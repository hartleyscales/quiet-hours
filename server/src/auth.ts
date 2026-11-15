/**
 * Sign-in with a USC email by one-time code, and bearer sessions.
 *
 * Sending the code goes through CodeSender. There is no email service yet:
 *   - "email" (production): UnconfiguredEmailSender, which fails with a clear
 *     503 email_not_configured until a real sender is written.
 *   - "dev-response" (local development only): the code is returned in the
 *     API response as `devCode`, next to a warning. readConfig() refuses to
 *     run this mode unless ENVIRONMENT is "development".
 */
import { ApiError, badRequest, forbidden, tooMany, unauthorized, unavailable } from "./errors";
import { newId, newSessionToken, newSigninCode, safeEqual, sha256Hex } from "./ids";

export const CODE_TTL_MS = 10 * 60_000;
export const MAX_CODE_ATTEMPTS = 5;
export const MAX_CODES_PER_HOUR = 5;
export const SESSION_TTL_MS = 180 * 24 * 3600_000;

export interface CodeSender {
  readonly mode: "email" | "dev-response";
  send(email: string, code: string): Promise<void>;
}

/** Production placeholder: there is no email service yet. */
export class UnconfiguredEmailSender implements CodeSender {
  readonly mode = "email" as const;
  async send(): Promise<void> {
    throw unavailable(
      "email_not_configured",
      "Sign-in codes are sent by email, and no email service is configured yet. See docs/SERVER-NOTES.md.",
    );
  }
}

/** Development only: nothing is sent; the route returns the code in its response. */
export class DevResponseSender implements CodeSender {
  readonly mode = "dev-response" as const;
  async send(): Promise<void> {}
}

export const DEV_CODE_WARNING =
  "INSECURE DEVELOPMENT MODE: the sign-in code is returned in this response instead of being emailed. This must never run in production.";

export interface User {
  id: string;
  email: string;
  createdAt: number;
}

/** Lower-cases and trims; accepts only addresses that end in "@usc.edu". */
export function normalizeUscEmail(raw: unknown): string {
  if (typeof raw !== "string") throw badRequest("invalid_email", "email must be a string.");
  const email = raw.trim().toLowerCase();
  if (!/^[^\s@]+@usc\.edu$/.test(email) || email.length > 254) {
    throw badRequest("email_not_usc", "Use your USC email address (it must end in @usc.edu).");
  }
  return email;
}

const codeHash = (challengeId: string, code: string) => sha256Hex(`${challengeId}:${code}`);

export async function startSignin(db: D1Database, sender: CodeSender, rawEmail: unknown, now: number) {
  const email = normalizeUscEmail(rawEmail);

  const demo = await db.prepare("SELECT 1 FROM users WHERE email = ? AND is_demo = 1").bind(email).first();
  if (demo) throw forbidden("demo_account", "That address belongs to a simulated demo participant.");

  const recent = await db
    .prepare("SELECT COUNT(*) AS n FROM signin_challenges WHERE email = ? AND created_at > ?")
    .bind(email, now - 3600_000)
    .first<{ n: number }>();
  if (Number(recent?.n ?? 0) >= MAX_CODES_PER_HOUR) {
    throw tooMany("too_many_codes", "Too many sign-in codes for this address in the last hour. Try again later.");
  }

  const id = newId("ch");
  const code = newSigninCode();
  const expiresAt = now + CODE_TTL_MS;
  await db
    .prepare("INSERT INTO signin_challenges (id, email, code_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?)")
    .bind(id, email, await codeHash(id, code), now, expiresAt)
    .run();

  try {
    await sender.send(email, code);
  } catch (err) {
    await db.prepare("DELETE FROM signin_challenges WHERE id = ?").bind(id).run();
    throw err;
  }

  return { email, expiresAt, code };
}

export async function verifySignin(db: D1Database, rawEmail: unknown, rawCode: unknown, now: number) {
  const email = normalizeUscEmail(rawEmail);
  const code = typeof rawCode === "string" ? rawCode.trim() : "";
  if (!/^\d{6}$/.test(code)) throw badRequest("code_invalid", "That code is not right, or it has expired.");

  const ch = await db
    .prepare(
      `SELECT id, code_hash, attempts FROM signin_challenges
        WHERE email = ? AND consumed_at IS NULL AND expires_at > ?
        ORDER BY created_at DESC LIMIT 1`,
    )
    .bind(email, now)
    .first<{ id: string; code_hash: string; attempts: number }>();
  if (!ch) throw badRequest("code_invalid", "That code is not right, or it has expired.");
  if (ch.attempts >= MAX_CODE_ATTEMPTS) {
    throw tooMany("too_many_attempts", "Too many wrong codes. Ask for a new one.");
  }
  const ok = await safeEqual(await codeHash(ch.id, code), ch.code_hash);
  if (!ok) {
    await db.prepare("UPDATE signin_challenges SET attempts = attempts + 1 WHERE id = ?").bind(ch.id).run();
    throw badRequest("code_invalid", "That code is not right, or it has expired.");
  }
  const consumed = await db
    .prepare("UPDATE signin_challenges SET consumed_at = ? WHERE id = ? AND consumed_at IS NULL")
    .bind(now, ch.id)
    .run();
  if (consumed.meta.changes !== 1) throw badRequest("code_invalid", "That code is not right, or it has expired.");

  await db
    .prepare("INSERT OR IGNORE INTO users (id, email, created_at) VALUES (?, ?, ?)")
    .bind(newId("us"), email, now)
    .run();
  const user = (await db.prepare("SELECT id, email, created_at FROM users WHERE email = ?").bind(email).first<{
    id: string;
    email: string;
    created_at: number;
  }>())!;

  const token = newSessionToken();
  const expiresAt = now + SESSION_TTL_MS;
  await db
    .prepare("INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)")
    .bind(await sha256Hex(token), user.id, now, expiresAt)
    .run();

  return { token, expiresAt, user: { id: user.id, email: user.email, createdAt: user.created_at } };
}

export function bearerToken(header: string | undefined): string | null {
  const m = header ? /^Bearer\s+(\S+)$/i.exec(header) : null;
  return m?.[1] ?? null;
}

export async function authenticate(db: D1Database, header: string | undefined, now: number): Promise<User> {
  const token = bearerToken(header);
  if (!token) throw unauthorized();
  const r = await db
    .prepare(
      `SELECT u.id, u.email, u.created_at FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ? AND s.expires_at > ?`,
    )
    .bind(await sha256Hex(token), now)
    .first<{ id: string; email: string; created_at: number }>();
  if (!r) throw unauthorized("That session token is not valid or has expired. Sign in again.");
  return { id: r.id, email: r.email, createdAt: r.created_at };
}

export async function signOut(db: D1Database, header: string | undefined): Promise<void> {
  const token = bearerToken(header);
  if (!token) throw unauthorized();
  await db.prepare("DELETE FROM sessions WHERE token_hash = ?").bind(await sha256Hex(token)).run();
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}
