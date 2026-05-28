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
                 server_port: int = 5000) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption('Party Game v3')
        self.clock  = pygame.time.Clock()

        fonts = Fonts()

        self.net = NetworkClient(server_host, server_port)
        self.net.start()

        arena_r  = ArenaRenderer(self.screen, fonts)
        coin_r   = CoinRenderer(self.screen, fonts)
        player_r = PlayerRenderer(self.screen, fonts)

        self.pong_r   = PongRenderer(self.screen, fonts)
        self.voting_r = VotingRenderer(self.screen, fonts)
        self.lobby_r  = LobbyRenderer(self.screen, fonts, arena_r, player_r)
        self.bomb_r   = BombRenderer(self.screen, fonts, arena_r, player_r)
        self.panel_r  = PanelRenderer(self.screen, fonts,
                                      lambda: self.net.connected)

        self._arena_r  = arena_r
        self._coin_r   = coin_r
        self._player_r = player_r
        self._fonts    = fonts

    def run(self) -> None:
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()

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
                    self._coin_r.draw_coin(coin['x'], coin['y'])
                for p in state.get('players', []):
                    self._player_r.draw_player(p)

            elif phase == 3:
                # show_win_overlay=True only during active pong
                self.pong_r.draw(state, show_win_overlay=True)

            elif phase == 4:
                self._draw_ended(state)

            elif phase == 5:
                self.bomb_r.draw(state)

            self.panel_r.draw(state)
            pygame.display.flip()
            self.clock.tick(FPS)

    def _draw_ended(self, state: dict) -> None:
        last_game = state.get('last_game', 0)

        if last_game == 1:
            # pong ended - draw frozen board without mid-game overlay
            self.pong_r.draw(state, show_win_overlay=False)
        elif last_game == 2:
            # bomb ended
            self.bomb_r.draw(state)
        else:
            self._arena_r.draw(state)
            for p in state.get('players', []):
                self._player_r.draw_player(p)

        self._draw_end_overlay(state, last_game)

    def _draw_end_overlay(self, state: dict, last_game: int) -> None:
        f   = self._fonts
        ov  = f.xl.render('KONIEC!', True, C['gold'])
        self.screen.blit(ov, (ARENA_W//2 - ov.get_width()//2, ARENA_H//2 - 60))

        if last_game == 1:
            # pong: show winning team only
            win = state.get('pong', {}).get('win', -1)
            if win >= 0:
                col = C['pad0'] if win == 0 else C['pad1']
                wn  = f.lg.render(f'Druzyna {win} wygrywa!', True, col)
                self.screen.blit(wn, (ARENA_W//2 - wn.get_width()//2, ARENA_H//2))
        elif last_game == 2:
            # bomb: loser is the one who held it (score=0), winners have score=1
            bomb    = state.get('bomb', {})
            holder  = bomb.get('holder', -1)
            players = state.get('players', [])
            for p in players:
                if p.get('id', -1) == holder:
                    col = PLAYER_RGB.get(p.get('color','red'), C['white'])
                    wn  = f.lg.render(f'{p["name"]} wysadzony!', True, col)
                    self.screen.blit(wn, (ARENA_W//2 - wn.get_width()//2, ARENA_H//2))
                    break
        else:
            # coins: show winning player
            players = sorted(state.get('players', []),
                             key=lambda x: -x.get('score', 0))
            if players:
                winner = players[0]
                wc = PLAYER_RGB.get(winner.get('color','red'), C['white'])
                wn = f.lg.render(f'{winner["name"]} wygrywa!', True, wc)
                self.screen.blit(wn, (ARENA_W//2 - wn.get_width()//2, ARENA_H//2))
