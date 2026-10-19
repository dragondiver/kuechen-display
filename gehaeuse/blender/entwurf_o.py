"""Entwurf O (ohne senkrechte Lippe wie Braun RT 20: Frontplatte geht vom Boden schraeg nach oben; weisser Rahmen ueber dem Displayrand, nur die Bildflaeche sichtbar, Kamera im Rahmen. Basis N: wie M, plus schwarze Kameraleiste ueber dem Displayglas, Schraege dafuer 14 mm laenger; Basis M: wie L, 7 Zoll, plus Bedienspalte rechts: Ein/Aus-Taste und Lautstaerkeknopf, beide gleich grau, Ø 12 mm, Mulde nach innen, enger und unten in der Spalte, orange LED rechts neben der Taste (13.10.2026); Mikrofonleiste flach oben, Oeffnungen nach oben; offizielles Touch Display 2, 7″; sonst wie K; mit weich gekanteten Ober- und Unterkanten der Frontplatte wie beim Braun RT 20): Keilgehaeuse, 10-Zoll-Touchdisplay mit 60 Grad Neigung, Pi im Gehaeuse,
ReSpeaker Flex XVF3800 Linear-4 als Mikrofonleiste in der oberen Blende, optionale Kamera.

Aufruf:  blender -b -P entwurf_d.py -- [quick] [ansicht ...]
Ansichten: iso front side back top detail   (ohne Angabe: alle)

Maße in Metern. Gesichert (Seeed-Wiki/Shop): Mikrofonabstand 33 mm, akustische Ports 7 mm,
Linear-Platine ca. 115 mm lang (aus DXF abgelesen). Angenommen: Gehaeuse, Display (10,1 Zoll,
sichtbar ca. 217 x 136 mm), Kamera, Lage der Lueftung und Buchsen.
"""
import bpy, sys, math, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
quick = "quick" in argv
innen = "innen" in argv
grau = "grau" in argv
weiss = "weiss" in argv
schwarzfront = "schwarzfront" in argv
mantel = "mantel" in argv
skala = "skala" in argv
acht = "acht" in argv  # Waveshare 8inch DSI LCD (C), Masse aus Waveshare-Zeichnung (referenz/8inch-dsi-lcd_c.pdf)
holz = "holz" in argv or mantel
schlitze = holz or "schlitze" in argv
WINKEL = next((int(a[1:]) for a in argv if a.startswith("w") and a[1:].isdigit()), 60)
views = [a for a in argv if a not in ("quick", "innen", "grau", "weiss", "schwarzfront", "holz", "schlitze", "mantel", "skala", "acht") and not (a.startswith("w") and a[1:].isdigit())] or (["innen_iso", "innen_side", "innen_back"] if innen else ["iso", "front", "detail", "side"])
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "renders")
mm = lambda v: v / 1000.0

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m

def put(o, m):
    o.data.materials.append(m)
    return o

def box(name, size, loc, m, bevel=0.0, seg=4, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.rotation_euler = rot
    if bevel:
        bv = o.modifiers.new("bevel", "BEVEL")
        bv.width = bevel
        bv.segments = seg
    bpy.ops.object.shade_smooth()
    return put(o, m)

def cyl(name, r, depth, loc, m, rot=(0, 0, 0), verts=32):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.shade_smooth()
    return put(o, m)

CREAM = mat("gehaeuse", (0.62, 0.62, 0.60), 0.55)
BLACK = mat("glas", (0.01, 0.012, 0.015), 0.12)
GRILLE = mat("gitter", (0.09, 0.095, 0.105), 0.8)
HOLE = mat("loch", (0.0, 0.0, 0.0), 1.0)
RUBBER = mat("gummi", (0.015, 0.015, 0.015), 0.9)
SCREEN = mat("screen", (0.01, 0.01, 0.012), 0.35, 0, (0.03, 0.03, 0.035), 1.0)
TEXT = mat("text", (1, 1, 1), 0.5, 0, (1.0, 1.0, 1.0), 6.0)
TEXT2 = mat("text2", (0.55, 0.55, 0.57), 0.5, 0, (0.6, 0.6, 0.62), 3.0)
TEAL = mat("orange_led", (0.9, 0.3, 0.03), 0.4, 0, (1.0, 0.33, 0.04), 14.0)
ORANGE = mat("orange", (0.9, 0.32, 0.03), 0.4)
WHITE = mat("weiss", (0.9, 0.9, 0.88), 0.5)
LENS = mat("linse", (0.02, 0.03, 0.06), 0.05, 0.3)
FLOOR = mat("boden", (0.32, 0.33, 0.35), 0.55)
SILVER = mat("silber", (0.6, 0.6, 0.62), 0.35, 0.9)
TILES = [mat("t1", (0.9, 0.32, 0.03), 0.4, 0, (1.0, 0.33, 0.04), 0.8),
         mat("t2", (0.1, 0.1, 0.11), 0.4, 0, (0.22, 0.22, 0.24), 0.5),
         mat("t3", (0.1, 0.1, 0.11), 0.4, 0, (0.22, 0.22, 0.24), 0.5),
         mat("t4", (0.1, 0.1, 0.11), 0.4, 0, (0.22, 0.22, 0.24), 0.5)]

# Gehaeuse: Keilprofil (y = Tiefe, z = Hoehe), Ausdehnung in x
W = mm(235 if acht else 230)
U0 = -16.3 if acht else -18  # 8″: Rand links = Rand unten = 14 mm  # Display nach links versetzt, rechts Platz fuer die Bedienspalte
SL = 148.0 if acht else 146.0  # Laenge der Schraege
_t = math.radians(WINKEL)
TIEFE = 113.0 if WINKEL == 60 else 105.0  # steiler: Tiefe halten, Oberseite waechst
HOEHE = SL * math.sin(_t)
YF = -TIEFE / 2
prof = [(YF, 0), (YF + SL * math.cos(_t), HOEHE), (TIEFE / 2, HOEHE), (TIEFE / 2, 0)]
verts = [(-W / 2, mm(y), mm(z)) for y, z in prof] + [(W / 2, mm(y), mm(z)) for y, z in prof]
n = len(prof)
faces = [list(range(n))[::-1], list(range(n, 2 * n))]
for i in range(n):
    j = (i + 1) % n
    faces.append([i, j, n + j, n + i])
me = bpy.data.meshes.new("keil")
me.from_pydata(verts, [], faces)
me.update()
body = bpy.data.objects.new("gehaeuse", me)
bpy.context.collection.objects.link(body)
bpy.context.view_layer.objects.active = body
me.update()
wattr = me.attributes.new(name="bevel_weight_edge", type="FLOAT", domain="EDGE")
for e in me.edges:
    a, b = e.vertices
    if abs(a - b) == n and min(a, b) in (0, 1):
        wattr.data[e.index].value = 1.0
bv = body.modifiers.new("weich", "BEVEL")
bv.width = mm(7)
bv.segments = 8
bv.limit_method = "WEIGHT"
bv2 = body.modifiers.new("scharf", "BEVEL")
bv2.width = mm(0.8)
bv2.segments = 2
bv2.limit_method = "ANGLE"
bv2.angle_limit = math.radians(30)
bpy.ops.object.shade_smooth()
put(body, CREAM)

# Frontpanel an der 60-Grad-Flaeche
TH = math.radians(WINKEL)
slope = Vector((0, math.cos(TH), math.sin(TH)))
normal = Vector((0, -math.sin(TH), math.cos(TH)))
start = Vector((0, mm(YF), mm(0)))
center = start + slope * mm(71 if acht else 72)
def pt(u, v, nn=0.0, abs_x=False):
    p = center + Vector((mm(u if abs_x else u + U0), 0, 0)) + slope * mm(v) + normal * mm(nn)
    return (p.x, p.y, p.z)
rot = (TH, 0, 0)

LEISTE = mat("kameraleiste", (0.02, 0.02, 0.022), 0.55)
# weisser Rahmen: Fenster nur so gross wie die Bildflaeche (154,5 x 87 mm + 1 mm), Display liegt dahinter
bpy.ops.mesh.primitive_cube_add(size=1, location=pt(0, -2, 0))
fenster = bpy.context.active_object
fenster.name = "fenster"
AW, AH = (172.82, 108.24) if acht else (154.5, 87)
fenster.scale = (mm(AW + 2), mm(AH + 2), mm(6))
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
fenster.rotation_euler = rot
fb = fenster.modifiers.new("rund", "BEVEL"); fb.width = mm(2); fb.segments = 4
fenster.hide_render = True
fenster.hide_viewport = True
bf = body.modifiers.new("fenster", "BOOLEAN"); bf.object = fenster; bf.operation = "DIFFERENCE"; bf.solver = "EXACT"
NN_UI = -5.4
box("glasrand", (mm(AW + 5.5), mm(AH + 5), mm(0.2)), pt(0, -2, -2.95), BLACK, rot=rot)
box("screen", (mm(AW), mm(AH), mm(0.2)), pt(0, -2, -2.8), SCREEN, rot=rot)

def label(body_text, size, u, v, m, align="CENTER", nn=3.6):
    c = bpy.data.curves.new("t_" + body_text, "FONT")
    c.body = body_text
    c.size = mm(size)
    c.align_x = align
    o = bpy.data.objects.new("t_" + body_text, c)
    bpy.context.collection.objects.link(o)
    o.location = pt(u, v, nn + NN_UI)
    o.rotation_euler = rot
    o.data.materials.append(m)
    return o

FX, FY = AW / 154.5, AH / 87
label("14:32", 18 * FY, -70 * FX, 18 * FY, TEXT, "LEFT")
label("Samstag, 4. Oktober", 4.6 * FY, -70 * FX, 8 * FY, TEXT2, "LEFT")
names = ["Rezepte", "YouTube", "Browser", "Eigene Apps"]
for i, u in enumerate([x * FX for x in (-54.6, -18.2, 18.2, 54.6)]):
    box("kachel", (mm(32 * FX), mm(28 * FY), mm(0.6)), pt(u, -24 * FY, 3.5 + NN_UI), TILES[i], bevel=mm(3), seg=4, rot=rot)
    label(names[i], 4.4 * FX, u, -26 * FY, TEXT, nn=4.3)
bpy.ops.mesh.primitive_uv_sphere_add(radius=mm(2.2), location=pt(68 * FX, 36 * FY, 4 + NN_UI), segments=20, ring_count=10)
put(bpy.context.active_object, TEAL)

# obere Blende: Mikrofonleiste (4 Ports, 33 mm Abstand) und optionale Kamera
# Mikrofonleiste flach auf der Oberseite, Oeffnungen nach oben (Kueche und Esstisch)
TOPZ = HOEHE + (1.1 if mantel else 0)
box("mikroleiste", (mm(124), mm(12), mm(0.8)), (mm(U0), mm((YF + SL * math.cos(_t) + TIEFE / 2) / 2), mm(TOPZ + 0.2)), mat("leiste", (0.08, 0.08, 0.09), 0.6), bevel=mm(1), seg=2)
for u in (-49.5, -16.5, 16.5, 49.5):
    cyl("mikro", mm(1.2), mm(0.6), (mm(U0 + u), mm((YF + SL * math.cos(_t) + TIEFE / 2) / 2), mm(TOPZ + 0.5)), HOLE, verts=16)
cyl("kamera_ring", mm(4.2), mm(1.2), pt(0, 66, 0.6), SILVER, rot=rot, verts=32)
cyl("kamera_linse", mm(3.0), mm(1.6), pt(0, 66, 0.9), LENS, rot=rot, verts=32)
cyl("kamera_led", mm(1.0), mm(0.8), pt(10, 66, 0.4), TEAL, rot=rot, verts=12)

# Lautsprecher: regelmaessiges Lochraster (Braun-Art) und oranger Drehknopf
fy = mm(YF)
if schwarzfront:
    box("frontplatte", (mm(34), mm(132.6), mm(1.0)), pt(95.5, 6.3, 0.5, abs_x=True), LEISTE, bevel=mm(1), seg=3, rot=rot)
# Bedienspalte rechts neben dem Display, auf der geneigten Flaeche
COLX = 93
TASTE = mat("taste", (0.16, 0.16, 0.17), 0.5)
def mulde_knopf(name, v, marke):
    # gleiche Bedienelemente: Zylinder mit nach innen gewoelbter Mulde (Kugel abgezogen)
    k = cyl(name, mm(6), mm(8), pt(COLX, v, 4.0, abs_x=True), TASTE, rot=rot, verts=64)
    R, tiefe = 14.0, 1.4
    bpy.ops.mesh.primitive_uv_sphere_add(radius=mm(R), location=pt(COLX, v, 8.0 + R - tiefe, abs_x=True), segments=192, ring_count=96)
    kugel = bpy.context.active_object
    kugel.hide_render = True
    kugel.hide_viewport = True
    b = k.modifiers.new("mulde", "BOOLEAN")
    b.object = kugel
    b.operation = "DIFFERENCE"
    b.solver = "EXACT"
    if marke == "strich":
        box(name + "_marke", (mm(1.0), mm(2.6), mm(0.4)), pt(COLX, v + 3.7, 7.8, abs_x=True), WHITE, rot=rot)
    else:
        cyl(name + "_marke", mm(0.8), mm(0.4), pt(COLX, v + 4.0, 7.8, abs_x=True), WHITE, rot=rot, verts=16)
    cyl(name + "_fuge", mm(6.7), mm(0.6), pt(COLX, v, 0.2, abs_x=True), HOLE, rot=rot, verts=64)

mulde_knopf("lautstaerke", -24, "strich")
mulde_knopf("ein_aus", -44, "punkt")
if skala:
    # Leuchtleiste wie die Skala beim RT 20: senkrechtes Fenster mit warmem Licht und feinen Strichen
    GLUT = mat("skala_licht", (0.80, 0.50, 0.34), 0.35, 0, (1.0, 0.50, 0.28), 1.1)
    box("skala_rahmen", (mm(11), mm(60), mm(0.6)), pt(COLX, 21, 0.3, abs_x=True), mat("skala_rand", (0.55, 0.55, 0.56), 0.4), bevel=mm(0.8), seg=3, rot=rot)
    box("skala", (mm(8.6), mm(57.6), mm(0.4)), pt(COLX, 21, 0.75, abs_x=True), GLUT, rot=rot)
    for i in range(10):
        lang = 5.0 if i % 3 == 0 else 3.0
        box("strich", (mm(lang), mm(0.5), mm(0.2)), pt(COLX - 4.3 + lang / 2, -6 + i * 6, 1.0, abs_x=True), mat("strich_" + str(i), (0.35, 0.33, 0.30), 0.6), rot=rot)
    box("zeiger", (mm(8.6), mm(0.8), mm(0.25)), pt(COLX, 30, 1.05, abs_x=True), mat("zeiger", (0.75, 0.12, 0.04), 0.5, 0, (0.9, 0.12, 0.03), 0.8), rot=rot)
cyl("status", mm(1.2), mm(0.8), pt(COLX + 11, -44, 0.4, abs_x=True), TEAL, rot=rot, verts=16)  # orange LED rechts neben der Ein/Aus-Taste


# Seitenlautsprecher in beiden Seitenwaenden (Treiber ca. 65 mm)
SPK_Y, SPK_Z = (19 if WINKEL == 60 else 10), 52

def holz_mat():
    # helles Kirsch-/Eschenfurnier wie beim RT 20, Maserung waagerecht
    m = bpy.data.materials.new("furnier")
    m.use_nodes = True
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    wv = N.new("ShaderNodeTexWave")
    wv.wave_type = "BANDS"; wv.bands_direction = "Z"
    wv.inputs["Scale"].default_value = 45
    wv.inputs["Distortion"].default_value = 9
    wv.inputs["Detail"].default_value = 3
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.25
    cr.color_ramp.elements[0].color = (0.50, 0.26, 0.11, 1)
    cr.color_ramp.elements[1].position = 0.85
    cr.color_ramp.elements[1].color = (0.60, 0.33, 0.14, 1)
    Lk.new(tc.outputs["Object"], wv.inputs["Vector"])
    Lk.new(wv.outputs["Fac"], cr.inputs["Fac"])
    Lk.new(cr.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.45
    return m

if holz:
    FURNIER = holz_mat()
    if mantel:
        bsdf = FURNIER.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Roughness"].default_value = 0.75
        wvn = [n for n in FURNIER.node_tree.nodes if n.type == "TEX_WAVE"][0]
        wvn.inputs["Distortion"].default_value = 3
        wvn.inputs["Scale"].default_value = 90
        crn = [n for n in FURNIER.node_tree.nodes if n.type == "VALTORGB"][0]
        crn.color_ramp.elements[0].color = (0.40, 0.23, 0.11, 1)
        crn.color_ramp.elements[1].color = (0.46, 0.27, 0.13, 1)
    for side in (-1, 1):
        # Furnierschicht = Gehaeuse geschnitten mit einer 1 mm duennen Scheibe an der Seite, leicht aufgedickt
        bpy.ops.mesh.primitive_cube_add(size=1, location=(side * (W / 2 - mm(0.5)), 0, mm(80)))
        f = bpy.context.active_object
        f.name = "furnier"
        f.scale = (mm(1.0), mm(300), mm(300))
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bi = f.modifiers.new("schnitt", "BOOLEAN"); bi.object = body; bi.operation = "INTERSECT"; bi.solver = "EXACT"
        bpy.ops.object.modifier_apply(modifier="schnitt")
        f.location.x += side * mm(0.6)
        f.data.materials.clear()
        put(f, FURNIER)
    if mantel:
        # Holzmantel wie beim RT 20: auch Oberseite und Rueckseite
        for name, loc, size, off in (("mantel_oben", (0, 0, mm(HOEHE) - mm(0.5)), (W + mm(2), mm(300), mm(1.0)), (0, 0, mm(0.6))),
                                     ("mantel_hinten", (0, mm(TIEFE / 2) - mm(0.5), mm(80)), (W + mm(2), mm(1.0), mm(300)), (0, mm(0.6), 0))):
            bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
            f = bpy.context.active_object
            f.name = name
            f.scale = size
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            bi = f.modifiers.new("schnitt", "BOOLEAN"); bi.object = body; bi.operation = "INTERSECT"; bi.solver = "EXACT"
            bpy.ops.object.modifier_apply(modifier="schnitt")
            f.location += Vector(off)
            f.data.materials.clear()
            put(f, FURNIER)

AUSSEN = W / 2 + (mm(1.1) if holz else 0)
for side in (-1, 1):
    if innen and side == -1:
        continue
    if schlitze:
        # Langloecher wie beim RT 20: waagerechte Schlitze im Kreis, in der Mitte geteilt
        R = 31.0
        for k in range(-6, 7):
            z = k * 4.6
            halb = math.sqrt(max(R * R - z * z, 0)) - 1.0
            if halb < 4:
                continue
            for seite in (-1, 1):
                laenge = halb - 2.0
                y = seite * (2.0 + laenge / 2)
                box("schlitz", (mm(1.0), mm(laenge), mm(2.0)), (side * AUSSEN, mm(SPK_Y + y), mm(SPK_Z + z)), HOLE, bevel=mm(0.9), seg=4)
    else:
        for iy in range(-8, 9):
            for iz in range(-8, 9):
                y, z = iy * 4.5, iz * 4.5
                if y * y + z * z <= 31 ** 2:
                    cyl("loch", mm(1.1), mm(0.8), (side * W / 2, mm(SPK_Y + y), mm(SPK_Z + z)), HOLE, rot=(0, math.pi / 2, 0), verts=14)

# Innenleben (Annahmen, nur bei durchsichtigem Gehaeuse sichtbar)
PCB = mat("pcb", (0.02, 0.025, 0.03), 0.5)
PIGREEN = mat("pi", (0.03, 0.3, 0.08), 0.5)
ALU = mat("alu", (0.55, 0.56, 0.58), 0.35, 0.9)
CELL = mat("zelle", (0.08, 0.2, 0.55), 0.4)
CONE = mat("kegel", (0.015, 0.015, 0.018), 0.7)
RIBBON = mat("band", (0.82, 0.82, 0.8), 0.6)
# vier 21700-Zellen im Tray unten
for k in range(4):
    cyl("zelle", mm(10.5), mm(70), (mm(-31.5 + k * 21), mm(10), mm(14)), CELL, rot=(math.pi / 2, 0, 0), verts=32)
box("tray", (mm(88), mm(76), mm(2)), (0, mm(10), mm(3.5)), PCB)
# UPS-HAT und Pi 5 (88 x 56 mm) mit Aktivkuehler
box("ups", (mm(88), mm(56), mm(2)), (0, mm(8), mm(29)), PCB, bevel=mm(1), seg=2)
box("pi", (mm(85), mm(56), mm(2)), (0, mm(8), mm(41)), PIGREEN, bevel=mm(1), seg=2)
box("kuehler", (mm(40), mm(40), mm(11)), (mm(-8), mm(8), mm(48)), ALU)
# Treiber links und rechts (FR 7 angenommen: 65 mm, ca. 25 mm tief)
for side in (-1, 1):
    cyl("korb", mm(33), mm(10), (side * mm(97), mm(SPK_Y), mm(SPK_Z)), PCB, rot=(0, math.pi / 2, 0), verts=48)
    cyl("kegel", mm(28), mm(8), (side * mm(100), mm(SPK_Y), mm(SPK_Z)), CONE, rot=(0, math.pi / 2, 0), verts=48)
    cyl("magnet", mm(13), mm(14), (side * mm(85), mm(SPK_Y), mm(SPK_Z)), ALU, rot=(0, math.pi / 2, 0), verts=32)
# Mikrofonplatine hinter der oberen Blende, Kernboard an der Rueckwand, Flachbandkabel
box("micpcb", (mm(115), mm(15), mm(1.6)), (mm(U0), mm((YF + SL * math.cos(_t) + TIEFE / 2) / 2), mm(TOPZ - 4)), PCB)
box("kern", (mm(80), mm(3), mm(60)), (0, mm(TIEFE / 2 - 8.5), mm(88)), PCB)
p1 = Vector((mm(U0), mm((YF + SL * math.cos(_t) + TIEFE / 2) / 2), mm(TOPZ - 5))); p2 = Vector((0, mm(TIEFE / 2 - 10.5), mm(95)))
d = p2 - p1
q = d.to_track_quat("Y", "Z")
box("band", (mm(24), d.length, mm(0.4)), (p1 + p2) / 2, RIBBON, rot=tuple(q.to_euler()))

# Rueckseite: Lueftung, Buchsen, Fuesse
back = mm(TIEFE / 2 + (1.1 if mantel else 0))
# Rueckseite (Rueckdeckel, weiss): Lueftung als Langloecher wie die Lautsprecher,
# unten Zuluft, oben Abluft (Kamineffekt fuer den Pi), dazu nur USB-C zum Laden
def lueftung(z0, reihen):
    for r in range(reihen):
        z = z0 + r * 4.6
        for seite in (-1, 1):
            box("lueftung", (mm(64), mm(1.0), mm(2.0)), (seite * mm(36), back + mm(0.3), mm(z)), HOLE, bevel=mm(0.9), seg=4)
lueftung(HOEHE - 32, 5)   # Abluft oben
lueftung(10, 2)           # Zuluft unten
box("usbc", (mm(9), mm(1.0), mm(3.4)), (mm(80), back + mm(0.2), mm(28)), BLACK, bevel=mm(1.2), seg=3)
for x in (-95, 95):
    for y in (-38, 38):
        cyl("fuss", mm(8), mm(3), (mm(x), mm(y), -mm(1.5)), RUBBER, verts=32)

bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -mm(3)))
put(bpy.context.active_object, FLOOR)

if innen:
    sol = body.modifiers.new("hohl", "SOLIDIFY")
    sol.thickness = mm(3)
    sol.offset = -1
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.5, 0, 0.1))
    cut = bpy.context.active_object
    cut.name = "schnitt"
    cut.scale = (1.0, 1.0, 0.6)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    cut.hide_render = True
    cut.hide_viewport = True
    bm = body.modifiers.new("schnitt", "BOOLEAN")
    bm.object = cut
    bm.operation = "DIFFERENCE"
    bm.solver = "EXACT"

world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.82, 0.85, 0.9, 1)
bg.inputs["Strength"].default_value = 0.18

target = bpy.data.objects.new("ziel", None)
bpy.context.collection.objects.link(target)

def light(name, loc, size, energy):
    l = bpy.data.lights.new(name, "AREA")
    l.shape = "SQUARE"
    l.size = size
    l.energy = energy
    o = bpy.data.objects.new(name, l)
    bpy.context.collection.objects.link(o)
    o.location = loc
    c = o.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"

light("key", (-0.5, -0.8, 0.7), 0.7, 28)
light("fill", (0.8, -0.5, 0.3), 0.8, 9)
light("rim", (0.15, 0.8, 0.6), 0.6, 14)

cam_data = bpy.data.cameras.new("kamera")
cam = bpy.data.objects.new("kamera", cam_data)
bpy.context.collection.objects.link(cam)
c = cam.constraints.new("TRACK_TO")
c.target = target
c.track_axis = "TRACK_NEGATIVE_Z"
c.up_axis = "UP_Y"
scene.camera = cam

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 24 if quick else 64
scene.cycles.use_denoising = True
scene.render.resolution_x = 960 if quick else 1280
scene.render.resolution_y = 720 if quick else 960
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = -0.2
scene.render.image_settings.file_format = "PNG"

mid = Vector((0, 0, mm(HOEHE / 2)))
VIEWS = {
    "iso": (-35, 24, 1.0, 55, mid),
    "front": (0, 30, 1.0, 55, mid),
    "side": (90, 3, 1.0, 55, mid),
    "back": (180, 12, 1.0, 55, mid),
    "top": (0, 84, 1.0, 55, mid),
    "detail": (-20, 32, 0.42, 85, Vector(pt(0, 50, 0))),
    "hinten": (155, 18, 1.0, 55, mid),
    "gitter": (-75, 12, 0.32, 85, Vector((-W / 2, mm(SPK_Y), mm(SPK_Z)))),
    "lippe": (-38, 14, 0.42, 85, Vector((mm(30), mm(-51.5), mm(22)))),
    "oben": (-25, 55, 0.5, 70, Vector((mm(20), mm(10), mm(110)))),
    "spalte": (25, 30, 0.36, 85, Vector(pt(COLX, 0, 4, abs_x=True))),
    "bedien": (20, 38, 0.30, 85, Vector(pt(COLX, -30, 4, abs_x=True))),
    "innen_iso": (-55, 26, 1.0, 55, mid),
    "innen_side": (-90, 6, 1.0, 55, mid),
    "innen_back": (-150, 18, 1.0, 55, mid),
}
for name in views:
    az, el, dist, lens, tgt = VIEWS[name]
    cam_data.lens = lens
    target.location = tgt
    a, e = math.radians(az), math.radians(el)
    cam.location = tgt + Vector((dist * math.cos(e) * math.sin(a), -dist * math.cos(e) * math.cos(a), dist * math.sin(e)))
    scene.render.filepath = os.path.join(OUT, f"entwurf_o_{name}{'' if WINKEL == 60 else f'_w{WINKEL}'}{'_8zoll' if acht else ''}{'_skala' if skala else ''}{'_mantel' if mantel else ('_holz' if holz else ('_schlitze' if schlitze else ''))}{'_weiss' if weiss else ''}{'_schwarzfront' if schwarzfront else ''}{'_grau' if grau else ''}{'_quick' if quick else ''}.png")
    bpy.ops.render.render(write_still=True)
    print("fertig:", scene.render.filepath)
