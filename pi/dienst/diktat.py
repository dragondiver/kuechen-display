"""Diktat ins Suchfeld einer App, ohne Elektra (kuechen-display#70).

Festlegung 15.11.2026: Der Ton geht an die OpenAI-Transkription (`gpt-transcribe`), weil man in
Spotify meist nach Namen sucht. Der Küchen-Dienst nimmt Kanal 0 des XVF3800 auf, solange die
Rückweg-Leiste ein Diktat offen hat, und schickt ihn beim Stopp als WAV.
Ohne Fremdpakete (urllib), wie hass.py.
"""

from __future__ import annotations

import json
import secrets
import struct
import urllib.error
import urllib.request

ADRESSE = "https://api.openai.com/v1/audio/transcriptions"
MODELL = "gpt-transcribe"
# Deutsch und Englisch: deutsche Ansagen, englische Band- und Songnamen.
SPRACHEN = ("de", "en")
MAX_S = 10.0  # danach nimmt der Dienst nichts mehr auf, auch ohne Stopp
MIN_S = 0.3  # kürzer ist ein Fehltipp, dafür geht nichts an OpenAI


class Aufnahme:
    """Puffer für ein Diktat. Kennt weder Mikrofon noch Netz."""

    def __init__(self, rate: int) -> None:
        self.rate = rate
        self.aktiv = False
        self.ton = bytearray()

    def start(self) -> None:
        self.aktiv = True
        self.ton = bytearray()

    def rahmen(self, pcm: bytes) -> None:
        if not self.aktiv:
            return
        platz = int(MAX_S * self.rate) * 2 - len(self.ton)
        self.ton += pcm[: max(platz, 0)]
        if platz <= len(pcm):
            self.aktiv = False

    def stopp(self) -> bytes:
        self.aktiv = False
        ton, self.ton = bytes(self.ton), bytearray()
        return ton

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
    pcm: bytes, rate: int, schluessel: str, modell: str = MODELL, timeout: float = 15
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
        # Die Fehlermeldung von OpenAI enthält keinen Schlüssel, nur Code und Grund.
        text = fehler.read().decode(errors="replace")[:300]
        raise DiktatFehler(f"OpenAI {fehler.code}: {text}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as fehler:
        raise DiktatFehler(f"OpenAI nicht erreichbar: {fehler}") from None
