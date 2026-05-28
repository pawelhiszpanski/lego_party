import pygame
from display.constants import (
    ARENA_W, ARENA_H, PANEL_W, WIN_H,
    PAD_W, PAD_H, BALL_R, PAD_X0, PAD_X1,
    C, PLAYER_RGB, PLAYER_R, PHASE_LBL, PHASE_COL,
)
from display.fonts import Fonts


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
        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)


class CoinRenderer:
    def __init__(self, screen: pygame.Surface, fonts: Fonts) -> None:
        self.screen = screen
        self.fonts  = fonts

    def draw_coin(self, x: float, y: float) -> None:
        ix, iy = int(x), int(y)
        r = 15
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

    def draw_player(self, p: dict, bomb_holder: bool = False) -> None:
        x, y  = int(p['x']), int(p['y'])
        color = PLAYER_RGB.get(p.get('color', 'red'), C['white'])
        name  = p.get('name', '?')[:10]

        sh = pygame.Surface((PLAYER_R*2+6, PLAYER_R*2+6), pygame.SRCALPHA)
        pygame.draw.circle(sh, (0,0,0,80), (PLAYER_R+3, PLAYER_R+5), PLAYER_R)
        self.screen.blit(sh, (x - PLAYER_R, y - PLAYER_R))

        # glow ring for bomb holder
        if bomb_holder:
            pygame.draw.circle(self.screen, (255, 120, 0), (x, y), PLAYER_R + 8, 4)

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
    _BALL_LERP = 0.55
    _PAD_LERP  = 0.25

    def __init__(self, screen: pygame.Surface, fonts: Fonts) -> None:
        self.screen  = screen
        self.fonts   = fonts
        self._ball_x = float(ARENA_W / 2)
        self._ball_y = float(ARENA_H / 2)
        self._pad0_y = float(ARENA_H / 2)
        self._pad1_y = float(ARENA_H / 2)

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

        pygame.draw.rect(self.screen, C['pong_bg'], (0, 0, ARENA_W, ARENA_H))
        for y in range(8, ARENA_H, 24):
            pygame.draw.rect(self.screen, C['mid_line'],
                             (ARENA_W//2 - 3, y, 6, 14))

        s0s = self.fonts.xl.render(str(s0), True, C['pad0'])
        s1s = self.fonts.xl.render(str(s1), True, C['pad1'])
        self.screen.blit(s0s, (ARENA_W//4     - s0s.get_width()//2, 18))
        self.screen.blit(s1s, (3*ARENA_W//4   - s1s.get_width()//2, 18))

        info = self.fonts.xs.render('PIERWSZE DO 3 PKT', True, C['dim'])
        self.screen.blit(info, (ARENA_W//2 - info.get_width()//2, 72))

        spd_s = self.fonts.xs.render(f'predkosc: {spd:.0f}', True, C['dim'])
        self.screen.blit(spd_s, (ARENA_W//2 - spd_s.get_width()//2, ARENA_H - 22))

        self._draw_pad(PAD_X0, ip0y, C['pad0'], -14)
        self._draw_pad(PAD_X1, ip1y, C['pad1'], -12)

        pygame.draw.circle(self.screen, (160,160,160), (ibx+2, iby+2), BALL_R)
        pygame.draw.circle(self.screen, C['white'],     (ibx,   iby),   BALL_R)
        pygame.draw.circle(self.screen, (220,220,255),  (ibx-3, iby-3), BALL_R//3)

        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)

        # win overlay only during active pong phase, not on ended screen
        if show_win_overlay and win >= 0:
            col = C['pad0'] if win == 0 else C['pad1']
            ov  = self.fonts.xl.render(f'Druzyna {win} wygrywa!', True, col)
            self.screen.blit(ov, (ARENA_W//2 - ov.get_width()//2, ARENA_H//2 - 30))

    def _draw_pad(self, px: int, py: int, color: tuple, glow_off: int) -> None:
        pygame.draw.rect(self.screen, color,
                         (px, py - PAD_H//2, PAD_W, PAD_H), border_radius=5)
        glow = pygame.Surface((40, PAD_H+20), pygame.SRCALPHA)
        glow.fill((0,0,0,0))
        pygame.draw.rect(glow, (*color, 40), (0, 0, 40, PAD_H+20), border_radius=8)
        self.screen.blit(glow, (px + glow_off, py - PAD_H//2 - 10))


class VotingRenderer:
    def __init__(self, screen: pygame.Surface, fonts: Fonts) -> None:
        self.screen = screen
        self.fonts  = fonts

    def draw(self, state: dict) -> None:
        pygame.draw.rect(self.screen, C['arena'],  (0, 0, ARENA_W, ARENA_H))
        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)

        title = self.fonts.lg.render('WYBIERZ GRE', True, C['gold'])
        self.screen.blit(title, (ARENA_W//2 - title.get_width()//2, 30))

        vl = state.get('vote_left', 10)
        tc = C['red'] if vl <= 3 else C['white']
        ts = self.fonts.xl.render(f'{vl}s', True, tc)
        self.screen.blit(ts, (ARENA_W//2 - ts.get_width()//2, 76))

        options = [
            ('A', '\U0001fa99', 'Monety', state.get('va', 0), C['vote_a']),
            ('B', '\U0001f3d3', 'Pong',   state.get('vb', 0), C['vote_b']),
            ('C', '\U0001f4a3', 'Bomba',  state.get('vc', 0), C['vote_c']),
            ('D', '\U0001f3b2', 'Losowo', state.get('vd', 0), (70, 70, 100)),
        ]
        bw, bh, gap = 190, 118, 16
        total_w = 2*bw + gap
        bx0 = ARENA_W//2 - total_w//2

        for i, (ltr, emoji, name, cnt, col) in enumerate(options):
            col_idx = i % 2
            row_idx = i // 2
            bx = bx0 + col_idx * (bw + gap)
            by = 165 + row_idx * (bh + 12)
            pygame.draw.rect(self.screen, col, (bx, by, bw, bh), border_radius=18)
            inner = pygame.Surface((bw-4, bh-4), pygame.SRCALPHA)
            inner.fill((*col, 100))
            self.screen.blit(inner, (bx+2, by+2))

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
    def __init__(self, screen: pygame.Surface, fonts: Fonts,
                 arena: ArenaRenderer, player_r: PlayerRenderer) -> None:
        self.screen   = screen
        self.fonts    = fonts
        self.arena    = arena
        self.player_r = player_r

    def draw(self, state: dict) -> None:
        self.arena.draw(state)
        players = state.get('players', [])
        cnt     = len(players)

        lbl1 = self.fonts.lg.render('LOBBY', True, C['gold'])
        lbl2 = self.fonts.md.render(f'Graczy: {cnt} / 4', True, C['white'])
        lbl3 = (
            self.fonts.sm.render('Kliknij  START GAME  na telefonie', True, C['green'])
            if cnt >= 2 else
            self.fonts.sm.render('Potrzeba minimum 2 graczy...', True, C['dim'])
        )

        self.screen.blit(lbl1, (ARENA_W//2 - lbl1.get_width()//2, ARENA_H//2 - 70))
        self.screen.blit(lbl2, (ARENA_W//2 - lbl2.get_width()//2, ARENA_H//2 - 15))
        self.screen.blit(lbl3, (ARENA_W//2 - lbl3.get_width()//2, ARENA_H//2 + 24))

        y0 = ARENA_H//2 + 68
        for p in players:
            col = PLAYER_RGB.get(p.get('color','red'), C['white'])
            ns  = self.fonts.sm.render(f"* {p.get('name','?')}", True, col)
            self.screen.blit(ns, (ARENA_W//2 - ns.get_width()//2, y0))
            y0 += 26


class BombRenderer:
    """Hot Potato game renderer."""

    _BOMB_COLOR   = (255, 120,  0)
    _FUSE_COLOR   = (255, 220, 50)
    _SAFE_COLOR   = (55,  200, 75)
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
        tl       = bomb.get('time_left', 0)
        exploded = bomb.get('exploded', 0)
        players  = state.get('players', [])

        # draw players
        for p in players:
            is_holder = (p.get('id', -1) == holder)
            self.player_r.draw_player(p, bomb_holder=is_holder)

        # draw bomb icon on holder
        for p in players:
            if p.get('id', -1) == holder:
                bx = int(p['x'])
                by = int(p['y']) - PLAYER_R - 36
                self._draw_bomb_icon(bx, by, tl, exploded)
                break

        # timer bar at top
        self._draw_timer(tl, exploded)

        # pass-range circle around holder (subtle)
        if not exploded and holder >= 0:
            for p in players:
                if p.get('id', -1) == holder:
                    px, py = int(p['x']), int(p['y'])
                    surf = pygame.Surface((120, 120), pygame.SRCALPHA)
                    pygame.draw.circle(surf, (255,120,0,30), (60,60), 60)
                    pygame.draw.circle(surf, (255,120,0,80), (60,60), 60, 2)
                    self.screen.blit(surf, (px-60, py-60))
                    break

        pygame.draw.rect(self.screen, C['border'], (0, 0, ARENA_W, ARENA_H), 4)

    def _draw_bomb_icon(self, cx: int, cy: int, tl: int, exploded: int) -> None:
        t = self._tick
        urgent = tl <= 10 and not exploded

        # pulse when urgent
        r = 18 + (3 if urgent and (t // 8) % 2 == 0 else 0)

        if exploded:
            # explosion burst
            for a in range(0, 360, 30):
                import math
                rad = math.radians(a)
                ex  = cx + int(math.cos(rad) * (r + 14))
                ey  = cy + int(math.sin(rad) * (r + 14))
                pygame.draw.circle(self.screen, (255, 200, 0), (ex, ey), 5)
            pygame.draw.circle(self.screen, (255, 80, 0), (cx, cy), r+8)
            lbl = self.fonts.lg.render('!', True, C['white'])
            self.screen.blit(lbl, (cx - lbl.get_width()//2, cy - lbl.get_height()//2))
            return

        # shadow
        pygame.draw.circle(self.screen, (0,0,0), (cx+3, cy+4), r)
        # body
        col = self._DANGER_COLOR if urgent else self._BOMB_COLOR
        pygame.draw.circle(self.screen, col, (cx, cy), r)
        pygame.draw.circle(self.screen, (0,0,0), (cx, cy), r, 2)
        # shine
        pygame.draw.circle(self.screen, (255,200,100), (cx-r//3, cy-r//3), r//4)
        # fuse spark (blinks)
        if (t // 5) % 2 == 0:
            pygame.draw.circle(self.screen, self._FUSE_COLOR,
                               (cx + r//2, cy - r - 4), 5)
        lbl = self.fonts.md.render('\U0001f4a3', True, C['white'])
        self.screen.blit(lbl, (cx - lbl.get_width()//2, cy - lbl.get_height()//2))

    def _draw_timer(self, tl: int, exploded: int) -> None:
        max_w = ARENA_W - 80
        bar_h = 14
        bx    = 40
        by    = 14

        # background
        pygame.draw.rect(self.screen, (30,30,50), (bx, by, max_w, bar_h), border_radius=7)

        if not exploded and tl > 0:
            ratio = min(tl / 45.0, 1.0)
            fill  = int(max_w * ratio)
            r = int(220 * (1 - ratio))
            g = int(200 * ratio)
            bar_col = (r, g, 20)
            if fill > 0:
                pygame.draw.rect(self.screen, bar_col,
                                 (bx, by, fill, bar_h), border_radius=7)

        pygame.draw.rect(self.screen, C['dim'], (bx, by, max_w, bar_h), 2, border_radius=7)

        label = ('WYBUCH!' if exploded else f'Bomba: {tl}s')
        col   = self._DANGER_COLOR if (exploded or tl <= 10) else C['white']
        lbl   = self.fonts.sm.render(label, True, col)
        self.screen.blit(lbl, (ARENA_W//2 - lbl.get_width()//2, by + bar_h + 6))


class PanelRenderer:
    def __init__(self, screen: pygame.Surface, fonts: Fonts,
                 connected_ref) -> None:
        self.screen        = screen
        self.fonts         = fonts
        self._connected_fn = connected_ref

    def draw(self, state: dict) -> None:
        px = ARENA_W
        pygame.draw.rect(self.screen, C['panel'], (px, 0, PANEL_W, WIN_H))
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

        sc_l = self.fonts.sm.render('WYNIKI', True, C['dim'])
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

        ok = self._connected_fn()
        st = self.fonts.xs.render(
            'Polaczono' if ok else 'Rozlaczono...',
            True, C['green'] if ok else C['red'],
        )
        self.screen.blit(st, (px + PANEL_W//2 - st.get_width()//2, WIN_H - 20))
