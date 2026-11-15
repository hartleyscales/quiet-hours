import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { RECAP_SYSTEM } from "../src/ai/prompts";
import { MAX_HIGHLIGHTS, MAX_HIGHLIGHT_TEXT, applyGroupCheck, buildRecap, validateHighlight } from "../src/ai/recap";
import { AiOutputError } from "../src/ai/types";
import { Harness, StubAi, T, standardWeek, wipe } from "./helpers";

beforeEach(() => wipe(env.DB));

const LINES = new Map([
  ["ln_a", "Called my mom"],
  ["ln_b", "Called my dad about his garden"],
  ["ln_c", "Called my grandma"],
  ["ln_d", "Walked to the Coliseum"],
  ["ln_e", "Read 80 pages"],
]);

describe("validateHighlight: the recap rules, in code", () => {
  const v = (d: object) => validateHighlight(d as any, LINES);

  it("accepts a group whose one number equals the ids attached", () => {
    const r = v({ kind: "group", text: "3 people called a family member", lineIds: ["ln_a", "ln_b", "ln_c"] });
    expect(r).toEqual({ ok: true, highlight: { kind: "group", text: "3 people called a family member", lineIds: ["ln_a", "ln_b", "ln_c"], count: 3 } });
  });

  it("rejects a count that does not equal the ids attached", () => {
    const r = v({ kind: "group", text: "41 people called a parent", lineIds: ["ln_a", "ln_b"] });
    expect(r.ok).toBe(false);
    expect((r as any).reason).toMatch(/count mismatch/);
  });

  it("rejects a group with no number, or with a second number", () => {
    expect(v({ kind: "group", text: "People called home", lineIds: ["ln_a", "ln_b"] }).ok).toBe(false);
    expect(v({ kind: "group", text: "2 people called home after 9", lineIds: ["ln_a", "ln_b"] }).ok).toBe(false);
  });

  it("rejects amount words that would be an unchecked count", () => {
    for (const text of [
      "2 people called home, most of them parents",
      "2 people called home, both parents",
      "2 people, half the campus, called home",
      "2 people called everyone they know",
      "2 people called home, two of them twice",
      "2 people made a dozen calls",
    ]) {
      expect(v({ kind: "group", text, lineIds: ["ln_a", "ln_b"] }).ok, text).toBe(false);
    }
  });

  it("rejects ids that are not stored lines of this week, duplicates, and empty id lists", () => {
    expect((v({ kind: "quote", text: "x", lineIds: ["ln_zzz"] }) as any).reason).toMatch(/not one of the lines/);
    expect(v({ kind: "group", text: "2 people called", lineIds: ["ln_a", "ln_a"] }).ok).toBe(false);
    expect(v({ kind: "quote", text: "x", lineIds: [] }).ok).toBe(false);
    expect(v({ kind: "group", text: "1 person called", lineIds: ["ln_a"] }).ok).toBe(false);
    expect(v({ kind: "headline", text: "x", lineIds: ["ln_a"] }).ok).toBe(false);
  });

  it("shows a quote as the stored line, never the model's copy", () => {
    const r = v({ kind: "quote", text: "Read 800 pages and found God", lineIds: ["ln_e"] });
    expect(r).toEqual({ ok: true, highlight: { kind: "quote", text: "Read 80 pages", lineIds: ["ln_e"], count: null } });
    expect(v({ kind: "quote", text: "x", lineIds: ["ln_a", "ln_b"] }).ok).toBe(false);
  });

  it("drops a highlight longer than the hard cap; a quote is never cut, so a long line cannot be quoted", () => {
    const long = new Map([...LINES, ["ln_long", "Walked all the way to the beach and back, then slept on the bus"]]);
    expect(MAX_HIGHLIGHT_TEXT).toBe(60);
    const quote = validateHighlight({ kind: "quote", text: "x", lineIds: ["ln_long"] } as any, long);
    expect((quote as any).reason).toMatch(/longer than 60 characters/);
    const sentence = "2 people walked somewhere far, came back and slept on a bus home";
    expect(sentence.length).toBeGreaterThan(60);
    const group = validateHighlight({ kind: "group", text: sentence, lineIds: ["ln_a", "ln_b"] } as any, long);
    expect((group as any).reason).toMatch(/longer than 60 characters/);
  });

  it("the second pass removes lines the sentence does not describe and re-renders the count", () => {
    const h = { kind: "group" as const, text: "4 people called family", lineIds: ["ln_a", "ln_b", "ln_c", "ln_d"], count: 4 };
    expect(applyGroupCheck(h, new Set(["ln_a", "ln_b", "ln_c"]))).toEqual({
      kind: "group",
      text: "3 people called family",
      lineIds: ["ln_a", "ln_b", "ln_c"],
      count: 3,
    });
    expect(applyGroupCheck(h, new Set(["ln_a"]))).toBeNull();
  });
});

describe("buildRecap: drop, check, retry", () => {
  const lines = [...LINES].map(([id, text]) => ({ id, text }));

  it("drops bad highlights, keeps good ones, and uses the group check", async () => {
    const ai = new StubAi();
    ai.recapImpl = async () => [
      { kind: "group", text: "4 people called family", lineIds: ["ln_a", "ln_b", "ln_c", "ln_d"] },
      { kind: "quote", text: "anything", lineIds: ["ln_e"] },
      { kind: "group", text: "9 people walked", lineIds: ["ln_d", "ln_a"] },
    ];
    ai.confirmImpl = async (_claim, ls) => ls.filter((l) => l.text.startsWith("Called")).map((l) => l.id);
    const r = await buildRecap(ai, lines);
    expect(r.highlights).toEqual([
      { kind: "group", text: "3 people called family", lineIds: ["ln_a", "ln_b", "ln_c"], count: 3 },
      { kind: "quote", text: "Read 80 pages", lineIds: ["ln_e"], count: null },
    ]);
    expect(r.dropped.map((d) => d.reason).join(" | ")).toMatch(/count mismatch/);
    expect(r.attempts).toBe(1);
  });

  it("keeps at most five highlights, and asks the model for five of at most 55 characters", async () => {
    expect(MAX_HIGHLIGHTS).toBe(5);
    expect(RECAP_SYSTEM).toContain("At most 5 highlights");
    expect(RECAP_SYSTEM).toContain("at most 55 characters");
    const ai = new StubAi();
    ai.recapImpl = async () => [...LINES.keys(), "ln_a"].map((id) => ({ kind: "quote", text: "x", lineIds: [id] }));
    const r = await buildRecap(ai, lines);
    expect(r.highlights.map((h) => h.lineIds[0])).toEqual(["ln_a", "ln_b", "ln_c", "ln_d", "ln_e"]);
    expect(r.dropped).toEqual([{ draft: { kind: "quote", text: "x", lineIds: ["ln_a"] }, reason: "more than 5 highlights" }]);
  });

  it("retries with feedback when most of a draft is unusable, and keeps the best attempt", async () => {
    const ai = new StubAi();
    const feedbackSeen: string[][] = [];
    ai.recapImpl = async (_l, feedback) => {
      feedbackSeen.push(feedback);
      if (feedbackSeen.length === 1) return [{ kind: "group", text: "50 people called", lineIds: ["ln_a", "ln_b"] }];
      return [{ kind: "group", text: "2 people called a parent", lineIds: ["ln_a", "ln_b"] }];
    };
    const r = await buildRecap(ai, lines);
    expect(r.attempts).toBe(2);
    expect(feedbackSeen[1]!.join()).toMatch(/count mismatch/);
    expect(r.highlights).toHaveLength(1);
  });

  it("retries output that is not usable at all, then gives up with an error", async () => {
    const ai = new StubAi();
    ai.recapImpl = async () => {
      throw new AiOutputError("The response was not valid JSON.");
    };
    await expect(buildRecap(ai, lines)).rejects.toThrow(/not valid JSON/);
    expect(ai.calls.recap).toBe(3);
  });

  it("does not call the model when there are no lines", async () => {
    const ai = new StubAi();
    expect(await buildRecap(ai, [])).toEqual({ highlights: [], dropped: [], attempts: 0 });
    expect(ai.calls.recap).toBe(0);
  });
});

describe("recap endpoints", () => {
  async function weekWithLines(h: Harness) {
    const { id } = await standardWeek(h, true);
    const tokens = await Promise.all(["a", "b", "c"].map((n) => h.signIn(`${n}@usc.edu`)));
    for (const t of tokens) await h.state(t);
    h.now = T.endsAt;
    const texts = ["Called my mom", "Called my dad", "Looked at the sky"];
    for (const [i, t] of tokens.entries()) await h.req("POST", "/v1/lines", { token: t, body: { text: texts[i] } });
    const ids = (await env.DB.prepare("SELECT id, text FROM lines").all<{ id: string; text: string }>()).results;
    const idOf = (text: string) => ids.find((l) => l.text === text)!.id;
    return { id, tokens, idOf };
  }

  it("generates, stores and serves a traceable recap; the told state carries it", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id, tokens, idOf } = await weekWithLines(h);
    h.ai!.recapImpl = async () => [
      { kind: "group", text: "2 people called a parent", lineIds: [idOf("Called my mom"), idOf("Called my dad")] },
      { kind: "quote", text: "Looked at the sky", lineIds: [idOf("Looked at the sky")] },
    ];

    const early = await h.req("GET", `/v1/weeks/${id}/recap`, { token: tokens[0] });
    expect([early.status, early.json.error.code]).toEqual([409, "not_told_yet"]);

    const gen = await h.req("POST", `/v1/admin/weeks/${id}/recap`, { admin: true });
    expect(gen.status).toBe(201);
    expect(gen.json.stats).toMatchObject({ in: 3, lines: 3, linesNotShown: 0 });

    h.now = T.toldAt;
    const s = await h.state(tokens[0]!);
    expect(s.phase).toBe("told");
    expect(s.recap.highlights[0]).toMatchObject({
      kind: "group",
      text: "2 people called a parent",
      count: 2,
      lines: [
        { id: idOf("Called my mom"), text: "Called my mom" },
        { id: idOf("Called my dad"), text: "Called my dad" },
      ],
    });
    const read = await h.req("GET", `/v1/weeks/${id}/recap`, { token: tokens[0] });
    expect(read.json.highlights).toHaveLength(2);
    const weeks = await h.req("GET", "/v1/weeks", { token: tokens[0] });
    expect(weeks.json.weeks).toEqual([expect.objectContaining({ id, hasRecap: true })]);
  });

  it("leaves lines that have not passed the editing check out of the recap", async () => {
    const h = new Harness({ now: T.voteClosesAt });
    const { id } = await standardWeek(h, true);
    const a = await h.signIn("a@usc.edu");
    await h.state(a);
    h.now = T.endsAt;
    h.ai = null;
    expect((await h.req("POST", "/v1/lines", { token: a, body: { text: "Unchecked" } })).json.pending).toBe(true);
    h.ai = new StubAi();
    let seen: string[] = [];
    h.ai.recapImpl = async (lines) => {
      seen = lines.map((l) => l.text);
      return [];
    };
    const gen = await h.req("POST", `/v1/admin/weeks/${id}/recap`, { admin: true });
    expect(gen.json.stats).toMatchObject({ lines: 0, linesNotShown: 1 });
    expect(seen).toEqual([]);
  });

  it("cannot be written before the window ends", async () => {
    const h = new Harness({ now: T.startsAt });
    const { id } = await standardWeek(h, true);
    const r = await h.req("POST", `/v1/admin/weeks/${id}/recap`, { admin: true });
    expect([r.status, r.json.error.code]).toEqual([409, "phase_closed"]);
  });
});

describe("with no API key, the AI endpoints fail clearly", () => {
  it("recap, proposals and moderation return 503 ai_unavailable", async () => {
    const h = new Harness({ now: T.endsAt, ai: null });
    const { id } = await standardWeek(h, true);
    for (const [path, body] of [
      [`/v1/admin/weeks/${id}/recap`, undefined],
      [`/v1/admin/weeks/${id}/moderate`, undefined],
    ] as const) {
      const r = await h.req("POST", path, { admin: true, body });
      expect(r.status, path).toBe(503);
      expect(r.json.error.code).toBe("ai_unavailable");
      expect(r.json.error.message).toMatch(/ANTHROPIC_API_KEY/);
    }
  });
});
