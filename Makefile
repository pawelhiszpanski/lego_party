CC     = gcc
CFLAGS = -Wall -Wextra -pthread -O2
TARGET = game_server

all: $(TARGET)

$(TARGET): server.c
	# Flaga -lm została przeniesiona na sam koniec, po server.c
	$(CC) $(CFLAGS) -o $(TARGET) server.c -lm
	@echo "OK: ./$(TARGET)"

clean:
	rm -f $(TARGET)

.PHONY: all clean