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

## Konstruktion A

`gehaeuse/cad/gehaeuse.py` ist der nächste Schritt: die Druckteile als echte Körper mit Wandstärke,
Laschen, Domen und Schrauben. Das Skript prüft, dass kein Teil ein anderes durchdringt, dass jede
Schraube durch ein Teil geht und ihr Gewindeeinsatz ganz in einem zweiten sitzt, und dass jedes Teil
aufs Druckbett passt.

```bash
uv run --with build123d python gehaeuse/cad/gehaeuse.py
```

Mit `--export` schreibt es `gehaeuse/cad/ausgabe/gehaeuse.glb` und `teile.json` (nicht im Git). Die
Explosionszeichnung lädt diese Datei.

```bash
uv run --with build123d python gehaeuse/cad/gehaeuse.py --export
```

Noch nicht enthalten: Druckdateien (STL/3MF), Kabelwege, Luftführung, das Volumen der Lautsprecherschalen.
