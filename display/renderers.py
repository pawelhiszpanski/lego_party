import math
import pygame
from display.constants import (
    ARENA_W, ARENA_H, PANEL_W, WIN_H,
    PAD_W, PAD_H, BALL_R, PAD_X0, PAD_X1,
    C, PLAYER_RGB, PLAYER_R, PHASE_LBL, PHASE_COL,
)
from display.fonts import Fonts



def _glow_circle(surf: pygame.Surface, color: tuple, cx: int, cy: int,
                 r: int, alpha: int = 60) -> None:
    s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color, alpha), (r + 2, r + 2), r)
    surf.blit(s, (cx - r - 2, cy - r - 2))



class ArenaRenderer:
    def __init__(self, screen: pygame.Surface, fonts: Fonts) -> None:
        self.screen = screen
        self.fonts  = fonts

    def draw(self, _state: dict) -> None:
        pygame.draw.rect(self.screen, C['arena'], (0, 0, ARENA_W, ARENA_H))
        for x in range(0, ARENA_W, 80):
            pygame.draw.line(self.screen, C['grid'], (x, 0), (x, ARENA_H))
        for y in range(0, ARENA_H, 80):
            pygame.draw.line(self.screen, C['grid'], (0, y), (ARENA_W, y))
        # subtle vignette
        v = pygame.Surface((ARENA_W, ARENA_H), pygame.SRCALPHA)
        for dist, alpha in ((40, 30), (80, 18), (130, 8)):
            pygame.draw.rect(v, (0, 0, 0, alpha), (0, 0, ARENA_W, ARENA_H), dist)
        self.screen.blit(v, (0, 0))
        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)


class CoinRenderer:
    def __init__(self, screen: pygame.Surface, fonts: Fonts) -> None:
        self.screen = screen
        self.fonts  = fonts

    def draw_coin(self, x: float, y: float, tick: int = 0) -> None:
        ix, iy = int(x), int(y)
        r = 15
        # subtle bob
        iy += int(math.sin(tick * 0.06 + x * 0.05) * 2)
        _glow_circle(self.screen, C['gold'], ix, iy, r + 6, 35)
        pygame.draw.circle(self.screen, (0, 0, 0),       (ix+2, iy+3), r)
        pygame.draw.circle(self.screen, C['gold'],        (ix,   iy),   r)
        pygame.draw.circle(self.screen, (255, 255, 180),  (ix-4, iy-4), r//3)
        pygame.draw.circle(self.screen, (170, 140, 5),    (ix,   iy),   r, 2)
        lbl = self.fonts.xs.render('$', True, (110, 80, 0))
        self.screen.blit(lbl, (ix - lbl.get_width()//2, iy - lbl.get_height()//2))


class PlayerRenderer:
    def __init__(self, screen: pygame.Surface, fonts: Fonts) -> None:
        self.screen = screen
        self.fonts  = fonts

    def draw_player(self, p: dict, bomb_holder: bool = False, tick: int = 0) -> None:
        x, y  = int(p['x']), int(p['y'])
        color = PLAYER_RGB.get(p.get('color', 'red'), C['white'])
        name  = p.get('name', '?')[:10]

        # outer glow
        glow_r = PLAYER_R + 10 + (int(math.sin(tick * 0.12) * 3) if bomb_holder else 0)
        glow_c = (255, 120, 0) if bomb_holder else color
        _glow_circle(self.screen, glow_c, x, y, glow_r, 45)

        # shadow
        sh = pygame.Surface((PLAYER_R*2+6, PLAYER_R*2+6), pygame.SRCALPHA)
        pygame.draw.circle(sh, (0, 0, 0, 80), (PLAYER_R+3, PLAYER_R+5), PLAYER_R)
        self.screen.blit(sh, (x - PLAYER_R, y - PLAYER_R))

        if bomb_holder:
            pygame.draw.circle(self.screen, (255, 120, 0), (x, y), PLAYER_R + 8, 3)

        pygame.draw.circle(self.screen, color,     (x, y), PLAYER_R)
        pygame.draw.circle(self.screen, C['white'], (x, y), PLAYER_R, 2)
        pygame.draw.circle(self.screen, C['white'],
                           (x - PLAYER_R//3, y - PLAYER_R//3), PLAYER_R//4)

        ns  = self.fonts.sm.render(name, True, C['white'])
        nx  = x - ns.get_width()//2
        ny  = y - PLAYER_R - 22
        sh2 = self.fonts.sm.render(name, True, C['border'])
        self.screen.blit(sh2, (nx+1, ny+1))
        self.screen.blit(ns,  (nx,   ny))

        sc = self.fonts.xs.render(str(p.get('score', 0)), True, C['gold'])
        self.screen.blit(sc, (x - sc.get_width()//2, ny - 16))


class PongRenderer:
    _BALL_LERP  = 0.55
    _PAD_LERP   = 0.25
    _TRAIL_LEN  = 10

    def __init__(self, screen: pygame.Surface, fonts: Fonts) -> None:
        self.screen   = screen
        self.fonts    = fonts
        self._ball_x  = float(ARENA_W / 2)
        self._ball_y  = float(ARENA_H / 2)
        self._pad0_y  = float(ARENA_H / 2)
        self._pad1_y  = float(ARENA_H / 2)
        self._trail: list[tuple[float, float]] = []

    def draw(self, state: dict, show_win_overlay: bool = False) -> None:
        pg  = state.get('pong', {})
        bx  = float(pg.get('bx', ARENA_W/2))
        by  = float(pg.get('by', ARENA_H/2))
        py0 = float(pg.get('py0', ARENA_H/2))
        py1 = float(pg.get('py1', ARENA_H/2))
        s0  = pg.get('s0', 0)
        s1  = pg.get('s1', 0)
        win = pg.get('win', -1)
        spd = float(pg.get('spd', 6.5))

        self._ball_x += (bx  - self._ball_x) * self._BALL_LERP
        self._ball_y += (by  - self._ball_y) * self._BALL_LERP
        self._pad0_y += (py0 - self._pad0_y) * self._PAD_LERP
        self._pad1_y += (py1 - self._pad1_y) * self._PAD_LERP

        ibx  = int(self._ball_x)
        iby  = int(self._ball_y)
        ip0y = int(self._pad0_y)
        ip1y = int(self._pad1_y)

        # update trail
        self._trail.append((self._ball_x, self._ball_y))
        if len(self._trail) > self._TRAIL_LEN:
            self._trail.pop(0)

        pygame.draw.rect(self.screen, C['pong_bg'], (0, 0, ARENA_W, ARENA_H))

        # center dashes
        for y in range(8, ARENA_H, 24):
            pygame.draw.rect(self.screen, C['mid_line'], (ARENA_W//2 - 3, y, 6, 14))

        # scores
        s0s = self.fonts.xl.render(str(s0), True, C['pad0'])
        s1s = self.fonts.xl.render(str(s1), True, C['pad1'])
        self.screen.blit(s0s, (ARENA_W//4   - s0s.get_width()//2, 18))
        self.screen.blit(s1s, (3*ARENA_W//4 - s1s.get_width()//2, 18))

        info = self.fonts.xs.render('FIRST TO 3 POINTS', True, C['dim'])
        self.screen.blit(info, (ARENA_W//2 - info.get_width()//2, 72))

        spd_s = self.fonts.xs.render(f'speed: {spd:.0f}', True, C['dim'])
        self.screen.blit(spd_s, (ARENA_W//2 - spd_s.get_width()//2, ARENA_H - 22))

        # pads
        self._draw_pad(PAD_X0, ip0y, C['pad0'], -14)
        self._draw_pad(PAD_X1, ip1y, C['pad1'], -12)

        # ball trail
        for i, (tx, ty) in enumerate(self._trail[:-1]):
            alpha = int(120 * (i / self._TRAIL_LEN))
            r     = max(2, int(BALL_R * 0.6 * (i / self._TRAIL_LEN)))
            ts    = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
            pygame.draw.circle(ts, (220, 220, 255, alpha), (r+1, r+1), r)
            self.screen.blit(ts, (int(tx) - r - 1, int(ty) - r - 1))

        # ball glow + ball
        _glow_circle(self.screen, C['white'], ibx, iby, BALL_R + 8, 50)
        pygame.draw.circle(self.screen, (160, 160, 160), (ibx+2, iby+2), BALL_R)
        pygame.draw.circle(self.screen, C['white'],      (ibx,   iby),   BALL_R)
        pygame.draw.circle(self.screen, (220, 220, 255), (ibx-3, iby-3), BALL_R//3)

        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)

        if show_win_overlay and win >= 0:
            col = C['pad0'] if win == 0 else C['pad1']
            ov  = self.fonts.xl.render(f'Team {win} wins!', True, col)
            self.screen.blit(ov, (ARENA_W//2 - ov.get_width()//2, ARENA_H//2 - 30))

    def _draw_pad(self, px: int, py: int, color: tuple, glow_off: int) -> None:
        _glow_circle(self.screen, color, px + PAD_W//2, py, PAD_H//2 + 10, 35)
        pygame.draw.rect(self.screen, color,
                         (px, py - PAD_H//2, PAD_W, PAD_H), border_radius=5)
        shine = pygame.Surface((PAD_W, PAD_H), pygame.SRCALPHA)
        pygame.draw.rect(shine, (255, 255, 255, 25), (0, 0, PAD_W, PAD_H//2), border_radius=5)
        self.screen.blit(shine, (px, py - PAD_H//2))


class VotingRenderer:
    def __init__(self, screen: pygame.Surface, fonts: Fonts) -> None:
        self.screen = screen
        self.fonts  = fonts

    def draw(self, state: dict) -> None:
        pygame.draw.rect(self.screen, C['arena'],  (0, 0, ARENA_W, ARENA_H))
        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)

        title = self.fonts.lg.render('CHOOSE YOUR GAME', True, C['gold'])
        self.screen.blit(title, (ARENA_W//2 - title.get_width()//2, 30))

        vl = state.get('vote_left', 10)
        tc = C['red'] if vl <= 3 else C['white']
        ts = self.fonts.xl.render(f'{vl}s', True, tc)
        self.screen.blit(ts, (ARENA_W//2 - ts.get_width()//2, 76))

        options = [
            ('A', '\U0001fa99', 'Coins',  state.get('va', 0), C['vote_a']),
            ('B', '\U0001f3d3', 'Pong',   state.get('vb', 0), C['vote_b']),
            ('C', '\U0001f4a3', 'Bomb',   state.get('vc', 0), C['vote_c']),
            ('D', '\U0001f3b2', 'Random', state.get('vd', 0), (70, 70, 100)),
        ]
        bw, bh, gap = 190, 118, 16
        total_w = 2*bw + gap
        bx0 = ARENA_W//2 - total_w//2

        for i, (ltr, emoji, name, cnt, col) in enumerate(options):
            col_idx = i % 2
            row_idx = i // 2
            bx = bx0 + col_idx * (bw + gap)
            by = 165 + row_idx * (bh + 12)

            # card with glow
            _glow_circle(self.screen, col, bx + bw//2, by + bh//2, bh//2 + 8, 20)
            pygame.draw.rect(self.screen, col, (bx, by, bw, bh), border_radius=18)
            shine = pygame.Surface((bw - 4, bh//2), pygame.SRCALPHA)
            pygame.draw.rect(shine, (255, 255, 255, 20), (0, 0, bw-4, bh//2), border_radius=14)
            self.screen.blit(shine, (bx+2, by+2))

            ls  = self.fonts.xl.render(ltr,            True, C['white'])
            ems = self.fonts.md.render(emoji+' '+name, True, C['white'])
            cs  = self.fonts.lg.render(str(cnt),        True, C['white'])

            self.screen.blit(ls,  (bx + bw//2 - ls.get_width()//2,  by + 6))
            self.screen.blit(ems, (bx + bw//2 - ems.get_width()//2, by + 54))
            self.screen.blit(cs,  (bx + bw//2 - cs.get_width()//2,  by + 82))

        players = state.get('players', [])
        votes   = state.get('votes', [-1,-1,-1,-1])
        VMAP = {-1:'?', 0:'A', 1:'B', 2:'C', 3:'D'}
        VCOL = {-1:C['dim'], 0:C['vote_a'], 1:C['vote_b'], 2:C['vote_c'], 3:C['white']}
        y0 = 440

        for p in players:
            pid = p.get('id', 0)
            v   = votes[pid] if pid < 4 else -1
            pc  = PLAYER_RGB.get(p.get('color','red'), C['white'])
            nm  = self.fonts.md.render(p.get('name','?'), True, pc)
            ar  = self.fonts.md.render(' -> ',            True, C['dim'])
            vs  = self.fonts.md.render(VMAP[v],           True, VCOL[v])
            rw  = nm.get_width() + ar.get_width() + vs.get_width()
            rx  = ARENA_W//2 - rw//2
            self.screen.blit(nm, (rx, y0))
            self.screen.blit(ar, (rx + nm.get_width(), y0))
            self.screen.blit(vs, (rx + nm.get_width() + ar.get_width(), y0))
            y0 += 30


class LobbyRenderer:
    _N_STARS = 40

    def __init__(self, screen: pygame.Surface, fonts: Fonts,
                 arena: ArenaRenderer, player_r: PlayerRenderer,
                 base_url: str = '') -> None:
        self.screen   = screen
        self.fonts    = fonts
        self.arena    = arena
        self.player_r = player_r
        self.base_url = base_url   # e.g. "http://192.168.0.x:8080"
        self._tick    = 0
        self._qr_surf: pygame.Surface | None = None
        self._qr_pin: str = ''
        import random
        rng = random.Random(42)
        self._stars = [
            (rng.randint(10, ARENA_W-10), rng.randint(10, ARENA_H-10),
             rng.uniform(0.4, 1.0), rng.uniform(0, math.tau))
            for _ in range(self._N_STARS)
        ]

    def _make_qr(self, pin: str) -> pygame.Surface:
        """Generate a QR-code pygame Surface for the given PIN."""
        import qrcode, io
        url = f'{self.base_url}/?pin={pin}' if self.base_url else pin
        qr  = qrcode.QRCode(box_size=6, border=2,
                             error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='white', back_color=(22, 22, 34))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return pygame.image.load(buf, 'qr.png').convert()

    def draw(self, state: dict) -> None:
        self._tick += 1
        self.arena.draw(state)

        # drifting star particles
        for sx, sy, spd, phase in self._stars:
            alpha = int(30 + 25 * math.sin(self._tick * spd * 0.04 + phase))
            r = 2
            s = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
            pygame.draw.circle(s, (150, 150, 220, alpha), (r+1, r+1), r)
            self.screen.blit(s, (sx - r - 1, sy - r - 1))

        players = state.get('players', [])
        cnt     = len(players)
        pin     = state.get('pin', '')

        # regenerate QR only when pin changes
        if pin and pin != self._qr_pin:
            try:
                self._qr_surf = self._make_qr(pin)
            except Exception:
                self._qr_surf = None
            self._qr_pin = pin

        # ── layout: QR on left, PIN card on right ─────────────────────────
        total_w  = 560
        start_x  = ARENA_W // 2 - total_w // 2
        card_y   = ARENA_H // 2 - 120
        card_h   = 188

        # ── left: QR code ─────────────────────────────────────────────────
        qr_size = 156
        qr_x    = start_x
        qr_y    = card_y + (card_h - qr_size) // 2

        if self._qr_surf:
            qr_scaled = pygame.transform.smoothscale(self._qr_surf, (qr_size, qr_size))
            # white border / frame
            frame = pygame.Surface((qr_size + 10, qr_size + 10))
            frame.fill((240, 240, 240))
            self.screen.blit(frame, (qr_x - 5, qr_y - 5))
            self.screen.blit(qr_scaled, (qr_x, qr_y))
        else:
            # fallback placeholder
            pygame.draw.rect(self.screen, (60, 60, 80),
                             (qr_x, qr_y, qr_size, qr_size), border_radius=8)
            fb = self.fonts.sm.render('QR', True, C['dim'])
            self.screen.blit(fb, (qr_x + qr_size//2 - fb.get_width()//2,
                                  qr_y + qr_size//2 - fb.get_height()//2))

        scan_s = self.fonts.xs.render('SCAN TO JOIN', True, (180, 180, 180))
        self.screen.blit(scan_s, (qr_x + qr_size//2 - scan_s.get_width()//2,
                                  qr_y + qr_size + 6))

        # ── right: PIN card ────────────────────────────────────────────────
        card_x  = qr_x + qr_size + 20
        card_w  = total_w - qr_size - 20

        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        card.fill((0, 0, 0, 165))
        self.screen.blit(card, (card_x, card_y))
        pygame.draw.rect(self.screen, C['gold'],
                         (card_x, card_y, card_w, card_h), 2, border_radius=14)

        or_s = self.fonts.xs.render('OR ENTER MANUALLY', True, (160, 160, 160))
        self.screen.blit(or_s, (card_x + card_w//2 - or_s.get_width()//2, card_y + 12))

        # large PIN with pulse
        pin_display = pin if pin else '----'
        spaced  = '  '.join(pin_display)
        pin_s   = self.fonts.xl.render(spaced, True, C['gold'])
        pulse   = 1.0 + 0.04 * math.sin(self._tick * 0.08)
        pw      = int(pin_s.get_width()  * pulse)
        ph      = int(pin_s.get_height() * pulse)
        pin_sc  = pygame.transform.smoothscale(pin_s, (pw, ph))
        self.screen.blit(pin_sc, (card_x + card_w//2 - pw//2, card_y + 42))

        lbl = self.fonts.xs.render('ROOM PIN', True, C['dim'])
        self.screen.blit(lbl, (card_x + card_w//2 - lbl.get_width()//2, card_y + 130))

        url_hint = self.base_url if self.base_url else 'see terminal for URL'
        url_s = self.fonts.xs.render(url_hint, True, (140, 140, 160))
        self.screen.blit(url_s, (card_x + card_w//2 - url_s.get_width()//2, card_y + 150))

        cnt_col  = C['green'] if cnt >= 2 else C['dim']
        info_txt = (f'Players: {cnt}/4  –  Start from any phone!'
                    if cnt >= 2 else f'Players: {cnt}/4  –  need at least 2…')
        info_s = self.fonts.xs.render(info_txt, True, cnt_col)
        self.screen.blit(info_s, (card_x + card_w//2 - info_s.get_width()//2,
                                  card_y + card_h - 22))

        # ── player list below ──────────────────────────────────────────────
        y0 = card_y + card_h + 16
        for p in players:
            col = PLAYER_RGB.get(p.get('color', 'red'), C['white'])
            ns  = self.fonts.sm.render(f"● {p.get('name', '?')}", True, col)
            self.screen.blit(ns, (ARENA_W//2 - ns.get_width()//2, y0))
            y0 += 26


class BombRenderer:
    _BOMB_COLOR   = (255, 120,  0)
    _FUSE_COLOR   = (255, 220, 50)
    _DANGER_COLOR = (220,  55, 55)

    def __init__(self, screen: pygame.Surface, fonts: Fonts,
                 arena: ArenaRenderer, player_r: PlayerRenderer) -> None:
        self.screen   = screen
        self.fonts    = fonts
        self.arena    = arena
        self.player_r = player_r
        self._tick    = 0

    def draw(self, state: dict) -> None:
        self._tick += 1
        self.arena.draw(state)

        bomb     = state.get('bomb', {})
        holder   = bomb.get('holder', -1)
        exploded = bomb.get('exploded', 0)
        players  = state.get('players', [])

        for p in players:
            is_holder = (p.get('id', -1) == holder)
            self.player_r.draw_player(p, bomb_holder=is_holder, tick=self._tick)

        # bomb icon above holder
        for p in players:
            if p.get('id', -1) == holder:
                bx = int(p['x'])
                by = int(p['y']) - PLAYER_R - 38
                self._draw_bomb_icon(bx, by, exploded)
                break

        # pass-range aura
        if not exploded and holder >= 0:
            for p in players:
                if p.get('id', -1) == holder:
                    px, py = int(p['x']), int(p['y'])
                    _glow_circle(self.screen, (255, 120, 0), px, py, 60, 18)
                    s = pygame.Surface((122, 122), pygame.SRCALPHA)
                    pygame.draw.circle(s, (255, 120, 0, 55), (61, 61), 60, 2)
                    self.screen.blit(s, (px - 61, py - 61))
                    break

        # tick indicator (no time shown)
        self._draw_tick_indicator()

        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)

    def _draw_bomb_icon(self, cx: int, cy: int, exploded: int) -> None:
        t = self._tick
        r = 18

        if exploded:
            for angle in range(0, 360, 30):
                rad = math.radians(angle)
                ex  = cx + int(math.cos(rad) * (r + 14))
                ey  = cy + int(math.sin(rad) * (r + 14))
                pygame.draw.circle(self.screen, (255, 200, 0), (ex, ey), 5)
            pygame.draw.circle(self.screen, (255, 80, 0), (cx, cy), r + 8)
            lbl = self.fonts.lg.render('BOOM!', True, C['white'])
            self.screen.blit(lbl, (cx - lbl.get_width()//2, cy - lbl.get_height()//2))
            return

        _glow_circle(self.screen, self._BOMB_COLOR, cx, cy, r + 14, 40)
        pygame.draw.circle(self.screen, (0, 0, 0), (cx+3, cy+4), r)
        pygame.draw.circle(self.screen, self._BOMB_COLOR, (cx, cy), r)
        pygame.draw.circle(self.screen, (0, 0, 0), (cx, cy), r, 2)
        pygame.draw.circle(self.screen, (255, 200, 100), (cx - r//3, cy - r//3), r//4)
        if (t // 5) % 2 == 0:
            pygame.draw.circle(self.screen, self._FUSE_COLOR, (cx + r//2, cy - r - 4), 5)
        lbl = self.fonts.md.render('\U0001f4a3', True, C['white'])
        self.screen.blit(lbl, (cx - lbl.get_width()//2, cy - lbl.get_height()//2))

    def _draw_tick_indicator(self) -> None:
        t  = self._tick
        cx = ARENA_W // 2
        cy = 22
        for i, offset in enumerate((-30, 0, 30)):
            phase = (t // 12 + i) % 3
            alpha = 220 if phase == 0 else 60
            s = pygame.Surface((14, 14), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 120, 0, alpha), (7, 7), 7)
            self.screen.blit(s, (cx + offset - 7, cy - 7))


class PanelRenderer:
    def __init__(self, screen: pygame.Surface, fonts: Fonts,
                 connected_ref) -> None:
        self.screen        = screen
        self.fonts         = fonts
        self._connected_fn = connected_ref

    def draw(self, state: dict, fps: float = 0.0) -> None:
        px = ARENA_W
        pygame.draw.rect(self.screen, C['panel'], (px, 0, PANEL_W, WIN_H))

        # gradient-like left strip
        for i in range(4):
            alpha = 20 - i * 5
            s = pygame.Surface((1, WIN_H), pygame.SRCALPHA)
            s.fill((255, 255, 255, alpha))
            self.screen.blit(s, (px + i, 0))

        pygame.draw.line(self.screen, C['border'], (px, 0), (px, WIN_H), 2)

        phase   = state.get('phase', 0)
        players = sorted(state.get('players', []), key=lambda p: -p.get('score', 0))

        cy = 18
        t1 = self.fonts.lg.render('\U0001f3ae PARTY', True, C['gold'])
        t2 = self.fonts.xs.render('GAME  v3',         True, C['dim'])
        self.screen.blit(t1, (px + PANEL_W//2 - t1.get_width()//2, cy)); cy += 42
        self.screen.blit(t2, (px + PANEL_W//2 - t2.get_width()//2, cy)); cy += 22

        idx  = phase if phase < len(PHASE_LBL) else 0
        ph_s = self.fonts.sm.render(PHASE_LBL[idx], True, PHASE_COL[idx])
        self.screen.blit(ph_s, (px + PANEL_W//2 - ph_s.get_width()//2, cy)); cy += 28

        if phase == 2:
            tl = state.get('time_left', 0)
            tc = C['red'] if tl <= 8 else C['white']
            ts = self.fonts.xl.render(f'{tl}s', True, tc)
            self.screen.blit(ts, (px + PANEL_W//2 - ts.get_width()//2, cy))
        cy += 60

        pygame.draw.line(self.screen, C['border'],
                         (px+10, cy), (px+PANEL_W-10, cy)); cy += 10

        sc_l = self.fonts.sm.render('SCORES', True, C['dim'])
        self.screen.blit(sc_l, (px + PANEL_W//2 - sc_l.get_width()//2, cy)); cy += 22

        rnk = ['1.','2.','3.','4.']
        for i, p in enumerate(players):
            col = PLAYER_RGB.get(p.get('color','red'), C['white'])
            bg  = C['row_hi'] if i == 0 else C['row_lo']
            pygame.draw.rect(self.screen, bg,
                             (px+8, cy, PANEL_W-16, 38), border_radius=6)
            pygame.draw.rect(self.screen, col,
                             (px+8, cy, 5, 38), border_radius=3)
            rk = self.fonts.sm.render(rnk[i] if i < 4 else f'{i+1}.', True, C['dim'])
            self.screen.blit(rk, (px+16, cy+10))
            nm = self.fonts.sm.render(p.get('name','?')[:12], True, C['white'])
            self.screen.blit(nm, (px+36, cy+10))
            sc = self.fonts.md.render(str(p.get('score', 0)), True, C['gold'])
            self.screen.blit(sc, (px+PANEL_W-18-sc.get_width(), cy+8))
            cy += 46

        # connection status
        ok = self._connected_fn()
        st = self.fonts.xs.render(
            'Connected' if ok else 'Disconnected',
            True, C['green'] if ok else C['red'],
        )
        self.screen.blit(st, (px + PANEL_W//2 - st.get_width()//2, WIN_H - 32))

        # FPS counter
        fps_s = self.fonts.xs.render(f'{fps:.0f} fps', True, C['dim'])
        self.screen.blit(fps_s, (px + PANEL_W//2 - fps_s.get_width()//2, WIN_H - 16))
