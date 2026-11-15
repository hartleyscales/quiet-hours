// Times, dates and numbers, written the way the mocks write them, always in campus time.
export const TZ = "America/Los_Angeles";

const parts = new Intl.DateTimeFormat("en-US", {
  timeZone: TZ, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", weekday: "long",
});

/** The campus wall clock at an instant. */
export function wall(ms) {
  const o = {};
  for (const p of parts.formatToParts(new Date(ms))) if (p.type !== "literal") o[p.type] = p.value;
  return { y: +o.year, mo: +o.month, d: +o.day, h: +o.hour % 24, mi: +o.minute, weekday: o.weekday };
}

const t = (v) => (typeof v === "number" ? v : Date.parse(v));
const dayKey = (w) => w.y * 10000 + w.mo * 100 + w.d;
/** Whole calendar days from `now` to `ms`, in campus time (0 = same day, 1 = tomorrow, -1 = yesterday). */
export function dayDiff(ms, now) {
  const a = wall(t(ms)), b = wall(t(now));
  return Math.round((Date.UTC(a.y, a.mo - 1, a.d) - Date.UTC(b.y, b.mo - 1, b.d)) / 86_400_000);
}
export const sameDay = (a, b) => dayKey(wall(t(a))) === dayKey(wall(t(b)));

/** "7:00" */
export function clock(ms) {
  const w = wall(t(ms));
  return `${w.h % 12 || 12}:${String(w.mi).padStart(2, "0")}`;
}
const meridiem = (ms) => (wall(t(ms)).h < 12 ? "AM" : "PM");
/** "8:00 PM" */
export const clockAmPm = (ms) => `${clock(ms)} ${meridiem(ms)}`;
/** "5:00 – 7:00 PM", or "11:30 AM – 1:00 PM" across noon. */
export function range(a, b) {
  return meridiem(a) === meridiem(b) ? `${clock(a)} – ${clock(b)} ${meridiem(b)}` : `${clockAmPm(a)} – ${clockAmPm(b)}`;
}
/** "Thursday" */
export const weekday = (ms) => wall(t(ms)).weekday;
/** "Today", "Yesterday" or "Thursday", for a day near now. */
export function dayName(ms, now) {
  const d = dayDiff(ms, now);
  return d === 0 ? "Today" : d === -1 ? "Yesterday" : weekday(ms);
}
/** "today" or "Tuesday", inside a sentence. */
export const dayInSentence = (ms, now) => (dayDiff(ms, now) === 0 ? "today" : weekday(ms));

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
/** "In 2 days, 4 hours", "In 3 hours, 12 minutes", "In 8 minutes". */
export function until(ms, now) {
  const mins = Math.max(1, Math.ceil((t(ms) - t(now)) / 60_000));
  const days = Math.floor(mins / 1440), hours = Math.floor((mins % 1440) / 60), m = mins % 60;
  if (days) return `In ${plural(days, "day", "days")}${hours ? `, ${plural(hours, "hour", "hours")}` : ""}`;
  if (hours) return `In ${plural(hours, "hour", "hours")}${m ? `, ${plural(m, "minute", "minutes")}` : ""}`;
  return `In ${plural(m, "minute", "minutes")}`;
}

/** "3,112" */
export const num = (n) => (Number(n) || 0).toLocaleString("en-US", { maximumFractionDigits: 1 });

/** A countdown in short form, for the Homes' figures: "1d 20h", "3h 12m", "8m". */
export function short(ms, now) {
  const mins = Math.max(1, Math.ceil((t(ms) - t(now)) / 60_000));
  const days = Math.floor(mins / 1440), hours = Math.floor((mins % 1440) / 60), m = mins % 60;
  if (days) return `${days}d ${hours}h`;
  if (hours) return `${hours}h ${m}m`;
  return `${m}m`;
}

/** How long ago, in short form, for a post: "2m", "1h", "3d" ("now" under a minute). */
export function ago(ms, now) {
  const mins = Math.floor((t(now) - t(ms)) / 60_000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h`;
  return `${Math.floor(mins / 1440)}d`;
}

/** "Thursday morning", "today at 9:00 AM": when something opens, inside a sentence. */
export function opensWhen(ms, now) {
  const w = wall(t(ms)), d = dayInSentence(ms, now);
  return w.h === 0 && w.mi === 0 ? `${d === "today" ? "this" : d} morning` : `${d} at ${clockAmPm(ms)}`;
}
