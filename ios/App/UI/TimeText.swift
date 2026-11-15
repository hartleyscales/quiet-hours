import Foundation

/// Times as the mock writes them, always in America/Los_Angeles.
enum TimeText {
    static let zone = TimeZone(identifier: "America/Los_Angeles") ?? .current
    private static let locale = Locale(identifier: "en_US_POSIX")

    private static var calendar: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = zone
        c.locale = Locale(identifier: "en_US")
        return c
    }()

    private static func formatter(_ format: String) -> DateFormatter {
        let f = DateFormatter()
        f.locale = locale
        f.timeZone = zone
        f.dateFormat = format
        return f
    }

    private static let clockFormat = formatter("h:mm")
    private static let ampmFormat = formatter("a")
    private static let weekdayFormat = formatter("EEEE")

    /// "7:00"
    static func clock(_ date: Date) -> String { clockFormat.string(from: date) }

    /// "5:00 – 7:00 PM", or "11:30 AM – 1:00 PM" when the halves differ.
    static func range(_ start: Date, _ end: Date) -> String {
        let a = ampmFormat.string(from: start), b = ampmFormat.string(from: end)
        if a == b { return "\(clock(start)) – \(clock(end)) \(b)" }
        return "\(clock(start)) \(a) – \(clock(end)) \(b)"
    }

    /// "5:00 PM"
    static func clockWithPeriod(_ date: Date) -> String { "\(clock(date)) \(ampmFormat.string(from: date))" }

    /// "Thursday"
    static func weekday(_ date: Date) -> String { weekdayFormat.string(from: date) }

    static func isSameDay(_ a: Date, _ b: Date) -> Bool { calendar.isDate(a, inSameDayAs: b) }

    /// "Today" on the day, otherwise the weekday.
    static func day(_ date: Date, now: Date) -> String {
        isSameDay(date, now) ? "Today" : weekday(date)
    }

    /// "In 2 days, 4 hours", "In 3 hours, 12 minutes", "In 8 minutes".
    static func until(_ date: Date, now: Date) -> String {
        let minutes = max(1, Int((date.timeIntervalSince(now) / 60).rounded(.up)))
        let days = minutes / (24 * 60), hours = (minutes / 60) % 24, mins = minutes % 60
        func unit(_ n: Int, _ word: String) -> String { "\(n) \(word)\(n == 1 ? "" : "s")" }
        if days > 0 {
            return hours > 0 ? "In \(unit(days, "day")), \(unit(hours, "hour"))" : "In \(unit(days, "day"))"
        }
        if hours > 0 {
            return mins > 0 ? "In \(unit(hours, "hour")), \(unit(mins, "minute"))" : "In \(unit(hours, "hour"))"
        }
        return "In \(unit(mins, "minute"))"
    }

    /// A post's age: "2m", "1h", "1d".
    static func age(since date: Date, now: Date) -> String {
        let minutes = max(1, Int(now.timeIntervalSince(date) / 60))
        if minutes < 60 { return "\(minutes)m" }
        if minutes < 24 * 60 { return "\(minutes / 60)h" }
        return "\(minutes / (24 * 60))d"
    }
}
