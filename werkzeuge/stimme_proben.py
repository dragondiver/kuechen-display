# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=2"]
# ///
"""Sprachproben mit Elektras Stimme Marin für die Projektseite (docs/projekt/) erzeugen.

Elektra spricht auf dem Gerät mit der Stimme `marin` (rundfunk, `RUNDFUNK_STIMME`).
Die Projektseite spielt diese Proben ab, wenn jemand dort eine Erinnerung auslöst
oder Elektra fragt; fehlt eine Datei, nimmt die Seite die Sprachausgabe des Browsers.
Die Proben kommen aus der Sprachausgabe der API (`/v1/audio/speech`), nicht aus
GPT-Live wie auf dem Gerät; die Stimme ist dieselbe, der Klang kann leicht abweichen.

Die Sätze müssen zu `SAETZE` in docs/projekt/index.html passen. Wer dort einen Satz
ändert, ändert ihn hier mit und erzeugt die Probe neu.

Aufruf (im Repo-Wurzelverzeichnis):
    uv run werkzeuge/stimme_proben.py --probe
    uv run --env-file ../rundfunk/.env werkzeuge/stimme_proben.py
    uv run --env-file ../rundfunk/.env werkzeuge/stimme_proben.py --nur antwort-de

Ergebnis: docs/projekt/ton/<name>.mp3
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
ZIEL = WURZEL / "docs" / "projekt" / "ton"
MODELL = "gpt-4o-mini-tts"
STIMME = "marin"
ANWEISUNG = {
    "de": "Sprich Deutsch, ruhig, freundlich und natürlich, wie eine Assistentin, die in der Küche kurz Bescheid gibt. Kein Werbeton.",
    "en": "Speak English, calm, friendly and natural, like an assistant giving a short heads-up in the kitchen. No advertising tone.",
}
SAETZE = {
    "erinnerung-de": ("de", "In 20 Minuten Chorprobe."),
    "erinnerung-en": ("en", "Choir practice in 20 minutes."),
    "antwort-de": ("de", "Heute Abend noch die Chorprobe und danach der Krimi."),
    "antwort-en": ("en", "Choir practice this evening, then the crime drama."),
}


def erzeuge(name: str, modell: str, stimme: str) -> Path:
    from openai import OpenAI

    sprache, satz = SAETZE[name]
    antwort = OpenAI().audio.speech.create(
        model=modell,
        voice=stimme,
        input=satz,
        instructions=ANWEISUNG[sprache],
        response_format="mp3",
    )
    ziel = ZIEL / f"{name}.mp3"
    ziel.write_bytes(antwort.content)
    return ziel


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Sprachproben mit Elektras Stimme Marin erzeugen."
    )
    p.add_argument(
        "--probe",
        action="store_true",
        help="nur zeigen, was erzeugt würde; kostet nichts",
    )
    p.add_argument(
        "--nur",
        choices=sorted(SAETZE),
        action="append",
        help="nur diese Probe(n) erzeugen",
    )
    p.add_argument("--modell", default=MODELL)
    p.add_argument("--stimme", default=STIMME)
    a = p.parse_args(argv)
    namen = a.nur or list(SAETZE)

    for n in namen:
        sprache, satz = SAETZE[n]
        print(f"{n:15} [{sprache}] {satz}")
    print(f"Modell {a.modell}, Stimme {a.stimme}, Ziel {ZIEL.relative_to(WURZEL)}/")
    if a.probe:
        print("Probelauf: nichts erzeugt.")
        return 0

    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY fehlt. Aufruf mit dem Schlüssel aus 1Password:\n"
            "  uv run --env-file ../rundfunk/.env werkzeuge/stimme_proben.py",
            file=sys.stderr,
        )
        return 2

    ZIEL.mkdir(parents=True, exist_ok=True)
    fehler = 0
    for n in namen:
        try:
            ziel = erzeuge(n, a.modell, a.stimme)
        except Exception as e:  # noqa: BLE001 — jeder Fehlschlag wird gemeldet, keiner verschluckt
            fehler += 1
            print(f"FEHLER {n}: {e}", file=sys.stderr)
            continue
        print(f"ok     {ziel.relative_to(WURZEL)}  {ziel.stat().st_size // 1024} KB")
    if fehler:
        print(f"{fehler} von {len(namen)} Proben fehlgeschlagen.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
