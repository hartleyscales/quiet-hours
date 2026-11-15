"""A sparse field of stars in the same dots as the moon, for the whole locked screen. Usage: python3 -I stars_art.py <render_moon.py> <out.png>"""
import importlib.util, random, sys
spec = importlib.util.spec_from_file_location("rm", sys.argv[1]); rm = importlib.util.module_from_spec(spec); spec.loader.exec_module(rm)
CW, CH, P = 195, 422, 6
rm.W, rm.H = CW * P, CH * P
MX, MY, MR = 97.0, 160.0, 66.0
rnd = random.Random(11)
buf = bytearray(rm.W * rm.H * 4)
sz = 4; off = (P - sz) // 2
n = 0
taken = set()
while n < 330:
    i, j = rnd.randrange(2, CW - 2), rnd.randrange(2, CH - 2)
    if (i - MX) ** 2 + (j - MY) ** 2 < MR * MR: continue
    if any((i + a, j + b) in taken for a in (-2, -1, 0, 1, 2) for b in (-2, -1, 0, 1, 2)): continue
    taken.add((i, j))
    r = rnd.random()
    alpha = 235 if r < 0.16 else (140 if r < 0.52 else 78)
    rm.rect(buf, i * P + off, j * P + off, sz, (234, 229, 222, alpha))
    n += 1
rm.write_png(sys.argv[2], buf)
print("stars", n, rm.W, rm.H)
