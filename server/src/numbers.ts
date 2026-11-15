/**
 * The contract's "Numbers". Every value is counted from stored participation
 * rows (and, for `lines`, stored lines) at the moment it is asked for.
 * Nothing is cached.
 *
 *   in              rows with status 'in'
 *   liveCount       the same count, reported only while the phase is `live`
 *   approxReaches   sum of approx_reaches over every row of the week. Each
 *                   row holds what that person's phone reported, and the
 *                   phone can only approximate how often the lock screen
 *                   appeared (docs/LOCK-NOTES.md, "Reach counter"). The sum
 *                   is exact; what is summed is not.
 *   hoursGivenBack  sum over participants (status 'in' or 'left') of the time
 *                   they were actually in: from max(startsAt, joinedAt) to
 *                   leftAt (or endsAt if they are in), clamped to the window,
 *                   minus away_ms, the time between leaving and coming back
 *   stayed          of the people who were in at startsAt (status 'in' or
 *                   'left', with joinedAt <= startsAt), how many never left:
 *                   status 'in' and came_back_at null (a row that came back
 *                   has left at least once)
 *   lines           every stored line of the week, in `ended` and `told`:
 *                   shown, waiting for the editing check, or hidden by it (a
 *                   line declined at submission is never stored). A count of
 *                   the lines table by week only, so it says nothing about
 *                   who wrote which line.
 *
 * Why "joinedAt <= startsAt" means "in at startsAt": skipping is only
 * possible before startsAt, and so is a rejoin that leaves joinedAt alone.
 * Someone who skipped and joins during the window gets joinedAt = the time
 * they joined (migrations/0003), the same as someone whose app first saw the
 * week mid-window: they count toward `in` and hours from then, but they were
 * not in at startsAt. Everyone else with joinedAt <= startsAt and status 'in'
 * or 'left' was in at startsAt: 'left' is only reachable from 'in' with a
 * leftAt inside the window, and coming back after a leave keeps joinedAt.
 *
 * Why max(startsAt, joinedAt) to the end, minus away_ms, is the time in:
 * after joinedAt a person is out only between a leave and coming back (each
 * gap is added to away_ms when they come back) or after their current leave
 * (the span ends at leftAt). A leave reported for a time before they came
 * back is ignored (POST /v1/me/leave), so a gap is never counted twice.
 *
 * Leaves and reach counts can be reported late (after endsAt, even after
 * toldAt), so these numbers can still move after the window. They are
 * always recomputed, never snapshotted, wherever they are shown.
 */
import type { Week } from "./db";
import type { Phase } from "./phase";

export interface Stayed {
  count: number;
  of: number;
  /** count / of, or null when of = 0. Unrounded. */
  share: number | null;
}

export interface Numbers {
  in: number;
  liveCount: number | null;
  approxReaches: number | null;
  secondsGivenBack: number | null;
  hoursGivenBack: number | null;
  stayed: Stayed | null;
  lines: number | null;
}

/** Every stored line of the week. Counted by week only; nothing about who wrote one. */
export async function countLines(db: D1Database, weekId: string): Promise<number> {
  const r = await db.prepare("SELECT COUNT(*) AS n FROM lines WHERE week_id = ?").bind(weekId).first<{ n: number }>();
  return Number(r?.n ?? 0);
}

export interface RawCounts {
  in: number;
  approxReaches: number;
  inAtStart: number;
  stayedCount: number;
  msGivenBack: number;
}

export async function rawCounts(db: D1Database, week: Week): Promise<RawCounts> {
  // starts/ends are null before the decision; then the window-based columns are 0.
  const starts = week.startsAt ?? 0;
  const ends = week.endsAt ?? 0;
  const r = await db
    .prepare(
      `SELECT
         COALESCE(SUM(status = 'in'), 0) AS in_count,
         COALESCE(SUM(approx_reaches), 0) AS approx_reaches,
         COALESCE(SUM(status IN ('in', 'left') AND joined_at <= ?1), 0) AS in_at_start,
         COALESCE(SUM(status = 'in' AND joined_at <= ?1 AND came_back_at IS NULL), 0) AS stayed,
         COALESCE(SUM(CASE WHEN status IN ('in', 'left')
              THEN MAX(0, MIN(COALESCE(left_at, ?2), ?2) - MAX(?1, joined_at) - away_ms)
              ELSE 0 END), 0) AS ms_given_back
       FROM participation WHERE week_id = ?3`,
    )
    .bind(starts, ends, week.id)
    .first<Record<string, unknown>>();
  return {
    in: Number(r?.in_count ?? 0),
    approxReaches: Number(r?.approx_reaches ?? 0),
    inAtStart: Number(r?.in_at_start ?? 0),
    stayedCount: Number(r?.stayed ?? 0),
    msGivenBack: Number(r?.ms_given_back ?? 0),
  };
}

/** The after-the-window numbers, from raw counts. */
export function afterNumbers(c: RawCounts) {
  return {
    in: c.in,
    approxReaches: c.approxReaches,
    secondsGivenBack: Math.floor(c.msGivenBack / 1000),
    hoursGivenBack: Math.round((c.msGivenBack / 3_600_000) * 10) / 10,
    stayed: { count: c.stayedCount, of: c.inAtStart, share: c.inAtStart ? c.stayedCount / c.inAtStart : null },
  };
}

/** The numbers shown in a given phase. Fields that do not apply are null. */
export async function numbersFor(db: D1Database, week: Week, phase: Phase | null): Promise<Numbers> {
  const c = await rawCounts(db, week);
  if (phase === "ended" || phase === "told") {
    const a = afterNumbers(c);
    return {
      in: a.in,
      liveCount: null,
      approxReaches: a.approxReaches,
      secondsGivenBack: a.secondsGivenBack,
      hoursGivenBack: a.hoursGivenBack,
      stayed: a.stayed,
      lines: await countLines(db, week.id),
    };
  }
  return {
    in: c.in,
    liveCount: phase === "live" ? c.in : null,
    approxReaches: phase === "live" ? c.approxReaches : null,
    secondsGivenBack: null,
    hoursGivenBack: null,
    stayed: null,
    lines: null,
  };
}
