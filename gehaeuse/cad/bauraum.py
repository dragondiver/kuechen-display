"""Bauraum-Modell des Küchen-Displays: alle Teile als Hüllkörper, dazu eine Kollisionsprüfung.

Aufruf aus dem Repo:  uv run --with build123d python gehaeuse/cad/bauraum.py [tiefe_mm]

Achsen wie in entwurf_o.py: x quer, y Tiefe (vorn negativ), z Höhe. Maße in mm.
Jedes Maß trägt seine Herkunft: Z = Zeichnung/Datenblatt, M = gemessen, F = vom Foto geschätzt, A = Annahme.
"""

import math
import sys
from itertools import combinations

from build123d import Box, Cylinder, Location, Plane, Polygon, extrude, offset

TIEFE = (
    float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
)  # 120 statt 105: Entscheidung 19.11.2026 (#4)
RAND_UNTEN = (
    float(sys.argv[2]) if len(sys.argv) > 2 else 14.0
)  # Bildrand unten wie Entwurf O
W, SL, WINKEL, WAND = 235.0, 148.0, 75.0, 4.0  # Entwurf O; Wandstärke A
LUFT = 2.0  # Mindestabstand zwischen zwei Teilen, A
c, s = math.cos(math.radians(WINKEL)), math.sin(math.radians(WINKEL))
HOEHE, YF, YB = SL * s, -TIEFE / 2, TIEFE / 2
U0 = -16.3  # Display nach links versetzt (Entwurf O)


def innenraum():
    """Keilprofil, um die Wandstärke nach innen versetzt, über die Innenbreite gezogen."""
    profil = Plane.YZ * Polygon(
        (YF, 0), (YF + SL * c, HOEHE), (YB, HOEHE), (YB, 0), align=None
    )
    return extrude(offset(profil, -WAND), (W - 2 * WAND) / 2, both=True)


def an_front(breite, hoch, t0, t1, u=0.0, mitte=74.0):
    """Quader hinter der schrägen Front: mitte = Lage auf der Schräge, t0..t1 = Tiefe hinter der Außenfläche."""
    t = (t0 + t1) / 2
    y, z = YF + mitte * c + t * s, mitte * s - t * c
    return Location((u, y, z), (WINKEL, 0, 0)) * Box(breite, hoch, t1 - t0)


def quader(bx, by, bz, x, y0, z0):
    """Quader mit Mitte x, vorderer Kante y0 und Unterkante z0."""
    return Location((x, y0 + by / 2, z0 + bz / 2)) * Box(bx, by, bz)


def teile(stapel_y=None):
    """Hüllkörper aller Einbauten. stapel_y = vordere Kante des Stapels; None = ganz hinten."""
    t = {}
    # Display: Glas 194 x 119 x 7,4 (Z), unterer Rand 14 mm (Entwurf O), 3 mm Frontlippe (A)
    dm = RAND_UNTEN - 5.4 + 119 / 2
    t["display"] = an_front(194, 119, 3, 10.4, U0, dm)
    # Platine auf der Rückseite 110 x 97,5 (Z), 1,6 dick plus Bauteile 3 (F); Lage mittig (A)
    t["display_platine"] = an_front(110, 97.5, 10.4, 15, U0, dm)
    # Kernplatine auf den vier Bolzen (8 mm, Z): 46 x 46 (F), Bauteile mit Schraubklemme 10 (F)
    t["kernplatine"] = an_front(60, 51, 15 + 8 - 3, 15 + 8 + 1.6 + 10, U0, dm)
    # Stapel: Acryl, 4 Zellen in zwei Lagen, UPS HAT, Pi 5, Active Cooler: 88 x 56 (Z), 88 hoch (F)
    sy = YB - WAND - LUFT - 56 if stapel_y is None else stapel_y
    t["stapel"] = quader(
        88, 56, 88, 0, sy, WAND + 2 + 1
    )  # 2 mm Schlitten, 1 mm Luft (A)
    # Lautsprecher FRS 7: Korb Ø 62, 28,5 hinter dem Rahmen (M, #3), Mitte wie Entwurf O
    for n, sx in (("l", -1), ("r", 1)):
        t["lautsprecher_" + n] = Location(
            (sx * (W / 2 - WAND - 28.5 / 2), 10, 52), (0, 90, 0)
        ) * Cylinder(31, 28.5)
    # Mikrofonleiste 115 x 15 (F) in einer Tasche unter dem Deckel, mit Buchse und Kabel 7 hoch (F)
    ym = (YF + SL * c + YB) / 2
    t["mikrofonleiste"] = quader(115, 15, 6, U0, ym - 7.5, HOEHE - 1 - 6)
    t["mikro_kabel"] = quader(12, 14, 6, U0, ym + 7.5, HOEHE - 1 - 6)
    # Kamera Module 3: 25 x 24 (Z), 11,5 tief mit Linse (Z)
    t["kamera"] = an_front(25, 24, 1, 12.5, U0, dm + 119 / 2 + 1 + 12)
    # Bedienspalte rechts neben dem Glas: Drehgeber 12 tief (PR #55), Taster, Leuchtleiste (A)
    t["bedienspalte"] = an_front(
        W / 2 - WAND - (U0 + 97) - 1, 119, 3, 16, (U0 + 97 + W / 2 - WAND + 1) / 2, dm
    )
    return t


IN_DER_WAND = (
    "display",
    "kamera",
    "mikrofonleiste",
    "mikro_kabel",
    "bedienspalte",
)  # sitzen in Taschen der Front oder des Deckels


def kammer(t, raum, seite, breite=50.0):
    """Was neben der Seitenwand für eine Lautsprecherschale frei ist: Streifen von `breite` mm, ohne alles, was dort schon sitzt."""
    k = raum & (
        Location((seite * (W / 2 - WAND - breite / 2), 0, HOEHE / 2))
        * Box(breite, TIEFE, HOEHE)
    )
    for n, teil in t.items():
        if not n.startswith("lautsprecher"):
            k = k - teil
    return k.volume / 1e6


def pruefe(t, raum):
    """Liefert (Teil, Teil, Überschneidung in cm³) und (Teil, Volumen außerhalb des Innenraums in cm³)."""
    fehler = []
    for a, b in combinations(t, 2):
        if (
            {a[:6], b[:6]} == {"lautsp", "schale"}
            or {a, b} == {"display", "display_platine"}
            or {a, b} == {"display_platine", "kernplatine"}
        ):
            continue  # gehören zusammen
        if {a, b} == {"mikrofonleiste", "mikro_kabel"}:
            continue
        v = (t[a] & t[b]).volume
        if v > 50:  # mm³; darunter berühren sich die Hüllkörper nur
            fehler.append((a, b, v / 1000))
    for a, k in t.items():
        if a in IN_DER_WAND and a.startswith("mikro"):
            continue
        if a in IN_DER_WAND:  # Front darf durchdrungen werden, Boden und Deckel nicht
            platten = Location((0, 0, WAND / 2)) * Box(W, TIEFE, WAND) + Location(
                (0, 0, HOEHE - WAND / 2)
            ) * Box(W, TIEFE, WAND)
            v = (k & platten).volume + (
                k - Location((0, 0, HOEHE / 2)) * Box(W, 2 * TIEFE, HOEHE)
            ).volume
            if v > 50:
                fehler.append((a, "Boden oder Deckel", v / 1000))
            continue
        v = (k - raum).volume
        if v > 50:  # mm³; darunter berühren sich die Hüllkörper nur
            fehler.append((a, "Gehäusewand", v / 1000))
    return fehler


def freie_tiefe(t):
    """Freie Tiefe hinter der Kernplatine bis zur Rückwand, dazu ihre Unter- und Oberkante."""
    bb = t["kernplatine"].bounding_box()
    return (YB - WAND) - bb.max.Y, bb.min.Z, bb.max.Z


if __name__ == "__main__":
    raum, t = innenraum(), teile()
    print(
        f"Gehäuse {W:.0f} x {TIEFE:.0f} x {HOEHE:.0f} mm, Wand {WAND:.0f} mm, Innenraum {raum.volume / 1e6:.2f} l"
    )
    frei, z0, z1 = freie_tiefe(t)
    print(
        f"Kernplatine reicht von z = {z0:.0f} bis {z1:.0f} mm; dahinter bleiben {frei:.0f} mm bis zur Rückwand, der Stapel braucht 56 mm"
    )
    print(
        f"Platz für eine Lautsprecherschale, 50 mm breit: links {kammer(t, raum, -1):.2f} l, rechts {kammer(t, raum, 1):.2f} l (brutto, ohne Wand der Schale)"
    )
    oben = SL - (RAND_UNTEN - 5.4 + 119)
    print(
        f"Über dem Glas bleiben auf der Schräge {oben:.1f} mm, davon {WAND:.0f} mm Deckel; die Kamera ist 24 mm hoch"
    )
    fehler = pruefe(t, raum)
    for a, b, v in sorted(fehler, key=lambda f: -f[2]):
        print(f"  KOLLISION {a} / {b}: {v:.1f} cm³")
    if not fehler:
        print("  keine Kollision")
    sys.exit(1 if fehler else 0)
