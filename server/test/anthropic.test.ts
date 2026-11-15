/**
 * The real Claude adapter, with the network replaced by a fake fetch. Checks
 * the request shape (model, streaming, effort, structured output, refusal
 * fallback, no thinking or sampling parameters) and how responses and errors
 * are read. No API key, no network.
 */
import { describe, expect, it } from "vitest";
import example from "../examples/campus-week.example.json";
import { AnthropicAi, MODEL } from "../src/ai/anthropic";
import type { CampusWeek } from "../src/ai/campus-week";
import { AiUnavailableError } from "../src/ai/types";

interface Captured {
  url: string;
  headers: Headers;
  body: any;
}

function sse(model: string, text: string, stopReason = "end_turn"): Response {
  const events = [
    ["message_start", { type: "message_start", message: { id: "msg_1", type: "message", role: "assistant", model, content: [], stop_reason: null, stop_sequence: null, usage: { input_tokens: 10, output_tokens: 1 } } }],
    ["content_block_start", { type: "content_block_start", index: 0, content_block: { type: "text", text: "" } }],
    ["content_block_delta", { type: "content_block_delta", index: 0, delta: { type: "text_delta", text } }],
    ["content_block_stop", { type: "content_block_stop", index: 0 }],
    ["message_delta", { type: "message_delta", delta: { stop_reason: stopReason, stop_sequence: null }, usage: { output_tokens: 20 } }],
    ["message_stop", { type: "message_stop" }],
  ];
  const body = events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");
  return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
}

function message(model: string, text: string | null, stopReason = "end_turn", stopDetails: object | null = null): Response {
  return Response.json({
    id: "msg_2",
    type: "message",
    role: "assistant",
    model,
    content: text === null ? [] : [{ type: "thinking", thinking: "", signature: "sig" }, { type: "text", text }],
    stop_reason: stopReason,
    stop_details: stopDetails,
    stop_sequence: null,
    usage: { input_tokens: 5, output_tokens: 5 },
  });
}

function fakeFetch(respond: (c: Captured) => Response) {
  const calls: Captured[] = [];
  const f = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = new Request(input, init);
    const c = { url: req.url, headers: req.headers, body: JSON.parse(await req.text()) };
    calls.push(c);
    return respond(c);
  }) as typeof fetch;
  return { f, calls };
}

const request = {
  campusWeek: example as unknown as CampusWeek,
  earliestStartLocal: "2026-11-17T17:00",
  latestEndLocal: "2026-11-19T09:00",
};

describe("AnthropicAi", () => {
  it("uses claude-opus-5-5 for every job", () => {
    expect(MODEL).toBe("claude-opus-5-5");
    const ai = new AnthropicAi("test-key");
    expect(Object.values(ai.models)).toEqual([MODEL, MODEL, MODEL, MODEL]);
  });

  it("proposals: streamed, high effort, JSON schema output, server-side refusal fallback, no thinking or sampling params", async () => {
    const windows = [{ startLocal: "2026-11-18T21:00", endLocal: "2026-11-18T22:00", reason: "Quiet." }];
    const { f, calls } = fakeFetch(() => sse(MODEL, JSON.stringify({ windows })));
    const ai = new AnthropicAi("test-key", { fetch: f, maxRetries: 0 });
    expect(await ai.proposeWindows(request, [])).toEqual(windows);

    const c = calls[0]!;
    expect(c.url).toMatch(/\/v1\/messages(\?beta=true)?$/);
    expect(c.headers.get("authorization") ?? c.headers.get("x-api-key")).toMatch(/test-key$/);
    expect(c.headers.get("anthropic-beta")).toContain("server-side-fallback-2026-07-01");
    expect(c.body).toMatchObject({
      model: "claude-opus-5-5",
      max_tokens: 64000,
      stream: true,
      fallbacks: "default",
      output_config: { effort: "high", format: { type: "json_schema" } },
    });
    expect(c.body.output_config.format.schema.required).toEqual(["windows"]);
    for (const absent of ["thinking", "temperature", "top_p", "top_k"]) expect(c.body).not.toHaveProperty(absent);
    expect(c.body.messages[0].content).toContain("Earliest start: 2026-11-17T17:00");
  });

  it("recap draft is streamed at high effort; the group check and editing check are short requests at medium and low effort", async () => {
    const { f, calls } = fakeFetch((c) =>
      c.body.stream
        ? sse(MODEL, JSON.stringify({ highlights: [{ kind: "quote", text: "x", lineIds: ["ln_a"] }] }))
        : c.body.system.startsWith("You check one sentence")
          ? message(MODEL, JSON.stringify({ results: [{ id: "ln_a", describes: true }, { id: "ln_b", describes: false }] }))
          : message(MODEL, JSON.stringify({ show: true, reason: "ok" })),
    );
    const ai = new AnthropicAi("test-key", { fetch: f, maxRetries: 0 });
    await ai.draftRecap([{ id: "ln_a", text: "Called my mom" }], []);
    expect(await ai.confirmGroup("2 people called a parent", [{ id: "ln_a", text: "a" }, { id: "ln_b", text: "b" }])).toEqual(["ln_a"]);
    expect(await ai.moderate("Reading on the lawn", "board_post")).toEqual({ show: true, reason: "ok" });

    const [draft, check, mod] = calls;
    expect(draft!.body).toMatchObject({ stream: true, output_config: { effort: "high" } });
    expect(check!.body).toMatchObject({ max_tokens: 16000, output_config: { effort: "medium", format: { type: "json_schema" } } });
    expect(mod!.body).toMatchObject({ max_tokens: 16000, output_config: { effort: "low", format: { type: "json_schema" } } });
    for (const c of calls) {
      expect(c.body.model).toBe("claude-opus-5-5");
      expect(c.body.fallbacks).toBe("default");
      expect(c.headers.get("anthropic-beta")).toContain("server-side-fallback-2026-07-01");
      expect(c.body).not.toHaveProperty("thinking");
    }
    expect(check!.body.stream).toBeUndefined();
    expect(mod!.body.stream).toBeUndefined();
  });

  it("a refused editing check (after the fallback chain) means the text is not shown", async () => {
    const { f } = fakeFetch(() => message(MODEL, null, "refusal", { type: "refusal", category: "general_harms" }));
    const ai = new AnthropicAi("test-key", { fetch: f, maxRetries: 0 });
    expect(await ai.moderate("...", "line")).toEqual({ show: false, reason: "check_declined" });
  });

  it("a refused draft surfaces as ai_refused after the fallback chain", async () => {
    const { f } = fakeFetch(() => sse(MODEL, "", "refusal"));
    const ai = new AnthropicAi("test-key", { fetch: f, maxRetries: 0 });
    await expect(ai.proposeWindows(request, [])).rejects.toMatchObject({ code: "ai_refused", status: 502 });
  });

  it("cut-off or non-JSON output is a retryable output error", async () => {
    const { f } = fakeFetch(() => sse(MODEL, "{\"windows\": [", "max_tokens"));
    const ai = new AnthropicAi("test-key", { fetch: f, maxRetries: 0 });
    await expect(ai.proposeWindows(request, [])).rejects.toMatchObject({ name: "AiOutputError" });
    const { f: f2 } = fakeFetch(() => message(MODEL, "not json"));
    await expect(new AnthropicAi("test-key", { fetch: f2, maxRetries: 0 }).moderate("hi", "line")).rejects.toMatchObject({ name: "AiOutputError" });
  });

  it("a rejected key or no key is ai_unavailable", async () => {
    const { f } = fakeFetch(() => Response.json({ type: "error", error: { type: "authentication_error", message: "invalid x-api-key" } }, { status: 401 }));
    const ai = new AnthropicAi("bad-key", { fetch: f, maxRetries: 0 });
    await expect(ai.moderate("hi", "line")).rejects.toMatchObject({ code: "ai_unavailable", status: 503 });
    expect(() => new AnthropicAi("")).toThrow(AiUnavailableError);
  });
});
