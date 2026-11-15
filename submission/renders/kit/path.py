# The path to launch in three frames, one camera language (phones lying flat on the real Locked screen, seen from
# about 30 degrees above, warm rim, the app's night all around), growing in scale:
#   path_1  one phone            path_2  a block of 5 x 6 (one residence hall)            path_3  the field receding (the campus)
# Each 1600 x 1200, opaque, every edge pixel exactly #080706, the subject centred with margin.
# usage: blender -b -P path.py -- <1|2|3> [test]
import sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from phone import *

# ---------------- key choices ----------------
NIGHT     = "#080706"
W, H, SPP = 1600, 1200, 1400
PITCH_X, PITCH_Y = HX * 2 + 0.034, HY * 2 + 0.046      # the hero's spacing
ELEV      = 30.0                       # frames 1 and 2: the camera looks at the subject's centre from 30 deg above the plane
FILL_FRAC = {1: 0.40, 2: 0.66}         # how much of the frame the subject's box may take (the larger of width and height)
LENS      = {1: 50.0, 2: 50.0, 3: 35.0}
FSTOP     = {1: 8.0, 2: 5.6, 3: 2.8}
BLOCK     = (5, 6)                     # frame 2: columns x rows
FIELD     = dict(cam_h=0.85, pitch=18.0, first_v=0.80, side=(0.30, 0.43), far=(7.5, 21.0))   # frame 3: hero_everyone_b's field, vanishing point centred
SCREEN_GAIN = 1.6                      # what is drawn on the screens, 1.6x in linear light, as in hero_everyone_b
RIM       = dict(elev=24.0, azim=62.0, strength=4.6, color=(1.0, 0.82, 0.64))
CASE_FADE_POWER = 2.6
# ---------------------------------------------

a = args(); WHICH = int(a[0]) if a else 1; TEST = "test" in a
sc = reset()
if TEST: W, H, SPP = W // 2, H // 2, 200
cycles(sc, W, H, SPP, view="Standard", look="None", exposure=0.0)
sc.cycles.use_denoising = False; sc.cycles.adaptive_threshold = 0.005; sc.cycles.adaptive_min_samples = 128; sc.cycles.filter_width = 1.3
sc.render.dither_intensity = 0.0; sc.render.image_settings.color_depth = "8"; sc.render.image_settings.color_mode = "RGB"
night = srgb(NIGHT)
wn = sc.world.node_tree
for n in list(wn.nodes): wn.nodes.remove(n)
bgc = wn.nodes.new("ShaderNodeBackground"); bgc.inputs[0].default_value = (*night, 1)
bgk = wn.nodes.new("ShaderNodeBackground"); bgk.inputs[1].default_value = 0.0
lpw = wn.nodes.new("ShaderNodeLightPath"); mxw = wn.nodes.new("ShaderNodeMixShader"); wo = wn.nodes.new("ShaderNodeOutputWorld")
wn.links.new(lpw.outputs["Is Camera Ray"], mxw.inputs[0]); wn.links.new(bgk.outputs[0], mxw.inputs[1]); wn.links.new(bgc.outputs[0], mxw.inputs[2]); wn.links.new(mxw.outputs[0], wo.inputs[0])

me = phone_mesh(seg=24 if WHICH == 1 else 14)
ms = bpy.data.materials.new("screen"); ms.use_nodes = True
screen_nodes(ms.node_tree, bpy.data.images.load(os.path.join(SCREENS, "locked.png")), camera_only=True, dim_from_object=True, bg=night, gain=SCREEN_GAIN)
def fading(name, base, rough, spec):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"); out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    setin(b, "Base Color", (*base, 1)); setin(b, "Roughness", rough); setin(b, "Specular IOR Level", spec)
    oi = nt.nodes.new("ShaderNodeObjectInfo"); sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(oi.outputs["Color"], sep.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*night, 1); mix = nt.nodes.new("ShaderNodeMixShader")
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = "POWER"; nt.links.new(sep.outputs[0], pw.inputs[0]); pw.inputs[1].default_value = CASE_FADE_POWER
    nt.links.new(pw.outputs[0], mix.inputs[0]); nt.links.new(em.outputs[0], mix.inputs[1]); nt.links.new(b.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"]); return m
for m_ in (fading("case", srgb(CASE_HEX), 0.6, 0.3), fading("bezel", (0.0028, 0.0026, 0.0024), 1.0, 0.0), ms): me.materials.append(m_)

cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
cd.lens = LENS[WHICH]; cd.sensor_width = 36.0; cd.clip_start = 0.02; cd.clip_end = 80
tx = 18.0 / cd.lens; ty = tx * H / W
def aim(loc, fwd):
    cam.location = loc; cam.rotation_euler = Vector(fwd).to_track_quat("-Z", "Y").to_euler(); bpy.context.view_layer.update()
    R = cam.matrix_world.to_3x3(); return Vector(loc), Vector(fwd).normalized(), R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0))
def project(p, C, F, Rt, Up, u0=0.5, v0=0.5):
    q = Vector(p) - C; zc = q.dot(F); return u0 + q.dot(Rt) / zc / (2 * tx), v0 - q.dot(Up) / zc / (2 * ty)
smooth = lambda t: max(0.0, min(1.0, t)) ** 2 * (3 - 2 * max(0.0, min(1.0, t)))
def put(p, dim=1.0):
    ob = bpy.data.objects.new("p", me); sc.collection.objects.link(ob); ob.location = p; ob.color = (dim, dim, dim, 1)

if WHICH in (1, 2):
    cols, rows = (1, 1) if WHICH == 1 else BLOCK
    pts = [Vector(((c - (cols - 1) / 2) * PITCH_X, (r - (rows - 1) / 2) * PITCH_Y, 0)) for r in range(rows) for c in range(cols)]
    for p in pts: put(p)
    corners = [p + Vector((sx * HX, sy * HY, z)) for p in pts for sx in (-1, 1) for sy in (-1, 1) for z in (0, HC)]
    e = math.radians(ELEV); d = 0.2
    while True:                                           # back the camera off until the subject's box fits
        C, F, Rt, Up = aim((0, -d * math.cos(e), d * math.sin(e) + HC / 2), (0, math.cos(e), -math.sin(e)))
        uv = np.array([project(c_, C, F, Rt, Up) for c_ in corners]); bw, bh = np.ptp(uv[:, 0]), np.ptp(uv[:, 1])
        if max(bw, bh) <= FILL_FRAC[WHICH]: break
        d *= 1.02
    # centre the box with lens shift (no change of perspective)
    cu, cv = (uv[:, 0].min() + uv[:, 0].max()) / 2, (uv[:, 1].min() + uv[:, 1].max()) / 2
    cd.shift_x = cu - 0.5; cd.shift_y = -(cv - 0.5) * H / W
    print("camera distance %.3f m, subject box %.3f x %.3f of the frame" % (d, bw, bh))
    focus = pts[0] if WHICH == 1 else Vector((0, (1 - (rows - 1) / 2) * PITCH_Y, HC))
    cd.dof.focus_distance = (Vector(focus) - C).dot(F)
else:
    FLD = FIELD; pit = math.radians(FLD["pitch"])
    C, F, Rt, Up = aim((0, 0, FLD["cam_h"]), (0, math.cos(pit), -math.sin(pit)))
    dd = F + Up * ((0.5 - FLD["first_v"]) * 2 * ty); t_ = (HC - FLD["cam_h"]) / dd.z; g0 = C + dd * t_      # where the first row sits
    n = 0
    for r in range(int((FLD["far"][1] - 0.6) / PITCH_Y) + 1):
        for c in range(-110, 111):
            p = Vector((c * PITCH_X, g0.y + r * PITCH_Y, 0)); u, v = project(p + Vector((0, 0, HC)), C, F, Rt, Up)
            dist = (p - C).length
            dim = smooth((FLD["side"][1] - abs(u - 0.5)) / (FLD["side"][1] - FLD["side"][0])) * smooth((FLD["far"][1] - dist) / (FLD["far"][1] - FLD["far"][0])) ** 1.3
            if dim <= 0.004 or v < 0.02 or abs(u - 0.5) > 0.47: continue
            put(p, dim); n += 1
    print("phones:", n)
    cd.dof.focus_distance = (Vector((0, g0.y + 0.62 * PITCH_Y, HC)) - C).dot(F)
cd.dof.use_dof = True; cd.dof.aperture_fstop = FSTOP[WHICH]
sun_light(sc, "rim", RIM["elev"], RIM["azim"], RIM["strength"], RIM["color"], 3.0)

HERE_ = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(HERE_, "work" if TEST else "", "path_%d.png" % WHICH)
t = time.time(); sc.render.filepath = out; bpy.ops.render.render(write_still=True); print("RENDERED %.1fs" % (time.time() - t))
p = (load_px(out)[..., :3] * 255).round().astype(int)
edge = np.concatenate([p[0], p[-1], p[:, 0], p[:, -1]])
print("EDGE pixels not (8,7,6):", int((edge != np.array([8, 7, 6])).any(1).sum()), "of", len(edge))
lit = (p != np.array([8, 7, 6])).any(-1); ys, xs = np.nonzero(lit)
print("subject box px: x %d..%d y %d..%d  (frame %d x %d)" % (xs.min(), xs.max(), ys.min(), ys.max(), W, H))
if not TEST: bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE_, "path_%d.blend" % WHICH))
