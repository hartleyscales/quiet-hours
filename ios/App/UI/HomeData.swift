import Foundation

// What a Home shows, as plain values. Every Home is built like the intro screens
// (HOMES-QUIET.md): one picture, one statement in the serif, one grey line, and at most one
// thing to do. Every word, number and control is decided here, from the app model; `HomeView`
// only places and moves them.

enum HomeKind: Hashable {
    case vote, decided, day, locked, summary, summaryBefore
}

/// Things a Home can do. Opting out and leaving live in the settings sheet.
struct HomeActions {
    var openSettings: () -> Void = {}
    var openBoard: () -> Void = {}
    var optBackIn: () -> Void = {}
    var join: () -> Void = {}
    var vote: (String) -> Void = { _ in }
}

/// The one picture at the top of a Home.
enum HomePicture: Hashable {
    /// Voting: the dot clock, still, at 0.8 (`canvas.pic`, top 74).
    case clock
    /// Decided, The day: the daylight moon, the sign-in art at its own size (`.art`, top 49).
    case moon
    /// The Summary: the dot speech bubble, still, at 0.8 (`canvas.pic`, top 74).
    case bubble
    /// Locked: the night moon, one fixed drawing (`.lmoon`, top 192), under the stars.
    case night(Int)

    var isNight: Bool {
        if case .night = self { return true }
        return false
    }

    /// Which picture, apart from the night moon's count.
    var form: Int {
        switch self {
        case .clock: return 0
        case .moon: return 1
        case .bubble: return 2
        case .night: return 3
        }
    }
}

/// How the statement is set (`.qbig` and its variants).
enum StatementSize: Hashable {
    /// `.qv .qbig`: 54/60, padding 8, top 452.
    case vote
    /// `.qbig`: 64/68, padding 28, top 452.
    case window
    /// `.qs .qbig`: a highlight, 38/44, centred in 432...564.
    case recap
    /// 9b: "Quiet hours are over.", 52/56, centred in 432...564.
    case over
}

/// `.qopt`: one window to vote for.
struct OptionPill: Hashable, Identifiable {
    var id: String
    /// "Thursday"
    var day: String
    /// "5:00 – 7:00 PM"
    var time: String
    /// Its share of all the votes, 0...1, for the tint.
    var share: Double
    var chosen: Bool
}

/// `.qopts`: the three choices.
struct OptionsBlock: Hashable {
    var pills: [OptionPill]
    /// The person has voted: the chosen pill is pressed in and every pill shows its tint.
    var voted: Bool
    var pressable: Bool

    var chosenID: String? { pills.first(where: \.chosen)?.id }
}

/// The one thing to do, at the foot.
enum HomePill: Hashable {
    /// `.qrow`: "14 things going on", raised (dark on Locked). Opens the board.
    case board(String)
    /// `.qgo`: the one dark button.
    case optBackIn
    /// `.golight`: "Join until 7:00", light on the dark screen.
    case join(String)

    /// The same pill keeps its place between Homes; a different one leaves and arrives.
    var key: String {
        switch self {
        case .board: return "board"
        case .optBackIn: return "optBackIn"
        case .join: return "join"
        }
    }
}

struct HomeScene: Hashable {
    var kind: HomeKind
    /// Out this week (or out of quiet hours on Locked): the same screen, pale.
    var out: Bool
    var picture: HomePicture
    var statement: String
    var statementSize: StatementSize
    /// The Summary: the highlights, shown one at a time in the statement's place.
    var highlights: [String] = []
    /// `.qsub`: the time, in Outfit 24 (Decided, The day).
    var time: String?
    /// `.qline`: the grey line.
    var line: String
    var options: OptionsBlock?
    var pill: HomePill?
    /// The quiet line for loading and errors, standing in for the grey line.
    var notice: String?
    var busy = false

    var night: Bool { kind == .locked }
}

/// The board, as its own screen.
struct PostRow: Hashable, Identifiable {
    var id: String
    var text: String
    /// "McCarthy Quad", or "Yours · McCarthy Quad"
    var place: String
    /// "9m", "1h"
    var age: String
    var mine: Bool
    var post: BoardPost
}

struct BoardScene: Hashable {
    var posts: [PostRow]
    var canPost: Bool
}

/// The settings sheet's first row: this week.
struct WeekRow: Hashable {
    enum Action: Hashable { case optOut, optBackIn, leave, join }
    var title: String
    var detail: String?
    var action: Action
}

struct SettingsScene: Hashable {
    /// Over Locked: the sheet and the wash behind it are dark.
    var night: Bool
    /// Left out when there is nothing to opt out of.
    var week: WeekRow?
    var email: String
}

extension AppModel {
    /// The Home for `screen`, or nil when `screen` is not a Home.
    func homeScene(for screen: Screen) -> HomeScene? {
        switch screen {
        case .voting(let out): return votingScene(out: out)
        case .selected(let out): return windowScene(kind: .decided, out: out)
        case .day(let out): return windowScene(kind: .day, out: out)
        case .locked(let out): return lockedScene(out: out)
        case .summaryBefore: return summaryScene(told: false)
        case .summary(let out): return summaryScene(told: true, out: out)
        default: return nil
        }
    }

    private var can: Can { state?.me?.can ?? Can() }
    private var weekRefused: Bool { rejoinRefused.contains(state?.week?.id ?? "") }

    // MARK: Voting

    private func votingScene(out: Bool) -> HomeScene {
        let options = tallied(state?.options ?? [])
        let total = options.reduce(0) { $0 + $1.votes }
        let chosen = out ? nil : (pendingVote ?? state?.myVote)
        let pills = options.map { o in
            OptionPill(id: o.id, day: TimeText.weekday(o.startsAt), time: TimeText.range(o.startsAt, o.endsAt),
                       share: total > 0 ? Double(o.votes) / Double(total) : 0, chosen: o.id == chosen)
        }
        let voted = chosen != nil && options.contains { $0.id == chosen }
        let line: String
        if out {
            line = "You're out this week."
        } else if voted, let reason = options.first(where: { $0.id == chosen })?.reason {
            line = reason
        } else {
            line = state?.week.map { "Closes \(TimeText.weekday($0.voteClosesAt)), \(TimeText.clockWithPeriod($0.voteClosesAt))" } ?? ""
        }
        return HomeScene(
            kind: .vote, out: out, picture: .clock, statement: "When this week?", statementSize: .vote,
            line: line,
            // Out, the choices leave the screen: "Opt back in" is the one thing to do.
            options: out ? nil : OptionsBlock(pills: pills, voted: voted, pressable: can.vote),
            pill: out && can.rejoin ? .optBackIn : nil,
            notice: notice, busy: busy)
    }

    /// The server's tally, with a vote just tapped moved over until the server answers.
    private func tallied(_ options: [VoteOption]) -> [VoteOption] {
        guard let pending = pendingVote, pending != state?.myVote else { return options }
        let previous = state?.myVote
        return options.map { o in
            var votes = o.votes
            if o.id == pending { votes += 1 }
            if o.id == previous { votes = max(0, votes - 1) }
            return VoteOption(id: o.id, startsAt: o.startsAt, endsAt: o.endsAt, minutes: o.minutes, reason: o.reason, votes: votes)
        }
    }

    // MARK: Decided, The day

    private func windowScene(kind: HomeKind, out: Bool) -> HomeScene {
        let start = state?.week?.startsAt, end = state?.week?.endsAt
        var line: String
        if out {
            line = "You're out this week."
        } else {
            var parts: [String] = []
            if let start, start > now { parts.append(TimeText.until(start, now: now) + ".") }
            if let n = state?.numbers?.in { parts.append("\(Count.text(n)) \(n == 1 ? "Trojan" : "Trojans") in.") }
            line = parts.joined(separator: " ")
        }
        var pill: HomePill?
        if out {
            pill = can.rejoin ? .optBackIn : nil
        } else if kind == .day, state?.board?.open == true {
            pill = .board(Self.goingOn(posts.count))
        }
        return HomeScene(
            kind: kind, out: out, picture: .moon,
            statement: start.map { TimeText.day($0, now: now) } ?? "", statementSize: .window,
            time: start.flatMap { s in end.map { TimeText.range(s, $0) } },
            line: line, pill: pill, notice: notice, busy: busy)
    }

    // MARK: Locked

    private func lockedScene(out: Bool) -> HomeScene {
        let endClock = state?.week?.endsAt.map(TimeText.clock) ?? ""
        let live = state?.numbers?.liveCount ?? state?.numbers?.in
        // "3,098 Trojans in", or out: "You're out. 3,098 Trojans in."
        let people = live.map { "\(Count.text($0)) \($0 == 1 ? "Trojan" : "Trojans") in" }
        let line = out ? (people.map { "You're out. \($0)." } ?? "You're out.") : (people ?? "")
        var pill: HomePill?
        if out {
            pill = can.rejoin && !weekRefused ? .join("Join until \(endClock)") : nil
        } else if state?.board?.open == true {
            pill = .board(Self.goingOn(posts.count))
        }
        return HomeScene(
            kind: .locked, out: out, picture: .night(DebugLaunch.moonCount ?? LockedMoonView.dots),
            statement: "Until \(endClock)", statementSize: .window,
            line: line, pill: pill, notice: notice, busy: busy)
    }

    // MARK: Summary

    private func summaryScene(told: Bool, out: Bool = false) -> HomeScene {
        if !told {
            let back = state?.week.map { " Back at \(TimeText.clock($0.toldAt))." } ?? ""
            return HomeScene(kind: .summaryBefore, out: false, picture: .bubble, statement: "Quiet hours are over.",
                             statementSize: .over, line: "People are still writing." + back, notice: notice, busy: busy)
        }
        let highlights = Array((state?.recap?.highlights.map(\.text) ?? []).prefix(5)).map(Self.sentence)
        let stayed = state?.numbers?.stayed ?? state?.recap?.stats?.stayed
        let stayedLine = stayed.map { "\(Count.text($0.count)) of \(Count.text($0.of)) stayed." }
        let line = out ? (stayedLine.map { "You were out this week. \($0)" } ?? "You were out this week.") : (stayedLine ?? "")
        return HomeScene(
            kind: .summary, out: false, picture: .bubble,
            statement: highlights.first ?? "Quiet hours are over.", statementSize: highlights.isEmpty ? .over : .recap,
            highlights: highlights, line: line, notice: notice, busy: busy)
    }

    // MARK: The board

    var boardScene: BoardScene {
        let rows = posts.map { post in
            PostRow(id: post.id, text: post.text, place: post.mine ? "Yours · \(post.place)" : post.place,
                    age: post.createdAt.map { TimeText.age(since: $0, now: now) } ?? "", mine: post.mine, post: post)
        }
        return BoardScene(posts: rows, canPost: can.post)
    }

    // MARK: Settings

    var settingsScene: SettingsScene {
        SettingsScene(night: isNight, week: weekRow, email: email ?? "")
    }

    /// "Opt out of this week", "Opt back in", "Leave quiet hours" or "Join until H:MM", as the
    /// server's `can` allows; nil when there is nothing to opt out of.
    private var weekRow: WeekRow? {
        guard let state, let week = state.week, let phase = state.phase, let me = state.me else { return nil }
        var window: String?
        if let start = week.startsAt, let end = week.endsAt {
            window = "\(TimeText.day(start, now: now)), \(TimeText.range(start, end))"
        }
        switch phase {
        case .vote, .decided:
            if me.status == .skipped {
                return can.rejoin ? WeekRow(title: "Opt back in", detail: window, action: .optBackIn) : nil
            }
            return can.skip ? WeekRow(title: "Opt out of this week", detail: window, action: .optOut) : nil
        case .live:
            let endClock = week.endsAt.map(TimeText.clock) ?? ""
            if me.status == .in {
                return can.leave ? WeekRow(title: "Leave quiet hours", detail: "They run until \(endClock)", action: .leave) : nil
            }
            return can.rejoin && !weekRefused ? WeekRow(title: "Join until \(endClock)", action: .join) : nil
        case .ended, .told:
            return nil
        }
    }

    /// The "this week" row: the same server and lock-engine paths as before it moved here.
    func act(_ action: WeekRow.Action) {
        Task {
            switch action {
            case .optOut: await optOut()
            case .optBackIn: await optBackIn()
            case .leave: await leave()
            case .join: await join()
            }
        }
    }

    // MARK: Words

    /// "14 things going on", "1 thing going on", "Nothing going on yet"
    nonisolated static func goingOn(_ n: Int) -> String {
        switch n {
        case 0: return "Nothing going on yet"
        case 1: return "1 thing going on"
        default: return "\(Count.text(n)) things going on"
        }
    }

    /// Highlights are set as sentences, as the mock sets them.
    nonisolated static func sentence(_ text: String) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespaces)
        guard let last = trimmed.last, !".!?…".contains(last) else { return trimmed }
        return trimmed + "."
    }

    func homeActions(openSettings: @escaping () -> Void, openBoard: @escaping () -> Void) -> HomeActions {
        HomeActions(
            openSettings: openSettings,
            openBoard: openBoard,
            optBackIn: { Task { await self.optBackIn() } },
            join: { Task { await self.join() } },
            vote: { id in
                guard let option = self.state?.options?.first(where: { $0.id == id }) else { return }
                Task { await self.vote(option) }
            })
    }
}
