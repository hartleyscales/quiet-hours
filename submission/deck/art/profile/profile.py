"""profile.py <out.svg> [tilt_deg]: a plain side profile of a man's head, facing left, as light dots on the night slide.
Drawn here as an outline through hand-placed points; filled on the app's 2pt lattice with the 8x8 ordered dither, brightest
along the face and falling away toward the back of the head, which the slide's right edge cuts off."""
import math, sys
OUT = sys.argv[1]; TILT = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
W, H = 660, 1080
P = [(760, 70), (600, 60), (478, 70), (378, 102), (300, 152), (262, 208), (272, 238),      # the hair, crown to fringe
     (259, 300), (253, 368), (258, 402),                                          # forehead, brow, the dip under it
     (240, 455), (206, 510), (215, 531), (246, 548),                              # the nose
     (239, 577), (253, 598), (241, 624), (259, 650),                              # lips
     (249, 694), (272, 729), (334, 753), (402, 768),                              # chin and jaw
     (412, 846), (414, 898), (409, 946), (396, 990),                              # the neck, smooth
     (296, 1034), (186, 1090), (110, 1140), (760, 1140)]                          # collarbone and chest, off the bottom
if TILT:
    a = math.radians(TILT); cx, cy = 430, 800
    P = [((x - cx) * math.cos(a) - (y - cy) * math.sin(a) + cx, (x - cx) * math.sin(a) + (y - cy) * math.cos(a) + cy) if y < 1000 else (x, y) for x, y in P]
def spline(pts, n=14):                    # Catmull-Rom through the open run of points
    out = []
    ext = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t * t + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t ** 3) for c in (0, 1)))
    return out + [pts[-1]]
poly = spline(P[:-1]) + [P[-1]]
def crossings(y):
    xs = []
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y): xs.append(x1 + (y - y1) / (y2 - y1) * (x2 - x1))
    return sorted(xs)
m8 = [[0]]
while len(m8) < 8:
    s = len(m8); m8 = [[4 * m8[y % s][x % s] + [[0, 2], [3, 1]][y // s][x // s] for x in range(2 * s)] for y in range(2 * s)]
PITCH, DOT = 6, 4; r = []
for j in range(H // PITCH):
    y = j * PITCH + 3; xs = crossings(y)
    if not xs: continue
    for i in range(W // PITCH):
        x = i * PITCH + 3
        if sum(1 for c in xs if c < x) % 2 == 0: continue
        dx = x - xs[0]
        d = 0.16 + 0.78 * math.exp(-dx / 150.0)
        d *= 1 - 0.45 * max(0.0, (y - 860) / 220.0)          # the chest fades toward the bottom edge
        if (m8[j & 7][i & 7] + 0.5) / 64 < d: r.append('<rect x="%d" y="%d" width="%d" height="%d"/>' % (i * PITCH + 1, j * PITCH + 1, DOT, DOT))
open(OUT, "w").write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" fill="#EAE5DE">%s</svg>' % (W, H, W, H, "".join(r)))
print(OUT, len(r), "dots")
