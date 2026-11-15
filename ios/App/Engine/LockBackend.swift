import Foundation

/// Which lock this build enforces. Chosen at compile time by the scheme:
/// `QuietHours` builds Screen Time mode; `QuietHoursFront` builds front mode (it sets the
/// `QH_FRONT_MODE` compilation condition and compiles `App/Engine/Front` instead of
/// `App/Engine/ScreenTime`).
enum LockMode: String, Sendable {
    /// Apple's Screen Time frameworks shield apps. Needs the Family Controls capability, which
    /// Apple gives only to paid developer teams.
    case screenTime
    /// Quiet Hours stays in front during the window; going to another app counts as reaching
    /// for the phone. No special capability; signs on a free Personal Team.
    case front

    static var compiled: LockMode {
        #if QH_FRONT_MODE
        return .front
        #else
        return .screenTime
        #endif
    }
}

#if QH_FRONT_MODE
typealias ActiveLock = FrontLock
#else
typealias ActiveLock = ScreenTimeLock
#endif

/// Access the lock needs from the person, in terms that do not depend on the mode.
enum QuietAccess: String, Sendable {
    case notDetermined
    case denied
    /// Granted, or nothing to grant (front mode).
    case approved
}

/// The part of the lock engine that differs between modes. `QuietHoursEngine` owns everything
/// else (window storage, notifications, Live Activity, state), so a UI talks only to the engine
/// and does not care which mode is compiled in.
@MainActor
protocol LockBackend: AnyObject {
    init()

    /// Called when the backend changed shared state on its own (front mode reacts to app
    /// lifecycle events directly), so the engine can republish `state`.
    var onChange: (() -> Void)? { get set }

    var access: QuietAccess { get }
    /// One line for the debug screen.
    var accessDetail: String { get }
    func requestAccess() async throws

    /// Throws `QuietEngineError` if a window cannot be scheduled right now.
    func checkReadyToSchedule() throws
    /// End of the interval this mode needs to watch for a window.
    func monitoredEnd(start: Date, end: Date) -> Date
    /// Starts enforcing a window that the engine has just stored. Throws `QuietEngineError`.
    func startEnforcing(_ window: QuietWindow) throws
    /// Stops enforcing. The engine has already removed the stored window.
    func stopEnforcing()
    /// Records leaving early and removes the lock. Returns false if no window is in progress.
    func leaveEarly(now: Date) -> Bool
    /// Fixes up shared state; cheap enough to run every second.
    func reconcile(now: Date)
    func didBecomeActive() async
    /// Screen Time mode: choose what the picker's picks mean. Front mode: ignored.
    func setLockScope(_ scope: LockScope)
    /// Fills in the mode's part of `state`.
    func fill(_ state: inout QuietState, now: Date)

    /// Body of the notification `preStartLead` before the start. `startTime` is formatted.
    static func preStartBody(startTime: String) -> String
    /// Body of the alert shown when the scheduled Live Activity starts.
    static var startAlertBody: String { get }
}
