import Foundation
import ManagedSettings

/// Handles the two shield buttons.
/// - Stay (primary): counts the press and closes the locked app.
/// - Leave quiet hours (secondary): removes the lock for the rest of the window and records
///   the time. The shield is then redrawn (`.defer`); with the lock gone the app underneath
///   should become usable. On iOS 26.5+, if `leaveOpensApp` is set, it opens Quiet Hours instead.
final class QuietShieldAction: ShieldActionDelegate {
    private let store = QuietStore()

    override func handle(action: ShieldAction, for application: ApplicationToken,
                         completionHandler: @escaping (ShieldActionResponse) -> Void) {
        respond(to: action, completionHandler)
    }

    override func handle(action: ShieldAction, for webDomain: WebDomainToken,
                         completionHandler: @escaping (ShieldActionResponse) -> Void) {
        respond(to: action, completionHandler)
    }

    override func handle(action: ShieldAction, for category: ActivityCategoryToken,
                         completionHandler: @escaping (ShieldActionResponse) -> Void) {
        respond(to: action, completionHandler)
    }

    private func respond(to action: ShieldAction, _ completionHandler: @escaping (ShieldActionResponse) -> Void) {
        switch action {
        case .primaryButtonPressed:
            QuietCore.recordStay()
            completionHandler(.close)

        case .secondaryButtonPressed:
            // The lock removal is synchronous and done before anything else.
            QuietCore.leaveEarly(source: "shield")
            let response = leaveResponse()
            // Then try to end the Live Activity. Answer the system when that finishes or after
            // two seconds, whichever comes first, so the button never hangs.
            let reply = ReplyOnce(completionHandler)
            let store = self.store
            Task.detached {
                let ended = await LiveActivityBridge.finish(status: .left, leftAt: Date(), dismissal: .immediate)
                store.log("shield: ended \(ended) Live Activit\(ended == 1 ? "y" : "ies") from the extension")
                reply.send(response)
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { reply.send(response) }

        default:
            // Submenu items (iOS 26.4+) are not used.
            completionHandler(.none)
        }
    }

    private func leaveResponse() -> ShieldActionResponse {
        if #available(iOS 26.5, *), store.leaveOpensApp {
            return .openParentalControlsApp
        }
        return .defer
    }
}

/// Calls the system's completion handler exactly once.
private final class ReplyOnce: @unchecked Sendable {
    private let lock = NSLock()
    private var handler: ((ShieldActionResponse) -> Void)?

    init(_ handler: @escaping (ShieldActionResponse) -> Void) {
        self.handler = handler
    }

    func send(_ response: ShieldActionResponse) {
        lock.lock()
        let handler = self.handler
        self.handler = nil
        lock.unlock()
        handler?(response)
    }
}
