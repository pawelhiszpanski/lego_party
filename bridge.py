#!/usr/bin/env python3
"""
bridge.py  –  Multi-room WebSocket game server.

Each room is identified by a 4-digit PIN.  Players create or join rooms
via WebSocket; the pygame display connects via TCP on port 5000 using the
same PIN.

NOTE: server.c / game_server are no longer used.
"""
import threading, socket, os, time, json, math, random
from flask import Flask, send_from_directory
from flask_sock import Sock

BRIDGE_PORT  = 8080
DISPLAY_PORT = 5000
STATIC_DIR   = os.path.join(os.path.dirname(__file__), 'static')

app  = Flask(__name__)
sock = Sock(app)

ARENA_W, ARENA_H  = 800, 600
PLAYER_SPEED      = 14
PLAYER_RADIUS     = 20
COIN_RADIUS       = 15
MAX_COINS         = 6
GAME_DURATION     = 30
VOTE_DURATION     = 10
END_TICKS         = 480       # ticks before returning to lobby (~8 s)
PONG_H            = 600
PONG_PAD_H        = 88
PONG_PAD_SPEED    = 28
PONG_BALL_INIT    = 6.5
PONG_BALL_MAX     = 28.0
PONG_ACCEL        = 1.055
PONG_WIN_SCORE    = 3
BOMB_PASS_RADIUS  = 60
BOMB_MIN_HOLD     = 90
HEARTBEAT_TIMEOUT = 8.0

PHASE_LOBBY  = 0
PHASE_VOTING = 1
PHASE_COINS  = 2
PHASE_PONG   = 3
PHASE_ENDED  = 4
PHASE_BOMB   = 5

COLOR_NAMES = ['red', 'blue', 'green', 'yellow']
START_X     = [80, 720, 80, 720]
START_Y     = [100, 100, 500, 500]


class WSClient:
    def __init__(self, ws):
        self.ws        = ws
        self._lock     = threading.Lock()
        self.alive     = True
        self.player_id = -1

    def send(self, msg: str):
        with self._lock:
            if not self.alive: return
            try:
                self.ws.send(msg)
            except Exception:
                self.alive = False


class TCPClient:
    def __init__(self, conn):
        self.conn  = conn
        self._lock = threading.Lock()
        self.alive = True

    def send(self, msg: str):
        with self._lock:
            if not self.alive: return
            try:
                self.conn.sendall((msg + '\n').encode())
            except Exception:
                self.alive = False
                try: self.conn.close()
                except Exception: pass


class Room:
    MAX_PLAYERS = 4

    def __init__(self, pin: str):
        self.pin        = pin
        self._lock      = threading.Lock()
        self._clients: list = []
        self._tick_n    = 0
        self._next_color = 0

        self._players: list = [None] * self.MAX_PLAYERS
        self._coins: list   = [self._rand_coin() for _ in range(MAX_COINS)]

        self._phase      = PHASE_LOBBY
        self._time_left  = GAME_DURATION
        self._vote_left  = VOTE_DURATION
        self._end_ticks  = 0
        self._last_game  = 0
        self._last_sec   = time.time()

        self._pong = self._mk_pong()
        self._bomb = self._mk_bomb()


    def add_client(self, c):
        with self._lock:
            self._clients.append(c)

    def remove_client(self, c):
        with self._lock:
            try: self._clients.remove(c)
            except ValueError: pass

    def add_player(self, name: str) -> int | None:
        with self._lock:
            if self._phase != PHASE_LOBBY:
                return None
            for pid in range(self.MAX_PLAYERS):
                p = self._players[pid]
                if p is None or not p['active']:
                    self._players[pid] = self._mk_player(pid, name)
                    return pid
            return None

    def deactivate_player(self, pid: int):
        with self._lock:
            p = self._players[pid] if 0 <= pid < self.MAX_PLAYERS else None
            if p: p['active'] = False

    def ping_player(self, pid: int):
        with self._lock:
            p = self._players[pid] if 0 <= pid < self.MAX_PLAYERS else None
            if p: p['last_ping'] = time.time()

    def apply_action(self, pid: int, payload: str):
        with self._lock:
            self._do_action(pid, payload)

    def apply_vote(self, pid: int, v: str):
        with self._lock:
            p = self._players[pid] if 0 <= pid < self.MAX_PLAYERS else None
            if p and p['active'] and self._phase == PHASE_VOTING:
                p['vote'] = {'A': 0, 'B': 1, 'C': 2, 'D': 3}.get(v, -1)

    def start_game(self) -> bool:
        with self._lock:
            if self._phase != PHASE_LOBBY: return False
            if sum(1 for p in self._players if p and p['active']) < 2: return False
            self._phase     = PHASE_VOTING
            self._vote_left = VOTE_DURATION
            self._last_sec  = time.time()
            for p in self._players:
                if p: p['vote'] = -1
            return True

    def is_empty(self) -> bool:
        with self._lock:
            return not any(c.alive for c in self._clients)

    def tick(self):
        with self._lock:
            self._tick_n += 1
            self._update()
            state_json   = self._build_json()
            snap         = list(self._clients)

        msg  = 'STATE:' + state_json
        dead = []
        for c in snap:
            c.send(msg)
            if not c.alive:
                dead.append(c)
        if dead:
            with self._lock:
                for c in dead:
                    try: self._clients.remove(c)
                    except ValueError: pass


    @staticmethod
    def _rand_coin():
        return {'x': float(60 + random.randint(0, ARENA_W - 120)),
                'y': float(60 + random.randint(0, ARENA_H - 120))}

    @staticmethod
    def _mk_pong():
        return {'bx': 400.0, 'by': 300.0, 'vx': 0.0, 'vy': 0.0,
                'py0': 300.0, 'py1': 300.0,
                's0': 0, 's1': 0, 'win': -1, 'spd': PONG_BALL_INIT}

    @staticmethod
    def _mk_bomb():
        return {'holder': -1, 'time_left': 20, 'hold_ticks': 0, 'exploded': 0}

    def _mk_player(self, pid: int, name: str) -> dict:
        p = {'pid': pid, 'name': name[:31],
             'x': float(START_X[pid]), 'y': float(START_Y[pid]),
             'score': 0, 'color': COLOR_NAMES[self._next_color % 4],
             'team': -1, 'vote': -1, 'last_ping': time.time(), 'active': True}
        self._next_color += 1
        return p

    def _active(self):
        return [p for p in self._players if p and p['active']]

    def _clamp(self, p):
        r = PLAYER_RADIUS
        p['x'] = max(float(r), min(float(ARENA_W - r), p['x']))
        p['y'] = max(float(r), min(float(ARENA_H - r), p['y']))

    def _pick_coins(self, p):
        cap2 = (COIN_RADIUS + PLAYER_RADIUS) ** 2
        for c in self._coins:
            dx = p['x'] - c['x']; dy = p['y'] - c['y']
            if dx*dx + dy*dy < cap2:
                p['score'] += 1
                c.update(self._rand_coin())


    def _update(self):
        now  = time.time()
        secs = 0
        if now - self._last_sec >= 1.0:
            secs          = int(now - self._last_sec)
            self._last_sec += secs

        if self._phase == PHASE_VOTING:
            self._vote_left -= secs
            if self._vote_left <= 0:
                self._vote_left = 0; self._resolve_vote()

        elif self._phase == PHASE_COINS:
            self._time_left -= secs
            if self._time_left <= 0:
                self._time_left = 0; self._phase = PHASE_ENDED; self._end_ticks = 0
            self._check_hb(now)

        elif self._phase == PHASE_PONG:
            self._pong_tick()
            if self._pong['win'] >= 0:
                self._phase = PHASE_ENDED; self._end_ticks = 0
            self._check_hb(now)

        elif self._phase == PHASE_BOMB:
            self._bomb_tick()
            self._bomb['time_left'] -= secs
            if self._bomb['time_left'] <= 0 and not self._bomb['exploded']:
                self._bomb['time_left'] = 0; self._bomb['exploded'] = 1
                h = self._bomb['holder']
                for p in self._active():
                    if p['pid'] != h: p['score'] = 1
                self._phase = PHASE_ENDED; self._end_ticks = 0
            self._check_hb(now)

        elif self._phase == PHASE_ENDED:
            self._end_ticks += 1
            if self._end_ticks >= END_TICKS:
                self._reset_lobby()

    def _check_hb(self, now):
        for p in self._players:
            if p and p['active'] and now - p['last_ping'] > HEARTBEAT_TIMEOUT:
                p['active'] = False


    def _do_action(self, pid: int, payload: str):
        p = self._players[pid] if 0 <= pid < self.MAX_PLAYERS else None
        if not p or not p['active']: return
        p['last_ping'] = time.time()

        if self._phase in (PHASE_COINS, PHASE_BOMB):
            if payload.startswith('x='):
                try:
                    parts = payload.split(',')
                    ax = max(-1.0, min(1.0, float(parts[0][2:])))
                    ay = max(-1.0, min(1.0, float(parts[1][2:])))
                except Exception:
                    ax = ay = 0.0
                p['x'] += ax * PLAYER_SPEED
                p['y'] += ay * PLAYER_SPEED
            else:
                hx = 'L' in payload or 'R' in payload
                hy = 'U' in payload or 'D' in payload
                n  = 0.7071 if hx and hy else 1.0
                if 'L' in payload: p['x'] -= PLAYER_SPEED * n
                if 'R' in payload: p['x'] += PLAYER_SPEED * n
                if 'U' in payload: p['y'] -= PLAYER_SPEED * n
                if 'D' in payload: p['y'] += PLAYER_SPEED * n
            self._clamp(p)
            if self._phase == PHASE_COINS:
                self._pick_coins(p)

        elif self._phase == PHASE_PONG and self._pong['win'] < 0:
            key  = 'py0' if p['team'] == 0 else 'py1'
            half = PONG_PAD_H / 2
            if 'U' in payload: self._pong[key] -= PONG_PAD_SPEED
            if 'D' in payload: self._pong[key] += PONG_PAD_SPEED
            self._pong[key] = max(half, min(PONG_H - half, self._pong[key]))


    def _pong_reset(self, d: int):
        ang = math.radians(random.uniform(-20, 20))
        self._pong.update({'bx': 400.0, 'by': 300.0, 'spd': PONG_BALL_INIT,
                           'vx': d * PONG_BALL_INIT * math.cos(ang),
                           'vy': PONG_BALL_INIT * math.sin(ang)})

    def _pong_init(self):
        self._pong = self._mk_pong()
        t = 0
        for p in self._active():
            p['team'] = t % 2; t += 1
        self._pong_reset(1)

    def _pong_tick(self):
        g = self._pong
        if g['win'] >= 0: return
        g['bx'] += g['vx']; g['by'] += g['vy']

        if g['by'] - 10 < 0:   g['by'] = 10.0;         g['vy'] = abs(g['vy'])
        if g['by'] + 10 > 600: g['by'] = 590.0;        g['vy'] = -abs(g['vy'])

        PAD_W = 14
        px0 = PAD_W
        if (g['vx'] < 0
                and px0 <= g['bx'] - 10 <= px0 + PAD_W + 4
                and abs(g['by'] - g['py0']) <= PONG_PAD_H / 2 + 10):
            g['spd'] = min(g['spd'] * PONG_ACCEL, PONG_BALL_MAX)
            rel = (g['by'] - g['py0']) / (PONG_PAD_H / 2)
            ang = math.radians(rel * 60)
            g['vx'] =  g['spd'] * math.cos(ang)
            g['vy'] =  g['spd'] * math.sin(ang)
            g['bx'] = float(px0 + PAD_W + 12)

        px1 = ARENA_W - PAD_W * 2
        if (g['vx'] > 0
                and px1 - 4 <= g['bx'] + 10 <= px1 + PAD_W
                and abs(g['by'] - g['py1']) <= PONG_PAD_H / 2 + 10):
            g['spd'] = min(g['spd'] * PONG_ACCEL, PONG_BALL_MAX)
            rel = (g['by'] - g['py1']) / (PONG_PAD_H / 2)
            ang = math.radians(rel * 60)
            g['vx'] = -g['spd'] * math.cos(ang)
            g['vy'] =  g['spd'] * math.sin(ang)
            g['bx'] = float(px1 - 12)

        if g['bx'] < 0:
            g['s1'] += 1
            if g['s1'] >= PONG_WIN_SCORE: g['win'] = 1; return
            self._pong_reset(1)
        if g['bx'] > ARENA_W:
            g['s0'] += 1
            if g['s0'] >= PONG_WIN_SCORE: g['win'] = 0; return
            self._pong_reset(-1)


    def _bomb_init(self):
        active = self._active()
        if not active: return
        h = random.choice(active)['pid']
        self._bomb = {'holder': h, 'time_left': random.randint(15, 30),
                      'hold_ticks': 0, 'exploded': 0}
        for p in active:
            p['x'] = float(START_X[p['pid']]); p['y'] = float(START_Y[p['pid']])
            p['score'] = 0

    def _bomb_tick(self):
        b = self._bomb
        if b['exploded'] or b['holder'] < 0: return
        b['hold_ticks'] += 1
        if b['hold_ticks'] < BOMB_MIN_HOLD: return
        h = self._players[b['holder']]
        if not h or not h['active']: return
        best_d2, best_pid = BOMB_PASS_RADIUS ** 2, -1
        for p in self._active():
            if p['pid'] == b['holder']: continue
            dx = p['x'] - h['x']; dy = p['y'] - h['y']
            d2 = dx*dx + dy*dy
            if d2 < best_d2:
                best_d2 = d2; best_pid = p['pid']
        if best_pid >= 0:
            b['holder'] = best_pid; b['hold_ticks'] = 0


    def _resolve_vote(self):
        counts = [0, 0, 0, 0]
        for p in self._active():
            v = p['vote']
            if 0 <= v <= 3: counts[v] += 1
        mx      = max(counts)
        winners = [i for i, c in enumerate(counts) if c == mx]
        chosen  = random.choice(winners)
        if chosen == 3: chosen = random.randint(0, 2)
        self._last_game = chosen
        self._last_sec  = time.time()

        active = self._active()
        if chosen == 0:
            self._phase = PHASE_COINS; self._time_left = GAME_DURATION
            for p in active: p['score'] = 0
            self._coins = [self._rand_coin() for _ in range(MAX_COINS)]
        elif chosen == 1:
            self._phase = PHASE_PONG
            for p in active: p['score'] = 0
            self._pong_init()
        else:
            self._phase = PHASE_BOMB; self._bomb_init()

    def _reset_lobby(self):
        self._phase = PHASE_LOBBY; self._time_left = GAME_DURATION
        self._vote_left = VOTE_DURATION; self._last_sec = time.time()
        for p in self._players:
            if p:
                p['score'] = 0; p['vote'] = -1
                if p['active']:
                    p['x'] = float(START_X[p['pid']])
                    p['y'] = float(START_Y[p['pid']])


    def _build_json(self) -> str:
        active  = self._active()
        votes   = [self._players[i]['vote'] if self._players[i] else -1
                   for i in range(self.MAX_PLAYERS)]
        va, vb, vc, vd = (sum(1 for p in active if p['vote'] == i) for i in range(4))
        players = [{'id': p['pid'], 'name': p['name'],
                    'x': round(p['x']), 'y': round(p['y']),
                    'score': p['score'], 'color': p['color'], 'team': p['team']}
                   for p in active]
        g  = self._pong; b = self._bomb
        return json.dumps({
            'phase': self._phase, 'time_left': self._time_left,
            'vote_left': self._vote_left, 'last_game': self._last_game,
            'va': va, 'vb': vb, 'vc': vc, 'vd': vd,
            'votes': votes, 'players': players,
            'coins': [{'x': round(c['x']), 'y': round(c['y'])} for c in self._coins],
            'pong': {'bx': round(g['bx'], 1), 'by': round(g['by'], 1),
                     'py0': round(g['py0'], 1), 'py1': round(g['py1'], 1),
                     's0': g['s0'], 's1': g['s1'], 'win': g['win'], 'spd': round(g['spd'], 1)},
            'bomb': {'holder': b['holder'], 'time_left': b['time_left'], 'exploded': b['exploded']},
            'pin': self.pin,
        }, separators=(',', ':'))



_rooms: dict[str, Room] = {}
_rooms_lock = threading.Lock()


def _gen_pin() -> str:
    for _ in range(200):
        pin = str(random.randint(1000, 9999))
        if pin not in _rooms:
            return pin
    return str(random.randint(1000, 9999))


def _create_room() -> Room:
    with _rooms_lock:
        pin  = _gen_pin()
        room = Room(pin)
        _rooms[pin] = room
    return room


def _get_room(pin: str) -> Room | None:
    with _rooms_lock:
        return _rooms.get(pin)



def _game_loop():
    TICK = 1.0 / 60
    while True:
        t0 = time.monotonic()
        with _rooms_lock:
            pins = list(_rooms.keys())
        for pin in pins:
            room = _get_room(pin)
            if room:
                room.tick()
                if room.is_empty():
                    with _rooms_lock:
                        _rooms.pop(pin, None)
        elapsed = time.monotonic() - t0
        wait    = TICK - elapsed
        if wait > 0:
            time.sleep(wait)


threading.Thread(target=_game_loop, daemon=True).start()


@sock.route('/ws')
def ws_handler(ws):
    client = WSClient(ws)
    room: Room | None = None
    pid:  int         = -1

    try:
        while True:
            msg = ws.receive(timeout=35)
            if msg is None: break
            msg = msg.strip()

            if msg.startswith('CREATE:'):
                name = msg[7:]
                r    = _create_room()
                p    = r.add_player(name)
                if p is None:
                    client.send('ERROR:Could not create room'); continue
                room = r; pid = p
                client.player_id = pid
                room.add_client(client)
                client.send(f'ROOM:{room.pin}')
                client.send(f'WELCOME:{pid}')

            elif msg.startswith('JOIN:'):
                parts = msg[5:].split(':', 1)
                if len(parts) != 2:
                    client.send('ERROR:Use JOIN:PIN:Name'); continue
                pin_in, name = parts[0].strip(), parts[1].strip()
                r = _get_room(pin_in)
                if r is None:
                    client.send('ERROR:Room not found'); continue
                p = r.add_player(name)
                if p is None:
                    client.send('ERROR:Room full or game in progress'); continue
                room = r; pid = p
                client.player_id = pid
                room.add_client(client)
                client.send(f'ROOM:{room.pin}')
                client.send(f'WELCOME:{pid}')

            elif msg == 'START' and room:
                if not room.start_game():
                    client.send('ERROR:Need at least 2 players')

            elif msg.startswith('VOTE:') and room and pid >= 0:
                room.apply_vote(pid, msg[5:])

            elif msg.startswith('ACTION:') and room and pid >= 0:
                room.apply_action(pid, msg[7:])
                room.ping_player(pid)

            elif msg == 'PING' and room and pid >= 0:
                room.ping_player(pid)
                client.send('PONG')

    except Exception:
        pass
    finally:
        client.alive = False
        if room:
            if pid >= 0: room.deactivate_player(pid)
            room.remove_client(client)



def _handle_display_tcp(conn: socket.socket):
    client = TCPClient(conn)
    room: Room | None = None
    buf = b''
    try:
        while True:
            data = conn.recv(4096)
            if not data: break
            buf += data
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                msg = line.decode('utf-8', errors='replace').strip()
                if msg.startswith('DISPLAY:'):
                    pin = msg[8:].strip()
                    r   = _get_room(pin)
                    if r:
                        room = r
                        room.add_client(client)
                        client.send('DISPLAY_OK')
                    else:
                        client.send('ERROR:Room not found')
    except Exception:
        pass
    finally:
        client.alive = False
        if room: room.remove_client(client)


def _tcp_display_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', DISPLAY_PORT))
    srv.listen(20)
    while True:
        try:
            conn, _ = srv.accept()
            threading.Thread(target=_handle_display_tcp, args=(conn,), daemon=True).start()
        except Exception:
            pass


threading.Thread(target=_tcp_display_server, daemon=True).start()


@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'controller.html')


if __name__ == '__main__':
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = '127.0.0.1'

    print('=' * 55)
    print('  Party Game  –  Multi-Room Server')
    print('=' * 55)
    print(f'  Controller:  http://{local_ip}:{BRIDGE_PORT}/')
    print(f'  Display TCP: 127.0.0.1:{DISPLAY_PORT}  (use --pin XXXX)')
    print(f'  Rooms:       created dynamically via PIN')
    print('=' * 55)

    app.run(host='0.0.0.0', port=BRIDGE_PORT, threaded=True)
