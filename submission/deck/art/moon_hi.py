"""moon_hi.py: the app's dot moon (design/scripts/color_moon.py) with the disc radius as an argument, for the deck's cover.
The dot moon at the original dot size, with each dot carrying tone and a little colour from NASA's map.
Usage: python3 -I moon_hi.py <render_moon.py> <moon.bmp> <out.png> dark 0 <radius in cells>
modes: dark (dithered, light dots for a dark surface; N dots if given), full (a dot in every cell, dark surface), light (dithered, ink dots for the light surface)"""
import importlib.util, math, random, struct, sys
spec = importlib.util.spec_from_file_location("rm", sys.argv[1]); rm = importlib.util.module_from_spec(spec); spec.loader.exec_module(rm)
mode = sys.argv[4]; N = int(sys.argv[5]) if len(sys.argv) > 5 else 0
d = open(sys.argv[2], "rb").read()
off0 = struct.unpack_from("<I", d, 10)[0]
tw, th = struct.unpack_from("<ii", d, 18)
bypp = struct.unpack_from("<H", d, 28)[0] // 8
rowsize = (tw * bypp + 3) & ~3
flip = th > 0; th = abs(th)
def rgb(x, y):
    yy = (th - 1 - y) if flip else y
    i = off0 + yy * rowsize + x * bypp
    return d[i + 2] / 255.0, d[i + 1] / 255.0, d[i] / 255.0
def lum(c): return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
R = float(sys.argv[6])                       # the disc's radius in cells: the cover moon is drawn finer than the app's 58
CW = CH = int(2 * R + 4); MX = MY = R + 2.0; MR = R
P = 6
rm.W, rm.H = CW * P, CH * P
samples = sorted(lum(rgb(x, y)) for y in range(th // 6, th * 5 // 6, 4) for x in range(tw // 4, tw * 3 // 4, 4))
lo, hi = samples[int(len(samples) * 0.06)], samples[int(len(samples) * 0.94)]
def sstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)
SAT = 3.2
cell = [[None] * CW for _ in range(CH)]     # (a, z, hue) per cell inside the disc
for j in range(CH):
    for i in range(CW):
        x, y = (i - MX) / MR, -(j - MY) / MR
        d2 = x * x + y * y
        if d2 >= 1: continue
        z = math.sqrt(1 - d2)
        lat, lon = math.asin(y), math.atan2(x, z)
        u0, v0 = (lon / (2 * math.pi) + 0.5) * tw, (0.5 - lat / math.pi) * th
        acc = [0.0, 0.0, 0.0]
        for du in (-1, 0, 1):
            for dv in (-1, 0, 1):
                c = rgb(int(u0 + du) % tw, min(th - 1, max(0, int(v0 + dv))))
                for k in range(3): acc[k] += c[k] / 9
        l = lum(acc)
        a = min(1.0, max(0.0, (l - lo) / (hi - lo)))
        hue = tuple(max(0.55, min(1.5, 1 + SAT * (acc[k] / max(l, 1e-6) - 1))) for k in range(3))   # colour relative to grey, pushed
        cell[j][i] = (a, z, hue)
def dither(dens):
    on = []
    err = [[0.0] * CW for _ in range(CH)]
    for j in range(CH):
        s = 1 if j % 2 == 0 else -1
        for i in (range(CW) if s == 1 else range(CW - 1, -1, -1)):
            if cell[j][i] is None: continue
            v = dens(*cell[j][i][:2]) + err[j][i]
            o = 1.0 if v >= 0.5 else 0.0
            e = v - o
            if o: on.append((i, j))
            for di, dj, w in ((s, 0, 7 / 16), (-s, 1, 3 / 16), (0, 1, 5 / 16), (s, 1, 1 / 16)):
                ii, jj = i + di, j + dj
                if 0 <= ii < CW and 0 <= jj < CH and cell[jj][ii] is not None: err[jj][ii] += e * w
    return on
if mode == "full":
    on = [(i, j) for j in range(CH) for i in range(CW) if cell[j][i] is not None]
elif mode == "dark":
    base = lambda a, z: (0.10 + 0.82 * sstep(0.18, 0.82, a)) * (1 - 0.30 * (1 - z) ** 2.2)
    if N:
        lo_k, hi_k = 0.05, 3.0
        for _ in range(30):
            k = (lo_k + hi_k) / 2
            if len(dither(lambda a, z: min(0.97, base(a, z) * k))) < N: lo_k = k
            else: hi_k = k
        on = dither(lambda a, z: min(0.97, base(a, z) * hi_k))
        rnd = random.Random(7)
        while len(on) > N: on.pop(rnd.randrange(len(on)))
    else:
        on = dither(base)
else:
    on = dither(lambda a, z: min(0.94, 0.07 + 0.78 * sstep(0.18, 0.82, 1 - a) + 0.18 * (1 - z) ** 2.2))
# An even edge without a visible line: dots sit exactly on the rim of the disc, evenly spaced, and their spacing
# follows how dense the picture is just inside that stretch of rim. Each keeps its own colour. N is kept by adjusting the inside.
def inside(i, j): return 0 <= i < CW and 0 <= j < CH and cell[j][i] is not None
ring = [(i, j) for j in range(CH) for i in range(CW) if inside(i, j) and not all(inside(i + a, j + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
ringset = set(ring)
if mode != "full":
    onset = set(on)
    ring.sort(key=lambda p: math.atan2(p[1] - MY, p[0] - MX))
    def local(i, j, r=4):
        tot = hit = 0
        for b in range(-r, r + 1):
            for a in range(-r, r + 1):
                q = (i + a, j + b)
                if inside(*q) and q not in ringset:
                    tot += 1; hit += q in onset
        return hit / tot if tot else 0.0
    dens = [local(i, j) for i, j in ring]
    m = len(ring)
    dens = [sum(dens[(k + s) % m] for s in range(-3, 4)) / 7 for k in range(m)]      # smooth along the rim
    edge, acc = set(), 0.5
    for k, p in enumerate(ring):
        acc += min(1.0, max(0.30, math.sqrt(dens[k]) * 1.1))      # a line needs sqrt(density) to match a field of dots
        if acc >= 1: edge.add(p); acc -= 1
    keep = (onset - ringset) | edge
    if N:
        rnd = random.Random(5)
        inner = sorted(keep - ringset); rnd.shuffle(inner)
        while len(keep) > N: keep.discard(inner.pop())
        if len(keep) < N:
            spare = [p for p in ((i, j) for j in range(CH) for i in range(CW)) if inside(*p) and p not in ringset and p not in keep]
            spare.sort(key=lambda p: -cell[p[1]][p[0]][0] + rnd.random() * 0.2)
            for p in spare[:N - len(keep)]: keep.add(p)
    on = sorted(keep, key=lambda p: (p[1], p[0]))
    print("rim dots", len(edge), "of", m)
buf = bytearray(rm.W * rm.H * 4)
sz = 4; o = (P - sz) // 2
for i, j in on:
    a, z, hue = cell[j][i]
    if mode == "full":   t = (0.07 + 0.93 * a ** 1.35) * (1 - 0.34 * (1 - z) ** 1.6)
    elif mode == "dark": t = (0.42 + 0.58 * a ** 1.1) * (1 - 0.25 * (1 - z) ** 1.6)
    if mode == "light":
        t = 0.13 + 0.40 * a ** 1.2                         # ink in the seas, a lighter warm grey in the highlands
        col = tuple(int(max(0, min(255, 255 * t * h))) for h in hue)
    else:
        col = tuple(int(max(0, min(255, 240 * t * h))) for h in hue)
    rm.rect(buf, i * P + o, j * P + o, sz, col + (255,))
rm.write_png(sys.argv[3], buf)
print(sys.argv[3], len(on), "dots", rm.W, rm.H)
