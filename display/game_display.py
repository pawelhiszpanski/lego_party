import sys
import pygame

from display.constants import WIN_W, WIN_H, FPS, ARENA_W, ARENA_H, C, PLAYER_RGB
from display.fonts import Fonts
from display.network import NetworkClient
from display.renderers import (
    ArenaRenderer, CoinRenderer, PlayerRenderer,
    PongRenderer, VotingRenderer, LobbyRenderer,
    BombRenderer, PanelRenderer,
)


class GameDisplay:
    def __init__(self, server_host: str = '127.0.0.1',
                 server_port: int = 5000,
                 pin: str | None = None) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption('Party Game v3 – Display')
        self.clock  = pygame.time.Clock()
        self._tick  = 0

        self._fonts = Fonts()

        # get PIN before starting network
        if not pin:
            pin = self._pin_screen()

        self.net = NetworkClient(server_host, server_port, pin=pin)
        self.net.start()

        arena_r  = ArenaRenderer(self.screen, self._fonts)
        coin_r   = CoinRenderer(self.screen, self._fonts)
        player_r = PlayerRenderer(self.screen, self._fonts)

        self.pong_r   = PongRenderer(self.screen, self._fonts)
        self.voting_r = VotingRenderer(self.screen, self._fonts)
        self.lobby_r  = LobbyRenderer(self.screen, self._fonts, arena_r, player_r)
        self.bomb_r   = BombRenderer(self.screen, self._fonts, arena_r, player_r)
        self.panel_r  = PanelRenderer(self.screen, self._fonts,
                                      lambda: self.net.connected)

        self._arena_r  = arena_r
        self._coin_r   = coin_r
        self._player_r = player_r

    def _pin_screen(self) -> str:
        clock = pygame.time.Clock()
        pin   = ''
        f     = self._fonts

        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()
                    elif e.key == pygame.K_BACKSPACE:
                        pin = pin[:-1]
                    elif e.key == pygame.K_RETURN and len(pin) == 4:
                        return pin
                    elif e.unicode.isdigit() and len(pin) < 4:
                        pin += e.unicode

            self.screen.fill(C['bg'])

            # centered card
            cw, ch = 420, 300
            cx = WIN_W // 2 - cw // 2
            cy = WIN_H // 2 - ch // 2
            pygame.draw.rect(self.screen, C['panel'], (cx, cy, cw, ch), border_radius=20)
            pygame.draw.rect(self.screen, C['border'], (cx, cy, cw, ch), 2, border_radius=20)

            t1 = f.lg.render('\U0001f3ae Party Game', True, C['gold'])
            t2 = f.md.render('Enter Room PIN', True, C['white'])
            self.screen.blit(t1, (WIN_W//2 - t1.get_width()//2, cy + 28))
            self.screen.blit(t2, (WIN_W//2 - t2.get_width()//2, cy + 80))

            # PIN boxes
            bw, bh, gap = 60, 72, 14
            total = 4 * bw + 3 * gap
            bx0   = WIN_W // 2 - total // 2
            for i in range(4):
                bx = bx0 + i * (bw + gap)
                by = cy + 130
                filled = i < len(pin)
                col    = C['vote_b'] if filled else C['row_lo']
                pygame.draw.rect(self.screen, col, (bx, by, bw, bh), border_radius=10)
                pygame.draw.rect(self.screen, C['border'], (bx, by, bw, bh), 2, border_radius=10)
                if filled:
                    d = f.xl.render(pin[i], True, C['white'])
                    self.screen.blit(d, (bx + bw//2 - d.get_width()//2,
                                        by + bh//2 - d.get_height()//2))

            hint_col = C['green'] if len(pin) == 4 else C['dim']
            hint     = f.sm.render('Press ENTER to connect' if len(pin) == 4
                                   else 'Type 4-digit PIN', True, hint_col)
            self.screen.blit(hint, (WIN_W//2 - hint.get_width()//2, cy + 228))

            pygame.display.flip()
            clock.tick(30)

    def run(self) -> None:
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()

            self._tick += 1
            self.screen.fill(C['bg'])
            state = self.net.get_state()
            phase = state.get('phase', 0)

            if phase == 0:
                self.lobby_r.draw(state)
            elif phase == 1:
                self.voting_r.draw(state)
            elif phase == 2:
                self._arena_r.draw(state)
                for coin in state.get('coins', []):
                    self._coin_r.draw_coin(coin['x'], coin['y'], self._tick)
                for p in state.get('players', []):
                    self._player_r.draw_player(p, tick=self._tick)
            elif phase == 3:
                self.pong_r.draw(state, show_win_overlay=True)
            elif phase == 4:
                self._draw_ended(state)
            elif phase == 5:
                self.bomb_r.draw(state)

            self.panel_r.draw(state, fps=self.clock.get_fps())
            pygame.display.flip()
            self.clock.tick(FPS)

    def _draw_ended(self, state: dict) -> None:
        last_game = state.get('last_game', 0)
        if last_game == 1:
            self.pong_r.draw(state, show_win_overlay=False)
        elif last_game == 2:
            self.bomb_r.draw(state)
        else:
            self._arena_r.draw(state)
            for p in state.get('players', []):
                self._player_r.draw_player(p, tick=self._tick)
        self._draw_end_overlay(state, last_game)

    def _draw_end_overlay(self, state: dict, last_game: int) -> None:
        f = self._fonts
        ov = pygame.Surface((ARENA_W, 160), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        self.screen.blit(ov, (0, ARENA_H//2 - 80))

        go = f.xl.render('GAME OVER!', True, C['gold'])
        self.screen.blit(go, (ARENA_W//2 - go.get_width()//2, ARENA_H//2 - 60))

        if last_game == 1:
            win = state.get('pong', {}).get('win', -1)
            if win >= 0:
                col = C['pad0'] if win == 0 else C['pad1']
                wn  = f.lg.render(f'Team {win} wins!', True, col)
                self.screen.blit(wn, (ARENA_W//2 - wn.get_width()//2, ARENA_H//2))
        elif last_game == 2:
            holder  = state.get('bomb', {}).get('holder', -1)
            for p in state.get('players', []):
                if p.get('id', -1) == holder:
                    col = PLAYER_RGB.get(p.get('color','red'), C['white'])
                    wn  = f.lg.render(f'{p["name"]} exploded!', True, col)
                    self.screen.blit(wn, (ARENA_W//2 - wn.get_width()//2, ARENA_H//2))
                    break
        else:
            players = sorted(state.get('players', []), key=lambda x: -x.get('score', 0))
            if players:
                winner = players[0]
                wc = PLAYER_RGB.get(winner.get('color','red'), C['white'])
                wn = f.lg.render(f'{winner["name"]} wins!', True, wc)
                self.screen.blit(wn, (ARENA_W//2 - wn.get_width()//2, ARENA_H//2))
