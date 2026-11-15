import Foundation

/// Identifiers and tuning values shared by the app and every extension.
enum QuietConstants {
    /// App Group that holds the shared UserDefaults suite. Set once, as QH_APP_GROUP in
    /// project.yml, and read from each target's Info.plist.
    static let appGroup: String =
        (Bundle.main.object(forInfoDictionaryKey: "QuietHoursAppGroup") as? String)
        ?? "group.com.hms-web-development.QuietHours"

    /// The single DeviceActivity we monitor. Scheduling a new window overwrites it.
    static let activityName = "quietHours.window"

    /// Named ManagedSettings store that carries the shield. Shared by app and extensions.
    static let managedStoreName = "quietHours"

    /// DeviceActivity refuses intervals shorter than 15 minutes (MonitoringError.intervalTooShort).
    /// Shorter windows are monitored over this padded length and ended early from
    /// `intervalWillEndWarning`. 16 rather than 15 to stay clear of the boundary.
    static let minimumMonitoredInterval: TimeInterval = 16 * 60

    /// DeviceActivity refuses intervals longer than one week (MonitoringError.intervalTooLong).
    /// Front mode keeps the same cap so both modes accept the same windows.
    static let maximumMonitoredInterval: TimeInterval = 7 * 24 * 60 * 60

    /// DeviceActivity callbacks are not to-the-second. A callback this close to a boundary
    /// is treated as being on it.
    static let boundaryTolerance: TimeInterval = 60

    /// Shield draw requests closer together than this are treated as one reach
    /// (see LOCK-NOTES.md, "Reach counter").
    static let reachMergeInterval: TimeInterval = 3

    /// How long before the window starts the local notification fires.
    static let preStartLead: TimeInterval = 5 * 60

    /// BGTaskScheduler identifier used to tidy up after the window ends. Derived from the app's
    /// bundle id so it always matches `BGTaskSchedulerPermittedIdentifiers` in the Info.plist,
    /// which project.yml sets to `$(QH_BUNDLE_ID).window-end`. Used by the app only.
    static let windowEndTaskIdentifier = (Bundle.main.bundleIdentifier ?? "com.hms-web-development.QuietHours") + ".window-end"

    /// Number of lines kept in the shared event log.
    static let logCapacity = 80

    // MARK: Screen Time mode

    /// Apple's limit on tokens in one shield setting: 50 apps, 50 categories, 50 sites, and 50
    /// exceptions in `.all(except:)`. Developers report that going over it silently shields
    /// nothing, so the engine refuses instead (see LOCK-NOTES.md, "Total lock").
    static let maximumShieldTokens = 50

    // MARK: Front mode

    /// Front mode: how long someone may be out of Quiet Hours before they count as having left.
    /// Measured from the moment they left the app.
    static let frontGracePeriod: TimeInterval = 120

    /// Front mode: how long after the app goes to the background we wait for a sign that the
    /// phone was locked before treating it as a switch to another app. iOS makes protected data
    /// unavailable about 10 seconds after a lock (passcode set to "Immediately", which Face ID
    /// and Touch ID require), so this leaves 5 seconds of margin. Must stay well under the ~30 s
    /// of background time iOS grants, or the decision is never made while the app can still see
    /// the signal.
    static let frontLockDetectionWindow: TimeInterval = 15

    /// Front mode: when the stepped-out notification fires, counted from leaving. Two seconds
    /// after the decision, so a lock or call seen right at the decision still cancels it.
    static let frontNotificationDelay: TimeInterval = frontLockDetectionWindow + 2

    /// Front mode: length of the debug test window. Longer than the grace period, so stepping
    /// out early in the window can run the grace period out and be recorded as leaving.
    static let frontTestWindowLength: TimeInterval = frontGracePeriod + 3 * 60

    /// Front mode: how often the app records that it is still in front. Lets the next launch
    /// tell how long ago the app stopped if it died without going to the background.
    static let frontHeartbeatInterval: TimeInterval = 5
}
