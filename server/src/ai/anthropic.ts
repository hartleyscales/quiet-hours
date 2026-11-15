/**
 * The three AI jobs on the Claude API, via the official SDK.
 *
 * Every job uses claude-opus-5-5 (MODEL). Thinking is always on for that
 * model, so it is never set; effort is the control, and its default on this
 * model is "medium", so every request sets it explicitly:
 *
 *   proposals, recap draft   effort "high", streamed, max_tokens 64000
 *   recap group check        effort "medium", max_tokens 16000
 *   editing check            effort "low" (it runs inline when someone
 *                            posts), max_tokens 16000
 *
 * Every request asks for structured JSON output (output_config.format) and
 * opts into the server-side refusal fallback (fallbacks: "default", beta
 * server-side-fallback-2026-07-01): if the model declines, the API re-runs
 * the request on a fallback model inside the same call. A final
 * stop_reason "refusal" means the whole chain declined.
 *
 * Every response is checked for stop_reason before content is read.
 */
import Anthropic from "@anthropic-ai/sdk";
import {
  GROUP_CHECK_SCHEMA,
  GROUP_CHECK_SYSTEM,
  MODERATION_SCHEMA,
  MODERATION_SYSTEM,
  PROPOSALS_SCHEMA,
  PROPOSALS_SYSTEM,
  RECAP_SCHEMA,
  RECAP_SYSTEM,
  groupCheckUserMessage,
  moderationUserMessage,
  proposalsUserMessage,
  recapUserMessage,
} from "./prompts";
import {
  AiFailedError,
  AiOutputError,
  AiRefusedError,
  AiUnavailableError,
  type AiProvider,
  type DraftHighlight,
  type DraftProposal,
  type LineForRecap,
  type ModerationVerdict,
  type ProposalRequest,
} from "./types";

export const MODEL = "claude-opus-5-5";
const FALLBACK_BETA = "server-side-fallback-2026-07-01";

type JsonSchema = { readonly [key: string]: unknown };

interface ResponseLike {
  stop_reason: string | null;
  stop_details?: { category?: string | null } | null;
  content: ReadonlyArray<{ type: string; text?: string }>;
}

/** Reads the JSON answer out of a response, after checking why it stopped. */
export function readJson(msg: ResponseLike): unknown {
  if (msg.stop_reason === "refusal") throw new AiRefusedError(msg.stop_details?.category ?? null);
  if (msg.stop_reason === "max_tokens") throw new AiOutputError("The response was cut off at max_tokens.");
  const text = msg.content
    .filter((b) => b.type === "text")
    .map((b) => b.text ?? "")
    .join("");
  try {
    return JSON.parse(text);
  } catch {
    throw new AiOutputError("The response was not valid JSON.");
  }
}

/** Maps SDK errors onto the API's error codes. */
function translate(err: unknown): never {
  if (err instanceof AiRefusedError || err instanceof AiOutputError) throw err;
  if (err instanceof Anthropic.AuthenticationError || err instanceof Anthropic.PermissionDeniedError) {
    throw new AiUnavailableError("The Claude API rejected ANTHROPIC_API_KEY.");
  }
  if (err instanceof Anthropic.RateLimitError) {
    throw new AiFailedError("The Claude API is rate limiting us. Try again shortly.", 503, "ai_busy");
  }
  if (err instanceof Anthropic.BadRequestError) {
    throw new AiFailedError(`The Claude API rejected the request: ${err.message}`);
  }
  if (err instanceof Anthropic.APIError) {
    throw new AiFailedError(`The Claude API failed (${err.status ?? "no status"}): ${err.message}`);
  }
  throw new AiFailedError(`Could not reach the Claude API: ${err instanceof Error ? err.message : String(err)}`);
}

export interface AnthropicAiOptions {
  /** Injected in tests to capture requests without touching the network. */
  fetch?: typeof fetch;
  maxRetries?: number;
}

export class AnthropicAi implements AiProvider {
  readonly id = "anthropic";
  readonly models = { proposals: MODEL, recap: MODEL, moderation: MODEL, recapCheck: MODEL };
  private readonly client: Anthropic;

  constructor(apiKey: string, opts: AnthropicAiOptions = {}) {
    if (!apiKey) throw new AiUnavailableError();
    this.client = new Anthropic({ apiKey, fetch: opts.fetch, maxRetries: opts.maxRetries ?? 2 });
  }

  /** Long jobs (proposals, recap draft): streamed so a long think cannot hit an HTTP timeout. */
  private async draft(system: string, user: string, schema: JsonSchema): Promise<unknown> {
    try {
      const msg = await this.client.beta.messages
        .stream({
          model: MODEL,
          max_tokens: 64000,
          betas: [FALLBACK_BETA],
          fallbacks: "default",
          output_config: { effort: "high", format: { type: "json_schema", schema: { ...schema } } },
          system,
          messages: [{ role: "user", content: user }],
        })
        .finalMessage();
      return readJson(msg);
    } catch (err) {
      translate(err);
    }
  }

  /** Short checks (editing check, recap group check). */
  private async check(system: string, user: string, schema: JsonSchema, effort: "low" | "medium"): Promise<unknown> {
    try {
      const msg = await this.client.beta.messages.create({
        model: MODEL,
        max_tokens: 16000,
        betas: [FALLBACK_BETA],
        fallbacks: "default",
        output_config: { effort, format: { type: "json_schema", schema: { ...schema } } },
        system,
        messages: [{ role: "user", content: user }],
      });
      return readJson(msg);
    } catch (err) {
      translate(err);
    }
  }

  async moderate(text: string, kind: "board_post" | "line"): Promise<ModerationVerdict> {
    let out: unknown;
    try {
      out = await this.check(MODERATION_SYSTEM, moderationUserMessage(text, kind), MODERATION_SCHEMA, "low");
    } catch (err) {
      // If the check itself is declined, the text is not shown.
      if (err instanceof AiRefusedError) return { show: false, reason: "check_declined" };
      throw err;
    }
    const o = out as { show?: unknown; reason?: unknown };
    if (typeof o.show !== "boolean") throw new AiOutputError("Editing check returned no verdict.");
    const reason = o.reason === "names_or_targets_person" || o.reason === "abusive" ? o.reason : "ok";
    // Trust "hide" over "ok" if the two fields disagree.
    return o.show && reason === "ok" ? { show: true, reason: "ok" } : { show: false, reason: reason === "ok" ? "abusive" : reason };
  }

  async proposeWindows(req: ProposalRequest, feedback: string[]): Promise<DraftProposal[]> {
    const out = (await this.draft(PROPOSALS_SYSTEM, proposalsUserMessage(req, feedback), PROPOSALS_SCHEMA)) as {
      windows?: unknown;
    };
    if (!Array.isArray(out?.windows)) throw new AiOutputError("Proposals response had no windows array.");
    return out.windows as DraftProposal[];
  }

  async draftRecap(lines: LineForRecap[], feedback: string[]): Promise<DraftHighlight[]> {
    const out = (await this.draft(RECAP_SYSTEM, recapUserMessage(lines, feedback), RECAP_SCHEMA)) as {
      highlights?: unknown;
    };
    if (!Array.isArray(out?.highlights)) throw new AiOutputError("Recap response had no highlights array.");
    return out.highlights as DraftHighlight[];
  }

  async confirmGroup(claim: string, lines: LineForRecap[]): Promise<string[]> {
    const out = (await this.check(GROUP_CHECK_SYSTEM, groupCheckUserMessage(claim, lines), GROUP_CHECK_SCHEMA, "medium")) as {
      results?: unknown;
    };
    if (!Array.isArray(out?.results)) throw new AiOutputError("Group check returned no results.");
    return (out.results as { id?: unknown; describes?: unknown }[])
      .filter((r) => r.describes === true && typeof r.id === "string")
      .map((r) => r.id as string);
  }
}
