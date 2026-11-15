/**
 * The "campus week": the input to window proposals (contract, AI job 1).
 * Hand-written or exported from campus systems by whoever runs the week;
 * the server never scrapes anything. Example: examples/campus-week.example.json.
 *
 * All local dates and times are America/Los_Angeles.
 *   date        "YYYY-MM-DD"
 *   local time  "YYYY-MM-DDTHH:MM"
 *   clock time  "HH:MM"
 */
import { z } from "zod";

const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "expected YYYY-MM-DD");
const localTime = z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/, "expected YYYY-MM-DDTHH:MM (campus local time)");
const clock = z.string().regex(/^\d{2}:\d{2}$/, "expected HH:MM");
const text = (max: number) => z.string().trim().min(1).max(max);
const count = z.number().int().min(0).max(1_000_000);

export const CampusWeekSchema = z
  .object({
    /** The Monday that starts the week. */
    weekOf: date,
    timezone: z.literal("America/Los_Angeles"),
    /** Students on campus, for scale. */
    population: z.object({ students: count, livingOnCampus: count.optional() }).strict(),
    /**
     * Students sitting in a scheduled class, per local hour of each day.
     * studentsInClassByHour[h] covers h:00-h:59. Exactly 24 numbers.
     */
    classLoad: z
      .array(z.object({ date, studentsInClassByHour: z.array(count).length(24) }).strict())
      .min(1)
      .max(7),
    games: z
      .array(
        z
          .object({
            title: text(120),
            sport: text(40),
            startLocal: localTime,
            endLocal: localTime.optional(),
            venue: text(120),
            home: z.boolean(),
            expectedAttendance: count.optional(),
          })
          .strict(),
      )
      .max(20)
      .default([]),
    exams: z
      .array(
        z
          .object({
            date,
            title: text(120),
            scope: z.enum(["campus-wide", "school", "large-course"]),
            studentsAffected: count.optional(),
            note: text(300).optional(),
          })
          .strict(),
      )
      .max(40)
      .default([]),
    sunset: z.array(z.object({ date, sunsetLocal: clock }).strict()).max(7).default([]),
    /** Anything else worth knowing (a holiday, a big campus event, a closure). */
    notes: z.array(text(300)).max(20).default([]),
  })
  .strict();

export type CampusWeek = z.infer<typeof CampusWeekSchema>;
