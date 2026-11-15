# The quiet Homes and the settings sheet

The owner approved a new form for every Home screen and for settings on November 15 ("I am happy with the set. Build."). It replaces the Homes described in `HOMES-V9.md`. The approved mock is `design/homes-quiet.html` (open it in a browser); `design/scripts/build_quiet.py` builds that page and is the easiest place to read each screen's markup and CSS. Sizes, positions, colours, shadows and copy come from there, exactly. Sign-in, How it works, The lock and the question screen are unchanged.

## The rule

Every Home is built like the intro screens: **one picture, one statement in the serif, one grey line, and at most one thing to do.** Nothing else is on the screen.

- There is no wordmark on any Home. The gear sits alone, top right.
- The statement is on the same line of every Home (top 452 in the 390 x 844 stage), so that moving between phases changes the words and the picture and nothing jumps.
- The serif (Instrument Serif italic) is used once per screen, for the statement. Every number and every other word is Outfit.
- Opting out, opting back in and leaving are in settings. A Home that is "out" also shows the one button back in.
- The board is its own screen, one tap from The day and Locked. It is no longer a sheet resting on the Home.
- The old hero card, its figures, the vote list with counts, the section headings ("Pick a window", "How the vote went", "The hour, told back"), the caption rows and the footer lines are all gone. Do not keep any of them.

## The screens

| Screen | Picture | Statement | Under it | The one thing to do |
|---|---|---|---|---|
| Voting | the dot clock | "When this week?" | grey line: when voting closes | three raised pills, one per option: the day on the left, the time on the right |
| Voting, after you vote | the same | the same | grey line: the reason for the option you chose (the server's `reason`) | the chosen pill is pressed in; every pill fills from the left to its share of the votes, as a faint tint, with no numbers |
| Decided | the daylight moon (the sign-in art) | the day ("Thursday") | the time in Outfit 24, then a grey line: how long until it starts, and how many are in | nothing |
| The day (board open) | the daylight moon | "Today" | the time, then the grey line | one raised pill: "N things going on", which opens the board |
| Locked | stars and the night moon (one fixed drawing) | "Until 7:00" | grey line: how many are in | one dark raised pill: "N things going on" |
| The board | none | "Going on now" in the serif, top left, with a round X button opposite to close it (the owner's ruling, November 15: he prefers the X to a "Close" link) | the posts as rows; your own shows "Yours · place" and "Take down" | the post field pinned at the bottom |
| Summary, before the recap | the dot speech bubble | "Quiet hours are over." | grey line: people are still writing, and when it comes back (the server's told time) | nothing |
| Summary | the dot speech bubble | one of the highlights, in the serif at 38 | five small dots showing which one, then a grey line: "N of M stayed." | tapping moves to the next highlight |
| Out this week (Voting, Decided, The day) | the same picture, pale | the same statement, pale | grey line in ink: "You're out this week." | one dark pill: "Opt back in" |
| Locked, out or left | stars and moon, dim | "Until 7:00", dim | "You're out. N Trojans in." | one light pill: "Join until 7:00" (only when the server allows rejoining) |

Notes:

- **Voting.** If the person has not voted, the pills are plain and the grey line says when voting closes. Tapping a pill votes (changeable). The tint widths are each option's count divided by the total, from the server. The option's reason is shown only as the grey line for the option the person chose. A person who is out does not see the pills at all: the one thing on the screen to do is "Opt back in" (the owner's ruling, November 15).
- **The count of things going on** is the number of posts on the board. With none, the pill reads "Nothing going on yet" and still opens the board, where the post field is.
- **Summary.** The highlights are shown one at a time, changing every 3.8 seconds with a 0.42 second fade, in the server's order; a tap goes to the next one and stops the timer. With Reduce Motion they do not change by themselves. "Hours back" and "reaches" are no longer shown anywhere. A person who was out sees the same screen with the grey line "You were out this week. N of M stayed."
- **The daylight moon** is the sign-in art at its own size; the night moon is one fixed drawing of 3,098 dots and no longer changes with how many people are in (Hartley, Nov 15). They are different sizes on purpose: the dots must stay the same size everywhere.
- **Stars.** `design/scripts/stars_quiet.png` is the star field for the new moon position (the old one left a gap above the moon). Use it on Locked.

## Settings

Settings is a sheet, not a screen. Pressing the gear raises it from the bottom over whichever Home is showing, and the Home dims behind it (a wash of the screen's own surface colour: light on light screens, near-black on Locked). Pressing the dimmed area, or dragging the sheet down, closes it. It has a small grab bar and no title. Its rows, top to bottom:

1. **This week.** One row whose words depend on the state: "Opt out of this week" with the window under it; "Opt back in" when the person is out; "Leave quiet hours" with "They run until H:MM" during quiet hours when the person is in; "Join until H:MM" during quiet hours when they are out and the server allows it. One tap does it, with no confirmation: the sheet closes and the Home eases to its new state. When there is nothing to opt out of (no window yet, or the window is over), the row is left out.
2. **What stays open.** The blocking configuration: which apps stay usable during quiet hours. Under it, one line summarising the choice. On the iPhone build that uses Screen Time it opens Apple's picker through the lock engine. Where there is no picker (the iPhone "front" build, and the web), the row is shown without its arrow, is not pressable, and its second line says "Chosen in the iPhone app".
3. **How it works.** Replays the three intro steps, then returns to where the person was.
4. **Sign out**, with the signed-in email under it.

Anything that exists only for development (the debug screen, the demo controls) goes below these in debug builds only, visibly separate, and never in a release build or the public web demo.

## Motion

- Between Homes: the statement, the line under it and the grey line cross-fade in place (about 250 ms). The picture cross-fades; if the dots can re-form from one picture to the next as they do in How it works, do that instead.
- The pill, when one Home has it and the next does not: it fades and sinks a few points; arriving, it rises.
- The day to Locked is the one slow change (about 900 ms): the surface goes from light to near-black, the stars come out, the daylight moon gives way to the night moon as its dots arrive, and the pill turns from light to dark.
- The board slides up from the bottom to cover the screen and back down, with `cubic-bezier(.2,.8,.2,1)` over about 500 ms. The settings sheet uses the same curve.
- Voting: the chosen pill presses in over 200 ms and the tints grow over 600 ms on the same curve.
- Opting out or back in: colours ease between the normal and the pale state in place over about 300 ms.
- Reduce Motion: a 200 ms cross-fade for everything.
- After any change the screen must be exactly what a fresh render of it would be: no leftover layers, timers or half-states.

## Data

Nothing about the server, its calls or its rules changes. Every time, count, option, reason, post and highlight is the server's. Do not invent numbers to fill a line: if the server has not sent something, leave that part of the line out.


## The board pill's arrow (Nov 15)

The "N things going on" pill carries the settings rows' arrow turned to point up (16 x 9, stroke 1.8), because the board rises from the pill, at its right end, 24 in from the edge, in the pill's text colour at half strength, so it reads as something that opens. Hartley chose this over a notification badge: nothing in the app should pull at you. A plain dot for unseen posts was discussed and left for later.
