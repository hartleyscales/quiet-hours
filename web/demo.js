// The demo strip: shown only when the page is opened with ?demo=<admin secret>, outside the phone.
// Moves the current week through its phases with the admin timeline call. On a demo week (made by the
// server's demo seed) it also runs each seed step once, in its phase, so the campus is populated, and on
// "told" it asks for the recap if there isn't one yet. The secret is only ever held in memory.
import { admin } from "./api.js";
import { wall } from "./format.js";

const ORDER = ["vote", "decided", "live", "ended", "told"];
const SEED_AT = { decided: "decided", live: "live", ended: "ended" }; // seed step to run once the week is in that phase

export function mountDemo(page, secret, { state, now, refresh, fit }) {
  const el = document.createElement("div");
  el.className = "demo";
  const targets = [["voting", "vote"], ["decided", "decided"], ["on the day", "day"], ["live", "live"], ["ended", "ended"], ["told", "told"]];
  el.innerHTML = targets.map(([label, t]) => `<button type="button" data-t="${t}">${label}</button>`).join("") + '<p class="st" aria-live="polite"></p>';
  page.appendChild(el);
  const status = el.querySelector(".st"), buttons = [...el.querySelectorAll("button")];

  const doneKey = (id) => `qh.demoSeeded.${id}`;
  const seeded = (id) => { try { return JSON.parse(localStorage.getItem(doneKey(id)) || "[]"); } catch { return []; } };
  const markSeeded = (id, step) => { try { localStorage.setItem(doneKey(id), JSON.stringify([...new Set([...seeded(id), step])])); } catch {} };

  async function currentWeek() {
    const st = state();
    if (st?.week) return { id: st.week.id, isDemo: st.week.isDemo };
    const { weeks } = await admin.weeks(secret);
    const w = weeks.find((x) => x.phase) ?? null; // the newest week whose vote has opened
    return w && { id: w.id, isDemo: w.isDemo };
  }

  async function seedOnce(week, step, log) {
    if (!week.isDemo || seeded(week.id).includes(step)) return;
    await admin.seed(secret, step);
    markSeeded(week.id, step);
    log.push(`seeded ${step}`);
  }

  /** Brings a demo week through each earlier phase it skipped, so every seed step runs in its own phase. */
  async function catchUp(week, upTo, log) {
    if (!week.isDemo) return;
    for (const phase of ORDER.slice(1, ORDER.indexOf(upTo))) {
      const step = SEED_AT[phase];
      if (!step || seeded(week.id).includes(step)) continue;
      await admin.jump(secret, week.id, phase);
      await seedOnce(week, step, log);
    }
  }

  async function run(target) {
    const log = [];
    let week = await currentWeek();
    if (!week) {
      if (target !== "vote") throw new Error("No week yet. Press voting first.");
      const made = await admin.seed(secret, "week");
      week = { id: made.weekId, isDemo: true };
      markSeeded(week.id, "week");
      return "voting · new demo week";
    }
    const phase = target === "day" ? "decided" : target;
    await catchUp(week, phase, log);
    let view = await admin.jump(secret, week.id, phase);
    if (SEED_AT[phase]) await seedOnce(week, SEED_AT[phase], log);
    if (target === "day") {
      // On the window's own day, before it starts: move the window to later today.
      const t = now(), w = wall(t), startsAt = Date.parse(view.week.startsAt);
      const sameDay = (() => { const a = wall(startsAt); return a.y === w.y && a.mo === w.mo && a.d === w.d; })();
      if (!sameDay) {
        const toMidnight = ((23 - w.h) * 60 + (60 - w.mi)) * 60_000;
        const lead = Math.min(3 * 3600_000, toMidnight - 5 * 60_000);
        if (lead < 60_000) throw new Error("Too close to midnight for “on the day”.");
        view = await admin.shift(secret, week.id, Math.round((t + lead - startsAt) / 1000));
      }
    }
    if (target === "told" && !view.hasRecap) {
      await admin.recap(secret, week.id);
      log.push("recap written");
    }
    return [targets.find(([, t]) => t === target)[0], ...log].join(" · ");
  }

  buttons.forEach((b) => b.addEventListener("click", async () => {
    buttons.forEach((x) => (x.disabled = true));
    status.textContent = "…";
    try {
      status.textContent = await run(b.dataset.t);
    } catch (err) {
      status.textContent = err.code ? `${err.code}: ${err.message}` : err.message;
    } finally {
      buttons.forEach((x) => (x.disabled = false));
      await refresh();
      fit();
    }
  }));
}
