# Quiet Hours iPhone app: build brief

You are building the real, native iPhone interface for Quiet Hours, a hackathon project (AI@USC, due Sunday 11:00 AM PT). The owner cares most about this being right. Every screen has been designed and approved as a working HTML/CSS/JS mock; your job is to build those screens natively in SwiftUI, wired to the real server and to the lock engine that already exists in this project. Fidelity to the mocks is the bar: do not redesign, restyle, reword or "improve" anything that is drawn.

Project root: `/Users/hartleyscales/quiet-hours`. Read first:

- `design/screens.html`: the approved mocks, one phone per screen (labels say which is which; `b`/`c` variants are opted-out or alternate states). Read its `<style>` and `<script>`: sizes, positions, colours, shadows, motion and copy all come from here. `design/scripts/build_screens.py` generated it and is easier to read (the CSS is in an f-string, so braces are doubled).
- `docs/CONTRACT.md`, `docs/API.md`: the server.
- `docs/LOCK-NOTES.md`, `ios/project.yml`, `ios/App/Engine/QuietHoursEngine.swift`, `ios/App/Engine/LockBackend.swift`: the lock engine and its two build variants (schemes `QuietHours` = Screen Time, `QuietHoursFront` = no entitlement).
- `docs/WEB-BRIEF.md`: a sibling web build from the same designs. Its table of "which screen shows when" and its "behaviours that must match the mock" apply to you unchanged. Read them there; they are not repeated here.

## Ground rules

- SwiftUI, Swift, iOS 26 minimum as the project already sets. No third-party packages.
- Work inside `ios/` only (plus an optional `docs/IOS-NOTES.md`). Put the interface in `ios/App/UI/`, the server client in `ios/App/API/`, bundled art and fonts in `ios/App/Resources/`, and update `ios/project.yml` so both schemes include them; regenerate with `xcodegen generate`. Do not change the lock engine's behaviour. If you need something small from it, add it without altering what exists and say so.
- Other agents are editing `server/`, `web/` and `docs/API.md` right now. Do not touch their files.
- Not a git repository. No commits, no deploys, no account or signing changes, no `-allowProvisioningUpdates`. No secrets in files.
- Everything is written new, today. Do not copy code from any other project on this machine.
- Do not download anything. Fonts are handled below.

## Layout

The mocks are drawn in a 390 x 844 space with absolute positions, which is within a few points of a real iPhone. Build each screen in that 390 x 844 design space inside one container view that scales it uniformly to the device's width and pins it to the top, with the screen's surface colour (light greige `#EAE5DE`, or the near-black on Locked) filling the whole display including safe areas. Text must stay sharp (scale the layout, not a bitmap). Keep the status bar readable: dark content on light screens, light on Locked.

## Type

The design uses Outfit (interface) and Instrument Serif italic (name, headlines, numbers). The font files will be placed in `ios/App/Resources/Fonts/` by the owner's assistant after you start. Write the app so it registers and uses them when present (list them under `UIAppFonts` and use `Font.custom` through one small helper), and falls back to the system font and New York italic when absent, so the build never depends on them. Use the exact sizes, weights and line heights from the mock's CSS.

## Depth

The look is soft neumorphism with strict meaning: raised = something you press; pressed-in = a field or a readout; pictures are flat. Reproduce the mock's shadows faithfully (highlight on the top edge, soft warm drop shadow underneath for raised things; inner shadow at the top for pressed-in things; the dark variants on Locked). CSS shadows with negative spread have no direct SwiftUI equivalent: get the same look with inner shadows (`.shadow(.inner(...))` shape styles) and a blurred, slightly inset shape underneath. Build these once as reusable styles and use them everywhere.

## Dots

All pictures are made of fixed-size square dots on a 2pt grid (dot 1.33pt).

- Sign-in moon: `web/assets/moon-col-light.png.json` has every dot as `[i, j, r, g, b]` (cell coordinates, 2pt cells). Copy the art you need from `web/assets/` into `ios/App/Resources/`. Draw dots with SwiftUI `Canvas`.
- How it works: port the mock's animation: the moon's dots re-form into the clock, lock and speech-bubble pictures, changing count quietly and draining from the moon's colours to one ink. The shapes are defined by signed-distance code in the mock's script (`clock`, `lock`, `bubble`, `phone`, with `fill`, `emboss`, `cast` and a Bayer matrix). Port that code to Swift so the pictures match. Drive it with `TimelineView`.
- The lock screen picture (`phone`) and the question screen picture (`bubble`) are the same shapes drawn still.
- Locked moon: exactly one dot per person who is in, redrawn when the count changes. Port the algorithm in `design/scripts/color_moon.py` (mode `dark` with N: serpentine Floyd-Steinberg dither with a bisection on gain, the rim pass, then trim or top up the inside to N) using the cell data in `web/assets/moon-col-dark.png.cells.json` (`[i, j, density, onRim, r, g, b]`). Use a seeded generator. For N = 3098 you must get exactly 3098 dots. The stars are `web/assets/locked-stars.png`.

## Server and state

- One small API client (`async`/`await`, `URLSession`) covering the calls in API.md. Base URL comes from an Info.plist key set in `project.yml` (default `http://localhost:8790` for the simulator, with local networking allowed); it must be easy to point at a hosted URL. Keep the sign-in token in the Keychain.
- One observable app model that polls `GET /v1/state` on a sensible interval and on becoming active, and decides which screen shows using the table in `docs/WEB-BRIEF.md`. Follow the server's `me.can` flags, not assumptions about phases; the server is gaining rejoin during `live` and skip/rejoin during `vote` while you work.
- Every number, time, option, reason, post and highlight is the server's. Format times as the mock does, in America/Los_Angeles.
- In development the server returns the sign-in code in its response; when it does, show it in the small line under the field, worded as an obvious demo aid.

## The lock engine

Talk to the lock only through `QuietHoursEngine`'s existing API, so the same interface works in both build variants.

- Screen 3 ("Everything locks."): "Allow the lock" calls the engine's authorization, asks for notification permission, and, where the engine reports it uses Apple's picker, presents the existing picker so the person chooses what stays open. Then onboarding is complete.
- When the server says a window is decided and the person is in, schedule it with the engine; if they opt out, cancel it. During `live`, "Leave quiet hours" tells the engine to leave and reports the leave to the server. If the engine says the person has left by itself (the shield's Leave button, or front mode's grace period running out), report that leave to the server with the time it happened. Report the engine's reach count to the server as the API describes. Give the engine the server's head count for its lock-screen copy if it has a place for one.
- "Join until H:MM" (opted out or left, during the window) calls the server's rejoin and, if it succeeds, starts enforcing through the engine for the rest of the window.
- Replace the debug screen as the app's root with the real interface, but keep `DebugView` reachable in DEBUG builds from the settings sheet.

## Not designed: build plainly, and list them in your report

- The code step after "Continue" on sign-in: the same screen, the field's label becomes "Code", the button says "Sign in", the small line says where the code went.
- The settings sheet behind the gear: who is signed in, "Sign out", and in DEBUG builds only: a way to open the debug screen, and a "Demo" section that takes the admin secret once (kept in the Keychain, never in code) and offers buttons that call the server's admin demo/time endpoints to jump the week to voting, decided, on the day, live, ended and told.
- Loading and error states: one quiet line of text in the existing style. No spinners, alerts or toasts.

Native touches that are in scope, and nothing beyond them: the keyboard behaviour the mock shows on sign-in and the question screen; a light selection haptic on voting and on opening the board; honouring Reduce Motion as the mock honours `prefers-reduced-motion`.

## Checking your work

- Both schemes must build with zero Swift warnings from your code: `xcodebuild -project QuietHours.xcodeproj -scheme QuietHours|QuietHoursFront -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build`, and the same for `generic/platform=iOS`.
- There may be no iPhone simulator runtime on this machine yet (`xcrun simctl list runtimes`); one may be installed while you work, so check again before you finish. If one is available: boot a simulator, run the Front scheme against your own local API, take a screenshot of every screen in every state, look at each one next to the mock, and fix what differs. If none is available, say plainly that nothing was looked at.
- For a local API use your own port and database so you don't collide with the others: from `server/`, apply migrations and run `wrangler dev` on a free port other than 8790 with `--persist-to` pointing into your scratch space and the same `--var` flags as the `dev:fake-ai` script in `server/package.json`. `server/scripts/demo-seed.mjs` and `demo-week.mjs` show how to seed a campus and step a week. If you hit a schema error, a new migration has landed: re-apply.

## Report

Files created and changed; how to run it; which screens and states you actually looked at and which you did not; the undesigned screens you made; anything in the mock you could not match and why; anything the engine or API did not do as documented; anything left undone. Stop any servers and simulators you started. Keep to this brief: ideas beyond it go in the report, not the code.
