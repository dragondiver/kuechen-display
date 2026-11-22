"""Rundumansichten des Zielentwurfs als PNG, ohne Fenster.

Liest das Modell der Projektseite (docs/projekt/modell.js), legt es als
entwurf_o.glb neben dieses Skript und rendert die Ansichten nach ansichten/.

Aufruf aus dem Repo:
    uv run --with pyvista --with trimesh --with pillow python gehaeuse/zielentwurf/ansichten.py
"""

import base64
import math
import os

import numpy as np
import pyvista as pv
import trimesh
from PIL import Image

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(os.path.dirname(HIER))
GLB = os.path.join(HIER, "entwurf_o.glb")
ZIEL = os.path.join(HIER, "ansichten")

FARBEN = {
    "holz": (0.80, 0.62, 0.38),
    "front": (0.94, 0.94, 0.91),
    "schale": (0.94, 0.94, 0.91),
    "screen": (0.10, 0.11, 0.13),
    "display": (0.05, 0.05, 0.06),
    "mikro": (0.45, 0.46, 0.48),
}
INNEN = ("kern", "pi", "ups", "akku", "ls_")


def glb_schreiben():
    with open(os.path.join(WURZEL, "docs", "projekt", "modell.js")) as ein:
        roh = ein.read()
    daten = base64.b64decode(roh.split('"')[1])
    with open(GLB, "wb") as aus:
        aus.write(daten)


def laden():
    """Liefert {name: PolyData} in Millimetern, z nach oben, Front nach -y."""
    szene = trimesh.load(GLB)
    teile = {}
    for knoten in szene.graph.nodes_geometry:
        lage, geo = szene.graph[knoten]
        m = szene.geometry[geo].copy()
        m.apply_transform(lage)
        v = np.asarray(m.vertices) * 1000.0
        v = np.column_stack([v[:, 0], -v[:, 2], v[:, 1]])  # glTF: y oben
        f = np.hstack([np.full((len(m.faces), 1), 3), m.faces]).ravel()
        teile[knoten] = pv.PolyData(v, f)
    return teile


def uebersicht(dateien, ziel, spalten):
    b, h = 700, 500
    zeilen = -(-len(dateien) // spalten)
    blatt = Image.new("RGB", (spalten * b, zeilen * h))
    for i, d in enumerate(dateien):
        blatt.paste(
            Image.open(os.path.join(ZIEL, d)).resize((b, h)),
            ((i % spalten) * b, (i // spalten) * h),
        )
    blatt.save(os.path.join(ZIEL, ziel))


def farbe(name):
    for anfang, wert in FARBEN.items():
        if name.startswith(anfang):
            return wert
    return (0.35, 0.36, 0.38)


def bild(teile, datei, azimut, hoehe, gerade=False):
    aussen = {n: m for n, m in teile.items() if not n.startswith(INNEN)}
    alle = pv.merge(list(aussen.values()))
    mitte, groesse = np.array(alle.center), alle.length
    pl = pv.Plotter(off_screen=True, window_size=(1400, 1000))
    pl.set_background("#dfe6e6")
    for name, m in aussen.items():
        pl.add_mesh(
            m.compute_normals(feature_angle=40, split_vertices=True),
            color=farbe(name),
            smooth_shading=True,
            ambient=0.35,
            diffuse=0.75,
            specular=0.1,
        )
    a, h = math.radians(azimut), math.radians(hoehe)
    richtung = np.array(
        [math.sin(a) * math.cos(h), -math.cos(a) * math.cos(h), math.sin(h)]
    )
    pl.camera.position = tuple(mitte + richtung * groesse * 3.2)
    pl.camera.focal_point = tuple(mitte)
    pl.camera.up = (0, 1, 0) if hoehe > 85 else (0, 0, 1)
    # Parallelprojektion: senkrechte Kanten bleiben im Bild senkrecht.
    pl.enable_parallel_projection()
    pl.reset_camera()
    pl.camera.zoom(1.2 if gerade else 1.0)
    pl.screenshot(os.path.join(ZIEL, datei))
    pl.close()


if __name__ == "__main__":
    os.makedirs(ZIEL, exist_ok=True)
    glb_schreiben()
    teile = laden()
    aussen = pv.merge([m for n, m in teile.items() if not n.startswith(INNEN)])
    b = aussen.bounds
    print("Baugruppen:", ", ".join(sorted(teile)))
    print(
        f"Außenmaße: {b[1] - b[0]:.1f} x {b[3] - b[2]:.1f} x {b[5] - b[4]:.1f} mm (B x T x H, mit Füßen und Knöpfen)"
    )
    for name in sorted(teile):
        q = teile[name].bounds
        print(
            f"  {name:12s} {q[1] - q[0]:6.1f} x {q[3] - q[2]:6.1f} x {q[5] - q[4]:6.1f}"
        )
    rundum = []
    for i, az in enumerate(range(0, 360, 45)):
        rundum.append(f"rundum_{i + 1}_{az:03d}.png")
        bild(teile, rundum[-1], az, 18)
    bild(teile, "ortho_vorn.png", 0, 0, gerade=True)
    bild(teile, "ortho_seite_rechts.png", 90, 0, gerade=True)
    bild(teile, "ortho_hinten.png", 180, 0, gerade=True)
    bild(teile, "ortho_oben.png", 0, 90, gerade=True)
    uebersicht(rundum, "rundum_uebersicht.png", 4)
    uebersicht(
        [
            "ortho_vorn.png",
            "ortho_seite_rechts.png",
            "ortho_hinten.png",
            "ortho_oben.png",
        ],
        "ortho_uebersicht.png",
        4,
    )
    print("fertig:", ZIEL)
