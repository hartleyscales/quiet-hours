import SwiftUI

// How one screen becomes the next (HOMES-QUIET.md, "Motion"; WEB-NOTES.md, "Changes of
// screen"). The root keeps the outgoing screen on stage while a seam runs, tells each screen
// its part through `seamRole`, and draws the dots that travel between them. Every effect ends
// when the seam ends: the outgoing screen is removed, the dot overlay is cleared, and the
// incoming screen is left exactly as a fresh render of it.

/// The neighbours with their own choreography. Everything else is a plain cross-fade.
enum Seam: Equatable {
    /// 250 ms (200 ms with Reduce Motion), whole screens.
    case fade
    /// The moon stays; the name shrinks into the headline; the form sinks away; "Next" rises.
    case signInToHow
    case howToSignIn
    /// One more dot morph (speech bubble to phone); the button glides to its new place.
    case howToLock
    /// The phone's dots re-form into the Home's picture; the words fade in; the pill rises.
    case lockToHome
    /// The surface lightens, the stars go out, the pill sinks away, the moon re-forms into the bubble.
    case lockedToQuestion
    /// The question's bubble settles into the Summary's smaller one; the words fade in.
    case questionToSummary

    /// How long the seam runs, start to end of its last effect.
    var duration: TimeInterval {
        switch self {
        case .fade: return 0.25
        case .signInToHow: return 0.75
        case .howToSignIn: return 0.95
        case .howToLock: return 1.15
        case .lockToHome: return 1.15
        case .lockedToQuestion: return 1.15
        case .questionToSummary: return 1.15
        }
    }
}

enum SeamRole: Equatable {
    case present
    case entering(Seam)
    case leaving(Seam)

    var seam: Seam? {
        switch self {
        case .present: return nil
        case .entering(let s), .leaving(let s): return s
        }
    }

    func isEntering(_ seam: Seam) -> Bool { self == .entering(seam) }
    func isLeaving(_ seam: Seam) -> Bool { self == .leaving(seam) }
}

extension EnvironmentValues {
    /// This screen's part in the change of screen under way.
    @Entry var seamRole: SeamRole = .present
    /// Dots are travelling between screens in the root's overlay: the pictures they stand in
    /// for stay hidden until they land.
    @Entry var dotsInFlight = false
    /// For a seam where one button's body stands in for another's: the label and the body
    /// (fill and shadow) of a `GoButton`, separately.
    @Entry var goLabelOpacity: Double = 1
    @Entry var goChromeOpacity: Double = 1
}

/// Where things are on the screens the seams join, in design points.
enum SeamGeometry {
    /// Sign-in's name (74/74 at 402) and How it works' headline (50/54 at 404): their middles.
    static let nameCentre: CGFloat = 402 + 37
    static let headlineCentre: CGFloat = 404 + 27
    /// How it works' button (bottom 34) and The lock's (above its small line).
    static let howGoY: CGFloat = 844 - 34 - 58
    static let lockGoY: CGFloat = 844 - 34 - 13 * 1.26 - 16 - 58
}

/// The curve the mock uses for things that travel: cubic-bezier(.2,.8,.2,1).
extension Animation {
    static func travel(_ duration: TimeInterval) -> Animation { .timingCurve(0.2, 0.8, 0.2, 1, duration: duration) }
    /// CSS `ease`.
    static func cssEase(_ duration: TimeInterval) -> Animation { .timingCurve(0.25, 0.1, 0.25, 1, duration: duration) }
}

// MARK: The dots between screens

/// A picture as dots in stage points, with a colour per dot (nil: the one ink).
struct DotPicture {
    var points: [Float]
    var colors: [UInt8]?
    var count: Int { points.count / 2 }

    func shifted(dy: Float) -> DotPicture {
        var p = points
        for i in stride(from: 1, to: p.count, by: 2) { p[i] += dy }
        return DotPicture(points: p, colors: colors)
    }
}

/// Draws dots travelling from one screen's picture to the next (`morph`), or drifting apart
/// and fading (`scatter`), under the incoming screen and over the outgoing one.
@MainActor
@Observable
final class DotOverlay {
    struct Run {
        let start: Date
        let duration: TimeInterval
        let k: Int
        let x0: [Float], y0: [Float], x1: [Float], y1: [Float]
        let c0: [UInt8], c1: [UInt8]
        let jitter: [Float]
        let inkOnly: Bool
        let scatter: Bool
    }

    private(set) var run: Run?
    private(set) var opacity: Double = 1
    private var generation = 0

    var isRunning: Bool { run != nil }

    /// Re-forms `from` into `to` over `duration`, as How it works does: dots paired top to
    /// bottom, each on its own slightly staggered clock, colours blending.
    func morph(from: DotPicture, to: DotPicture, duration: TimeInterval) {
        let na = from.count, nb = to.count
        guard na > 0, nb > 0 else { return }
        let k = max(na, nb)
        var x0 = [Float](repeating: 0, count: k), y0 = x0, x1 = x0, y1 = x0, j = x0
        var c0 = [UInt8](repeating: 0, count: k * 3), c1 = c0
        let ink: [UInt8] = [58, 52, 46]
        for i in 0..<k {
            let ia = i * na / k, ib = i * nb / k
            x0[i] = from.points[ia * 2]; y0[i] = from.points[ia * 2 + 1]
            x1[i] = to.points[ib * 2]; y1[i] = to.points[ib * 2 + 1]
            j[i] = Float.random(in: 0..<0.1)
            for c in 0..<3 {
                c0[i * 3 + c] = from.colors.map { $0[ia * 3 + c] } ?? ink[c]
                c1[i * 3 + c] = to.colors.map { $0[ib * 3 + c] } ?? ink[c]
            }
        }
        begin(Run(start: Date(), duration: duration, k: k, x0: x0, y0: y0, x1: x1, y1: y1, c0: c0, c1: c1,
                  jitter: j, inkOnly: from.colors == nil && to.colors == nil, scatter: false))
    }

    /// The dots drift apart from the picture's middle and fade.
    func scatter(_ picture: DotPicture, duration: TimeInterval) {
        let n = picture.count
        guard n > 0 else { return }
        var cx: Float = 0, cy: Float = 0
        for i in 0..<n { cx += picture.points[i * 2]; cy += picture.points[i * 2 + 1] }
        cx /= Float(n); cy /= Float(n)
        var x0 = [Float](repeating: 0, count: n), y0 = x0, x1 = x0, y1 = x0, j = x0
        for i in 0..<n {
            let x = picture.points[i * 2], y = picture.points[i * 2 + 1]
            x0[i] = x; y0[i] = y
            let angle = atan2(y - cy, x - cx) + Float.random(in: -0.5...0.5)
            let distance = Float.random(in: 14...46) * (0.6 + 0.4 * min(1, hypot(x - cx, y - cy) / 120))
            x1[i] = x + cos(angle) * distance
            y1[i] = y + sin(angle) * distance
            j[i] = Float.random(in: 0..<0.25)
        }
        let colors = picture.colors ?? []
        begin(Run(start: Date(), duration: duration, k: n, x0: x0, y0: y0, x1: x1, y1: y1, c0: colors, c1: colors,
                  jitter: j, inkOnly: picture.colors == nil, scatter: true))
    }

    /// The run stays (holding its last frame) until the root clears it at the end of the seam,
    /// in the same moment the incoming screen shows its own picture.
    private func begin(_ r: Run) {
        generation += 1
        opacity = 1
        run = r
    }

    /// An interrupted seam: whatever is drawn fades with the screens it came from.
    func fadeAway(_ duration: TimeInterval) {
        guard run != nil else { return }
        generation += 1
        let mine = generation
        withAnimation(.easeInOut(duration: duration)) { opacity = 0 }
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(duration + 0.05))
            guard let self, self.generation == mine else { return }
            self.run = nil
            self.opacity = 1
        }
    }

    func clear() {
        generation += 1
        run = nil
        opacity = 1
    }

    private static func ease(_ t: Double) -> Double { t < 0.5 ? 4 * t * t * t : 1 - pow(-2 * t + 2, 3) / 2 }

    func draw(_ context: GraphicsContext, scale s: CGFloat, at date: Date) {
        guard let r = run else { return }
        let p = min(1, date.timeIntervalSince(r.start) / r.duration)
        let side = DotArt.dotSize * s
        let k = r.k
        if r.scatter {
            // Out and away, quick at first; each dot fades on its own clock.
            for i in 0..<k {
                let t = min(1, max(0, (p - Double(r.jitter[i])) / 0.75))
                let e = 1 - pow(1 - t, 3)
                let alpha = 1 - t
                guard alpha > 0.01 else { continue }
                let x = CGFloat(r.x0[i] + (r.x1[i] - r.x0[i]) * Float(e)) * s
                let y = CGFloat(r.y0[i] + (r.y1[i] - r.y0[i]) * Float(e)) * s
                let color: Color
                if r.inkOnly {
                    color = Palette.dotInk
                } else {
                    color = Color(.sRGB, red: Double(r.c0[i * 3]) / 255, green: Double(r.c0[i * 3 + 1]) / 255, blue: Double(r.c0[i * 3 + 2]) / 255)
                }
                context.fill(Path(CGRect(x: x, y: y, width: side, height: side)), with: .color(color.opacity(alpha)))
            }
            return
        }
        let tint = Self.ease(min(1, p / 0.7))
        var ink = Path()
        for i in 0..<k {
            let e = p >= 1 ? 1 : Float(Self.ease(min(1, max(0, (p - Double(i) / Double(k) * 0.3 - Double(r.jitter[i])) / 0.6))))
            let rect = CGRect(x: CGFloat(r.x0[i] + (r.x1[i] - r.x0[i]) * e) * s,
                              y: CGFloat(r.y0[i] + (r.y1[i] - r.y0[i]) * e) * s, width: side, height: side)
            if r.inkOnly {
                ink.addRect(rect)
            } else {
                let q = i * 3
                func mix(_ c: Int) -> Double { (Double(r.c0[q + c]) + (Double(r.c1[q + c]) - Double(r.c0[q + c])) * tint) / 255 }
                context.fill(Path(rect), with: .color(Color(.sRGB, red: mix(0), green: mix(1), blue: mix(2))))
            }
        }
        if r.inkOnly { context.fill(ink, with: .color(Palette.dotInk)) }
    }
}

struct DotOverlayView: View {
    @Environment(\.stageScale) private var s
    let overlay: DotOverlay

    var body: some View {
        TimelineView(.animation(minimumInterval: nil, paused: !overlay.isRunning)) { timeline in
            Canvas { context, _ in
                overlay.draw(context, scale: s, at: timeline.date)
            }
        }
        .opacity(overlay.opacity)
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

// MARK: Small motion helpers for screens

/// A part of a screen that fades in at `delay` when its screen arrives through `seam`.
struct ArriveFade: ViewModifier {
    @Environment(\.seamRole) private var role
    let seam: Seam
    var delay: TimeInterval = 0.12
    var duration: TimeInterval = 0.3
    /// Raised things also rise 8 points; text only fades.
    var rise: CGFloat = 0
    @State private var shown: Bool?

    func body(content: Content) -> some View {
        let on = shown ?? !role.isEntering(seam)
        content
            .opacity(on ? 1 : 0)
            .modifier(DesignOffset(y: on ? 0 : rise))
            .onAppear {
                guard shown == nil else { return }
                shown = !role.isEntering(seam)
                if role.isEntering(seam) {
                    withAnimation(rise > 0 ? .travel(0.45).delay(delay) : .cssEase(duration).delay(delay)) { shown = true }
                }
            }
    }
}

/// A part that leaves when its screen leaves through `seam`: text fades, raised things sink 6
/// points as they fade.
struct LeaveFade: ViewModifier {
    @Environment(\.seamRole) private var role
    let seam: Seam
    var delay: TimeInterval = 0
    var sink: CGFloat = 0
    @State private var gone = false

    func body(content: Content) -> some View {
        content
            .opacity(gone ? 0 : 1)
            .modifier(DesignOffset(y: gone ? sink : 0))
            .onChange(of: role) { _, new in
                if new.isLeaving(seam) {
                    withAnimation((sink > 0 ? Animation.travel(0.38) : .cssEase(0.22)).delay(delay)) { gone = true }
                }
            }
    }
}

struct DesignOffset: ViewModifier {
    @Environment(\.stageScale) private var s
    var x: CGFloat = 0
    var y: CGFloat

    func body(content: Content) -> some View {
        content.offset(x: x * s, y: y * s)
    }
}

extension View {
    func arrives(_ seam: Seam, delay: TimeInterval = 0.12, duration: TimeInterval = 0.3, rise: CGFloat = 0) -> some View {
        modifier(ArriveFade(seam: seam, delay: delay, duration: duration, rise: rise))
    }

    func leaves(_ seam: Seam, delay: TimeInterval = 0, sink: CGFloat = 0) -> some View {
        modifier(LeaveFade(seam: seam, delay: delay, sink: sink))
    }

    /// Hidden while its screen takes part in `seams` in the given way.
    func hidden(whenEntering entering: [Seam] = [], leaving: [Seam] = []) -> some View {
        modifier(SeamHidden(entering: entering, leaving: leaving))
    }

    /// Hidden while the root's travelling dots stand in for this picture.
    func hiddenWhileDots(entering: [Seam] = [], leaving: [Seam] = []) -> some View {
        modifier(DotsHidden(entering: entering, leaving: leaving))
    }

    /// Gone the moment its screen starts to leave through `seam`.
    func vanishes(leaving seam: Seam) -> some View {
        modifier(SeamVanish(leaving: seam))
    }

    func glides(_ seam: Seam, fromScale: CGFloat, fromY: CGFloat) -> some View {
        modifier(GlideIn(seam: seam, fromScale: fromScale, fromY: fromY))
    }
}

/// Hidden from the first moment of a seam (another screen's copy of it takes over).
struct SeamVanish: ViewModifier {
    @Environment(\.seamRole) private var role
    let leaving: Seam
    func body(content: Content) -> some View {
        content.opacity(role.isLeaving(leaving) ? 0 : 1)
    }
}

/// Hidden while the root's dots stand in for it.
struct DotsHidden: ViewModifier {
    @Environment(\.seamRole) private var role
    @Environment(\.dotsInFlight) private var inFlight
    let entering: [Seam]
    let leaving: [Seam]
    func body(content: Content) -> some View {
        let hide = inFlight && (entering.contains { role.isEntering($0) } || leaving.contains { role.isLeaving($0) })
        content.opacity(hide ? 0 : 1)
    }
}

/// Arriving through `seam`, it travels from another screen's copy of it: from `fromScale` and
/// `fromY` design points away, to its own place.
struct GlideIn: ViewModifier {
    @Environment(\.seamRole) private var role
    let seam: Seam
    let fromScale: CGFloat
    let fromY: CGFloat
    @State private var landed: Bool?

    func body(content: Content) -> some View {
        let home = landed ?? !role.isEntering(seam)
        content
            .scaleEffect(home ? 1 : fromScale)
            .modifier(DesignOffset(y: home ? 0 : fromY))
            .onAppear {
                guard landed == nil else { return }
                landed = !role.isEntering(seam)
                if role.isEntering(seam) { withAnimation(.travel(0.45)) { landed = true } }
            }
    }
}

struct SeamHidden: ViewModifier {
    @Environment(\.seamRole) private var role
    let entering: [Seam]
    let leaving: [Seam]

    func body(content: Content) -> some View {
        let hide = entering.contains { role.isEntering($0) } || leaving.contains { role.isLeaving($0) }
        content.opacity(hide ? 0 : 1)
    }
}
