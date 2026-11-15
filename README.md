# Quiet Hours

One window a week when USC puts its phones down, together.

Built solo for the AI@USC hackathon, November 14–15, 2026.

**Try it:** https://quiet-hours-9gv.pages.dev (every screen, on sample data; the buttons under the phone step through a week)

## What it is

Once a week, at a time the campus votes on, every participating student's distracting apps lock together for about two hours. A plain-text board says what people are doing and where. Afterward the app asks one question, what did you do, and tells the hour back in students' own words.

The full description is in [submission/DEVPOST.md](submission/DEVPOST.md).

## What's here

| Folder | What it holds |
|---|---|
| `ios/` | The iPhone app in SwiftUI, with the Screen Time lock, shield extensions and a Live Activity |
| `server/` | The API in TypeScript on Cloudflare Workers with a D1 database, and its tests |
| `web/` | The web demo: the same screens in plain HTML, CSS and JavaScript on sample data |
| `design/` | The scripts that draw the app's dot pictures and the screen mocks |
| `docs/` | Design and engineering notes |
| `submission/` | The Devpost text, screenshots, the slide deck's source and the render scripts |

## Running it

- **Web demo:** `node web/dev.mjs`, then open the address it prints.
- **Server tests:** `cd server && npm install && npm test` (118 tests).
- **iPhone app:** open `ios/QuietHours.xcodeproj` in Xcode and run the `QuietHoursFront` scheme in a simulator.

## Where it stands

- The lock is written on Apple's Screen Time frameworks and compiles. It has not run on a phone yet, because Apple enables that capability only for approved developer teams.
- Signing in with a one-time code sent to a USC address is written and tested. The service that sends the email is not connected yet.
- The AI is Claude Opus 5.5 through the Claude API. It needs an API key set as a secret; none is in this repository.
