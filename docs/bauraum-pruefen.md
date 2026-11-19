# Bauraum prüfen

`gehaeuse/cad/bauraum.py` baut das Gehäuse und alle Einbauten als einfache Hüllkörper auf und meldet,
wo sich zwei Teile durchdringen oder ein Teil durch die Wand ragt. Es ist noch keine Konstruktion zum
Drucken, es beantwortet nur die Frage, ob alles hineinpasst.

## Aufruf

Aus dem Repo, `uv` muss installiert sein:

```bash
uv run --with build123d python gehaeuse/cad/bauraum.py
```

Mit einer anderen Gehäusetiefe in Millimetern:

```bash
uv run --with build123d python gehaeuse/cad/bauraum.py 120
```

Der erste Lauf lädt build123d herunter und dauert etwa eine Minute. Das Skript endet mit Code 1,
wenn es eine Kollision findet.

## Maße ändern

Jedes Maß steht in `teile()` und trägt im Kommentar seine Herkunft: Z für Zeichnung oder Datenblatt,
M für gemessen, F für vom Foto geschätzt, A für Annahme. Wer am Gerät nachmisst, ersetzt den Wert und
macht aus F oder A ein M.

## Was es nicht prüft

Kabel und Stecker, die Luftführung, Schrauben und Wandstärken einzelner Teile. Display, Kamera,
Mikrofonleiste und Bedienspalte sitzen in Taschen der Front oder des Deckels und werden deshalb nicht
gegen die Wand geprüft.
