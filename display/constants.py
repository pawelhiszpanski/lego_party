"""
display/constants.py
Stałe kolorów, rozmiarów i etykiet używanych w całym module display.
"""

ARENA_W, ARENA_H = 800, 600
PANEL_W          = 260
WIN_W            = ARENA_W + PANEL_W
WIN_H            = ARENA_H
FPS              = 60

PAD_W, PAD_H = 14, 88
BALL_R       = 10
PAD_X0       = PAD_W
PAD_X1       = ARENA_W - PAD_W * 2

C: dict[str, tuple[int, int, int]] = {
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

PLAYER_RGB: dict[str, tuple[int, int, int]] = {
    'red':    C['p_red'],
    'blue':   C['p_blue'],
    'green':  C['p_green'],
    'yellow': C['p_yellow'],
}

PLAYER_R = 22

PHASE_LBL = ['LOBBY', 'GŁOSOWANIE', 'ZBIERANIE MONET', 'PONG', 'KONIEC', 'HOT POTATO']
PHASE_COL = [C['gold'], C['vote_c'], C['green'], C['vote_b'], C['red'], (220, 100, 20)]
