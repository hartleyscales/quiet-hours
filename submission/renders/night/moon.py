# moon.png: the app's 3,098-dot moon alone, as beads hanging in the dark. Right half of the frame; the left half is left for the title.
# usage: blender -b -P moon.py -- <draft|final> [wide]
#   default : stars only right of centre, so the whole left half is exactly the background   -> moon.png
#   wide    : the same stars plus the rest of the field across the whole frame                -> moon_wide_stars.png
import sys, os
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from night_common import *
from bpy_extras.object_utils import world_to_camera_view

# ---------------- key choices ----------------
LENS     = 100.0
DIST     = 10.0
MOON_UV  = (0.75, 0.50)     # centre of the right half
MOON_H   = 0.75             # diameter as a fraction of frame height
BULGE    = 0.22             # the disc is a shallow dome toward the camera (fraction of its radius); dot positions on screen stay exact
GLOW     = 0.24             # each bead's own faint light
KEY      = dict(off=(-1.55, -2.0, 1.55), size=1.3, power=140.0, color=(1.0, 0.93, 0.84))   # one soft warm key, upper left, in front
LIMB_BLUR = 1.0             # px of defocus (at 2560 wide) at the far limb
N_STARS  = 64
STAR_BLUR = (8.0, 17.0)     # px of defocus on the stars
STAR_GLOW = (1.3, 3.2)
# ---------------------------------------------

a = args(); q = a[0] if a else "draft"; wide = len(a) > 1 and a[1] == "wide"
W, H, SPP = (1280, 720, 192) if q == "draft" else (2560, 1440, 768)
sc = reset(); cycles(sc, W, H, SPP, thresh=0.02 if q == "draft" else 0.005); world_bg(sc)
rng = np.random.default_rng(3098)

right = np.array([1.0, 0, 0]); up = np.array([0, 0, 1.0]); fwd = np.array([0, 1.0, 0])
C = -fwd * DIST
Wd = 36.0 / LENS; Hd = Wd * 9 / 16
def at_depth(u, v, depth): return C + depth * (fwd + (u - 0.5) * Wd * right + (0.5 - v) * Hd * up)

moon_c = at_depth(*MOON_UV, DIST); Rm = 0.5 * MOON_H * DIST * Hd
xy, mcol, flag, pitch = load_moon()
BR = 0.333 * pitch * Rm
flat = moon_c + Rm * (xy[:, :1] * right + xy[:, 1:] * up)
rho2 = np.clip((xy ** 2).sum(1), 0, 1)
dz = BULGE * Rm * np.sqrt(1 - rho2)                                  # toward the camera
pos = C + (flat - C) * ((DIST - dz) / DIST)[:, None]                 # slid along the camera ray: the layout on screen is unchanged
rad = BR * (DIST - dz) / DIST                                        # and so is each dot's size
tv, tf = tmpl_sphere(24, 12)
moon = tile(sc, "moon", tv, tf, pos, rad, mcol)
moon.data.materials.append(glow_mat("bead", GLOW, limb=0.5, surface=dict(rough=0.34, spec=0.5, coat=0.35, coat_rough=0.2)))

# key light
ld = bpy.data.lights.new("key", "AREA"); key = bpy.data.objects.new("key", ld); sc.collection.objects.link(key)
kp = moon_c + Rm / 0.76 * np.array(KEY["off"]); key.location = kp
key.rotation_euler = (Vector(moon_c) - Vector(kp)).to_track_quat("-Z", "Y").to_euler()
ld.shape = "DISK"; ld.size = KEY["size"]; ld.energy = KEY["power"]; ld.color = KEY["color"]
key.visible_camera = False

# camera
cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam)
cam.matrix_world = Matrix(((right[0], up[0], -fwd[0], C[0]), (right[1], up[1], -fwd[1], C[1]), (right[2], up[2], -fwd[2], C[2]), (0, 0, 0, 1)))
cd.lens = LENS; cd.sensor_width = 36.0; cd.sensor_fit = "HORIZONTAL"; cd.clip_start = 0.05; cd.clip_end = 500
f = LENS / 1000.0
focus = DIST - BULGE * Rm * 0.66                                     # sharpest three quarters of the way out; the centre and the limb share the rest
kpx = (f * f / (focus - f)) * (2560 / 0.036)                         # defocus px per unit of |z - s| / z, at f/1
fstop = kpx * (DIST - focus) / DIST / LIMB_BLUR
cd.dof.use_dof = True; cd.dof.focus_distance = focus; cd.dof.aperture_fstop = fstop; cd.dof.aperture_blades = 0
sc.camera = cam
print("Rm %.3f bead r %.4f focus %.3f fstop %.3f" % (Rm, BR, focus, fstop))

# stars: much smaller, dimmer beads far behind, out of focus. Laid out on screen (sparse, never behind the moon, clear of the frame edges).
def depth_for_blur(b): return focus / (1 - b * fstop / kpx)
stars = []; tries = 0
while len(stars) < N_STARS and tries < 200000:
    tries += 1
    u, v = 0.035 + 0.93 * rng.random(), 0.05 + 0.90 * rng.random()
    if math.hypot((u - MOON_UV[0]) * 16 / 9, v - MOON_UV[1]) < 0.5 * MOON_H + 0.035: continue
    if any(math.hypot((u - s[0]) * 16 / 9, v - s[1]) < 0.105 for s in stars): continue
    stars.append((u, v, STAR_BLUR[0] + (STAR_BLUR[1] - STAR_BLUR[0]) * rng.random() ** 1.4, 0.32 + 0.30 * rng.random(), STAR_GLOW[0] + (STAR_GLOW[1] - STAR_GLOW[0]) * rng.random() ** 2))
stars = np.array(stars)
keep = np.ones(len(stars), bool) if wide else (stars[:, 0] > 0.5 + 0.012)
sp = np.array([at_depth(s[0], s[1], depth_for_blur(s[2])) for s in stars])
scol = mcol[rng.permutation(len(mcol))[:len(stars)]] * stars[:, 4:5]
ob = tile(sc, "stars", *tmpl_sphere(12, 6), sp[keep], (BR * stars[:, 3] * depth_for_blur(stars[:, 2]) / DIST)[keep], scol[keep])
ob.data.materials.append(glow_mat("star", 1.0, limb=0.3))
print("stars placed %d, kept %d" % (len(stars), keep.sum()))

bpy.context.view_layer.update()
def px(P):
    co = world_to_camera_view(sc, cam, Vector([float(x) for x in P])); return [round(co.x * 2560, 1), round((1 - co.y) * 1440, 1)]
mc = px(moon_c); me = px(moon_c + Rm * right)
anchors = {"image": {"width": 2560, "height": 1440, "background": "#080706"},
           "moon_centre": mc, "moon_radius_px": round(me[0] - mc[0], 1),
           "stars": [{"xy": px(p), "blur_px": round(float(s[2]), 1)} for p, s, k in zip(sp, stars, keep) if k]}
name = "moon_wide_stars" if wide else "moon"
raw = os.path.join(HERE, "work", "%s_%s_raw.png" % (name, q)); os.makedirs(os.path.dirname(raw), exist_ok=True)
render(sc, raw)
a8 = to8(load_px(raw))
outp = os.path.join(HERE, name + ".png") if q == "final" else os.path.join(HERE, "work", name + "_draft.png")
save8(a8, outp); measure(a8, outp)
if q == "final":
    json.dump(anchors, open(os.path.join(HERE, name + "_anchors.json"), "w"), indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "work", name + ".blend"))
print("DONE", outp)
