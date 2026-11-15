import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { DAY, HOUR, Harness, MIN, T, standardWeek, wipe } from "./helpers";

beforeEach(() => wipe(env.DB));

const isoOf = (ms: number) => new Date(ms).toISOString();

describe("admin: weeks and options", () => {
  it("creates a week, sets options, and refuses overlapping weeks or bad timelines", async () => {
    const h = new Harness({ now: T.voteOpensAt - DAY });
    const body = { voteOpensAt: isoOf(T.voteOpensAt), voteClosesAt: isoOf(T.voteClosesAt), toldAt: isoOf(T.toldAt) };
    const r = await h.req("POST", "/v1/admin/weeks", { admin: true, body });
    expect(r.status).toBe(201);
    expect(r.json.phase).toBeNull();
    const id = r.json.week.id;

    const overlap = await h.req("POST", "/v1/admin/weeks", { admin: true, body: { ...body, voteOpensAt: isoOf(T.voteOpensAt + HOUR) } });
    expect([overlap.status, overlap.json.error.code]).toEqual([409, "week_overlap"]);
    const backwards = await h.req("POST", "/v1/admin/weeks", { admin: true, body: { ...body, toldAt: isoOf(T.voteOpensAt) } });
    expect(backwards.status).toBe(400);
    const noOffset = await h.req("POST", "/v1/admin/weeks", { admin: true, body: { ...body, toldAt: "2026-11-19T09:00:00" } });
    expect(noOffset.status).toBe(400);

    const opts = await h.req("PUT", `/v1/admin/weeks/${id}/options`, {
      admin: true,
      body: { options: [{ startsAt: isoOf(T.startsAt), endsAt: isoOf(T.endsAt), reason: "Late and quiet." }] },
    });
    expect(opts.json.options).toEqual([expect.objectContaining({ minutes: 90, reason: "Late and quiet.", source: "admin" })]);
    const early = await h.req("PUT", `/v1/admin/weeks/${id}/options`, {
      admin: true,
      body: { options: [{ startsAt: isoOf(T.voteClosesAt - HOUR), endsAt: isoOf(T.voteClosesAt), reason: "x" }] },
    });
    expect(early.status).toBe(400);
    // The hour is told back 15 minutes after the window ends, so an option must end at least that long before toldAt.
    const tooLate = await h.req("PUT", `/v1/admin/weeks/${id}/options`, {
      admin: true,
      body: { options: [{ startsAt: isoOf(T.startsAt), endsAt: isoOf(T.toldAt - 10 * MIN), reason: "x" }] },
    });
    expect([tooLate.status, tooLate.json.error.code]).toEqual([400, "bad_option"]);

    // The same reason check as AI proposals: at most 70 characters, at most two sentences.
    const withReason = (reason: string) =>
      h.req("PUT", `/v1/admin/weeks/${id}/options`, {
        admin: true,
        body: { options: [{ startsAt: isoOf(T.startsAt), endsAt: isoOf(T.endsAt), reason }] },
      });
    let r2 = await withReason("x".repeat(71));
    expect([r2.status, r2.json.error.code]).toEqual([400, "invalid_request"]);
    r2 = await withReason("Quiet. Nothing on. No exams.");
    expect([r2.status, r2.json.error.code]).toEqual([400, "bad_option"]);
    expect(r2.json.error.message).toMatch(/3 sentences/);
    r2 = await withReason("The quietest night of the week. No exams the next day.");
    expect(r2.status).toBe(200);
  });

  it("will not replace options once anyone has voted", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    const { id, optionIds } = await standardWeek(h);
    const a = await h.signIn("a@usc.edu");
    await h.req("POST", "/v1/vote", { token: a, body: { optionId: optionIds[0] } });
    const r = await h.req("PUT", `/v1/admin/weeks/${id}/options`, {
      admin: true,
      body: { options: [{ startsAt: isoOf(T.startsAt), endsAt: isoOf(T.endsAt), reason: "x" }] },
    });
    expect([r.status, r.json.error.code]).toEqual([409, "votes_exist"]);
  });
});

describe("admin: timeline moves a week through every phase", () => {
  it("jumpTo puts now at the start of each phase, keeping durations and people's times coherent", async () => {
    const h = new Harness({ now: T.voteOpensAt + HOUR });
    const { id } = await standardWeek(h);
    const a = await h.signIn("a@usc.edu");
    await h.state(a); // joins during the vote

    h.now = Date.parse("2026-12-01T12:00:00Z"); // demo day, outside the week
    const jump = async (phase: string) => {
      const r = await h.req("POST", `/v1/admin/weeks/${id}/timeline`, { admin: true, body: { jumpTo: phase } });
      expect(r.status, JSON.stringify(r.json)).toBe(200);
      return r.json;
    };
    for (const phase of ["vote", "decided", "live", "ended", "told"]) {
      const w = await jump(phase);
      expect(w.phase).toBe(phase);
      expect((await h.state(a)).phase).toBe(phase);
      h.now += MIN;
    }
    // Durations are unchanged: the window is still 90 minutes, told 15 minutes after it ends.
    const w = (await h.req("GET", `/v1/admin/weeks/${id}`, { admin: true })).json.week;
    expect(Date.parse(w.endsAt) - Date.parse(w.startsAt)).toBe(90 * MIN);
    expect(Date.parse(w.toldAt) - Date.parse(w.endsAt)).toBe(15 * MIN);
    // The person who joined during the vote stayed the whole (moved) window.
    expect((await h.state(a)).numbers.hoursGivenBack).toBe(1.5);
  });

  it("steps a week through every phase right after another week has been told, shortening only its past vote", async () => {
    const h = new Harness({ now: Date.parse("2026-12-01T12:00:00Z") });
    const first = await standardWeek(h, true);
    await h.req("POST", `/v1/admin/weeks/${first.id}/timeline`, { admin: true, body: { jumpTo: "told" } });
    const firstToldAt = h.now;

    // A day later. Moved rigidly, the second week's vote would start two days back, inside the first week.
    h.now += DAY;
    const body = { voteOpensAt: isoOf(h.now + DAY), voteClosesAt: isoOf(h.now + 2 * DAY), toldAt: isoOf(h.now + 3 * DAY + 90 * MIN + 12 * HOUR) };
    const second = (await h.req("POST", "/v1/admin/weeks", { admin: true, body })).json.week.id;
    await h.req("PUT", `/v1/admin/weeks/${second}/options`, {
      admin: true,
      body: { options: [{ startsAt: isoOf(h.now + 3 * DAY), endsAt: isoOf(h.now + 3 * DAY + 90 * MIN), reason: "Late and quiet." }] },
    });
    const a = await h.signIn("a@usc.edu");
    for (const phase of ["vote", "decided", "live", "ended", "told"]) {
      const r = await h.req("POST", `/v1/admin/weeks/${second}/timeline`, { admin: true, body: { jumpTo: phase } });
      expect(r.status, `${phase}: ${JSON.stringify(r.json)}`).toBe(200);
      expect(r.json.phase).toBe(phase);
      const s = await h.state(a);
      expect([s.week.id, s.phase]).toEqual([second, phase]);
      h.now += MIN;
    }
    const w = (await h.req("GET", `/v1/admin/weeks/${second}`, { admin: true })).json.week;
    expect(Date.parse(w.voteOpensAt)).toBeGreaterThanOrEqual(firstToldAt); // squeezed, not overlapping
    expect(Date.parse(w.endsAt) - Date.parse(w.startsAt)).toBe(90 * MIN); // the window keeps its length
    expect((await h.state(a)).numbers.hoursGivenBack).toBe(1.5);
    // The first week was not touched.
    const f = (await h.req("GET", `/v1/admin/weeks/${first.id}`, { admin: true })).json;
    expect([f.phase, Date.parse(f.week.toldAt)]).toEqual(["told", firstToldAt]);

    // A window is never squeezed: it cannot be put before an earlier week's toldAt.
    h.now = firstToldAt + DAY + 30 * MIN;
    const third = h.now + 10 * DAY;
    const t = (await h.req("POST", "/v1/admin/weeks", { admin: true, body: { voteOpensAt: isoOf(third), voteClosesAt: isoOf(third + DAY), toldAt: isoOf(third + 3 * DAY) } })).json.week.id;
    await h.req("PUT", `/v1/admin/weeks/${t}/options`, { admin: true, body: { options: [{ startsAt: isoOf(third + 2 * DAY), endsAt: isoOf(third + 2 * DAY + 3 * HOUR), reason: "Long." }] } });
    const r = await h.req("POST", `/v1/admin/weeks/${t}/timeline`, { admin: true, body: { jumpTo: "ended" } });
    expect([r.status, r.json.error.code]).toEqual([409, "week_overlap"]);
    expect([first.id, second]).toContain(r.json.error.details.weekId);
  });

  it("jumpTo vote undoes a decision so the vote can run again; shiftSeconds moves everything", async () => {
    const h = new Harness({ now: T.startsAt });
    const { id } = await h.week({
      voteOpensAt: T.voteOpensAt,
      voteClosesAt: T.voteClosesAt,
      toldAt: T.toldAt,
      options: [{ startsAt: T.startsAt, endsAt: T.endsAt }, { startsAt: T.option2Start, endsAt: T.option2End }],
      winner: 1, // decided on the earlier window: toldAt is 15 minutes after it
    });
    let r = await h.req("POST", `/v1/admin/weeks/${id}/timeline`, { admin: true, body: { jumpTo: "vote" } });
    expect([r.json.phase, r.json.winningOptionId, r.json.week.startsAt]).toEqual(["vote", null, null]);
    // toldAt goes back to 15 minutes after the latest option, so either can win again.
    expect(Date.parse(r.json.week.toldAt) - Date.parse(r.json.options[0].endsAt)).toBe(15 * MIN);
    r = await h.req("POST", `/v1/admin/weeks/${id}/timeline`, { admin: true, body: { shiftSeconds: -3600 } });
    expect(r.json.week.voteOpensAt).toBe(isoOf(T.startsAt - HOUR));
    r = await h.req("POST", `/v1/admin/weeks/${id}/timeline`, { admin: true, body: { jumpTo: "soon" } });
    expect(r.status).toBe(400);
  });
});

describe("demo seed", () => {
  it("seeds every phase, marks every row as demo, and removes all of it without touching real rows", async () => {
    const h = new Harness({ now: Date.parse("2026-12-01T20:00:00Z") });
    const real = await h.signIn("real.person@usc.edu");
    const seed = async (step: string) => {
      const r = await h.req("POST", "/v1/admin/demo/seed", { admin: true, body: { step } });
      expect(r.status, JSON.stringify(r.json)).toBe(201);
      return r.json;
    };
    const jump = (id: string, body: object) => h.req("POST", `/v1/admin/weeks/${id}/timeline`, { admin: true, body });

    const week = await seed("week");
    expect(week).toMatchObject({ demoUsers: 48, votes: 44, options: 3 });
    let s = await h.state(real);
    expect(s.phase).toBe("vote");
    expect(s.week.isDemo).toBe(true);
    expect(s.options.map((o: any) => o.votes)).toEqual([13, 21, 10]);
    const latestEnd = Math.max(...s.options.map((o: any) => Date.parse(o.endsAt)));
    expect(Date.parse(s.week.toldAt) - latestEnd).toBe(15 * MIN);

    expect((await h.req("POST", "/v1/admin/demo/seed", { admin: true, body: { step: "live" } })).json.error.code).toBe("wrong_phase");

    await jump(week.weekId, { jumpTo: "decided" });
    await seed("decided");
    s = await h.state(real);
    expect(s.winner.votes).toBe(21);
    expect(Date.parse(s.week.toldAt) - Date.parse(s.week.endsAt)).toBe(15 * MIN);
    expect(s.numbers.in).toBe(48 - 5 + 1);

    await jump(week.weekId, { jumpTo: "live" });
    await jump(week.weekId, { shiftSeconds: -40 * 60 }); // 40 minutes into the window
    await seed("live");
    s = await h.state(real);
    expect(s.numbers.liveCount).toBe(44 - 3);
    expect((await h.req("GET", "/v1/board", { token: real })).json.posts).toHaveLength(10);

    await jump(week.weekId, { jumpTo: "ended" });
    await seed("ended");
    s = await h.state(real);
    expect(s.numbers.stayed).toMatchObject({ count: 44 - 7, of: 44 });
    expect((await h.db.prepare("SELECT COUNT(*) AS n FROM lines").first<{ n: number }>())!.n).toBe(34);

    // Every seeded row is marked.
    for (const table of ["weeks", "options", "users", "votes", "participation", "board_posts", "lines"]) {
      const marked = await h.db.prepare(`SELECT COUNT(*) AS n FROM ${table} WHERE is_demo = 1`).first<{ n: number }>();
      expect(marked!.n, table).toBeGreaterThan(0);
    }

    const removed = await h.req("DELETE", "/v1/admin/demo", { admin: true });
    expect(removed.json.removed).toMatchObject({ weeks: 1, users: 48, posts: 10, lines: 34 });
    for (const table of ["weeks", "options", "votes", "participation", "board_posts", "lines", "recaps"]) {
      expect((await h.db.prepare(`SELECT COUNT(*) AS n FROM ${table}`).first<{ n: number }>())!.n, table).toBe(0);
    }
    const users = (await h.db.prepare("SELECT email FROM users").all<{ email: string }>()).results;
    expect(users).toEqual([{ email: "real.person@usc.edu" }]);
  });

  it("demo participants cannot be signed into", async () => {
    const h = new Harness({ now: Date.parse("2026-12-01T20:00:00Z") });
    await h.req("POST", "/v1/admin/demo/seed", { admin: true, body: { step: "week" } });
    const r = await h.req("POST", "/v1/auth/start", { body: { email: "demo.participant.01+quiet-hours-demo@usc.edu" } });
    expect([r.status, r.json.error.code]).toEqual([403, "demo_account"]);
  });
});
