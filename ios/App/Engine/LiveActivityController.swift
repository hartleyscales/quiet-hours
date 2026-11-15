import ActivityKit
import Foundation

/// Starts the lock-screen countdown for a window.
///
/// The app can only request a Live Activity while it is in the foreground. iOS 26 added
/// scheduled starts: requesting with `start:` while the app is open makes the system start it
/// at that date even if the app is closed by then. That is how the countdown begins with the
/// window. Its stale date is the window's end, so it reads as over even if nothing ends it.
enum LiveActivityController {
    static var areEnabled: Bool { ActivityAuthorizationInfo().areActivitiesEnabled }

    /// Replaces any existing Quiet Hours Live Activity with one for `window`. `alertBody` is
    /// shown when a scheduled activity starts (it comes from the compiled mode).
    /// Returns a short description of what happened, for the log.
    static func schedule(for window: QuietWindow, alertBody: String, now: Date = Date()) async -> String {
        await LiveActivityBridge.finish(status: .ended, leftAt: nil, dismissal: .immediate)
        guard areEnabled else { return "Live Activities are turned off for this app" }

        let attributes = QuietActivityAttributes(windowID: window.id, startsAt: window.start, endsAt: window.end)
        let content = ActivityContent(state: QuietActivityAttributes.ContentState(status: .quiet, leftAt: nil),
                                      staleDate: window.end)
        do {
            if window.start.timeIntervalSince(now) > 5 {
                let alert = AlertConfiguration(title: "Quiet hours", body: LocalizedStringResource(stringLiteral: alertBody),
                                               sound: .default)
                _ = try Activity.request(attributes: attributes, content: content, pushType: nil,
                                         style: .standard, alertConfiguration: alert, start: window.start)
                return "Live Activity scheduled to start at the window's start"
            } else {
                _ = try Activity.request(attributes: attributes, content: content, pushType: nil)
                return "Live Activity started now (window already under way)"
            }
        } catch {
            return "Live Activity request failed: \(error.localizedDescription)"
        }
    }
}
