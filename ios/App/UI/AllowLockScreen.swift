import SwiftUI

/// 3 · The lock: "Allow the lock" asks for the engine's authorization and for notifications,
/// then, where the engine uses Apple's picker, shows it so the person chooses what stays open.
struct AllowLockScreen: View {
    @Environment(AppModel.self) private var model
    @Environment(\.seamRole) private var role
    @State private var showingPicker = false
    @State private var working = false
    @State private var pickerShown = false

    var body: some View {
        Stage(surface: Palette.surface) {
            ZStack(alignment: .topLeading) {
                InkDots(points: DotArt.phoneDots)
                    .designFrame(width: 390, height: 460)
                    .hiddenWhileDots(entering: [.howToLock], leaving: [.lockToHome])

                Text("Everything locks.")
                    .textStyle(.serif(50, line: 54))
                    .foregroundStyle(Palette.ink)
                    .arrives(.howToLock, delay: 0.12)
                    .leaves(.lockToHome)
                    .centred(y: 404, padding: 28)

                Text("Except the apps you keep open.")
                    .textStyle(.sans(18, 300, line: 26))
                    .foregroundStyle(Palette.muted)
                    .arrives(.howToLock, delay: 0.16)
                    .leaves(.lockToHome)
                    .centred(y: 470, padding: 44)

                VStack(spacing: 0) {
                    GoButton(title: "Allow the lock", enabled: !working) { allow() }
                        // From How it works, that screen's button body travels here; this one
                        // brings only its label, and takes over the body when the seam ends.
                        .environment(\.goChromeOpacity, role.isEntering(.howToLock) ? 0 : 1)
                        .modifier(LabelIn(seam: .howToLock))
                        .glides(.howToLock, fromScale: 1, fromY: SeamGeometry.howGoY - SeamGeometry.lockGoY)
                        .leaves(.lockToHome, sink: 6)
                    NoticeOr(text: "Apple will ask you to confirm, then show your apps.")
                        .designPadding(.top, 12 + 4)
                        .arrives(.howToLock, delay: 0.18)
                        .leaves(.lockToHome)
                }
                .pinned(bottom: 34)
            }
        }
        .quietHoursAppPicker(isPresented: $showingPicker)
        .onChange(of: showingPicker) { _, shown in
            if shown { pickerShown = true } else if pickerShown { model.finishOnboarding() }
        }
    }

    private func allow() {
        working = true
        Task {
            defer { working = false }
            guard await model.allowLock() else { return }
            if QuietHoursEngine.shared.state.usesAppPicker {
                showingPicker = true
            } else {
                model.finishOnboarding()
            }
        }
    }
}

/// A button's new label fading in over another button's body (from a quarter of the way in).
struct LabelIn: ViewModifier {
    @Environment(\.seamRole) private var role
    let seam: Seam
    @State private var shown: Bool?

    func body(content: Content) -> some View {
        content
            .environment(\.goLabelOpacity, (shown ?? !role.isEntering(seam)) ? 1 : 0)
            .onAppear {
                guard shown == nil else { return }
                shown = !role.isEntering(seam)
                if role.isEntering(seam) { withAnimation(.cssEase(0.34).delay(0.11)) { shown = true } }
            }
    }
}
