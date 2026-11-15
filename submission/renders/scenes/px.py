# px.py : print display-space pixel values of a PNG at given x,y (top-left origin). blender -b -P px.py -- file x,y x,y ...
import bpy, sys, numpy as np
a = sys.argv[sys.argv.index("--") + 1:]
img = bpy.data.images.load(a[0])
img.colorspace_settings.name = "Non-Color"
w, h = img.size
p = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(p); p = p.reshape(h, w, 4)
for s in a[1:]:
    x, y = [int(v) for v in s.split(",")]
    blk = p[h - 1 - y - 2:h - 1 - y + 3, x - 2:x + 3, :3].mean((0, 1))
    print(s, [int(round(v * 255)) for v in blk], "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in blk))
