import Foundation
import ManagedSettings

/// Lock operations shared by the app and the extensions. Every function reads the current
/// window from shared storage and decides for itself whether it applies, so a late or
/// duplicate callback from any process is harmless.
enum QuietCore {

    static var managedStore: ManagedSettingsStore {
        ManagedSettingsStore(named: ManagedSettingsStore.Name(QuietConstants.managedStoreName))
    }

    // MARK: Shield

    static func applyShield(_ targets: LockTargets) {
        let store = managedStore
        switch targets.scope {
        case .selected:
            store.shield.applications = targets.applications.isEmpty ? nil : targets.applications
            store.shield.applicationCategories = targets.categories.isEmpty ? nil : .specific(targets.categories)
            store.shield.webDomains = targets.webDomains.isEmpty ? nil : targets.webDomains
            store.shield.webDomainCategories = targets.categories.isEmpty ? nil : .specific(targets.categories)
        case .allExcept:
            // Total lock. Everything in one store: Apple staff say one store can't make another
            // less restrictive, so the exceptions must sit with the `.all`. Apple exempts this
            // app itself, and iOS keeps some system apps open regardless (LOCK-NOTES.md).
            store.shield.applications = nil
            store.shield.applicationCategories = .all(except: targets.applications)
            store.shield.webDomains = nil
            store.shield.webDomainCategories = .all(except: targets.webDomains)
        }
    }

    static func clearShield() {
        managedStore.clearAllSettings()
    }

    /// Whether our ManagedSettings store currently carries a shield, as the system reports it.
    static var isShieldSet: Bool {
        let shield = managedStore.shield
        return shield.applications != nil
            || shield.applicationCategories != nil
            || shield.webDomains != nil
            || shield.webDomainCategories != nil
    }

    /// iOS 26.5 can expire stored tokens. Refreshes them in place and saves them if anything
    /// changed. Returns true if the tokens changed. A no-op before iOS 26.5.
    @discardableResult
    static func refreshStoredTokens(source: String) -> Bool {
        guard #available(iOS 26.5, *) else { return false }
        let store = QuietStore()
        let before = store.targets
        guard !before.isEmpty else { return false }
        var apps = Array(before.applications)
        var categories = Array(before.categories)
        var domains = Array(before.webDomains)
        do {
            if !apps.isEmpty { try ManagedSettingsStore.refresh(&apps) }
            if !categories.isEmpty { try ManagedSettingsStore.refresh(&categories) }
            if !domains.isEmpty { try ManagedSettingsStore.refresh(&domains) }
        } catch {
            store.log("\(source): token refresh failed: \(error.localizedDescription)")
            return false
        }
        let after = LockTargets(scope: before.scope, applications: Set(apps), categories: Set(categories),
                                webDomains: Set(domains))
        guard after != before else { return false }
        store.targets = after
        store.log("\(source): refreshed expired tokens")
        return true
    }

    // MARK: Window transitions

    /// Applies the lock if a window is in progress, nobody has left, and it has not ended.
    @discardableResult
    static func beginIfDue(source: String, now: Date = Date()) -> Bool {
        let store = QuietStore()
        guard let window = store.window else {
            store.log("\(source): no window stored, nothing to lock")
            return false
        }
        guard now >= window.start.addingTimeInterval(-QuietConstants.boundaryTolerance), now < window.end else {
            store.log("\(source): outside the window, not locking")
            return false
        }
        guard store.leftAt == nil, store.clearedAt == nil else {
            store.log("\(source): window already left or ended, not locking")
            return false
        }
        refreshStoredTokens(source: source)
        let targets = store.targets
        guard targets.locksSomething else {
            store.log("\(source): nothing selected, not locking")
            return false
        }
        applyShield(targets)
        if store.appliedAt == nil {
            store.appliedAt = now
            store.appliedBy = source
        }
        store.log("\(source): lock applied (\(targets.summary))")
        return true
    }

    /// Removes the lock at the end of the window.
    @discardableResult
    static func endWindow(source: String, now: Date = Date()) -> Bool {
        let store = QuietStore()
        guard store.window != nil else { return false }
        clearShield()
        if store.clearedAt == nil {
            store.clearedAt = now
            store.clearedBy = source
        }
        store.log("\(source): lock removed, window over")
        return true
    }

    /// Leave early: removes the lock for the rest of the window and records the time.
    @discardableResult
    static func leaveEarly(source: String, now: Date = Date()) -> Bool {
        let store = QuietStore()
        guard let window = store.window else {
            store.log("\(source): leave pressed with no window")
            clearShield()
            return false
        }
        guard now >= window.start.addingTimeInterval(-QuietConstants.boundaryTolerance) else {
            store.log("\(source): leave pressed before the window started, ignored")
            return false
        }
        clearShield()
        guard store.leftAt == nil, store.clearedAt == nil, now < window.end else {
            store.log("\(source): leave pressed after leaving or ending; lock cleared again")
            return false
        }
        store.leftAt = now
        store.clearedAt = now
        store.clearedBy = "\(source) (left)"
        store.log("\(source): LEFT EARLY, lock removed for the rest of the window")
        return true
    }

    // MARK: Counters

    /// Called each time the system asks the shield extension to draw a shield.
    /// Counts a reach unless the previous request was less than `reachMergeInterval` ago.
    static func recordShieldRequest(now: Date = Date()) {
        let store = QuietStore()
        store.shieldRequests += 1
        let previous = store.reachLastRequestAt
        store.reachLastRequestAt = now
        let phase = store.phase(at: now)
        guard phase == .active || phase == .due else { return }
        if let previous, now.timeIntervalSince(previous) < QuietConstants.reachMergeInterval { return }
        store.reachCount += 1
    }

    static func recordStay() {
        let store = QuietStore()
        store.stayPresses += 1
        store.log("shield: Stay pressed")
    }
}
