# The screen, taken apart: the Locked screen's picture lifted off a quiet (dark) phone in four layers.
# Every lifted pixel is the real locked.png: the stars on a pane of dark glass, the pill, the words, and the
# dot moon as 3,098 loose tiles (true layout, web/moon.js N = 3098, fitted to the screenshot).
# usage: blender -b -P exploded.py -- <draft|final> [outname]
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

# ---------------- key choices ----------------
YAW      = 24.0                       # phone lies turned 24 deg, its top away and to the left
LIFT     = dict(stars=0.022, pill=0.029, words=0.035, moon=0.040)   # metres above the glass; the moon highest so the parts fan apart and its shadow clears the pane's
CAM      = dict(loc=(-0.094, -0.436, 0.420), target=(-0.076, -0.020, 0.015), lens=66, fstop=4.0)   # focus is put on the moon layer
KEY      = dict(loc=(-0.42, 0.46, 0.34), size=0.22, power=26, color=(1.0, 0.83, 0.64))            # warm, from the left
FILL     = dict(loc=(0.55, -0.45, 0.60), size=0.9, power=3.0, color=(0.80, 0.86, 1.0))
LIGHT    = "sun"
SUN      = dict(elev=18.0, azim=YAW + 12.0, strength=9.0, color=(1.0, 0.84, 0.64), angle=0.6)   # low sun from the phone's right: the lifted picture throws its shadow on the paper
SKY      = dict(strength=0.006, bounce=(0.80, 0.74, 0.66), bounce_strength=0.20)
PANE_ALPHA = 1.0                      # the night pane is black glass
LEAVES   = [((-0.40, 0.23), (-0.21, 0.13), 13)]   # one far bough, its shadow soft in the top-left corner
GROUND   = "#EAE5DE"                  # the app's daylight surface, as paper
CASE     = "#B4775E"                  # clay case
CASE_GAIN = 0.62                      # albedo pulled down so the lit case reads as #B4775E under AgX and this exposure
EXPOSURE = 1.0
# ---------------------------------------------

a = args(); q = a[0] if a else "draft"
sc = reset()
W, H, SPP = (1280, 720, 160) if q == "draft" else (2560, 1440, 900)
cycles(sc, W, H, SPP, view="AgX", look="AgX - Base Contrast", exposure=EXPOSURE)
world_color(sc, (0.9, 0.82, 0.74), 0.035)

PW, PH = 1206, 2622
SW, SH = PW * PX, PH * PX             # screen size in metres (66.5 x 144.6 mm)
rig = bpy.data.objects.new("rig", None); sc.collection.objects.link(rig); rig.rotation_euler = (0, 0, math.radians(YAW))

def ring_solid(name, hx, hy, R, prof, seg=14, z0=0.0, close_bottom=True, split=None):
    """Rounded-rectangle solid from (inset, height) profile rings; returns object. Faces from ring `split` on use material slot 1."""
    th = np.linspace(0, np.pi / 2, seg + 1)
    rings = []
    for d, z in prof:
        r = max(R - d, 0.0); cx = min(hx - R, hx - d); cy = min(hy - R, hy - d)
        pts = []
        for (sx, sy, off) in [(1, 1, 0), (-1, 1, np.pi / 2), (-1, -1, np.pi), (1, -1, 3 * np.pi / 2)]:
            ang = th + off
            pts.append(np.stack([sx * cx + r * np.cos(ang), sy * cy + r * np.sin(ang), np.full(seg + 1, z0 + z)], 1))
        rings.append(np.concatenate(pts))
    M = rings[0].shape[0]; V = np.concatenate(rings)
    faces, mats = [], []
    for k in range(len(rings) - 1):
        for i in range(M):
            j = (i + 1) % M
            faces.append((k * M + i, k * M + j, (k + 1) * M + j, (k + 1) * M + i)); mats.append(1 if (split is not None and k >= split) else 0)
    faces.append(tuple(range((len(rings) - 1) * M, len(rings) * M))); mats.append(1 if split is not None else 0)
    if close_bottom:
        faces.append(tuple(range(M - 1, -1, -1))); mats.append(0)
    me = bpy.data.meshes.new(name); me.from_pydata(V.tolist(), [], faces); me.update()
    me.polygons.foreach_set("material_index", np.array(mats, dtype=np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(len(faces), dtype=bool))
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); ob.parent = rig
    return ob

def arc(d0, z0, rad, n=8, up=True):
    """Quarter-round from the top of a wall (d0, z0) over to the flat (d0 + rad, z0 + rad)."""
    t = np.linspace(0, np.pi / 2, n + 1)[1:]
    return [(d0 + rad * (1 - np.cos(tt)), z0 + rad * np.sin(tt)) for tt in t]

# ---------- screenshot, split into its layers ----------
L = load_px(os.path.join(SCREENS, "locked.png")); rgb = L[..., :3]; lum = rgb.mean(-1)
bgl = float(np.median(lum))
d = json.load(open(os.path.join(HERE, "data", "moon_3098.json")))
dots = np.array(d["dots"], dtype=np.float64)
K = 402.0 / 390.0                      # iOS screen is 402 pt wide; the art is drawn for 390
# fit the dot grid to the screenshot: slide it until the dots sit on the brightest pixels
px0 = (dots[:, 0] * 2 + 1 / 3 + 2 / 3) * 3 * K; py0 = (dots[:, 1] * 2 + 1 / 3 + 2 / 3) * 3 * K     # dot centres, px, before offset
best = (-1, 0, 0); sm = blur(lum, 1.0)
for oy in range(520, 680, 2):
    for ox in range(-20, 40, 2):
        s = sm[np.clip((py0 + oy).astype(int), 0, PH - 1), np.clip((px0 + ox).astype(int), 0, PW - 1)].sum()
        if s > best[0]: best = (s, ox, oy)
_, ox, oy = best
bx, by = ox, oy; best = (-1, ox, oy)
for oy2 in np.arange(by - 2, by + 2.01, 0.5):
    for ox2 in np.arange(bx - 2, bx + 2.01, 0.5):
        s = sm[np.clip((py0 + oy2).astype(int), 0, PH - 1), np.clip((px0 + ox2).astype(int), 0, PW - 1)].sum()
        if s > best[0]: best = (s, ox2, oy2)
_, ox, oy = best
mcx = (d["cx"] * 2 + 1) * 3 * K + ox; mcy = (d["cy"] * 2 + 1) * 3 * K + oy; mr = d["r"] * 2 * 3 * K
print("moon fit: offset", ox, oy, "centre px", round(mcx, 1), round(mcy, 1), "radius px", round(mr, 1), "mean lum at dots", best[0] / len(dots))

yy, xx = np.mgrid[0:PH, 0:PW]
not_stars = (np.hypot(xx - mcx, yy - mcy) < mr + 14) | ((yy > 1380) & (yy < 1720) & (xx > 150) & (xx < 1060)) | (yy > 2270) & (yy < 2480) | (yy < 140) \
            | (np.hypot(xx - 1067, yy - 226) < 80)
star = np.clip((lum - bgl - 0.02) / 0.25, 0, 1) * (~not_stars)
star_rgb = rgb * star[..., None] / np.maximum(lum, 1e-3)[..., None] * 0.9
os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
save_px(np.clip(star_rgb, 0, 1), os.path.join(HERE, "data", "locked_stars.png"))
head = np.zeros_like(lum); sub = np.zeros_like(lum); ptx = np.zeros_like(lum)
hl = lum[1395:1610, 150:1060]; head[1395:1610, 150:1060] = np.clip((hl - bgl - 0.01) / (hl.max() - bgl - 0.02), 0, 1)
sl = lum[1620:1705, 250:950]; sub[1620:1705, 250:950] = np.clip((sl - bgl - 0.01) / (sl.max() - bgl - 0.02), 0, 1)
pill_l = float(lum[2380, 150]); pl = lum[2310:2450, 200:1000]; ptx[2310:2450, 200:1000] = np.clip((pl - pill_l - 0.01) / (pl.max() - pill_l - 0.02), 0, 1)
save_px(np.stack([head, sub, ptx], -1), os.path.join(HERE, "data", "locked_masks.png"))
c_head = rgb[1395:1610, 150:1060].reshape(-1, 3)[hl.argmax()]; c_sub = rgb[1620:1705, 250:950].reshape(-1, 3)[sl.argmax()]
c_ptx = rgb[2310:2450, 200:1000].reshape(-1, 3)[pl.argmax()]; c_pill = rgb[2380, 150]
print("colours 0-255: headline", (c_head * 255).round(), "sub", (c_sub * 255).round(), "pill text", (c_ptx * 255).round(), "pill", (c_pill * 255).round())
tolin = lambda c: tuple(float(v) for v in lin(np.asarray(c) * 255))

def screen_uv(nt):
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / SW, 1 / SH, 1); mp.inputs["Location"].default_value = (0.5, 0.5, 0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"]); return mp
def img(nt, path, mp, noncolor=False):
    it = nt.nodes.new("ShaderNodeTexImage"); it.image = bpy.data.images.load(path, check_existing=True)
    if noncolor: it.image.colorspace_settings.name = "Non-Color"
    it.extension = "CLIP"; it.interpolation = "Cubic"; nt.links.new(mp.outputs["Vector"], it.inputs["Vector"]); return it

# ---------- ground ----------
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0)); ground = bpy.context.object
mg, ntg, bgd, _ = new_mat("paper"); setin(bgd, "Base Color", (*srgb(GROUND), 1)); setin(bgd, "Roughness", 0.9); setin(bgd, "Specular IOR Level", 0.2)
ng = ntg.nodes.new("ShaderNodeTexNoise"); ng.inputs["Scale"].default_value = 900; ng.inputs["Detail"].default_value = 5; ng.inputs["Roughness"].default_value = 0.7
bmp = ntg.nodes.new("ShaderNodeBump"); bmp.inputs["Strength"].default_value = 0.25; bmp.inputs["Distance"].default_value = 0.0002
ntg.links.new(ng.outputs["Fac"], bmp.inputs["Height"]); ntg.links.new(bmp.outputs["Normal"], bgd.inputs["Normal"])
ground.data.materials.append(mg)

# ---------- the phone: black slab in a clay case, screen dark ----------
HX, HY, RC, HC = 0.0372, 0.0763, 0.0128, 0.0104          # case half-size, corner radius, height
FIL = 0.0032
prof = [(0.0006, 0.0), (0.0, 0.0006), (0.0, HC - FIL)] + arc(0.0, HC - FIL, FIL, 8)          # wall and shoulder
prof += [(FIL + 0.0002, HC)]                                                                 # the lip (already flat at d = FIL)
G0 = FIL + 0.0006; GZ = HC - 0.0009
prof += [(G0 - 0.0002, HC - 0.0002), (G0, GZ)]                                               # inner wall down to the glass
split = len(prof) - 1
prof += [(G0 + 0.0004, GZ), (0.0125, GZ)]
phone = ring_solid("phone", HX, HY, RC, prof, seg=18, split=split)
mc, ntc, bc, _ = new_mat("case"); setin(bc, "Base Color", (*(np.array(srgb(CASE)) * CASE_GAIN), 1)); setin(bc, "Roughness", 0.55); setin(bc, "Specular IOR Level", 0.3)
ncn = ntc.nodes.new("ShaderNodeTexNoise"); ncn.inputs["Scale"].default_value = 2500; ncn.inputs["Detail"].default_value = 3
cb = ntc.nodes.new("ShaderNodeBump"); cb.inputs["Strength"].default_value = 0.12; cb.inputs["Distance"].default_value = 0.0001
ntc.links.new(ncn.outputs["Fac"], cb.inputs["Height"]); ntc.links.new(cb.outputs["Normal"], bc.inputs["Normal"])
mgl, ntgl, bgl_, _ = new_mat("glass"); setin(bgl_, "Base Color", (0.004, 0.004, 0.004, 1)); setin(bgl_, "Roughness", 0.04); setin(bgl_, "Specular IOR Level", 0.6)
phone.data.materials.append(mc); phone.data.materials.append(mgl)
GLASS = GZ

# ---------- layer 1: the stars, on a pane of dark glass ----------
zs = GLASS + LIFT["stars"]; T = 0.0007
pane = ring_solid("stars", SW / 2, SH / 2, 0.0091, [(0.0, 0.0), (0.0, T - 0.0002), (0.0002, T), (0.004, T)], seg=14, z0=zs)
mst, nts, bst, outs = new_mat("stars"); mp = screen_uv(nts); it = img(nts, os.path.join(HERE, "data", "locked_stars.png"), mp)
setin(bst, "Base Color", (*srgb("#080706"), 1)); setin(bst, "Roughness", 0.07); setin(bst, "Specular IOR Level", 0.55)
nts.links.new(it.outputs["Color"], bst.inputs["Emission Color"]); setin(bst, "Emission Strength", 2.2); setin(bst, "Alpha", PANE_ALPHA)
pane.data.materials.append(mst)

# ---------- layer 2: the pill ----------
zp = GLASS + LIFT["pill"]
px0p, px1p, py0p, py1p = 76, 1131, 2288, 2466                                # the pill in the screenshot (px)
phx = (px1p - px0p) / 2 * PX; phy = (py1p - py0p) / 2 * PX
pcx = ((px0p + px1p) / 2 - PW / 2) * PX; pcy = -((py0p + py1p) / 2 - PH / 2) * PX
HPL = 0.0016
pp = [(0.0, 0.0)] + [(dd, HPL * (1 - (1 - min(dd / 0.0030, 1)) ** 2.3) ** (1 / 2.3)) for dd in np.linspace(0.0001, phy * 0.97, 22)]
pill = ring_solid("pill", phx, phy, phy * 0.999, pp, seg=20, z0=0.0)
pill.location = (pcx, pcy, zp)
mpl, ntpl, bpl, _ = new_mat("pill")
tcp = ntpl.nodes.new("ShaderNodeTexCoord"); mpp = ntpl.nodes.new("ShaderNodeMapping")
mpp.inputs["Scale"].default_value = (1 / SW, 1 / SH, 1); mpp.inputs["Location"].default_value = (0.5 + pcx / SW, 0.5 + pcy / SH, 0)
ntpl.links.new(tcp.outputs["Object"], mpp.inputs["Vector"])
itp = img(ntpl, os.path.join(HERE, "data", "locked_masks.png"), mpp, noncolor=True)
sep = ntpl.nodes.new("ShaderNodeSeparateColor"); ntpl.links.new(itp.outputs["Color"], sep.inputs[0])
mx = ntpl.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.inputs["A"].default_value = (*tolin(c_pill), 1); mx.inputs["B"].default_value = (*tolin(c_ptx), 1)
ntpl.links.new(sep.outputs[2], mx.inputs["Factor"]); ntpl.links.new(mx.outputs["Result"], bpl.inputs["Base Color"])
setin(bpl, "Roughness", 0.42); setin(bpl, "Emission Color", (*tolin(c_ptx), 1)); ntpl.links.new(sep.outputs[2], bpl.inputs["Emission Strength"])
pill.data.materials.append(mpl)

# ---------- layer 3: the words (the screenshot's own letters, as thin cut cards) ----------
zw = GLASS + LIFT["words"]
me = bpy.data.meshes.new("words"); me.from_pydata([(-SW / 2, -SH / 2, zw), (SW / 2, -SH / 2, zw), (SW / 2, SH / 2, zw), (-SW / 2, SH / 2, zw)], [], [(0, 1, 2, 3)])
words = bpy.data.objects.new("words", me); sc.collection.objects.link(words); words.parent = rig
mw, ntw, bw, _ = new_mat("words"); mpw = screen_uv(ntw); itw = img(ntw, os.path.join(HERE, "data", "locked_masks.png"), mpw, noncolor=True)
sw = ntw.nodes.new("ShaderNodeSeparateColor"); ntw.links.new(itw.outputs["Color"], sw.inputs[0])
mxw = ntw.nodes.new("ShaderNodeMix"); mxw.data_type = "RGBA"; mxw.inputs["A"].default_value = (*tolin(c_head), 1); mxw.inputs["B"].default_value = (*tolin(c_sub), 1)
ntw.links.new(sw.outputs[1], mxw.inputs["Factor"])
al = ntw.nodes.new("ShaderNodeMath"); al.operation = "MAXIMUM"; ntw.links.new(sw.outputs[0], al.inputs[0]); ntw.links.new(sw.outputs[1], al.inputs[1])
ntw.links.new(mxw.outputs["Result"], bw.inputs["Base Color"]); ntw.links.new(al.outputs[0], bw.inputs["Alpha"])
ntw.links.new(mxw.outputs["Result"], bw.inputs["Emission Color"]); setin(bw, "Emission Strength", 0.55); setin(bw, "Roughness", 0.8)
words.data.materials.append(mw)

# ---------- layer 4: the moon, 3,098 loose tiles ----------
zm = GLASS + LIFT["moon"]; N = len(dots); rng = np.random.default_rng(4)
tx = (px0 + ox - PW / 2) * PX; ty = -(py0 + oy - PH / 2) * PX
side = 4.0 * K * PX
pos = np.stack([tx, ty, zm + rng.normal(0, 0.00012, N)], 1)
Rt = tilt_mats(rng, N, 9.0)
cv, cf = tmpl("cube")
col = lin(dots[:, 2:5])
tiles = tile(sc, "moon", cv, cf, trs(pos, np.stack([np.full(N, side), np.full(N, side), np.full(N, 0.00007)], 1), Rt), {"col": col}, smooth=False)
tiles.parent = rig
mt, ntt, bt, _ = new_mat("tile"); at = ntt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "col"
ntt.links.new(at.outputs["Color"], bt.inputs["Base Color"]); ntt.links.new(at.outputs["Color"], bt.inputs["Emission Color"])
setin(bt, "Emission Strength", 0.45); setin(bt, "Roughness", 0.6)
tiles.data.materials.append(mt)

# ---------- light and lens ----------
if LIGHT == "studio":
    area_light(sc, "key", KEY["loc"], (0, 0, 0.02), KEY["size"], KEY["power"], KEY["color"])
    area_light(sc, "fill", FILL["loc"], (0, 0, 0.02), FILL["size"], FILL["power"], FILL["color"])
else:
    sun, frm = sun_light(sc, "sun", SUN["elev"], SUN["azim"], SUN["strength"], SUN["color"], SUN["angle"])
    wn = sc.world.node_tree
    for n in list(wn.nodes): wn.nodes.remove(n)
    sky = wn.nodes.new("ShaderNodeTexSky"); sky.sky_type = "MULTIPLE_SCATTERING"; sky.sun_disc = False
    sky.sun_elevation = math.radians(SUN["elev"]); sky.sun_rotation = math.radians(90 - SUN["azim"])
    bgs = wn.nodes.new("ShaderNodeBackground"); bgs.inputs[1].default_value = SKY["strength"]
    bg2 = wn.nodes.new("ShaderNodeBackground"); bg2.inputs[0].default_value = (*SKY["bounce"], 1); bg2.inputs[1].default_value = SKY["bounce_strength"]
    addw = wn.nodes.new("ShaderNodeAddShader"); wo = wn.nodes.new("ShaderNodeOutputWorld")
    wn.links.new(sky.outputs[0], bgs.inputs[0]); wn.links.new(bgs.outputs[0], addw.inputs[0]); wn.links.new(bg2.outputs[0], addw.inputs[1]); wn.links.new(addw.outputs[0], wo.inputs[0])
if LIGHT == "sun" and LEAVES:
    th = np.linspace(0, 2 * np.pi, 60, endpoint=False)
    rr = (0.42 + 0.58 * np.abs(np.cos(2.5 * (th - np.pi / 2))) ** 0.55) * (0.75 + 0.25 * np.cos((th - np.pi / 2) / 2) ** 2)
    lv = np.concatenate([np.zeros((1, 3)), np.stack([rr * np.cos(th), rr * np.sin(th), np.zeros(60)], 1)])
    lf = np.array([[0, 1 + i, 1 + (i + 1) % 60] for i in range(60)])
    lr = np.random.default_rng(31); land = []
    for (p0, p1, cnt) in LEAVES:
        t = lr.random(cnt); land.append(np.array(p0)[None] * (1 - t[:, None]) + np.array(p1)[None] * t[:, None] + lr.normal(0, 0.03, (cnt, 2)))
    land = np.concatenate(land); NL = len(land)
    lpos = np.concatenate([land, np.zeros((NL, 1))], 1) + np.array(frm)[None] * (1.6 + 1.4 * lr.random(NL))[:, None]
    qv = lr.normal(size=(NL, 4)); qv /= np.linalg.norm(qv, axis=1, keepdims=True); w_, x_, y_, z_ = qv.T
    Rl = np.stack([np.stack([1 - 2 * (y_ * y_ + z_ * z_), 2 * (x_ * y_ - z_ * w_), 2 * (x_ * z_ + y_ * w_)], 1),
                   np.stack([2 * (x_ * y_ + z_ * w_), 1 - 2 * (x_ * x_ + z_ * z_), 2 * (y_ * z_ - x_ * w_)], 1),
                   np.stack([2 * (x_ * z_ - y_ * w_), 2 * (y_ * z_ + x_ * w_), 1 - 2 * (x_ * x_ + y_ * y_)], 1)], 1)
    leaves = tile(sc, "leaves", lv, lf, trs(lpos, 0.04 + 0.03 * lr.random(NL), Rl), smooth=False)
    mlf, _, blf, _ = new_mat("leaf"); setin(blf, "Base Color", (0.10, 0.16, 0.04, 1)); leaves.data.materials.append(mlf)
    leaves.visible_camera = False; leaves.visible_glossy = False

cam = camera(sc, CAM["loc"], CAM["target"], lens=CAM["lens"], fstop=CAM["fstop"])
bpy.context.view_layer.update()
moon_world = rig.matrix_world @ Vector(((mcx - PW / 2) * PX, -(mcy - PH / 2) * PX, zm))
focus_on(cam, moon_world)

os.makedirs(os.path.join(HERE, "drafts"), exist_ok=True)
raw = os.path.join(HERE, "drafts", "exploded_%s_raw.png" % q)
dt = render(sc, raw)
_r = load_px(raw)[..., :3]; print("PROBE ground left-middle sRGB:", (np.median(_r[int(H*0.45):int(H*0.6), int(W*0.1):int(W*0.3)].reshape(-1,3), axis=0) * 255).round(1))
outp = os.path.join(HERE, "drafts", "exploded_%s.png" % q) if q == "draft" else os.path.join(HERE, a[1] if len(a) > 1 else "exploded.png")
finish(raw, outp, grain=0.013, vignette=0.09, seed=7)
if q == "final":
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "exploded.blend"))
print("DONE", outp, "render %.1fs" % dt)
