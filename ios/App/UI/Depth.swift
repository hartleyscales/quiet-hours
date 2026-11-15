import SwiftUI

// Soft neumorphism with strict meaning: raised = something you press; pressed-in = a field or
// a readout; pictures are flat. Each style below is one of the mock's CSS box-shadow lists,
// rebuilt as a blurred, offset, inset (negative spread) shape underneath and inner shadows
// on the face.

/// One CSS box-shadow, in design points.
struct BoxShadow: Hashable {
    var x: CGFloat = 0
    var y: CGFloat
    var blur: CGFloat
    var spread: CGFloat = 0
    var color: Color
    var inset = false

    static func == (a: BoxShadow, b: BoxShadow) -> Bool {
        a.x == b.x && a.y == b.y && a.blur == b.blur && a.spread == b.spread && a.inset == b.inset && a.color == b.color
    }
    func hash(into h: inout Hasher) { h.combine(x); h.combine(y); h.combine(blur); h.combine(spread); h.combine(inset) }
}

/// A face colour and its shadows: one look from the mock.
struct Depth {
    var fill: Color
    var shadows: [BoxShadow]

    // Light surface. Raised.
    /// `.gear`
    static let raisedRound = Depth(fill: Palette.raised, shadows: [
        BoxShadow(y: 1, blur: 0, color: .white(0.95), inset: true),
        BoxShadow(y: 8, blur: 12, spread: -6, color: .warm(0.32)),
        BoxShadow(y: 1, blur: 2, color: .warm(0.1)),
    ])
    /// `.qrow`, `.qopt`: a raised pill on a Home.
    static let pill = Depth(fill: Palette.raised, shadows: [
        BoxShadow(y: 1, blur: 0, color: .white(0.9), inset: true),
        BoxShadow(y: 12, blur: 18, spread: -10, color: .warm(0.4)),
        BoxShadow(y: 1, blur: 2, color: .warm(0.12)),
    ])
    /// `.go`, `.qgo`: the one dark button.
    static let button = Depth(fill: Palette.ink, shadows: [
        BoxShadow(y: 1, blur: 0, color: .white(0.16), inset: true),
        BoxShadow(y: 14, blur: 20, spread: -10, color: Color(hex: 0x1C1A18, alpha: 0.5)),
    ])
    /// `.qset`: the settings sheet, light.
    static let settings = Depth(fill: Color(hex: 0xF4F1EC), shadows: [
        BoxShadow(y: 1, blur: 0, color: .white(0.9), inset: true),
        BoxShadow(y: -18, blur: 40, spread: -18, color: .warm(0.38)),
    ])

    // Light surface. Pressed in.
    /// `.rowf`, `.qf`
    static let field = Depth(fill: Palette.well, shadows: [
        BoxShadow(y: 2, blur: 4, color: .warm(0.13), inset: true),
        BoxShadow(y: 1, blur: 0, color: .white(0.7)),
    ])
    /// `.rowf:focus-within`, `.qf.on`
    static let fieldFocused = Depth(fill: Palette.well, shadows: [
        BoxShadow(y: 3, blur: 6, color: .warm(0.18), inset: true),
        BoxShadow(y: 1, blur: 0, color: .white(0.7)),
    ])
    /// `.qopt.on`: the window you voted for, pressed in.
    static let pillChosen = Depth(fill: Color(hex: 0xE2DCD4), shadows: [
        BoxShadow(y: 2, blur: 5, color: .warm(0.18), inset: true),
        BoxShadow(y: 1, blur: 0, color: .white(0.8)),
    ])
    /// `.pips i`
    static let pip = Depth(fill: Palette.well, shadows: [
        BoxShadow(y: 1, blur: 2, color: .warm(0.2), inset: true),
    ])

    // Locked (near-black), and the board.
    /// `.nt.nb .gear`, `.q.nt9 .qrow`
    static let nightRaised = Depth(fill: Palette.nightRaised, shadows: [
        BoxShadow(y: 1, blur: 0, color: .white(0.1), inset: true),
        BoxShadow(y: 12, blur: 16, spread: -9, color: .black),
        BoxShadow(y: 0, blur: 0, spread: 1, color: .white(0.025)),
    ])
    /// `.golight`: the light button on the dark screen.
    static let nightButton = Depth(fill: Palette.nightText, shadows: [
        BoxShadow(y: 1, blur: 0, color: .white(0.6), inset: true),
        BoxShadow(y: 14, blur: 20, spread: -10, color: .black),
    ])
    /// `.nt9 .cmp9`: the post field on the board.
    static let nightComposer = Depth(fill: Color(hex: 0x070605), shadows: [
        BoxShadow(y: 2, blur: 4, color: .black(0.85), inset: true),
        BoxShadow(y: 1, blur: 0, color: .white(0.07)),
    ])
    /// `.nt9 .qset`: the settings sheet over Locked.
    static let nightSettings = Depth(fill: Color(hex: 0x151311), shadows: [
        BoxShadow(y: 1, blur: 0, color: .white(0.1), inset: true),
        BoxShadow(y: -18, blur: 40, spread: -18, color: .black),
    ])
}

/// Draws a `Depth` in a rounded rectangle of `radius` design points, filling its frame.
/// `top`/`bottom` give the top and bottom corners their own radii (the settings sheet rounds
/// only its top).
struct DepthBox: View {
    @Environment(\.stageScale) private var s
    let depth: Depth
    let top: CGFloat
    let bottom: CGFloat

    init(_ depth: Depth, radius: CGFloat) {
        self.depth = depth
        top = radius
        bottom = radius
    }

    init(_ depth: Depth, top: CGFloat, bottom: CGFloat) {
        self.depth = depth
        self.top = top
        self.bottom = bottom
    }

    private func shape(_ grow: CGFloat) -> UnevenRoundedRectangle {
        let t = max(0, top + grow) * s, b = max(0, bottom + grow) * s
        return UnevenRoundedRectangle(topLeadingRadius: t, bottomLeadingRadius: b, bottomTrailingRadius: b,
                                      topTrailingRadius: t, style: .circular)
    }

    var body: some View {
        let outer = depth.shadows.filter { !$0.inset }
        ZStack {
            // CSS paints the first shadow on top, so draw the list back to front.
            ForEach(Array(outer.enumerated().reversed()), id: \.offset) { _, shadow in
                shape(shadow.spread)
                    .fill(shadow.color)
                    .padding(-shadow.spread * s)
                    .offset(x: shadow.x * s, y: shadow.y * s)
                    .blur(radius: shadow.blur / 2 * s)
            }
            shape(0).fill(face)
        }
    }

    private var face: AnyShapeStyle {
        var style = AnyShapeStyle(depth.fill)
        for shadow in depth.shadows where shadow.inset {
            style = AnyShapeStyle(style.shadow(.inner(color: shadow.color, radius: shadow.blur / 2 * s,
                                                      x: shadow.x * s, y: shadow.y * s)))
        }
        return style
    }
}
