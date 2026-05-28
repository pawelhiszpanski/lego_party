import pygame


class Fonts:
    def __init__(self) -> None:
        self.xl = pygame.font.SysFont('Arial', 52, bold=True)
        self.lg = pygame.font.SysFont('Arial', 36, bold=True)
        self.md = pygame.font.SysFont('Arial', 26)
        self.sm = pygame.font.SysFont('Arial', 18)
        self.xs = pygame.font.SysFont('Arial', 14)
