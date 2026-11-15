import DeviceActivity
import Foundation

/// Turns a window into the DeviceActivity schedule that enforces it.
enum WindowSchedule {
    static var activityName: DeviceActivityName { DeviceActivityName(QuietConstants.activityName) }

    /// End of the interval DeviceActivity will monitor. DeviceActivity rejects intervals under
    /// 15 minutes, so short windows are padded; the monitor ends them at the real end through
    /// `intervalWillEndWarning`.
    static func monitoredEnd(start: Date, end: Date) -> Date {
        max(end, start.addingTimeInterval(QuietConstants.minimumMonitoredInterval))
    }

    /// A one-off schedule (repeats: false) pinned to exact calendar dates, so it fires once.
    static func make(for window: QuietWindow, calendar: Calendar = .current) -> DeviceActivitySchedule {
        let padding = window.monitoredEnd.timeIntervalSince(window.end)
        var warning: DateComponents?
        if padding > 0 {
            let seconds = Int(padding.rounded())
            warning = DateComponents(minute: seconds / 60, second: seconds % 60)
        }
        return DeviceActivitySchedule(
            intervalStart: components(window.start, calendar),
            intervalEnd: components(window.monitoredEnd, calendar),
            repeats: false,
            warningTime: warning
        )
    }

    private static func components(_ date: Date, _ calendar: Calendar) -> DateComponents {
        var c = calendar.dateComponents([.year, .month, .day, .hour, .minute, .second], from: date)
        c.calendar = calendar
        return c
    }
}
