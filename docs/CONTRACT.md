# Quiet Hours: shared contract

This file is the agreement between the iPhone app (`ios/`) and the server (`server/`). It covers behaviour and data only. It says nothing about how the app looks; the design is being done separately and must not be assumed here.

## What the product does

Once a week, every participating student's phone locks its distracting apps at the same time, for a window the campus chose by vote. One window for the whole campus. No groups or teams.

## The week, as phases

The server owns the clock. A week has six timestamps, and the phase is derived from them, never stored.

| Phase | True when | What is available |
|---|---|---|
| `vote` | `voteOpensAt` ≤ now < `voteClosesAt` | Proposed windows with a reason each, running tally, vote, skip or rejoin. Someone who skipped cannot vote; a vote cast before skipping still counts |
| `decided` | `voteClosesAt` ≤ now < `startsAt` | The winning window, how many are in, skip or rejoin. The board opens on the calendar day of `startsAt` (America/Los_Angeles) |
| `live` | `startsAt` ≤ now < `endsAt` | Lock is active. Live count, board, leave early. People who are out can join or come back |
| `ended` | `endsAt` ≤ now < `toldAt` | One optional line on what you did. First numbers |
| `told` | `toldAt` ≤ now < next week's `voteOpensAt` | The hour told back, and stats |

`toldAt` is 15 minutes after `endsAt`: the recap comes back while people are still together, not later that night. A line is at most 200 characters; the recap is at most five highlights of about 55 characters each.

A person is in by default each week. Their status for a week is `in`, `skipped` or `left` (with a time). Leaving early is always allowed.

## Things the server stores

- **User**: id, USC email (must end `@usc.edu`), created time.
- **Week**: id, the six timestamps, the winning option once decided.
- **Option** (a proposed window): week, start, end, a short reason (one or two sentences, at most 70 characters), vote count.
- **Vote**: user, week, option. One per user per week, changeable until the vote closes.
- **Participation**: user, week, status, left time, count of reaches.
- **Board post**: week, one line of text, a place, created time. Text only. Hidden after `endsAt`.
- **Line** (what someone did): week, text. Stored without any link to the user who wrote it.
- **Recap**: week, highlights (each one traceable to stored lines), stats.

## Numbers

- **In**: users whose status for the week is `in`.
- **Live count**: users with status `in` while the phase is `live`.
- **Reaches**: total times anyone met the lock screen over a locked app during the window.
- **Hours given back**: sum over participants of the time they were in during the window, in hours.
- **Stayed**: share of people who were in at `startsAt` and never left.

Every number shown is a real count from stored rows. Nothing is estimated or invented.

## What the AI does, and its rules

1. **Proposes windows.** Given a description of the campus's week (class load by hour, games, exams, sunset), it returns three candidate windows, each with its own length and a short reason: why that time suits the week, never what to do with it.
2. **Tells the hour back.** Given the stored lines, it picks and groups the remarkable ones into short highlights. It never invents, embellishes or merges lines into something nobody wrote. Counts in highlights ("41 people called a parent") must be real counts of matching lines.
3. **Edits.** Board posts and lines that name or target a person, or that are abusive, are not shown.

## On the phone

- The lock uses Apple's Screen Time frameworks (FamilyControls, ManagedSettings, DeviceActivity). The user chooses what locks once, in Apple's picker.
- Opening a locked app shows Apple's shield screen with our content: a title, a subtitle that includes the current count, and two buttons, **Stay** and **Leave quiet hours**.
- Leaving removes the lock for the rest of the window and is reported to the server.
- Each time the shield is met counts as one reach.
- Calls and the user's chosen essentials stay open.
- The lock must start and stop on time even if the app is not open.
