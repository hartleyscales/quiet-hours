import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { DAY, HOUR, Harness, MIN, StubAi, T, standardWeek, wipe } from "./helpers";

const isoOf = (ms: number) => new Date(ms).toISOString();

beforeEach(() => wipe(env.DB));

describe("which week is current, and its phase in /v1/state", () => {
  it("has no week before any vote opens, and says when the next one does", async () => {
    const h = new Harness({ now: T.voteOpensAt - 1 });
    await standardWeek(h);
    const token = await h.signIn("a@usc.edu");
    const s = await h.state(token);
    expect(s.phase).toBeNull();
    expect(s.week).toBeNull();
    expect([s.options, s.totalVotes]).toEqual([null, null]);
    expect(s.upcomingVoteOpensAt).toBe(new Date(T.voteOpensAt).toISOString());
  });

  it("reports each phase at its boundaries, with the matching fields", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    const { optionIds } = await standardWeek(h);
    const token = await h.signIn("a@usc.edu");

    let s = await h.state(token);
    expect(s.phase).toBe("vote");
    expect(s.options).toHaveLength(2);
    expect(s.options[0]).toMatchObject({ id: optionIds[0], minutes: 90, votes: 0, reason: "Option 1." });
    expect(s.totalVotes).toBe(0);
    expect(s.winner).toBeNull();
    expect(s.nextChangeAt).toBe(new Date(T.voteClosesAt).toISOString());

    h.now = T.voteClosesAt; // decided lazily on this read
    s = await h.state(token);
    expect(s.phase).toBe("decided");
    expect(s.options.map((o: any) => [o.id, o.votes])).toEqual([[optionIds[0], 0], [optionIds[1], 0]]); // the final count
    expect(s.winner.id).toBe(optionIds[0]); // tie at 0-0 goes to the first option
    expect(s.week.startsAt).toBe(new Date(T.startsAt).toISOString());
    expect(s.week.toldAt).toBe(isoOf(T.endsAt + 15 * MIN)); // the decision sets toldAt 15 minutes after the window
    expect(s.board).toEqual({ open: false, opensAt: new Date(T.laMidnightOfStart).toISOString(), closesAt: new Date(T.endsAt).toISOString() });

    h.now = T.laMidnightOfStart;
    expect((await h.state(token)).board.open).toBe(true);

    h.now = T.startsAt;
    s = await h.state(token);
    expect(s.phase).toBe("live");
    expect(s.numbers.liveCount).toBe(1);

    h.now = T.endsAt;
    s = await h.state(token);
    expect(s.phase).toBe("ended");
    expect(s.board.open).toBe(false);
    expect(s.numbers.hoursGivenBack).toBe(1.5);

    h.now = T.toldAt;
    s = await h.state(token);
    expect(s.phase).toBe("told");
    expect(s.recap).toBeNull(); // not written yet
  });

  it("stops being current exactly when the next week's vote opens", async () => {
    const h = new Harness({ now: T.toldAt });
    const first = await standardWeek(h, true);
    const next = await h.week({ voteOpensAt: T.toldAt + DAY, voteClosesAt: T.toldAt + 2 * DAY, toldAt: T.toldAt + 6 * DAY });
    const token = await h.signIn("a@usc.edu");
    h.now = T.toldAt + DAY - 1;
    let s = await h.state(token);
    expect([s.phase, s.week.id]).toEqual(["told", first.id]);
    expect(s.week.nextWeekVoteOpensAt).toBe(new Date(T.toldAt + DAY).toISOString());
    h.now = T.toldAt + DAY;
    s = await h.state(token);
    expect([s.phase, s.week.id]).toEqual(["vote", next.id]);
  });
});

describe("voting", () => {
  it("one vote per person per week, changeable until the vote closes", async () => {
    const h = new Harness({ now: T.voteOpensAt + HOUR });
    const { optionIds } = await standardWeek(h);
    const a = await h.signIn("a@usc.edu");
    const b = await h.signIn("b@usc.edu");

    let r = await h.req("POST", "/v1/vote", { token: a, body: { optionId: optionIds[0] } });
    expect(r.status).toBe(200);
    expect(r.json.myVote).toBe(optionIds[0]);
    r = await h.req("POST", "/v1/vote", { token: a, body: { optionId: optionIds[1] } });
    expect(r.json.options.map((o: any) => o.votes)).toEqual([0, 1]);
    await h.req("POST", "/v1/vote", { token: b, body: { optionId: optionIds[1] } });
    const rows = await h.db.prepare("SELECT COUNT(*) AS n FROM votes").first<{ n: number }>();
    expect(rows!.n).toBe(2);

    h.now = T.voteClosesAt - 1;
    expect((await h.req("POST", "/v1/vote", { token: a, body: { optionId: optionIds[0] } })).status).toBe(200);
    h.now = T.voteClosesAt;
    r = await h.req("POST", "/v1/vote", { token: a, body: { optionId: optionIds[1] } });
    expect(r.status).toBe(409);
    expect(r.json.error.code).toBe("phase_closed");
  });

  it("after the vote closes, state still carries every option with its final count, the total and the winner", async () => {
    const h = new Harness({ now: T.voteOpensAt + HOUR });
    const { optionIds } = await standardWeek(h);
    const [a, b, c] = await Promise.all(["a", "b", "c"].map((n) => h.signIn(`${n}@usc.edu`)));
    await h.req("POST", "/v1/vote", { token: a, body: { optionId: optionIds[1] } });
    await h.req("POST", "/v1/vote", { token: b, body: { optionId: optionIds[1] } });
    await h.req("POST", "/v1/vote", { token: c, body: { optionId: optionIds[0] } });
    await h.req("POST", "/v1/me/skip", { token: b }); // a vote cast before skipping still counts
    const during = await h.state(a!);
    expect(during.options.map((o: any) => Object.keys(o).sort())).toEqual(Array(2).fill(["endsAt", "id", "minutes", "reason", "startsAt", "votes"]));

    for (const now of [T.voteClosesAt, T.startsAt, T.endsAt, T.toldAt]) {
      h.now = now;
      const s = await h.state(a!);
      expect(s.options, s.phase).toEqual(during.options.map((o: any) => ({ ...o, votes: o.id === optionIds[1] ? 2 : 1 })));
      expect(s.totalVotes).toBe(3);
      expect(s.winner).toEqual(s.options[1]);
      expect(s.myVote).toBe(optionIds[1]);
    }
    // A vote after the close is refused and changes nothing.
    h.now = T.voteClosesAt;
    expect((await h.req("POST", "/v1/vote", { token: c, body: { optionId: optionIds[1] } })).status).toBe(409);
    expect((await h.state(c!)).options.map((o: any) => o.votes)).toEqual([1, 2]);
  });

  it("rejects an option from another week, and a stale weekId", async () => {
    const h = new Harness({ now: T.voteOpensAt + HOUR });
    const { id } = await standardWeek(h);
    const other = await h.week({
      voteOpensAt: T.toldAt + DAY,
      voteClosesAt: T.toldAt + 2 * DAY,
      toldAt: T.toldAt + 6 * DAY,
      options: [{ startsAt: T.toldAt + 3 * DAY, endsAt: T.toldAt + 3 * DAY + HOUR }],
    });
    const a = await h.signIn("a@usc.edu");
    const r = await h.req("POST", "/v1/vote", { token: a, body: { optionId: other.optionIds[0] } });
    expect(r.status).toBe(404);
    const stale = await h.req("POST", "/v1/vote", { token: a, body: { optionId: "x", weekId: other.id } });
    expect(stale.status).toBe(409);
    expect(stale.json.error).toMatchObject({ code: "week_changed", details: { currentWeekId: id } });
  });

  it("the winner is picked by count; ties go to the option listed first", async () => {
    const h = new Harness({ now: T.voteOpensAt + HOUR });
    const { optionIds } = await standardWeek(h);
    const users = await Promise.all(["a", "b", "c"].map((n) => h.signIn(`${n}@usc.edu`)));
    await h.req("POST", "/v1/vote", { token: users[0], body: { optionId: optionIds[1] } });
    await h.req("POST", "/v1/vote", { token: users[1], body: { optionId: optionIds[1] } });
    await h.req("POST", "/v1/vote", { token: users[2], body: { optionId: optionIds[0] } });
    const closed = await h.req("POST", `/v1/admin/weeks/${(await h.state(users[0]!)).week.id}/close-vote`, { admin: true });
    expect(closed.status).toBe(200);
    expect(closed.json.winningOptionId).toBe(optionIds[1]);
    expect(closed.json.phase).toBe("decided");
    expect(closed.json.week.startsAt).toBe(new Date(T.option2Start).toISOString());
    expect(closed.json.week.toldAt).toBe(isoOf(T.option2End + 15 * MIN));
    // The vote is closed now.
    const late = await h.req("POST", "/v1/vote", { token: users[2], body: { optionId: optionIds[1] } });
    expect(late.status).toBe(409);
  });
});

describe("participation: in by default, skip, rejoin, leave", () => {
  it("is in by default the first time the app sees the week", async () => {
    const h = new Harness({ now: T.voteOpensAt + HOUR });
    await standardWeek(h);
    const a = await h.signIn("a@usc.edu");
    const s = await h.state(a);
    expect(s.me.status).toBe("in");
    expect(s.numbers.in).toBe(1);
  });

  it("skip and rejoin during vote and decided; skip is refused once the window has started", async () => {
    const h = new Harness({ now: T.voteOpensAt + HOUR });
    await standardWeek(h);
    const a = await h.signIn("a@usc.edu");
    let r = await h.req("POST", "/v1/me/skip", { token: a });
    expect(r.json.me).toMatchObject({ status: "skipped", can: { vote: false, rejoin: true, skip: false } });
    r = await h.req("POST", "/v1/me/rejoin", { token: a });
    expect(r.json.me).toMatchObject({ status: "in", can: { vote: true, rejoin: false, skip: true } });

    h.now = T.voteClosesAt;
    r = await h.req("POST", "/v1/me/skip", { token: a });
    expect(r.json.me).toMatchObject({ status: "skipped", can: { rejoin: true, skip: false } });
    expect((await h.state(a)).numbers.in).toBe(0);
    r = await h.req("POST", "/v1/me/rejoin", { token: a });
    expect(r.json.me.status).toBe("in");
    expect(r.json.me.joinedAt).toBe(isoOf(T.voteOpensAt + HOUR)); // a rejoin before the window keeps joinedAt

    h.now = T.startsAt;
    r = await h.req("POST", "/v1/me/skip", { token: a });
    expect(r.json.error).toMatchObject({ code: "phase_closed", details: { phase: "live", allowed: ["vote", "decided"] } });
  });

  it("someone who skipped during the vote cannot vote; a vote cast before skipping is kept and counted", async () => {
    const h = new Harness({ now: T.voteOpensAt + HOUR });
    const { optionIds } = await standardWeek(h);
    const a = await h.signIn("a@usc.edu");
    await h.req("POST", "/v1/vote", { token: a, body: { optionId: optionIds[1] } });
    await h.req("POST", "/v1/me/skip", { token: a });

    let r = await h.req("POST", "/v1/vote", { token: a, body: { optionId: optionIds[0] } });
    expect([r.status, r.json.error.code]).toEqual([409, "not_in"]);
    const s = await h.state(a);
    expect(s.myVote).toBe(optionIds[1]);
    expect(s.options.map((o: any) => o.votes)).toEqual([0, 1]);
    expect(s.me.can.vote).toBe(false);

    await h.req("POST", "/v1/me/rejoin", { token: a });
    r = await h.req("POST", "/v1/vote", { token: a, body: { optionId: optionIds[0] } });
    expect(r.json.options.map((o: any) => o.votes)).toEqual([1, 0]);
  });

  it("leave only once the window has started; in live it defaults to now; the earliest reported time wins", async () => {
    const h = new Harness({ now: T.voteOpensAt + HOUR });
    await standardWeek(h);
    const a = await h.signIn("a@usc.edu");
    const b = await h.signIn("b@usc.edu");
    await h.state(a);
    await h.state(b);
    h.now = T.voteClosesAt;
    let r = await h.req("POST", "/v1/me/leave", { token: a });
    expect([r.status, r.json.error.code]).toEqual([409, "phase_closed"]);

    h.now = T.startsAt + 20 * MIN;
    r = await h.req("POST", "/v1/me/leave", { token: a });
    expect(r.json).toMatchObject({ recorded: true, me: { status: "left", leftAt: isoOf(T.startsAt + 20 * MIN) } });
    // A later report of the same leave changes nothing.
    r = await h.req("POST", "/v1/me/leave", { token: a, body: { leftAt: isoOf(T.startsAt + 30 * MIN) } });
    expect(r.json).toMatchObject({ recorded: false, reason: "already_left_earlier", me: { leftAt: isoOf(T.startsAt + 20 * MIN) } });
    // The phone's own recorded time arrives and is earlier: it wins.
    r = await h.req("POST", "/v1/me/leave", { token: a, body: { leftAt: isoOf(T.startsAt + 5 * MIN) } });
    expect(r.json).toMatchObject({ recorded: true, me: { leftAt: isoOf(T.startsAt + 5 * MIN) } });
    expect((await h.state(a)).me.can.leave).toBe(false);

    // A leftAt ahead of the server's clock is read as now.
    r = await h.req("POST", "/v1/me/leave", { token: b, body: { leftAt: isoOf(T.startsAt + HOUR) } });
    expect(r.json.me.leftAt).toBe(isoOf(T.startsAt + 20 * MIN));
  });

  it("a skipped person cannot leave or report reaches", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    await h.req("POST", "/v1/me/skip", { token: a });
    h.now = T.startsAt + MIN;
    expect((await h.req("POST", "/v1/me/leave", { token: a })).json.error.code).toBe("not_in");
    expect((await h.req("POST", "/v1/me/reaches", { token: a, body: { approxReaches: 3 } })).json.error.code).toBe("not_in");
  });

  it("does not put anyone in after the window has ended", async () => {
    const h = new Harness({ now: T.endsAt });
    await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    const s = await h.state(a);
    expect(s.me.status).toBeNull();
    expect(s.numbers.in).toBe(0);
  });

  it("reaches: the phone's approximate running total, the largest one reported is kept", async () => {
    const h = new Harness({ now: T.startsAt });
    await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    await h.req("POST", "/v1/me/reaches", { token: a, body: { approxReaches: 4 } });
    const r = await h.req("POST", "/v1/me/reaches", { token: a, body: { approxReaches: 2 } });
    expect(r.json.me.approxReaches).toBe(4);
    expect((await h.req("POST", "/v1/me/reaches", { token: a, body: { total: 4 } })).json.error.code).toBe("invalid_request");
    h.now = T.voteClosesAt;
    expect((await h.req("POST", "/v1/me/reaches", { token: a, body: { approxReaches: 9 } })).status).toBe(409);
  });
});

describe("numbers, computed from stored rows", () => {
  /**
   * Window 21:00-22:30 (90 min). Five people:
   *   A  in before the start, never leaves         stays 90 min
   *   B  in before the start, leaves at +30        stays 30 min
   *   C  skips                                      not counted
   *   D  first opens the app at +60 (mid-window)    stays 30 min, not "in at start"
   *   E  in before the start, leaves at +0          stays 0 min
   */
  it("in, live count, approximate reaches, hours given back and stayed", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    await standardWeek(h, true);
    const [a, b, c, d, e] = await Promise.all(["a", "b", "c", "d", "e"].map((n) => h.signIn(`${n}@usc.edu`)));
    for (const t of [a, b, c, e]) await h.state(t!);
    await h.req("POST", "/v1/me/skip", { token: c });

    let s = await h.state(a!);
    expect(s.numbers).toEqual({ in: 3, liveCount: null, approxReaches: null, secondsGivenBack: null, hoursGivenBack: null, stayed: null, lines: null });

    h.now = T.startsAt;
    await h.req("POST", "/v1/me/leave", { token: e });
    h.now = T.startsAt + 30 * MIN;
    await h.req("POST", "/v1/me/leave", { token: b });
    await h.req("POST", "/v1/me/reaches", { token: a, body: { approxReaches: 3 } });
    await h.req("POST", "/v1/me/reaches", { token: b, body: { approxReaches: 5 } });
    h.now = T.startsAt + 60 * MIN;
    await h.state(d!); // D joins mid-window
    s = await h.state(a!);
    expect(s.numbers).toMatchObject({ in: 2, liveCount: 2, approxReaches: 8, hoursGivenBack: null, stayed: null, lines: null });

    h.now = T.endsAt;
    s = await h.state(a!);
    // 90 + 30 + 30 + 0 = 150 minutes = 2.5 hours
    expect(s.numbers).toEqual({
      in: 2,
      liveCount: null,
      approxReaches: 8,
      secondsGivenBack: 150 * 60,
      hoursGivenBack: 2.5,
      stayed: { count: 1, of: 3, share: 1 / 3 },
      lines: 0,
    });
  });

  it("lines: every stored line of the week, in ended and told only, with nothing about who wrote it", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id } = await standardWeek(h, true);
    const [a, b, c] = await Promise.all(["a", "b", "c"].map((n) => h.signIn(`${n}@usc.edu`)));
    for (const t of [a, b, c]) await h.state(t!);
    for (const now of [T.voteClosesAt, T.startsAt]) {
      h.now = now;
      expect((await h.state(a!)).numbers.lines).toBeNull();
    }

    h.now = T.endsAt;
    expect((await h.state(a!)).numbers.lines).toBe(0);
    await h.req("POST", "/v1/lines", { token: a, body: { text: "Called my mom" } });
    expect((await h.req("POST", "/v1/lines", { token: b, body: { text: "Alice is the worst" } })).status).toBe(422); // not stored
    h.ai = null; // the check cannot run: stored as pending, still a line written
    await h.req("POST", "/v1/lines", { token: c, body: { text: "Looked at the sky" } });
    const s = await h.state(a!);
    expect(s.numbers.lines).toBe(2);
    const lineIds = (await h.db.prepare("SELECT id FROM lines").all<{ id: string }>()).results.map((l) => l.id);
    for (const lineId of lineIds) expect(JSON.stringify(s)).not.toContain(lineId);

    h.now = T.toldAt;
    expect((await h.state(b!)).numbers.lines).toBe(2);
    expect((await h.req("GET", `/v1/admin/weeks/${id}`, { admin: true })).json).toMatchObject({ lines: 2, numbers: { lines: 2 } });
  });
});

describe("the board", () => {
  it("is open from local midnight of the start day until endsAt, and only for people who are in", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    const b = await h.signIn("b@usc.edu");
    const post = { text: "Reading on the lawn", place: "McCarthy Quad" };

    h.now = T.laMidnightOfStart - 1;
    let r = await h.req("POST", "/v1/board", { token: a, body: post });
    expect([r.status, r.json.error.code]).toEqual([409, "board_closed"]);
    expect((await h.req("GET", "/v1/board", { token: a })).json).toMatchObject({ open: false, posts: [] });

    h.now = T.laMidnightOfStart;
    r = await h.req("POST", "/v1/board", { token: a, body: post });
    expect(r.status).toBe(201);
    expect(r.json).toMatchObject({ shown: true, post: { text: "Reading on the lawn", place: "McCarthy Quad", pending: false } });

    h.now = T.endsAt - 1;
    let list = await h.req("GET", "/v1/board", { token: b });
    expect(list.json.open).toBe(true);
    expect(list.json.posts).toHaveLength(1);
    expect(list.json.posts[0]).toMatchObject({ text: "Reading on the lawn", mine: false });
    expect(JSON.stringify(list.json)).not.toContain("us_"); // no user ids

    h.now = T.endsAt;
    list = await h.req("GET", "/v1/board", { token: b });
    expect(list.json).toMatchObject({ open: false, posts: [] });
    expect((await h.req("POST", "/v1/board", { token: a, body: post })).status).toBe(409);
  });

  it("text only, one line, length limits, five posts per person per week", async () => {
    const h = new Harness({ now: T.startsAt });
    await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    expect((await h.req("POST", "/v1/board", { token: a, body: { text: "", place: "x" } })).status).toBe(400);
    expect((await h.req("POST", "/v1/board", { token: a, body: { text: "x".repeat(141), place: "x" } })).status).toBe(400);
    const multi = await h.req("POST", "/v1/board", { token: a, body: { text: "one\ntwo", place: " Doheny " } });
    expect(multi.json.post).toMatchObject({ text: "one two", place: "Doheny" });
    for (let i = 0; i < 4; i++) expect((await h.req("POST", "/v1/board", { token: a, body: { text: `p${i}`, place: "x" } })).status).toBe(201);
    expect((await h.req("POST", "/v1/board", { token: a, body: { text: "p5", place: "x" } })).status).toBe(429);
  });

  it("take down: only your own post, only while the board is open; gone for everyone; still counts toward the limit", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id: weekId } = await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    const b = await h.signIn("b@usc.edu");
    for (const t of [a, b]) await h.state(t);
    const takeDown = (token: string, id: string) => h.req("DELETE", `/v1/board/${id}`, { token });
    const ids = async (token: string) => (await h.req("GET", "/v1/board", { token })).json.posts.map((p: any) => p.id);

    expect((await takeDown(a, "po_anything")).json.error.code).toBe("board_closed"); // before the board opens

    h.now = T.laMidnightOfStart;
    const post = async (token: string, text: string) => {
      h.now += MIN;
      return (await h.req("POST", "/v1/board", { token, body: { text, place: "Quad" } })).json.post.id as string;
    };
    const mine = await post(a, "Chess, two boards");
    const theirs = await post(b, "Reading on the lawn");
    const list = await h.req("GET", "/v1/board", { token: b });
    expect(list.json.posts.map((p: any) => [p.id, p.mine])).toEqual([[theirs, true], [mine, false]]);

    // Someone else's post and an unknown id answer the same 404.
    for (const id of [theirs, "po_doesnotexist"]) {
      const r = await takeDown(a, id);
      expect([r.status, r.json.error.code]).toEqual([404, "post_not_found"]);
    }
    let r = await takeDown(a, mine);
    expect(r.status).toBe(200);
    expect(r.json).toEqual({
      open: true,
      opensAt: isoOf(T.laMidnightOfStart),
      closesAt: isoOf(T.endsAt),
      posts: [expect.objectContaining({ id: theirs, mine: false })],
    });
    r = await takeDown(a, mine); // twice is harmless
    expect([r.status, r.json.posts.length]).toEqual([200, 1]);
    expect(await ids(a)).toEqual([theirs]);
    expect(await ids(b)).toEqual([theirs]);

    // The taken-down post still counts: 1 + 4 more, then the limit.
    for (let i = 0; i < 4; i++) {
      h.now += MIN;
      expect((await h.req("POST", "/v1/board", { token: a, body: { text: `p${i}`, place: "x" } })).status).toBe(201);
    }
    expect((await h.req("POST", "/v1/board", { token: a, body: { text: "p5", place: "x" } })).status).toBe(429);

    // A taken-down post that was waiting for the editing check is not checked any more.
    h.ai = null;
    const pending = await post(b, "Cards at the fountain");
    await takeDown(b, pending);
    h.ai = new StubAi();
    expect((await h.req("POST", `/v1/admin/weeks/${weekId}/moderate`, { admin: true })).json.posts).toEqual({ ok: 0, hidden: 0, stillPending: 0 });
    expect((await h.req("GET", `/v1/admin/weeks/${weekId}`, { admin: true })).json.pendingChecks.posts).toBe(0);

    h.now = T.endsAt; // the window has ended
    r = await takeDown(b, theirs);
    expect([r.status, r.json.error.code]).toEqual([409, "board_closed"]);
  });

  it("the editing check: rejected posts are not stored; unchecked posts are hidden from everyone but their writer", async () => {
    const h = new Harness({ now: T.startsAt });
    await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    const b = await h.signIn("b@usc.edu");
    let r = await h.req("POST", "/v1/board", { token: a, body: { text: "Come find Alice", place: "Leavey" } });
    expect(r.status).toBe(422);
    expect(r.json.error).toMatchObject({ code: "not_shown", details: { reason: "names_or_targets_person" } });
    expect((await h.db.prepare("SELECT COUNT(*) AS n FROM board_posts").first<{ n: number }>())!.n).toBe(0);

    h.ai = null; // the check cannot run
    r = await h.req("POST", "/v1/board", { token: a, body: { text: "Chess, two boards", place: "Tutor Center" } });
    expect(r.status).toBe(201);
    expect(r.json).toMatchObject({ shown: false, post: { pending: true } });
    expect((await h.req("GET", "/v1/board", { token: a })).json.posts).toHaveLength(1);
    expect((await h.req("GET", "/v1/board", { token: b })).json.posts).toHaveLength(0);

    h.ai = new StubAi();
    const week = (await h.state(a)).week.id;
    const mod = await h.req("POST", `/v1/admin/weeks/${week}/moderate`, { admin: true });
    expect(mod.json.posts).toEqual({ ok: 1, hidden: 0, stillPending: 0 });
    expect((await h.req("GET", "/v1/board", { token: b })).json.posts).toHaveLength(1);
  });
});

describe("lines", () => {
  it("one optional line, only in ended, only for people who were in", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    const c = await h.signIn("c@usc.edu");
    await h.state(a);
    await h.req("POST", "/v1/me/skip", { token: c });

    h.now = T.endsAt - 1;
    expect((await h.req("POST", "/v1/lines", { token: a, body: { text: "Called my mom" } })).status).toBe(409);
    h.now = T.endsAt;
    let r = await h.req("POST", "/v1/lines", { token: a, body: { text: "Called my mom" } });
    expect(r.status).toBe(201);
    expect(r.json).toEqual({ ok: true, shown: true, pending: false });
    r = await h.req("POST", "/v1/lines", { token: a, body: { text: "Again" } });
    expect([r.status, r.json.error.code]).toEqual([409, "already_wrote"]);
    expect((await h.req("POST", "/v1/lines", { token: c, body: { text: "Hi" } })).json.error.code).toBe("not_in");
    h.now = T.toldAt;
    expect((await h.req("POST", "/v1/lines", { token: c, body: { text: "Hi" } })).status).toBe(409);
  });

  it("a rejected line is not stored, and the writer can try again", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    await h.state(a);
    h.now = T.endsAt;
    expect((await h.req("POST", "/v1/lines", { token: a, body: { text: "Alice is the worst" } })).status).toBe(422);
    expect((await h.db.prepare("SELECT COUNT(*) AS n FROM lines").first<{ n: number }>())!.n).toBe(0);
    expect((await h.req("POST", "/v1/lines", { token: a, body: { text: "Went for a walk" } })).status).toBe(201);
  });
});
