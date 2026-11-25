# Probestück für die Kameraaufnahme

Ein kleines Druckteil, an dem sich Display und Kamera anhalten lassen, bevor das Gehäuse
konstruiert wird. Es zeigt die obere Mitte der Front: Rahmenlippe, Glasstufe, Linsenloch,
Anschlag für die Kamera und 20 mm Dach. Hintergrund und Messwerte stehen in
[#6](https://github.com/dragondiver/kuechen-display/issues/6).

## Erzeugen

```bash
uv run --with build123d --with pyvista --with pillow python gehaeuse/probe/kamera_probe.py
```

Das Skript rechnet die Luft an sechs Stellen aus, prüft auf Durchdringungen und schreibt nach
`gehaeuse/probe/ausgabe/`:

- `kamera_probe.stl` und `kamera_probe.step` zum Drucken
- vier Bilder: Schnitt durch die Mitte, Innenansicht mit und ohne Einbauten, Ansicht von vorn

Endet der Lauf mit „keine Fehler“, ist das Teil druckbar. Die Maße stehen oben im Skript,
getrennt nach gemessen, aus der Zeichnung und zum Ausprobieren.

## Drucken

1. `kamera_probe.stl` in Bambu Studio laden. Das Teil liegt schon richtig: Frontfläche auf dem Bett.
2. Schichthöhe 0,2 mm, keine Stützen. Das Dach steht 15° schräg und druckt ohne.
3. Material egal, 60 × 29 × 20 mm, etwa 7 cm³.

## Prüfen

1. Display mit der Bildseite gegen die dünne Lippe halten, Glasoberkante an die Stufe schieben.
   Liegt das Glas flach in der Tasche?
2. Kamera quer einsetzen, Stecker zur Seite. Die Linse geht durchs Loch, das silberne
   Kameragehäuse liegt auf der Rückseite der Frontplatte auf. Die drei niedrigen Wände führen
   es nur seitlich, die Platine schwebt 3 mm darüber.
   Zwei Stützen stehen unter den oberen Löchern der Platine. Je einen Gummiring oder ein Stück
   Moosgummi (0,5 mm) auflegen und mit M2 × 6 handfest anschrauben, die Schraube schneidet sich
   ihr Gewinde selbst. Die unteren Löcher bleiben frei, sie liegen über dem Display.
3. Ansehen und aufschreiben:
   - Treffen die beiden Schrauben die Löcher der Platine?
   - Berührt das Kameragehäuse das Glas?
   - Stößt die Platine oben ans Dach?
   - Sitzt die Linse hinter der Frontfläche, und wie weit? Gerechnet sind 0,3 mm.
   - Steht die Kamera gerade im Loch, obwohl sie schräg auf der Platine sitzt?
   - Kommt das Flachbandkabel seitlich heraus, ohne zu knicken?
4. Kamera anschließen und ein Bild aufnehmen: Schattet der Lochrand die Bildecken ab?

Was nicht passt, als Maß in #6 schreiben. Die Werte unter „was das Probestück ausprobiert“
im Skript ändern und neu drucken.
