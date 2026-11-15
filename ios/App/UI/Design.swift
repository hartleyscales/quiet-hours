import SwiftUI
import UIKit

// The mocks (design/screens.html) are drawn in a 390 x 844 space with absolute positions.
// Every screen is built in that space and scaled as a layout (not a bitmap), so every length
// below is in design points and goes through the stage scale before it reaches SwiftUI.

extension EnvironmentValues {
    /// Device points per design point. Set once by `Stage`.
    @Entry var stageScale: CGFloat = 1
}

enum Design {
    static let width: CGFloat = 390
    static let height: CGFloat = 844
}

// MARK: Colour

extension Color {
    /// `Color(hex: 0xEAE5DE)`, or with an alpha: `Color(hex: 0x1C1A18, alpha: 0.35)`.
    init(hex: UInt32, alpha: Double = 1) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255,
                  opacity: alpha)
    }

    /// The mock's warm shadow colour, rgba(70,52,36,a).
    static func warm(_ alpha: Double) -> Color { Color(.sRGB, red: 70 / 255, green: 52 / 255, blue: 36 / 255, opacity: alpha) }
    static func white(_ alpha: Double) -> Color { Color(.sRGB, red: 1, green: 1, blue: 1, opacity: alpha) }
    static func black(_ alpha: Double) -> Color { Color(.sRGB, red: 0, green: 0, blue: 0, opacity: alpha) }
}

/// The product's own colours, fixed by design (the mock's `.s` rules).
enum Palette {
    static let surface = Color(hex: 0xEAE5DE)
    static let ink = Color(hex: 0x1C1A18)
    static let muted = Color(hex: 0x6A635B)
    static let fine = Color(hex: 0x7A7269)
    static let placeholder = Color(hex: 0x8A8279)
    static let raised = Color(hex: 0xEFEBE5)
    static let well = Color(hex: 0xDED8D0)
    static let buttonText = Color(hex: 0xF3EFE9)
    static let dotInk = Color(hex: 0x3A342E)
    /// Out this week: the statement and the time go pale (`.qout .qbig`).
    static let pale = Color(hex: 0xA9A299)
    /// The Summary's dots (`.qpips i`).
    static let pip = Color(hex: 0xD5CEC5)

    // Locked (near-black).
    static let night = Color(hex: 0x080706)
    static let nightText = Color(hex: 0xEAE5DE)
    static let nightMuted = Color(hex: 0x9B9289)
    static let nightRaised = Color(hex: 0x161412)
    static let nightComposerText = Color(hex: 0x8B837A)
    /// Locked, out: the statement goes dim (`.qout.nt9 .qbig`).
    static let nightPale = Color(hex: 0x6B645C)
    /// The board's own screen (`.qb .board9.open`).
    static let board = Color(hex: 0x0C0B0A)
}

// MARK: Type

/// Outfit for the interface, Instrument Serif italic for the name, headlines and numbers.
/// Uses the bundled fonts when they are registered and falls back to the system font and
/// New York italic otherwise, so nothing depends on them being present.
enum QHFont {
    enum Family: Hashable { case sans, serif }

    static func ui(_ family: Family, size: CGFloat, weight: Int = 400) -> UIFont {
        switch family {
        case .sans:
            let name = weight <= 300 ? "Outfit-Light" : weight >= 500 ? "Outfit-Medium" : "Outfit-Regular"
            if let font = UIFont(name: name, size: size) { return font }
            let fallback: UIFont.Weight = weight <= 300 ? .light : weight >= 500 ? .medium : .regular
            return UIFont.systemFont(ofSize: size, weight: fallback)
        case .serif:
            if let font = UIFont(name: "InstrumentSerif-Italic", size: size) { return font }
            let base = UIFont.systemFont(ofSize: size).fontDescriptor
            let serif = base.withDesign(.serif) ?? base
            let italic = serif.withSymbolicTraits(.traitItalic) ?? serif
            return UIFont(descriptor: italic, size: size)
        }
    }
}

/// One text style from the mock's CSS: family, size, weight and line height, in design points.
struct TextStyle: Hashable {
    var family: QHFont.Family = .sans
    var size: CGFloat
    var weight: Int = 400
    /// CSS line-height in design points; nil is CSS `normal` (the font's own).
    var lineHeight: CGFloat?

    static func sans(_ size: CGFloat, _ weight: Int = 400, line: CGFloat? = nil) -> TextStyle {
        TextStyle(family: .sans, size: size, weight: weight, lineHeight: line)
    }
    static func serif(_ size: CGFloat, line: CGFloat? = nil) -> TextStyle {
        TextStyle(family: .serif, size: size, weight: 400, lineHeight: line)
    }
}

private struct TextStyleModifier: ViewModifier {
    @Environment(\.stageScale) private var s
    let style: TextStyle

    func body(content: Content) -> some View {
        let font = QHFont.ui(style.family, size: style.size * s, weight: style.weight)
        // CSS centres the font's ascent + descent in each line box of `line-height`.
        let natural = font.ascender - font.descender
        let line = (style.lineHeight ?? natural / s) * s
        if line >= natural {
            content
                .font(Font(font))
                .lineSpacing(line - natural)
                .padding(.vertical, (line - natural) / 2)
        } else {
            // Tighter than the font's own: every line box is exactly `line` tall. `.exact` keeps
            // the full ascent above the first baseline; CSS splits the shortfall above and below,
            // so move the glyphs up by half of it (the layout box stays `line` per line).
            content
                .font(Font(font))
                .lineHeight(.exact(points: line))
                .offset(y: (line - natural) / 2)
        }
    }
}

extension View {
    /// Applies a mock text style at the stage scale.
    func textStyle(_ style: TextStyle) -> some View {
        modifier(TextStyleModifier(style: style))
    }
}

/// Line breaks as the mock's browser makes them: each line takes as many words as fit. Text on
/// iOS moves a lone last word down to the line before it (so "41 people called a / parent."
/// becomes "41 people called / a parent."); breaking the lines here first keeps the mock's.
enum GreedyLines {
    /// `text` with a newline wherever a line of `width` design points fills, set in `style` at
    /// the stage scale `s`.
    static func wrap(_ text: String, style: TextStyle, width: CGFloat, scale s: CGFloat) -> String {
        let font = QHFont.ui(style.family, size: style.size * s, weight: style.weight)
        let limit = width * s - 1
        func fits(_ line: String) -> Bool { (line as NSString).size(withAttributes: [.font: font]).width <= limit }
        var lines: [String] = []
        for paragraph in text.components(separatedBy: "\n") {
            var line = ""
            for word in paragraph.split(separator: " ") {
                let longer = line.isEmpty ? String(word) : line + " " + word
                if line.isEmpty || fits(longer) {
                    line = longer
                } else {
                    lines.append(line)
                    line = String(word)
                }
            }
            lines.append(line)
        }
        return lines.joined(separator: "\n")
    }
}

/// Count formatting as the mock shows it: "3,112".
enum Count {
    static func text(_ n: Int) -> String {
        n.formatted(.number.grouping(.automatic).locale(Locale(identifier: "en_US")))
    }
}
