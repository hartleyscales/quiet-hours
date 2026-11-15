import SwiftUI

/// Every Home (HOMES-QUIET.md), built like the intro screens: one picture, one statement in
/// the serif, one grey line, and at most one thing to do. The gear sits alone, top right.
///
/// One view for all of them, so moving between phases changes the words and the picture and
/// nothing jumps: the statement sits on the same line on every Home. When the scene changes,
/// only what changed moves, in one transaction chosen here (`animation(from:to:)`). The layout
/// reads only `HomeScene`; every decision about content is in HomeData.swift.
struct HomeView: View {
    let scene: HomeScene
    let actions: HomeActions
    @Environment(\.seamRole) private var role
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    @State private var shown: HomeScene
    @State private var appeared = false
    /// The dots re-forming from one Home's picture into the next's, as How it works does.
    @State private var morph = DotOverlay()
    @State private var morphing = false
    @State private var morphGeneration = 0
    /// The Summary: which highlight shows, whether it is faded in, and whether the timer runs.
    @State private var highlight = 0
    @State private var highlightIn = true
    @State private var rotating = true
    @State private var advancing = false
    /// Arriving through a seam: each part comes in on its own cue.
    @State private var gearIn = true
    @State private var wordsIn = true
    @State private var footIn = true
    /// Leaving for the question: the stars, the gear and the pill go.
    @State private var departing = false

    init(scene: HomeScene, actions: HomeActions) {
        self.scene = scene
        self.actions = actions
        _shown = State(initialValue: scene)
    }

    /// The gear's place: `.bar` right edge (390 - 24 - 42).
    static let gearX: CGFloat = 324

    private var rising: Bool { role.isEntering(.lockToHome) || role.isEntering(.questionToSummary) }

    var body: some View {
        Stage(surface: shown.night ? Palette.night : Palette.surface) {
            ScaleReader { s in
                ZStack(alignment: .topLeading) {
                    if shown.night {
                        // With Reduce Motion the stars and the moon's dots do not come out a
                        // few at a time: they cross-fade with the rest.
                        StarsView(comeOut: appeared && !reduceMotion)
                            .designFrame(width: 390, height: 844)
                            .opacity((shown.out ? 0.55 : 1) * (departing ? 0 : 1))
                            .transition(.opacity)
                    }

                    picture

                    GearButton(night: shown.night, action: actions.openSettings)
                        .opacity(gearIn && !departing ? 1 : 0)
                        .at(x: Self.gearX, y: 52)

                    words(s)
                        .opacity(wordsIn ? 1 : 0)
                        .leaves(.lockedToQuestion)

                    foot
                        .opacity(footIn && !departing ? 1 : 0)
                        .modifier(DesignOffset(y: footIn && !departing ? 0 : 8))
                }
                .frame(width: Design.width * s, height: Design.height * s, alignment: .topLeading)
                .contentShape(Rectangle())
                // The Summary: a tap anywhere goes to the next highlight and stops the timer.
                .onTapGesture { tapHighlight() }
            }
        }
        .onChange(of: scene) { _, new in
            let animation = animation(from: shown, to: new)
            pictureChange(from: shown.picture, to: new.picture)
            if new.kind != shown.kind || new.highlights != shown.highlights {
                highlight = 0
                highlightIn = true
                rotating = true
            }
            withAnimation(animation) { shown = new }
        }
        .onChange(of: role) { _, new in
            if new.isLeaving(.lockedToQuestion) {
                withAnimation(.travel(0.5)) { departing = true }
            }
        }
        .task(id: rotationKey) { await rotate() }
        .onAppear {
            if rising {
                gearIn = false; wordsIn = false; footIn = false
                withAnimation(.cssEase(0.3).delay(0.06)) { gearIn = true }
                withAnimation(.cssEase(0.4).delay(0.4)) { wordsIn = true }
                withAnimation(.travel(0.45).delay(0.55)) { footIn = true }
            }
            appeared = true
        }
    }

    /// One transaction per change of Home: the slow change into and out of Locked, a 300 ms
    /// ease for opting out or back in, a quick cross-fade for everything else, and nothing for
    /// new numbers on the same screen.
    private func animation(from a: HomeScene, to b: HomeScene) -> Animation? {
        let changed = a.kind != b.kind || a.out != b.out || a.options?.chosenID != b.options?.chosenID
            || a.pill?.key != b.pill?.key || (a.options == nil) != (b.options == nil)
        if reduceMotion { return changed ? .easeInOut(duration: 0.2) : nil }
        if a.night != b.night { return .easeInOut(duration: 0.9) }
        if a.out != b.out { return .easeInOut(duration: 0.3) }
        return changed ? .easeInOut(duration: 0.25) : nil
    }

    // MARK: The picture

    private var pictureOpacity: Double {
        shown.out ? (shown.night ? 0.22 : 0.3) : 1
    }

    private var picture: some View {
        ZStack(alignment: .topLeading) {
            ZStack(alignment: .topLeading) {
                PictureLayer(picture: shown.picture, comeOut: appeared && !reduceMotion)
                    .id(shown.picture.form)
                    .transition(.asymmetric(
                        // The night moon's dots arrive by themselves, scattered.
                        insertion: shown.picture.isNight && !reduceMotion ? .identity : .opacity,
                        removal: .opacity))
            }
            .opacity(morphing ? 0 : 1)
            DotOverlayView(overlay: morph)
                .designFrame(width: 390, height: 844)
        }
        .opacity(pictureOpacity)
        .hiddenWhileDots(entering: [.lockToHome, .questionToSummary], leaving: [.lockedToQuestion])
        .leaves(.lockedToQuestion)
    }

    /// Between two daylight pictures the dots re-form, as in How it works; anything else
    /// cross-fades in the change's own transaction.
    private func pictureChange(from a: HomePicture, to b: HomePicture) {
        guard a.form != b.form else { return }
        morphGeneration += 1
        let generation = morphGeneration
        guard !morphing, !reduceMotion, !a.isNight, !b.isNight, role == .present else {
            endMorph()
            return
        }
        morph.morph(from: a.stageDots, to: b.stageDots, duration: DotMorph.duration)
        morphing = true
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(DotMorph.duration))
            guard generation == morphGeneration else { return }
            endMorph()
        }
    }

    /// The morph has landed (or was cut short): the picture itself shows again, exactly as a
    /// fresh render of it.
    private func endMorph() {
        guard morphing else { return }
        var t = Transaction()
        t.disablesAnimations = true
        withTransaction(t) {
            morphing = false
            morph.clear()
        }
    }

    // MARK: The words

    private var statementColor: Color {
        shown.night ? (shown.out ? Palette.nightPale : Palette.nightText) : (shown.out ? Palette.pale : Palette.ink)
    }

    private var lineColor: Color {
        shown.night ? (shown.out ? Palette.nightText : Palette.nightMuted) : (shown.out ? Palette.ink : Palette.muted)
    }

    /// `.qline`'s top on each Home.
    private var lineTop: CGFloat {
        switch shown.kind {
        case .vote: return 522
        case .decided, .day: return 564
        case .locked: return 528
        case .summaryBefore: return 584
        case .summary: return 606
        }
    }

    private var statementText: String {
        if shown.kind == .summary, shown.highlights.indices.contains(highlight) { return shown.highlights[highlight] }
        return shown.statement
    }

    private func words(_ s: CGFloat) -> some View {
        ZStack(alignment: .topLeading) {
            ZStack(alignment: .topLeading) {
                statement(s)
                    // The highlights change by their own fade; everything else cross-fades.
                    .id(shown.kind == .summary ? "highlights" : "\(shown.statementSize)-\(shown.statement)")
                    .transition(.opacity)
            }

            if let time = shown.time {
                Text(time)
                    .textStyle(.sans(24, line: 30))
                    .foregroundStyle(shown.out ? Palette.pale : Palette.ink)
                    .lineLimit(1)
                    .centred(y: 524)
                    .id(time)
                    .transition(.opacity)
            }

            if shown.kind == .summary, shown.highlights.count > 1 {
                // `.qpips`: which highlight this is.
                HStack(spacing: 8 * s) {
                    ForEach(shown.highlights.indices, id: \.self) { i in
                        Circle()
                            .fill(i == highlight ? Palette.ink : Palette.pip)
                            .designFrame(width: 7, height: 7)
                    }
                }
                .animation(.cssEase(0.3), value: highlight)
                .frame(width: Design.width * s)
                .at(y: 580)
                .transition(.opacity)
                .accessibilityHidden(true)
            }

            let line = shown.notice ?? shown.line
            if !line.isEmpty {
                Text(GreedyLines.wrap(line, style: .sans(15, line: 21), width: 302, scale: s))
                    .textStyle(.sans(15, line: 21))
                    .foregroundStyle(lineColor)
                    .lineLimit(shown.kind == .vote ? 3 : nil)
                    .fixedSize(horizontal: false, vertical: true)
                    .centred(y: lineTop, padding: 44)
                    .id("\(lineTop)-\(line)")
                    .transition(.opacity)
            }
        }
    }

    @ViewBuilder private func statement(_ s: CGFloat) -> some View {
        switch shown.statementSize {
        case .vote:
            Text(GreedyLines.wrap(statementText, style: .serif(54, line: 60), width: 374, scale: s))
                .textStyle(.serif(54, line: 60))
                .foregroundStyle(statementColor)
                .fixedSize(horizontal: false, vertical: true)
                .centred(y: 452, padding: 8)
        case .window:
            Text(GreedyLines.wrap(statementText, style: .serif(64, line: 68), width: 334, scale: s))
                .textStyle(.serif(64, line: 68))
                .foregroundStyle(statementColor)
                .fixedSize(horizontal: false, vertical: true)
                .centred(y: 452, padding: 28)
        case .recap, .over:
            // `.qs .qbig`: centred in a 132-high box at 432.
            let style: TextStyle = shown.statementSize == .recap ? .serif(38, line: 44) : .serif(52, line: 56)
            Text(GreedyLines.wrap(statementText, style: style, width: 334, scale: s))
                .textStyle(style)
                .foregroundStyle(statementColor)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .opacity(highlightIn ? 1 : 0)
                .designFrame(width: 334, height: 132)
                .at(x: 28, y: 432)
                .accessibilityAddTraits(shown.highlights.count > 1 ? .isButton : [])
                .accessibilityHint(shown.highlights.count > 1 ? "Shows the next thing people did." : "")
        }
    }

    // MARK: The Summary's highlights

    private var rotationKey: String {
        "\(shown.kind == .summary)-\(shown.highlights.count)-\(shown.highlights.first ?? "")-\(rotating)-\(reduceMotion)"
    }

    /// One at a time, every 3.8 seconds, in the server's order. With Reduce Motion they do not
    /// change by themselves.
    private func rotate() async {
        guard shown.kind == .summary, shown.highlights.count > 1, rotating, !reduceMotion else { return }
        while !Task.isCancelled {
            try? await Task.sleep(for: .seconds(3.8))
            guard !Task.isCancelled else { return }
            await advance()
        }
    }

    private func tapHighlight() {
        guard shown.kind == .summary, shown.highlights.count > 1 else { return }
        rotating = false
        Task { await advance() }
    }

    /// Fades the highlight out (0.42 s), changes it, fades it back in.
    private func advance() async {
        let n = shown.highlights.count
        guard n > 1, !advancing else { return }
        advancing = true
        defer { advancing = false }
        let fade = reduceMotion ? 0.1 : 0.42
        withAnimation(.easeInOut(duration: fade)) { highlightIn = false }
        try? await Task.sleep(for: .seconds(fade))
        highlight = (highlight + 1) % max(1, shown.highlights.count)
        withAnimation(.easeInOut(duration: fade)) { highlightIn = true }
    }

    // MARK: The one thing to do

    private var foot: some View {
        ZStack(alignment: .topLeading) {
            if let options = shown.options {
                OptionsView(block: options, pale: shown.out, packed: false, action: actions.vote)
                    .pinned(bottom: 46)
                    .transition(reduceMotion ? .opacity : .modifier(active: Sunk(gone: true), identity: Sunk(gone: false)))
            }
            if let pill = shown.pill {
                pillView(pill)
                    .id(pill.key)
                    .pinned(bottom: 46)
                    // Leaving, it fades and sinks a few points; arriving, it rises.
                    .transition(reduceMotion ? .opacity : .modifier(active: Sunk(gone: true), identity: Sunk(gone: false)))
            }
        }
    }

    @ViewBuilder private func pillView(_ pill: HomePill) -> some View {
        switch pill {
        case .board(let title):
            BoardPill(title: title, night: shown.night, action: actions.openBoard)
        case .optBackIn:
            GoButton(title: "Opt back in", enabled: !shown.busy, action: actions.optBackIn)
        case .join(let title):
            GoButton(title: title, night: true, enabled: !shown.busy, action: actions.join)
        }
    }
}

/// Fading and sinking a few points (leaving), or fading up from there (arriving).
private struct Sunk: ViewModifier {
    @Environment(\.stageScale) private var s
    let gone: Bool
    func body(content: Content) -> some View {
        content.opacity(gone ? 0 : 1).offset(y: gone ? 6 * s : 0)
    }
}

// MARK: Pictures

/// One Home picture at rest, at its own place.
private struct PictureLayer: View {
    let picture: HomePicture
    let comeOut: Bool

    var body: some View {
        switch picture {
        case .clock:
            InkDots(points: DotArt.homeClockDots)
                .designFrame(width: 390, height: 340)
                .at(y: 74)
        case .bubble:
            InkDots(points: DotArt.homeBubbleDots)
                .designFrame(width: 390, height: 340)
                .at(y: 74)
        case .moon:
            LightMoonView()
                .designFrame(width: 390, height: 540)
                .at(y: 49)
        case .night(let count):
            LockedMoonView(count: count, comeOut: comeOut)
                .designFrame(width: 390, height: 240)
                .at(y: 192)
        }
    }
}

extension HomePicture {
    /// The picture as dots in stage points, for dots that travel from one picture to another.
    @MainActor var stageDots: DotPicture {
        switch self {
        case .clock: return DotPicture(points: DotArt.homeClockDots, colors: nil).shifted(dy: 74)
        case .bubble: return DotPicture(points: DotArt.homeBubbleDots, colors: nil).shifted(dy: 74)
        case .moon: return DotPicture(points: LightMoon.shared.points, colors: LightMoon.shared.colors).shifted(dy: 49)
        case .night(let count): return LockedMoonView.picture(count, top: 192)
        }
    }
}

// MARK: The pills

/// `.qopts`: the three choices. Voted, the chosen one is pressed in and each fills from the
/// left to its share of the votes. Out, they are not shown: the Home has only "Opt back in".
private struct OptionsView: View {
    @Environment(\.stageScale) private var s
    let block: OptionsBlock
    let pale: Bool
    let packed: Bool
    let action: (String) -> Void

    var body: some View {
        VStack(spacing: (packed ? 0 : 12) * s) {
            ForEach(block.pills) { pill in
                OptionPillView(pill: pill, voted: block.voted, pale: pale, pressable: block.pressable) { action(pill.id) }
            }
        }
    }
}

/// `.qopt`: the day on the left, the time on the right.
private struct OptionPillView: View {
    @Environment(\.stageScale) private var s
    let pill: OptionPill
    let voted: Bool
    let pale: Bool
    let pressable: Bool
    let action: () -> Void
    @State private var tick = 0

    var body: some View {
        let pressed = pill.chosen && !pale
        Button {
            guard pressable else { return }
            tick += 1
            action()
        } label: {
            HStack(spacing: 12 * s) {
                Text(pill.day)
                    .textStyle(.sans(17, 500))
                    .foregroundStyle(pale ? Palette.pale : Palette.ink)
                Spacer(minLength: 0)
                Text(pill.time)
                    .textStyle(.sans(16))
                    .foregroundStyle(pale ? Palette.pale : Palette.muted)
            }
            .lineLimit(1)
            .designPadding(.horizontal, 24)
            .designFrame(width: 342, height: 58)
            .background {
                ZStack {
                    ZStack {
                        DepthBox(.pill, radius: 29).opacity(pale || pressed ? 0 : 1)
                        DepthBox(.pillChosen, radius: 29).opacity(pressed ? 1 : 0)
                    }
                    .animation(.travel(0.2), value: pressed)
                    // `::before`: the share of the votes, a faint tint from the left, over the
                    // pill's face and under the words, cut to the pill's shape.
                    Color.clear
                        .overlay(alignment: .leading) {
                            Rectangle()
                                .fill(Color(hex: 0x1C1A18, alpha: 0.075))
                                .designFrame(width: voted && !pale ? 342 * min(1, max(0, pill.share)) : 0)
                                .animation(.travel(0.6), value: voted)
                                .animation(.travel(0.6), value: pill.share)
                        }
                        .clipShape(RoundedRectangle(cornerRadius: 29 * s))
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(PlainPress())
        .allowsHitTesting(pressable)
        .sensoryFeedback(.selection, trigger: tick)
        .accessibilityAddTraits(pill.chosen ? .isSelected : [])
    }
}

/// `.qrow`: "14 things going on", with an arrow at its right end. Raised; on Locked, its dark form. Opens the board.
private struct BoardPill: View {
    let title: String
    let night: Bool
    let action: () -> Void
    @State private var tick = 0

    var body: some View {
        Button {
            tick += 1
            action()
        } label: {
            Text(title)
                .textStyle(.sans(16, 500))
                .foregroundStyle(night ? Palette.nightText : Palette.ink)
                .lineLimit(1)
                .contentTransition(.opacity)
                .designFrame(width: 342, height: 58)
                // The pill opens the board: the settings rows' arrow at its right end, in its own text colour.
                .overlay(alignment: .trailing) {
                    ChevronIcon()
                        .rotationEffect(.degrees(-90))      // it points up: the board rises from the pill
                        .foregroundStyle((night ? Palette.nightText : Palette.ink).opacity(0.5))
                        .designPadding(.trailing, 24)
                        .accessibilityHidden(true)
                }
                .background {
                    ZStack {
                        DepthBox(.pill, radius: 29).opacity(night ? 0 : 1)
                        DepthBox(.nightRaised, radius: 29).opacity(night ? 1 : 0)
                    }
                }
        }
        .buttonStyle(PlainPress())
        .sensoryFeedback(.selection, trigger: tick)
        .accessibilityHint("Opens the board.")
    }
}
