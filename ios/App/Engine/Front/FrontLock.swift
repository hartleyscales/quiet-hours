import CallKit
import Foundation
import UIKit
import UserNotifications

/// Front mode. During the window Quiet Hours is meant to stay in front; going to another app
/// counts as reaching for the phone. No Screen Time frameworks, so it signs on a free team.
///
/// What happens when Quiet Hours leaves the front during the window (LOCK-NOTES.md, "Front mode"):
/// 1. An absence starts, `.undecided`. The app asks iOS for background time (about 30 s) and
///    queues the stepped-out notification for `frontLockDetectionWindow` later.
/// 2. If protected data goes away in that time, the phone was locked: `.lock`, not counted.
///    If a call is ringing or active: `.call`, not counted. Either cancels the notification.
/// 3. Otherwise: `.out`. One reach, the notification goes out, the Live Activity counts down
///    the grace period. Coming back by `since + frontGracePeriod` keeps the person in; not
///    coming back records `leftAt = since + frontGracePeriod`.
/// The app is suspended soon after, so anything later is settled from stored facts the next
/// time it runs.
@MainActor
final class FrontLock: NSObject, LockBackend {
    var onChange: (() -> Void)?

    private let store = QuietStore()
    /// Recreated each time the app becomes active: Apple DTS notes a long-lived observer's
    /// `calls` can be briefly stale after the app resumes. Created while in the foreground, so
    /// it is up to date by the time the app leaves the front.
    private var callObserver = CXCallObserver()
    private var backgroundTask: UIBackgroundTaskIdentifier = .invalid
    private var decisionTask: Task<Void, Never>?
    private var heartbeatTask: Task<Void, Never>?
    /// Notification calls are asynchronous; chaining them keeps a cancel from overtaking the
    /// schedule it is meant to undo.
    private var notificationChain: Task<Void, Never>?
    /// When the app last became active in this process.
    private var activeSince: Date?
    private var checkedLaunch = false
    private var lockSignal = DeviceSignals.LockSignal.unavailable

    override init() {
        super.init()
        callObserver.setDelegate(self, queue: nil)
        lockSignal = DeviceSignals.lockSignal
        let center = NotificationCenter.default
        center.addObserver(self, selector: #selector(appDidBecomeActive),
                           name: UIApplication.didBecomeActiveNotification, object: nil)
        center.addObserver(self, selector: #selector(appDidEnterBackground),
                           name: UIApplication.didEnterBackgroundNotification, object: nil)
        center.addObserver(self, selector: #selector(appWillTerminate),
                           name: UIApplication.willTerminateNotification, object: nil)
        center.addObserver(self, selector: #selector(protectedDataWillBecomeUnavailable),
                           name: UIApplication.protectedDataWillBecomeUnavailableNotification, object: nil)
        center.addObserver(self, selector: #selector(protectedDataDidBecomeAvailable),
                           name: UIApplication.protectedDataDidBecomeAvailableNotification, object: nil)
    }

    // MARK: Access (nothing to grant)

    var access: QuietAccess { .approved }
    var accessDetail: String { "nothing to grant (front mode)" }
    func requestAccess() async throws {}
    func setLockScope(_ scope: LockScope) {}

    // MARK: Window

    func checkReadyToSchedule() throws {}

    func monitoredEnd(start: Date, end: Date) -> Date { end }

    func startEnforcing(_ window: QuietWindow) throws {
        resetInFlightWork()
        store.log("front: open Quiet Hours by \(QuietHoursEngine.time(window.start)) and keep it in front")
    }

    func stopEnforcing() {
        resetInFlightWork()
    }

    func leaveEarly(now: Date) -> Bool {
        settle(now: now, returning: false)
        guard let window = store.window else {
            store.log("front: leave pressed with no window")
            return false
        }
        guard now >= window.start.addingTimeInterval(-QuietConstants.boundaryTolerance) else {
            store.log("front: leave pressed before the window started, ignored")
            return false
        }
        guard store.leftAt == nil, now < window.end else {
            store.log("front: leave pressed after leaving or ending, ignored")
            return false
        }
        store.leftAt = now
        store.clearedAt = now
        store.clearedBy = "app (left)"
        resetInFlightWork()
        store.frontAbsence = nil
        store.log("front: LEFT EARLY")
        return true
    }

    // MARK: Lifecycle

    func didBecomeActive() async {}

    func reconcile(now: Date) {
        checkLaunchOnce(now: now)
        settle(now: now, returning: false)
        markInFrontIfDue(now: now)
        // Record the end the way Screen Time mode does, for the same server report.
        if store.phase(at: now) == .ended, store.clearedAt == nil, let window = store.window {
            store.clearedAt = window.end
            store.clearedBy = "front (window over)"
            store.log("front: window over")
        }
    }

    @objc private func appDidBecomeActive() {
        let now = Date()
        lockSignal = DeviceSignals.lockSignal
        callObserver = CXCallObserver()
        callObserver.setDelegate(self, queue: nil)
        checkLaunchOnce(now: now)
        activeSince = now
        cancelDecision()
        endBackgroundTask()
        comeBack(now: now)
        markInFrontIfDue(now: now)
        if store.window != nil { store.frontSeenAt = now }
        startHeartbeat()
        onChange?()
    }

    @objc private func appDidEnterBackground() {
        let now = Date()
        stopHeartbeat()
        // In front since before the start, and the heartbeat has not marked it yet.
        if store.phase(at: now) == .due { markInFront(at: max(store.window?.start ?? now, activeSince ?? now)) }
        activeSince = nil
        guard store.phase(at: now) == .active, store.frontAbsence == nil else { return }
        store.frontSeenAt = now
        store.frontAbsence = FrontAbsenceRecord(since: now, reason: .undecided)
        beginBackgroundTask()
        if callInProgress {
            decide(.call, now: now)
            onChange?()
            return
        }
        // No warning if the window ends before the grace period would: nobody can be marked
        // as having left then.
        if let window = store.window, now.addingTimeInterval(QuietConstants.frontGracePeriod) < window.end {
            scheduleSteppedOutNotification(since: now)
        }
        decisionTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(QuietConstants.frontLockDetectionWindow))
            guard !Task.isCancelled else { return }
            self?.decideAtDeadline()
        }
        store.log("front: left the front; watching \(Int(QuietConstants.frontLockDetectionWindow)) s for a lock or call")
        onChange?()
    }

    /// Apple calls this only if the app is still running (not suspended) when it is ended; it
    /// is "generally not called when the user quits the app". When it does come while Quiet
    /// Hours is in front, it is most likely being closed from the app switcher.
    @objc private func appWillTerminate() {
        let now = Date()
        stopHeartbeat()
        guard store.phase(at: now) == .active, store.frontAbsence == nil else { return }
        store.frontAbsence = FrontAbsenceRecord(since: now, reason: .undecided)
        // About five seconds left. Queue the stepped-out notification and wait (at most one
        // second) for iOS to accept it; the next launch settles the rest.
        if let window = store.window, now.addingTimeInterval(QuietConstants.frontGracePeriod) < window.end {
            let request = SteppedOutNotification.request(since: now)
            let accepted = DispatchSemaphore(value: 0)
            UNUserNotificationCenter.current().add(request) { _ in accepted.signal() }
            _ = accepted.wait(timeout: .now() + 1)
        }
        store.log("front: closed while in front; counts as stepping out unless the phone was restarting")
    }

    @objc private func protectedDataWillBecomeUnavailable() {
        let now = Date()
        guard let absence = store.frontAbsence else {
            store.log("front: protected data going away (phone locking)")
            return
        }
        store.log("front: protected data going away \(Self.duration(now.timeIntervalSince(absence.since))) after leaving the front")
        if absence.reason == .undecided {
            decide(.lock, now: now)
            onChange?()
        }
    }

    @objc private func protectedDataDidBecomeAvailable() {
        store.log("front: protected data available again (phone unlocked)")
    }

    // MARK: Deciding

    private var callInProgress: Bool {
        callObserver.calls.contains { !$0.hasEnded }
    }

    fileprivate func callsChanged() {
        guard let absence = store.frontAbsence, absence.reason == .undecided, callInProgress else { return }
        decide(.call, now: Date())
        onChange?()
    }

    private func decideAtDeadline() {
        decisionTask = nil
        guard let absence = store.frontAbsence, absence.reason == .undecided else {
            endBackgroundTask()
            return
        }
        // Back in front already: `comeBack` settles it.
        guard UIApplication.shared.applicationState != .active else { return }
        let now = Date()
        if !UIApplication.shared.isProtectedDataAvailable {
            decide(.lock, now: now)
        } else if callInProgress {
            decide(.call, now: now)
        } else {
            decide(.out, now: now)
            showSteppedOutOnLiveActivity(absence, thenEndBackgroundTask: true)
        }
        onChange?()
    }

    /// Switches the Live Activity to the grace-period countdown. It goes stale at the deadline
    /// (or the window's end), which the widget reads as "left" (or "over").
    private func showSteppedOutOnLiveActivity(_ absence: FrontAbsenceRecord, thenEndBackgroundTask: Bool) {
        let end = store.window?.end ?? absence.backBy
        let task = thenEndBackgroundTask ? backgroundTask : .invalid
        if thenEndBackgroundTask { backgroundTask = .invalid }
        let pending = notificationChain
        Task {
            let updated = await LiveActivityBridge.update(status: .steppedOut, backBy: absence.backBy,
                                                          staleDate: min(absence.backBy, end))
            if updated == 0 { self.store.log("front: no running Live Activity to update") }
            await pending?.value
            if task != .invalid { UIApplication.shared.endBackgroundTask(task) }
        }
    }

    private func decide(_ reason: FrontAbsence, now: Date) {
        guard var absence = store.frontAbsence, absence.reason == .undecided, reason != .undecided else { return }
        absence.reason = reason
        absence.decidedAt = now
        store.frontAbsence = absence
        cancelDecision()
        let after = Self.duration(now.timeIntervalSince(absence.since))
        switch reason {
        case .out:
            store.reachCount += 1
            store.log("front: STEPPED OUT (reach \(store.reachCount)), decided \(after) after leaving; back by \(QuietHoursEngine.time(absence.backBy)) to stay in")
        case .lock:
            store.frontLocks += 1
            cancelSteppedOutNotification()
            endBackgroundTask()
            store.log("front: phone locked, decided \(after) after leaving: not counted")
        case .call:
            store.frontCalls += 1
            cancelSteppedOutNotification()
            endBackgroundTask()
            store.log("front: phone call, decided \(after) after leaving: not counted")
        case .restart:
            store.frontRestarts += 1
            cancelSteppedOutNotification()
            store.log("front: phone restarted since leaving the front: not counted")
        case .undecided:
            break
        }
    }

    /// Settles the current absence from stored facts, for when the process that saw Quiet Hours
    /// leave the front stopped, or was suspended, before it decided. Then records leaving if
    /// the grace period has run out.
    private func settle(now: Date, returning: Bool) {
        guard let window = store.window, let absence = store.frontAbsence else { return }
        if absence.reason == .undecided {
            let notified = absence.since.addingTimeInterval(QuietConstants.frontNotificationDelay)
            if let boot = DeviceSignals.bootTime, boot > absence.since {
                decide(.restart, now: now)
            } else if returning || (decisionTask == nil && now >= notified) {
                // Back before a lock or call showed up, or no decision is coming (the process
                // that saw the app leave is gone, or ran out of background time) and the
                // stepped-out notification has gone out: an app switch, or a closed app.
                decide(.out, now: now)
                if !returning { showSteppedOutOnLiveActivity(absence, thenEndBackgroundTask: false) }
            }
        }
        guard store.leftAt == nil, let absence = store.frontAbsence, absence.reason == .out else { return }
        let backBy = absence.backBy
        guard backBy < window.end, now >= backBy else { return }
        store.leftAt = backBy
        store.clearedAt = backBy
        store.clearedBy = "front (not back in time)"
        store.frontAbsence = nil
        cancelSteppedOutNotification()
        store.log("front: LEFT at \(QuietHoursEngine.time(backBy)): out since \(QuietHoursEngine.time(absence.since)), not back within \(Int(QuietConstants.frontGracePeriod)) s")
    }

    /// Quiet Hours is in front again.
    private func comeBack(now: Date) {
        guard let before = store.frontAbsence else { return }
        settle(now: now, returning: true)
        guard let absence = store.frontAbsence else {
            store.log("front: back in Quiet Hours after \(Self.duration(now.timeIntervalSince(before.since))), after leaving")
            return
        }
        store.frontAbsence = nil
        cancelSteppedOutNotification()
        store.log("front: back after \(Self.duration(now.timeIntervalSince(absence.since))) (\(absence.reason.rawValue))")
        if absence.reason == .out, let window = store.window, now < window.end {
            Task { await LiveActivityBridge.update(status: .quiet, backBy: nil, staleDate: window.end) }
        }
    }

    // MARK: In front

    private func markInFrontIfDue(now: Date) {
        guard UIApplication.shared.applicationState != .background, store.phase(at: now) == .due,
              let window = store.window else { return }
        markInFront(at: max(window.start, activeSince ?? now))
    }

    private func markInFront(at date: Date) {
        guard store.appliedAt == nil else { return }
        store.appliedAt = date
        store.appliedBy = "app (in front)"
        store.log("front: IN. Quiet Hours in front from \(QuietHoursEngine.time(date))")
    }

    /// Once per process: if Quiet Hours was in front in the window and stopped without going to
    /// the background (power off from the slider, crash, closed from the app switcher with no
    /// notice), say so. Not counted either way: there is no evidence the person used another app.
    private func checkLaunchOnce(now: Date) {
        guard !checkedLaunch else { return }
        checkedLaunch = true
        guard store.frontAbsence == nil, store.phase(at: now) == .active,
              let seen = store.frontSeenAt, let applied = store.appliedAt, seen >= applied,
              now.timeIntervalSince(seen) > 3 * QuietConstants.frontHeartbeatInterval else { return }
        if let boot = DeviceSignals.bootTime, boot > seen {
            store.frontRestarts += 1
            store.log("front: phone restarted while Quiet Hours was in front (last seen \(QuietHoursEngine.time(seen))): not counted")
        } else {
            store.frontStops += 1
            store.log("front: Quiet Hours stopped while in front (last seen \(QuietHoursEngine.time(seen))): not counted")
        }
    }

    private func startHeartbeat() {
        heartbeatTask?.cancel()
        heartbeatTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(QuietConstants.frontHeartbeatInterval))
                guard !Task.isCancelled, let self else { return }
                if self.store.window != nil { self.store.frontSeenAt = Date() }
                self.onChange?()
            }
        }
    }

    private func stopHeartbeat() {
        heartbeatTask?.cancel()
        heartbeatTask = nil
    }

    // MARK: Background time

    private func beginBackgroundTask() {
        guard backgroundTask == .invalid else { return }
        backgroundTask = UIApplication.shared.beginBackgroundTask(withName: "QuietHours.front") { [weak self] in
            guard let self else { return }
            let undecided = self.store.frontAbsence?.reason == .undecided
            self.store.log("front: background time ran out\(undecided ? " before deciding" : "")")
            // A decision made after a resume would judge the phone as it is then, not as it was
            // when Quiet Hours left the front. Leave it to `settle`, which uses stored facts.
            self.cancelDecision()
            // Must end before this handler returns, or iOS ends the app.
            self.endBackgroundTask(immediately: true)
        }
        if backgroundTask == .invalid {
            store.log("front: iOS gave no background time; deciding later from stored facts")
            cancelDecision()
        }
    }

    /// Ends the current background task once queued notification work has been handed to iOS,
    /// so a cancel is never left waiting in a suspended app. `immediately` is for the expiration
    /// handler, which must end it before returning.
    private func endBackgroundTask(immediately: Bool = false) {
        guard backgroundTask != .invalid else { return }
        let task = backgroundTask
        backgroundTask = .invalid
        if immediately {
            UIApplication.shared.endBackgroundTask(task)
            return
        }
        let pending = notificationChain
        Task {
            await pending?.value
            UIApplication.shared.endBackgroundTask(task)
        }
    }

    private func cancelDecision() {
        decisionTask?.cancel()
        decisionTask = nil
    }

    private func resetInFlightWork() {
        cancelDecision()
        endBackgroundTask()
        cancelSteppedOutNotification()
    }

    // MARK: Notification

    private func scheduleSteppedOutNotification(since: Date) {
        let request = SteppedOutNotification.request(since: since)
        enqueueNotificationWork {
            do {
                try await UNUserNotificationCenter.current().add(request)
            } catch {
                QuietStore().log("front: could not queue the stepped-out notification: \(error.localizedDescription)")
            }
        }
    }

    private func cancelSteppedOutNotification() {
        enqueueNotificationWork { SteppedOutNotification.remove() }
    }

    private func enqueueNotificationWork(_ work: @escaping () async -> Void) {
        let previous = notificationChain
        notificationChain = Task {
            await previous?.value
            await work()
        }
    }

    // MARK: State

    func fill(_ state: inout QuietState, now: Date) {
        state.access = access
        state.accessDetail = accessDetail
        state.usesAppPicker = false
        state.lockScope = nil
        state.isReadyToSchedule = true
        state.backBy = store.frontBackBy(at: now)
        switch lockSignal {
        case .reliable: state.setupWarning = nil
        case .uncertain: state.setupWarning = "Without Face ID or Touch ID, locking the phone may count as stepping out. Turn on Face ID or Touch ID, or set Require Passcode to Immediately."
        case .unavailable: state.setupWarning = "With no passcode, locking the phone counts as stepping out. Set a passcode."
        }

        let away: String
        if let absence = store.frontAbsence {
            var line = "\(absence.reason.rawValue) since \(QuietHoursEngine.time(absence.since))"
            if let backBy = store.frontBackBy(at: now) { line += ", back by \(QuietHoursEngine.time(backBy))" }
            away = line
        } else {
            away = "no"
        }
        state.details = [
            QuietDetail(label: "Grace period", value: "\(Int(QuietConstants.frontGracePeriod)) s"),
            QuietDetail(label: "Lock signal", value: lockSignal.description),
            QuietDetail(label: "Protected data now", value: UIApplication.shared.isProtectedDataAvailable ? "available" : "unavailable"),
            QuietDetail(label: "Away", value: away),
            QuietDetail(label: "Last seen in front", value: store.frontSeenAt.map(QuietHoursEngine.time) ?? "-"),
            QuietDetail(label: "Not counted: lock / call / restart / stop",
                        value: "\(store.frontLocks) / \(store.frontCalls) / \(store.frontRestarts) / \(store.frontStops)"),
            QuietDetail(label: "Call in progress", value: callInProgress ? "yes" : "no"),
        ]
    }

    // MARK: Copy

    static func preStartBody(startTime: String) -> String {
        "Starting at \(startTime). Open Quiet Hours then and leave it in front."
    }

    static var startAlertBody: String { "Quiet hours have started. Open Quiet Hours and leave it in front." }

    nonisolated static func duration(_ seconds: TimeInterval) -> String {
        Duration.seconds(max(0, seconds.rounded())).formatted(.units(allowed: [.minutes, .seconds], width: .narrow))
    }
}

extension FrontLock: CXCallObserverDelegate {
    nonisolated func callObserver(_ callObserver: CXCallObserver, callChanged call: CXCall) {
        // Delegate queue is nil, so this arrives on the main queue.
        MainActor.assumeIsolated { self.callsChanged() }
    }
}
