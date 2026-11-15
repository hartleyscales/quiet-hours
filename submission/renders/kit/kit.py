# Quiet Hours deck kit: clean product renders of the phone with the app's real screens, on transparent film.
# Everything is built here; the screen is the real screenshot as emission, seen only by the camera, so it is colour-true.
# usage: blender -b -P kit.py -- "<angle>:<screen>,<screen>;<angle>:<screen>" [test]
#   e.g.  blender -b -P kit.py -- "a:signin,vote"        (writes phone_<screen>_<angle>.png and ..._noshadow.png)
import sys, os, json, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from phone import *
from mathutils import Matrix, Vector

# ---------------- key choices ----------------
CASE      = CASE_HEX                  # quiet brown clay, matte (set in phone.py)
CASE_GAIN = 0.84                      # albedo trim so the lit case measures close to CASE under Standard
FRAME     = 3000                      # square frame before the crop; phone comes out about 2,050 px tall
LENS, SENSOR_H = 100.0, 24.0          # long lens for every angle
# Studio light, the same for every angle. These three light the phone only (light linking), so they throw no shadow on the floor:
KEY       = dict(loc=(-0.60, -0.80, 0.75), size=0.70, power=6.9)    # one gentle key, upper left of camera
FILL      = dict(loc=(0.75, -0.95, 0.25), size=1.60, power=2.3)      # broad soft fill from the right
TOP       = dict(loc=(0.0, -0.25, 1.20), size=1.20, power=2.6)       # soft top light
# The floor is lit by one light of its own, so the contact shadow is compact and falls to exactly zero around it:
SHADOW    = {"stand": dict(loc=(0.03, -0.16, 0.90), size=0.24, power=20.0), "flat": dict(loc=(-0.22, 0.16, 0.90), size=0.42, power=20.0)}
SHADOW_BASE = 1.6                     # an unshadowed floor light beside it: sets how dark the shadow can get (higher = lighter shadow)
ANGLES = {
    # turn: degrees about the vertical (+ = screen faces the viewer's right, its left edge shows); tip: degrees back
    "a":    dict(mode="stand", turn=24.0,  tip=5.0, cam=(0.0, -0.90, 0.108), target=(0.0, 0.0, 0.074)),
    "b":    dict(mode="stand", turn=-24.0, tip=5.0, cam=(0.0, -0.90, 0.108), target=(0.0, 0.0, 0.074)),
    "c":    dict(mode="stand", turn=40.0,  tip=4.0, cam=(0.0, -0.90, 0.030), target=(0.0, 0.0, 0.077)),
    "flat": dict(mode="flat",  turn=14.0,  tip=0.0, cam=(0.0, -0.9 * math.cos(math.radians(55)), 0.9 * math.sin(math.radians(55))), target=(0.0, 0.0, 0.004)),
}
SAMPLES   = 900
MARGIN_PX = 40                        # even margin around the content, in final pixels
# ---------------------------------------------

a = args(); jobs = a[0] if a else "a:signin"; TEST = len(a) > 1 and a[1] == "test"
if TEST: FRAME = 1200; MARGIN_PX = 16
HERE_ = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE_, "work"); os.makedirs(WORK, exist_ok=True)
sc = reset()
cycles(sc, FRAME, FRAME, 96 if TEST else SAMPLES, view="Standard", look="None", exposure=0.0)
sc.cycles.use_denoising = False                 # no denoiser: nothing touches the text or the alpha
sc.cycles.adaptive_threshold = 0.004; sc.cycles.adaptive_min_samples = 96; sc.cycles.filter_width = 1.2
sc.render.film_transparent = True
sc.render.image_settings.color_mode = "RGBA"; sc.render.image_settings.color_depth = "8"; sc.render.image_settings.compression = 40
sc.render.dither_intensity = 0.0
world_color(sc, (0, 0, 0), 0.0)

rig = bpy.data.objects.new("rig", None); sc.collection.objects.link(rig)
phone = bpy.data.objects.new("phone", phone_mesh()); sc.collection.objects.link(phone); phone.parent = rig

mc, ntc, bc, _ = new_mat("case")
setin(bc, "Base Color", (*(np.array(srgb(CASE)) * CASE_GAIN), 1)); setin(bc, "Roughness", 0.66); setin(bc, "Specular IOR Level", 0.22)
mb, ntb, bb, _ = new_mat("bezel"); setin(bb, "Base Color", (0.0028, 0.0026, 0.0024, 1)); setin(bb, "Roughness", 1.0); setin(bb, "Specular IOR Level", 0.0)
ms = bpy.data.materials.new("screen"); ms.use_nodes = True
tex = screen_nodes(ms.node_tree, None, camera_only=True)
for m_ in (mc, mb, ms): phone.data.materials.append(m_)

# ground: catches the shadow, bounces a little light, never seen itself
bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, 0)); ground = bpy.context.object
mgr, _, bgr, _ = new_mat("ground"); setin(bgr, "Base Color", (0.80, 0.78, 0.75, 1)); setin(bgr, "Roughness", 1.0); setin(bgr, "Specular IOR Level", 0.0)
ground.data.materials.append(mgr); ground.is_shadow_catcher = True

phone_coll = bpy.data.collections.new("phone_only"); ground_coll = bpy.data.collections.new("ground_only")
for o in sc.collection.objects:
    if o.parent == rig:
        phone_coll.objects.link(o); o.visible_diffuse = False      # the floor sees the phone's shadow, never its bounced light: a clean alpha
ground_coll.objects.link(ground)
for nm, L_ in (("key", KEY), ("fill", FILL), ("top", TOP)):
    lo = area_light(sc, nm, L_["loc"], (0, 0, 0.075), L_["size"], L_["power"], (1.0, 0.985, 0.96))
    lo.light_linking.receiver_collection = phone_coll
shadow_light = area_light(sc, "shadow", (0, 0, 1), (0, 0, 0), 0.2, 20.0)
shadow_light.light_linking.receiver_collection = ground_coll
base_d = bpy.data.lights.new("shadow_base", "SUN"); base_l = bpy.data.objects.new("shadow_base", base_d); sc.collection.objects.link(base_l)
base_d.energy = SHADOW_BASE; base_d.angle = 0.02
base_l.light_linking.receiver_collection = ground_coll; base_l.light_linking.blocker_collection = ground_coll   # nothing but the floor may block it

cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
cd.lens = LENS; cd.sensor_fit = "VERTICAL"; cd.sensor_height = SENSOR_H; cd.dof.use_dof = False; cd.clip_start = 0.05; cd.clip_end = 20

def pose(A):
    if A["mode"] == "stand":
        # stand it up (screen towards the camera), tip it back about its foot, then turn it about its own vertical axis
        M = Matrix.Rotation(math.radians(A["turn"]), 4, "Z") @ Matrix.Translation((0, HC / 2, 0)) @ \
            Matrix.Rotation(math.radians(-A["tip"]), 4, "X") @ Matrix.Translation((0, 0, HY)) @ Matrix.Rotation(math.radians(90), 4, "X")
    else:
        M = Matrix.Rotation(math.radians(A["turn"]), 4, "Z")
    rig.matrix_world = M
    S_ = SHADOW[A["mode"]]; shadow_light.location = S_["loc"]; shadow_light.data.size = S_["size"]; shadow_light.data.energy = S_["power"]
    shadow_light.rotation_euler = (Vector((0, 0, 0)) - Vector(S_["loc"])).to_track_quat("-Z", "Y").to_euler()
    cam.location = A["cam"]; cam.rotation_euler = (Vector(A["target"]) - Vector(A["cam"])).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()

def render_to(path):
    t = time.time(); sc.render.filepath = path; bpy.ops.render.render(write_still=True); return time.time() - t

def crop_for(angle):
    """Same crop box for every file of one angle: the alpha bounding box of a quick shadowed pass, plus an even margin."""
    cf = os.path.join(WORK, "crop_%s_%d.json" % (angle, FRAME))
    if os.path.exists(cf) and "--recrop" not in a:
        return json.load(open(cf))
    sc.render.use_border = False; sc.render.resolution_percentage = 25; spp = sc.cycles.samples; sc.cycles.samples = 200
    ground.visible_camera = True
    render_to(os.path.join(WORK, "pre_%s.png" % angle))
    sc.render.resolution_percentage = 100; sc.cycles.samples = spp
    al = load_px(os.path.join(WORK, "pre_%s.png" % angle))[..., 3]; h, w = al.shape
    al[:3] = 0; al[-3:] = 0; al[:, :3] = 0; al[:, -3:] = 0          # ignore the frame's own rim
    ys, xs = np.nonzero(al > 0.006); k = FRAME / w
    x0, x1, y0, y1 = xs.min() * k - MARGIN_PX, (xs.max() + 1) * k + MARGIN_PX, ys.min() * k - MARGIN_PX, (ys.max() + 1) * k + MARGIN_PX
    box = dict(x0=int(max(0, round(x0))), x1=int(min(FRAME, round(x1))), y0=int(max(0, round(y0))), y1=int(min(FRAME, round(y1))))
    if box["x0"] == 0 or box["y0"] == 0 or box["x1"] == FRAME or box["y1"] == FRAME: print("WARNING content touches the frame", angle, box)
    json.dump(box, open(cf, "w")); return box

for job in jobs.split(";"):
    angle, screens = job.split(":"); A = ANGLES[angle]; pose(A)
    box = crop_for(angle)
    sc.render.use_border = True; sc.render.use_crop_to_border = True
    sc.render.border_min_x = box["x0"] / FRAME; sc.render.border_max_x = box["x1"] / FRAME
    sc.render.border_min_y = 1 - box["y1"] / FRAME; sc.render.border_max_y = 1 - box["y0"] / FRAME
    print("CROP", angle, box, "->", box["x1"] - box["x0"], "x", box["y1"] - box["y0"])
    for s in screens.split(","):
        img = bpy.data.images.load(os.path.join(SCREENS, s + ".png"), check_existing=False)
        tex.image = img
        outdir = WORK if TEST else HERE_
        ground.visible_camera = True
        t1 = render_to(os.path.join(outdir, "phone_%s_%s.png" % (s, angle)))
        ground.visible_camera = False
        t2 = render_to(os.path.join(outdir, "phone_%s_%s_noshadow.png" % (s, angle)))
        print("KIT %s %s shadow %.1fs noshadow %.1fs" % (s, angle, t1, t2))
if not TEST:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE_, "kit.blend"))
print("DONE")
