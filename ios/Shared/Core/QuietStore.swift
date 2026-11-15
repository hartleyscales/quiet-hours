import Foundation

/// Shared storage for the app and its extensions: the App Group's UserDefaults suite.
///
/// Each fact has its own key, so two processes that write different facts (the monitor writing
/// "applied at", the shield writing the reach count) never overwrite each other's values.
/// Read-modify-write on a single key (the counters) is not atomic across processes; in practice
/// only one process writes each counter.
struct QuietStore {
    enum Key {
        static let pickerSelection = "selection.picker"      // Screen Time: FamilyActivitySelection JSON (app only)
        static let targets = "selection.targets"             // Screen Time: LockTargets JSON
        static let window = "window"                         // QuietWindow JSON
        static let appliedAt = "lock.appliedAt"
        static let appliedBy = "lock.appliedBy"
        static let clearedAt = "lock.clearedAt"
        static let clearedBy = "lock.clearedBy"
        static let leftAt = "lock.leftAt"
        static let reachCount = "reach.count"
        static let reachLastRequestAt = "reach.lastRequestAt"
        static let shieldRequests = "reach.shieldRequests"
        static let stayPresses = "stay.count"
        /// The number of people in quiet hours, written by the app, read by the shield.
        /// Placeholder path: nothing writes it yet except the debug screen.
        static let peopleCount = "people.count"
        static let peopleCountUpdatedAt = "people.updatedAt"
        static let leaveOpensApp = "shield.leaveOpensApp"
        static let log = "log"
        // Front mode. Written by the app only.
        static let frontAbsence = "front.absence"            // FrontAbsenceRecord JSON
        static let frontSeenAt = "front.seenAt"              // last heartbeat while in front
        static let frontLocks = "front.locks"                // absences excused as a lock
        static let frontCalls = "front.calls"                // ... as a call
        static let frontRestarts = "front.restarts"          // ... as a restart
        static let frontStops = "front.stops"                // app stopped in front without notice
    }

    let defaults: UserDefaults

    init() {
        // UserDefaults(suiteName:) only returns nil for reserved names, never for an App Group id.
        defaults = UserDefaults(suiteName: QuietConstants.appGroup) ?? .standard
    }

    // MARK: Selection (Screen Time mode; `targets` is in Shared/ScreenTime/LockTargets.swift)

    var pickerSelectionData: Data? {
        get { defaults.data(forKey: Key.pickerSelection) }
        nonmutating set { defaults.set(newValue, forKey: Key.pickerSelection) }
    }

    // MARK: Window

    var window: QuietWindow? {
        get { decode(QuietWindow.self, Key.window) }
        nonmutating set {
            if let newValue { encode(newValue, Key.window) } else { defaults.removeObject(forKey: Key.window) }
        }
    }

    var appliedAt: Date? {
        get { date(Key.appliedAt) }
        nonmutating set { setDate(newValue, Key.appliedAt) }
    }
    var appliedBy: String? {
        get { defaults.string(forKey: Key.appliedBy) }
        nonmutating set { defaults.set(newValue, forKey: Key.appliedBy) }
    }
    var clearedAt: Date? {
        get { date(Key.clearedAt) }
        nonmutating set { setDate(newValue, Key.clearedAt) }
    }
    var clearedBy: String? {
        get { defaults.string(forKey: Key.clearedBy) }
        nonmutating set { defaults.set(newValue, forKey: Key.clearedBy) }
    }
    var leftAt: Date? {
        get { date(Key.leftAt) }
        nonmutating set { setDate(newValue, Key.leftAt) }
    }

    // MARK: Counters

    var reachCount: Int {
        get { defaults.integer(forKey: Key.reachCount) }
        nonmutating set { defaults.set(newValue, forKey: Key.reachCount) }
    }
    var reachLastRequestAt: Date? {
        get { date(Key.reachLastRequestAt) }
        nonmutating set { setDate(newValue, Key.reachLastRequestAt) }
    }
    var shieldRequests: Int {
        get { defaults.integer(forKey: Key.shieldRequests) }
        nonmutating set { defaults.set(newValue, forKey: Key.shieldRequests) }
    }
    var stayPresses: Int {
        get { defaults.integer(forKey: Key.stayPresses) }
        nonmutating set { defaults.set(newValue, forKey: Key.stayPresses) }
    }

    // MARK: People count (placeholder path)

    var peopleCount: Int? {
        get { defaults.object(forKey: Key.peopleCount) as? Int }
        nonmutating set {
            defaults.set(newValue, forKey: Key.peopleCount)
            setDate(newValue == nil ? nil : Date(), Key.peopleCountUpdatedAt)
        }
    }
    var peopleCountUpdatedAt: Date? { date(Key.peopleCountUpdatedAt) }

    // MARK: Options

    /// When true, on iOS 26.5 and later, "Leave quiet hours" opens the app after removing the lock.
    var leaveOpensApp: Bool {
        get { defaults.bool(forKey: Key.leaveOpensApp) }
        nonmutating set { defaults.set(newValue, forKey: Key.leaveOpensApp) }
    }

    // MARK: Front mode

    var frontAbsence: FrontAbsenceRecord? {
        get { decode(FrontAbsenceRecord.self, Key.frontAbsence) }
        nonmutating set {
            if let newValue { encode(newValue, Key.frontAbsence) } else { defaults.removeObject(forKey: Key.frontAbsence) }
        }
    }
    var frontSeenAt: Date? {
        get { date(Key.frontSeenAt) }
        nonmutating set { setDate(newValue, Key.frontSeenAt) }
    }
    var frontLocks: Int {
        get { defaults.integer(forKey: Key.frontLocks) }
        nonmutating set { defaults.set(newValue, forKey: Key.frontLocks) }
    }
    var frontCalls: Int {
        get { defaults.integer(forKey: Key.frontCalls) }
        nonmutating set { defaults.set(newValue, forKey: Key.frontCalls) }
    }
    var frontRestarts: Int {
        get { defaults.integer(forKey: Key.frontRestarts) }
        nonmutating set { defaults.set(newValue, forKey: Key.frontRestarts) }
    }
    var frontStops: Int {
        get { defaults.integer(forKey: Key.frontStops) }
        nonmutating set { defaults.set(newValue, forKey: Key.frontStops) }
    }

    /// Front mode: the time the person must be back in Quiet Hours by, if they are out and it
    /// counts. An undecided absence counts once the stepped-out notification has gone out
    /// (`frontNotificationDelay` after leaving), because the app may have been suspended or
    /// killed before it could decide; the app settles it on its next run.
    func frontBackBy(at now: Date) -> Date? {
        guard let absence = frontAbsence else { return nil }
        switch absence.reason {
        case .out:
            return absence.backBy
        case .undecided where now >= absence.since.addingTimeInterval(QuietConstants.frontNotificationDelay):
            return absence.backBy
        case .undecided, .lock, .call, .restart:
            return nil
        }
    }

    // MARK: Per-window record

    /// Forget everything recorded about the previous window. Called when a new window is scheduled.
    func resetWindowRecord() {
        for key in [Key.appliedAt, Key.appliedBy, Key.clearedAt, Key.clearedBy, Key.leftAt,
                    Key.reachCount, Key.reachLastRequestAt, Key.shieldRequests, Key.stayPresses,
                    Key.frontAbsence, Key.frontSeenAt, Key.frontLocks, Key.frontCalls,
                    Key.frontRestarts, Key.frontStops] {
            defaults.removeObject(forKey: key)
        }
    }

    /// The phase, from stored values only. Screen Time mode never writes the front-mode keys,
    /// so the front-mode lines are inert there.
    func phase(at now: Date = Date()) -> WindowPhase {
        guard let window else { return .none }
        if leftAt != nil { return .left }
        let backBy = frontBackBy(at: now)
        // Front mode: out past the grace period, and the window had not ended by then. The app
        // writes `leftAt` the next time it runs; until then the phase is derived.
        if let backBy, backBy < window.end, now >= backBy { return .left }
        if clearedAt != nil || now >= window.end { return .ended }
        if now < window.start { return .scheduled }
        if appliedAt == nil { return .due }
        return backBy == nil ? .active : .steppedOut
    }

    // MARK: Event log

    /// Appends a timestamped line to the shared log the debug screen shows.
    func log(_ message: String, at now: Date = Date()) {
        let stamp = now.formatted(.dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits).second(.twoDigits))
        var lines = defaults.stringArray(forKey: Key.log) ?? []
        lines.append("\(stamp)  \(message)")
        if lines.count > QuietConstants.logCapacity { lines.removeFirst(lines.count - QuietConstants.logCapacity) }
        defaults.set(lines, forKey: Key.log)
    }

    var logLines: [String] { defaults.stringArray(forKey: Key.log) ?? [] }

    func clearLog() { defaults.removeObject(forKey: Key.log) }

    // MARK: Helpers

    private func date(_ key: String) -> Date? {
        guard let seconds = defaults.object(forKey: key) as? Double else { return nil }
        return Date(timeIntervalSince1970: seconds)
    }

    private func setDate(_ date: Date?, _ key: String) {
        if let date { defaults.set(date.timeIntervalSince1970, forKey: key) } else { defaults.removeObject(forKey: key) }
    }

    func decode<T: Decodable>(_ type: T.Type, _ key: String) -> T? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(type, from: data)
    }

    func encode<T: Encodable>(_ value: T, _ key: String) {
        defaults.set(try? JSONEncoder().encode(value), forKey: key)
    }
}
