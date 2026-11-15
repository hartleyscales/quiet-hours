"""dots.py <frame.png> <cols> <rows> <out.svg> [crop=w:h:x:y]: a photograph as the app draws its pictures: square dots on a lattice, 8x8 ordered dither, one ink."""
import subprocess, sys
src, cols, rows, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
crop = (sys.argv[5] + ',') if len(sys.argv) > 5 else ''
gamma = float(sys.argv[6]) if len(sys.argv) > 6 else 1.0
vf = crop + "format=gray,scale=%d:%d:flags=area" % (cols, rows)
raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", src, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
assert len(raw) == cols * rows, len(raw)
m = [[0]]
while len(m) < 8:
    s = len(m); m = [[4 * m[y % s][x % s] + [[0, 2], [3, 1]][y // s][x // s] for x in range(2 * s)] for y in range(2 * s)]
P, D = 6, 4
n = 0; r = []
for j in range(rows):
    for i in range(cols):
        lum = raw[j * cols + i] / 255
        d = 1 - lum ** gamma          # gamma under 1 lifts the shadows, so a dark object keeps its form
        if d > 0.04 and (m[j & 7][i & 7] + 0.5) / 64 < d:
            r.append('<rect x="%d" y="%d" width="%d" height="%d"/>' % (i * P + 1, j * P + 1, D, D)); n += 1
open(out, "w").write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" fill="#3A342E">%s</svg>' % (cols * P, rows * P, cols * P, rows * P, "".join(r)))
print(out, n, "dots")
