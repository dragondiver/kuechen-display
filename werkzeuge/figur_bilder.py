# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=2", "pillow>=10"]
# ///
"""Elektras Figur in vier Zuständen aus einer Vorlage erzeugen (kuechen-display#15).

Die Figur sitzt unten rechts auf dem Ruhebildschirm, solange Elektra zuhört.
Die Oberfläche wechselt zwischen Einzelbildern: zuhören, sprechen (Mund halb und
ganz offen, im Wechsel = Lippenbewegung) und nachdenken. Schallbögen und das
Mikrofon-Leuchten zeichnet die Oberfläche selbst darüber, deshalb stehen sie
nicht in den Bildern.

Ablauf: Aus der Vorlage entsteht zuerst das Grundbild „zuhoeren“. Die übrigen
Zustände werden aus diesem Grundbild abgeleitet, nicht aus der Vorlage, damit die
Figur in allen Bildern gleich aussieht.

Aufruf (im Repo-Wurzelverzeichnis):
    uv run werkzeuge/figur_bilder.py --probe          # nur zeigen, was passieren würde
    OPENAI_API_KEY=… uv run werkzeuge/figur_bilder.py  # wirklich erzeugen (kostet Geld)

Ergebnis: docs/entwuerfe/figur/<zustand>.png (1024 px, transparent) und
<zustand>-klein.png (256 px, für das Display; die Figur ist dort etwa 3 cm groß).
"""

from __future__ import annotations

import argparse
import base64
import io
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ORDNER = Path("docs/entwuerfe/figur")
VORLAGE = ORDNER / "vorlage-pferdeschwanz.png"
# Linke Figur („Agent hört zu“) aus Florians Vorlage vom 19.10.2026, 1254 × 1254 px.
AUSSCHNITT = (30, 250, 610, 830)
MODELL = "gpt-image-2.5-sunburst"  # Standard der Bild-API im Oktober 2026
KLEIN_PX = 256

GRUNDREGELN = (
    "Draw exactly one character: the young woman with the brown ponytail from the "
    "reference image. Keep her face, hair, ponytail, orange t-shirt, white earpiece "
    "with orange ring, soft 3D illustration style, colors and proportions exactly as "
    "in the reference. Head-and-shoulders portrait, centered, facing slightly to the "
    "right as in the reference. Fully transparent background: no circle, no sound "
    "waves, no microphone button, no text, no shadow on the ground."
)


@dataclass(frozen=True)
class Zustand:
    name: str
    aenderung: str
    aus_grundbild: bool  # False nur für das Grundbild selbst


ZUSTAENDE = [
    Zustand(
        "zuhoeren",
        "Mouth closed with a gentle, friendly smile. Eyes look forward.",
        False,
    ),
    Zustand(
        "sprechen-halb",
        "Identical image, change only the mouth: slightly open, mid-word.",
        True,
    ),
    Zustand(
        "sprechen-offen",
        "Identical image, change only the mouth: open in a friendly smile while talking, "
        "as in the right character of the reference.",
        True,
    ),
    Zustand(
        "nachdenken",
        "Identical image, change only the eyes and mouth: eyes look up to the side as if "
        "thinking, mouth closed and neutral.",
        True,
    ),
]


def prompt_fuer(zustand: Zustand) -> str:
    return f"{GRUNDREGELN} {zustand.aenderung}"


def vorlage_zuschneiden(
    pfad: Path, ausschnitt: tuple[int, int, int, int] | None
) -> bytes:
    from PIL import Image

    bild = Image.open(pfad).convert("RGBA")
    if ausschnitt:
        bild = bild.crop(ausschnitt)
    puffer = io.BytesIO()
    bild.save(puffer, format="PNG")
    return puffer.getvalue()


def erzeuge(client, modell: str, qualitaet: str, eingabe: bytes, prompt: str) -> bytes:
    antwort = client.images.edit(
        model=modell,
        image=("eingabe.png", eingabe, "image/png"),
        prompt=prompt,
        background="transparent",
        output_format="png",
        size="1024x1024",
        quality=qualitaet,
    )
    return base64.b64decode(antwort.data[0].b64_json)


def speichern(png: bytes, name: str) -> None:
    from PIL import Image

    ORDNER.mkdir(parents=True, exist_ok=True)
    (ORDNER / f"{name}.png").write_bytes(png)
    klein = Image.open(io.BytesIO(png)).resize((KLEIN_PX, KLEIN_PX), Image.LANCZOS)
    klein.save(ORDNER / f"{name}-klein.png")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--probe", action="store_true", help="nichts erzeugen, nur Ablauf zeigen"
    )
    p.add_argument("--vorlage", type=Path, default=VORLAGE)
    p.add_argument(
        "--ohne-ausschnitt", action="store_true", help="Vorlage nicht zuschneiden"
    )
    p.add_argument("--modell", default=MODELL)
    p.add_argument("--qualitaet", default="medium", choices=["low", "medium", "high"])
    p.add_argument(
        "--nur",
        nargs="*",
        default=None,
        help="nur diese Zustände (Grundbild muss existieren)",
    )
    args = p.parse_args(argv)

    ausschnitt = None if args.ohne_ausschnitt else AUSSCHNITT
    auswahl = [z for z in ZUSTAENDE if args.nur is None or z.name in args.nur]
    unbekannt = set(args.nur or []) - {z.name for z in ZUSTAENDE}
    if unbekannt:
        print(f"Unbekannte Zustände: {', '.join(sorted(unbekannt))}", file=sys.stderr)
        return 2
    if not args.vorlage.exists():
        print(f"Vorlage fehlt: {args.vorlage}", file=sys.stderr)
        return 2

    if args.probe:
        print(f"Modell {args.modell}, Qualität {args.qualitaet}, {len(auswahl)} Bilder")
        print(f"Vorlage {args.vorlage}, Ausschnitt {ausschnitt}")
        for z in auswahl:
            quelle = "Grundbild zuhoeren.png" if z.aus_grundbild else "Vorlage"
            print(f"- {z.name}: aus {quelle} -> {ORDNER / z.name}.png")
            print(f"  {prompt_fuer(z)}")
        return 0

    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY fehlt. Zum Beispiel aus 1Password: "
            "op run --env-file <datei> -- uv run werkzeuge/figur_bilder.py",
            file=sys.stderr,
        )
        return 2

    from openai import OpenAI

    client = OpenAI()
    grund_pfad = ORDNER / "zuhoeren.png"
    for z in auswahl:
        if z.aus_grundbild:
            if not grund_pfad.exists():
                print(
                    "Grundbild zuhoeren.png fehlt, zuerst ohne --nur laufen lassen.",
                    file=sys.stderr,
                )
                return 2
            eingabe = grund_pfad.read_bytes()
        else:
            eingabe = vorlage_zuschneiden(args.vorlage, ausschnitt)
        print(f"erzeuge {z.name} …", flush=True)
        speichern(
            erzeuge(client, args.modell, args.qualitaet, eingabe, prompt_fuer(z)),
            z.name,
        )
    print(f"fertig: {ORDNER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
