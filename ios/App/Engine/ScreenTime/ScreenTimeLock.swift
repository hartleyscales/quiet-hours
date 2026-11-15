import DeviceActivity
import FamilyControls
import Foundation
import ManagedSettings

/// Screen Time mode: Apple's Screen Time frameworks shield the chosen apps. The extensions do
/// the real work at the window's boundaries; this class schedules them and covers what they
/// might miss while the app is open.
@MainActor
final class ScreenTimeLock: LockBackend {
    var onChange: (() -> Void)?

    /// What Apple's picker last returned. Kept for the picker; extensions read `store.targets`.
    private(set) var selection: FamilyActivitySelection

    private let store = QuietStore()
    private let center = DeviceActivityCenter()

    init() {
        selection = FamilyActivitySelection()
        selection = loadSelection()
    }

    // MARK: Access

    var access: QuietAccess {
        switch AuthorizationCenter.shared.authorizationStatus {
        case .notDetermined: return .notDetermined
        case .denied: return .denied
        default: return .approved   // .approved, and .approvedWithDataAccess (iOS 26.4)
        }
    }

    var accessDetail: String { "Screen Time \(AuthorizationCenter.shared.authorizationStatus)" }

    func requestAccess() async throws {
        do {
            try await AuthorizationCenter.shared.requestAuthorization(for: .individual)
            store.log("app: Screen Time authorization is \(AuthorizationCenter.shared.authorizationStatus)")
        } catch {
            store.log("app: Screen Time authorization failed: \(error.localizedDescription)")
            throw error
        }
    }

    // MARK: Selection

    /// Saves what Apple's picker returned. Extensions read the tokens from shared storage.
    func updateSelection(_ newSelection: FamilyActivitySelection) {
        guard newSelection != selection else { return }
        selection = newSelection
        store.pickerSelectionData = try? JSONEncoder().encode(newSelection)
        var targets = store.targets
        targets.applications = newSelection.applicationTokens
        targets.categories = newSelection.categoryTokens
        targets.webDomains = newSelection.webDomainTokens
        store.targets = targets
        store.log("app: selection saved (\(targets.summary))")
        reapplyIfActive(targets)
    }

    /// Changing the scope clears the picks: the same picks mean opposite things under the two
    /// scopes ("lock Instagram" would become "leave Instagram open").
    func setLockScope(_ scope: LockScope) {
        guard store.targets.scope != scope else { return }
        let targets = LockTargets(scope: scope)
        store.targets = targets
        selection = FamilyActivitySelection(includeEntireCategory: scope == .allExcept)
        store.pickerSelectionData = try? JSONEncoder().encode(selection)
        store.log("app: lock scope is now \(scope.rawValue); picks cleared, choose again")
        reapplyIfActive(targets)
    }

    /// A lock that is already on picks up changes immediately, unless they break Apple's
    /// limits (reportedly that shields nothing at all), in which case the old lock stays.
    private func reapplyIfActive(_ targets: LockTargets) {
        if let problem = targets.tokenLimitProblem {
            store.log("app: WARNING \(problem) Not applied.")
            return
        }
        if store.phase() == .active { QuietCore.applyShield(targets) }
    }

    /// The selection to open Apple's picker with. Under "lock everything except", a whole
    /// category ticked in the picker should leave its apps open, and `.all(except:)` takes only
    /// app tokens, so the selection must include each picked category's apps
    /// (`includeEntireCategory: true`). Under "lock what I pick" categories are shielded as
    /// categories, so it stays off (and app tokens stay under Apple's limit of 50).
    func pickerStartingSelection() -> FamilyActivitySelection {
        let wantsWholeCategories = store.targets.scope == .allExcept
        guard selection.includeEntireCategory != wantsWholeCategories else { return selection }
        var rebuilt = FamilyActivitySelection(includeEntireCategory: wantsWholeCategories)
        rebuilt.applicationTokens = selection.applicationTokens
        rebuilt.categoryTokens = selection.categoryTokens
        rebuilt.webDomainTokens = selection.webDomainTokens
        return rebuilt
    }

    // MARK: Window

    func checkReadyToSchedule() throws {
        guard access == .approved else { throw QuietEngineError.notAuthorized }
        let targets = store.targets
        guard targets.locksSomething else { throw QuietEngineError.nothingSelected }
        if let problem = targets.tokenLimitProblem { throw QuietEngineError.tooManyTokens(problem) }
    }

    func monitoredEnd(start: Date, end: Date) -> Date {
        WindowSchedule.monitoredEnd(start: start, end: end)
    }

    func startEnforcing(_ window: QuietWindow) throws {
        QuietCore.clearShield()
        do {
            try center.startMonitoring(WindowSchedule.activityName, during: WindowSchedule.make(for: window))
        } catch {
            store.log("app: DeviceActivity refused the schedule: \(error.localizedDescription)")
            throw QuietEngineError.monitoring(error.localizedDescription)
        }
        if window.isPadded {
            store.log("app: shorter than 15 min, monitored until \(QuietHoursEngine.time(window.monitoredEnd)); ends early via warning")
        }
        if let interval = center.schedule(for: WindowSchedule.activityName)?.nextInterval {
            store.log("app: DeviceActivity will monitor \(QuietHoursEngine.time(interval.start))–\(QuietHoursEngine.time(interval.end))")
        } else {
            store.log("app: DeviceActivity reports no upcoming interval")
        }
    }

    func stopEnforcing() {
        center.stopMonitoring([WindowSchedule.activityName])
        QuietCore.clearShield()
    }

    func leaveEarly(now: Date) -> Bool {
        QuietCore.leaveEarly(source: "app", now: now)
    }

    // MARK: Lifecycle

    func didBecomeActive() async {
        guard QuietCore.refreshStoredTokens(source: "app") else { return }
        let targets = store.targets
        var refreshed = selection
        refreshed.applicationTokens = targets.applications
        refreshed.categoryTokens = targets.categories
        refreshed.webDomainTokens = targets.webDomains
        selection = refreshed
        store.pickerSelectionData = try? JSONEncoder().encode(refreshed)
        if store.phase() == .active { QuietCore.applyShield(targets) }
    }

    /// The extensions do the real work. This covers what they might miss while the app is open:
    /// a lock not yet applied inside the window, or still on after it.
    func reconcile(now: Date) {
        switch store.phase(at: now) {
        case .due:
            if access == .approved, store.targets.locksSomething {
                QuietCore.beginIfDue(source: "app", now: now)
            }
        case .ended:
            if store.clearedAt == nil {
                QuietCore.endWindow(source: "app", now: now)
            } else if QuietCore.isShieldSet {
                QuietCore.clearShield()
                store.log("app: lock was still on after the window, removed")
            }
        case .left:
            if QuietCore.isShieldSet {
                QuietCore.clearShield()
                store.log("app: lock was still on after leaving, removed")
            }
        case .none, .scheduled, .active, .steppedOut:
            break
        }
    }

    // MARK: State

    func fill(_ state: inout QuietState, now: Date) {
        let targets = store.targets
        state.access = access
        state.accessDetail = accessDetail
        state.usesAppPicker = true
        state.lockScope = targets.scope
        state.selectedApplications = targets.applications.count
        state.selectedCategories = targets.categories.count
        state.selectedWebDomains = targets.webDomains.count
        state.isReadyToSchedule = (try? checkReadyToSchedule()) != nil
        state.setupWarning = targets.tokenLimitProblem
        let interval = center.schedule(for: WindowSchedule.activityName)?.nextInterval
        state.details = [
            QuietDetail(label: "Shield set (system)", value: QuietCore.isShieldSet ? "yes" : "no"),
            QuietDetail(label: "Shield draw requests (raw)", value: "\(store.shieldRequests)"),
            QuietDetail(label: "DeviceActivity monitoring",
                        value: center.activities.contains(WindowSchedule.activityName) ? "yes" : "no"),
            QuietDetail(label: "Monitored interval", value: interval.map {
                "\(QuietHoursEngine.time($0.start)) – \(QuietHoursEngine.time($0.end))"
            } ?? "-"),
        ]
    }

    // MARK: Copy

    static func preStartBody(startTime: String) -> String { "Starting at \(startTime)." }
    static var startAlertBody: String { "Quiet hours have started." }

    // MARK: Helpers

    private func loadSelection() -> FamilyActivitySelection {
        guard let data = store.pickerSelectionData,
              let saved = try? JSONDecoder().decode(FamilyActivitySelection.self, from: data) else {
            return FamilyActivitySelection(includeEntireCategory: store.targets.scope == .allExcept)
        }
        return saved
    }
}

/// Screen Time mode extras on the engine, for a UI that drives Apple's picker itself.
extension QuietHoursEngine {
    /// What Apple's picker last returned.
    var selection: FamilyActivitySelection { lock.selection }

    /// Saves what Apple's picker returned. What the picks mean depends on `state.lockScope`.
    func updateSelection(_ newSelection: FamilyActivitySelection) {
        lock.updateSelection(newSelection)
        refresh()
    }

    /// The selection to bind Apple's picker to before presenting it.
    func pickerStartingSelection() -> FamilyActivitySelection {
        lock.pickerStartingSelection()
    }
}
