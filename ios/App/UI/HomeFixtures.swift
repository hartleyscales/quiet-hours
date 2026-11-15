import Foundation

#if DEBUG
/// DEBUG builds only: each Home filled with the mock's own sample values
/// (design/homes-quiet.html), so a screenshot can be laid over the mock rendered at 390 x 844 and
/// compared point for point. Launch with `-QHDebugFixture vote|voted|vote-out|decided|
/// decided-out|day|day-out|locked|locked-out|summary|summary-before|summary-out`; add
/// `-QHDebugBoardOpen YES` (The day, Locked) for the board or `-QHDebugSettings YES` for the
/// settings sheet over it, and `-QHDebugFixtureThen <name>` to move to another fixture after a
/// moment, to watch the change. Nothing here talks to the server.
enum HomeFixtures {
    static let names = ["vote", "voted", "vote-out", "decided", "decided-out", "day", "day-out", "locked", "locked-out",
                        "summary", "summary-before", "summary-out"]

    static func scene(_ name: String, chosen: Int = 0) -> HomeScene? {
        let out = name.hasSuffix("-out")
        switch name {
        case "vote", "vote-out": return vote(voted: nil, out: out)
        case "voted": return vote(voted: chosen, out: false)
        case "decided", "decided-out": return window(.decided, out: out)
        case "day", "day-out": return window(.day, out: out)
        case "locked", "locked-out": return locked(out: out)
        case "summary-before":
            return HomeScene(kind: .summaryBefore, out: false, picture: .bubble, statement: "Quiet hours are over.",
                             statementSize: .over, line: "People are still writing. Back at 7:15.")
        case "summary", "summary-out":
            return HomeScene(kind: .summary, out: false, picture: .bubble, statement: highlights[0], statementSize: .recap,
                             highlights: highlights,
                             line: out ? "You were out this week. 3,041 of 3,112 stayed." : "3,041 of 3,112 stayed.")
        default: return nil
        }
    }

    // MARK: Voting

    private static let options: [(String, String, String, Double)] = [
        ("Thursday", "5:00 – 7:00 PM", "Most classes are out. Sunset is at 4:48.", 0.47),
        ("Sunday", "4:00 – 5:30 PM", "No home game, and the week hasn't begun.", 0.34),
        ("Wednesday", "12:00 – 1:00 PM", "Lunch, when most people are on campus.", 0.20),
    ]

    private static func vote(voted: Int?, out: Bool) -> HomeScene {
        let pills = options.enumerated().map { i, o in
            OptionPill(id: "op\(i)", day: o.0, time: o.1, share: o.3, chosen: i == voted)
        }
        let line = out ? "You're out this week." : voted.map { options[$0].2 } ?? "Closes Tuesday, 8:00 PM"
        return HomeScene(kind: .vote, out: out, picture: .clock, statement: "When this week?", statementSize: .vote,
                         line: line, options: out ? nil : OptionsBlock(pills: pills, voted: voted != nil, pressable: true),
                         pill: out ? .optBackIn : nil)
    }

    // MARK: Decided, The day, Locked

    private static func window(_ kind: HomeKind, out: Bool) -> HomeScene {
        let day = kind == .day
        let line = out ? "You're out this week."
            : day ? "In 3 hours, 12 minutes. 3,112 Trojans in." : "In 1 day, 20 hours. 3,112 Trojans in."
        return HomeScene(kind: kind, out: out, picture: .moon, statement: day ? "Today" : "Thursday", statementSize: .window,
                         time: "5:00 – 7:00 PM", line: line,
                         pill: out ? .optBackIn : day ? .board(AppModel.goingOn(posts.count)) : nil)
    }

    private static func locked(out: Bool) -> HomeScene {
        HomeScene(kind: .locked, out: out, picture: .night(DebugLaunch.moonCount ?? 3098), statement: "Until 7:00",
                  statementSize: .window,
                  line: out ? "You're out. 3,098 Trojans in." : "3,098 Trojans in",
                  pill: out ? .join("Join until 7:00") : .board(AppModel.goingOn(posts.count)))
    }

    private static let highlights = [
        "41 people called a parent.", "Someone finished a painting they started in September.",
        "Spikeball on McCarthy Quad grew to about thirty.", "63 people took a nap.", "19 people cooked for someone else.",
    ]

    // MARK: The board

    private static let posts: [(String, String, String, Bool)] = [
        ("Guitar on the lawn, come sit", "McCarthy Quad", "2m", true), ("Spikeball, anyone welcome", "Alumni Park", "9m", false),
        ("Jam session, bring anything", "Village fountain", "14m", false), ("Cooking for whoever shows up", "Cale kitchen", "21m", false),
        ("Pickup soccer needs two more", "Brittingham Field", "26m", false), ("Sketching on the steps", "Doheny Library", "31m", false),
        ("Walking to the Rose Garden", "Leaving from Tommy Trojan", "38m", false), ("Frisbee, all levels", "Cromwell Field", "44m", false),
        ("Chess, two boards going", "Campus Center patio", "52m", false), ("Reading on the grass", "Founders Park", "1h", false),
        ("Sunset walk", "Leaving Leavey at 5:30", "1h", false), ("Hammocks up, room for more", "Trousdale by Bovard", "1h", false),
        ("Basketball, next five", "Lyon Center courts", "2h", false), ("Board games in the lounge", "Ginsburg Hall", "2h", false),
    ]

    static let board = BoardScene(
        posts: posts.enumerated().map { i, p in
            PostRow(id: "po\(i)", text: p.0, place: p.3 ? "Yours · \(p.1)" : p.1, age: p.2, mine: p.3,
                    post: BoardPost(id: "po\(i)", text: p.0, place: p.1, createdAt: nil, mine: p.3, pending: false))
        },
        canPost: true)

    // MARK: Settings

    static func settings(_ name: String) -> SettingsScene {
        let out = name.hasSuffix("-out")
        var week: WeekRow?
        switch name {
        case "vote", "voted": week = WeekRow(title: "Opt out of this week", action: .optOut)
        case "vote-out": week = WeekRow(title: "Opt back in", action: .optBackIn)
        case "decided", "decided-out":
            week = WeekRow(title: out ? "Opt back in" : "Opt out of this week", detail: "Thursday, 5:00 – 7:00 PM",
                           action: out ? .optBackIn : .optOut)
        case "day", "day-out":
            week = WeekRow(title: out ? "Opt back in" : "Opt out of this week", detail: "Today, 5:00 – 7:00 PM",
                           action: out ? .optBackIn : .optOut)
        case "locked": week = WeekRow(title: "Leave quiet hours", detail: "They run until 7:00", action: .leave)
        case "locked-out": week = WeekRow(title: "Join until 7:00", action: .join)
        default: week = nil
        }
        return SettingsScene(night: name.hasPrefix("locked"), week: week, email: "ttrojan@usc.edu")
    }

    /// Where a fixture goes when its "this week" row or its button is pressed.
    static func after(_ action: WeekRow.Action, from name: String) -> String {
        switch action {
        case .optOut: return name == "voted" ? "vote-out" : name + "-out"
        case .optBackIn: return String(name.dropLast(4))
        case .leave: return "locked-out"
        case .join: return "locked"
        }
    }
}
#endif
