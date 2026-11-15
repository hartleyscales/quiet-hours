import ActivityKit
import Foundation

/// The Live Activity that shows the time left in the window on the lock screen.
struct QuietActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        enum Status: String, Codable, Hashable {
            case quiet
            /// Front mode only: out of Quiet Hours, grace period running until `backBy`.
            case steppedOut
            case left
            case ended
        }
        var status: Status
        var leftAt: Date?
        /// Front mode: when the grace period runs out. Set with `.steppedOut`.
        var backBy: Date? = nil
    }

    var windowID: String
    var startsAt: Date
    var endsAt: Date
}
