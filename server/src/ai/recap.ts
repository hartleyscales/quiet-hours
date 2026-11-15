/**
 * The hour told back (contract, AI job 2), with its rules enforced in code.
 *
 * The model only drafts. Before anything is stored:
 *   1. Structure: every highlight names the stored lines it came from, by id,
 *      and every id must be a visible line of this week.
 *   2. Quotes: exactly one line, and the text shown is the stored text of that
 *      line, never the model's copy. Nothing can be embellished.
 *   3. Groups: two or more lines. The sentence must contain exactly one
 *      number, in digits, equal to the number of ids attached, and no other
 *      number or amount word ("several", "most", "half", "dozen", ...).
 *   4. Groups again: a second model pass checks every attached line against
 *      the sentence. Lines it does not describe are removed and the number is
 *      re-rendered from the ids that remain, so the count stays equal to the
 *      ids attached. A group left with fewer than two lines is dropped.
 *   5. Size (docs/CONTRACT.md: at most five highlights of about 55
 *      characters each): the model is asked for at most MAX_HIGHLIGHTS, each
 *      at most ASKED_HIGHLIGHT_TEXT characters. Drafts past MAX_HIGHLIGHTS
 *      are dropped, and so is any highlight whose text is longer than
 *      MAX_HIGHLIGHT_TEXT, the hard cap. A quote is never shortened (it is
 *      the stored line), so a quote of a longer line is dropped.
 * Drafts that fail are dropped with a reason; if too much is dropped the
 * whole draft is retried (up to MAX_ATTEMPTS) with the reasons as feedback.
 */
import { AiOutputError, type AiProvider, type DraftHighlight, type LineForRecap } from "./types";

export const MAX_ATTEMPTS = 3;
export const MAX_HIGHLIGHTS = 5;
/** What the prompt asks for ("about 55 characters" in the contract). */
export const ASKED_HIGHLIGHT_TEXT = 55;
/** The hard cap enforced in code: a little slack over what is asked, never more. */
export const MAX_HIGHLIGHT_TEXT = 60;

export interface Highlight {
  kind: "quote" | "group";
  text: string;
  lineIds: string[];
  /** For groups, the number of lines (always lineIds.length). Null for quotes. */
  count: number | null;
}

export interface Dropped {
  draft: unknown;
  reason: string;
}

const NUMBER_WORDS = [
  "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
  "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty",
  "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "hundreds", "thousand", "thousands", "million",
  "dozen", "dozens", "both", "twice", "thrice", "couple", "pair",
];
const AMOUNT_WORDS = [
  "few", "several", "many", "most", "half", "majority", "minority", "all", "every", "everyone", "everybody",
  "nobody", "none", "lots", "plenty", "numerous", "countless", "handful", "percent", "bunch", "tons", "whole",
];
const FORBIDDEN_WORD = new RegExp(`\\b(${[...NUMBER_WORDS, ...AMOUNT_WORDS].join("|")})\\b`, "i");

/** Checks one drafted highlight against the stored lines. */
export function validateHighlight(
  draft: DraftHighlight,
  lines: ReadonlyMap<string, string>,
): { ok: true; highlight: Highlight } | { ok: false; reason: string } {
  if (!draft || typeof draft !== "object") return { ok: false, reason: "not an object" };
  const ids = Array.isArray(draft.lineIds) ? draft.lineIds : null;
  if (!ids || ids.length === 0) return { ok: false, reason: "no line ids attached" };
  if (ids.some((id) => typeof id !== "string")) return { ok: false, reason: "a line id is not a string" };
  if (new Set(ids).size !== ids.length) return { ok: false, reason: "the same line id is attached twice" };
  const unknown = ids.find((id) => !lines.has(id));
  if (unknown !== undefined) return { ok: false, reason: `line id ${JSON.stringify(unknown)} is not one of the lines given` };

  if (draft.kind === "quote") {
    if (ids.length !== 1) return { ok: false, reason: "a quote must carry exactly one line id" };
    const stored = lines.get(ids[0]!)!;
    if (stored.length > MAX_HIGHLIGHT_TEXT) {
      return { ok: false, reason: `quoted line ${ids[0]} is longer than ${MAX_HIGHLIGHT_TEXT} characters; quote only short lines` };
    }
    return { ok: true, highlight: { kind: "quote", text: stored, lineIds: [...ids], count: null } };
  }

  if (draft.kind !== "group") return { ok: false, reason: `unknown kind ${JSON.stringify(draft.kind)}` };
  if (ids.length < 2) return { ok: false, reason: "a group must carry at least two line ids" };
  const text = typeof draft.text === "string" ? draft.text.trim() : "";
  if (!text) return { ok: false, reason: "a group has no sentence" };
  if (text.length > MAX_HIGHLIGHT_TEXT) {
    return { ok: false, reason: `a group sentence is longer than ${MAX_HIGHLIGHT_TEXT} characters: ${JSON.stringify(text)}` };
  }
  if (/[\r\n]/.test(text)) return { ok: false, reason: "a group sentence spans more than one line" };
  const numbers = text.match(/\d+(?:[.,]\d+)*/g) ?? [];
  if (numbers.length !== 1) {
    return { ok: false, reason: `a group sentence must contain exactly one number (its count); found ${numbers.length}: ${JSON.stringify(text)}` };
  }
  if (Number(numbers[0]) !== ids.length) {
    return { ok: false, reason: `count mismatch: the sentence says ${numbers[0]} but ${ids.length} line ids are attached: ${JSON.stringify(text)}` };
  }
  const word = FORBIDDEN_WORD.exec(text);
  if (word) return { ok: false, reason: `a group sentence uses the amount word "${word[1]}": ${JSON.stringify(text)}` };
  return { ok: true, highlight: { kind: "group", text, lineIds: [...ids], count: ids.length } };
}

/**
 * Applies the second-pass check to a validated group: keeps only the lines
 * the sentence describes and re-renders the count from them. Null if fewer
 * than two remain.
 */
export function applyGroupCheck(h: Highlight, confirmed: ReadonlySet<string>): Highlight | null {
  const kept = h.lineIds.filter((id) => confirmed.has(id));
  if (kept.length < 2) return null;
  if (kept.length === h.lineIds.length) return h;
  return { kind: "group", text: h.text.replace(/\d+(?:[.,]\d+)*/, String(kept.length)), lineIds: kept, count: kept.length };
}

/** Last line of defence before storage: the invariants, asserted. */
export function assertRecapInvariants(highlights: Highlight[], lines: ReadonlyMap<string, string>): void {
  if (highlights.length > MAX_HIGHLIGHTS) throw new Error(`more than ${MAX_HIGHLIGHTS} highlights`);
  for (const h of highlights) {
    if (h.text.length > MAX_HIGHLIGHT_TEXT) throw new Error(`highlight longer than ${MAX_HIGHLIGHT_TEXT} characters`);
    if (h.lineIds.length === 0 || h.lineIds.some((id) => !lines.has(id))) throw new Error("highlight without traceable lines");
    if (h.kind === "quote" && (h.lineIds.length !== 1 || h.text !== lines.get(h.lineIds[0]!))) throw new Error("quote is not verbatim");
    if (h.kind === "group") {
      const nums = h.text.match(/\d+(?:[.,]\d+)*/g) ?? [];
      if (h.count !== h.lineIds.length || nums.length !== 1 || Number(nums[0]) !== h.lineIds.length) {
        throw new Error("group count does not equal the ids attached");
      }
    }
  }
}

export interface RecapResult {
  highlights: Highlight[];
  dropped: Dropped[];
  attempts: number;
}

/**
 * Drafts, validates, checks and (if needed) retries. Returns the best attempt.
 * Throws only for provider errors (unavailable, refused, failed) or if no
 * attempt produced usable output at all.
 */
export async function buildRecap(ai: AiProvider, lines: LineForRecap[]): Promise<RecapResult> {
  if (lines.length === 0) return { highlights: [], dropped: [], attempts: 0 };
  const byId = new Map(lines.map((l) => [l.id, l.text]));
  let best: RecapResult | null = null;
  let feedback: string[] = [];
  let lastOutputError: AiOutputError | null = null;
  let attempts = 0;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    attempts = attempt;
    let drafts: DraftHighlight[];
    try {
      drafts = await ai.draftRecap(lines, feedback);
    } catch (err) {
      if (err instanceof AiOutputError) {
        lastOutputError = err;
        feedback = [err.message];
        continue;
      }
      throw err;
    }

    const kept: Highlight[] = [];
    const dropped: Dropped[] = [];
    for (const d of drafts.slice(0, MAX_HIGHLIGHTS)) {
      const v = validateHighlight(d, byId);
      if (!v.ok) {
        dropped.push({ draft: d, reason: v.reason });
        continue;
      }
      if (v.highlight.kind === "group") {
        const groupLines = v.highlight.lineIds.map((id) => ({ id, text: byId.get(id)! }));
        const confirmed = new Set(await ai.confirmGroup(v.highlight.text, groupLines));
        const checked = applyGroupCheck(v.highlight, confirmed);
        if (!checked) {
          dropped.push({ draft: d, reason: `fewer than two of its lines match the sentence ${JSON.stringify(v.highlight.text)}` });
          continue;
        }
        if (checked !== v.highlight) {
          const removed = v.highlight.lineIds.filter((id) => !confirmed.has(id));
          dropped.push({ draft: d, reason: `lines ${removed.join(", ")} do not match the sentence; count re-rendered to ${checked.count}` });
        }
        kept.push(checked);
      } else {
        kept.push(v.highlight);
      }
    }
    for (const d of drafts.slice(MAX_HIGHLIGHTS)) dropped.push({ draft: d, reason: `more than ${MAX_HIGHLIGHTS} highlights` });

    const result: RecapResult = { highlights: kept, dropped, attempts: attempt };
    if (!best || kept.length > best.highlights.length) best = result;
    // Good enough: the draft was mostly usable (or deliberately empty).
    const rejected = dropped.filter((d) => !d.reason.includes("count re-rendered")).length;
    if (rejected === 0 || (kept.length > 0 && rejected <= kept.length / 2)) {
      best = result;
      break;
    }
    feedback = dropped.map((d) => d.reason);
  }

  if (!best) throw lastOutputError ?? new AiOutputError("No usable recap draft.");
  assertRecapInvariants(best.highlights, byId);
  return { ...best, attempts };
}
