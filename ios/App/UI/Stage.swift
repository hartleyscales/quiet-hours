import SwiftUI
import UIKit

/// The 390 x 844 design space, scaled uniformly to the device's width and pinned to the top,
/// with the screen's surface colour filling the whole display, safe areas included. On a
/// phone shorter than the design's proportions (iPhone SE) it scales to fit the height instead,
/// centred, so nothing is cut off.
///
/// The keyboard never moves or resizes the stage's contents. The reader around them respects
/// only the keyboard's safe area, so its height shrinks as the keyboard rises, inside SwiftUI's
/// own keyboard animation; the stage keeps the full height and stays pinned to the top, and the
/// difference is handed down as `keyboardInset`. Whatever a screen lays out from it travels
/// with the keyboard's top edge, both ways.
struct Stage<Content: View>: View {
    @Environment(\.stageSurfaceHidden) private var surfaceHidden
    let surface: Color
    @ViewBuilder let content: () -> Content
    /// The reader's height with no keyboard up: the full screen.
    @State private var fullHeight: CGFloat?

    var body: some View {
        GeometryReader { open in
            let full = max(fullHeight ?? open.size.height, open.size.height)
            let s = min(open.size.width / Design.width, full / Design.height)
            content()
                .frame(width: Design.width * s, height: Design.height * s, alignment: .topLeading)
                .environment(\.stageScale, s)
                .environment(\.keyboardInset, max(0, full - open.size.height))
                .frame(width: open.size.width, alignment: .top)
                .ignoresSafeArea(.keyboard)
        }
        .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { height in
            fullHeight = max(fullHeight ?? 0, height)
        }
        .ignoresSafeArea(.container)
        .background(surfaceHidden ? Color.clear.ignoresSafeArea() : surface.ignoresSafeArea())
    }
}

extension EnvironmentValues {
    /// Set by the root, which draws one surface under every screen and eases it between them.
    @Entry var stageSurfaceHidden = false
    /// Height of the on-screen keyboard over the stage, in device points (0 when none).
    @Entry var keyboardInset: CGFloat = 0
}

/// Below this keyboard height (device points) no on-screen keyboard is up: a hardware
/// keyboard, or only a shortcut bar. Screens then stay in their resting layout.
enum KeyboardUp {
    static let minimum: CGFloat = 150
}

/// Hands its content the stage scale and the keyboard's height. A screen's own body sits
/// outside the `Stage` and so cannot read them itself; anything it builds that needs them
/// goes through this.
struct ScaleReader<Content: View>: View {
    @Environment(\.stageScale) private var s
    @ViewBuilder let content: (CGFloat) -> Content

    var body: some View { content(s) }
}

struct StageReader<Content: View>: View {
    @Environment(\.stageScale) private var s
    @Environment(\.keyboardInset) private var keyboard
    @ViewBuilder let content: (_ scale: CGFloat, _ keyboard: CGFloat) -> Content

    var body: some View { content(s, keyboard) }
}

/// Places a view in the design space: `x`, `y` and `width` in design points, top-left anchored.
struct Placed: ViewModifier {
    @Environment(\.stageScale) private var s
    let x: CGFloat
    let y: CGFloat
    let width: CGFloat?
    let alignment: Alignment

    func body(content: Content) -> some View {
        content
            .frame(width: width.map { $0 * s }, alignment: alignment)
            .offset(x: x * s, y: y * s)
    }
}

/// Anchors a view's bottom edge `bottom` design points above the design space's bottom.
struct PinnedBottom: ViewModifier {
    @Environment(\.stageScale) private var s
    let x: CGFloat
    let bottom: CGFloat
    let width: CGFloat?

    func body(content: Content) -> some View {
        content
            .frame(width: width.map { $0 * s })
            .frame(width: Design.width * s, height: (Design.height - bottom) * s,
                   alignment: width == nil ? .bottom : .bottomLeading)
            .offset(x: width == nil ? 0 : x * s)
    }
}

extension View {
    /// `left`/`top`/`width` as in the mock's CSS.
    func at(x: CGFloat = 0, y: CGFloat, width: CGFloat? = nil, alignment: Alignment = .topLeading) -> some View {
        modifier(Placed(x: x, y: y, width: width, alignment: alignment))
    }

    /// Full width (`left:0; right:0`) at `top`, centred text with horizontal `padding`.
    func centred(y: CGFloat, padding: CGFloat = 0) -> some View {
        multilineTextAlignment(.center)
            .modifier(DesignPadding(edges: .horizontal, length: padding))
            .modifier(Placed(x: 0, y: y, width: Design.width, alignment: .top))
    }

    /// Padding in design points.
    func designPadding(_ edges: Edge.Set = .all, _ length: CGFloat) -> some View {
        modifier(DesignPadding(edges: edges, length: length))
    }

    /// `bottom` as in the mock's CSS; with `width`, also `left` = x. Without, centred.
    func pinned(bottom: CGFloat, x: CGFloat = 24, width: CGFloat? = 342) -> some View {
        modifier(PinnedBottom(x: x, bottom: bottom, width: width))
    }

    /// Scales a design length.
    func designFrame(width: CGFloat? = nil, height: CGFloat? = nil, alignment: Alignment = .center) -> some View {
        modifier(DesignFrame(width: width, height: height, alignment: alignment))
    }
}

struct DesignPadding: ViewModifier {
    @Environment(\.stageScale) private var s
    let edges: Edge.Set
    let length: CGFloat

    func body(content: Content) -> some View {
        content.padding(edges, length * s)
    }
}

struct DesignFrame: ViewModifier {
    @Environment(\.stageScale) private var s
    let width: CGFloat?
    let height: CGFloat?
    let alignment: Alignment

    func body(content: Content) -> some View {
        content.frame(width: width.map { $0 * s }, height: height.map { $0 * s }, alignment: alignment)
    }
}

