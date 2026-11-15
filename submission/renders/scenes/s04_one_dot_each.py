# 04 One dot each   (my own idea)
# The app's night moon is "exactly one dot per person who is in". Here the lawn draws it: 3,098 daisies,
# one per Trojan in, at the app's own dot positions (web/moon.js ported below, fed by the app's
# moon-col-dark.png.cells.json), seen from up in the tree as the sun goes.
#
# KEY CHOICES
N_PEOPLE = 3098                      # the number on the real `locked` screen
PITCH = 0.032                        # metres between dot cells: the moon is about 3.7 m across
FLOWER_R = 0.0125                    # every daisy the same size, as every dot is
CAM_LOC = (-0.75, -4.05, 5.1)
CAM_AIM = (-0.75, 0.15, 0.0)
LENS, FSTOP = 35, 2.8
SUN_ELEV, SUN_AZIM = 13.0, -42.0
SKY_STRENGTH = 0.085
EXPOSURE = 0.35
WB = 7400
LAWN_H = 0.024
SEED = 9
CELLS = "/Users/hartleyscales/quiet-hours/web/assets/moon-col-dark.png.cells.json"

import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, numpy as np
from qh_kit import *


# ------------------------------------------------------------ the app's moon (port of web/moon.js moonDots)
def seeded(seed):
    a = [seed & 0xFFFFFFFF]

    def imul(x, y):
        return (x * y) & 0xFFFFFFFF

    def rnd():
        a[0] = (a[0] + 0x6D2B79F5) & 0xFFFFFFFF
        x = imul(a[0] ^ (a[0] >> 15), 1 | a[0])
        x = ((x + imul(x ^ (x >> 7), 61 | x)) & 0xFFFFFFFF) ^ x
        return ((x ^ (x >> 14)) & 0xFFFFFFFF) / 4294967296
    return rnd


def brightness(c, MX, MY, MR):
    x, y = (c[0] - MX) / MR, -(c[1] - MY) / MR
    z = math.sqrt(max(0, 1 - x * x - y * y))
    s = min(1, max(0, (c[2] / (1 - 0.3 * (1 - z) ** 2.2) - 0.1) / 0.82))
    u = 0.5 - math.sin(math.asin(1 - 2 * s) / 3)
    return 0.18 + 0.64 * u


def moon_dots(data, N):
    CW, CH, MX, MY, MR, cells = data["cw"], data["ch"], data["cx"], data["cy"], data["r"], data["cells"]
    total = len(cells)
    if N >= total:
        return list(range(total))
    grid = -np.ones(CW * CH, np.int64)
    for k, c in enumerate(cells):
        grid[c[1] * CW + c[0]] = k

    def at(i, j):
        return grid[j * CW + i] if (0 <= i < CW and 0 <= j < CH) else -1
    density = [c[2] for c in cells]

    def dither(gain):
        err = [0.0] * (CW * CH)
        on = []
        for j in range(CH):
            s = 1 if j % 2 == 0 else -1
            for n in range(CW):
                i = n if s == 1 else CW - 1 - n
                k = grid[j * CW + i]
                if k < 0:
                    continue
                v = min(0.97, density[k] * gain) + err[j * CW + i]
                o = 1 if v >= 0.5 else 0
                e = v - o
                if o:
                    on.append(int(k))
                if at(i + s, j) >= 0:
                    err[j * CW + i + s] += e * 7 / 16
                if j + 1 < CH:
                    if at(i - s, j + 1) >= 0:
                        err[(j + 1) * CW + i - s] += e * 3 / 16
                    if at(i, j + 1) >= 0:
                        err[(j + 1) * CW + i] += e * 5 / 16
                    if at(i + s, j + 1) >= 0:
                        err[(j + 1) * CW + i + s] += e * 1 / 16
        return on

    lo, hi = 0.05, 3.0
    for q in range(30):
        g = (lo + hi) / 2
        if len(dither(g)) < N:
            lo = g
        else:
            hi = g
    on = dither(hi)
    r7 = seeded(7)
    while len(on) > N:
        on.pop(int(r7() * len(on)))
    is_rim = lambda k: cells[k][3] == 1
    ring = [k for k, c in enumerate(cells) if c[3] == 1]
    ring.sort(key=lambda k: math.atan2(cells[k][1] - MY, cells[k][0] - MX))
    onset = set(on)

    def local(k):
        i, j = cells[k][0], cells[k][1]
        tot = hit = 0
        for b in range(-4, 5):
            for a_ in range(-4, 5):
                q = at(i + a_, j + b)
                if q >= 0 and not is_rim(q):
                    tot += 1
                    hit += int(q) in onset
        return hit / tot if tot else 0
    m = len(ring)
    raw = [local(k) for k in ring]
    dens = [sum(raw[(k + d) % m] for d in range(-3, 4)) / 7 for k in range(m)]
    edge = []
    acc = 0.5
    for n, k in enumerate(ring):
        acc += min(1, max(0.3, math.sqrt(dens[n]) * 1.1))
        if acc >= 1:
            edge.append(k)
            acc -= 1
    keep = [k for k in on if not is_rim(k)]
    seen = set(keep)
    for k in edge:
        if k not in seen:
            keep.append(k)
            seen.add(k)
    r5 = seeded(5)
    if len(seen) > N:
        inner = sorted([k for k in keep if not is_rim(k)], key=lambda k: (cells[k][0], cells[k][1]))
        for i in range(len(inner) - 1, 0, -1):
            j = int(r5() * (i + 1))
            inner[i], inner[j] = inner[j], inner[i]
        while len(seen) > N and inner:
            seen.discard(inner.pop())
        if len(seen) > N:
            seen = set(edge[int((q + 0.5) * len(edge) / N)] for q in range(N))
    elif len(seen) < N:
        spare = [k for k in range(total) if not is_rim(k) and k not in seen]
        key = {k: -brightness(cells[k], MX, MY, MR) + r5() * 0.2 for k in spare}
        spare.sort(key=lambda k: key[k])
        for k in spare:
            if len(seen) >= N:
                break
            seen.add(k)
        if len(seen) < N:
            rest = [k for k in ring if k not in seen]
            need = N - len(seen)
            for q in range(need):
                seen.add(rest[int((q + 0.5) * len(rest) / need)])
    return sorted(seen, key=lambda k: (cells[k][1], cells[k][0]))


# ------------------------------------------------------------ daisies, all in one mesh
def daisies(name, centres, rng, R=FLOWER_R, petals=13):
    n = len(centres)
    per = petals * 4 + 8 + 4
    V = np.zeros((n, per, 3), np.float32)
    C = np.ones((n, per, 4), np.float32)
    faces = []
    phi = rng.uniform(0, 6.28, n)
    tiltx, tilty = rng.normal(0, 0.16, n), rng.normal(0, 0.16, n)
    white = np.array([0.95, 0.94, 0.90]) * rng.uniform(0.92, 1.04, (n, 1))
    for pt in range(petals):
        a = phi + 2 * np.pi * pt / petals + rng.normal(0, 0.05, n)
        ca, sa = np.cos(a), np.sin(a)
        L = R * rng.uniform(0.9, 1.08, n)
        for q, (rad, wid) in enumerate([(0.16, 0.0), (0.62, 0.115), (1.0, 0.0), (0.62, -0.115)]):
            r = L * rad
            w = R * wid
            V[:, pt * 4 + q, 0] = r * ca - w * sa
            V[:, pt * 4 + q, 1] = r * sa + w * ca
            V[:, pt * 4 + q, 2] = 0.22 * R * rad * rad
            C[:, pt * 4 + q, :3] = white
        faces.append([pt * 4, pt * 4 + 1, pt * 4 + 2, pt * 4 + 3])
    b = petals * 4
    for q in range(8):
        a = 2 * np.pi * q / 8
        V[:, b + q, 0] = 0.27 * R * np.cos(a)
        V[:, b + q, 1] = 0.27 * R * np.sin(a)
        V[:, b + q, 2] = 0.06 * R
        C[:, b + q, :3] = (0.78, 0.50, 0.04)
    cface = [b + q for q in range(8)]
    s0 = b + 8
    # tilt each flower head a little, then lift it onto its stem
    V[:, :, 2] += V[:, :, 0] * tiltx[:, None] + V[:, :, 1] * tilty[:, None]
    hgt = centres[:, 2]
    V[:, :s0, 0] += centres[:, 0:1]
    V[:, :s0, 1] += centres[:, 1:2]
    V[:, :s0, 2] += hgt[:, None]
    for q, (dx, dz) in enumerate([(-0.0006, 0.0), (0.0006, 0.0), (0.0006, 1.0), (-0.0006, 1.0)]):
        V[:, s0 + q, 0] = centres[:, 0] + dx
        V[:, s0 + q, 1] = centres[:, 1]
        V[:, s0 + q, 2] = hgt * dz
        C[:, s0 + q, :3] = (0.10, 0.17, 0.04)
    sface = [s0, s0 + 1, s0 + 2, s0 + 3]
    base = (np.arange(n) * per)[:, None]
    quads = np.concatenate([base + np.array(f)[None] for f in faces + [sface]], 1).reshape(-1)
    octs = (base + np.array(cface)[None]).reshape(-1)
    nq = n * (petals + 1)
    loops = np.concatenate([quads, octs]).astype(np.int32)
    starts = np.concatenate([np.arange(nq) * 4, nq * 4 + np.arange(n) * 8]).astype(np.int32)
    totals = np.concatenate([np.full(nq, 4), np.full(n, 8)]).astype(np.int32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(n * per)
    me.loops.add(len(loops))
    me.polygons.add(len(starts))
    me.vertices.foreach_set("co", V.reshape(-1))
    me.loops.foreach_set("vertex_index", loops)
    me.polygons.foreach_set("loop_start", starts)
    me.polygons.foreach_set("loop_total", totals)
    me.update(calc_edges=True)
    ca = me.color_attributes.new("col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", C.reshape(-1))
    m = bpy.data.materials.new("daisy")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "col"
    nt.links.new(at.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.6
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    nt.links.new(at.outputs["Color"], tr.inputs["Color"])
    ms = nt.nodes.new("ShaderNodeMixShader")
    ms.inputs["Fac"].default_value = 0.35
    nt.links.new(p.outputs[0], ms.inputs[1])
    nt.links.new(tr.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return new_obj(name, me, m)


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FINAL = "final" in args
tag = "final" if FINAL else "draft"

sc = reset()
setup_render(sc, *((2560, 1440, 500) if FINAL else (1280, 720, 96)), exposure=EXPOSURE,
             noise=0.01 if FINAL else 0.035, wb=WB)
rng = np.random.default_rng(SEED)
sky(sc, SUN_ELEV, SUN_AZIM, SKY_STRENGTH, aerosol=1.6)
cam = camera(sc, CAM_LOC, CAM_AIM, LENS, FSTOP, (0.0, -0.4, 0.03))

data = json.load(open(CELLS))
dots = moon_dots(data, N_PEOPLE)
print("moon dots:", len(dots))
cells = data["cells"]
xy = np.array([[(cells[k][0] - data["cx"]) * PITCH, -(cells[k][1] - data["cy"]) * PITCH] for k in dots])
xy += rng.normal(0, PITCH * 0.035, xy.shape)                     # they grew there; they were not printed
z = LAWN_H * 1.25 + rng.normal(0, 0.0025, len(xy))
daisies("moon", np.concatenate([xy, z[:, None]], 1), rng)
# a few strays in the lawn around it, as the app has stars
st = rect_points(rng, -5.0, 3.6, -3.0, 6.0, 1.8)
st = st[np.linalg.norm(st, axis=1) > data["r"] * PITCH + 0.25]
daisies("strays", np.concatenate([st, np.full((len(st), 1), LAWN_H * 1.25)], 1), rng)

g = mat_grass()
apex = (CAM_LOC[0], CAM_LOC[1])
p1 = rect_points(rng, -5.2, 3.7, -3.2, 3.2, 70000)
make_grass("lawn_near", p1, g, rng, h_mean=LAWN_H, w_mean=0.0042, bend=0.5, segs=3, tuft=0.03)
p2 = rect_points(rng, -9.0, 7.5, 3.2, 9.0, 26000)
make_grass("lawn_mid", p2, g, rng, h_mean=LAWN_H, w_mean=0.0075, bend=0.5, segs=2, tuft=0.04)
ground(col_a=(0.05, 0.08, 0.018, 1), col_b=(0.09, 0.13, 0.03, 1))

# trees up-sun, out of frame: their shadows lie across the far lawn and the near corner; the moon stays lit
bark = mat_bark()
D = sun_dir(SUN_ELEV, SUN_AZIM)
Dh = Vector((D.x, D.y, 0)).normalized()
U = Vector((Dh.y, -Dh.x, 0))
reach = 7.0 / math.tan(math.radians(SUN_ELEV))
for k, (u, r, along) in enumerate([(-9.5, 4.2, 0.0), (10.5, 4.4, 3.0)]):
    P = U * u + Dh * (reach + along)
    canopy(f"shade_tree{k}", (P.x, P.y, 7.0), r, 5200, np.random.default_rng(60 + k), clusters=34, cluster_sigma=0.55,
           leaf_size=0.3, flat=(1, 1, 0.8))
    trunk(f"shade_trunk{k}", (P.x, P.y, 0), r=0.35, h=6.5, mat=bark, rng=np.random.default_rng(70 + k), flare=0.6)

out = OUT + f"04_one-dot-each_{tag}_raw.png"
render(sc, out)
finish(out, OUT + ("04_one-dot-each.png" if FINAL else "04_one-dot-each_draft.png"))
if FINAL:
    bpy.ops.wm.save_as_mainfile(filepath=OUT + "04_one-dot-each.blend")
