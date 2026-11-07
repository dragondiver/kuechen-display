"""Exportiert Entwurf O als docs/projekt/modell.js (GLB in Base64), aufgeteilt in Baugruppen.

Aufruf aus dem Repo:  blender -b -P werkzeuge/modell_exportieren.py
"""
import base64, sys, os, tempfile, bpy, bmesh, math
from mathutils import Vector
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUELLE = os.path.join(WURZEL, "gehaeuse", "blender", "entwurf_o.py")
ZIEL = os.path.join(WURZEL, "docs", "projekt", "modell.js")
GLB = os.path.join(tempfile.gettempdir(), "kuechen-display.glb")
sys.argv = ["blender", "--", "w75", "acht", "mantel", "skala"]
src = open(QUELLE).read().split('world = bpy.data.worlds.new("w")')[0]
g = {"__file__": QUELLE, "__name__": "__main__"}
exec(compile(src, QUELLE, "exec"), g)
body = g["body"]
# Hilfsobjekte und alte Bildschirm-Elemente entfernen; Modifikatoren anwenden
drop = []
for o in list(bpy.data.objects):
    n = o.name
    if n.startswith("t_") or n.startswith("kachel") or n.startswith("Sphere") or n.startswith("Plane") or n.startswith("zeiger_alt"):
        if o.type != "MESH" or n.startswith(("t_", "kachel", "Plane")) or (n.startswith("Sphere") and not o.hide_viewport):
            drop.append(o)
for o in drop:
    bpy.data.objects.remove(o, do_unlink=True)
# Gehaeuse: hohl machen, in Frontplatte und Rest teilen
sol = body.modifiers.new("hohl", "SOLIDIFY"); sol.thickness = 0.003; sol.offset = -1
dg = bpy.context.evaluated_depsgraph_get()
def bake(o):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear()
    o.data = me
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
for o in meshes:
    if o.hide_viewport:
        continue
    if o.modifiers:
        bake(o)
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.hide_viewport:
        bpy.data.objects.remove(o, do_unlink=True)
TH = g["TH"]; normal = g["normal"]; start = g["start"]
front = body.copy(); front.data = body.data.copy(); front.name = "front_platte"
bpy.context.collection.objects.link(front)
co = start - normal * 0.007
for ob, keep_outer in ((front, True), (body, False)):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=normal, clear_inner=keep_outer, clear_outer=not keep_outer)
    bm.to_mesh(ob.data); bm.free()
body.name = "schale"
def gruppe(o):
    n = o.name
    x = sum((o.matrix_world @ Vector(c)).x for c in o.bound_box) / 8
    seite = "l" if x < 0 else "r"
    if n.startswith("front_platte") or n.startswith(("kamera_", "lautstaerke", "ein_aus", "skala", "strich", "zeiger", "status")): return "front"
    if n.startswith(("glasrand",)): return "display"
    if n.startswith("screen"): return "screen"
    if n.startswith(("mikroleiste", "mikro", "micpcb")): return "mikro"
    if n.startswith(("kern", "band")): return "kern"
    if n.startswith(("pi", "kuehler")): return "pi"
    if n.startswith("ups"): return "ups"
    if n.startswith(("zelle", "tray")): return "akku"
    if n.startswith(("korb", "kegel", "magnet")): return "ls_" + seite
    if n.startswith(("furnier", "schlitz")): return "holz_" + seite
    if n.startswith("mantel_oben"): return "holz_oben"
    if n.startswith(("mantel_hinten", "lueftung", "usbc")): return "holz_hinten"
    if n.startswith(("schale", "fuss")): return "schale"
    return None
gr = {}
for o in list(bpy.data.objects):
    if o.type != "MESH": continue
    k = gruppe(o)
    if k is None:
        print("OHNE GRUPPE", o.name); bpy.data.objects.remove(o, do_unlink=True); continue
    gr.setdefault(k, []).append(o)
for k, obs in gr.items():
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1: bpy.ops.object.join()
    a = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    a.name = k
    a.data.name = k
    print("GRUPPE", k, len(a.data.vertices), "verts", len(a.data.polygons), "faces", [m.name if m else None for m in a.data.materials])
for o in list(bpy.data.objects):
    if o.type != "MESH":
        bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", use_selection=False, export_apply=False, export_yup=True, export_texcoords=False, export_normals=True, export_cameras=False, export_lights=False, export_animations=False, export_morph=False, export_skins=False)
# Als Skriptdatei, weil Artefakte kein .glb ausliefern und die Seite so überall gleich lädt.
with open(GLB, "rb") as ein, open(ZIEL, "w") as aus:
    aus.write('window.KD_MODELL="' + base64.b64encode(ein.read()).decode() + '";\n')
os.remove(GLB)
print("MODELL", os.path.getsize(ZIEL))
print("MASSE TH", math.degrees(TH), "W", g["W"], "HOEHE", g["HOEHE"], "AW", g["AW"], "AH", g["AH"])
