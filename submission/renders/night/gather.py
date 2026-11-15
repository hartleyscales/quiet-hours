# gather.png: the crowd becoming the moon. One bead is out (a ring on the floor), the rest are on; an arc lifts them into the moon.
# 3,098 beads on the left side in total (2,897 crowd + 200 in the arc + the 1 that is out), and the app's 3,098-dot moon on the right.
# usage: blender -b -P gather.py -- <draft|final>
import sys, os
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from night_common import *
from bpy_extras.object_utils import world_to_camera_view

# ---------------- key choices ----------------
PITCH_DEG = 35.0            # camera above the floor
LENS      = 50.0            # long-ish
CAM_DIST  = 12.0            # camera to floor along the view axis
RING_UV   = (0.335, 0.745)  # the one that is out: a third in from the left, in the near crowd
MOON_UV   = (0.787, 0.435)  # moon centre on screen
MOON_GAP  = 0.50            # clear air between the floor and the moon's lowest bead
MOON_H    = 0.54            # moon diameter as a fraction of frame height
MOON_YAW  = 8.0             # degrees the moon turns toward the crowd
CROWD_C   = (0.325, 0.625); CROWD_R = (0.30, 0.21)     # crowd patch on screen (superellipse), soft edged
ARC_UV    = [(0.475, 0.60), (0.465, 0.36), (0.570, 0.295), None]   # lift-off point, two handles, arrival on the moon's left limb
N_ARC     = 280
RING_R    = 0.058; CLEAR_R = 0.26
S_CROWD   = 1.15; S_MOON = 1.55; S_RING = 2.6
MOON_SPILL = 0.22           # how much of the moon's light reaches the floor (a faint pool under it, no more)
FLOOR_ALB = (0.56, 0.53, 0.49)
BLUR_FAR  = 7.0             # px of defocus (at 2560 wide) on the farthest crowd beads
# ---------------------------------------------

a = args(); q = a[0] if a else "draft"
W, H, SPP = (1280, 720, 160) if q == "draft" else (2560, 1440, 700)
sc = reset(); cycles(sc, W, H, SPP, thresh=0.02 if q == "draft" else 0.006); world_bg(sc)
rng = np.random.default_rng(3098)

# ---- camera frame (own maths, so the scene can be laid out in screen space) ----
p = math.radians(PITCH_DEG)
right = np.array([1.0, 0, 0]); up = np.array([0, math.sin(p), math.cos(p)]); fwd = np.array([0, math.cos(p), -math.sin(p)])
C = -fwd * CAM_DIST
Wd = 36.0 / LENS; Hd = Wd * 9 / 16
def ray(u, v): return fwd + (u - 0.5) * Wd * right + (0.5 - v) * Hd * up
def floor_at(u, v, z=0.0):
    d = ray(u, v); t = (z - C[2]) / d[2]; return C + t * d, t
def at_depth(u, v, depth): return C + depth * ray(u, v)
def project(P):
    P = np.atleast_2d(P) - C; dep = P @ fwd
    return 0.5 + (P @ right) / dep / Wd, 0.5 - (P @ up) / dep / Hd, dep

ring_p, ring_dep = floor_at(*RING_UV)
rz = ray(*MOON_UV)[2]
moon_dep = (MOON_GAP - C[2]) / (rz - 0.5 * MOON_H * Hd * math.cos(p))     # depth at which the moon of this screen size clears the floor by MOON_GAP
moon_c = at_depth(*MOON_UV, moon_dep)
Rm = 0.5 * MOON_H * moon_dep * Hd
focus = moon_dep + 0.40 * (ring_dep - moon_dep)       # focal plane between the moon and the ring: both crisp, the far crowd soft
ya = math.radians(MOON_YAW)
ex = right * math.cos(ya) - fwd * math.sin(ya); ey = up
xy, mcol, flag, pitch = load_moon()
BR = 0.333 * pitch * Rm                               # bead radius (the app's dot is 1.33 of a 2 pt cell)
moon_pos = moon_c + Rm * (xy[:, :1] * ex + xy[:, 1:] * ey)
print("focus %.2f  moon R %.3f  bead r %.4f  moon centre z %.2f" % (focus, Rm, BR, moon_c[2]))

# every bead on the left is one of the moon's own dots: shuffle the 3,098 colours over ring / arc / crowd
perm = rng.permutation(len(xy)); arc_col = mcol[perm[1:1 + N_ARC]]; crowd_col = mcol[perm[1 + N_ARC:]]
N_CROWD = len(crowd_col)

# ---- arc: cubic Bezier from the floor to the moon's left limb ----
P3 = moon_c + Rm * (-0.90 * ex + 0.13 * ey); u3, v3, d3 = project(P3)
P0, d0 = floor_at(*ARC_UV[0], z=BR)
P1 = at_depth(*ARC_UV[1], d0 + (d3[0] - d0) * 0.30); P2 = at_depth(*ARC_UV[2], d0 + (d3[0] - d0) * 0.72)
def bez(t):
    t = np.asarray(t)[..., None]; s = 1 - t
    return s ** 3 * P0 + 3 * s * s * t * P1 + 3 * s * t * t * P2 + t ** 3 * P3
def bez_d(t):
    t = np.asarray(t)[..., None]; s = 1 - t
    return 3 * s * s * (P1 - P0) + 6 * s * t * (P2 - P1) + 3 * t * t * (P3 - P2)
arc_pos = []
while len(arc_pos) < N_ARC:
    t = rng.random() ** 0.52                           # sparse at the floor, dense on arrival
    tan = bez_d(t); tan /= np.linalg.norm(tan)
    n1 = np.cross(tan, fwd); n1 /= np.linalg.norm(n1); n2 = np.cross(tan, n1)
    sig = 0.030 + 0.115 * (1 - t) ** 1.6
    P = bez(t) + sig * (rng.normal() * n1 + rng.normal() * n2 * 0.7)
    P[2] = max(P[2], BR)
    if arc_pos and np.min(np.linalg.norm(np.array(arc_pos) - P, axis=1)) < 2.6 * BR: continue
    arc_pos.append(P)
arc_pos = np.array(arc_pos)

# ---- crowd: clumpy scatter on the floor (people on a lawn), accepted through a soft screen-space patch ----
def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)
corners = np.array([floor_at(u, v)[0] for u in (0.0, 0.66) for v in (0.36, 0.88)])
lo = corners.min(0); hi = corners.max(0)
NCL = 90
cl_c = lo[:2] + (hi[:2] - lo[:2]) * rng.random((NCL, 2)); cl_s = 0.09 + 0.34 * rng.random(NCL) ** 1.6; cl_w = cl_s ** 1.2; cl_w /= cl_w.sum()
wk = rng.normal(size=(7, 2)); wk = wk / np.linalg.norm(wk, axis=1, keepdims=True) * (2 * np.pi / (0.7 + 2.2 * rng.random((7, 1)))); wph = rng.random(7) * 6.283
def field(c): return float(np.sin(wk @ c + wph).sum()) / 2.2          # slow unevenness: thin places and inlets
crowd = np.zeros((0, 2)); tries = 0
while len(crowd) < N_CROWD:
    tries += 1
    if rng.random() < 0.72:
        k = rng.choice(NCL, p=cl_w); c = cl_c[k] + cl_s[k] * rng.normal(size=2)
    else:
        c = lo[:2] + (hi[:2] - lo[:2]) * rng.random(2)
    u, v, _ = project(np.array([c[0], c[1], BR])); u = u[0]; v = v[0]
    fl = field(c)
    qv = abs((u - CROWD_C[0]) / CROWD_R[0]) ** 2.4 + abs((v - CROWD_C[1]) / CROWD_R[1]) ** 2.4
    if rng.random() > (1 - sstep(0.30, 1.0, qv + 0.16 * fl)) * (0.48 + 0.52 * sstep(-0.9, 0.35, fl)): continue
    if np.hypot(*(c - ring_p[:2])) < CLEAR_R * (0.9 + 0.2 * rng.random()): continue
    if len(crowd) and np.min(np.hypot(*(crowd - c).T)) < 5.0 * BR: continue
    crowd = np.vstack([crowd, c])
crowd_pos = np.concatenate([crowd, np.full((N_CROWD, 1), BR)], 1)
print("crowd placed", len(crowd), "tries", tries)

# ---- geometry ----
tv, tf = tmpl_sphere(14, 7)
ob_crowd = tile(sc, "crowd", tv, tf, np.vstack([crowd_pos, arc_pos]), np.full(N_CROWD + N_ARC, BR), np.vstack([crowd_col, arc_col]))
ob_crowd.data.materials.append(glow_mat("crowd_glow", S_CROWD))
ob_moon = tile(sc, "moon", tv, tf, moon_pos, np.full(len(moon_pos), BR), mcol)
ob_moon.data.materials.append(glow_mat("moon_glow", S_MOON, spill=MOON_SPILL))

# the one that is out: an unlit bead, a thin ring of light around it on the floor
out_bead = tile(sc, "out", *tmpl_sphere(24, 12), np.array([[ring_p[0], ring_p[1], BR]]), np.array([BR]))
m, nt, out = new_mat("unlit"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
b.inputs["Base Color"].default_value = (0.62, 0.59, 0.54, 1); b.inputs["Roughness"].default_value = 0.6
if "Emission Color" in b.inputs:                       # a trace of its own grey so the dull bead still reads at slide size
    b.inputs["Emission Color"].default_value = (0.62, 0.59, 0.54, 1); b.inputs["Emission Strength"].default_value = 0.05
nt.links.new(b.outputs[0], out.inputs["Surface"]); out_bead.data.materials.append(m)
bpy.ops.mesh.primitive_torus_add(major_radius=RING_R, minor_radius=BR * 0.82, major_segments=96, minor_segments=12, location=(ring_p[0], ring_p[1], BR * 0.82))
ring = bpy.context.object; bpy.ops.object.shade_smooth()
m, nt, out = new_mat("ring"); em = nt.nodes.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (*lin((234, 229, 222)), 1); em.inputs["Strength"].default_value = S_RING
nt.links.new(em.outputs[0], out.inputs["Surface"]); ring.data.materials.append(m)

# floor: matte; unlit it is exactly the slide background, and its response to light fades out before the frame edges,
# the headline block (top left) and the caption band (bottom)
bpy.ops.mesh.primitive_plane_add(size=300.0, location=(0, 0, 0)); floor = bpy.context.object
m, nt, out = new_mat("floor")
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Window"], sep.inputs[0])
def mrange(sock, a0, a1):
    n = nt.nodes.new("ShaderNodeMapRange"); n.interpolation_type = "SMOOTHSTEP"
    n.inputs["From Min"].default_value = a0; n.inputs["From Max"].default_value = a1
    n.inputs["To Min"].default_value = 0.0; n.inputs["To Max"].default_value = 1.0
    nt.links.new(sock, n.inputs["Value"]); return n.outputs["Result"]
def mulv(s1, s2):
    n = nt.nodes.new("ShaderNodeMath"); n.operation = "MULTIPLY"; nt.links.new(s1, n.inputs[0]); nt.links.new(s2, n.inputs[1]); return n.outputs[0]
sx, sy = sep.outputs["X"], sep.outputs["Y"]                      # window y runs up from the bottom
mask = mulv(mulv(mrange(sx, 0.015, 0.10), mrange(sx, 0.985, 0.90)), mulv(mrange(sy, 1 - 0.315, 1 - 0.40), mrange(sy, 1 - 0.885, 1 - 0.80)))
colm = nt.nodes.new("ShaderNodeMixRGB"); colm.blend_type = "MULTIPLY"; colm.inputs["Fac"].default_value = 1.0
colm.inputs["Color1"].default_value = (*FLOOR_ALB, 1); nt.links.new(mask, colm.inputs["Color2"])
dif = nt.nodes.new("ShaderNodeBsdfDiffuse"); nt.links.new(colm.outputs[0], dif.inputs["Color"])
em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*BG_LIN, 1)
lp = nt.nodes.new("ShaderNodeLightPath"); nt.links.new(lp.outputs["Is Camera Ray"], em.inputs["Strength"])
add = nt.nodes.new("ShaderNodeAddShader"); nt.links.new(dif.outputs[0], add.inputs[0]); nt.links.new(em.outputs[0], add.inputs[1])
nt.links.new(add.outputs[0], out.inputs["Surface"]); floor.data.materials.append(m)

# ---- camera ----
cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam)
cam.matrix_world = Matrix(((right[0], up[0], -fwd[0], C[0]), (right[1], up[1], -fwd[1], C[1]), (right[2], up[2], -fwd[2], C[2]), (0, 0, 0, 1)))
cd.lens = LENS; cd.sensor_width = 36.0; cd.sensor_fit = "HORIZONTAL"; cd.clip_start = 0.05; cd.clip_end = 500
far_dep = project(crowd_pos)[2].max()
f = LENS / 1000.0
fstop = (f * f / (focus - f)) * (far_dep - focus) / far_dep * (2560 / 0.036) / BLUR_FAR
cd.dof.use_dof = True; cd.dof.focus_distance = focus; cd.dof.aperture_fstop = fstop; cd.dof.aperture_blades = 0
sc.camera = cam; bpy.context.view_layer.update()
print("far depth %.2f  fstop %.3f" % (far_dep, fstop))

# ---- anchors (final-resolution pixels, origin top-left) ----
def px(P):
    co = world_to_camera_view(sc, cam, Vector([float(x) for x in P])); return [round(co.x * 2560, 1), round((1 - co.y) * 1440, 1)]
cu, cv, _ = project(crowd_pos)
mc = px(moon_c); mr = px(moon_c + Rm * ex); ml = px(moon_c - Rm * ex); mt = px(moon_c + Rm * ey); mb = px(moon_c - Rm * ey)
rr = px(ring_p + np.array([RING_R, 0, 0])); rb = px(ring_p + np.array([0, -RING_R, 0]))
anchors = {
    "image": {"width": 2560, "height": 1440, "background": "#080706"},
    "ring_centre": px(ring_p),
    "ring_radius_px": {"x": round(rr[0] - px(ring_p)[0], 1), "y": round(rb[1] - px(ring_p)[1], 1)},
    "crowd_centre": [round(float(cu.mean()) * 2560, 1), round(float(cv.mean()) * 1440, 1)],
    "crowd_bounds": {"left": round(float(np.percentile(cu, 1)) * 2560), "right": round(float(np.percentile(cu, 99)) * 2560),
                     "top": round(float(np.percentile(cv, 1)) * 1440), "bottom": round(float(np.percentile(cv, 99)) * 1440)},
    "moon_centre": mc,
    "moon_radius_px": round(((mr[0] - ml[0]) / 2 + (mb[1] - mt[1]) / 2) / 2, 1),
    "moon_radius_xy_px": [round((mr[0] - ml[0]) / 2, 1), round((mb[1] - mt[1]) / 2, 1)],
    "arc_midpoint": px(bez(0.5)),
    "arc_start": px(P0), "arc_end": px(P3),
    "counts": {"crowd": int(N_CROWD), "arc": int(N_ARC), "out": 1, "moon": int(len(moon_pos))},
}
print("ANCHORS", json.dumps(anchors))

raw = os.path.join(HERE, "work", "gather_%s_raw.png" % q); os.makedirs(os.path.dirname(raw), exist_ok=True)
render(sc, raw)
a8 = to8(load_px(raw))
outp = os.path.join(HERE, "gather.png" if q == "final" else "work/gather_draft.png")
save8(a8, outp); measure(a8, outp)
if q == "final":
    json.dump(anchors, open(os.path.join(HERE, "gather_anchors.json"), "w"), indent=2)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "work", "gather.blend"))
print("DONE", outp)
