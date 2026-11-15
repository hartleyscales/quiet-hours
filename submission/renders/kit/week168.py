# The week as 168 phones, one per hour: 24 across (hours) by 7 down (days), lying flat, seen from directly above
# (orthographic). 166 are asleep (dark glass); two are awake on the real Locked screen: row 4, columns 18 and 19
# (Thursday, 5 PM and 6 PM). Transparent film with a soft shadow, and a _noshadow twin. Anchors written beside it.
# usage: blender -b -P week168.py -- [test]
import sys, os, json, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from phone import *

# ---------------- key choices ----------------
COLS, ROWS = 24, 7
PITCH_X, PITCH_Y = 0.1313, 0.1731            # wider apart sideways than in depth: the grid comes out 2.6 to 1
AWAKE     = [(4, 18), (4, 19)]               # (row, column), counting from 1, row 1 at the top
PX_PER_MM = 1.2                              # a phone is 86 x 181 px
MARGIN_MM = 36.0                             # even margin around the grid (the shadows fall inside it)
CASE_GAIN = 0.84
KEY       = dict(elev=38.0, azim=135.0, strength=5.2)    # raking sun from the upper left, on the phones only
TOPFILL   = 1.10                                         # soft light from straight above, no highlight
SHADOW    = dict(elev=38.0, azim=135.0, strength=3.0, angle=14.0, base=5.0)   # the floor's own pair of lights: small soft shadow to the lower right
SAMPLES   = 700
# ---------------------------------------------

TEST = "test" in args(); VARIANT_B = "b" in args()
OUT = "week168_b" if VARIANT_B else "week168"
PALE = (0.30, 0.80, 0.18)                     # variant b: washes keep 30% of their colour and sit between 80% and 98% value
HERE_ = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE_, "work"); os.makedirs(WORK, exist_ok=True)
GW = (COLS - 1) * PITCH_X + 2 * HX; GH = (ROWS - 1) * PITCH_Y + 2 * HY
k = PX_PER_MM * (0.5 if TEST else 1.0)
W = int(round((GW * 1000 + 2 * MARGIN_MM) * k)); H = int(round((GH * 1000 + 2 * MARGIN_MM) * k))
sc = reset()
cycles(sc, W, H, 128 if TEST else SAMPLES, view="Standard", look="None", exposure=0.0)
sc.cycles.use_denoising = False; sc.cycles.adaptive_threshold = 0.004; sc.cycles.adaptive_min_samples = 96; sc.cycles.filter_width = 1.2
sc.render.film_transparent = True; sc.render.dither_intensity = 0.0
sc.render.image_settings.color_mode = "RGBA"; sc.render.image_settings.color_depth = "8"
world_color(sc, (0, 0, 0), 0.0)

def mat_simple(name, base, rough, spec):
    m, nt, b, _ = new_mat(name); setin(b, "Base Color", (*base, 1)); setin(b, "Roughness", rough); setin(b, "Specular IOR Level", spec); return m
m_case = mat_simple("case", tuple(np.array(srgb(CASE_HEX)) * CASE_GAIN), 0.66, 0.22)
m_glass = mat_simple("asleep_glass", (0.0125, 0.0120, 0.0116), 1.0, 0.0)      # asleep: flat charcoal glass, a step lighter than the night screen
m_bezel = mat_simple("bezel", (0.0028, 0.0026, 0.0024), 1.0, 0.0)
m_locked = bpy.data.materials.new("locked"); m_locked.use_nodes = True
screen_nodes(m_locked.node_tree, bpy.data.images.load(os.path.join(SCREENS, "locked.png")), camera_only=True)

me = phone_mesh(seg=12)
if VARIANT_B:
    # the 166 ordinary hours are ON: pair_alone's washes, made pale and quiet; seen only by the camera, like every screen in the kit
    atlas_path = os.path.join(WORK, "wash_atlas_pale.png"); NXA, NYA, _ = make_wash_atlas(atlas_path, pale=PALE)
    m_on = bpy.data.materials.new("on"); m_on.use_nodes = True; nb = m_on.node_tree
    for n in list(nb.nodes): nb.nodes.remove(n)
    tcb = nb.nodes.new("ShaderNodeTexCoord"); mpb = nb.nodes.new("ShaderNodeMapping")
    mpb.inputs["Scale"].default_value = (0.90 / SW / NXA, 0.90 / SH / NYA, 1); mpb.inputs["Location"].default_value = (0.5 / NXA, 0.5 / NYA, 0)
    oib = nb.nodes.new("ShaderNodeObjectInfo"); spb = nb.nodes.new("ShaderNodeSeparateColor"); nb.links.new(oib.outputs["Color"], spb.inputs[0])
    cmb = nb.nodes.new("ShaderNodeCombineXYZ"); nb.links.new(spb.outputs[1], cmb.inputs[0]); nb.links.new(spb.outputs[2], cmb.inputs[1])
    adb = nb.nodes.new("ShaderNodeVectorMath"); adb.operation = "ADD"
    txb = nb.nodes.new("ShaderNodeTexImage"); txb.image = bpy.data.images.load(atlas_path); txb.interpolation = "Linear"; txb.extension = "REPEAT"
    emb = nb.nodes.new("ShaderNodeEmission"); dkb = nb.nodes.new("ShaderNodeBsdfDiffuse"); dkb.inputs["Color"].default_value = (0.003, 0.003, 0.003, 1)
    lpb = nb.nodes.new("ShaderNodeLightPath"); mxb = nb.nodes.new("ShaderNodeMixShader"); omb = nb.nodes.new("ShaderNodeOutputMaterial")
    nb.links.new(tcb.outputs["Object"], mpb.inputs["Vector"]); nb.links.new(mpb.outputs["Vector"], adb.inputs[0]); nb.links.new(cmb.outputs[0], adb.inputs[1])
    nb.links.new(adb.outputs[0], txb.inputs["Vector"]); nb.links.new(txb.outputs["Color"], emb.inputs["Color"])
    nb.links.new(lpb.outputs["Is Camera Ray"], mxb.inputs[0]); nb.links.new(dkb.outputs[0], mxb.inputs[1]); nb.links.new(emb.outputs[0], mxb.inputs[2]); nb.links.new(mxb.outputs[0], omb.inputs["Surface"])
    for m_ in (m_case, m_bezel, m_on): me.materials.append(m_)
else:
    for m_ in (m_case, m_glass, m_glass): me.materials.append(m_)
rng_t = np.random.default_rng(21)
phones = bpy.data.collections.new("phones"); floor_c = bpy.data.collections.new("floor")
x0 = -GW / 2 + HX; y0 = GH / 2 - HY                       # centre of the top-left phone
fx0 = -GW / 2 - MARGIN_MM / 1000; fy0 = GH / 2 + MARGIN_MM / 1000    # frame's top-left corner in the world
anchors = {"frame": [W, H], "phone_px": [round(2 * HX * 1000 * k, 1), round(2 * HY * 1000 * k, 1)], "pitch_px": [round(PITCH_X * 1000 * k, 2), round(PITCH_Y * 1000 * k, 2)]}
def px_of(x, y): return [round((x - fx0) * 1000 * k, 1), round((fy0 - y) * 1000 * k, 1)]
for r in range(1, ROWS + 1):
    for c in range(1, COLS + 1):
        ob = bpy.data.objects.new("h_%d_%d" % (r, c), me); sc.collection.objects.link(ob); phones.objects.link(ob)
        x, y = x0 + (c - 1) * PITCH_X, y0 - (r - 1) * PITCH_Y; ob.location = (x, y, 0); ob.visible_diffuse = False
        if VARIANT_B: ob.color = (1.0, int(rng_t.integers(0, NXA)) / NXA, int(rng_t.integers(0, NYA)) / NYA, 1.0)
        if (r, c) in AWAKE:
            ob.material_slots[1].link = "OBJECT"; ob.material_slots[1].material = m_bezel
            ob.material_slots[2].link = "OBJECT"; ob.material_slots[2].material = m_locked
            anchors.setdefault("awake_px", []).append(px_of(x, y))
        if (r, c) == (1, 1): anchors["top_left_px"] = px_of(x, y)
        if (r, c) == (ROWS, COLS): anchors["bottom_right_px"] = px_of(x, y)

bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0)); floor = bpy.context.object
floor.data.materials.append(mat_simple("floor", (0.80, 0.78, 0.75), 1.0, 0.0)); floor.is_shadow_catcher = True; floor_c.objects.link(floor)

key, _ = sun_light(sc, "key", KEY["elev"], KEY["azim"], KEY["strength"], (1.0, 0.985, 0.96), 8.0); key.light_linking.receiver_collection = phones
top, _ = sun_light(sc, "top", 90.0, 0.0, TOPFILL, (1, 1, 1), 30.0); top.light_linking.receiver_collection = phones; top.data.specular_factor = 0.0
sh, _ = sun_light(sc, "shadow", SHADOW["elev"], SHADOW["azim"], SHADOW["strength"], (1, 1, 1), SHADOW["angle"]); sh.light_linking.receiver_collection = floor_c
bs, _ = sun_light(sc, "base", 90.0, 0.0, SHADOW["base"], (1, 1, 1), 1.0); bs.light_linking.receiver_collection = floor_c; bs.light_linking.blocker_collection = floor_c

cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
cd.type = "ORTHO"; cd.ortho_scale = W / (1000 * k); cd.clip_start = 0.1; cd.clip_end = 10      # ortho_scale is the frame's width in metres
cam.location = (0, 0, 2.0); cam.rotation_euler = (0, 0, 0)

def render_to(path):
    t = time.time(); sc.render.filepath = path; bpy.ops.render.render(write_still=True); return time.time() - t
outdir = WORK if TEST else HERE_
t1 = render_to(os.path.join(outdir, OUT + ".png"))
floor.visible_camera = False
t2 = render_to(os.path.join(outdir, OUT + "_noshadow.png"))
json.dump(anchors, open(os.path.join(outdir, OUT + "_anchors.json"), "w"), indent=1)
print("RENDERED %.1fs %.1fs  frame %d x %d  grid aspect %.2f" % (t1, t2, W, H, GW / GH)); print("ANCHORS", anchors)
# check the anchors against the picture: the opaque box of the render should run from the first phone's left edge to the last one's right edge
p = load_px(os.path.join(outdir, OUT + "_noshadow.png")); al = p[..., 3]; ys, xs = np.nonzero(al > 0.5)
print("opaque box x %d..%d y %d..%d ; expected x %.1f..%.1f y %.1f..%.1f" % (xs.min(), xs.max(), ys.min(), ys.max(),
      anchors["top_left_px"][0] - HX * 1000 * k, anchors["bottom_right_px"][0] + HX * 1000 * k, anchors["top_left_px"][1] - HY * 1000 * k, anchors["bottom_right_px"][1] + HY * 1000 * k))
ps = load_px(os.path.join(outdir, OUT + ".png"))[..., 3]
print("edge alpha max (0-255): top %.0f bottom %.0f left %.0f right %.0f" % (ps[0].max() * 255, ps[-1].max() * 255, ps[:, 0].max() * 255, ps[:, -1].max() * 255))
if not TEST: bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE_, OUT + ".blend"))
