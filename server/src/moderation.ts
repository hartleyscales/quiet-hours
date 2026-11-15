/**
 * The editing check (contract, AI job 3): board posts and lines that name or
 * target a person, or that are abusive, are not shown.
 *
 * Fail closed. Text is shown only after the check says "ok":
 *   ok        stored as 'ok', shown
 *   rejected  not stored; the writer gets 422 not_shown and can rewrite
 *   pending   the check could not run (no key, API down): stored as 'pending',
 *             NOT shown, until POST /v1/admin/weeks/:id/moderate re-runs it
 */
import type { AiProvider, ModerationReason } from "./ai/types";
import { ApiError, unprocessable } from "./errors";

export type CheckOutcome =
  | { state: "ok" }
  | { state: "pending"; note: string }
  | { state: "rejected"; reason: Exclude<ModerationReason, "ok"> };

export async function checkText(ai: AiProvider | null, text: string, kind: "board_post" | "line"): Promise<CheckOutcome> {
  if (!ai) return { state: "pending", note: "ai_unavailable" };
  try {
    const v = await ai.moderate(text, kind);
    return v.show ? { state: "ok" } : { state: "rejected", reason: v.reason === "ok" ? "abusive" : v.reason };
  } catch (err) {
    return { state: "pending", note: err instanceof ApiError ? err.code : "check_failed" };
  }
}

const MESSAGES: Record<Exclude<ModerationReason, "ok">, string> = {
  names_or_targets_person: "This can't be shown: it names or points at a specific person.",
  abusive: "This can't be shown: it reads as abusive.",
  check_declined: "This can't be shown: the editing check declined it.",
};

export function notShown(reason: Exclude<ModerationReason, "ok">): ApiError {
  return unprocessable("not_shown", MESSAGES[reason], { reason });
}
