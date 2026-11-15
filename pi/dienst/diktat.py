"""Diktat ins Suchfeld einer App, ohne Elektra (kuechen-display#70).

Festlegung 15.11.2026: Der Ton geht an die OpenAI-Transkription (`gpt-transcribe`), weil man in
Spotify meist nach Namen sucht. Der Küchen-Dienst nimmt Kanal 0 des XVF3800 auf, solange die
Rückweg-Leiste ein Diktat offen hat, und schickt ihn am Ende als WAV.

Ende (Festlegung 15.11.2026): nach STILLE_S Ruhe im Anschluss an Sprache, auf Tipp, nach
OHNE_SPRACHE_S ohne erkannte Sprache oder nach MAX_S. „Sprache“ und „Ruhe“ misst der Pegel jedes
Rahmens gegen den Boden (10. Perzentil der Rahmen vor der Sprache, danach eingefroren, sonst wandert
er bei langem Sprechen mit nach oben), damit Kühlschrank oder leise Musik nicht als Sprache zählen. Die Schwellen sind Startwerte und werden am Display nachgestellt.
Ohne Fremdpakete (urllib), wie hass.py.
"""

from __future__ import annotations

import json
import math
import re
import secrets
import struct
import threading
import urllib.error
import urllib.request
from array import array

ADRESSE = "https://api.openai.com/v1/audio/transcriptions"
MODELL = "gpt-transcribe"
# Deutsch und Englisch: deutsche Ansagen, englische Band- und Songnamen.
SPRACHEN = ("de", "en")
MAX_S = 20.0  # danach nimmt der Dienst nichts mehr auf, auch ohne Stopp
MIN_S = 0.3  # kürzer ist ein Fehltipp, dafür geht nichts an OpenAI
STILLE_S = 2.0  # so lange Ruhe nach Sprache beendet das Diktat (Florian 15.11.)
OHNE_SPRACHE_S = (
    10.0  # Bedenkzeit; ohne erkannte Sprache bis hierhin: Ende (Florian 15.11.)
)
KALIBRIER_S = 0.24  # erst danach wird verglichen, vorher gibt es keinen Boden
SPRACHE_DB = 15.0  # Pegel über dem Boden, ab dem ein Rahmen als Sprache zählt
SPRACHE_RAHMEN = 3  # so viele Sprach-Rahmen hintereinander, damit kein Klappern zählt
STILLE_DB = 8.0  # darunter (über dem Boden) zählt ein Rahmen als Ruhe


def pegel_db(pcm: bytes) -> float:
    """RMS eines PCM16-Rahmens in dBFS; Stille gibt -100."""
    proben = array("h")
    proben.frombytes(pcm[: len(pcm) // 2 * 2])
    if not proben:
        return -100.0
    rms = math.sqrt(sum(p * p for p in proben) / len(proben))
    return 20 * math.log10(rms / 32768) if rms > 0 else -100.0


class Aufnahme:
    """Puffer für ein Diktat mit Ende bei Ruhe. Kennt weder Mikrofon noch Netz."""

    def __init__(self, rate: int) -> None:
        self.rate = rate
        self.aktiv = False
        self.ton = bytearray()
        self.pegel: list[float] = []
        self.dauern: list[float] = []
        self.sprache = False
        self.boden_db = -100.0
        self.ruhe_s = 0.0
        self.grund = ""
        # Jede Aufnahme bekommt eine Nummer; ein veraltetes „ergebnis“ (Seite neu geladen,
        # neues Diktat gestartet) erkennt daran, dass es leer ausgeht (verifier zu #72).
        self.nummer = 0
        self.fertig = threading.Event()
        self.fertig.set()

    def start(self) -> int:
        self.beenden(
            "neu gestartet"
        )  # weckt ein wartendes „ergebnis“ der alten Aufnahme
        self.nummer += 1
        self.ton = bytearray()
        self.pegel, self.dauern = [], []
        self.sprache = False
        self.boden_db = -100.0
        self.ruhe_s = 0.0
        self.grund = ""
        self.fertig.clear()
        self.aktiv = True
        return self.nummer

    def beenden(self, grund: str) -> None:
        if self.aktiv:
            self.aktiv = False
            self.grund = grund
        self.fertig.set()

    def rahmen(self, pcm: bytes) -> None:
        if not self.aktiv:
            return
        platz = int(MAX_S * self.rate) * 2 - len(self.ton)
        self.ton += pcm[: max(platz, 0)]
        if platz <= len(pcm):
            return self.beenden("max")
        self.pegel.append(pegel_db(pcm))
        self.dauern.append(len(pcm) / 2 / self.rate)
        bisher = self.sekunden(self.ton)
        if bisher < KALIBRIER_S:
            return
        if not self.sprache:
            self.boden_db = sorted(self.pegel)[len(self.pegel) // 10]
        boden = self.boden_db
        if not self.sprache:
            letzte = self.pegel[-SPRACHE_RAHMEN:]
            if len(letzte) == SPRACHE_RAHMEN and min(letzte) > boden + SPRACHE_DB:
                self.sprache = True
            elif bisher >= OHNE_SPRACHE_S:
                self.beenden("keine Sprache")
            return
        if self.pegel[-1] < boden + STILLE_DB:
            self.ruhe_s += self.dauern[-1]
            if self.ruhe_s >= STILLE_S - 1e-9:
                self.beenden("Ruhe")
        else:
            self.ruhe_s = 0.0

    def nehmen(self) -> bytes:
        """Den aufgenommenen Ton herausnehmen; beendet eine laufende Aufnahme."""
        self.beenden(self.grund or "Tipp")
        ton, self.ton = bytes(self.ton), bytearray()
        return ton

    def spitze(self) -> float:
        return max(self.pegel, default=-100.0)

    def sekunden(self, ton: bytes) -> float:
        return len(ton) / 2 / self.rate


def wav(pcm: bytes, rate: int) -> bytes:
    """Mono PCM16 als WAV."""
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(pcm))
        + pcm
    )


def formular(
    felder: list[tuple[str, str]], datei: bytes, name: str = "diktat.wav"
) -> tuple[bytes, str]:
    """multipart/form-data mit Textfeldern und einer WAV-Datei unter `file`."""
    grenze = "kuechen" + secrets.token_hex(12)
    teile = []
    for feld, wert in felder:
        teile.append(
            f'--{grenze}\r\nContent-Disposition: form-data; name="{feld}"\r\n\r\n{wert}\r\n'.encode()
        )
    teile.append(
        f'--{grenze}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
        "Content-Type: audio/wav\r\n\r\n".encode()
        + datei
        + b"\r\n"
    )
    teile.append(f"--{grenze}--\r\n".encode())
    return b"".join(teile), f"multipart/form-data; boundary={grenze}"


class DiktatFehler(Exception):
    pass


def transkribieren(
    pcm: bytes, rate: int, schluessel: str, modell: str = MODELL, timeout: float = 8
) -> str:
    felder = [("model", modell), ("response_format", "json")]
    felder += [("languages[]", s) for s in SPRACHEN]
    rumpf, art = formular(felder, wav(pcm, rate))
    anfrage = urllib.request.Request(
        ADRESSE,
        data=rumpf,
        headers={"Authorization": f"Bearer {schluessel}", "Content-Type": art},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
            return str(json.load(antwort).get("text", "")).strip()
    except urllib.error.HTTPError as fehler:
        text = fehler.read().decode(errors="replace")[:300]
        # OpenAI zitiert einen falschen Schlüssel teilweise („sk-…xxxx“); nichts davon ins Journal.
        text = re.sub(r"sk-[A-Za-z0-9_*\-…]+", "sk-…", text)
        raise DiktatFehler(f"OpenAI {fehler.code}: {text}") from None
    except ValueError as fehler:  # 200, aber kein JSON
        raise DiktatFehler(f"OpenAI-Antwort unlesbar: {fehler}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as fehler:
        raise DiktatFehler(f"OpenAI nicht erreichbar: {fehler}") from None
