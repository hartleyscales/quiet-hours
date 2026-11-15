import Foundation
import SwiftUI

/// The Locked screen's moon: one fixed drawing of N dots (the app always asks for the same N).
///
/// A port of `design/scripts/color_moon.py`, mode `dark` with N: a serpentine Floyd-Steinberg
/// dither of `min(0.97, density * gain)` with a bisection on the gain so the count reaches N,
/// the rim pass (evenly spaced dots on the disc's rim, spaced by the density just inside),
/// then trimming or topping up the inside to exactly N. The random choices use the same
/// generator as the script (Python's Mersenne Twister, seeds 7 and 5), so a given N always
/// gives the same moon. Cells come from the bundled `moon-col-dark.png.cells.json`
/// (`[i, j, density, onRim, r, g, b]`, 2pt cells, drawn 390 x 240 at top 100).
struct DarkMoonCells: Sendable {
    let cw: Int
    let ch: Int
    let cx: Double
    let cy: Double
    /// The disc's radius in cells.
    let r: Double
    let i: [Int]
    let j: [Int]
    let density: [Double]
    let rgb: [UInt8]
    /// Cell index at (i, j), or -1 outside the disc.
    let grid: [Int]

    var count: Int { i.count }

    static let shared: DarkMoonCells? = {
        guard let url = Bundle.main.url(forResource: "moon-col-dark.png.cells", withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return DarkMoonCells(json: data)
    }()

    init?(json data: Data) {
        struct File: Decodable { let cw: Int; let ch: Int; let cx: Double; let cy: Double; let r: Double; let cells: [[Double]] }
        guard let file = try? JSONDecoder().decode(File.self, from: data) else { return nil }
        cw = file.cw
        ch = file.ch
        cx = file.cx
        cy = file.cy
        r = file.r
        var ii: [Int] = [], jj: [Int] = [], dd: [Double] = [], cc: [UInt8] = []
        var g = Array(repeating: -1, count: file.cw * file.ch)
        for cell in file.cells where cell.count >= 7 {
            let a = Int(cell[0]), b = Int(cell[1])
            guard a >= 0, a < file.cw, b >= 0, b < file.ch else { continue }
            g[b * file.cw + a] = ii.count
            ii.append(a)
            jj.append(b)
            dd.append(cell[2])
            cc.append(UInt8(clamping: Int(cell[4])))
            cc.append(UInt8(clamping: Int(cell[5])))
            cc.append(UInt8(clamping: Int(cell[6])))
        }
        i = ii
        j = jj
        density = dd
        rgb = cc
        grid = g
    }

    func index(_ a: Int, _ b: Int) -> Int {
        guard a >= 0, a < cw, b >= 0, b < ch else { return -1 }
        return grid[b * cw + a]
    }

    /// Cell indices of the dots for `n` people, in reading order.
    func dots(for n: Int) -> [Int] {
        guard n > 0, count > 0 else { return [] }
        if n >= count { return Array(0..<count) }

        // Dither with a bisection on the gain, then drop random dots down to N.
        var lo = 0.05, hi = 3.0
        for _ in 0..<30 {
            let k = (lo + hi) / 2
            if dither(gain: k).count < n { lo = k } else { hi = k }
        }
        var on = dither(gain: hi)
        var rnd7 = PythonRandom(seed: 7)
        while on.count > n { on.remove(at: rnd7.randbelow(on.count)) }

        // The rim pass.
        func inside(_ a: Int, _ b: Int) -> Bool { index(a, b) >= 0 }
        var ring: [Int] = []          // in grid order, as the script finds them
        var isRing = Array(repeating: false, count: count)
        for b in 0..<ch {
            for a in 0..<cw {
                let c = index(a, b)
                guard c >= 0 else { continue }
                if !(inside(a + 1, b) && inside(a - 1, b) && inside(a, b + 1) && inside(a, b - 1)) {
                    ring.append(c)
                    isRing[c] = true
                }
            }
        }
        var isOn = Array(repeating: false, count: count)
        for c in on { isOn[c] = true }
        // Sorted by angle around the centre; ties keep grid order (Python's sort is stable).
        let angles = ring.map { atan2(Double(j[$0]) - cy, Double(i[$0]) - cx) }
        let order = ring.indices.sorted { angles[$0] != angles[$1] ? angles[$0] < angles[$1] : $0 < $1 }
        ring = order.map { ring[$0] }

        func local(_ c: Int, _ r: Int = 4) -> Double {
            var total = 0, hit = 0
            for db in -r...r {
                for da in -r...r {
                    let q = index(i[c] + da, j[c] + db)
                    if q >= 0 && !isRing[q] {
                        total += 1
                        if isOn[q] { hit += 1 }
                    }
                }
            }
            return total > 0 ? Double(hit) / Double(total) : 0
        }
        let raw = ring.map { local($0) }
        let m = ring.count
        var smooth = Array(repeating: 0.0, count: m)
        for k in 0..<m {
            var sum = 0.0
            for d in -3...3 { sum += raw[((k + d) % m + m) % m] }
            smooth[k] = sum / 7
        }
        var keep = Set<Int>()
        for c in 0..<count where isOn[c] && !isRing[c] { keep.insert(c) }
        var acc = 0.5
        for k in 0..<m {
            acc += min(1.0, max(0.30, smooth[k].squareRoot() * 1.1))
            if acc >= 1 {
                keep.insert(ring[k])
                acc -= 1
            }
        }

        // Exactly N: trim or top up the inside.
        var rnd5 = PythonRandom(seed: 5)
        // Python sorts the (i, j) tuples: by i, then j.
        var inner = keep.filter { !isRing[$0] }.sorted { i[$0] != i[$1] ? i[$0] < i[$1] : j[$0] < j[$1] }
        rnd5.shuffle(&inner)
        let innerCount = inner.count
        if keep.count - innerCount > n {
            // Fewer people than the rim alone would take (the script assumes this never
            // happens). Keep the script's own split between rim and inside, the rim's share
            // evenly spaced along it, so the moon still has exactly N dots.
            let rimKept = ring.filter { keep.contains($0) }
            let rimShare = Int((Double(n) * Double(rimKept.count) / Double(rimKept.count + innerCount)).rounded())
            keep = Set((0..<rimShare).map { rimKept[$0 * rimKept.count / max(rimShare, 1)] })
            keep.formUnion(inner.suffix(n - rimShare))
            inner.removeAll()
        }
        while keep.count > n, let c = inner.popLast() { keep.remove(c) }
        if keep.count < n {
            var spare: [(cell: Int, key: Double, order: Int)] = []
            for b in 0..<ch {
                for a in 0..<cw {
                    let c = index(a, b)
                    guard c >= 0, !isRing[c], !keep.contains(c) else { continue }
                    spare.append((c, 0, spare.count))
                }
            }
            // The script sorts by brightness with a little noise.
            for k in spare.indices { spare[k].key = -brightness(spare[k].cell) + rnd5.random() * 0.2 }
            spare.sort { $0.key != $1.key ? $0.key < $1.key : $0.order < $1.order }
            for item in spare.prefix(n - keep.count) { keep.insert(item.cell) }
        }
        return keep.sorted { j[$0] != j[$1] ? j[$0] < j[$1] : i[$0] < i[$1] }
    }

    /// The cell's brightness `a`, recovered from its density: the cell data stores
    /// `(0.10 + 0.82 * smoothstep(0.18, 0.82, a)) * (1 - 0.30 * (1 - z)^2.2)`, where z is the
    /// sphere's depth at the cell. Outside 0.18...0.82 the smoothstep is flat, so those clamp.
    private func brightness(_ c: Int) -> Double {
        let x = (Double(i[c]) - cx) / r, y = -(Double(j[c]) - cy) / r
        let z = max(0, 1 - x * x - y * y).squareRoot()
        let s = min(1, max(0, (density[c] / (1 - 0.30 * pow(1 - z, 2.2)) - 0.10) / 0.82))
        let t = 0.5 - sin(asin(1 - 2 * s) / 3)
        return 0.18 + 0.64 * t
    }

    /// Serpentine Floyd-Steinberg over the disc. Returns the cells that get a dot.
    private func dither(gain: Double) -> [Int] {
        var on: [Int] = []
        var err = Array(repeating: 0.0, count: cw * ch)
        for b in 0..<ch {
            let s = b % 2 == 0 ? 1 : -1
            var a = s == 1 ? 0 : cw - 1
            while a >= 0 && a < cw {
                defer { a += s }
                let c = grid[b * cw + a]
                guard c >= 0 else { continue }
                let v = min(0.97, density[c] * gain) + err[b * cw + a]
                let o = v >= 0.5 ? 1.0 : 0.0
                let e = v - o
                if o == 1 { on.append(c) }
                for (da, db, w) in [(s, 0, 7.0 / 16), (-s, 1, 3.0 / 16), (0, 1, 5.0 / 16), (s, 1, 1.0 / 16)] {
                    let aa = a + da, bb = b + db
                    if aa >= 0 && aa < cw && bb >= 0 && bb < ch && grid[bb * cw + aa] >= 0 {
                        err[bb * cw + aa] += e * w
                    }
                }
            }
        }
        return on
    }
}

/// Python's `random.Random(seed)`: MT19937 seeded by `init_by_array([seed])`, with the same
/// `_randbelow`, `shuffle` and `random` the script uses.
struct PythonRandom {
    private var mt = [UInt32](repeating: 0, count: 624)
    private var index = 624

    init(seed: UInt32) {
        mt[0] = 19_650_218
        for k in 1..<624 {
            mt[k] = 1_812_433_253 &* (mt[k - 1] ^ (mt[k - 1] >> 30)) &+ UInt32(k)
        }
        let key: [UInt32] = [seed]
        var i = 1, j = 0
        for _ in 0..<max(624, key.count) {
            mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) &* 1_664_525)) &+ key[j] &+ UInt32(j)
            i += 1
            j += 1
            if i >= 624 { mt[0] = mt[623]; i = 1 }
            if j >= key.count { j = 0 }
        }
        for _ in 0..<623 {
            mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) &* 1_566_083_941)) &- UInt32(i)
            i += 1
            if i >= 624 { mt[0] = mt[623]; i = 1 }
        }
        mt[0] = 0x8000_0000
        index = 624
    }

    private mutating func next() -> UInt32 {
        if index >= 624 {
            for k in 0..<624 {
                let y = (mt[k] & 0x8000_0000) | (mt[(k + 1) % 624] & 0x7FFF_FFFF)
                mt[k] = mt[(k + 397) % 624] ^ (y >> 1) ^ ((y & 1) != 0 ? 0x9908_B0DF : 0)
            }
            index = 0
        }
        var y = mt[index]
        index += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C_5680
        y ^= (y << 15) & 0xEFC6_0000
        y ^= y >> 18
        return y
    }

    private mutating func bits(_ k: Int) -> UInt32 { next() >> UInt32(32 - k) }

    /// A uniform integer in 0..<n (`_randbelow_with_getrandbits`).
    mutating func randbelow(_ n: Int) -> Int {
        let k = Int.bitWidth - n.leadingZeroBitCount
        var r = Int(bits(k))
        while r >= n { r = Int(bits(k)) }
        return r
    }

    mutating func shuffle<T>(_ x: inout [T]) {
        guard x.count > 1 else { return }
        for i in stride(from: x.count - 1, through: 1, by: -1) {
            let j = randbelow(i + 1)
            x.swapAt(i, j)
        }
    }

    mutating func random() -> Double {
        let a = Double(next() >> 5), b = Double(next() >> 6)
        return (a * 67_108_864.0 + b) * (1.0 / 9_007_199_254_740_992.0)
    }
}

/// The Locked moon, drawn for `count` people. Recomputed only when the count changes. With
/// `comeOut`, its dots arrive from scattered places over about a second.
struct LockedMoonView: View {
    /// The night moon is one fixed drawing: the same dots whoever is in.
    static let dots = 3098
    @Environment(\.stageScale) private var s
    let count: Int
    var comeOut = false
    @State private var drawn: (count: Int, points: [Float], colors: [UInt8])?
    @State private var since: Date?
    @State private var settled = false

    var body: some View {
        // Read here, not only inside the renderer, so a new moon redraws the canvas.
        let current = drawn
        let scale = s
        let start = settled ? nil : since
        TimelineView(.animation(minimumInterval: nil, paused: start == nil)) { timeline in
            Canvas { context, _ in
                guard let current else { return }
                if let start {
                    Self.paintArriving(current.points, colors: current.colors, in: context, scale: scale,
                                       t: timeline.date.timeIntervalSince(start))
                } else {
                    DotPainter.paintColored(current.points, colors: current.colors, in: context, scale: scale)
                }
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
        .task(id: count) {
            let n = count
            let result = await Task.detached(priority: .userInitiated) { LockedMoonView.compute(n) }.value
            let first = drawn == nil
            drawn = (n, result.points, result.colors)
            if first && comeOut {
                since = Date()
                try? await Task.sleep(for: .seconds(1.05))
                settled = true
            }
        }
    }

    /// Each dot comes in from a scattered place on its own clock, fading up as it travels.
    private static func paintArriving(_ points: [Float], colors: [UInt8], in context: GraphicsContext, scale s: CGFloat, t: TimeInterval) {
        let n = min(points.count / 2, colors.count / 3)
        let side = DotArt.dotSize * s
        for k in 0..<n {
            // A fixed scatter per dot, from its index.
            var h = UInt64(k) &* 0x9E37_79B9_7F4A_7C15
            h ^= h >> 29; h = h &* 0xBF58_476D_1CE4_E5B9; h ^= h >> 32
            let r1 = Double(h & 0xFFFF) / 65_535, r2 = Double((h >> 16) & 0xFFFF) / 65_535, r3 = Double((h >> 32) & 0xFFFF) / 65_535
            let delay = r1 * 0.4
            let p = min(1, max(0, (t - delay) / 0.6))
            guard p > 0 else { continue }
            let e = 1 - pow(1 - p, 3)
            let angle = r2 * 2 * Double.pi, distance = 24 + r3 * 60
            let x = Double(points[k * 2]) + cos(angle) * distance * (1 - e)
            let y = Double(points[k * 2 + 1]) + sin(angle) * distance * (1 - e)
            let c = Color(.sRGB, red: Double(colors[k * 3]) / 255, green: Double(colors[k * 3 + 1]) / 255,
                          blue: Double(colors[k * 3 + 2]) / 255)
            context.fill(Path(CGRect(x: x * s, y: y * s, width: side, height: side)), with: .color(c.opacity(p)))
        }
    }

    /// The moon for `n` people as stage dots, its frame's top at `top`.
    static func picture(_ n: Int, top: Float) -> DotPicture {
        let r = compute(n)
        return DotPicture(points: r.points, colors: r.colors).shifted(dy: top)
    }

    nonisolated static func compute(_ n: Int) -> (points: [Float], colors: [UInt8]) {
        guard let cells = DarkMoonCells.shared else { return ([], []) }
        let dots = cells.dots(for: n)
        var points: [Float] = []
        var colors: [UInt8] = []
        points.reserveCapacity(dots.count * 2)
        colors.reserveCapacity(dots.count * 3)
        for c in dots {
            // Cell (i, j) of the 2pt grid; the dot sits a third of a point in.
            points.append(Float(cells.i[c] * 2) + 0.33)
            points.append(Float(cells.j[c] * 2) + 0.33)
            colors.append(cells.rgb[c * 3])
            colors.append(cells.rgb[c * 3 + 1])
            colors.append(cells.rgb[c * 3 + 2])
        }
        return (points, colors)
    }
}
