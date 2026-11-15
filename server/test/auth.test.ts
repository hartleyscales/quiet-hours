import { beforeEach, describe, expect, it } from "vitest";
import { DEV_FAKE_AI, DEV_SIGNIN_CODES_IN_RESPONSE } from "../src/config";
import { Harness, MIN, T, wipe } from "./helpers";
import { env } from "cloudflare:test";

beforeEach(() => wipe(env.DB));

describe("sign-in with a USC email by one-time code", () => {
  it("accepts only addresses that end in @usc.edu", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    for (const email of ["a@gmail.com", "a@usc.edu.evil.com", "a@alumni.usc.edu", "@usc.edu", "a b@usc.edu", "a@b@usc.edu"]) {
      const r = await h.req("POST", "/v1/auth/start", { body: { email } });
      expect(r.status, email).toBe(400);
      expect(r.json.error.code, email).toBe("email_not_usc");
    }
    const ok = await h.req("POST", "/v1/auth/start", { body: { email: "  Tommy.Trojan@USC.EDU " } });
    expect(ok.status).toBe(200);
    expect(ok.json.email).toBe("tommy.trojan@usc.edu");
  });

  it("returns a session token for the right code, once", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    const start = await h.req("POST", "/v1/auth/start", { body: { email: "a@usc.edu" } });
    expect(start.json.devCode).toMatch(/^\d{6}$/);
    const v = await h.req("POST", "/v1/auth/verify", { body: { email: "a@usc.edu", code: start.json.devCode } });
    expect(v.status).toBe(200);
    expect(v.json.user.email).toBe("a@usc.edu");
    expect((await h.req("GET", "/v1/state", { token: v.json.token })).status).toBe(200);
    const again = await h.req("POST", "/v1/auth/verify", { body: { email: "a@usc.edu", code: start.json.devCode } });
    expect(again.status).toBe(400);
  });

  it("stores only hashes of codes and tokens", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    const start = await h.req("POST", "/v1/auth/start", { body: { email: "a@usc.edu" } });
    const v = await h.req("POST", "/v1/auth/verify", { body: { email: "a@usc.edu", code: start.json.devCode } });
    const ch = await h.db.prepare("SELECT code_hash FROM signin_challenges").first<{ code_hash: string }>();
    const s = await h.db.prepare("SELECT token_hash FROM sessions").first<{ token_hash: string }>();
    expect(ch!.code_hash).not.toContain(start.json.devCode);
    expect(s!.token_hash).not.toBe(v.json.token);
  });

  it("locks a code after 5 wrong tries, and expires codes after 10 minutes", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    const start = await h.req("POST", "/v1/auth/start", { body: { email: "a@usc.edu" } });
    const wrong = start.json.devCode === "000000" ? "111111" : "000000";
    for (let i = 0; i < 5; i++) {
      expect((await h.req("POST", "/v1/auth/verify", { body: { email: "a@usc.edu", code: wrong } })).status).toBe(400);
    }
    const locked = await h.req("POST", "/v1/auth/verify", { body: { email: "a@usc.edu", code: start.json.devCode } });
    expect(locked.status).toBe(429);

    const s2 = await h.req("POST", "/v1/auth/start", { body: { email: "b@usc.edu" } });
    h.now += 10 * MIN;
    const expired = await h.req("POST", "/v1/auth/verify", { body: { email: "b@usc.edu", code: s2.json.devCode } });
    expect(expired.status).toBe(400);
  });

  it("limits codes per address per hour", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    for (let i = 0; i < 5; i++) expect((await h.req("POST", "/v1/auth/start", { body: { email: "a@usc.edu" } })).status).toBe(200);
    expect((await h.req("POST", "/v1/auth/start", { body: { email: "a@usc.edu" } })).status).toBe(429);
  });

  it("rejects missing or bad tokens, and sign-out ends the session", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    expect((await h.req("GET", "/v1/state")).status).toBe(401);
    expect((await h.req("GET", "/v1/state", { token: "nope" })).status).toBe(401);
    const token = await h.signIn("a@usc.edu");
    expect((await h.req("POST", "/v1/auth/sign-out", { token })).status).toBe(200);
    expect((await h.req("GET", "/v1/state", { token })).status).toBe(401);
  });
});

describe("the development code mode cannot pass for production", () => {
  it("development mode returns the code, a warning, and a header on every response", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    const r = await h.req("POST", "/v1/auth/start", { body: { email: "a@usc.edu" } });
    expect(r.json.delivery).toBe("dev-response");
    expect(r.json.devWarning).toMatch(/INSECURE DEVELOPMENT MODE/);
    expect(r.headers.get("X-Quiet-Hours-Insecure-Dev-Mode")).toContain("signin-codes-in-responses");
    const health = await h.req("GET", "/v1/health");
    expect(health.json.insecureDevModes).toEqual(["signin-codes-in-responses"]);
  });

  it("refuses to serve anything if a dev mode is set outside ENVIRONMENT=development", async () => {
    for (const bad of [
      { ENVIRONMENT: "production", SIGNIN_CODE_DELIVERY: DEV_SIGNIN_CODES_IN_RESPONSE },
      { ENVIRONMENT: undefined, SIGNIN_CODE_DELIVERY: DEV_SIGNIN_CODES_IN_RESPONSE },
      { ENVIRONMENT: "production", SIGNIN_CODE_DELIVERY: "email", AI_MODE: DEV_FAKE_AI },
    ]) {
      const h = new Harness({ now: T.voteOpensAt, env: bad });
      const r = await h.req("POST", "/v1/auth/start", { body: { email: "a@usc.edu" } });
      expect(r.status).toBe(500);
      expect(r.json.error.code).toBe("server_misconfigured");
      expect(JSON.stringify(r.json)).not.toMatch(/devCode/);
      expect((await h.req("GET", "/v1/health")).status).toBe(500);
    }
  });

  it("production (email delivery) never returns a code, and says email is not configured", async () => {
    const h = new Harness({ now: T.voteOpensAt, env: { ENVIRONMENT: "production", SIGNIN_CODE_DELIVERY: "email" } });
    const r = await h.req("POST", "/v1/auth/start", { body: { email: "a@usc.edu" } });
    expect(r.status).toBe(503);
    expect(r.json.error.code).toBe("email_not_configured");
    expect(JSON.stringify(r.json)).not.toMatch(/devCode/);
    expect(r.headers.get("X-Quiet-Hours-Insecure-Dev-Mode")).toBeNull();
    // The failed send leaves no usable challenge behind.
    expect((await h.db.prepare("SELECT COUNT(*) AS n FROM signin_challenges").first<{ n: number }>())!.n).toBe(0);
  });
});

describe("admin secret", () => {
  it("rejects a missing or wrong secret, and disables admin calls when none is configured", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    expect((await h.req("GET", "/v1/admin/weeks")).status).toBe(403);
    expect((await h.req("GET", "/v1/admin/weeks", { admin: "wrong" })).status).toBe(403);
    expect((await h.req("GET", "/v1/admin/weeks", { admin: true })).status).toBe(200);
    const off = new Harness({ now: T.voteOpensAt, env: { ADMIN_SECRET: undefined } });
    const r = await off.req("GET", "/v1/admin/weeks", { admin: true });
    expect(r.status).toBe(503);
    expect(r.json.error.code).toBe("admin_not_configured");
  });
});
