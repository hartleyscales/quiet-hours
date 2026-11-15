# 01 Under the tree
# A patch of lawn at the foot of a sycamore, late afternoon. A sketch pad with a pencil drawing
# of branches, the pencil across it, fallen leaves, and the phone face down in the grass.
#
# KEY CHOICES
CAM_DIST, CAM_ELEV = 1.62, 25.0      # metres from the aim point, degrees above the lawn
CAM_AIM = (0.0, 0.04, 0.02)
LENS, FSTOP = 100, 4.0               # long lens, shallow focus resting on the page
FOCUS = (0.12, -0.02, 0.035)
SUN_ELEV, SUN_AZIM = 17.0, -58.0     # low sun from the left and a little behind: raking light
SKY_STRENGTH = 0.085
EXPOSURE = 0.22
WB = 7300                            # camera white balance set cool-side, so the sun reads warm
NOTEBOOK = dict(loc=(0.125, 0.0, 0.024), rot=(7.0, 0.0, -11.0))
PHONE = dict(loc=(-0.085, 0.125, 0.0275), rot=(3.0, 183.0, 27.0))   # face down, case and camera up
PENCIL_LOCAL = dict(loc=(0.036, -0.034, 0.0155), rot=(0, 0, 17.0))
LAWN_H = 0.028
SEED = 11

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, numpy as np
from qh_kit import *
from qh_props import *

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FINAL = "final" in args
tag = "final" if FINAL else "draft"

sc = reset()
setup_render(sc, *((2560, 1440, 500) if FINAL else (1280, 720, 96)), exposure=EXPOSURE,
             noise=0.01 if FINAL else 0.035, wb=WB)
rng = np.random.default_rng(SEED)
sky(sc, SUN_ELEV, SUN_AZIM, SKY_STRENGTH, aerosol=1.8)
D = sun_dir(SUN_ELEV, SUN_AZIM)

e = math.radians(CAM_ELEV)
CAM_LOC = (CAM_AIM[0], CAM_AIM[1] - CAM_DIST * math.cos(e), CAM_AIM[2] + CAM_DIST * math.sin(e))
cam = camera(sc, CAM_LOC, CAM_AIM, LENS, FSTOP, FOCUS)

# --- props
draw = make_drawing(OUT + "tex_drawing.png", seed=7)
nb = build_notebook("notebook", draw)
place(nb, NOTEBOOK["loc"], NOTEBOOK["rot"])
pen = build_pencil("pencil")
pen.parent = nb
place(pen, PENCIL_LOCAL["loc"], PENCIL_LOCAL["rot"])

ph = build_phone("phone", mat_screen("scr_dark", dark=True))
place(ph, PHONE["loc"], PHONE["rot"])

leafA = mat_leaf("leafA", a=(0.50, 0.33, 0.07, 1), b=(0.26, 0.13, 0.04, 1), green=(0.36, 0.34, 0.07, 1))
leafB = mat_leaf("leafB", a=(0.58, 0.36, 0.09, 1), b=(0.33, 0.15, 0.045, 1))
lr = np.random.default_rng(5)
# one on the corner of the pad, one that has landed on the phone, the rest in the grass
fallen_leaf("leaf1", leafB, (0.030, 0.085, 0.040), (8, -6, 150), 0.050, 0.3, lr)
fallen_leaf("leaf2", leafA, (-0.098, 0.066, 0.036), (-8, 8, 250), 0.045, 0.3, lr)
fallen_leaf("leaf3", leafA, (-0.03, -0.14, 0.030), (5, 3, 20), 0.052, 0.22, lr)
fallen_leaf("leaf4", leafB, (-0.33, 0.42, 0.03), (-8, 10, 300), 0.058, 0.6, lr)
fallen_leaf("leaf5", leafA, (0.22, 0.52, 0.03), (10, -12, 100), 0.056, 0.6, lr)
fallen_leaf("leaf6", leafB, (-0.14, 0.95, 0.03), (10, 5, 200), 0.058, 0.6, lr)
fallen_leaf("leaf7", leafB, (0.30, -0.22, 0.03), (-6, 8, 330), 0.05, 0.6, lr)

# --- lawn
g = mat_grass()
apex = (CAM_LOC[0], CAM_LOC[1])
keep_out = [(NOTEBOOK["loc"][0], NOTEBOOK["loc"][1], PAGE_W / 2 - 0.003, PAGE_H / 2 - 0.003, NOTEBOOK["rot"][2]),
            (PHONE["loc"][0], PHONE["loc"][1], CASE_W / 2 - 0.004, CASE_H / 2 - 0.004, PHONE["rot"][2])]
p1 = wedge_points(rng, apex, 0, 17, 0.9, 2.3, 420000)
p1 = p1[exclude(p1, keep_out)]
make_grass("lawn_near", p1, g, rng, h_mean=LAWN_H, w_mean=0.0023, bend=0.5, segs=4)
p2 = wedge_points(rng, apex, 0, 19, 2.3, 4.5, 150000)
make_grass("lawn_mid", p2, g, rng, h_mean=LAWN_H, w_mean=0.0036, bend=0.5, segs=3)
p3 = wedge_points(rng, apex, 0, 24, 4.5, 12.0, 26000)
make_grass("lawn_far", p3, g, rng, h_mean=LAWN_H * 1.1, w_mean=0.008, bend=0.5, segs=2, tuft=0.05)
ground()

# --- the tree: its foot at the edge of frame, and its leaves between the sun and the lawn
bark = mat_bark()
trunk("sycamore", (0.70, 1.02, 0), r=0.34, h=5, mat=bark, rng=np.random.default_rng(4), flare=1.3)
S = Vector((0.03, 0.05, 0))
pool = [(Vector(NOTEBOOK["loc"]) + Vector((-0.01, 0.0, 0)), D, 0.17)]      # the page sits in a pool of sun
canopy("gobo_far", S + D * 10.0, 3.3, 7000, np.random.default_rng(21), clusters=30, cluster_sigma=0.45,
       leaf_size=0.085, clear=pool)
canopy("gobo_near", S + D * 4.5, 1.5, 2000, np.random.default_rng(22), clusters=16, cluster_sigma=0.28,
       leaf_size=0.075, clear=pool)

canopy("gobo_twig", Vector(NOTEBOOK["loc"]) + Vector((0.06, 0.02, 0)) + D * 2.3, 0.55, 260, np.random.default_rng(23), clusters=9,
       cluster_sigma=0.12, leaf_size=0.07, clear=[(Vector(NOTEBOOK["loc"]) + Vector((0.02, -0.02, 0)), D, 0.075)])

out = OUT + f"01_under-the-tree_{tag}_raw.png"
render(sc, out)
finish(out, OUT + ("01_under-the-tree.png" if FINAL else "01_under-the-tree_draft.png"))
if FINAL:
    bpy.ops.wm.save_as_mainfile(filepath=OUT + "01_under-the-tree.blend")
