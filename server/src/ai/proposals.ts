/**
 * Window proposals (contract, AI job 1), checked in code.
 *
 * A draft is accepted only if it has exactly three windows and each one:
 *   - is a real campus-local time (not in the hour skipped by daylight saving),
 *   - starts at or after the week's voteClosesAt and ends at least 15
 *     minutes before its toldAt (the hour is told back 15 minutes after the
 *     window ends),
 *   - lasts 30 minutes to 4 hours,
 *   - is not identical to another window in the draft,
 *   - has a reason that passes reasonProblem: one line, at most MAX_REASON
 *     characters, at most two sentences. The same check applies to options
 *     an admin sets (admin.ts, setOptions), and the demo seed's reasons pass it.
 * Otherwise the draft is retried (up to MAX_ATTEMPTS) with the reasons.
 */
import type { Week } from "../db";
import { TOLD_AFTER_END_MS } from "../phase";
import { formatLocal, iso, parseLocal } from "../time";
import type { CampusWeek } from "./campus-week";
import { AiOutputError, type AiProvider, type DraftProposal } from "./types";

export const MAX_ATTEMPTS = 3;
export const MIN_MINUTES = 30;
export const MAX_MINUTES = 240;
/** A window's reason sits in small type under its day and time: about two short lines. */
export const MAX_REASON = 70;
export const MAX_REASON_SENTENCES = 2;

export interface Proposal {
  startsAt: string;
  endsAt: string;
  startLocal: string;
  endLocal: string;
  minutes: number;
  reason: string;
}

export interface ProposalWindowBounds {
  earliestStart: number;
  latestEnd: number;
}

/** Bounds for a week: after the vote closes, and done in time to tell the hour back by toldAt. */
export function boundsFor(week: Week): ProposalWindowBounds {
  return { earliestStart: Math.ceil(week.voteClosesAt / 60_000) * 60_000, latestEnd: week.toldAt - TOLD_AFTER_END_MS };
}

/** How many sentences: each sentence end followed by another sentence starts a new one. */
export function sentenceCount(text: string): number {
  // Abbreviations such as "p.m.", "U.S." or "vs." are not sentence ends.
  const plain = text.replace(/\b(?:[A-Za-z]\.){2,}|\b(?:vs|Dr|St|Mr|Ms|Mrs|Jr|Sr|No|approx|etc)\./g, "abbr");
  return (plain.match(/[.!?]["')\]]?\s+["'(]?[A-Z0-9]/g) ?? []).length + 1;
}

/**
 * What is wrong with a window's reason, or null if nothing is. The one check
 * for every path a reason comes in by: AI proposals, options an admin sets,
 * and (by test) the demo seed.
 */
export function reasonProblem(reason: string): string | null {
  if (!reason) return "has no reason";
  if (/[\r\n]/.test(reason)) return "reason must be on one line";
  if (reason.length > MAX_REASON) {
    return `reason is ${reason.length} characters; it must be at most ${MAX_REASON}, short enough to read at a glance`;
  }
  const sentences = sentenceCount(reason);
  if (sentences > MAX_REASON_SENTENCES) return `reason has ${sentences} sentences; it must be one or two short sentences`;
  return null;
}

export function validateProposals(
  drafts: DraftProposal[],
  bounds: ProposalWindowBounds,
): { ok: true; proposals: Proposal[] } | { ok: false; reasons: string[] } {
  const reasons: string[] = [];
  if (!Array.isArray(drafts) || drafts.length !== 3) {
    return { ok: false, reasons: [`expected exactly 3 windows, got ${Array.isArray(drafts) ? drafts.length : "none"}`] };
  }
  const proposals: Proposal[] = [];
  drafts.forEach((d, i) => {
    const n = `window ${i + 1}`;
    const start = typeof d?.startLocal === "string" ? parseLocal(d.startLocal) : null;
    const end = typeof d?.endLocal === "string" ? parseLocal(d.endLocal) : null;
    if (start === null || end === null) {
      reasons.push(`${n}: start and end must be real campus-local times written YYYY-MM-DDTHH:MM`);
      return;
    }
    const minutes = Math.round((end - start) / 60_000);
    if (minutes < MIN_MINUTES || minutes > MAX_MINUTES) {
      reasons.push(`${n}: lasts ${minutes} minutes; it must last ${MIN_MINUTES} to ${MAX_MINUTES} minutes`);
    }
    if (start < bounds.earliestStart) reasons.push(`${n}: starts before ${formatLocal(bounds.earliestStart)}, when the vote closes`);
    if (end > bounds.latestEnd) reasons.push(`${n}: ends after ${formatLocal(bounds.latestEnd)}, too late for the hour to be told back in time`);
    const reason = typeof d.reason === "string" ? d.reason.trim() : "";
    const problem = reasonProblem(reason);
    if (problem) reasons.push(`${n}: ${problem}`);
    proposals.push({ startsAt: iso(start), endsAt: iso(end), startLocal: formatLocal(start), endLocal: formatLocal(end), minutes, reason });
  });
  const keys = proposals.map((p) => `${p.startsAt}/${p.endsAt}`);
  if (new Set(keys).size !== keys.length) reasons.push("two windows are identical");
  return reasons.length ? { ok: false, reasons } : { ok: true, proposals };
}

export async function proposeWindows(ai: AiProvider, week: Week, campusWeek: CampusWeek) {
  const bounds = boundsFor(week);
  const request = {
    campusWeek,
    earliestStartLocal: formatLocal(bounds.earliestStart),
    latestEndLocal: formatLocal(bounds.latestEnd),
  };
  let feedback: string[] = [];
  const rejected: { attempt: number; reasons: string[] }[] = [];
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    let drafts: DraftProposal[];
    try {
      drafts = await ai.proposeWindows(request, feedback);
    } catch (err) {
      if (!(err instanceof AiOutputError)) throw err;
      feedback = [err.message];
      rejected.push({ attempt, reasons: feedback });
      continue;
    }
    const v = validateProposals(drafts, bounds);
    if (v.ok) return { proposals: v.proposals, attempts: attempt, rejected };
    feedback = v.reasons;
    rejected.push({ attempt, reasons: v.reasons });
  }
  return { proposals: null, attempts: MAX_ATTEMPTS, rejected };
}
