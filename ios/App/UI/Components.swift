import SwiftUI

// Pieces several screens share, each one a rule from the mock's CSS.

/// A button style that draws the label as it is: the mock gives presses no extra look.
struct PlainPress: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.contentShape(Rectangle())
    }
}

/// `.go`, `.qgo`: the one dark button (or, on the dark Locked screen, `.golight`, the one
/// light one). 342 wide.
struct GoButton: View {
    /// For a seam where one button's body stands in for another's: the label and the body
    /// (fill and shadow), separately.
    @Environment(\.goLabelOpacity) private var labelSeam
    @Environment(\.goChromeOpacity) private var chromeSeam
    let title: String
    var night = false
    var enabled = true
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .textStyle(.sans(17, 500))
                .foregroundStyle(night ? Palette.ink : Palette.buttonText)
                .lineLimit(1)
                .contentTransition(.opacity)
                .opacity(labelSeam)
                .designFrame(width: 342, height: 58)
                .background { DepthBox(night ? .nightButton : .button, radius: 29).opacity(chromeSeam) }
        }
        .buttonStyle(PlainPress())
        .disabled(!enabled)
    }
}

/// `.fine`: the small line under a form or at the foot of a screen.
struct FineLine: View {
    let text: String
    var color: Color = Palette.fine

    var body: some View {
        Text(text)
            .textStyle(.sans(13))
            .foregroundStyle(color)
            .multilineTextAlignment(.center)
    }
}

/// Text underlined `offset` design points below the baseline, as `text-underline-offset`.
struct UnderlinedText: View {
    @Environment(\.stageScale) private var s
    let text: String
    let style: TextStyle
    let color: Color
    let lineColor: Color

    var body: some View {
        let font = QHFont.ui(style.family, size: style.size * s, weight: style.weight)
        let natural = font.ascender - font.descender
        let line = (style.lineHeight ?? natural / s) * s
        let baseline = max(0, (line - natural) / 2) + font.ascender
        Text(text)
            .textStyle(style)
            .foregroundStyle(color)
            .overlay(alignment: .topLeading) {
                Rectangle()
                    .fill(lineColor)
                    .frame(height: max(1, CTFontGetUnderlineThickness(font as CTFont)))
                    .offset(y: baseline + 3 * s)
            }
    }
}

/// A quiet underlined link that takes 30 points of height, as the mock's header buttons do
/// (`.s9head button`: the board's "Close").
struct LinkButton: View {
    let title: String
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            UnderlinedText(text: title, style: .sans(14), color: color, lineColor: color)
                .lineLimit(1)
                .fixedSize()
                .designPadding(.vertical, 6)
        }
        .buttonStyle(PlainPress())
    }
}

/// `.skip`: a quiet underlined text button, 44 high.
struct TextLinkButton: View {
    let title: String
    var color: Color = Palette.muted
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            UnderlinedText(text: title, style: .sans(14), color: color, lineColor: color)
                .lineLimit(1)
                .fixedSize()
                .designPadding(.horizontal, 14)
                .designFrame(height: 44)
        }
        .buttonStyle(PlainPress())
    }
}

/// `.bar`: the name on the left, the settings button on the right (the quiet line screen).
struct TopBar: View {
    let onSettings: () -> Void

    var body: some View {
        HStack(spacing: 0) {
            Text("Quiet Hours")
                .textStyle(.serif(25, line: 25))
                .foregroundStyle(Palette.ink)
            Spacer(minLength: 0)
            GearButton(night: false, action: onSettings)
        }
        .designFrame(width: 342)
        .at(x: 24, y: 52)
    }
}

/// `.gear`: the settings button, 42 round. On the Homes it sits alone, top right.
struct GearButton: View {
    var night = false
    let action: () -> Void

    var body: some View {
        RoundIconButton(night: night, size: 42, label: "Settings", action: action) {
            StrokeIcon(shape: SlidersIcon(), size: 19, lineWidth: 1.8)
        }
    }
}

/// `.gear`: a raised round button with an icon.
struct RoundIconButton<Icon: View>: View {
    var night = false
    let size: CGFloat
    let label: String
    let action: () -> Void
    @ViewBuilder let icon: () -> Icon

    var body: some View {
        Button(action: action) {
            icon()
                .foregroundStyle(night ? Palette.nightText : Palette.ink)
                .designFrame(width: size, height: size)
                .background {
                    ZStack {
                        DepthBox(.raisedRound, radius: size / 2).opacity(night ? 0 : 1)
                        DepthBox(.nightRaised, radius: size / 2).opacity(night ? 1 : 0)
                    }
                }
        }
        .buttonStyle(PlainPress())
        .accessibilityLabel(label)
    }
}

/// `.pips`: where you are in How it works.
struct Pips: View {
    @Environment(\.stageScale) private var s
    let on: Int?

    var body: some View {
        HStack(spacing: 8 * s) {
            ForEach(0..<3, id: \.self) { i in
                ZStack {
                    DepthBox(.pip, radius: 4)
                    Circle().fill(Palette.ink).opacity(i == on ? 1 : 0)
                }
                .designFrame(width: 8, height: 8)
            }
        }
        .animation(.timingCurve(0.25, 0.1, 0.25, 1, duration: 0.3), value: on)
    }
}

/// The quiet line for loading and errors, in the screen's small-line style, or the
/// screen's own line when there is nothing to say.
struct NoticeOr: View {
    @Environment(AppModel.self) private var model
    let text: String
    var color: Color = Palette.fine

    var body: some View {
        FineLine(text: model.notice ?? text, color: color)
    }
}
