# usage: blender -b -P comp.py -- out.png "#EAE5DE" in1.png [in2.png ...]   lays the cut-outs side by side over a flat colour
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
a = args(); out, hexc, files = a[0], a[1], [f for f in a[2:] if not f.startswith("--")]
h_ = hexc.lstrip("#"); bgc = np.array([int(h_[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)
tiles = []
for f in files:
    p = load_px(f); al = p[..., 3:4]; rgb = p[..., :3]
    if "--probe" in a:
        ys, xs = np.nonzero(p[..., 3] > 0.99); row = (ys.min() + ys.max()) // 2; x0 = xs[ys == row].min()
        print("edge pixels (rgb255, a) at row", row, [(tuple((p[row, x, :3] * 255).round().astype(int)), round(float(p[row, x, 3]), 2)) for x in range(x0 - 4, x0 + 3)])
    comp = rgb * al + bgc[None, None] * (1 - al)          # Blender hands back straight (unassociated) colour for byte PNGs
    pad = 60; h, w = comp.shape[:2]
    canvas = np.tile(bgc[None, None], (h + 2 * pad, w + 2 * pad, 1)); canvas[pad:pad + h, pad:pad + w] = comp
    tiles.append(canvas)
H = max(t.shape[0] for t in tiles)
tiles = [np.concatenate([t, np.tile(bgc[None, None], (H - t.shape[0], t.shape[1], 1))], 0) for t in tiles]
save_px(np.concatenate(tiles, 1), out)
print("wrote", out)
