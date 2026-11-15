# calib.py : measure a view transform on an emission ramp (own process, CPU). Writes a JSON cache.
# blender -b -P calib.py -- <exposure> <wb> <look> <out.json>
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from qh_kit import *
from qh_kit import _calibrate_here
a = sys.argv[sys.argv.index("--") + 1:]
sc = reset()
setup_render(sc, 1024, 16, 4, exposure=float(a[0]), look=a[2], wb=(float(a[1]) if a[1] != "none" else None))
sc.cycles.device = "CPU"
cal = _calibrate_here(sc)
json.dump(dict(targets=list(map(float, cal["targets"])), curves=[list(map(float, c)) for c in cal["curves"]]), open(a[3], "w"))
