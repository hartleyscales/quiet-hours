# Server notes

The Quiet Hours server is a Cloudflare Worker (TypeScript, Hono, Zod) with a D1 database, in `server/`. Endpoints and examples: [API.md](API.md). Behaviour and data: [CONTRACT.md](CONTRACT.md). Phone-side limits that shaped the server: [LOCK-NOTES.md](LOCK-NOTES.md).

Last verified 2026-11-14: 103 tests pass, `tsc` is clean, and a full week ran end to end under `wrangler dev` (transcript at the end).

## 1. What was on disk

A previous session built most of the server and was cut off before verifying or documenting it. What it left worked: 94 tests passed and `tsc` was clean before I changed anything. It had also run the server locally (the local D1 under `server/.wrangler/state` had migration 0001 applied, a demo week and two signed-in testers).

Already there and kept as it was:

- Schema for everything the contract stores (`migrations/0001_init.sql`), with `is_demo` on every seeded table.
- Phase logic derived from timestamps (`src/phase.ts`), the Los Angeles calendar-day board rule with daylight-saving handling (`src/time.ts`), and tests at every boundary.
- Sign-in by one-time code behind a `CodeSender` interface, with a development mode named `INSECURE_DEV_RETURN_CODE_IN_RESPONSE` that refuses to run outside `ENVIRONMENT=development`, puts a warning in the response and a header on every response.
- The state call, voting, skip and rejoin, the board, anonymous lines, recap reading, and the admin calls the brief listed.
- The numbers, counted in SQL from participation rows (`src/numbers.ts`).
- The three AI jobs behind one `AiProvider` interface, with the recap rules enforced in code (`src/ai/recap.ts`), proposal validation (`src/ai/proposals.ts`), a realistic campus-week example (`examples/campus-week.example.json`), a development-only fake AI, and a test stub.
- The demo seed (`src/demo.ts`, `scripts/demo-seed.mjs`) and an end-to-end script (`scripts/demo-week.mjs`).

No docs existed. I found no copies of this code in other projects on the machine (searched for distinctive identifiers and comments).

## 2. What I changed

In order of importance.

1. **Late leaves.** Before: a leave was accepted only during `live` and `ended`, only for the current week, and a second report was ignored. That loses every leave whose report waits past `toldAt`, which LOCK-NOTES says is normal (the shield extension has no network; the report waits for the app). Now `POST /v1/me/leave` takes `weekId` and works for any week whose window has started, current or past, through `told` and after. It uses the phone's `leftAt`; keeps the earliest of several reports; rejects a time well before the window (probably from another week); ignores a time at or after `endsAt` (not early). Same for reach reports.
2. **Recap stats follow late reports.** Before: the recap served the stats snapshot taken when it was written, so a late leave would make the recap disagree with `/v1/state`. Now the stats are recomputed whenever the recap is read; the snapshot is still stored in the row as a record.
3. **The reach count is named as approximate.** Migration `0002_approx_reaches.sql` renames the column to `approx_reaches`. The API field is `approxReaches` in `me`, `numbers` and recap stats, and the phone sends `{"approxReaches": n}` (it was `{"total": n}`). Comments and docs say what the phone actually counts. A test fails if any stored column or response field carrying the count drops the "approx".
4. **Claude API requests, checked against the claude-api skill.**
   - Model: every job now uses `claude-opus-5-5`. Before, proposals and recap used `claude-fable-5-2` and the two checks used `claude-haiku-5-5`. The skill's rule is to use `claude-opus-5-5` unless the user names another model, and not to downgrade for cost on the user's behalf. Changing it is one constant (`MODEL` in `src/ai/anthropic.ts`).
   - Refusal fallback (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) is now on every request. Before, the two Haiku checks had none.
   - Effort is set on every request (Opus 5.5 defaults to `medium`): `high` for proposals and the recap draft, `medium` for the recap's group check, `low` for the editing check.
   - `max_tokens`: 64000 for the streamed drafts, 16000 for the checks. Before, the checks had 4096, which thinking (always on for this model, and counted against `max_tokens`) could exhaust and cut off the answer.
   - No `thinking` or sampling parameters are sent. The SDK (`@anthropic-ai/sdk` 1.8.0, the latest) sends API version `2026-10-21`.
5. **Demo time control with weeks back to back.** Before: `jumpTo` moved a week rigidly, so stepping a new week to `live` right after another week had been told pushed its vote over that week and failed with `week_overlap`. Now only the already-past vote is shortened to fit; the window, `toldAt` and everyone's times still move rigidly. The overlap error now says what to do.
6. **Dev scripts.** `npm run dev` and `npm run dev:fake-ai` apply local migrations first (wrangler dev does not). Added `server/.gitignore` covering `.dev.vars`, `.wrangler/` and `node_modules/`.
7. **End-to-end script.** `scripts/demo-week.mjs` now states the status it expects from every call and exits 1 on any surprise, and plays a second tester whose leave is reported after `toldAt`.
8. **Tests.** 94 became 103: a new `test/late-reports.test.ts` (late leave in `ended`, in `told` after the recap, for a past week after the next vote opened, bad and ignored times, mid-window joiners, skipped people, approximate naming), a back-to-back timeline test, and rewritten adapter tests for the new request shape.

Running `npm run dev` applied `0002` to the existing local database. Nothing else in it was changed.

## 3. Decisions the contract left open

- **"Six timestamps."** Five are stored on the week: `voteOpensAt`, `voteClosesAt`, `startsAt`, `endsAt`, `toldAt`. The sixth, next week's `voteOpensAt`, is read from the next week's row. The current week is the one whose vote opened last, so `told` ends exactly when the next vote opens.
- **The window comes from the vote.** `startsAt` and `endsAt` are null until the vote is decided, then copied from the winning option, and `toldAt` is set 15 minutes after `endsAt` (the contract's rule). Admins create a week with three times and add options; the `toldAt` they give is only the latest it can be, and options must end at least 15 minutes before it.
- **Deciding.** The winner is picked by count the first time anything reads the week after `voteClosesAt`, or when an admin closes the vote early. Ties go to the option listed first. A week with no options never decides.
- **Option vote counts** are counted from the votes table on every read rather than stored, so they cannot drift.
- **In by default** means: the first time a person's app reads state during `vote`, `decided` or `live`, they get a participation row with status `in`. People whose app never opened that week are not counted anywhere; their phone has no window to lock either.
- **Skip and rejoin** during `vote` and `decided`; someone who skipped cannot vote, but a vote cast before skipping is kept. During `live`, rejoin lets someone who skipped join (counted from then) or someone who left come back (the gap not counted); skip is not possible once the window has started. A leave reported for a time before the person's latest rejoin is ignored (migrations/0003).
- **Leaving.** See section 2. The tolerance before `startsAt` is 5 minutes (`CLOCK_SKEW_MS`).
- **Reaches** are a running total per person per week; the server keeps the largest it has seen.
- **The board** opens at midnight in Los Angeles on the window's calendar day, but never during the vote (if the vote closes that day, it opens when the vote closes). It closes at `endsAt`, and posts are hidden from then on. Only people who are `in` can post: 5 posts a week, 140 characters plus a 60-character place.
- **Lines** only during `ended`, one per person who was in the window, 200 characters.
- **Numbers.** `stayed.of` counts people whose `joinedAt` is at or before `startsAt` and who are `in` or `left`; `stayed.count` leaves out anyone who left, even if they came back. Someone who first opened the app, or joined after a skip, mid-window counts toward `in` and hours from their `joinedAt` but not toward `stayed`. Time between leaving and coming back is not counted in hours. `hoursGivenBack` is rounded to 0.1, with exact `secondsGivenBack` beside it. Each number is shown only in the phases the contract names it (table in API.md).
- **Editing check (AI job 3) fails closed.** Text the check rejects is not stored at all, so the writer can rewrite it. Text the check could not run on is stored as pending and shown to nobody but its writer, until `POST /v1/admin/weeks/:id/moderate` runs it. The prompt allows family roles ("called my mom") and public figures, and rejects names, handles, phone numbers, and pointed references to an identifiable person.
- **The hour told back (AI job 2).** Two kinds of highlight: a quote (one line, shown from storage, never the model's copy) and a group (one sentence, one number in digits equal to the lines attached, no amount words, every line confirmed by a second pass). At most 5 highlights, each asked for at most 55 characters and dropped over 60 (a quote is never cut), up to 3 attempts. Only lines that passed the editing check go in.
- **Window proposals (AI job 1)** are a draft for the admin: three windows of 30 minutes to 4 hours inside the week's bounds, each with a reason of one or two short sentences, at most 70 characters (the same check applies to options an admin sets). `apply: true` makes them the options.
- **Demo data** lives in the same tables, marked `is_demo = 1`. Demo users have `+quiet-hours-demo@usc.edu` addresses (the schema only allows USC addresses) and cannot be signed into, so no code is ever sent to them.

## 4. What is not production-ready

1. **No email is sent.** Production sign-in answers `503 email_not_configured`. A real `CodeSender` needs an email provider that can send to any `@usc.edu` address (Resend, Postmark, Amazon SES, or Cloudflare's own if it can by then) and its key as a secret. Only `src/auth.ts` and `codeSender()` in `src/app.ts` change.
2. **Line anonymity has limits outside the live database.** The current database cannot link a line to its writer: no user, no time, no insertion order. But the line insert and the writer's `wrote_line = 1` happen in the same transaction, so anything that records *when* writes happened can link them: D1 Time Travel (point-in-time restore, kept for days to weeks depending on plan), request logs or Workers traces of `POST /v1/lines` with the caller's session, or a database export taken between two submissions. Before real use: queue lines and insert them in shuffled batches (for example, all at `toldAt`), keep Workers request logging off for that route, and say plainly in the app what "anonymous" covers. Line and post text is also sent to the Claude API for the editing check and the recap.
3. **The recap is not written automatically.** An admin calls `POST /v1/admin/weeks/:id/recap`. A Cron Trigger at each `toldAt` (plus a retry of pending editing checks) would remove that step.
4. **Admin is one shared secret** in a header. No roles, no audit log. The demo timeline and seed calls work in production too, and can move or pollute a real week. Gate them behind `ENVIRONMENT` or a separate secret before real use.
5. **No rate limiting by IP or device.** Limits are per address (5 codes an hour, 5 tries per code) and per person (5 posts a week). Add a Cloudflare rate-limiting rule on `/v1/auth/*`.
6. **The editing check runs inline** on every post and line: one Opus 5.5 request at low effort, a few seconds. If the API is down, text waits as pending until an admin re-runs the check.
7. **Numbers are only as true as what phones report.** `approxReaches` is an approximation by construction. `stayed` can count someone who revoked Screen Time access instead of pressing Leave (LOCK-NOTES limit 8). Hours given back assume the lock was on for everyone `in`.
8. **Smaller things.** Sessions last 180 days, revocable only by signing out. `GET /v1/weeks` is not paginated. The board's `before` cursor pages by time only, so two posts in the same millisecond could straddle a page. Wrangler is 4.124 (4.162 is out). The development fake AI is compiled into the Worker, though it refuses to run outside development.

## 5. Deploying later

Nothing below has been run. It needs a Cloudflare account and Hartley's login.

```sh
cd server
npm ci
npm test

npx wrangler login                                  # by hand, in a browser
npx wrangler d1 create quiet-hours                  # prints a database_id
#   put that id in wrangler.toml, replacing 00000000-0000-0000-0000-000000000000
npx wrangler d1 migrations apply quiet-hours --remote

openssl rand -base64 32 | npx wrangler secret put ADMIN_SECRET   # keep a copy somewhere safe
npx wrangler secret put ANTHROPIC_API_KEY                         # paste the key at the prompt

# Before sign-in can work: write the email CodeSender (section 4, item 1) and add its key:
#   npx wrangler secret put <PROVIDER>_API_KEY

npx wrangler deploy
curl -s https://quiet-hours.<your-subdomain>.workers.dev/v1/health
#   expect "environment":"production", "insecureDevModes":[], "ai":{"mode":"anthropic","configured":true}
```

`wrangler.toml`'s `[vars]` are the production values (`ENVIRONMENT=production`, `SIGNIN_CODE_DELIVERY=email`, `AI_MODE=anthropic`). Development modes are only ever set on the `wrangler dev` command line. A deploy that somehow carried one would answer `500 server_misconfigured` on every route rather than serve codes in responses.

Then create the first week with `POST /v1/admin/weeks`, propose or set its options, and let the clock run.

## 6. Last end-to-end run

`wrangler dev` with the development fake AI, on a fresh local database, then `npm run demo:week`. Every call states the status it expects; `!!` would mark a surprise. The demo week is seeded with 48 simulated participants; `tester@usc.edu` and `late.leaver@usc.edu` act only through the public API. The fake AI picks proposals and groups by fixed rules, and its output says so. Times are Los Angeles. The admin timeline moves the week, so dates jump.

```text
== health
   GET    /v1/health                                 200  environment=development insecureDevModes=signin-codes-in-responses,fake-ai ai=dev-fake/configured

== reset demo data, seed a demo week (DEMO DATA), sign in two testers
   DELETE /v1/admin/demo                             200  removed {"weeks":0,"users":0,"posts":0,"lines":0,"votes":0,"participation":0}
   POST   /v1/admin/demo/seed                        201  week=wk_f44f3w3exs7zke demoUsers=48 votes=44
   POST   /v1/auth/start                             400  email_not_usc: Use your USC email address (it must end in @usc.edu).
   POST   /v1/auth/start                             200  delivery=dev-response devCode=590077
   POST   /v1/auth/verify                            200  tester@usc.edu -> session token
   POST   /v1/auth/start                             200  delivery=dev-response devCode=526814
   POST   /v1/auth/verify                            200  late.leaver@usc.edu -> session token

== vote
   GET    /v1/state                                  200  phase=vote me=in board=closed in=49
         option op_qehbs4z946xk82  11/17/26, 9:00 PM for 60 min  votes=13  "DEMO: The latest window, after the evening review sessions have emptied out of Leavey."
         option op_efrxpbn0jv7xsa  11/17/26, 7:30 PM for 90 min  votes=21  "DEMO: Classes are nearly over by 7:30 and nothing big is on, so most people are free at once."
         option op_p5rk6pff3hngws  11/18/26, 8:00 PM for 120 min  votes=10  "DEMO: A longer stretch on the quietest night of the week, with no games and no exams the next morning."
   POST   /v1/vote                                   200  myVote=op_qehbs4z946xk82 tallies=14,21,10
   POST   /v1/vote                                   200  changed: myVote=op_efrxpbn0jv7xsa tallies=13,22,10
   GET    /v1/state                                  200  phase=vote me=in board=closed in=50
   POST   /v1/me/skip                                409  phase_closed: You can skip only during: decided. The week is in "vote".
   POST   /v1/admin/weeks/wk_f44f3w3exs7zke/proposals 200  3 proposals from dev-fake-ai (not a model) in 1 attempt(s), applied=false
         proposal 2026-11-16T16:00 for 60 min  "[FAKE AI, development only] Candidate 1, picked by a fixed rule rather than by reading the campus week."
         proposal 2026-11-17T13:10 for 90 min  "[FAKE AI, development only] Candidate 2, picked by a fixed rule rather than by reading the campus week."
         proposal 2026-11-18T10:00 for 120 min  "[FAKE AI, development only] Candidate 3, picked by a fixed rule rather than by reading the campus week."

== decided
   POST   /v1/admin/weeks/wk_f44f3w3exs7zke/close-vote 200  phase=decided winner=op_efrxpbn0jv7xsa
   GET    /v1/state                                  200  phase=decided me=in board=closed in=50
         winner 11/17/26, 7:30 PM to 11/17/26, 9:00 PM (22 votes); board opens 11/17/26, 12:00 AM
   POST   /v1/vote                                   409  phase_closed: You can vote only during: vote. The week is in "decided".
   POST   /v1/me/skip                                200  me=skipped
   POST   /v1/me/rejoin                              200  me=in
   POST   /v1/admin/demo/seed                        201  demo skips=5
   GET    /v1/state                                  200  phase=decided me=in board=closed in=45
   POST   /v1/me/leave                               409  phase_closed: You can leave only once the window has started.

== live (moved 40 minutes into the window)
   POST   /v1/admin/weeks/wk_f44f3w3exs7zke/timeline 200  phase=live startsAt=11/14/26, 3:06 PM
   POST   /v1/admin/weeks/wk_f44f3w3exs7zke/timeline 200  phase=live startsAt=11/14/26, 2:26 PM
   POST   /v1/admin/demo/seed                        201  demo posts=10 leaves=3
   GET    /v1/state                                  200  phase=live me=in board=open in=42 liveCount=42 approxReaches=63
   POST   /v1/board                                  201  shown=true pending=false
   POST   /v1/board                                  422  not_shown: This can't be shown: it names or points at a specific person.
   GET    /v1/board?limit=3                          200  open=true "Playing cards, all welcome" @ Hahn Plaza (mine); "Just sitting. Join if you want" @ Hahn Plaza benches; "Cooking dal for whoever shows up" @ Webb Tower kitchen, floor 6
   POST   /v1/me/reaches                             200  approxReaches=3
   POST   /v1/me/reaches                             200  approxReaches=3 (kept the larger total)
   POST   /v1/me/leave                               200  recorded=true me=left leftAt=11/14/26, 3:06 PM
   GET    /v1/state                                  200  phase=live me=left board=open in=41 liveCount=41 approxReaches=66
         (late.leaver presses Leave in the shield 10 minutes into the window; app closed, nothing sent)
   POST   /v1/lines                                  409  phase_closed: You can write your line only during: ended. The week is in "live".

== ended
   POST   /v1/admin/weeks/wk_f44f3w3exs7zke/timeline 200  phase=ended
   POST   /v1/admin/demo/seed                        201  demo late leaves=4 lines=34
   GET    /v1/state                                  200  phase=ended me=left board=closed in=37 approxReaches=187 secondsGivenBack=216600 hoursGivenBack=60.2 stayed={"count":37,"of":45,"share":0.8222222222222222}
   GET    /v1/board                                  200  open=false posts=0 (hidden after endsAt)
   POST   /v1/lines                                  201  {"ok":true,"shown":true,"pending":false} (no line id comes back)
   POST   /v1/lines                                  409  already_wrote: You have already written your line for this week.

== told
   POST   /v1/admin/weeks/wk_f44f3w3exs7zke/timeline 200  phase=told
   POST   /v1/admin/weeks/wk_f44f3w3exs7zke/recap    201  8 highlights, 0 dropped, 1 attempt(s), generator=dev-fake-ai: dev-fake-ai (not a model) + dev-fake-ai (not a model)
   GET    /v1/state                                  200  phase=told me=left board=closed in=37 approxReaches=187 secondsGivenBack=216600 hoursGivenBack=60.2 stayed={"count":37,"of":45,"share":0.8222222222222222}
         group 8 people called or facetimed someone they love   [8 line id(s)]
         group 4 people went outside for a walk   [4 line id(s)]
         group 4 people read something   [4 line id(s)]
         group 3 people cooked or ate with others   [3 line id(s)]
         group 3 people fell asleep   [3 line id(s)]
         quote Went to the gym and actually paid attention to the workout   [1 line id(s)]
         quote Played guitar in Alumni Park, a few people sang along   [1 line id(s)]
         quote Sat on the Doheny steps and watched the light change   [1 line id(s)]

== a leave reported late, after the hour was told back
         late.leaver's app opens now and sends what the shield recorded: startsAt + 10 minutes
   GET    /v1/state                                  200  phase=told me=in board=closed in=37 approxReaches=187 secondsGivenBack=216600 hoursGivenBack=60.2 stayed={"count":37,"of":45,"share":0.8222222222222222}
   POST   /v1/me/leave                               400  left_at_invalid: leftAt is before this week's window started. Is it from another week?
   POST   /v1/me/leave                               200  recorded=true me=left leftAt=11/13/26, 1:46 AM
   POST   /v1/me/reaches                             200  approxReaches=4
   GET    /v1/state                                  200  phase=told me=left board=closed in=36 approxReaches=191 secondsGivenBack=211800 hoursGivenBack=58.8 stayed={"count":36,"of":45,"share":0.8}
   GET    /v1/weeks/wk_f44f3w3exs7zke/recap          200  recap stats now: in=36 approxReaches=191 secondsGivenBack=211800 hoursGivenBack=58.8 stayed={"count":36,"of":45,"share":0.8} lines=35 linesNotShown=0
   GET    /v1/weeks                                  200  wk_f44f3w3exs7zke hasRecap=true isDemo=true

done, every call returned the expected status. Remove demo data with: node scripts/demo-seed.mjs remove
```

Without a key (`npm run dev`), the AI admin calls answer `503 ai_unavailable` ("The AI is not configured: set the ANTHROPIC_API_KEY secret (locally, in server/.dev.vars)."), and every response carries `X-Quiet-Hours-Insecure-Dev-Mode: signin-codes-in-responses`.
