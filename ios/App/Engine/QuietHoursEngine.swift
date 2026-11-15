import ActivityKit
import Foundation
import Observation

/// Everything the UI needs to know about the lock, in one value. The same in both modes;
/// fields that only one mode fills say so.
struct QuietState: Equatable {
    /// The lock compiled into this build.
    var mode: LockMode = .compiled

    var access: QuietAccess = .notDetermined
    var isAuthorized: Bool { access == .approved }
    /// One line describing access, for the debug screen.
    var accessDetail = ""

    /// Screen Time mode: the person chooses apps in Apple's picker (see `quietHoursAppPicker`).
    /// Front mode: false; there is nothing to choose.
    var usesAppPicker = false
    /// Screen Time mode: what the picks mean. Nil in front mode.
    var lockScope: LockScope?
    var selectedApplications = 0
    var selectedCategories = 0
    var selectedWebDomains = 0
    var hasSelection: Bool { selectedApplications + selectedCategories + selectedWebDomains > 0 }
    /// Whether `scheduleWindow` would accept a window now (access and selection are in order).
    var isReadyToSchedule = false
    /// Something about the phone's setup that will make the lock misjudge, in a sentence the UI
    /// can show, or nil. Front mode: no passcode or no Face ID / Touch ID. Screen Time mode: more
    /// picks than Apple allows.
    var setupWarning: String?

    var window: QuietWindow?
    var phase: WindowPhase = .none
    var isScheduled: Bool { phase == .scheduled }
    /// Inside the window and not left. Includes `.due` (lock not yet on) and `.steppedOut`.
    var isActive: Bool { phase == .active || phase == .due || phase == .steppedOut }
    var hasLeft: Bool { phase == .left }
    var leftAt: Date?
    /// Front mode: when the person must be back in Quiet Hours to stay in. Set while stepped out.
    var backBy: Date?

    /// When the lock went on (front mode: when Quiet Hours was first in front in the window).
    var lockAppliedAt: Date?
    var lockAppliedBy: String?
    var lockClearedAt: Date?
    var lockClearedBy: String?

    /// Screen Time mode: shield draws counted as reaches. Front mode: times the person stepped
    /// out to another app.
    var reachCount = 0
    /// Screen Time mode: presses of Stay on the shield. Always 0 in front mode.
    var stayPresses = 0
    var peopleCount: Int?
    var leaveOpensApp = false

    var liveActivity = "none"
    var liveActivitiesEnabled = false
    var notificationsAllowed = false

    /// Mode-specific diagnostics, for the debug screen only.
    var details: [QuietDetail] = []
    var log: [String] = []
}

struct QuietDetail: Equatable, Hashable {
    let label: String
    let value: String
}

enum QuietEngineError: LocalizedError {
    case notAuthorized
    case nothingSelected
    case tooManyTokens(String)
    case endNotAfterStart
    case alreadyOver
    case tooLong
    case monitoring(String)

    var errorDescription: String? {
        switch self {
        case .notAuthorized: return "Screen Time access has not been granted."
        case .nothingSelected: return "Nothing has been chosen to lock."
        case .tooManyTokens(let message): return message
        case .endNotAfterStart: return "The window must end after it starts."
        case .alreadyOver: return "That window has already ended."
        case .tooLong: return "A window cannot be longer than one week."
        case .monitoring(let message): return "DeviceActivity refused the schedule: \(message)"
        }
    }
}

/// The lock engine. The future UI talks only to this, and the same calls work in both modes.
///
/// - Access: `requestAuthorization()`, `state.isAuthorized`.
/// - Selection (Screen Time mode only; `state.usesAppPicker`): `.quietHoursAppPicker(isPresented:)`
///   on any view, `setLockScope(_:)`.
/// - Window: `scheduleWindow(id:start:end:)`, `cancelWindow()`, `leaveEarly()`.
/// - Shared numbers: `setPeopleCount(_:)`; `state.reachCount`, `state.leftAt`.
/// - Lifecycle: call `didBecomeActive()` when the scene becomes active.
@MainActor
@Observable
final class QuietHoursEngine {
    static let shared = QuietHoursEngine()

    private(set) var state = QuietState()

    /// The mode's backend. Its concrete type is chosen at compile time (see `ActiveLock`).
    @ObservationIgnored let lock = ActiveLock()
    @ObservationIgnored private let store = QuietStore()
    @ObservationIgnored private var notificationsAllowed = false
    @ObservationIgnored private var tidyingActivities = false

    private init() {
        lock.onChange = { [weak self] in self?.refresh() }
        dropWindowFromOtherMode()
        refresh()
    }

    /// Both builds install as the same app and share storage. A window scheduled by the other
    /// mode cannot be enforced by this one (a front-mode window has no DeviceActivity schedule;
    /// a Screen Time window has no front-mode records), so it is removed.
    private func dropWindowFromOtherMode() {
        guard let window = store.window else { return }
        let scheduledBy = window.scheduledBy ?? LockMode.screenTime.rawValue
        guard scheduledBy != LockMode.compiled.rawValue else { return }
        store.window = nil
        lock.stopEnforcing()
        store.resetWindowRecord()
        PreStartNotification.cancel()
        WindowEndTask.cancel()
        store.log("app: dropped window \(window.id) scheduled in \(scheduledBy) mode; this build is \(LockMode.compiled.rawValue) mode")
    }

    // MARK: Access

    /// Asks for what the lock needs. Screen Time mode: Screen Time access (Face ID prompt).
    /// Front mode: nothing; returns at once.
    func requestAuthorization() async throws {
        do {
            try await lock.requestAccess()
        } catch {
            refresh()
            throw error
        }
        refresh()
    }

    /// Asks for permission to show notifications (pre-start; in front mode also "stepped out").
    @discardableResult
    func requestNotificationPermission() async -> Bool {
        notificationsAllowed = await PreStartNotification.requestPermission()
        store.log("app: notifications \(notificationsAllowed ? "allowed" : "not allowed")")
        refresh()
        return notificationsAllowed
    }

    /// Screen Time mode: whether the picks mean "lock these" or "lock everything except these".
    /// Front mode: ignored.
    func setLockScope(_ scope: LockScope) {
        lock.setLockScope(scope)
        refresh()
    }

    // MARK: Window

    /// Schedules the one window. Replaces any window already scheduled. Screen Time mode: the
    /// lock starts and stops through DeviceActivity, so the app need not be running. Front
    /// mode: the person opens Quiet Hours at the start and keeps it in front.
    func scheduleWindow(id: String = UUID().uuidString, start: Date, end: Date) async throws {
        let now = Date()
        try lock.checkReadyToSchedule()
        guard end > start else { throw QuietEngineError.endNotAfterStart }
        guard end > now else { throw QuietEngineError.alreadyOver }
        let monitoredEnd = lock.monitoredEnd(start: start, end: end)
        guard monitoredEnd.timeIntervalSince(start) <= QuietConstants.maximumMonitoredInterval else {
            throw QuietEngineError.tooLong
        }
        let window = QuietWindow(id: id, start: start, end: end, monitoredEnd: monitoredEnd,
                                 scheduledBy: LockMode.compiled.rawValue)

        // Store the window before enforcement starts: if the window is already under way,
        // DeviceActivity calls the monitor immediately and the monitor reads it from here.
        store.window = window
        store.resetWindowRecord()
        do {
            try lock.startEnforcing(window)
        } catch {
            store.window = nil
            refresh()
            throw error
        }
        store.log("app: window \(window.id) scheduled \(Self.time(start))–\(Self.time(end)) (\(LockMode.compiled.rawValue) mode)")

        let body = ActiveLock.preStartBody(startTime: Self.clock(window.start))
        if let fireAt = await PreStartNotification.schedule(for: window, body: body) {
            store.log("app: notification set for \(Self.time(fireAt))\(notificationsAllowed ? "" : " (notifications not allowed)")")
        } else {
            store.log("app: no notification (too close to the start)")
        }
        store.log("app: " + (await LiveActivityController.schedule(for: window, alertBody: ActiveLock.startAlertBody)))
        WindowEndTask.schedule(at: window.end)
        refresh()
    }

    /// Length of the debug test window: 2 minutes in Screen Time mode; in front mode longer than
    /// the grace period, so running it out can be tested.
    nonisolated static var testWindowLength: TimeInterval {
        LockMode.compiled == .front ? QuietConstants.frontTestWindowLength : 120
    }

    /// Debug helper: a short window starting about one minute from now, on a minute boundary.
    @discardableResult
    func startTestWindow(now: Date = Date()) async throws -> QuietWindow {
        let oneMinuteOut = now.addingTimeInterval(60)
        let start = Calendar.current.nextDate(after: oneMinuteOut, matching: DateComponents(second: 0),
                                              matchingPolicy: .nextTime) ?? oneMinuteOut
        let end = start.addingTimeInterval(Self.testWindowLength)
        let id = "test-\(Int(start.timeIntervalSince1970))"
        try await scheduleWindow(id: id, start: start, end: end)
        return store.window ?? QuietWindow(id: id, start: start, end: end,
                                           monitoredEnd: lock.monitoredEnd(start: start, end: end))
    }

    /// Removes the window entirely: no lock, no notification, no Live Activity.
    func cancelWindow() async {
        // Clear the stored window first: in Screen Time mode stopping monitoring makes the system
        // call intervalDidEnd, and the monitor ignores it when no window is stored.
        store.window = nil
        lock.stopEnforcing()
        store.resetWindowRecord()
        PreStartNotification.cancel()
        WindowEndTask.cancel()
        await LiveActivityBridge.finish(status: .ended, leftAt: nil, dismissal: .immediate)
        store.log("app: window cancelled")
        refresh()
    }

    /// Leave early: removes the lock for the rest of the window and records the time.
    /// In Screen Time mode the same happens when "Leave quiet hours" is pressed on the shield.
    @discardableResult
    func leaveEarly() async -> Bool {
        let left = lock.leaveEarly(now: Date())
        if left {
            await LiveActivityBridge.finish(status: .left, leftAt: store.leftAt, dismissal: .immediate)
        }
        refresh()
        return left
    }

    // MARK: Shared numbers

    /// Writes the number of people in quiet hours. Screen Time mode shows it in the shield's
    /// subtitle; the shield reads it when drawn, and one already on screen is not updated.
    func setPeopleCount(_ count: Int?) {
        store.peopleCount = count
        refresh()
    }

    /// Screen Time mode, iOS 26.5+: whether "Leave quiet hours" also opens this app.
    func setLeaveOpensApp(_ on: Bool) {
        store.leaveOpensApp = on
        refresh()
    }

    func clearLog() {
        store.clearLog()
        refresh()
    }

    // MARK: Lifecycle

    /// Call when the scene becomes active.
    func didBecomeActive() async {
        await lock.didBecomeActive()
        notificationsAllowed = await PreStartNotification.isAllowed()
        await settle()
    }

    /// Re-reads shared storage, fixes anything that could not be done earlier, and publishes
    /// `state`. Cheap enough to call every second.
    func refresh(now: Date = Date()) {
        lock.reconcile(now: now)
        state = buildState(now: now)
        if !tidyingActivities, activityTidy(now: now) != nil {
            tidyingActivities = true
            Task {
                await tidyActivities(now: now)
                tidyingActivities = false
                state = buildState(now: Date())
            }
        }
    }

    /// `refresh()` that waits for Live Activity clean-up. Used by the background task.
    func settle(now: Date = Date()) async {
        lock.reconcile(now: now)
        await tidyActivities(now: now)
        state = buildState(now: now)
    }

    // MARK: Live Activity clean-up

    private func activityTidy(now: Date) -> (status: QuietActivityAttributes.ContentState.Status,
                                             leftAt: Date?, dismissal: ActivityUIDismissalPolicy)? {
        let live = LiveActivityBridge.activities.contains {
            $0.activityState != .ended && $0.activityState != .dismissed
        }
        guard live else { return nil }
        switch store.phase(at: now) {
        case .left:
            return (.left, store.leftAt, .immediate)
        case .ended:
            let end = store.window?.end ?? now
            return (.ended, nil, .after(end.addingTimeInterval(10 * 60)))
        case .none:
            return (.ended, nil, .immediate)
        case .scheduled, .due, .active, .steppedOut:
            return nil
        }
    }

    private func tidyActivities(now: Date) async {
        guard let tidy = activityTidy(now: now) else { return }
        let ended = await LiveActivityBridge.finish(status: tidy.status, leftAt: tidy.leftAt, dismissal: tidy.dismissal)
        if ended > 0 { store.log("app: ended \(ended) Live Activit\(ended == 1 ? "y" : "ies")") }
    }

    // MARK: State

    private func buildState(now: Date) -> QuietState {
        var s = QuietState()
        s.window = store.window
        s.phase = store.phase(at: now)
        s.leftAt = store.leftAt
        s.lockAppliedAt = store.appliedAt
        s.lockAppliedBy = store.appliedBy
        s.lockClearedAt = store.clearedAt
        s.lockClearedBy = store.clearedBy
        s.reachCount = store.reachCount
        s.stayPresses = store.stayPresses
        s.peopleCount = store.peopleCount
        s.leaveOpensApp = store.leaveOpensApp
        s.liveActivity = LiveActivityBridge.summary
        s.liveActivitiesEnabled = LiveActivityController.areEnabled
        s.notificationsAllowed = notificationsAllowed
        lock.fill(&s, now: now)
        s.log = store.logLines.reversed()
        return s
    }

    nonisolated static func time(_ date: Date) -> String {
        date.formatted(date: .omitted, time: .standard)
    }

    /// "7:00" in a 12-hour locale, "19:00" in a 24-hour one. For notification text.
    nonisolated static func clock(_ date: Date) -> String {
        date.formatted(.dateTime.hour(.defaultDigits(amPM: .omitted)).minute(.twoDigits))
    }
}
