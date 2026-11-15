import Foundation

/// DEBUG builds only: launch arguments that put the app in a given state without touching the
/// screen, for checking screens in the simulator against the mocks. Release builds read none.
///
///     xcrun simctl launch <device> com.hms-web-development.QuietHours \
///       -QHAPIBaseURL http://127.0.0.1:8795 -QHDebugToken <token> -QHDebugOnboarded YES
///
/// - `QHDebugToken`: use this session token (from `POST /v1/auth/verify`).
/// - `QHDebugOnboarded`: YES skips How it works and The lock; NO shows them again.
/// - `QHDebugOnboarding`: `lock` opens onboarding at The lock.
/// - `QHDebugHowStep`: How it works moves to this step (1-3) after it appears.
/// - `QHDebugFocus`: `email`, `code` (with `QHDebugEmail`), `question` or `composer` focuses that
///   field 1.5 s after its screen appears, so the keyboard-up states can be seen.
/// - `QHDebugBlur`: YES also dismisses the keyboard 2.5 s later.
/// - `QHDebugText`: text already typed into the question's field or the board's composer.
/// - `QHDebugBoardOpen`: YES opens the board once The day or Locked shows.
/// - `QHDebugSettings`: YES opens the settings sheet once a screen with the gear shows.
/// - `QHDebugFastPoll`: YES reads `/v1/state` every 2 s, to watch changes of screen as they come.
/// - `QHDebugFixture`: show one Home filled with the mock's sample values (HomeFixtures.swift).
/// - `QHDebugFixtureThen`: with a fixture, move to this other fixture after 2.5 s.
/// - `QHDebugMoonCount`: draw the Locked moon for this many people instead of the server's
///   count (to compare N = 3,098 with the mock).
enum DebugLaunch {
    #if DEBUG
    private static var defaults: UserDefaults { .standard }
    static var token: String? { defaults.string(forKey: "QHDebugToken") }
    static var onboarded: Bool? { defaults.object(forKey: "QHDebugOnboarded") == nil ? nil : defaults.bool(forKey: "QHDebugOnboarded") }
    static var onboardingAtLock: Bool { defaults.string(forKey: "QHDebugOnboarding") == "lock" }
    static var howStep: Int { defaults.integer(forKey: "QHDebugHowStep") }
    static var focus: String? { defaults.string(forKey: "QHDebugFocus") }
    static var email: String? { defaults.string(forKey: "QHDebugEmail") }
    static var text: String? { defaults.string(forKey: "QHDebugText") }
    static var blur: Bool { defaults.bool(forKey: "QHDebugBlur") }
    static var settings: Bool { defaults.bool(forKey: "QHDebugSettings") }
    static var fixture: String? { defaults.string(forKey: "QHDebugFixture") }
    static var fixtureThen: String? { defaults.string(forKey: "QHDebugFixtureThen") }
    static var fastPoll: Bool { defaults.bool(forKey: "QHDebugFastPoll") }
    static var boardOpen: Bool { defaults.bool(forKey: "QHDebugBoardOpen") }
    static var moonCount: Int? { defaults.object(forKey: "QHDebugMoonCount") == nil ? nil : defaults.integer(forKey: "QHDebugMoonCount") }
    #else
    static let token: String? = nil
    static let onboarded: Bool? = nil
    static let onboardingAtLock = false
    static let howStep = 0
    static let focus: String? = nil
    static let email: String? = nil
    static let text: String? = nil
    static let blur = false
    static let settings = false
    static let fixture: String? = nil
    static let fixtureThen: String? = nil
    static let fastPoll = false
    static let boardOpen = false
    static let moonCount: Int? = nil
    #endif
}
