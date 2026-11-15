import Foundation
import ManagedSettings

/// Screen Time mode: what the person picked in Apple's picker, as opaque tokens the extensions
/// can read without FamilyControls, plus what the picks mean (`scope`).
struct LockTargets: Codable, Equatable {
    /// Default for a new install: lock everything except what the person picks.
    /// See LOCK-NOTES.md, "Total lock", for why.
    static let defaultScope: LockScope = .allExcept

    var scope: LockScope = LockTargets.defaultScope
    var applications: Set<ApplicationToken> = []
    var categories: Set<ActivityCategoryToken> = []
    var webDomains: Set<WebDomainToken> = []

    init(scope: LockScope = LockTargets.defaultScope,
         applications: Set<ApplicationToken> = [],
         categories: Set<ActivityCategoryToken> = [],
         webDomains: Set<WebDomainToken> = []) {
        self.scope = scope
        self.applications = applications
        self.categories = categories
        self.webDomains = webDomains
    }

    /// Picks saved before `scope` existed meant "lock these", so a missing scope decodes as
    /// `.selected`. A stored selection must never flip meaning.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        scope = try c.decodeIfPresent(LockScope.self, forKey: .scope) ?? .selected
        applications = try c.decodeIfPresent(Set<ApplicationToken>.self, forKey: .applications) ?? []
        categories = try c.decodeIfPresent(Set<ActivityCategoryToken>.self, forKey: .categories) ?? []
        webDomains = try c.decodeIfPresent(Set<WebDomainToken>.self, forKey: .webDomains) ?? []
    }

    var isEmpty: Bool { applications.isEmpty && categories.isEmpty && webDomains.isEmpty }

    /// Whether applying these targets shields anything. "Lock everything except nothing" does.
    var locksSomething: Bool { scope == .allExcept || !isEmpty }

    /// The first of Apple's 50-token limits these targets break, described for an error, or nil.
    /// Under `.allExcept` only app and site exceptions are used; picked categories are ignored
    /// (their apps count, when the picker included them).
    var tokenLimitProblem: String? {
        let limit = QuietConstants.maximumShieldTokens
        switch scope {
        case .selected:
            if applications.count > limit { return "\(applications.count) apps chosen; Apple allows \(limit)." }
            if categories.count > limit { return "\(categories.count) categories chosen; Apple allows \(limit)." }
            if webDomains.count > limit { return "\(webDomains.count) sites chosen; Apple allows \(limit)." }
        case .allExcept:
            if applications.count > limit { return "\(applications.count) apps left open; Apple allows \(limit) exceptions." }
            if webDomains.count > limit { return "\(webDomains.count) sites left open; Apple allows \(limit) exceptions." }
        }
        return nil
    }

    var summary: String {
        let counts = "\(applications.count) apps, \(categories.count) categories, \(webDomains.count) sites"
        switch scope {
        case .selected: return "lock \(counts)"
        case .allExcept: return "lock all except \(counts)"
        }
    }
}

extension QuietStore {
    /// Nothing stored yet: the default scope. Stored but unreadable: lock nothing, rather than
    /// let a decoding failure in an extension turn into locking everything.
    var targets: LockTargets {
        get {
            guard defaults.data(forKey: Key.targets) != nil else { return LockTargets() }
            return decode(LockTargets.self, Key.targets) ?? LockTargets(scope: .selected)
        }
        nonmutating set { encode(newValue, Key.targets) }
    }
}
