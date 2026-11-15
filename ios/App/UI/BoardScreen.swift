import SwiftUI

/// The board, as its own screen (HOMES-QUIET.md; the mock's `.qb`): one tap from The day and
/// Locked, it slides up from the bottom to cover the screen. "Going on now" in the serif, top
/// left, with a round X opposite to close it; the posts as rows, scrolling, fading at the list's top and
/// bottom edges; your own post says "Yours · place" and "Take down"; the post field is pinned
/// at the bottom and rides the keyboard while it is up.
struct BoardScreen: View {
    @Environment(AppModel.self) private var model
    let board: BoardScene
    let onClose: () -> Void

    @State private var position = ScrollPosition(edge: .top)
    @State private var draft = ""
    @State private var pendingText: String?
    @FocusState private var composing: Bool

    var body: some View {
        Stage(surface: Palette.board) {
            StageReader { s, keyboard in content(s, keyboard) }
        }
        .task {
            if let typed = DebugLaunch.text { draft = typed }
            if DebugLaunch.focus == "composer" {
                try? await Task.sleep(for: .seconds(0.8))
                composing = true
            }
        }
    }

    private func content(_ s: CGFloat, _ keyboard: CGFloat) -> some View {
        let up = keyboard >= KeyboardUp.minimum
        let fieldBottom: CGFloat = up ? keyboard / s + 16 : 30
        return ZStack(alignment: .topLeading) {
            header(s)
            list(s, footRoom: up ? fieldBottom + 58 + 16 : 104)

            if board.canPost {
                composer(s)
                    .pinned(bottom: fieldBottom, x: 20, width: 350)
                if let notice = model.notice {
                    Text(notice)
                        .textStyle(.sans(13, line: 18))
                        .foregroundStyle(Palette.nightMuted)
                        .designFrame(width: 338, alignment: .leading)
                        .pinned(bottom: fieldBottom + 66, x: 26, width: 338)
                        .transition(.opacity)
                }
            }
        }
    }

    // MARK: Parts

    /// `.qb .s9head`: the title, and the round X that closes the board.
    private func header(_ s: CGFloat) -> some View {
        // A line height tighter than the font's own draws the glyphs moved up by half the
        // difference (TextStyle), so the title is moved by that much to sit level with the X.
        let font = QHFont.ui(.serif, size: 38 * s)
        let lift = min(0, (42 * s - (font.ascender - font.descender)) / 2)
        return HStack(alignment: .center, spacing: 0) {
            Text("Going on now")
                .textStyle(.serif(38, line: 42))
                .foregroundStyle(Palette.nightText)
                .lineLimit(1)
                .offset(y: lift)
            Spacer(minLength: 0)
            // `.qb .s9x`: a round X, 42, level with the title; its right edge at 24 like the gear's.
            RoundIconButton(night: true, size: 42, label: "Close the board", action: close) {
                StrokeIcon(shape: CloseIcon(), size: 17, lineWidth: 1.9)
            }
            .designPadding(.trailing, -2)
        }
        .designPadding(.top, 70)
        .designPadding(.horizontal, 26)
        .designFrame(width: 390, alignment: .topLeading)
    }

    /// `.qb .board9.open .s9list`: from 128 to 104 above the bottom (or to just over the post
    /// field while the keyboard is up), fading over 26 points at the top and 30 at the bottom.
    private func list(_ s: CGFloat, footRoom: CGFloat) -> some View {
        let height = max(0, Design.height - 128 - footRoom)
        return ScrollView(.vertical) {
            VStack(spacing: 0) {
                ForEach(board.posts) { row in
                    PostRowView(row: row) { takeDown(row.post) }
                        .transition(.opacity)
                }
            }
            .designPadding(.top, 14)
            .designPadding(.bottom, 22)
            // A fixed width, so rows arriving into an empty list fade in where they stand.
            .designFrame(width: 390, alignment: .top)
        }
        .scrollPosition($position)
        .scrollIndicators(.hidden)
        .designFrame(width: 390, height: height, alignment: .top)
        .clipped()
        .mask {
            VStack(spacing: 0) {
                LinearGradient(colors: [.clear, .black], startPoint: .top, endPoint: .bottom).designFrame(height: 26)
                Rectangle().fill(.black)
                LinearGradient(colors: [.black, .clear], startPoint: .top, endPoint: .bottom).designFrame(height: 30)
            }
        }
        .at(y: 128)
        .animation(.easeInOut(duration: 0.26), value: board.posts.map(\.id))
    }

    private func close() {
        composing = false
        onClose()
    }

    /// Your own post leaves; the rest close the gap.
    private func takeDown(_ post: BoardPost) {
        Task {
            if let problem = await model.takeDown(post) {
                model.say(problem)
                return
            }
            model.forget(post)
        }
    }

    // MARK: The post field

    /// `.nt9 .cmp9`: "What you're doing, and where". A post is a line and a place: what is
    /// typed is split on the last comma or " at "; with neither, the field asks "Where?" next.
    private func composer(_ s: CGFloat) -> some View {
        HStack(spacing: 0) {
            TextField("", text: $draft, prompt: Text(pendingText == nil ? "What you're doing, and where" : "Where?")
                .foregroundStyle(Palette.nightComposerText))
                .textStyle(.sans(15))
                .foregroundStyle(Palette.nightText)
                .tint(Palette.nightText)
                .focused($composing)
                .submitLabel(.send)
                .onSubmit { send() }
            Button { send() } label: {
                StrokeIcon(shape: ArrowUpIcon(), size: 18, lineWidth: 2.2)
                    .foregroundStyle(Palette.ink)
                    .designFrame(width: 38, height: 38)
                    .background(Circle().fill(Palette.nightText))
            }
            .buttonStyle(PlainPress())
            .accessibilityLabel("Post")
        }
        .designPadding(.leading, 22)
        .designPadding(.trailing, 10)
        .designFrame(width: 350, height: 58)
        .background { DepthBox(.nightComposer, radius: 29) }
        .contentShape(Rectangle())
        .onTapGesture { composing = true }
    }

    private func send() {
        let typed = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !typed.isEmpty else {
            composing = true
            return
        }
        let text: String, place: String
        if let first = pendingText {
            text = first
            place = typed
        } else if let split = Self.split(typed) {
            (text, place) = split
        } else {
            pendingText = typed
            draft = ""
            composing = true
            return
        }
        Task {
            if let problem = await model.post(text: text, place: place) {
                model.say(problem)
            } else {
                draft = ""
                pendingText = nil
                composing = false
                position.scrollTo(edge: .top)
            }
        }
    }

    /// "Guitar on the lawn, McCarthy Quad" -> ("Guitar on the lawn", "McCarthy Quad").
    static func split(_ typed: String) -> (String, String)? {
        let comma = typed.range(of: ",", options: .backwards)
        let at = typed.range(of: " at ", options: [.backwards, .caseInsensitive])
        let cut: Range<String.Index>?
        switch (comma, at) {
        case let (c?, a?): cut = c.lowerBound > a.lowerBound ? c : a
        case let (c?, nil): cut = c
        case let (nil, a?): cut = a
        default: cut = nil
        }
        guard let cut else { return nil }
        let text = typed[..<cut.lowerBound].trimmingCharacters(in: .whitespaces)
        let place = typed[cut.upperBound...].trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !place.isEmpty else { return nil }
        return (text, place)
    }
}

/// `.r9` on the board: what, where, and how long ago (or "Take down" on your own).
private struct PostRowView: View {
    @Environment(\.stageScale) private var s
    let row: PostRow
    let onTakeDown: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 14 * s) {
                VStack(alignment: .leading, spacing: 0) {
                    Text(row.text)
                        .textStyle(.sans(16, 500, line: 22))
                        .foregroundStyle(Palette.nightText)
                        .lineLimit(1)
                        .truncationMode(.tail)
                    Text(row.place)
                        .textStyle(.sans(14, line: 20))
                        .foregroundStyle(Palette.nightMuted)
                        .lineLimit(1)
                        .truncationMode(.tail)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if row.mine {
                    Button(action: onTakeDown) {
                        UnderlinedText(text: "Take down", style: .sans(14), color: Palette.nightText,
                                       lineColor: Color(hex: 0xEAE5DE, alpha: 0.4))
                            .fixedSize()
                            .designPadding(.vertical, 8)
                    }
                    .buttonStyle(PlainPress())
                } else {
                    Text(row.age)
                        .textStyle(.sans(13))
                        .foregroundStyle(Palette.nightMuted)
                        .fixedSize()
                }
            }
            .designFrame(height: 66)
            Rectangle()
                .fill(Color.white(0.07))
                .designFrame(height: 1)
        }
        .designFrame(width: 338)
        .designPadding(.horizontal, 26)
    }
}
