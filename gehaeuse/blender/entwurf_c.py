"""Entwurf C: kleiner Monitor mit aufgesetztem XVF3800-Puck.

Aufruf:  blender -b -P entwurf_c.py -- [quick] [ansicht ...]
Ansichten: iso front side back top   (ohne Angabe: alle)

Maße in Metern. Gesichert (Quelle CNX/Seeed): Puck 99 mm Durchmesser, 4 mm dick.
Angenommen (nicht geprüft): Gehäuse, Displaygröße (4,3 Zoll), Lage von Mikrofonen und LEDs,
Position der Buchsen.
"""
import bpy, sys, math, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
quick = "quick" in argv
views = [a for a in argv if a != "quick"] or ["iso", "front", "side", "back", "top"]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "renders")

mm = lambda v: v / 1000.0
W, H, D = mm(125), mm(100), mm(100)     # Gehäuse (angenommen)
PUCK_R, PUCK_T = mm(49.5), mm(4)        # gesichert: 99 mm x 4 mm

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

def put(obj, m):
    obj.data.materials.append(m)
    return obj

def box(name, size, loc, m, bevel=0.0, seg=6):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        bv = o.modifiers.new("bevel", "BEVEL")
        bv.width = bevel
        bv.segments = seg
    bpy.ops.object.shade_smooth()
    return put(o, m)

def cyl(name, r, depth, loc, m, rot=(0, 0, 0), verts=48):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.shade_smooth()
    return put(o, m)

CREAM = mat("gehaeuse", (0.74, 0.71, 0.66), 0.45)
BLACK = mat("glas", (0.01, 0.012, 0.015), 0.15)
DARK = mat("puck", (0.035, 0.038, 0.045), 0.45, 0.3)
GRILLE = mat("gitter", (0.09, 0.095, 0.105), 0.8)
HOLE = mat("loch", (0.0, 0.0, 0.0), 1.0)
RUBBER = mat("gummi", (0.015, 0.015, 0.015), 0.9)
SCREEN = mat("screen", (0.01, 0.02, 0.03), 0.25, 0, (0.03, 0.05, 0.08), 1.0)
TEXT = mat("text", (1, 1, 1), 0.5, 0, (0.95, 0.97, 1.0), 6.0)
TEXT2 = mat("text2", (0.5, 0.55, 0.6), 0.5, 0, (0.5, 0.56, 0.62), 3.0)
TEAL = mat("teal", (0.1, 0.9, 0.7), 0.4, 0, (0.18, 0.9, 0.69), 14.0)
TEAL_DIM = mat("teal_dim", (0.05, 0.3, 0.24), 0.4, 0, (0.1, 0.35, 0.27), 1.2)
FLOOR = mat("boden", (0.32, 0.33, 0.35), 0.55)

front = -D / 2

# Gehaeuse
box("gehaeuse", (W, D, H), (0, 0, 0), CREAM, bevel=mm(8), seg=8)

# Display (4,3 Zoll angenommen: sichtbar ca. 95 x 54 mm)
dz = mm(11)
box("rahmen", (mm(103), mm(1.2), mm(62)), (0, front - mm(0.4), dz), BLACK, bevel=mm(3), seg=4)
box("screen", (mm(95), mm(0.4), mm(54)), (0, front - mm(1.1), dz), SCREEN)

def label(body, size, loc, m, align="CENTER"):
    c = bpy.data.curves.new("t_" + body, "FONT")
    c.body = body
    c.size = size
    c.align_x = align
    o = bpy.data.objects.new("t_" + body, c)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (math.pi / 2, 0, 0)
    o.data.materials.append(m)
    return o

label("14:32", mm(20), (-mm(20), front - mm(1.5), dz - mm(2)), TEXT)
label("Wohnzimmer  21 C", mm(5.5), (-mm(20), front - mm(1.5), dz - mm(17)), TEXT2)
bpy.ops.mesh.primitive_torus_add(major_radius=mm(13), minor_radius=mm(1.1),
                                 location=(mm(30), front - mm(1.4), dz + mm(1)),
                                 rotation=(math.pi / 2, 0, 0), major_segments=64, minor_segments=12)
put(bpy.context.active_object, TEAL)
bpy.ops.mesh.primitive_uv_sphere_add(radius=mm(3), location=(mm(30), front - mm(1.4), dz + mm(1)), segments=24, ring_count=12)
put(bpy.context.active_object, TEAL)

# Lautsprechergitter
gz = mm(-33)
box("gitter", (mm(92), mm(1.0), mm(13)), (0, front - mm(0.3), gz), GRILLE, bevel=mm(2), seg=3)
for r in range(2):
    for i in range(44):
        x = (i - 21.5) * mm(2.0) + (mm(1.0) if r else 0)
        z = gz + (mm(2.6) if r else -mm(2.6))
        cyl("loch", mm(0.7), mm(0.6), (x, front - mm(0.8), z), HOLE, rot=(math.pi / 2, 0, 0), verts=10)

# Puck (XVF3800): 99 mm x 4 mm, sitzt mittig oben
pz = H / 2 + PUCK_T / 2
cyl("puck", PUCK_R, PUCK_T, (0, 0, pz), DARK, verts=96)
top = H / 2 + PUCK_T
for i in range(12):
    a = i / 12 * 2 * math.pi
    bpy.ops.mesh.primitive_uv_sphere_add(radius=mm(1.6), location=(math.cos(a) * mm(39), math.sin(a) * mm(39), top + mm(0.2)),
                                         segments=16, ring_count=8)
    put(bpy.context.active_object, TEAL if i < 3 else TEAL_DIM)
for k in range(4):
    a = math.pi / 4 + k * math.pi / 2
    cyl("mikro", mm(1.2), mm(0.4), (math.cos(a) * mm(27), math.sin(a) * mm(27), top), HOLE, verts=16)
cyl("mute", mm(4.5), mm(1.2), (0, 0, top + mm(0.4)), mat("mute", (0.1, 0.11, 0.12), 0.5, 0.2), verts=32)

# Rueckseite: USB-C, Fuesse
box("usb", (mm(9), mm(1.0), mm(3.4)), (0, D / 2 + mm(0.1), mm(-33)), BLACK, bevel=mm(1.2), seg=3)
for x in (-mm(50), mm(50)):
    for y in (-mm(38), mm(38)):
        cyl("fuss", mm(6), mm(3), (x, y, -H / 2 - mm(1.5)), RUBBER, verts=32)

# Boden und Licht
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -H / 2 - mm(3)))
put(bpy.context.active_object, FLOOR)

world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.82, 0.85, 0.9, 1)
bg.inputs["Strength"].default_value = 0.18

target = bpy.data.objects.new("ziel", None)
bpy.context.collection.objects.link(target)
target.location = (0, 0, mm(8))

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

light("key", (-0.35, -0.55, 0.45), 0.5, 14)
light("fill", (0.55, -0.35, 0.2), 0.6, 5)
light("rim", (0.1, 0.55, 0.4), 0.5, 8)

cam_data = bpy.data.cameras.new("kamera")
cam_data.lens = 70
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

VIEWS = {"iso": (-35, 24), "front": (0, 8), "side": (90, 8), "back": (180, 8), "top": (0, 84)}
dist = 0.55
for name in views:
    az, el = VIEWS[name]
    a, e = math.radians(az), math.radians(el)
    cam.location = Vector((dist * math.cos(e) * math.sin(a), -dist * math.cos(e) * math.cos(a), mm(8) + dist * math.sin(e)))
    scene.render.filepath = os.path.join(OUT, f"entwurf_c_{name}{'_quick' if quick else ''}.png")
    bpy.ops.render.render(write_still=True)
    print("fertig:", scene.render.filepath)
