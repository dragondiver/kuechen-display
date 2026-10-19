# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=2", "pillow>=10"]
# ///
"""Hintergrundbilder des Ruhebildschirms für sechs Wetterlagen erzeugen (kuechen-display#15).

Stil W3 (illustrierte Landschaft) mit dem Stuttgarter Fernsehturm. Der Turm steht
im Startbild (Heute) genau in der Lücke zwischen linker und rechter Glaskarte:
bei x = 730 von 1280 px, also 57 % der Bildbreite. Auf den anderen Seiten
(Apps, Morgen/Woche) darf er verdeckt sein.

Ablauf wie bei figur_bilder.py: Erst entsteht das Grundbild „gedaempft“ aus Text,
die übrigen Lagen werden aus diesem Grundbild abgeleitet, damit Landschaft und
Turm in allen Bildern an derselben Stelle bleiben. Die Bild-API liefert 1536 × 1024;
das Skript skaliert auf 1280 px Breite und schneidet mittig auf 800 px Höhe zu.

Aufruf (im Repo-Wurzelverzeichnis):
    uv run werkzeuge/wetter_bilder.py --probe
    uv run --env-file ../rundfunk/.env werkzeuge/wetter_bilder.py
    uv run werkzeuge/wetter_bilder.py --pruefen   # Prüfbilder mit den Kartenflächen
    uv run werkzeuge/wetter_bilder.py --neu-zuschneiden [--turm-x N]   # ohne API

Ergebnis: docs/entwuerfe/wetter/<lage>.png (1280 × 800); die unbeschnittenen
Originale liegen in wetter/roh/ (nicht im Git). Mit --pruefen zusätzlich
docs/entwuerfe/wetter/pruefung/<lage>.png mit eingezeichneten Glaskarten, um zu
sehen, ob der Turm in der Lücke steht.
"""

from __future__ import annotations

import argparse
import base64
import io
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ORDNER = Path("docs/entwuerfe/wetter")
MODELL = "gpt-image-2.5-sunburst"
BREITE, HOEHE = 1280, 800
# Glaskarten im Startbild (Entwurf C, 1280 × 800): links 48–688, rechts 772–1232.
KARTE_LINKS = (48, 48, 688, 752)
KARTE_RECHTS = (772, 48, 1232, 430)
TURM_X = 730  # Mitte der Lücke

GRUNDREGELN = (
    "Wallpaper for a calm kitchen display, wide landscape format. Softly illustrated "
    "landscape in a gentle 3D illustration style with muted, harmonious colors: rolling "
    "hills of the Stuttgart region, a few small houses and round trees in the middle "
    "distance, darker hills in the foreground. On a distant hill stands the Stuttgart TV "
    "tower (Fernsehturm Stuttgart): a slender concrete shaft, a cylindrical multi-level "
    "basket near the top and a thin red-and-white antenna mast above it. The tower is "
    "small but clearly recognizable and stands at exactly 57 percent of the image width "
    "from the left edge, nowhere else. Keep the left half and the upper right area calm "
    "and free of small details, because text cards will cover them. No people, no text, "
    "no logos, no frame, no UI."
)


@dataclass(frozen=True)
class Lage:
    name: str
    beschreibung: str
    aus_grundbild: bool


LAGEN = [
    Lage(
        "gedaempft",
        "Muted, hazy daylight, soft grey-blue sky, gentle diffuse light.",
        False,
    ),
    Lage(
        "sonnig",
        "Same landscape and tower in the same place. Change only sky and light: clear "
        "sunny day, soft blue sky, warm sunlight, gentle shadows.",
        True,
    ),
    Lage(
        "wolkig",
        "Same landscape and tower in the same place. Change only sky and light: many soft "
        "white and grey clouds with patches of blue sky.",
        True,
    ),
    Lage(
        "nacht",
        "Same landscape and tower in the same place. Change only sky and light: calm "
        "night, deep blue sky with a few stars, a few warmly lit windows, small red "
        "aviation lights on the tower.",
        True,
    ),
    Lage(
        "schnee",
        "Same landscape and tower in the same place. Snow on hills, roofs and trees, "
        "light snowfall, bright white-grey winter sky.",
        True,
    ),
    Lage(
        "regen",
        "Same landscape and tower in the same place. Rainy day: dark grey clouds, fine "
        "rain streaks, wet muted colors.",
        True,
    ),
]


def prompt_fuer(lage: Lage) -> str:
    return f"{GRUNDREGELN} {lage.beschreibung}"


def fenster(roh_breite: int, roh_hoehe: int, turm_x: int) -> tuple[int, int, int, int]:
    """Ausschnitt (links, oben, breite, hoehe) im Rohbild, in dem der Turm bei
    TURM_X/BREITE der Breite steht – so groß wie möglich, Seitenverhältnis 16:10,
    senkrecht mittig. Das Modell hält die Turmposition aus dem Prompt nicht ein
    (erster Lauf 19.10.2026: 70 % statt 57 %), deshalb wird hier verschoben."""
    anteil = TURM_X / BREITE
    breite = min(
        roh_breite,
        turm_x / anteil,
        (roh_breite - turm_x) / (1 - anteil),
        roh_hoehe * BREITE / HOEHE,
    )
    breite = int(breite)
    if breite < roh_breite / 2:
        raise ValueError(
            f"Turm bei x = {turm_x} steht zu nah am Rand: der Ausschnitt wäre nur "
            f"{breite} px breit. Grundbild neu erzeugen (--nur gedaempft)."
        )
    hoehe = round(breite * HOEHE / BREITE)
    links = round(turm_x - anteil * breite)
    oben = (roh_hoehe - hoehe) // 2
    return links, oben, breite, hoehe


def turm_finden(png: bytes) -> int:
    """x des Turms im Rohbild: die Spalte, die sich im oberen Bilddrittel am
    stärksten dunkel vom Himmel daneben abhebt. Gemessen am Grundbild."""
    from PIL import Image

    bild = Image.open(io.BytesIO(png)).convert("L")
    w, h = bild.size
    zeilen = range(int(h * 0.25), int(h * 0.45))
    bester = (float("-inf"), w // 2)
    for x in range(w // 3, w - 20):
        abstand = sum(bild.getpixel((x - 6, y)) - bild.getpixel((x, y)) for y in zeilen)
        bester = max(bester, (abstand, x))
    return bester[1]


def zuschneiden(png: bytes, turm_x: int) -> bytes:
    """Ausschnitt nach fenster() auf 1280 × 800 bringen."""
    from PIL import Image

    bild = Image.open(io.BytesIO(png)).convert("RGB")
    links, oben, breite, hoehe = fenster(bild.width, bild.height, turm_x)
    bild = bild.crop((links, oben, links + breite, oben + hoehe))
    bild = bild.resize((BREITE, HOEHE), Image.LANCZOS)
    puffer = io.BytesIO()
    bild.save(puffer, format="PNG", optimize=True)
    return puffer.getvalue()


def pruefbild(pfad: Path, ziel: Path) -> None:
    """Glaskarten halbtransparent und die Sollposition des Turms einzeichnen."""
    from PIL import Image, ImageDraw

    bild = Image.open(pfad).convert("RGBA")
    ebene = Image.new("RGBA", bild.size, (0, 0, 0, 0))
    zeichnen = ImageDraw.Draw(ebene)
    for karte in (KARTE_LINKS, KARTE_RECHTS):
        zeichnen.rounded_rectangle(karte, radius=36, fill=(20, 24, 32, 120))
    zeichnen.line((TURM_X, 0, TURM_X, HOEHE), fill=(255, 80, 40, 200), width=2)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(bild, ebene).convert("RGB").save(ziel)


def erzeuge(
    client, modell: str, qualitaet: str, prompt: str, eingabe: bytes | None
) -> bytes:
    gemeinsam = {
        "model": modell,
        "prompt": prompt,
        "size": "1536x1024",
        "quality": qualitaet,
        "output_format": "png",
    }
    if eingabe is None:
        antwort = client.images.generate(**gemeinsam)
    else:
        antwort = client.images.edit(
            image=("grundbild.png", eingabe, "image/png"), **gemeinsam
        )
    return base64.b64decode(antwort.data[0].b64_json)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    p.add_argument(
        "--probe", action="store_true", help="nichts erzeugen, nur Ablauf zeigen"
    )
    p.add_argument(
        "--pruefen", action="store_true", help="nur Prüfbilder aus vorhandenen Bildern"
    )
    p.add_argument(
        "--neu-zuschneiden",
        action="store_true",
        help="ohne API: alle Lagen aus roh/ neu zuschneiden",
    )
    p.add_argument(
        "--turm-x",
        type=int,
        default=None,
        help="x des Turms im Rohbild (sonst gemessen)",
    )
    p.add_argument("--modell", default=MODELL)
    p.add_argument("--qualitaet", default="medium", choices=["low", "medium", "high"])
    p.add_argument("--nur", nargs="*", default=None, help="nur diese Lagen")
    args = p.parse_args(argv)

    namen = {lage.name for lage in LAGEN}
    unbekannt = set(args.nur or []) - namen
    if unbekannt:
        print(f"Unbekannte Lagen: {', '.join(sorted(unbekannt))}", file=sys.stderr)
        return 2
    auswahl = [lage for lage in LAGEN if args.nur is None or lage.name in args.nur]

    if args.probe:
        print(f"Modell {args.modell}, Qualität {args.qualitaet}, {len(auswahl)} Bilder")
        print(
            f"Format 1536 × 1024 -> {BREITE} × {HOEHE}, Turm soll bei x = {TURM_X} stehen"
        )
        for lage in auswahl:
            quelle = "Grundbild gedaempft.png" if lage.aus_grundbild else "nur Text"
            print(f"- {lage.name}: aus {quelle} -> {ORDNER / lage.name}.png")
            print(f"  {prompt_fuer(lage)}")
        return 0

    if args.pruefen:
        vorhanden = [lage for lage in auswahl if (ORDNER / f"{lage.name}.png").exists()]
        if not vorhanden:
            print(f"Keine Bilder in {ORDNER}.", file=sys.stderr)
            return 2
        for lage in vorhanden:
            pruefbild(
                ORDNER / f"{lage.name}.png", ORDNER / "pruefung" / f"{lage.name}.png"
            )
        print(f"Prüfbilder: {ORDNER / 'pruefung'}")
        return 0

    roh_ordner = ORDNER / "roh"
    if args.neu_zuschneiden:
        grund_roh = roh_ordner / "gedaempft.png"
        if not grund_roh.exists():
            print(f"Rohbild fehlt: {grund_roh}", file=sys.stderr)
            return 2
        turm_x = args.turm_x or turm_finden(grund_roh.read_bytes())
        print(f"Turm im Rohbild bei x = {turm_x}")
        for lage in auswahl:
            roh_datei = roh_ordner / f"{lage.name}.png"
            if not roh_datei.exists():
                print(f"- {lage.name}: kein Rohbild, übersprungen", file=sys.stderr)
                continue
            (ORDNER / f"{lage.name}.png").write_bytes(
                zuschneiden(roh_datei.read_bytes(), turm_x)
            )
            pruefbild(
                ORDNER / f"{lage.name}.png", ORDNER / "pruefung" / f"{lage.name}.png"
            )
            print(f"- {lage.name}: neu zugeschnitten")
        return 0

    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY fehlt, z. B.: "
            "uv run --env-file ../rundfunk/.env werkzeuge/wetter_bilder.py",
            file=sys.stderr,
        )
        return 2

    from openai import OpenAI

    client = OpenAI()
    ORDNER.mkdir(parents=True, exist_ok=True)
    # Die Lagen werden aus dem unbeschnittenen Grundbild abgeleitet (1536 × 1024),
    # sonst verschiebt das andere Seitenverhältnis die Landschaft samt Turm.
    roh_ordner.mkdir(parents=True, exist_ok=True)
    grund = roh_ordner / "gedaempft.png"
    turm_x = args.turm_x
    for lage in auswahl:
        eingabe = None
        if lage.aus_grundbild:
            if not grund.exists():
                print(
                    "Grundbild gedaempft.png fehlt, zuerst ohne --nur laufen lassen.",
                    file=sys.stderr,
                )
                return 2
            eingabe = grund.read_bytes()
        print(f"erzeuge {lage.name} …", flush=True)
        roh = erzeuge(client, args.modell, args.qualitaet, prompt_fuer(lage), eingabe)
        (roh_ordner / f"{lage.name}.png").write_bytes(roh)
        if turm_x is None:
            turm_x = turm_finden(grund.read_bytes() if grund.exists() else roh)
            print(f"  Turm im Rohbild bei x = {turm_x}")
        (ORDNER / f"{lage.name}.png").write_bytes(zuschneiden(roh, turm_x))
        pruefbild(ORDNER / f"{lage.name}.png", ORDNER / "pruefung" / f"{lage.name}.png")
    print(f"fertig: {ORDNER} (Prüfbilder in {ORDNER / 'pruefung'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
