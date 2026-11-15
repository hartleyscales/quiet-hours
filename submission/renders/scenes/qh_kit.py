# qh_kit.py : shared kit for the Quiet Hours "scenes" look tests.
# Everything here is built procedurally in Blender on 2026-11-15: phone, case,
# grass, sycamore leaves, notebook, pencil, tree line, sky. No external assets
# except the app's own screenshots, used unaltered as screen emission.
#
# Units are metres. Ground is z = 0. Cameras look roughly toward +Y.

import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector, Matrix, Euler

SCREENS = "/Users/hartleyscales/quiet-hours/submission/screens/"
OUT = "/Users/hartleyscales/quiet-hours/submission/renders/scenes/"

CLAY = "#B4775E"
GREIGE = "#EAE5DE"


# ---------------------------------------------------------------- colour
def s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexcol(h, a=1.0):
    h = h.lstrip("#")
    return (s2l(int(h[0:2], 16) / 255), s2l(int(h[2:4], 16) / 255), s2l(int(h[4:6], 16) / 255), a)


# ---------------------------------------------------------------- scene
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def setup_render(sc, w=1280, h=720, samples=64, exposure=0.0, look="AgX - Medium High Contrast",
                 view="AgX", noise=0.03, wb=None, wb_tint=10.0):
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "METAL"
    c = sc.cycles
    c.device = "GPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = noise
    c.use_denoising = True
    try:
        c.denoiser = "OPENIMAGEDENOISE"
        c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    except Exception as e:
        print("denoiser", e)
    c.max_bounces = 8
    c.diffuse_bounces = 3
    c.glossy_bounces = 4
    c.transmission_bounces = 6
    c.transparent_max_bounces = 12
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 8.0
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = view
    try:
        sc.view_settings.look = look
    except Exception:
        sc.view_settings.look = "None"
    sc.view_settings.exposure = exposure
    if wb is not None:
        try:
            sc.view_settings.use_white_balance = True
            sc.view_settings.white_balance_temperature = wb
            sc.view_settings.white_balance_tint = wb_tint
        except Exception as e:
            print("white balance unavailable", e)
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "16"
    sc.render.use_persistent_data = False


def sky(sc, elev_deg, azim_deg, strength=0.003, aerosol=1.0, ozone=1.0, air=1.0, sun_size_deg=0.545,
        sun_intensity=1.0, altitude=100.0, sun_disc=True):
    """Blender's own multiple-scattering sky. azim_deg: 0 = sun toward +Y, positive toward +X."""
    w = bpy.data.worlds.new("sky")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    s = nt.nodes.new("ShaderNodeTexSky")
    s.sky_type = "MULTIPLE_SCATTERING"
    s.sun_elevation = math.radians(elev_deg)
    s.sun_rotation = math.radians(azim_deg)
    s.sun_disc = sun_disc
    s.sun_size = math.radians(sun_size_deg)
    s.sun_intensity = sun_intensity
    s.aerosol_density = aerosol
    s.ozone_density = ozone
    s.air_density = air
    try:
        pass  # altitude left at Blender default
    except Exception:
        pass
    nt.links.new(s.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = strength
    return s, bg


def sun_dir(elev_deg, azim_deg):
    e, a = math.radians(elev_deg), math.radians(azim_deg)
    return Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))


def camera(sc, loc, target, lens=70, fstop=4.0, focus=None, sensor=36.0, blades=9):
    cam = bpy.data.cameras.new("cam")
    cam.lens = lens
    cam.sensor_width = sensor
    cam.sensor_fit = "HORIZONTAL"
    cam.clip_start = 0.01
    cam.clip_end = 2000
    ob = bpy.data.objects.new("cam", cam)
    sc.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = fstop
    cam.dof.aperture_blades = blades
    cam.dof.focus_distance = (Vector(focus if focus is not None else target) - Vector(loc)).length
    sc.camera = ob
    return ob


def link(ob, parent=None):
    bpy.context.scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def new_obj(name, mesh, mat=None, parent=None):
    ob = bpy.data.objects.new(name, mesh)
    if mat is not None:
        mesh.materials.append(mat)
    return link(ob, parent)


def smooth(mesh):
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.update()


def bevel(ob, width, segs=4, angle=60, weighted=True):
    m = ob.modifiers.new("bevel", "BEVEL")
    m.width = width
    m.segments = segs
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.harden_normals = False
    if weighted:
        wn = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
        wn.keep_sharp = True
        wn.weight = 100
    smooth(ob.data)


# ---------------------------------------------------------------- materials
def mat_principled(name, base, rough=0.5, metallic=0.0, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = base
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metallic
    for k, v in kw.items():
        p.inputs[k].default_value = v
    return m


def add_bump(m, scale=800.0, strength=0.1, detail=4.0, dist=0.0002):
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = dist
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    nt.links.new(n.outputs["Fac"], b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return n


VMIN, VMAX = 0.002, 24.0


def calibrate_screen(sc):
    """Cached, out-of-process version of _calibrate_here (a second render inside one Blender process
    crashed Metal's kernel cache on this machine)."""
    import subprocess, json
    vs = sc.view_settings
    wb = getattr(vs, "white_balance_temperature", None) if getattr(vs, "use_white_balance", False) else None
    key = f"{vs.exposure:.3f}_{wb if wb else 'none'}_{vs.look.replace(' ', '')}"
    path = OUT + f"_calib_{key}.json"
    if not os.path.exists(path):
        subprocess.run([bpy.app.binary_path, "-b", "-P", OUT + "calib.py", "--", str(vs.exposure),
                        str(wb) if wb else "none", vs.look, path], check=True, capture_output=True)
    d = json.load(open(path))
    return dict(targets=np.array(d["targets"]), curves=[np.array(c) for c in d["curves"]])


def _calibrate_here(sc):
    """Measure this scene's view transform (AgX + look + exposure + white balance) on a ramp of pure
    emission, and return, per channel, the scene-linear emission that lands on each display value.
    Used so a screenshot shown on a phone comes out of the render with its own colours."""
    keep = (sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples, sc.cycles.use_denoising,
            sc.render.filepath, sc.world, sc.camera)
    w = bpy.data.worlds.new("black")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.0
    sc.world = w
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -500))
    pl = bpy.context.active_object
    pl.scale = (1, 0.05, 1)
    m = bpy.data.materials.new("ramp")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[0].default_value = VMAX / VMIN
    ml = nt.nodes.new("ShaderNodeMath")
    ml.operation = "MULTIPLY"
    ml.inputs[1].default_value = VMIN
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs[0], pw.inputs[1])
    nt.links.new(pw.outputs[0], ml.inputs[0])
    nt.links.new(ml.outputs[0], em.inputs["Strength"])
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    pl.data.materials.append(m)
    cam = bpy.data.cameras.new("calcam")
    cam.type = "ORTHO"
    cam.ortho_scale = 1.0
    co = bpy.data.objects.new("calcam", cam)
    sc.collection.objects.link(co)
    co.location = (0, 0, -499)
    sc.camera = co
    sc.render.resolution_x, sc.render.resolution_y = 1024, 16
    sc.cycles.samples = 4
    sc.cycles.use_denoising = False
    path = OUT + "_calib.png"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = "Non-Color"
    a = np.empty(1024 * 16 * 4, np.float32)
    img.pixels.foreach_get(a)
    d = a.reshape(16, 1024, 4)[4:12].mean(0)[:, :3]          # display value per channel along the ramp
    x = (np.arange(1024) + 0.5) / 1024
    targets = np.linspace(0, 1, 33)
    curves = []
    for c in range(3):
        dc = np.maximum.accumulate(d[:, c])
        curves.append(np.interp(targets, dc, x))             # ramp position (log-normalised emission) per display value
    bpy.data.objects.remove(pl)
    bpy.data.objects.remove(co)
    bpy.data.images.remove(img)
    os.remove(path)
    (sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples, sc.cycles.use_denoising,
     sc.render.filepath, sc.world, sc.camera) = keep
    print("calibration: display 234/229/222 needs emission",
          [round(VMIN * (VMAX / VMIN) ** float(np.interp(v / 255, targets, curves[i])), 3) for i, v in enumerate((234, 229, 222))])
    return dict(targets=targets, curves=curves)


def mat_screen(name, image_path=None, strength=1.0, dark=False, gain=(1.0, 1.0, 1.0), calib=None, ior=1.5):
    """Phone glass: black gloss with the real screenshot as emission (unaltered)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.004, 0.004, 0.004, 1)
    p.inputs["Roughness"].default_value = 0.06
    p.inputs["IOR"].default_value = ior          # 1.3 stands in for a coated display glass
    p.inputs["Coat Weight"].default_value = 0.0
    if image_path and not dark:
        img = bpy.data.images.load(image_path, check_existing=True)
        img.colorspace_settings.name = "sRGB"
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        t.extension = "EXTEND"
        t.interpolation = "Cubic"
        if calib is not None:
            # true-colour path: read the screenshot's display values and emit whatever the camera's
            # view transform will turn back into those same values
            img.colorspace_settings.name = "Non-Color"
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            comb = nt.nodes.new("ShaderNodeCombineColor")
            nt.links.new(t.outputs["Color"], sep.inputs[0])
            for ci in range(3):
                fc = nt.nodes.new("ShaderNodeFloatCurve")
                cm = fc.mapping.curves[0]
                tg, cv = calib["targets"], calib["curves"][ci]
                cm.points[0].location = (float(tg[0]), float(cv[0]))
                cm.points[1].location = (float(tg[-1]), float(cv[-1]))
                for k in range(1, len(tg) - 1):
                    cm.points.new(float(tg[k]), float(cv[k]))
                for pt in cm.points:
                    pt.handle_type = "VECTOR"
                fc.mapping.update()
                pw = nt.nodes.new("ShaderNodeMath")
                pw.operation = "POWER"
                pw.inputs[0].default_value = VMAX / VMIN
                ml = nt.nodes.new("ShaderNodeMath")
                ml.operation = "MULTIPLY"
                ml.inputs[1].default_value = VMIN
                nt.links.new(sep.outputs[ci], fc.inputs["Value"])
                nt.links.new(fc.outputs[0], pw.inputs[1])
                nt.links.new(pw.outputs[0], ml.inputs[0])
                nt.links.new(ml.outputs[0], comb.inputs[ci])
            nt.links.new(comb.outputs[0], p.inputs["Emission Color"])
            p.inputs["Emission Strength"].default_value = strength
            return m
        # gain: a per-channel trim that undoes the view transform's shift, so the greige reads true on screen
        mul = nt.nodes.new("ShaderNodeVectorMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = gain
        nt.links.new(t.outputs["Color"], mul.inputs[0])
        nt.links.new(mul.outputs[0], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = strength
    return m


def mat_screen_busy(name, strength=4.0):
    """Abstract soft light for a 'busy' screen: no interface, only drifting colour and glare."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.004, 0.004, 0.004, 1)
    p.inputs["Roughness"].default_value = 0.06
    tc = nt.nodes.new("ShaderNodeTexCoord")
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    sc_ = nt.nodes.new("ShaderNodeMath")
    sc_.operation = "MULTIPLY"
    sc_.inputs[1].default_value = 53.0
    nt.links.new(oi.outputs["Random"], sc_.inputs[0])
    nt.links.new(sc_.outputs[0], comb.inputs[0])
    nt.links.new(sc_.outputs[0], comb.inputs[2])
    add = nt.nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    nt.links.new(tc.outputs["Object"], add.inputs[0])
    nt.links.new(comb.outputs[0], add.inputs[1])
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 11.0
    n.inputs["Detail"].default_value = 0.5
    n.inputs["Roughness"].default_value = 0.3
    nt.links.new(add.outputs[0], n.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.30, (1.0, 0.16, 0.30, 1)
    e[1].position, e[1].color = 0.72, (0.45, 0.12, 1.0, 1)
    for pos, c in [(0.40, (1.0, 0.55, 0.06, 1)), (0.50, (0.95, 0.97, 1.0, 1)), (0.60, (0.06, 0.5, 1.0, 1))]:
        el = e.new(pos)
        el.color = c
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Emission Color"])
    lv = nt.nodes.new("ShaderNodeMapRange")
    lv.inputs["To Min"].default_value = strength * 0.65
    lv.inputs["To Max"].default_value = strength * 1.35
    nt.links.new(oi.outputs["Random"], lv.inputs["Value"])
    nt.links.new(lv.outputs["Result"], p.inputs["Emission Strength"])
    return m


# ---------------------------------------------------------------- phone
def rrect(w, h, r, n=10):
    pts = []
    for cx, cy, a0 in [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)]:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def prism(name, outline, z0, z1):
    bm = bmesh.new()
    lo = [bm.verts.new((x, y, z0)) for x, y in outline]
    hi = [bm.verts.new((x, y, z1)) for x, y in outline]
    n = len(outline)
    bm.faces.new(hi)
    bm.faces.new(list(reversed(lo)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def tray(name, outer, inner, z_base, z_floor, z_rim, with_floor=True):
    """Closed shell: outer wall from z_base to z_rim, rim ring, inner wall down to z_floor."""
    bm = bmesh.new()
    ob = [bm.verts.new((x, y, z_base)) for x, y in outer]
    ot = [bm.verts.new((x, y, z_rim)) for x, y in outer]
    it = [bm.verts.new((x, y, z_rim)) for x, y in inner]
    fl = [bm.verts.new((x, y, z_floor)) for x, y in inner]
    n = len(outer)
    bm.faces.new(list(reversed(ob)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((ob[i], ob[j], ot[j], ot[i]))
        bm.faces.new((ot[i], ot[j], it[j], it[i]))
        bm.faces.new((it[i], it[j], fl[j], fl[i]))
    if with_floor:
        bm.faces.new(fl)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def disc(name, r, z0, z1, n=40, cx=0.0, cy=0.0):
    out = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return prism(name, out, z0, z1)


_phone_mats = {}


def phone_mats(case_hex=CLAY, case_sat=1.35, case_gain=0.85):
    key = case_hex
    if key in _phone_mats:
        return _phone_mats[key]
    body = mat_principled("phone_body", (0.012, 0.012, 0.013, 1), rough=0.28, metallic=0.85)
    glass = mat_principled("phone_glass", (0.004, 0.004, 0.004, 1), rough=0.05)
    backglass = mat_principled("phone_backglass", (0.010, 0.010, 0.011, 1), rough=0.32)
    lensring = mat_principled("lens_ring", (0.05, 0.05, 0.055, 1), rough=0.22, metallic=1.0)
    lens = mat_principled("lens", (0.002, 0.003, 0.006, 1), rough=0.02)
    lens.node_tree.nodes["Principled BSDF"].inputs["Coat Weight"].default_value = 1.0
    flash = mat_principled("flash", (0.75, 0.68, 0.5, 1), rough=0.25)
    if case_hex:
        # AgX and blue skylight wash the clay toward pink in full sun: push the base deeper to compensate
        cc = hexcol(case_hex)
        mx = max(cc[:3])
        cc = tuple(mx * (c / mx) ** case_sat * case_gain for c in cc[:3]) + (1,)
        case = mat_principled("case_" + case_hex, cc, rough=0.62)
        pb = case.node_tree.nodes["Principled BSDF"]
        pb.inputs["Sheen Weight"].default_value = 0.08
        pb.inputs["Sheen Roughness"].default_value = 0.5
        add_bump(case, scale=5000.0, strength=0.06, dist=0.00004)
    else:
        case = None
    _phone_mats[key] = dict(body=body, glass=glass, backglass=backglass, lensring=lensring, lens=lens,
                            flash=flash, case=case)
    return _phone_mats[key]


# phone dimensions (m)
PW, PH, PT, PR = 0.0706, 0.1496, 0.00825, 0.0110
SW, SH, SR = 0.0674, 0.1466, 0.0094          # screen: 1206 x 2622 aspect
CASE_WALL, CASE_BACK, CASE_LIP = 0.0021, 0.0013, 0.0009
CASE_W, CASE_H = PW + 2 * CASE_WALL + 0.0003, PH + 2 * CASE_WALL + 0.0003


def build_phone(name, screen_mat, case_hex=CLAY, with_case=True):
    """Phone lying flat, screen toward +Z, top toward +Y. Origin: centre of the phone's back (z=0).
    Returns the parent empty. Total footprint with case: CASE_W x CASE_H."""
    mats = phone_mats(case_hex if with_case else None)
    root = bpy.data.objects.new(name, None)
    link(root)
    # body
    body = new_obj(name + "_body", prism("body", rrect(PW, PH, PR), 0.0, PT), mats["body"], root)
    bevel(body, 0.0011, 4)
    # glass face (bezel) and the screen itself
    face = new_obj(name + "_face", prism("face", rrect(PW - 0.0016, PH - 0.0016, PR - 0.0008), PT - 0.0002, PT + 0.00012),
                   mats["glass"], root)
    bevel(face, 0.0001, 2)
    scr_out = rrect(SW, SH, SR)
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, PT + 0.00016)) for x, y in scr_out]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new("uv")
    for l in f.loops:
        l[uv].uv = (l.vert.co.x / SW + 0.5, l.vert.co.y / SH + 0.5)
    me = bpy.data.meshes.new("screen")
    bm.to_mesh(me)
    bm.free()
    scr = new_obj(name + "_screen", me, screen_mat, root)
    # back glass
    back = new_obj(name + "_back", prism("back", rrect(PW - 0.002, PH - 0.002, PR - 0.001), -0.00005, 0.0002),
                   mats["backglass"], root)
    # camera island: seen from the back it sits top-left, i.e. +x, +y in this frame
    icx, icy = PW / 2 - 0.0045 - 0.0185, PH / 2 - 0.0045 - 0.019
    zb = -CASE_BACK if with_case else 0.0
    isl_out = [(x + icx, y + icy) for x, y in rrect(0.0355, 0.0365, 0.0088)]
    isl = new_obj(name + "_island", prism("island", isl_out, zb - 0.0012, 0.0), mats["backglass"], root)
    bevel(isl, 0.0007, 3)
    for dx, dy in [(0.0086, 0.0088), (0.0086, -0.0088), (-0.0082, 0.0)]:
        ring = new_obj(name + "_ring", disc("ring", 0.0073, zb - 0.0027, zb - 0.001, 40, icx + dx, icy + dy),
                       mats["lensring"], root)
        bevel(ring, 0.0005, 3)
        g = new_obj(name + "_lg", disc("lg", 0.0059, zb - 0.00285, zb - 0.0026, 40, icx + dx, icy + dy),
                    mats["lens"], root)
        smooth(g.data)
    fl = new_obj(name + "_flash", disc("flash", 0.0024, zb - 0.0014, zb - 0.001, 24, icx - 0.0082, icy + 0.0112),
                 mats["flash"], root)
    if with_case:
        outer = rrect(CASE_W, CASE_H, PR + CASE_WALL + 0.0002)
        inner = rrect(PW + 0.0003, PH + 0.0003, PR + 0.0002)
        case = new_obj(name + "_case", tray("case", outer, inner, -CASE_BACK, 0.00001, PT + CASE_LIP),
                       mats["case"], root)
        bevel(case, 0.0008, 3)
        col_o = [(x + icx, y + icy) for x, y in rrect(0.0405, 0.0415, 0.0112)]
        col_i = [(x + icx, y + icy) for x, y in rrect(0.0362, 0.0372, 0.0091)]
        collar = new_obj(name + "_collar", tray("collar", col_o, col_i, -CASE_BACK + 0.0003, -CASE_BACK + 0.0002,
                                                -CASE_BACK - 0.0019, with_floor=False), mats["case"], root)
        bevel(collar, 0.0007, 3)
        # side buttons: two volume on the left (-x), power on the right (+x)
        for bx, by, bl in [(-CASE_W / 2, 0.030, 0.011), (-CASE_W / 2, 0.014, 0.011), (CASE_W / 2, 0.022, 0.018)]:
            bo = [(x + bx, y + by) for x, y in rrect(0.0016, bl, 0.0007, 4)]
            b = new_obj(name + "_btn", prism("btn", bo, PT / 2 - 0.0016, PT / 2 + 0.0016), mats["case"], root)
            bevel(b, 0.0005, 2)
    return root


def place(ob, loc, rot_deg=(0, 0, 0)):
    ob.location = loc
    ob.rotation_euler = Euler([math.radians(a) for a in rot_deg], "XYZ")
    return ob


# ---------------------------------------------------------------- grass
def vnoise(x, y, seed=0):
    """Cheap smooth 2D noise in 0..1 from a few sines (enough for clumping)."""
    r = np.random.default_rng(seed)
    out = np.zeros_like(x)
    for k in range(6):
        fx, fy = r.normal(0, 1, 2)
        ph = r.uniform(0, 6.28)
        out += np.sin(x * fx * 2.2 + y * fy * 2.2 + ph)
    return 0.5 + 0.5 * np.tanh(out / 2.2)


def wedge_points(rng, apex, heading_deg, half_fov_deg, r0, r1, density):
    th = math.radians(half_fov_deg)
    area = th * (r1 * r1 - r0 * r0)
    n = int(area * density)
    r = np.sqrt(rng.uniform(0, 1, n) * (r1 * r1 - r0 * r0) + r0 * r0)
    a = math.radians(90 - heading_deg) + rng.uniform(-th, th, n)
    return np.stack([apex[0] + r * np.cos(a), apex[1] + r * np.sin(a)], 1)


def rect_points(rng, x0, x1, y0, y1, density):
    n = int((x1 - x0) * (y1 - y0) * density)
    return np.stack([rng.uniform(x0, x1, n), rng.uniform(y0, y1, n)], 1)


def exclude(pts, rects):
    """rects: (cx, cy, half_w, half_h, yaw_deg). Returns mask of points to keep."""
    keep = np.ones(len(pts), bool)
    for cx, cy, hw, hh, yaw in rects:
        c, s = math.cos(math.radians(-yaw)), math.sin(math.radians(-yaw))
        dx, dy = pts[:, 0] - cx, pts[:, 1] - cy
        lx, ly = dx * c - dy * s, dx * s + dy * c
        keep &= ~((np.abs(lx) < hw) & (np.abs(ly) < hh))
    return keep


GRASS_PALETTE = np.array([
    [0.070, 0.135, 0.028],
    [0.095, 0.165, 0.034],
    [0.055, 0.110, 0.026],
    [0.125, 0.175, 0.045],
    [0.160, 0.185, 0.060],
])
STRAW = np.array([0.42, 0.33, 0.14])


def make_grass(name, pts, mat, rng, h_mean=0.045, h_var=0.18, w_mean=0.0032, bend=0.55, segs=3,
               straw=0.06, clump_seed=3, lean_bias=None, hscale=None, tuft=0.022, flop=0.12):
    n = len(pts)
    # tufts: blades gather toward jittered cell centres and lean outward from them, like real turf
    tuft_dir = None
    if tuft:
        ij = np.floor(pts / tuft)
        hsh = np.sin(ij[:, 0] * 12.9898 + ij[:, 1] * 78.233) * 43758.5453
        j1 = hsh - np.floor(hsh)
        hsh2 = np.sin(ij[:, 0] * 39.3468 + ij[:, 1] * 11.135) * 24634.6345
        j2 = hsh2 - np.floor(hsh2)
        cen = (ij + 0.2 + 0.6 * np.stack([j1, j2], 1)) * tuft
        off = pts - cen
        pts = cen + off * 0.6
        tuft_dir = np.arctan2(off[:, 1], off[:, 0])
        tuft_tone = 0.8 + 0.4 * j1
    cl = vnoise(pts[:, 0] * 2.0, pts[:, 1] * 2.0, clump_seed)
    h = h_mean * (0.8 + 0.4 * cl) * np.exp(rng.normal(0, h_var, n)).clip(0.5, 1.5)
    if hscale is not None:
        h = h * hscale
    w = w_mean * rng.uniform(0.7, 1.3, n)
    head = rng.uniform(0, 2 * np.pi, n)
    if tuft_dir is not None:
        # lean direction is head + 90deg; aim it outward from the tuft centre, loosely
        head = tuft_dir - np.pi / 2 + rng.normal(0, 0.9, n)
    b = bend * rng.gamma(2.0, 0.5, n).clip(0.05, 2.5)
    fl = rng.uniform(0, 1, n) < flop
    b[fl] *= rng.uniform(2.0, 4.0, fl.sum())
    h[fl] *= rng.uniform(0.9, 1.35, fl.sum())
    if lean_bias is not None:
        # lean_bias = (dx, dy, amount): pull blade lean toward a common direction (a trodden / wind-set lawn)
        tgt = math.atan2(lean_bias[1], lean_bias[0]) - np.pi / 2
        d = np.angle(np.exp(1j * (tgt - head)))
        head = head + d * lean_bias[2]
    wd = np.stack([np.cos(head), np.sin(head), np.zeros(n)], 1)
    ld = np.stack([-np.sin(head), np.cos(head), np.zeros(n)], 1)
    rows = segs + 1
    V = np.zeros((n, rows, 2, 3), np.float32)
    T = np.zeros((n, rows, 2), np.float32)
    root = np.concatenate([pts, np.zeros((n, 1))], 1)
    for k in range(rows):
        t = k / segs
        lean = (b * h * t * t)[:, None] * ld
        up = np.zeros((n, 3))
        up[:, 2] = h * t * (1.0 - np.minimum(0.24 * b, 0.8) * t)
        c = root + lean + up
        hw = (w * 0.5 * (1.0 - t ** 1.7) + 0.00012)[:, None]
        V[:, k, 0] = c - wd * hw
        V[:, k, 1] = c + wd * hw
        T[:, k, :] = t
    # colours
    pi = rng.integers(0, len(GRASS_PALETTE), n)
    col = GRASS_PALETTE[pi] * rng.uniform(0.8, 1.2, (n, 1))
    patch = vnoise(pts[:, 0] * 0.9 + 5, pts[:, 1] * 0.9 - 2, clump_seed + 11)[:, None]
    col = col * (0.82 + 0.36 * patch)
    if tuft_dir is not None:
        col = col * tuft_tone[:, None]
    is_straw = rng.uniform(0, 1, n) < straw
    col[is_straw] = STRAW * rng.uniform(0.7, 1.2, (is_straw.sum(), 1))
    C = np.ones((n, rows, 2, 4), np.float32)
    C[..., :3] = col[:, None, None, :]
    # faces
    nv = n * rows * 2
    base = (np.arange(n) * rows * 2)[:, None]
    quads = []
    for k in range(segs):
        a = base + k * 2
        quads.append(np.concatenate([a, a + 1, a + 3, a + 2], 1))
    Q = np.stack(quads, 1).reshape(-1)
    nf = n * segs
    me = bpy.data.meshes.new(name)
    me.vertices.add(nv)
    me.loops.add(nf * 4)
    me.polygons.add(nf)
    me.vertices.foreach_set("co", V.reshape(-1))
    me.loops.foreach_set("vertex_index", Q.astype(np.int32))
    me.polygons.foreach_set("loop_start", np.arange(nf, dtype=np.int32) * 4)
    me.polygons.foreach_set("loop_total", np.full(nf, 4, np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(nf, bool))
    me.update(calc_edges=True)
    ca = me.color_attributes.new("col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", C.reshape(-1))
    ta = me.attributes.new("t", "FLOAT", "POINT")
    ta.data.foreach_set("value", T.reshape(-1))
    ob = new_obj(name, me, mat)
    print("grass", name, n, "blades")
    return ob


def mat_grass(translucency=0.42, rough=0.5, spec=0.3):
    m = bpy.data.materials.new("grass")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    out = nt.nodes["Material Output"]
    ac = nt.nodes.new("ShaderNodeAttribute")
    ac.attribute_name = "col"
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "t"
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = 0.35
    ramp.inputs["To Max"].default_value = 1.1
    nt.links.new(at.outputs["Fac"], ramp.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "SCALE"
    nt.links.new(ac.outputs["Color"], mul.inputs[0])
    nt.links.new(ramp.outputs["Result"], mul.inputs["Scale"])
    nt.links.new(mul.outputs[0], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = spec
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 1.0
    nt.links.new(mul.outputs[0], tint.inputs["A"])
    tint.inputs["B"].default_value = (1.35, 1.45, 0.6, 1)
    nt.links.new(tint.outputs["Result"], tr.inputs["Color"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = translucency
    nt.links.new(p.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def ground(size=400.0, col_a=(0.035, 0.05, 0.012, 1), col_b=(0.07, 0.10, 0.02, 1)):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    g = bpy.context.active_object
    m = mat_principled("soil", col_a, rough=0.95)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 3.0
    n.inputs["Detail"].default_value = 6.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = col_a
    mix.inputs["B"].default_value = col_b
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    nt.links.new(n.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], p.inputs["Base Color"])
    g.data.materials.append(m)
    return g


# ---------------------------------------------------------------- sycamore leaf
LOBES = [(90, 1.0, 20), (48, 0.86, 18), (132, 0.86, 18), (2, 0.6, 17), (178, 0.6, 17)]


def leaf_radius(th_deg, teeth=1.0, seed=0):
    """Outline of a plane/sycamore leaf in polar form (tip at 90 deg, petiole at 270)."""
    th = np.asarray(th_deg, float)
    r = np.zeros_like(th)
    for a, L, s in LOBES:
        d = np.abs((th - a + 180) % 360 - 180)
        r = np.maximum(r, L * (0.57 + 0.43 * np.exp(-(d / s) ** 1.6)))
    # coarse teeth
    r = r * (1 + teeth * 0.045 * (2 * np.abs(((th + seed * 7.0) / 9.0) % 1 - 0.5) - 0.5) * 2)
    # cordate base
    d = np.abs((th - 270 + 180) % 360 - 180)
    r = r * (0.16 + 0.84 * (1 - np.exp(-(d / 55.0) ** 2.2)))
    return r


def leaf_mesh(name, size=0.07, curl=0.25, rng=None, A=120, R=10, teeth=1.0):
    rng = rng or np.random.default_rng(0)
    th = np.linspace(0, 360, A, endpoint=False)
    rr = leaf_radius(th, teeth, rng.integers(0, 9))
    s = np.linspace(0, 1, R + 1)
    TH, S = np.meshgrid(np.radians(th), s)
    RR = np.tile(rr, (R + 1, 1)) * S * size
    X, Y = RR * np.cos(TH), RR * np.sin(TH)
    a0, a1 = rng.uniform(0, 6.28, 2)
    Z = curl * size * ((RR / size) ** 2 * (0.5 + 0.5 * np.cos(2 * (TH - a0))) + 0.35 * (RR / size) ** 3 * np.sin(5 * TH + a1)
                       + 0.15 * S ** 2)
    # midrib crease
    co = np.stack([X, Y, Z], -1).astype(np.float32)
    # vein factor
    vein = np.zeros_like(X)
    for a, L, sg in LOBES:
        d = np.abs((np.degrees(TH) - a + 180) % 360 - 180)
        perp = RR / size * np.abs(np.sin(np.radians(np.minimum(d, 89))))
        vein = np.maximum(vein, np.exp(-(perp / 0.012) ** 2) * (d < 60))
    rows, colsn = R + 1, A
    idx = np.arange(rows * colsn).reshape(rows, colsn)
    q = np.stack([idx[:-1], np.roll(idx[:-1], -1, 1), np.roll(idx[1:], -1, 1), idx[1:]], -1).reshape(-1)
    nf = (rows - 1) * colsn
    me = bpy.data.meshes.new(name)
    me.vertices.add(rows * colsn)
    me.loops.add(nf * 4)
    me.polygons.add(nf)
    me.vertices.foreach_set("co", co.reshape(-1))
    me.loops.foreach_set("vertex_index", q.astype(np.int32))
    me.polygons.foreach_set("loop_start", np.arange(nf, dtype=np.int32) * 4)
    me.polygons.foreach_set("loop_total", np.full(nf, 4, np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(nf, bool))
    me.update(calc_edges=True)
    me.validate()
    va = me.attributes.new("vein", "FLOAT", "POINT")
    va.data.foreach_set("value", vein.astype(np.float32).reshape(-1))
    return me


def mat_leaf(name, a=(0.42, 0.25, 0.06, 1), b=(0.20, 0.10, 0.035, 1), veincol=(0.50, 0.36, 0.14, 1),
             transl=0.3, green=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    out = nt.nodes["Material Output"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 28.0
    n.inputs["Detail"].default_value = 5.0
    n.inputs["Roughness"].default_value = 0.65
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = a
    mix.inputs["B"].default_value = b
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.35
    ramp.inputs["From Max"].default_value = 0.7
    nt.links.new(n.outputs["Fac"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], mix.inputs["Factor"])
    last = mix.outputs["Result"]
    if green is not None:
        n2 = nt.nodes.new("ShaderNodeTexNoise")
        n2.inputs["Scale"].default_value = 9.0
        nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
        r2 = nt.nodes.new("ShaderNodeMapRange")
        r2.inputs["From Min"].default_value = 0.5
        r2.inputs["From Max"].default_value = 0.75
        nt.links.new(n2.outputs["Fac"], r2.inputs["Value"])
        m2 = nt.nodes.new("ShaderNodeMix")
        m2.data_type = "RGBA"
        nt.links.new(r2.outputs["Result"], m2.inputs["Factor"])
        nt.links.new(last, m2.inputs["A"])
        m2.inputs["B"].default_value = green
        last = m2.outputs["Result"]
    va = nt.nodes.new("ShaderNodeAttribute")
    va.attribute_name = "vein"
    vm = nt.nodes.new("ShaderNodeMix")
    vm.data_type = "RGBA"
    nt.links.new(va.outputs["Fac"], vm.inputs["Factor"])
    nt.links.new(last, vm.inputs["A"])
    vm.inputs["B"].default_value = veincol
    nt.links.new(vm.outputs["Result"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.55
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.35
    bmp.inputs["Distance"].default_value = 0.0006
    nt.links.new(n.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], p.inputs["Normal"])
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    nt.links.new(vm.outputs["Result"], tr.inputs["Color"])
    ms = nt.nodes.new("ShaderNodeMixShader")
    ms.inputs["Fac"].default_value = transl
    nt.links.new(p.outputs[0], ms.inputs[1])
    nt.links.new(tr.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs["Surface"])
    return m


def fallen_leaf(name, mat, loc, rot_deg, size=0.07, curl=0.3, rng=None):
    me = leaf_mesh(name, size, curl, rng)
    ob = new_obj(name, me, mat)
    place(ob, loc, rot_deg)
    # petiole
    cu = bpy.data.curves.new(name + "_stem", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("NURBS")
    pts = [(0, -0.16 * size, 0.0), (0.02 * size, -0.45 * size, 0.04 * size), (0.08 * size, -0.8 * size, 0.02 * size)]
    sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts):
        p.co = (*c, 1)
    sp.use_endpoint_u = True
    cu.bevel_depth = 0.012 * size
    st = bpy.data.objects.new(name + "_stem", cu)
    cu.materials.append(mat)
    link(st, ob)
    return ob


# ---------------------------------------------------------------- canopy gobo / tree line
def canopy(name, centre, radius, n, rng, clusters=18, cluster_sigma=0.5, leaf_size=0.09, flat=None,
           col=(0.07, 0.13, 0.025, 1), transl=0.35, clear=None):
    """A cloud of sycamore leaves: a real tree's worth of gaps for the sun to come through."""
    cen = np.array(centre)
    cc = rng.normal(0, 1, (clusters, 3))
    cc = cc / np.linalg.norm(cc, axis=1)[:, None] * rng.uniform(0.2, 1, (clusters, 1)) ** 0.5 * radius
    if flat is not None:
        cc = cc * np.array(flat)
    which = rng.integers(0, clusters, n)
    pos = cen + cc[which] + rng.normal(0, cluster_sigma, (n, 3))
    if clear is not None:
        for c0, cd, cr in clear:
            c0, cd = np.array(c0), np.array(cd)
            rel = pos - c0
            perp = rel - np.outer(rel @ cd, cd)
            pos = pos[np.linalg.norm(perp, axis=1) > cr]
        n = len(pos)
    th = np.linspace(0, 360, 28, endpoint=False)
    rr = leaf_radius(th, 0.0) * leaf_size
    lx, ly = rr * np.cos(np.radians(th)), rr * np.sin(np.radians(th))
    L = np.stack([lx, ly, np.zeros_like(lx)], 1)
    # random rotations
    q = rng.normal(0, 1, (n, 4))
    q /= np.linalg.norm(q, axis=1)[:, None]
    w, x, y, z = q.T
    Rm = np.stack([
        np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], 1),
        np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], 1),
        np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], 1)], 1)
    sc = rng.uniform(0.7, 1.3, (n, 1, 1))
    V = np.einsum("nij,kj->nki", Rm, L) * sc + pos[:, None, :]
    k = len(th)
    me = bpy.data.meshes.new(name)
    me.vertices.add(n * k)
    me.loops.add(n * k)
    me.polygons.add(n)
    me.vertices.foreach_set("co", V.astype(np.float32).reshape(-1))
    me.loops.foreach_set("vertex_index", np.arange(n * k, dtype=np.int32))
    me.polygons.foreach_set("loop_start", np.arange(n, dtype=np.int32) * k)
    me.polygons.foreach_set("loop_total", np.full(n, k, np.int32))
    me.update(calc_edges=True)
    m = bpy.data.materials.new(name + "_mat")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = col
    p.inputs["Roughness"].default_value = 0.5
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    tr.inputs["Color"].default_value = (col[0] * 2.2, col[1] * 2.4, col[2] * 1.2, 1)
    ms = nt.nodes.new("ShaderNodeMixShader")
    ms.inputs["Fac"].default_value = transl
    nt.links.new(p.outputs[0], ms.inputs[1])
    nt.links.new(tr.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    ob = new_obj(name, me, m)
    return ob


def mat_bark():
    m = mat_principled("bark", (0.3, 0.27, 0.2, 1), rough=0.85)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    v = nt.nodes.new("ShaderNodeTexVoronoi")
    v.inputs["Scale"].default_value = 7.0
    v.inputs["Randomness"].default_value = 1.0
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1, 1, 0.45)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], v.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].position = 0.0
    e[0].color = (0.55, 0.50, 0.38, 1)
    e[1].position = 1.0
    e[1].color = (0.16, 0.14, 0.10, 1)
    for pos, c in [(0.3, (0.33, 0.33, 0.22, 1)), (0.55, (0.42, 0.36, 0.26, 1)), (0.8, (0.22, 0.20, 0.15, 1))]:
        el = e.new(pos)
        el.color = c
    ramp.color_ramp.interpolation = "CONSTANT"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(v.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = 0.6
    b.inputs["Distance"].default_value = 0.01
    nt.links.new(v.outputs["Distance"], b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return m


def trunk(name, loc, r=0.35, h=6.0, mat=None, rng=None, flare=1.1):
    rng = rng or np.random.default_rng(1)
    A, Zn = 48, 40
    z = np.concatenate([np.linspace(0, 1.2, 24), np.linspace(1.25, h, Zn - 24)])
    th = np.linspace(0, 2 * np.pi, A, endpoint=False)
    TH, ZZ = np.meshgrid(th, z)
    ph = rng.uniform(0, 6.28, 3)
    rad = r * (1 + flare * np.exp(-ZZ / 0.22) * (0.6 + 0.4 * np.sin(5 * TH + ph[0]) * np.sin(3 * TH + ph[1]))
               + 0.05 * np.sin(2 * TH + ph[2] + ZZ * 0.8)) * (1 - 0.05 * ZZ / h)
    X, Y = rad * np.cos(TH), rad * np.sin(TH)
    co = np.stack([X, Y, ZZ - 0.05], -1).astype(np.float32)
    idx = np.arange(Zn * A).reshape(Zn, A)
    q = np.stack([idx[:-1], np.roll(idx[:-1], -1, 1), np.roll(idx[1:], -1, 1), idx[1:]], -1).reshape(-1)
    nf = (Zn - 1) * A
    me = bpy.data.meshes.new(name)
    me.vertices.add(Zn * A)
    me.loops.add(nf * 4)
    me.polygons.add(nf)
    me.vertices.foreach_set("co", co.reshape(-1))
    me.loops.foreach_set("vertex_index", q.astype(np.int32))
    me.polygons.foreach_set("loop_start", np.arange(nf, dtype=np.int32) * 4)
    me.polygons.foreach_set("loop_total", np.full(nf, 4, np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(nf, bool))
    me.update(calc_edges=True)
    ob = new_obj(name, me, mat or mat_bark())
    ob.location = loc
    return ob


def tree_line(rng, n=26, r0=28, r1=70, heading_deg=0, half_fov=45, bark=None,
              col=(0.05, 0.10, 0.02, 1), leaves_per=900, leaf_size=0.5):
    """Distant trees: trunks + leaf clouds, only ever seen out of focus."""
    obs = []
    for i in range(n):
        a = math.radians(90 - heading_deg) + rng.uniform(-math.radians(half_fov), math.radians(half_fov))
        r = rng.uniform(r0, r1)
        x, y = r * math.cos(a), r * math.sin(a)
        hgt = rng.uniform(4.5, 7.5)
        obs.append(trunk(f"tl_trunk{i}", (x, y, 0), r=rng.uniform(0.22, 0.4), h=hgt, mat=bark, rng=rng, flare=0.5))
        c = col[0] * rng.uniform(0.7, 1.4), col[1] * rng.uniform(0.7, 1.3), col[2] * rng.uniform(0.6, 1.5), 1
        obs.append(canopy(f"tl_canopy{i}", (x, y, hgt + rng.uniform(0.5, 2.0)), rng.uniform(3.5, 5.5), leaves_per, rng,
                          clusters=14, cluster_sigma=0.9, leaf_size=leaf_size, flat=(1, 1, 0.65), col=c))
    return obs


# ---------------------------------------------------------------- post: grain
def finish(src, dst, grain=0.022, vignette=0.12, seed=1, halation=0.0):
    """Fine luminance grain and a light optical vignette, applied to the display-referred PNG."""
    img = bpy.data.images.load(src)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)
    rgb = a[..., :3]
    # image.pixels are linearised from the file's sRGB: go back to display space for the grain
    disp = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.clip(rgb, 0, None) ** (1 / 2.4) - 0.055)
    if halation > 0:
        # lens halation around sources that are far brighter than the scene (not a glow on the interface)
        mx = disp.max(-1, keepdims=True)
        src_ = disp * np.clip((mx - 0.72) / 0.28, 0, 1)
        fy = np.fft.fftfreq(h)[:, None]
        fx = np.fft.rfftfreq(w)[None, :]
        acc = np.zeros_like(disp)
        for sig, wt in [(w / 220.0, 0.55), (w / 45.0, 0.45)]:
            G = np.exp(-2 * (np.pi * sig) ** 2 * (fx * fx + fy * fy))
            for c in range(3):
                acc[..., c] += wt * np.fft.irfft2(np.fft.rfft2(src_[..., c]) * G, s=(h, w))
        disp = 1 - (1 - disp) * (1 - np.clip(halation * acc, 0, 1))
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    r2 = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (w / 2)) ** 2
    disp = disp * (1 - vignette * r2)[..., None]
    g = rng.normal(0, 1, (h, w)).astype(np.float32)
    # soften the grain a touch so it is silver, not digital
    g = (g + 0.5 * (np.roll(g, 1, 0) + np.roll(g, 1, 1))) / 1.5
    lum = disp.mean(-1)
    amt = grain * (0.35 + 1.3 * lum * (1 - lum) * 2)
    disp = np.clip(disp + (g * amt)[..., None], 0, 1)
    a[..., :3] = disp      # a byte image stores display values as given
    out = bpy.data.images.new("fin", w, h, alpha=False)
    out.pixels.foreach_set(a.reshape(-1))
    out.filepath_raw = dst
    out.file_format = "PNG"
    out.save()
    print("finished", dst)


def render(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
