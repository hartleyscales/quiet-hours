import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import example from "../examples/campus-week.example.json";
import { CampusWeekSchema } from "../src/ai/campus-week";
import { FakeAi } from "../src/ai/fake";
import { PROPOSALS_SCHEMA, PROPOSALS_SYSTEM } from "../src/ai/prompts";
import { MAX_REASON, reasonProblem, sentenceCount, validateProposals } from "../src/ai/proposals";
import { DEMO_OPTIONS } from "../src/demo";
import { Harness, T, standardWeek, wipe } from "./helpers";

beforeEach(() => wipe(env.DB));

const bounds = { earliestStart: T.voteClosesAt, latestEnd: T.toldAt };
const good = [
  { startLocal: "2026-11-18T21:00", endLocal: "2026-11-18T22:00", reason: "Classes are almost empty after 9 p.m. and the basketball game is over." },
  { startLocal: "2026-11-17T21:30", endLocal: "2026-11-17T23:00", reason: "Right after the MATH 125 midterm lets out." },
  { startLocal: "2026-11-18T17:00", endLocal: "2026-11-18T19:00", reason: "Starts just after sunset, before the evening game." },
];

describe("the campus week input", () => {
  it("the hand-written example is valid", () => {
    const r = CampusWeekSchema.safeParse(example);
    expect(r.success, JSON.stringify(!r.success && r.error.issues)).toBe(true);
  });
  it("rejects a class load that is not 24 hours long, and unknown fields", () => {
    const bad = structuredClone(example) as any;
    bad.classLoad[0].studentsInClassByHour.pop();
    expect(CampusWeekSchema.safeParse(bad).success).toBe(false);
    expect(CampusWeekSchema.safeParse({ ...example, scraped: true }).success).toBe(false);
  });
});

describe("validateProposals", () => {
  it("accepts three valid windows and converts local times to UTC", () => {
    const r = validateProposals(good, bounds);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.proposals[0]).toMatchObject({ startsAt: "2026-11-19T05:00:00.000Z", endsAt: "2026-11-19T06:00:00.000Z", minutes: 60 });
      expect(r.proposals.map((p) => p.minutes)).toEqual([60, 90, 120]);
    }
  });
  it("rejects the wrong count, bad times, out-of-bounds windows, bad lengths, duplicates and long reasons", () => {
    expect(validateProposals(good.slice(0, 2), bounds).ok).toBe(false);
    const cases: [object, RegExp][] = [
      [{ startLocal: "2026-11-18 21:00" }, /real campus-local times/],
      [{ startLocal: "2026-11-17T16:00", endLocal: "2026-11-17T17:00" }, /before .* vote closes/],
      [{ startLocal: "2026-11-19T08:30", endLocal: "2026-11-19T09:30" }, /after .* told back/],
      [{ endLocal: "2026-11-18T21:15" }, /lasts 15 minutes/],
      [{ endLocal: "2026-11-19T02:00" }, /lasts 300 minutes/],
      [{ reason: "x".repeat(71) }, /reason is 71 characters; it must be at most 70/],
      [{ reason: "Quiet. Nothing on. No exams." }, /reason has 3 sentences; it must be one or two/],
      [{ reason: "Quiet night\nNothing on" }, /one line/],
      [{ reason: "  " }, /has no reason/],
      [{ startLocal: good[1]!.startLocal, endLocal: good[1]!.endLocal }, /identical/],
    ];
    for (const [patch, msg] of cases) {
      const r = validateProposals([{ ...good[0]!, ...patch }, good[1]!, good[2]!], bounds);
      expect(r.ok, JSON.stringify(patch)).toBe(false);
      expect((r as any).reasons.join(" | "), JSON.stringify(patch)).toMatch(msg);
    }
  });
  it("a reason is at most 70 characters and at most two sentences, on one line", () => {
    expect(MAX_REASON).toBe(70);
    expect(reasonProblem("x".repeat(70))).toBeNull();
    expect(reasonProblem("Quiet night. Nothing else is on.")).toBeNull(); // two sentences
    expect(reasonProblem("Quiet. Nothing on. No exams.")).toMatch(/3 sentences/);
  });
  it("does not mistake abbreviations for sentence ends", () => {
    expect(sentenceCount("After the 7 p.m. game vs. UCLA ends.")).toBe(1);
    expect(sentenceCount("Quiet. Very quiet.")).toBe(2);
  });
  it("the prompt asks for the same reason the code checks, and every reason the server supplies passes it", async () => {
    expect(PROPOSALS_SYSTEM).toContain("one or two short sentences, at most 70 characters in all");
    expect(PROPOSALS_SCHEMA.properties.windows.items.properties.reason.description).toBe("One or two short sentences, at most 70 characters in all");
    const fake = await new FakeAi().proposeWindows({ campusWeek: example as any, earliestStartLocal: "2026-11-17T17:00", latestEndLocal: "2026-11-18T22:30" });
    for (const reason of [...fake.map((p) => p.reason), ...DEMO_OPTIONS.map((o) => o.reason)]) {
      expect(reasonProblem(reason), reason).toBeNull();
    }
    expect(DEMO_OPTIONS.every((o) => o.reason.startsWith("DEMO: "))).toBe(true);
  });
});

describe("POST /v1/admin/weeks/:id/proposals", () => {
  it("returns validated proposals, retrying a bad draft with feedback, and can apply them as options", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    const { id } = await h.week({ voteOpensAt: T.voteOpensAt, voteClosesAt: T.voteClosesAt, toldAt: T.toldAt });
    const feedback: string[][] = [];
    h.ai!.proposeImpl = async (req, fb) => {
      feedback.push(fb);
      expect(req.earliestStartLocal).toBe("2026-11-17T17:00");
      expect(req.latestEndLocal).toBe("2026-11-18T22:30"); // 15 minutes before toldAt
      return feedback.length === 1 ? good.slice(0, 2) : good;
    };
    const r = await h.req("POST", `/v1/admin/weeks/${id}/proposals`, { admin: true, body: { campusWeek: example, apply: true } });
    expect(r.status).toBe(200);
    expect(r.json.attempts).toBe(2);
    expect(feedback[1]!.join()).toMatch(/exactly 3/);
    expect(r.json.proposals).toHaveLength(3);
    const week = await h.req("GET", `/v1/admin/weeks/${id}`, { admin: true });
    expect(week.json.options.map((o: any) => [o.minutes, o.source])).toEqual([
      [60, "ai"],
      [90, "ai"],
      [120, "ai"],
    ]);
  });

  it("gives up after three invalid drafts with the reasons", async () => {
    const h = new Harness({ now: T.voteOpensAt });
    const { id } = await h.week({ voteOpensAt: T.voteOpensAt, voteClosesAt: T.voteClosesAt, toldAt: T.toldAt });
    h.ai!.proposeImpl = async () => [good[0]!, good[0]!, good[0]!];
    const r = await h.req("POST", `/v1/admin/weeks/${id}/proposals`, { admin: true, body: { campusWeek: example } });
    expect(r.status).toBe(502);
    expect(r.json.error.code).toBe("ai_invalid_output");
    expect(r.json.error.details.rejected).toHaveLength(3);
  });

  it("fails with 503 ai_unavailable when no key is configured, and rejects a malformed campus week", async () => {
    const h = new Harness({ now: T.voteOpensAt, ai: null });
    const { id } = await standardWeek(h);
    let r = await h.req("POST", `/v1/admin/weeks/${id}/proposals`, { admin: true, body: { campusWeek: example } });
    expect([r.status, r.json.error.code]).toEqual([503, "ai_unavailable"]);
    r = await h.req("POST", `/v1/admin/weeks/${id}/proposals`, { admin: true, body: { campusWeek: { weekOf: "soon" } } });
    expect([r.status, r.json.error.code]).toEqual([400, "invalid_request"]);
  });
});
