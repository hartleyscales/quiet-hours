# The redesigned Home screens (V9)

The owner rejected the first Home screens: they were centred lines of text stacked down the page. The Homes have been redrawn and approved. `design/screens.html` now holds the new versions; it is the spec, exactly as before. This note explains the structure so you build it as a system and not screen by screen. Sign-in, How it works, The lock and the question screen are unchanged.

## The structure

Every Home is left-aligned and has at most two parts under the wordmark bar.

1. **The hero**: one raised card (class `hero` in the mock) that is this week's window. Always the same anatomy, top to bottom:
   - a small caption on the left and, when the person is in, one underlined link on the right ("Opt out");
   - one large serif headline;
   - one line under it in the interface face;
   - a divider, then two or three figures side by side, each a serif value over a small label.
   The hero is the only raised object on a Home, apart from the board's sheet. It sits in the same place and is the same size on Voting, Decided, The day and the Summary.

2. **What sits under the hero** is one of two things:
   - **The board's sheet** (The day, Locked): an edge-to-edge sheet with rounded top corners that runs to the bottom of the screen, because it pulls up to fill the screen. It holds a header row ("Going on today" on the left, "See all 14" on the right), posts as rows (what in medium weight, where under it, how long ago at the right; your own post says "Yours · place" and has "Take down" at the right instead of the age), and the post field pinned at its foot. "See all" pulls the sheet up to just under the wordmark bar, covering the hero; the list then scrolls, fading over about 30pt at its top and bottom edges; the header's link becomes "Close". The post field stays pinned in both states. This replaces the old stack of cards and the old full-screen board entirely.
   - **Rows straight on the base surface** (Voting, Decided, the Summary): no card and no sheet. A header row (label left, a note right), then the rows, then at the very bottom of the screen one small line, or the dark "Opt back in" button when the person is out.

## Each Home

| Screen | Hero | Under the hero |
|---|---|---|
| 4 Voting | caption "This week's quiet hours" + "Opt out"; "When this week?"; "Closes Tuesday, 8:00 PM"; figures: time until voting closes, how many are in | On the base surface: "Pick a window" + total votes. Each option is a row: day and time on one line, the reason under it, then the tally bar and its count. Tapping a row votes; the chosen row is pressed into the surface. Bottom line: "You can change your vote until it closes." |
| 5 Decided | "Thursday"; "5:00 – 7:00 PM"; figures: time until it starts, how many are in | On the base surface: "How the vote went" + total votes; the same rows without reasons, not pressable, the winner pressed in. Bottom line says when the board opens. |
| 6 The day | "Today"; the time; figures: time until it starts, how many are in | The board's sheet, showing four posts at rest. |
| 7 Locked | No card. The near-black sky with stars is the hero and the moon (one dot per person in) is its object, centred, where it was. Under the moon, left-aligned: a caption row ("Quiet hours are on" + "Leave" on the right), "Until 7:00" in the serif, and the count line. | The board's sheet in its dark form, starting lower so three posts show at rest. |
| 9 Summary | caption with the day and time; "How it went"; "Quiet hours are over."; three figures: "N of M stayed", hours back, reaches | On the base surface: "The hour, told back" + "from N lines"; the highlights as rows in the serif, with dividers. Bottom line: "Voting for next week opens Sunday." |
| 9b Summary, before the recap | as 9 | Header note says "at H:MM"; one sentence says people are still writing, with the count of lines so far. |

Opted out (4b, 5b, 6b, 7b, 9c): the same screens, with both parts flat and pale (no raise, no sheet background, pale text), the caption replaced by "You're out this week." in ink, no "Opt out" link, and the post field or bottom line replaced by the one dark button ("Opt back in", or "Join until H:MM" on Locked in its light-on-dark form). 9c is the exception: full strength, with only the caption ("You were out this week.") and the bottom line changed.

## Data

Nothing about the data, the server calls or the rules changes. Every value on these screens is the server's: times and countdowns, counts, vote totals and per-option counts, posts and their ages, highlights, the count of lines. Countdown figures are short forms ("3h 12m", "1d 20h"). Post ages are short forms ("2m", "1h"). The figures update as state is polled.

## Motion between Homes

The structure makes the motion simple, and it must be built this way on both clients.

- **The hero card never moves or blinks** between Voting, Decided, The day and the Summary. Only what is inside it changes: caption, headline, line and figures cross-fade in place (about 250 ms). If a figure's value changes while the screen is showing, it changes without animation.
- **Rows on the base surface** leave by fading and sinking a few points, and arrive by fading up, 40 to 60 ms apart, top first.
- **The board's sheet** arrives by rising from the bottom edge to its resting place and leaves by sinking back, with the mock's easing (`cubic-bezier(.2,.8,.2,1)`, about 500 ms). Pulling it up and letting it down uses the same curve.
- **The day → Locked** is the one slow change (about 900 ms): the surface goes from light to near-black, the stars come out a few at a time, the moon's dots arrive scattered over about a second, the hero card fades out as the moon takes its place, the caption row, "Until 7:00" and the count fade in, and the sheet does not leave: it stays, glides down to its lower resting place and changes from its light form to its dark form.
- **Locked → the question**: the surface lightens, the stars go out, the sheet sinks away, and the moon's dots re-form into the speech-bubble picture, their colour blending from light to ink.
- **The question → the Summary**: the bubble's dots drift apart and fade; the hero card rises in (shadow growing from none); the rows fade up. When the recap lands, the highlights fade up one at a time, about 120 ms apart.
- **Opting out or back in** on any Home: no swap. Colours, shadows and backgrounds ease between the normal and the quiet state in place over about 300 ms.
- Anything not listed, and any jump between screens that are not neighbours: a plain cross-fade of about 250 ms, with light↔dark eased so it never flashes. Reduce Motion / `prefers-reduced-motion`: a 200 ms cross-fade for everything.
- After any transition, the screen must be exactly what a fresh render of it would be. No leftover layers, timers or half-states, including when changes arrive in quick succession.
