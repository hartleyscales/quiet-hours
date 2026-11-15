// The sample campus: an in-browser stand-in for the server, with the same calls as api.js.
// One campus, one week, the numbers and words from the approved mocks. Everything the viewer does really
// changes this state (votes move the tallies, opting out moves the count, posts come and go, leaving dims a
// dot), following the server's rules from docs/API.md. Nothing leaves the tab and a reload starts it over.
//
// The week runs on its own clock. Each step of the demo sets that clock to a moment in the week; from there it
// runs with real time but never crosses into the next phase by itself.

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message || code);
    this.status = status; this.code = code; this.details = details;
  }
}
const fail = (status, code, message) => { throw new ApiError(status, code, message); };

const iso = (ms) => new Date(ms).toISOString();
const T = (s) => Date.parse(s);
const MIN = 60_000, HOUR = 60 * MIN;

// The week: votes Sunday to Tuesday 8:00 PM, then Thursday 5:00 – 7:00 PM, told back at 7:15 (America/Los_Angeles).
const WEEK = {
  id: "wk_sample_week",
  voteOpensAt: T("2026-11-15T17:00:00Z"), // Sun 9:00 AM
  voteClosesAt: T("2026-11-18T04:00:00Z"), // Tue 8:00 PM
  startsAt: T("2026-11-20T01:00:00Z"), // Thu 5:00 PM
  endsAt: T("2026-11-20T03:00:00Z"), // Thu 7:00 PM
  toldAt: T("2026-11-20T03:15:00Z"), // Thu 7:15 PM
  nextWeekVoteOpensAt: T("2026-11-22T17:00:00Z"), // Sun 9:00 AM
};
const BOARD_OPENS = T("2026-11-19T08:00:00Z"); // Thu 12:00 AM, the window's own day

const OPTIONS = [ // others' votes; the viewer's own vote is added on top
  { id: "op_thursday", startsAt: WEEK.startsAt, endsAt: WEEK.endsAt, reason: "Most classes are out. Sunset is at 4:48.", others: 1203 },
  { id: "op_sunday", startsAt: T("2026-11-23T00:00:00Z"), endsAt: T("2026-11-23T01:30:00Z"), reason: "No home game, and the week hasn't begun.", others: 867 },
  { id: "op_wednesday", startsAt: T("2026-11-18T20:00:00Z"), endsAt: T("2026-11-18T21:00:00Z"), reason: "Lunch, when most people are on campus.", others: 512 },
];

const POSTS = [ // newest first, with how many minutes ago each went up; the first is the viewer's own
  ["Guitar on the lawn, come sit", "McCarthy Quad", 2, true],
  ["Spikeball, anyone welcome", "Alumni Park", 9],
  ["Jam session, bring anything", "Village fountain", 14],
  ["Cooking for whoever shows up", "Cale kitchen", 21],
  ["Pickup soccer needs two more", "Brittingham Field", 26],
  ["Sketching on the steps", "Doheny Library", 31],
  ["Walking to the Rose Garden", "Leaving from Tommy Trojan", 38],
  ["Frisbee, all levels", "Cromwell Field", 44],
  ["Chess, two boards going", "Campus Center patio", 52],
  ["Reading on the grass", "Founders Park", 62],
  ["Sunset walk", "Leaving Leavey at 5:30", 70],
  ["Hammocks up, room for more", "Trousdale by Bovard", 85],
  ["Basketball, next five", "Lyon Center courts", 125],
  ["Board games in the lounge", "Ginsburg Hall", 140],
];

const HIGHLIGHTS = [
  ["group", "41 people called a parent.", 41],
  ["quote", "Someone finished a painting they started in September.", null],
  ["quote", "Spikeball on McCarthy Quad grew to about thirty.", null],
  ["group", "63 people took a nap.", 63],
  ["group", "19 people cooked for someone else.", 19],
];

// Everyone else on campus.
const OTHERS = {
  in: 3111, // in before the window
  live: 3097, // still in during the window
  stayed: 3040, // of OTHERS.in, never left
  hoursBack: 6138,
  reaches: 1904,
  lines: 1287,
};

// Where each step of the demo puts the week's clock, and the moment it stops at.
const STEPS = {
  vote: { at: T("2026-11-16T08:00:00Z"), until: WEEK.voteClosesAt }, // Mon 12:00 AM, 1d 20h before the vote closes
  decided: { at: T("2026-11-18T05:00:00Z"), until: BOARD_OPENS }, // Tue 9:00 PM
  day: { at: T("2026-11-19T21:48:00Z"), until: WEEK.startsAt }, // Thu 1:48 PM
  live: { at: T("2026-11-20T01:40:00Z"), until: WEEK.endsAt }, // Thu 5:40 PM
  ended: { at: WEEK.endsAt + 20_000, until: WEEK.toldAt }, // Thu 7:00 PM
  told: { at: T("2026-11-20T03:30:00Z"), until: WEEK.nextWeekVoteOpensAt }, // Thu 7:30 PM
};
const SAMPLE_EMAIL = "tommy.trojan@usc.edu";

let S;
function fresh() {
  let n = 0;
  S = {
    signedIn: false, email: "", pending: null,
    clock: { at: STEPS.vote.at, until: STEPS.vote.until, since: Date.now() },
    status: "in", joinedAt: WEEK.voteOpensAt + 3 * HOUR, leftAt: null, wroteLine: false,
    myVote: null, // Voting opens untouched, as the mock's first Voting screen; a tap votes (and the vote is kept)
    // The sample posts are as old as the mocks say whenever the board is open; the viewer's own new posts keep their time.
    posts: POSTS.map(([text, place, age, mine]) => ({ id: `po_sample_${++n}`, text, place, mine: Boolean(mine), age })),
    made: 1, // posts the viewer has put up this week; taking one down does not free a slot, as on the server
    prefs: new Map(),
  };
}
fresh();

const now = () => Math.min(S.clock.at + (Date.now() - S.clock.since), S.clock.until - 1000);
function phaseAt(t) {
  if (t < WEEK.voteOpensAt) return null;
  if (t < WEEK.voteClosesAt) return "vote";
  if (t < WEEK.startsAt) return "decided";
  if (t < WEEK.endsAt) return "live";
  if (t < WEEK.toldAt) return "ended";
  return "told";
}
const boardOpen = (t) => t >= BOARD_OPENS && t < WEEK.endsAt;

function can(phase, t) {
  const s = S.status, before = phase === "vote" || phase === "decided";
  return {
    vote: phase === "vote" && s !== "skipped",
    skip: before && s === "in",
    rejoin: (before && s === "skipped") || (phase === "live" && (s === "skipped" || s === "left")),
    leave: phase === "live" && s === "in",
    reportReaches: phase === "live" && (s === "in" || s === "left"),
    post: boardOpen(t) && s === "in",
    writeLine: phase === "ended" && (s === "in" || s === "left") && !S.wroteLine,
  };
}
const meView = (phase, t) => ({
  status: S.status, joinedAt: iso(S.joinedAt), leftAt: S.leftAt === null ? null : iso(S.leftAt),
  approxReaches: 0, wroteLine: S.wroteLine, can: can(phase, t),
});
const optionView = (o) => ({
  id: o.id, startsAt: iso(o.startsAt), endsAt: iso(o.endsAt), minutes: Math.round((o.endsAt - o.startsAt) / MIN),
  reason: o.reason, votes: o.others + (S.myVote === o.id ? 1 : 0),
});

function numbers(phase) {
  const me = S.status;
  if (phase === "ended" || phase === "told") {
    const stayedHours = me === "in" ? (WEEK.endsAt - Math.max(WEEK.startsAt, S.joinedAt)) / HOUR : me === "left" ? (S.leftAt - Math.max(WEEK.startsAt, S.joinedAt)) / HOUR : 0;
    const inAtStart = OTHERS.in + (me !== "skipped" && S.joinedAt <= WEEK.startsAt ? 1 : 0);
    const stayed = OTHERS.stayed + (me === "in" && S.joinedAt <= WEEK.startsAt ? 1 : 0);
    const hours = Math.round((OTHERS.hoursBack + Math.max(0, stayedHours)) * 10) / 10;
    return {
      in: OTHERS.stayed + (me === "in" ? 1 : 0), liveCount: null, approxReaches: OTHERS.reaches,
      secondsGivenBack: Math.round(hours * 3600), hoursGivenBack: hours,
      stayed: { count: stayed, of: inAtStart, share: stayed / inAtStart },
      lines: OTHERS.lines + (S.wroteLine ? 1 : 0), // not in docs/API.md yet: the anonymous lines so far
    };
  }
  const live = phase === "live";
  const n = (live ? OTHERS.live : OTHERS.in) + (me === "in" ? 1 : 0);
  return { in: n, liveCount: live ? n : null, approxReaches: live ? OTHERS.reaches : null, secondsGivenBack: null, hoursGivenBack: null, stayed: null };
}

const signedInOnly = () => { if (!S.signedIn) fail(401, "unauthorized", "Not signed in."); };
const current = () => { signedInOnly(); const t = now(); return { t, phase: phaseAt(t) }; };
const only = (phase, allowed, what) => { if (!allowed.includes(phase)) fail(409, "phase_closed", `You can ${what} only during: ${allowed.join(", ")}.`); };
const sameWeek = (weekId) => { if (weekId && weekId !== WEEK.id) fail(409, "week_changed", "The current week has changed."); };
const oneLine = (s, max) => {
  const v = String(s ?? "").trim().replace(/\s+/g, " ");
  if (!v || v.length > max) fail(400, "invalid_request", `Must be 1 to ${max} characters.`);
  return v;
};
// The same editing check the development server applies: no handles or phone numbers, nothing abusive.
const unshowable = (s) => /@\w|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/.test(s) || /\b(idiot|stupid|loser|moron|hate you|kill|ugly|shut up)\b/i.test(s);
const reply = (v) => Promise.resolve(structuredClone(v));

// ------------------------------------------------------------------ the same calls as api.js

export const signedIn = () => S.signedIn;
export const email = () => S.email;
export function forget() { S.signedIn = false; }
const lost = new Set();
export const onSignedOut = (fn) => lost.add(fn);
export const prefs = { get: (k) => S.prefs.get(k) ?? null, set: (k, v) => { S.prefs.set(k, String(v)); } };

export async function startSignIn(address) {
  const e = String(address ?? "").trim().toLowerCase();
  if (!/^[^@\s]+@usc\.edu$/.test(e)) fail(400, "email_not_usc", "Use a USC address.");
  S.pending = { email: e, code: String(Math.floor(100000 + Math.random() * 900000)) };
  return reply({ email: e, expiresAt: iso(Date.now() + 10 * MIN), delivery: "dev-response", devCode: S.pending.code });
}
export async function verify(address, code) {
  if (!String(code ?? "").trim()) fail(400, "code_invalid", "Enter the code.");
  S.signedIn = true;
  S.email = S.pending?.email ?? String(address).trim().toLowerCase();
  setStep("vote"); // a new sign-in starts the week at its vote
  return reply({ token: "sample", expiresAt: iso(Date.now() + 180 * 24 * HOUR), user: { id: "us_sample_viewer", email: S.email } });
}
export async function signOut() { S.signedIn = false; return reply({ ok: true }); }

export async function state() {
  const { t, phase } = current();
  const decided = phase !== "vote";
  const winner = OPTIONS[0];
  return reply({
    serverTime: iso(t),
    phase,
    nextChangeAt: null, // the sample week only moves when a step is chosen
    week: {
      id: WEEK.id, voteOpensAt: iso(WEEK.voteOpensAt), voteClosesAt: iso(WEEK.voteClosesAt),
      startsAt: decided ? iso(WEEK.startsAt) : null, endsAt: decided ? iso(WEEK.endsAt) : null,
      toldAt: iso(WEEK.toldAt), nextWeekVoteOpensAt: iso(WEEK.nextWeekVoteOpensAt), isDemo: true,
    },
    upcomingVoteOpensAt: iso(WEEK.nextWeekVoteOpensAt),
    // The live API gives the options only during the vote; the decided Home shows the whole tally when it has it.
    options: phase === "vote" || phase === "decided" ? OPTIONS.map(optionView) : null,
    myVote: S.myVote,
    winner: decided ? optionView(winner) : null,
    board: { open: boardOpen(t), opensAt: decided ? iso(BOARD_OPENS) : null, closesAt: decided ? iso(WEEK.endsAt) : null },
    me: meView(phase, t),
    numbers: numbers(phase),
    recap: phase === "told" ? recap(phase) : null,
  });
}

function recap(phase) {
  return {
    weekId: WEEK.id, generatedAt: iso(WEEK.toldAt), generator: "sample data",
    highlights: HIGHLIGHTS.map(([kind, text, count], i) => ({ kind, text, lineIds: [`ln_sample_${i + 1}`], count, lines: [] })),
    stats: (({ in: n, approxReaches, secondsGivenBack, hoursGivenBack, stayed, lines }) => ({ in: n, approxReaches, secondsGivenBack, hoursGivenBack, stayed, lines, linesNotShown: 0 }))(numbers(phase)),
  };
}

export async function vote(optionId, weekId) {
  const { phase } = current();
  only(phase, ["vote"], "vote");
  sameWeek(weekId);
  if (S.status === "skipped") fail(409, "not_in", "Rejoin to vote.");
  if (!OPTIONS.some((o) => o.id === optionId)) fail(404, "option_not_found", "That option is not one of this week's windows.");
  S.myVote = optionId;
  return reply({ myVote: S.myVote, options: OPTIONS.map(optionView) });
}

export async function skip(weekId) {
  const { t, phase } = current();
  only(phase, ["vote", "decided"], "skip");
  sameWeek(weekId);
  if (S.status === "in") S.status = "skipped";
  return reply({ me: meView(phase, t) });
}

export async function rejoin(weekId) {
  const { t, phase } = current();
  only(phase, ["vote", "decided", "live"], "rejoin");
  sameWeek(weekId);
  if (S.status === "skipped" || (phase === "live" && S.status === "left")) {
    if (phase === "live") S.joinedAt = Math.max(S.joinedAt, t);
    S.status = "in"; S.leftAt = null;
  }
  return reply({ me: meView(phase, t) });
}

export async function leave(weekId) {
  const { t, phase } = current();
  only(phase, ["live"], "leave");
  if (S.status !== "in") fail(409, "not_in", "You are not in right now.");
  S.status = "left"; S.leftAt = t;
  return reply({ weekId: weekId ?? WEEK.id, recorded: true, me: meView(phase, t) });
}

export async function board() {
  const { t } = current();
  const open = boardOpen(t);
  // The viewer's own post is part of being in; out, the board reads as it does for anyone who didn't post.
  const at = (p) => p.createdAt ?? S.clock.at - p.age * MIN;
  const posts = open ? S.posts.filter((p) => !p.mine || S.status === "in").sort((a, b) => at(b) - at(a)) : [];
  return reply({
    open, opensAt: iso(BOARD_OPENS), closesAt: iso(WEEK.endsAt),
    posts: posts.map((p) => ({ id: p.id, text: p.text, place: p.place, createdAt: iso(at(p)), mine: p.mine, pending: false })),
  });
}

let postN = 100;
export async function post(text, place, weekId) {
  const { t } = current();
  sameWeek(weekId);
  const tx = oneLine(text, 140), pl = oneLine(place, 60);
  if (!boardOpen(t)) fail(409, "board_closed", "The board is not open right now.");
  if (S.status !== "in") fail(409, "not_in", "Only people who are in can post on the board.");
  if (S.made >= 5) fail(429, "post_limit", "At most 5 posts a week.");
  if (unshowable(`${tx} ${pl}`)) fail(422, "not_shown", "The editing check declined this post.");
  const p = { id: `po_sample_${++postN}`, text: tx, place: pl, mine: true, createdAt: t };
  S.posts.unshift(p);
  S.made++;
  return reply({ post: { id: p.id, text: p.text, place: p.place, createdAt: iso(t), mine: true, pending: false }, shown: true });
}

export async function takeDown(postId) {
  const { t } = current();
  if (!boardOpen(t)) fail(409, "board_closed", "The board is not open right now.");
  const k = S.posts.findIndex((p) => p.id === postId && p.mine);
  if (k >= 0) S.posts.splice(k, 1);
  else if (S.posts.some((p) => p.id === postId) || !String(postId).startsWith("po_sample_")) fail(404, "post_not_found", "No such post on this week's board.");
  // (one of yours already taken down: nothing changes, and it answers as before)
  return board(); // as the server answers: the board without the post
}

export async function writeLine(text, weekId) {
  const { phase } = current();
  only(phase, ["ended"], "write your line");
  sameWeek(weekId);
  const v = oneLine(text, 200);
  if (S.status !== "in" && S.status !== "left") fail(409, "not_in", "Only people who were in can write a line.");
  if (S.wroteLine) fail(409, "already_wrote", "You have already written your line for this week.");
  if (unshowable(v)) fail(422, "not_shown", "The editing check declined this line.");
  S.wroteLine = true;
  return reply({ ok: true, shown: true, pending: false });
}

// ------------------------------------------------------------------ the demo's own controls

function setStep(step) {
  const c = STEPS[step];
  S.clock = { at: c.at, until: c.until, since: Date.now() };
  if (step === "vote" || step === "decided" || step === "day") {
    if (S.status === "left") S.status = "skipped"; // nobody has left before the window
    S.leftAt = null;
    S.joinedAt = WEEK.voteOpensAt + 3 * HOUR;
  }
  if (step === "ended") { // the question again, as at the moment the window ends
    S.wroteLine = false;
    for (const k of [...S.prefs.keys()]) if (k.startsWith("qh.skipLine.")) S.prefs.delete(k);
  }
}

export const demo = {
  /** Back to the start: signed out, the week as the mocks show it, nothing remembered. */
  reset() { fresh(); },
  /** Puts the week at a step: "vote", "decided", "day", "live", "ended" or "told". Signs in a sample viewer if needed. */
  step(step) {
    if (!S.signedIn) { S.signedIn = true; S.email = SAMPLE_EMAIL; }
    setStep(step);
  },
  /** The viewer opted out this week, or is in. (Leaving during the window is the screen's own button.) */
  setOut(out) {
    const phase = phaseAt(now());
    if (out && S.status === "in") {
      S.status = "skipped"; S.leftAt = null;
    } else if (!out && S.status !== "in") {
      if (phase === "live") S.joinedAt = Math.max(S.joinedAt, now());
      S.status = "in"; S.leftAt = null;
    }
  },
  get out() { return S.status !== "in"; },
};
