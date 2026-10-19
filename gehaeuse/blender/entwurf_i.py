"""Entwurf I (Braun/Rams-Stil, Lippe 24 mm wie F, Seitenlautsprecher wie H): Keilgehaeuse, 10-Zoll-Touchdisplay mit 60 Grad Neigung, Pi im Gehaeuse,
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
views = [a for a in argv if a not in ("quick", "innen")] or (["innen_iso", "innen_side", "innen_back"] if innen else ["iso", "front", "side"])
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
W = mm(252)
prof = [(-62, 0), (-62, 24), (22, 169.5), (62, 169.5), (62, 0)]
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
bv = body.modifiers.new("bevel", "BEVEL")
bv.width = mm(3)
bv.segments = 3
bpy.ops.object.shade_smooth()
put(body, CREAM)

# Frontpanel an der 60-Grad-Flaeche
TH = math.radians(60)
slope = Vector((0, math.cos(TH), math.sin(TH)))
normal = Vector((0, -math.sin(TH), math.cos(TH)))
start = Vector((0, mm(-62), mm(24)))
center = start + slope * mm(3 + 81)
def pt(u, v, nn=0.0):
    p = center + Vector((mm(u), 0, 0)) + slope * mm(v) + normal * mm(nn)
    return (p.x, p.y, p.z)
rot = (TH, 0, 0)

box("panel", (mm(238), mm(162), mm(3)), pt(0, 0, 1.5), BLACK, bevel=mm(2), seg=4, rot=rot)
box("screen", (mm(217), mm(136), mm(0.4)), pt(0, -5, 3.2), SCREEN, rot=rot)

def label(body_text, size, u, v, m, align="CENTER", nn=3.6):
    c = bpy.data.curves.new("t_" + body_text, "FONT")
    c.body = body_text
    c.size = mm(size)
    c.align_x = align
    o = bpy.data.objects.new("t_" + body_text, c)
    bpy.context.collection.objects.link(o)
    o.location = pt(u, v, nn)
    o.rotation_euler = rot
    o.data.materials.append(m)
    return o

label("14:32", 26, -100, 28, TEXT, "LEFT")
label("Samstag, 4. Oktober", 6.5, -100, 14, TEXT2, "LEFT")
names = ["Rezepte", "YouTube", "Browser", "Eigene Apps"]
for i, u in enumerate((-78, -26, 26, 78)):
    box("kachel", (mm(46), mm(40), mm(0.6)), pt(u, -32, 3.5), TILES[i], bevel=mm(3), seg=4, rot=rot)
    label(names[i], 6.2, u, -35, TEXT, nn=4.3)
bpy.ops.mesh.primitive_uv_sphere_add(radius=mm(2.2), location=pt(95, 52, 4), segments=20, ring_count=10)
put(bpy.context.active_object, TEAL)

# obere Blende: Mikrofonleiste (4 Ports, 33 mm Abstand) und optionale Kamera
for u in (-49.5, -16.5, 16.5, 49.5):
    cyl("mikro", mm(1.7), mm(0.8), pt(u, 72, 3.1), HOLE, rot=rot, verts=16)
cyl("kamera_ring", mm(5), mm(1.2), pt(0, 72, 3.2), SILVER, rot=rot, verts=32)
cyl("kamera_linse", mm(3.6), mm(1.6), pt(0, 72, 3.5), LENS, rot=rot, verts=32)
cyl("kamera_led", mm(1.0), mm(0.8), pt(34, 72, 3.2), TEAL, rot=rot, verts=12)

# Lautsprecher: regelmaessiges Lochraster (Braun-Art) und oranger Drehknopf
fy = mm(-62)
cyl("knopf", mm(8), mm(10), (mm(104), fy - mm(4), mm(12)), ORANGE, rot=(math.pi / 2, 0, 0), verts=64)
box("marke", (mm(1.2), mm(0.6), mm(5)), (mm(104), fy - mm(9.2), mm(15.5)), WHITE)


# Seitenlautsprecher: kreisfoermiges Lochraster in beiden Seitenwaenden (Treiber ca. 65 mm)
SPK_Y, SPK_Z = 10, 62
for side in (-1, 1):
    if innen and side == -1:
        continue
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
    cyl("zelle", mm(10.5), mm(70), (mm(-31.5 + k * 21), mm(10), mm(11)), CELL, rot=(math.pi / 2, 0, 0), verts=32)
box("tray", (mm(88), mm(76), mm(2)), (0, mm(10), mm(0.5)), PCB)
# UPS-HAT und Pi 5 (88 x 56 mm) mit Aktivkuehler
box("ups", (mm(88), mm(56), mm(2)), (0, mm(8), mm(26)), PCB, bevel=mm(1), seg=2)
box("pi", (mm(85), mm(56), mm(2)), (0, mm(8), mm(38)), PIGREEN, bevel=mm(1), seg=2)
box("kuehler", (mm(40), mm(40), mm(11)), (mm(-8), mm(8), mm(45)), ALU)
# Treiber links und rechts (FR 7 angenommen: 65 mm, ca. 25 mm tief)
for side in (-1, 1):
    cyl("korb", mm(33), mm(10), (side * mm(108), mm(SPK_Y), mm(SPK_Z)), PCB, rot=(0, math.pi / 2, 0), verts=48)
    cyl("kegel", mm(28), mm(8), (side * mm(111), mm(SPK_Y), mm(SPK_Z)), CONE, rot=(0, math.pi / 2, 0), verts=48)
    cyl("magnet", mm(13), mm(14), (side * mm(96), mm(SPK_Y), mm(SPK_Z)), ALU, rot=(0, math.pi / 2, 0), verts=32)
# Mikrofonplatine hinter der oberen Blende, Kernboard an der Rueckwand, Flachbandkabel
box("micpcb", (mm(115), mm(15), mm(1.6)), pt(0, 72, -1.2), PCB, rot=rot)
box("kern", (mm(80), mm(3), mm(60)), (0, mm(56), mm(125)), PCB)
p1 = Vector(pt(0, 70, -2.5)); p2 = Vector((0, mm(54), mm(135)))
d = p2 - p1
q = d.to_track_quat("Y", "Z")
box("band", (mm(24), d.length, mm(0.4)), (p1 + p2) / 2, RIBBON, rot=tuple(q.to_euler()))

# Rueckseite: Lueftung, Buchsen, Fuesse
back = mm(62)
for zz in (140, 148, 156):
    for i in range(14):
        cyl("loch", mm(1.7), mm(1.0), ((i - 6.5) * mm(8), back + mm(0.3), mm(zz)), HOLE, rot=(math.pi / 2, 0, 0), verts=14)
box("usbc", (mm(9), mm(1.0), mm(3.4)), (mm(70), back + mm(0.2), mm(22)), BLACK, bevel=mm(1.2), seg=3)
box("rj45", (mm(16), mm(1.0), mm(13)), (mm(45), back + mm(0.2), mm(26)), SILVER, bevel=mm(0.8), seg=2)
for x in (-105, 105):
    for y in (-45, 45):
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

mid = Vector((0, 0, mm(85)))
VIEWS = {
    "iso": (-35, 24, 1.0, 55, mid),
    "front": (0, 30, 1.0, 55, mid),
    "side": (90, 3, 1.0, 55, mid),
    "back": (180, 12, 1.0, 55, mid),
    "top": (0, 84, 1.0, 55, mid),
    "detail": (-20, 32, 0.42, 85, Vector(pt(0, 60, 0))),
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
    scene.render.filepath = os.path.join(OUT, f"entwurf_i_{name}{'_quick' if quick else ''}.png")
    bpy.ops.render.render(write_still=True)
    print("fertig:", scene.render.filepath)
