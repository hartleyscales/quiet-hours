# usage: blender -b -P measure.py -- file.png [file2.png ...]   prints alpha box, edge alpha, screen and case colours
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
for f in args():
    p = load_px(f); h, w = p.shape[:2]; al = p[..., 3]; rgb = (p[..., :3] * 255).round().astype(int)
    ys, xs = np.nonzero(al > 0.99); print(os.path.basename(f), w, "x", h, "opaque box x", xs.min(), xs.max(), "y", ys.min(), ys.max())
    ys2, xs2 = np.nonzero(al > 0.004); print("  any-alpha box x", xs2.min(), xs2.max(), "y", ys2.min(), ys2.max(),
          "edge alpha max (0-255): top %.1f bottom %.1f left %.1f right %.1f" % (al[0].max() * 255, al[-1].max() * 255, al[:, 0].max() * 255, al[:, -1].max() * 255))
    # most common opaque colour = the screen background
    op = rgb[al > 0.99]; key = op[:, 0] * 65536 + op[:, 1] * 256 + op[:, 2]; vals, cnt = np.unique(key, return_counts=True)
    top = np.argsort(-cnt)[:4]
    print("  most common opaque colours:", [((int(vals[i]) >> 16), (int(vals[i]) >> 8) & 255, int(vals[i]) & 255, int(cnt[i])) for i in top])
    sh = al[(al > 0.004) & (al < 0.99)]; print("  partial alpha: max %.3f  count %d" % (sh.max() if len(sh) else 0, len(sh)))
    # shadow profile: darkest shadow alpha outside the phone
    cx = (xs.min() + xs.max()) // 2
    col = al[:, cx]; print("  alpha down centre column below phone:", [round(float(col[min(h - 1, ys.max() + d)]), 3) for d in (3, 10, 30, 60, 120, 240, 480)])
    case = (al > 0.99) & ((rgb[..., 0] - rgb[..., 2]) > 30) & (rgb[..., 1] < rgb[..., 0] - 20)
    cy, cx_ = np.nonzero(case); wall = case & (np.arange(w)[None, :] < xs.min() + 0.035 * (xs.max() - xs.min()))
    if case.sum() > 100:
        cc = rgb[case]; lum_ = cc.sum(1); hi = cc[lum_ >= np.quantile(lum_, 0.75)]
        print("  case: median", np.median(cc, 0).astype(int), " lit side (brightest quarter, median)", np.median(hi, 0).astype(int), " left strip median", (np.median(rgb[wall], 0).astype(int) if wall.sum() > 50 else None))
    row = (ys.min() + ys.max()) // 2
    print("  case samples (rgb) left wall / lip:", rgb[row, xs.min() + 12], rgb[row, xs.min() + 40], rgb[ys.min() + 14, cx], rgb[ys.max() - 14, cx])
