import pygame


def _best_font(names: list[str], size: int, bold: bool = False) -> pygame.font.Font:
    for name in names:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.SysFont('arial', size, bold=bold)


_PREF = ['ubuntumono', 'ubuntu', 'dejavusans', 'liberationsans', 'freesans', 'arial']


class Fonts:
    def __init__(self) -> None:
        self.xl = _best_font(_PREF, 52, bold=True)
        self.lg = _best_font(_PREF, 36, bold=True)
        self.md = _best_font(_PREF, 26)
        self.sm = _best_font(_PREF, 18)
        self.xs = _best_font(_PREF, 14)
