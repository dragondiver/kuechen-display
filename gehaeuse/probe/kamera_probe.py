"""Probestück: obere Mitte der Front mit Glasstufe, Kameraloch und einem Stück Dach.

Zum Anhalten von Display und Kamera, bevor das Gehäuse konstruiert wird (#6).
Achsen: x quer, y entlang der Schräge nach oben (wie in entwurf_o.py gemessen),
z von der Frontfläche nach innen. Die Frontfläche liegt beim Druck auf dem Bett.

Aufruf aus dem Repo:
    uv run --with build123d --with pyvista --with pillow python gehaeuse/probe/kamera_probe.py
"""

import math
import os

import numpy as np
import pyvista as pv
from build123d import (
    Box,
    Cone,
    Cylinder,
    Plane,
    Polygon,
    Pos,
    export_step,
    export_stl,
    extrude,
)

HIER = os.path.dirname(os.path.abspath(__file__))
ZIEL = os.path.join(HIER, "ausgabe")

# --- Entwurf O (gehaeuse/zielentwurf)
NEIGUNG = 75.0  # Grad
SCHRAEGE = 148.0  # Länge der Front
WAND = 3.0  # Dach und Front, angenommen
GLAS_OBEN = 128.5  # Glasoberkante auf der Schräge (S0 - 2 + 59,5)
FENSTER_OBEN = 124.1  # Oberkante des Bildfensters

# --- am Teil gemessen, 22.11.2026 (#4, #6)
GLAS_DICK = 1.55  # 1,5 bis 1,6 mit Folie
UEBERSTAND = 2.0  # Glas über dem LCD-Modul, oben
KAM_LINSE_UEBER_PLATINE = 8.2  # Platinenvorderseite bis Linsenfront
KAM_GEHAEUSE_HOCH = 5.5  # silbernes Kameragehäuse über der Platine
KAM_PLATINE = (23.8, 25.1)  # quer gedreht: 23,8 quer, 25,1 entlang der Schräge
KAM_LINSE_ZUR_STECKERKANTE = 9.3  # aus 25.11.: Kante gegenüber bis Gehäuse-Unterseite 19,9, also Linse 14,5 von dort
KAM_STECKER_HOCH = 2.45

KAM_GEHAEUSE = 10.8  # Kantenlänge des Kameragehäuses
KAM_TUBUS_R = 7.1 / 2  # Linsentubus

KAM_LOCH_PAAR = (
    21.0  # Mittenabstand der zwei Löcher einer Reihe: außen 23,13, Loch 1,98 bis 2,2
)
KAM_LOCH_REIHE = 12.5  # Mittenabstand der beiden Reihen: außen 14,5, Loch 1,98 bis 2,2

# --- aus den Zeichnungen, nicht gemessen
KAM_LOCH_RAND = 2.0  # erste Lochreihe: Abstand zur Platinenkante gegenüber dem Stecker
LCD_DICK = 4.8
KAM_PLATINE_DICK = 1.12

# --- was das Probestück ausprobiert
LIPPE = 1.0  # Rahmenlippe über dem Glas (Entwurf: 2,8)
STUETZE_LUFT = 0.5  # Stützen enden unter der Platine, dazwischen ein Gummiring
STUETZE_R = 2.2
SCHRAUBLOCH_R = 0.85  # Kernloch für M2 direkt im Kunststoff
FUEHRUNG = 2.5  # Höhe der drei Wände; sie führen nur das silberne Gehäuse und bleiben unter der Platine
KAM_S = 133.5  # Linsenmitte auf der Schräge (Entwurf 137, entschieden 132,5, hier 1 mm höher)
SPIEL = 0.5  # rundum
BREITE = 60.0
DACH_TIEF = 20.0

T = math.radians(NEIGUNG)
H = SCHRAEGE * math.sin(T)


def dach_s(z, innen):
    """Lage der Dachfläche auf der Schräge in der Tiefe z."""
    return (H - (WAND if innen else 0) + z * math.cos(T)) / math.sin(T)


def quader(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(
        x1 - x0, y1 - y0, z1 - z0
    )


def baue():
    # Das silberne Kameragehäuse liegt auf der Rückseite der Frontplatte auf. Die Platine ist
    # kein Anschlag: Die Kamera sitzt schräg darauf, und neben ihr stehen Bauteile (Foto 22.11.).
    z_gehaeuse = WAND
    z_platine = z_gehaeuse + KAM_GEHAEUSE_HOCH  # Platinenvorderseite
    linse = z_platine - KAM_LINSE_UEBER_PLATINE  # Linsenfront hinter der Frontfläche
    z_glas = LIPPE + GLAS_DICK  # Glasrückseite
    tasche = GLAS_OBEN + SPIEL

    profil = [
        (FENSTER_OBEN, 0),
        (SCHRAEGE, 0),
        (dach_s(DACH_TIEF, False), DACH_TIEF),
        (dach_s(DACH_TIEF, True), DACH_TIEF),
        (dach_s(WAND, True), WAND),
        (FENSTER_OBEN, WAND),
    ]
    teil = Pos(-BREITE / 2, 0, 0) * extrude(
        Plane.YZ * Polygon(*profil, align=None), BREITE
    )
    # Tasche fürs Glas: bleibt nur die Lippe stehen
    teil -= quader(-BREITE, BREITE, FENSTER_OBEN - 1, tasche, LIPPE, WAND + 1)
    # Loch für den Linsentubus, vorn leicht angefast
    r = KAM_TUBUS_R + SPIEL
    teil -= Pos(0, KAM_S, WAND / 2) * Cylinder(r, WAND + 2)
    teil -= Pos(0, KAM_S, 0.25) * Cone(r + 0.5, r, 0.5)
    # Führung für die Kamera: drei niedrige Wände ums Kameragehäuse, unten offen zum Display.
    i = KAM_GEHAEUSE / 2 + SPIEL
    a = i + 1.6
    unten = tasche + 0.5
    teil += quader(-a, -i, unten, KAM_S + a, WAND, WAND + FUEHRUNG)
    teil += quader(i, a, unten, KAM_S + a, WAND, WAND + FUEHRUNG)
    teil += quader(-a, a, KAM_S + i, KAM_S + a, WAND, WAND + FUEHRUNG)
    # Zwei Stützen an den oberen Löchern der Platine. Die unteren Löcher liegen über dem Display.
    kante = -(
        KAM_PLATINE[0] - KAM_LINSE_ZUR_STECKERKANTE
    )  # Platinenkante gegenüber dem Stecker
    loch_y = KAM_S + KAM_LOCH_PAAR / 2
    loecher = [
        (kante + KAM_LOCH_RAND, loch_y),
        (kante + KAM_LOCH_RAND + KAM_LOCH_REIHE, loch_y),
    ]
    z_stuetze = z_platine - STUETZE_LUFT
    for lx, ly in loecher:
        teil += Pos(lx, ly, (WAND + z_stuetze) / 2) * Cylinder(
            STUETZE_R, z_stuetze - WAND
        )
    # Steg zwischen der Stütze in der Mitte und der oberen Führungswand, sonst bleibt ein Spalt
    teil += quader(
        loecher[1][0] - STUETZE_R,
        loecher[1][0] + STUETZE_R,
        KAM_S + a - 0.1,
        loch_y,
        WAND,
        WAND + FUEHRUNG,
    )
    for lx, ly in loecher:
        teil -= Pos(lx, ly, z_stuetze - 2.5 + 0.5) * Cylinder(SCHRAUBLOCH_R, 5 + 1)

    g = KAM_GEHAEUSE / 2
    px0 = -(KAM_PLATINE[0] - KAM_LINSE_ZUR_STECKERKANTE)
    px1 = KAM_LINSE_ZUR_STECKERKANTE
    py0, py1 = KAM_S - KAM_PLATINE[1] / 2, KAM_S + KAM_PLATINE[1] / 2
    z_pl_hinten = z_platine + KAM_PLATINE_DICK
    einbauten = {
        "glas": quader(
            -BREITE / 2, BREITE / 2, FENSTER_OBEN - 12, GLAS_OBEN, LIPPE, z_glas
        ),
        "lcd": quader(
            -BREITE / 2,
            BREITE / 2,
            FENSTER_OBEN - 12,
            GLAS_OBEN - UEBERSTAND,
            z_glas,
            z_glas + LCD_DICK,
        ),
        "kam_tubus": Pos(0, KAM_S, (linse + z_gehaeuse) / 2)
        * Cylinder(KAM_TUBUS_R, z_gehaeuse - linse),
        "kam_gehaeuse": quader(-g, g, KAM_S - g, KAM_S + g, z_gehaeuse, z_platine),
        "kam_platine": quader(px0, px1, py0, py1, z_platine, z_pl_hinten),
        "kam_stecker": quader(
            px1 - 5.71,
            px1,
            KAM_S - 9.8,
            KAM_S + 9.8,
            z_pl_hinten,
            z_pl_hinten + KAM_STECKER_HOCH,
        ),
    }
    masse = {
        "Kameragehäuse zur Glasrückseite (Tiefe)": z_gehaeuse - z_glas,
        "Kameragehäuse zur LCD-Kante (Schräge)": KAM_S - g - (GLAS_OBEN - UEBERSTAND),
        "Loch zur Glastasche (Schräge)": KAM_S - r - tasche,
        "Platine vorn oben zum Dach (senkrecht)": (dach_s(z_platine, True) - py1)
        * math.sin(T),
        "Stecker hinten oben zum Dach (senkrecht)": (
            dach_s(z_pl_hinten + KAM_STECKER_HOCH, True) - (KAM_S + 9.8)
        )
        * math.sin(T),
        "Wände bis zur Platine (Platz für Bauteile)": z_platine - WAND - FUEHRUNG,
        "Stützen unter der Platine (Gummiring)": z_platine - z_stuetze,
        "Linse hinter der Frontfläche": linse,
    }
    return teil, einbauten, masse


def pruefe(teil, einbauten, masse):
    fehler = []
    for name, wert in masse.items():
        print(f"  {name:45s} {wert:+.2f} mm")
        if name != "Linse hinter der Frontfläche" and wert < 0.3:
            fehler.append(f"zu wenig Luft: {name} {wert:+.2f} mm")
    if masse["Linse hinter der Frontfläche"] < 0:
        fehler.append("Linse steht über die Frontfläche hinaus")
    for name, k in einbauten.items():
        schnitt = teil & k
        v = schnitt.volume if schnitt is not None else 0
        if v > 0.01:
            fehler.append(f"Durchdringung: Probestück und {name}, {v:.1f} mm³")
    namen = list(einbauten)
    for n, a in enumerate(namen):
        for b in namen[n + 1 :]:
            if a.startswith("kam") and b.startswith("kam"):
                continue
            schnitt = einbauten[a] & einbauten[b]
            v = schnitt.volume if schnitt is not None else 0
            if v > 0.01:
                fehler.append(f"Durchdringung: {a} und {b}, {v:.1f} mm³")
    return fehler


FARBEN = {
    "teil": (0.93, 0.93, 0.90),
    "glas": (0.35, 0.55, 0.70),
    "lcd": (0.55, 0.57, 0.60),
    "kam_tubus": (0.12, 0.12, 0.13),
    "kam_gehaeuse": (0.72, 0.73, 0.75),
    "kam_platine": (0.10, 0.45, 0.20),
    "kam_stecker": (0.85, 0.82, 0.70),
}


def netz(koerper):
    ecken, dreiecke = koerper.tessellate(0.05, 0.2)
    v = np.array([(q.X, q.Y, q.Z) for q in ecken])
    f = np.hstack([[3, *t] for t in dreiecke])
    return pv.PolyData(v, f)


def bild(netze, datei, richtung, oben, schnitt_x=None, nur_teil=False):
    pl = pv.Plotter(off_screen=True, window_size=(1400, 1000))
    pl.set_background("white")
    for name, m in netze.items():
        if nur_teil and name != "teil":
            continue
        if schnitt_x is not None:
            m = m.clip(normal=(1, 0, 0), origin=(schnitt_x, 0, 0))
            if m.n_points == 0:
                continue
        pl.add_mesh(m, color=FARBEN[name], ambient=0.35, diffuse=0.7, specular=0.05)
        kanten = m.extract_feature_edges(feature_angle=25)
        if kanten.n_points:
            pl.add_mesh(kanten, color="black", line_width=1.5)
    alle = pv.merge(list(netze.values()))
    mitte = np.array(alle.center)
    pl.camera.position = tuple(
        mitte + np.array(richtung, dtype=float) * alle.length * 3
    )
    pl.camera.focal_point = tuple(mitte)
    pl.camera.up = oben
    pl.enable_parallel_projection()
    pl.reset_camera()
    pl.camera.zoom(1.1)
    pl.screenshot(os.path.join(ZIEL, datei))
    pl.close()


if __name__ == "__main__":
    os.makedirs(ZIEL, exist_ok=True)
    teil, einbauten, masse = baue()
    g = teil.bounding_box().size
    print(
        f"Probestück {g.X:.1f} x {g.Y:.1f} x {g.Z:.1f} mm, Volumen {teil.volume / 1000:.1f} cm³"
    )
    fehler = pruefe(teil, einbauten, masse)
    for z in fehler:
        print("  FEHLER " + z)
    print("  keine Fehler" if not fehler else f"  {len(fehler)} Fehler")
    # Für den Slicer in die Mitte des Betts (256 x 256 mm) schieben, sonst liegt das Teil halb daneben.
    m = teil.bounding_box().center()
    druck = Pos(128 - m.X, 128 - m.Y, 0) * teil
    export_stl(druck, os.path.join(ZIEL, "kamera_probe.stl"))
    export_step(druck, os.path.join(ZIEL, "kamera_probe.step"))
    netze = {"teil": netz(teil), **{n: netz(k) for n, k in einbauten.items()}}
    bild(netze, "1_schnitt_mitte.png", (1, 0, 0), (0, 1, 0), schnitt_x=0)
    bild(netze, "2_innen_schraeg.png", (0.5, -0.6, 1), (0, 1, 0))
    bild(netze, "3_innen_nur_teil.png", (0.5, -0.6, 1), (0, 1, 0), nur_teil=True)
    bild(netze, "4_vorn_nur_teil.png", (0, 0, -1), (0, 1, 0), nur_teil=True)
    print("fertig:", ZIEL)
    raise SystemExit(1 if fehler else 0)
