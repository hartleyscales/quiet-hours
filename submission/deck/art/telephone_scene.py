# telephone_scene.py: a 1980s desk telephone on a table, seen from the side at table height. Built from nothing, here.
#   blender -b -P telephone_scene.py -- out.png [azimuth_deg] [elevation_deg]
import bpy, bmesh, math, sys
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]; AZ = float(argv[1]) if len(argv) > 1 else 62.0; EL = float(argv[2]) if len(argv) > 2 else 9.0
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 96; sc.cycles.use_denoising = True
try:
    p = bpy.context.preferences.addons["cycles"].preferences; p.compute_device_type = "METAL"; p.get_devices()
    for d in p.devices: d.use = True
    sc.cycles.device = "GPU"
except Exception as e: print("cpu", e)
sc.render.resolution_x, sc.render.resolution_y = 1560, 1200
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
sc.render.film_transparent = True; sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"; sc.render.filepath = OUT

def mat(name, col, rough=0.55):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough
    return m
BODY = mat("body", (0.012, 0.012, 0.012), 0.32); KEY = mat("key", (0.8, 0.79, 0.77), 0.45); CORD = mat("cord", (0.012, 0.012, 0.012), 0.38)
TABLE = mat("table", (0.93, 0.92, 0.90), 0.9)

def finish(o, m, bevel=0.5, seg=4, smooth=True):
    o.data.materials.append(m)
    if bevel:
        b = o.modifiers.new("b", "BEVEL"); b.width = bevel; b.segments = seg; b.limit_method = "ANGLE"
    if smooth:
        for poly in o.data.polygons: poly.use_smooth = True
    return o
def box(name, verts, m, bevel=0.5):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in ((0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)): bm.faces.new([vs[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); return finish(o, m, bevel)
def cube(name, loc, size, m, bevel=0.4, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot); o = bpy.context.object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(scale=True); return finish(o, m, bevel)

# x: the phone's width (handset runs along it), y: depth (front at -y), z: up. Centimetres.
W, D = 21.0, 22.0; HB, HF = 9.0, 3.6          # height at the back and at the front lip
w, d = W / 2, D / 2
base = box("base", [(-w,-d,0),(w,-d,0),(w,d,0),(-w,d,0), (-w,-d,HF),(w,-d,HF),(w,d,HB),(-w,d,HB)], BODY, 1.1)
slope = math.atan2(HB - HF, D)
def on_slope(x, y, lift=0.0):
    z = HF + (y + d) / D * (HB - HF); return Vector((x, y - math.sin(slope) * lift, z + math.cos(slope) * lift))
for r in range(4):
    for c in range(3):
        cube("key", on_slope(-4.6 + c * 4.6, -6.6 + r * 3.5, 0.35), (3.3, 2.4, 0.9), KEY, 0.35, (slope, 0, 0))
# the cradle at the back, two ears, and the handset lying in it
cy = d - 3.6; cz = on_slope(0, cy).z
cube("cradle", (0, cy, cz + 0.6), (W - 1.0, 6.4, 2.6), BODY, 0.9)
for sx in (-1, 1):
    cube("ear", (sx * 6.2, cy, cz + 2.6), (2.2, 6.0, 2.6), BODY, 0.8)
hz = cz + 5.3
for sx in (-1, 1):
    bpy.ops.mesh.primitive_cylinder_add(radius=3.1, depth=3.0, vertices=64, location=(sx * 9.6, cy, hz - 0.6)); finish(bpy.context.object, BODY, 0.9)
cube("grip", (0, cy, hz + 1.7), (21.0, 3.6, 2.0), BODY, 0.95)
for sx in (-1, 1):
    cube("neck", (sx * 9.2, cy, hz + 0.7), (4.4, 3.8, 2.2), BODY, 1.0)
# the coiled cord: out of the handset's left end, down to the table, round to the side of the base
path = [Vector((-13.0, cy, hz - 1.6)), Vector((-17.5, cy - 1.0, hz - 6.5)), Vector((-19.5, cy - 4.0, 1.9)), Vector((-17.5, cy - 9.5, 1.5)), Vector((-13.0, cy - 12.5, 1.5)), Vector((-w, cy - 13.0, 1.6))]
def bez(t):
    pts = path[:]
    while len(pts) > 1: pts = [a.lerp(b, t) for a, b in zip(pts, pts[1:])]
    return pts[0]
cu = bpy.data.curves.new("cord", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.21; cu.bevel_resolution = 4
sp = cu.splines.new("POLY"); N, TURNS, R = 1400, 64, 0.78
sp.points.add(N - 1)
for i in range(N):
    t = i / (N - 1); c = bez(t); tan = (bez(min(1, t + 0.002)) - bez(max(0, t - 0.002))).normalized()
    u = tan.cross(Vector((0, 0, 1))); u = u.normalized() if u.length > 1e-4 else Vector((1, 0, 0)); v = tan.cross(u).normalized()
    a = t * TURNS * 2 * math.pi; q = c + (u * math.cos(a) + v * math.sin(a)) * R
    sp.points[i].co = (q.x, q.y, q.z, 1)
co = bpy.data.objects.new("cord", cu); sc.collection.objects.link(co); co.data.materials.append(CORD)
# the table, and light from the upper left as the app draws it
bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, 0)); bpy.context.object.data.materials.append(TABLE); bpy.context.object.is_shadow_catcher = True
wd = bpy.data.worlds.new("w"); sc.world = wd; wd.use_nodes = True; wd.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1); wd.node_tree.nodes["Background"].inputs[1].default_value = 0.5
def area(loc, energy, size):
    bpy.ops.object.light_add(type="AREA", location=loc); L = bpy.context.object; L.data.energy = energy; L.data.size = size
    L.rotation_euler = (Vector((0, 0, 4)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); return L
az = math.radians(AZ); el = math.radians(EL)
cam_dir = Vector((-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))   # from the target toward the camera
right = Vector((0, 0, 1)).cross(cam_dir).normalized()
area(Vector((0, 0, 4)) - cam_dir * 12 - right * 46 + Vector((0, 0, 80)), 150000, 60)
area(Vector((0, 0, 4)) + cam_dir * 60 + right * 30 + Vector((0, 0, 10)), 5000, 60)
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 50
tgt = Vector((-2.5, 0, 6.2)); cam.location = tgt + cam_dir * 200
cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.ops.render.render(write_still=True)
