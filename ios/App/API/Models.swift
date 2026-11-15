import Foundation

// The server's shapes (docs/API.md). Decoding is lenient where the server is still growing:
// unknown phases and statuses decode as nil rather than failing the whole response.

enum Phase: String, Decodable, Sendable {
    case vote, decided, live, ended, told
}

enum Status: String, Decodable, Sendable {
    case `in`, skipped, left
}

struct WeekInfo: Decodable, Equatable, Sendable {
    let id: String
    let voteOpensAt: Date
    let voteClosesAt: Date
    let startsAt: Date?
    let endsAt: Date?
    let toldAt: Date
    let nextWeekVoteOpensAt: Date?
    let isDemo: Bool?
}

struct VoteOption: Codable, Equatable, Identifiable, Sendable {
    let id: String
    let startsAt: Date
    let endsAt: Date
    let minutes: Int?
    let reason: String
    let votes: Int
}

struct BoardWindow: Decodable, Equatable, Sendable {
    let open: Bool
    let opensAt: Date?
    let closesAt: Date?
}

struct Can: Decodable, Equatable, Sendable {
    var vote = false
    var skip = false
    var rejoin = false
    var leave = false
    var reportReaches = false
    var post = false
    var writeLine = false

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        vote = (try? c.decode(Bool.self, forKey: .vote)) ?? false
        skip = (try? c.decode(Bool.self, forKey: .skip)) ?? false
        rejoin = (try? c.decode(Bool.self, forKey: .rejoin)) ?? false
        leave = (try? c.decode(Bool.self, forKey: .leave)) ?? false
        reportReaches = (try? c.decode(Bool.self, forKey: .reportReaches)) ?? false
        post = (try? c.decode(Bool.self, forKey: .post)) ?? false
        writeLine = (try? c.decode(Bool.self, forKey: .writeLine)) ?? false
    }

    private enum CodingKeys: String, CodingKey { case vote, skip, rejoin, leave, reportReaches, post, writeLine }
}

struct Me: Decodable, Equatable, Sendable {
    let status: Status?
    let joinedAt: Date?
    let leftAt: Date?
    let approxReaches: Int
    let wroteLine: Bool
    let can: Can

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        status = (try? c.decode(Status.self, forKey: .status))
        joinedAt = try c.decodeIfPresent(Date.self, forKey: .joinedAt)
        leftAt = try c.decodeIfPresent(Date.self, forKey: .leftAt)
        approxReaches = (try? c.decode(Int.self, forKey: .approxReaches)) ?? 0
        wroteLine = (try? c.decode(Bool.self, forKey: .wroteLine)) ?? false
        can = (try? c.decode(Can.self, forKey: .can)) ?? Can()
    }

    private enum CodingKeys: String, CodingKey { case status, joinedAt, leftAt, approxReaches, wroteLine, can }
}

struct Stayed: Decodable, Equatable, Sendable {
    let count: Int
    let of: Int
    let share: Double?
}

struct Numbers: Decodable, Equatable, Sendable {
    let `in`: Int?
    let liveCount: Int?
    let approxReaches: Int?
    let secondsGivenBack: Double?
    let hoursGivenBack: Double?
    let stayed: Stayed?
    /// Lines written this week, during `ended` and `told`.
    let lines: Int?
}

struct Highlight: Decodable, Equatable, Sendable {
    let kind: String?
    let text: String
    let count: Int?
}

struct RecapStats: Decodable, Equatable, Sendable {
    let `in`: Int?
    let approxReaches: Int?
    let secondsGivenBack: Double?
    let hoursGivenBack: Double?
    let stayed: Stayed?
    let lines: Int?
    let linesNotShown: Int?
}

struct Recap: Decodable, Equatable, Sendable {
    let weekId: String?
    let highlights: [Highlight]
    let stats: RecapStats?
}

struct AppState: Decodable, Equatable, Sendable {
    let serverTime: Date
    let phase: Phase?
    let nextChangeAt: Date?
    let week: WeekInfo?
    let upcomingVoteOpensAt: Date?
    let options: [VoteOption]?
    let myVote: String?
    let winner: VoteOption?
    let board: BoardWindow?
    let me: Me?
    let numbers: Numbers?
    let recap: Recap?

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        serverTime = try c.decode(Date.self, forKey: .serverTime)
        phase = try? c.decode(Phase.self, forKey: .phase)
        nextChangeAt = try c.decodeIfPresent(Date.self, forKey: .nextChangeAt)
        week = try c.decodeIfPresent(WeekInfo.self, forKey: .week)
        upcomingVoteOpensAt = try c.decodeIfPresent(Date.self, forKey: .upcomingVoteOpensAt)
        options = try c.decodeIfPresent([VoteOption].self, forKey: .options)
        myVote = try c.decodeIfPresent(String.self, forKey: .myVote)
        winner = try c.decodeIfPresent(VoteOption.self, forKey: .winner)
        board = try c.decodeIfPresent(BoardWindow.self, forKey: .board)
        me = try c.decodeIfPresent(Me.self, forKey: .me)
        numbers = try c.decodeIfPresent(Numbers.self, forKey: .numbers)
        recap = try? c.decodeIfPresent(Recap.self, forKey: .recap)
    }

    private enum CodingKeys: String, CodingKey {
        case serverTime, phase, nextChangeAt, week, upcomingVoteOpensAt, options, myVote, winner, board, me, numbers, recap
    }
}

struct BoardPost: Decodable, Hashable, Identifiable, Sendable {
    let id: String
    let text: String
    let place: String
    let createdAt: Date?
    let mine: Bool
    let pending: Bool?
}

struct BoardResponse: Decodable, Sendable {
    let open: Bool
    let posts: [BoardPost]
}

struct StartResponse: Decodable, Sendable {
    let email: String
    let delivery: String?
    let devCode: String?
}

struct VerifyResponse: Decodable, Sendable {
    struct User: Decodable, Sendable { let id: String; let email: String }
    let token: String
    let user: User
}

struct VoteResponse: Decodable, Sendable {
    let myVote: String?
    let options: [VoteOption]?
}

struct MeResponse: Decodable, Sendable {
    let me: Me
}

struct ReportResponse: Decodable, Sendable {
    let weekId: String?
    let recorded: Bool?
    let reason: String?
    let me: Me?
}

struct PostResponse: Decodable, Sendable {
    let post: BoardPost
    let shown: Bool
}

struct LineResponse: Decodable, Sendable {
    let ok: Bool?
    let shown: Bool?
    let pending: Bool?
}

/// Admin week view; only what the demo buttons need.
struct AdminWeekView: Decodable, Sendable {
    let week: WeekInfo
    let phase: String?
}

struct AdminWeeks: Decodable, Sendable {
    let weeks: [WeekInfo]
}
