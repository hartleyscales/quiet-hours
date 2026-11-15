# The app's night moon made of phones: 3,098 phones lying flat, one per dot of the Locked screen's moon (the true layout
# from web/moon.js at N = 3098, exported earlier to ../objects/data/moon_3098.json), each screen glowing in its own dot's colour.
# The camera is orthographic and looks down from 33 degrees above the plane; the rows are spaced so that the lattice comes
# out square in the picture, and a phone seen that way is a dot of the app's own proportion (two thirds of its cell).
# usage: blender -b -P moon_of_phones.py -- <wide|close> [test]
import sys, os, json, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from phone import *

# ---------------- key choices ----------------
NIGHT     = "#080706"
W, H, SPP = 2560, 1440, 1200
ELEV      = 33.0                          # camera elevation above the plane (orthographic)
PITCH_X   = 2 * HX * 1.5                  # a phone is two thirds of its cell across, as the app's dot is
MOON_AT   = (0.715, 0.50)                 # wide: the moon's centre in the frame (x, y from the top-left)
MOON_H    = 0.75                          # wide: the moon's diameter as a share of the frame's height
CLOSE     = dict(limb_deg=118.0, back=1.30, aside=-0.20, cam_h=0.50, pitch=14.5, lens=35.0, fstop=2.8, far=(4.5, 13.0), left=(0.03, 0.12))
#           close: the same moon, same phones, from a low camera standing just outside the lower-left limb and looking up the rows
RIM       = dict(elev=24.0, azim=62.0, strength=4.6, color=(1.0, 0.82, 0.64))
GLOW      = 1.0                           # screens emit exactly their dot's colour
# ---------------------------------------------

a = args(); MODE = a[0] if a else "wide"; TEST = "test" in a
sc = reset()
if TEST: W, H, SPP = W // 2, H // 2, 200
cycles(sc, W, H, SPP, view="Standard", look="None", exposure=0.0)
sc.cycles.use_denoising = False; sc.cycles.adaptive_threshold = 0.004; sc.cycles.adaptive_min_samples = 160; sc.cycles.filter_width = 1.5
sc.render.dither_intensity = 0.0; sc.render.image_settings.color_depth = "8"; sc.render.image_settings.color_mode = "RGB"
night = srgb(NIGHT)
wn = sc.world.node_tree
for n in list(wn.nodes): wn.nodes.remove(n)
bgc = wn.nodes.new("ShaderNodeBackground"); bgc.inputs[0].default_value = (*night, 1)
bgk = wn.nodes.new("ShaderNodeBackground"); bgk.inputs[1].default_value = 0.0
lpw = wn.nodes.new("ShaderNodeLightPath"); mxw = wn.nodes.new("ShaderNodeMixShader"); wo = wn.nodes.new("ShaderNodeOutputWorld")
wn.links.new(lpw.outputs["Is Camera Ray"], mxw.inputs[0]); wn.links.new(bgk.outputs[0], mxw.inputs[1]); wn.links.new(bgc.outputs[0], mxw.inputs[2]); wn.links.new(mxw.outputs[0], wo.inputs[0])

d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "objects", "data", "moon_3098.json")))
dots = np.array(d["dots"], dtype=np.float64); N = len(dots)
e = math.radians(ELEV); PITCH_Y = PITCH_X / math.sin(e)          # so the lattice is square as the camera sees it

me = phone_mesh(seg=18 if MODE == "close" else 8)
def mat_simple(name, base, rough, spec):
    m, nt, b, _ = new_mat(name); setin(b, "Base Color", (*base, 1)); setin(b, "Roughness", rough); setin(b, "Specular IOR Level", spec); return m
ms = bpy.data.materials.new("glow"); ms.use_nodes = True; nt = ms.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
oi = nt.nodes.new("ShaderNodeObjectInfo"); em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = GLOW
dk = nt.nodes.new("ShaderNodeBsdfDiffuse"); dk.inputs["Color"].default_value = (0.003, 0.003, 0.003, 1)
lp = nt.nodes.new("ShaderNodeLightPath"); mx = nt.nodes.new("ShaderNodeMixShader"); om = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(oi.outputs["Color"], em.inputs["Color"]); nt.links.new(lp.outputs["Is Camera Ray"], mx.inputs[0]); nt.links.new(dk.outputs[0], mx.inputs[1])
nt.links.new(em.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], om.inputs["Surface"])
def fading(name, base, rough, spec):
    """Dissolves into the night colour as the object's alpha goes to 0 (used where the close view's field fades out)."""
    m = bpy.data.materials.new(name); m.use_nodes = True; n2 = m.node_tree
    b = next(n for n in n2.nodes if n.type == "BSDF_PRINCIPLED"); o2 = next(n for n in n2.nodes if n.type == "OUTPUT_MATERIAL")
    setin(b, "Base Color", (*base, 1)); setin(b, "Roughness", rough); setin(b, "Specular IOR Level", spec)
    oi2 = n2.nodes.new("ShaderNodeObjectInfo"); e2 = n2.nodes.new("ShaderNodeEmission"); e2.inputs["Color"].default_value = (*night, 1); mxs = n2.nodes.new("ShaderNodeMixShader")
    pw = n2.nodes.new("ShaderNodeMath"); pw.operation = "POWER"; n2.links.new(oi2.outputs["Alpha"], pw.inputs[0]); pw.inputs[1].default_value = 2.6
    n2.links.new(pw.outputs[0], mxs.inputs[0]); n2.links.new(e2.outputs[0], mxs.inputs[1]); n2.links.new(b.outputs[0], mxs.inputs[2]); n2.links.new(mxs.outputs[0], o2.inputs["Surface"]); return m
for m_ in (fading("case", srgb(CASE_HEX), 0.6, 0.3), fading("bezel", (0.0028, 0.0026, 0.0024), 1.0, 0.0), ms): me.materials.append(m_)

col = lin(dots[:, 2:5]); nightv = np.array(night)
pos = np.stack([(dots[:, 0] - d["cx"]) * PITCH_X, -(dots[:, 1] - d["cy"]) * PITCH_Y, np.zeros(N)], 1)
cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
dim = np.ones(N)
if MODE == "wide":
    cd.type = "ORTHO"; cd.clip_start = 1.0; cd.clip_end = 400
    fwd = Vector((0, math.cos(e), -math.sin(e))); cam.rotation_euler = fwd.to_track_quat("-Z", "Y").to_euler()
    pitch_px = MOON_H * H / (2 * d["r"])                          # one cell, in pixels
    cd.ortho_scale = W / pitch_px * PITCH_X                       # frame width in metres
    cam.location = Vector((0, 0, HC)) - fwd * 120.0
    cd.shift_x = 0.5 - MOON_AT[0]; cd.shift_y = (MOON_AT[1] - 0.5) * H / W      # slide the picture so the moon's centre sits where it should
    print("pitch %.2f px, phone %.1f px wide" % (pitch_px, pitch_px / 1.5))
else:
    Cc = CLOSE; th = math.radians(Cc["limb_deg"]); pit = math.radians(Cc["pitch"])
    limb = Vector((d["r"] * math.cos(th) * PITCH_X, -d["r"] * math.sin(th) * PITCH_Y, 0))
    C = Vector((limb.x + Cc["aside"], limb.y - Cc["back"], Cc["cam_h"])); F = Vector((0, math.cos(pit), -math.sin(pit)))
    cd.lens = Cc["lens"]; cd.sensor_width = 36.0; cd.clip_start = 0.05; cd.clip_end = 80
    cam.location = C; cam.rotation_euler = F.to_track_quat("-Z", "Y").to_euler(); bpy.context.view_layer.update()
    Rm = cam.matrix_world.to_3x3(); Rt = np.array(Rm @ Vector((1, 0, 0))); Up = np.array(Rm @ Vector((0, 1, 0))); Fv = np.array(F)
    q = pos + np.array([0, 0, HC]) - np.array(C); zc = q @ Fv
    u = 0.5 + (q @ Rt) / zc / (2 * 18.0 / Cc["lens"]); dist = np.linalg.norm(q, axis=1)
    sm = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1))
    v = 0.5 - (q @ Up) / zc / (2 * 18.0 / Cc["lens"] * H / W)
    dim = sm((u - Cc["left"][0]) / (Cc["left"][1] - Cc["left"][0])) * sm((1 - u - Cc["left"][0]) / (Cc["left"][1] - Cc["left"][0])) * sm((Cc["far"][1] - dist) / (Cc["far"][1] - Cc["far"][0])) ** 1.3 * sm((0.90 - v) / 0.07)
    dim[zc < 0.3] = 0
    near = pos[(zc > 0.3) & (dist < 2.2) & (dim > 0.5)]; fo = near[np.argsort(np.linalg.norm(near - np.array(C), axis=1))[min(6, len(near) - 1)]]
    cd.dof.use_dof = True; cd.dof.aperture_fstop = Cc["fstop"]; cd.dof.focus_distance = float((fo + np.array([0, 0, HC]) - np.array(C)) @ Fv)
shown = 0
for k_ in range(N):
    if dim[k_] <= 0.004: continue
    ob = bpy.data.objects.new("m", me); sc.collection.objects.link(ob); ob.location = pos[k_]; shown += 1
    c_ = nightv + (col[k_] - nightv) * dim[k_]                    # the glow melts into the night colour where the field fades
    ob.color = (float(c_[0]), float(c_[1]), float(c_[2]), float(dim[k_]))
print("phones shown:", shown, "of", N)
sun_light(sc, "rim", RIM["elev"], RIM["azim"], RIM["strength"], RIM["color"], 3.0)

HERE_ = os.path.dirname(os.path.abspath(__file__))
name = "moon_of_phones" if MODE == "wide" else "moon_of_phones_close"
out = os.path.join(HERE_, "work" if TEST else "", name + ".png")
t = time.time(); sc.render.filepath = out; bpy.ops.render.render(write_still=True); print("RENDERED %.1fs" % (time.time() - t))
p = (load_px(out)[..., :3] * 255).round().astype(int)
edge = np.concatenate([p[0], p[-1], p[:, 0], p[:, -1]])
print("EDGE pixels not (8,7,6):", int((edge != np.array([8, 7, 6])).any(1).sum()), "of", len(edge))
lit = (p != np.array([8, 7, 6])).any(-1); ys, xs = np.nonzero(lit)
print("lit box px: x %d..%d y %d..%d (frame %d x %d); left half max" % (xs.min(), xs.max(), ys.min(), ys.max(), W, H), p[:, :W // 2].reshape(-1, 3).max(0))
if not TEST: bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE_, name + ".blend"))
