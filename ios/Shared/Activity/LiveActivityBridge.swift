import ActivityKit
import Foundation

/// Ends or updates our Live Activities. Used by the app, and attempted from the monitor and
/// shield-action extensions. Apple documents ending a Live Activity from the app (foreground or
/// background); whether an extension process can see the app's activities is not documented,
/// so the extensions log how many they found and the app tidies up on its next run.
enum LiveActivityBridge {
    typealias State = QuietActivityAttributes.ContentState

    static var activities: [Activity<QuietActivityAttributes>] {
        Activity<QuietActivityAttributes>.activities
    }

    /// Ends every Quiet Hours Live Activity that is still pending, running or stale.
    /// Returns how many it ended.
    @discardableResult
    static func finish(status: State.Status, leftAt: Date?, dismissal: ActivityUIDismissalPolicy) async -> Int {
        var ended = 0
        for activity in activities where activity.activityState != .ended && activity.activityState != .dismissed {
            let content = ActivityContent(state: State(status: status, leftAt: leftAt), staleDate: nil)
            await activity.end(content, dismissalPolicy: dismissal)
            ended += 1
        }
        return ended
    }

    /// Updates every running Quiet Hours Live Activity in place. Front mode uses it when the
    /// person steps out (`.steppedOut`, stale at the grace deadline) and comes back (`.quiet`,
    /// stale at the window's end). Returns how many it updated.
    @discardableResult
    static func update(status: State.Status, backBy: Date?, staleDate: Date?) async -> Int {
        var updated = 0
        for activity in activities where activity.activityState == .active || activity.activityState == .stale {
            let content = ActivityContent(state: State(status: status, leftAt: nil, backBy: backBy), staleDate: staleDate)
            await activity.update(content)
            updated += 1
        }
        return updated
    }

    /// Synchronous wrapper for extension callbacks that must finish before returning.
    @discardableResult
    static func finishBlocking(status: State.Status, leftAt: Date?, dismissal: ActivityUIDismissalPolicy,
                               timeout: TimeInterval = 3) -> Int {
        let semaphore = DispatchSemaphore(value: 0)
        let box = ResultBox()
        Task.detached {
            box.value = await finish(status: status, leftAt: leftAt, dismissal: dismissal)
            semaphore.signal()
        }
        _ = semaphore.wait(timeout: .now() + timeout)
        return box.value
    }

    private final class ResultBox: @unchecked Sendable {
        var value = 0
    }

    /// One line describing the activities this process can see, for the debug screen.
    static var summary: String {
        let list = activities
        guard !list.isEmpty else { return "none" }
        return list.map { "\($0.activityState)" }.joined(separator: ", ")
    }
}
