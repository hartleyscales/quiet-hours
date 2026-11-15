import Foundation
import UserNotifications

/// Front mode: the local notification that tells someone they have stepped out and how long
/// they have to come back.
///
/// It is queued the moment Quiet Hours leaves the front, to fire `frontNotificationDelay` later
/// (2 s after the decision), and cancelled if a lock or call shows up first. It cannot fire at
/// the moment of leaving: at that moment a lock and an app switch look the same, and a
/// notification would light up the screen of every phone that had just been locked. Queuing it
/// in advance means it still fires if the app is suspended or killed before deciding.
enum SteppedOutNotification {
    static let identifier = "quietHours.steppedOut"

    static func request(since: Date, now: Date = Date()) -> UNNotificationRequest {
        let fireAt = since.addingTimeInterval(QuietConstants.frontNotificationDelay)
        let backBy = since.addingTimeInterval(QuietConstants.frontGracePeriod)
        let content = UNMutableNotificationContent()
        content.title = "You stepped out of quiet hours"
        content.body = "Come back within \(FrontLock.duration(backBy.timeIntervalSince(fireAt))) (by \(QuietHoursEngine.clock(backBy))) to stay in."
        content.sound = .default
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: max(1, fireAt.timeIntervalSince(now)), repeats: false)
        return UNNotificationRequest(identifier: identifier, content: content, trigger: trigger)
    }

    /// Removes it whether it is still queued or already showing.
    static func remove() {
        let center = UNUserNotificationCenter.current()
        center.removePendingNotificationRequests(withIdentifiers: [identifier])
        center.removeDeliveredNotifications(withIdentifiers: [identifier])
    }
}
