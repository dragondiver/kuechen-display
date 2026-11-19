"""Tischständer für den Tischtest (#18): Display, Kamera, Mikrofonleiste, zwei FRS 7.

Aufruf:  blender -b -P gehaeuse/blender/tischstaender.py
Schreibt nach gehaeuse/renders/tischstaender/: sockel.stl, leiste.stl, vorschau-*.png

Zwei Teile, beide ohne Stützen druckbar:
- sockel: Bodenplatte mit Rinne fürs Display (lehnt mit 75 Grad an zwei Stützen),
  zwei Becher für die Lautsprecher (Membran nach oben), freie Fläche für Kernboard und Pi-Turm.
- leiste: wird oben auf die Zapfen der Stützen gesteckt, trägt die Kameratasche (15 Grad
  nach hinten geneigt) und die zwei Endtaschen für die Mikrofonleiste.

Maße in Millimetern. x quer, y von vorn nach hinten, z nach oben. Alles mit Spiel gebaut;
die Werte im Block MASSE sind die Stellen, an denen ein nachgemessenes Maß etwas ändert.
"""

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------- MASSE
GLAS_B = 194.0  # Display Glas, Breite (Waveshare-Zeichnung)
GLAS_H = 119.0  # Display Glas, Höhe
GLAS_D = 5.3  # Dicke an der Kante, gemessen 19.11.2026
RINNE = 8.0  # Rinnenbreite; 5,3 mm bei 75 Grad sind 5,5 mm, dazu Luft
LIPPE_H = 4.0  # vordere Lippe, verdeckt nur den Glasrand
WINKEL = 75.0  # Neigung wie im Gehäuseentwurf

FRS_KORB = 63.2  # Innendurchmesser Becher; Korb gemessen 61,7, Flansch 66,4 im Quadrat
FRS_TIEFE = 36.0  # Becherhöhe; Lautsprecher ca. 31 mm tief

KAM_B = 25.0  # Kameraplatine Breite (Raspberry Pi, Camera Module 3)
KAM_LUFT = 0.8
KAM_TASCHE = 4.5  # Platz hinter den Haltelippen: Platine plus Stecker auf der Rückseite

MIK_L = 110.6  # Mikrofonleiste, gemessen 110,6 x 11
MIK_B = 11.3  # lichte Breite der Endtaschen; Platine gemessen 11,1
MIK_LUFT = 0.2  # Luft je Ende in der Länge
MIK_AUFLAGE = 9.0  # so weit liegt die Platine an jedem Ende auf
MIK_HOCH = 3.5  # Auflage über der Leiste, Platz für Stecker und Kabel darunter

# ---------------------------------------------------------------- abgeleitet
B = 240.0  # Sockelbreite
T = 165.0  # Sockeltiefe
BODEN = 2.4
Y_LIPPE = 6.0
Y_RINNE0 = Y_LIPPE + 3.0
Y_RINNE1 = Y_RINNE0 + RINNE
Z_OBEN = 125.0  # Oberkante der Stützen, 5 mm über der Displaykante
# Glas steht links 8 mm, sonst 3 mm über den Körper; die Stützen liegen 11 bis 17 mm vom Glasrand an
STUETZE_X0, STUETZE_X1 = 80.0, 86.0
NEIG = 1.0 / math.tan(math.radians(WINKEL))
Y_ST_OBEN = Y_RINNE1 + (Z_OBEN - BODEN) * NEIG  # Vorderkante der Stütze oben
ZAPFEN = (6.0, 8.0, 4.0)  # x, y, z
ZAPFEN_Y0 = Y_ST_OBEN + 6.0
LEISTE_D = 4.0
LEISTE_Y0 = Y_ST_OBEN - 3.5
LEISTE_T = 44.0
BECHER_X, BECHER_Y = 82.0, 126.0
BECHER_WAND = 2.5

AUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "renders", "tischstaender")
os.makedirs(AUS, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
SZENE = bpy.context.scene


# ---------------------------------------------------------------- Bausteine
def _objekt(bm, name):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    SZENE.collection.objects.link(ob)
    return ob


def quader(x0, x1, y0, y1, z0, z1, name="q", mat=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((x0 + (v.co.x + 0.5) * (x1 - x0), y0 + (v.co.y + 0.5) * (y1 - y0), z0 + (v.co.z + 0.5) * (z1 - z0)))
        if mat is not None:
            v.co = mat @ v.co
    return _objekt(bm, name)


def zylinder(cx, cy, r, z0, z1, name="z", seg=96):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=z1 - z0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(cx, cy, (z0 + z1) / 2))
    return _objekt(bm, name)


def prisma_yz(punkte, x0, x1, name="p"):
    """Polygon in der y-z-Ebene, entlang x gezogen."""
    bm = bmesh.new()
    a = [bm.verts.new((x0, y, z)) for y, z in punkte]
    b = [bm.verts.new((x1, y, z)) for y, z in punkte]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(punkte)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))
    return _objekt(bm, name)


def prisma_xy(punkte, z0, z1, name="p"):
    """Polygon in der x-y-Ebene, entlang z gezogen."""
    bm = bmesh.new()
    a = [bm.verts.new((x, y, z0)) for x, y in punkte]
    b = [bm.verts.new((x, y, z1)) for x, y in punkte]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(punkte)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))
    return _objekt(bm, name)


def _bool(a, b, art):
    m = a.modifiers.new("b", "BOOLEAN")
    m.operation = art
    m.solver = "EXACT"
    m.object = b
    bpy.context.view_layer.objects.active = a
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(b, do_unlink=True)
    return a


def plus(a, *rest):
    for b in rest:
        _bool(a, b, "UNION")
    return a


def minus(a, *rest):
    for b in rest:
        _bool(a, b, "DIFFERENCE")
    return a


# ---------------------------------------------------------------- Sockel
def sockel():
    s = quader(-B / 2, B / 2, 0, T, 0, BODEN, "sockel")
    # Rinne: vorn Lippe, hinten niedrige Kante
    plus(
        s,
        quader(-102, 102, Y_LIPPE, Y_RINNE0, 0, BODEN + LIPPE_H),
        quader(-102, 102, Y_RINNE1, Y_RINNE1 + 2.5, 0, BODEN + 3.0),
    )
    for sx in (-1, 1):
        x0, x1 = sorted((sx * STUETZE_X0, sx * STUETZE_X1))
        profil = [(Y_RINNE1, 0), (Y_ST_OBEN, Z_OBEN), (Y_ST_OBEN + 20, Z_OBEN), (Y_ST_OBEN + 26, 0)]
        st = prisma_yz(profil, x0, x1)
        zx0 = (x0 + x1) / 2 - ZAPFEN[0] / 2
        plus(
            s,
            st,
            quader(zx0, zx0 + ZAPFEN[0], ZAPFEN_Y0, ZAPFEN_Y0 + ZAPFEN[1], Z_OBEN - 1, Z_OBEN + ZAPFEN[2]),
            # Fuß gegen seitliches Wackeln
            prisma_yz([(Y_RINNE1 + 4, 0), (Y_RINNE1 + 4, 14), (Y_RINNE1 + 30, 0)], x0 - 0, x1 + 0),
            quader(x0 - 5, x1 + 5, Y_RINNE1 + 2.5, Y_ST_OBEN + 26, 0, BODEN + 3.0),
        )
        # Lautsprecherbecher
        cx = sx * BECHER_X
        ra = FRS_KORB / 2 + BECHER_WAND
        plus(s, zylinder(cx, BECHER_Y, ra, 0, BODEN + FRS_TIEFE))
        minus(
            s,
            zylinder(cx, BECHER_Y, FRS_KORB / 2, BODEN, BODEN + FRS_TIEFE + 1),
            zylinder(cx, BECHER_Y, FRS_KORB / 2 - 5, -1, BODEN + 1, seg=90),
            # außen ein Drittel offen: Platz für Lötfahnen und Krokodilklemmen
            prisma_xy(
                [(cx, BECHER_Y), (cx + sx * 40, BECHER_Y - 69.3), (cx + sx * 40, BECHER_Y + 69.3)],
                BODEN + 6,
                BODEN + FRS_TIEFE + 1,
            ),
            # innen ein schmaler Kabelschlitz
            quader(*sorted((cx, cx - sx * (ra + 2))), BECHER_Y - 5, BECHER_Y + 5, BODEN + 12, BODEN + FRS_TIEFE + 1),
        )
        # Material sparen neben der Mittelfläche
        minus(s, quader(*sorted((sx * 50, sx * 72)), 28, 78, -1, BODEN + 1))
    return s


# ---------------------------------------------------------------- Leiste
def leiste():
    z0, z1 = Z_OBEN, Z_OBEN + LEISTE_D
    y0, y1 = LEISTE_Y0, LEISTE_Y0 + LEISTE_T
    l = quader(-100, 100, y0, y1, z0, z1, "leiste")

    # Kameratasche: C-Profil, Platine wird von oben eingeschoben, 15 Grad nach hinten geneigt
    innen = KAM_B + KAM_LUFT
    ty0 = y0 + 1.0  # Vorderkante der Haltelippen
    ty_wand = ty0 + 1.5 + KAM_TASCHE
    h = 22.0
    dreh = Matrix.Translation((0, ty_wand + 2, z1)) @ Matrix.Rotation(math.radians(-15), 4, "X") @ Matrix.Translation((0, -(ty_wand + 2), -z1))
    tasche = quader(-innen / 2 - 2, innen / 2 + 2, ty0, ty_wand + 2, z1 - 3, z1 + h)
    minus(
        tasche,
        quader(-innen / 2, innen / 2, ty0 + 1.5, ty_wand, z1 - 5, z1 + h + 5),
        quader(-innen / 2 + 1.5, innen / 2 - 1.5, ty0 - 1, ty0 + 2, z1 - 5, z1 + h + 5),
    )
    tasche.data.transform(dreh)
    plus(l, tasche)
    # was durch die Neigung unter die Leiste ragt, abschneiden
    minus(l, quader(-30, 30, y0 - 10, y1, z0 - 10, z0))
    # Schlitz fürs Kamerakabel (16 mm breit)
    minus(l, quader(-10, 10, ty0 + 1.5, ty_wand, z0 - 1, z1 + 0.01))

    # Mikrofonleiste: je eine Tasche an den Enden, 3,5 mm über der Leiste. Die Mitte bleibt frei,
    # weil das Flachbandkabel quer über die lange Kante abgeht und Bauteile unten sitzen dürfen.
    yc = y1 - 10.0
    for sx in (-1, 1):
        innen_x = sx * (MIK_L / 2 - MIK_AUFLAGE)
        stop_x = sx * (MIK_L / 2 + MIK_LUFT)
        block = quader(*sorted((innen_x, stop_x + sx * 2)), yc - MIK_B / 2 - 2, yc + MIK_B / 2 + 2, z1 - 1, z1 + MIK_HOCH + 2.6)
        minus(block, quader(*sorted((innen_x - sx, stop_x)), yc - MIK_B / 2, yc + MIK_B / 2, z1 + MIK_HOCH, z1 + MIK_HOCH + 5))
        plus(l, block)

    # Löcher für die Zapfen, 0,35 mm Luft ringsum
    for sx in (-1, 1):
        cx = sx * (STUETZE_X0 + STUETZE_X1) / 2
        minus(l, quader(cx - ZAPFEN[0] / 2 - 0.35, cx + ZAPFEN[0] / 2 + 0.35, ZAPFEN_Y0 - 0.35, ZAPFEN_Y0 + ZAPFEN[1] + 0.35, z0 - 1, z1 + 1))
    return l


# ---------------------------------------------------------------- Prüfen, Export, Vorschau
def pruefen(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    offen = [e for e in bm.edges if len(e.link_faces) != 2]
    vol = bm.calc_volume() / 1000.0
    bm.free()
    ecken = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    mass = [max(c[i] for c in ecken) - min(c[i] for c in ecken) for i in range(3)]
    print(f"PRUEF {ob.name}: {mass[0]:.1f} x {mass[1]:.1f} x {mass[2]:.1f} mm, {vol:.0f} cm3, offene Kanten {len(offen)}")


def export(ob, datei, dz=0.0):
    ob.location.z -= dz
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.ops.wm.stl_export(filepath=os.path.join(AUS, datei), export_selected_objects=True)
    ob.location.z += dz


def attrappe(ob, farbe):
    m = bpy.data.materials.new(ob.name)
    m.diffuse_color = farbe
    ob.data.materials.append(m)


def vorschau():
    # Bauteile als Attrappen, nur fürs Bild
    kipp = Matrix.Translation((0, Y_RINNE1, BODEN)) @ Matrix.Rotation(math.radians(-(90 - WINKEL)), 4, "X")
    attrappe(quader(-GLAS_B / 2, GLAS_B / 2, -GLAS_D, 0, 0, GLAS_H, "display", mat=kipp), (0.03, 0.03, 0.04, 1))
    for sx in (-1, 1):
        attrappe(quader(sx * BECHER_X - 33.25, sx * BECHER_X + 33.25, BECHER_Y - 33.25, BECHER_Y + 33.25, BODEN + FRS_TIEFE, BODEN + FRS_TIEFE + 3, "frs"), (0.1, 0.1, 0.1, 1))
    y1 = LEISTE_Y0 + LEISTE_T - 1
    attrappe(quader(-MIK_L / 2, MIK_L / 2, y1 - 15.55, y1 - 4.45, Z_OBEN + LEISTE_D + MIK_HOCH, Z_OBEN + LEISTE_D + MIK_HOCH + 1.6, "mik"), (0.05, 0.2, 0.1, 1))

    SZENE.render.engine = "BLENDER_WORKBENCH"
    SZENE.display.shading.light = "STUDIO"
    SZENE.display.shading.color_type = "MATERIAL"
    SZENE.display.shading.show_cavity = True
    SZENE.display.shading.show_shadows = True
    SZENE.render.resolution_x, SZENE.render.resolution_y = 1400, 1000
    welt = bpy.data.worlds.new("w")
    SZENE.world = welt
    kd = bpy.data.cameras.new("k")
    kd.lens = 60
    kd.clip_end = 5000
    kam = bpy.data.objects.new("k", kd)
    SZENE.collection.objects.link(kam)
    SZENE.camera = kam
    ziel = Vector((0, 75, 60))
    for name, ort in (("vorn", (260, -480, 300)), ("hinten", (-300, 560, 330)), ("seite", (700, 80, 80))):
        kam.location = ort
        kam.rotation_euler = (ziel - kam.location).to_track_quat("-Z", "Y").to_euler()
        SZENE.render.filepath = os.path.join(AUS, f"vorschau-{name}.png")
        bpy.ops.render.render(write_still=True)


s = sockel()
l = leiste()
attrappe(s, (0.85, 0.82, 0.74, 1))
attrappe(l, (0.9, 0.45, 0.1, 1))
pruefen(s)
pruefen(l)
export(s, "sockel.stl")
export(l, "leiste.stl", dz=Z_OBEN)
vorschau()
