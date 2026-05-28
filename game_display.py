#!/usr/bin/env python3
"""

Logika podzielona jest na pakiet display/:
    display/constants.py    – stałe kolorów i rozmiarów
    display/fonts.py        – zestaw czcionek Pygame
    display/network.py      – klient TCP (odbiera stan z serwera C)
    display/renderers.py    – klasy rysujące poszczególne ekrany
    display/game_display.py – główna klasa GameDisplay

Fazy: 0=LOBBY  1=VOTING  2=COINS  3=PONG  4=ENDED
"""

from display.game_display import GameDisplay

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000

if __name__ == '__main__':
    print(f'[DISPLAY] Łączenie z {SERVER_HOST}:{SERVER_PORT}…')
    GameDisplay(SERVER_HOST, SERVER_PORT).run()