/**
 * GET /v1/state: everything a client needs to draw the current moment.
 */
import type { User } from "./auth";
import {
  currentWeek,
  decideIfDue,
  ensureParticipation,
  getOption,
  getParticipation,
  getVote,
  listOptions,
  nextWeekVoteOpensAt,
  type Option,
  type Participation,
  type Week,
} from "./db";
import { numbersFor } from "./numbers";
import { boardOpensAt, capabilities, isBoardOpen, nextChangeAt, phaseAt, type Phase } from "./phase";
import { readRecap } from "./recaps";
import { iso, isoOrNull } from "./time";

export function optionView(o: Option) {
  return {
    id: o.id,
    startsAt: iso(o.startsAt),
    endsAt: iso(o.endsAt),
    minutes: Math.round((o.endsAt - o.startsAt) / 60_000),
    reason: o.reason,
    votes: o.votes,
  };
}

export function weekView(w: Week, nextVoteOpensAt: number | null) {
  return {
    id: w.id,
    voteOpensAt: iso(w.voteOpensAt),
    voteClosesAt: iso(w.voteClosesAt),
    startsAt: isoOrNull(w.startsAt),
    endsAt: isoOrNull(w.endsAt),
    toldAt: iso(w.toldAt),
    nextWeekVoteOpensAt: isoOrNull(nextVoteOpensAt),
    isDemo: w.isDemo,
  };
}

/**
 * The caller's part in a week, and what they can do in it right now. Null
 * participation (their app never saw the week) reads as status null.
 */
export function meView(p: Participation | null, phase: Phase | null, boardOpen: boolean) {
  const status = p?.status ?? null;
  const wroteLine = p?.wroteLine ?? false;
  return {
    status,
    joinedAt: isoOrNull(p?.joinedAt),
    leftAt: isoOrNull(p?.leftAt),
    /** What this person's phone reported. Approximate; see migrations/0002. */
    approxReaches: p?.approxReaches ?? 0,
    wroteLine,
    can: capabilities(phase, { status, wroteLine }, boardOpen),
  };
}

/** Phases in which opening the app puts you in for the week (in by default). */
export const JOINABLE: ReadonlySet<Phase> = new Set(["vote", "decided", "live"]);

/**
 * The current week, decided if its vote has closed, and the caller's row in
 * it (created, status 'in', if this is the first time their app has seen the
 * week and it is not over yet).
 */
export async function loadCurrent(db: D1Database, user: User, now: number) {
  let week = await currentWeek(db, now);
  if (!week) return null;
  week = await decideIfDue(db, week, now);
  const phase = phaseAt(week, now)!;
  let me: Participation | null = await getParticipation(db, user.id, week.id);
  if (!me && JOINABLE.has(phase)) me = await ensureParticipation(db, user.id, week.id, now);
  return { week, phase, me };
}

export async function buildState(db: D1Database, user: User, now: number) {
  const current = await loadCurrent(db, user, now);
  if (!current) {
    const upcoming = await nextWeekVoteOpensAt(db, now);
    return {
      serverTime: iso(now),
      phase: null,
      nextChangeAt: isoOrNull(upcoming),
      week: null,
      upcomingVoteOpensAt: isoOrNull(upcoming),
      options: null,
      totalVotes: null,
      myVote: null,
      winner: null,
      board: { open: false, opensAt: null, closesAt: null },
      me: null,
      numbers: null,
      recap: null,
    };
  }
  const { week, phase, me } = current;
  const nextOpens = await nextWeekVoteOpensAt(db, week.voteOpensAt);
  const boardOpen = isBoardOpen(week, now);
  // The options in every phase: the running tally during the vote, the final
  // count after it (votes cannot change once it closes). The winner is `winner`.
  const [options, myVote, winner, numbers, recap] = await Promise.all([
    listOptions(db, week.id),
    getVote(db, user.id, week.id),
    week.winningOptionId ? getOption(db, week.winningOptionId) : Promise.resolve(null),
    numbersFor(db, week, phase),
    phase === "told" ? readRecap(db, week.id) : Promise.resolve(null),
  ]);
  return {
    serverTime: iso(now),
    phase,
    nextChangeAt: isoOrNull(nextChangeAt(week, now, nextOpens)),
    week: weekView(week, nextOpens),
    upcomingVoteOpensAt: isoOrNull(nextOpens),
    options: options.map(optionView),
    /** Every vote cast this week: the sum of the options' counts. */
    totalVotes: options.reduce((n, o) => n + o.votes, 0),
    myVote,
    winner: winner ? optionView(winner) : null,
    board: {
      open: boardOpen,
      opensAt: isoOrNull(boardOpensAt(week)),
      closesAt: isoOrNull(week.endsAt),
    },
    me: meView(me, phase, boardOpen),
    numbers,
    recap,
  };
}
