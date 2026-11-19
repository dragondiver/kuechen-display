"""Konstruktion A des Küchen-Display-Gehäuses: echte Körper mit Wandstärke, Verschraubung und Prüfung.

Aufruf aus dem Repo:  uv run --with build123d python gehaeuse/cad/gehaeuse.py [--export]

Achsen: x quer, y Tiefe (vorn negativ), z Höhe. Maße in mm.
Herkunft der Maße: Z = Zeichnung/Datenblatt, M = gemessen, F = vom Foto geschätzt, A = Annahme, E = entschieden.

Geprüft wird: (1) kein Teil durchdringt ein anderes, (2) jede Schraube hat ein Durchgangsloch in einem Teil
und einen Gewindeeinsatz, der ganz und mit Fleisch drumherum in einem anderen Teil sitzt.
"""

import json
import math
import os
import sys
from itertools import combinations

from build123d import (
    Box,
    Color,
    Compound,
    Cylinder,
    Location,
    Plane,
    Polygon,
    export_gltf,
    extrude,
    fillet,
)

W, TIEFE, SL, WINKEL, WAND = (
    235.0,
    120.0,
    157.0,
    75.0,
    4.0,
)  # E 19.11.2026: 120 tief, Front 157 lang (#4)
C, S = math.cos(math.radians(WINKEL)), math.sin(math.radians(WINKEL))
H, YF, YB = SL * S, -TIEFE / 2, TIEFE / 2
XI = W / 2 - WAND  # Innenfläche der Seitenwange
U0 = (
    -15.0
)  # Display nach links versetzt; -16,3 im Entwurf O passt mit 4 mm Wange nicht mehr (A)
GLAS_B, GLAS_H, BILD_B, BILD_H = 194.0, 119.0, 172.82, 108.24  # Z Waveshare
SM = (
    14 - 5.38 + GLAS_H / 2
)  # Mitte des Glases auf der Schräge: 14 mm Bildrand unten (Entwurf O)
T_GLAS, T_DISP, T_PLAT = (
    1.0,
    8.4,
    13.0,
)  # Lippe 1 mm (A), Display 7,4 dick (Z), Platine mit Bauteilen (F)
SPK_Y, SPK_Z = 10.0, 52.0  # Lautsprechermitte (A, nach Entwurf O)
EINSATZ_D, EINSATZ_L, FLEISCH = (
    4.0,
    5.7,
    1.5,
)  # ruthex M3 kurz: Loch 4,0 x 5,7 (Z), Wand um den Einsatz (A)


def fl(u, s, t):
    """Punkt hinter der schrägen Front: u quer, s die Schräge hinauf, t Tiefe hinter der Außenfläche."""
    return (u, YF + s * C + t * S, s * S - t * C)


def fr(u, s, t):
    """Lage in der Frontebene: lokal x quer, y die Schräge hinauf, z nach außen."""
    return Location(fl(u, s, t), (WINKEL, 0, 0))


def prisma(punkte, x0, x1):
    """Fläche in der y-z-Ebene, von x0 bis x1 gezogen."""
    k = extrude(Plane.YZ * Polygon(*punkte, align=None), x1 - x0)
    return (
        Location((x0 - k.bounding_box().min.X, 0, 0)) * k
    )  # die Zugrichtung hängt vom Umlaufsinn ab


def quader(x0, x1, y0, y1, z0, z1):
    return Location(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)) * Box(
        abs(x1 - x0), y1 - y0, z1 - z0
    )


def zyl(d, laenge, ort, richtung):
    """Zylinder ab `ort` in `richtung` ("x", "-x", "y", "z", "f" = Frontnormale nach außen, "-z" ...)."""
    dreh = {
        "z": (0, 0, 0),
        "-z": (180, 0, 0),
        "y": (-90, 0, 0),
        "-y": (90, 0, 0),
        "x": (0, 90, 0),
        "-x": (0, -90, 0),
        "f": (WINKEL, 0, 0),
    }[richtung]
    return Location(ort, dreh) * Location((0, 0, laenge / 2)) * Cylinder(d / 2, laenge)


FRONT_Y = 4 / S  # waagrechte Dicke der Frontplatte


def baue():
    """Liefert die Druckteile, die Einbauten als Hüllkörper und die Schraubenliste."""
    p, e, schrauben = {}, {}, []

    def schraube(name, kopf, richtung, laenge, durch, einsatz):
        schrauben.append(
            {
                "name": name,
                "kopf": kopf,
                "richtung": richtung,
                "laenge": laenge,
                "durch": durch,
                "einsatz": einsatz,
            }
        )

    # --- Frontplatte (PLA weiß): 4 mm, Bildfenster, Tasche fürs Glas, Dome, Nut für den Boden
    f = prisma(
        [(YF, 0), (YF + SL * C, H), (YF + SL * C + FRONT_Y, H), (YF + FRONT_Y, 0)],
        -XI,
        XI,
    )
    f -= fr(U0, SM, 2) * Box(BILD_B + 2, BILD_H + 2, 12)
    f -= fr(U0, SM, T_GLAS + 5) * Box(GLAS_B + 0.6, GLAS_H + 0.6, 10)
    s_kam = SM + GLAS_H / 2 + 1 + 12  # Kamera Module 3: 25 x 24 (Z), Linse mittig (A)
    f -= fr(U0, s_kam, 2) * Cylinder(4, 12)
    f -= fr(U0, s_kam, 1.5 + 5) * Box(25.6, 24.6, 10)
    xb = (U0 + GLAS_B / 2 + XI) / 2 + 3  # Mitte der Bedienspalte
    for s_, d in ((100, 7.2), (72, 12.2), (52, 3.1)):  # Drehgeber, Taster, LED (A)
        f -= fr(xb, s_, 2) * Cylinder(d / 2, 12)
    f -= fr(xb, 32, 2) * Box(6, 18, 12)  # Fenster der Leuchtleiste (A)
    f -= quader(
        -XI + 6, XI - 6, YF + FRONT_Y - 1.3, YF + FRONT_Y + 1.2, 1.2, 3.2
    )  # Nut für die Feder des Bodens
    dome_front = {
        "front_ol": (-XI + 6, 146),
        "front_or": (XI - 6, 146),
        "front_ur": (XI - 6, 17),
    }
    dome_klemm = {
        "klemm_ol": (U0 - 70, SM + GLAS_H / 2 + 6),
        "klemm_or": (U0 + 70, SM + GLAS_H / 2 + 6),
        "klemm_ro": (U0 + GLAS_B / 2 + 6, 104),
        "klemm_ru": (U0 + GLAS_B / 2 + 6, 40),
    }
    for u, s_ in list(dome_front.values()) + list(dome_klemm.values()):
        f += (
            fr(u, s_, T_DISP)
            * Location((0, 0, (T_DISP - 3) / 2))
            * Cylinder(4.2, T_DISP - 3)
        )
    p["front"] = f

    # --- Klemmrahmen (PLA grau): liegt hinten auf dem Rand des Displays
    k = fr(U0, SM, T_DISP + 1.5) * (
        Box(GLAS_B, GLAS_H, 3) - Box(GLAS_B - 20, GLAS_H - 20, 4)
    )
    for n, (u, s_) in dome_klemm.items():
        k += fr(u, s_, T_DISP + 1.5) * Box(12, 12, 3)
        schraube(n, fl(u, s_, T_DISP + 3), "f", 8, "klemmrahmen", "front")
    p["klemmrahmen"] = k

    # --- Seitenwangen (PLA Wood) mit Laschen, Klötzen und Domen
    slots = [zyl(1, 1, (0, 0, 0), "z")]  # Platzhalter, wird unten ersetzt
    for sx, n in ((-1, "l"), (1, "r")):
        x0, x1 = sx * XI, sx * W / 2
        w = prisma(
            [(YF, 0), (YF + SL * C, H), (YB, H), (YB, 0)], min(x0, x1), max(x0, x1)
        )
        for i in range(-5, 6):  # Langlöcher im Kreis vor dem Lautsprecher (Entwurf O)
            dz = i * 4.6
            halb = math.sqrt(max(27.5**2 - dz**2, 0))
            w -= (
                quader(
                    x0, x1, SPK_Y - halb, SPK_Y + halb, SPK_Z + dz - 1, SPK_Z + dz + 1
                )
                if halb > 3
                else slots[0]
            )
        xi = sx * (XI - 6)  # Mitte der 12 mm breiten Laschen
        # Laschen parallel zur Front: Schraube von innen in den Dom der Frontplatte
        for name in ("front_ol", "front_or", "front_ur"):
            u, s_ = dome_front[name]
            if (u > 0) == (sx > 0):
                w += fr(xi, s_, T_DISP + 2) * Box(12, 14, 4)
                schraube(name, fl(u, s_, T_DISP + 4), "f", 10, "wange_" + n, "front")
        # Laschen parallel zum Deckel: Schraube von unten in den Dom des Deckels
        for yy in (10, 36):
            w += quader(
                sx * (XI - 12), sx * XI, yy - 7, yy + 7, H - WAND - 8, H - WAND - 4
            )
            schraube(
                f"deckel_{n}_{yy}",
                (xi, yy, H - WAND - 8),
                "z",
                10,
                "wange_" + n,
                "deckel",
            )
        # Klötze hinten: oben nur Rückdeckel, unten Rückdeckel und Boden
        w += quader(
            sx * (XI - 20),
            sx * XI,
            YB - WAND - 10,
            YB - WAND,
            H - WAND - 16,
            H - WAND - 2,
        )
        w += quader(sx * (XI - 20), sx * XI, YB - WAND - 10, YB - WAND, WAND, WAND + 14)
        w += quader(
            sx * (XI - 20), sx * XI, -40, -28, WAND, WAND + 10
        )  # Klotz vorn für den Boden
        for zz in (H - WAND - 9, WAND + 8):
            schraube(
                f"rueck_{n}_{'o' if zz > 50 else 'u'}",
                (sx * (XI - 15), YB, zz),
                "-y",
                10,
                "rueckdeckel",
                "wange_" + n,
            )
        schraube(
            f"boden_{n}_h",
            (sx * (XI - 5), YB - WAND - 5, 0),
            "z",
            10,
            "boden",
            "wange_" + n,
        )
        schraube(
            f"boden_{n}_v", (sx * (XI - 10), -34, 0), "z", 10, "boden", "wange_" + n
        )
        # Dome für die Lautsprecherschale
        for nn, (yy, zz) in {"o": (10, 122), "u": (10, 9.5), "h": (49.5, 60)}.items():
            w += zyl(9, 6, (sx * XI, yy, zz), "-x" if sx > 0 else "x")
            schraube(
                f"schale_{n}_{nn}",
                (sx * (XI - 9), yy, zz),
                "x" if sx > 0 else "-x",
                8,
                "schale_" + n,
                "wange_" + n,
            )
        p["wange_" + n] = w

        # --- Lautsprecherschale (PLA): gerundete Wanne, innerer Flansch klemmt den Rahmen des FRS 7
        def wanne(d, sx=sx):
            b = fillet(Box(100 - 2 * d, 71 - 2 * d, 100 - 2 * d).edges(), 18 - d)
            b = Location((sx * XI, 8.5, 66)) * b
            hinter_front = prisma(
                [
                    fl(0, -20, 18.5 + d)[1:],
                    fl(0, SL + 40, 18.5 + d)[1:],
                    (YB + 50, H + 50),
                    (YB + 50, -50),
                ],
                -W,
                W,
            )
            return b & hinter_front & quader(0, sx * (XI - 3), -200, 200, -50, 300)

        sch = wanne(0) - wanne(2.4)
        offen = Location((sx * (XI - 3), 8.5, 66)) * Box(
            8, 71 - 4.8, 100 - 4.8
        )  # Seite zur Wange
        flansch = (
            quader(sx * (XI - 4.5), sx * (XI - 3), -27, 44, 16, 116) & wanne(0)
        ) - zyl(63, 20, (sx * (XI - 10), SPK_Y, SPK_Z), "x" if sx > 0 else "-x")
        rand = (
            quader(sx * (XI - 3.2), sx * XI, -27, 44, 16, 116)
            & (Location((sx * 3, 0, 0)) * wanne(0))
        ) - quader(
            sx * (XI - 4), sx * (XI + 1), SPK_Y - 34, SPK_Y + 34, SPK_Z - 34, SPK_Z + 34
        )
        sch = (sch - offen) + flansch + rand
        for yy, zz in ((10, 122), (10, 9.5), (49.5, 60)):
            sch += quader(
                sx * (XI - 9), sx * (XI - 6), yy - 6, yy + 6, zz - 6, zz + 6
            ) - wanne(2.4)
        p["schale_" + n] = sch
        # Lautsprecher FRS 7: Rahmen 66,5 x 3 (M), Korb Ø 62 x 28,5 (Z Verpackung)
        e["lautsprecher_" + n] = quader(
            sx * (XI - 3),
            sx * XI,
            SPK_Y - 33.25,
            SPK_Y + 33.25,
            SPK_Z - 33.25,
            SPK_Z + 33.25,
        ) + zyl(62, 28.5, (sx * (XI - 3), SPK_Y, SPK_Z), "-x" if sx > 0 else "x")

    # --- Deckel (PLA Wood): Tasche für die Mikrofonleiste, Dome
    yd0 = YF + SL * C + FRONT_Y
    d = quader(-XI, XI, yd0, YB - WAND, H - WAND, H)
    ym = 22.0
    d -= quader(
        U0 - 58, U0 + 58, ym - 8, ym + 8, H - WAND, H - 1
    )  # Tasche, 1 mm Haut bleibt
    d -= quader(
        U0 - 9, U0 + 9, ym + 8, ym + 20, H - WAND, H - 1
    )  # Kanal für das Flachbandkabel nach hinten
    for i in range(4):
        d -= zyl(
            1.6, 3, (U0 + (i - 1.5) * 33, ym, H - 2), "z"
        )  # Schallöffnungen, 33 mm Abstand (Z)
    for sx, n in ((-1, "l"), (1, "r")):
        for yy in (10, 36):
            d += zyl(8.4, 4, (sx * (XI - 6), yy, H - WAND - 4), "z")
    for sx, n in ((-1, "l"), (1, "r")):
        d += zyl(8.4, 4, (U0 + sx * 66, ym, H - WAND - 4), "z")
        schraube(
            f"mikro_{n}",
            (U0 + sx * 66, ym, H - WAND - 6.5),
            "z",
            8,
            "mikrobuegel",
            "deckel",
        )
    p["deckel"] = d
    # Bügel hält die Mikrofonleiste von unten
    p["mikrobuegel"] = (
        quader(U0 - 72, U0 + 72, ym - 5, ym + 5, H - WAND - 6.5, H - WAND - 4)
        + quader(U0 - 50, U0 - 20, ym - 5, ym + 5, H - WAND - 4, H - WAND - 2.7)
        + quader(U0 + 20, U0 + 50, ym - 5, ym + 5, H - WAND - 4, H - WAND - 2.7)
    )
    e["mikrofonleiste"] = quader(
        U0 - 57.5, U0 + 57.5, ym - 7.5, ym + 7.5, H - 2.6, H - 1
    )  # 115 x 15 x 1,6 (F)
    e["mikro_buchse_kabel"] = quader(
        U0 - 8, U0 + 8, ym - 5.2, ym + 18, H - 5.6, H - 2.6
    ) - quader(
        U0 - 9, U0 + 9, ym - 6, ym + 5.2, H - 5.6, H - 4
    )  # Buchse und flaches Kabel nach hinten (F)

    # --- Boden (PLA): Feder für die Front, Rippe hinter dem Klemmrahmen, Führungen für den Schlitten
    b = prisma(
        [
            (YF + FRONT_Y, 0),
            (YF + FRONT_Y + WAND * C / S, WAND),
            (YB - WAND, WAND),
            (YB - WAND, 0),
        ],
        -XI,
        XI,
    )
    b += quader(
        -XI + 7, XI - 7, YF + FRONT_Y - 1.0, YF + FRONT_Y + 0.9, 1.5, 2.9
    )  # Feder
    y_rippe = fl(0, 0, T_DISP + 4.2)[1] + (WAND + 5) / math.tan(math.radians(WINKEL))
    b += quader(
        U0 - GLAS_B / 2 + 4, U0 + GLAS_B / 2 - 4, y_rippe, y_rippe + 2.5, WAND, WAND + 5
    )
    ST_X, ST_Y0, ST_Y1 = (
        44.0,
        YB - WAND - 2 - 56,
        YB - WAND - 2,
    )  # Stapel 88 x 56 (Z), 2 mm vor dem Rückdeckel
    for sx in (-1, 1):
        b += quader(sx * 57, sx * 59.5, ST_Y0, ST_Y1, WAND, WAND + 4)  # Führungsleisten
    for xx, yy in (
        (-100, -50),
        (100, -50),
        (-100, 50),
        (100, 50),
    ):  # Füße: Mulden für Ø 12 Gummifüße (A)
        b -= zyl(12.4, 0.6, (xx, yy, 0), "z")
    p["boden"] = b

    # --- Schlitten (PLA grau): Platte unter dem Stapel, zwei Dome für die Schrauben von unten
    sl = quader(-56, 56, ST_Y0, ST_Y1, WAND + 0.2, WAND + 3.2)
    for sx, n in ((-1, "l"), (1, "r")):
        sl += zyl(9, 4, (sx * 50.5, (ST_Y0 + ST_Y1) / 2, WAND + 3.2), "z")
        schraube(
            f"schlitten_{n}",
            (sx * 50.5, (ST_Y0 + ST_Y1) / 2, 0),
            "z",
            10,
            "boden",
            "schlitten",
        )
    p["schlitten"] = sl
    e["stapel"] = quader(
        -ST_X, ST_X, ST_Y0, ST_Y1, WAND + 3.2, WAND + 3.2 + 88
    )  # 88 hoch (F)

    # --- Rückdeckel (PLA Wood): Abluft oben quer, Zuluft seitlich neben dem Stapel, USB-C
    r = quader(-XI, XI, YB - WAND, YB, 0, H)
    for i in range(5):
        for sx in (-1, 1):
            r -= quader(
                sx * 36 - 30,
                sx * 36 + 30,
                YB - WAND - 1,
                YB + 1,
                H - 16 - i * 4.6 - 1.25,
                H - 16 - i * 4.6 + 1.25,
            )
    for sx in (-1, 1):
        for i in range(4):
            r -= quader(
                sx * (47.5 + i * 4.6) - 1.25,
                sx * (47.5 + i * 4.6) + 1.25,
                YB - WAND - 1,
                YB + 1,
                34,
                94,
            )
    r -= quader(
        54 - 4.6, 54 + 4.6, YB - WAND - 1, YB + 1, 18.3, 21.7
    )  # USB-C-Einbaubuchse (A, Teil noch nicht gefunden)
    p["rueckdeckel"] = r

    # --- Einbauten als Hüllkörper
    e["display"] = fr(U0, SM, (T_GLAS + T_DISP) / 2) * Box(
        GLAS_B, GLAS_H, T_DISP - T_GLAS
    )
    e["display_platine"] = fr(U0, SM, (T_DISP + T_PLAT) / 2) * Box(
        110, 97.5, T_PLAT - T_DISP
    )  # Z, Lage mittig (A)
    e["kernplatine"] = fr(U0, SM, T_DISP + 1.6 + 8 + 5.8) * Box(
        46, 46, 11.6
    )  # auf 8-mm-Bolzen (Z), 46 x 46, 10 hoch (F)
    e["kamera"] = fr(U0, s_kam, 1.5 + 5.5) * Box(25, 24, 11)
    e["bedienteile"] = fr(xb, 69, 4 + 6) * Box(
        14, 80, 12
    )  # Drehgeber 12 tief (PR #55), Taster, LED, Leuchtleiste (A)
    return p, e, schrauben


def bohre(p, schrauben):
    """Schneidet Durchgangsloch (3,4) und Einsatzloch (4,0) und liefert je Schraube die Körper zum Prüfen."""
    roh = dict(p)
    for sch in schrauben:
        sch["schaft"] = zyl(3.0, sch["laenge"], sch["kopf"], sch["richtung"])
        sch["einsatz_k"] = None
        for anfang in [x * 0.5 for x in range(int(sch["laenge"] * 2))]:
            ort = (
                zyl(0.01, anfang, sch["kopf"], sch["richtung"]).bounding_box().center()
            )
            ende = tuple(2 * c - k for c, k in zip((ort.X, ort.Y, ort.Z), sch["kopf"]))
            probe = zyl(EINSATZ_D, EINSATZ_L, ende, sch["richtung"])
            if (probe - roh[sch["einsatz"]]).volume < 0.5:
                sch["einsatz_k"], sch["einsatz_ort"] = probe, ende
                break
        p[sch["durch"]] -= zyl(3.4, sch["laenge"], sch["kopf"], sch["richtung"])
        if sch["einsatz_k"] is not None:
            p[sch["einsatz"]] -= zyl(
                EINSATZ_D, EINSATZ_L, sch["einsatz_ort"], sch["richtung"]
            )
    return roh


def pruefe(p, e, roh, schrauben):
    fehler = []
    alle = {**p, **e}
    paar_ok = [
        {"display", "display_platine"},
        {"display_platine", "kernplatine"},
        {"mikrofonleiste", "mikro_buchse_kabel"},
    ]
    for a, b in combinations(alle, 2):
        if {a, b} in paar_ok:
            continue
        v = (alle[a] & alle[b]).volume
        if v > 20:
            fehler.append(f"DURCHDRINGUNG {a} / {b}: {v / 1000:.2f} cm³")
    for sch in schrauben:
        n = sch["name"]
        if (sch["schaft"] & roh[sch["durch"]]).volume < 3:
            fehler.append(f"SCHRAUBE {n}: geht nicht durch {sch['durch']}")
        if sch["einsatz_k"] is None:
            fehler.append(
                f"SCHRAUBE {n}: kein Platz für den Gewindeeinsatz in {sch['einsatz']}"
            )
            continue
        mantel = zyl(
            EINSATZ_D + 2 * FLEISCH, EINSATZ_L, sch["einsatz_ort"], sch["richtung"]
        )
        if (mantel - roh[sch["einsatz"]]).volume > 0.05 * mantel.volume:
            fehler.append(
                f"SCHRAUBE {n}: zu wenig Fleisch um den Einsatz in {sch['einsatz']}"
            )
        for name, k in alle.items():
            if (
                name not in (sch["durch"], sch["einsatz"])
                and (sch["schaft"] & k).volume > 1
            ):
                fehler.append(f"SCHRAUBE {n}: stößt durch {name}")
    return fehler


FARBEN = {
    "front": (0.95, 0.95, 0.93),
    "wange": (0.80, 0.68, 0.50),
    "deckel": (0.80, 0.68, 0.50),
    "rueckdeckel": (0.80, 0.68, 0.50),
    "boden": (0.92, 0.92, 0.90),
    "schale": (0.86, 0.86, 0.83),
    "klemmrahmen": (0.6, 0.61, 0.62),
    "schlitten": (0.6, 0.61, 0.62),
    "mikrobuegel": (0.6, 0.61, 0.62),
}


if __name__ == "__main__":
    p, e, schrauben = baue()
    roh = bohre(p, schrauben)
    print(
        f"Gehäuse {W:.0f} x {TIEFE:.0f} x {H:.0f} mm, {len(p)} Druckteile, {len(schrauben)} Schrauben M3"
    )
    for name, k in p.items():  # Bambu Lab A1: Bett 256 x 256 mm, nutzbar etwa 250
        g = sorted(k.bounding_box().size)
        if g[1] > 250 or g[2] > 250:
            print(f"  ZU GROSS fürs Druckbett: {name} {g[2]:.0f} x {g[1]:.0f} mm")
    print(
        "  größtes Teil: "
        + max(((sorted(k.bounding_box().size)[2], n) for n, k in p.items()))[1]
    )
    fehler = pruefe(p, e, roh, schrauben)
    for z in fehler:
        print("  " + z)
    print("  keine Fehler" if not fehler else f"  {len(fehler)} Fehler")
    if "--export" in sys.argv:
        ziel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ausgabe")
        os.makedirs(ziel, exist_ok=True)
        kinder = []
        for name, k in {**p, **e}.items():
            k.label = name
            k.color = Color(*FARBEN.get(name.split("_")[0], (0.2, 0.2, 0.22)))
            kinder.append(k)
        for sch in schrauben:
            kk = (
                sch["schaft"]
                + zyl(
                    5.5,
                    2,
                    sch["kopf"],
                    {
                        "z": "-z",
                        "-z": "z",
                        "y": "-y",
                        "-y": "y",
                        "x": "-x",
                        "-x": "x",
                        "f": "f",
                    }[sch["richtung"]],
                )
                if sch["richtung"] != "f"
                else sch["schaft"]
            )
            kk.label, kk.color = "schraube_" + sch["name"], Color(0.08, 0.08, 0.09)
            kinder.append(kk)
        export_gltf(
            Compound(label="kuechen_display", children=kinder),
            os.path.join(ziel, "gehaeuse.glb"),
            binary=True,
        )
        datei = open(os.path.join(ziel, "teile.json"), "w")  # noqa: SIM115
        json.dump(
            {
                "teile": list(p),
                "einbauten": list(e),
                "schrauben": [
                    {k: s[k] for k in ("name", "richtung", "durch", "einsatz")}
                    for s in schrauben
                ],
            },
            datei,
            indent=1,
        )
        datei.close()
        print("exportiert nach", ziel)
    sys.exit(1 if fehler else 0)
