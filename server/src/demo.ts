/**
 * DEMO DATA. Simulated participants, votes, posts and lines so a demo can
 * walk through every phase. Every row written here has is_demo = 1, and
 * DELETE /v1/admin/demo removes them all. Nothing here is real.
 *
 * Seeding is step by step because what a participant does depends on the
 * phase (you cannot leave before the window starts). Typical order:
 *   step "week"     creates a demo week in its vote, demo users and votes
 *   (admin: timeline jumpTo "decided")
 *   step "decided"  some demo users skip this one
 *   (admin: timeline jumpTo "live", then optionally shiftSeconds back)
 *   step "live"     board posts, a few early leaves, reaches so far
 *   (admin: timeline jumpTo "ended")
 *   step "ended"    late-reported leaves, final reaches, lines
 * scripts/demo-seed.mjs and scripts/demo-week.mjs drive these calls.
 */
import { conflict } from "./errors";
import { newId } from "./ids";
import { decideIfDue, getWeek, overlappingWeek, type Week } from "./db";
import { TOLD_AFTER_END_MS, boardOpensAt, phaseAt, type Phase } from "./phase";
import { wallClock, zonedTimeToUtc } from "./time";

export const DEMO_USERS = 48;
export const demoEmail = (i: number) => `demo.participant.${String(i + 1).padStart(2, "0")}+quiet-hours-demo@usc.edu`;

export const DEMO_OPTIONS = [
  { day: 3, start: [21, 0], minutes: 60, reason: "DEMO: Review sessions in Leavey are over by then." },
  { day: 3, start: [19, 30], minutes: 90, reason: "DEMO: Classes are mostly done and nothing big is on." },
  { day: 4, start: [20, 0], minutes: 120, reason: "DEMO: The quietest night of the week. No exams the next day." },
];
// How many of the demo users vote for each option (the rest do not vote).
const DEMO_VOTES = [13, 21, 10];

const DEMO_POSTS: [string, string][] = [
  ["Reading on the grass, bring a book", "McCarthy Quad"],
  ["Sketching the fountain, extra pencils here", "Doheny Library steps"],
  ["Slow walk, all welcome, no destination", "Trousdale & Exposition"],
  ["Playing chess, two boards", "Ronald Tutor Campus Center, 2nd floor"],
  ["Writing letters home, have stamps", "Fertitta Hall courtyard"],
  ["Guitar, quietly, requests ok", "Alumni Park"],
  ["Stargazing if the sky is clear", "Parkside rooftop"],
  ["Puzzle, 1000 pieces, half done", "Leavey Library lobby"],
  ["Cooking dal for whoever shows up", "Webb Tower kitchen, floor 6"],
  ["Just sitting. Join if you want", "Hahn Plaza benches"],
];

const DEMO_LINES = [
  "Called my mom and actually listened this time",
  "Called my dad, we talked about his garden for an hour",
  "Called my grandma for the first time since August",
  "FaceTimed my little brother and helped with his homework",
  "Called my mom back after ignoring her all week",
  "Called my parents together, they put me on speaker at dinner",
  "Called my sister in Seoul, it was morning for her",
  "Walked to the Coliseum and back without headphones",
  "Walked around Exposition Park until it got dark",
  "Took a long walk with my roommate and talked about home",
  "Walked to get boba and noticed how loud the birds are",
  "Read 80 pages of a novel I bought in September",
  "Read poetry out loud on the lawn with two strangers",
  "Finally read the chapter for Thursday, and enjoyed it",
  "Reading in bed, which I haven't done since high school",
  "Cooked dinner with my suitemates, nobody touched a phone",
  "Ate dinner slowly for once",
  "Cooked my mom's recipe badly but it was still good",
  "Slept. Honestly the best hour of my week",
  "Napped and woke up without checking anything",
  "Fell asleep on the quad and a dog woke me up",
  "Wrote a letter by hand to my best friend from home",
  "Sat on the Doheny steps and watched the light change",
  "Played chess with a stranger and lost three times",
  "Practiced cello for the first time in a month",
  "Sketched the fountain, badly, and loved it",
  "Cried a little, then felt better",
  "Cleaned my whole room and found my old journal",
  "Looked at the sky for a while",
  "Learned a card trick from someone on my floor",
  "Did a puzzle in Leavey with people I'd never met",
  "Went to the gym and actually paid attention to the workout",
  "Planned my spring classes on paper",
  "Played guitar in Alumni Park, a few people sang along",
];

export type DemoStep = "week" | "decided" | "live" | "ended";

async function demoUserIds(db: D1Database): Promise<string[]> {
  const { results } = await db.prepare("SELECT id FROM users WHERE is_demo = 1 ORDER BY email").all<{ id: string }>();
  return results.map((r) => r.id);
}

async function demoWeek(db: D1Database, now: number): Promise<Week> {
  const r = await db
    .prepare("SELECT id FROM weeks WHERE is_demo = 1 AND vote_opens_at <= ? ORDER BY vote_opens_at DESC LIMIT 1")
    .bind(now)
    .first<{ id: string }>();
  if (!r) throw conflict("no_demo_week", 'No demo week has opened yet. Run step "week" first.');
  return decideIfDue(db, (await getWeek(db, r.id))!, now);
}

function requirePhase(week: Week, now: number, step: DemoStep, wanted: Phase): void {
  const phase = phaseAt(week, now);
  if (phase !== wanted) {
    throw conflict("wrong_phase", `Demo step "${step}" needs the demo week in "${wanted}", but it is in "${phase}". Use the admin timeline call first.`, {
      phase,
      wanted,
    });
  }
}

/** Spreads n instants evenly inside [from, to]. */
const spread = (n: number, from: number, to: number) =>
  Array.from({ length: n }, (_, i) => Math.floor(from + ((to - from) * (i + 1)) / (n + 1)));

export async function seedDemo(db: D1Database, step: DemoStep, now: number) {
  switch (step) {
    case "week":
      return seedWeek(db, now);
    case "decided":
      return seedDecided(db, now);
    case "live":
      return seedLive(db, now);
    case "ended":
      return seedEnded(db, now);
  }
}

async function seedWeek(db: D1Database, now: number) {
  const voteOpensAt = now - 60_000;
  const voteClosesAt = now + 2 * 86_400_000;
  const dayAt = (days: number, h: number, m: number) => {
    const w = wallClock(now + days * 86_400_000);
    return zonedTimeToUtc(w.year, w.month, w.day, h, m)!;
  };
  const windows = DEMO_OPTIONS.map((o) => {
    const start = dayAt(o.day, o.start[0]!, o.start[1]!);
    return { start, end: start + o.minutes * 60_000 };
  });
  // 15 minutes after the latest option ends. Once decided, toldAt is 15 minutes after the winner's end (decideIfDue).
  const toldAt = Math.max(...windows.map((w) => w.end)) + TOLD_AFTER_END_MS;
  const clash = await overlappingWeek(db, voteOpensAt, toldAt, null);
  if (clash) {
    throw conflict("week_overlap", `Week ${clash.id} overlaps the demo week. Remove demo data (DELETE /v1/admin/demo) or move that week.`, {
      weekId: clash.id,
    });
  }

  const weekId = newId("wk");
  const stmts: D1PreparedStatement[] = [
    db
      .prepare("INSERT INTO weeks (id, vote_opens_at, vote_closes_at, told_at, created_at, is_demo) VALUES (?, ?, ?, ?, ?, 1)")
      .bind(weekId, voteOpensAt, voteClosesAt, toldAt, now),
  ];
  const optionIds = DEMO_OPTIONS.map(() => newId("op"));
  DEMO_OPTIONS.forEach((o, i) => {
    stmts.push(
      db
        .prepare(
          "INSERT INTO options (id, week_id, position, starts_at, ends_at, reason, source, is_demo) VALUES (?, ?, ?, ?, ?, ?, 'demo', 1)",
        )
        .bind(optionIds[i], weekId, i + 1, windows[i]!.start, windows[i]!.end, o.reason),
    );
  });

  const existing = await demoUserIds(db);
  const userIds: string[] = [...existing];
  for (let i = existing.length; i < DEMO_USERS; i++) {
    const id = newId("us");
    userIds.push(id);
    stmts.push(db.prepare("INSERT INTO users (id, email, created_at, is_demo) VALUES (?, ?, ?, 1)").bind(id, demoEmail(i), now));
  }
  let u = 0;
  userIds.forEach((id, i) => {
    stmts.push(
      db
        .prepare("INSERT INTO participation (user_id, week_id, status, joined_at, is_demo) VALUES (?, ?, 'in', ?, 1)")
        .bind(id, weekId, voteOpensAt + (i + 1) * 1000),
    );
  });
  DEMO_VOTES.forEach((n, optionIndex) => {
    for (let k = 0; k < n && u < userIds.length; k++, u++) {
      stmts.push(
        db
          .prepare("INSERT INTO votes (user_id, week_id, option_id, updated_at, is_demo) VALUES (?, ?, ?, ?, 1)")
          .bind(userIds[u], weekId, optionIds[optionIndex], now),
      );
    }
  });
  await db.batch(stmts);
  return { step: "week", weekId, demoUsers: userIds.length, votes: u, options: optionIds.length };
}

async function seedDecided(db: D1Database, now: number) {
  const week = await demoWeek(db, now);
  requirePhase(week, now, "decided", "decided");
  const users = (await demoUserIds(db)).slice(-5);
  await db.batch(
    users.map((id) =>
      db.prepare("UPDATE participation SET status = 'skipped' WHERE user_id = ? AND week_id = ? AND status = 'in'").bind(id, week.id),
    ),
  );
  return { step: "decided", weekId: week.id, skipped: users.length };
}

async function seedLive(db: D1Database, now: number) {
  const week = await demoWeek(db, now);
  requirePhase(week, now, "live", "live");
  const users = await demoUserIds(db);
  const stmts: D1PreparedStatement[] = [];

  const postTimes = spread(DEMO_POSTS.length, boardOpensAt(week)!, now);
  DEMO_POSTS.forEach(([text, place], i) => {
    stmts.push(
      db
        .prepare(
          `INSERT INTO board_posts (id, week_id, user_id, text, place, created_at, moderation, moderation_note, is_demo)
           VALUES (?, ?, ?, ?, ?, ?, 'ok', 'demo data, hand-written', 1)`,
        )
        .bind(newId("po"), week.id, users[i % users.length], text, place, postTimes[i]),
    );
  });

  const leavers = users.slice(0, 3);
  const leaveTimes = spread(leavers.length, week.startsAt!, now);
  leavers.forEach((id, i) => {
    stmts.push(
      db
        .prepare("UPDATE participation SET status = 'left', left_at = ? WHERE user_id = ? AND week_id = ? AND status = 'in'")
        .bind(leaveTimes[i], id, week.id),
    );
  });
  users.forEach((id, i) => {
    stmts.push(
      db
        .prepare("UPDATE participation SET approx_reaches = MAX(approx_reaches, ?) WHERE user_id = ? AND week_id = ? AND status IN ('in', 'left')")
        .bind(i % 4, id, week.id),
    );
  });
  await db.batch(stmts);
  return { step: "live", weekId: week.id, posts: DEMO_POSTS.length, left: leavers.length };
}

async function seedEnded(db: D1Database, now: number) {
  const week = await demoWeek(db, now);
  requirePhase(week, now, "ended", "ended");
  const users = await demoUserIds(db);
  const stmts: D1PreparedStatement[] = [];

  // Leaves that happened during the window, reported late (as a phone would).
  const lateLeavers = users.slice(3, 7);
  const leaveTimes = spread(lateLeavers.length, week.startsAt!, week.endsAt!);
  lateLeavers.forEach((id, i) => {
    stmts.push(
      db
        .prepare("UPDATE participation SET status = 'left', left_at = ? WHERE user_id = ? AND week_id = ? AND status = 'in'")
        .bind(leaveTimes[i], id, week.id),
    );
  });
  users.forEach((id, i) => {
    stmts.push(
      db
        .prepare("UPDATE participation SET approx_reaches = MAX(approx_reaches, ?) WHERE user_id = ? AND week_id = ? AND status IN ('in', 'left')")
        .bind((i * 7) % 9, id, week.id),
    );
  });
  await db.batch(stmts);

  // Lines: one per participating demo user, until the hand-written lines run out.
  const { results } = await db
    .prepare(
      "SELECT user_id FROM participation WHERE week_id = ? AND is_demo = 1 AND status IN ('in', 'left') AND wrote_line = 0 ORDER BY user_id",
    )
    .bind(week.id)
    .all<{ user_id: string }>();
  const writers = results.slice(0, DEMO_LINES.length);
  const lineStmts: D1PreparedStatement[] = [];
  writers.forEach((w, i) => {
    lineStmts.push(
      db.prepare("INSERT INTO lines (id, week_id, text, moderation, is_demo) VALUES (?, ?, ?, 'ok', 1)").bind(newId("ln"), week.id, DEMO_LINES[i]),
      db.prepare("UPDATE participation SET wrote_line = 1 WHERE user_id = ? AND week_id = ?").bind(w.user_id, week.id),
    );
  });
  if (lineStmts.length) await db.batch(lineStmts);
  return { step: "ended", weekId: week.id, lateLeaves: lateLeavers.length, lines: writers.length };
}

/** Removes every row marked is_demo, and everything that hangs off demo weeks and users. */
export async function removeDemo(db: D1Database) {
  const count = async (sql: string) => Number((await db.prepare(sql).first<{ n: number }>())?.n ?? 0);
  const before = {
    weeks: await count("SELECT COUNT(*) AS n FROM weeks WHERE is_demo = 1"),
    users: await count("SELECT COUNT(*) AS n FROM users WHERE is_demo = 1"),
    posts: await count("SELECT COUNT(*) AS n FROM board_posts WHERE is_demo = 1"),
    lines: await count("SELECT COUNT(*) AS n FROM lines WHERE is_demo = 1"),
    votes: await count("SELECT COUNT(*) AS n FROM votes WHERE is_demo = 1"),
    participation: await count("SELECT COUNT(*) AS n FROM participation WHERE is_demo = 1"),
  };
  await db.batch([
    db.prepare("DELETE FROM board_posts WHERE is_demo = 1"),
    db.prepare("DELETE FROM lines WHERE is_demo = 1"),
    db.prepare("DELETE FROM votes WHERE is_demo = 1"),
    db.prepare("DELETE FROM participation WHERE is_demo = 1"),
    db.prepare("DELETE FROM recaps WHERE is_demo = 1"),
    db.prepare("UPDATE weeks SET winning_option_id = NULL, starts_at = NULL, ends_at = NULL WHERE is_demo = 1"),
    db.prepare("DELETE FROM weeks WHERE is_demo = 1"),
    db.prepare("DELETE FROM options WHERE is_demo = 1"),
    db.prepare("DELETE FROM users WHERE is_demo = 1"),
  ]);
  return { removed: before };
}
