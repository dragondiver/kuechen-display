#!/usr/bin/env python3
"""Akku-Wächter für den Waveshare UPS HAT (E) am Küchen-Display (#9).

Liest alle 2 s über I2C (Adresse 0x2D) Ladezustand, Zellspannungen und Akkustrom.
Fällt eine Zelle unter 3150 mV, während der Akku nicht geladen wird, und bleibt das
60 s so, fährt der Pi sauber herunter. Vorher bekommt der HAT den Befehl 0x55 in
Register 0x01: Er schaltet den Strom nach ca. 30 s ab und den Pi wieder ein, sobald
ein Ladegerät steckt. Schwelle und Ablauf entsprechen Waveshares Beispiel `ups.py`.

Den aktuellen Stand schreibt der Wächter nach /run/ups-waechter/status.json, damit
eine Anzeige (Ruhebildschirm, Home Assistant) ihn lesen kann, ohne selbst I2C zu sprechen.

Läuft als systemd-Dienst `ups-waechter.service` (root). Anleitung: docs/akku-waechter.md
"""

import json
import os
import subprocess
import sys
import time

import smbus

ADRESSE = 0x2D
ZELLE_LEER_MV = 3150   # wie Waveshare ups.py
LADESTROM_MA = 50      # darunter gilt der Akku als "lädt nicht"
TAKT_S = 2
FRIST_S = 60
STATUS = "/run/ups-waechter/status.json"


def wort(daten, i):
    return daten[i] | daten[i + 1] << 8


def mit_vorzeichen(wert):
    return wert - 0x10000 if wert > 0x7FFF else wert


def lesen(bus):
    zustand = bus.read_i2c_block_data(ADRESSE, 0x02, 1)[0]
    if zustand & 0x40:
        modus = "schnellladen"
    elif zustand & 0x80:
        modus = "laden"
    elif zustand & 0x20:
        modus = "entladen"
    else:
        modus = "leerlauf"
    vbus = bus.read_i2c_block_data(ADRESSE, 0x10, 6)
    akku = bus.read_i2c_block_data(ADRESSE, 0x20, 12)
    zellen = bus.read_i2c_block_data(ADRESSE, 0x30, 8)
    strom = mit_vorzeichen(wort(akku, 2))
    return {
        "modus": modus,
        "usb_mv": wort(vbus, 0),
        "usb_ma": wort(vbus, 2),
        "usb_mw": wort(vbus, 4),
        "akku_mv": wort(akku, 0),
        "akku_ma": strom,
        "prozent": wort(akku, 4),
        "rest_mah": wort(akku, 6),
        "minuten_bis_leer": wort(akku, 8) if strom < 0 else None,
        "minuten_bis_voll": wort(akku, 10) if strom >= 0 else None,
        "zellen_mv": [wort(zellen, i) for i in (0, 2, 4, 6)],
    }


def status_schreiben(werte):
    werte = dict(werte, zeit=int(time.time()))
    tmp = STATUS + ".tmp"
    with open(tmp, "w") as f:
        json.dump(werte, f)
    os.replace(tmp, STATUS)


def log(text):
    print(text, flush=True)


def herunterfahren():
    log("Akku leer: HAT schaltet nach dem Herunterfahren ab und bei Strom wieder ein")
    try:
        smbus.SMBus(1).write_byte_data(ADRESSE, 0x01, 0x55)
    except OSError as fehler:
        log(f"Befehl an den HAT fehlgeschlagen ({fehler}), fahre trotzdem herunter")
    subprocess.run(["systemctl", "poweroff"], check=False)


def main():
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    bus = smbus.SMBus(1)
    leer_seit = None
    letzter_modus = None
    fehler_in_folge = 0
    while True:
        try:
            werte = lesen(bus)
            fehler_in_folge = 0
        except OSError as fehler:
            fehler_in_folge += 1
            if fehler_in_folge in (1, 30):
                log(f"I2C-Lesefehler: {fehler}")
            time.sleep(TAKT_S)
            continue

        status_schreiben(werte)
        if werte["modus"] != letzter_modus:
            log(f"Zustand {werte['modus']}, Akku {werte['prozent']} %, {werte['akku_mv']} mV")
            letzter_modus = werte["modus"]

        leer = min(werte["zellen_mv"]) < ZELLE_LEER_MV and werte["akku_ma"] < LADESTROM_MA
        if leer:
            if leer_seit is None:
                leer_seit = time.monotonic()
                log(f"Zelle unter {ZELLE_LEER_MV} mV ({werte['zellen_mv']}), Abschalten in {FRIST_S} s, außer es wird geladen")
            elif time.monotonic() - leer_seit >= FRIST_S:
                herunterfahren()
                return 0
        elif leer_seit is not None:
            log("Entwarnung: Akku wird geladen oder Spannung wieder ausreichend")
            leer_seit = None
        time.sleep(TAKT_S)


if __name__ == "__main__":
    sys.exit(main())
