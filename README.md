# 🎮 LEGO Party Clone

Wieloosobowa, sieciowa gra imprezowa typu arkadowego, zbudowana w architekturze rozproszonej na potrzeby projektu z przedmiotu **Przetwarzanie Współbieżne i Rozproszone**. 

Rozgrywka opiera się na koncepcji wspólnego ekranu (np. telewizor/monitor z uruchomionym modułem graficznym), gdzie sterowanie postaciami odbywa się asynchronicznie za pomocą smartfonów połączonych z lokalną siecią bez konieczności instalowania zewnętrznych aplikacji.

---

## 📐 Architektura Systemu

System działa w architekturze hybrydowej, łącząc wysokowydajny serwer dedykowany (C), warstwę translacji protokołów (Python WebSockets) oraz klientów renderujących.

```text
Telefon 1  ──┐
             │   WebSocket (port 8080)
Telefon 2  ──┼────────────────────────► bridge.py ──► server.c (port 5000)
             │                                │              │
Telefon N  ──┘                       HTTP /   │       game_display.py
                                 controller.html      (TCP port 5000)
```

### Komponenty Systemu

|            Komponent          |   Język  |                                     Rola w architekturze                                                 |
| ----------------------------- | -------- | -------------------------------------------------------------------------------------------------------- |
| **`server.c`**                | C        | Autorytarny serwer gry. Zarządza maszyną stanów, współbieżną obsługą klientów, fizyką i synchronizacją.  |
| **`bridge.py`**               | Python   | Serwer HTTP oraz asynchroniczny translator protokołów (Full-Duplex Relay: WebSockets ↔ TCP).             |
| **`game_display.py`**         | Python   | Klient renderujący. Pobiera stan gry i wyświetla główną planszę (Pygame, ~60 FPS).                       |
| **`static/controller.html`**  | HTML/JS  | Lekki interfejs kontrolera uruchamiany w przeglądarce mobilnej (Web-based D-pad).                        |

---

## ⚙️ Wymagania systemowe

* **Kompilator:** GCC z pełną obsługą wątków POSIX (`pthread`) oraz biblioteki matematycznej (`-lm`).
* **Środowisko:** Python 3.8+
* **Zależności Pythona:** `flask`, `flask-sock`, `pygame`

Instalacja pakietów w środowisku wirtualnym:
```bash
python3 -m venv venv
source venv/bin/activate
pip install flask flask-sock pygame
```

---

## 🚀 Instalacja i Uruchomienie

### 1. Kompilacja serwera (C)
Skompiluj serwer za pomocą dołączonego pliku `Makefile`:
```bash
make
```
*Alternatywnie (ręcznie): gcc -Wall -Wextra -pthread -O2 -o game_server server.c -lm*

### 2. Uruchomienie Serwera Gry (Terminal 1)
```bash
./game_server
```
*Serwer rozpocznie nasłuchiwanie na porcie TCP 5000.*

### 3. Uruchomienie Bridge'a sieciowego (Terminal 2)
```bash
python3 bridge.py
```
*Serwer Flask wystartuje na porcie 8080. W konsoli pojawi się lokalny adres IP dla telefonów (np. http://192.168.0.113:8080/).*

### 4. Uruchomienie Głównego Ekranu Gry (Terminal 3)
```bash
python3 game_display.py
```
*Otworzy się okno graficzne Pygame z podglądem areny.*

### 5. Dołączanie do rozgrywki
Otwórz przeglądarkę na smartfonie (urządzenie musi być w tej samej sieci Wi-Fi) i przejdź pod adres wskazany przez `bridge.py`. Wpisz swój nick i dołącz do gry.

---

## 🕹️ Mechanika Rozgrywki i Fazy Gry

Gra zorganizowana jest wokół centralnej maszyny stanów realizowanej przez wątek główny serwera:

1. **`PHASE_LOBBY` (Faza 0):** Oczekiwanie na graczy (wymagane minimum 2 osoby). Po dołączeniu graczy host może wymusić przejście dalej za pomocą przycisku na telefonie.
2. **`PHASE_VOTING` (Faza 1):** Trwające 10 sekund demokratyczne głosowanie na tryb gry. Do wyboru: Zbieranie monet, Pong lub losowanie.
3. **`PHASE_COINS` (Faza 2):** Tryb zbierania złotych monet (🪙) na arenie o wymiarach 800x600 pikseli w czasie 30 sekund.
4. **`PHASE_PONG` (Faza 3):** Zręcznościowy Pong dla wszystkich połączonych graczy (podział na drużynę lewą i prawą). Rozgrywka toczy się do 3 punktów, a piłka przyspiesza po każdym odbiciu.
5. **`PHASE_ENDED` (Faza 4):** Ekran podsumowania i prezentacja zwycięzcy. Po 8 sekundach system automatycznie wraca do Lobby.

---

## 🛰️ Protokół Komunikacyjny (TCP, port 5000)

Wszystkie wiadomości przesyłane są asynchronicznie jako ciągi tekstowe UTF-8 zakończone znakiem nowej linii (`\n`).

### Klient → Serwer
* `JOIN:<name>` – Żądanie rejestracji gracza o podanym imieniu.
* `ACTION:<kierunki>` – Przesłanie intencji ruchu (np. `ACTION:U`, `ACTION:RD`). Obsługuje składowe: **L**eft, **R**ight, **U**p, **D**own.
* `START` – Sygnał wymuszenia startu głosowania z poziomu poczekalni.
* `VOTE:<A/B/C>` – Oddanie głosu w fazie wyboru minigry.
* `PING` – Ramka kontrolna obecności klienta (Heartbeat send co 3s).
* `DISPLAY` – Rejestracja dedykowanego klienta graficznego (Pygame).

### Serwer → Klient
* `WELCOME:<id>` – Potwierdzenie rejestracji w strukturach serwera, zwraca przydzielony ID (0-3).
* `DISPLAY_OK` – Potwierdzenie autoryzacji ekranu głównego.
* `PONG` – Odpowiedź na ramkę żywotności.
* `ERROR:<msg>` – Komunikat błędu (np. pełny serwer, gra w toku).
* `STATE:<json_string>` – Pełny zrzut stanu gry wysyłany w pętli co ~16.6 ms (~60 TPS).

### Format ramki stanowej JSON (Przykład)
```json
{
  "phase": 1,
  "time_left": 30,
  "vote_left": 10,
  "last_game": 0,
  "va": 1, "vb": 0, "vc": 1,
  "votes": [0, -1, 2, -1],
  "players": [
    {"id": 0, "name": "Pawel", "x": 80, "y": 100, "score": 0, "color": "red", "team": 0}
  ],
  "coins": [
    {"x": 421, "y": 210}
  ],
  "pong": {"bx": 400.0, "by": 300.0, "vx": 6.2, "vy": -2.1, "py0": 300.0, "py1": 300.0, "score0": 0, "score1": 0, "win": -1, "spd": 9.0}
}
```

---

## 🔒 Rozwiązania Współbieżności i Problemów Sieciowych

| Zagrożenie / Problem | Zastosowane rozwiązanie |
| :--- | :--- |
| **Wyścigi (Race Conditions)** | Dostęp do krytycznych struktur danych (`players`, `coins`, `pong`) po stronie C jest w pełni izolowany za pomocą struktur blokad `pthread_mutex_t`. |
| **Opóźnienia (Network Latency)** | Model **sztywnego autorytarnego serwera** (Server-Authoritative). Klienci mobilni przesyłają jedynie intencje wejściowe (`ACTION`), cała fizyka i detekcja kolizji obliczana jest centralnie na serwerze. |
| **Zjawisko Jitteru** | Niezależny mechanizm taktowania pętli renderowania Pygame (~60 FPS) stosuje ciągłą interpolację liniową dla pozycji piłki i graczy, eliminując rwanie obrazu przy wahaniach pakietów. |
| **Nagłe rozłączenia (Drop-out)** | Mechanizm Heartbeatu. Brak ramki `PING` od klienta przez ponad 8 sekund (`HEARTBEAT_TIMEOUT`) skutkuje automatycznym wyczyszczeniem slotu gracza i zwolnieniem zasobów. |
| **Oszustwa (Cheating)** | Całkowity brak zaufania do klienta. Telefon nie zna pozycji monet ani innych graczy i nie decyduje o zmianie współrzędnych – serwer odrzuca niepoprawne pakiety. |

---

## 📁 Struktura Projektu

```text
lego_party/
├── server.c            # Wielowątkowy rdzeń serwera gry (C)
├── bridge.py           # Translator WebSocket ↔ TCP (Flask-Sock)
├── game_display.py     # Silnik renderowania i wizualizacji (Pygame)
├── Makefile            # Skrypt automatyzujący budowanie projektu
├── .gitignore          # Filtrowanie plików środowiska i binariów
└── static/
    └── controller.html # Responsywny kontroler mobilny (HTML5/JS)
```
