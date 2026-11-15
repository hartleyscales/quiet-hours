# qh_props.py : the notebook (with its pencil drawing of branches), and the pencil.
# The drawing is generated here, stroke by stroke, into a texture: nothing is copied in.

import bpy, bmesh, math
import numpy as np
from qh_kit import *

PAGE_W, PAGE_H = 0.210, 0.148      # landscape sketch pad, spiral along the far (top) edge
PX = 10000                         # pixels per metre (10 px / mm)


def make_drawing(path, seed=7):
    rng = np.random.default_rng(seed)
    W, H = int(PAGE_W * PX), int(PAGE_H * PX)
    acc = np.zeros((H, W), np.float32)

    def stroke(pts, pressure=1.0, wob=0.6, spread=1.7):
        pts = np.asarray(pts, float)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        L = seg.sum()
        if L < 2:
            return
        s = np.concatenate([[0], np.cumsum(seg)])
        n = int(L / 0.35) + 2
        u = np.linspace(0, L, n)
        x = np.interp(u, s, pts[:, 0])
        y = np.interp(u, s, pts[:, 1])
        ph = rng.uniform(0, 6.28, 2)
        x += wob * np.sin(u / 23 + ph[0])
        y += wob * np.sin(u / 19 + ph[1])
        t = u / L
        pr = pressure * (0.3 + 0.7 * np.sin(np.pi * t) ** 0.5) * rng.uniform(0.8, 1.1)
        for k in range(3):
            jx = x + rng.normal(0, spread, n)
            jy = y + rng.normal(0, spread, n)
            ok = (jx >= 0) & (jx < W) & (jy >= 0) & (jy < H)
            np.add.at(acc, (jy[ok].astype(int), jx[ok].astype(int)), pr[ok] * 0.11)

    def leaf(p, ang, size):
        th = np.linspace(0, 360, 90)
        r = leaf_radius(th, 1.0, rng.integers(0, 9)) * size
        a = np.radians(th) + ang - math.pi / 2
        out = np.stack([p[0] + r * np.cos(a), p[1] + r * np.sin(a)], 1)
        # the petiole meets the leaf at its base: shift so the base sits on p
        base = np.array([math.cos(ang), math.sin(ang)]) * size * 0.2
        out += base
        stroke(out, 0.75, wob=0.8)
        c = np.array(p) + base
        for la, L, _ in LOBES:
            d = ang + math.radians(la - 90)
            stroke([c, c + np.array([math.cos(d), math.sin(d)]) * size * L * 0.82], 0.4, wob=0.3)

    MAXD = 5

    def bough(p, ang, length, width, depth):
        n = 14
        pts = [np.array(p, float)]
        a = ang
        curv = rng.normal(0, 0.35)
        for i in range(n):
            a += curv / n + rng.normal(0, 0.035)
            pts.append(pts[-1] + length / n * np.array([math.cos(a), math.sin(a)]))
        pts = np.array(pts)
        wd = np.linspace(width, width * 0.62, n + 1)
        tang = np.gradient(pts, axis=0)
        tang /= np.linalg.norm(tang, axis=1)[:, None]
        nor = np.stack([-tang[:, 1], tang[:, 0]], 1)
        if width > 7:
            Lft = pts + nor * wd[:, None] / 2
            Rgt = pts - nor * wd[:, None] / 2
            stroke(Lft, 0.75)
            stroke(Lft + rng.normal(0, 1.5, 2), 0.4)
            stroke(Rgt, 1.15)
            stroke(Rgt + rng.normal(0, 1.2, 2), 0.7)
            m = int(length / 5)
            for j in range(m):
                k = rng.uniform(0, n - 0.01)
                i0 = int(k)
                base = Rgt[i0] + (Rgt[i0 + 1] - Rgt[i0]) * (k - i0)
                d = nor[i0] * wd[i0] * rng.uniform(0.25, 0.62) + tang[i0] * wd[i0] * 0.4
                stroke([base, base + d], 0.42, wob=0.2, spread=1.1)
            for j in range(int(length / 60)):
                k = rng.uniform(1, n - 2)
                i0 = int(k)
                c = pts[i0] + nor[i0] * wd[i0] * rng.uniform(-0.2, 0.3)
                stroke([c, c + tang[i0] * rng.uniform(14, 40)], 0.3, wob=0.6)
        else:
            stroke(pts, 0.95 if width > 3 else 0.6)
            if width > 4:
                stroke(pts + nor * width * 0.5, 0.5)
        end, aend = pts[-1], a
        if depth < MAXD and length > 55:
            sp = rng.uniform(0.35, 0.6)
            bough(end, aend + sp * rng.uniform(0.6, 1.1), length * rng.uniform(0.62, 0.8), width * 0.62, depth + 1)
            bough(end, aend - sp * rng.uniform(0.6, 1.1), length * rng.uniform(0.6, 0.78), width * 0.6, depth + 1)
            if rng.uniform() < 0.6:
                i0 = int(rng.integers(4, 10))
                side = rng.choice([-1, 1])
                bough(pts[i0], math.atan2(tang[i0][1], tang[i0][0]) + side * rng.uniform(0.5, 0.9),
                      length * 0.5, width * 0.4, depth + 2)
        elif rng.uniform() < 0.7:
            leaf(end, aend + rng.normal(0, 0.5), rng.uniform(45, 80))

    # one bough entering low on the left, reaching up and across the page
    bough((70, 260), math.radians(22), 640, 66, 0)
    # a second, lighter limb coming in from the top-left, unfinished
    bough((260, H - 150), math.radians(-20), 400, 28, 2)

    # blur: pencil softness
    k = np.array([1, 4, 6, 4, 1], np.float32) / 16
    for _ in range(2):
        acc = sum(np.roll(acc, i - 2, 0) * k[i] for i in range(5))
        acc = sum(np.roll(acc, i - 2, 1) * k[i] for i in range(5))
    tooth = rng.uniform(0, 1, (H, W)).astype(np.float32)
    tooth = (tooth + np.roll(tooth, 1, 0) + np.roll(tooth, 1, 1)) / 3
    dark = 1 - np.exp(-acc * (0.5 + 1.1 * tooth) * 6.5)
    paper = np.array([0.925, 0.905, 0.855], np.float32)
    graphite = np.array([0.23, 0.23, 0.25], np.float32)
    fib = 1 - 0.035 * rng.uniform(0, 1, (H, W)).astype(np.float32)
    rgb = (paper[None, None] * (1 - dark[..., None]) + graphite[None, None] * dark[..., None]) * fib[..., None]
    # punched holes for the wire, along the top edge
    pitch = 63.5
    yy, xx = np.mgrid[0:H, 0:W]
    for cx in np.arange(60, W - 40, pitch):
        m = (np.abs(xx - cx) < 12) & (np.abs(yy - (H - 60)) < 15)
        rgb[m] = np.array([0.05, 0.045, 0.04])
    a = np.ones((H, W, 4), np.float32)
    a[..., :3] = rgb
    img = bpy.data.images.new("drawing", W, H, alpha=False)
    img.pixels.foreach_set(a.reshape(-1))
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return path


def build_notebook(name, drawing_path):
    """Origin at the centre of the pad's underside. Page top (spiral edge) toward +Y."""
    root = bpy.data.objects.new(name, None)
    link(root)
    kraft = mat_principled("kraft", (0.36, 0.25, 0.14, 1), rough=0.8)
    add_bump(kraft, 1500, 0.2, dist=0.0002)
    edge = mat_principled("page_edge", (0.80, 0.77, 0.70, 1), rough=0.9)
    nt = edge.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1, 1, 9000)
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 1.0
    r = nt.nodes.new("ShaderNodeMapRange")
    r.inputs["To Min"].default_value = 0.55
    r.inputs["To Max"].default_value = 1.0
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "SCALE"
    mul.inputs[0].default_value = (0.80, 0.77, 0.70)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], n.inputs["Vector"])
    nt.links.new(n.outputs["Fac"], r.inputs["Value"])
    nt.links.new(r.outputs["Result"], mul.inputs["Scale"])
    nt.links.new(mul.outputs[0], nt.nodes["Principled BSDF"].inputs["Base Color"])
    # folded-back cover + back board
    cov = new_obj(name + "_cover", prism("cover", rrect(PAGE_W + 0.003, PAGE_H + 0.003, 0.004, 5), 0.0, 0.0028), kraft, root)
    bevel(cov, 0.0004, 2)
    cov.rotation_euler = (0, 0, math.radians(0.8))
    stack = new_obj(name + "_stack", prism("stack", rrect(PAGE_W, PAGE_H, 0.003, 5), 0.0028, 0.0118), edge, root)
    # top page: a grid so it can lift at a corner
    nx, ny = 64, 46
    xs = np.linspace(-PAGE_W / 2, PAGE_W / 2, nx)
    ys = np.linspace(-PAGE_H / 2, PAGE_H / 2, ny)
    X, Y = np.meshgrid(xs, ys)
    d = ((X / (PAGE_W / 2)) * 0.75 - (Y / (PAGE_H / 2)) * 0.65)          # toward the near-right corner
    Z = 0.01195 + 0.02 * np.clip(d - 0.95, 0, None) ** 2 + 0.0003 * np.sin(X * 40) * np.cos(Y * 30)
    co = np.stack([X, Y, Z], -1).astype(np.float32)
    idx = np.arange(nx * ny).reshape(ny, nx)
    q = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1)
    nf = (nx - 1) * (ny - 1)
    me = bpy.data.meshes.new("page")
    me.vertices.add(nx * ny)
    me.loops.add(nf * 4)
    me.polygons.add(nf)
    me.vertices.foreach_set("co", co.reshape(-1))
    me.loops.foreach_set("vertex_index", q.astype(np.int32))
    me.polygons.foreach_set("loop_start", np.arange(nf, dtype=np.int32) * 4)
    me.polygons.foreach_set("loop_total", np.full(nf, 4, np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(nf, bool))
    me.update(calc_edges=True)
    uvl = me.uv_layers.new(name="uv")
    U = (X / PAGE_W + 0.5).reshape(-1)
    V = (Y / PAGE_H + 0.5).reshape(-1)
    uv = np.stack([U[q], V[q]], 1).astype(np.float32)
    uvl.data.foreach_set("uv", uv.reshape(-1))
    paper = mat_principled("paper", (0.9, 0.88, 0.82, 1), rough=0.8)
    pnt = paper.node_tree
    t = pnt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(drawing_path)
    t.extension = "EXTEND"
    pnt.links.new(t.outputs["Color"], pnt.nodes["Principled BSDF"].inputs["Base Color"])
    pnt.nodes["Principled BSDF"].inputs["Sheen Weight"].default_value = 0.1
    add_bump(paper, 2500, 0.08, dist=0.00005)
    # a little light comes through the lifted sheet
    tr = pnt.nodes.new("ShaderNodeBsdfTranslucent")
    pnt.links.new(t.outputs["Color"], tr.inputs["Color"])
    ms = pnt.nodes.new("ShaderNodeMixShader")
    ms.inputs["Fac"].default_value = 0.12
    pnt.links.new(pnt.nodes["Principled BSDF"].outputs[0], ms.inputs[1])
    pnt.links.new(tr.outputs[0], ms.inputs[2])
    pnt.links.new(ms.outputs[0], pnt.nodes["Material Output"].inputs["Surface"])
    new_obj(name + "_page", me, paper, root)
    # wire: one continuous spiral along the top edge
    wire = mat_principled("wire", (0.55, 0.55, 0.56, 1), rough=0.28, metallic=1.0)
    cu = bpy.data.curves.new("spiral", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    pitch, R = 0.00635, 0.0078
    x0, x1 = -PAGE_W / 2 + 0.006, PAGE_W / 2 - 0.004
    turns = (x1 - x0) / pitch
    npt = int(turns * 28)
    sp.points.add(npt - 1)
    ay, az = PAGE_H / 2 + 0.0016, 0.0066
    for i, p in enumerate(sp.points):
        ph = 2 * math.pi * i / 28
        p.co = (x0 + pitch * ph / (2 * math.pi), ay + R * math.cos(ph), az + R * math.sin(ph), 1)
    cu.bevel_depth = 0.00048
    cu.bevel_resolution = 3
    cu.materials.append(wire)
    w = bpy.data.objects.new(name + "_wire", cu)
    link(w, root)
    for s in cu.splines:
        s.use_smooth = True
    return root


def build_pencil(name, length=0.158):
    """Lies along +X, point toward +X. Origin at the middle of the barrel, on its axis."""
    root = bpy.data.objects.new(name, None)
    link(root)
    wood = mat_principled("cedar", (0.50, 0.30, 0.14, 1), rough=0.42)
    wp = wood.node_tree.nodes["Principled BSDF"]
    wp.inputs["Coat Weight"].default_value = 0.35
    wp.inputs["Coat Roughness"].default_value = 0.25
    nt = wood.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (25, 900, 900)
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 1.0
    n.inputs["Detail"].default_value = 3.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.56, 0.35, 0.17, 1)
    mix.inputs["B"].default_value = (0.36, 0.20, 0.09, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], n.inputs["Vector"])
    nt.links.new(n.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], wp.inputs["Base Color"])
    raw = mat_principled("cedar_raw", (0.62, 0.42, 0.24, 1), rough=0.7)
    lead = mat_principled("graphite", (0.035, 0.035, 0.04, 1), rough=0.3, metallic=0.6)
    cone_l, tip_l = 0.017, 0.005
    body_l = length - cone_l - tip_l
    ry = Matrix.Rotation(math.radians(90), 4, "Y")

    def cyl(nm, r1, r2, depth, xc, verts, mat, flat=False):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r1, radius2=r2, depth=depth)
        bmesh.ops.transform(bm, matrix=ry, verts=bm.verts)
        bmesh.ops.translate(bm, vec=(xc, 0, 0), verts=bm.verts)
        me = bpy.data.meshes.new(nm)
        bm.to_mesh(me)
        bm.free()
        ob = new_obj(nm, me, mat, root)
        if not flat:
            smooth(me)
            wn = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
            wn.keep_sharp = True
        return ob

    b = cyl(name + "_body", 0.0037, 0.0037, body_l, -length / 2 + body_l / 2, 6, wood, flat=True)
    bevel(b, 0.0005, 3, angle=50)
    cyl(name + "_cone", 0.0033, 0.0011, cone_l, -length / 2 + body_l + cone_l / 2, 32, raw)
    cyl(name + "_tip", 0.0011, 0.00025, tip_l, -length / 2 + body_l + cone_l + tip_l / 2, 24, lead)
    cyl(name + "_core", 0.0011, 0.0011, 0.0003, -length / 2 - 0.0001, 16, lead)
    return root
