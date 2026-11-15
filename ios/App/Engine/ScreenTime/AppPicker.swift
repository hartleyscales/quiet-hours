import FamilyControls
import SwiftUI

extension View {
    /// Presents Apple's app picker and saves the result in the engine. The same call compiles in
    /// front mode, where it does nothing, so a UI never needs to know which mode is built.
    func quietHoursAppPicker(isPresented: Binding<Bool>) -> some View {
        modifier(QuietAppPicker(isPresented: isPresented))
    }
}

private struct QuietAppPicker: ViewModifier {
    @Binding var isPresented: Bool
    @State private var selection = FamilyActivitySelection()

    func body(content: Content) -> some View {
        content
            .familyActivityPicker(headerText: headerText, isPresented: $isPresented, selection: $selection)
            // Seed from the engine before the picker can be shown, and again whenever the scope
            // (and so the picks) changes, so Done never saves a stale or empty selection.
            .onAppear { seed() }
            .onChange(of: QuietHoursEngine.shared.state.lockScope) { _, _ in seed() }
            .onChange(of: isPresented) { _, shown in
                if shown { seed() }
            }
            .onChange(of: selection) { _, newValue in
                QuietHoursEngine.shared.updateSelection(newValue)
            }
    }

    private func seed() {
        let current = QuietHoursEngine.shared.pickerStartingSelection()
        if current != selection { selection = current }
    }

    /// Plain instructions so the picks mean what the person thinks. Placeholder words.
    private var headerText: String {
        switch QuietHoursEngine.shared.state.lockScope ?? LockTargets.defaultScope {
        case .selected: return "Choose what locks during quiet hours."
        case .allExcept: return "Everything locks during quiet hours. Choose what stays open."
        }
    }
}
