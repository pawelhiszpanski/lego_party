#!/usr/bin/env python3
"""
Telefon (przeglądarka)
    └── WebSocket ws://<IP>:8080/ws
         └── bridge.py
              └── TCP 127.0.0.1:5000
                   └── server (C)
"""

import threading
import socket
import os
import sys

from flask import Flask, send_from_directory
from flask_sock import Sock

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000
BRIDGE_PORT = 8080
STATIC_DIR  = os.path.join(os.path.dirname(__file__), 'static')

app  = Flask(__name__)
sock = Sock(app)

@app.route('/')
def index():
    """Serwuje stronę kontrolera dla telefonu."""
    return send_from_directory(STATIC_DIR, 'controller.html')

@sock.route('/ws')
def websocket_handler(ws):
    """
    Każdy telefon dostaje osobne połączenie TCP do serwera gry.
    Dane płyną w obie strony:
        telefon  →  WebSocket  →  bridge  →  TCP  →  serwer C
        serwer C →  TCP        →  bridge  →  WebSocket  →  telefon
    """
    try:
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp.settimeout(5)
        tcp.connect((SERVER_HOST, SERVER_PORT))
        tcp.settimeout(None)
    except Exception as e:
        try:
            ws.send(f'ERROR:Brak połączenia z serwerem: {e}')
        except Exception:
            pass
        return

    stop = threading.Event()

    def server_to_phone():
        buf = b''
        while not stop.is_set():
            try:
                tcp.settimeout(1.0)
                chunk = tcp.recv(4096)
                if not chunk:
                    break
                buf += chunk

                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    msg = line.decode('utf-8', errors='replace')
                    try:
                        ws.send(msg)
                    except Exception:
                        stop.set()
                        return
            except socket.timeout:
                continue
            except Exception:
                break
        stop.set()

    relay_thread = threading.Thread(target=server_to_phone, daemon=True)
    relay_thread.start()

    try:
        while not stop.is_set():
            try:
                msg = ws.receive(timeout=30)
            except Exception:
                break
            if msg is None:
                break
            try:
                tcp.send((msg.strip() + '\n').encode())
            except Exception:
                break
    except Exception:
        pass
    finally:
        stop.set()
        try:
            tcp.close()
        except Exception:
            pass



if __name__ == '__main__':
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = '127.0.0.1'

    print('=' * 55)
    print('  Party Game – Bridge Server')
    print('=' * 55)
    print(f'  Serwer gry (C): {SERVER_HOST}:{SERVER_PORT}')
    print(f'  Bridge HTTP/WS: 0.0.0.0:{BRIDGE_PORT}')
    print()
    print(f'  ► Kontroler na telefonie:')
    print(f'    http://{local_ip}:{BRIDGE_PORT}/')
    print()
    print('  Upewnij się że serwer gry (./game_server) jest')
    print('  uruchomiony przed otwarciem strony na telefonie.')
    print('=' * 55)

    app.run(host='0.0.0.0', port=BRIDGE_PORT, threaded=True)
