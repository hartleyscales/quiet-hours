import ManagedSettings
import ManagedSettingsUI
import UIKit

/// Supplies the content of the shield drawn over a locked app or site.
///
/// The shield is a fixed system template: icon, title, subtitle, primary button,
/// secondary button, and colours. Nothing else can be drawn. Visual properties are left
/// at the system defaults on purpose; the design is being done separately.
///
/// Apple runs this extension in a sandbox with no network access, so the people count comes
/// from shared storage, written earlier by the app.
final class QuietShieldConfiguration: ShieldConfigurationDataSource {

    override func configuration(shielding application: Application) -> ShieldConfiguration {
        makeShield()
    }

    override func configuration(shielding application: Application, in category: ActivityCategory) -> ShieldConfiguration {
        makeShield()
    }

    override func configuration(shielding webDomain: WebDomain) -> ShieldConfiguration {
        makeShield()
    }

    override func configuration(shielding webDomain: WebDomain, in category: ActivityCategory) -> ShieldConfiguration {
        makeShield()
    }

    private func makeShield() -> ShieldConfiguration {
        // The reach counter. Each draw request is the closest signal the platform gives us
        // that someone met the shield. See LOCK-NOTES.md for exactly what this counts.
        QuietCore.recordShieldRequest()

        let store = QuietStore()
        let copy = ShieldCopy(windowEnd: store.window?.end, peopleCount: store.peopleCount)
        return ShieldConfiguration(
            title: ShieldConfiguration.Label(text: copy.title, color: .label),
            subtitle: ShieldConfiguration.Label(text: copy.subtitle, color: .secondaryLabel),
            primaryButtonLabel: ShieldConfiguration.Label(text: copy.stay, color: .white),
            secondaryButtonLabel: ShieldConfiguration.Label(text: copy.leave, color: .systemBlue)
        )
    }
}
