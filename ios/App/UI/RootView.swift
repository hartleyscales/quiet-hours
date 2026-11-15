import SwiftUI

/// The app's root: decides which designed screen shows from the server's state, keeps polling
/// while the app is in front, and moves from one screen to the next.
///
/// Screens are layers. Between Homes there is one layer, a `HomeView` that moves its own parts.
/// For the choreographed seams (Seams.swift) the outgoing layer stays on stage, told it is
/// leaving, while the incoming one arrives; travelling dots are drawn between them; when the
/// seam is over the outgoing layer goes and the incoming one is simply present. Anything else,
/// and any change that arrives while a seam is running, is a cross-fade of whole layers.
struct RootView: View {
    @State private var model = AppModel()
    @State private var settingsOpen = false
    @State private var boardOpen = false
    @State private var pickerShown = false
    @State private var layers: [ScreenLayer] = []
    @State private var nextID = 0
    @State private var seamTask: Task<Void, Never>?
    @State private var fadeDuration: TimeInterval = 0.25
    @State private var overlay = DotOverlay()
    @State private var intro = DotMorph()
    @State private var surface = Palette.surface
    /// The last Home the model described, and the one before it, for a Home on its way out.
    @State private var lastHome: HomeScene?
    @State private var previousHome: HomeScene?
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    struct ScreenLayer: Identifiable {
        let id: Int
        var screen: Screen
        var role: SeamRole
        /// A Home that is leaving keeps showing what it showed.
        var frozen: HomeScene?
    }

    var body: some View {
        #if DEBUG
        if let name = DebugLaunch.fixture, HomeFixtures.scene(name) != nil {
            FixtureStage(name: name)
                .environment(model)
        } else {
            app
        }
        #else
        app
        #endif
    }

    private var app: some View {
        let live = model.homeScene(for: model.screen)
        let settings = { open(settings: true) }
        let actions = model.homeActions(openSettings: settings, openBoard: { open(board: true) })
        return ZStack {
            surface.ignoresSafeArea()
            ForEach(layers) { layer in
                content(layer, live: live, actions: actions, settings: settings)
                    .environment(\.seamRole, layer.role)
                    .environment(\.dotsInFlight, overlay.isRunning)
                    .environment(\.stageSurfaceHidden, true)
                    .modifier(LayerFade(role: layer.role, duration: fadeDuration))
                    .allowsHitTesting(!isLeaving(layer.role))
                    .zIndex(isLeaving(layer.role) ? 0 : 2)
            }
            Stage(surface: .clear) {
                DotOverlayView(overlay: overlay)
            }
            .environment(\.stageSurfaceHidden, true)
            .allowsHitTesting(false)
            .zIndex(1)

            // The board, its own screen, slides up over The day and Locked.
            if boardOpen {
                BoardScreen(board: model.boardScene) { open(board: false) }
                    .transition(reduceMotion ? .opacity : .move(edge: .bottom))
                    .zIndex(3)
            }

            SettingsOverlay(
                isOpen: $settingsOpen, scene: model.settingsScene,
                onWeek: { action in
                    open(settings: false)
                    model.act(action)
                },
                onPicker: { pickerShown = true },
                onHowItWorks: {
                    open(settings: false)
                    model.replayIntro()
                },
                onSignOut: {
                    open(settings: false)
                    Task { await model.signOut() }
                })
                .zIndex(4)
        }
        .environment(model)
        .preferredColorScheme(isNight(layers.last?.screen ?? model.screen) || boardOpen ? .dark : .light)
        // "What stays open": Apple's picker, through the lock engine (nothing in the front build).
        .quietHoursAppPicker(isPresented: $pickerShown)
        .task { await model.run() }
        .onAppear {
            guard layers.isEmpty else { return }
            layers = [ScreenLayer(id: nextID, screen: model.screen, role: .present)]
            nextID += 1
            surface = surfaceColor(model.screen)
            lastHome = live
        }
        .onChange(of: live) { old, new in
            if let old { previousHome = old }
            if let new { lastHome = new }
        }
        .onChange(of: model.screen) { _, new in change(to: new) }
        .onChange(of: live?.pill?.key) { _, key in
            // The board is one tap from The day and Locked only; anywhere else it goes.
            if boardOpen && key != "board" { open(board: false) }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await model.becameActive() } }
        }
        .task {
            if DebugLaunch.boardOpen {
                try? await Task.sleep(for: .seconds(2))
                if model.homeScene(for: model.screen)?.pill?.key == "board" { open(board: true) }
            }
            if DebugLaunch.settings {
                try? await Task.sleep(for: .seconds(2))
                open(settings: true)
            }
        }
        .onChange(of: model.isSignedIn) { _, signedIn in
            if !signedIn { settingsOpen = false }
        }
    }

    /// The board and the settings sheet travel on the mock's curve (`cubic-bezier(.2,.8,.2,1)`,
    /// 500 ms); with Reduce Motion they cross-fade in 200 ms.
    private func open(board: Bool? = nil, settings: Bool? = nil) {
        withAnimation(reduceMotion ? .easeInOut(duration: 0.2) : .travel(0.5)) {
            if let board { boardOpen = board }
            if let settings { settingsOpen = settings }
        }
    }

    // MARK: One screen

    @ViewBuilder
    private func content(_ layer: ScreenLayer, live: HomeScene?, actions: HomeActions, settings: @escaping () -> Void) -> some View {
        switch layer.screen {
        case .signIn:
            SignInScreen()
        case .howItWorks:
            HowItWorksScreen(morph: intro)
        case .allowLock:
            AllowLockScreen()
        case .loading:
            QuietLineScreen(showsBar: false, onSettings: settings)
        case .noWeek:
            QuietLineScreen(showsBar: true, onSettings: settings)
        case .question:
            QuestionScreen()
        case .voting, .selected, .day, .locked, .summaryBefore, .summary:
            if let scene = layer.frozen ?? (layer.role == .present || isEntering(layer.role) ? live : nil) ?? lastHome {
                HomeView(scene: scene, actions: actions)
            }
        }
    }

    // MARK: Changes of screen

    private func change(to new: Screen) {
        guard let index = layers.lastIndex(where: { !isLeaving($0.role) }) else {
            layers = [ScreenLayer(id: nextID, screen: new, role: .present)]
            nextID += 1
            return
        }
        let from = layers[index].screen
        guard from != new else { return }

        if seamTask != nil || reduceMotion {
            crossFade(to: new, duration: reduceMotion ? 0.2 : 0.25)
            return
        }
        if isHome(from) && isHome(new) {
            // One HomeView: it moves its own parts (HOMES-QUIET.md, "Motion").
            let slow = isNight(from) != isNight(new)
            withAnimation(.easeInOut(duration: slow ? 0.9 : 0.25)) { surface = surfaceColor(new) }
            layers[index].screen = new
            return
        }
        let seam = seam(from: from, to: new)
        if seam == .fade {
            crossFade(to: new, duration: 0.25)
        } else {
            start(seam, at: index, to: new)
        }
    }

    private func start(_ seam: Seam, at index: Int, to new: Screen) {
        let from = layers[index]
        if new == .howItWorks { intro.reset() }
        startDots(seam, from: from, to: new)
        if isHome(from.screen) { layers[index].frozen = scene(showing: from.screen) }
        layers[index].role = .leaving(seam)
        layers.append(ScreenLayer(id: nextID, screen: new, role: .entering(seam)))
        nextID += 1
        let target = surfaceColor(new)
        if seam == .lockedToQuestion {
            withAnimation(.easeInOut(duration: 0.7)) { surface = target }
        } else {
            surface = target
        }
        seamTask = Task { @MainActor in
            try? await Task.sleep(for: .seconds(seam.duration))
            guard !Task.isCancelled else { return }
            finishSeam()
        }
    }

    /// The seam is over: the outgoing screen goes, the dots land, the incoming screen is present.
    private func finishSeam() {
        var t = Transaction()
        t.disablesAnimations = true
        withTransaction(t) {
            layers.removeAll { isLeaving($0.role) }
            for i in layers.indices { layers[i].role = .present }
            overlay.clear()
        }
        seamTask = nil
    }

    /// Every layer on stage fades out from wherever it is; the new screen fades in, laid out at
    /// rest from its first frame (it is inserted without animation; only its opacity moves).
    private func crossFade(to new: Screen, duration: TimeInterval) {
        seamTask?.cancel()
        overlay.fadeAway(duration)
        if new == .howItWorks { intro.reset() }
        var t = Transaction()
        t.disablesAnimations = true
        withTransaction(t) {
            for i in layers.indices {
                if isHome(layers[i].screen) && layers[i].frozen == nil { layers[i].frozen = scene(showing: layers[i].screen) }
                layers[i].role = .leaving(.fade)
            }
            layers.append(ScreenLayer(id: nextID, screen: new, role: .entering(.fade)))
        }
        nextID += 1
        fadeDuration = duration
        withAnimation(.easeInOut(duration: duration)) { surface = surfaceColor(new) }
        seamTask = Task { @MainActor in
            try? await Task.sleep(for: .seconds(duration))
            guard !Task.isCancelled else { return }
            finishSeam()
        }
    }

    private func startDots(_ seam: Seam, from layer: ScreenLayer, to new: Screen) {
        switch seam {
        case .howToLock:
            overlay.morph(from: intro.picture(at: Date()), to: DotPicture(points: DotArt.phoneDots, colors: nil), duration: 1.1)
        case .howToSignIn:
            let moon = LightMoon.shared
            overlay.morph(from: intro.picture(at: Date()), to: DotPicture(points: moon.points, colors: moon.colors), duration: 0.9)
        case .lockToHome:
            // The phone's dots re-form into the Home's picture. A pale picture (opted out) is
            // not drawn by them: they drift apart and fade instead.
            let phone = DotPicture(points: DotArt.phoneDots, colors: nil)
            if let scene = model.homeScene(for: new), !scene.out {
                overlay.morph(from: phone, to: scene.picture.stageDots, duration: 1.1)
            } else {
                overlay.scatter(phone, duration: 0.75)
            }
        case .lockedToQuestion:
            // The moon's own dots re-form into the speech bubble, light to ink. A pale moon
            // (opted out) has no dots of its own to give: the bubble fades in instead.
            if let scene = layer.frozen ?? lastHome, case .night(let count) = scene.picture, !scene.out {
                let moon = LockedMoonView.picture(count, top: 192)
                overlay.morph(from: moon, to: DotPicture(points: DotArt.bubbleDots, colors: nil), duration: 1.1)
            }
        case .questionToSummary:
            // The question's bubble settles into the Summary's, smaller and higher.
            overlay.morph(from: DotPicture(points: DotArt.bubbleDots, colors: nil), to: HomePicture.bubble.stageDots, duration: 1.1)
        case .fade, .signInToHow:
            break
        }
    }

    private func seam(from: Screen, to: Screen) -> Seam {
        switch (from, to) {
        case (.signIn, .howItWorks): return .signInToHow
        case (.howItWorks, .signIn): return .howToSignIn
        case (.howItWorks, .allowLock): return .howToLock
        case (.allowLock, .voting), (.allowLock, .selected), (.allowLock, .day), (.allowLock, .summary), (.allowLock, .summaryBefore):
            return .lockToHome
        case (.locked, .question): return .lockedToQuestion
        case (.question, .summary), (.question, .summaryBefore): return .questionToSummary
        default: return .fade
        }
    }

    // MARK: Helpers

    /// What a Home on `screen` was showing: the latest scene of that kind the model described.
    private func scene(showing screen: Screen) -> HomeScene? {
        for candidate in [lastHome, previousHome] {
            if let candidate, matches(candidate, screen) { return candidate }
        }
        return lastHome
    }

    private func matches(_ scene: HomeScene, _ screen: Screen) -> Bool {
        switch screen {
        case .voting(let out): return scene.kind == .vote && scene.out == out
        case .selected(let out): return scene.kind == .decided && scene.out == out
        case .day(let out): return scene.kind == .day && scene.out == out
        case .locked(let out): return scene.kind == .locked && scene.out == out
        case .summaryBefore: return scene.kind == .summaryBefore
        case .summary: return scene.kind == .summary
        default: return false
        }
    }

    private func isHome(_ screen: Screen) -> Bool {
        switch screen {
        case .voting, .selected, .day, .locked, .summaryBefore, .summary: return true
        default: return false
        }
    }

    private func isNight(_ screen: Screen) -> Bool {
        if case .locked = screen { return true }
        return false
    }

    private func surfaceColor(_ screen: Screen) -> Color { isNight(screen) ? Palette.night : Palette.surface }

    private func isLeaving(_ role: SeamRole) -> Bool {
        if case .leaving = role { return true }
        return false
    }

    private func isEntering(_ role: SeamRole) -> Bool {
        if case .entering = role { return true }
        return false
    }
}

/// A whole screen fading in or out (`Seam.fade`).
private struct LayerFade: ViewModifier {
    let role: SeamRole
    let duration: TimeInterval
    @State private var shown: Bool?

    func body(content: Content) -> some View {
        content
            .opacity((shown ?? (role != .entering(.fade))) ? 1 : 0)
            .onAppear {
                guard shown == nil else { return }
                if role == .entering(.fade) {
                    shown = false
                    withAnimation(.easeInOut(duration: duration)) { shown = true }
                } else {
                    shown = true
                }
            }
            .onChange(of: role) { _, new in
                if new == .leaving(.fade) { withAnimation(.easeInOut(duration: duration)) { shown = false } }
            }
    }
}

#if DEBUG
/// `-QHDebugFixture`: one Home with the mock's sample values, with the board and the settings
/// sheet over it as in the app. Pressing things moves between fixtures (a vote, opting out and
/// back in, leaving and joining), so each change of Home can be watched without a server.
private struct FixtureStage: View {
    @State var name: String
    @State private var chosen = 0
    @State private var boardOpen = false
    @State private var settingsOpen = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let scene = HomeFixtures.scene(name, chosen: chosen) ?? HomeFixtures.scene("decided")!
        let actions = HomeActions(
            openSettings: { open(settings: true) },
            openBoard: { open(board: true) },
            optBackIn: { name = HomeFixtures.after(.optBackIn, from: name) },
            join: { name = "locked" },
            vote: { id in
                chosen = Int(id.dropFirst(2)) ?? 0
                name = "voted"
            })
        ZStack {
            (scene.night ? Palette.night : Palette.surface)
                .ignoresSafeArea()
                .animation(.easeInOut(duration: reduceMotion ? 0.2 : 0.9), value: scene.night)
            HomeView(scene: scene, actions: actions)
                .environment(\.stageSurfaceHidden, true)
            if boardOpen {
                BoardScreen(board: HomeFixtures.board) { open(board: false) }
                    .transition(reduceMotion ? .opacity : .move(edge: .bottom))
                    .zIndex(3)
            }
            SettingsOverlay(
                isOpen: $settingsOpen, scene: HomeFixtures.settings(name), showsDebug: false,
                onWeek: { action in
                    open(settings: false)
                    name = HomeFixtures.after(action, from: name)
                },
                onPicker: {},
                onHowItWorks: { open(settings: false) },
                onSignOut: { open(settings: false) })
                .zIndex(4)
        }
        .preferredColorScheme(scene.night || boardOpen ? .dark : .light)
        .task {
            if DebugLaunch.boardOpen {
                try? await Task.sleep(for: .seconds(1))
                open(board: true)
            }
            if DebugLaunch.settings {
                try? await Task.sleep(for: .seconds(1))
                open(settings: true)
            }
            if let then = DebugLaunch.fixtureThen, HomeFixtures.scene(then) != nil {
                try? await Task.sleep(for: .seconds(2.5))
                if then == "voted" { chosen = 0 }
                name = then
            }
        }
    }

    private func open(board: Bool? = nil, settings: Bool? = nil) {
        withAnimation(reduceMotion ? .easeInOut(duration: 0.2) : .travel(0.5)) {
            if let board { boardOpen = board }
            if let settings { settingsOpen = settings }
        }
    }
}
#endif
