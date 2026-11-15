import Foundation

/// The words on the shield. Kept in one place so the design work can replace them.
struct ShieldCopy {
    let title: String
    let subtitle: String
    let stay = "Stay"
    let leave = "Leave quiet hours"

    init(windowEnd: Date?, peopleCount: Int?) {
        if let windowEnd {
            // "7:00" in a 12-hour locale, "19:00" in a 24-hour one.
            let time = windowEnd.formatted(.dateTime.hour(.defaultDigits(amPM: .omitted)).minute(.twoDigits))
            title = "Quiet hours until \(time)"
        } else {
            title = "Quiet hours"
        }
        switch peopleCount {
        case .none: subtitle = "You're in quiet hours."
        case .some(1): subtitle = "1 person is in quiet hours right now."
        case .some(let n): subtitle = "\(n) people are in quiet hours right now."
        }
    }
}
