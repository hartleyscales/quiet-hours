# usage: blender -b -P crop.py -- in.png out.png x0 y0 x1 y1 ["#RRGGBB"]   cuts a 1:1 window (over a flat colour if the file has alpha)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
a = args(); p = load_px(a[0]); x0, y0, x1, y1 = [int(v) for v in a[2:6]]
c = p[y0:y1, x0:x1]
if len(a) > 6:
    h_ = a[6].lstrip("#"); bg = np.array([int(h_[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)
    c = np.concatenate([c[..., :3] * c[..., 3:4] + bg * (1 - c[..., 3:4]), np.ones_like(c[..., :1])], -1)
save_px(c, a[1]); print("wrote", a[1])
