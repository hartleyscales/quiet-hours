# Quiet Hours web app: notes

The web app in `web/`. Plain HTML, CSS and ES modules; no build step, no dependencies. The spec is `docs/WEB-BRIEF.md` and the approved mocks in `design/screens.html`; the Homes, the board and settings are `docs/HOMES-QUIET.md` and `design/homes-quiet.html` (November 15).

## Run it

```sh
node web/dev.mjs                     # http://127.0.0.1:8788, proxies /v1 and /admin to http://127.0.0.1:8790
PORT=8798 QH_API=http://127.0.0.1:8797 node web/dev.mjs   # other ports
```

- `http://127.0.0.1:8788/` runs on the **sample campus** (default). No API needed, no network calls apart from the page's own files and Google Fonts. State lives in the tab and resets on reload.
- `http://127.0.0.1:8788/?api=` runs against the **live API** through the proxy (`?api=<base url>` for an API elsewhere; it would need CORS, which the server does not send yet). `window.QH_API` or `<meta name="qh-api">` in `index.html` do the same.
- `?api=&demo=<admin secret>` adds the admin phase strip below the phone (live API only). The secret is held in memory only.

## Where data comes from

`app.js` loads exactly one of two modules with the same calls: `api.js` (the live API, docs/API.md) or `demo-api.js` (the sample campus). The screens never know which.

The sample campus is one week from the mocks: votes until Tuesday 8:00 PM; Thursday 5:00 – 7:00 PM wins; told back at 7:15. Its numbers are the mocks' (3,112 in, 1,203 / 867 / 512 votes before the viewer's own, 14 posts with one of yours, 3,098 in during the window, 3,041 of 3,112 stayed, 6,140 hours, 1,904 reaches, 1,287 lines, five highlights). Everything the viewer does follows the server's rules and moves the numbers by one.

The step row under the phone (`steps.js`), in the order a student meets the app:

| Step | Shows |
|---|---|
| Sign in | 1, signed out. Any `@usc.edu` address; the code is shown under the field; any code works. Then 2 and 3, then Voting. |
| How it works | 2 |
| The lock | 3; "Allow the lock" lands on Voting |
| Voting | 4, untouched until the viewer taps a pill (4b opted out) |
| Decided | 5 (5b) |
| The day | 6, with the pill that opens the board (6b) |
| Quiet hours on | 7, moon with one dot per person, and the board's pill (7b) |
| Just ended | 8, then 9b once the line is added or skipped (9b when opted out) |
| Told back | 9 (9c) |

"Opted out" is a switch: it skips the week for the viewer, so every screen that has an opted-out version shows it. It also turns on by itself when the viewer opts out or leaves inside the phone.

## Decisions worth knowing

- **Stage.** One 390 x 844 stage scaled with a transform. Phone-sized viewports (under 600px wide) fill the width, unless that would push the bottom off screen, in which case it fits the height and the surface colour fills the sides. Wider viewports show the mock page's phone frame on its dark background.
- **Keyboard-up layouts** (`k`, sign-in and the question) apply only where an on-screen keyboard appears (no hover, coarse pointer), and slide into place.
- **Highlights** get a closing period when they lack one, as the mock sets them.
- **The moon** (`moon.js`) is a port of `design/scripts/color_moon.py` (mode dark, N). N = 3098 gives exactly 3098 dots, 94% of them in the same cells as `web/assets/moon-col-dark.png` and the same 223 rim dots; the rest differ only by the seeded random trims. Small N draws N rim dots; N above 10,545 cells fills every cell.
- **The opted-out board in the sample** leaves out the viewer's own post. (Nothing shows the board to someone who is out any more; the live server keeps a post up after its writer opts out.)

## The Homes

Every Home is the quiet form of `docs/HOMES-QUIET.md`: one picture, one statement in the serif, one grey line, at most one thing to do, and the gear alone at the top right. Markup and CSS are the mock's own (`design/homes-quiet.html`). Each was compared with the mock at 390 x 844 on the sample campus: Voting (both states), Decided and out, The day, the Summary (both), the board and the three settings sheets have no pixel more than 8/255 apart, apart from the Locked moon (drawn on a canvas from the count, as before) and where the words are meant to differ (the sample's email, "Chosen in the iPhone app").

- **Voting.** Tapping a pill votes (changeable): it presses in, every pill fills from the left to its share of the server's counts, and the grey line becomes the chosen option's reason. Until then the grey line says when voting closes.
- **Voting, out.** The clock and the statement pale, "You're out this week." in ink, and the dark "Opt back in". The spec also asks for the three pills, pale; four 58pt pills don't fit under the grey line (they would start at 530, over the line at 522–543), so they are left out until that layout is drawn.
- **The board** is its own screen in the Home's layer (`over`, the last child of the stage): it slides up over The day or Locked from the pill ("N things going on", or "Nothing going on yet") and down from "Close". It is the mock's one board, dark from both Homes. It stays up if The day turns into Locked under it, and goes when the Home no longer offers it. `sheet.js` fills it: rows, ages, "Take down" (`DELETE /v1/board/:id`), and the field with its "Where?" second entry. A refusal is said for four seconds where the title is, in the grey line's face.
- **Settings** is a sheet in the same layer: the gear raises it, the Home dims behind it in its own surface colour, and the dim, Escape or a drag down closes it. Rows: this week (opt out / opt back in / leave / join, from `me.can`, left out when there is nothing to do; during the vote it has no window under it yet), "What stays open" (shown without its arrow and not pressable, "Chosen in the iPhone app"), How it works (replays the intro, then back to the Home), Sign out with the email. A week row does its call at once, closes the sheet, and the Home eases to its new state.
- **The Summary** shows the highlights one at a time in the server's order, every 3.8 s with the mock's 0.42 s fade; a tap moves on and stops the clock. With Reduce Motion they wait for a tap and change with a 200 ms cross-fade. Five dots show which one (none when there is one highlight). Before the recap: "People are still writing. Back at H:MM." (the time only while the phase is `ended`).
- **Countdowns** are the long forms the mock writes ("In 1 day, 20 hours."), and move as state is polled. A count the server hasn't sent is left out of its line.

## Changes of screen

`motion.js` puts each new screen up. Choreographed, both ways:

- **Sign in ↔ How it works.** The moon stays put (its dots are the same in both). The name shrinks into the headline; the subtitle and line fade, the field and button sink away; "Next" rises.
- **How it works ↔ The lock.** One more step of How it works: the dots re-form into the phone (1.1 s), the headline and subtitle cross-fade, the pips fade, the button glides to its place with its label cross-fading.
- **The lock ↔ Voting.** The phone's dots re-form into the clock (1.1 s); the words fade, "Allow the lock" sinks and the pills rise.
- **Between Homes** (`docs/HOMES-QUIET.md`, "Motion"): the statement, the line under it and the grey line cross-fade where they stand (250 ms); the picture re-forms as How it works does (clock ↔ daylight moon ↔ speech bubble, 1.1 s) or stays when it is the same; the pill rises in or fades and sinks. The day → Locked is the slow one (900 ms): the surface goes to near-black, the stars come out a few at a time, the daylight moon's dots go as the night moon's arrive, and the pill turns from light to dark in place. Locked → the question or the Summary re-forms the moon into the speech bubble. Where one end of a re-form is the daylight moon (an image, which the browser scales more softly than a canvas below 3x), the dots and the image hand over with a 160 ms cross-fade.
- **Opting out or back in** on any Home: colours ease between the normal and the pale state in place over 300 ms; the pill changes its look and label in place, or rises in or sinks away.
- **The board and settings** slide up from the bottom and back down with `cubic-bezier(.2,.8,.2,1)` over 500 ms, from wherever they are if interrupted; with Reduce Motion they fade in 200 ms.

Any other change is a 250 ms cross-fade of the whole stage, with the page behind it easing light to dark at the same pace. A change that arrives mid-way freezes the one in progress and cross-fades from there to the newest screen. With `prefers-reduced-motion`, every change is a 200 ms cross-fade.

Every effect is a Web Animation, a canvas or a copy of old content that is cancelled or removed when the change ends; a screen at rest is pixel-identical whichever way it was reached.

## What the live API is missing for these screens

- **CORS.** The API sends no CORS headers, so a web app on another origin cannot call it; use the same origin (dev.mjs proxy, or the same host in production).

Taking a post down (`DELETE /v1/board/:id`) and the count of lines so far (`numbers.lines`) are in the API now and the app uses both.
