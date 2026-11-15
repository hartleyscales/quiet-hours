# The phone, built from nothing: a plain black slab in a matte clay case, as one mesh with three material slots
# (0 case, 1 bezel, 2 screen). Local frame: x to the screen's right, y to its top, z out of the glass; back at z = 0.
import bpy, bmesh, numpy as np, math
from mathutils import Vector, Matrix
from common import PX, PT, blur, save_px

PW, PH = 1206, 2622
SW, SH = PW * PX, PH * PX                 # screen 66.5 x 144.6 mm
R_SCREEN = 62 * PT                        # display corner radius: 62 pt on a 402 pt wide screen
BEZEL, LIP, HC = 0.0013, 0.0014, 0.0096      # thin black border, slim case lip, phone-in-case thickness
CASE_HEX = "#9E6A54"                      # quiet brown clay; under the kit light its lit side measures near (176, 122, 98)
DS = LIP + BEZEL
HX, HY, RC = SW / 2 + DS, SH / 2 + DS, R_SCREEN + DS
GZ = HC - 0.00065                         # glass level

def ring_mesh(name, hx, hy, R, prof, seg=24, sharp_deg=32):
    """Rounded-rectangle solid from rings (inset, height, material index of the band starting at that ring)."""
    th = np.linspace(0, np.pi / 2, seg + 1); rings = []
    for d, z, _ in prof:
        r = max(R - d, 0.0); cx = min(hx - R, hx - d); cy = min(hy - R, hy - d); pts = []
        for (sx, sy, off) in [(1, 1, 0), (-1, 1, np.pi / 2), (-1, -1, np.pi), (1, -1, 3 * np.pi / 2)]:
            ang = th + off
            pts.append(np.stack([sx * cx + r * np.cos(ang), sy * cy + r * np.sin(ang), np.full(seg + 1, z)], 1))
        rings.append(np.concatenate(pts))
    M = rings[0].shape[0]; V = np.concatenate(rings); faces, mats = [], []
    for k in range(len(rings) - 1):
        for i in range(M):
            j = (i + 1) % M
            faces.append((k * M + i, k * M + j, (k + 1) * M + j, (k + 1) * M + i)); mats.append(prof[k][2])
    faces.append(tuple(range((len(rings) - 1) * M, len(rings) * M))); mats.append(prof[-1][2])
    faces.append(tuple(range(M - 1, -1, -1))); mats.append(prof[0][2])
    me = bpy.data.meshes.new(name); me.from_pydata(V.tolist(), [], faces); me.update()
    me.polygons.foreach_set("material_index", np.array(mats, dtype=np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(len(faces), dtype=bool))
    if sharp_deg: me.set_sharp_from_angle(angle=math.radians(sharp_deg))
    return me

def phone_mesh(seg=24):
    RB, FL = 0.0026, 0.0008
    t8 = np.linspace(0, np.pi / 2, 11)
    prof  = [(RB * (1 - math.sin(t)), RB * (1 - math.cos(t)), 0) for t in t8]                 # back edge, rounded
    prof += [(FL * (1 - math.cos(t)), HC - FL + FL * math.sin(t), 0) for t in t8]             # wall, front edge
    prof += [(LIP - 0.00045, HC, 0), (LIP - 0.00012, HC - 0.00022, 0), (LIP, GZ, 1)]          # lip and its inner wall
    prof += [(DS, GZ, 2)]                                                                     # bezel ends, screen begins
    body = ring_mesh("phone_body", HX, HY, RC, prof, seg=seg)
    bm = bmesh.new(); bm.from_mesh(body); bpy.data.meshes.remove(body)
    for (side, yc, length) in [(-1, 0.0400, 0.0085), (-1, 0.0245, 0.0120), (-1, 0.0095, 0.0120), (1, 0.0235, 0.0190)]:
        b2 = bmesh.new(); bmesh.ops.create_cube(b2, size=1.0)
        for v in b2.verts: v.co = Vector((v.co.x * 0.0016, v.co.y * length, v.co.z * 0.0034))
        bmesh.ops.bevel(b2, geom=list(b2.edges), offset=0.00055, segments=4, affect="EDGES", profile=0.5)
        for f in b2.faces: f.smooth = True
        tmp = bpy.data.meshes.new("btn"); b2.to_mesh(tmp); b2.free()
        n0 = len(bm.verts); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp); bm.verts.ensure_lookup_table()
        for v in bm.verts[n0:]: v.co += Vector((side * (HX - 0.00042), yc, HC * 0.5))
    me = bpy.data.meshes.new("phone"); bm.to_mesh(me); bm.free()
    return me

def pane_mesh(thick=0.0010, seg=24):
    """A thin glass pane the size and corner radius of the screen. Slots: 0 edge and back, 1 the face that carries the picture."""
    e = 0.00012
    prof = [(e, 0.0, 0), (0.0, e, 0), (0.0, thick - e, 0), (e, thick, 1)]
    return ring_mesh("pane", SW / 2, SH / 2, R_SCREEN, prof, seg=seg, sharp_deg=50)

def stand_matrix(turn_deg, tip_deg, thick=HC, half_h=HY):
    """Stand it on its foot facing -Y, tip it back, turn it about its own vertical axis."""
    return Matrix.Rotation(math.radians(turn_deg), 4, "Z") @ Matrix.Translation((0, thick / 2, 0)) @ \
           Matrix.Rotation(math.radians(-tip_deg), 4, "X") @ Matrix.Translation((0, 0, half_h)) @ Matrix.Rotation(math.radians(90), 4, "X")

def screen_nodes(nt, image, camera_only=True, dim_from_object=False, bg=None, gain=1.0):
    """Emission of the real screenshot mapped by object coordinates; returns the texture node."""
    for n in list(nt.nodes): nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / SW, 1 / SH, 1); mp.inputs["Location"].default_value = (0.5, 0.5, 0)
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.interpolation = "Linear"; tex.extension = "EXTEND"; tex.image = image
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.0
    om = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    col = tex.outputs["Color"]
    if gain != 1.0:                           # brighten what is drawn on the screen and leave its background exactly as it is
        sub = nt.nodes.new("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"; nt.links.new(col, sub.inputs[0]); sub.inputs[1].default_value = bg
        pos = nt.nodes.new("ShaderNodeVectorMath"); pos.operation = "MAXIMUM"; nt.links.new(sub.outputs[0], pos.inputs[0]); pos.inputs[1].default_value = (0, 0, 0)
        scl = nt.nodes.new("ShaderNodeVectorMath"); scl.operation = "SCALE"; nt.links.new(pos.outputs[0], scl.inputs[0]); scl.inputs["Scale"].default_value = gain
        add = nt.nodes.new("ShaderNodeVectorMath"); add.operation = "ADD"; nt.links.new(scl.outputs[0], add.inputs[0]); add.inputs[1].default_value = bg
        sp = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(add.outputs[0], sp.inputs[0])
        m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MAXIMUM"; nt.links.new(sp.outputs[0], m1.inputs[0]); nt.links.new(sp.outputs[1], m1.inputs[1])
        m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MAXIMUM"; nt.links.new(m1.outputs[0], m2.inputs[0]); nt.links.new(sp.outputs[2], m2.inputs[1])
        m3 = nt.nodes.new("ShaderNodeMath"); m3.operation = "MAXIMUM"; nt.links.new(m2.outputs[0], m3.inputs[0]); m3.inputs[1].default_value = 1.0
        inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "DIVIDE"; inv.inputs[0].default_value = 1.0; nt.links.new(m3.outputs[0], inv.inputs[1])
        nrm = nt.nodes.new("ShaderNodeVectorMath"); nrm.operation = "SCALE"; nt.links.new(add.outputs[0], nrm.inputs[0]); nt.links.new(inv.outputs[0], nrm.inputs["Scale"])
        col = nrm.outputs[0]                  # anything pushed past white is pulled back along its own hue
    if dim_from_object:                       # fade towards the night colour by the object's own colour (r channel)
        oi = nt.nodes.new("ShaderNodeObjectInfo"); sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(oi.outputs["Color"], sep.inputs[0])
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.inputs["A"].default_value = (*bg, 1)
        nt.links.new(sep.outputs[0], mx.inputs["Factor"]); nt.links.new(col, mx.inputs["B"]); col = mx.outputs["Result"]
    nt.links.new(col, em.inputs["Color"])
    if camera_only:
        dark = nt.nodes.new("ShaderNodeBsdfDiffuse"); dark.inputs["Color"].default_value = (0.003, 0.003, 0.003, 1)
        lp = nt.nodes.new("ShaderNodeLightPath"); mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0]); nt.links.new(dark.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], om.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], om.inputs["Surface"])
    return tex

def make_wash_atlas(path, nx=16, ny=8, tw=96, th=208, seed=3, pale=None):
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
    if pale:                                 # (colour kept, floor, range): a quieter, lighter family of the same washes
        keep, lo, rng_ = pale; g = A.mean(-1, keepdims=True); A = lo + rng_ * (g + keep * (A - g))
    save_px(A, path)
    means = A.reshape(ny, th, nx, tw, 3).mean((1, 3))          # each screen's average colour, for the light it spills
    return nx, ny, means

