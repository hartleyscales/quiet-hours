"""face_dots.py <frame.png> <mask.png> <crop w:h:x:y> <cols> <out.svg> [gamma] [floor]: a person from a film frame as light dots on the night
slide, the way the app draws its night moon: a 2pt lattice, the 8x8 ordered dither, one cream ink. Fades out toward the bottom."""
import subprocess, sys
src, msk, crop, cols, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
gamma = float(sys.argv[6]) if len(sys.argv) > 6 else 1.2; floor = float(sys.argv[7]) if len(sys.argv) > 7 else 0.1
w, h = [int(v) for v in crop.split(":")[:2]]; rows = round(cols * h / w)
def raw(path, extra=""):
    vf = "crop=%s,format=gray,%sscale=%d:%d:flags=area" % (crop, extra, cols, rows)
    b = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    assert len(b) == cols * rows, len(b); return b
L, M = raw(src, "unsharp=7:7:1.4,"), raw(msk)
m8 = [[0]]
while len(m8) < 8:
    s = len(m8); m8 = [[4 * m8[y % s][x % s] + [[0, 2], [3, 1]][y // s][x // s] for x in range(2 * s)] for y in range(2 * s)]
inside = sorted(L[k] for k in range(cols * rows) if M[k] > 127)
lo, hi = inside[int(len(inside) * 0.04)], inside[int(len(inside) * 0.985)]      # stretch the tones the person actually has
P, D = 6, 4; r = []
for j in range(rows):
    fade = min(1.0, max(0.0, (rows - j) / (rows * 0.34)))      # the last third dissolves
    for i in range(cols):
        m = M[j * cols + i] / 255
        if m < 0.5: continue
        t = min(1.0, max(0.0, (L[j * cols + i] - lo) / (hi - lo)))
        d = (floor + (1 - floor) * t ** gamma) * fade
        if (m8[j & 7][i & 7] + 0.5) / 64 < d: r.append('<rect x="%d" y="%d" width="%d" height="%d"/>' % (i * P + 1, j * P + 1, D, D))
open(out, "w").write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" fill="#EAE5DE">%s</svg>' % (cols * P, rows * P, cols * P, rows * P, "".join(r)))
print(out, len(r), "dots", cols, rows)
