# Shared helpers for the `objects` lane look tests. Everything is built here, procedurally, today.
import bpy, bmesh, numpy as np, math, sys, os, time
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
QH = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SCREENS = os.path.join(QH, "submission", "screens")
PX = 0.0665 / 1206.0          # metres per screenshot pixel (66.5 mm wide screen, 1206 px)
PT = PX * 3.0                 # metres per point

def srgb(hexs):
    """#RRGGBB -> linear RGB tuple."""
    h = hexs.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c)

def lin(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return a

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    try: sc.world.use_nodes = True
    except Exception: pass
    return sc

def cycles(sc, w, h, samples, view="AgX", look=None, exposure=0.0):
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    try: prefs.refresh_devices()
    except Exception: prefs.get_devices()
    for d in prefs.devices: d.use = (d.type == "METAL")
    c = sc.cycles
    c.device = "GPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.01 if samples >= 400 else 0.03
    c.use_denoising = True
    try: c.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    c.max_bounces = 8; c.diffuse_bounces = 4; c.glossy_bounces = 4; c.transmission_bounces = 8
    c.caustics_reflective = False; c.caustics_refractive = False
    c.filter_width = 1.5
    sc.render.resolution_x = w; sc.render.resolution_y = h; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "16"
    sc.view_settings.view_transform = view
    if look:
        try: sc.view_settings.look = look
        except Exception as e:
            print("look not set:", e)
    sc.view_settings.exposure = exposure
    sc.render.film_transparent = False

def camera(sc, loc, target, lens=85, fstop=4.0, focus=None, sensor=36.0, blades=0, roll=0.0):
    cd = bpy.data.cameras.new("cam"); ob = bpy.data.objects.new("cam", cd); sc.collection.objects.link(ob)
    loc = Vector(loc); target = Vector(target)
    ob.location = loc
    q = (target - loc).to_track_quat("-Z", "Y")
    ob.rotation_euler = q.to_euler()
    if roll:
        ob.rotation_euler.rotate_axis("Z", roll)
    cd.lens = lens; cd.sensor_width = sensor
    cd.clip_start = 0.005; cd.clip_end = 100
    cd.dof.use_dof = True
    cd.dof.focus_distance = (Vector(focus) - loc).length if focus is not None else (target - loc).length
    cd.dof.aperture_fstop = fstop; cd.dof.aperture_blades = blades
    sc.camera = ob
    return ob

def focus_on(cam, point):
    """Focus distance measured along the view axis (a focal plane, not a sphere)."""
    d = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
    cam.data.dof.focus_distance = (Vector(point) - cam.location).dot(d)

def area_light(sc, name, loc, target, size, power, color=(1, 1, 1), size_y=None, spread=None):
    ld = bpy.data.lights.new(name, "AREA"); ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    ld.shape = "RECTANGLE" if size_y else "SQUARE"
    ld.size = size
    if size_y: ld.size_y = size_y
    ld.energy = power; ld.color = color
    if spread is not None: ld.spread = spread
    return ob

def sun_light(sc, name, elev_deg, azim_deg, strength, color=(1, 1, 1), angle_deg=0.6):
    """azim: direction the light comes FROM, degrees counter-clockwise from +X."""
    ld = bpy.data.lights.new(name, "SUN"); ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob)
    e, a = math.radians(elev_deg), math.radians(azim_deg)
    frm = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
    ob.rotation_euler = (-frm).to_track_quat("-Z", "Y").to_euler()
    ld.energy = strength; ld.color = color; ld.angle = math.radians(angle_deg)
    return ob, frm

def world_color(sc, color, strength=1.0):
    nt = sc.world.node_tree
    bg = next((n for n in nt.nodes if n.type == "BACKGROUND"), None)
    if bg is None:
        bg = nt.nodes.new("ShaderNodeBackground"); out = nt.nodes.new("ShaderNodeOutputWorld")
        nt.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs[0].default_value = (*color, 1); bg.inputs[1].default_value = strength
    return bg

def new_mat(name):
    m = bpy.data.materials.new(name)
    try: m.use_nodes = True
    except Exception: pass
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    return m, nt, bsdf, out

def setin(node, name, value):
    if name in node.inputs:
        node.inputs[name].default_value = value
        return True
    return False

# ---------- fast instanced meshes built with numpy ----------
def tmpl(kind, **kw):
    bm = bmesh.new()
    if kind == "sphere":
        bmesh.ops.create_uvsphere(bm, u_segments=kw.get("u", 24), v_segments=kw.get("v", 12), radius=1.0)
    elif kind == "cyl":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=kw.get("u", 10), radius1=1.0, radius2=1.0, depth=1.0)
    elif kind == "cube":
        bmesh.ops.create_cube(bm, size=1.0)
        if kw.get("bevel"):
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=kw["bevel"], segments=kw.get("seg", 2), affect="EDGES", profile=0.5)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.verts.ensure_lookup_table()
    v = np.array([vv.co[:] for vv in bm.verts], dtype=np.float64)
    f = np.array([[vv.index for vv in ff.verts] for ff in bm.faces], dtype=np.int64)
    bm.free()
    return v, f

def tile(sc, name, tv, tf, M, attrs=None, smooth=True):
    """Instances template (tv, tf) under N 4x4 matrices M as one mesh; attrs: name -> (N,) or (N,3) per-instance."""
    N, nv, nf = M.shape[0], tv.shape[0], tf.shape[0]
    co = np.einsum("nij,vj->nvi", M[:, :3, :3], tv) + M[:, None, :3, 3]
    faces = tf[None] + (np.arange(N) * nv)[:, None, None]
    me = bpy.data.meshes.new(name)
    me.vertices.add(N * nv); me.vertices.foreach_set("co", co.astype(np.float32).ravel())
    me.loops.add(N * nf * 3); me.polygons.add(N * nf)
    me.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
    me.polygons.foreach_set("loop_start", np.arange(N * nf, dtype=np.int32) * 3)
    me.polygons.foreach_set("loop_total", np.full(N * nf, 3, dtype=np.int32))
    me.update(calc_edges=True)
    if smooth:
        me.polygons.foreach_set("use_smooth", np.ones(N * nf, dtype=bool))
    for k, a in (attrs or {}).items():
        a = np.asarray(a, dtype=np.float32)
        if a.ndim == 1:
            at = me.attributes.new(k, "FLOAT", "POINT"); at.data.foreach_set("value", np.repeat(a, nv))
        else:
            rgba = np.concatenate([a, np.ones((N, 1), np.float32)], 1)
            at = me.attributes.new(k, "FLOAT_COLOR", "POINT"); at.data.foreach_set("color", np.repeat(rgba, nv, axis=0).ravel())
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    return ob

def trs(pos, scale, rot=None):
    """(N,3) pos, (N,3) or (N,) scale, optional (N,3,3) rotation -> (N,4,4)."""
    N = pos.shape[0]; M = np.zeros((N, 4, 4)); M[:, 3, 3] = 1
    s = np.asarray(scale, dtype=np.float64)
    if s.ndim == 1: s = np.repeat(s[:, None], 3, 1)
    R = rot if rot is not None else np.repeat(np.eye(3)[None], N, 0)
    M[:, :3, :3] = R * s[:, None, :]
    M[:, :3, 3] = pos
    return M

def tilt_mats(rng, N, max_deg):
    """Small random tilts about random horizontal axes."""
    ang = np.radians(max_deg) * np.sqrt(rng.random(N)); az = rng.random(N) * 2 * np.pi
    ax = np.stack([np.cos(az), np.sin(az), np.zeros(N)], 1)
    K = np.zeros((N, 3, 3))
    K[:, 0, 1] = -ax[:, 2]; K[:, 0, 2] = ax[:, 1]; K[:, 1, 0] = ax[:, 2]; K[:, 1, 2] = -ax[:, 0]; K[:, 2, 0] = -ax[:, 1]; K[:, 2, 1] = ax[:, 0]
    s, c = np.sin(ang)[:, None, None], np.cos(ang)[:, None, None]
    return np.eye(3)[None] + s * K + (1 - c) * (K @ K)

def fibres(sc, name, rng, region, per_mm2, length=(0.0005, 0.0016), lift=0.00022, radius=0.000009):
    """Matted felt nap: short, nearly flat fibres as real hair curves over region (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = region
    N = int((x1 - x0) * (y1 - y0) * 1e6 * per_mm2)
    p = np.stack([x0 + (x1 - x0) * rng.random(N), y0 + (y1 - y0) * rng.random(N), np.full(N, 0.00001)], 1)
    th = rng.random(N) * 2 * np.pi; L = length[0] + (length[1] - length[0]) * rng.random(N)
    d = np.stack([np.cos(th), np.sin(th), np.zeros(N)], 1); n = np.stack([-np.sin(th), np.cos(th), np.zeros(N)], 1)
    h = lift * rng.random(N) ** 2.2 * 3.0
    bend = rng.normal(0, 0.18, N)[:, None] * L[:, None] * n
    p1 = p + 0.5 * L[:, None] * d + bend; p1[:, 2] += h * 0.8
    p2 = p + L[:, None] * d; p2[:, 2] += h
    pts = np.stack([p, p1, p2], 1).reshape(-1, 3).astype(np.float32)
    cu = bpy.data.hair_curves.new(name); cu.add_curves([3] * N)
    cu.attributes["position"].data.foreach_set("vector", pts.ravel())
    ra = cu.attributes.get("radius") or cu.attributes.new("radius", "FLOAT", "POINT")
    ra.data.foreach_set("value", np.full(N * 3, radius, dtype=np.float32))
    ob = bpy.data.objects.new(name, cu); sc.collection.objects.link(ob)
    print("fibres:", N)
    return ob

# ---------- image io with numpy ----------
def load_px(path):
    im = bpy.data.images.load(path, check_existing=False); im.colorspace_settings.name = "Non-Color"
    w, h = im.size; a = np.empty(w * h * 4, dtype=np.float32); im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1].copy()          # top-down, display-referred values

def save_px(arr, path):
    """arr top-down (h,w,3|4) display values 0..1 -> 8-bit PNG, written as is."""
    h, w = arr.shape[:2]
    if arr.shape[2] == 3: arr = np.concatenate([arr, np.ones((h, w, 1), arr.dtype)], 2)
    im = bpy.data.images.new("out", w, h, alpha=True, float_buffer=False)
    im.colorspace_settings.name = "Non-Color"
    im.pixels.foreach_set(np.clip(arr[::-1], 0, 1).astype(np.float32).ravel())
    im.filepath_raw = path; im.file_format = "PNG"; im.save()
    bpy.data.images.remove(im)

def blur(a, sigma):
    if sigma <= 0: return a
    r = int(max(1, round(sigma * 3))); x = np.arange(-r, r + 1); k = np.exp(-x * x / (2 * sigma * sigma)); k /= k.sum()
    out = a
    for ax in (0, 1):
        pad = [(0, 0)] * out.ndim; pad[ax] = (r, r)
        p = np.pad(out, pad, mode="edge"); acc = np.zeros_like(out, dtype=np.float64)
        for i, kv in enumerate(k):
            sl = [slice(None)] * out.ndim; sl[ax] = slice(i, i + out.shape[ax]); acc += kv * p[tuple(sl)]
        out = acc
    return out

def finish(raw_path, out_path, grain=0.018, vignette=0.10, seed=1):
    """Film-like finish on the rendered PNG: fine luminance grain (slightly soft, stronger in mids) and a light vignette."""
    a = load_px(raw_path)[..., :3].astype(np.float64)
    h, w = a.shape[:2]; rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    r2 = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (w / 2)) ** 2
    a *= (1 - vignette * np.clip(r2, 0, 1.5) ** 1.2)[..., None]
    s = max(0.45, 0.6 * w / 2560)
    g = blur(rng.normal(0, 1, (h, w)), s); g /= g.std()
    lum = a.mean(-1)
    amp = grain * (0.35 + 1.3 * np.sqrt(np.clip(lum, 0, 1)) * (1 - 0.6 * lum))
    a += (g * amp)[..., None] + rng.normal(0, grain * 0.15, (h, w, 3))
    save_px(a.astype(np.float32), out_path)

def render(sc, path):
    t = time.time()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    dt = time.time() - t
    print("RENDERED %s in %.1fs" % (path, dt))
    return dt
