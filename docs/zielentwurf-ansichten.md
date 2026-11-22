# Ansichten des Zielentwurfs erzeugen

Der Zielentwurf fürs Gehäuse liegt unter `gehaeuse/zielentwurf/`. Die README dort sagt,
was festgelegt ist und welche Maße gelten. Diese Seite beschreibt nur, wie die Bilder entstehen.

## Voraussetzung

`uv` ist installiert. Blender wird nicht gebraucht.

## Schritte

1. Im Repo-Verzeichnis ausführen:

   ```bash
   uv run --with pyvista --with trimesh --with pillow python gehaeuse/zielentwurf/ansichten.py
   ```

2. Das Skript liest `docs/projekt/modell.js`, schreibt `gehaeuse/zielentwurf/entwurf_o.glb`
   und gibt die Maße jeder Baugruppe aus.
3. Die Bilder liegen danach in `gehaeuse/zielentwurf/ansichten/`: acht Rundumansichten
   (`rundum_*.png`), vier gerade Ansichten (`ortho_*.png`) und die Blätter
   `rundum_uebersicht.png` und `ortho_uebersicht.png`.

Der erste Lauf lädt pyvista und VTK herunter, etwa 100 MB. Danach dauert ein Lauf unter
einer Minute. Das GLB und die Bilder stehen in `.gitignore`.

## Wenn sich das Modell ändert

Erst `blender -b -P werkzeuge/modell_exportieren.py` laufen lassen, das schreibt
`docs/projekt/modell.js` neu. Danach den Befehl aus Schritt 1 wiederholen.
