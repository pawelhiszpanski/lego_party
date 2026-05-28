#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <math.h>

#define PORT               5000
#define MAX_CLIENTS        10
#define MAX_PLAYERS        4
#define MAX_COINS          6
#define ARENA_W            800
#define ARENA_H            600
#define PLAYER_SPEED       14
#define COIN_RADIUS        15
#define PLAYER_RADIUS      20
#define GAME_DURATION      30
#define HEARTBEAT_TIMEOUT  8
#define TICK_US            16667
#define VOTE_DURATION      10
#define END_TICKS          480
#define PONG_WIN_SCORE     3

#define PONG_W             800
#define PONG_H             600
#define PONG_PAD_W         14
#define PONG_PAD_H         88
#define PONG_BALL_R        10
#define PONG_PAD_SPEED     28
#define PONG_BALL_INIT     6.5f
#define PONG_BALL_MAX      28.0f
#define PONG_ACCEL         1.055f

#define BOMB_DURATION      45
#define BOMB_PASS_RADIUS   60
#define BOMB_MIN_HOLD      90   /* ticks before bomb can be passed again */

typedef enum {
    PHASE_LOBBY  = 0,
    PHASE_VOTING = 1,
    PHASE_COINS  = 2,
    PHASE_PONG   = 3,
    PHASE_ENDED  = 4,
    PHASE_BOMB   = 5
} GamePhase;

typedef struct {
    int  sock, active, is_display, player_id;
} Client;

typedef struct {
    int    active;
    char   name[32];
    float  x, y;
    int    score, color, team, vote;
    time_t last_ping;
    int    client_idx;
} Player;

typedef struct { float x, y; int active; } Coin;

typedef struct {
    float bx, by, vx, vy;
    float py0, py1;
    int   score0, score1, winner;
    float speed;
} PongState;

typedef struct {
    int holder;       /* player id holding the bomb, -1 = none */
    int time_left;    /* seconds remaining */
    int hold_ticks;   /* ticks current holder has held it */
    int exploded;     /* 1 when bomb went off */
} BombState;

static Client    clients[MAX_CLIENTS];
static Player    players[MAX_PLAYERS];
static Coin      coins[MAX_COINS];
static PongState pong;
static BombState bomb;
static GamePhase phase      = PHASE_LOBBY;
static int       time_left  = GAME_DURATION;
static int       vote_left  = VOTE_DURATION;
static int       next_color = 0;
static int       end_ticks  = 0;
static int       last_game  = 0;

static time_t    g_last_second = 0;

static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;

static const int   START_X[MAX_PLAYERS] = { 80, 720,  80, 720 };
static const int   START_Y[MAX_PLAYERS] = {100, 100, 500, 500 };
static const char *COLOR_NAMES[4] = {"red","blue","green","yellow"};

static void spawn_coin(int i) {
    coins[i].x = 60 + rand() % (ARENA_W - 120);
    coins[i].y = 60 + rand() % (ARENA_H - 120);
    coins[i].active = 1;
}

static void broadcast(const char *msg, int len) {
    for (int i = 0; i < MAX_CLIENTS; i++)
        if (clients[i].active) write(clients[i].sock, msg, len);
}

static void build_json(char *buf, int sz) {
    int p = 0, va = 0, vb = 0, vc = 0, vd = 0;
    int votes_arr[MAX_PLAYERS];
    for (int i = 0; i < MAX_PLAYERS; i++) {
        votes_arr[i] = players[i].active ? players[i].vote : -1;
        if (players[i].active) {
            if      (players[i].vote == 0) va++;
            else if (players[i].vote == 1) vb++;
            else if (players[i].vote == 2) vc++;
            else if (players[i].vote == 3) vd++;
        }
    }
    p += snprintf(buf+p, sz-p,
        "{\"phase\":%d,\"time_left\":%d,\"vote_left\":%d,"
        "\"last_game\":%d,\"va\":%d,\"vb\":%d,\"vc\":%d,\"vd\":%d,"
        "\"votes\":[%d,%d,%d,%d],\"players\":[",
        phase, time_left, vote_left, last_game,
        va, vb, vc, vd,
        votes_arr[0], votes_arr[1], votes_arr[2], votes_arr[3]);

    int first = 1;
    for (int i = 0; i < MAX_PLAYERS; i++) {
        if (!players[i].active) continue;
        if (!first) buf[p++] = ',';
        first = 0;
        p += snprintf(buf+p, sz-p,
            "{\"id\":%d,\"name\":\"%s\",\"x\":%.0f,\"y\":%.0f,"
            "\"score\":%d,\"color\":\"%s\",\"team\":%d}",
            i, players[i].name, players[i].x, players[i].y,
            players[i].score, COLOR_NAMES[players[i].color],
            players[i].team);
    }
    p += snprintf(buf+p, sz-p, "],\"coins\":[");
    first = 1;
    for (int i = 0; i < MAX_COINS; i++) {
        if (!coins[i].active) continue;
        if (!first) buf[p++] = ',';
        first = 0;
        p += snprintf(buf+p, sz-p,
            "{\"x\":%.0f,\"y\":%.0f}", coins[i].x, coins[i].y);
    }
    p += snprintf(buf+p, sz-p,
        "],\"pong\":{\"bx\":%.1f,\"by\":%.1f,"
        "\"py0\":%.1f,\"py1\":%.1f,"
        "\"s0\":%d,\"s1\":%d,\"win\":%d,\"spd\":%.1f},"
        "\"bomb\":{\"holder\":%d,\"time_left\":%d,\"exploded\":%d}}",
        pong.bx, pong.by, pong.py0, pong.py1,
        pong.score0, pong.score1, pong.winner, pong.speed,
        bomb.holder, bomb.time_left, bomb.exploded);
}

static void pong_reset_ball(int dir) {
    pong.bx    = PONG_W / 2.0f;
    pong.by    = PONG_H / 2.0f;
    pong.speed = PONG_BALL_INIT;
    float ang  = ((float)(rand() % 40) - 20.0f) * 3.14159f / 180.0f;
    pong.vx    = dir * pong.speed * cosf(ang);
    pong.vy    = pong.speed * sinf(ang);
}

static void pong_init(void) {
    pong.py0 = pong.py1 = PONG_H / 2.0f;
    pong.score0 = pong.score1 = 0;
    pong.winner = -1;
    int t = 0;
    for (int i = 0; i < MAX_PLAYERS; i++)
        if (players[i].active) players[i].team = t++ % 2;
    pong_reset_ball(1);
}

static void pong_tick(void) {
    if (pong.winner >= 0) return;

    pong.bx += pong.vx;
    pong.by += pong.vy;

    if (pong.by - PONG_BALL_R < 0) {
        pong.by = PONG_BALL_R;
        pong.vy = fabsf(pong.vy);
    }
    if (pong.by + PONG_BALL_R > PONG_H) {
        pong.by = PONG_H - PONG_BALL_R;
        pong.vy = -fabsf(pong.vy);
    }

    int px0 = PONG_PAD_W;
    if (pong.vx < 0 &&
        pong.bx - PONG_BALL_R <= px0 + PONG_PAD_W &&
        pong.bx - PONG_BALL_R >= px0 - 4 &&
        pong.by >= pong.py0 - PONG_PAD_H/2.0f - PONG_BALL_R &&
        pong.by <= pong.py0 + PONG_PAD_H/2.0f + PONG_BALL_R) {

        pong.speed *= PONG_ACCEL;
        if (pong.speed > PONG_BALL_MAX) pong.speed = PONG_BALL_MAX;

        float rel = (pong.by - pong.py0) / (PONG_PAD_H / 2.0f);
        float ang  = rel * 60.0f * 3.14159f / 180.0f;
        pong.vx    =  pong.speed * cosf(ang);
        pong.vy    =  pong.speed * sinf(ang);
        pong.bx    = px0 + PONG_PAD_W + PONG_BALL_R + 2;
    }

    int px1 = PONG_W - PONG_PAD_W * 2;
    if (pong.vx > 0 &&
        pong.bx + PONG_BALL_R >= px1 &&
        pong.bx + PONG_BALL_R <= px1 + PONG_PAD_W + 4 &&
        pong.by >= pong.py1 - PONG_PAD_H/2.0f - PONG_BALL_R &&
        pong.by <= pong.py1 + PONG_PAD_H/2.0f + PONG_BALL_R) {

        pong.speed *= PONG_ACCEL;
        if (pong.speed > PONG_BALL_MAX) pong.speed = PONG_BALL_MAX;

        float rel = (pong.by - pong.py1) / (PONG_PAD_H / 2.0f);
        float ang  = rel * 60.0f * 3.14159f / 180.0f;
        pong.vx    = -pong.speed * cosf(ang);
        pong.vy    =  pong.speed * sinf(ang);
        pong.bx    = px1 - PONG_BALL_R - 2;
    }

    if (pong.bx < 0) {
        pong.score1++;
        fprintf(stderr, "[PONG] 1: %d\n", pong.score1);
        if (pong.score1 >= PONG_WIN_SCORE) { pong.winner = 1; return; }
        pong_reset_ball(1);
    }
    if (pong.bx > PONG_W) {
        pong.score0++;
        fprintf(stderr, "[PONG] 0: %d\n", pong.score0);
        if (pong.score0 >= PONG_WIN_SCORE) { pong.winner = 0; return; }
        pong_reset_ball(-1);
    }
}

static void bomb_init(void) {
    bomb.exploded  = 0;
    bomb.time_left = BOMB_DURATION;
    bomb.hold_ticks = 0;
    /* pick random starting holder */
    int cnt = 0, ids[MAX_PLAYERS];
    for (int i = 0; i < MAX_PLAYERS; i++)
        if (players[i].active) ids[cnt++] = i;
    bomb.holder = cnt > 0 ? ids[rand() % cnt] : 0;
    for (int i = 0; i < MAX_PLAYERS; i++)
        if (players[i].active) {
            players[i].x = START_X[i];
            players[i].y = START_Y[i];
            players[i].score = 0;
        }
    fprintf(stderr, "[BOMB] Start, holder=%d\n", bomb.holder);
}

static void bomb_tick(void) {
    if (bomb.exploded) return;
    bomb.hold_ticks++;

    /* try to pass: check proximity to other players */
    if (bomb.holder >= 0 && bomb.hold_ticks >= BOMB_MIN_HOLD) {
        float hx = players[bomb.holder].x;
        float hy = players[bomb.holder].y;
        float best_dist = 1e9f;
        int   best_pid  = -1;
        for (int i = 0; i < MAX_PLAYERS; i++) {
            if (i == bomb.holder || !players[i].active) continue;
            float dx = players[i].x - hx;
            float dy = players[i].y - hy;
            float d  = sqrtf(dx*dx + dy*dy);
            if (d < BOMB_PASS_RADIUS && d < best_dist) {
                best_dist = d;
                best_pid  = i;
            }
        }
        if (best_pid >= 0) {
            fprintf(stderr, "[BOMB] Pass %d -> %d\n", bomb.holder, best_pid);
            bomb.holder     = best_pid;
            bomb.hold_ticks = 0;
        }
    }
}

static void resolve_vote(void) {
    int va = 0, vb = 0, vc = 0, vd = 0;
    for (int i = 0; i < MAX_PLAYERS; i++) {
        if (!players[i].active) continue;
        if      (players[i].vote == 0) va++;
        else if (players[i].vote == 1) vb++;
        else if (players[i].vote == 2) vc++;
        else if (players[i].vote == 3) vd++;
    }

    /* pick highest; ties broken randomly */
    int max_v = va;
    if (vb > max_v) max_v = vb;
    if (vc > max_v) max_v = vc;
    if (vd > max_v) max_v = vd;

    int winners[4], nw = 0;
    if (va == max_v) winners[nw++] = 0;
    if (vb == max_v) winners[nw++] = 1;
    if (vc == max_v) winners[nw++] = 2;
    if (vd == max_v) winners[nw++] = 3;

    int chosen_mode = winners[rand() % nw];
    if (chosen_mode == 3) chosen_mode = rand() % 3; /* D = random game */

    last_game = chosen_mode;
    fprintf(stderr, "[VOTE] A=%d B=%d C=%d D=%d -> game %d\n",
            va, vb, vc, vd, chosen_mode);

    g_last_second = time(NULL);

    if (chosen_mode == 0) {
        phase     = PHASE_COINS;
        time_left = GAME_DURATION;
        for (int i = 0; i < MAX_PLAYERS; i++) players[i].score = 0;
        for (int i = 0; i < MAX_COINS;   i++) spawn_coin(i);
    } else if (chosen_mode == 1) {
        phase = PHASE_PONG;
        for (int i = 0; i < MAX_PLAYERS; i++) players[i].score = 0;
        pong_init();
    } else {
        phase = PHASE_BOMB;
        bomb_init();
    }
}

static void reset_to_lobby(void) {
    phase     = PHASE_LOBBY;
    time_left = GAME_DURATION;
    vote_left = VOTE_DURATION;
    for (int i = 0; i < MAX_PLAYERS; i++) {
        players[i].score = 0;
        players[i].vote  = -1;
        if (players[i].active) {
            players[i].x = START_X[i];
            players[i].y = START_Y[i];
        }
    }
    g_last_second = time(NULL);
    fprintf(stderr, "[SERVER] Lobby\n");
}

static void *game_loop(void *arg) {
    (void)arg;
    srand((unsigned)time(NULL));
    for (int i = 0; i < MAX_COINS; i++) spawn_coin(i);
    g_last_second = time(NULL);

    for (;;) {
        usleep(TICK_US);
        pthread_mutex_lock(&mutex);

        time_t now = time(NULL);

        if (phase == PHASE_VOTING && now > g_last_second) {
            vote_left -= (int)(now - g_last_second);
            g_last_second = now;
            if (vote_left <= 0) { vote_left = 0; resolve_vote(); }
        }

        if (phase == PHASE_COINS && now > g_last_second) {
            time_left -= (int)(now - g_last_second);
            g_last_second = now;
            if (time_left <= 0) {
                time_left = 0; phase = PHASE_ENDED; end_ticks = 0;
                fprintf(stderr, "[COINS] Koniec!\n");
            }
            for (int i = 0; i < MAX_PLAYERS; i++)
                if (players[i].active &&
                    (now - players[i].last_ping) > HEARTBEAT_TIMEOUT)
                    players[i].active = 0;
        }

        if (phase == PHASE_PONG) {
            pong_tick();
            if (pong.winner >= 0) {
                phase = PHASE_ENDED; end_ticks = 0;
                fprintf(stderr, "[PONG] Team %d wins!\n", pong.winner);
            }
            for (int i = 0; i < MAX_PLAYERS; i++)
                if (players[i].active &&
                    (now - players[i].last_ping) > HEARTBEAT_TIMEOUT)
                    players[i].active = 0;
        }

        if (phase == PHASE_BOMB) {
            bomb_tick();
            if (now > g_last_second) {
                bomb.time_left -= (int)(now - g_last_second);
                g_last_second = now;
                if (bomb.time_left <= 0) {
                    bomb.time_left = 0;
                    bomb.exploded  = 1;
                    /* loser is the holder */
                    for (int i = 0; i < MAX_PLAYERS; i++)
                        if (players[i].active && i != bomb.holder)
                            players[i].score = 1;
                    fprintf(stderr, "[BOMB] Exploded on %d!\n", bomb.holder);
                    phase = PHASE_ENDED; end_ticks = 0;
                }
            }
            for (int i = 0; i < MAX_PLAYERS; i++)
                if (players[i].active &&
                    (now - players[i].last_ping) > HEARTBEAT_TIMEOUT)
                    players[i].active = 0;
        }

        if (phase == PHASE_ENDED) {
            if (++end_ticks >= END_TICKS) reset_to_lobby();
        }

        char json[4096], msg[4400];
        build_json(json, sizeof(json));
        int ml = snprintf(msg, sizeof(msg), "STATE:%s\n", json);
        broadcast(msg, ml);

        pthread_mutex_unlock(&mutex);
    }
    return NULL;
}

static void clamp_player(int pid) {
    float r = PLAYER_RADIUS;
    if (players[pid].x < r)           players[pid].x = r;
    if (players[pid].x > ARENA_W - r) players[pid].x = ARENA_W - r;
    if (players[pid].y < r)           players[pid].y = r;
    if (players[pid].y > ARENA_H - r) players[pid].y = ARENA_H - r;
}

static void check_coins(int pid) {
    float cap = COIN_RADIUS + PLAYER_RADIUS;
    for (int i = 0; i < MAX_COINS; i++) {
        if (!coins[i].active) continue;
        float dx = players[pid].x - coins[i].x;
        float dy = players[pid].y - coins[i].y;
        if (dx*dx + dy*dy < cap*cap) { players[pid].score++; spawn_coin(i); }
    }
}

static void apply_action(int pid, const char *dir) {
    if (!players[pid].active) return;
    float spd = PLAYER_SPEED;
    int left  = (strchr(dir,'L') != NULL);
    int right = (strchr(dir,'R') != NULL);
    int up    = (strchr(dir,'U') != NULL);
    int down  = (strchr(dir,'D') != NULL);

    float norm = (left+right > 0 && up+down > 0) ? 0.7071f : 1.0f;

    if (left)  players[pid].x -= spd * norm;
    if (right) players[pid].x += spd * norm;
    if (up)    players[pid].y -= spd * norm;
    if (down)  players[pid].y += spd * norm;

    clamp_player(pid);
    check_coins(pid);
}

static void *connection_handler(void *arg) {
    int ci   = *(int *)arg; free(arg);
    int sock = clients[ci].sock;
    char buf[2048], line[1024];
    int  buf_len = 0;

    while (1) {
        int n = recv(sock, buf + buf_len, sizeof(buf) - buf_len - 1, 0);
        if (n <= 0) break;
        buf_len += n;
        buf[buf_len] = '\0';

        char *start = buf, *nl;
        while ((nl = strchr(start, '\n')) != NULL) {
            int ll = (int)(nl - start);
            strncpy(line, start, ll);
            line[ll] = '\0';
            pthread_mutex_lock(&mutex);

            if (strncmp(line, "JOIN:", 5) == 0) {
                if (phase != PHASE_LOBBY) {
                    write(sock, "ERROR:Gra w toku\n", 17);
                } else {
                    int pid = -1;
                    for (int i = 0; i < MAX_PLAYERS; i++)
                        if (!players[i].active) { pid = i; break; }
                    if (pid < 0) {
                        write(sock, "ERROR:Brak miejsca\n", 19);
                    } else {
                        strncpy(players[pid].name, line+5, 31);
                        players[pid].name[31]   = '\0';
                        players[pid].x          = START_X[pid];
                        players[pid].y          = START_Y[pid];
                        players[pid].score      = 0;
                        players[pid].vote       = -1;
                        players[pid].color      = next_color++ % 4;
                        players[pid].active     = 1;
                        players[pid].last_ping  = time(NULL);
                        players[pid].client_idx = ci;
                        clients[ci].player_id   = pid;
                        char w[32];
                        int wl = snprintf(w, sizeof(w), "WELCOME:%d\n", pid);
                        write(sock, w, wl);
                        fprintf(stderr, "[JOIN] Player %d: %s\n",
                                pid, players[pid].name);
                    }
                }

            } else if (strcmp(line, "START") == 0) {
                if (phase == PHASE_LOBBY) {
                    int cnt = 0;
                    for (int i = 0; i < MAX_PLAYERS; i++)
                        if (players[i].active) cnt++;
                    if (cnt >= 2) {
                        phase         = PHASE_VOTING;
                        vote_left     = VOTE_DURATION;
                        g_last_second = time(NULL);
                        for (int i = 0; i < MAX_PLAYERS; i++)
                            players[i].vote = -1;
                        fprintf(stderr, "[VOTE] Start\n");
                    } else {
                        write(sock, "ERROR:Za malo graczy\n", 21);
                    }
                }

            } else if (strncmp(line, "VOTE:", 5) == 0) {
                int pid = clients[ci].player_id;
                if (pid >= 0 && players[pid].active && phase == PHASE_VOTING) {
                    char v = line[5];
                    players[pid].vote = (v=='A') ? 0 : (v=='B') ? 1 : (v=='C') ? 2 : 3;
                    fprintf(stderr, "[VOTE] Player %d: %c\n", pid, v);
                }

            } else if (strncmp(line, "ACTION:", 7) == 0) {
                int pid = clients[ci].player_id;
                if (pid < 0 || !players[pid].active) goto done;
                players[pid].last_ping = time(NULL);

                if (phase == PHASE_COINS) {
                    apply_action(pid, line + 7);
                } else if (phase == PHASE_PONG && pong.winner < 0) {
                    int team   = players[pid].team;
                    float *py  = (team == 0) ? &pong.py0 : &pong.py1;
                    float half = PONG_PAD_H / 2.0f;
                    if (strchr(line+7,'U')) *py -= PONG_PAD_SPEED;
                    if (strchr(line+7,'D')) *py += PONG_PAD_SPEED;
                    if (*py - half < 0)      *py = half;
                    if (*py + half > PONG_H) *py = PONG_H - half;
                } else if (phase == PHASE_BOMB && !bomb.exploded) {
                    apply_action(pid, line + 7);
                }

            } else if (strcmp(line, "PING") == 0) {
                int pid = clients[ci].player_id;
                if (pid >= 0 && players[pid].active)
                    players[pid].last_ping = time(NULL);
                write(sock, "PONG\n", 5);

            } else if (strcmp(line, "DISPLAY") == 0) {
                clients[ci].is_display = 1;
                write(sock, "DISPLAY_OK\n", 11);
                fprintf(stderr, "[DISPLAY] Connected\n");
            }

            done:
            pthread_mutex_unlock(&mutex);
            start = nl + 1;
        }
        buf_len = (int)((buf + buf_len) - start);
        memmove(buf, start, buf_len);
    }

    pthread_mutex_lock(&mutex);
    int pid = clients[ci].player_id;
    if (pid >= 0 && pid < MAX_PLAYERS) {
        players[pid].active = 0;
        fprintf(stderr, "[DISC] Player %d\n", pid);
    }
    clients[ci].active = 0; clients[ci].player_id = -1;
    pthread_mutex_unlock(&mutex);
    close(sock);
    return NULL;
}

int main(void) {
    int listenfd; struct sockaddr_in serv_addr; pthread_t tid;
    memset(clients, 0, sizeof(clients));
    memset(players, 0, sizeof(players));
    for (int i = 0; i < MAX_CLIENTS; i++) clients[i].player_id = -1;

    listenfd = socket(AF_INET, SOCK_STREAM, 0);
    if (listenfd < 0) { perror("socket"); return 1; }
    int opt = 1;
    setsockopt(listenfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family      = AF_INET;
    serv_addr.sin_addr.s_addr = htonl(INADDR_ANY);
    serv_addr.sin_port        = htons(PORT);
    if (bind(listenfd, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) < 0) {
        perror("bind"); return 1;
    }
    listen(listenfd, 10);
    fprintf(stderr, "[SERVER] Port %d\n", PORT);

    pthread_create(&tid, NULL, game_loop, NULL);
    pthread_detach(tid);

    for (;;) {
        int connfd = accept(listenfd, NULL, NULL);
        if (connfd < 0) continue;
        pthread_mutex_lock(&mutex);
        int slot = -1;
        for (int i = 0; i < MAX_CLIENTS; i++)
            if (!clients[i].active) { slot = i; break; }
        if (slot >= 0) {
            clients[slot].sock      = connfd;
            clients[slot].active    = 1;
            clients[slot].is_display = 0;
            clients[slot].player_id = -1;
            pthread_mutex_unlock(&mutex);
            int *a = malloc(sizeof(int)); *a = slot;
            pthread_create(&tid, NULL, connection_handler, a);
            pthread_detach(tid);
        } else {
            pthread_mutex_unlock(&mutex);
            close(connfd);
        }
    }
    return 0;
}