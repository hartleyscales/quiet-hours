import SwiftUI
import UserNotifications

@main
struct QuietHoursApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup {
            // The interface (App/UI). The lock engine's debug screen is reachable from the
            // settings sheet in DEBUG builds.
            RootView()
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        // Background task handlers must be registered before launch finishes.
        WindowEndTask.register()
        UNUserNotificationCenter.current().delegate = self
        // Create the engine now, not when a view first asks for it: in front mode it watches
        // app lifecycle events from launch on.
        _ = QuietHoursEngine.shared
        return true
    }

    // Show notifications even when the app is open, except a late "stepped out" one: the
    // person is plainly back in Quiet Hours.
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        if notification.request.identifier == "quietHours.steppedOut" { return [] }
        return [.banner, .list, .sound]
    }
}
