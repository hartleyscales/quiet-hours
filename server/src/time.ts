/**
 * Time zone helpers. The campus clock is America/Los_Angeles; everything is
 * stored as UTC milliseconds and converted only where the contract talks
 * about a calendar day (the board) or where the AI speaks in local time
 * (window proposals).
 */
export const CAMPUS_TZ = "America/Los_Angeles";

export interface WallClock {
  year: number;
  month: number; // 1-12
  day: number;
  hour: number;
  minute: number;
  second: number;
}

const formatters = new Map<string, Intl.DateTimeFormat>();

function formatter(tz: string): Intl.DateTimeFormat {
  let f = formatters.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    formatters.set(tz, f);
  }
  return f;
}

/** The wall-clock reading in `tz` at instant `ms`. */
export function wallClock(ms: number, tz: string = CAMPUS_TZ): WallClock {
  const parts: Record<string, number> = {};
  for (const p of formatter(tz).formatToParts(new Date(ms))) {
    if (p.type !== "literal") parts[p.type] = Number(p.value);
  }
  return {
    year: parts.year!,
    month: parts.month!,
    day: parts.day!,
    hour: parts.hour === 24 ? 0 : parts.hour!,
    minute: parts.minute!,
    second: parts.second!,
  };
}

/** How far `tz` is ahead of UTC at instant `ms`, in milliseconds (LA: -7h or -8h). */
function offsetAt(ms: number, tz: string): number {
  const whole = Math.floor(ms / 1000) * 1000;
  const w = wallClock(whole, tz);
  return Date.UTC(w.year, w.month - 1, w.day, w.hour, w.minute, w.second) - whole;
}

/**
 * The UTC instant at which the wall clock in `tz` reads the given time.
 * Returns null for a wall time that does not exist (the hour skipped when
 * clocks spring forward). For the repeated hour in autumn, returns the first.
 */
export function zonedTimeToUtc(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  tz: string = CAMPUS_TZ,
): number | null {
  const asIfUtc = Date.UTC(year, month - 1, day, hour, minute, 0);
  // Try both offsets around the guess and keep the candidates that round-trip.
  const candidates = new Set<number>();
  for (const probe of [asIfUtc - 12 * 3600_000, asIfUtc, asIfUtc + 12 * 3600_000]) {
    candidates.add(asIfUtc - offsetAt(probe, tz));
  }
  const valid = [...candidates]
    .filter((t) => {
      const w = wallClock(t, tz);
      return w.year === year && w.month === month && w.day === day && w.hour === hour && w.minute === minute;
    })
    .sort((a, b) => a - b);
  return valid[0] ?? null;
}

/** Midnight at the start of the local calendar day that contains `ms`. */
export function startOfLocalDay(ms: number, tz: string = CAMPUS_TZ): number {
  const w = wallClock(ms, tz);
  // Midnight always exists in America/Los_Angeles (changes happen at 02:00).
  return zonedTimeToUtc(w.year, w.month, w.day, 0, 0, tz)!;
}

const pad = (n: number) => String(n).padStart(2, "0");

/** "2026-11-18T21:00" in `tz`. */
export function formatLocal(ms: number, tz: string = CAMPUS_TZ): string {
  const w = wallClock(ms, tz);
  return `${w.year}-${pad(w.month)}-${pad(w.day)}T${pad(w.hour)}:${pad(w.minute)}`;
}

/** Parses "YYYY-MM-DDTHH:MM" as a wall time in `tz`. Null if malformed or nonexistent. */
export function parseLocal(text: string, tz: string = CAMPUS_TZ): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(text.trim());
  if (!m) return null;
  const [y, mo, d, h, mi] = m.slice(1).map(Number) as [number, number, number, number, number];
  if (mo < 1 || mo > 12 || d < 1 || d > 31 || h > 23 || mi > 59) return null;
  return zonedTimeToUtc(y, mo, d, h, mi, tz);
}

export const iso = (ms: number) => new Date(ms).toISOString();
export const isoOrNull = (ms: number | null | undefined) => (ms == null ? null : iso(ms));

/** Parses an ISO 8601 instant that names its offset ("Z" or "+hh:mm"). */
export function parseInstant(text: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/.test(text)) return null;
  const ms = Date.parse(text);
  return Number.isFinite(ms) ? ms : null;
}
