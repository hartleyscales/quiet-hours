# Quiet Hours web app: build brief

You are building the web app for Quiet Hours, a hackathon project (AI@USC, due Sunday 11:00 AM PT). Every screen has already been designed and approved by the owner as a working HTML/CSS/JS mock. Your job is to turn those mocks into one real app wired to the real server. Fidelity to the mocks is the bar: do not redesign, restyle, reword or "improve" anything that is drawn.

Read these first:

- `design/screens.html`: the approved mocks, one phone per screen, with their CSS and behaviour. Open it, read its `<style>` and `<script>`. This is the visual and behavioural spec.
- `design/scripts/build_screens.py`: the script that generated that page. Easier to read than the built file (the CSS is in an f-string, so braces are doubled).
- `docs/CONTRACT.md` and `docs/API.md`: what the server does and every call.
- `design/scripts/color_moon.py`: the spec for the moon you must redraw in JavaScript (see "The Locked moon").

## Where and what

- Build in `web/` only. Art is already in `web/assets/`.
- Plain HTML, CSS and JavaScript (ES modules). No framework, no bundler, no build step, no npm dependencies in the shipped app. Fonts from Google Fonts as in the mock (Outfit, Instrument Serif).
- Do not edit anything in `server/`, `ios/`, `design/` or `docs/` (except you may add `docs/WEB-NOTES.md`). Another agent is editing `server/` and `docs/API.md` right now.
- Not a git repository. No commits, deploys, logins or account changes. No API keys in files.
- Everything must be written new, today. Do not copy code from any other project on this machine.

## The stage

The mocks are drawn on a fixed 390 x 844 stage with absolute positions. Keep that:

- One 390 x 844 stage, scaled uniformly with a CSS transform to fit the viewport.
- On a phone-sized viewport the stage fills the width, and the page background behind it matches the screen's surface colour (light greige, or near-black on the Locked screen) so any extra height looks intentional.
- On a wide viewport, show the stage centred as a phone with the same rounded frame the mock page uses, on the mock page's dark background.
- Respect `prefers-reduced-motion` as the mock does.

## Which screen shows when

Drive everything from `GET /v1/state` and its `me.can` flags. Do not hard-code which phase allows what; the server is the authority, and it is gaining two abilities while you work (rejoin during `live`, and skip/rejoin during `vote`). Poll state on a sensible interval and on focus, and re-render when the phase or the person's status changes.

| Situation | Screen in the mock |
|---|---|
| Not signed in | 1 Sign-in. After "Continue", the same screen asks for the code: the field's label becomes "Code", the button says "Sign in", the small line says where the code went. Keep the keyboard-up behaviour the mock's CSS already defines for sign-in (classes `k`). |
| Signed in, first time on this device | 2 How it works (three steps, dots re-form), then 3 The lock. On the web nothing can lock, so "Allow the lock" simply continues; but call `window.webkit?.messageHandlers?.quietHours?.postMessage({ type: "allowLock" })` first if it exists, so the iPhone wrapper can hook in later. Remember completion in `localStorage`. |
| Phase `vote`, status `in` | 4 Home, voting |
| Phase `vote`, status `skipped` | 4b |
| Phase `decided`, before the day of the window | 5 Home, selected / 5b opted out |
| Phase `decided`, board open (state tells you) | 6 Home, on the day, with the stack and the board / 6b opted out |
| Phase `live`, status `in` | 7 Home, locked (dark, stars, moon, stack and board) |
| Phase `live`, status `skipped` or `left` | 7b. The button is "Join until H:MM" and calls rejoin when `me.can.rejoin` is true; if the server refuses, show the screen without the button. |
| Phase `ended`, person can write a line and hasn't written or skipped | 8 The question (and its typing state). "Skip" is remembered per week in `localStorage`. |
| Phase `ended` otherwise | 9b Summary, before the recap lands |
| Phase `told` | 9 Summary / 9c if the person was out |

Every number, time, date, count, option, reason, board post and highlight comes from the server. Nothing in the mock's sample text may be left hard-coded where real data exists. Format times like the mock ("5:00 – 7:00 PM", "In 2 days, 4 hours", "Until 7:00"), in America/Los_Angeles.

Screens that are not designed, which you must build as plainly as possible in the same visual language and list in your report so the owner can review them:

- The settings sheet behind the gear: who is signed in, and "Sign out". Nothing else.
- Error and loading states: one quiet line of text in the existing style. No spinners, toasts or modals.

## Behaviours that must match the mock

- How it works: the dot animation exactly as in the mock, including the moon's coloured dots draining to ink.
- The board: the collapsed stack on Home, opening to the full-screen list with the top and bottom fades, wheel and touch scrolling, the composer, and "Take down" on your own post. Posting and taking down are real server calls. Posts are text plus a place: the mock's single composer field reads "What you're doing, and where". Split what the person types on the last comma or " at " into text and place if the API requires both; if there is no separator, ask for the place by changing the placeholder to "Where?" and taking a second entry. Keep it to that.
- Voting: tapping an option votes (changeable); the tally bars and counts are the server's.
- Opt out / Opt back in / Leave quiet hours: real calls, then re-render from the returned state.
- The question: 200-character limit with the counter, the field grows, "Add it" posts the line.
- Summary: three numbers on one line ("N of M stayed", hours back, reaches), then up to five highlights as centred serif lines. No cards.

## The Locked moon

On the Locked screen the moon is drawn with exactly one dot per person who is in (`liveCount`), and must be redrawn when that number changes.

- `web/assets/moon-col-dark.png.cells.json` has every cell of the moon's disc: `[i, j, density, onRim, r, g, b]`, plus the grid size. Cells are 2pt, dots are 1.33pt squares, as in the mock (the image is 390 x 240pt, drawn at top 100px).
- Port the algorithm in `design/scripts/color_moon.py` (mode `dark`, with N): serpentine Floyd-Steinberg dither of `min(0.97, density * gain)`, a bisection on `gain` so the dot count reaches N, the rim pass that places evenly spaced dots on rim cells following local density, then trimming or topping up the inside to hit N exactly. Use a seeded generator so the same N always gives the same moon.
- Check: for N = 3098 you must draw exactly 3098 dots and the result should look like `web/assets/moon-col-dark.png`. For N larger than the number of cells, fill every cell. For small N, draw N dots; do not fake it.
- Draw on a canvas at device pixel ratio. Recompute only when N changes.

## Running it

- Write `web/dev.mjs`: a tiny Node static server (no dependencies) for `web/` that proxies `/v1` and `/admin` to the API, so the app is same-origin in development. The API base must also be overridable (for example `window.QH_API` or a `<meta>` tag) for when it is hosted elsewhere.
- Start your own API for testing with a separate local database so you don't collide with the other agent: from `server/`, apply migrations and run `wrangler dev` on a port other than 8790 with `--persist-to` pointing at a directory inside your scratch space, using the same `--var` flags as the `dev:fake-ai` script in `server/package.json`. If you hit a schema error, a new migration has probably landed: re-apply migrations. Read `server/scripts/demo-seed.mjs` and `demo-week.mjs` to see how to seed a campus and step a week through its phases.
- In development the server returns the sign-in code in the response (see API.md). Use it to sign in during testing; if the sign-in response carries a code, show it in the small line under the field so a demo can proceed, worded so it is obviously a demo aid.

## A demo strip, outside the phone

For the demo video the owner must be able to move a week through its phases. When the page is opened with `?demo=<admin secret>` (never store the secret in code), show a small plain strip below the phone frame, outside the stage, with buttons that call the server's admin demo/time endpoints to jump to: voting, decided, on the day, live, ended, told. Without the query parameter there is no strip and no trace of it.

## Done means

- `node web/dev.mjs` plus the API gives a working app where you can sign in and walk a seeded week through every phase, and every screen in the table appears with real data.
- You have exercised, against the running API: sign-in, vote, change vote, opt out, opt back in, post to the board, take down, leave, rejoin (if the server allows it yet), write a line, and reading the recap. Say exactly which you ran and what happened. If you cannot look at the pages in a browser, say so plainly; do not claim visual checks you did not make.
- Report: files created, how to run it, the undesigned screens you had to make, anything in the mock you could not match and why, anything in API.md that didn't behave as documented, and anything left undone. Stop any servers you started.

Keep the scope to this brief. If something seems worth adding, list it in the report instead of building it.
