import SwiftUI

/// 1 · Sign-in. After "Continue" the same screen asks for the code (not designed: the field's
/// label becomes "Code", the button says "Sign in", the small line says where the code went).
struct SignInScreen: View {
    @Environment(AppModel.self) private var model

    @State private var email = ""
    @State private var code = ""
    @State private var codeStep = false
    @State private var sentTo = ""
    @State private var devCode: String?
    @State private var problem: String?
    @State private var working = false
    @FocusState private var focused: Bool

    var body: some View {
        Stage(surface: Palette.surface) {
            StageReader { s, keyboard in content(s, keyboard) }
        }
        .task {
            switch DebugLaunch.focus {
            case "email":
                try? await Task.sleep(for: .seconds(1.5))
                focused = true
                if DebugLaunch.blur {
                    try? await Task.sleep(for: .seconds(2.5))
                    focused = false
                }
            case "code":
                email = DebugLaunch.email ?? ""
                start()
            default:
                break
            }
        }
    }

    private func content(_ s: CGFloat, _ keyboard: CGFloat) -> some View {
        // The mock's keyboard-up state (`.k`): everything rides up by the same amount and the
        // form sits on the keyboard.
        let kb = keyboard / s
        let up = keyboard >= KeyboardUp.minimum
        let shift: CGFloat = up ? 226 + max(0, kb - 336) : 0
        return ZStack(alignment: .topLeading) {
            // The moon stays where it is when How it works takes over: its dots are the same.
            LightMoonView()
                .designFrame(width: 390, height: 540)
                .hiddenWhileDots(entering: [.howToSignIn])
                .at(y: -shift)

            Text("Quiet Hours")
                .textStyle(.serif(74, line: 74))
                .foregroundStyle(Palette.ink)
                .shadow(color: Palette.surface, radius: 3 * s)
                .shadow(color: Palette.surface, radius: 3 * s)
                .shadow(color: Palette.surface, radius: 6 * s)
                .lineLimit(1)
                // It shrinks into How it works' headline (that screen draws the glide), and
                // grows back out of it.
                .vanishes(leaving: .signInToHow)
                .glides(.howToSignIn, fromScale: 50.0 / 74.0, fromY: SeamGeometry.headlineCentre - SeamGeometry.nameCentre)
                .centred(y: 402 - shift)

            Text("One window a week when USC puts its phones down, together.")
                .textStyle(.sans(18, 300, line: 26))
                .foregroundStyle(Palette.muted)
                .leaves(.signInToHow)
                .arrives(.howToSignIn, delay: 0.16)
                .centred(y: 490 - shift, padding: 48)

            form(s)
                .pinned(bottom: up ? kb + 16 : 34)
        }
        .contentShape(Rectangle())
        .onTapGesture { focused = false }
    }

    private func form(_ s: CGFloat) -> some View {
        VStack(spacing: 12 * s) {
            field(s)
                .leaves(.signInToHow)
                .arrives(.howToSignIn, delay: 0.18)
            GoButton(title: codeStep ? "Sign in" : "Continue", enabled: !working) { submit() }
                .leaves(.signInToHow, sink: 6)
                .arrives(.howToSignIn, delay: 0.23, rise: 8)
            FineLine(text: fineText)
                .designPadding(.top, 4)
                .leaves(.signInToHow)
                .arrives(.howToSignIn, delay: 0.28)
        }
    }

    private func field(_ s: CGFloat) -> some View {
        HStack(spacing: 12 * s) {
            Text(codeStep ? "Code" : "USC email")
                .textStyle(.sans(15))
                .foregroundStyle(Palette.muted)
                .fixedSize()
            Group {
                if codeStep {
                    TextField("", text: $code, prompt: Text("6 digits").foregroundStyle(Palette.placeholder))
                        .keyboardType(.numberPad)
                        .textContentType(.oneTimeCode)
                } else {
                    TextField("", text: $email, prompt: Text("you@usc.edu").foregroundStyle(Palette.placeholder))
                        .keyboardType(.emailAddress)
                        .textContentType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .submitLabel(.continue)
                        .onSubmit { submit() }
                }
            }
            .textStyle(.sans(16))
            .foregroundStyle(Palette.ink)
            .tint(Palette.ink)
            .multilineTextAlignment(.trailing)
            .focused($focused)
        }
        .designPadding(.horizontal, 22)
        .designFrame(width: 342, height: 58)
        .background {
            ZStack {
                DepthBox(.field, radius: 29)
                DepthBox(.fieldFocused, radius: 29).opacity(focused ? 1 : 0)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture { focused = true }
    }

    private var fineText: String {
        if let problem { return problem }
        if codeStep {
            if let devCode { return "Demo only: your code is \(devCode)." }
            return "We sent a code to \(sentTo)."
        }
        return "We'll send a code to your inbox."
    }

    private func submit() {
        guard !working else { return }
        if codeStep { verify() } else { start() }
    }

    private func start() {
        let address = email.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !address.isEmpty else {
            focused = true
            return
        }
        working = true
        problem = nil
        Task {
            defer { working = false }
            do {
                let result = try await model.startSignIn(email: address)
                sentTo = result.email
                devCode = result.devCode
                code = ""
                codeStep = true
                // The code field is a new field; focus it once it exists.
                try? await Task.sleep(for: .milliseconds(150))
                focused = true
            } catch let error as APIError {
                problem = Self.line(for: error)
            } catch {}
        }
    }

    private func verify() {
        let digits = code.filter(\.isNumber)
        guard !digits.isEmpty else {
            focused = true
            return
        }
        working = true
        problem = nil
        Task {
            defer { working = false }
            do {
                let session = try await model.checkCode(email: sentTo, code: digits)
                // Let the keyboard go down first, so How it works starts from a screen at rest.
                if focused {
                    focused = false
                    try? await Task.sleep(for: .seconds(0.45))
                }
                await model.adopt(session)
            } catch let error as APIError {
                problem = Self.line(for: error)
            } catch {}
        }
    }

    private static func line(for error: APIError) -> String {
        switch error.code {
        case "email_not_usc", "invalid_email", "invalid_request": return "Use your @usc.edu address."
        case "code_invalid": return "That code didn't work. Try again."
        case "too_many_codes", "too_many_attempts": return "Too many tries. Wait a little, then try again."
        case "demo_account": return "That address belongs to the demo campus."
        case "email_not_configured": return "Sign-in email isn't set up on the server yet."
        case "network": return "Can't reach Quiet Hours right now."
        default: return "Something went wrong. Try again."
        }
    }
}

/// The sign-in moon: every dot carries its own colour.
struct LightMoonView: View {
    @Environment(\.stageScale) private var s

    var body: some View {
        Canvas { context, _ in
            let moon = LightMoon.shared
            DotPainter.paintColored(moon.points, colors: moon.colors, in: context, scale: s)
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}
