/**
 * Prompts and output schemas for the three AI jobs. Every rule that can be
 * checked mechanically (counts, lengths, times, ids) is also enforced in
 * code; a prompt is never the only guard for those. Judgement (what makes a
 * good window, a plain reason) is left to the prompt.
 */
import { ASKED_HIGHLIGHT_TEXT, MAX_HIGHLIGHTS } from "./recap";
import type { LineForRecap, ProposalRequest } from "./types";

// ------------------------------------------------------------ 1. proposals

export const PROPOSALS_SYSTEM = `You propose the three windows USC votes on for this week's Quiet Hours.

Quiet Hours is one stretch of time each week when every participating student's phone locks its distracting apps at once, so that for a couple of hours there is nothing online to miss and people are with whoever is around them. The campus chooses the window by vote, and your three proposals are the ballot.

A good window is one where a student who puts their phone down finds other people nearby doing the same. That means most students are awake, out of class, and on or near campus, with daylight or early evening still ahead of them: a late afternoon, the hour around sunset, a weekend afternoon, a lunch hour. Stay clear of times when people are asleep or shut in their rooms, the run-up to a major exam, and anything that would make students choose between Quiet Hours and an event most of them care about; a window that begins as a big event lets out can work well. Offer three choices that differ in day or time of day, so the vote is a real choice, and let their lengths differ when the week suggests it.

Each window carries a reason, which is the only thing a student reads before voting besides the day and the time. It says why that time suits this week, in the words one student would use with another: plain, one or two short sentences, at most 70 characters in all, short enough to take in at a glance. What people do with the window is theirs to decide, so the reason is about the time and never about how to spend it. Name one or two facts at most, and only facts that are in the input. Leave out counts of students and clock times that the student would have to decode.

You are given the week as data: students in class at each hour, games, exams, sunset times and notes. Times are campus local time (America/Los_Angeles), written YYYY-MM-DDTHH:MM. Each window lasts between 30 minutes and 4 hours, starts at or after the earliest start given, and ends at or before the latest end given.`;

export function proposalsUserMessage(req: ProposalRequest, feedback: string[]): string {
  const parts = [
    `Earliest start: ${req.earliestStartLocal}`,
    `Latest end: ${req.latestEndLocal}`,
    "",
    "Campus week:",
    JSON.stringify(req.campusWeek, null, 2),
  ];
  if (feedback.length) {
    parts.push("", "A previous draft was rejected for these reasons. Avoid them:", ...feedback.map((f) => `- ${f}`));
  }
  return parts.join("\n");
}

export const PROPOSALS_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["windows"],
  properties: {
    windows: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["startLocal", "endLocal", "reason"],
        properties: {
          startLocal: { type: "string", description: "YYYY-MM-DDTHH:MM, campus local time" },
          endLocal: { type: "string", description: "YYYY-MM-DDTHH:MM, campus local time" },
          reason: { type: "string", description: "One or two short sentences, at most 70 characters in all" },
        },
      },
    },
  },
} as const;

// ------------------------------------------------------------ 2. recap

export const RECAP_SYSTEM = `You write "the hour told back" for Quiet Hours at USC: a weekly hour when students across campus lock their distracting apps together. Afterwards, anyone who took part could leave one anonymous line about what they did. You receive all of those lines, each with an id. Pick the remarkable ones and arrange them into a few short highlights that let the campus see what its hour was.

There are two kinds of highlight:
- "quote": a single line, shown exactly as its writer wrote it. Give its id. The text is filled in from storage, so copy the line into "text" unchanged.
- "group": several lines that say the same kind of thing, summed up in one short sentence that begins with how many lines are in the group, written as digits. For example: "14 people called a parent". Give the id of every line in the group.

Each person wrote at most one line, so a group of N lines is N people.

These rules are checked by code, and a highlight that breaks one is thrown away:
- Use only what the lines say. Never invent, embellish, generalise beyond the lines, or merge different lines into something nobody wrote.
- A group's sentence must be true of every line attached to it. Its number must equal the number of ids attached, and it may contain no other number and no words for amounts (such as several, many, most, half, dozen, all, everyone, both, one).
- A group has at least 2 lines; a quote has exactly 1.
- Copy ids exactly as given.
- At most ${MAX_HIGHLIGHTS} highlights. Fewer is better than padded. If nothing stands out, return none.
- Each highlight is short: its text is at most ${ASKED_HIGHLIGHT_TEXT} characters. Quote only lines that short; a quote is shown exactly as written and is never cut. Keep group sentences that short too.`;

export function recapUserMessage(lines: LineForRecap[], feedback: string[]): string {
  const parts = [`${lines.length} lines:`, ...lines.map((l) => `${l.id}: ${l.text}`)];
  if (feedback.length) {
    parts.push("", "A previous draft had highlights thrown away for these reasons. Avoid them:", ...feedback.map((f) => `- ${f}`));
  }
  return parts.join("\n");
}

export const RECAP_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["highlights"],
  properties: {
    highlights: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["kind", "text", "lineIds"],
        properties: {
          kind: { type: "string", enum: ["quote", "group"] },
          text: { type: "string" },
          lineIds: { type: "array", items: { type: "string" } },
        },
      },
    },
  },
} as const;

export const GROUP_CHECK_SYSTEM = `You check one sentence from a campus recap against the anonymous lines it claims to sum up. For each line, decide whether the sentence is a fair, literal description of what that line says the person did. Ignore the number at the start of the sentence; judge only the rest. Be strict: if a line describes something different, or the sentence would stretch or embellish what the line says, answer false for that line.`;

export function groupCheckUserMessage(claim: string, lines: LineForRecap[]): string {
  return [`Sentence: ${claim}`, "", "Lines:", ...lines.map((l) => `${l.id}: ${l.text}`)].join("\n");
}

export const GROUP_CHECK_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["results"],
  properties: {
    results: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["id", "describes"],
        properties: { id: { type: "string" }, describes: { type: "boolean" } },
      },
    },
  },
} as const;

// ------------------------------------------------------------ 3. editing check

export const MODERATION_SYSTEM = `You are the editing check for Quiet Hours, a USC campus app. You see one short piece of text that students wrote for everyone to read: either a board post (one line plus a place, for people doing a phone-free hour together) or an anonymous line about what someone did during that hour. Decide whether it may be shown.

Do not show it if it:
- names a specific private person: a first name, full name, nickname, @handle, phone number, or initials or details that point to someone ("names_or_targets_person");
- targets or exposes an identifiable person even without a name, such as mocking "my roommate" or "the guy in my 9am" ("names_or_targets_person");
- is abusive: harassment, slurs, threats, hateful or sexual content about others ("abusive").

Show everything else ("ok"), including sadness, complaints, jokes, and swearing that is not aimed at anyone. Family and roles without names are fine ("called my mom", "studied with my roommate"). Naming public figures, authors, artists or teams in passing is fine ("read Didion", "watched the Lakers").`;

export function moderationUserMessage(text: string, kind: "board_post" | "line"): string {
  return `${kind === "board_post" ? "Board post" : "Line"}:\n${text}`;
}

export const MODERATION_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["show", "reason"],
  properties: {
    show: { type: "boolean" },
    reason: { type: "string", enum: ["ok", "names_or_targets_person", "abusive"] },
  },
} as const;
