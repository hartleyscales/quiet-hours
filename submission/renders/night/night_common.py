# Shared helpers for the `night` lane (gather.png, moon.png). Everything procedural, made today.
import bpy, bmesh, numpy as np, math, sys, os, time, json
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
MOON_JSON = os.path.join(HERE, "..", "objects", "data", "moon_3098.json")
BG8 = (8, 7, 6)                       # the slide's night background, #080706

def lin(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

BG_LIN = tuple(float(v) for v in lin(BG8))

def args():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    try: sc.world.use_nodes = True
    except Exception: pass
    return sc

def cycles(sc, w, h, samples, thresh=0.01):
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    try: prefs.refresh_devices()
    except Exception: prefs.get_devices()
    for d in prefs.devices: d.use = (d.type == "METAL")
    c = sc.cycles
    c.device = "GPU"; c.samples = samples
    c.use_adaptive_sampling = True; c.adaptive_threshold = thresh
    c.use_denoising = True
    try: c.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    c.max_bounces = 4; c.diffuse_bounces = 2; c.glossy_bounces = 2; c.transmission_bounces = 0
    c.caustics_reflective = False; c.caustics_refractive = False
    c.sample_clamp_indirect = 4.0
    c.filter_width = 1.5
    sc.render.resolution_x = w; sc.render.resolution_y = h; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "16"
    sc.render.dither_intensity = 0.0
    sc.view_settings.view_transform = "Standard"
    try: sc.view_settings.look = "None"
    except Exception as e: print("look:", e)
    sc.view_settings.exposure = 0.0; sc.view_settings.gamma = 1.0
    sc.render.film_transparent = False

def world_bg(sc):
    """World shows exactly the slide background to the camera and lights nothing."""
    nt = sc.world.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld"); bg = nt.nodes.new("ShaderNodeBackground")
    lp = nt.nodes.new("ShaderNodeLightPath")
    bg.inputs[0].default_value = (*BG_LIN, 1)
    nt.links.new(lp.outputs["Is Camera Ray"], bg.inputs[1])
    nt.links.new(bg.outputs[0], out.inputs[0])

def new_mat(name):
    m = bpy.data.materials.new(name)
    try: m.use_nodes = True
    except Exception: pass
    nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out

def glow_mat(name, strength, limb=0.55, surface=None, spill=1.0):
    """Bead that carries its own light: emission in the per-bead `col`, a little dimmer toward the limb so it reads as a sphere.
    surface: optional dict(rough=, spec=) to add a lit Principled body under the glow."""
    m, nt, out = new_mat(name)
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "col"
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.5
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY_ADD"          # strength * (1 - limb * facing)
    nt.links.new(lw.outputs["Facing"], mul.inputs[0]); mul.inputs[1].default_value = -limb * strength; mul.inputs[2].default_value = strength
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    if spill == 1.0:
        nt.links.new(mul.outputs[0], em.inputs["Strength"])
    else:                                              # seen at full strength, but lights its surroundings at `spill`
        lp = nt.nodes.new("ShaderNodeLightPath"); mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = spill; mr.inputs["To Max"].default_value = 1.0
        nt.links.new(lp.outputs["Is Camera Ray"], mr.inputs["Value"])
        m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
        nt.links.new(mul.outputs[0], m2.inputs[0]); nt.links.new(mr.outputs["Result"], m2.inputs[1])
        nt.links.new(m2.outputs[0], em.inputs["Strength"])
    if surface is None:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    else:
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(at.outputs["Color"], b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = surface.get("rough", 0.4)
        if "Specular IOR Level" in b.inputs: b.inputs["Specular IOR Level"].default_value = surface.get("spec", 0.5)
        if surface.get("coat") and "Coat Weight" in b.inputs:
            b.inputs["Coat Weight"].default_value = surface["coat"]; b.inputs["Coat Roughness"].default_value = surface.get("coat_rough", 0.15)
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(b.outputs[0], add.inputs[0]); nt.links.new(em.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs["Surface"])
    return m

def tmpl_sphere(u=16, v=8):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    bmesh.ops.triangulate(bm, faces=list(bm.faces)); bm.verts.ensure_lookup_table()
    tv = np.array([vv.co[:] for vv in bm.verts], dtype=np.float64)
    tf = np.array([[vv.index for vv in ff.verts] for ff in bm.faces], dtype=np.int64); bm.free()
    return tv, tf

def tile(sc, name, tv, tf, pos, rad, col=None):
    """One mesh of N spheres at pos (N,3) with radius rad (N,) and per-sphere linear colour col (N,3)."""
    N, nv, nf = pos.shape[0], tv.shape[0], tf.shape[0]
    co = tv[None] * np.asarray(rad, dtype=np.float64).reshape(N, 1, 1) + pos[:, None, :]
    faces = tf[None] + (np.arange(N) * nv)[:, None, None]
    me = bpy.data.meshes.new(name)
    me.vertices.add(N * nv); me.vertices.foreach_set("co", co.astype(np.float32).ravel())
    me.loops.add(N * nf * 3); me.polygons.add(N * nf)
    me.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
    me.polygons.foreach_set("loop_start", np.arange(N * nf, dtype=np.int32) * 3)
    me.polygons.foreach_set("loop_total", np.full(N * nf, 3, dtype=np.int32))
    me.update(calc_edges=True)
    me.polygons.foreach_set("use_smooth", np.ones(N * nf, dtype=bool))
    if col is not None:
        rgba = np.concatenate([np.asarray(col, np.float32), np.ones((N, 1), np.float32)], 1)
        at = me.attributes.new("col", "FLOAT_COLOR", "POINT"); at.data.foreach_set("color", np.repeat(rgba, nv, axis=0).ravel())
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    return ob

def load_moon():
    d = json.load(open(MOON_JSON))
    dots = np.array(d["dots"], dtype=np.float64)
    xy = np.stack([(dots[:, 0] - d["cx"]) / d["r"], -(dots[:, 1] - d["cy"]) / d["r"]], 1)   # unit-radius moon, y up
    return xy, lin(dots[:, 2:5]), dots[:, 5].astype(int), 1.0 / d["r"]                      # positions, linear colours, flag, pitch

# ---------- 8-bit output: dither that leaves exact values exact ----------
def load_px(path):
    im = bpy.data.images.load(path, check_existing=False); im.colorspace_settings.name = "Non-Color"
    w, h = im.size; a = np.empty(w * h * 4, dtype=np.float32); im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1, :, :3].astype(np.float64).copy()          # top-down, display values 0..1

def save8(arr8, path):
    h, w = arr8.shape[:2]
    sc = bpy.context.scene
    im = bpy.data.images.new("out8", w, h, alpha=False, float_buffer=False)
    im.colorspace_settings.name = "Non-Color"
    a = np.concatenate([arr8.astype(np.float32) / 255.0, np.ones((h, w, 1), np.float32)], 2)
    im.pixels.foreach_set(a[::-1].ravel())
    im.filepath_raw = path; im.file_format = "PNG"; im.save()
    bpy.data.images.remove(im)

def to8(a, seed=7):
    """16-bit display values -> 8-bit with half-LSB noise dither (kills banding in the soft glows).
    A pixel already sitting on an exact 8-bit value (the flat background) is left exactly there."""
    rng = np.random.default_rng(seed)
    v = a * 255.0
    dev = np.abs(v - np.array(BG8)).max(-1)
    print("RAW16 background stats: share within 0.02 LSB of bg %.4f, within 0.3 LSB %.4f" % ((dev < 0.02).mean(), (dev < 0.3).mean()))
    k = 4; pad = np.pad(dev, k, mode="edge"); cs = pad.cumsum(0).cumsum(1); cs = np.pad(cs, ((1, 0), (1, 0)))
    n9 = 2 * k + 1; h, w = dev.shape
    loc = (cs[n9:n9 + h, n9:n9 + w] - cs[:h, n9:n9 + w] - cs[n9:n9 + h, :w] + cs[:h, :w]) / (n9 * n9)       # 9 px local mean of the deviation
    exact = ((loc < 0.3) & (dev < 1.5))[..., None]    # flat background (render/denoise residue under a third of a step) is written as exactly bg
    edge = np.zeros((h, w), bool); edge[:6] = True; edge[-6:] = True; edge[:, :6] = True; edge[:, -6:] = True
    exact |= (edge & (dev < 3.0))[..., None]          # the outer 6 px carry nothing but background: no stray denoise pixels on the border
    n = rng.random(v.shape[:2])[..., None]
    out = np.where(exact, np.array(BG8, dtype=np.float64), np.floor(v + n))
    return np.clip(out, 0, 255).astype(np.uint8)

def measure(a8, label=""):
    """Report edge colours and how far anything strays from the background in the keep-clear regions."""
    h, w = a8.shape[:2]; bg = np.array(BG8)
    rep = {}
    def stat(name, reg):
        d = np.abs(reg.astype(int) - bg).max()
        rep[name] = dict(mean=[round(float(x), 2) for x in reg.reshape(-1, 3).mean(0)], max_dev=int(d),
                         max=[int(x) for x in reg.reshape(-1, 3).max(0)])
    stat("edge_top", a8[:4]); stat("edge_bottom", a8[-4:]); stat("edge_left", a8[:, :4]); stat("edge_right", a8[:, -4:])
    stat("top30_left60", a8[: int(h * 0.30), : int(w * 0.60)])
    stat("bottom12", a8[int(h * 0.88):])
    stat("left_half", a8[:, : w // 2])
    print("MEASURE", label, json.dumps(rep))
    return rep

def render(sc, path):
    t = time.time(); sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED %s in %.1fs" % (path, time.time() - t))
