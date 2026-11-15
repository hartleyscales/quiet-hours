import { createExecutionContext, env } from "cloudflare:test";
import { createApp } from "../src/app";
import type {
  AiProvider,
  DraftHighlight,
  DraftProposal,
  LineForRecap,
  ModerationVerdict,
  ProposalRequest,
} from "../src/ai/types";
import { DEV_SIGNIN_CODES_IN_RESPONSE, type Env } from "../src/config";
import { newId } from "../src/ids";
import { TOLD_AFTER_END_MS } from "../src/phase";

export const ADMIN = "test-admin-secret";
export const MIN = 60_000;
export const HOUR = 3_600_000;
export const DAY = 86_400_000;

/** A test double for the AI. Each job can be replaced per test. */
export class StubAi implements AiProvider {
  readonly id = "test-stub";
  readonly models = { proposals: "stub-strong", recap: "stub-strong", moderation: "stub-fast", recapCheck: "stub-fast" };
  calls = { moderate: 0, propose: 0, recap: 0, confirm: 0 };
  moderateImpl = async (text: string): Promise<ModerationVerdict> =>
    /BAD/.test(text) ? { show: false, reason: "abusive" } : /Alice/.test(text) ? { show: false, reason: "names_or_targets_person" } : { show: true, reason: "ok" };
  proposeImpl = async (_req: ProposalRequest, _feedback: string[]): Promise<DraftProposal[]> => [];
  recapImpl = async (_lines: LineForRecap[], _feedback: string[]): Promise<DraftHighlight[]> => [];
  confirmImpl = async (_claim: string, lines: LineForRecap[]): Promise<string[]> => lines.map((l) => l.id);

  moderate(text: string) {
    this.calls.moderate++;
    return this.moderateImpl(text);
  }
  proposeWindows(req: ProposalRequest, feedback: string[]) {
    this.calls.propose++;
    return this.proposeImpl(req, feedback);
  }
  draftRecap(lines: LineForRecap[], feedback: string[]) {
    this.calls.recap++;
    return this.recapImpl(lines, feedback);
  }
  confirmGroup(claim: string, lines: LineForRecap[]) {
    this.calls.confirm++;
    return this.confirmImpl(claim, lines);
  }
}

export interface Res<T = any> {
  status: number;
  json: T;
  headers: Headers;
}

const TABLES = ["recaps", "lines", "board_posts", "participation", "votes", "sessions", "signin_challenges"];

/** Empties every table so each test starts clean. */
export async function wipe(db: D1Database) {
  await db.batch([
    ...TABLES.map((t) => db.prepare(`DELETE FROM ${t}`)),
    db.prepare("UPDATE weeks SET winning_option_id = NULL, starts_at = NULL, ends_at = NULL"),
    db.prepare("DELETE FROM options"),
    db.prepare("DELETE FROM weeks"),
    db.prepare("DELETE FROM users"),
  ]);
}

export class Harness {
  now: number;
  ai: StubAi | null;
  env: Env;
  private app: ReturnType<typeof createApp>;

  constructor(opts: { now: number; ai?: StubAi | null; env?: Partial<Env> }) {
    this.now = opts.now;
    this.ai = opts.ai === undefined ? new StubAi() : opts.ai;
    this.env = {
      ...(env as unknown as Env),
      ENVIRONMENT: "development",
      SIGNIN_CODE_DELIVERY: DEV_SIGNIN_CODES_IN_RESPONSE,
      AI_MODE: "anthropic",
      ADMIN_SECRET: ADMIN,
      ANTHROPIC_API_KEY: undefined,
      ...opts.env,
    };
    this.app = createApp({ now: () => this.now, ai: () => this.ai });
  }

  get db(): D1Database {
    return this.env.DB;
  }

  async req<T = any>(
    method: string,
    path: string,
    opts: { body?: unknown; token?: string; admin?: boolean | string } = {},
  ): Promise<Res<T>> {
    const headers: Record<string, string> = {};
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (opts.token) headers.Authorization = `Bearer ${opts.token}`;
    if (opts.admin) headers["X-Admin-Secret"] = opts.admin === true ? ADMIN : opts.admin;
    const res = await this.app.fetch(
      new Request(`http://test${path}`, {
        method,
        headers,
        body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      }),
      this.env,
      createExecutionContext(),
    );
    const text = await res.text();
    return { status: res.status, json: text ? JSON.parse(text) : null, headers: res.headers };
  }

  async signIn(email: string): Promise<string> {
    const start = await this.req("POST", "/v1/auth/start", { body: { email } });
    if (start.status !== 200) throw new Error(`start failed: ${JSON.stringify(start.json)}`);
    const verify = await this.req("POST", "/v1/auth/verify", { body: { email, code: start.json.devCode } });
    if (verify.status !== 200) throw new Error(`verify failed: ${JSON.stringify(verify.json)}`);
    return verify.json.token;
  }

  async state(token: string) {
    const r = await this.req("GET", "/v1/state", { token });
    if (r.status !== 200) throw new Error(`state failed: ${JSON.stringify(r.json)}`);
    return r.json;
  }

  /**
   * Inserts a week directly with exact timestamps, plus options. If `winner`
   * is given (an option index), the week is already decided on that option.
   */
  async week(t: {
    voteOpensAt: number;
    voteClosesAt: number;
    toldAt: number;
    options?: { startsAt: number; endsAt: number; reason?: string }[];
    winner?: number;
  }) {
    const id = newId("wk");
    const options = (t.options ?? []).map((o, i) => ({ ...o, id: newId("op"), position: i + 1 }));
    await this.db.batch([
      this.db
        .prepare("INSERT INTO weeks (id, vote_opens_at, vote_closes_at, told_at, created_at) VALUES (?, ?, ?, ?, ?)")
        .bind(id, t.voteOpensAt, t.voteClosesAt, t.toldAt, t.voteOpensAt),
      ...options.map((o) =>
        this.db
          .prepare("INSERT INTO options (id, week_id, position, starts_at, ends_at, reason, source) VALUES (?, ?, ?, ?, ?, ?, 'admin')")
          .bind(o.id, id, o.position, o.startsAt, o.endsAt, o.reason ?? `Option ${o.position}.`),
      ),
    ]);
    if (t.winner !== undefined) {
      // As the decision does (db.ts, decideIfDue): toldAt is 15 minutes after the window ends.
      const w = options[t.winner]!;
      await this.db
        .prepare("UPDATE weeks SET winning_option_id = ?, starts_at = ?, ends_at = ?, told_at = ? WHERE id = ?")
        .bind(w.id, w.startsAt, w.endsAt, w.endsAt + TOLD_AFTER_END_MS, id)
        .run();
    }
    return { id, optionIds: options.map((o) => o.id) };
  }
}

/**
 * A standard week used across tests (all times exact):
 *   vote opens  2026-11-16 09:00 PST (17:00Z)
 *   vote closes 2026-11-17 17:00 PST
 *   window      2026-11-18 21:00-22:30 PST (option 1) / 19:00-20:00 (option 2)
 *   told        2026-11-18 22:45 PST, 15 minutes after option 1 ends. Until
 *               the decision it is also the week's bound: options end at
 *               least 15 minutes before it.
 */
export const T = {
  voteOpensAt: Date.parse("2026-11-16T09:00:00-08:00"),
  voteClosesAt: Date.parse("2026-11-17T17:00:00-08:00"),
  startsAt: Date.parse("2026-11-18T21:00:00-08:00"),
  endsAt: Date.parse("2026-11-18T22:30:00-08:00"),
  toldAt: Date.parse("2026-11-18T22:45:00-08:00"),
  laMidnightOfStart: Date.parse("2026-11-18T00:00:00-08:00"),
  option2Start: Date.parse("2026-11-18T19:00:00-08:00"),
  option2End: Date.parse("2026-11-18T20:00:00-08:00"),
};

export function standardWeek(h: Harness, decided = false) {
  return h.week({
    voteOpensAt: T.voteOpensAt,
    voteClosesAt: T.voteClosesAt,
    toldAt: T.toldAt,
    options: [
      { startsAt: T.startsAt, endsAt: T.endsAt },
      { startsAt: T.option2Start, endsAt: T.option2End },
    ],
    winner: decided ? 0 : undefined,
  });
}
