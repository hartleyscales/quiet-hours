import Foundation
import Observation
import SwiftUI

/// Which designed screen shows (docs/WEB-BRIEF.md, "Which screen shows when").
enum Screen: Equatable {
    case signIn
    case howItWorks
    case allowLock
    /// Signed in, nothing from the server yet (or it could not be reached).
    case loading
    /// Signed in, but no week's vote has opened yet.
    case noWeek
    case voting(out: Bool)
    case selected(out: Bool)
    case day(out: Bool)
    case locked(out: Bool)
    case question
    case summaryBefore
    case summary(out: Bool)
}

/// The app's one model: who is signed in, the server's state, the board, and keeping the lock
/// engine in step with the server. Every number, time, option and post shown comes from here.
@MainActor
@Observable
final class AppModel {
    // MARK: Session

    private(set) var token: String? = Keychain.get(Keychain.tokenKey)
    private(set) var email: String? = Keychain.get(Keychain.emailKey)
    var isSignedIn: Bool { token != nil }

    /// "How it works" and "The lock" have been seen on this device.
    private(set) var onboarded = UserDefaults.standard.bool(forKey: Keys.onboarded)
    /// Inside onboarding: "How it works" done, "The lock" showing.
    private(set) var onboardingAtLock = false
    /// "How it works" replayed from settings: it shows until its last step, then the Home again.
    private(set) var replayingIntro = false

    // MARK: Server state

    private(set) var state: AppState?
    /// Server clock minus this phone's, at the last state read.
    private var clockOffset: TimeInterval = 0
    private(set) var posts: [BoardPost] = []
    /// One quiet line for loading and errors, shown in place of the screen's small line.
    private(set) var notice: String?
    private(set) var reachable = true

    /// A vote just tapped, shown while the call is in flight.
    private(set) var pendingVote: String?
    /// The server refused "Join until": show the screen without the button.
    private(set) var rejoinRefused: Set<String> = []
    private(set) var busy = false

    @ObservationIgnored private let engine = QuietHoursEngine.shared

    init() {
        if let token = DebugLaunch.token {
            Keychain.set(token, for: Keychain.tokenKey)
            self.token = token
            if let email = DebugLaunch.email {
                Keychain.set(email, for: Keychain.emailKey)
                self.email = email
            }
        }
        if let onboarded = DebugLaunch.onboarded {
            self.onboarded = onboarded
            UserDefaults.standard.set(onboarded, forKey: Keys.onboarded)
        }
        if DebugLaunch.onboardingAtLock {
            onboarded = false
            onboardingAtLock = true
        }
    }
    @ObservationIgnored private var lastBoardFetch: Date = .distantPast
    @ObservationIgnored private var noticeTask: Task<Void, Never>?
    @ObservationIgnored private var refreshing = false

    private enum Keys {
        static let onboarded = "qh.onboarded"
        static let lineSkipped = "qh.lineSkipped"          // [weekId]
        static let reportedLeave = "qh.reportedLeave"      // [weekId: leftAt seconds]
        static let reportedReaches = "qh.reportedReaches"  // [weekId: count]
        static let reachBase = "qh.reachBase"              // [weekId: count carried over a reschedule]
    }

    /// The server's "now".
    var now: Date { Date().addingTimeInterval(clockOffset) }

    // MARK: Which screen

    var screen: Screen {
        guard isSignedIn else { return .signIn }
        if !onboarded { return onboardingAtLock ? .allowLock : .howItWorks }
        if replayingIntro { return .howItWorks }
        guard let state else { return .loading }
        guard let phase = state.phase, state.week != nil else { return .noWeek }
        let status = state.me?.status
        switch phase {
        case .vote:
            return .voting(out: status == .skipped)
        case .decided:
            return state.board?.open == true ? .day(out: status == .skipped) : .selected(out: status == .skipped)
        case .live:
            return .locked(out: status != .in)
        case .ended:
            if let me = state.me, me.can.writeLine, !me.wroteLine, !lineSkipped { return .question }
            return .summaryBefore
        case .told:
            guard let recap = state.recap, !recap.highlights.isEmpty || recap.stats != nil else { return .summaryBefore }
            return .summary(out: status == .skipped || status == nil)
        }
    }

    /// True while the Locked screen shows (the status bar goes light).
    var isNight: Bool {
        if case .locked = screen { return true }
        return false
    }

    // MARK: Sign in

    func startSignIn(email: String) async throws -> StartResponse {
        try await APIClient(token: nil).startSignIn(email: email)
    }

    /// Checks a sign-in code. The session starts with `adopt(_:)`, which the sign-in screen calls
    /// once its keyboard is down, so the change of screen starts from a screen at rest.
    func checkCode(email: String, code: String) async throws -> VerifyResponse {
        try await APIClient(token: nil).verify(email: email, code: code)
    }

    func adopt(_ result: VerifyResponse) async {
        Keychain.set(result.token, for: Keychain.tokenKey)
        Keychain.set(result.user.email, for: Keychain.emailKey)
        token = result.token
        self.email = result.user.email
        state = nil
        await refresh()
    }

    func signOut() async {
        let client = api
        replayingIntro = false
        token = nil
        email = nil
        state = nil
        posts = []
        Keychain.set(nil, for: Keychain.tokenKey)
        Keychain.set(nil, for: Keychain.emailKey)
        try? await client.signOut()
    }

    // MARK: Onboarding

    /// "How it works" pressed through to its end: onboarding moves on to The lock, or a replay
    /// from settings returns to where the person was.
    func finishHowItWorks() {
        if replayingIntro {
            replayingIntro = false
        } else {
            onboardingAtLock = true
        }
    }

    /// Settings' "How it works": the three intro steps again.
    func replayIntro() {
        guard onboarded else { return }
        replayingIntro = true
    }

    /// "Allow the lock": the engine's authorization, then notifications. The caller presents
    /// Apple's picker afterwards when `engine.state.usesAppPicker`.
    func allowLock() async -> Bool {
        do {
            try await engine.requestAuthorization()
        } catch {
            say("Screen Time access wasn't given. Try again.")
            return false
        }
        await engine.requestNotificationPermission()
        return true
    }

    func finishOnboarding() {
        onboarded = true
        onboardingAtLock = false
        UserDefaults.standard.set(true, forKey: Keys.onboarded)
        Task { await refresh() }
    }

    // MARK: Refresh

    private var api: APIClient { APIClient(token: token) }

    /// Reads `/v1/state` (and the board when it is open), then brings the lock in step.
    func refresh() async {
        guard isSignedIn, !refreshing else { return }
        refreshing = true
        defer { refreshing = false }
        do {
            let asked = Date()
            let fresh = try await api.state()
            clockOffset = fresh.serverTime.timeIntervalSince(asked)
            if fresh != state { state = fresh }
            reachable = true
            if noticeIsConnection { notice = nil }
            if fresh.board?.open == true {
                await loadBoard()
            } else if !posts.isEmpty {
                posts = []
            }
            await syncEngine()
        } catch let error as APIError {
            handle(error)
        } catch {}
    }

    func loadBoard(force: Bool = false) async {
        guard isSignedIn, force || Date().timeIntervalSince(lastBoardFetch) > 15 else { return }
        do {
            let board = try await api.board()
            lastBoardFetch = Date()
            let ordered = board.posts.filter(\.mine) + board.posts.filter { !$0.mine }
            if ordered != posts { posts = ordered }
        } catch let error as APIError {
            handle(error)
        } catch {}
    }

    /// Seconds until the next poll: sooner when the screen is about to change by itself.
    var pollInterval: TimeInterval {
        if DebugLaunch.fastPoll { return 2 }
        var interval: TimeInterval = state?.phase == .live ? 10 : 20
        if let next = state?.nextChangeAt {
            interval = min(interval, max(1, next.timeIntervalSince(now) + 0.5))
        }
        return reachable ? interval : 5
    }

    /// Runs while the app is in front: polls the server and watches the engine.
    func run() async {
        await refresh()
        var sinceRefresh: TimeInterval = 0
        while !Task.isCancelled {
            try? await Task.sleep(for: .seconds(1))
            sinceRefresh += 1
            engine.refresh()
            await reportEngine()
            if sinceRefresh >= pollInterval {
                sinceRefresh = 0
                await refresh()
            }
        }
    }

    func becameActive() async {
        await engine.didBecomeActive()
        await refresh()
    }

    // MARK: Actions

    func vote(_ option: VoteOption) async {
        guard let week = state?.week, state?.me?.can.vote == true else { return }
        pendingVote = option.id
        defer { pendingVote = nil }
        do {
            _ = try await api.vote(optionId: option.id, weekId: week.id)
            await refresh()
        } catch let error as APIError {
            handle(error)
            await refresh()
        } catch {}
    }

    func optOut() async {
        guard let week = state?.week else { return }
        await perform { _ = try await $0.skip(weekId: week.id) }
    }

    func optBackIn() async {
        guard let week = state?.week else { return }
        await perform { _ = try await $0.rejoin(weekId: week.id) }
    }

    /// "Leave quiet hours": the engine removes the lock and records the time; the server hears.
    func leave() async {
        guard let week = state?.week else { return }
        busy = true
        defer { busy = false }
        let left = await engine.leaveEarly()
        let leftAt = left ? engine.state.leftAt : now
        do {
            _ = try await api.leave(weekId: week.id, leftAt: leftAt)
            if let leftAt { markLeaveReported(week.id, leftAt) }
        } catch let error as APIError {
            handle(error)
        } catch {}
        await refresh()
    }

    /// "Join until H:MM": back in for the rest of the window, enforced by the engine.
    func join() async {
        guard let week = state?.week else { return }
        busy = true
        defer { busy = false }
        do {
            let result = try await api.rejoin(weekId: week.id)
            if result.me.status == .in, let start = week.startsAt, let end = week.endsAt {
                await schedule(weekId: week.id, start: start, end: end)
            } else {
                rejoinRefused.insert(week.id)
            }
        } catch let error as APIError {
            if error.code != "network" { rejoinRefused.insert(week.id) }
            handle(error)
        } catch {}
        await refresh()
    }

    /// Posts to the board. Returns nil when it went up, or the reason it did not.
    func post(text: String, place: String) async -> String? {
        guard let week = state?.week else { return nil }
        do {
            _ = try await api.post(text: text, place: place, weekId: week.id)
            await loadBoard(force: true)
            return nil
        } catch let error as APIError {
            switch error.code {
            case "not_shown": return "That one can't go up. Try saying it another way."
            case "post_limit": return "You can post five times a week."
            case "board_closed": return "The board is closed."
            case "not_in": return "Only people who are in can post."
            case "invalid_request": return "Keep it to one short line and a place."
            default: return connectionLine(error)
            }
        } catch { return nil }
    }

    /// Takes one of your posts down on the server. Returns nil when it is gone, or the reason
    /// it is not. The board drops it from the list with `forget(_:)` once it has faded.
    func takeDown(_ post: BoardPost) async -> String? {
        do {
            try await api.takeDown(postId: post.id)
            return nil
        } catch let error as APIError {
            if error.status == 404 { return "That post couldn't be taken down." }
            return connectionLine(error)
        } catch { return nil }
    }

    func forget(_ post: BoardPost) {
        posts.removeAll { $0.id == post.id }
        Task { await loadBoard(force: true) }
    }

    /// The question's "Add it". Returns nil when it went in, or the reason it did not.
    func writeLine(_ text: String) async -> String? {
        guard let week = state?.week else { return nil }
        do {
            _ = try await api.writeLine(text: text, weekId: week.id)
            await refresh()
            return nil
        } catch let error as APIError {
            switch error.code {
            case "not_shown": return "That one can't go in. Try saying it another way."
            case "already_wrote", "phase_closed", "not_in":
                await refresh()
                return nil
            default: return connectionLine(error)
            }
        } catch { return nil }
    }

    /// The question's "Skip", remembered for the week on this device.
    func skipLine() {
        guard let week = state?.week else { return }
        var skipped = UserDefaults.standard.stringArray(forKey: Keys.lineSkipped) ?? []
        if !skipped.contains(week.id) { skipped.append(week.id) }
        UserDefaults.standard.set(skipped, forKey: Keys.lineSkipped)
        lineSkippedTick += 1
    }

    private var lineSkippedTick = 0
    private var lineSkipped: Bool {
        _ = lineSkippedTick
        guard let id = state?.week?.id else { return false }
        return (UserDefaults.standard.stringArray(forKey: Keys.lineSkipped) ?? []).contains(id)
    }

    private func perform(_ work: (APIClient) async throws -> Void) async {
        busy = true
        defer { busy = false }
        do {
            try await work(api)
        } catch let error as APIError {
            handle(error)
        } catch {}
        await refresh()
    }

    // MARK: The lock engine

    /// Brings the engine in step with the server: schedule the decided window for people who
    /// are in, cancel it for people who opted out, and give it the head count.
    private func syncEngine() async {
        guard let state, let week = state.week, let me = state.me else { return }
        if let count = state.numbers?.liveCount ?? state.numbers?.in { engine.setPeopleCount(count) }
        guard onboarded, let start = week.startsAt, let end = week.endsAt,
              state.phase == .decided || state.phase == .live else { return }
        let window = engine.state.window
        let ours = window?.id == week.id
        switch me.status {
        case .in:
            guard end > Date() else { return }
            if ours && engine.state.hasLeft {
                // Left on this phone. Until the server has heard, report rather than re-lock;
                // once it has, "in" means they joined again.
                guard let leftAt = engine.state.leftAt, leaveReported(week.id, leftAt) else { return }
            } else if ours, window?.start == start, window?.end == end {
                return
            }
            await schedule(weekId: week.id, start: start, end: end)
        case .skipped:
            if ours { await engine.cancelWindow() }
        case .left, .none:
            break
        }
    }

    private func schedule(weekId: String, start: Date, end: Date) async {
        // Reaches already reported for this week carry over: rescheduling resets the engine's count.
        var base = UserDefaults.standard.dictionary(forKey: Keys.reachBase) as? [String: Int] ?? [:]
        base[weekId] = reportedReaches(weekId)
        UserDefaults.standard.set(base, forKey: Keys.reachBase)
        do {
            try await engine.scheduleWindow(id: weekId, start: start, end: end)
        } catch {
            say(error.localizedDescription)
        }
    }

    /// Tells the server what the engine recorded by itself: a leave from the shield or from
    /// front mode's grace period, and the reach count.
    private func reportEngine() async {
        guard isSignedIn, let window = engine.state.window, window.id.hasPrefix("wk_") else { return }
        if engine.state.hasLeft, let leftAt = engine.state.leftAt, !leaveReported(window.id, leftAt) {
            do {
                _ = try await api.leave(weekId: window.id, leftAt: leftAt)
                markLeaveReported(window.id, leftAt)
                await refresh()
            } catch let error as APIError {
                // Anything but "could not reach the server" will not change on a retry.
                if error.code != "network" && error.status < 500 { markLeaveReported(window.id, leftAt) }
            } catch {}
        }
        let base = (UserDefaults.standard.dictionary(forKey: Keys.reachBase) as? [String: Int])?[window.id] ?? 0
        let total = base + engine.state.reachCount
        if total > reportedReaches(window.id), Date() >= window.start {
            do {
                _ = try await api.reportReaches(weekId: window.id, count: total)
                setReportedReaches(window.id, total)
            } catch let error as APIError {
                if error.code != "network" && error.status < 500 { setReportedReaches(window.id, total) }
            } catch {}
        }
    }

    private func leaveReported(_ weekId: String, _ leftAt: Date) -> Bool {
        let reported = UserDefaults.standard.dictionary(forKey: Keys.reportedLeave) as? [String: Double] ?? [:]
        return reported[weekId] == leftAt.timeIntervalSince1970
    }

    private func markLeaveReported(_ weekId: String, _ leftAt: Date) {
        var reported = UserDefaults.standard.dictionary(forKey: Keys.reportedLeave) as? [String: Double] ?? [:]
        reported[weekId] = leftAt.timeIntervalSince1970
        UserDefaults.standard.set(reported, forKey: Keys.reportedLeave)
    }

    private func reportedReaches(_ weekId: String) -> Int {
        (UserDefaults.standard.dictionary(forKey: Keys.reportedReaches) as? [String: Int])?[weekId] ?? 0
    }

    private func setReportedReaches(_ weekId: String, _ count: Int) {
        var reported = UserDefaults.standard.dictionary(forKey: Keys.reportedReaches) as? [String: Int] ?? [:]
        reported[weekId] = count
        UserDefaults.standard.set(reported, forKey: Keys.reportedReaches)
    }

    // MARK: Quiet lines

    private var noticeIsConnection = false

    private func handle(_ error: APIError) {
        if error.isUnauthorized {
            Task { await signOut() }
            return
        }
        if error.code == "network" {
            reachable = false
            noticeIsConnection = true
            notice = "Can't reach Quiet Hours right now."
            return
        }
        say("Something went wrong. Try again.")
    }

    private func connectionLine(_ error: APIError) -> String {
        if error.isUnauthorized {
            Task { await signOut() }
        }
        return error.code == "network" ? "Can't reach Quiet Hours right now." : "Something went wrong. Try again."
    }

    /// Shows one quiet line for a few seconds.
    func say(_ line: String) {
        noticeIsConnection = false
        notice = line
        noticeTask?.cancel()
        noticeTask = Task {
            try? await Task.sleep(for: .seconds(5))
            guard !Task.isCancelled else { return }
            notice = nil
        }
    }

    // MARK: Demo (DEBUG builds only)

    #if DEBUG
    /// Kept in the Keychain; mirrored here so the settings sheet redraws when it changes.
    private(set) var adminSecret: String? = Keychain.get(Keychain.adminSecretKey)

    func setAdminSecret(_ secret: String?) {
        let value = secret?.trimmingCharacters(in: .whitespacesAndNewlines)
        let kept = value?.isEmpty == false ? value : nil
        Keychain.set(kept, for: Keychain.adminSecretKey)
        adminSecret = kept
    }

    /// Moves the current week so that now is the start of `step`: vote, decided, day, live,
    /// ended or told. Returns a line describing what happened.
    func demoJump(_ step: String) async -> String {
        guard let secret = adminSecret else { return "Enter the admin secret first." }
        let client = api
        do {
            var weekId = state?.week?.id
            if weekId == nil {
                if step == "vote" {
                    try await client.adminSeedWeek(secret: secret)
                    await refresh()
                    return "Seeded a demo week in its vote."
                }
                weekId = try await client.adminWeeks(secret: secret).weeks.first?.id
            }
            guard let weekId else { return "No week to move. Press Voting first." }
            switch step {
            case "day":
                // On the day: the window starts a little later today, the board is open.
                let view = try await client.adminJump(weekId: weekId, to: "live", secret: secret)
                let gap = Int((view.week.startsAt ?? view.week.voteClosesAt).timeIntervalSince(view.week.voteClosesAt))
                var day = Calendar(identifier: .gregorian)
                day.timeZone = TimeText.zone
                let midnight = day.nextDate(after: Date(), matching: DateComponents(hour: 0), matchingPolicy: .nextTime) ?? Date()
                let toMidnight = Int(midnight.timeIntervalSinceNow) - 120
                let shift = max(60, min(gap - 5, 3 * 3600 + 12 * 60, toMidnight))
                _ = try await client.adminShift(weekId: weekId, seconds: shift, secret: secret)
            case "told":
                _ = try await client.adminJump(weekId: weekId, to: "told", secret: secret)
                do { try await client.adminWriteRecap(weekId: weekId, secret: secret) } catch {
                    await refresh()
                    return "Told, but the recap could not be written: \((error as? APIError)?.code ?? "error")."
                }
            default:
                _ = try await client.adminJump(weekId: weekId, to: step, secret: secret)
            }
            await refresh()
            return "Done."
        } catch let error as APIError {
            await refresh()
            return "\(error.code): \(error.message)"
        } catch {
            return error.localizedDescription
        }
    }
    #endif
}
