import socket
import threading
import time
import json
from typing import Any


class NetworkClient:
    DEFAULT_STATE: dict[str, Any] = {
        'phase': 0, 'time_left': 30, 'vote_left': 10,
        'va': 0, 'vb': 0, 'vc': 0, 'votes': [-1, -1, -1, -1],
        'last_game': 0, 'players': [], 'coins': [],
        'pong': {
            'bx': 400, 'by': 300,
            'py0': 300, 'py1': 300,
            's0': 0, 's1': 0,
            'win': -1, 'spd': 9.0,
        },
    }

    def __init__(self, host: str, port: int) -> None:
        self.host      = host
        self.port      = port
        self.state     = dict(self.DEFAULT_STATE)
        self.lock      = threading.Lock()
        self.connected = False

    def start(self) -> None:
        """Uruchamia wątek tła nawiązujący i utrzymujący połączenie."""
        threading.Thread(target=self._run, daemon=True).start()

    def get_state(self) -> dict[str, Any]:
        """Zwraca kopię aktualnego stanu (bezpieczna dla wątku renderującego)."""
        with self.lock:
            return dict(self.state)
        

    def _run(self) -> None:
        while True:
            try:
                sock = socket.socket()
                sock.connect((self.host, self.port))
                sock.send(b'DISPLAY\n')
                self.connected = True
                buf = b''
                while True:
                    data = sock.recv(8192)
                    if not data:
                        break
                    buf += data
                    while b'\n' in buf:
                        line, buf = buf.split(b'\n', 1)
                        msg = line.decode('utf-8', errors='replace')
                        if msg.startswith('STATE:'):
                            try:
                                with self.lock:
                                    self.state = json.loads(msg[6:])
                            except Exception:
                                pass
                sock.close()
            except Exception as e:
                print(f'[DISPLAY] {e}, retry za 2s')
            finally:
                self.connected = False
                time.sleep(2)
