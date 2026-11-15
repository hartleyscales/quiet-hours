import Foundation

/// One quiet-hours window as the phone knows it.
struct QuietWindow: Codable, Equatable, Sendable {
    /// Identifier of the window. The future UI should pass the server's week id.
    var id: String
    /// When the lock should start.
    var start: Date
    /// When the lock should stop.
    var end: Date
    /// End of the interval handed to DeviceActivity (Screen Time mode). Later than `end` only
    /// when the window is shorter than DeviceActivity's minimum interval. Equal to `end` in
    /// front mode.
    var monitoredEnd: Date
    /// `LockMode.rawValue` of the build that scheduled it. Both builds install as the same app,
    /// so a window from the other mode is dropped on launch. Nil means Screen Time (windows
    /// stored before this field existed).
    var scheduledBy: String? = nil

    var isPadded: Bool { monitoredEnd > end }
    var duration: TimeInterval { end.timeIntervalSince(start) }
}

/// Where a window stands, derived from the stored timestamps. Never stored itself.
enum WindowPhase: String, Sendable {
    /// No window scheduled.
    case none
    /// Window scheduled, start not reached.
    case scheduled
    /// Inside the window but the lock is not on yet. Screen Time mode: DeviceActivity only calls
    /// `intervalDidStart` once the phone is in use. Front mode: Quiet Hours has not been in
    /// front since the window started.
    case due
    /// Inside the window and the lock is on (front mode: Quiet Hours is in front, or the phone
    /// is locked, on a call, or was restarted).
    case active
    /// Front mode only: out of the app, grace period running.
    case steppedOut
    /// The person left early.
    case left
    /// The window is over.
    case ended
}

/// Screen Time mode: what the person's picks in Apple's picker mean. Stored with the picks,
/// because the same picks mean opposite things under the two scopes.
enum LockScope: String, Codable, Sendable {
    /// Lock only what the person picked. Everything else stays open.
    case selected
    /// Lock every app and website except what the person picked, and except what iOS never
    /// locks (see LOCK-NOTES.md, "Total lock").
    case allExcept
}

/// Front mode: why Quiet Hours is out of the front during the window.
enum FrontAbsence: String, Codable, Sendable {
    /// Just left the front; waiting up to `frontLockDetectionWindow` for a lock or call signal.
    case undecided
    /// Another app (or the home screen). Counts as a reach and starts the grace period.
    case out
    /// The phone was locked. Not counted.
    case lock
    /// A phone call was ringing or active. Not counted.
    case call
    /// The phone restarted while Quiet Hours was away. Not counted.
    case restart
}

/// Front mode: the current spell away from Quiet Hours. At most one at a time; cleared when
/// the person comes back.
struct FrontAbsenceRecord: Codable, Equatable, Sendable {
    /// When Quiet Hours left the front.
    var since: Date
    var reason: FrontAbsence
    /// When `reason` stopped being `.undecided`.
    var decidedAt: Date?

    /// When the person must be back to stay in, if this absence counts.
    var backBy: Date { since.addingTimeInterval(QuietConstants.frontGracePeriod) }
}
