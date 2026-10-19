"""Verbrauch und Kosten der Bild-API mitschreiben (für figur_bilder.py und wetter_bilder.py).

Preise laut OpenAI-Preisseite für gpt-image-2.5 (Stand Oktober 2026), in US-Dollar
pro Million Tokens. Ändern sich die Preise, hier anpassen.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PREIS_BILD_EIN = 8.00
PREIS_TEXT_EIN = 5.00
PREIS_BILD_AUS = 30.00

PROTOKOLL = Path("docs/bild-laeufe.md")
KOPF = (
    "# Läufe der Bild-API\n\n"
    "Wird von `werkzeuge/figur_bilder.py` und `werkzeuge/wetter_bilder.py` fortgeschrieben.\n"
    "Kosten aus den Tokens der API-Antwort und den Preisen in `werkzeuge/bildkosten.py`.\n\n"
    "| Zeit | Skript | Bild | Modell | Qualität | Bild ein | Text ein | Bild aus | Kosten |\n"
    "|---|---|---|---|---|---:|---:|---:|---:|\n"
)


def kosten(bild_ein: int, text_ein: int, bild_aus: int) -> float:
    return (
        bild_ein * PREIS_BILD_EIN
        + text_ein * PREIS_TEXT_EIN
        + bild_aus * PREIS_BILD_AUS
    ) / 1_000_000


def protokollieren(
    antwort, skript: str, bild: str, modell: str, qualitaet: str
) -> float | None:
    """Eine Zeile ins Protokoll schreiben und ausgeben. Ohne usage: Zeile mit „?“."""
    usage = getattr(antwort, "usage", None)
    if usage is None:
        zahlen, betrag, text = ("?", "?", "?"), None, "?"
    else:
        details = getattr(usage, "input_tokens_details", None)
        bild_ein = getattr(details, "image_tokens", 0) or 0
        text_ein = getattr(details, "text_tokens", 0) or 0
        bild_aus = getattr(usage, "output_tokens", 0) or 0
        betrag = kosten(bild_ein, text_ein, bild_aus)
        zahlen, text = (str(bild_ein), str(text_ein), str(bild_aus)), f"{betrag:.3f} $"
    if not PROTOKOLL.exists():
        PROTOKOLL.parent.mkdir(parents=True, exist_ok=True)
        PROTOKOLL.write_text(KOPF, encoding="utf-8")
    zeit = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M")
    zeile = f"| {zeit} | {skript} | {bild} | {modell} | {qualitaet} | {' | '.join(zahlen)} | {text} |\n"
    with PROTOKOLL.open("a", encoding="utf-8") as f:
        f.write(zeile)
    print(
        f"  Tokens Bild ein/Text ein/Bild aus: {'/'.join(zahlen)}, Kosten {text}",
        flush=True,
    )
    return betrag
