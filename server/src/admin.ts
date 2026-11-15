/**
 * Admin operations: weeks, options, closing the vote, moving a week through
 * time for demos, re-running the editing check.
 */
import { conflict, notFound, badRequest } from "./errors";
import { newId } from "./ids";
import { countVotes, decideIfDue, getWeek, overlappingWeek, type Week } from "./db";
import { checkText } from "./moderation";
import { reasonProblem } from "./ai/proposals";
import type { AiProvider } from "./ai/types";
import { TOLD_AFTER_END_MS, phaseAt, type Phase } from "./phase";

export async function requireWeek(db: D1Database, id: string): Promise<Week> {
  const w = await getWeek(db, id);
  if (!w) throw notFound("week_not_found", `No week with id ${id}.`);
  return w;
}

export async function createWeek(
  db: D1Database,
  input: { voteOpensAt: number; voteClosesAt: number; toldAt: number },
  now: number,
): Promise<Week> {
  const { voteOpensAt, voteClosesAt, toldAt } = input;
  if (!(voteOpensAt < voteClosesAt && voteClosesAt < toldAt)) {
    throw badRequest("bad_timeline", "Need voteOpensAt < voteClosesAt < toldAt.");
  }
  const clash = await overlappingWeek(db, voteOpensAt, toldAt, null);
  if (clash) {
    throw conflict("week_overlap", `Week ${clash.id} overlaps this one. Weeks may not overlap (voteOpensAt to toldAt).`, {
      weekId: clash.id,
    });
  }
  const id = newId("wk");
  await db
    .prepare("INSERT INTO weeks (id, vote_opens_at, vote_closes_at, told_at, created_at) VALUES (?, ?, ?, ?, ?)")
    .bind(id, voteOpensAt, voteClosesAt, toldAt, now)
    .run();
  return (await getWeek(db, id))!;
}

export interface OptionInput {
  startsAt: number;
  endsAt: number;
  reason: string;
}

/** Replaces a week's options. Only before anyone has voted and before a decision. */
export async function setOptions(db: D1Database, week: Week, options: OptionInput[], source: "admin" | "ai") {
  if (week.winningOptionId) throw conflict("already_decided", "This week's vote is already decided.");
  if ((await countVotes(db, week.id)) > 0) {
    throw conflict("votes_exist", "People have already voted on this week's options, so they can no longer be replaced.");
  }
  options.forEach((o, i) => {
    if (!(o.startsAt < o.endsAt)) throw badRequest("bad_option", `Option ${i + 1}: startsAt must be before endsAt.`);
    if (o.startsAt < week.voteClosesAt) throw badRequest("bad_option", `Option ${i + 1}: starts before the vote closes.`);
    if (o.endsAt > week.toldAt - TOLD_AFTER_END_MS) {
      throw badRequest("bad_option", `Option ${i + 1}: ends less than 15 minutes before toldAt, so the hour could not be told back in time.`);
    }
    const problem = reasonProblem(o.reason);
    if (problem) throw badRequest("bad_option", `Option ${i + 1}: ${problem}.`);
  });
  await db.batch([
    db.prepare("DELETE FROM options WHERE week_id = ?").bind(week.id),
    ...options.map((o, i) =>
      db
        .prepare(
          "INSERT INTO options (id, week_id, position, starts_at, ends_at, reason, source, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        )
        .bind(newId("op"), week.id, i + 1, o.startsAt, o.endsAt, o.reason, source, week.isDemo ? 1 : 0),
    ),
  ]);
}

/** Decides now from the current count, regardless of voteClosesAt. */
async function forceDecide(db: D1Database, week: Week): Promise<Week> {
  if (week.winningOptionId) return week;
  const decided = await decideIfDue(db, { ...week, voteClosesAt: Number.NEGATIVE_INFINITY }, 0);
  if (!decided.winningOptionId) throw conflict("no_options", "This week has no options to decide between.");
  return decided;
}

/** Closes the vote now (if still open) and picks the winner by count. */
export async function closeVote(db: D1Database, week: Week, now: number): Promise<Week> {
  const phase = phaseAt(week, now);
  if (phase === null) throw conflict("vote_not_open", "This week's vote has not opened yet.");
  if (phase === "vote") {
    await db.prepare("UPDATE weeks SET vote_closes_at = ? WHERE id = ?").bind(now, week.id).run();
    week = (await getWeek(db, week.id))!;
  }
  const decided = await decideIfDue(db, week, now);
  if (!decided.winningOptionId) throw conflict("no_options", "This week has no options to decide between.");
  return decided;
}

/**
 * Moves every timestamp of a week (and of its options, participation and
 * board posts, so durations and numbers stay coherent) by `delta` ms.
 *
 * squeeze: for jumpTo. Moving a week forward through its phases moves its
 * vote into the past, where it can run into a week that has just ended
 * (two weeks back to back in a demo). When `squeeze.voteClosesBy` is given
 * and the moved vote would start before an earlier week's toldAt, the vote
 * alone (already over at `now`) is shortened to start at that toldAt and to
 * close by `voteClosesBy`. The window, toldAt and everyone's times keep the
 * plain shift.
 */
async function shiftWeek(
  db: D1Database,
  week: Week,
  delta: number,
  squeeze: { now: number; voteClosesBy: number } | null = null,
): Promise<Week> {
  if (delta === 0) return week;
  let opens = week.voteOpensAt + delta;
  let closes = week.voteClosesAt + delta;
  const told = week.toldAt + delta;
  if (squeeze) {
    const r = await db
      .prepare("SELECT MAX(told_at) AS t FROM weeks WHERE id != ? AND told_at <= ?")
      .bind(week.id, squeeze.now)
      .first<{ t: number | null }>();
    const floor = r?.t == null ? null : Number(r.t);
    if (floor !== null && opens < floor && floor < squeeze.voteClosesBy) {
      opens = floor;
      closes = Math.min(Math.max(closes, opens + 1), squeeze.voteClosesBy);
    }
  }
  const clash = await overlappingWeek(db, opens, told, week.id);
  if (clash) {
    throw conflict(
      "week_overlap",
      `Moving this week would overlap week ${clash.id} (weeks may not overlap from voteOpensAt to toldAt). Move that week with shiftSeconds, or remove demo data, first.`,
      { weekId: clash.id },
    );
  }
  await db.batch([
    db
      .prepare(
        `UPDATE weeks SET vote_opens_at = ?1, vote_closes_at = ?2,
                starts_at = starts_at + ?3, ends_at = ends_at + ?3, told_at = ?4 WHERE id = ?5`,
      )
      .bind(opens, closes, delta, told, week.id),
    db.prepare("UPDATE options SET starts_at = starts_at + ?1, ends_at = ends_at + ?1 WHERE week_id = ?2").bind(delta, week.id),
    db
      .prepare(
        "UPDATE participation SET joined_at = joined_at + ?1, left_at = left_at + ?1, came_back_at = came_back_at + ?1 WHERE week_id = ?2",
      )
      .bind(delta, week.id),
    db.prepare("UPDATE board_posts SET created_at = created_at + ?1 WHERE week_id = ?2").bind(delta, week.id),
  ]);
  return (await getWeek(db, week.id))!;
}

/**
 * Demo time control. jumpTo moves the whole week so that `now` is the first
 * instant of the given phase:
 *   vote     voteOpensAt  = now (and any decision is undone, so it can be re-run)
 *   decided  voteClosesAt = now (the winner is picked by count right away)
 *   live     startsAt     = now
 *   ended    endsAt       = now
 *   told     toldAt       = now
 * shiftSeconds moves the whole week by that many seconds instead.
 *
 * Jumping to decided, live, ended or told puts the vote in the past; if it
 * would then overlap a week that has already been told, the vote is
 * shortened to fit (see shiftWeek). shiftSeconds never shortens anything.
 */
export async function moveWeek(
  db: D1Database,
  week: Week,
  now: number,
  move: { jumpTo: Phase } | { shiftSeconds: number },
): Promise<Week> {
  if ("shiftSeconds" in move) return shiftWeek(db, week, Math.round(move.shiftSeconds * 1000));
  switch (move.jumpTo) {
    case "vote": {
      if (week.winningOptionId) {
        // The decision set toldAt from the winner; put it back after the last option, so any of them can win again.
        await db
          .prepare(
            `UPDATE weeks SET winning_option_id = NULL, starts_at = NULL, ends_at = NULL,
                    told_at = (SELECT MAX(ends_at) FROM options WHERE week_id = ?1) + ?2 WHERE id = ?1`,
          )
          .bind(week.id, TOLD_AFTER_END_MS)
          .run();
        week = (await getWeek(db, week.id))!;
      }
      return shiftWeek(db, week, now - week.voteOpensAt);
    }
    case "decided": {
      const moved = await shiftWeek(db, week, now - week.voteClosesAt, { now, voteClosesBy: now });
      return decideIfDue(db, moved, now);
    }
    case "live":
    case "ended":
    case "told": {
      const decided = await forceDecide(db, week);
      const anchor = { live: decided.startsAt!, ended: decided.endsAt!, told: decided.toldAt }[move.jumpTo];
      const delta = now - anchor;
      return shiftWeek(db, decided, delta, { now, voteClosesBy: decided.startsAt! + delta });
    }
  }
}

/** Re-runs the editing check on a week's pending posts and lines. */
export async function moderatePending(db: D1Database, ai: AiProvider, weekId: string) {
  const posts = await db
    .prepare("SELECT id, text, place FROM board_posts WHERE week_id = ? AND moderation = 'pending' AND taken_down = 0")
    .bind(weekId)
    .all<{ id: string; text: string; place: string }>();
  const lines = await db
    .prepare("SELECT id, text FROM lines WHERE week_id = ? AND moderation = 'pending'")
    .bind(weekId)
    .all<{ id: string; text: string }>();
  const tally = { posts: { ok: 0, hidden: 0, stillPending: 0 }, lines: { ok: 0, hidden: 0, stillPending: 0 } };

  for (const p of posts.results) {
    const out = await checkText(ai, `${p.text}\nPlace: ${p.place}`, "board_post");
    if (out.state === "pending") {
      tally.posts.stillPending++;
      continue;
    }
    const state = out.state === "ok" ? "ok" : "hidden";
    await db
      .prepare("UPDATE board_posts SET moderation = ?, moderation_note = ? WHERE id = ?")
      .bind(state, out.state === "ok" ? null : out.reason, p.id)
      .run();
    tally.posts[state]++;
  }
  for (const l of lines.results) {
    const out = await checkText(ai, l.text, "line");
    if (out.state === "pending") {
      tally.lines.stillPending++;
      continue;
    }
    const state = out.state === "ok" ? "ok" : "hidden";
    await db.prepare("UPDATE lines SET moderation = ? WHERE id = ?").bind(state, l.id).run();
    tally.lines[state]++;
  }
  return tally;
}
