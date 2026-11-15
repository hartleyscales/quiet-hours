/**
 * Generating, storing and reading the hour told back.
 *
 * A recap row stores the highlights (each with the ids of the stored lines it
 * came from) and a snapshot of the stats at generation time. When a recap is
 * read, its stats are recomputed from participation rows instead of read
 * from the snapshot: leaves and reach counts can be reported after the
 * window, even after toldAt, and the recap must agree with /v1/state's
 * numbers. The snapshot stays in the row as a record of what the numbers
 * were when the recap was written.
 */
import { buildRecap, type Highlight } from "./ai/recap";
import type { AiProvider } from "./ai/types";
import { getWeek, type Week } from "./db";
import { afterNumbers, rawCounts } from "./numbers";
import { iso } from "./time";

export interface RecapStats {
  in: number;
  /** Sum of what phones reported. Approximate; see migrations/0002. */
  approxReaches: number;
  secondsGivenBack: number;
  hoursGivenBack: number;
  stayed: { count: number; of: number; share: number | null };
  /** Lines that were visible and given to the AI when the recap was written. */
  lines: number;
  /** Lines not used because they had not (yet) passed the editing check. */
  linesNotShown: number;
}

async function stats(db: D1Database, week: Week, lines: number, linesNotShown: number): Promise<RecapStats> {
  return { ...afterNumbers(await rawCounts(db, week)), lines, linesNotShown };
}

export async function generateAndStoreRecap(db: D1Database, ai: AiProvider, week: Week, now: number) {
  const { results } = await db
    .prepare("SELECT id, text, moderation FROM lines WHERE week_id = ? ORDER BY id")
    .bind(week.id)
    .all<{ id: string; text: string; moderation: string }>();
  const visible = results.filter((l) => l.moderation === "ok").map((l) => ({ id: l.id, text: l.text }));
  const notShown = results.length - visible.length;

  const result = await buildRecap(ai, visible);
  const snapshot = await stats(db, week, visible.length, notShown);
  const generator = visible.length === 0 ? "none (no lines)" : `${ai.id}: ${ai.models.recap} + ${ai.models.recapCheck}`;

  await db
    .prepare(
      `INSERT OR REPLACE INTO recaps (week_id, highlights_json, stats_json, generator, generated_at, attempts, dropped_json, is_demo)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      week.id,
      JSON.stringify(result.highlights),
      JSON.stringify(snapshot),
      generator,
      now,
      result.attempts,
      JSON.stringify(result.dropped),
      week.isDemo ? 1 : 0,
    )
    .run();
  return { ...(await readRecap(db, week.id))!, attempts: result.attempts, dropped: result.dropped };
}

export interface RecapView {
  weekId: string;
  generatedAt: string;
  generator: string;
  highlights: (Highlight & { lines: { id: string; text: string }[] })[];
  stats: RecapStats;
}

/** The stored recap, with the text of every line each highlight came from and stats as of now. */
export async function readRecap(db: D1Database, weekId: string): Promise<RecapView | null> {
  const r = await db.prepare("SELECT * FROM recaps WHERE week_id = ?").bind(weekId).first<Record<string, unknown>>();
  const week = r ? await getWeek(db, weekId) : null;
  if (!r || !week) return null;
  const highlights = JSON.parse(String(r.highlights_json)) as Highlight[];
  const snapshot = JSON.parse(String(r.stats_json)) as Partial<RecapStats>;
  const { results } = await db
    .prepare("SELECT id, text FROM lines WHERE week_id = ? AND moderation = 'ok'")
    .bind(weekId)
    .all<{ id: string; text: string }>();
  const text = new Map(results.map((l) => [l.id, l.text]));
  return {
    weekId,
    generatedAt: iso(Number(r.generated_at)),
    generator: String(r.generator),
    highlights: highlights.map((h) => ({
      ...h,
      lines: h.lineIds.filter((id) => text.has(id)).map((id) => ({ id, text: text.get(id)! })),
    })),
    stats: await stats(db, week, Number(snapshot.lines ?? 0), Number(snapshot.linesNotShown ?? 0)),
  };
}
