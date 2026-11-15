import SwiftUI

/// 8 · The question, the moment the window ends: one picture, one line to write, one button.
/// While typing (8b) the picture and Skip go, everything rides up and the counter shows.
struct QuestionScreen: View {
    @Environment(AppModel.self) private var model

    @State private var text = ""
    @State private var fieldHeight: CGFloat = 104
    @State private var sending = false
    @FocusState private var typing: Bool

    private static let limit = 200

    var body: some View {
        Stage(surface: Palette.surface) {
            StageReader { s, keyboard in content(s, keyboard) }
        }
        .task {
            if let typed = DebugLaunch.text { text = typed }
            if DebugLaunch.focus == "question" {
                try? await Task.sleep(for: .seconds(1.5))
                typing = true
                if DebugLaunch.blur {
                    try? await Task.sleep(for: .seconds(2.5))
                    typing = false
                }
            }
        }
    }

    private func content(_ s: CGFloat, _ keyboard: CGFloat) -> some View {
        // Laid out from the keyboard alone (not from focus), so everything moves with it.
        let kb = keyboard / s
        let up = keyboard >= KeyboardUp.minimum
        let fieldTop: CGFloat = up ? 196 : 514
        // The counter sits at 332, or 8 under the field once the field grows past it.
        let counterGap = max(8, 332 - 196 - fieldHeight / s)
        return ZStack(alignment: .topLeading) {
            // The picture rides up with the words (382 to 66) and fades out.
            // Positions follow the keyboard through SwiftUI's own keyboard animation; fades are
            // animated here, and nothing fades all the way to 0 so it keeps travelling with the rest.
            // From Locked, the moon's dots re-form into this picture (drawn by the root until
            // they land; with no moon to come from, it fades in). To the summary, they drift away.
            InkDots(points: DotArt.bubbleDots)
                .designFrame(width: 390, height: 460)
                .opacity(up ? 0.001 : 1)
                .animation(.easeOut(duration: 0.25), value: up)
                .hiddenWhileDots(entering: [.lockedToQuestion], leaving: [.questionToSummary])
                .arrives(.lockedToQuestion, delay: 0.5, duration: 0.5)
                .at(y: up ? 66 - 382 : 0)

            Text(headline)
                .textStyle(.sans(15))
                .foregroundStyle(Palette.muted)
                .arrives(.lockedToQuestion, delay: 0.35)
                .leaves(.questionToSummary)
                .centred(y: up ? 66 : 382)

            Text("What did you do?")
                .textStyle(.serif(50, line: 54))
                .foregroundStyle(Palette.ink)
                .arrives(.lockedToQuestion, delay: 0.4)
                .leaves(.questionToSummary)
                .centred(y: up ? 90 : 406, padding: 28)

            Text(model.notice ?? recapLine)
                .textStyle(.sans(18, 300, line: 26))
                .foregroundStyle(Palette.muted)
                .arrives(.lockedToQuestion, delay: 0.45)
                .leaves(.questionToSummary)
                .centred(y: up ? 152 : 468, padding: 44)

            VStack(alignment: .trailing, spacing: counterGap * s) {
                field(up: up, s)
                Text("\(text.count) / \(Self.limit)")
                    .textStyle(.sans(13))
                    .foregroundStyle(Palette.fine)
                    .designPadding(.trailing, 30 - 24)
                    .opacity(up ? 1 : 0.001)
                    .animation(.easeOut(duration: 0.25), value: up)
            }
            .arrives(.lockedToQuestion, delay: 0.45, duration: 0.45)
            .leaves(.questionToSummary)
            .at(x: 24, y: fieldTop)

            VStack(spacing: 2 * s) {
                GoButton(title: "Add it", enabled: !sending) { send() }
                if !up {
                    TextLinkButton(title: "Skip") {
                        typing = false
                        model.skipLine()
                    }
                }
            }
            .arrives(.lockedToQuestion, delay: 0.55, rise: 8)
            .leaves(.questionToSummary, sink: 6)
            .pinned(bottom: up ? kb + 16 : 18)
        }
        .contentShape(Rectangle())
        .onTapGesture { typing = false }
    }

    private func field(up: Bool, _ s: CGFloat) -> some View {
        TextField("", text: $text, axis: .vertical)
            .textStyle(.sans(17, line: 24))
            .foregroundStyle(Palette.ink)
            .tint(Palette.ink)
            .focused($typing)
            .background(alignment: .topLeading) {
                // Drawn as text rather than as the field's prompt, which would cut it to one line.
                if text.isEmpty {
                    Text("It's anonymous. Say what you really did.")
                        .textStyle(.sans(17, line: 24))
                        .foregroundStyle(Palette.placeholder)
                        .fixedSize(horizontal: false, vertical: true)
                        .allowsHitTesting(false)
                }
            }
            .lineLimit(1...9)
            .onChange(of: text) { _, new in
                var clean = new
                if clean.contains("\n") {
                    clean = clean.replacingOccurrences(of: "\n", with: " ")
                    typing = false
                }
                if clean.count > Self.limit { clean = String(clean.prefix(Self.limit)) }
                if clean != new { text = clean }
            }
            .designPadding(.vertical, 16)
            .designPadding(.horizontal, 20)
            .frame(width: 342 * s, alignment: .topLeading)
            // 128 at rest; while typing it grows from 104. Keyed to focus, so the height has
            // settled before the keyboard starts to move.
            .frame(minHeight: (typing ? 104 : 128) * s, alignment: .topLeading)
            .animation(.easeOut(duration: 0.2), value: typing)
            .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { fieldHeight = $0 }
            .background {
                ZStack {
                    DepthBox(.field, radius: 28)
                    DepthBox(.fieldFocused, radius: 28)
                        .opacity(typing ? 1 : 0.001)
                        .animation(.easeOut(duration: 0.2), value: typing)
                }
            }
            .contentShape(Rectangle())
            .onTapGesture { typing = true }
    }

    private var headline: String {
        guard let end = model.state?.week?.endsAt else { return "" }
        let stayed = model.state?.numbers?.stayed?.count ?? 0
        return "It's \(TimeText.clock(end)). \(Count.text(stayed)) \(stayed == 1 ? "Trojan" : "Trojans") stayed to the end."
    }

    private var recapLine: String {
        guard let told = model.state?.week?.toldAt else { return "" }
        // "in 15 minutes": how long, not what time.
        let wait = TimeText.until(told, now: model.now)
        return "It goes into the recap \(wait.prefix(1).lowercased())\(wait.dropFirst())."
    }

    private func send() {
        let line = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !line.isEmpty else {
            typing = true
            return
        }
        sending = true
        Task {
            defer { sending = false }
            if let problem = await model.writeLine(line) {
                model.say(problem)
            } else {
                typing = false
            }
        }
    }
}
