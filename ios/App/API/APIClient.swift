import Foundation

/// An error from the server (`{"error": {"code", "message"}}`) or from getting there.
struct APIError: Error, Sendable {
    let status: Int
    /// The server's stable code (`phase_closed`, `not_shown`, ...), `network` when the server
    /// could not be reached, or `bad_response` when its answer could not be read.
    let code: String
    let message: String

    var isUnauthorized: Bool { status == 401 }
}

/// The one client for the Quiet Hours API (docs/API.md).
///
/// The base URL comes from the `QuietHoursAPIBaseURL` Info.plist key, set from `QH_API_BASE_URL`
/// in project.yml (default `http://localhost:8790`). A launch argument or default named
/// `QHAPIBaseURL` overrides it, so a build can be pointed at another server without rebuilding:
/// `xcrun simctl launch <device> <bundle id> -QHAPIBaseURL https://example.org`.
final class APIClient: Sendable {
    let baseURL: URL
    let token: String?

    init(token: String?) {
        self.token = token
        baseURL = APIClient.configuredBaseURL
    }

    static var configuredBaseURL: URL {
        let override = UserDefaults.standard.string(forKey: "QHAPIBaseURL")
        let plist = Bundle.main.object(forInfoDictionaryKey: "QuietHoursAPIBaseURL") as? String
        for candidate in [override, plist] {
            if let text = candidate?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty,
               let url = URL(string: text), url.scheme != nil {
                return url
            }
        }
        return URL(string: "http://localhost:8790")!
    }

    // MARK: Sign in

    func startSignIn(email: String) async throws -> StartResponse {
        try await send("POST", "/v1/auth/start", body: ["email": email])
    }

    func verify(email: String, code: String) async throws -> VerifyResponse {
        try await send("POST", "/v1/auth/verify", body: ["email": email, "code": code])
    }

    func signOut() async throws {
        let _: OK = try await send("POST", "/v1/auth/sign-out", body: [String: String]())
    }

    // MARK: The week

    func state() async throws -> AppState {
        try await send("GET", "/v1/state")
    }

    func vote(optionId: String, weekId: String) async throws -> VoteResponse {
        try await send("POST", "/v1/vote", body: ["optionId": optionId, "weekId": weekId])
    }

    func skip(weekId: String) async throws -> MeResponse {
        try await send("POST", "/v1/me/skip", body: ["weekId": weekId])
    }

    func rejoin(weekId: String) async throws -> MeResponse {
        try await send("POST", "/v1/me/rejoin", body: ["weekId": weekId])
    }

    func leave(weekId: String, leftAt: Date?) async throws -> ReportResponse {
        var body = ["weekId": weekId]
        if let leftAt { body["leftAt"] = Self.iso(leftAt) }
        return try await send("POST", "/v1/me/leave", body: body)
    }

    func reportReaches(weekId: String, count: Int) async throws -> ReportResponse {
        try await send("POST", "/v1/me/reaches", body: ReachBody(weekId: weekId, approxReaches: count))
    }

    func board() async throws -> BoardResponse {
        try await send("GET", "/v1/board?limit=200")
    }

    func post(text: String, place: String, weekId: String) async throws -> PostResponse {
        try await send("POST", "/v1/board", body: ["text": text, "place": place, "weekId": weekId])
    }

    /// Takes one of your own posts down. 404 when it is not yours or no longer there.
    func takeDown(postId: String) async throws {
        let _: OK = try await send("DELETE", "/v1/board/\(postId)")
    }

    func writeLine(text: String, weekId: String) async throws -> LineResponse {
        try await send("POST", "/v1/lines", body: ["text": text, "weekId": weekId])
    }

    // MARK: Admin (DEBUG demo buttons)

    func adminWeeks(secret: String) async throws -> AdminWeeks {
        try await send("GET", "/v1/admin/weeks", admin: secret)
    }

    func adminJump(weekId: String, to phase: String, secret: String) async throws -> AdminWeekView {
        try await send("POST", "/v1/admin/weeks/\(weekId)/timeline", body: ["jumpTo": phase], admin: secret)
    }

    func adminShift(weekId: String, seconds: Int, secret: String) async throws -> AdminWeekView {
        try await send("POST", "/v1/admin/weeks/\(weekId)/timeline", body: ["shiftSeconds": seconds], admin: secret)
    }

    func adminSeedWeek(secret: String) async throws {
        let _: OK = try await send("POST", "/v1/admin/demo/seed", body: ["step": "week"], admin: secret)
    }

    func adminWriteRecap(weekId: String, secret: String) async throws {
        let _: OK = try await send("POST", "/v1/admin/weeks/\(weekId)/recap", body: [String: String](), admin: secret)
    }

    // MARK: Plumbing

    private struct OK: Decodable {}
    private struct ReachBody: Encodable { let weekId: String; let approxReaches: Int }
    private struct ErrorBody: Decodable {
        struct Inner: Decodable { let code: String; let message: String? }
        let error: Inner
    }

    private func send<T: Decodable>(_ method: String, _ path: String, admin: String? = nil) async throws -> T {
        try await send(method, path, body: Optional<[String: String]>.none, admin: admin)
    }

    private func send<T: Decodable, B: Encodable>(_ method: String, _ path: String, body: B?, admin: String? = nil) async throws -> T {
        guard let url = URL(string: path, relativeTo: baseURL) else {
            throw APIError(status: 0, code: "bad_request", message: "Bad path \(path)")
        }
        var request = URLRequest(url: url, timeoutInterval: 20)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let admin { request.setValue(admin, forHTTPHeaderField: "X-Admin-Secret") }
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(body)
        }
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch {
            throw APIError(status: 0, code: "network", message: error.localizedDescription)
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            if let failure = try? Self.decoder.decode(ErrorBody.self, from: data) {
                throw APIError(status: status, code: failure.error.code, message: failure.error.message ?? "")
            }
            throw APIError(status: status, code: "http_\(status)", message: String(data: data, encoding: .utf8) ?? "")
        }
        do {
            return try Self.decoder.decode(T.self, from: data)
        } catch {
            throw APIError(status: status, code: "bad_response", message: String(describing: error))
        }
    }

    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { d in
            let text = try d.singleValueContainer().decode(String.self)
            if let date = try? Date.ISO8601FormatStyle(includingFractionalSeconds: true).parse(text) { return date }
            if let date = try? Date.ISO8601FormatStyle().parse(text) { return date }
            throw DecodingError.dataCorrupted(.init(codingPath: d.codingPath, debugDescription: "Not an ISO 8601 time: \(text)"))
        }
        return decoder
    }()

    static func iso(_ date: Date) -> String {
        Date.ISO8601FormatStyle(includingFractionalSeconds: true).format(date)
    }
}
