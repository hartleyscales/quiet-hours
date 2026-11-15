import SwiftUI

/// The mock's How it works animation: the moon's dots re-form into each step's picture,
/// changing count quietly and draining from the moon's colours to one ink.
@MainActor
@Observable
final class DotMorph {
    static let duration: TimeInterval = 1.1

    /// moon, clock, lock, bubble.
    private let states: [[Float]]
    private let moon = LightMoon.shared
    private let jitter: [Float]

    private(set) var step = 0
    private(set) var running = false
    private var from: [Float]
    private var to: [Float]
    private var target: [Float]
    private var start = Date()
    private var tintFrom = 1.0
    private var tintTo = 1.0
    private var generation = 0

    init() {
        let moonPoints = LightMoon.shared.points
        states = [moonPoints, DotArt.clockDots, DotArt.lockDots, DotArt.bubbleDots]
        let most = states.map { $0.count / 2 }.max() ?? 0
        jitter = (0..<most).map { _ in Float.random(in: 0..<0.1) }
        from = moonPoints
        to = moonPoints
        target = moonPoints
    }

    private static func ease(_ t: Double) -> Double {
        t < 0.5 ? 4 * t * t * t : 1 - pow(-2 * t + 2, 3) / 2
    }

    /// What to draw at `date`: dot corners, and how much of the moon's colour is left
    /// (1 = the moon's own colours, 0 = ink).
    func frame(at date: Date) -> (points: [Float], tint: Double) {
        guard running else { return (target, tintTo) }
        let p = min(1, date.timeIntervalSince(start) / Self.duration)
        if p >= 1 { return (target, tintTo) }
        let tint = tintFrom + (tintTo - tintFrom) * Self.ease(min(1, p / 0.7))
        let k = from.count / 2
        var cur = [Float](repeating: 0, count: k * 2)
        for i in 0..<k {
            let e = Float(Self.ease(min(1, max(0, (p - Double(i) / Double(k) * 0.3 - Double(jitter[i])) / 0.6))))
            cur[i * 2] = from[i * 2] + (to[i * 2] - from[i * 2]) * e
            cur[i * 2 + 1] = from[i * 2 + 1] + (to[i * 2 + 1] - from[i * 2 + 1]) * e
        }
        return (cur, tint)
    }

    /// Back to the moon at rest, for How it works shown again.
    func reset() {
        generation += 1
        step = 0
        running = false
        from = states[0]
        to = states[0]
        target = states[0]
        tintFrom = 1
        tintTo = 1
    }

    /// The picture as it is drawn at `date`, for the dots that travel to the next screen.
    func picture(at date: Date) -> DotPicture {
        let (points, tint) = frame(at: date)
        guard tint > 0.01, moon.count > 0 else { return DotPicture(points: points, colors: nil) }
        let c = points.count / 2, n = moon.count
        var colors = [UInt8](repeating: 0, count: c * 3)
        let ink = DotArt.ink
        for i in 0..<c {
            let m = (i * n / c) * 3
            colors[i * 3] = UInt8((ink.r + (Double(moon.colors[m]) - ink.r) * tint).rounded())
            colors[i * 3 + 1] = UInt8((ink.g + (Double(moon.colors[m + 1]) - ink.g) * tint).rounded())
            colors[i * 3 + 2] = UInt8((ink.b + (Double(moon.colors[m + 2]) - ink.b) * tint).rounded())
        }
        return DotPicture(points: points, colors: colors)
    }

    /// Moves to `next`'s picture. With Reduce Motion the picture changes at once.
    func go(_ next: Int, reduceMotion: Bool) {
        let now = Date()
        let current = frame(at: now)
        step = next
        let a = current.points, b = states[next]
        target = b
        tintFrom = current.tint
        tintTo = next == 0 ? 1 : 0
        generation += 1
        if reduceMotion {
            running = false
            from = b
            to = b
            return
        }
        let na = a.count / 2, nb = b.count / 2, k = max(na, nb)
        var f = [Float](repeating: 0, count: k * 2), t = [Float](repeating: 0, count: k * 2)
        for i in 0..<k {
            let ia = i * na / k, ib = i * nb / k
            f[i * 2] = a[ia * 2]
            f[i * 2 + 1] = a[ia * 2 + 1]
            t[i * 2] = b[ib * 2]
            t[i * 2 + 1] = b[ib * 2 + 1]
        }
        from = f
        to = t
        start = now
        running = true
        let mine = generation
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(Self.duration + 0.05))
            guard let self, self.generation == mine else { return }
            self.running = false
        }
    }

    func draw(_ context: GraphicsContext, scale s: CGFloat, at date: Date) {
        let (points, tint) = frame(at: date)
        if tint <= 0.01 {
            DotPainter.paintInk(points, in: context, scale: s)
            return
        }
        let c = points.count / 2, n = moon.count
        guard c > 0, n > 0 else { return }
        let ink = DotArt.ink
        let side = DotArt.dotSize * s
        for i in 0..<c {
            let m = (i * n / c) * 3
            let r = (ink.r + (Double(moon.colors[m]) - ink.r) * tint) / 255
            let g = (ink.g + (Double(moon.colors[m + 1]) - ink.g) * tint) / 255
            let b = (ink.b + (Double(moon.colors[m + 2]) - ink.b) * tint) / 255
            let rect = CGRect(x: CGFloat(points[i * 2]) * s, y: CGFloat(points[i * 2 + 1]) * s, width: side, height: side)
            context.fill(Path(rect), with: .color(Color(.sRGB, red: (r * 255).rounded() / 255,
                                                         green: (g * 255).rounded() / 255,
                                                         blue: (b * 255).rounded() / 255)))
        }
    }
}

/// 2 · How it works: three steps, the dots re-form between them.
struct HowItWorksScreen: View {
    @Environment(AppModel.self) private var model
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    /// Owned by the root, so the dots can travel on to the next screen from where they are.
    let morph: DotMorph

    private static let copy: [(title: String, sub: String, button: String)] = [
        ("Quiet Hours", "", "Next"),
        ("Vote on the hour.", "Each week the campus picks one window of time. You get a say.", "Next"),
        ("Then it goes quiet.", "When it starts, your distracting apps lock. So do everyone else's.", "Next"),
        ("Hear how it went.", "Afterwards, read what people did with the time.", "Got it"),
    ]

    var body: some View {
        Stage(surface: Palette.surface) {
            ZStack(alignment: .topLeading) {
                DotMorphCanvas(morph: morph)
                    .designFrame(width: 390, height: 460)
                    .hiddenWhileDots(leaving: [.howToLock, .howToSignIn])

                Text(Self.copy[morph.step].title)
                    .textStyle(.serif(50, line: 54))
                    .foregroundStyle(Palette.ink)
                    .modifier(StepIn(step: morph.step, reduceMotion: reduceMotion))
                    // From sign-in, the name shrinks into this headline.
                    .glides(.signInToHow, fromScale: 74.0 / 50.0, fromY: SeamGeometry.nameCentre - SeamGeometry.headlineCentre)
                    .leaves(.howToLock)
                    .vanishes(leaving: .howToSignIn)
                    .centred(y: 404, padding: 28)
                Text(Self.copy[morph.step].sub)
                    .textStyle(.sans(18, 300, line: 26))
                    .foregroundStyle(Palette.muted)
                    .modifier(StepIn(step: morph.step, reduceMotion: reduceMotion))
                    .leaves(.howToLock)
                    .leaves(.howToSignIn)
                    .centred(y: 470, padding: 44)

                Pips(on: morph.step > 0 ? morph.step - 1 : nil)
                    .arrives(.signInToHow, delay: 0.24)
                    .leaves(.howToLock)
                    .leaves(.howToSignIn)
                    .frame(maxWidth: .infinity)
                    .pinned(bottom: 116, width: nil)

                GoButton(title: Self.copy[morph.step].button) { next() }
                    .modifier(GoGlide(seam: .howToLock, toY: SeamGeometry.lockGoY - SeamGeometry.howGoY))
                    .arrives(.signInToHow, delay: 0.2, rise: 8)
                    .leaves(.howToSignIn, sink: 6)
                    .pinned(bottom: 34)
            }
        }
        .task {
            try? await Task.sleep(for: .seconds(0.9))
            if morph.step == 0 { morph.go(1, reduceMotion: reduceMotion) }
            for step in stride(from: 2, through: min(3, DebugLaunch.howStep), by: 1) {
                try? await Task.sleep(for: .seconds(1.5))
                morph.go(step, reduceMotion: reduceMotion)
            }
        }
    }

    private func next() {
        if morph.step == 3 {
            model.finishHowItWorks()
        } else {
            morph.go(morph.step + 1, reduceMotion: reduceMotion)
        }
    }
}

/// How it works' button on its way to The lock's place: it travels up while its label fades;
/// The lock's own button, label only, comes in on top and its body takes over at the end.
private struct GoGlide: ViewModifier {
    @Environment(\.seamRole) private var role
    let seam: Seam
    let toY: CGFloat
    @State private var moved = false
    @State private var labelGone = false

    func body(content: Content) -> some View {
        content
            .modifier(DesignOffset(y: moved ? toY : 0))
            .environment(\.goLabelOpacity, labelGone ? 0 : 1)
            .onChange(of: role) { _, new in
                guard new.isLeaving(seam) else { return }
                withAnimation(.travel(0.45)) { moved = true }
                withAnimation(.cssEase(0.22)) { labelGone = true }
            }
    }
}

/// The step's words fade up 6 points each time they change (`@keyframes hwin`, .5s ease).
struct StepIn: ViewModifier {
    @Environment(\.stageScale) private var s
    let step: Int
    let reduceMotion: Bool

    private struct Value {
        var opacity = 1.0
        var y: CGFloat = 0
    }

    func body(content: Content) -> some View {
        let scale = s
        return content
            .keyframeAnimator(initialValue: Value(), trigger: reduceMotion ? 0 : step + 1) { view, value in
                view.opacity(value.opacity).offset(y: value.y * scale)
            } keyframes: { _ in
                KeyframeTrack(\.opacity) {
                    MoveKeyframe(0)
                    LinearKeyframe(1, duration: 0.5, timingCurve: .cssEase)
                }
                KeyframeTrack(\.y) {
                    MoveKeyframe(6)
                    LinearKeyframe(0, duration: 0.5, timingCurve: .cssEase)
                }
            }
    }
}

extension UnitCurve {
    /// CSS `ease`.
    static let cssEase = UnitCurve.bezier(startControlPoint: UnitPoint(x: 0.25, y: 0.1),
                                          endControlPoint: UnitPoint(x: 0.25, y: 1))
}

/// Redraws the morph every frame while it runs, and not at all while it rests.
struct DotMorphCanvas: View {
    @Environment(\.stageScale) private var s
    let morph: DotMorph

    var body: some View {
        TimelineView(.animation(minimumInterval: nil, paused: !morph.running)) { timeline in
            Canvas { context, _ in
                morph.draw(context, scale: s, at: timeline.date)
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}
