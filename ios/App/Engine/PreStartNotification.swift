import Foundation
import UserNotifications

/// The local notification shortly before the window starts.
enum PreStartNotification {
    static let identifier = "quietHours.preStart"

    static func requestPermission() async -> Bool {
        (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound])) ?? false
    }

    static func isAllowed() async -> Bool {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        return settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional
    }

    /// Schedules the notification `preStartLead` before the start. If that moment has already
    /// passed (a window starting in under five minutes), fires in five seconds instead, as long
    /// as that is still before the start. Returns when it will fire, or nil if it was skipped.
    /// `body` comes from the compiled mode (`LockBackend.preStartBody`).
    @discardableResult
    static func schedule(for window: QuietWindow, body: String, now: Date = Date()) async -> Date? {
        cancel()
        var fireAt = window.start.addingTimeInterval(-QuietConstants.preStartLead)
        if fireAt < now.addingTimeInterval(5) { fireAt = now.addingTimeInterval(5) }
        guard fireAt < window.start else { return nil }

        let content = UNMutableNotificationContent()
        content.title = "Quiet hours"
        content.body = body
        content.sound = .default

        let components = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute, .second], from: fireAt)
        let trigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: false)
        let request = UNNotificationRequest(identifier: identifier, content: content, trigger: trigger)
        do {
            try await UNUserNotificationCenter.current().add(request)
            return fireAt
        } catch {
            QuietStore().log("app: could not schedule notification: \(error.localizedDescription)")
            return nil
        }
    }

    static func cancel() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [identifier])
    }
}
