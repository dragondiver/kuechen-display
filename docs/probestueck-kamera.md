# Probestück für die Kameraaufnahme

Ein kleines Druckteil, an dem sich Display und Kamera anhalten lassen, bevor das Gehäuse
konstruiert wird. Es zeigt die obere Mitte der Front: Rahmenlippe, Glasstufe, Linsenloch,
Anschlag für die Kamera und 20 mm Dach. Stand 27.11.2026: Kamera normal eingebaut (Breitbild,
Stecker unten), Schräge 150 statt 148 mm. Fünfte Fassung vom 28.11.2026: Loch 8,9 mm mit
Freistich dahinter, Linsenmitte 134,0 mm, Stützen als Kegel mit Kernloch 1,9 mm. Hintergrund und Messwerte stehen in
[#6](https://github.com/dragondiver/kuechen-display/issues/6).

## Erzeugen

```bash
uv run --with build123d --with pyvista --with pillow python gehaeuse/probe/kamera_probe.py
```

Das Skript rechnet die Luft an neun Stellen aus, prüft auf Durchdringungen und schreibt nach
`gehaeuse/probe/ausgabe/`:

- `kamera_probe.stl` und `kamera_probe.step` zum Drucken
- vier Bilder: Schnitt durch die Mitte, Innenansicht mit und ohne Einbauten, Ansicht von vorn

Endet der Lauf mit „keine Fehler“, ist das Teil druckbar. Die Maße stehen oben im Skript,
getrennt nach gemessen, aus der Zeichnung und zum Ausprobieren.

## Drucken

1. `kamera_probe.stl` in Bambu Studio laden. Das Teil liegt schon richtig: Frontfläche auf dem Bett.
2. Schichthöhe 0,2 mm, keine Stützen. Das Dach steht 15° schräg und druckt ohne.
3. Material egal, 60 × 31 × 20 mm, etwa 8 cm³.

## Prüfen

1. Display mit der Bildseite gegen die dünne Lippe halten, Glasoberkante an die Stufe schieben.
   Liegt das Glas flach in der Tasche?
2. Kamera normal einsetzen, Stecker nach unten zum Display. Die Linse geht durchs Loch, das
   silberne Kameragehäuse liegt auf der Rückseite der Frontplatte auf. Die drei niedrigen Wände
   führen es nur seitlich, die Platine schwebt 3 mm darüber.
   Vier Stützen stehen unter den vier Löchern der Platine, die Platine liegt direkt auf. Mit
   M2 × 6 handfest anschrauben, die Schraube schneidet sich ihr Gewinde selbst. Zwei Schrauben
   diagonal halten schon (Probe vom 28.11.2026), ein Polster kommt nicht dazwischen.
3. Ansehen und aufschreiben:
   - Treffen alle vier Schrauben die Löcher der Platine?
   - Stoßen die beiden unteren Stützen an Bauteile neben dem Kameragehäuse?
   - Berührt das Kameragehäuse das Glas?
   - Stößt die Platine oben ans Dach? Gerechnet sind 0,65 mm Luft.
   - Sitzt die Linse hinter der Frontfläche, und wie weit? Gerechnet sind 0,3 mm.
   - Federt die Kamera noch, wenn alle vier Schrauben sitzen?
   - Kommt das Flachbandkabel nach unten hinter dem Display heraus, ohne zu knicken?
4. Kamera anschließen und ein Bild aufnehmen: Schattet der Lochrand die Bildecken ab? Wird das
   Bild scharf? In der vierten Fassung hielt das Loch die Linse fest, der Autofokus kam nicht an.

Was nicht passt, als Maß in #6 schreiben. Die Werte unter „was das Probestück ausprobiert“
im Skript ändern und neu drucken.
