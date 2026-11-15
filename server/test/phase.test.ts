import { describe, expect, it } from "vitest";
import { boardOpensAt, capabilities, isBoardOpen, nextChangeAt, phaseAt, type WeekTimes } from "../src/phase";
import { formatLocal, parseLocal, startOfLocalDay, zonedTimeToUtc } from "../src/time";
import { T } from "./helpers";

const week: WeekTimes = {
  voteOpensAt: T.voteOpensAt,
  voteClosesAt: T.voteClosesAt,
  startsAt: T.startsAt,
  endsAt: T.endsAt,
  toldAt: T.toldAt,
};

describe("phaseAt: every boundary of the contract's table", () => {
  const cases: [string, number, string | null][] = [
    ["1 ms before the vote opens", T.voteOpensAt - 1, null],
    ["the instant the vote opens", T.voteOpensAt, "vote"],
    ["1 ms before the vote closes", T.voteClosesAt - 1, "vote"],
    ["the instant the vote closes", T.voteClosesAt, "decided"],
    ["1 ms before startsAt", T.startsAt - 1, "decided"],
    ["the instant of startsAt", T.startsAt, "live"],
    ["1 ms before endsAt", T.endsAt - 1, "live"],
    ["the instant of endsAt", T.endsAt, "ended"],
    ["1 ms before toldAt", T.toldAt - 1, "ended"],
    ["the instant of toldAt", T.toldAt, "told"],
    ["a month later", T.toldAt + 30 * 86_400_000, "told"],
  ];
  for (const [name, now, expected] of cases) {
    it(`${name} -> ${expected}`, () => expect(phaseAt(week, now)).toBe(expected));
  }

  it("is `decided` after the vote closes while the window is still unknown", () => {
    const undecided = { ...week, startsAt: null, endsAt: null };
    expect(phaseAt(undecided, T.voteClosesAt)).toBe("decided");
    expect(phaseAt(undecided, T.toldAt + 1)).toBe("decided");
  });
});

describe("the board: opens on the calendar day of startsAt in Los Angeles, hidden after endsAt", () => {
  it("opens at local midnight of the start day", () => {
    expect(boardOpensAt(week)).toBe(T.laMidnightOfStart);
    expect(new Date(T.laMidnightOfStart).toISOString()).toBe("2026-11-18T08:00:00.000Z");
  });

  it("is closed 1 ms before midnight, open at midnight, open 1 ms before endsAt, closed at endsAt", () => {
    expect(isBoardOpen(week, T.laMidnightOfStart - 1)).toBe(false);
    expect(isBoardOpen(week, T.laMidnightOfStart)).toBe(true);
    expect(isBoardOpen(week, T.startsAt)).toBe(true);
    expect(isBoardOpen(week, T.endsAt - 1)).toBe(true);
    expect(isBoardOpen(week, T.endsAt)).toBe(false);
    expect(isBoardOpen(week, T.toldAt)).toBe(false);
  });

  it("is never open during the vote, even on the start day", () => {
    // Vote closes at 18:00 on the same day the window starts at 21:00.
    const sameDay = { ...week, voteClosesAt: Date.parse("2026-11-18T18:00:00-08:00") };
    expect(boardOpensAt(sameDay)).toBe(sameDay.voteClosesAt);
    expect(isBoardOpen(sameDay, Date.parse("2026-11-18T10:00:00-08:00"))).toBe(false);
    expect(isBoardOpen(sameDay, sameDay.voteClosesAt)).toBe(true);
  });

  it("is closed while the window is undecided", () => {
    const undecided = { ...week, startsAt: null, endsAt: null };
    expect(boardOpensAt(undecided)).toBeNull();
    expect(isBoardOpen(undecided, T.startsAt)).toBe(false);
  });

  it("uses the Los Angeles day, not the UTC day (a 21:00 PST start is the next day in UTC)", () => {
    // 2026-11-18 21:00 PST is 2026-11-19 05:00 UTC; the board still opens on the 18th, local.
    expect(new Date(T.startsAt).toISOString().slice(0, 10)).toBe("2026-11-19");
    expect(formatLocal(boardOpensAt(week)!)).toBe("2026-11-18T00:00");
  });

  it("handles the day clocks fall back (2026-11-01) and spring forward (2026-03-08)", () => {
    const fallBack = Date.parse("2026-11-01T21:00:00-08:00");
    expect(new Date(startOfLocalDay(fallBack)).toISOString()).toBe("2026-11-01T07:00:00.000Z"); // midnight PDT
    const springForward = Date.parse("2026-03-08T21:00:00-07:00");
    expect(new Date(startOfLocalDay(springForward)).toISOString()).toBe("2026-03-08T08:00:00.000Z"); // midnight PST
  });
});

describe("nextChangeAt", () => {
  it("walks through every boundary in order, including the board opening", () => {
    const next = 1_000_000_000_000_000;
    expect(nextChangeAt(week, T.voteOpensAt, null)).toBe(T.voteClosesAt);
    expect(nextChangeAt(week, T.voteClosesAt, null)).toBe(T.laMidnightOfStart);
    expect(nextChangeAt(week, T.laMidnightOfStart, null)).toBe(T.startsAt);
    expect(nextChangeAt(week, T.startsAt, null)).toBe(T.endsAt);
    expect(nextChangeAt(week, T.endsAt, null)).toBe(T.toldAt);
    expect(nextChangeAt(week, T.toldAt, null)).toBeNull();
    expect(nextChangeAt(week, T.toldAt, next)).toBe(next);
  });
});

describe("capabilities", () => {
  const me = (status: "in" | "skipped" | "left" | null, wroteLine = false) => ({ status, wroteLine });
  it("vote only in vote, and not after skipping", () => {
    expect(capabilities("vote", me("in"), false).vote).toBe(true);
    expect(capabilities("vote", me("skipped"), false).vote).toBe(false);
    expect(capabilities("decided", me("in"), false).vote).toBe(false);
  });
  it("skip in vote and decided; rejoin then after a skip, and in live after a skip or a leave", () => {
    for (const phase of ["vote", "decided"] as const) {
      expect(capabilities(phase, me("in"), false)).toMatchObject({ skip: true, rejoin: false });
      expect(capabilities(phase, me("skipped"), false)).toMatchObject({ skip: false, rejoin: true });
    }
    expect(capabilities("live", me("in"), true)).toMatchObject({ skip: false, rejoin: false });
    expect(capabilities("live", me("skipped"), true)).toMatchObject({ skip: false, rejoin: true });
    expect(capabilities("live", me("left"), true)).toMatchObject({ skip: false, rejoin: true });
    for (const phase of ["ended", "told"] as const) {
      expect(capabilities(phase, me("skipped"), false)).toMatchObject({ skip: false, rejoin: false });
      expect(capabilities(phase, me("left"), false)).toMatchObject({ skip: false, rejoin: false });
    }
  });
  it("leave only in live and only when in", () => {
    expect(capabilities("live", me("in"), true).leave).toBe(true);
    expect(capabilities("live", me("left"), true).leave).toBe(false);
    expect(capabilities("live", me("skipped"), true).leave).toBe(false);
    expect(capabilities("ended", me("in"), false).leave).toBe(false);
  });
  it("post only while the board is open and only when in", () => {
    expect(capabilities("decided", me("in"), true).post).toBe(true);
    expect(capabilities("decided", me("in"), false).post).toBe(false);
    expect(capabilities("live", me("left"), true).post).toBe(false);
  });
  it("one line, only in ended, only for people who were in", () => {
    expect(capabilities("ended", me("in"), false).writeLine).toBe(true);
    expect(capabilities("ended", me("left"), false).writeLine).toBe(true);
    expect(capabilities("ended", me("in", true), false).writeLine).toBe(false);
    expect(capabilities("ended", me("skipped"), false).writeLine).toBe(false);
    expect(capabilities("told", me("in"), false).writeLine).toBe(false);
  });
});

describe("time helpers", () => {
  it("rejects the wall time skipped by daylight saving and picks the first of a repeated hour", () => {
    expect(zonedTimeToUtc(2026, 3, 8, 2, 30)).toBeNull();
    expect(new Date(zonedTimeToUtc(2026, 11, 1, 1, 30)!).toISOString()).toBe("2026-11-01T08:30:00.000Z");
  });
  it("round-trips local times", () => {
    expect(formatLocal(parseLocal("2026-11-18T21:00")!)).toBe("2026-11-18T21:00");
    expect(parseLocal("2026-11-18 21:00")).toBeNull();
    expect(parseLocal("2026-03-08T02:15")).toBeNull();
  });
});
