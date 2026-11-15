/**
 * Reports from the phone that arrive late. Leaving from the shield happens
 * in an extension with the app closed and no network, so the phone keeps
 * the time and reports it when the app next runs (docs/LOCK-NOTES.md, limit
 * 7). That can be after endsAt, after toldAt, or after the next week's vote
 * has opened. The server must accept such a leave and use the reported time.
 */
import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { DAY, HOUR, Harness, MIN, T, standardWeek, wipe } from "./helpers";

beforeEach(() => wipe(env.DB));

const isoOf = (ms: number) => new Date(ms).toISOString();

/** A decided standard week with the given people in (their app saw it while the vote was decided). */
async function weekWith(h: Harness, names: string[]) {
  h.now = T.voteClosesAt;
  const { id } = await standardWeek(h, true);
  const tokens: Record<string, string> = {};
  for (const n of names) {
    tokens[n] = await h.signIn(`${n}@usc.edu`);
    await h.state(tokens[n]!);
  }
  return { id, tokens };
}

describe("a leave reported late", () => {
  it("in ended: leftAt is required, and the reported time is the one used", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { tokens } = await weekWith(h, ["a", "b"]);
    h.now = T.endsAt + 10 * MIN;
    expect((await h.state(tokens.a!)).phase).toBe("ended");
    let r = await h.req("POST", "/v1/me/leave", { token: tokens.b });
    expect([r.status, r.json.error.code]).toEqual([400, "left_at_required"]);
    r = await h.req("POST", "/v1/me/leave", { token: tokens.b, body: { leftAt: isoOf(T.startsAt + 15 * MIN) } });
    expect(r.status).toBe(200);
    expect(r.json).toMatchObject({ recorded: true, me: { status: "left", leftAt: isoOf(T.startsAt + 15 * MIN) } });

    const s = await h.state(tokens.a!);
    // a stayed 90 minutes, b 15: 105 minutes.
    expect(s.numbers).toMatchObject({ in: 1, secondsGivenBack: 105 * 60, hoursGivenBack: 1.8, stayed: { count: 1, of: 2 } });
  });

  it("in told, after the recap was written: accepted, and both the state numbers and the recap's stats move", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id, tokens } = await weekWith(h, ["a", "b"]);
    h.now = T.toldAt;
    expect((await h.req("POST", `/v1/admin/weeks/${id}/recap`, { admin: true })).status).toBe(201);
    let recap = await h.req("GET", `/v1/weeks/${id}/recap`, { token: tokens.a });
    expect(recap.json.stats).toMatchObject({ stayed: { count: 2, of: 2 }, hoursGivenBack: 3 });

    h.now = T.toldAt + 2 * HOUR;
    const r = await h.req("POST", "/v1/me/leave", { token: tokens.b, body: { weekId: id, leftAt: isoOf(T.startsAt + 30 * MIN) } });
    expect(r.json).toMatchObject({ weekId: id, recorded: true, me: { status: "left" } });

    const s = await h.state(tokens.a!);
    expect(s.phase).toBe("told");
    expect(s.numbers).toMatchObject({ hoursGivenBack: 2, stayed: { count: 1, of: 2 } });
    recap = await h.req("GET", `/v1/weeks/${id}/recap`, { token: tokens.a });
    expect(recap.json.stats).toMatchObject({ hoursGivenBack: 2, stayed: { count: 1, of: 2 } });
    expect(s.recap.stats).toEqual(recap.json.stats);
    // The row still records what the numbers were when the recap was written.
    const row = await h.db.prepare("SELECT stats_json FROM recaps WHERE week_id = ?").bind(id).first<{ stats_json: string }>();
    expect(JSON.parse(row!.stats_json).stayed).toMatchObject({ count: 2, of: 2 });
  });

  it("for a past week, by weekId, after the next week's vote has opened", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id, tokens } = await weekWith(h, ["a"]);
    const next = await h.week({ voteOpensAt: T.toldAt + DAY, voteClosesAt: T.toldAt + 2 * DAY, toldAt: T.toldAt + 6 * DAY });
    h.now = T.toldAt + DAY + HOUR;
    expect((await h.state(tokens.a!)).week.id).toBe(next.id);

    // Without weekId it means the current week, whose window has not started.
    let r = await h.req("POST", "/v1/me/leave", { token: tokens.a, body: { leftAt: isoOf(T.startsAt + 10 * MIN) } });
    expect([r.status, r.json.error.code]).toEqual([409, "phase_closed"]);

    r = await h.req("POST", "/v1/me/leave", { token: tokens.a, body: { weekId: id, leftAt: isoOf(T.startsAt + 10 * MIN) } });
    expect(r.json).toMatchObject({ weekId: id, recorded: true, me: { status: "left", leftAt: isoOf(T.startsAt + 10 * MIN) } });
    r = await h.req("POST", "/v1/me/reaches", { token: tokens.a, body: { weekId: id, approxReaches: 6 } });
    expect(r.json).toMatchObject({ weekId: id, me: { approxReaches: 6 } });

    // The current week is untouched.
    const s = await h.state(tokens.a!);
    expect(s.me).toMatchObject({ status: "in", leftAt: null, approxReaches: 0 });
    expect((await h.req("POST", "/v1/me/leave", { token: tokens.a, body: { weekId: "wk_nope", leftAt: isoOf(T.startsAt) } })).status).toBe(404);
  });

  it("rejects a leftAt from before the window, ignores one at or after endsAt, and reads slight clock skew as startsAt", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id, tokens } = await weekWith(h, ["a"]);
    h.now = T.endsAt + HOUR;
    let r = await h.req("POST", "/v1/me/leave", { token: tokens.a, body: { weekId: id, leftAt: isoOf(T.startsAt - 10 * MIN) } });
    expect([r.status, r.json.error.code]).toEqual([400, "left_at_invalid"]);
    expect(r.json.error.details).toEqual({ startsAt: isoOf(T.startsAt), endsAt: isoOf(T.endsAt) });

    r = await h.req("POST", "/v1/me/leave", { token: tokens.a, body: { weekId: id, leftAt: isoOf(T.endsAt) } });
    expect(r.json).toMatchObject({ recorded: false, reason: "after_window", me: { status: "in" } });

    r = await h.req("POST", "/v1/me/leave", { token: tokens.a, body: { weekId: id, leftAt: isoOf(T.startsAt - 2 * MIN) } });
    expect(r.json).toMatchObject({ recorded: true, me: { status: "left", leftAt: isoOf(T.startsAt) } });
    expect((await h.state(tokens.a!)).numbers).toMatchObject({ secondsGivenBack: 0, stayed: { count: 0, of: 1 } });
  });

  it("someone who first opened the app mid-window cannot have left before they joined", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    await standardWeek(h, true);
    const d = await h.signIn("d@usc.edu");
    h.now = T.startsAt + 30 * MIN;
    await h.state(d);
    h.now = T.endsAt + MIN;
    const r = await h.req("POST", "/v1/me/leave", { token: d, body: { leftAt: isoOf(T.startsAt + 10 * MIN) } });
    expect(r.json.me.leftAt).toBe(isoOf(T.startsAt + 30 * MIN));
    expect((await h.state(d)).numbers).toMatchObject({ secondsGivenBack: 0, stayed: { count: 0, of: 0, share: null } });
  });

  it("a person who skipped, or whose app never saw the week, has nothing to leave", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id, tokens } = await weekWith(h, ["c"]);
    await h.req("POST", "/v1/me/skip", { token: tokens.c });
    h.now = T.toldAt;
    const late = await h.signIn("late@usc.edu");
    for (const token of [tokens.c!, late]) {
      const r = await h.req("POST", "/v1/me/leave", { token, body: { weekId: id, leftAt: isoOf(T.startsAt + MIN) } });
      expect([r.status, r.json.error.code]).toEqual([409, "not_in"]);
    }
  });
});

describe("the reach count is never presented as exact", () => {
  /** Every key in a JSON value, at any depth. */
  const keys = (v: unknown): string[] =>
    v && typeof v === "object"
      ? Object.entries(v as Record<string, unknown>).flatMap(([k, x]) => [k, ...keys(x)])
      : [];

  it("every stored column and every response field that carries it says approx", async () => {
    const cols = (await env.DB.prepare("PRAGMA table_info(participation)").all<{ name: string }>()).results.map((c) => c.name);
    expect(cols.filter((c) => /reach/i.test(c))).toEqual(["approx_reaches"]);

    const h = new Harness({ now: T.voteClosesAt });
    const { id, tokens } = await weekWith(h, ["a"]);
    h.now = T.startsAt + MIN;
    const responses = [await h.req("POST", "/v1/me/reaches", { token: tokens.a, body: { approxReaches: 2 } }), await h.req("GET", "/v1/state", { token: tokens.a })];
    h.now = T.toldAt;
    await h.req("POST", `/v1/admin/weeks/${id}/recap`, { admin: true });
    responses.push(
      await h.req("GET", "/v1/state", { token: tokens.a }),
      await h.req("GET", `/v1/weeks/${id}/recap`, { token: tokens.a }),
      await h.req("GET", `/v1/admin/weeks/${id}`, { admin: true }),
    );
    const reachKeys = new Set(responses.flatMap((r) => keys(r.json)).filter((k) => /reach/i.test(k)));
    expect([...reachKeys].sort()).toEqual(["approxReaches", "reportReaches"]);
  });
});
