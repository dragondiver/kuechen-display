"""Entwurf E (Grundig-Stil, Variante von D): Keilgehaeuse, 10-Zoll-Touchdisplay mit 60 Grad Neigung, Pi im Gehaeuse,
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
views = [a for a in argv if a != "quick"] or ["iso", "front", "side", "detail"]
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

CREAM = mat("gehaeuse", (0.74, 0.71, 0.66), 0.45)
BLACK = mat("glas", (0.01, 0.012, 0.015), 0.12)
GRILLE = mat("gitter", (0.09, 0.095, 0.105), 0.8)
HOLE = mat("loch", (0.0, 0.0, 0.0), 1.0)
RUBBER = mat("gummi", (0.015, 0.015, 0.015), 0.9)
SCREEN = mat("screen", (0.02, 0.014, 0.009), 0.35, 0, (0.06, 0.034, 0.016), 1.0)
TEXT = mat("text", (1, 0.85, 0.6), 0.5, 0, (1.0, 0.82, 0.55), 6.0)
TEXT2 = mat("text2", (0.6, 0.5, 0.35), 0.5, 0, (0.7, 0.55, 0.35), 3.0)
TEAL = mat("teal", (0.1, 0.9, 0.7), 0.4, 0, (0.18, 0.9, 0.69), 14.0)
LENS = mat("linse", (0.02, 0.03, 0.06), 0.05, 0.3)
FLOOR = mat("boden", (0.32, 0.33, 0.35), 0.55)
SILVER = mat("silber", (0.6, 0.6, 0.62), 0.35, 0.9)

def wood_mat():
    m = bpy.data.materials.new("nussbaum")
    m.use_nodes = True
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    wv = N.new("ShaderNodeTexWave")
    wv.wave_type = "BANDS"
    wv.bands_direction = "Z"
    wv.inputs["Scale"].default_value = 170
    wv.inputs["Distortion"].default_value = 7
    wv.inputs["Detail"].default_value = 3
    wv.inputs["Detail Scale"].default_value = 1.3
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.2
    cr.color_ramp.elements[0].color = (0.06, 0.028, 0.014, 1)
    cr.color_ramp.elements[1].position = 0.8
    cr.color_ramp.elements[1].color = (0.20, 0.10, 0.045, 1)
    Lk.new(tc.outputs["Object"], wv.inputs["Vector"])
    Lk.new(wv.outputs["Fac"], cr.inputs["Fac"])
    Lk.new(cr.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.35
    try:
        b.inputs["Coat Weight"].default_value = 0.3
    except KeyError:
        pass
    return m

def cloth_mat():
    m = bpy.data.materials.new("stoff")
    m.use_nodes = True
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    ck = N.new("ShaderNodeTexChecker")
    ck.inputs["Scale"].default_value = 700
    ck.inputs["Color1"].default_value = (0.55, 0.43, 0.22, 1)
    ck.inputs["Color2"].default_value = (0.36, 0.27, 0.12, 1)
    bp = N.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.7
    bp.inputs["Distance"].default_value = 0.0006
    Lk.new(tc.outputs["Object"], ck.inputs["Vector"])
    Lk.new(ck.outputs["Color"], b.inputs["Base Color"])
    Lk.new(ck.outputs["Fac"], bp.inputs["Height"])
    Lk.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.95
    return m

WOOD = wood_mat()
CLOTH = cloth_mat()
BRASS = mat("messing", (0.78, 0.55, 0.22), 0.25, 1.0)
IVORY = mat("elfenbein", (0.78, 0.72, 0.58), 0.4)
TILES = [mat("t1", (0.14, 0.07, 0.015), 0.4, 0, (0.95, 0.5, 0.12), 0.35),
         mat("t2", (0.14, 0.015, 0.015), 0.4, 0, (0.95, 0.12, 0.1), 0.35),
         mat("t3", (0.02, 0.06, 0.14), 0.4, 0, (0.18, 0.45, 0.95), 0.35),
         mat("t4", (0.015, 0.1, 0.08), 0.4, 0, (0.14, 0.78, 0.6), 0.35)]

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
bv.width = mm(7)
bv.segments = 6
bpy.ops.object.shade_smooth()
put(body, WOOD)

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
box("rahmen", (mm(243), mm(167), mm(2)), pt(0, 0, 0.8), BRASS, bevel=mm(1), seg=3, rot=rot)
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

# Lautsprecherstoff mit Messingrahmen und Drehknopf an der Frontlippe
fy = mm(-62)
box("stoffrahmen", (mm(176), mm(1.0), mm(19)), (-mm(14), fy - mm(0.3), mm(12)), BRASS, bevel=mm(0.8), seg=2)
box("stoff", (mm(170), mm(1.2), mm(15)), (-mm(14), fy - mm(0.7), mm(12)), CLOTH)
cyl("knopf_ring", mm(11.5), mm(2), (mm(104), fy - mm(1), mm(12)), BRASS, rot=(math.pi / 2, 0, 0), verts=48)
cyl("knopf", mm(9.5), mm(9), (mm(104), fy - mm(5), mm(12)), IVORY, rot=(math.pi / 2, 0, 0), verts=48)
cyl("knopf_kappe", mm(6.5), mm(1.2), (mm(104), fy - mm(9.6), mm(12)), BRASS, rot=(math.pi / 2, 0, 0), verts=48)

# Rueckseite: Lueftung, Buchsen, Fuesse
back = mm(62)
for zz in (138, 147, 156):
    for i in range(10):
        box("schlitz", (mm(22), mm(1.0), mm(2.6)), ((i - 4.5) * mm(26), back + mm(0.2), mm(zz)), HOLE, bevel=mm(0.8), seg=2)
box("usbc", (mm(9), mm(1.0), mm(3.4)), (mm(70), back + mm(0.2), mm(22)), BLACK, bevel=mm(1.2), seg=3)
box("rj45", (mm(16), mm(1.0), mm(13)), (mm(45), back + mm(0.2), mm(26)), SILVER, bevel=mm(0.8), seg=2)
for x in (-100, 100):
    for y in (-48, 48):
        bpy.ops.mesh.primitive_cone_add(radius1=mm(4.6), radius2=mm(7.5), depth=mm(32), location=(mm(x), mm(y), -mm(16)), vertices=32)
        bpy.ops.object.shade_smooth()
        put(bpy.context.active_object, WOOD)
        cyl("kappe", mm(4.9), mm(2), (mm(x), mm(y), -mm(31)), BRASS, verts=32)

bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -mm(32)))
put(bpy.context.active_object, FLOOR)

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
}
for name in views:
    az, el, dist, lens, tgt = VIEWS[name]
    cam_data.lens = lens
    target.location = tgt
    a, e = math.radians(az), math.radians(el)
    cam.location = tgt + Vector((dist * math.cos(e) * math.sin(a), -dist * math.cos(e) * math.cos(a), dist * math.sin(e)))
    scene.render.filepath = os.path.join(OUT, f"entwurf_e_{name}{'_quick' if quick else ''}.png")
    bpy.ops.render.render(write_still=True)
    print("fertig:", scene.render.filepath)
