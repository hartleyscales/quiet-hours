/**
 * HTTP API. Route list and examples: docs/API.md.
 */
import { Hono, type Context } from "hono";
import { z } from "zod";
import { AnthropicAi } from "./ai/anthropic";
import { CampusWeekSchema } from "./ai/campus-week";
import { FakeAi } from "./ai/fake";
import { MAX_REASON, proposeWindows } from "./ai/proposals";
import { AiUnavailableError, type AiProvider } from "./ai/types";
import { closeVote, createWeek, moderatePending, moveWeek, requireWeek, setOptions } from "./admin";
import {
  DEV_CODE_WARNING,
  DevResponseSender,
  UnconfiguredEmailSender,
  authenticate,
  signOut,
  startSignin,
  verifySignin,
  type CodeSender,
  type User,
} from "./auth";
import { readConfig, type Config, type Env } from "./config";
import { decideIfDue, getParticipation, getWeek, listWeeks, nextWeekVoteOpensAt, type Participation, type Week } from "./db";
import { removeDemo, seedDemo } from "./demo";
import { ApiError, badRequest, conflict, forbidden, notFound, tooMany, unavailable } from "./errors";
import { newId, safeEqual } from "./ids";
import { checkText, notShown } from "./moderation";
import { numbersFor } from "./numbers";
import { PHASES, boardOpensAt, isBoardOpen, phaseAt } from "./phase";
import { generateAndStoreRecap, readRecap } from "./recaps";
import { buildState, loadCurrent, meView, optionView, weekView } from "./state";
import { iso, isoOrNull, parseInstant } from "./time";

export const MAX_POSTS_PER_WEEK = 5;
export const POST_TEXT_MAX = 140;
export const PLACE_MAX = 60;
export const LINE_MAX = 200;
/** How far before startsAt a reported leftAt may be (phone clock skew) before it is rejected. */
export const CLOCK_SKEW_MS = 5 * 60_000;

export interface Deps {
  /** Clock. Tests inject one; production uses Date.now. */
  now?: () => number;
  /** AI provider factory. Tests inject stubs. Null means "not configured". */
  ai?: (env: Env, config: Config) => AiProvider | null;
}

type Vars = { config: Config; user: User; now: number };
type C = Context<{ Bindings: Env; Variables: Vars }>;

function defaultAi(env: Env, config: Config): AiProvider | null {
  if (config.aiMode === "dev-fake") return new FakeAi();
  return env.ANTHROPIC_API_KEY ? new AnthropicAi(env.ANTHROPIC_API_KEY) : null;
}

function codeSender(config: Config): CodeSender {
  return config.signinDelivery === "dev-response" ? new DevResponseSender() : new UnconfiguredEmailSender();
}

// ------------------------------------------------------------ input parsing

const instant = z.string().transform((s, ctx) => {
  const ms = parseInstant(s);
  if (ms === null) {
    ctx.addIssue({ code: "custom", message: "expected an ISO 8601 time with an offset, e.g. 2026-11-18T21:00:00-08:00" });
    return z.NEVER;
  }
  return ms;
});

const oneLine = (max: number) =>
  z
    .string()
    .transform((s) => s.trim().replace(/\s+/g, " "))
    .pipe(z.string().min(1, "must not be empty").max(max, `must be at most ${max} characters`));

async function body<T extends z.ZodTypeAny>(c: C, schema: T): Promise<z.output<T>> {
  let raw: unknown;
  try {
    const text = await c.req.text();
    raw = text ? JSON.parse(text) : {};
  } catch {
    throw badRequest("invalid_json", "The request body is not valid JSON.");
  }
  const parsed = schema.safeParse(raw);
  if (!parsed.success) {
    throw badRequest("invalid_request", "The request body does not match what this endpoint expects.", {
      issues: parsed.error.issues.map((i) => ({ path: i.path.join("."), message: i.message })),
    });
  }
  return parsed.data;
}

/** If the client says which week it means, make sure it is still the current one. */
function assertSameWeek(clientWeekId: string | undefined, weekId: string) {
  if (clientWeekId && clientWeekId !== weekId) {
    throw conflict("week_changed", "The current week has changed. Fetch /v1/state again.", { currentWeekId: weekId });
  }
}

const weekRef = { weekId: z.string().optional() };

// ------------------------------------------------------------ app

export function createApp(deps: Deps = {}) {
  const clock = deps.now ?? Date.now;
  const aiFactory = deps.ai ?? defaultAi;
  const app = new Hono<{ Bindings: Env; Variables: Vars }>();

  const ai = (c: C) => aiFactory(c.env, c.var.config);
  const requireAi = (c: C) => {
    const p = ai(c);
    if (!p) throw new AiUnavailableError();
    return p;
  };

  app.onError((err, c) => {
    if (err instanceof ApiError) {
      return c.json({ error: { code: err.code, message: err.message, ...(err.details ? { details: err.details } : {}) } }, err.status as 400);
    }
    console.error("unhandled", err instanceof Error ? err.stack ?? err.message : err);
    return c.json({ error: { code: "internal", message: "Something went wrong on the server." } }, 500);
  });
  app.notFound((c) => c.json({ error: { code: "not_found", message: `No route for ${c.req.method} ${c.req.path}.` } }, 404));

  // Config check, clock, and the loud development header on every response.
  app.use("*", async (c, next) => {
    const config = readConfig(c.env);
    c.set("config", config);
    c.set("now", clock());
    await next();
    if (config.insecureModes.length) {
      c.header("X-Quiet-Hours-Insecure-Dev-Mode", config.insecureModes.join(", "));
    }
  });

  // ---------------------------------------------------------- public

  app.get("/v1/health", (c) => {
    const config = c.var.config;
    return c.json({
      ok: true,
      serverTime: iso(c.var.now),
      environment: config.environment,
      insecureDevModes: config.insecureModes,
      signinDelivery: config.signinDelivery,
      ai: { mode: config.aiMode, configured: config.aiMode === "dev-fake" || Boolean(c.env.ANTHROPIC_API_KEY) },
    });
  });

  app.post("/v1/auth/start", async (c) => {
    const { email } = await body(c, z.object({ email: z.string() }));
    const config = c.var.config;
    const out = await startSignin(c.env.DB, codeSender(config), email, c.var.now);
    return c.json({
      email: out.email,
      expiresAt: iso(out.expiresAt),
      delivery: config.signinDelivery,
      ...(config.signinDelivery === "dev-response" ? { devCode: out.code, devWarning: DEV_CODE_WARNING } : {}),
    });
  });

  app.post("/v1/auth/verify", async (c) => {
    const { email, code } = await body(c, z.object({ email: z.string(), code: z.string() }));
    const out = await verifySignin(c.env.DB, email, code, c.var.now);
    return c.json({ token: out.token, expiresAt: iso(out.expiresAt), user: { id: out.user.id, email: out.user.email } });
  });

  // ---------------------------------------------------------- signed in

  const signedIn = async (c: C, next: () => Promise<void>) => {
    c.set("user", await authenticate(c.env.DB, c.req.header("Authorization"), c.var.now));
    await next();
  };

  app.post("/v1/auth/sign-out", async (c) => {
    await signOut(c.env.DB, c.req.header("Authorization"));
    return c.json({ ok: true });
  });

  app.get("/v1/state", signedIn, async (c) => c.json(await buildState(c.env.DB, c.var.user, c.var.now)));

  /** The current week in a phase that allows the action, or a 409 that says so. */
  const currentIn = async (c: C, allowed: string[], action: string) => {
    const cur = await loadCurrent(c.env.DB, c.var.user, c.var.now);
    if (!cur) throw conflict("no_week", "There is no current week.");
    if (!allowed.includes(cur.phase)) {
      throw conflict("phase_closed", `You can ${action} only during: ${allowed.join(", ")}. The week is in "${cur.phase}".`, {
        phase: cur.phase,
        allowed,
      });
    }
    return cur;
  };

  app.post("/v1/vote", signedIn, async (c) => {
    const input = await body(c, z.object({ optionId: z.string(), ...weekRef }));
    const db = c.env.DB;
    const { week, me } = await currentIn(c, ["vote"], "vote");
    assertSameWeek(input.weekId, week.id);
    const skipped = () => conflict("not_in", "You skipped this week, so you cannot vote. Rejoin first.");
    if (me?.status === "skipped") throw skipped();
    const now = c.var.now;
    // The WHERE clause re-checks the vote is open and the voter has not skipped,
    // so a vote racing the close or a skip cannot land after it.
    const res = await db
      .prepare(
        `INSERT INTO votes (user_id, week_id, option_id, updated_at)
         SELECT ?1, ?2, o.id, ?3 FROM options o JOIN weeks w ON w.id = o.week_id
          WHERE o.id = ?4 AND o.week_id = ?2 AND w.vote_opens_at <= ?3 AND w.vote_closes_at > ?3 AND w.winning_option_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM participation p WHERE p.user_id = ?1 AND p.week_id = ?2 AND p.status = 'skipped')
         ON CONFLICT (user_id, week_id) DO UPDATE SET option_id = excluded.option_id, updated_at = excluded.updated_at`,
      )
      .bind(c.var.user.id, week.id, now, input.optionId)
      .run();
    if (res.meta.changes !== 1) {
      const option = await db.prepare("SELECT 1 FROM options WHERE id = ? AND week_id = ?").bind(input.optionId, week.id).first();
      if (!option) throw notFound("option_not_found", "That option is not one of this week's windows.");
      if ((await getParticipation(db, c.var.user.id, week.id))?.status === "skipped") throw skipped();
      throw conflict("phase_closed", "The vote has closed.", { phase: "decided" });
    }
    const state = await buildState(db, c.var.user, now);
    return c.json({ myVote: state.myVote, options: state.options });
  });

  const currentMe = async (c: C) => (await buildState(c.env.DB, c.var.user, c.var.now)).me;

  /** Skip this week. Only before the window starts. A vote already cast is kept and still counted. */
  app.post("/v1/me/skip", signedIn, async (c) => {
    const input = await body(c, z.object(weekRef));
    const { week, me } = await currentIn(c, ["vote", "decided"], "skip");
    assertSameWeek(input.weekId, week.id);
    if (me!.status === "in") {
      await c.env.DB.prepare("UPDATE participation SET status = 'skipped' WHERE user_id = ? AND week_id = ? AND status = 'in'")
        .bind(c.var.user.id, week.id)
        .run();
    }
    return c.json({ me: await currentMe(c) });
  });

  /**
   * Rejoin. Before the window (vote, decided), someone who skipped is in
   * again. During the window (live), someone who is out gets back in
   * (migrations/0003):
   *   - skipped: in, counted from now (joined_at = now), not in at startsAt;
   *   - left: in again; the time since the leave is added to away_ms and
   *     came_back_at = now. They can leave again.
   */
  app.post("/v1/me/rejoin", signedIn, async (c) => {
    const input = await body(c, z.object(weekRef));
    const { week, phase, me } = await currentIn(c, ["vote", "decided", "live"], "rejoin");
    assertSameWeek(input.weekId, week.id);
    const db = c.env.DB;
    const now = c.var.now;
    if (me!.status === "skipped" && phase === "live") {
      await db
        .prepare("UPDATE participation SET status = 'in', joined_at = ?3 WHERE user_id = ?1 AND week_id = ?2 AND status = 'skipped'")
        .bind(c.var.user.id, week.id, now)
        .run();
    } else if (me!.status === "skipped") {
      await db.prepare("UPDATE participation SET status = 'in' WHERE user_id = ? AND week_id = ? AND status = 'skipped'")
        .bind(c.var.user.id, week.id)
        .run();
    } else if (me!.status === "left" && phase === "live") {
      await db
        .prepare(
          `UPDATE participation SET status = 'in', away_ms = away_ms + MAX(0, ?3 - left_at), left_at = NULL, came_back_at = ?3
            WHERE user_id = ?1 AND week_id = ?2 AND status = 'left'`,
        )
        .bind(c.var.user.id, week.id, now)
        .run();
    }
    return c.json({ me: await currentMe(c) });
  });

  /**
   * The week a report from the phone is about, for reports that may arrive
   * late (leave, reaches): the week named by weekId, which may be a past
   * week, or the current week. Its window must have started.
   */
  const reportWeek = async (c: C, weekId: string | undefined, action: string) => {
    const db = c.env.DB;
    const now = c.var.now;
    const cur = await loadCurrent(db, c.var.user, now);
    let week: Week;
    let me: Participation | null;
    if (cur && (!weekId || weekId === cur.week.id)) {
      ({ week, me } = cur);
    } else if (weekId) {
      const named = await getWeek(db, weekId);
      if (!named) throw notFound("week_not_found", "No such week.");
      week = await decideIfDue(db, named, now);
      me = await getParticipation(db, c.var.user.id, week.id);
    } else {
      throw conflict("no_week", "There is no current week.");
    }
    if (week.startsAt === null || week.endsAt === null || now < week.startsAt) {
      throw conflict("phase_closed", `You can ${action} only once the window has started.`, {
        phase: phaseAt(week, now),
        allowed: ["live", "ended", "told"],
      });
    }
    return { week: { ...week, startsAt: week.startsAt, endsAt: week.endsAt }, me };
  };

  const reportReply = async (c: C, week: Week, extra: Record<string, unknown> = {}) => {
    const now = c.var.now;
    const p = await getParticipation(c.env.DB, c.var.user.id, week.id);
    return c.json({ weekId: week.id, ...extra, me: meView(p, phaseAt(week, now), isBoardOpen(week, now)) });
  };

  /**
   * Leave early. The phone records the time of the leave and may report it
   * late: the shield extension that handles "Leave quiet hours" runs with the
   * app closed and cannot reach the network, so the report waits until the
   * app next runs, which can be after endsAt or even after toldAt
   * (docs/LOCK-NOTES.md, limit 7). So:
   *   - weekId names the week (the phone has it as the scheduled window's id);
   *     without it, the current week.
   *   - leftAt is the time the phone recorded. It is required once the window
   *     is over; during `live` it defaults to now.
   *   - A leftAt ahead of the server's clock is read as now.
   *   - A leftAt more than CLOCK_SKEW_MS before startsAt is rejected (it is
   *     probably from another week); less than that is read as startsAt.
   *   - A leftAt at or after endsAt is not an early leave: nothing changes.
   *   - A leftAt before the person last came back (rejoin after a leave) is
   *     ignored: that leave was recorded before they came back, and coming
   *     back closed it. Nothing changes.
   *   - If a leave is already recorded, the earlier of the two times is kept.
   */
  app.post("/v1/me/leave", signedIn, async (c) => {
    const input = await body(c, z.object({ leftAt: instant.optional(), ...weekRef }));
    const now = c.var.now;
    const { week, me } = await reportWeek(c, input.weekId, "leave");
    if (!me) throw conflict("not_in", "You were not part of this week's window.");
    if (me.status === "skipped") throw conflict("not_in", "You skipped this one, so there is nothing to leave.");
    if (input.leftAt === undefined && now >= week.endsAt) {
      throw badRequest("left_at_required", "After the window, a leave must say when it happened (leftAt).");
    }
    const reported = Math.min(input.leftAt ?? now, now);
    const window = { startsAt: iso(week.startsAt), endsAt: iso(week.endsAt) };
    if (reported < week.startsAt - CLOCK_SKEW_MS) {
      throw badRequest("left_at_invalid", "leftAt is before this week's window started. Is it from another week?", window);
    }
    if (reported >= week.endsAt) return reportReply(c, week, { recorded: false, reason: "after_window" });
    if (me.cameBackAt !== null && reported < me.cameBackAt) {
      return reportReply(c, week, { recorded: false, reason: "before_rejoin" });
    }

    const leftAt = Math.max(reported, week.startsAt, me.joinedAt);
    const res = await c.env.DB.prepare(
      `UPDATE participation SET status = 'left', left_at = ?1
        WHERE user_id = ?2 AND week_id = ?3 AND (came_back_at IS NULL OR came_back_at <= ?1)
          AND (status = 'in' OR (status = 'left' AND left_at > ?1))`,
    )
      .bind(leftAt, c.var.user.id, week.id)
      .run();
    return reportReply(c, week, res.meta.changes === 1 ? { recorded: true } : { recorded: false, reason: "already_left_earlier" });
  });

  /**
   * Reaches: the phone reports its running total for the week. It is an
   * approximation (the phone counts shield draws; docs/LOCK-NOTES.md, "Reach
   * counter"), stored as reported. The server keeps the largest total it has
   * seen, so retries and duplicates are safe. Like a leave, it may arrive
   * late and carry weekId.
   */
  app.post("/v1/me/reaches", signedIn, async (c) => {
    const input = await body(c, z.object({ approxReaches: z.number().int().min(0).max(100_000), ...weekRef }));
    const { week, me } = await reportWeek(c, input.weekId, "report reaches");
    if (!me || (me.status !== "in" && me.status !== "left")) {
      throw conflict("not_in", "Only people who were in this week's window report reaches.");
    }
    await c.env.DB.prepare("UPDATE participation SET approx_reaches = MAX(approx_reaches, ?) WHERE user_id = ? AND week_id = ?")
      .bind(input.approxReaches, c.var.user.id, week.id)
      .run();
    return reportReply(c, week);
  });

  // ---------------------------------------------------------- board

  /**
   * The open board as the caller sees it, newest first: posts that passed the
   * editing check, plus the caller's own pending ones. Taken-down posts are
   * never shown (migrations/0004).
   */
  const openBoard = async (c: C, week: Week, limit: number, before: number | null) => {
    const { results } = await c.env.DB
      .prepare(
        `SELECT id, text, place, created_at, moderation, user_id = ?1 AS mine FROM board_posts
          WHERE week_id = ?2 AND created_at < ?3 AND taken_down = 0
            AND (moderation = 'ok' OR (moderation = 'pending' AND user_id = ?1))
          ORDER BY created_at DESC, id DESC LIMIT ?4`,
      )
      .bind(c.var.user.id, week.id, before ?? Number.MAX_SAFE_INTEGER, limit)
      .all<{ id: string; text: string; place: string; created_at: number; moderation: string; mine: number }>();
    return {
      open: true,
      opensAt: isoOrNull(boardOpensAt(week)),
      closesAt: isoOrNull(week.endsAt),
      posts: results.map((p) => ({
        id: p.id,
        text: p.text,
        place: p.place,
        createdAt: iso(p.created_at),
        mine: p.mine === 1,
        pending: p.moderation === "pending",
      })),
    };
  };
  const BOARD_PAGE = 50;

  app.get("/v1/board", signedIn, async (c) => {
    const db = c.env.DB;
    const cur = await loadCurrent(db, c.var.user, c.var.now);
    if (!cur) return c.json({ open: false, opensAt: null, closesAt: null, posts: [] });
    const { week } = cur;
    const open = isBoardOpen(week, c.var.now);
    const window = { opensAt: isoOrNull(boardOpensAt(week)), closesAt: isoOrNull(week.endsAt) };
    if (!open) return c.json({ open: false, ...window, posts: [] });

    const limit = Math.min(Math.max(Number(c.req.query("limit") ?? BOARD_PAGE) || BOARD_PAGE, 1), 200);
    const beforeParam = c.req.query("before");
    const before = beforeParam ? parseInstant(beforeParam) : null;
    if (beforeParam && before === null) throw badRequest("invalid_request", "before must be an ISO 8601 time.");
    return c.json(await openBoard(c, week, limit, before));
  });

  /**
   * Take down your own post, while the board is open. The post is hidden
   * from everyone from then on but still counts toward MAX_POSTS_PER_WEEK
   * (migrations/0004). Someone else's post and an unknown id both answer
   * 404, so post ids cannot be probed. A second call changes nothing.
   * Responds with the board's first page, as GET /v1/board.
   */
  app.delete("/v1/board/:id", signedIn, async (c) => {
    const db = c.env.DB;
    const now = c.var.now;
    const cur = await loadCurrent(db, c.var.user, now);
    if (!cur) throw conflict("no_week", "There is no current week.");
    const { week } = cur;
    if (!isBoardOpen(week, now)) throw conflict("board_closed", "The board is not open right now.");
    const key = [c.req.param("id"), week.id, c.var.user.id] as const;
    const own = await db.prepare("SELECT 1 FROM board_posts WHERE id = ? AND week_id = ? AND user_id = ?").bind(...key).first();
    if (!own) throw notFound("post_not_found", "No post of yours with that id on this week's board.");
    await db.prepare("UPDATE board_posts SET taken_down = 1 WHERE id = ? AND week_id = ? AND user_id = ?").bind(...key).run();
    return c.json(await openBoard(c, week, BOARD_PAGE, null));
  });

  app.post("/v1/board", signedIn, async (c) => {
    const input = await body(c, z.object({ text: oneLine(POST_TEXT_MAX), place: oneLine(PLACE_MAX), ...weekRef }));
    const db = c.env.DB;
    const now = c.var.now;
    const cur = await loadCurrent(db, c.var.user, now);
    if (!cur) throw conflict("no_week", "There is no current week.");
    const { week, me } = cur;
    assertSameWeek(input.weekId, week.id);
    if (!isBoardOpen(week, now)) throw conflict("board_closed", "The board is not open right now.");
    if (me?.status !== "in") throw conflict("not_in", "Only people who are in can post on the board.");
    const mine = await db
      .prepare("SELECT COUNT(*) AS n FROM board_posts WHERE week_id = ? AND user_id = ?")
      .bind(week.id, c.var.user.id)
      .first<{ n: number }>();
    if (Number(mine?.n ?? 0) >= MAX_POSTS_PER_WEEK) {
      throw tooMany("post_limit", `You can post at most ${MAX_POSTS_PER_WEEK} times a week.`);
    }

    const check = await checkText(ai(c), `${input.text}\nPlace: ${input.place}`, "board_post");
    if (check.state === "rejected") throw notShown(check.reason);
    const id = newId("po");
    await db
      .prepare(
        `INSERT INTO board_posts (id, week_id, user_id, text, place, created_at, moderation, moderation_note)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .bind(id, week.id, c.var.user.id, input.text, input.place, now, check.state, check.state === "pending" ? check.note : null)
      .run();
    return c.json(
      {
        post: { id, text: input.text, place: input.place, createdAt: iso(now), mine: true, pending: check.state === "pending" },
        shown: check.state === "ok",
      },
      201,
    );
  });

  // ---------------------------------------------------------- lines

  /**
   * One optional line on what you did, during `ended`. The line is stored
   * with no link to the writer: the lines row has no user and no time, and
   * participation only gets wrote_line = 1 (so nobody writes twice).
   */
  app.post("/v1/lines", signedIn, async (c) => {
    const input = await body(c, z.object({ text: oneLine(LINE_MAX), ...weekRef }));
    const db = c.env.DB;
    const { week, me } = await currentIn(c, ["ended"], "write your line");
    assertSameWeek(input.weekId, week.id);
    if (!me || (me.status !== "in" && me.status !== "left")) {
      throw conflict("not_in", "Only people who were in this week's window can write a line.");
    }
    if (me.wroteLine) throw conflict("already_wrote", "You have already written your line for this week.");

    const check = await checkText(ai(c), input.text, "line");
    if (check.state === "rejected") throw notShown(check.reason);
    const userId = c.var.user.id;
    // One transaction: the line goes in only if this person has not written one, then the flag is set.
    const [inserted] = await db.batch([
      db
        .prepare(
          `INSERT INTO lines (id, week_id, text, moderation)
           SELECT ?, ?, ?, ? WHERE EXISTS (
             SELECT 1 FROM participation WHERE user_id = ? AND week_id = ? AND wrote_line = 0 AND status IN ('in', 'left'))`,
        )
        .bind(newId("ln"), week.id, input.text, check.state, userId, week.id),
      db
        .prepare("UPDATE participation SET wrote_line = 1 WHERE user_id = ? AND week_id = ? AND status IN ('in', 'left')")
        .bind(userId, week.id),
    ]);
    if (inserted?.meta.changes !== 1) throw conflict("already_wrote", "You have already written your line for this week.");
    // Deliberately no line id in the response: nothing ties this person to the row.
    return c.json({ ok: true, shown: check.state === "ok", pending: check.state === "pending" }, 201);
  });

  // ---------------------------------------------------------- recaps

  app.get("/v1/weeks", signedIn, async (c) => {
    const now = c.var.now;
    const weeks = (await listWeeks(c.env.DB)).filter((w) => w.toldAt <= now);
    const ids = new Set(
      (await c.env.DB.prepare("SELECT week_id FROM recaps").all<{ week_id: string }>()).results.map((r) => r.week_id),
    );
    return c.json({
      weeks: weeks.map((w) => ({
        id: w.id,
        startsAt: w.startsAt === null ? null : iso(w.startsAt),
        endsAt: w.endsAt === null ? null : iso(w.endsAt),
        toldAt: iso(w.toldAt),
        hasRecap: ids.has(w.id),
        isDemo: w.isDemo,
      })),
    });
  });

  app.get("/v1/weeks/:id/recap", signedIn, async (c) => {
    const week = await getWeek(c.env.DB, c.req.param("id") ?? "");
    if (!week) throw notFound("week_not_found", "No such week.");
    if (c.var.now < week.toldAt) throw conflict("not_told_yet", "This week's hour has not been told back yet.", { toldAt: iso(week.toldAt) });
    const recap = await readRecap(c.env.DB, week.id);
    if (!recap) throw notFound("recap_not_ready", "The recap for this week has not been written yet.");
    return c.json(recap);
  });

  // ---------------------------------------------------------- admin

  const admin = async (c: C, next: () => Promise<void>) => {
    const secret = c.env.ADMIN_SECRET;
    if (!secret) throw unavailable("admin_not_configured", "ADMIN_SECRET is not set, so admin calls are disabled.");
    const given = c.req.header("X-Admin-Secret") ?? "";
    if (!(await safeEqual(given, secret))) throw forbidden("admin_forbidden", "Missing or wrong X-Admin-Secret.");
    await next();
  };

  const adminWeekView = async (c: C, weekId: string) => {
    const db = c.env.DB;
    const week = await requireWeek(db, weekId);
    const now = c.var.now;
    const phase = phaseAt(week, now);
    const options = (
      await db
        .prepare(
          `SELECT o.*, (SELECT COUNT(*) FROM votes v WHERE v.option_id = o.id) AS votes FROM options o WHERE week_id = ? ORDER BY position`,
        )
        .bind(week.id)
        .all<Record<string, unknown>>()
    ).results.map((o) => ({
      ...optionView({
        id: String(o.id),
        weekId: week.id,
        position: Number(o.position),
        startsAt: Number(o.starts_at),
        endsAt: Number(o.ends_at),
        reason: String(o.reason),
        source: o.source as "admin",
        votes: Number(o.votes),
      }),
      source: String(o.source),
    }));
    const pending = await db
      .prepare(
        `SELECT (SELECT COUNT(*) FROM board_posts WHERE week_id = ?1 AND moderation = 'pending' AND taken_down = 0) AS posts,
                (SELECT COUNT(*) FROM lines WHERE week_id = ?1 AND moderation = 'pending') AS lines,
                (SELECT COUNT(*) FROM lines WHERE week_id = ?1) AS all_lines`,
      )
      .bind(week.id)
      .first<{ posts: number; lines: number; all_lines: number }>();
    return {
      week: weekView(week, await nextWeekVoteOpensAt(db, week.voteOpensAt)),
      phase,
      winningOptionId: week.winningOptionId,
      options,
      numbers: await numbersFor(db, week, phase),
      lines: Number(pending?.all_lines ?? 0),
      pendingChecks: { posts: Number(pending?.posts ?? 0), lines: Number(pending?.lines ?? 0) },
      hasRecap: (await db.prepare("SELECT 1 FROM recaps WHERE week_id = ?").bind(week.id).first()) !== null,
    };
  };

  app.use("/v1/admin/*", admin);

  app.get("/v1/admin/weeks", async (c) => {
    const weeks = await listWeeks(c.env.DB);
    return c.json({ weeks: weeks.map((w) => ({ ...weekView(w, null), phase: phaseAt(w, c.var.now) })) });
  });

  app.post("/v1/admin/weeks", async (c) => {
    const input = await body(c, z.object({ voteOpensAt: instant, voteClosesAt: instant, toldAt: instant }));
    const week = await createWeek(c.env.DB, input, c.var.now);
    return c.json(await adminWeekView(c, week.id), 201);
  });

  app.get("/v1/admin/weeks/:id", async (c) => c.json(await adminWeekView(c, c.req.param("id"))));

  // Reasons are also checked in setOptions (one or two sentences), the same check as AI proposals.
  const optionInput = z.object({ startsAt: instant, endsAt: instant, reason: oneLine(MAX_REASON) });

  app.put("/v1/admin/weeks/:id/options", async (c) => {
    const input = await body(c, z.object({ options: z.array(optionInput).min(1).max(5) }));
    const week = await requireWeek(c.env.DB, c.req.param("id"));
    await setOptions(c.env.DB, week, input.options, "admin");
    return c.json(await adminWeekView(c, week.id));
  });

  app.post("/v1/admin/weeks/:id/proposals", async (c) => {
    const input = await body(c, z.object({ campusWeek: CampusWeekSchema, apply: z.boolean().default(false) }));
    const week = await requireWeek(c.env.DB, c.req.param("id"));
    const provider = requireAi(c);
    const out = await proposeWindows(provider, week, input.campusWeek);
    if (!out.proposals) {
      throw new ApiError(502, "ai_invalid_output", "The model's proposals failed validation on every attempt.", {
        attempts: out.attempts,
        rejected: out.rejected,
      });
    }
    if (input.apply) {
      await setOptions(
        c.env.DB,
        week,
        out.proposals.map((p) => ({ startsAt: Date.parse(p.startsAt), endsAt: Date.parse(p.endsAt), reason: p.reason })),
        "ai",
      );
    }
    return c.json({
      proposals: out.proposals,
      applied: input.apply,
      attempts: out.attempts,
      rejected: out.rejected,
      model: provider.models.proposals,
    });
  });

  app.post("/v1/admin/weeks/:id/close-vote", async (c) => {
    const week = await requireWeek(c.env.DB, c.req.param("id"));
    await closeVote(c.env.DB, week, c.var.now);
    return c.json(await adminWeekView(c, week.id));
  });

  app.post("/v1/admin/weeks/:id/timeline", async (c) => {
    const input = await body(
      c,
      z.union([z.object({ jumpTo: z.enum(PHASES) }).strict(), z.object({ shiftSeconds: z.number().int() }).strict()]),
    );
    const week = await requireWeek(c.env.DB, c.req.param("id"));
    await moveWeek(c.env.DB, week, c.var.now, input);
    return c.json(await adminWeekView(c, week.id));
  });

  app.post("/v1/admin/weeks/:id/recap", async (c) => {
    const db = c.env.DB;
    const week = await requireWeek(db, c.req.param("id"));
    const phase = phaseAt(week, c.var.now);
    if (phase !== "ended" && phase !== "told") {
      throw conflict("phase_closed", "A recap can be written once the window has ended.", { phase });
    }
    const provider = requireAi(c);
    const recap = await generateAndStoreRecap(db, provider, week, c.var.now);
    return c.json(recap, 201);
  });

  app.post("/v1/admin/weeks/:id/moderate", async (c) => {
    const week = await requireWeek(c.env.DB, c.req.param("id"));
    const provider = requireAi(c);
    return c.json(await moderatePending(c.env.DB, provider, week.id));
  });

  app.post("/v1/admin/demo/seed", async (c) => {
    const { step } = await body(c, z.object({ step: z.enum(["week", "decided", "live", "ended"]) }));
    return c.json(await seedDemo(c.env.DB, step, c.var.now), 201);
  });

  app.delete("/v1/admin/demo", async (c) => c.json(await removeDemo(c.env.DB)));

  return app;
}
