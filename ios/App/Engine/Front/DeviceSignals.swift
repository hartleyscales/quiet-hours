import Darwin
import Foundation
import LocalAuthentication

/// Front mode: what the phone itself can tell us, through public APIs only.
enum DeviceSignals {
    /// When the phone last started, from the kernel (`sysctl kern.boottime`, public BSD API).
    /// A boot later than the start of an absence means the phone restarted during it.
    static var bootTime: Date? {
        var mib: [Int32] = [CTL_KERN, KERN_BOOTTIME]
        var value = timeval()
        var size = MemoryLayout<timeval>.size
        guard sysctl(&mib, u_int(mib.count), &value, &size, nil, 0) == 0 else { return nil }
        return Date(timeIntervalSince1970: TimeInterval(value.tv_sec) + TimeInterval(value.tv_usec) / 1_000_000)
    }

    /// How far the lock signal (protected data becoming unavailable about 10 s after a lock)
    /// can be trusted on this phone. See LOCK-NOTES.md, "Front mode".
    enum LockSignal: String {
        /// Face ID or Touch ID is set up, so iOS requires the passcode immediately and withholds
        /// protected data about 10 s after every lock.
        case reliable
        /// A passcode but no Face ID or Touch ID: "Require Passcode" may be set to a delay, and
        /// then the signal comes too late or not at all. Locks may count as stepping out.
        case uncertain
        /// No passcode: iOS never withholds protected data, so every lock counts as stepping out.
        case unavailable

        var description: String {
            switch self {
            case .reliable: return "reliable (Face ID / Touch ID on)"
            case .uncertain: return "uncertain (passcode, no Face ID / Touch ID)"
            case .unavailable: return "none (no passcode)"
            }
        }
    }

    /// Checks, without prompting, whether biometrics or a passcode are set up. Cannot see the
    /// "Use Face ID for iPhone Unlock" switch, so biometrics enrolled for other uses only read
    /// as reliable too.
    static var lockSignal: LockSignal {
        let context = LAContext()
        var error: NSError?
        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) { return .reliable }
        if let error, error.code == LAError.Code.biometryLockout.rawValue { return .reliable }
        error = nil
        if context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) { return .uncertain }
        return .unavailable
    }
}
