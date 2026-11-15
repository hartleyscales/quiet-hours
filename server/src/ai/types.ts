/**
 * The three AI jobs from the contract, behind one interface so the real
 * Claude implementation, the development fake and test stubs are
 * interchangeable. Everything a provider returns is a DRAFT: the server
 * validates it in code (src/ai/recap.ts, src/ai/proposals.ts) before any of
 * it is stored or shown.
 */
import { ApiError } from "../errors";
import type { CampusWeek } from "./campus-week";

export interface LineForRecap {
  id: string;
  text: string;
}

/** A highlight as the model drafted it. Untrusted until validated. */
export interface DraftHighlight {
  kind: string;
  text: string;
  lineIds: string[];
}

/** A window as the model drafted it, in campus local time ("YYYY-MM-DDTHH:MM"). */
export interface DraftProposal {
  startLocal: string;
  endLocal: string;
  reason: string;
}

export interface ProposalRequest {
  campusWeek: CampusWeek;
  /** Local "YYYY-MM-DDTHH:MM": windows may not start earlier (the vote closes then). */
  earliestStartLocal: string;
  /** Local "YYYY-MM-DDTHH:MM": windows may not end later (15 minutes before the week's toldAt). */
  latestEndLocal: string;
}

export type ModerationReason = "ok" | "names_or_targets_person" | "abusive" | "check_declined";

export interface ModerationVerdict {
  show: boolean;
  reason: ModerationReason;
}

export interface AiProvider {
  /** "anthropic" or "dev-fake-ai". Stored with every recap. */
  readonly id: string;
  readonly models: { proposals: string; recap: string; moderation: string; recapCheck: string };

  /** Job 3, the editing check: may this board post or line be shown? */
  moderate(text: string, kind: "board_post" | "line"): Promise<ModerationVerdict>;

  /** Job 1: three candidate windows. `feedback` lists why a previous draft was rejected. */
  proposeWindows(req: ProposalRequest, feedback: string[]): Promise<DraftProposal[]>;

  /** Job 2, first pass: pick and group remarkable lines into highlights. */
  draftRecap(lines: LineForRecap[], feedback: string[]): Promise<DraftHighlight[]>;

  /**
   * Job 2, second pass: given a group's sentence and the lines attached to
   * it, return the ids of the lines the sentence truly describes.
   */
  confirmGroup(claim: string, lines: LineForRecap[]): Promise<string[]>;
}

/** No key (or no provider) configured. */
export class AiUnavailableError extends ApiError {
  constructor(message = "The AI is not configured: set the ANTHROPIC_API_KEY secret (locally, in server/.dev.vars).") {
    super(503, "ai_unavailable", message);
  }
}

/** The model declined (stop_reason "refusal"), after any server-side fallback. */
export class AiRefusedError extends ApiError {
  constructor(category: string | null) {
    super(502, "ai_refused", "The model declined this request.", { category });
  }
}

/** The model's output could not be used (not JSON, cut off, wrong shape). Retryable. */
export class AiOutputError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AiOutputError";
  }
}

/** Any other failure talking to the API. */
export class AiFailedError extends ApiError {
  constructor(message: string, status = 502, code = "ai_failed") {
    super(status, code, message);
  }
}
