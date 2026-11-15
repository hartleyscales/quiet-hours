/**
 * DEVELOPMENT-ONLY FAKE AI. Not a model; a few deterministic rules so the
 * whole week can be exercised locally without an API key. Enabled only by
 * AI_MODE=DEV_FAKE_AI_NOT_REAL, which readConfig() refuses outside
 * ENVIRONMENT=development. Everything it writes says it is fake.
 *
 * Its output goes through exactly the same validation as the real model's.
 */
import { formatLocal, parseLocal } from "../time";
import { ASKED_HIGHLIGHT_TEXT, MAX_HIGHLIGHTS } from "./recap";
import type {
  AiProvider,
  DraftHighlight,
  DraftProposal,
  LineForRecap,
  ModerationVerdict,
  ProposalRequest,
} from "./types";

const ABUSIVE = /\b(idiot|stupid|loser|moron|hate you|kill|ugly|shut up)\b/i;
const HANDLE_OR_PHONE = /@\w|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/;

/** Themes the fake can group by. Each label is only applied to lines its pattern matches. */
const THEMES: { label: string; pattern: RegExp }[] = [
  { label: "called or facetimed someone they love", pattern: /\b(called|phoned|facetimed|face-timed)\b/i },
  { label: "went outside for a walk", pattern: /\bwalk(ed)?\b/i },
  { label: "read something", pattern: /\b(read|reading)\b/i },
  { label: "cooked or ate with others", pattern: /\b(cooked|dinner|ate)\b/i },
  { label: "fell asleep", pattern: /\b(slept|nap|napped|asleep)\b/i },
];

export class FakeAi implements AiProvider {
  readonly id = "dev-fake-ai";
  readonly models = {
    proposals: "dev-fake-ai (not a model)",
    recap: "dev-fake-ai (not a model)",
    moderation: "dev-fake-ai (not a model)",
    recapCheck: "dev-fake-ai (not a model)",
  };

  async moderate(text: string): Promise<ModerationVerdict> {
    if (HANDLE_OR_PHONE.test(text)) return { show: false, reason: "names_or_targets_person" };
    if (ABUSIVE.test(text)) return { show: false, reason: "abusive" };
    return { show: true, reason: "ok" };
  }

  async proposeWindows(req: ProposalRequest): Promise<DraftProposal[]> {
    const earliest = parseLocal(req.earliestStartLocal)!;
    const latest = parseLocal(req.latestEndLocal)!;
    const hour = 3600_000;
    const start = Math.ceil(earliest / hour) * hour;
    const span = latest - start;
    // Three windows spread over the allowed span, 60 / 90 / 120 minutes long.
    const lengths = [60, 90, 120].map((m) => m * 60_000);
    return lengths.map((len, i) => {
      const s = start + Math.floor(((span - len) * i) / 3 / 60_000) * 60_000;
      return {
        startLocal: formatLocal(s),
        endLocal: formatLocal(s + len),
        reason: `[FAKE AI, development only] Option ${i + 1}, picked by a fixed rule.`,
      };
    });
  }

  async draftRecap(lines: LineForRecap[]): Promise<DraftHighlight[]> {
    const out: DraftHighlight[] = [];
    const used = new Set<string>();
    for (const theme of THEMES) {
      const ids = lines.filter((l) => !used.has(l.id) && theme.pattern.test(l.text)).map((l) => l.id);
      if (ids.length >= 2) {
        out.push({ kind: "group", text: `${ids.length} people ${theme.label}`, lineIds: ids });
        ids.forEach((id) => used.add(id));
      }
    }
    const rest = lines
      .filter((l) => !used.has(l.id) && l.text.length <= ASKED_HIGHLIGHT_TEXT)
      .sort((a, b) => b.text.length - a.text.length);
    for (const l of rest.slice(0, 3)) out.push({ kind: "quote", text: l.text, lineIds: [l.id] });
    return out.slice(0, MAX_HIGHLIGHTS);
  }

  async confirmGroup(claim: string, lines: LineForRecap[]): Promise<string[]> {
    const theme = THEMES.find((t) => claim.endsWith(t.label));
    return theme ? lines.filter((l) => theme.pattern.test(l.text)).map((l) => l.id) : [];
  }
}
