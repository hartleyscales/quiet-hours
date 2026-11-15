import SwiftUI

/// Bare debug screen for the lock engine. Plain system controls only; not the app's design.
/// Works in both modes: it reads only the engine's mode-agnostic API.
struct DebugView: View {
    @State private var engine = QuietHoursEngine.shared
    @State private var showingPicker = false
    @State private var alertMessage: String?
    @Environment(\.scenePhase) private var scenePhase

    private var state: QuietState { engine.state }
    private var isFront: Bool { state.mode == .front }

    var body: some View {
        Form {
            Section {
                Text("DEBUG SCREEN. Lock engine only. This is not the app's design.")
                    .font(.footnote.bold())
                row("Mode compiled in", isFront ? "front (Quiet Hours stays in front)" : "Screen Time")
                if let warning = state.setupWarning {
                    Text(warning).font(.footnote).foregroundStyle(.red)
                }
            }

            Section("Live state") {
                row("Access", state.accessDetail)
                row("Notifications", state.notificationsAllowed ? "allowed" : "not allowed")
                row("Live Activities", state.liveActivitiesEnabled ? "enabled" : "disabled")
                if state.usesAppPicker {
                    row("Lock scope", scopeText)
                    row("Selection", "\(state.selectedApplications) apps, \(state.selectedCategories) categories, \(state.selectedWebDomains) sites")
                }
                row("Window", windowText)
                row("Phase", state.phase.rawValue)
                if isFront { row("Back by", state.backBy.map(QuietHoursEngine.time) ?? "-") }
                row(isFront ? "In front since" : "Lock applied", stamp(state.lockAppliedAt, by: state.lockAppliedBy))
                row("Lock removed", stamp(state.lockClearedAt, by: state.lockClearedBy))
                row("Left early at", state.leftAt.map(QuietHoursEngine.time) ?? "-")
                row("Reach count", "\(state.reachCount)")
                if !isFront { row("Stay presses", "\(state.stayPresses)") }
                ForEach(state.details, id: \.self) { detail in
                    row(detail.label, detail.value)
                }
                row("Live Activity", state.liveActivity)
            }

            Section("Actions") {
                Button(isFront ? "Allow notifications" : "Authorize (Screen Time + notifications)") {
                    run {
                        try await engine.requestAuthorization()
                        await engine.requestNotificationPermission()
                    }
                }
                if state.usesAppPicker {
                    Picker("Picks mean", selection: Binding(
                        get: { state.lockScope ?? .allExcept },
                        set: { engine.setLockScope($0) })) {
                        Text("Lock all except picked").tag(LockScope.allExcept)
                        Text("Lock only picked").tag(LockScope.selected)
                    }
                    Button(state.lockScope == .selected ? "Choose apps to lock" : "Choose apps to leave open") {
                        showingPicker = true
                    }
                }
                Button("Start \(Int(QuietHoursEngine.testWindowLength / 60))-minute test window, 1 minute from now") {
                    run { try await engine.startTestWindow() }
                }
                Button("Leave early") {
                    run {
                        let left = await engine.leaveEarly()
                        if !left { alertMessage = "Nothing to leave: no window in progress." }
                    }
                }
                Button("Cancel window", role: .destructive) {
                    run { await engine.cancelWindow() }
                }
            }

            if !isFront {
                Section("Shield subtitle count (placeholder)") {
                    Stepper("People: \(state.peopleCount.map(String.init) ?? "not set")",
                            onIncrement: { engine.setPeopleCount((state.peopleCount ?? 0) + 1) },
                            onDecrement: { engine.setPeopleCount(max(0, (state.peopleCount ?? 0) - 1)) })
                    Button("Clear count") { engine.setPeopleCount(nil) }
                    Toggle("Leave opens the app (iOS 26.5+)", isOn: Binding(
                        get: { state.leaveOpensApp },
                        set: { engine.setLeaveOpensApp($0) }))
                }
            }

            Section("Event log, newest first") {
                if state.log.isEmpty {
                    Text("empty").foregroundStyle(.secondary)
                }
                ForEach(Array(state.log.enumerated()), id: \.offset) { _, line in
                    Text(line).font(.caption.monospaced())
                }
                Button("Clear log") { engine.clearLog() }
            }
        }
        .navigationTitle("Lock engine (debug)")
        .navigationBarTitleDisplayMode(.inline)
        .quietHoursAppPicker(isPresented: $showingPicker)
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await engine.didBecomeActive() } }
        }
        .task {
            await engine.didBecomeActive()
            while !Task.isCancelled {
                engine.refresh()
                try? await Task.sleep(for: .seconds(1))
            }
        }
        .alert("Engine", isPresented: Binding(get: { alertMessage != nil }, set: { if !$0 { alertMessage = nil } })) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(alertMessage ?? "")
        }
    }

    private var scopeText: String {
        switch state.lockScope {
        case .selected: return "lock only what is picked"
        case .allExcept: return "lock all except what is picked"
        case .none: return "-"
        }
    }

    private var windowText: String {
        guard let window = state.window else { return "none" }
        return "\(QuietHoursEngine.time(window.start)) – \(QuietHoursEngine.time(window.end))"
    }

    private func stamp(_ date: Date?, by source: String?) -> String {
        guard let date else { return "-" }
        return "\(QuietHoursEngine.time(date)) by \(source ?? "?")"
    }

    private func row(_ label: String, _ value: String) -> some View {
        LabeledContent(label) {
            Text(value).font(.callout.monospacedDigit()).multilineTextAlignment(.trailing)
        }
    }

    private func run(_ work: @escaping () async throws -> Void) {
        Task {
            do { try await work() } catch { alertMessage = error.localizedDescription }
        }
    }
}
