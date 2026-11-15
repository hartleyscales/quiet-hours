import DeviceActivity
import Foundation

/// Runs in its own process when DeviceActivity reaches a boundary of the scheduled window,
/// whether or not the app is running. Applies the lock at the start, removes it at the end.
///
/// The system calls these only while the phone is in use: a pocketed phone gets
/// `intervalDidStart` the first time it is picked up inside the window.
final class QuietMonitor: DeviceActivityMonitor {
    private let store = QuietStore()

    override func intervalDidStart(for activity: DeviceActivityName) {
        super.intervalDidStart(for: activity)
        guard isOurs(activity) else { return }
        store.log("monitor: intervalDidStart")
        QuietCore.beginIfDue(source: "monitor")
    }

    override func intervalWillStartWarning(for activity: DeviceActivityName) {
        super.intervalWillStartWarning(for: activity)
        guard isOurs(activity) else { return }
        store.log("monitor: intervalWillStartWarning (ignored)")
    }

    /// For windows shorter than DeviceActivity's 15-minute minimum the monitored interval is
    /// padded and the warning time is set so that this fires at the real end.
    override func intervalWillEndWarning(for activity: DeviceActivityName) {
        super.intervalWillEndWarning(for: activity)
        guard isOurs(activity) else { return }
        store.log("monitor: intervalWillEndWarning")
        guard let window = store.window, window.isPadded else { return }
        guard Date() >= window.end.addingTimeInterval(-QuietConstants.boundaryTolerance) else {
            store.log("monitor: warning came before the real end, ignored")
            return
        }
        finishWindow(source: "monitor (short-window end)")
    }

    override func intervalDidEnd(for activity: DeviceActivityName) {
        super.intervalDidEnd(for: activity)
        guard isOurs(activity) else { return }
        store.log("monitor: intervalDidEnd")
        // intervalDidEnd also arrives when the app stops or replaces monitoring mid-window.
        // Only act if the stored window has actually reached its end; the app handles
        // cancellations itself.
        guard let window = store.window,
              Date() >= window.end.addingTimeInterval(-QuietConstants.boundaryTolerance) else {
            store.log("monitor: not at the stored window's end, ignored")
            return
        }
        finishWindow(source: "monitor")
    }

    private func finishWindow(source: String) {
        QuietCore.endWindow(source: source)
        let ended = LiveActivityBridge.finishBlocking(status: .ended, leftAt: nil,
                                                      dismissal: .after(Date().addingTimeInterval(10 * 60)))
        store.log("monitor: ended \(ended) Live Activit\(ended == 1 ? "y" : "ies") from the extension")
    }

    private func isOurs(_ activity: DeviceActivityName) -> Bool {
        activity.rawValue == QuietConstants.activityName
    }
}
