import Foundation
import SwiftUI

// All pictures are fixed-size square dots on a 2pt grid (dot 1.33pt). This is a direct port
// of the mock's script: the signed-distance pictures (`clock`, `lock`, `bubble`, `phone`), the
// light they are embossed with, the 8 x 8 Bayer matrix and `fill`, which turns a picture into
// dots. Coordinates are the mock's: a 390-wide space, picture centre (195, 224).

enum DotArt {
    /// Side of one dot in design points (4 pixels at 3x).
    static let dotSize: CGFloat = 4.0 / 3.0
    /// The one ink the pictures are drawn in.
    static let ink = (r: 58.0, g: 52.0, b: 46.0)

    typealias Picture = (Double, Double) -> Double

    // MARK: Signed distances (negative inside)

    static func sdRR(_ x: Double, _ y: Double, _ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double, _ r: Double) -> Double {
        let qx = abs(x - (x0 + x1) / 2) - ((x1 - x0) / 2 - r)
        let qy = abs(y - (y0 + y1) / 2) - ((y1 - y0) / 2 - r)
        return hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
    }

    static func sdC(_ x: Double, _ y: Double, _ cx: Double, _ cy: Double, _ r: Double) -> Double {
        hypot(x - cx, y - cy) - r
    }

    static func sdSeg(_ x: Double, _ y: Double, _ ax: Double, _ ay: Double, _ bx: Double, _ by: Double, _ w: Double) -> Double {
        let px = x - ax, py = y - ay, vx = bx - ax, vy = by - ay
        let h = max(0, min(1, (px * vx + py * vy) / (vx * vx + vy * vy)))
        return hypot(px - vx * h, py - vy * h) - w
    }

    static let LX = -0.7071, LY = -0.7071   // light from the upper left

    /// Darker where the edge faces away from the light. 0 outside the shape.
    static func emboss(_ sd: Picture, _ x: Double, _ y: Double, _ w: Double, _ mid: Double, _ amt: Double) -> Double {
        let d = sd(x, y)
        if d > 0 { return 0 }
        let gx = sd(x + 1, y) - sd(x - 1, y), gy = sd(x, y + 1) - sd(x, y - 1)
        var g = hypot(gx, gy)
        if g == 0 { g = 1 }
        return min(0.97, max(0.1, mid - amt * max(0, 1 + d / w) * ((gx / g) * LX + (gy / g) * LY)))
    }

    static func cast(_ sd: Picture, _ x: Double, _ y: Double) -> Double {
        let d = sd(x - 12, y - 16)
        return d < 8 ? 0.2 * max(0, min(1, (8 - d) / 16)) : 0
    }

    /// JavaScript's Math.round (halves go up).
    private static func jsRound(_ v: Double) -> Double { (v + 0.5).rounded(.down) }

    // MARK: Pictures

    static func clock(_ x: Double, _ y: Double) -> Double {
        let dc = hypot(x - 195, y - 224)
        let rim: Picture = { a, b in abs(hypot(a - 195, b - 224) - 117) - 12 }
        var v = emboss(rim, x, y, 12, 0.62, 0.42)
        if v != 0 { return v }
        if dc < 105 {
            let mh: Picture = { a, b in sdSeg(a, b, 195, 224, 195, 142, 5) }
            let hh: Picture = { a, b in sdSeg(a, b, 195, 224, 242, 197, 6) }
            v = emboss(hh, x, y, 6, 0.86, 0.22)
            if v != 0 { return v }
            v = emboss(mh, x, y, 5, 0.86, 0.22)
            if v != 0 { return v }
            if dc < 10 { return 0.95 }
            let k = Int(jsRound(atan2(y - 224, x - 195) / (Double.pi / 6)))
            let a12 = Double(k) * (Double.pi / 6)
            let major = k % 3 == 0
            let off = hypot(x - (195 + cos(a12) * dc), y - (224 + sin(a12) * dc))
            if dc > (major ? 78 : 86) && dc < 98 && off < (major ? 3.2 : 2.2) { return 0.9 }
            let toward = ((x - 195) * LX + (y - 224) * LY) / max(dc, 1)
            let rimShadow = max(0, 1 - (105 - dc) / 18) * max(0, toward)
            let handShadow = min(mh(x - 5, y - 6), hh(x - 5, y - 6)) < 0 ? 0.28 : 0
            return min(0.6, 0.09 + 0.36 * rimShadow + handShadow)
        }
        return cast({ a, b in sdC(a, b, 195, 224, 129) }, x, y)
    }

    static func lock(_ x: Double, _ y: Double) -> Double {
        let body: Picture = { a, b in sdRR(a, b, 101, 206, 289, 346, 28) }
        let shackle: Picture = { a, b in
            let d = abs(hypot(a - 195, b - 210) - 64) - 13
            return b < 214 ? d : max(d, b - 214)
        }
        let hole: Picture = { a, b in min(sdC(a, b, 195, 262, 15), sdRR(a, b, 188, 262, 202, 308, 7)) }
        if body(x, y) <= 0 {
            let hd = hole(x, y)
            if hd <= 0 {
                let gx = hole(x + 1, y) - hole(x - 1, y), gy = hole(x, y + 1) - hole(x, y - 1)
                var g = hypot(gx, gy)
                if g == 0 { g = 1 }
                return hd > -4 && (gx / g) * LX + (gy / g) * LY > 0.2 ? 0.78 : 0.05
            }
            var v = emboss(body, x, y, 22, 0.6, 0.44)
            if abs(y - 238) < 1.7 && x > 114 && x < 276 { v = max(0.12, v - 0.42) }
            return v
        }
        let v = emboss(shackle, x, y, 13, 0.62, 0.44)
        return v != 0 ? v : cast(body, x, y)
    }

    static func bubble(_ x: Double, _ y: Double) -> Double {
        let front: Picture = { a, b in
            let tail = max(b - 344, 296 - b, 108 - a, (a - 168) + (b - 296) * 1.1)
            return min(sdRR(a, b, 72, 142, 290, 300, 36), tail)
        }
        let back: Picture = { a, b in sdRR(a, b, 162, 92, 326, 216, 30) }
        let lines: [[Double]] = [[106, 178, 256, 192], [106, 214, 256, 228], [106, 250, 200, 264]]
        if front(x, y) <= 0 {
            for l in lines where sdRR(x, y, l[0], l[1], l[2], l[3], 7) <= 0 {
                return sdRR(x, y - 2.6, l[0], l[1], l[2], l[3], 7) > 0 ? 0.72 : 0.1
            }
            return emboss(front, x, y, 22, 0.62, 0.44)
        }
        if back(x, y) <= 0 {
            let under = front(x - 10, y - 12) < 6 ? 0.22 : 0
            return min(0.9, emboss(back, x, y, 18, 0.34, 0.3) + under)
        }
        return max(cast(front, x, y), cast(back, x, y) * 0.7)
    }

    static func phone(_ x: Double, _ y: Double) -> Double {
        let outer: Picture = { a, b in sdRR(a, b, 121, 46, 269, 376, 32) }
        let frame: Picture = { a, b in abs(sdRR(a, b, 126, 51, 264, 371, 27)) - 6 }
        let v = emboss(frame, x, y, 6, 0.72, 0.4)
        if v != 0 { return v }
        if outer(x, y) > 0 { return cast(outer, x, y) }
        if sdRR(x, y, 176, 64, 214, 74, 5) <= 0 { return 0.8 }                    // the island
        let col = Int(((x - 141) / 38).rounded(.down)), row = Int(((y - 92) / 44).rounded(.down))
        if col < 0 || col > 2 || row < 0 || row > 5 { return 0.05 }
        let x0 = 141 + Double(col) * 38, y0 = 92 + Double(row) * 44
        let tile: Picture = { a, b in sdRR(a, b, x0, y0, x0 + 30, y0 + 30, 8) }
        if tile(x, y) > 0 { return 0.05 }
        let open = (row == 0 && col == 0) || (row == 2 && col == 1) || (row == 4 && col == 2)
        return open ? emboss(tile, x, y, 9, 0.8, 0.3) : 0.24                  // three stay solid, the rest fade
    }

    // MARK: Dots

    /// The 8 x 8 Bayer matrix, built the way the mock builds it.
    static let bayer: [[Int]] = {
        var m: [[Int]] = [[0]]
        let base = [[0, 2], [3, 1]]
        while m.count < 8 {
            let n = m.count
            var o = Array(repeating: Array(repeating: 0, count: n * 2), count: n * 2)
            for y in 0..<(n * 2) {
                for x in 0..<(n * 2) {
                    o[y][x] = 4 * m[y % n][x % n] + base[y / n][x / n]
                }
            }
            m = o
        }
        return m
    }()

    /// A picture as dots on the 390 x 460 canvas: flat [x0, y0, x1, y1, ...] of each dot's
    /// top-left corner, in design points.
    static func fill(_ picture: Picture) -> [Float] {
        var points: [Float] = []
        for j in 0..<230 {
            for i in 0..<195 {
                let x = Double(i * 2 + 1), y = Double(j * 2 + 1)
                let d = picture(x, y)
                if d > 0 && (Double(bayer[j & 7][i & 7]) + 0.5) / 64 < d {
                    points.append(Float(x - 0.67))
                    points.append(Float(y - 0.67))
                }
            }
        }
        return points
    }

    /// One picture scaled about its centre and drawn on a canvas of `cols` x `rows` cells,
    /// centred at (cx, cy): the mock's `still()`.
    static func still(_ picture: Picture, scale: Double, cx: Double, cy: Double, cols: Int, rows: Int) -> [Float] {
        var points: [Float] = []
        for j in 0..<rows {
            for i in 0..<cols {
                let x = Double(i * 2 + 1), y = Double(j * 2 + 1)
                let d = picture(195 + (x - cx) / scale, 224 + (y - cy) / scale)
                if d > 0 && (Double(bayer[j & 7][i & 7]) + 0.5) / 64 < d {
                    points.append(Float(x - 0.67))
                    points.append(Float(y - 0.67))
                }
            }
        }
        return points
    }

    // The pictures are fixed, so each is made once.
    static let clockDots = fill(clock)
    static let lockDots = fill(lock)
    static let bubbleDots = fill(bubble)
    static let phoneDots = fill(phone)
    /// The Homes' pictures (`canvas.pic`): the clock (Voting) and the bubble (the Summary) at
    /// 0.8 on the 390 x 340 canvas at top 74.
    static let homeClockDots = still(clock, scale: 0.8, cx: 195, cy: 196, cols: 195, rows: 170)
    static let homeBubbleDots = still(bubble, scale: 0.8, cx: 195, cy: 196, cols: 195, rows: 170)
}

/// The sign-in moon: every dot of `moon-col-light.png` with its colour, from the bundled
/// `moon-col-light.png.json` (`[i, j, r, g, b]`, 2pt cells).
struct LightMoon: Sendable {
    /// Flat [x0, y0, ...] top-left corners in design points, sorted top to bottom, left to right.
    let points: [Float]
    /// Flat [r0, g0, b0, ...] 0-255.
    let colors: [UInt8]
    var count: Int { points.count / 2 }

    static let shared: LightMoon = load()

    private static func load() -> LightMoon {
        guard let url = Bundle.main.url(forResource: "moon-col-light.png", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let rows = try? JSONDecoder().decode([[Int]].self, from: data) else {
            return LightMoon(points: [], colors: [])
        }
        let sorted = rows.filter { $0.count >= 5 }.sorted { $0[1] != $1[1] ? $0[1] < $1[1] : $0[0] < $1[0] }
        var points: [Float] = []
        var colors: [UInt8] = []
        points.reserveCapacity(sorted.count * 2)
        colors.reserveCapacity(sorted.count * 3)
        for d in sorted {
            points.append(Float(d[0] * 2) + 0.33)
            points.append(Float(d[1] * 2) + 0.33)
            colors.append(UInt8(clamping: d[2]))
            colors.append(UInt8(clamping: d[3]))
            colors.append(UInt8(clamping: d[4]))
        }
        return LightMoon(points: points, colors: colors)
    }
}

/// Draws flat dot lists into a Canvas at the stage scale.
enum DotPainter {
    /// One ink for every dot: a single path, a single fill.
    static func paintInk(_ points: [Float], count: Int? = nil, in context: GraphicsContext, scale s: CGFloat,
                         color: Color = Palette.dotInk) {
        let n = min(count ?? points.count / 2, points.count / 2)
        let side = DotArt.dotSize * s
        var path = Path()
        for k in 0..<n {
            path.addRect(CGRect(x: CGFloat(points[k * 2]) * s, y: CGFloat(points[k * 2 + 1]) * s, width: side, height: side))
        }
        context.fill(path, with: .color(color))
    }

    /// Each dot in its own colour.
    static func paintColored(_ points: [Float], colors: [UInt8], in context: GraphicsContext, scale s: CGFloat) {
        let n = min(points.count / 2, colors.count / 3)
        let side = DotArt.dotSize * s
        for k in 0..<n {
            let rect = CGRect(x: CGFloat(points[k * 2]) * s, y: CGFloat(points[k * 2 + 1]) * s, width: side, height: side)
            let c = Color(.sRGB, red: Double(colors[k * 3]) / 255, green: Double(colors[k * 3 + 1]) / 255,
                          blue: Double(colors[k * 3 + 2]) / 255)
            context.fill(Path(rect), with: .color(c))
        }
    }
}

/// A still dot picture in the one ink.
struct InkDots: View {
    @Environment(\.stageScale) private var s
    let points: [Float]

    var body: some View {
        Canvas { context, _ in
            DotPainter.paintInk(points, in: context, scale: s)
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}
