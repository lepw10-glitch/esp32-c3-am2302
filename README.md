# ESP32-C3 + AM2302 mit OLED und Python-Dashboard

Ein ESP32-C3 liest einen AM2302 (DHT22) aus, zeigt Temperatur und Luftfeuchte auf dem eingebauten OLED und gibt sie per USB-Serial aus. Ein Flask-Dashboard (nur localhost) zeigt Live-Werte und Verläufe.

## Hardware

- AYWHP ESP32-C3 (ESP32-C3FH4, 4 MB Flash, USB-C) mit OLED 0,42" 72x40 (SSD1306-kompatibel)
- AM2302 / DHT22

| Bauteil | Anschluss |
|---|---|
| OLED SDA | GPIO 5 (fest auf dem Board) |
| OLED SCL | GPIO 6 (fest auf dem Board) |
| AM2302 "+" | 3V3 |
| AM2302 "OUT" | GPIO 4 |
| AM2302 "-" | GND |

## Firmware (`firmware/`)

PlatformIO, Arduino-Framework. Bibliotheken: U8g2 und `beegee-tokyo/DHT sensor library for ESPx` (Include `<DHTesp.h>`).
Die Build-Flags `-DARDUINO_USB_MODE=1` und `-DARDUINO_USB_CDC_ON_BOOT=1` sind nötig, damit Serial über das native USB funktioniert.

Alle 10 s eine Messung. Serial-Format pro Messung: `T=22.8 H=48.3` (115200 Baud). Bei Sensorfehler zeigt das OLED "Sensor Fehler".

Flashen: in `firmware/` mit PlatformIO `Upload` ausführen.

## Dashboard

Installation (venv nicht aktivieren, direkt aufrufen):

```
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start: `dashboard.bat` (öffnet http://127.0.0.1:5000) oder `venv\Scripts\python.exe dashboard.py`.

- Der COM-Port wird automatisch über die Espressif-USB-VID 0x303A erkannt, Wiederverbindung alle 2 s.
- Alle 5 Minuten ein Eintrag in `messdaten.csv` (`YYYY-MM-DD HH:MM:SS;temp;hum`), der Verlauf wird beim Start wieder geladen.
- Chart.js kommt per CDN, das Dashboard braucht dafür Internet.
- Das Dashboard lauscht bewusst nur auf `127.0.0.1`.

## Hinweise

- Der COM-Port ist exklusiv: Serial Monitor und Upload nur, wenn das Dashboard beendet ist.
- `messdaten.csv` ist per `.gitignore` ausgeschlossen.
