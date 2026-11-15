# Porcelain controls: the Voting screen (voted.png state: Thursday chosen) cast as one unglazed greige slab.
# Pills raised, Thursday pressed in, the words debossed from the real screenshot's own ink, the dot clock as
# 2,921 dark stoneware pegs in the app's true layout (web/dotart.js still(clock)). Late sun through leaves.
# usage: blender -b -P porcelain.py -- <shot> <draft|final> [outname]
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

# ---------------- key choices ----------------
S_PX     = 0.180 / 1206.0      # the screen is cast 180 mm wide (2.7x a phone): metres per screenshot pixel
GREIGE   = "#EAE5DE"           # app surface; albedo compensated below so sunlit slab reads close to it under AgX
PEG      = "#3A342E"           # the app's dot ink
PILL_UP, PRESS_DN, FILLET = 0.0034, 0.0024, 0.0060
DEBOSS   = 0.00042
SUN      = dict(elev=23.0, azim=152.0, strength=9.0, color=(1.0, 0.84, 0.64), angle=0.9)   # late sun, from back-left
SKY      = dict(strength=0.006, bounce=(0.80, 0.74, 0.66), bounce_strength=0.20)   # a little blue sky plus warm bounce from the ground and leaves                                                           # blue-sky fill in the shadows
EXPOSURE = 1.05
SHOTS = {
    # from the foot of the screen, looking up it: pills near, clock soft behind; left third is bare slab for words
    "three": dict(cam=(-0.125, -0.500, 0.290), target=(-0.030, -0.066, 0.0), focus=(-0.02, -0.105, 0.0), lens=62, fstop=7.1),
    # macro on the pressed pill's left end, raised Sunday behind it
    "press": dict(cam=(-0.175, -0.270, 0.105), target=(-0.035, -0.098, 0.0), focus=(-0.062, -0.094, 0.0), lens=100, fstop=5.6),
}
# ---------------------------------------------

a = args(); shot = a[0] if a else "three"; q = a[1] if len(a) > 1 else "draft"
S = SHOTS[shot]
sc = reset()
W, H, SPP = (1280, 720, 128) if q == "draft" else (2560, 1440, 700)
cycles(sc, W, H, SPP, view="AgX", look="AgX - Base Contrast", exposure=EXPOSURE)

# ---------- height field from the real screenshot layout ----------
SCALE = 2                                    # height map pixels per screenshot pixel
HM = os.path.join(HERE, "data", "porcelain_height.exr")
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
    fw = FILLET / S_PX
    hgt = np.zeros((h, w), np.float32)
    pills = [(74, 1855, 1131, 2034, -PRESS_DN), (74, 2072, 1131, 2250, PILL_UP), (74, 2288, 1131, 2467, PILL_UP)]
    for (x0, y0, x1, y1, amt) in pills:
        d = -sd_rr(x0, y0, x1 + 1, y1 + 1, (y1 + 1 - y0) / 2)
        if amt > 0:
            hgt += amt * prof(d, fw) + 0.0004 * np.clip(d / 90, 0, 1) ** 0.5 * (d > 0)      # a little crown
        else:
            hgt += amt * prof(d, fw * 0.8, 2.0)
    dg = -(np.hypot(xx - 1067, yy - 226) - 65.5)
    hgt += PILL_UP * 0.9 * prof(dg, fw * 0.8)
    # the words and the gear glyph: the screenshot's own ink, pressed in
    v = load_px(os.path.join(SCREENS, "voted.png")); L = v[..., :3].mean(-1)
    ink = np.clip((0.62 - L) / 0.42, 0, 1)
    keep = np.zeros_like(ink)
    for (x0, y0, x1, y1) in [(100, 1395, 1110, 1580), (120, 1612, 1090, 1695),
                             (120, 1900, 1090, 1995), (120, 2115, 1090, 2212), (120, 2330, 1090, 2428), (1030, 190, 1104, 262)]:
        keep[y0:y1, x0:x1] = 1
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

# ---------- the dot clock: stoneware pegs ----------
ck = json.load(open(os.path.join(HERE, "data", "clock.json")))
pts = np.array(ck["still"], dtype=np.float64).reshape(-1, 2)
# place by fitting the dots' bounding box to the clock's in the screenshot (x 286..956, y 515..1198)
K = 402.0 / 390.0                            # the iOS screen is 402 pt wide; the web art is drawn for 390
pts = pts * K
ox = 286 - 3 * pts[:, 0].min(); oy = 515 - 3 * pts[:, 1].min()
print("clock fit: width px", 3 * (pts[:, 0].max() - pts[:, 0].min()) + 4, "vs 671; height", 3 * (pts[:, 1].max() - pts[:, 1].min()) + 4, "vs 684")
cxp = ox + 3 * pts[:, 0] + 2.0 * K; cyp = oy + 3 * pts[:, 1] + 2.0 * K
N = len(pts); rng = np.random.default_rng(5)
side = 4.0 * K * S_PX * 0.94
proud = 0.00030 + 0.00012 * rng.random(N)
pos = np.stack([(cxp - PW / 2) * S_PX, -(cyp - PH / 2) * S_PX, proud - 0.0006], 1)
ang = rng.normal(0, math.radians(3.5), N); c, s_ = np.cos(ang), np.sin(ang)
R = np.zeros((N, 3, 3)); R[:, 0, 0] = c; R[:, 0, 1] = -s_; R[:, 1, 0] = s_; R[:, 1, 1] = c; R[:, 2, 2] = 1
R = tilt_mats(rng, N, 2.5) @ R
cv, cf = tmpl("cube", bevel=0.09, seg=2)
pegs = tile(sc, "pegs", cv, cf, trs(pos, np.stack([np.full(N, side), np.full(N, side), np.full(N, 0.0012)], 1), R),
            {"tone": (0.8 + 0.4 * rng.random(N)).astype(np.float32)}, smooth=False)
mpg, ntp, bp, _ = new_mat("peg")
at = ntp.nodes.new("ShaderNodeAttribute"); at.attribute_name = "tone"
mul = ntp.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 1.0
mul.inputs["A"].default_value = (*srgb(PEG), 1); nt_l = ntp.links.new(at.outputs["Fac"], mul.inputs["B"])
ntp.links.new(mul.outputs["Result"], bp.inputs["Base Color"]); setin(bp, "Roughness", 0.6)
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
boughs = [((-0.34, 0.13), (-0.13, 0.00), 24), ((-0.10, 0.145), (0.22, 0.075), 26), ((0.11, -0.03), (0.25, -0.15), 14),
          ((-0.33, -0.24), (-0.20, -0.34), 10)]
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
raw = os.path.join(HERE, "drafts", "porcelain_%s_%s_raw.png" % (shot, q))
dt = render(sc, raw)
_r = load_px(raw)[..., :3]; _l = _r.mean(-1); _t = np.quantile(_l, 0.80)
print("PROBE sunlit (top 20%% median) sRGB:", (np.median(_r[_l >= _t], axis=0) * 255).round(1), "shade (low 20%% median):", (np.median(_r[_l <= np.quantile(_l, 0.2)], axis=0) * 255).round(1))
outp = os.path.join(HERE, "drafts", "porcelain_%s_%s.png" % (shot, q)) if q == "draft" else os.path.join(HERE, a[2] if len(a) > 2 else "porcelain_%s.png" % shot)
finish(raw, outp, grain=0.012, vignette=0.07, seed=3)
if q == "final":
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "porcelain_%s.blend" % shot))
print("DONE", outp, "render %.1fs" % dt)
