"""Render a dithered crescent moon from NASA's LROC colour map (public domain).

Usage: python3 -I render_moon.py <moon.bmp> <out_dir> [share]
Pure standard library: reads a 24-bit BMP, writes RGBA PNGs.
"""
import math
import struct
import sys
import zlib

W, H = 780, 1688          # 2x of a 390 x 844 phone
CELL = 4                  # dot pitch in px (2 logical px)
CX, CY, R = 160, 800, 600  # moon centre and radius in px


def read_bmp(path):
    d = open(path, "rb").read()
    off = struct.unpack_from("<I", d, 10)[0]
    w, h = struct.unpack_from("<ii", d, 18)
    bypp = struct.unpack_from("<H", d, 28)[0] // 8
    rowsize = (w * bypp + 3) & ~3
    flip = h > 0
    h = abs(h)

    def px(x, y):
        yy = (h - 1 - y) if flip else y
        i = off + yy * rowsize + x * bypp
        return (0.114 * d[i] + 0.587 * d[i + 1] + 0.299 * d[i + 2]) / 255.0

    return w, h, px


def bayer(n):
    m = [[0]]
    while len(m) < n:
        s = len(m)
        m = [[4 * m[y % s][x % s] + ((0, 2), (3, 1))[y // s][x // s] for x in range(2 * s)] for y in range(2 * s)]
    return [[(v + 0.5) / (n * n) for v in row] for row in m]


def hash2(x, y):
    s = math.sin(x * 127.1 + y * 311.7) * 43758.5453
    return s - math.floor(s)


def write_png(path, buf):
    raw = bytearray()
    stride = W * 4
    for y in range(H):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def rect(buf, x0, y0, size, rgba):
    for y in range(max(0, y0), min(H, y0 + size)):
        base = y * W * 4
        for x in range(max(0, x0), min(W, x0 + size)):
            i = base + x * 4
            buf[i:i + 4] = bytes(rgba)


def main():
    bmp, out = sys.argv[1], sys.argv[2]
    share = float(sys.argv[3]) if len(sys.argv) > 3 else 0.15
    tw, th, tex = read_bmp(bmp)

    samples = sorted(tex(x, y) for y in range(0, th, 8) for x in range(0, tw, 8))
    lo, hi = samples[int(len(samples) * 0.05)], samples[int(len(samples) * 0.95)]

    theta = math.acos(1 - 2 * share)
    L = (math.sin(theta), 0.10, -math.cos(theta))
    n = math.sqrt(sum(v * v for v in L))
    L = tuple(v / n for v in L)
    B = bayer(8)

    cells = []  # (px, py, kind, brightness)
    for j in range(H // CELL):
        for i in range(W // CELL):
            px, py = i * CELL + CELL // 2, j * CELL + CELL // 2
            x, y = (px - CX) / R, -(py - CY) / R
            d2 = x * x + y * y
            h = hash2(i, j)
            if d2 >= 1:
                if h < 0.0012:
                    cells.append((px, py, "star", 0.0))
                continue
            z = math.sqrt(1 - d2)
            lat, lon = math.asin(y), math.atan2(x, z)
            u = int((lon / (2 * math.pi) + 0.5) * tw) % tw
            v = min(th - 1, max(0, int((0.5 - lat / math.pi) * th)))
            a = min(1.0, max(0.0, (tex(u, v) - lo) / (hi - lo)))
            lam = x * L[0] + y * L[1] + z * L[2]
            if lam > 0:
                b = min(1.0, lam * 2.8) ** 0.7 * (0.22 + 0.78 * a)
                if b > B[j % 8][i % 8]:
                    cells.append((px, py, "lit", b))
            elif h < 0.02 * (0.35 + a):
                cells.append((px, py, "dark", a))

    # "You": one bright lit cell in the part of the crescent that shows above the sheet.
    cand = [c for c in cells if c[2] == "lit" and c[3] > 0.55 and 440 < c[1] < 700]
    you = sorted(cand, key=lambda c: abs(c[1] - 560) + abs(c[0] - 640) * 0.5)[0] if cand else None

    schemes = {
        "night": {"hi": (243, 237, 223, 255), "mid": (190, 184, 170, 255), "low": (118, 127, 146, 255),
                  "dark": (78, 86, 104, 255), "star": (150, 156, 170, 255), "you": (255, 90, 71, 255)},
        "day": {"hi": (28, 26, 24, 255), "mid": (92, 87, 80, 255), "low": (146, 139, 130, 255),
                "dark": (198, 191, 180, 255), "star": (205, 198, 187, 255), "you": (153, 0, 0, 255)},
    }
    for name, c in schemes.items():
        buf = bytearray(W * H * 4)
        for px, py, kind, b in cells:
            if kind == "lit":
                col = c["hi"] if b > 0.6 else c["mid"] if b > 0.3 else c["low"]
                s = 3 if b > 0.3 else 2
            elif kind == "dark":
                col, s = c["dark"], 2
            else:
                col, s = c["star"], 2
            rect(buf, px - s // 2, py - s // 2, s, col)
        if you:
            rect(buf, you[0] - 7, you[1] - 7, 14, (0, 0, 0, 0))
            rect(buf, you[0] - 5, you[1] - 5, 10, c["you"])
        write_png(f"{out}/moon-{name}.png", buf)

    lit = sum(1 for c in cells if c[2] == "lit")
    print(f"cells={len(cells)} lit={lit} tex_lo={lo:.3f} tex_hi={hi:.3f}")
    if you:
        print(f"you_px={you[0]},{you[1]} you_logical={you[0] / 2:.0f},{you[1] / 2:.0f}")


if __name__ == "__main__":
    main()
