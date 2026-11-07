# Projektseite

Die Seite liegt in `docs/projekt/` und erscheint nach dem Merge unter
<https://dragondiver.github.io/kuechen-display/projekt/>:

- `index.html`: Projektseite, `messungen.html`: Messprotokoll des Tischtests
- `stil.css`: gemeinsame Gestaltung beider Seiten
- `sprache.js`: Umschalter Deutsch/Englisch. Jeder Text steht doppelt im HTML
  (`<span lang="de">…</span><span lang="en">…</span>`), Texte aus dem Skript als `{ de: …, en: … }`.
  Wer einen Text ändert, ändert beide Sprachen.
- `modell.js`: das 3D-Modell, `bilder/`: Renders, Wetterbilder, Tischfotos

## Lokal ansehen

```bash
python3 -m http.server 8765 --directory docs/projekt
```

Dann <http://localhost:8765> öffnen. Direkt als Datei geöffnet lädt das 3D-Modell nicht.

## 3D-Modell neu exportieren

Nach Änderungen an `gehaeuse/blender/entwurf_o.py`:

```bash
blender -b -P werkzeuge/modell_exportieren.py
```

Das Skript überschreibt `docs/projekt/modell.js` (das GLB als Base64, weil Artefakte kein `.glb` ausliefern). Die Baugruppen im Modell tragen feste Namen
(`front`, `pi`, `holz_l` usw.), die `index.html` für die Explosionsansicht verwendet.

## Bevor neue Bilder hineinkommen

Das Repo ist öffentlich, und iPhone-Fotos enthalten GPS-Koordinaten. Fotos nie direkt kopieren, sondern
ohne Metadaten neu speichern. Prüfen:

```bash
python3 -c "import glob; from PIL import Image; [print(f, len(dict(Image.open(f).getexif()))) for f in glob.glob('docs/**/*.jp*g', recursive=True)]"
```

Jede Zeile muss mit `0` enden. Dasselbe gilt für Namen, Adressen, den Wohnort und Bestellnummern.
