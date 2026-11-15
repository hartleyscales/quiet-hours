/**
 * Lines are stored without any link to the user who wrote it (contract).
 * These tests check there is no stored path from a line back to a person:
 * not by column, not by foreign key, not by time, not by insertion order.
 */
import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { Harness, T, standardWeek, wipe } from "./helpers";

beforeEach(() => wipe(env.DB));

type Col = { name: string; type: string };

describe("lines are anonymous by construction", () => {
  it("the lines table has no user column, no time column, and only a week foreign key", async () => {
    const cols = (await env.DB.prepare("PRAGMA table_info(lines)").all<Col>()).results.map((c) => c.name).sort();
    expect(cols).toEqual(["id", "is_demo", "moderation", "text", "week_id"]);
    const fks = (await env.DB.prepare("PRAGMA foreign_key_list(lines)").all<{ table: string }>()).results.map((f) => f.table);
    expect(fks).toEqual(["weeks"]);
  });

  it("no other table references lines", async () => {
    const tables = (
      await env.DB.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_cf_%'").all<{ name: string }>()
    ).results.map((t) => t.name);
    for (const t of tables) {
      const fks = (await env.DB.prepare(`PRAGMA foreign_key_list(${t})`).all<{ table: string }>()).results;
      expect(fks.map((f) => f.table), t).not.toContain("lines");
    }
  });

  it("is WITHOUT ROWID with a random key, so storage order is not submission order", async () => {
    const sql = (await env.DB.prepare("SELECT sql FROM sqlite_master WHERE name = 'lines'").first<{ sql: string }>())!.sql;
    expect(sql).toMatch(/WITHOUT ROWID/);
    await expect(env.DB.prepare("SELECT rowid FROM lines").all()).rejects.toThrow();
  });

  it("writing a line changes nothing about the writer except wrote_line, and returns no line id", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    await standardWeek(h, true);
    const tokens = await Promise.all(["a", "b", "c"].map((n) => h.signIn(`${n}@usc.edu`)));
    for (const t of tokens) await h.state(t);
    h.now = T.endsAt + 5_000;

    const snapshot = async () =>
      (await env.DB.prepare("SELECT * FROM participation ORDER BY user_id").all<Record<string, unknown>>()).results;
    const before = await snapshot();
    const res = [];
    for (const [i, t] of tokens.entries()) {
      h.now += 60_000;
      res.push(await h.req("POST", "/v1/lines", { token: t, body: { text: `line ${i}` } }));
    }
    const after = await snapshot();

    for (const r of res) {
      expect(r.status).toBe(201);
      expect(Object.keys(r.json).sort()).toEqual(["ok", "pending", "shown"]);
    }
    // Every participation column is identical except wrote_line.
    expect(after.map(({ wrote_line, ...rest }) => rest)).toEqual(before.map(({ wrote_line, ...rest }) => rest));
    expect(after.every((r) => r.wrote_line === 1)).toBe(true);

    // The only things stored about a line: its id, week, text, check state, demo flag.
    const lines = (await env.DB.prepare("SELECT * FROM lines").all<Record<string, unknown>>()).results;
    expect(lines).toHaveLength(3);
    const users = (await env.DB.prepare("SELECT id, email FROM users").all<{ id: string; email: string }>()).results;
    for (const line of lines) {
      for (const value of Object.values(line)) {
        for (const u of users) {
          expect(String(value)).not.toContain(u.id);
          expect(String(value)).not.toContain(u.email);
        }
      }
    }
  });

  it("the recap and its API never expose who wrote a line", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id } = await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    await h.state(a);
    h.now = T.endsAt;
    await h.req("POST", "/v1/lines", { token: a, body: { text: "Walked to the Coliseum" } });
    h.now = T.toldAt;
    const lineId = (await env.DB.prepare("SELECT id FROM lines").first<{ id: string }>())!.id;
    h.ai!.recapImpl = async () => [{ kind: "quote", text: "x", lineIds: [lineId] }];
    await h.req("POST", `/v1/admin/weeks/${id}/recap`, { admin: true });
    const recap = await h.req("GET", `/v1/weeks/${id}/recap`, { token: a });
    const userId = (await env.DB.prepare("SELECT id FROM users").first<{ id: string }>())!.id;
    expect(JSON.stringify(recap.json)).not.toContain(userId);
    expect(JSON.stringify(recap.json)).not.toContain("a@usc.edu");
  });
});
