/**
 * Someone who is out can join or come back while the window is on
 * (POST /v1/me/rejoin during `live`). The numbers count only time actually
 * spent in, and late leave reports cannot undo a rejoin.
 *
 * Window 21:00-22:30 (90 minutes) throughout.
 */
import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { Harness, MIN, T, standardWeek, wipe } from "./helpers";

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

const at = (minutes: number) => T.startsAt + minutes * MIN;

describe("rejoin during the window", () => {
  it("someone who skipped joins mid-window: in from then, hours from the join, not part of stayed either way", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { tokens } = await weekWith(h, ["a", "c"]);
    await h.req("POST", "/v1/me/skip", { token: tokens.c });

    h.now = at(30);
    let s = await h.state(tokens.c!);
    expect(s.me).toMatchObject({ status: "skipped", can: { rejoin: true, skip: false, leave: false } });
    const r = await h.req("POST", "/v1/me/rejoin", { token: tokens.c });
    expect(r.status).toBe(200);
    expect(r.json.me).toMatchObject({ status: "in", joinedAt: isoOf(at(30)), can: { rejoin: false, leave: true, reportReaches: true } });
    s = await h.state(tokens.a!);
    expect(s.numbers).toMatchObject({ in: 2, liveCount: 2 });

    h.now = T.endsAt;
    s = await h.state(tokens.a!);
    // a 90 minutes, c 60 (from 21:30). c was not in at startsAt.
    expect(s.numbers).toMatchObject({ in: 2, secondsGivenBack: 150 * 60, stayed: { count: 1, of: 1, share: 1 } });
  });

  it("someone who left comes back: the gap does not count; they are in the stayed denominator, not the numerator", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { tokens } = await weekWith(h, ["a", "b"]);
    h.now = at(20);
    await h.req("POST", "/v1/me/leave", { token: tokens.b });
    h.now = at(50);
    expect((await h.state(tokens.b!)).me).toMatchObject({ status: "left", can: { rejoin: true, leave: false } });
    const r = await h.req("POST", "/v1/me/rejoin", { token: tokens.b });
    expect(r.json.me).toMatchObject({ status: "in", leftAt: null, can: { rejoin: false, leave: true } });
    expect((await h.state(tokens.a!)).numbers).toMatchObject({ in: 2, liveCount: 2 });

    h.now = T.endsAt;
    const s = await h.state(tokens.a!);
    // a 90 minutes; b 20 + 40 = 60, not the 30 minutes away.
    expect(s.numbers).toMatchObject({ in: 2, secondsGivenBack: 150 * 60, stayed: { count: 1, of: 2, share: 0.5 } });
  });

  it("someone who came back can leave again; only their time in counts", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { tokens } = await weekWith(h, ["b"]);
    h.now = at(10);
    await h.req("POST", "/v1/me/leave", { token: tokens.b });
    h.now = at(30);
    await h.req("POST", "/v1/me/rejoin", { token: tokens.b });
    h.now = at(60);
    const r = await h.req("POST", "/v1/me/leave", { token: tokens.b });
    expect(r.json).toMatchObject({ recorded: true, me: { status: "left", leftAt: isoOf(at(60)), can: { rejoin: true } } });

    h.now = T.endsAt;
    // 10 + 30 minutes in.
    expect((await h.state(tokens.b!)).numbers).toMatchObject({ in: 0, secondsGivenBack: 40 * 60, stayed: { count: 0, of: 1 } });
  });

  it("a leave reported late with a time before the rejoin is ignored; a later one is a new leave", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id, tokens } = await weekWith(h, ["b"]);
    h.now = at(10);
    await h.req("POST", "/v1/me/leave", { token: tokens.b }); // reported without leftAt: recorded at 21:10
    h.now = at(30);
    await h.req("POST", "/v1/me/rejoin", { token: tokens.b });

    // The phone's own copy of that first leave (it recorded 21:08) arrives after the rejoin.
    h.now = at(31);
    let r = await h.req("POST", "/v1/me/leave", { token: tokens.b, body: { weekId: id, leftAt: isoOf(at(8)) } });
    expect(r.json).toMatchObject({ recorded: false, reason: "before_rejoin", me: { status: "in", leftAt: null } });

    // After the window, two late reports: one from before the rejoin (ignored), one after it (recorded).
    h.now = T.endsAt + 5 * MIN;
    r = await h.req("POST", "/v1/me/leave", { token: tokens.b, body: { weekId: id, leftAt: isoOf(at(25)) } });
    expect(r.json).toMatchObject({ recorded: false, reason: "before_rejoin", me: { status: "in" } });
    r = await h.req("POST", "/v1/me/leave", { token: tokens.b, body: { weekId: id, leftAt: isoOf(at(70)) } });
    expect(r.json).toMatchObject({ recorded: true, me: { status: "left", leftAt: isoOf(at(70)) } });

    // 10 + 40 minutes in.
    expect((await h.state(tokens.b!)).numbers).toMatchObject({ secondsGivenBack: 50 * 60, stayed: { count: 0, of: 1 } });
  });

  it("someone who joined mid-window after a skip: a leave from before the join reads as the join time", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { tokens } = await weekWith(h, ["c"]);
    await h.req("POST", "/v1/me/skip", { token: tokens.c });
    h.now = at(30);
    await h.req("POST", "/v1/me/rejoin", { token: tokens.c });
    h.now = T.endsAt + MIN;
    const r = await h.req("POST", "/v1/me/leave", { token: tokens.c, body: { leftAt: isoOf(at(29)) } });
    expect(r.json).toMatchObject({ recorded: true, me: { status: "left", leftAt: isoOf(at(30)) } });
    expect((await h.state(tokens.c!)).numbers).toMatchObject({ secondsGivenBack: 0, stayed: { count: 0, of: 0 } });
  });

  it("rejoin is refused once the window has ended", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { tokens } = await weekWith(h, ["b", "c"]);
    await h.req("POST", "/v1/me/skip", { token: tokens.c });
    h.now = at(10);
    await h.req("POST", "/v1/me/leave", { token: tokens.b });

    h.now = T.endsAt;
    for (const token of [tokens.b!, tokens.c!]) {
      expect((await h.state(token)).me.can.rejoin).toBe(false);
      const r = await h.req("POST", "/v1/me/rejoin", { token });
      expect(r.json.error).toMatchObject({ code: "phase_closed", details: { phase: "ended", allowed: ["vote", "decided", "live"] } });
    }
    expect((await h.state(tokens.b!)).me.status).toBe("left");
  });

  it("an admin timeline shift moves the time someone came back with everything else", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id, tokens } = await weekWith(h, ["b"]);
    h.now = at(10);
    await h.req("POST", "/v1/me/leave", { token: tokens.b });
    h.now = at(30);
    await h.req("POST", "/v1/me/rejoin", { token: tokens.b });
    await h.req("POST", `/v1/admin/weeks/${id}/timeline`, { admin: true, body: { shiftSeconds: 3600 } });
    const row = await h.db.prepare("SELECT came_back_at, away_ms FROM participation").first<{ came_back_at: number; away_ms: number }>();
    expect(row).toEqual({ came_back_at: at(90), away_ms: 20 * MIN });
  });
});
