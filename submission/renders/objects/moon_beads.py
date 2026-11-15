# The moon of beads: the Locked screen's night moon, one ball-head pin per dot (3,098 = "3,098 Trojans in"),
# pushed into a near-black felt board in the app's true dot layout (web/moon.js, N = 3098).
# usage: blender -b -P moon_beads.py -- <wide|close> <draft|final>
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

# ---------------- key choices ----------------
PITCH   = 0.002            # 2 mm between dots (the app's 2 pt cell) -> moon is 232 mm across
BEAD_R  = 0.00070          # bead radius (the app's dot is 1.33 of a 2 pt cell)
KEY     = dict(loc=(-0.80, 0.10, 0.20), size=0.07, size_y=0.34, power=95, color=(1.0, 0.80, 0.58))   # low, warm, from the left (~14 deg)
FILL    = dict(loc=(0.5, -0.3, 1.2), size=1.2, power=1.1, color=(0.72, 0.82, 1.0))                   # barely-there cool top fill
FELT    = "#0B0A09"        # near-black felt, a hair above the app's night #080706 so the nap can catch light
SHOTS = {
    # moon sits left of centre; the right third falls away into dark felt for the slide's words
    "wide":  dict(cam=(0.30, -0.80, 0.93), target=(0.078, 0.004, 0), focus=(0.0, -0.045, BEAD_R * 2), lens=100, fstop=2.0, exposure=-0.45),
    # single beads distinct: low across the lower-right limb, looking toward the light
    "close": dict(cam=(0.165, -0.285, 0.165), target=(0.118, -0.022, 0.0), focus=(0.104, -0.030, 0.002), lens=150, fstop=12.0, exposure=-0.45),
}
# ---------------------------------------------

a = args(); shot = a[0] if a else "wide"; q = a[1] if len(a) > 1 else "draft"
S = SHOTS[shot]
sc = reset()
W, H, SPP = (1280, 720, 160) if q == "draft" else (2560, 1440, 900)
cycles(sc, W, H, SPP, view="AgX", look="AgX - Medium High Contrast", exposure=S["exposure"])
world_color(sc, (0, 0, 0), 0.0)

d = json.load(open(os.path.join(HERE, "data", "moon_3098.json")))
dots = np.array(d["dots"], dtype=np.float64); N = len(dots)
rng = np.random.default_rng(11)
x = (dots[:, 0] - d["cx"]) * PITCH + rng.normal(0, 0.00005, N)       # hand-placed: a twentieth of a millimetre of wander
y = -(dots[:, 1] - d["cy"]) * PITCH + rng.normal(0, 0.00005, N)
hgt = 0.0011 + 0.0007 * rng.random(N)                                # pin stands 1.1-1.8 mm proud of the felt
rad = BEAD_R * (0.90 + 0.2 * rng.random(N))
R = tilt_mats(rng, N, 7.0)
up = R[:, :, 2]
head = np.stack([x, y, np.zeros(N)], 1) + up * (hgt + rad)[:, None]

# colour: the app's own per-dot colour, warmed; about a third are pale brass
col = lin(dots[:, 2:5]); print("cell colour mean (linear)", col.mean(0), "min", col.min(0), "max", col.max(0))
lum = col.mean(1, keepdims=True)
cream = np.array(srgb("#EFE4CC")); brass = np.array([0.80, 0.60, 0.30])
shade = (0.55 + 0.75 * (lum / lum.max()))
base = cream[None] * shade * (0.9 + 0.2 * rng.random((N, 1)))
is_brass = rng.random(N) < 0.34
base[is_brass] = brass[None] * (0.75 + 0.35 * rng.random((is_brass.sum(), 1)))
rough = np.where(is_brass, 0.22 + 0.12 * rng.random(N), 0.30 + 0.25 * rng.random(N))

sv, sf = tmpl("sphere", u=28, v=14)
beads = tile(sc, "beads", sv, sf, trs(head, np.stack([rad, rad, rad * 0.94], 1), R),
             {"col": base, "metal": is_brass.astype(np.float32), "rough": rough})
m, nt, b, out = new_mat("bead")
at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "col"
am = nt.nodes.new("ShaderNodeAttribute"); am.attribute_name = "metal"
ar = nt.nodes.new("ShaderNodeAttribute"); ar.attribute_name = "rough"
nt.links.new(at.outputs["Color"], b.inputs["Base Color"])
nt.links.new(am.outputs["Fac"], b.inputs["Metallic"])
nt.links.new(ar.outputs["Fac"], b.inputs["Roughness"])
setin(b, "Coat Weight", 0.6); setin(b, "Coat Roughness", 0.07)
beads.data.materials.append(m)

# pin shanks (steel), from 2 mm inside the felt up into the bead
cv, cf = tmpl("cyl", u=8)
slen = hgt + 0.002 + rad * 0.5
smid = np.stack([x, y, np.zeros(N)], 1) + up * (slen / 2 - 0.002)[:, None]
shank = tile(sc, "shanks", cv, cf, trs(smid, np.stack([np.full(N, 0.00017), np.full(N, 0.00017), slen], 1), R))
ms, nts, bs, _ = new_mat("steel"); setin(bs, "Base Color", (0.55, 0.52, 0.48, 1)); setin(bs, "Metallic", 1.0); setin(bs, "Roughness", 0.3)
shank.data.materials.append(ms)

# felt board
bpy.ops.mesh.primitive_plane_add(size=4.0, location=(0, 0, 0)); felt = bpy.context.object
mf, ntf, bf, outf = new_mat("felt")
tc = ntf.nodes.new("ShaderNodeTexCoord")
n1 = ntf.nodes.new("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = 5200; n1.inputs["Detail"].default_value = 5; n1.inputs["Roughness"].default_value = 0.7
n2 = ntf.nodes.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 420; n2.inputs["Detail"].default_value = 3
n3 = ntf.nodes.new("ShaderNodeTexNoise"); n3.inputs["Scale"].default_value = 14; n3.inputs["Detail"].default_value = 2
for n in (n1, n2, n3): ntf.links.new(tc.outputs["Object"], n.inputs["Vector"])
ramp = ntf.nodes.new("ShaderNodeValToRGB")
fc = np.array(srgb(FELT))
ramp.color_ramp.elements[0].position = 0.38; ramp.color_ramp.elements[0].color = (*(fc * 0.75), 1)
ramp.color_ramp.elements[1].position = 0.80; ramp.color_ramp.elements[1].color = (*(fc * 1.9 + 0.002), 1)
ntf.links.new(n1.outputs["Fac"], ramp.inputs["Fac"])
ntf.links.new(ramp.outputs["Color"], bf.inputs["Base Color"])
setin(bf, "Roughness", 1.0); setin(bf, "Specular IOR Level", 0.1)
setin(bf, "Sheen Weight", 0.035); setin(bf, "Sheen Roughness", 0.5); setin(bf, "Sheen Tint", (0.9, 0.8, 0.66, 1))
add1 = ntf.nodes.new("ShaderNodeMath"); add1.operation = "MULTIPLY_ADD"     # n1*1 + n2*0.6
ntf.links.new(n1.outputs["Fac"], add1.inputs[0]); add1.inputs[1].default_value = 1.0; ntf.links.new(n2.outputs["Fac"], add1.inputs[2])
add2 = ntf.nodes.new("ShaderNodeMath"); add2.operation = "MULTIPLY_ADD"
ntf.links.new(n3.outputs["Fac"], add2.inputs[0]); add2.inputs[1].default_value = 6.0; ntf.links.new(add1.outputs[0], add2.inputs[2])
bump = ntf.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.55; bump.inputs["Distance"].default_value = 0.00025
ntf.links.new(add2.outputs[0], bump.inputs["Height"]); ntf.links.new(bump.outputs["Normal"], bf.inputs["Normal"])
felt.data.materials.append(mf)

# felt nap: real fibres, only where the lens can resolve them
if True:
    fb = fibres(sc, "nap", rng, (0.02, -0.12, 0.26, 0.10), 34) if shot == "close" else fibres(sc, "nap", rng, (-0.22, -0.20, 0.42, 0.30), 12, length=(0.0008, 0.0026), radius=0.000014)
    mh, nth, bh, _ = new_mat("nap"); setin(bh, "Base Color", (0.030, 0.027, 0.024, 1)); setin(bh, "Roughness", 0.8); setin(bh, "Specular IOR Level", 0.3)
    fb.data.materials.append(mh)

# light: one low warm key from the left, a whisper of cool fill
area_light(sc, "key", KEY["loc"], (0.02, 0, 0), KEY["size"], KEY["power"], KEY["color"], size_y=KEY["size_y"])
area_light(sc, "fill", FILL["loc"], (0, 0, 0), FILL["size"], FILL["power"], FILL["color"])

cam = camera(sc, S["cam"], S["target"], lens=S["lens"], fstop=S["fstop"])
bpy.context.view_layer.update(); focus_on(cam, S["focus"])

os.makedirs(os.path.join(HERE, "drafts"), exist_ok=True)
raw = os.path.join(HERE, "drafts", "moon_%s_%s_raw.png" % (shot, q))
dt = render(sc, raw)
outp = os.path.join(HERE, "drafts", "moon_%s_%s.png" % (shot, q)) if q == "draft" else os.path.join(HERE, a[2] if len(a) > 2 else "moon_%s.png" % shot)
finish(raw, outp, grain=0.016, vignette=0.12)
if q == "final":
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "moon_beads_%s.blend" % shot))
print("DONE", outp, "render %.1fs" % dt)
