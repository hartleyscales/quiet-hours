# The day moon: the sign-in screen cast in the same unglazed greige porcelain. Its daylight moon is 9,857 stoneware
# pegs in the app's true layout and colours (web/assets/moon-col-light.png.json), fitted to signin.png; the title
# and its line are pressed in from the screenshot's own ink. Late sun through leaves.
# usage: blender -b -P daymoon.py -- <shot> <draft|final> [outname]
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

# ---------------- key choices ----------------
S_PX     = 0.180 / 1206.0      # the screen is cast 180 mm wide: metres per screenshot pixel
GREIGE   = "#EAE5DE"
DEBOSS   = 0.00055
PEG_GAIN = 0.32                # the pegs take the app's own dot colours, fired darker so they hold against sunlit porcelain
SUN      = dict(elev=23.0, azim=152.0, strength=9.0, color=(1.0, 0.84, 0.64), angle=0.9)   # late sun, from back-left
SKY      = dict(strength=0.006, bounce=(0.80, 0.74, 0.66), bounce_strength=0.20)
EXPOSURE = 1.05
SHOTS = {
    # from below the title, looking up the slab: title sharp, moon just behind it; left third bare for words
    "title": dict(cam=(-0.120, -0.470, 0.330), target=(-0.036, 0.022, 0.0), focus=(0.0, -0.020, 0.0), lens=80, fstop=8.0),
}
BOUGHS = [((-0.36, 0.24), (-0.13, 0.13), 22), ((0.02, 0.21), (0.24, 0.10), 20), ((-0.36, -0.10), (-0.24, -0.22), 9)]
# ---------------------------------------------

a = args(); shot = a[0] if a else "title"; q = a[1] if len(a) > 1 else "draft"
S = SHOTS[shot]
sc = reset()
W, H, SPP = (1280, 720, 128) if q == "draft" else (2560, 1440, 700)
cycles(sc, W, H, SPP, view="AgX", look="AgX - Base Contrast", exposure=EXPOSURE)

# ---------- height field from the real screenshot layout ----------
SCALE = 2                                    # height map pixels per screenshot pixel
HM = os.path.join(HERE, "data", "daymoon_height.exr")
PW, PH = 1206, 2622
def build_height():
    w, h = PW * SCALE, PH * SCALE
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); xx = (xx + 0.5) / SCALE; yy = (yy + 0.5) / SCALE   # screenshot px
    def sd_rr(x0, y0, x1, y1, r):
        qx = np.abs(xx - (x0 + x1) / 2) - ((x1 - x0) / 2 - r); qy = np.abs(yy - (y0 + y1) / 2) - ((y1 - y0) / 2 - r)
        return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
    def prof(d_in, wid, p=2.3):              # pillowy quarter-superellipse: crisp at the foot, soft at the shoulder
        t = np.clip(d_in / wid, 0, 1)
        return (1 - (1 - t) ** p) ** (1 / p)
    hgt = np.zeros((h, w), np.float32)
    v = load_px(os.path.join(SCREENS, "signin.png")); L = v[..., :3].mean(-1)
    ink = np.clip((0.66 - L) / 0.46, 0, 1)
    keep = np.zeros_like(ink); keep[1235:1700, 60:1150] = 1
    ink = np.kron(ink * keep, np.ones((SCALE, SCALE), np.float32))
    ink = blur(ink, 0.9).astype(np.float32)
    hgt -= DEBOSS * ink
    hgt = blur(hgt, 0.8).astype(np.float32)
    im = bpy.data.images.new("hm", w, h, alpha=False, float_buffer=True); im.colorspace_settings.name = "Non-Color"
    px = np.zeros((h, w, 4), np.float32); px[..., 0] = px[..., 1] = px[..., 2] = hgt[::-1]; px[..., 3] = 1
    im.pixels.foreach_set(px.ravel()); im.filepath_raw = HM; im.file_format = "OPEN_EXR"; im.save(); bpy.data.images.remove(im)
if not os.path.exists(HM) or "--rebuild" in a:
    build_height()

# ---------- the slab ----------
bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=120, size=1.4, location=(0, 0, 0)); slab = bpy.context.object
sub = slab.modifiers.new("sub", "SUBSURF"); sub.subdivision_type = "SIMPLE"; sub.levels = 0; sub.render_levels = 1
sub.use_adaptive_subdivision = True
try:
    sub.adaptive_space = "PIXEL"; sub.adaptive_pixel_size = 1.6 if q == "draft" else 0.75
except Exception as e: print("adaptive:", e)
m, nt, b, out = new_mat("porcelain"); m.displacement_method = "BOTH"
tc = nt.nodes.new("ShaderNodeTexCoord")
mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Scale"].default_value = (1 / (PW * S_PX), 1 / (PH * S_PX), 1); mp.inputs["Location"].default_value = (0.5, 0.5, 0)
nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
it = nt.nodes.new("ShaderNodeTexImage"); it.image = bpy.data.images.load(HM); it.image.colorspace_settings.name = "Non-Color"
it.interpolation = "Cubic"; it.extension = "CLIP"
nt.links.new(mp.outputs["Vector"], it.inputs["Vector"])
# hand-cast surface: a slow waviness and a fine tooth
nA = nt.nodes.new("ShaderNodeTexNoise"); nA.inputs["Scale"].default_value = 9; nA.inputs["Detail"].default_value = 2
nB = nt.nodes.new("ShaderNodeTexNoise"); nB.inputs["Scale"].default_value = 2600; nB.inputs["Detail"].default_value = 4; nB.inputs["Roughness"].default_value = 0.65
nC = nt.nodes.new("ShaderNodeTexNoise"); nC.inputs["Scale"].default_value = 260; nC.inputs["Detail"].default_value = 3
for n in (nA, nB, nC): nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
h1 = nt.nodes.new("ShaderNodeMath"); h1.operation = "MULTIPLY_ADD"; nt.links.new(nA.outputs["Fac"], h1.inputs[0]); h1.inputs[1].default_value = 0.0005; nt.links.new(it.outputs["Color"], h1.inputs[2])
h2 = nt.nodes.new("ShaderNodeMath"); h2.operation = "MULTIPLY_ADD"; nt.links.new(nB.outputs["Fac"], h2.inputs[0]); h2.inputs[1].default_value = 0.000022; nt.links.new(h1.outputs[0], h2.inputs[2])
h3 = nt.nodes.new("ShaderNodeMath"); h3.operation = "MULTIPLY_ADD"; nt.links.new(nC.outputs["Fac"], h3.inputs[0]); h3.inputs[1].default_value = 0.00004; nt.links.new(h2.outputs[0], h3.inputs[2])
dn = nt.nodes.new("ShaderNodeDisplacement"); dn.inputs["Midlevel"].default_value = 0.0; dn.inputs["Scale"].default_value = 1.0
nt.links.new(h3.outputs[0], dn.inputs["Height"]); nt.links.new(dn.outputs[0], out.inputs["Displacement"])
g = np.array(srgb(GREIGE))
mixc = nt.nodes.new("ShaderNodeMix"); mixc.data_type = "RGBA"
mixc.inputs["A"].default_value = (*(g * 0.97), 1); mixc.inputs["B"].default_value = (*(g * np.array([1.0, 0.985, 0.96]) * 0.90), 1)
rmp = nt.nodes.new("ShaderNodeValToRGB"); rmp.color_ramp.elements[0].position = 0.35; rmp.color_ramp.elements[1].position = 0.75
nt.links.new(nC.outputs["Fac"], rmp.inputs["Fac"]); nt.links.new(rmp.outputs["Color"], mixc.inputs["Factor"])
nt.links.new(mixc.outputs["Result"], b.inputs["Base Color"])
setin(b, "Roughness", 0.72); setin(b, "Specular IOR Level", 0.35)
setin(b, "Subsurface Weight", 0.25); setin(b, "Subsurface Radius", (1.0, 0.7, 0.5)); setin(b, "Subsurface Scale", 0.0012)
slab.data.materials.append(m)

# ---------- the day moon: stoneware pegs ----------
dd = np.array(json.load(open(os.path.join(QH, "web", "assets", "moon-col-light.png.json"))), dtype=np.float64)
K = 402.0 / 390.0
v = load_px(os.path.join(SCREENS, "signin.png")); Lm = blur(v[..., :3].mean(-1), 1.0)
qx = (dd[:, 0] * 2 + 1) * 3 * K; qy = (dd[:, 1] * 2 + 1) * 3 * K
best = (1e18, 0, 0)
for oy in np.arange(-40, 60, 2.0):
    for ox in np.arange(-40, 40, 2.0):
        sc_ = Lm[np.clip((qy + oy).astype(int), 0, PH - 1), np.clip((qx + ox).astype(int), 0, PW - 1)].sum()
        if sc_ < best[0]: best = (sc_, ox, oy)
bx, by = best[1], best[2]
for oy in np.arange(by - 2, by + 2.01, 0.5):
    for ox in np.arange(bx - 2, bx + 2.01, 0.5):
        sc_ = Lm[np.clip((qy + oy).astype(int), 0, PH - 1), np.clip((qx + ox).astype(int), 0, PW - 1)].sum()
        if sc_ < best[0]: best = (sc_, ox, oy)
print("moon fit offset px", best[1], best[2], "mean lum at dots", best[0] / len(dd))
cxp = qx + best[1]; cyp = qy + best[2]
N = len(dd); rng = np.random.default_rng(5)
side = 4.0 * K * S_PX * 0.94
proud = 0.00030 + 0.00012 * rng.random(N)
pos = np.stack([(cxp - PW / 2) * S_PX, -(cyp - PH / 2) * S_PX, proud - 0.0006], 1)
ang = rng.normal(0, math.radians(3.5), N); c, s_ = np.cos(ang), np.sin(ang)
R = np.zeros((N, 3, 3)); R[:, 0, 0] = c; R[:, 0, 1] = -s_; R[:, 1, 0] = s_; R[:, 1, 1] = c; R[:, 2, 2] = 1
R = tilt_mats(rng, N, 2.5) @ R
cv, cf = tmpl("cube", bevel=0.09, seg=2)
pcol = lin(dd[:, 2:5]) * PEG_GAIN * (0.85 + 0.3 * rng.random((N, 1)))
pegs = tile(sc, "pegs", cv, cf, trs(pos, np.stack([np.full(N, side), np.full(N, side), np.full(N, 0.0012)], 1), R), {"col": pcol}, smooth=False)
mpg, ntp, bp, _ = new_mat("peg")
at = ntp.nodes.new("ShaderNodeAttribute"); at.attribute_name = "col"
ntp.links.new(at.outputs["Color"], bp.inputs["Base Color"]); setin(bp, "Roughness", 0.6)
pegs.data.materials.append(mpg)

# ---------- light: a real low sun, sky fill, and leaves between ----------
sun, frm = sun_light(sc, "sun", SUN["elev"], SUN["azim"], SUN["strength"], SUN["color"], SUN["angle"])
wn = sc.world.node_tree
for n in list(wn.nodes): wn.nodes.remove(n)
sky = wn.nodes.new("ShaderNodeTexSky"); sky.sky_type = "MULTIPLE_SCATTERING"; sky.sun_disc = False
sky.sun_elevation = math.radians(SUN["elev"]); sky.sun_rotation = math.radians(90 - SUN["azim"])
bg = wn.nodes.new("ShaderNodeBackground"); bg.inputs[1].default_value = SKY["strength"]
bg2 = wn.nodes.new("ShaderNodeBackground"); bg2.inputs[0].default_value = (*SKY["bounce"], 1); bg2.inputs[1].default_value = SKY["bounce_strength"]
addw = wn.nodes.new("ShaderNodeAddShader")
wo = wn.nodes.new("ShaderNodeOutputWorld"); wn.links.new(sky.outputs[0], bg.inputs[0])
wn.links.new(bg.outputs[0], addw.inputs[0]); wn.links.new(bg2.outputs[0], addw.inputs[1]); wn.links.new(addw.outputs[0], wo.inputs[0])

# leaves: placed by where their shadow should land on the slab, then pushed up the sun ray
def leaf_outline(n=60):
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    lob = np.abs(np.cos(2.5 * (th - np.pi / 2))) ** 0.55          # five lobes, the middle one up
    r = 0.42 + 0.58 * lob
    r *= 0.75 + 0.25 * np.cos((th - np.pi / 2) / 2) ** 2           # shorter towards the stem
    return np.stack([r * np.cos(th), r * np.sin(th), np.zeros(n)], 1)
lo = leaf_outline(); lv = np.concatenate([np.zeros((1, 3)), lo]); nl = len(lo)
lf = np.array([[0, 1 + i, 1 + (i + 1) % nl] for i in range(nl)])
lr = np.random.default_rng(23)
land = []
# boughs (in slab coordinates, metres): one over the bare left, one reaching across the clock, a twig at the far right
boughs = BOUGHS
for (p0, p1, cnt) in boughs:
    t = lr.random(cnt); p = np.array(p0)[None] * (1 - t[:, None]) + np.array(p1)[None] * t[:, None]
    land.append(p + lr.normal(0, 0.028, (cnt, 2)))
land = np.concatenate(land); NL = len(land)
dist = 0.9 + 1.8 * lr.random(NL)
lpos = np.concatenate([land, np.zeros((NL, 1))], 1) + np.array(frm)[None] * dist[:, None]
# random orientation, loosely facing the sun
def rand_rot(n, rg):
    qv = rg.normal(size=(n, 4)); qv /= np.linalg.norm(qv, axis=1, keepdims=True); w_, x_, y_, z_ = qv.T
    return np.stack([np.stack([1 - 2 * (y_ * y_ + z_ * z_), 2 * (x_ * y_ - z_ * w_), 2 * (x_ * z_ + y_ * w_)], 1),
                     np.stack([2 * (x_ * y_ + z_ * w_), 1 - 2 * (x_ * x_ + z_ * z_), 2 * (y_ * z_ - x_ * w_)], 1),
                     np.stack([2 * (x_ * z_ - y_ * w_), 2 * (y_ * z_ + x_ * w_), 1 - 2 * (x_ * x_ + y_ * y_)], 1)], 1)
leaves = tile(sc, "leaves", lv, lf, trs(lpos, 0.030 + 0.026 * lr.random(NL), rand_rot(NL, lr)), smooth=False)
ml, ntl, bl, _ = new_mat("leaf"); setin(bl, "Base Color", (0.10, 0.16, 0.04, 1)); setin(bl, "Roughness", 0.6)
leaves.data.materials.append(ml)
leaves.visible_camera = False; leaves.visible_glossy = False

cam = camera(sc, S["cam"], S["target"], lens=S["lens"], fstop=S["fstop"])
bpy.context.view_layer.update(); focus_on(cam, S["focus"])

os.makedirs(os.path.join(HERE, "drafts"), exist_ok=True)
raw = os.path.join(HERE, "drafts", "daymoon_%s_%s_raw.png" % (shot, q))
dt = render(sc, raw)
_r = load_px(raw)[..., :3]; _l = _r.mean(-1); _t = np.quantile(_l, 0.80)
print("PROBE sunlit (top 20%% median) sRGB:", (np.median(_r[_l >= _t], axis=0) * 255).round(1), "shade (low 20%% median):", (np.median(_r[_l <= np.quantile(_l, 0.2)], axis=0) * 255).round(1))
outp = os.path.join(HERE, "drafts", "daymoon_%s_%s.png" % (shot, q)) if q == "draft" else os.path.join(HERE, a[2] if len(a) > 2 else "daymoon_%s.png" % shot)
finish(raw, outp, grain=0.012, vignette=0.07, seed=3)
if q == "final":
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "daymoon_%s.blend" % shot))
print("DONE", outp, "render %.1fs" % dt)
