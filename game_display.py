#!/usr/bin/env python3
"""
game_display.py  –  Party Game display.

Run:  python3 game_display.py
Connects automatically to bridge.py (TCP 127.0.0.1:5000).
The room PIN is shown on screen – no manual input needed.
"""
from display.game_display import GameDisplay

if __name__ == '__main__':
    GameDisplay().run()