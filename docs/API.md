# Quiet Hours API

The server in `server/`: a Cloudflare Worker with a D1 (SQLite) database. This document covers every endpoint in the order a phone meets them through a week, then the admin calls, then errors. Behaviour and data follow [CONTRACT.md](CONTRACT.md). Decisions and limits are in [SERVER-NOTES.md](SERVER-NOTES.md).

Every response shape below is copied from a real local run (2026-11-14). Ids and times are edited so all the examples describe one week:

| | Los Angeles | UTC (what the API sends) |
|---|---|---|
| `voteOpensAt` | Mon 16 Nov, 09:00 | `2026-11-16T17:00:00.000Z` |
| `voteClosesAt` | Tue 17 Nov, 17:00 | `2026-11-18T01:00:00.000Z` |
| board opens | Wed 18 Nov, 00:00 | `2026-11-18T08:00:00.000Z` |
| `startsAt` | Wed 18 Nov, 21:00 | `2026-11-19T05:00:00.000Z` |
| `endsAt` | Wed 18 Nov, 22:30 | `2026-11-19T06:30:00.000Z` |
| `toldAt` | Wed 18 Nov, 22:45 | `2026-11-19T06:45:00.000Z` |

## Contents

1. [Basics](#basics)
2. [Run it locally](#run-it-locally)
3. [Sign in](#sign-in): `POST /v1/auth/start`, `POST /v1/auth/verify`, `POST /v1/auth/sign-out`
4. [The state call](#the-state-call): `GET /v1/state`
5. [Vote](#vote): `POST /v1/vote`
6. [Skip and rejoin](#skip-and-rejoin): `POST /v1/me/skip`, `POST /v1/me/rejoin`
7. [The board](#the-board): `GET /v1/board`, `POST /v1/board`, `DELETE /v1/board/:id`
8. [Leave early](#leave-early): `POST /v1/me/leave`
9. [Reaches](#reaches): `POST /v1/me/reaches`
10. [Your line](#your-line): `POST /v1/lines`
11. [The hour told back](#the-hour-told-back): `GET /v1/weeks`, `GET /v1/weeks/:id/recap`
12. [Health](#health): `GET /v1/health`
13. [Admin](#admin)
14. [Errors](#errors)

## Basics

- **Base URL.** Locally `http://127.0.0.1:8790`. All routes start with `/v1`.
- **JSON** in and out. Send `Content-Type: application/json` with a body. An empty body counts as `{}`.
- **Auth.** Signed-in routes need `Authorization: Bearer <token>` from [sign-in](#sign-in). Admin routes need `X-Admin-Secret: <secret>` instead.
- **Times** are ISO 8601. Responses are always UTC (`...Z`). Requests must name their offset (`Z` or `-08:00`); a time without one is rejected.
- **Ids** are random strings with a type prefix: `us_` user, `wk_` week, `op_` option, `po_` board post, `ln_` line.
- **The server owns the clock.** Every phase is derived from the week's timestamps at the moment of the request ([CONTRACT.md](CONTRACT.md), "The week, as phases"). Nothing about the phase is stored.
- **`weekId` on writes.** Most writes accept an optional `weekId`. On vote, skip, rejoin, board and lines it is a guard: if the current week has changed, the call fails with `409 week_changed` instead of acting on the wrong week. On leave and reaches it selects the week, which may be a past one (see [Leave early](#leave-early)).
- **Development mode is loud.** When a development mode is on, every response carries `X-Quiet-Hours-Insecure-Dev-Mode: <modes>`. See [Health](#health).

## Run it locally

Needs Node 22+ (wrangler 4 requires it). Nothing here talks to Cloudflare or creates anything in the cloud.

```sh
cd server
npm install
npm test                 # 118 tests in the Workers runtime, AI stubbed, no network
npm run typecheck

npm run dev              # http://127.0.0.1:8790; applies migrations to the local D1 first
# or
npm run dev:fake-ai      # same, plus a deterministic fake AI, so recap/proposals work without a key
```

Both `dev` scripts start the server in development mode with:

- `SIGNIN_CODE_DELIVERY=INSECURE_DEV_RETURN_CODE_IN_RESPONSE`: the sign-in code comes back in the response as `devCode`.
- `ADMIN_SECRET=local-dev-admin-secret`.
- `dev:fake-ai` only: `AI_MODE=DEV_FAKE_AI_NOT_REAL`. Its output says `[FAKE AI, development only]`.

For the real Claude API locally, put the key in `server/.dev.vars` (one line, `ANTHROPIC_API_KEY=...`; the file is git-ignored) and use `npm run dev`. Without a key the AI calls fail with `503 ai_unavailable`, and new board posts and lines wait as pending (see [The board](#the-board)).

Walk a whole week in a second terminal:

```sh
npm run demo:week        # seeds DEMO DATA, signs in two testers, steps through every phase, prints a transcript
node scripts/demo-seed.mjs remove   # delete every demo row
```

A first request by hand:

```sh
curl -s -X POST http://127.0.0.1:8790/v1/auth/start -H 'Content-Type: application/json' \
  -d '{"email":"tommy.trojan@usc.edu"}'
# copy devCode from the response
curl -s -X POST http://127.0.0.1:8790/v1/auth/verify -H 'Content-Type: application/json' \
  -d '{"email":"tommy.trojan@usc.edu","code":"504040"}'
# copy token
curl -s http://127.0.0.1:8790/v1/state -H "Authorization: Bearer $TOKEN"
```

## Sign in

A USC address gets a 6-digit one-time code; the code gets a session token. Codes expire after 10 minutes, lock after 5 wrong tries, and an address can ask for at most 5 codes an hour. Only hashes of codes and tokens are stored. Sessions last 180 days.

### `POST /v1/auth/start`

```json
{ "email": "Tommy.Trojan@USC.edu" }
```

The address is trimmed and lower-cased and must end in `@usc.edu` (`a@alumni.usc.edu` does not).

Response `200`, development mode:

```json
{
  "email": "tommy.trojan@usc.edu",
  "expiresAt": "2026-11-16T17:10:00.000Z",
  "delivery": "dev-response",
  "devCode": "504040",
  "devWarning": "INSECURE DEVELOPMENT MODE: the sign-in code is returned in this response instead of being emailed. This must never run in production."
}
```

In production (`delivery: "email"`) there is never a `devCode`. No email sender is written yet, so production answers `503 email_not_configured` and keeps no challenge.

Errors: `400 email_not_usc`, `403 demo_account` (a seeded demo participant), `429 too_many_codes`, `503 email_not_configured`.

### `POST /v1/auth/verify`

```json
{ "email": "tommy.trojan@usc.edu", "code": "504040" }
```

Response `200`. The user is created on first sign-in.

```json
{
  "token": "<session token>",
  "expiresAt": "2027-05-15T17:00:00.000Z",
  "user": { "id": "us_m9zhayaavvey2e", "email": "tommy.trojan@usc.edu" }
}
```

Errors: `400 code_invalid` (wrong, expired or already used; one message for all three), `429 too_many_attempts`.

### `POST /v1/auth/sign-out`

Signed in. Deletes this session. Response `200 {"ok": true}`.

## The state call

### `GET /v1/state`

Signed in. Everything a client needs to draw the current moment. Call it on launch, on foreground, and at `nextChangeAt`.

Reading state has two side effects, both from the contract:

- **In by default.** The first time a person's app reads state during `vote`, `decided` or `live`, they are put in for the week (`me.status: "in"`). After the window, nobody new is put in.
- **The decision.** If the vote has closed and no winner is stored yet, the winner is picked by count right then (ties go to the option listed first) and the window is copied onto the week.

**The current week** is the one whose vote opened most recently. It stays current through `told` until the next week's vote opens.

#### Fields

| Field | Type | Meaning |
|---|---|---|
| `serverTime` | time | The server's clock. Use it, not the phone's, to compare against the week's times. |
| `phase` | `vote` \| `decided` \| `live` \| `ended` \| `told` \| null | Null when no week's vote has opened yet. |
| `nextChangeAt` | time \| null | The next instant anything on this screen changes by itself: a phase boundary, the board opening, or the next week's vote. Refresh then. |
| `week` | object \| null | The current week (below). |
| `week.id` | string | Pass this as `weekId`, and to the lock engine as the window id. |
| `week.voteOpensAt`, `voteClosesAt` | time | Set when the week is created. |
| `week.startsAt`, `endsAt` | time \| null | The window. Null until the vote is decided; then the winning option's times. |
| `week.toldAt` | time | When the hour is told back: 15 minutes after `endsAt`, set when the vote is decided. Before that, the latest it can be (set when the week is created; every option ends at least 15 minutes before it). |
| `week.nextWeekVoteOpensAt` | time \| null | The end of `told`, when the next week exists. |
| `week.isDemo` | boolean | True for a week made by the demo seed. |
| `upcomingVoteOpensAt` | time \| null | When the next week's vote opens, if one exists. With no current week, the first one. |
| `options` | array \| null | The week's proposed windows, in the order they were listed, in every phase: during `vote` with the running tally, from `decided` on with the final count (votes cannot change once the vote closes). Same item shape in every phase. Null only when there is no current week. |
| `options[].id`, `startsAt`, `endsAt` | | The window. |
| `options[].minutes` | number | Its length. |
| `options[].reason` | string | Why this window, in plain words: one line of one or two short sentences, at most 70 characters in all. |
| `options[].votes` | number | Counted from stored votes at this moment. Includes votes from people who later skipped. |
| `totalVotes` | number \| null | Every vote cast this week: the sum of `options[].votes`. Null only when there is no current week. |
| `myVote` | string \| null | The option id this person voted for. |
| `winner` | object \| null | Once decided: the winning option, same shape as an option, with its final count. Its `id` marks the winner in `options`. |
| `board.open` | boolean | Whether the board takes posts and shows them right now. |
| `board.opensAt` | time \| null | Midnight in Los Angeles at the start of the window's calendar day, or the moment the vote closed if that is later. Null until decided. |
| `board.closesAt` | time \| null | `endsAt`. Posts are hidden from then on. |
| `me` | object \| null | This person's part in the week (below). Null with no current week. |
| `me.status` | `in` \| `skipped` \| `left` \| null | Null if their app never saw this week before the window ended. |
| `me.joinedAt` | time \| null | When they were put in: their app's first read of the week, or, for someone who skipped and then joined during `live`, the time they joined. |
| `me.leftAt` | time \| null | When they left early, as reported by the phone. |
| `me.approxReaches` | number | What this person's phone reported. An approximation; see [Reaches](#reaches). |
| `me.wroteLine` | boolean | Whether they have written this week's line. |
| `me.can` | object | What this person can do right now: `vote`, `skip`, `rejoin`, `leave`, `reportReaches`, `post`, `writeLine`. `vote` is false for someone who skipped. `skip` is true in `vote` and `decided` for someone who is in. `rejoin` is true in `vote` and `decided` for someone who skipped, and in `live` for someone who skipped or left. The server enforces the same rules on every write. Late reports of a leave or of reaches are accepted after the window even though `can` shows false then. |
| `numbers` | object \| null | The contract's numbers, counted from stored rows at this moment. Fields that do not apply in this phase are null (below). |
| `recap` | object \| null | During `told`, once written: the hour told back, same shape as [`GET /v1/weeks/:id/recap`](#get-v1weeksidrecap). |

#### `numbers`, by phase

| Field | vote, decided | live | ended, told | Meaning |
|---|---|---|---|---|
| `in` | count | count | count | People whose status is `in`. |
| `liveCount` | null | count | null | The same count, while the window is on. |
| `approxReaches` | null | sum | sum | Sum of what the phones reported. Each phone's figure is an approximation; the sum adds nothing to it. |
| `secondsGivenBack` | null | null | number | Sum over participants of the time they were actually in during the window, exact. Someone who joined mid-window counts from their join; time between leaving and coming back does not count. |
| `hoursGivenBack` | null | null | number | The same in hours, rounded to 0.1. |
| `stayed` | null | null | `{count, of, share}` | Of the people in at `startsAt` (`of`), how many never left (`count`). Someone who left and came back is in `of` but not `count`; someone who joined after `startsAt` is in neither. `share` is `count / of`, unrounded, null when `of` is 0. |
| `lines` | null | null | count | Lines written for this week so far: every stored line, whether shown, waiting for the editing check, or hidden by it (a line the check declines when it is sent is not stored). A count only; nothing about who wrote which. Not the same as the recap's `stats.lines`, which counts the lines the recap was written from. |

These numbers keep moving after the window when late reports arrive (see [Leave early](#leave-early)). They are always recomputed, never cached.

#### Example: no week yet

```json
{
  "serverTime": "2026-11-14T12:00:00.000Z",
  "phase": null,
  "nextChangeAt": "2026-11-16T17:00:00.000Z",
  "week": null,
  "upcomingVoteOpensAt": "2026-11-16T17:00:00.000Z",
  "options": null,
  "totalVotes": null,
  "myVote": null,
  "winner": null,
  "board": { "open": false, "opensAt": null, "closesAt": null },
  "me": null,
  "numbers": null,
  "recap": null
}
```

#### Example: `vote`

```json
{
  "serverTime": "2026-11-16T20:00:00.000Z",
  "phase": "vote",
  "nextChangeAt": "2026-11-18T01:00:00.000Z",
  "week": {
    "id": "wk_sjnxz3a32vqzfd",
    "voteOpensAt": "2026-11-16T17:00:00.000Z",
    "voteClosesAt": "2026-11-18T01:00:00.000Z",
    "startsAt": null,
    "endsAt": null,
    "toldAt": "2026-11-19T06:45:00.000Z",
    "nextWeekVoteOpensAt": null,
    "isDemo": false
  },
  "upcomingVoteOpensAt": null,
  "options": [
    {
      "id": "op_jwpxjy1j1qhay7",
      "startsAt": "2026-11-19T05:00:00.000Z",
      "endsAt": "2026-11-19T06:30:00.000Z",
      "minutes": 90,
      "reason": "Classes are nearly over and nothing big is on that evening.",
      "votes": 0
    },
    {
      "id": "op_rsznqv15dcd7ya",
      "startsAt": "2026-11-19T03:00:00.000Z",
      "endsAt": "2026-11-19T04:00:00.000Z",
      "minutes": 60,
      "reason": "The quietest night of the week, with no exam the next morning.",
      "votes": 0
    }
  ],
  "totalVotes": 0,
  "myVote": null,
  "winner": null,
  "board": { "open": false, "opensAt": null, "closesAt": null },
  "me": {
    "status": "in",
    "joinedAt": "2026-11-16T20:00:00.000Z",
    "leftAt": null,
    "approxReaches": 0,
    "wroteLine": false,
    "can": { "vote": true, "skip": true, "rejoin": false, "leave": false, "reportReaches": false, "post": false, "writeLine": false }
  },
  "numbers": { "in": 1, "liveCount": null, "approxReaches": null, "secondsGivenBack": null, "hoursGivenBack": null, "stayed": null, "lines": null },
  "recap": null
}
```

#### Example: `decided`, before the board opens

```json
{
  "serverTime": "2026-11-18T02:00:00.000Z",
  "phase": "decided",
  "nextChangeAt": "2026-11-18T08:00:00.000Z",
  "week": {
    "id": "wk_sjnxz3a32vqzfd",
    "voteOpensAt": "2026-11-16T17:00:00.000Z",
    "voteClosesAt": "2026-11-18T01:00:00.000Z",
    "startsAt": "2026-11-19T05:00:00.000Z",
    "endsAt": "2026-11-19T06:30:00.000Z",
    "toldAt": "2026-11-19T06:45:00.000Z",
    "nextWeekVoteOpensAt": null,
    "isDemo": false
  },
  "upcomingVoteOpensAt": null,
  "options": [
    { "id": "op_jwpxjy1j1qhay7", "startsAt": "2026-11-19T05:00:00.000Z", "endsAt": "2026-11-19T06:30:00.000Z", "minutes": 90, "reason": "Classes are nearly over and nothing big is on that evening.", "votes": 2 },
    { "id": "op_rsznqv15dcd7ya", "startsAt": "2026-11-19T03:00:00.000Z", "endsAt": "2026-11-19T04:00:00.000Z", "minutes": 60, "reason": "The quietest night of the week, with no exam the next morning.", "votes": 0 }
  ],
  "totalVotes": 2,
  "myVote": "op_jwpxjy1j1qhay7",
  "winner": {
    "id": "op_jwpxjy1j1qhay7",
    "startsAt": "2026-11-19T05:00:00.000Z",
    "endsAt": "2026-11-19T06:30:00.000Z",
    "minutes": 90,
    "reason": "Classes are nearly over and nothing big is on that evening.",
    "votes": 2
  },
  "board": { "open": false, "opensAt": "2026-11-18T08:00:00.000Z", "closesAt": "2026-11-19T06:30:00.000Z" },
  "me": {
    "status": "in",
    "joinedAt": "2026-11-16T20:00:00.000Z",
    "leftAt": null,
    "approxReaches": 0,
    "wroteLine": false,
    "can": { "vote": false, "skip": true, "rejoin": false, "leave": false, "reportReaches": false, "post": false, "writeLine": false }
  },
  "numbers": { "in": 2, "liveCount": null, "approxReaches": null, "secondsGivenBack": null, "hoursGivenBack": null, "stayed": null, "lines": null },
  "recap": null
}
```

From `2026-11-18T08:00:00.000Z` (midnight in Los Angeles on the window's day) the same response has `"board": {"open": true, ...}`, `can.post: true`, and `nextChangeAt` moves to `startsAt`.

#### Example: `live`

```json
{
  "serverTime": "2026-11-19T05:30:00.000Z",
  "phase": "live",
  "nextChangeAt": "2026-11-19T06:30:00.000Z",
  "week": { "id": "wk_sjnxz3a32vqzfd", "voteOpensAt": "2026-11-16T17:00:00.000Z", "voteClosesAt": "2026-11-18T01:00:00.000Z", "startsAt": "2026-11-19T05:00:00.000Z", "endsAt": "2026-11-19T06:30:00.000Z", "toldAt": "2026-11-19T06:45:00.000Z", "nextWeekVoteOpensAt": null, "isDemo": false },
  "upcomingVoteOpensAt": null,
  "options": [
    { "id": "op_jwpxjy1j1qhay7", "startsAt": "2026-11-19T05:00:00.000Z", "endsAt": "2026-11-19T06:30:00.000Z", "minutes": 90, "reason": "Classes are nearly over and nothing big is on that evening.", "votes": 2 },
    { "id": "op_rsznqv15dcd7ya", "startsAt": "2026-11-19T03:00:00.000Z", "endsAt": "2026-11-19T04:00:00.000Z", "minutes": 60, "reason": "The quietest night of the week, with no exam the next morning.", "votes": 0 }
  ],
  "totalVotes": 2,
  "myVote": "op_jwpxjy1j1qhay7",
  "winner": { "id": "op_jwpxjy1j1qhay7", "startsAt": "2026-11-19T05:00:00.000Z", "endsAt": "2026-11-19T06:30:00.000Z", "minutes": 90, "reason": "Classes are nearly over and nothing big is on that evening.", "votes": 2 },
  "board": { "open": true, "opensAt": "2026-11-18T08:00:00.000Z", "closesAt": "2026-11-19T06:30:00.000Z" },
  "me": {
    "status": "in",
    "joinedAt": "2026-11-16T20:00:00.000Z",
    "leftAt": null,
    "approxReaches": 3,
    "wroteLine": false,
    "can": { "vote": false, "skip": false, "rejoin": false, "leave": true, "reportReaches": true, "post": true, "writeLine": false }
  },
  "numbers": { "in": 2, "liveCount": 2, "approxReaches": 3, "secondsGivenBack": null, "hoursGivenBack": null, "stayed": null, "lines": null },
  "recap": null
}
```

For someone who skipped or left, the same response has `me.status` `"skipped"` or `"left"` and `"can": { ..., "rejoin": true, "leave": false, "post": false, ... }` (`reportReaches` stays true for `left`).

#### Example: `ended`

The other person left 30 minutes in; this one stayed. 90 + 30 minutes = 7200 seconds. The other person has written their line; this one has not yet.

```json
{
  "serverTime": "2026-11-19T06:35:00.000Z",
  "phase": "ended",
  "nextChangeAt": "2026-11-19T06:45:00.000Z",
  "week": { "id": "wk_sjnxz3a32vqzfd", "voteOpensAt": "2026-11-16T17:00:00.000Z", "voteClosesAt": "2026-11-18T01:00:00.000Z", "startsAt": "2026-11-19T05:00:00.000Z", "endsAt": "2026-11-19T06:30:00.000Z", "toldAt": "2026-11-19T06:45:00.000Z", "nextWeekVoteOpensAt": null, "isDemo": false },
  "upcomingVoteOpensAt": null,
  "options": [
    { "id": "op_jwpxjy1j1qhay7", "startsAt": "2026-11-19T05:00:00.000Z", "endsAt": "2026-11-19T06:30:00.000Z", "minutes": 90, "reason": "Classes are nearly over and nothing big is on that evening.", "votes": 2 },
    { "id": "op_rsznqv15dcd7ya", "startsAt": "2026-11-19T03:00:00.000Z", "endsAt": "2026-11-19T04:00:00.000Z", "minutes": 60, "reason": "The quietest night of the week, with no exam the next morning.", "votes": 0 }
  ],
  "totalVotes": 2,
  "myVote": "op_jwpxjy1j1qhay7",
  "winner": { "id": "op_jwpxjy1j1qhay7", "startsAt": "2026-11-19T05:00:00.000Z", "endsAt": "2026-11-19T06:30:00.000Z", "minutes": 90, "reason": "Classes are nearly over and nothing big is on that evening.", "votes": 2 },
  "board": { "open": false, "opensAt": "2026-11-18T08:00:00.000Z", "closesAt": "2026-11-19T06:30:00.000Z" },
  "me": {
    "status": "in",
    "joinedAt": "2026-11-16T20:00:00.000Z",
    "leftAt": null,
    "approxReaches": 3,
    "wroteLine": false,
    "can": { "vote": false, "skip": false, "rejoin": false, "leave": false, "reportReaches": false, "post": false, "writeLine": true }
  },
  "numbers": {
    "in": 1,
    "liveCount": null,
    "approxReaches": 3,
    "secondsGivenBack": 7200,
    "hoursGivenBack": 2,
    "stayed": { "count": 1, "of": 2, "share": 0.5 },
    "lines": 1
  },
  "recap": null
}
```

#### Example: `told`

As `ended`, with `phase: "told"`, `nextChangeAt` set to the next week's `voteOpensAt` (null if none exists yet), `me.can` all false, and the recap once an admin has written it. Both people wrote a line before `toldAt`, so `numbers.lines` is 2:

```json
{
  "serverTime": "2026-11-19T06:50:00.000Z",
  "phase": "told",
  "nextChangeAt": null,
  "...": "week, options, totalVotes, myVote, winner, board and me as in ended, except me.wroteLine true and me.can all false",
  "numbers": {
    "in": 1,
    "liveCount": null,
    "approxReaches": 3,
    "secondsGivenBack": 7200,
    "hoursGivenBack": 2,
    "stayed": { "count": 1, "of": 2, "share": 0.5 },
    "lines": 2
  },
  "recap": {
    "weekId": "wk_sjnxz3a32vqzfd",
    "generatedAt": "2026-11-19T06:45:05.000Z",
    "generator": "anthropic: claude-opus-5-5 + claude-opus-5-5",
    "highlights": [
      {
        "kind": "group",
        "text": "2 people called or facetimed someone they love",
        "lineIds": ["ln_51kpwerzxke0xw", "ln_v6np3msp9mz9sb"],
        "count": 2,
        "lines": [
          { "id": "ln_51kpwerzxke0xw", "text": "Called my dad, we talked about his garden" },
          { "id": "ln_v6np3msp9mz9sb", "text": "Called my mom and walked home the long way" }
        ]
      }
    ],
    "stats": {
      "in": 1,
      "approxReaches": 3,
      "secondsGivenBack": 7200,
      "hoursGivenBack": 2,
      "stayed": { "count": 1, "of": 2, "share": 0.5 },
      "lines": 2,
      "linesNotShown": 0
    }
  }
}
```

## Vote

### `POST /v1/vote`

Signed in, during `vote`, for someone who has not skipped (`409 not_in` otherwise; rejoin first). One vote per person per week; calling again changes it. A vote that arrives after `voteClosesAt` is refused even if it raced the close. A vote cast before skipping is kept and still counted, and stays in `myVote`.

```json
{ "optionId": "op_jwpxjy1j1qhay7", "weekId": "wk_sjnxz3a32vqzfd" }
```

Response `200`: the caller's vote and the fresh tally.

```json
{
  "myVote": "op_jwpxjy1j1qhay7",
  "options": [
    { "id": "op_jwpxjy1j1qhay7", "startsAt": "2026-11-19T05:00:00.000Z", "endsAt": "2026-11-19T06:30:00.000Z", "minutes": 90, "reason": "Classes are nearly over and nothing big is on that evening.", "votes": 1 },
    { "id": "op_rsznqv15dcd7ya", "startsAt": "2026-11-19T03:00:00.000Z", "endsAt": "2026-11-19T04:00:00.000Z", "minutes": 60, "reason": "The quietest night of the week, with no exam the next morning.", "votes": 0 }
  ]
}
```

Errors: `404 option_not_found` (not one of this week's options), `409 not_in` (skipped), `409 phase_closed`, `409 week_changed`, `409 no_week`.

## Skip and rejoin

### `POST /v1/me/skip` and `POST /v1/me/rejoin`

Signed in. Body optional: `{ "weekId": "wk_sjnxz3a32vqzfd" }`. Calling either when it has nothing to do is harmless.

- **Skip**: during `vote` and `decided`, for someone who is in. Not once the window has started (leave instead). Someone who skipped cannot vote; a vote they cast before skipping is kept and counted.
- **Rejoin** during `vote` and `decided`: someone who skipped is in again, as before.
- **Rejoin** during `live`: someone who is out gets back in, and can leave again later.
  - Skipped: they join now. `joinedAt` becomes now and they count from then: toward hours from the moment they joined, not from `startsAt`, and not toward `stayed` (they were not in at `startsAt`).
  - Left: they come back. `status` is `in` again and `leftAt` is null. The time they were away does not count toward hours, and they count in `stayed`'s `of` but not its `count`.
- Not possible once the window has ended (`409 phase_closed`).

Response `200`, after skip:

```json
{
  "me": {
    "status": "skipped",
    "joinedAt": "2026-11-16T20:00:00.000Z",
    "leftAt": null,
    "approxReaches": 0,
    "wroteLine": false,
    "can": { "vote": false, "skip": false, "rejoin": true, "leave": false, "reportReaches": false, "post": false, "writeLine": false }
  }
}
```

Rejoin returns the same shape with `"status": "in"`. The phone should cancel or reschedule its lock to match (`cancelWindow()` / `scheduleWindow` in [LOCK-NOTES.md](LOCK-NOTES.md)); after a rejoin during `live`, that means locking again for the rest of the window.

For someone who left and came back, a leave reported with a time before their latest rejoin is ignored (`recorded: false, reason: "before_rejoin"`), because that leave was already recorded before they came back. (For someone who joined after a skip, a leave from before the join reads as the join time, as for anyone who joined mid-window.) So the phone should send any leave it has not reported yet before it calls rejoin; otherwise the rejoin finds the person still in and does nothing, and the leave that follows counts.

Errors: `409 phase_closed`, `409 week_changed`.

## The board

Open from midnight in Los Angeles on the window's calendar day (but never before the vote has closed) until `endsAt`. Text only: one line of up to 140 characters and a place of up to 60. Line breaks and runs of spaces are folded into single spaces. Posts are hidden from everyone at `endsAt`.

### `GET /v1/board`

Signed in. Query: `limit` (1-200, default 50), `before` (an ISO time; returns posts created before it, for paging). Newest first. Posts carry no author; `mine` says whether the caller wrote it. Posts that were taken down are never listed.

Response `200` while open:

```json
{
  "open": true,
  "opensAt": "2026-11-18T08:00:00.000Z",
  "closesAt": "2026-11-19T06:30:00.000Z",
  "posts": [
    {
      "id": "po_4j7s45vbczak69",
      "text": "Reading on the grass, bring a book",
      "place": "McCarthy Quad",
      "createdAt": "2026-11-19T05:12:00.000Z",
      "mine": false,
      "pending": false
    }
  ]
}
```

While closed: `{"open": false, "opensAt": ..., "closesAt": ..., "posts": []}`.

### `POST /v1/board`

Signed in, while the board is open, status `in`. At most 5 posts per person per week; a post that was taken down still counts toward the 5.

```json
{ "text": "Reading on the grass, bring a book", "place": "McCarthy Quad", "weekId": "wk_sjnxz3a32vqzfd" }
```

Every post goes through the editing check (contract, AI job 3) before anyone else sees it:

| Check result | Stored | Response |
|---|---|---|
| Fine | yes, shown | `201`, `"shown": true` |
| Names or targets a person, or abusive | no; the writer can rewrite | `422 not_shown` |
| Could not run (no key, API down) | yes, `pending`: shown only to its writer | `201`, `"shown": false`, `"post.pending": true` |

Response `201`:

```json
{
  "post": {
    "id": "po_4j7s45vbczak69",
    "text": "Reading on the grass, bring a book",
    "place": "McCarthy Quad",
    "createdAt": "2026-11-19T05:12:00.000Z",
    "mine": true,
    "pending": false
  },
  "shown": true
}
```

Errors: `400 invalid_request` (empty or too long), `409 board_closed`, `409 not_in`, `409 week_changed`, `422 not_shown` (details: `{"reason": "names_or_targets_person" | "abusive" | "check_declined"}`), `429 post_limit`.

### `DELETE /v1/board/:id`

Signed in, while the board is open (until `endsAt`). Takes down one of your own posts on this week's board, shown or pending, whatever your status now. No body. From then on the post is not listed for anyone, its writer included, so it no longer counts in the board's posts. It still counts toward the 5 posts a week: taking a post down does not free a slot. Taking down a post that is already down changes nothing and answers `200` again.

Response `200`: the board's first page, exactly as `GET /v1/board` with no query, without the post:

```json
{
  "open": true,
  "opensAt": "2026-11-18T08:00:00.000Z",
  "closesAt": "2026-11-19T06:30:00.000Z",
  "posts": [
    {
      "id": "po_8m2kq7w4zr1x5c",
      "text": "Playing chess, two boards",
      "place": "Ronald Tutor Campus Center, 2nd floor",
      "createdAt": "2026-11-19T05:03:00.000Z",
      "mine": false,
      "pending": false
    }
  ]
}
```

Errors: `404 post_not_found` (no such post on this week's board, or it is someone else's: the two are not told apart, so post ids cannot be probed), `409 board_closed`, `409 no_week`.

## Leave early

### `POST /v1/me/leave`

Signed in. Leaving is always allowed. The phone records the time of a leave, and the report can arrive late: "Leave quiet hours" on the shield runs in an extension with the app closed and no network, so the report waits until the app next runs ([LOCK-NOTES.md](LOCK-NOTES.md), limit 7). That can be after `endsAt`, after `toldAt`, or after the next week's vote has opened. The server accepts all of these and uses the time the phone recorded.

```json
{ "weekId": "wk_sjnxz3a32vqzfd", "leftAt": "2026-11-19T05:20:00.000Z" }
```

| Field | |
|---|---|
| `weekId` | The week the leave belongs to. Optional, but the phone should always send it (it is the scheduled window's id); without it, the current week is meant, and a late report after the next week's vote opens would land on the wrong week. |
| `leftAt` | When the person left, by the phone's clock. Optional during `live` (defaults to now). Required after `endsAt`. |

What the server does with `leftAt`:

- Later than the server's clock: read as now.
- More than 5 minutes before `startsAt`: rejected with `400 left_at_invalid` (probably from another week). Up to 5 minutes before: read as `startsAt` (clock skew).
- Before the person was put in (someone who first opened the app, or joined after a skip, mid-window): read as their `joinedAt`.
- At or after `endsAt`: not an early leave. Nothing changes; `recorded: false, reason: "after_window"`.
- Before the person's latest rejoin (they left and came back): ignored, since that leave was recorded before they came back. Nothing changes; `recorded: false, reason: "before_rejoin"`. A time after the rejoin is a new leave.
- A leave already recorded: the earlier of the two times is kept. A later or equal time gives `recorded: false, reason: "already_left_earlier"`.

Response `200`:

```json
{
  "weekId": "wk_sjnxz3a32vqzfd",
  "recorded": true,
  "me": {
    "status": "left",
    "joinedAt": "2026-11-16T20:00:00.000Z",
    "leftAt": "2026-11-19T05:20:00.000Z",
    "approxReaches": 3,
    "wroteLine": true,
    "can": { "vote": false, "skip": false, "rejoin": false, "leave": false, "reportReaches": false, "post": false, "writeLine": false }
  }
}
```

The same leave reported again with a later time:

```json
{ "weekId": "wk_sjnxz3a32vqzfd", "recorded": false, "reason": "already_left_earlier", "me": { "status": "left", "leftAt": "2026-11-19T05:20:00.000Z", "...": "..." } }
```

A late leave changes `in`, `secondsGivenBack`, `hoursGivenBack` and `stayed` everywhere they appear, the recap's `stats` included.

Errors: `400 left_at_required`, `400 left_at_invalid` (details: the window's `startsAt` and `endsAt`), `404 week_not_found`, `409 phase_closed` (the window has not started), `409 not_in` (skipped, or the person's app never saw the week).

## Reaches

### `POST /v1/me/reaches`

Signed in. The phone's running total of reaches for the week. **It is an approximation.** iOS never reports "the shield was shown"; the phone counts the times iOS asked it to draw the shield, merged within 3 seconds, which can undercount or overcount ([LOCK-NOTES.md](LOCK-NOTES.md), "Reach counter"). The server stores what the phone reports and names it `approxReaches` everywhere.

```json
{ "weekId": "wk_sjnxz3a32vqzfd", "approxReaches": 3 }
```

The server keeps the largest total it has seen for the person and week, so retries, duplicates and out-of-order reports are safe. Like a leave, it may arrive late and should carry `weekId`. Accepted once the window has started, for people who were `in` (including those who left).

Response `200`: `{ "weekId": "...", "me": { ... "approxReaches": 3 ... } }`, same `me` shape as above.

Errors: `400 invalid_request` (not a whole number 0-100000), `404 week_not_found`, `409 phase_closed`, `409 not_in`.

## Your line

### `POST /v1/lines`

Signed in, during `ended`, for people who were in the window (status `in` or `left`). One line per person per week, up to 200 characters. Optional.

```json
{ "text": "Called my mom and walked home the long way", "weekId": "wk_sjnxz3a32vqzfd" }
```

Response `201`:

```json
{ "ok": true, "shown": true, "pending": false }
```

**The line is stored with no link to its writer.** The `lines` row holds only a random id, the week, the text and its check state: no user, no time, and the table has no insertion order (`WITHOUT ROWID`). The writer's participation row only gets `wroteLine: true`, so they cannot write twice. The response deliberately carries no line id. Limits of this guarantee are in [SERVER-NOTES.md](SERVER-NOTES.md).

The editing check works as on the board: a rejected line is not stored (`422 not_shown`, rewrite and send again); an unchecked one is stored as pending and kept out of the recap until it passes.

Errors: `400 invalid_request`, `409 already_wrote`, `409 not_in`, `409 phase_closed`, `409 week_changed`, `422 not_shown`.

## The hour told back

### `GET /v1/weeks`

Signed in. Weeks that have reached `toldAt`, newest first.

```json
{
  "weeks": [
    {
      "id": "wk_sjnxz3a32vqzfd",
      "startsAt": "2026-11-19T05:00:00.000Z",
      "endsAt": "2026-11-19T06:30:00.000Z",
      "toldAt": "2026-11-19T06:45:00.000Z",
      "hasRecap": true,
      "isDemo": false
    }
  ]
}
```

### `GET /v1/weeks/:id/recap`

Signed in, from `toldAt` on.

```json
{
  "weekId": "wk_sjnxz3a32vqzfd",
  "generatedAt": "2026-11-19T06:45:05.000Z",
  "generator": "anthropic: claude-opus-5-5 + claude-opus-5-5",
  "highlights": [
    {
      "kind": "group",
      "text": "2 people called or facetimed someone they love",
      "lineIds": ["ln_51kpwerzxke0xw", "ln_v6np3msp9mz9sb"],
      "count": 2,
      "lines": [
        { "id": "ln_51kpwerzxke0xw", "text": "Called my dad, we talked about his garden" },
        { "id": "ln_v6np3msp9mz9sb", "text": "Called my mom and walked home the long way" }
      ]
    },
    {
      "kind": "quote",
      "text": "Sat on the Doheny steps and watched the light change",
      "lineIds": ["ln_k3v9q2m7xd4h1a"],
      "count": null,
      "lines": [{ "id": "ln_k3v9q2m7xd4h1a", "text": "Sat on the Doheny steps and watched the light change" }]
    }
  ],
  "stats": {
    "in": 1,
    "approxReaches": 3,
    "secondsGivenBack": 7200,
    "hoursGivenBack": 2,
    "stayed": { "count": 1, "of": 2, "share": 0.5 },
    "lines": 2,
    "linesNotShown": 0
  }
}
```

| Field | |
|---|---|
| `highlights` | At most 5. |
| `highlights[].kind` | `quote`: one line, shown exactly as stored. `group`: two or more lines summed up in one sentence. |
| `highlights[].text` | For a quote, the stored line itself (never the model's copy). For a group, a sentence whose only number is the count. At most 60 characters either way (the model is asked for 55). |
| `highlights[].lineIds`, `lines` | The stored lines it came from, with their text. Every highlight has at least one. |
| `highlights[].count` | For a group, the number of lines attached, which always equals the number in the sentence. Null for a quote. |
| `stats` | The same numbers as `/v1/state` after the window, recomputed at read time so late leaves count. `lines` and `linesNotShown` describe the recap's input: lines that had passed the editing check when it was written, and lines that had not. |

Errors: `404 week_not_found`, `404 recap_not_ready`, `409 not_told_yet` (details: `toldAt`).

## Health

### `GET /v1/health`

No auth.

```json
{
  "ok": true,
  "serverTime": "2026-11-16T17:00:00.000Z",
  "environment": "development",
  "insecureDevModes": ["signin-codes-in-responses", "fake-ai"],
  "signinDelivery": "dev-response",
  "ai": { "mode": "dev-fake", "configured": true }
}
```

In production: `"environment": "production"`, `"insecureDevModes": []`, `"signinDelivery": "email"`, `"ai": {"mode": "anthropic", "configured": <key set>}`. A development mode set outside `ENVIRONMENT=development` makes every route, this one included, answer `500 server_misconfigured`.

## Admin

Every `/v1/admin/*` call needs `X-Admin-Secret`. Missing or wrong: `403 admin_forbidden`. If the server has no `ADMIN_SECRET` at all: `503 admin_not_configured`.

Most admin calls answer with the **admin week view**:

```json
{
  "week": {
    "id": "wk_sjnxz3a32vqzfd",
    "voteOpensAt": "2026-11-16T17:00:00.000Z",
    "voteClosesAt": "2026-11-18T01:00:00.000Z",
    "startsAt": "2026-11-19T05:00:00.000Z",
    "endsAt": "2026-11-19T06:30:00.000Z",
    "toldAt": "2026-11-19T06:45:00.000Z",
    "nextWeekVoteOpensAt": null,
    "isDemo": false
  },
  "phase": "decided",
  "winningOptionId": "op_jwpxjy1j1qhay7",
  "options": [
    { "id": "op_jwpxjy1j1qhay7", "startsAt": "2026-11-19T05:00:00.000Z", "endsAt": "2026-11-19T06:30:00.000Z", "minutes": 90, "reason": "Classes are nearly over and nothing big is on that evening.", "votes": 2, "source": "admin" },
    { "id": "op_rsznqv15dcd7ya", "startsAt": "2026-11-19T03:00:00.000Z", "endsAt": "2026-11-19T04:00:00.000Z", "minutes": 60, "reason": "The quietest night of the week, with no exam the next morning.", "votes": 0, "source": "admin" }
  ],
  "numbers": { "in": 2, "liveCount": null, "approxReaches": null, "secondsGivenBack": null, "hoursGivenBack": null, "stayed": null, "lines": null },
  "lines": 0,
  "pendingChecks": { "posts": 0, "lines": 0 },
  "hasRecap": false
}
```

`options[].source` is `admin`, `ai` or `demo`. `lines` counts every stored line of the week; `pendingChecks` counts posts and lines still waiting for the editing check.

### `GET /v1/admin/weeks`

Every week, newest first: `{"weeks": [{ ...week, "phase": "told" }]}`.

### `POST /v1/admin/weeks`

Create a week. The window is not set here; it comes from the vote.

```json
{ "voteOpensAt": "2026-11-16T09:00:00-08:00", "voteClosesAt": "2026-11-17T17:00:00-08:00", "toldAt": "2026-11-18T22:45:00-08:00" }
```

`toldAt` here is the latest the hour can be told back: every option must end at least 15 minutes before it. When the vote is decided, `toldAt` becomes 15 minutes after the winning window's end (the contract's rule), which is never later than this. Needs `voteOpensAt < voteClosesAt < toldAt`. Weeks may not overlap from `voteOpensAt` to `toldAt`. Response `201`: the admin week view, `phase: null` until the vote opens.

Errors: `400 bad_timeline`, `400 invalid_request` (a time without an offset), `409 week_overlap`.

### `GET /v1/admin/weeks/:id`

The admin week view.

### `PUT /v1/admin/weeks/:id/options`

Replace the week's options (1 to 5). Each must start at or after `voteClosesAt` and end at least 15 minutes before `toldAt`. Each `reason` is one or two short sentences, at most 70 characters in all (the same check as AI proposals; longer is `400 invalid_request`, more than two sentences `400 bad_option`). Refused once anyone has voted or the week is decided.

```json
{
  "options": [
    { "startsAt": "2026-11-18T21:00:00-08:00", "endsAt": "2026-11-18T22:30:00-08:00", "reason": "Classes are nearly over and nothing big is on that evening." },
    { "startsAt": "2026-11-18T19:00:00-08:00", "endsAt": "2026-11-18T20:00:00-08:00", "reason": "The quietest night of the week, with no exam the next morning." }
  ]
}
```

Response `200`: the admin week view. Errors: `400 bad_option`, `409 votes_exist`, `409 already_decided`.

### `POST /v1/admin/weeks/:id/proposals`

AI job 1: three candidate windows from a description of the campus's week. Nothing is scraped; the admin supplies the input. Format and a realistic example: [`server/examples/campus-week.example.json`](../server/examples/campus-week.example.json) (schema in `server/src/ai/campus-week.ts`: class load by hour for each day, games, exams, sunset times, notes; all local times in America/Los_Angeles).

```json
{ "campusWeek": { "weekOf": "2026-11-16", "timezone": "America/Los_Angeles", "population": { "students": 47000 }, "classLoad": [ "..." ], "games": [ "..." ], "exams": [ "..." ], "sunset": [ "..." ], "notes": [ "..." ] }, "apply": false }
```

The model's draft is checked in code: exactly three windows; each a real local time, after `voteClosesAt` and done at least 15 minutes before `toldAt`, 30 minutes to 4 hours long, not identical to another; each reason on one line, one or two sentences, at most 70 characters in all. The prompt also asks for plain words, facts from the input only, and no counts of students or clock times; code does not check those. A failing draft is retried up to 3 times with the reasons. With `"apply": true` the proposals replace the week's options (same rules as `PUT .../options`).

Response `200` (from the development fake AI; the real model's reasons read the campus week):

```json
{
  "proposals": [
    { "startsAt": "2026-11-18T05:00:00.000Z", "endsAt": "2026-11-18T06:00:00.000Z", "startLocal": "2026-11-17T21:00", "endLocal": "2026-11-17T22:00", "minutes": 60, "reason": "[FAKE AI, development only] Option 1, picked by a fixed rule." },
    { "...": "two more" }
  ],
  "applied": false,
  "attempts": 1,
  "rejected": [],
  "model": "claude-opus-5-5"
}
```

Errors: `400 invalid_request` (the campus week does not match the schema), `502 ai_invalid_output` (every attempt failed validation; details list why), `502 ai_refused`, `502 ai_failed`, `503 ai_busy`, `503 ai_unavailable`.

### `POST /v1/admin/weeks/:id/close-vote`

Close the vote now (if it is still open) and pick the winner by count. Ties go to the option listed first. The winning option's times become the week's `startsAt` and `endsAt`, and `toldAt` becomes 15 minutes after `endsAt`. The vote also closes by itself at `voteClosesAt`; this call is for closing early. Response `200`: the admin week view with `phase: "decided"` and `winningOptionId`.

Errors: `409 vote_not_open`, `409 no_options`.

### `POST /v1/admin/weeks/:id/timeline`

Demo time control: move a week's timestamps so a demo can step through every phase in minutes. Two forms:

```json
{ "jumpTo": "live" }
```

Moves the whole week so that now is the first instant of that phase: `vote` puts `voteOpensAt` at now (and undoes any decision so the vote can run again, with `toldAt` back at 15 minutes after the latest option); `decided` puts `voteClosesAt` at now and picks the winner; `live`, `ended`, `told` put `startsAt`, `endsAt`, `toldAt` at now, deciding first by the current count if needed.

```json
{ "shiftSeconds": -2400 }
```

Moves the whole week by that many seconds (here, 40 minutes into the past, so a `live` week is 40 minutes in).

Everyone's times move with the week (`joinedAt`, `leftAt`, the time someone came back, board posts, options), so numbers stay coherent. When a jump would push the week's already-past vote into a week that has just been told (two weeks back to back in a demo), only that vote is shortened to fit. A window is never shortened: if it would overlap another week, the call fails with `409 week_overlap`; move the other week with `shiftSeconds` or remove demo data first.

Response `200`: the admin week view. Errors: `400 invalid_request`, `409 week_overlap`, `409 no_options`.

### `POST /v1/admin/weeks/:id/recap`

AI job 2: write the hour told back from the week's stored lines that have passed the editing check. Allowed once the window has ended. Writing again replaces the recap.

The model only drafts. Before anything is stored, code checks every highlight: it must carry the ids of stored lines of this week; a quote is exactly one line and is shown as the stored text; a group has at least two lines and one number, in digits, equal to the number of ids attached, and no amount words ("several", "most", "half", "both", ...). A second model pass checks each line of a group against its sentence; lines it does not describe are removed and the number is rewritten from the ids that remain. The model is asked for at most 5 highlights of at most 55 characters each; drafts past the fifth are dropped, and so is any highlight longer than 60 characters (a quote is never cut, so a longer line cannot be quoted). Anything failing is dropped; if too much is dropped, the whole draft is retried (up to 3 times) with the reasons.

Response `201`: the recap (as `GET /v1/weeks/:id/recap`) plus `attempts` and `dropped` (each dropped draft with its reason).

Errors: `409 phase_closed`, `502 ai_refused`, `502 ai_failed`, `503 ai_busy`, `503 ai_unavailable`.

### `POST /v1/admin/weeks/:id/moderate`

AI job 3 again: re-run the editing check on the week's pending posts and lines (stored while the check could not run). Response `200`:

```json
{ "posts": { "ok": 1, "hidden": 0, "stillPending": 0 }, "lines": { "ok": 0, "hidden": 0, "stillPending": 0 } }
```

Errors: `503 ai_unavailable`.

### `POST /v1/admin/demo/seed`

**Demo data.** Simulated participants, votes, board posts and lines, so a demo has a populated campus. Every row it writes has `is_demo = 1`; the week reports `isDemo: true`; option reasons start with `DEMO:`. Demo participants cannot be signed into. Seeding goes step by step because what people do depends on the phase:

| `step` | Needs the demo week in | Writes |
|---|---|---|
| `week` | (creates it, in `vote`) | the week, 3 options, 48 demo users, 44 votes |
| `decided` | `decided` | 5 demo users skip |
| `live` | `live` | 10 board posts, 3 leaves, reach counts |
| `ended` | `ended` | 4 leaves reported late, final reach counts, 34 lines |

```json
{ "step": "week" }
```

Response `201`: `{"step": "week", "weekId": "wk_...", "demoUsers": 48, "votes": 44, "options": 3}`. Errors: `409 wrong_phase` (move the week with the timeline call first), `409 no_demo_week`, `409 week_overlap`.

`scripts/demo-seed.mjs <step>` calls this; `scripts/demo-week.mjs` walks a whole week.

### `DELETE /v1/admin/demo`

Removes every demo row, and everything that hangs off a demo week, including what real testers did inside it. Real users and real weeks are untouched. Response `200`:

```json
{ "removed": { "weeks": 1, "users": 48, "posts": 10, "lines": 34, "votes": 44, "participation": 48 } }
```

## Errors

Every error has the same shape:

```json
{
  "error": {
    "code": "phase_closed",
    "message": "You can skip only during: vote, decided. The week is in \"live\".",
    "details": { "phase": "live", "allowed": ["vote", "decided"] }
  }
}
```

`code` is stable; branch on it. `message` is for people reading logs, not for display. `details` appears only for some codes.

| Status | Code | When |
|---|---|---|
| 400 | `invalid_json` | The body is not JSON. |
| 400 | `invalid_request` | The body does not match the endpoint. `details.issues`: `[{path, message}]`. |
| 400 | `email_not_usc`, `invalid_email` | Sign-in with an address that does not end in `@usc.edu`. |
| 400 | `code_invalid` | Wrong, expired or used sign-in code. |
| 400 | `left_at_required` | A leave after the window without `leftAt`. |
| 400 | `left_at_invalid` | `leftAt` well before the window. `details`: the window. |
| 400 | `bad_timeline`, `bad_option` | Admin: impossible week or option times. |
| 401 | `unauthorized` | Missing, unknown or expired session token. |
| 403 | `admin_forbidden` | Missing or wrong `X-Admin-Secret`. |
| 403 | `demo_account` | Sign-in to a seeded demo participant. |
| 404 | `not_found` | No such route. |
| 404 | `week_not_found`, `option_not_found`, `post_not_found`, `recap_not_ready` | `post_not_found` also covers a post that is not yours. |
| 409 | `phase_closed` | Not possible in this phase. `details.phase`, `details.allowed`. |
| 409 | `no_week` | There is no current week. |
| 409 | `week_changed` | The `weekId` sent is no longer the current week. `details.currentWeekId`. |
| 409 | `not_in` | Only for people who are (or were) in the window. Also: a vote from someone who skipped. |
| 409 | `board_closed` | The board is not open. |
| 409 | `already_wrote` | One line per person per week. |
| 409 | `not_told_yet` | The recap is not readable before `toldAt`. `details.toldAt`. |
| 409 | `week_overlap`, `votes_exist`, `already_decided`, `vote_not_open`, `no_options`, `wrong_phase`, `no_demo_week` | Admin and demo conflicts. |
| 422 | `not_shown` | The editing check declined the text. `details.reason`: `names_or_targets_person`, `abusive` or `check_declined`. |
| 429 | `too_many_codes`, `too_many_attempts`, `post_limit` | Limits. |
| 500 | `server_misconfigured` | A development mode is set outside `ENVIRONMENT=development`. Every route answers this. |
| 500 | `internal` | A bug. Details are in the server log only. |
| 502 | `ai_refused` | The model, and its fallback, declined. `details.category`. |
| 502 | `ai_failed`, `ai_invalid_output` | The Claude API failed, or its output failed validation on every attempt. |
| 503 | `ai_unavailable` | No `ANTHROPIC_API_KEY`, or the key was rejected. |
| 503 | `ai_busy` | The Claude API is rate limiting. Try again shortly. |
| 503 | `email_not_configured` | Production sign-in: no email sender exists yet. |
| 503 | `admin_not_configured` | No `ADMIN_SECRET` on the server. |
