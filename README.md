# 🎮 Party Game – Gra Wieloosobowa Sterowana Smartfonami

Projekt na **Przetwarzanie Współbieżne i Rozproszone**.  
Wieloosobowa gra party, w której gracze sterują przez telefon (przeglądarkę),
a gra wyświetla się na wspólnym ekranie (komputer / TV).

---

## Architektura systemu

```
Telefon 1  ──┐
             │  WebSocket (port 8080)
Telefon 2  ──┼──────────────────────►  bridge.py  ──►  server.c (port 5000)
             │                              │                │
Telefon N  ──┘                      HTTP /  │         game_display.py
                                  controller.html      (TCP port 5000)
```

| Komponent                 | Język   | Rola                                              |
|---------------------------|---------|---------------------------------------------------|
| `server.c`                | C       | Autorytarny serwer gry, logika, state broadcast   |
| `bridge.py`               | Python  | Serwuje HTML telefonom, relayuje WS ↔ TCP         |
| `game_display.py`         | Python  | Okno Pygame – główny ekran gry                    |
| `static/controller.html`  | HTML/JS | D-pad kontroler na telefon                        |
----------------------------|---------|---------------------------------------------------|
---

## Wymagania

- **GCC** (z obsługą POSIX threads)
- **Python 3.8+**
- Biblioteki Python:
  ```bash
  pip install flask flask-sock pygame
  ```

---

## Instalacja i uruchomienie

### 1. Kompilacja serwera C

```bash
make
```
lub ręcznie:
```bash
gcc -Wall -pthread -O2 -o game_server server.c
```

### 2. Uruchom serwer gry (terminal 1)

```bash
./game_server
```

Serwer nasłuchuje na porcie **5000**.

### 3. Uruchom bridge (terminal 2)

```bash
python3 bridge.py
```

Bridge wypisze adres IP do wpisania na telefonie, np.:
```
► Kontroler na telefonie: http://192.168.1.42:8080/
```

### 4. Uruchom wyświetlacz gry (terminal 3)

```bash
python3 game_display.py
```

Otworzy się okno Pygame z planszą gry.

### 5. Podłącz telefony

Na każdym telefonie otwórz w przeglądarce:
```
http://<adres-komputera>:8080/
```
Wpisz imię i kliknij **DOŁĄCZ DO GRY**.

---

## Zasady gry

1. Gra startuje automatycznie gdy dołączą **≥ 2 graczy** (lobby).
2. Na planszy pojawiają się złote **monety** (🪙).
3. Zbieraj monety ruszając się D-padem na telefonie.
4. Gracz z największą liczbą monet po **60 sekundach** wygrywa.
5. Monety respawnują natychmiast po zebraniu.
6. Po zakończeniu gra wraca do lobby po 10 sekundach.

---

## Protokół komunikacyjny (TCP, port 5000)

Wiadomości tekstowe zakończone `\n`.

### Klient → Serwer

| Wiadomość        | Opis                                  |
|------------------|---------------------------------------|
| `JOIN:<name>`    | Dołącz do gry z podanym imieniem      |
| `ACTION:L/R/U/D` | Ruch: lewo / prawo / góra / dół       |
| `PING`           | Heartbeat (co 3 sekundy)              |
| `DISPLAY`        | Rejestracja klienta jako wyświetlacza |

### Serwer → Klient

| Wiadomość        | Opis                                         |
|------------------|----------------------------------------------|
| `WELCOME:<id>`   | Potwierdzenie dołączenia, przydzielony ID     |
| `STATE:<json>`   | Stan gry w JSON (rozsyłany co 50 ms)          |
| `PONG`           | Odpowiedź na PING                            |
| `ERROR:<msg>`    | Komunikat o błędzie                          |
| `DISPLAY_OK`     | Potwierdzenie rejestracji wyświetlacza       |

### Przykład STATE JSON

```json
{
  "phase": 1,
  "time_left": 42,
  "players": [
    {"id": 0, "name": "Dawid",  "x": 120, "y": 300, "score": 5, "color": "red"},
    {"id": 1, "name": "Pawel",  "x": 640, "y": 180, "score": 3, "color": "blue"}
  ],
  "coins": [
    {"x": 320, "y": 240},
    {"x": 500, "y": 420}
  ]
}
```

**Fazy gry:** `0` = lobby, `1` = trwa, `2` = koniec

---

## Mechanizmy spójności (zgodnie z etap2.pdf)

| Zagrożenie         | Zastosowane rozwiązanie                              |
|--------------------|------------------------------------------------------|
| Opóźnienia sieciowe| Autorytarny serwer – logika tylko po stronie C       |
| Jitter             | Pygame interpoluje 30 FPS niezależnie od ticków      |
| Race conditions    | `pthread_mutex_t` chroni cały stan gry               |
| Utrata połączenia  | Heartbeat PING/PONG co 3 s, timeout 8 s → usunięcie  |
| Cheating           | Telefon przesyła tylko intencje (L/R/U/D), nie wynik |
| Drop-in/Drop-out   | Gracze dołączają w lobby, gra toczy się bez przerwy  |

---

## Struktura plików

```
party-game/
├── server.c          ← Serwer gry w C (autorytarny, wielowątkowy)
├── bridge.py         ← HTTP + WebSocket bridge (Flask)
├── game_display.py   ← Wyświetlacz Pygame (główny ekran)
├── Makefile          ← Kompilacja serwera C
├── README.md         ← Ten plik
└── static/
    └── controller.html ← Kontroler D-pad dla telefonu
```

---

## Możliwe rozszerzenia (na przyszłość)

- Więcej minigier (zapis modułowy)
- Sabotaż między graczami (kolizje, power-upy)
- Kod PIN do dołączania (krótki, łatwy do wpisania)
- Asymetria informacji (tajne cele widoczne tylko na telefonie)
- Lepsza grafika (sprite'y zamiast kół)
