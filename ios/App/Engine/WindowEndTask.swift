import BackgroundTasks
import Foundation

/// Best-effort tidy-up after the window ends: a background app refresh requested for the end
/// time. When (and whether) it runs is up to iOS; it is a backstop for ending the Live Activity
/// and clearing a lock whose end callback was missed, not a timer.
enum WindowEndTask {
    static func register() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: QuietConstants.windowEndTaskIdentifier, using: nil) { task in
            QuietStore().log("app: background tidy-up ran")
            let work = Task { @MainActor in
                await QuietHoursEngine.shared.settle()
                task.setTaskCompleted(success: true)
            }
            task.expirationHandler = { work.cancel() }
        }
    }

    static func schedule(at date: Date) {
        cancel()
        let request = BGAppRefreshTaskRequest(identifier: QuietConstants.windowEndTaskIdentifier)
        request.earliestBeginDate = date
        do {
            try BGTaskScheduler.shared.submit(request)
        } catch {
            QuietStore().log("app: could not request background tidy-up: \(error.localizedDescription)")
        }
    }

    static func cancel() {
        BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: QuietConstants.windowEndTaskIdentifier)
    }
}
