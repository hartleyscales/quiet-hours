#!/usr/bin/env node
// DEMO DATA SEED for Quiet Hours. Creates SIMULATED participants, votes,
// board posts and lines. Every row it creates is marked is_demo = 1 in the
// database and can be removed with `node scripts/demo-seed.mjs remove`.
//
// Usage (against a running `npm run dev` / `npm run dev:fake-ai`):
//   node scripts/demo-seed.mjs week      demo week in its vote, 48 demo users, 44 votes
//   node scripts/demo-seed.mjs decided   5 demo users skip (week must be in "decided")
//   node scripts/demo-seed.mjs live      10 board posts, 3 leaves, reaches (week must be "live")
//   node scripts/demo-seed.mjs ended     4 late leaves, final reaches, 34 lines (week must be "ended")
//   node scripts/demo-seed.mjs remove    delete every demo row
//
// Move the demo week between phases with the admin timeline call, e.g.
//   curl -X POST $QH_URL/v1/admin/weeks/<weekId>/timeline \
//     -H "X-Admin-Secret: $QH_ADMIN_SECRET" -H "Content-Type: application/json" -d '{"jumpTo":"live"}'
// or run scripts/demo-week.mjs, which walks the whole week end to end.
//
// Env: QH_URL (default http://127.0.0.1:8790), QH_ADMIN_SECRET (default local-dev-admin-secret).

const BASE = process.env.QH_URL ?? "http://127.0.0.1:8790";
const SECRET = process.env.QH_ADMIN_SECRET ?? "local-dev-admin-secret";
const step = process.argv[2];
const steps = ["week", "decided", "live", "ended", "remove"];

if (!steps.includes(step)) {
  console.error(`usage: node scripts/demo-seed.mjs <${steps.join("|")}>`);
  process.exit(2);
}

const res =
  step === "remove"
    ? await fetch(`${BASE}/v1/admin/demo`, { method: "DELETE", headers: { "X-Admin-Secret": SECRET } })
    : await fetch(`${BASE}/v1/admin/demo/seed`, {
        method: "POST",
        headers: { "X-Admin-Secret": SECRET, "Content-Type": "application/json" },
        body: JSON.stringify({ step }),
      });
const body = await res.json();
console.log(`DEMO DATA ${step}: HTTP ${res.status}`);
console.log(JSON.stringify(body, null, 2));
process.exit(res.ok ? 0 : 1);
