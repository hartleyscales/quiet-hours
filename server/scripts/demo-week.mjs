#!/usr/bin/env node
// End-to-end walk through one whole week against a running local server,
// using DEMO DATA (see scripts/demo-seed.mjs) plus two real signed-in
// testers who act only through the public API. Prints a transcript. Every
// call states the HTTP status it expects; anything else is flagged
// UNEXPECTED and the script exits 1.
//
//   npm run dev:fake-ai      # in one terminal (or `npm run dev` for the real AI)
//   npm run demo:week        # in another
//
// Env: QH_URL (default http://127.0.0.1:8790), QH_ADMIN_SECRET (default
// local-dev-admin-secret). It starts by removing all demo data, and leaves
// the new demo week in "told".
//
// Testers: tester@usc.edu does everything in the open. late.leaver@usc.edu
// plays a phone whose "Leave quiet hours" happened in the shield with the
// app closed: the leave is only reported after the hour has been told back.

import { readFileSync } from "node:fs";

const BASE = process.env.QH_URL ?? "http://127.0.0.1:8790";
const SECRET = process.env.QH_ADMIN_SECRET ?? "local-dev-admin-secret";
const campusWeek = JSON.parse(readFileSync(new URL("../examples/campus-week.example.json", import.meta.url), "utf8"));

let unexpected = 0;

async function call(method, path, { body, admin = false, token, expect = 200, show } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (admin) headers["X-Admin-Secret"] = SECRET;
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const json = await res.json().catch(() => null);
  const ok = res.status === expect;
  if (!ok) unexpected++;
  const summary = json?.error ? `${json.error.code}: ${json.error.message}` : show ? show(json) : "";
  console.log(`${ok ? "  " : "!!"} ${method.padEnd(6)} ${path.padEnd(42)} ${res.status}${ok ? "" : ` UNEXPECTED (wanted ${expect})`}  ${summary}`);
  return { status: res.status, json };
}

const fmt = (iso) =>
  iso ? new Date(iso).toLocaleString("en-US", { timeZone: "America/Los_Angeles", dateStyle: "short", timeStyle: "short" }) : "-";
const nums = (n) =>
  n
    ? Object.entries(n)
        .filter(([, v]) => v !== null)
        .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`)
        .join(" ")
    : "";
const stateLine = (s) => `phase=${s.phase} me=${s.me?.status ?? "-"} board=${s.board.open ? "open" : "closed"} ${nums(s.numbers)}`;
const section = (title) => console.log(`\n== ${title}`);

async function signIn(email) {
  const start = await call("POST", "/v1/auth/start", { body: { email }, show: (j) => `delivery=${j.delivery} devCode=${j.devCode ?? "(none)"}` });
  const verify = await call("POST", "/v1/auth/verify", { body: { email, code: start.json.devCode }, show: (j) => `${j.user.email} -> session token` });
  return verify.json.token;
}

section("health");
const health = await call("GET", "/v1/health", {
  show: (j) => `environment=${j.environment} insecureDevModes=${j.insecureDevModes.join(",") || "none"} ai=${j.ai.mode}/${j.ai.configured ? "configured" : "NOT configured"}`,
});
if (health.status !== 200) process.exit(1);

section("reset demo data, seed a demo week (DEMO DATA), sign in two testers");
await call("DELETE", "/v1/admin/demo", { admin: true, show: (j) => `removed ${JSON.stringify(j.removed)}` });
const seeded = await call("POST", "/v1/admin/demo/seed", { admin: true, body: { step: "week" }, expect: 201, show: (j) => `week=${j.weekId} demoUsers=${j.demoUsers} votes=${j.votes}` });
const weekId = seeded.json.weekId;
await call("POST", "/v1/auth/start", { body: { email: "someone@gmail.com" }, expect: 400 });
const tester = await signIn("tester@usc.edu");
const lateLeaver = await signIn("late.leaver@usc.edu");

section("vote");
let s = (await call("GET", "/v1/state", { token: tester, show: stateLine })).json;
for (const o of s.options) console.log(`         option ${o.id}  ${fmt(o.startsAt)} for ${o.minutes} min  votes=${o.votes}  "${o.reason}"`);
await call("POST", "/v1/vote", { token: tester, body: { optionId: s.options[0].id, weekId }, show: (j) => `myVote=${j.myVote} tallies=${j.options.map((o) => o.votes)}` });
await call("POST", "/v1/vote", { token: tester, body: { optionId: s.options[1].id, weekId }, show: (j) => `changed: myVote=${j.myVote} tallies=${j.options.map((o) => o.votes)}` });
await call("GET", "/v1/state", { token: lateLeaver, show: stateLine });
await call("POST", "/v1/me/skip", { token: tester, body: { weekId }, show: (j) => `me=${j.me.status} can.vote=${j.me.can.vote}` });
await call("POST", "/v1/vote", { token: tester, body: { optionId: s.options[0].id, weekId }, expect: 409 });
await call("POST", "/v1/me/rejoin", { token: tester, body: { weekId }, show: (j) => `me=${j.me.status} can.vote=${j.me.can.vote}` });
// Proposals are a draft for the admin: without "apply": true nothing is stored, so this works mid-vote.
const proposals = await call("POST", `/v1/admin/weeks/${weekId}/proposals`, {
  admin: true,
  body: { campusWeek },
  show: (j) => `${j.proposals.length} proposals from ${j.model} in ${j.attempts} attempt(s), applied=${j.applied}`,
});
for (const p of proposals.json?.proposals ?? []) console.log(`         proposal ${p.startLocal} for ${p.minutes} min  "${p.reason}"`);

section("decided");
await call("POST", `/v1/admin/weeks/${weekId}/close-vote`, { admin: true, show: (j) => `phase=${j.phase} winner=${j.winningOptionId}` });
s = (await call("GET", "/v1/state", { token: tester, show: stateLine })).json;
console.log(`         winner ${fmt(s.winner.startsAt)} to ${fmt(s.winner.endsAt)} (${s.winner.votes} votes); board opens ${fmt(s.board.opensAt)}`);
await call("POST", "/v1/vote", { token: tester, body: { optionId: s.options?.[0]?.id ?? s.winner.id }, expect: 409 });
await call("POST", "/v1/me/skip", { token: tester, body: { weekId }, show: (j) => `me=${j.me.status}` });
await call("POST", "/v1/me/rejoin", { token: tester, body: { weekId }, show: (j) => `me=${j.me.status}` });
await call("POST", "/v1/admin/demo/seed", { admin: true, body: { step: "decided" }, expect: 201, show: (j) => `demo skips=${j.skipped}` });
await call("GET", "/v1/state", { token: tester, show: stateLine });
await call("POST", "/v1/me/leave", { token: tester, expect: 409 });

section("live (moved 40 minutes into the window)");
await call("POST", `/v1/admin/weeks/${weekId}/timeline`, { admin: true, body: { jumpTo: "live" }, show: (j) => `phase=${j.phase} startsAt=${fmt(j.week.startsAt)}` });
await call("POST", `/v1/admin/weeks/${weekId}/timeline`, { admin: true, body: { shiftSeconds: -40 * 60 }, show: (j) => `phase=${j.phase} startsAt=${fmt(j.week.startsAt)}` });
await call("POST", "/v1/admin/demo/seed", { admin: true, body: { step: "live" }, expect: 201, show: (j) => `demo posts=${j.posts} leaves=${j.left}` });
s = (await call("GET", "/v1/state", { token: tester, show: stateLine })).json;
await call("POST", "/v1/board", { token: tester, body: { text: "Playing cards, all welcome", place: "Hahn Plaza" }, expect: 201, show: (j) => `shown=${j.shown} pending=${j.post.pending}` });
await call("POST", "/v1/board", { token: tester, body: { text: "Find @tommy and tell him he's an idiot", place: "Doheny" }, expect: 422 });
await call("GET", "/v1/board?limit=3", {
  token: tester,
  show: (j) => `open=${j.open} ${j.posts.map((p) => `"${p.text}" @ ${p.place}${p.mine ? " (mine)" : ""}`).join("; ")}`,
});
await call("POST", "/v1/me/reaches", { token: tester, body: { weekId, approxReaches: 3 }, show: (j) => `approxReaches=${j.me.approxReaches}` });
await call("POST", "/v1/me/reaches", { token: tester, body: { weekId, approxReaches: 2 }, show: (j) => `approxReaches=${j.me.approxReaches} (kept the larger total)` });
await call("POST", "/v1/me/leave", { token: tester, body: { weekId }, show: (j) => `recorded=${j.recorded} me=${j.me.status} leftAt=${fmt(j.me.leftAt)}` });
await call("GET", "/v1/state", { token: tester, show: stateLine });
console.log("         (late.leaver presses Leave in the shield 10 minutes into the window; app closed, nothing sent)");
await call("POST", "/v1/lines", { token: tester, body: { text: "Too early" }, expect: 409 });

section("ended");
await call("POST", `/v1/admin/weeks/${weekId}/timeline`, { admin: true, body: { jumpTo: "ended" }, show: (j) => `phase=${j.phase}` });
await call("POST", "/v1/admin/demo/seed", { admin: true, body: { step: "ended" }, expect: 201, show: (j) => `demo late leaves=${j.lateLeaves} lines=${j.lines}` });
await call("GET", "/v1/state", { token: tester, show: stateLine });
await call("GET", "/v1/board", { token: tester, show: (j) => `open=${j.open} posts=${j.posts.length} (hidden after endsAt)` });
await call("POST", "/v1/lines", { token: tester, body: { text: "Called my mom and walked home the long way", weekId }, expect: 201, show: (j) => `${JSON.stringify(j)} (no line id comes back)` });
await call("POST", "/v1/lines", { token: tester, body: { text: "Second line", weekId }, expect: 409 });

section("told");
await call("POST", `/v1/admin/weeks/${weekId}/timeline`, { admin: true, body: { jumpTo: "told" }, show: (j) => `phase=${j.phase}` });
await call("POST", `/v1/admin/weeks/${weekId}/recap`, {
  admin: true,
  expect: 201,
  show: (j) => `${j.highlights.length} highlights, ${j.dropped.length} dropped, ${j.attempts} attempt(s), generator=${j.generator}`,
});
s = (await call("GET", "/v1/state", { token: tester, show: stateLine })).json;
for (const h of s.recap?.highlights ?? []) console.log(`         ${h.kind.padEnd(5)} ${h.text}   [${h.lineIds.length} line id(s)]`);

section("a leave reported late, after the hour was told back");
console.log("         late.leaver's app opens now and sends what the shield recorded: startsAt + 10 minutes");
// The admin timeline moved the whole window since the leave, so the recorded time is
// recomputed against the moved window (a real phone's time would not move).
s = (await call("GET", "/v1/state", { token: lateLeaver, show: stateLine })).json;
const recordedLeftAt = new Date(Date.parse(s.week.startsAt) + 10 * 60_000).toISOString();
await call("POST", "/v1/me/leave", { token: lateLeaver, body: { weekId, leftAt: "2020-01-01T00:00:00Z" }, expect: 400 });
await call("POST", "/v1/me/leave", {
  token: lateLeaver,
  body: { weekId, leftAt: recordedLeftAt },
  show: (j) => `recorded=${j.recorded} me=${j.me.status} leftAt=${fmt(j.me.leftAt)}`,
});
await call("POST", "/v1/me/reaches", { token: lateLeaver, body: { weekId, approxReaches: 4 }, show: (j) => `approxReaches=${j.me.approxReaches}` });
await call("GET", "/v1/state", { token: tester, show: stateLine });
await call("GET", `/v1/weeks/${weekId}/recap`, { token: tester, show: (j) => `recap stats now: ${nums(j.stats)}` });
await call("GET", "/v1/weeks", { token: tester, show: (j) => j.weeks.map((w) => `${w.id} hasRecap=${w.hasRecap} isDemo=${w.isDemo}`).join("; ") });

console.log(`\n${unexpected === 0 ? "done, every call returned the expected status" : `done, ${unexpected} UNEXPECTED status(es)`}. Remove demo data with: node scripts/demo-seed.mjs remove`);
process.exit(unexpected === 0 ? 0 : 1);
