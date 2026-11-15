import SwiftUI

/// Behind the gear (HOMES-QUIET.md, "Settings"; the mock's `.qset`): a sheet, not a screen. It
/// rises from the bottom over whichever Home is showing, and the Home dims behind it under a
/// wash of the screen's own surface colour. Pressing the dimmed area, or dragging the sheet
/// down, closes it. A small grab bar and no title; four rows: this week, what stays open, how it
/// works, the account. In DEBUG builds the debug screen and the demo controls follow, below and
/// visibly apart.
struct SettingsOverlay: View {
    @Binding var isOpen: Bool
    let scene: SettingsScene
    /// The debug screen and the demo controls (DEBUG builds only, and not over a fixture).
    var showsDebug = true
    let onWeek: (WeekRow.Action) -> Void
    let onPicker: () -> Void
    let onHowItWorks: () -> Void
    let onSignOut: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            if isOpen {
                // `.qdim`: the screen's own surface, as a wash.
                (scene.night ? Color(hex: 0x080706, alpha: 0.66) : Color(hex: 0xEAE5DE, alpha: 0.62))
                    .ignoresSafeArea()
                    .contentShape(Rectangle())
                    .onTapGesture { close() }
                    .accessibilityAddTraits(.isButton)
                    .accessibilityLabel("Close settings")
                    .transition(.opacity)
            }
            Stage(surface: .clear) {
                StageReader { s, keyboard in
                    ZStack(alignment: .bottomLeading) {
                        Color.clear
                        if isOpen {
                            SettingsSheetView(scene: scene, showsDebug: showsDebug, keyboard: keyboard / s,
                                              close: close, onWeek: onWeek, onPicker: onPicker,
                                              onHowItWorks: onHowItWorks, onSignOut: onSignOut)
                                .transition(reduceMotion ? .opacity : .move(edge: .bottom))
                        }
                    }
                    .frame(width: Design.width * s, height: Design.height * s)
                }
            }
            .environment(\.stageSurfaceHidden, true)
            .allowsHitTesting(isOpen)
        }
    }

    private func close() {
        withAnimation(reduceMotion ? .easeInOut(duration: 0.2) : .travel(0.5)) { isOpen = false }
    }
}

/// `.qset`: the sheet itself.
private struct SettingsSheetView: View {
    @Environment(\.stageScale) private var s
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let scene: SettingsScene
    let showsDebug: Bool
    /// The keyboard's height in design points (the debug build's admin secret field).
    let keyboard: CGFloat
    let close: () -> Void
    let onWeek: (WeekRow.Action) -> Void
    let onPicker: () -> Void
    let onHowItWorks: () -> Void
    let onSignOut: () -> Void

    @State private var drag: CGFloat = 0
    private var engine: QuietHoursEngine { QuietHoursEngine.shared }

    private var night: Bool { scene.night }
    private var titleColor: Color { night ? Palette.nightText : Palette.ink }
    private var detailColor: Color { night ? Palette.nightMuted : Palette.muted }
    private var arrowColor: Color { night ? Palette.nightMuted : Palette.placeholder }
    private var lineColor: Color { night ? .white(0.07) : .warm(0.1) }

    var body: some View {
        let debug = hasDebug
        VStack(spacing: 0) {
            // `::before`: the grab bar.
            Capsule()
                .fill(night ? Color(hex: 0xEAE5DE, alpha: 0.2) : Color(hex: 0x1C1A18, alpha: 0.16))
                .designFrame(width: 36, height: 4)
                .designPadding(.top, 10)
                .designPadding(.bottom, 6)

            if let week = scene.week {
                row(week.title, week.detail) { onWeek(week.action) }
            }
            pickerRow
            row("How it works", nil, arrow: true) { onHowItWorks() }
            row("Sign out", scene.email.isEmpty ? nil : scene.email, last: true) { onSignOut() }

            #if DEBUG
            if debug {
                SettingsDebugSection(night: night)
            }
            #endif
        }
        .designPadding(.bottom, 26)
        .designFrame(width: 390)
        .background(alignment: .top) {
            DepthBox(night ? .nightSettings : .settings, top: 38, bottom: 0)
                // Runs on past the stage's foot, in case the screen is taller than 390 x 844.
                .designPadding(.bottom, -200)
        }
        .designPadding(.bottom, keyboard >= KeyboardUp.minimum / s ? keyboard : 0)
        .offset(y: max(0, drag) * s)
        .gesture(dragToClose)
        .animation(.travel(0.35), value: keyboard >= KeyboardUp.minimum / s)
    }

    private var hasDebug: Bool {
        #if DEBUG
        return showsDebug
        #else
        return false
        #endif
    }

    private var dragToClose: some Gesture {
        DragGesture(minimumDistance: 6)
            .onChanged { value in drag = max(0, value.translation.height / s) }
            .onEnded { value in
                let distance = value.translation.height / s, predicted = value.predictedEndTranslation.height / s
                if distance > 90 || predicted > 220 {
                    // It slides on down from where the finger left it.
                    close()
                } else {
                    withAnimation(reduceMotion ? .easeInOut(duration: 0.2) : .travel(0.35)) { drag = 0 }
                }
            }
    }

    // MARK: Rows

    /// "What stays open": Apple's picker through the lock engine where there is one; in the
    /// front build, the row is shown without its arrow and is not pressable.
    @ViewBuilder private var pickerRow: some View {
        let state = engine.state
        if state.usesAppPicker {
            row("What stays open", Self.pickSummary(state), arrow: true) { onPicker() }
        } else {
            row("What stays open", "Chosen in the iPhone app", enabled: false) {}
        }
    }

    /// One line summarising the choice. Apple's picker gives the app tokens only, not names,
    /// so the line counts them: "3 apps, 1 category".
    static func pickSummary(_ state: QuietState) -> String {
        func count(_ n: Int, _ one: String, _ many: String) -> String? { n > 0 ? "\(n) \(n == 1 ? one : many)" : nil }
        let picks = [count(state.selectedApplications, "app", "apps"),
                     count(state.selectedCategories, "category", "categories"),
                     count(state.selectedWebDomains, "site", "sites")].compactMap { $0 }.joined(separator: ", ")
        if picks.isEmpty { return "Nothing chosen yet" }
        // "Lock only what I pick" (a debug setting): the picks are what locks.
        return state.lockScope == .selected ? "Everything except \(picks)" : picks
    }

    /// `.qset button`: 64 high, a line under it (but the last).
    private func row(_ title: String, _ detail: String?, arrow: Bool = false, enabled: Bool = true, last: Bool = false,
                     action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 0) {
                HStack(spacing: 14 * s) {
                    VStack(alignment: .leading, spacing: 0) {
                        Text(title)
                            .textStyle(.sans(16, 500, line: 22))
                            .foregroundStyle(titleColor)
                        if let detail {
                            Text(detail)
                                .textStyle(.sans(14, line: 20))
                                .foregroundStyle(detailColor)
                        }
                    }
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    if arrow {
                        ChevronIcon().foregroundStyle(arrowColor)
                    }
                }
                .designFrame(height: last ? 64 : 63)
                if !last {
                    Rectangle().fill(lineColor).designFrame(height: 1)
                }
            }
            .designFrame(width: 338)
            .contentShape(Rectangle())
        }
        .buttonStyle(PlainPress())
        .disabled(!enabled)
        .accessibilityElement(children: .combine)
    }
}

#if DEBUG
/// DEBUG builds only, below the four rows: the lock engine's debug screen, and the demo
/// controls that move the week through its phases on the server. Never in a release build.
private struct SettingsDebugSection: View {
    @Environment(AppModel.self) private var model
    @Environment(\.stageScale) private var s
    let night: Bool

    @State private var secret = ""
    @State private var demoLine = ""
    @State private var working = false
    @State private var showingDebug = false

    private var ink: Color { night ? Palette.nightText : Palette.ink }
    private var muted: Color { night ? Palette.nightMuted : Palette.muted }

    var body: some View {
        VStack(alignment: .leading, spacing: 10 * s) {
            Text("Debug build only")
                .textStyle(.sans(13))
                .foregroundStyle(muted)
            HStack(spacing: 8 * s) {
                chip("Lock engine") { showingDebug = true }
                if model.adminSecret != nil {
                    chip("Forget admin secret") { model.setAdminSecret(nil) }
                }
            }
            if model.adminSecret == nil {
                HStack(spacing: 8 * s) {
                    SecureField("Admin secret", text: $secret)
                        .textStyle(.sans(15))
                        .foregroundStyle(ink)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .designPadding(.horizontal, 14)
                        .designFrame(height: 40)
                        .background(Capsule().strokeBorder(muted.opacity(0.5), lineWidth: 1))
                    chip("Keep") {
                        model.setAdminSecret(secret)
                        secret = ""
                    }
                }
            } else {
                let steps: [(String, String)] = [("Voting", "vote"), ("Decided", "decided"), ("On the day", "day"),
                                                 ("Live", "live"), ("Ended", "ended"), ("Told", "told")]
                VStack(alignment: .leading, spacing: 8 * s) {
                    HStack(spacing: 8 * s) { ForEach(steps.prefix(3), id: \.1) { step($0.0, $0.1) } }
                    HStack(spacing: 8 * s) { ForEach(steps.suffix(3), id: \.1) { step($0.0, $0.1) } }
                }
                if !demoLine.isEmpty {
                    Text(demoLine)
                        .textStyle(.sans(13))
                        .foregroundStyle(muted)
                        .lineLimit(2)
                }
            }
        }
        .designPadding(.top, 16)
        .designPadding(.horizontal, 26)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay(alignment: .top) {
            // Apart from the four rows: a full-width hairline over the debug part.
            Rectangle().fill(night ? Color.white(0.12) : Color.warm(0.18)).designFrame(height: 1)
        }
        .designPadding(.top, 12)
        .sheet(isPresented: $showingDebug) {
            NavigationStack {
                DebugView()
                    .toolbar {
                        ToolbarItem(placement: .topBarTrailing) {
                            Button("Done") { showingDebug = false }
                        }
                    }
            }
        }
    }

    private func step(_ title: String, _ step: String) -> some View {
        chip(title) {
            working = true
            Task {
                demoLine = await model.demoJump(step)
                working = false
            }
        }
        .disabled(working)
    }

    private func chip(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .textStyle(.sans(14))
                .foregroundStyle(ink)
                .lineLimit(1)
                .fixedSize()
                .designPadding(.horizontal, 14)
                .designFrame(height: 40)
                .background(Capsule().strokeBorder(muted.opacity(0.5), lineWidth: 1))
        }
        .buttonStyle(PlainPress())
    }
}
#endif

/// Loading, unreachable, or no week yet: one quiet line of text in the existing style.
struct QuietLineScreen: View {
    @Environment(AppModel.self) private var model
    let showsBar: Bool
    let onSettings: () -> Void

    var body: some View {
        Stage(surface: Palette.surface) {
            ZStack(alignment: .topLeading) {
                if showsBar { TopBar(onSettings: onSettings) }
                Text(line)
                    .textStyle(.sans(15))
                    .foregroundStyle(Palette.muted)
                    .centred(y: 410, padding: 44)
            }
        }
    }

    private var line: String {
        if let notice = model.notice { return notice }
        if !showsBar || model.state == nil { return "Loading this week." }
        if let opens = model.state?.upcomingVoteOpensAt {
            return "Voting opens \(TimeText.weekday(opens)) at \(TimeText.clockWithPeriod(opens))."
        }
        return "No week yet."
    }
}
