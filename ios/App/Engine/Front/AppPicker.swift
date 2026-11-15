import SwiftUI

extension View {
    /// Front mode has nothing to pick, so this does nothing. In Screen Time builds the same call
    /// presents Apple's app picker (`App/Engine/ScreenTime/AppPicker.swift`).
    func quietHoursAppPicker(isPresented: Binding<Bool>) -> some View {
        self
    }
}
