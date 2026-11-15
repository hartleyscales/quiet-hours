# Quiet Hours

**Tagline (Devpost's one-line field):** One window a week when USC puts its phones down, together.

**Working prototype:** https://quiet-hours-9gv.pages.dev (every screen, on sample data; the buttons under the phone step through a week)

---

## The problem

You'd put your phone down if everyone else did.

Economists have measured this. They offered more than 1,000 college students real money to quit TikTok for four weeks. On their own, students had to be paid $55 to do it. When everyone at their university would quit too, the same students offered to pay $24 to make it happen. Six in ten would be better off if the app didn't exist. They stay because everyone else is there (Bursztyn, Handel, Jiménez-Durán and Roth, *American Economic Review*, 2025).

Screen-time apps lock one phone at a time, and apps like Opal and Brick do that well. But everything on everyone else's phone keeps happening. The person holding out is the only one missing it, and that is why most people give in.

Until about 2000 none of this was a problem, because the phone stayed in the room. You left it on the desk when you went out. For as long as you were out, nothing could reach you, and the same was true of everyone you met. Every hour on a campus was a quiet one.

## The solution

Quiet Hours asks for about two of those hours back each week. The campus votes on when, and at that time every participating student's distracting apps lock together. It uses the same kind of lock those apps use, on every phone that's in, at the same moment. For about two hours, nothing is happening without you. It is a time when there's nothing to miss.

A week goes like this. The app offers three windows and you vote with one tap. The winner is set, with a countdown and a count of how many Trojans are in. When the window opens, every app you didn't choose to keep open locks, and the screen goes dark and shows the moon. Leaving takes one tap and is always allowed.

One thing stays open: a plain-text board of what people are doing and where. "Spikeball, anyone welcome. Alumni Park." It appears on the day and clears when the window ends. Afterward the app asks a single question, what did you do, and fifteen minutes later everyone who took part gets the same short recap of the hour in students' own words.

## How it uses AI

The AI has three jobs, and you never have to talk to it.

- **It proposes the windows.** Each week it reads the campus calendar and drafts three windows, with a reason for each. Students vote to pick one.
- **It keeps the board anonymous.** Every post and every answer is checked before anyone sees it. Anything that names a person goes back to its writer.
- **It tells the hour back.** Afterward it picks up to five highlights from what people wrote.

It is unobtrusive by design. There is no chat window and nothing to prompt, and its work simply shows up in the app. It is accurate: quotes appear exactly as written, and every count is checked against the answers behind it, so the recap can only say what students wrote. It is secure: no name reaches another student, if a check can't run the text is shown to nobody, and no answer can be traced to its writer. These rules are enforced in code and covered by tests.

## Tech stack

- **iPhone app:** native SwiftUI. The lock is written on Apple's Screen Time frameworks (FamilyControls, ManagedSettings, DeviceActivity), with shield extensions for the Stay or Leave screen and a Live Activity for the countdown.
- **Server:** TypeScript on Cloudflare Workers with a D1 database, built with Hono. It handles sign-in, the vote, opting in and out, the board, the anonymous answers and the recap. The phase of the week is derived from the clock, so every phone agrees. 118 tests pass.
- **AI:** Claude Opus 5.5 through the Claude API. Nothing in the design depends on one model.
- **Web demo:** the same screens in plain HTML, CSS and JavaScript on sample data, hosted on Cloudflare Pages, so anyone can walk through a week in a minute.
- **Design:** one picture, one statement and at most one thing to do on every screen. Every picture in the app is drawn in dots by code.

## Challenges

- **Apple's approval.** The lock needs Apple's Family Controls entitlement, which Apple enables only for approved developer teams. The lock is written and compiles, but it has not run on a phone yet.
- **Sign-in.** Signing in with a one-time code sent to a USC address is written and tested, but the service that sends the email is not connected yet.
- **Anonymity that holds.** "Anonymous" had to mean that no answer can be traced to its writer, and that the recap cannot leak a name or invent a line. That shaped the database and the two-pass way the recap is checked.
- **Keeping it quiet.** The first home screens carried six facts each. Getting each one down to a single statement took most of a day, and the AI went the same way: it has no interface of its own.

## What's next

It starts small and spreads.

1. **Apple's approval.** The request takes a few weeks.
2. **One hall.** A residence hall or Student Government picks a window and tries it. All it needs from USC is the email address students already have.
3. **The campus.** When your friends are in, you want in. Nobody wants to be the only one still scrolling.

After that, the window itself can learn. It is about two hours now, and its length could grow or shrink from week to week with how students say the last one went.

## Built with

Swift, SwiftUI, Screen Time API (FamilyControls, ManagedSettings, DeviceActivity), ActivityKit, TypeScript, Cloudflare Workers, Cloudflare D1, Hono, Claude API (Claude Opus 5.5), HTML/CSS/JavaScript, Cloudflare Pages
