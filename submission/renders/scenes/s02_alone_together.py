# 02 Alone, and together   (two frames, one camera)
# A lawn after sunset with a few dozen phones lying face up, receding into soft focus.
#   A: every screen lit and busy (abstract soft colour, no invented interface) except one dark phone
#      in the foreground: one person holding out alone.
#   B: every phone on the app's night screen (the real `locked` screenshot) at the same moment.
# Run:  blender -b -P s02_alone_together.py -- A|B [final]
#
# KEY CHOICES
CAM_H, CAM_TILT = 0.42, 17.0         # camera height (m), degrees below the horizon
LENS, FSTOP = 50, 8.0
SUN_ELEV, SUN_AZIM = 0.5, 40.0       # sun disc switched off: afterglow only, low on the right
SKY_STRENGTH = 1.15                  # dusk ambient level
EXPOSURE = 0.0
WB = 11500
HERO = (0.06, 1.06)                  # the hold-out phone, in clay
BUSY_STRENGTH = 2.1
N_PHONES = 44
R0, R1, HALF = 0.92, 4.1, 19.0       # where the phones lie: the top of the frame stays empty lawn
SPACING = 0.25
LAWN_H = 0.024
SEED = 4
CASES = ["#34373A", "#C7BDA8", "#5F6D5A", "#2B3542", "#8B8985", "#6C4A3A", None, "#34373A", "#A9A39A"]

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, numpy as np
from qh_kit import *

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FINAL = "final" in args
WHICH = "B" if "B" in args else "A"
name = "02a_alone" if WHICH == "A" else "02b_together"

sc = reset()
setup_render(sc, *((2560, 1440, 600) if FINAL else (1280, 720, 128)), exposure=EXPOSURE,
             noise=0.01 if FINAL else 0.035, wb=WB)
CAL = calibrate_screen(sc)
rng = np.random.default_rng(SEED)
s, bg = sky(sc, SUN_ELEV, SUN_AZIM, SKY_STRENGTH, aerosol=2.5, sun_disc=False)

t = math.radians(CAM_TILT)
CAM_LOC = (0.0, 0.0, CAM_H)
aim = (0.0, CAM_H / math.tan(t), 0.0)
cam = camera(sc, CAM_LOC, aim, LENS, FSTOP, (HERO[0], HERO[1], 0.03))

# --- where the phones lie: dart-throwing, hero first
pts = [np.array(HERO)]
tries = 0
while len(pts) < N_PHONES and tries < 20000:
    tries += 1
    r = math.sqrt(rng.uniform(R0 * R0, R1 * R1))
    a = math.radians(90) + rng.uniform(-math.radians(HALF), math.radians(HALF))
    p = np.array([r * math.cos(a), r * math.sin(a)])
    dmin = SPACING * (1.15 if np.linalg.norm(p - pts[0]) < 0.4 else 1.0)
    if all(np.linalg.norm(p - q) > dmin for q in pts):
        pts.append(p)
print("phones", len(pts))

locked = mat_screen("scr_locked", SCREENS + "locked.png", 1.0, calib=CAL, ior=1.18)
busy = mat_screen_busy("scr_busy", BUSY_STRENGTH)
dark = mat_screen("scr_off", dark=True, ior=1.18)
keep_out = []
for i, p in enumerate(pts):
    hero = i == 0
    if WHICH == "B":
        m = locked
    else:
        m = dark if hero else busy
    case = CLAY if hero else CASES[int(rng.integers(0, len(CASES)))]
    ph = build_phone(f"phone{i}", m, case_hex=case or CLAY, with_case=case is not None)
    # top of the phone away from the camera, so every screen reads upright; a little yaw, a little prop from the turf
    face = math.degrees(math.atan2(p[0], p[1]))
    yaw = -face + (rng.uniform(-9, 9) if hero else float(np.clip(rng.normal(0, 20), -34, 34)))
    pitch = rng.uniform(7, 13)
    roll = rng.normal(0, 3)
    place(ph, (p[0], p[1], LAWN_H * 0.55 + 0.012 + 0.07 * math.sin(math.radians(pitch))), (pitch, roll, yaw))
    keep_out.append((p[0], p[1], CASE_W / 2 - 0.004, CASE_H / 2 - 0.006, yaw))

# --- lawn
g = mat_grass()
apex = (0.0, 0.0)
p1 = wedge_points(rng, apex, 0, 23, 0.6, 2.2, 380000)
p1 = p1[exclude(p1, keep_out)]
make_grass("lawn_near", p1, g, rng, h_mean=LAWN_H, w_mean=0.0024, bend=0.5, segs=4)
p2 = wedge_points(rng, apex, 0, 24, 2.2, 5.0, 140000)
p2 = p2[exclude(p2, keep_out)]
make_grass("lawn_mid", p2, g, rng, h_mean=LAWN_H, w_mean=0.0038, bend=0.5, segs=3)
p3 = wedge_points(rng, apex, 0, 26, 5.0, 22.0, 16000)
make_grass("lawn_far", p3, g, rng, h_mean=LAWN_H * 1.2, w_mean=0.011, bend=0.5, segs=2, tuft=0.06)
ground()

out = OUT + f"{name}_{'final' if FINAL else 'draft'}_raw.png"
render(sc, out)
finish(out, OUT + (f"{name}.png" if FINAL else f"{name}_draft.png"), grain=0.026, halation=0.5 if WHICH == "A" else 0.0)
if FINAL:
    bpy.ops.wm.save_as_mainfile(filepath=OUT + f"{name}.blend")
