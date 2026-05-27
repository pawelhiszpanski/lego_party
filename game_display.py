#!/usr/bin/env python3
"""
game_display.py v3
Fazy: 0=LOBBY  1=VOTING  2=COINS  3=PONG  4=ENDED
"""

import pygame, socket, threading, json, sys, time, math

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000
ARENA_W, ARENA_H = 800, 600
PANEL_W = 260
WIN_W   = ARENA_W + PANEL_W
WIN_H   = ARENA_H
FPS     = 60

PAD_W, PAD_H = 14, 88
BALL_R        = 10
PAD_X0        = PAD_W
PAD_X1        = ARENA_W - PAD_W * 2

C = {
    'bg':       (18,  18,  28),
    'arena':    (28,  28,  45),
    'grid':     (38,  38,  58),
    'border':   (10,  10,  20),
    'panel':    (22,  22,  34),
    'white':    (255, 255, 255),
    'dim':      (100, 100, 130),
    'gold':     (255, 210,  30),
    'green':    ( 55, 210,  85),
    'red':      (220,  55,  55),
    'row_hi':   ( 55,  55,  80),
    'row_lo':   ( 36,  36,  54),
    'p_red':    (220,  60,  60),
    'p_blue':   ( 55, 115, 220),
    'p_green':  ( 55, 200,  75),
    'p_yellow': (240, 200,  35),
    'vote_a':   ( 26, 122, 170),
    'vote_b':   (138,  26, 176),
    'vote_c':   (176, 112,  16),
    'pong_bg':  (  8,   8,  18),
    'pad0':     ( 55, 115, 220),
    'pad1':     (220,  60,  60),
    'mid_line': ( 40,  40,  65),
}

PLAYER_RGB = {
    'red': C['p_red'], 'blue': C['p_blue'],
    'green': C['p_green'], 'yellow': C['p_yellow'],
}
PHASE_LBL = ['LOBBY', 'GŁOSOWANIE', 'ZBIERANIE MONET', 'PONG', 'KONIEC']
PHASE_COL = [C['gold'], C['vote_c'], C['green'], C['vote_b'], C['red']]
PLAYER_R  = 22


class GameDisplay:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption('Party Game v3')
        self.clock  = pygame.time.Clock()
        self.tick   = 0

        self.state = {
            'phase': 0, 'time_left': 30, 'vote_left': 10,
            'va': 0, 'vb': 0, 'vc': 0, 'votes': [-1,-1,-1,-1],
            'last_game': 0, 'players': [], 'coins': [],
            'pong': {'bx': 400, 'by': 300, 'py0': 300, 'py1': 300,
                     's0': 0, 's1': 0, 'win': -1, 'spd': 9.0},
        }
        self.lock      = threading.Lock()
        self.connected = False

        self._ball_x = 400.0
        self._ball_y = 300.0

        self.f_xl = pygame.font.SysFont('Arial', 52, bold=True)
        self.f_lg = pygame.font.SysFont('Arial', 36, bold=True)
        self.f_md = pygame.font.SysFont('Arial', 26)
        self.f_sm = pygame.font.SysFont('Arial', 18)
        self.f_xs = pygame.font.SysFont('Arial', 14)

        self._start_network()

    def _start_network(self):
        def run():
            while True:
                try:
                    sock = socket.socket()
                    sock.connect((SERVER_HOST, SERVER_PORT))
                    sock.send(b'DISPLAY\n')
                    self.connected = True
                    buf = b''
                    while True:
                        data = sock.recv(8192)
                        if not data:
                            break
                        buf += data
                        while b'\n' in buf:
                            line, buf = buf.split(b'\n', 1)
                            msg = line.decode('utf-8', errors='replace')
                            if msg.startswith('STATE:'):
                                try:
                                    with self.lock:
                                        self.state = json.loads(msg[6:])
                                except Exception:
                                    pass
                    sock.close()
                except Exception as e:
                    print(f'[DISPLAY] {e}, retry za 2s')
                finally:
                    self.connected = False
                    time.sleep(2)
        threading.Thread(target=run, daemon=True).start()

    def _draw_arena(self):
        pygame.draw.rect(self.screen, C['arena'], (0, 0, ARENA_W, ARENA_H))
        for x in range(0, ARENA_W, 80):
            pygame.draw.line(self.screen, C['grid'], (x, 0), (x, ARENA_H))
        for y in range(0, ARENA_H, 80):
            pygame.draw.line(self.screen, C['grid'], (0, y), (ARENA_W, y))
        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)

    def _draw_coin(self, x, y):
        ix, iy = int(x), int(y)
        r = 15
        pygame.draw.circle(self.screen, (0, 0, 0), (ix+2, iy+3), r)
        pygame.draw.circle(self.screen, C['gold'], (ix, iy), r)
        pygame.draw.circle(self.screen, (255, 255, 180), (ix-4, iy-4), r//3)
        pygame.draw.circle(self.screen, (170, 140, 5), (ix, iy), r, 2)
        lbl = self.f_xs.render('$', True, (110, 80, 0))
        self.screen.blit(lbl, (ix - lbl.get_width()//2, iy - lbl.get_height()//2))

    def _draw_player(self, p):
        x, y  = int(p['x']), int(p['y'])
        color = PLAYER_RGB.get(p.get('color', 'red'), C['white'])
        name  = p.get('name', '?')[:10]
        sh = pygame.Surface((PLAYER_R*2+6, PLAYER_R*2+6), pygame.SRCALPHA)
        pygame.draw.circle(sh, (0, 0, 0, 80), (PLAYER_R+3, PLAYER_R+5), PLAYER_R)
        self.screen.blit(sh, (x - PLAYER_R, y - PLAYER_R))
        pygame.draw.circle(self.screen, color, (x, y), PLAYER_R)
        pygame.draw.circle(self.screen, C['white'], (x, y), PLAYER_R, 2)
        pygame.draw.circle(self.screen, C['white'],
                           (x - PLAYER_R//3, y - PLAYER_R//3), PLAYER_R//4)
        ns = self.f_sm.render(name, True, C['white'])
        nx = x - ns.get_width()//2
        ny = y - PLAYER_R - 22
        sh2 = self.f_sm.render(name, True, C['border'])
        self.screen.blit(sh2, (nx+1, ny+1))
        self.screen.blit(ns, (nx, ny))
        sc = self.f_xs.render(str(p.get('score', 0)), True, C['gold'])
        self.screen.blit(sc, (x - sc.get_width()//2, ny - 16))

    def _draw_pong(self, state):
        pg  = state.get('pong', {})
        bx  = float(pg.get('bx', 400))
        by  = float(pg.get('by', 300))
        py0 = float(pg.get('py0', 300))
        py1 = float(pg.get('py1', 300))
        s0  = pg.get('s0', 0)
        s1  = pg.get('s1', 0)
        win = pg.get('win', -1)
        spd = float(pg.get('spd', 9.0))

        self._ball_x += (bx - self._ball_x) * 0.55
        self._ball_y += (by - self._ball_y) * 0.55
        ibx = int(self._ball_x)
        iby = int(self._ball_y)

        pygame.draw.rect(self.screen, C['pong_bg'], (0, 0, ARENA_W, ARENA_H))

        for y in range(8, ARENA_H, 24):
            pygame.draw.rect(self.screen, C['mid_line'],
                             (ARENA_W//2 - 3, y, 6, 14))

        s0s = self.f_xl.render(str(s0), True, C['pad0'])
        s1s = self.f_xl.render(str(s1), True, C['pad1'])
        self.screen.blit(s0s, (ARENA_W//4  - s0s.get_width()//2, 18))
        self.screen.blit(s1s, (3*ARENA_W//4 - s1s.get_width()//2, 18))

        info = self.f_xs.render('PIERWSZE DO 3 PKT', True, C['dim'])
        self.screen.blit(info, (ARENA_W//2 - info.get_width()//2, 72))

        spd_s = self.f_xs.render(f'prędkość: {spd:.0f}', True, C['dim'])
        self.screen.blit(spd_s, (ARENA_W//2 - spd_s.get_width()//2, ARENA_H - 22))

        pygame.draw.rect(self.screen, C['pad0'],
                         (PAD_X0, int(py0) - PAD_H//2, PAD_W, PAD_H),
                         border_radius=5)
        pygame.draw.rect(self.screen, C['pad1'],
                         (PAD_X1, int(py1) - PAD_H//2, PAD_W, PAD_H),
                         border_radius=5)

        glow0 = pygame.Surface((40, PAD_H + 20), pygame.SRCALPHA)
        glow0.fill((0, 0, 0, 0))
        pygame.draw.rect(glow0, (*C['pad0'], 40), (0, 0, 40, PAD_H + 20), border_radius=8)
        self.screen.blit(glow0, (PAD_X0 - 14, int(py0) - PAD_H//2 - 10))

        glow1 = pygame.Surface((40, PAD_H + 20), pygame.SRCALPHA)
        glow1.fill((0, 0, 0, 0))
        pygame.draw.rect(glow1, (*C['pad1'], 40), (0, 0, 40, PAD_H + 20), border_radius=8)
        self.screen.blit(glow1, (PAD_X1 - 12, int(py1) - PAD_H//2 - 10))

        pygame.draw.circle(self.screen, (160, 160, 160), (ibx+2, iby+2), BALL_R)
        pygame.draw.circle(self.screen, C['white'], (ibx, iby), BALL_R)
        pygame.draw.circle(self.screen, (220, 220, 255), (ibx-3, iby-3), BALL_R//3)

        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)

        if win >= 0:
            col = C['pad0'] if win == 0 else C['pad1']
            ov  = self.f_xl.render(f'Drużyna {win} wygrywa!', True, col)
            self.screen.blit(ov, (ARENA_W//2 - ov.get_width()//2, ARENA_H//2 - 30))

    def _draw_voting(self, state):
        pygame.draw.rect(self.screen, C['arena'], (0, 0, ARENA_W, ARENA_H))
        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)

        title = self.f_lg.render('WYBIERZ GRĘ', True, C['gold'])
        self.screen.blit(title, (ARENA_W//2 - title.get_width()//2, 40))

        vl  = state.get('vote_left', 10)
        tc  = C['red'] if vl <= 3 else C['white']
        ts  = self.f_xl.render(f'{vl}s', True, tc)
        self.screen.blit(ts, (ARENA_W//2 - ts.get_width()//2, 90))

        va = state.get('va', 0)
        vb = state.get('vb', 0)
        vc = state.get('vc', 0)

        options = [
            ('A', 'Monety 🪙', va, C['vote_a']),
            ('B', 'Pong 🏓',   vb, C['vote_b']),
            ('C', 'Losowo 🎲', vc, C['vote_c']),
        ]
        bw, bh, gap = 190, 130, 20
        total_w = 3 * bw + 2 * gap
        bx0 = ARENA_W//2 - total_w//2

        for i, (ltr, name, cnt, col) in enumerate(options):
            bx = bx0 + i * (bw + gap)
            by = 210
            pygame.draw.rect(self.screen, col,
                             (bx, by, bw, bh), border_radius=18)
            inner = pygame.Surface((bw-4, bh-4), pygame.SRCALPHA)
            inner.fill((*col, 100))
            self.screen.blit(inner, (bx+2, by+2))

            ls = self.f_xl.render(ltr, True, C['white'])
            ns = self.f_md.render(name[3:] if len(name)>3 else name, True, C['white'])
            cs = self.f_lg.render(str(cnt), True, C['white'])

            self.screen.blit(ls, (bx + bw//2 - ls.get_width()//2, by + 10))
            self.screen.blit(ns, (bx + bw//2 - ns.get_width()//2, by + 60))
            self.screen.blit(cs, (bx + bw//2 - cs.get_width()//2, by + 92))

        players = state.get('players', [])
        votes   = state.get('votes', [-1,-1,-1,-1])
        VMAP = {-1: '?', 0: 'A', 1: 'B', 2: 'C'}
        VCOL = {-1: C['dim'], 0: C['vote_a'], 1: C['vote_b'], 2: C['vote_c']}
        y0 = 380
        row_w_total = sum(
            self.f_md.size(p.get('name','?') + ' → ' + VMAP[votes[p['id']] if p['id']<4 else -1])[0]
            for p in players
        ) if players else 0

        for p in players:
            pid = p.get('id', 0)
            v   = votes[pid] if pid < 4 else -1
            pc  = PLAYER_RGB.get(p.get('color', 'red'), C['white'])
            nm  = self.f_md.render(p.get('name', '?'), True, pc)
            ar  = self.f_md.render(' → ', True, C['dim'])
            vs  = self.f_md.render(VMAP[v], True, VCOL[v])
            rw  = nm.get_width() + ar.get_width() + vs.get_width()
            rx  = ARENA_W//2 - rw//2
            self.screen.blit(nm, (rx, y0))
            self.screen.blit(ar, (rx + nm.get_width(), y0))
            self.screen.blit(vs, (rx + nm.get_width() + ar.get_width(), y0))
            y0 += 34

    def _draw_lobby(self, state):
        self._draw_arena()
        players = state.get('players', [])
        cnt = len(players)

        lbl1 = self.f_lg.render('LOBBY', True, C['gold'])
        lbl2 = self.f_md.render(f'Graczy: {cnt} / 4', True, C['white'])
        if cnt >= 2:
            lbl3 = self.f_sm.render('Kliknij  START GAME  na telefonie', True, C['green'])
        else:
            lbl3 = self.f_sm.render('Potrzeba minimum 2 graczy…', True, C['dim'])

        self.screen.blit(lbl1, (ARENA_W//2 - lbl1.get_width()//2, ARENA_H//2 - 70))
        self.screen.blit(lbl2, (ARENA_W//2 - lbl2.get_width()//2, ARENA_H//2 - 15))
        self.screen.blit(lbl3, (ARENA_W//2 - lbl3.get_width()//2, ARENA_H//2 + 24))

        y0 = ARENA_H//2 + 68
        for p in players:
            col = PLAYER_RGB.get(p.get('color', 'red'), C['white'])
            ns  = self.f_sm.render(f"● {p.get('name','?')}", True, col)
            self.screen.blit(ns, (ARENA_W//2 - ns.get_width()//2, y0))
            y0 += 26

    def _draw_panel(self, state):
        px = ARENA_W
        pygame.draw.rect(self.screen, C['panel'], (px, 0, PANEL_W, WIN_H))
        pygame.draw.line(self.screen, C['border'], (px, 0), (px, WIN_H), 2)

        phase   = state.get('phase', 0)
        players = sorted(state.get('players', []), key=lambda p: -p.get('score', 0))

        cy = 18
        t1 = self.f_lg.render('🎮 PARTY', True, C['gold'])
        t2 = self.f_xs.render('GAME  v3', True, C['dim'])
        self.screen.blit(t1, (px + PANEL_W//2 - t1.get_width()//2, cy)); cy += 42
        self.screen.blit(t2, (px + PANEL_W//2 - t2.get_width()//2, cy)); cy += 22

        ph_s = self.f_sm.render(PHASE_LBL[phase], True, PHASE_COL[phase])
        self.screen.blit(ph_s, (px + PANEL_W//2 - ph_s.get_width()//2, cy)); cy += 28

        if phase == 2:
            tl = state.get('time_left', 0)
            tc = C['red'] if tl <= 8 else C['white']
            ts = self.f_xl.render(f'{tl}s', True, tc)
            self.screen.blit(ts, (px + PANEL_W//2 - ts.get_width()//2, cy))
        cy += 60

        pygame.draw.line(self.screen, C['border'],
                         (px+10, cy), (px+PANEL_W-10, cy)); cy += 10

        sc_l = self.f_sm.render('WYNIKI', True, C['dim'])
        self.screen.blit(sc_l, (px + PANEL_W//2 - sc_l.get_width()//2, cy)); cy += 22

        rnk = ['1.','2.','3.','4.']
        for i, p in enumerate(players):
            col = PLAYER_RGB.get(p.get('color', 'red'), C['white'])
            bg  = C['row_hi'] if i == 0 else C['row_lo']
            pygame.draw.rect(self.screen, bg,
                             (px+8, cy, PANEL_W-16, 38), border_radius=6)
            pygame.draw.rect(self.screen, col,
                             (px+8, cy, 5, 38), border_radius=3)
            rk = self.f_sm.render(rnk[i] if i < 4 else f'{i+1}.', True, C['dim'])
            self.screen.blit(rk, (px+16, cy+10))
            nm = self.f_sm.render(p.get('name','?')[:12], True, C['white'])
            self.screen.blit(nm, (px+36, cy+10))
            sc = self.f_md.render(str(p.get('score', 0)), True, C['gold'])
            self.screen.blit(sc, (px+PANEL_W-18-sc.get_width(), cy+8))
            cy += 46

        ok  = self.connected
        st  = self.f_xs.render('Połączono ✓' if ok else 'Rozłączono…',
                                True, C['green'] if ok else C['red'])
        self.screen.blit(st, (px + PANEL_W//2 - st.get_width()//2, WIN_H - 20))

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()

            self.tick += 1
            self.screen.fill(C['bg'])

            with self.lock:
                state = dict(self.state)

            phase = state.get('phase', 0)

            if phase == 0:    # LOBBY
                self._draw_lobby(state)
            elif phase == 1:  # VOTING
                self._draw_voting(state)
            elif phase == 2:  # COINS
                self._draw_arena()
                for coin in state.get('coins', []):
                    self._draw_coin(coin['x'], coin['y'])
                for p in state.get('players', []):
                    self._draw_player(p)
            elif phase == 3:  # PONG
                self._draw_pong(state)
            elif phase == 4:  # ENDED
                if state.get('last_game', 0) == 1:
                    self._draw_pong(state)
                else:
                    self._draw_arena()
                    for p in state.get('players', []):
                        self._draw_player(p)
                players = sorted(state.get('players', []),
                                 key=lambda x: -x.get('score', 0))
                if players:
                    winner = players[0]
                    wc  = PLAYER_RGB.get(winner.get('color','red'), C['white'])
                    ov  = self.f_xl.render('KONIEC!', True, C['gold'])
                    wn  = self.f_lg.render(f'{winner["name"]} wygrywa!', True, wc)
                    self.screen.blit(ov,
                        (ARENA_W//2 - ov.get_width()//2, ARENA_H//2 - 60))
                    self.screen.blit(wn,
                        (ARENA_W//2 - wn.get_width()//2, ARENA_H//2))

            self._draw_panel(state)
            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == '__main__':
    print(f'[DISPLAY] Łączenie z {SERVER_HOST}:{SERVER_PORT}…')
    GameDisplay().run()