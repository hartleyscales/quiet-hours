"""dotpic.py: a picture in the app's own dot language (web/dotart.js, ported): shapes as signed distances, embossed with
light from the upper left, laid on a 2pt lattice with the 8x8 ordered dither, one ink. Writes an SVG at 3x.
   python3 dotpic.py telephone out.svg"""
import math, sys
LX = LY = -0.7071
def sdRR(x, y, x0, y0, x1, y1, r):
    qx = abs(x - (x0 + x1) / 2) - ((x1 - x0) / 2 - r); qy = abs(y - (y0 + y1) / 2) - ((y1 - y0) / 2 - r)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
def sdC(x, y, cx, cy, r): return math.hypot(x - cx, y - cy) - r
def sdSeg(x, y, ax, ay, bx, by, w):
    px, py, vx, vy = x - ax, y - ay, bx - ax, by - ay; h = max(0, min(1, (px * vx + py * vy) / (vx * vx + vy * vy)))
    return math.hypot(px - vx * h, py - vy * h) - w
def emboss(sd, x, y, w, mid, amt):
    d = sd(x, y)
    if d > 0: return 0
    gx = sd(x + 1, y) - sd(x - 1, y); gy = sd(x, y + 1) - sd(x, y - 1); g = math.hypot(gx, gy) or 1
    return min(0.97, max(0.1, mid - amt * max(0, 1 + d / w) * ((gx / g) * LX + (gy / g) * LY)))
def cast(sd, x, y):
    d = sd(x - 12, y - 16)
    return 0.2 * max(0, min(1, (8 - d) / 16)) if d < 8 else 0
M8 = [[0]]
while len(M8) < 8:
    s = len(M8); M8 = [[4 * M8[y % s][x % s] + [[0, 2], [3, 1]][y // s][x // s] for x in range(2 * s)] for y in range(2 * s)]

# A desk telephone with its handset down and its cord coiled: the phone that stayed in the room.
BASE = lambda a, b: sdRR(a, b, 92, 196, 298, 352, 30)
def HAND(a, b):
    ends = min(sdRR(a, b, 62, 132, 142, 196, 24), sdRR(a, b, 248, 132, 328, 196, 24))
    bar = sdRR(a, b, 120, 138, 270, 172, 17)
    return min(ends, bar)
KEYS = [(151 + c * 44, 232 + r * 30) for r in range(4) for c in range(3)]
CORD = []
for k in range(19):   # a coil from under the left end of the handset, out and back to the side of the base
    t = k / 18
    CORD.append((70 - 26 * math.sin(t * math.pi), 206 + t * 118))
def cord(a, b): return min(abs(math.hypot(a - cx, b - cy) - 9) - 1.9 for cx, cy in CORD)
def telephone(x, y):
    if HAND(x, y) <= 0: return emboss(HAND, x, y, 16, 0.74, 0.36)
    if BASE(x, y) <= 0:
        if HAND(x - 7, y - 9) < 3: return 0.5                      # the handset's shadow on the base
        for kx, ky in KEYS:
            key = lambda a, b: sdRR(a, b, kx - 15, ky - 9, kx + 15, ky + 9, 8)
            if key(x, y) <= 0: return emboss(key, x, y, 7, 0.84, 0.24)
        return emboss(BASE, x, y, 26, 0.58, 0.46)
    c = cord(x, y)
    if c <= 0: return 0.86
    return max(cast(BASE, x, y), cast(HAND, x, y) * 0.8)

# A ballot: a raised square with a tick cut into it. For "students decide".
BOX = lambda a, b: sdRR(a, b, 105, 136, 285, 316, 34)
TICK = lambda a, b: min(sdSeg(a, b, 152, 228, 184, 262, 11), sdSeg(a, b, 184, 262, 242, 186, 11))
def ballot(x, y):
    if BOX(x, y) <= 0:
        t = TICK(x, y)
        if t <= 0:
            gx = TICK(x + 1, y) - TICK(x - 1, y); gy = TICK(x, y + 1) - TICK(x, y - 1); g = math.hypot(gx, gy) or 1
            return 0.8 if t > -4 and (gx / g) * LX + (gy / g) * LY > 0.2 else 0.04      # cut in: dark on the lit lip, empty inside
        return emboss(BOX, x, y, 24, 0.6, 0.44)
    return cast(BOX, x, y)
# A target: two rings and a centre. For "accurate".
RINGS = [lambda a, b: abs(math.hypot(a - 195, b - 226) - 96) - 13, lambda a, b: abs(math.hypot(a - 195, b - 226) - 54) - 12, lambda a, b: sdC(a, b, 195, 226, 20)]
def target(x, y):
    for k, ring in enumerate(RINGS):
        v = emboss(ring, x, y, 12, 0.62 if k < 2 else 0.8, 0.42)
        if v: return v
    return cast(lambda a, b: sdC(a, b, 195, 226, 109), x, y) if math.hypot(x - 195, y - 226) > 109 else 0.05

# The app's padlock (web/dotart.js `lock`), ported so it can be drawn on a coarser lattice.
LBODY = lambda a, b: sdRR(a, b, 101, 206, 289, 346, 28)
def SHACKLE(a, b):
    d = abs(math.hypot(a - 195, b - 210) - 64) - 13
    return d if b < 214 else max(d, b - 214)
HOLE = lambda a, b: min(sdC(a, b, 195, 262, 15), sdRR(a, b, 188, 262, 202, 308, 7))
def lock(x, y):
    if LBODY(x, y) <= 0:
        hd = HOLE(x, y)
        if hd <= 0:
            gx = HOLE(x + 1, y) - HOLE(x - 1, y); gy = HOLE(x, y + 1) - HOLE(x, y - 1); g = math.hypot(gx, gy) or 1
            return 0.78 if hd > -4 and (gx / g) * LX + (gy / g) * LY > 0.2 else 0.05
        return emboss(LBODY, x, y, 22, 0.6, 0.44)
    return emboss(SHACKLE, x, y, 13, 0.62, 0.44) or cast(LBODY, x, y)

# A crescent moon. For "quiet".
CRESCENT = lambda a, b: max(sdC(a, b, 190, 228, 104), -sdC(a, b, 250, 188, 84))
def crescent(x, y):
    return emboss(CRESCENT, x, y, 22, 0.62, 0.44) or cast(CRESCENT, x, y)

STEP = 2          # the lattice in points: 2 is the app's; a small picture on a slide wants a coarser one so its dots still show
def fill(fn):
    out = []
    for j in range(int(460 / STEP)):
        for i in range(int(390 / STEP)):
            x, y = i * STEP + STEP / 2, j * STEP + STEP / 2; d = fn(x, y)
            if d > 0 and (M8[j & 7][i & 7] + 0.5) / 64 < d: out.append((x - STEP / 3, y - STEP / 3))
    return out
if __name__ == "__main__":
    if len(sys.argv) > 3: STEP = float(sys.argv[3])
    pts = fill(globals()[sys.argv[1]])
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs) - 6, min(ys) - 6, max(xs) + 6 + STEP, max(ys) + 6 + STEP
    W, H = (x1 - x0) * 3, (y1 - y0) * 3
    D = STEP * 2    # the dot is two thirds of its cell, at 3x
    r = "".join('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f"/>' % ((px - x0) * 3, (py - y0) * 3, D, D) for px, py in pts)
    open(sys.argv[2], "w").write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.0f %.0f" width="%.0f" height="%.0f" fill="#3A342E">%s</svg>' % (W, H, W, H, r))
    print(sys.argv[2], len(pts), "dots", "%.0fx%.0f" % (W, H))
