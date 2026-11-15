import SwiftUI
import UIKit

/// The Locked sky: the stars of `stars_quiet.png` (330 dots on the 2pt grid, three strengths,
/// kept clear of the moon at its place on the quiet Locked screen), read from the image once so
/// they can come out a few at a time. At rest it draws exactly the image's dots.
struct StarField: Sendable {
    struct Star: Sendable {
        let x: Float
        let y: Float
        let alpha: Float
        let delay: Float
    }

    let stars: [Star]

    static let shared = StarField()

    private init() {
        guard let image = UIImage(named: "stars_quiet")?.cgImage else {
            stars = []
            return
        }
        let w = image.width, h = image.height
        var pixels = [UInt8](repeating: 0, count: w * h * 4)
        let drawn: Bool = pixels.withUnsafeMutableBytes { buffer in
            guard let ctx = CGContext(data: buffer.baseAddress, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                                      space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
            ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
            return true
        }
        guard drawn else {
            stars = []
            return
        }
        // Each star is a 4px square at (i * 6 + 1, j * 6 + 1) in the 3x image: one cell of the 2pt grid.
        var found: [Star] = []
        var rng = SystemRandomNumberGenerator()
        for j in 0..<(h / 6) {
            for i in 0..<(w / 6) {
                let px = i * 6 + 2, py = j * 6 + 2
                let a = pixels[(py * w + px) * 4 + 3]
                guard a > 8 else { continue }
                found.append(Star(x: Float(i * 2) + 0.33, y: Float(j * 2) + 0.33, alpha: Float(a) / 255,
                                  delay: Float.random(in: 0...0.65, using: &rng)))
            }
        }
        stars = found
    }
}

/// The stars, over the whole screen. Inserted with `comeOut`, they appear a few at a time.
struct StarsView: View {
    @Environment(\.stageScale) private var s
    let comeOut: Bool
    @State private var since: Date?
    @State private var settled = false

    private static let fade: Float = 0.3
    private static let color = Color(hex: 0xEAE5DE)

    var body: some View {
        TimelineView(.animation(minimumInterval: nil, paused: settled || since == nil)) { timeline in
            Canvas { context, _ in
                let t = settled ? 10 : since.map { Float(timeline.date.timeIntervalSince($0)) } ?? 10
                let side = DotArt.dotSize * s
                for star in StarField.shared.stars {
                    let level = min(1, max(0, (t - star.delay) / Self.fade))
                    guard level > 0 else { continue }
                    let rect = CGRect(x: CGFloat(star.x) * s, y: CGFloat(star.y) * s, width: side, height: side)
                    context.fill(Path(rect), with: .color(Self.color.opacity(Double(star.alpha * level))))
                }
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
        .onAppear {
            guard comeOut, since == nil else { return }
            since = Date()
            Task {
                try? await Task.sleep(for: .seconds(1.0))
                settled = true
            }
        }
    }
}
