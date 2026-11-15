# H2 "The week, in one object": one phone standing, and four thin glass panes dealt out of its screen towards the
# viewer and to the right, each carrying one real screen. Left to right as the camera sees it, the week runs:
# vote (on the phone) -> voted -> decided -> locked -> summary (nearest pane).
# Transparent film, soft floor shadow. Screens are emission seen only by the camera (colour-true); the soft shadows the
# panes throw on each other are rendered separately on catcher faces and multiplied in, so unshadowed greige stays exact.
# usage: blender -b -P hero_week.py -- [test]
import sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from phone import *

# ---------------- key choices ----------------
PHONE_SCREEN = "vote"
PANES     = ["voted", "decided", "locked", "summary"]     # nearest the phone first; the last is nearest the viewer
TURN0, TURN_STEP, TIP = 20.0, 5.0, 5.0                    # phone turned 20 deg; each pane 5 deg squarer to the camera: an even fan
STEP      = (0.058, -0.034)                               # each pane steps 58 mm to the right and 34 mm towards the viewer
PANE_T    = 0.0015                                        # glass thickness
W, H      = 2800, 1500
LENS      = 135.0
CAM       = dict(loc=(0.121, -1.42, 0.104), target=(0.121, -0.07, 0.072))
KEY       = dict(loc=(-0.60, -0.80, 0.75), size=0.70, power=6.9)     # the kit's key, upper left of camera
FACE_KEY  = dict(loc=(0.42, -1.25, 0.36), size=0.36, power=20.0)     # shadow pass only: a small light just right of the camera, so each pane shades a narrow band of the one behind
FILL      = dict(loc=(0.75, -0.95, 0.25), size=1.60, power=2.3)
TOP       = dict(loc=(0.05, -0.30, 1.20), size=1.20, power=2.6)
FLOOR     = dict(loc=(0.115, -0.30, 1.60), size=0.30, power=60.0, base=1.6)   # floor shadow light and its unshadowed partner
FACE_BASE = 7.5                                           # unshadowed light on the faces in the shadow pass: higher = lighter pane shadows
SAMPLES   = 900
# ---------------------------------------------

TEST = "test" in args()
HERE_ = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE_, "work"); os.makedirs(WORK, exist_ok=True)
sc = reset()
if TEST: W, H, SAMPLES = W // 2, H // 2, 160
cycles(sc, W, H, SAMPLES, view="Standard", look="None", exposure=0.0)
sc.cycles.use_denoising = False; sc.cycles.adaptive_threshold = 0.004; sc.cycles.adaptive_min_samples = 96; sc.cycles.filter_width = 1.2
sc.render.film_transparent = True; sc.render.dither_intensity = 0.0
sc.render.image_settings.color_mode = "RGBA"; sc.render.image_settings.color_depth = "8"
world_color(sc, (0, 0, 0), 0.0)

def mat_simple(name, base, rough, spec, metallic=0.0):
    m, nt, b, _ = new_mat(name); setin(b, "Base Color", (*base, 1)); setin(b, "Roughness", rough); setin(b, "Specular IOR Level", spec); setin(b, "Metallic", metallic); return m
m_case = mat_simple("case", srgb(CASE_HEX), 0.66, 0.22); m_bezel = mat_simple("bezel", (0.0028, 0.0026, 0.0024), 1.0, 0.0)
m_edge = mat_simple("glass_edge", (0.42, 0.46, 0.46), 0.18, 0.6)
m_white = mat_simple("catch", (0.8, 0.8, 0.8), 1.0, 0.0)
def screen_mat(name):
    m = bpy.data.materials.new("screen_" + name); m.use_nodes = True
    screen_nodes(m.node_tree, bpy.data.images.load(os.path.join(SCREENS, name + ".png")), camera_only=True); return m

def face_mesh(z):
    th = np.linspace(0, np.pi / 2, 25); pts = []
    for (sx, sy, off) in [(1, 1, 0), (-1, 1, np.pi / 2), (-1, -1, np.pi), (1, -1, 3 * np.pi / 2)]:
        a_ = th + off; pts += [(sx * (SW / 2 - R_SCREEN) + R_SCREEN * math.cos(t), sy * (SH / 2 - R_SCREEN) + R_SCREEN * math.sin(t), z) for t in a_]
    me = bpy.data.meshes.new("face"); me.from_pydata(pts, [], [tuple(range(len(pts)))]); me.update(); return me

real, catchers = [], []
def add(me, M, mats, catcher=False):
    ob = bpy.data.objects.new(me.name, me); sc.collection.objects.link(ob); ob.matrix_world = M
    for m_ in mats: me.materials.append(m_)
    (catchers if catcher else real).append(ob); return ob

Mp = stand_matrix(TURN0, TIP)
add(phone_mesh(), Mp, [m_case, m_bezel, screen_mat(PHONE_SCREEN)])
add(face_mesh(GZ + 0.00006), Mp, [m_white], catcher=True)
for i, name in enumerate(PANES, start=1):
    M = Matrix.Translation((STEP[0] * i, STEP[1] * i - 0.005, 0)) @ stand_matrix(TURN0 - TURN_STEP * i, TIP, thick=PANE_T, half_h=SH / 2)
    add(pane_mesh(PANE_T), M, [m_edge, screen_mat(name)])
    add(face_mesh(PANE_T + 0.00006), M, [m_white], catcher=True)

bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, 0)); ground = bpy.context.object
ground.data.materials.append(mat_simple("ground", (0.80, 0.78, 0.75), 1.0, 0.0)); ground.is_shadow_catcher = True

c_objs = bpy.data.collections.new("objects"); c_real = bpy.data.collections.new("real"); c_catch = bpy.data.collections.new("faces"); c_ground = bpy.data.collections.new("floor")
for o in real: c_objs.objects.link(o); c_real.objects.link(o); o.visible_diffuse = False
for o in catchers: c_objs.objects.link(o); c_catch.objects.link(o); o.is_shadow_catcher = True; o.visible_diffuse = False; o.visible_shadow = False
c_ground.objects.link(ground)
tgt = (0.09, -0.07, 0.075)
key = area_light(sc, "key", KEY["loc"], tgt, KEY["size"], KEY["power"], (1.0, 0.985, 0.96)); key.light_linking.receiver_collection = c_real
fk = area_light(sc, "face_key", FACE_KEY["loc"], tgt, FACE_KEY["size"], FACE_KEY["power"]); fk.light_linking.receiver_collection = c_catch
for nm, L_ in (("fill", FILL), ("top", TOP)):
    lo = area_light(sc, nm, L_["loc"], tgt, L_["size"], L_["power"], (1.0, 0.985, 0.96)); lo.light_linking.receiver_collection = c_real
fl = area_light(sc, "floor", FLOOR["loc"], (FLOOR["loc"][0], FLOOR["loc"][1] + 0.22, 0), FLOOR["size"], FLOOR["power"]); fl.light_linking.receiver_collection = c_ground
def flat_sun(name, strength, direction, coll):
    d = bpy.data.lights.new(name, "SUN"); o = bpy.data.objects.new(name, d); sc.collection.objects.link(o); d.energy = strength; d.angle = 0.02
    o.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
    o.light_linking.receiver_collection = coll; o.light_linking.blocker_collection = c_ground; return o   # nothing but the floor may block it
flat_sun("floor_base", FLOOR["base"], (0, 0, -1), c_ground)
flat_sun("face_base", FACE_BASE, (0.25, 1.0, -0.15), c_catch)

cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
cd.lens = LENS; cd.sensor_width = 36.0; cd.dof.use_dof = False; cd.clip_start = 0.05; cd.clip_end = 20
cam.location = CAM["loc"]; cam.rotation_euler = (Vector(CAM["target"]) - Vector(CAM["loc"])).to_track_quat("-Z", "Y").to_euler()

def render_to(path):
    t = time.time(); sc.render.filepath = path; bpy.ops.render.render(write_still=True); return time.time() - t
tag = "_test" if TEST else ""
# pass A: the picture (catcher faces away)
for o in catchers: o.hide_render = True
tA = render_to(os.path.join(WORK, "week_A%s.png" % tag))
ground.visible_camera = False
tA2 = render_to(os.path.join(WORK, "week_A_noshadow%s.png" % tag))
# pass B: only the shadows that fall on the faces
for o in catchers: o.hide_render = False
for o in real: o.visible_camera = False
sc.cycles.samples = SAMPLES * 2
tB = render_to(os.path.join(WORK, "week_B%s.png" % tag))
print("RENDERED A %.1fs A2 %.1fs B %.1fs" % (tA, tA2, tB))
B = load_px(os.path.join(WORK, "week_B%s.png" % tag)); s = B[..., 3:4]
print("face shadow: max %.3f, share of frame over 0.02: %.3f" % (float(s.max()), float((s > 0.02).mean())))
outdir = WORK if TEST else HERE_
for src, dst in (("week_A%s.png" % tag, "hero_week.png"), ("week_A_noshadow%s.png" % tag, "hero_week_noshadow.png")):
    A = load_px(os.path.join(WORK, src)); out = A.copy(); out[..., :3] = A[..., :3] * (1 - s)
    # multiply in display space would crush colour; do it in linear light
    lin_ = np.where(A[..., :3] <= 0.04045, A[..., :3] / 12.92, ((A[..., :3] + 0.055) / 1.055) ** 2.4) * (1 - s)
    out[..., :3] = np.where(lin_ <= 0.0031308, lin_ * 12.92, 1.055 * np.power(np.maximum(lin_, 0), 1 / 2.4) - 0.055)
    out[..., :3] = np.where(s > 0, out[..., :3], A[..., :3])      # untouched pixels stay bit-exact
    save_px(out, os.path.join(outdir, dst))
    al = out[..., 3]; print(dst, "edge alpha max (0-255): top %.0f bottom %.0f left %.0f right %.0f" % (al[0].max() * 255, al[-1].max() * 255, al[:, 0].max() * 255, al[:, -1].max() * 255))
if not TEST: bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE_, "hero_week.blend"))
print("DONE")
