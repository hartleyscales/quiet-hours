import SwiftUI

// The mock's inline SVG icons, drawn in their own view boxes.

/// The gear button's sliders: `M4 7h10M18 7h2M4 17h2M10 17h10`, circles at (16,7) and (8,17).
struct SlidersIcon: Shape {
    func path(in rect: CGRect) -> Path {
        let k = rect.width / 24
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: rect.minX + x * k, y: rect.minY + y * k) }
        var path = Path()
        for (a, b) in [((4, 7), (14, 7)), ((18, 7), (20, 7)), ((4, 17), (6, 17)), ((10, 17), (20, 17))] {
            path.move(to: p(CGFloat(a.0), CGFloat(a.1)))
            path.addLine(to: p(CGFloat(b.0), CGFloat(b.1)))
        }
        path.addEllipse(in: CGRect(x: rect.minX + 14 * k, y: rect.minY + 5 * k, width: 4 * k, height: 4 * k))
        path.addEllipse(in: CGRect(x: rect.minX + 6 * k, y: rect.minY + 15 * k, width: 4 * k, height: 4 * k))
        return path
    }
}

/// The settings rows' arrow: `M1 1l7 7-7 7` in a 9 x 16 view box, drawn 9 x 16.
struct ChevronIcon: View {
    @Environment(\.stageScale) private var s

    var body: some View {
        Path { p in
            p.move(to: CGPoint(x: 1, y: 1))
            p.addLine(to: CGPoint(x: 8, y: 8))
            p.addLine(to: CGPoint(x: 1, y: 15))
        }
        .applying(CGAffineTransform(scaleX: s, y: s))
        .stroke(style: StrokeStyle(lineWidth: 1.8 * s, lineCap: .round, lineJoin: .round))
        .frame(width: 9 * s, height: 16 * s)
    }
}

/// The composer's send arrow: `M12 19V5M6 11l6-6 6 6`.
struct ArrowUpIcon: Shape {
    func path(in rect: CGRect) -> Path {
        let k = rect.width / 24
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: rect.minX + x * k, y: rect.minY + y * k) }
        var path = Path()
        path.move(to: p(12, 19))
        path.addLine(to: p(12, 5))
        path.move(to: p(6, 11))
        path.addLine(to: p(12, 5))
        path.addLine(to: p(18, 11))
        return path
    }
}

/// An SVG icon at `size` design points with the SVG's stroke width (in view-box units).
struct StrokeIcon<S: Shape>: View {
    @Environment(\.stageScale) private var s
    let shape: S
    let size: CGFloat
    let lineWidth: CGFloat

    var body: some View {
        shape
            .stroke(style: StrokeStyle(lineWidth: lineWidth * size / 24 * s, lineCap: .round, lineJoin: .round))
            .frame(width: size * s, height: size * s)
    }
}

/// The X that closes the board: two strokes corner to corner, inset like the web's `M6 6l12 12M18 6L6 18`.
struct CloseIcon: Shape {
    func path(in rect: CGRect) -> Path {
        let k = rect.width / 24
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: rect.minX + x * k, y: rect.minY + y * k) }
        var path = Path()
        path.move(to: p(6, 6)); path.addLine(to: p(18, 18))
        path.move(to: p(18, 6)); path.addLine(to: p(6, 18))
        return path
    }
}
