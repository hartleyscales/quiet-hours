import ActivityKit
import SwiftUI
import WidgetKit

// Placeholder presentation for the Live Activity. Plain system text only; the real look
// comes from the separate design work.

@main
struct QuietHoursWidgets: WidgetBundle {
    var body: some Widget {
        QuietHoursLiveActivity()
    }
}

struct QuietHoursLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: QuietActivityAttributes.self) { context in
            QuietActivityView(attributes: context.attributes, state: context.state, isStale: context.isStale)
                .padding()
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.center) {
                    QuietActivityView(attributes: context.attributes, state: context.state, isStale: context.isStale)
                }
            } compactLeading: {
                Text("Quiet")
            } compactTrailing: {
                QuietRemaining(attributes: context.attributes, state: context.state, isStale: context.isStale)
            } minimal: {
                QuietRemaining(attributes: context.attributes, state: context.state, isStale: context.isStale)
            }
        }
    }
}

private struct QuietActivityView: View {
    let attributes: QuietActivityAttributes
    let state: QuietActivityAttributes.ContentState
    let isStale: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(headline)
                .font(.headline)
            QuietRemaining(attributes: attributes, state: state, isStale: isStale)
                .font(.title2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var headline: String {
        let end = attributes.endsAt.formatted(.dateTime.hour(.defaultDigits(amPM: .omitted)).minute(.twoDigits))
        switch effectiveStatus(state, isStale, attributes) {
        case .quiet: return "Quiet hours until \(end)"
        case .steppedOut:
            let back = (state.backBy ?? attributes.endsAt).formatted(.dateTime.hour(.defaultDigits(amPM: .omitted)).minute(.twoDigits))
            return "Stepped out. Back by \(back)"
        case .left: return "You left quiet hours"
        case .ended: return "Quiet hours are over"
        }
    }
}

/// Time left in the window. `Text(timerInterval:)` counts down on its own, with no updates
/// from the app, which is what lets this run while the app is closed.
private struct QuietRemaining: View {
    let attributes: QuietActivityAttributes
    let state: QuietActivityAttributes.ContentState
    let isStale: Bool

    var body: some View {
        switch effectiveStatus(state, isStale, attributes) {
        case .quiet where attributes.endsAt > attributes.startsAt:
            Text(timerInterval: attributes.startsAt...attributes.endsAt, countsDown: true)
                .monospacedDigit()
        case .steppedOut where (state.backBy ?? .distantPast) > attributes.startsAt:
            // Counts down the grace period instead of the window.
            Text(timerInterval: attributes.startsAt...(state.backBy ?? attributes.endsAt), countsDown: true)
                .monospacedDigit()
        default:
            Text("Done")
        }
    }
}

/// The activity's stale date is the window's end, so a stale activity is an ended window even
/// if nothing was able to end it. Front mode: a stepped-out activity goes stale at the grace
/// deadline (or the window's end, if that comes first), so stale means the person did not come
/// back in time, or the window ended while they were out.
private func effectiveStatus(_ state: QuietActivityAttributes.ContentState, _ isStale: Bool,
                             _ attributes: QuietActivityAttributes) -> QuietActivityAttributes.ContentState.Status {
    guard isStale else { return state.status }
    switch state.status {
    case .quiet: return .ended
    case .steppedOut: return (state.backBy ?? attributes.endsAt) < attributes.endsAt ? .left : .ended
    case .left, .ended: return state.status
    }
}
