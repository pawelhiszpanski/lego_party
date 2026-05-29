#!/usr/bin/env python3
"""
game_display.py  –  Party Game display entry point.

Usage:
    python3 game_display.py              # shows PIN input screen
    python3 game_display.py --pin 1234   # connects directly to room 1234
"""
import argparse
from display.game_display import GameDisplay

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Party Game Display')
    parser.add_argument('--pin', default=None, help='4-digit room PIN')
    args = parser.parse_args()

    GameDisplay(SERVER_HOST, SERVER_PORT, pin=args.pin).run()