/**
 * Data access. Plain SQL against D1. Rows are mapped to camelCase objects
 * here and nowhere else.
 */
import { TOLD_AFTER_END_MS, type Status, type WeekTimes } from "./phase";

export interface Week extends WeekTimes {
  id: string;
  winningOptionId: string | null;
  createdAt: number;
  isDemo: boolean;
}

export interface Option {
  id: string;
  weekId: string;
  position: number;
  startsAt: number;
  endsAt: number;
  reason: string;
  source: "admin" | "ai" | "demo";
  votes: number;
}

export interface Participation {
  userId: string;
  weekId: string;
  status: Status;
  joinedAt: number;
  leftAt: number | null;
  /** When they last came back after leaving during the window (migrations/0003). */
  cameBackAt: number | null;
  /** The phone's own running total; approximate (see migrations/0002). */
  approxReaches: number;
  wroteLine: boolean;
}

type Row = Record<string, unknown>;

const num = (v: unknown) => (v === null || v === undefined ? null : Number(v));

export function mapWeek(r: Row): Week {
  return {
    id: String(r.id),
    voteOpensAt: Number(r.vote_opens_at),
    voteClosesAt: Number(r.vote_closes_at),
    startsAt: num(r.starts_at),
    endsAt: num(r.ends_at),
    toldAt: Number(r.told_at),
    winningOptionId: r.winning_option_id == null ? null : String(r.winning_option_id),
    createdAt: Number(r.created_at),
    isDemo: Number(r.is_demo) === 1,
  };
}

function mapOption(r: Row): Option {
  return {
    id: String(r.id),
    weekId: String(r.week_id),
    position: Number(r.position),
    startsAt: Number(r.starts_at),
    endsAt: Number(r.ends_at),
    reason: String(r.reason),
    source: r.source as Option["source"],
    votes: Number(r.votes ?? 0),
  };
}

function mapParticipation(r: Row): Participation {
  return {
    userId: String(r.user_id),
    weekId: String(r.week_id),
    status: r.status as Status,
    joinedAt: Number(r.joined_at),
    leftAt: num(r.left_at),
    cameBackAt: num(r.came_back_at),
    approxReaches: Number(r.approx_reaches),
    wroteLine: Number(r.wrote_line) === 1,
  };
}

// ---------------------------------------------------------------- weeks

/** The current week: the one whose vote opened most recently. */
export async function currentWeek(db: D1Database, now: number): Promise<Week | null> {
  const r = await db
    .prepare("SELECT * FROM weeks WHERE vote_opens_at <= ? ORDER BY vote_opens_at DESC LIMIT 1")
    .bind(now)
    .first<Row>();
  return r ? mapWeek(r) : null;
}

export async function getWeek(db: D1Database, id: string): Promise<Week | null> {
  const r = await db.prepare("SELECT * FROM weeks WHERE id = ?").bind(id).first<Row>();
  return r ? mapWeek(r) : null;
}

export async function nextWeekVoteOpensAt(db: D1Database, after: number): Promise<number | null> {
  const r = await db
    .prepare("SELECT vote_opens_at FROM weeks WHERE vote_opens_at > ? ORDER BY vote_opens_at ASC LIMIT 1")
    .bind(after)
    .first<Row>();
  return r ? Number(r.vote_opens_at) : null;
}

export async function listWeeks(db: D1Database): Promise<Week[]> {
  const { results } = await db.prepare("SELECT * FROM weeks ORDER BY vote_opens_at DESC").all<Row>();
  return results.map(mapWeek);
}

/** Another week whose [voteOpensAt, toldAt] overlaps the given span, if any. */
export async function overlappingWeek(
  db: D1Database,
  voteOpensAt: number,
  toldAt: number,
  excludeId: string | null,
): Promise<Week | null> {
  const r = await db
    .prepare(
      "SELECT * FROM weeks WHERE vote_opens_at < ? AND told_at > ? AND id IS NOT ? LIMIT 1",
    )
    .bind(toldAt, voteOpensAt, excludeId)
    .first<Row>();
  return r ? mapWeek(r) : null;
}

// ---------------------------------------------------------------- options

export async function listOptions(db: D1Database, weekId: string): Promise<Option[]> {
  const { results } = await db
    .prepare(
      `SELECT o.*, (SELECT COUNT(*) FROM votes v WHERE v.option_id = o.id) AS votes
         FROM options o WHERE o.week_id = ? ORDER BY o.position`,
    )
    .bind(weekId)
    .all<Row>();
  return results.map(mapOption);
}

export async function getOption(db: D1Database, id: string): Promise<Option | null> {
  const r = await db
    .prepare(
      `SELECT o.*, (SELECT COUNT(*) FROM votes v WHERE v.option_id = o.id) AS votes
         FROM options o WHERE o.id = ?`,
    )
    .bind(id)
    .first<Row>();
  return r ? mapOption(r) : null;
}

export async function countVotes(db: D1Database, weekId: string): Promise<number> {
  const r = await db.prepare("SELECT COUNT(*) AS n FROM votes WHERE week_id = ?").bind(weekId).first<Row>();
  return Number(r?.n ?? 0);
}

/**
 * Picks the winner by count and copies its window onto the week, once, with
 * toldAt set 15 minutes after its end (TOLD_AFTER_END_MS). Options end at
 * least that long before the toldAt the week was created with, so toldAt
 * only moves earlier. Ties go to the option listed first (lowest position).
 * Safe to call concurrently: only the first UPDATE matches
 * `winning_option_id IS NULL`. Returns the (possibly updated) week.
 */
export async function decideIfDue(db: D1Database, week: Week, now: number): Promise<Week> {
  if (week.winningOptionId !== null || now < week.voteClosesAt) return week;
  const winner = await db
    .prepare(
      `SELECT o.id, o.starts_at, o.ends_at, COUNT(v.user_id) AS votes
         FROM options o LEFT JOIN votes v ON v.option_id = o.id
        WHERE o.week_id = ?
        GROUP BY o.id
        ORDER BY votes DESC, o.position ASC
        LIMIT 1`,
    )
    .bind(week.id)
    .first<Row>();
  if (!winner) return week; // no options: nothing to decide (admin must set options)
  await db
    .prepare(
      `UPDATE weeks SET winning_option_id = ?, starts_at = ?, ends_at = ?, told_at = ?
        WHERE id = ? AND winning_option_id IS NULL`,
    )
    .bind(winner.id, winner.starts_at, winner.ends_at, Number(winner.ends_at) + TOLD_AFTER_END_MS, week.id)
    .run();
  return (await getWeek(db, week.id))!;
}

// ---------------------------------------------------------------- participation

export async function getParticipation(db: D1Database, userId: string, weekId: string): Promise<Participation | null> {
  const r = await db
    .prepare("SELECT * FROM participation WHERE user_id = ? AND week_id = ?")
    .bind(userId, weekId)
    .first<Row>();
  return r ? mapParticipation(r) : null;
}

/**
 * In by default: creates the caller's row with status 'in' the first time
 * their app touches the week, and returns it. Existing rows are untouched.
 */
export async function ensureParticipation(
  db: D1Database,
  userId: string,
  weekId: string,
  now: number,
): Promise<Participation> {
  const existing = await getParticipation(db, userId, weekId);
  if (existing) return existing;
  await db
    .prepare(
      "INSERT OR IGNORE INTO participation (user_id, week_id, status, joined_at) VALUES (?, ?, 'in', ?)",
    )
    .bind(userId, weekId, now)
    .run();
  return (await getParticipation(db, userId, weekId))!;
}

export async function getVote(db: D1Database, userId: string, weekId: string): Promise<string | null> {
  const r = await db
    .prepare("SELECT option_id FROM votes WHERE user_id = ? AND week_id = ?")
    .bind(userId, weekId)
    .first<Row>();
  return r ? String(r.option_id) : null;
}
