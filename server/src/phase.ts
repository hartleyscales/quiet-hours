/**
 * The week as phases (docs/CONTRACT.md, "The week, as phases").
 *
 * Pure functions of a week's timestamps and "now". Nothing here is stored.
 *
 *   vote     voteOpensAt  <= now < voteClosesAt
 *   decided  voteClosesAt <= now < startsAt
 *   live     startsAt     <= now < endsAt
 *   ended    endsAt       <= now < toldAt
 *   told     toldAt       <= now < next week's voteOpensAt
 *
 * The upper bound of `told` is enforced by which week is current: the current
 * week is the one with the latest voteOpensAt <= now, so a week stops being
 * current exactly when the next week's vote opens.
 *
 * startsAt and endsAt are null until the vote is decided (they are copied
 * from the winning option). With startsAt unknown, a week past voteClosesAt
 * is `decided`: the vote is closed and the window is not here yet.
 */
import { startOfLocalDay } from "./time";

export const PHASES = ["vote", "decided", "live", "ended", "told"] as const;
export type Phase = (typeof PHASES)[number];

/**
 * toldAt is 15 minutes after endsAt (docs/CONTRACT.md). It is set when the
 * vote is decided (db.ts, decideIfDue). Before that, a week's toldAt is the
 * latest the hour can be told back, and every option ends at least this long
 * before it.
 */
export const TOLD_AFTER_END_MS = 15 * 60_000;

export interface WeekTimes {
  voteOpensAt: number;
  voteClosesAt: number;
  startsAt: number | null;
  endsAt: number | null;
  toldAt: number;
}

/** The phase at `now`, or null if the week's vote has not opened yet. */
export function phaseAt(w: WeekTimes, now: number): Phase | null {
  if (now < w.voteOpensAt) return null;
  if (now < w.voteClosesAt) return "vote";
  if (w.startsAt === null || w.endsAt === null || now < w.startsAt) return "decided";
  if (now < w.endsAt) return "live";
  if (now < w.toldAt) return "ended";
  return "told";
}

/**
 * When the board opens: midnight (America/Los_Angeles) at the start of the
 * calendar day of startsAt. The board is never open during the vote, so if
 * the vote closes after that midnight, the board opens when the vote closes.
 * Null while the window is unknown.
 */
export function boardOpensAt(w: WeekTimes): number | null {
  if (w.startsAt === null) return null;
  return Math.max(startOfLocalDay(w.startsAt), w.voteClosesAt);
}

/** The board is open from boardOpensAt until endsAt. Posts are hidden after endsAt. */
export function isBoardOpen(w: WeekTimes, now: number): boolean {
  const opens = boardOpensAt(w);
  if (opens === null || w.endsAt === null) return false;
  return now >= opens && now < w.endsAt;
}

/**
 * The next instant at which anything a client draws changes on its own
 * (a phase boundary, or the board opening). Clients can use it to schedule
 * their next refresh. Null when nothing further is scheduled.
 */
export function nextChangeAt(w: WeekTimes, now: number, nextWeekVoteOpensAt: number | null): number | null {
  const marks = [w.voteOpensAt, w.voteClosesAt, boardOpensAt(w), w.startsAt, w.endsAt, w.toldAt, nextWeekVoteOpensAt];
  let next: number | null = null;
  for (const t of marks) {
    if (t !== null && t > now && (next === null || t < next)) next = t;
  }
  return next;
}

export type Status = "in" | "skipped" | "left";

export interface Me {
  status: Status | null;
  wroteLine: boolean;
}

/**
 * What the caller can do right now. The server enforces the same rules on
 * every write; these flags let a client draw only what will work.
 *
 * Two late-report cases are allowed by the API but not advertised here
 * because only the phone knows whether it has something unsent: a leave or a
 * reach count from the window may still be reported after it, in `ended`,
 * `told`, or for a past week by weekId (see POST /v1/me/leave and
 * /v1/me/reaches).
 */
export function capabilities(phase: Phase | null, me: Me, boardOpen: boolean) {
  const s = me.status;
  const beforeWindow = phase === "vote" || phase === "decided";
  return {
    vote: phase === "vote" && s !== "skipped",
    skip: beforeWindow && s === "in",
    rejoin: (beforeWindow && s === "skipped") || (phase === "live" && (s === "skipped" || s === "left")),
    leave: phase === "live" && s === "in",
    reportReaches: phase === "live" && (s === "in" || s === "left"),
    post: boardOpen && s === "in",
    writeLine: phase === "ended" && (s === "in" || s === "left") && !me.wroteLine,
  };
}
export type Capabilities = ReturnType<typeof capabilities>;
