# 03 Four moments
# Four phones standing in short grass like small standing stones, each showing one real screen
# of the week in order (voted, decided, locked, summary). Low sun behind and to one side,
# four long shadows running toward the camera. Focus rests on the third: the quiet hour itself.
#
# KEY CHOICES
CAM_DIST, CAM_ELEV = 1.95, 3.6
CAM_AIM = (0.035, 0.0, 0.115)
LENS, FSTOP = 85, 5.6
SUN_ELEV, SUN_AZIM = 8.0, -24.0      # low, behind the row and to the left: four separate shadows toward camera-right
SKY_STRENGTH = 0.085
EXPOSURE = 0.1
WB = 7000
ORDER = ["voted", "decided", "locked", "summary"]
X0, DX = -0.105, 0.147               # row runs left to right...
Y0, DY = -0.125, 0.065               # ...and steps back, so the week recedes
LEAN = [7.0, 4.5, 6.0, 8.5]          # degrees back from upright
YAW = [5.0, -3.0, 1.5, -6.0]
SINK = 0.012
LAWN_H = 0.021
FOCUS_INDEX = 2
SEED = 31

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, numpy as np
from qh_kit import *

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FINAL = "final" in args
tag = "final" if FINAL else "draft"

sc = reset()
setup_render(sc, *((2560, 1440, 500) if FINAL else (1280, 720, 96)), exposure=EXPOSURE,
             noise=0.01 if FINAL else 0.035, wb=WB)
rng = np.random.default_rng(SEED)
CAL = calibrate_screen(sc)       # screens are emitted through the inverse of the view transform: they read true
sky(sc, SUN_ELEV, SUN_AZIM, SKY_STRENGTH, aerosol=2.2)

e = math.radians(CAM_ELEV)
CAM_LOC = (CAM_AIM[0], CAM_AIM[1] - CAM_DIST * math.cos(e), CAM_AIM[2] + CAM_DIST * math.sin(e))

keep_out = []
focus = None
for i, nm in enumerate(ORDER):
    ph = build_phone("phone_" + nm, mat_screen("scr_" + nm, SCREENS + nm + ".png", 1.0, calib=CAL))
    x, y = X0 + DX * i, Y0 + DY * i
    z = CASE_H / 2 * math.cos(math.radians(LEAN[i])) - SINK
    place(ph, (x, y, z), (90 - LEAN[i], 0, YAW[i]))
    keep_out.append((x, y + 0.004, CASE_W / 2 + 0.002, 0.008, YAW[i]))
    if i == FOCUS_INDEX:
        focus = (x, y - 0.006, z + 0.01)

cam = camera(sc, CAM_LOC, CAM_AIM, LENS, FSTOP, focus)

g = mat_grass()
apex = (CAM_LOC[0], CAM_LOC[1])
p1 = wedge_points(rng, apex, 0, 16, 1.0, 2.9, 380000)
p1 = p1[exclude(p1, keep_out)]
make_grass("lawn_near", p1, g, rng, h_mean=LAWN_H, w_mean=0.0022, bend=0.45, segs=4, tuft=0.018)
p2 = wedge_points(rng, apex, 0, 18, 2.9, 6.5, 130000)
make_grass("lawn_mid", p2, g, rng, h_mean=LAWN_H, w_mean=0.0036, bend=0.45, segs=3)
p3 = wedge_points(rng, apex, 0, 20, 6.5, 16.0, 22000)
make_grass("lawn_far", p3, g, rng, h_mean=LAWN_H * 1.2, w_mean=0.009, bend=0.45, segs=2, tuft=0.05)
p4 = wedge_points(rng, apex, 0, 22, 16.0, 60.0, 1300)
make_grass("lawn_horizon", p4, g, rng, h_mean=LAWN_H * 2.0, w_mean=0.04, bend=0.45, segs=2, tuft=0.2)
ground(col_a=(0.05, 0.08, 0.018, 1), col_b=(0.09, 0.13, 0.03, 1))

bark = mat_bark()
tree_line(np.random.default_rng(8), n=16, r0=50, r1=120, heading_deg=4, half_fov=11, bark=bark)

# two real trees up-sun, out of frame: their long shadows lie either side of the row, which stays in the sun
D = sun_dir(SUN_ELEV, SUN_AZIM)
Dh = Vector((D.x, D.y, 0)).normalized()
U = Vector((Dh.y, -Dh.x, 0))
reach = 7.0 / math.tan(math.radians(SUN_ELEV))
for k, (u, r, along) in enumerate([(-5.6, 3.6, 0.0), (6.4, 4.0, 2.0)]):
    P = U * u + Dh * (reach + along)
    canopy(f"shade_tree{k}", (P.x, P.y, 7.0), r, 5200, np.random.default_rng(40 + k), clusters=34, cluster_sigma=0.55,
           leaf_size=0.3, flat=(1, 1, 0.8))
    trunk(f"shade_trunk{k}", (P.x, P.y, 0), r=0.35, h=6.5, mat=bark, rng=np.random.default_rng(50 + k), flare=0.6)

# a few fallen sycamore leaves, so the lawn is a place and not a surface
leafA = mat_leaf("leafA", a=(0.50, 0.33, 0.07, 1), b=(0.26, 0.13, 0.04, 1), green=(0.36, 0.34, 0.07, 1))
leafB = mat_leaf("leafB", a=(0.58, 0.36, 0.09, 1), b=(0.33, 0.15, 0.045, 1))
lr = np.random.default_rng(77)
lp = wedge_points(lr, apex, 0, 13, 1.2, 5.5, 5.0)
lp = lp[exclude(lp, [(0.12, -0.03, 0.36, 0.22, 30)])]
lp = lp[lp[:, 1] > -0.25]
for k, (x, y) in enumerate(lp):
    fallen_leaf(f"leaf{k}", leafA if k % 2 else leafB, (x, y, LAWN_H * 0.9),
                (lr.uniform(-12, 12), lr.uniform(-12, 12), lr.uniform(0, 360)), lr.uniform(0.045, 0.06), lr.uniform(0.2, 0.5), lr)

out = OUT + f"03_four-moments_{tag}_raw.png"
render(sc, out)
finish(out, OUT + ("03_four-moments.png" if FINAL else "03_four-moments_draft.png"))
if FINAL:
    bpy.ops.wm.save_as_mainfile(filepath=OUT + "03_four-moments.blend")
