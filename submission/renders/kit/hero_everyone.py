# H1 "Everyone at once": an ordered field of identical phones lying flat, every one on the real Locked screen,
# receding into the app's night. Opaque, background exactly #080706, every frame-edge pixel that colour.
# usage: blender -b -P hero_everyone.py -- [test]
import sys, os, json, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from phone import *

# ---------------- key choices ----------------
NIGHT     = "#080706"
CASE      = "#B4775E"
PITCH_X, PITCH_Y = HX * 2 + 0.034, HY * 2 + 0.046      # phone spacing across and along the rows
CAM_H     = 0.50                       # camera height above the plane
LENS, FSTOP = 35.0, 2.8
PITCH_DEG = 14.5                       # camera looks 14.5 deg below level: nearest row is seen from about 30 deg above the plane
YAW_DEG   = 0.0                        # square to the rows, so every row is level in the frame
VANISH_X  = 0.69                       # lens shift puts the vanishing point here across the frame: the rows recede up and to the right
FIRST_AT  = (0.31, 0.875)              # where the first phone (front-left corner of the field) sits in the frame (x, y from top-left, 0..1)
FADE_RIGHT = (0.80, 0.955)             # phones dim to nothing between these frame x positions
FADE_FAR   = (1.8, 7.0)                # and between these distances from the camera (metres)
RIM       = dict(elev=24.0, azim=62.0, strength=3.0, color=(0.62, 0.76, 1.0))   # faint cool light from behind-right
W, H, SPP = 2560, 1440, 1400
# ---------------------------------------------

TEST = "test" in args(); VARIANT_B = "b" in args()
SCREEN_GAIN = 1.0; CASE_COL = srgb(CASE); OUTNAME = "hero_everyone"; CASE_FADE_POWER = 1.0
if VARIANT_B:
    # brighter where it counts: what is drawn on the screens 1.6x (linear), a warmer and stronger rim on a browner case, light held further back
    SCREEN_GAIN = 1.6; CASE_COL = srgb(CASE_HEX); OUTNAME = "hero_everyone_b"
    RIM = dict(elev=24.0, azim=62.0, strength=4.6, color=(1.0, 0.82, 0.64)); FADE_FAR = (4.5, 12.5); CASE_FADE_POWER = 2.6
VARIANT_ALONE = "alone" in args()
ALONE_COL = 2                          # pair_alone: the one locked phone is the third in the nearest row (a little left of the field's centre)
SPILL = 0.035                          # watts of spill light per lit phone
BUSY_BRIGHT = 1.0                      # emission of the busy screens (1 = display white where the wash is white)
if VARIANT_ALONE:
    # the "before" of the pair: hero_everyone_b's camera, grid, fade and rim, but every screen on except one
    SCREEN_GAIN = 1.6; CASE_COL = srgb(CASE_HEX); OUTNAME = "pair_alone"
    RIM = dict(elev=24.0, azim=62.0, strength=4.6, color=(1.0, 0.82, 0.64)); FADE_FAR = (4.5, 12.5); CASE_FADE_POWER = 2.6
sc = reset()
if TEST: W, H, SPP = 1280, 720, 200
cycles(sc, W, H, SPP, view="Standard", look="None", exposure=0.0)
sc.cycles.use_denoising = False; sc.cycles.adaptive_threshold = 0.005; sc.cycles.adaptive_min_samples = 128; sc.cycles.filter_width = 1.3
sc.render.dither_intensity = 0.0; sc.render.image_settings.color_depth = "8"
night = srgb(NIGHT)
# the world is the night colour to the camera and gives no light
wn = sc.world.node_tree
for n in list(wn.nodes): wn.nodes.remove(n)
bgc = wn.nodes.new("ShaderNodeBackground"); bgc.inputs[0].default_value = (*night, 1); bgc.inputs[1].default_value = 1.0
bgk = wn.nodes.new("ShaderNodeBackground"); bgk.inputs[1].default_value = 0.0
lpw = wn.nodes.new("ShaderNodeLightPath"); mxw = wn.nodes.new("ShaderNodeMixShader"); wo = wn.nodes.new("ShaderNodeOutputWorld")
wn.links.new(lpw.outputs["Is Camera Ray"], mxw.inputs[0]); wn.links.new(bgk.outputs[0], mxw.inputs[1]); wn.links.new(bgc.outputs[0], mxw.inputs[2])
wn.links.new(mxw.outputs[0], wo.inputs[0])

me = phone_mesh(seg=14)
img = bpy.data.images.load(os.path.join(SCREENS, "locked.png"))
ms = bpy.data.materials.new("screen"); ms.use_nodes = True
screen_nodes(ms.node_tree, img, camera_only=True, dim_from_object=True, bg=night, gain=SCREEN_GAIN)

def fading(name, base, rough, spec):
    """A surface that dissolves into the night colour as the object's own colour goes to 0."""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"); out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    setin(b, "Base Color", (*base, 1)); setin(b, "Roughness", rough); setin(b, "Specular IOR Level", spec)
    oi = nt.nodes.new("ShaderNodeObjectInfo"); sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(oi.outputs["Color"], sep.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*night, 1)
    mix = nt.nodes.new("ShaderNodeMixShader")
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = "POWER"; nt.links.new(sep.outputs[0], pw.inputs[0]); pw.inputs[1].default_value = CASE_FADE_POWER   # in variant b the cases let go before the moons do
    nt.links.new(pw.outputs[0], mix.inputs[0]); nt.links.new(em.outputs[0], mix.inputs[1]); nt.links.new(b.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"]); return m
mc = fading("case", CASE_COL, 0.6, 0.3); mb = fading("bezel", (0.0028, 0.0026, 0.0024), 1.0, 0.0)
HERE_ = os.path.dirname(os.path.abspath(__file__))

def make_wash_atlas(path, nx=16, ny=8, tw=96, th=208, seed=3):
    """128 different lit screens, none of them an interface: a few large soft blocks of muted colour and light each."""
    rng = np.random.default_rng(seed); A = np.zeros((ny * th, nx * tw, 3), np.float32)
    def hsv(h, s_, v):
        i = int(h * 6) % 6; f = h * 6 - int(h * 6); p_, q, t_ = v * (1 - s_), v * (1 - f * s_), v * (1 - (1 - f) * s_)
        return np.array([(v, t_, p_), (q, v, p_), (p_, v, t_), (p_, q, v), (t_, p_, v), (v, p_, q)][i], np.float32)
    xs = np.linspace(0, 1, tw)[None, :, None]; ys = np.linspace(0, 1, th)[:, None, None]
    for j in range(ny):
        for i in range(nx):
            m = rng.random()
            base = hsv(rng.random(), 0.04, rng.uniform(0.88, 0.97)) if m < 0.55 else (hsv(rng.random(), 0.1, rng.uniform(0.08, 0.14)) if m < 0.78 else hsv(rng.random(), 0.14, 0.80))
            t = np.tile(base[None, None], (th, tw, 1))
            if rng.random() < 0.3:                       # one picture filling the screen
                c1, c2 = hsv(rng.random(), rng.uniform(0.10, 0.34), rng.uniform(0.55, 0.95)), hsv(rng.random(), rng.uniform(0.08, 0.30), rng.uniform(0.3, 0.8))
                t = c1[None, None] * (1 - ys) + c2[None, None] * ys + 0 * xs
                bx, by = rng.random(), rng.uniform(0.2, 0.7)
                t = t + 0.35 * np.exp(-(((xs - bx) / 0.35) ** 2 + ((ys - by) / 0.2) ** 2))
            else:                                        # a few blocks down the screen
                y = int(th * rng.uniform(0.07, 0.14))
                while y < th - 10:
                    hgt = int(th * rng.uniform(0.18, 0.42)); mg = int(rng.choice([0, 0, 6]))
                    c1, c2 = hsv(rng.random(), rng.uniform(0.08, 0.34), rng.uniform(0.5, 0.95)), hsv(rng.random(), rng.uniform(0.06, 0.30), rng.uniform(0.4, 0.9))
                    blk = c1[None, None] * (1 - xs[:, mg:tw - mg]) + c2[None, None] * xs[:, mg:tw - mg]
                    t[y:y + hgt, mg:tw - mg] = blk
                    y += hgt + int(th * rng.uniform(0.06, 0.16))
            A[j * th:(j + 1) * th, i * tw:(i + 1) * tw] = blur(np.clip(t, 0, 1), 5.0)
    save_px(A, path)
    means = A.reshape(ny, th, nx, tw, 3).mean((1, 3))          # each screen's average colour, for the light it spills
    return nx, ny, means

if VARIANT_ALONE:
    atlas_path = os.path.join(HERE_, "work", "wash_atlas.png"); NXA, NYA, WASH_MEAN = make_wash_atlas(atlas_path)
    mbusy = bpy.data.materials.new("busy"); mbusy.use_nodes = True; nb = mbusy.node_tree
    for n in list(nb.nodes): nb.nodes.remove(n)
    tcb = nb.nodes.new("ShaderNodeTexCoord"); mpb = nb.nodes.new("ShaderNodeMapping")
    mpb.inputs["Scale"].default_value = (0.90 / SW / NXA, 0.90 / SH / NYA, 1); mpb.inputs["Location"].default_value = (0.5 / NXA, 0.5 / NYA, 0)
    oib = nb.nodes.new("ShaderNodeObjectInfo"); spb = nb.nodes.new("ShaderNodeSeparateColor"); nb.links.new(oib.outputs["Color"], spb.inputs[0])
    cmb = nb.nodes.new("ShaderNodeCombineXYZ"); nb.links.new(spb.outputs[1], cmb.inputs[0]); nb.links.new(spb.outputs[2], cmb.inputs[1])
    adb = nb.nodes.new("ShaderNodeVectorMath"); adb.operation = "ADD"
    txb = nb.nodes.new("ShaderNodeTexImage"); txb.image = bpy.data.images.load(atlas_path); txb.interpolation = "Linear"; txb.extension = "REPEAT"
    mxb = nb.nodes.new("ShaderNodeMix"); mxb.data_type = "RGBA"; mxb.inputs["A"].default_value = (*night, 1)
    emb = nb.nodes.new("ShaderNodeEmission"); emb.inputs["Strength"].default_value = BUSY_BRIGHT; omb = nb.nodes.new("ShaderNodeOutputMaterial")
    nb.links.new(tcb.outputs["Object"], mpb.inputs["Vector"]); nb.links.new(mpb.outputs["Vector"], adb.inputs[0]); nb.links.new(cmb.outputs[0], adb.inputs[1])
    nb.links.new(adb.outputs[0], txb.inputs["Vector"]); nb.links.new(spb.outputs[0], mxb.inputs["Factor"]); nb.links.new(txb.outputs["Color"], mxb.inputs["B"])
    nb.links.new(mxb.outputs["Result"], emb.inputs["Color"]); nb.links.new(emb.outputs[0], omb.inputs["Surface"])
    for m_ in (mc, mb, mbusy): me.materials.append(m_)
    # a dark floor that takes a little of the screens' light and is otherwise exactly the night colour
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 20, 0)); floor = bpy.context.object
    mf = bpy.data.materials.new("floor"); mf.use_nodes = True; nf = mf.node_tree
    bf = next(n for n in nf.nodes if n.type == "BSDF_PRINCIPLED"); of = next(n for n in nf.nodes if n.type == "OUTPUT_MATERIAL")
    setin(bf, "Base Color", (0.030, 0.028, 0.026, 1)); setin(bf, "Roughness", 0.5); setin(bf, "Specular IOR Level", 0.35)
    ef = nf.nodes.new("ShaderNodeEmission"); ef.inputs["Color"].default_value = (*night, 1); lf = nf.nodes.new("ShaderNodeLightPath")
    nf.links.new(lf.outputs["Is Camera Ray"], ef.inputs["Strength"]); af = nf.nodes.new("ShaderNodeAddShader")
    nf.links.new(ef.outputs[0], af.inputs[0]); nf.links.new(bf.outputs[0], af.inputs[1]); nf.links.new(af.outputs[0], of.inputs["Surface"])
    floor.data.materials.append(mf)
    sc.cycles.use_denoising = True; sc.cycles.samples = 300 if TEST else 1600; sc.cycles.adaptive_threshold = 0.01
else:
    for m_ in (mc, mb, ms): me.materials.append(m_)
anchors = {}; rng_t = np.random.default_rng(12)
phones_coll = bpy.data.collections.new("phones"); floor_coll = bpy.data.collections.new("floor")
if VARIANT_ALONE: floor_coll.objects.link(floor)

# camera
cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
cd.lens = LENS; cd.sensor_width = 36.0; cd.clip_start = 0.05; cd.clip_end = 60; cd.shift_x = 0.5 - VANISH_X
yaw, pit = math.radians(YAW_DEG), math.radians(PITCH_DEG)
fwd = Vector((-math.sin(yaw) * math.cos(pit), math.cos(yaw) * math.cos(pit), -math.sin(pit)))
cam.location = (0, 0, CAM_H); cam.rotation_euler = fwd.to_track_quat("-Z", "Y").to_euler()
bpy.context.view_layer.update()
Mw = cam.matrix_world; right = (Mw.to_3x3() @ Vector((1, 0, 0))); up = (Mw.to_3x3() @ Vector((0, 1, 0)))
tx = 18.0 / LENS; ty = tx * H / W                    # tan of the half field of view, across and up
def ground_at(u, v, z=HC):
    d = fwd + right * ((u - VANISH_X) * 2 * tx) + up * ((0.5 - v) * 2 * ty)
    t = (z - CAM_H) / d.z; return Vector((0, 0, CAM_H)) + d * t
def frame_of(p):
    q = Vector(p) - Vector((0, 0, CAM_H)); zc = q.dot(fwd)
    return VANISH_X + q.dot(right) / zc / (2 * tx), 0.5 - q.dot(up) / zc / (2 * ty)
G0 = ground_at(*FIRST_AT)
smooth = lambda t: max(0.0, min(1.0, t)) ** 2 * (3 - 2 * max(0.0, min(1.0, t)))
count = 0; rows = int((FADE_FAR[1] - 0.6) / PITCH_Y) + 1
for r in range(rows):
    for c in range(0, 80):
        p = Vector((G0.x + c * PITCH_X, G0.y + r * PITCH_Y, 0.0))
        u, v = frame_of(p + Vector((0, 0, HC)))
        if u > FADE_RIGHT[1] + 0.02: break
        dist = (p - Vector((0, 0, CAM_H))).length
        dim = smooth((FADE_RIGHT[1] - u) / (FADE_RIGHT[1] - FADE_RIGHT[0])) * smooth((FADE_FAR[1] - dist) / (FADE_FAR[1] - FADE_FAR[0])) ** 1.3
        if dim <= 0.004 or v < 0.02: continue
        ob = bpy.data.objects.new("p_%d_%d" % (r, c), me); sc.collection.objects.link(ob)
        ob.location = p; ob.color = (dim, dim, dim, 1.0); count += 1
        if VARIANT_ALONE:
            ti, tj = int(rng_t.integers(0, NXA)), int(rng_t.integers(0, NYA))
            ob.color = (dim, ti / NXA, tj / NYA, 1.0); phones_coll.objects.link(ob)
            if not (r == 0 and c == ALONE_COL):
                # the light a lit screen spills around itself: a small soft lamp over each phone, unseen, blocked by nothing but the floor
                ld = bpy.data.lights.new("spill", "AREA"); ld.shape = "DISK"; ld.size = 0.09; lo = bpy.data.objects.new("spill", ld); sc.collection.objects.link(lo)
                lo.location = (p.x, p.y, 0.055); ld.energy = SPILL * dim; ld.color = tuple(float(v) for v in lin(WASH_MEAN[NYA - 1 - tj, ti] * 255))
                lo.light_linking.blocker_collection = floor_coll; lo.visible_camera = False
            if r == 0 and c == ALONE_COL:
                ob.material_slots[2].link = "OBJECT"; ob.material_slots[2].material = ms
                uc, vc = frame_of(p + Vector((0, 0, HC))); anchors["locked_phone_centre_px"] = [round(uc * W, 1), round(vc * H, 1)]
print("phones:", count, "rows:", rows, "first at", tuple(round(x, 3) for x in G0))

rim_ob, _ = sun_light(sc, "rim", RIM["elev"], RIM["azim"], RIM["strength"], RIM["color"], 3.0)
if VARIANT_ALONE: rim_ob.light_linking.receiver_collection = phones_coll      # the rim touches the phones, never the floor
cd.dof.use_dof = True; cd.dof.aperture_fstop = FSTOP; cd.dof.aperture_blades = 0
focus_pt = Vector((G0.x + 1.5 * PITCH_X, G0.y + 0.62 * PITCH_Y, HC))      # between the first and second rows, a little nearer the second
cd.dof.focus_distance = (focus_pt - Vector((0, 0, CAM_H))).dot(fwd)

out = os.path.join(HERE_, "work", OUTNAME + "_test.png") if TEST else os.path.join(HERE_, OUTNAME + ".png")
sc.render.image_settings.color_mode = "RGB"
t = time.time(); sc.render.filepath = out; bpy.ops.render.render(write_still=True); print("RENDERED %.1fs" % (time.time() - t))
if VARIANT_ALONE:
    # melt the last 70 px into the night colour and snap near-night pixels to it, so the frame has no border on a night slide
    im = load_px(out)[..., :3].astype(np.float64); nd = np.array([8, 7, 6]) / 255.0
    yy, xx = np.mgrid[0:H, 0:W]; dd = np.minimum(np.minimum(xx, W - 1 - xx), np.minimum(yy, H - 1 - yy)) / (70.0 * W / 2560)
    mm = np.clip(dd, 0, 1); mm = mm * mm * (3 - 2 * mm)
    im = nd + (im - nd) * mm[..., None]
    near = (np.abs(im - nd).max(-1) * 255) <= 1.5; im[near] = nd
    save_px(im.astype(np.float32), out)
    anchors["frame"] = [W, H]; json.dump(anchors, open(os.path.join(HERE_, "work" if TEST else "", OUTNAME + "_anchors.json"), "w")); print("ANCHORS", anchors)
p = (load_px(out)[..., :3] * 255).round().astype(int)
edge = np.concatenate([p[0], p[-1], p[:, 0], p[:, -1]])
print("EDGE pixels: min", edge.min(0), "max", edge.max(0), " not (8,7,6):", int((edge != np.array([8, 7, 6])).any(1).sum()), "of", len(edge))
print("corner block top-left 40% x 40%: max", p[:int(H * 0.4), :int(W * 0.4)].reshape(-1, 3).max(0))
if not TEST: bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE_, OUTNAME + ".blend"))
