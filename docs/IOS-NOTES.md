# iPhone interface: notes

Written 2026-11-14 with the build in `ios/App/UI` and `ios/App/API`. The brief is [IOS-BRIEF.md](IOS-BRIEF.md).

## Run it

```sh
# API on its own port and database (from server/)
npx wrangler d1 migrations apply quiet-hours --local --persist-to <dir>
npx wrangler dev --port 8795 --persist-to <dir> --var ENVIRONMENT:development \
  --var SIGNIN_CODE_DELIVERY:INSECURE_DEV_RETURN_CODE_IN_RESPONSE \
  --var ADMIN_SECRET:local-dev-admin-secret --var AI_MODE:DEV_FAKE_AI_NOT_REAL

# App (from ios/)
xcodegen generate
xcodebuild -project QuietHours.xcodeproj -scheme QuietHoursFront \
  -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO -derivedDataPath <dd> build
xcrun simctl install <device> <dd>/Build/Products/Debug-iphonesimulator/QuietHoursFront.app
xcrun simctl launch <device> com.hms-web-development.QuietHours -QHAPIBaseURL http://127.0.0.1:8795
```

The API address is `QH_API_BASE_URL` in `ios/project.yml` (default `http://localhost:8790`), written to the Info.plist key `QuietHoursAPIBaseURL`. For a hosted server, change it there or pass `QH_API_BASE_URL=https://...` to xcodebuild; the `-QHAPIBaseURL` launch argument overrides it without rebuilding. Plain HTTP is allowed for local networking only (`NSAllowsLocalNetworking`).

To move a week through its phases from the phone: gear, then (DEBUG builds, below the four settings rows) enter the admin secret once (kept in the Keychain), then Voting / Decided / On the day / Live / Ended / Told. "Voting" seeds a demo week when there is none; "Told" also asks the server to write the recap. "Lock engine" opens the engine's debug screen.

Each Home without a server (DEBUG): `-QHDebugFixture vote|voted|vote-out|decided|decided-out|day|day-out|locked|locked-out|summary|summary-before|summary-out`, with `-QHDebugBoardOpen YES` (day, locked) for the board, `-QHDebugSettings YES` for the settings sheet, and `-QHDebugFixtureThen <name>` to move to another fixture after 2.5 s and watch the change. In a fixture, pressing a pill, "Opt back in", "Join" or the settings sheet's first row moves between fixtures the way the server would.

## Where things are

| File | What |
|---|---|
| `App/API/APIClient.swift`, `Models.swift`, `Keychain.swift` | Every call in API.md, the response shapes, the token in the Keychain. |
| `App/UI/AppModel.swift` | The one model: session, polling `/v1/state` (10 s live, 20 s otherwise, and at `nextChangeAt`), the board, which screen shows, every action, and keeping the lock engine in step. |
| `App/UI/HomeData.swift` | What each Home screen shows, as plain values (wording, numbers, which control appears). |
| `App/UI/RootView.swift` | Picks the screen from `AppModel.screen`. |
| `App/UI/Stage.swift`, `Design.swift`, `Depth.swift` | The 390 x 844 stage, type (fonts, sizes, CSS line heights) and the raised / pressed-in styles. |
| `App/UI/Dots.swift`, `LockedMoon.swift`, `HowItWorksScreen.swift` | The dot pictures, the Locked moon, the How it works morph. |
| One file per screen | `SignInScreen`, `HowItWorksScreen`, `AllowLockScreen`, `QuestionScreen`, `BoardScreen`, `SettingsSheet` (the settings sheet, and the quiet line screen). |
| `App/UI/HomeView.swift` | Every Home (`docs/HOMES-QUIET.md`): one picture, the statement, the time, the grey line, the pills; the Summary's highlights; the picture morph between Homes. |
| `App/UI/HomeData.swift` | What each Home, the board and the settings sheet show, as plain values (`HomeScene`, `BoardScene`, `SettingsScene`): every word, number and control is decided there. |
| `App/UI/Seams.swift`, `RootView.swift`, `Stars.swift` | Changes of screen: roles for the screens in a seam, the travelling dots, the stars coming out. |
| `App/UI/HomeFixtures.swift`, `DebugLaunch.swift` | DEBUG only: each Home with the mock's sample values (`-QHDebugFixture day`), and launch arguments that put the simulator in a state for screenshots. |

`HomeView` reads only a `HomeScene`; the layout holds no logic. Between Homes it is one view, so the statement stays on its line and only what changed moves. The board (`BoardScreen`) and the settings sheet (`SettingsOverlay`) are layers the root puts over the Home.

## Changes of screen

`RootView` keeps screens as layers. Choreographed seams (both directions where the web sibling has them): Sign in ↔ How it works, How it works → The lock, The lock → any Home (the phone's dots re-form into the Home's picture), Locked → the question (the night moon's dots re-form into the bubble), the question → the Summary (the bubble settles into the Summary's smaller one). Between Homes (inside `HomeView`): the words cross-fade in place (250 ms); between two daylight pictures (clock, daylight moon, bubble) the dots re-form as in How it works (1.1 s); a pill that goes fades and sinks 6 points, one that comes rises; The day → Locked is the slow change (900 ms: surface, stars, daylight moon out as the night moon's dots arrive, the pill light to dark). The board slides up and the settings sheet rises on `cubic-bezier(.2,.8,.2,1)` over 500 ms. During a seam the outgoing layer stays on stage, told it is leaving; the dots that travel are drawn in one overlay; when the seam ends the outgoing layer is removed and the incoming one is simply present. Everything else, and any change that arrives while a seam runs, is a 250 ms cross-fade of whole layers (200 ms for everything with Reduce Motion). Opting out or back in is not a change of screen: colours, shadows and backgrounds ease in place over 300 ms.

## Lock engine wiring

- "Allow the lock": `requestAuthorization()`, `requestNotificationPermission()`, then Apple's picker when `state.usesAppPicker`; onboarding completes when the picker closes (front mode: at once).
- Decided or live, status `in`: `scheduleWindow(id: week.id, start, end)` unless the same window is already stored. Status `skipped`: `cancelWindow()`.
- "Leave quiet hours": `leaveEarly()`, then `POST /v1/me/leave` with the engine's `leftAt`.
- A leave the engine recorded by itself (shield, or front mode's grace period) is reported with its time; reported leaves are remembered per week so they go once.
- Reaches: the engine's count is reported when it grows. Rescheduling resets the engine's count, so the total already reported is carried as a base.
- "Join until": `POST /v1/me/rejoin`, then `scheduleWindow` for the same week, which puts the lock back on (see below).
- `setPeopleCount(liveCount ?? in)` after each state read.

**Leave, then rejoin, in one window.** Front mode, simulator: left by staying out past the grace period, and by "Leave quiet hours"; rejoined through the API and through "Join until". Each time the engine took the window again (`leftAt` cleared, phase back to `active`, "IN" in its log) and the server showed `in`. Screen Time mode could not be run (no Family Controls in the simulator, and the team is free). By reading the code: `scheduleWindow` restarts DeviceActivity monitoring and clears the stored leave, the phase becomes `due`, and `ScreenTimeLock.reconcile` applies the shield while the app is open (it is: Join is pressed in the app).

## Choices worth knowing

The quiet Homes (2026-11-15, `HOMES-QUIET.md`):

- The gear is top right, as the spec says. The mock page draws it top left: `.s.hm .bar` (three classes) outranks `.q .bar{justify-content:flex-end}` (two), so the browser keeps `space-between`. `HomeView.gearX` is the one place to change it.
- Voting, out (not drawn): the three choices go flat and pale and sit closer (58 high, no gaps) directly above "Opt back in", because three pills and the button at their own sizes do not fit under the grey line.
- The board is drawn once, dark, and is used dark from The day as well as from Locked, with the mock's title "Going on now".
- Line breaks are made greedily before the text is set (`GreedyLines`), as the browser makes them. iOS otherwise moves a lone last word down ("41 people called / a parent.").
- "What stays open", Screen Time build: Apple's picker hands back tokens, not names, so the line under it counts the picks ("3 apps, 1 category"; "Nothing chosen yet"). Front build: no arrow, not pressable, "Chosen in the iPhone app".
- Settings' "How it works" sets `AppModel.replayingIntro`; the screen shows How it works until its last "Got it", which returns to the Home instead of moving onboarding on.
- The DEBUG part of the settings sheet (debug screen, demo controls) sits under a full-width line below the four rows; it is compiled out of release builds and hidden over fixtures.

- The stage scales to the device's width; on a phone shorter than 390 x 844's proportions (iPhone SE) it scales to the height instead, centred, so nothing is cut off.
- Your own posts come first on the board, as in the mock; the rest keep the server's order.
- Voting: the chosen option's reason, as the grey line, is clamped to three lines (it fits above the pills).
- The keyboard: SwiftUI's own keyboard avoidance is turned off for the stage; the keyboard's height is read inside SwiftUI's keyboard animation and the screens lay out their `.k` positions from it, so they move with the keyboard both ways.
- In a simulator build without code signing the Keychain does not survive a reinstall, so a reinstall signs you out. Signed builds keep it.
