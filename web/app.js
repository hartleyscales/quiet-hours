// Quiet Hours, the web app. One 390 x 844 stage; which screen it shows comes from GET /v1/state.
//
// Where the data comes from: the sample campus in demo-api.js by default (no network, resets on reload), or the
// live API in api.js when the page is told where it is (?api=<base url>, window.QH_API, <meta name="qh-api">).
// Both offer the same calls; nothing below knows which one it has.
import * as f from "./format.js";
import { moonDots, drawMoon } from "./moon.js";
import { howItWorks, drawFilled, drawStill, still, clock, lock, bubble, phone, fill, lightMoon } from "./dotart.js";
import { mountBoard } from "./sheet.js";
import { createMotion, warmStars } from "./motion.js";

const LIVE = new URLSearchParams(location.search).has("api") || typeof window.QH_API === "string" ||
  Boolean(document.querySelector('meta[name="qh-api"]')?.content);
const api = LIVE ? await import("./api.js") : await import("./demo-api.js");

const root = document.documentElement;
const page = document.getElementById("page");
const stage = document.getElementById("stage");

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
function h(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}
const EASE = "cubic-bezier(.2,.8,.2,1)";
const reduced = () => Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);

// ------------------------------------------------------------------ the stage

let K = 1;
const typing = () => stage.contains(document.activeElement) && /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
function fit() {
  const vw = root.clientWidth || window.innerWidth, vh = window.innerHeight; // clientWidth: without a scrollbar
  const wide = vw >= 600;
  if (!wide && typing()) return; // a phone keyboard resizes some browsers' viewport; keep the stage still
  root.classList.toggle("wide", wide);
  const below = [...page.children].filter((c) => c.id !== "frame").reduce((n, c) => n + c.offsetHeight, 0);
  let k;
  if (wide) k = Math.min(1, (vh - 48 - below) / 844, (vw - 32) / 390);
  else {
    k = vw / 390; // a phone: the stage fills the width
    if (844 * k > vh) k = vh / 844; // unless that would push the bottom off screen
  }
  k = Math.max(0.3, k);
  if (k !== K) {
    K = k;
    root.style.setProperty("--k", K);
    screen?.rescale?.();
  }
}
root.style.setProperty("--k", K);
window.addEventListener("resize", fit);

function surface(dark) {
  root.classList.toggle("dark-surface", dark);
  document.querySelector('meta[name="theme-color"]').content = dark ? "#080706" : "#EAE5DE";
}

// ------------------------------------------------------------------ small things kept on this device

const store = api.prefs;
const onboarded = () => store.get("qh.onboarded") === "1";
const skippedLine = (weekId) => store.get(`qh.skipLine.${weekId}`) === "1";

// ------------------------------------------------------------------ app state

let st = null; // the last /v1/state
let posts = null; // the last /v1/board posts
let offset = 0; // server clock minus this clock
const now = () => Date.now() + offset;
let screen = null; // { key, el, update(st), home?, board?, dark?, destroy?(), setPosts?(posts), rescale?(), pic?() }
let home = false; // in the signed-in Home flow (not sign-in or onboarding)

// The Home's own layer, above every screen: the board and settings slide up into it. Changes of screen happen
// under it and never touch it.
const over = document.createElement("div");
over.className = "over";
stage.appendChild(over);

let shown = 0; // counts screens shown, so a screen that took a moment to build can tell it has been overtaken
const watchers = new Set(); // told which screen is up (the demo's step row follows it)
const notify = () => watchers.forEach((fn) => fn(screen?.key, st));
const motion = createMotion({ stage, scale: () => K, over });
/** Puts a screen up, by way of the change from the one before (motion.js). `prepare` fills it once it is on the stage. */
function show(next, prepare) {
  shown++;
  const prev = screen;
  screen = next;
  motion.present(prev, next, prepare);
  prev?.destroy?.();
  layer();
  notify();
}

// A quiet line in place of an existing one, for a few seconds.
const flashes = new WeakMap();
function flash(el, text) {
  if (!el) return;
  const was = flashes.get(el);
  if (was) clearTimeout(was.t);
  const keep = was ? was.html : el.innerHTML;
  el.textContent = text;
  flashes.set(el, { html: keep, t: setTimeout(() => { flashes.delete(el); el.innerHTML = keep; }, 4000) });
}
/** Sets an element's text (or HTML), unless a flash is showing there; then it shows once the flash ends. */
function put(el, value, html = false) {
  if (!el) return;
  const v = html ? value : esc(value);
  const was = flashes.get(el);
  if (was) was.html = v;
  else if (el.innerHTML !== v) el.innerHTML = v;
}

function say(err) {
  switch (err?.code) {
    case "network": return "Can't reach Quiet Hours. Try again.";
    case "not_shown": return "That one can't be shown. Try saying it another way.";
    case "post_limit": return "That's five posts this week, the most there can be.";
    case "board_closed": return "The board is closed.";
    case "invalid_request": return "That's too long.";
    case "already_wrote": return "You've already added yours.";
    case "phase_closed": case "week_changed": case "no_week": return "That's closed now.";
    case "not_in": return "Only people who are in can do that.";
    default: return null;
  }
}
const sayOr = (err) => say(err) ?? "Something went wrong. Try again.";

/** Runs a write, then draws again from the server's answer and a fresh state. */
async function act(run, noteEl, { refused } = {}) {
  try {
    const res = await run();
    if (res?.me && st) st.me = res.me;
    if (st) render();
  } catch (err) {
    if (err.status === 409 && refused) refused(err);
    else flash(noteEl, sayOr(err));
  }
  await refresh();
}

// ------------------------------------------------------------------ pieces the screens share

const GEAR = '<button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button>';
const BAR = `<div class="bar">${GEAR}</div>`; // no wordmark on a Home: the gear alone, top right
const UP = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6"/></svg>';
const CHEV = '<svg width="9" height="16" viewBox="0 0 9 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 1l7 7-7 7"/></svg>';

const people = (n, one, many) => `${f.num(n)} ${n === 1 ? one : many}`;

/** The gear raises settings over the Home. */
function wireGear(el) {
  el.querySelector(".gear")?.addEventListener("click", () => openSettings());
}

/** True where focusing a field brings up an on-screen keyboard. Only then does the layout move to make room for one. */
const softKeyboard = () => window.matchMedia("(hover: none) and (pointer: coarse)").matches;

/** Buttons keep a field focused when pressed, so the keyboard-up layout doesn't jump under the pointer. */
const holdFocus = (btn) => btn.addEventListener("pointerdown", (e) => { if (typing()) e.preventDefault(); });

// ------------------------------------------------------------------ 1 · sign-in

function signInScreen() {
  const el = h(`<div class="s c d">
<img class="art" src="assets/moon-col-light.png" alt="">
<h1 class="name">Quiet Hours</h1>
<p class="sub">One window a week when USC puts its phones down, together.</p>
<form novalidate>
<div class="rowf"><label for="qh-field">USC email</label><input id="qh-field" type="email" placeholder="you@usc.edu" autocomplete="email" autocapitalize="off" spellcheck="false" enterkeyhint="go"></div>
<button class="go" type="submit">Continue</button>
<p class="fine">We'll send a code to your inbox.</p>
</form>
</div>`);
  const form = el.querySelector("form"), input = el.querySelector("input"), label = el.querySelector("label"), btn = el.querySelector(".go"), fine = el.querySelector(".fine");
  const art = el.querySelector(".art");
  let address = null, busy = false;
  input.addEventListener("focus", () => { if (softKeyboard()) el.classList.add("k"); });
  input.addEventListener("blur", () => el.classList.remove("k"));
  holdFocus(btn);
  const signInSay = (err) => ({
    email_not_usc: "Use your USC email.", invalid_email: "Use your USC email.", invalid_request: "Use your USC email.",
    too_many_codes: "Too many codes asked for. Try again in an hour.", demo_account: "That's a demo account; it can't sign in.",
    email_not_configured: "Codes by email aren't set up yet.", code_invalid: "That code didn't work.",
    too_many_attempts: "Too many tries. Reload to ask for a new code.",
  })[err.code] ?? sayOr(err);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const v = input.value.trim();
    if (busy) return;
    if (!v) { input.focus(); return; }
    busy = true;
    try {
      if (address === null) {
        const out = await api.startSignIn(v);
        address = out.email;
        label.textContent = "Code";
        input.value = ""; input.placeholder = ""; input.type = "text";
        input.inputMode = "numeric"; input.autocomplete = "one-time-code"; input.setAttribute("enterkeyhint", "done");
        btn.textContent = "Sign in";
        fine.textContent = out.devCode ? `Demo mode: no email was sent. Your code is ${out.devCode}.` : `We sent a code to ${out.email}.`;
        input.focus();
      } else {
        await api.verify(address, v);
        input.blur();
        await afterSignIn();
      }
    } catch (err) {
      fine.textContent = signInSay(err);
    } finally { busy = false; }
  });
  return { key: "signin", el, pic: () => lightPicture() && { kind: "moon-light", el: art, ...lightPicture() } };
}

// ------------------------------------------------------------------ 2 · how it works, 3 · the lock

let lightDots = null, lightData = null, lightPic = null;
const loadLight = () => (lightDots ??= fetch("assets/moon-col-light.png.json").then((r) => r.json()).then((d) => (lightData = d)));
/** The sign-in moon as dots, once its data has loaded. */
const lightPicture = () => (lightPic ??= lightData && lightMoon(lightData));
loadLight().catch(() => {});

async function howScreen(next) {
  const light = await loadLight();
  await document.fonts?.ready;
  const el = h(`<div class="s hw">
<canvas width="1170" height="1380" aria-hidden="true"></canvas>
<p class="step" aria-live="polite">Quiet Hours</p>
<p class="sub"></p>
<div class="pips" aria-hidden="true"><i></i><i></i><i></i></div>
<button class="go" type="button">Next</button>
</div>`);
  const how = howItWorks(el, light, next), canvas = el.querySelector("canvas");
  return {
    key: "how", el, destroy: how.stop,
    pic: () => ({ ...how.snapshot(), el: canvas }), picVersion: how.version, arrived: (ms) => how.delayFirst(ms),
  };
}

function lockScreen(next) {
  const el = h(`<div class="s hw lk">
<canvas width="1170" height="1380" aria-hidden="true"></canvas>
<p class="step">Everything locks.</p>
<p class="sub">Except the apps you keep open.</p>
<div class="foot">
<button class="go" type="button">Allow the lock</button>
<p class="fine">Apple will ask you to confirm, then show your apps.</p>
</div>
</div>`);
  const canvas = el.querySelector("canvas");
  drawFilled(canvas, phone);
  el.querySelector(".go").addEventListener("click", () => {
    try { window.webkit?.messageHandlers?.quietHours?.postMessage({ type: "allowLock" }); } catch {}
    store.set("qh.onboarded", "1");
    next();
  });
  return { key: "lock", el, pic: () => ({ kind: "phone", el: canvas, pts: fill(phone), cols: null }) };
}

// ------------------------------------------------------------------ quiet lines: loading, nothing scheduled, can't reach

function quietScreen(key, text, { bar = false, late = false } = {}) {
  const el = h(`<div class="s hm${bar ? " q" : ""}">${bar ? BAR : ""}<p class="quiet${late ? " late" : ""}"></p></div>`);
  el.querySelector(".quiet").textContent = text;
  if (bar) wireGear(el);
  return { key, el, home: bar, update() {} };
}

function noWeekScreen() {
  const s = quietScreen("none", "", { bar: true });
  s.update = (st) => {
    const at = st.upcomingVoteOpensAt;
    put(s.el.querySelector(".quiet"), at ? `Voting opens ${f.dayInSentence(at, now())} at ${f.clockAmPm(at)}.` : "Nothing is scheduled yet.");
  };
  return s;
}

// ------------------------------------------------------------------ the Homes (docs/HOMES-QUIET.md)
//
// Every Home is one picture, one statement in the serif (on the same line on every Home), one grey line and at
// most one thing to do. The gear sits alone, top right; settings and the board are screens of the Home's own
// layer, sliding up over it.

const trojansIn = (n) => `${f.num(n)} ${n === 1 ? "Trojan" : "Trojans"} in`;
/** "In 1 day, 20 hours. 3,112 Trojans in.", each part only when the server sent it. */
function untilLine(st) {
  const at = st.week?.startsAt, n = st.numbers?.in;
  return [at ? `${f.until(at, now())}.` : "", typeof n === "number" ? `${trojansIn(n)}.` : ""].filter(Boolean).join(" ");
}
const OUT = "You're out this week.";
/** The pill that opens the board: the number of posts on it. */
const goingOn = (p) => (p.length ? `${f.num(p.length)} ${p.length === 1 ? "thing" : "things"} going on` : "Nothing going on yet");

function homeEl(cls, inner) {
  const el = h(`<div class="s hm q${cls ? ` ${cls}` : ""}">${inner}</div>`);
  wireGear(el);
  return el;
}
/** "Opt back in" on a Home that is out. A refusal hides it until the server says otherwise. */
function backIn(btn, line) {
  btn?.addEventListener("click", () => act(() => api.rejoin(st.week.id), line, { refused: () => (btn.hidden = true) }));
}

// ------------------------------------------------------------------ 4 · voting, out this week

function voteScreen(out) {
  // Out: the clock and the statement pale, the grey line in ink, and the one way back in. (Three pale pills with a
  // fourth under them don't fit below the grey line; see docs/WEB-NOTES.md.)
  const el = homeEl(`qv${out ? " qout" : ""}`, `<canvas class="pic" width="1170" height="1020" aria-hidden="true"></canvas>
${BAR}
<h2 class="qbig">When this week?</h2>
<p class="qline"></p>
${out ? '<button class="qgo" type="button">Opt back in</button>' : '<div class="qopts"></div>'}`);
  const canvas = el.querySelector("canvas.pic"), line = el.querySelector(".qline"), box = el.querySelector(".qopts"), back = el.querySelector(".qgo");
  drawStill(canvas, clock);
  backIn(back, line);
  let pending = null; // the option just tapped, until the server answers
  function draw(st) {
    const closes = st.week?.voteClosesAt;
    const closing = closes ? `Closes ${f.dayInSentence(closes, now())}, ${f.clockAmPm(closes)}` : "";
    if (out) { put(line, OUT); return; }
    const mine = pending ?? st.myVote ?? null;
    const options = (st.options ?? []).map((o) => ({ ...o, votes: o.votes - (pending && o.id === st.myVote ? 1 : 0) + (pending && o.id === pending ? 1 : 0) }));
    const total = options.reduce((n, o) => n + o.votes, 0);
    const key = options.map((o) => o.id).join();
    if (box.dataset.key !== key) {
      box.dataset.key = key;
      box.innerHTML = options.map(() => '<button class="qopt" type="button" aria-pressed="false"><b></b><i></i></button>').join("");
      [...box.children].forEach((b, i) => b.addEventListener("click", () => pick(options[i].id)));
    }
    // A tap presses the pill in; once there is a vote, every pill fills from the left to its share, with no numbers.
    options.forEach((o, i) => {
      const b = box.children[i], on = o.id === mine;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
      put(b.querySelector("b"), f.dayName(o.startsAt, now()));
      put(b.querySelector("i"), f.range(o.startsAt, o.endsAt));
      b.style.setProperty("--w", total ? `${Math.round((o.votes / total) * 100)}%` : "0%");
    });
    el.classList.toggle("voted", Boolean(mine));
    put(line, options.find((o) => o.id === mine)?.reason || closing);
  }
  async function pick(id) {
    if (!st?.me?.can?.vote || id === (pending ?? st.myVote)) return;
    pending = id;
    draw(st);
    try {
      const res = await api.vote(id, st.week.id);
      st.myVote = res.myVote; st.options = res.options;
    } catch (err) {
      flash(line, err.code === "network" ? sayOr(err) : "Your vote didn't go through. Try again.");
      if (err.status === 409) refresh();
    } finally {
      pending = null;
      if (screen?.el === el) draw(st);
    }
  }
  return {
    key: out ? "vote-out" : "vote", el, home: true,
    pic: () => ({ kind: "clock-home", el: canvas, pts: still(clock), cols: null }),
    update(st) {
      draw(st);
      if (back) back.hidden = !st.me?.can?.rejoin;
    },
  };
}

// ------------------------------------------------------------------ 5 · decided, 6 · the day, and out this week

function dayScreen(day, out) {
  const el = homeEl(out ? "qout" : "", `<img class="art" src="assets/moon-col-light.png" alt="">
${BAR}
<h2 class="qbig"></h2>
<p class="qsub"></p>
<p class="qline"></p>
${out ? '<button class="qgo" type="button">Opt back in</button>' : day ? '<button class="qrow" type="button"></button>' : ""}`);
  const art = el.querySelector(".art"), line = el.querySelector(".qline"), back = el.querySelector(".qgo"), pill = el.querySelector(".qrow");
  backIn(back, line);
  pill?.addEventListener("click", () => openBoard());
  return {
    key: (day ? "day" : "sel") + (out ? "-out" : ""), el, home: true, board: Boolean(pill),
    pic: () => lightPicture() && { kind: "moon-light", el: art, ...lightPicture() },
    update(st) {
      const { startsAt, endsAt } = st.week;
      put(el.querySelector(".qbig"), startsAt ? f.dayName(startsAt, now()) : "");
      put(el.querySelector(".qsub"), startsAt && endsAt ? f.range(startsAt, endsAt) : "");
      put(line, out ? OUT : untilLine(st));
      if (back) back.hidden = !st.me?.can?.rejoin;
      if (pill) pill.hidden = !st.board?.open || !posts;
    },
    setPosts(p) { if (pill) put(pill, goingOn(p)); },
  };
}

// ------------------------------------------------------------------ 7 · locked, out or left

let moonData = null, moonLoad = null;
const loadMoon = () => (moonLoad ??= fetch("assets/moon-col-dark.png.cells.json").then((r) => r.json()).then((d) => (moonData = d)));

/** The night moon is one fixed drawing: the same dots whoever is in (Hartley, Nov 15: its beauty is in being exact). */
const MOON_DOTS = 3098;
/** The moon on its canvas, redrawn only when the scale changes. */
function moonOn(canvas) {
  let n = -1, dots = [], drawn = "";
  const draw = () => {
    if (!moonData || n < 0) return;
    const sc = K * (window.devicePixelRatio || 1), key = `${n}@${sc}`;
    if (key === drawn) return;
    drawn = key;
    drawMoon(canvas, moonData, dots, sc);
  };
  loadMoon().then(() => { if (n >= 0) { dots = moonDots(moonData, n); draw(); } });
  return {
    count(next) {
      if (next === n) return;
      n = next;
      if (moonData) { dots = moonDots(moonData, n); draw(); }
    },
    rescale: draw,
    /** The dots as a picture, for a change of screen to carry on from or arrive at. */
    pic() {
      if (!moonData || n < 0) return null;
      const pts = new Float64Array(dots.length * 2), cols = new Uint8Array(dots.length * 3);
      dots.forEach((k, i) => { const c = moonData.cells[k]; pts[i * 2] = c[0] * 2 + 1 / 3; pts[i * 2 + 1] = c[1] * 2 + 1 / 3; cols[i * 3] = c[4]; cols[i * 3 + 1] = c[5]; cols[i * 3 + 2] = c[6]; });
      return { kind: "moon-dark", el: canvas, pts, cols, cells: dots, scale: K * (window.devicePixelRatio || 1) };
    },
  };
}

function lockedScreen(out) {
  const el = homeEl(`nt nb nt9${out ? " qout" : ""}`, `<img class="stars" src="assets/stars_quiet.png" alt="">
${BAR}
<canvas class="lmoon" aria-hidden="true"></canvas>
<h2 class="qbig"></h2>
<p class="qline"></p>
${out ? '<button class="golight" type="button"></button>' : '<button class="qrow" type="button"></button>'}`);
  const line = el.querySelector(".qline"), join = el.querySelector(".golight"), pill = el.querySelector(".qrow");
  const moon = moonOn(el.querySelector("canvas.lmoon"));
  join?.addEventListener("click", () => act(() => api.rejoin(st.week.id), line, { refused: () => (join.hidden = true) }));
  pill?.addEventListener("click", () => openBoard());
  return {
    key: out ? "live-out" : "live", el, dark: true, home: true, board: Boolean(pill),
    update(st) {
      const { endsAt } = st.week, live = st.numbers?.liveCount ?? st.numbers?.in;
      moon.count(MOON_DOTS);
      put(el.querySelector(".qbig"), endsAt ? `Until ${f.clock(endsAt)}` : "");
      const count = typeof live === "number" ? trojansIn(live) : "";
      put(line, out ? `You're out.${count ? ` ${count}.` : ""}` : count);
      if (join) {
        if (endsAt) put(join, `Join until ${f.clock(endsAt)}`);
        join.hidden = !st.me?.can?.rejoin || !endsAt;
      }
      if (pill) pill.hidden = !st.board?.open || !posts;
    },
    setPosts(p) { if (pill) put(pill, goingOn(p)); },
    rescale: () => moon.rescale(),
    pic: () => moon.pic(),
  };
}

// ------------------------------------------------------------------ 8 · the question

function questionScreen() {
  const el = h(`<div class="s hw q">
<canvas width="1170" height="1380" aria-hidden="true"></canvas>
<p class="lab"></p>
<p class="step">What did you do?</p>
<p class="sub"></p>
<textarea class="qf" maxlength="200" rows="1" placeholder="It's anonymous. Say what you really did." aria-label="What did you do?"></textarea>
<p class="qn">0 / 200</p>
<div class="foot">
<button class="go" type="button">Add it</button>
<button class="skip" type="button">Skip</button>
</div>
</div>`);
  const canvas = el.querySelector("canvas");
  drawFilled(canvas, bubble);
  const q = (s) => el.querySelector(s), ta = q(".qf"), qn = q(".qn"), sub = q(".sub"), add = q(".go");
  let busy = false;
  function size() { // the field grows with what's written; the count sits just under where the field is heading
    const base = 128, top = el.classList.contains("k") ? 196 : 514;
    ta.style.height = base + "px";
    const tall = Math.max(base, ta.scrollHeight);
    ta.style.height = tall + "px";
    qn.style.top = top + tall + 8 + "px";
  }
  ta.addEventListener("focus", () => { el.classList.add("t"); if (softKeyboard()) el.classList.add("k"); ta.classList.add("on"); size(); });
  ta.addEventListener("blur", () => { el.classList.remove("t", "k"); ta.classList.remove("on"); size(); });
  ta.addEventListener("input", () => { el.classList.add("t"); qn.textContent = `${ta.value.length} / 200`; size(); });
  holdFocus(add);
  add.addEventListener("click", async () => {
    const v = ta.value.trim();
    if (busy) return;
    if (!v) { ta.focus(); return; }
    busy = true;
    try {
      await api.writeLine(v, st.week.id);
      ta.blur();
      if (st?.me) { st.me.wroteLine = true; st.me.can = { ...st.me.can, writeLine: false }; }
      render();
      refresh();
    } catch (err) {
      flash(sub, sayOr(err));
      if (err.status === 409) refresh();
    } finally { busy = false; }
  });
  q(".skip").addEventListener("click", () => { store.set(`qh.skipLine.${st.week.id}`, "1"); render(); });
  requestAnimationFrame(size);
  return {
    key: "question", el,
    pic: () => ({ kind: "bubble", el: canvas, pts: fill(bubble), cols: null }),
    update(st) {
      const told = st.week.toldAt, stayed = st.numbers?.stayed?.count ?? 0;
      put(q(".lab"), `It's ${f.clock(st.week.endsAt)}. ${people(stayed, "Trojan", "Trojans")} stayed to the end.`);
      put(sub, `It goes into the recap ${f.until(told, now()).replace(/^I/, "i")}.`);   // "in 15 minutes": how long, not what time
    },
  };
}

// ------------------------------------------------------------------ 9 · summary, before the recap, out

function summaryScreen(variant) {
  // variant: "sum" (told, in), "sum-out" (told, out), "sum-pre" (before the recap lands), "sum-pre-out"
  const out = variant.endsWith("out"), pre = variant.startsWith("sum-pre");
  const el = homeEl("qs", `<canvas class="pic" width="1170" height="1020" aria-hidden="true"></canvas>
${BAR}
${pre ? '<h2 class="qbig" style="font-size:52px;line-height:56px">Quiet hours are over.</h2>\n<p class="qline" style="top:584px"></p>'
    : '<h2 class="qbig" aria-live="polite"></h2>\n<div class="qpips" aria-hidden="true"></div>\n<p class="qline"></p>'}`);
  const canvas = el.querySelector("canvas.pic"), big = el.querySelector(".qbig"), line = el.querySelector(".qline"), pips = el.querySelector(".qpips");
  drawStill(canvas, bubble);

  // The highlights one at a time, in the server's order: a new one every 3.8 s with a 0.42 s fade. A tap moves on
  // and stops the clock. With Reduce Motion they wait for a tap, and change with a 200 ms cross-fade.
  let said = [], at = 0, every = 0, swap = 0, fade = null;
  function showAt(k) {
    at = (k + said.length) % said.length;
    const done = () => { big.textContent = said[at]; [...pips.children].forEach((d, i) => d.classList.toggle("on", i === at)); };
    if (reduced()) {
      fade?.cancel();
      const a = (fade = big.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 100, easing: "ease" }));
      a.finished.then(() => { if (fade !== a) return; done(); fade = big.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 100, easing: "ease" }); }, () => {});
      return;
    }
    big.style.opacity = "0";
    clearTimeout(swap);
    swap = setTimeout(() => { swap = 0; done(); big.style.opacity = ""; }, 420);
  }
  if (!pre) el.addEventListener("click", (e) => {
    if (e.target.closest(".bar") || said.length < 2) return;
    clearInterval(every); every = 0;
    showAt(at + 1);
  });

  return {
    key: variant, el, home: true,
    pic: () => ({ kind: "bubble-home", el: canvas, pts: still(bubble), cols: null }),
    update(st) {
      if (pre) { // people are still writing, and when it comes back (the server's told time)
        const told = st.week?.toldAt;
        put(line, `People are still writing.${st.phase === "ended" && told ? ` Back at ${f.clock(told)}.` : ""}`);
        return;
      }
      const s = st.numbers?.stayed;
      const tally = typeof s?.count === "number" && typeof s?.of === "number" ? `${f.num(s.count)} of ${f.num(s.of)} stayed.` : "";
      put(line, out ? `You were out this week.${tally ? ` ${tally}` : ""}` : tally);
      // Highlights get a closing period when they lack one, as the mock sets them.
      const next = (st.recap?.highlights ?? []).slice(0, 5).map((x) => String(x.text ?? "").trim()).filter(Boolean)
        .map((t) => (/[.!?…"”']$/.test(t) ? t : `${t}.`));
      if (next.join("\n") === said.join("\n") && big.textContent) return;
      said = next; at = 0;
      clearInterval(every); every = 0; clearTimeout(swap); swap = 0; fade?.cancel(); fade = null;
      big.style.opacity = "";
      big.textContent = said[0] ?? "Quiet hours are over.";
      pips.innerHTML = said.length > 1 ? said.map((_, i) => `<i${i ? "" : ' class="on"'}></i>`).join("") : "";
      if (!reduced() && said.length > 1) every = setInterval(() => showAt(at + 1), 3800);
    },
    destroy() { clearInterval(every); clearTimeout(swap); fade?.cancel(); },
  };
}

// ------------------------------------------------------------------ the board: its own screen, one tap from The day and Locked

let board = null; // { el, sheet, cmp, anim, update() } while it is up
function openBoard() {
  if (board || !screen?.board || !posts) return;
  const el = h(`<div class="s hm q nt nb nt9 qb" role="dialog" aria-modal="true" aria-label="Going on now">
<div class="sheet9 board9 open">
<div class="s9head"><span>Going on now</span></div>
<button type="button" class="s9more s9x" aria-label="Close"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
<div class="s9list"></div>
<form class="cmp9"><input type="text" placeholder="What you're doing, and where" aria-label="What you're doing, and where" maxlength="202" autocomplete="off" enterkeyhint="send"><button class="snd" type="submit" aria-label="Post">${UP}</button></form>
</div>
</div>`);
  over.appendChild(el);
  const B = (board = { el, cmp: el.querySelector(".cmp9"), anim: null });
  B.sheet = mountBoard(el.querySelector(".sheet9"), {
    now,
    take: async (p) => { await api.takeDown(p.id); posts = (posts ?? []).filter((x) => x.id !== p.id); screen?.setPosts?.(posts); },
    send: async (text, place) => {
      const res = await api.post(text, place, st.week.id);
      posts = [res.post, ...(posts ?? []).filter((p) => p.id !== res.post.id)];
      board?.sheet.setPosts(posts);
      screen?.setPosts?.(posts);
      loadBoard();
    },
    say,
  });
  B.update = () => { B.sheet.setPosts(posts ?? []); B.cmp.hidden = !st?.me?.can?.post; };
  B.update();
  el.querySelector(".s9more").addEventListener("click", () => closeBoard());
  layer();
  // Up from the bottom to cover the screen.
  B.anim = reduced()
    ? el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, easing: "ease" })
    : el.animate([{ transform: "translateY(844px)" }, { transform: "none" }], { duration: 500, easing: EASE });
  el.querySelector(".s9more").focus({ preventScroll: true });
}
/** Back down, from wherever it is. `instant` takes it away at once. */
function closeBoard({ instant = false } = {}) {
  const B = board;
  if (!B) return;
  board = null;
  const done = () => {
    B.anim?.cancel();
    B.sheet.destroy();
    B.el.remove();
    if (B.el.contains(document.activeElement) || document.activeElement === document.body) screen?.el.querySelector(".qrow")?.focus({ preventScroll: true });
  };
  B.el.inert = true;
  layer();
  if (instant) return done();
  const cs = getComputedStyle(B.el), from = cs.transform, op = +cs.opacity;
  B.anim?.cancel();
  B.anim = reduced()
    ? B.el.animate([{ opacity: op }, { opacity: 0 }], { duration: 200, easing: "ease", fill: "forwards" })
    : B.el.animate([{ transform: from === "none" ? "none" : from }, { transform: "translateY(844px)" }], { duration: 500, easing: EASE, fill: "forwards" });
  B.anim.finished.then(done, () => {});
}

// ------------------------------------------------------------------ settings: a sheet behind the gear, over whichever Home is up

let settings = null; // { el, dim, sheet, anim[], key, fill() } while it is up

/** The first row: what this week allows right now, or nothing when there is nothing to opt out of. */
function weekRow() {
  const me = st?.me, can = me?.can ?? {}, w = st?.week;
  if (!me || !w) return null;
  const when = w.startsAt && w.endsAt ? `${f.dayName(w.startsAt, now())}, ${f.range(w.startsAt, w.endsAt)}` : "";
  if (st.phase === "live") {
    if (me.status === "in" && can.leave) return { title: "Leave quiet hours", sub: w.endsAt ? `They run until ${f.clock(w.endsAt)}` : "", run: () => api.leave(w.id) };
    if (me.status !== "in" && can.rejoin && w.endsAt) return { title: `Join until ${f.clock(w.endsAt)}`, sub: "", run: () => api.rejoin(w.id) };
    return null;
  }
  if (me.status === "in" && can.skip) return { title: "Opt out of this week", sub: when, run: () => api.skip(w.id) };
  if (me.status === "skipped" && can.rejoin) return { title: "Opt back in", sub: when, run: () => api.rejoin(w.id) };
  return null;
}

function fillSettings(S) {
  const row = weekRow(), email = api.email();
  const key = `${row ? `${row.title}|${row.sub}` : ""}|${email}`;
  if (S.key === key) return;
  S.key = key;
  S.sheet.innerHTML = (row ? `<button type="button" class="qweek"><div><b>${esc(row.title)}</b>${row.sub ? `<span>${esc(row.sub)}</span>` : ""}</div></button>` : "") +
    // On the web there is no picker for what stays open: shown without its arrow, and not pressable.
    '<div class="qfix"><div><b>What stays open</b><span>Chosen in the iPhone app</span></div></div>' +
    `<button type="button" class="qhow"><div><b>How it works</b></div>${CHEV}</button>` +
    `<button type="button" class="qsign"><div><b>Sign out</b>${email ? `<span>${esc(email)}</span>` : ""}</div></button>`;
  // One tap does it: the sheet closes and the Home eases to its new state.
  S.sheet.querySelector(".qweek")?.addEventListener("click", () => {
    const r = weekRow();
    closeSettings();
    if (r) act(r.run, screen?.el.querySelector(".qline"));
  });
  S.sheet.querySelector(".qhow").addEventListener("click", () => { closeSettings({ fade: true }); showHow(() => goHome()); });
  S.sheet.querySelector(".qsign").addEventListener("click", async () => {
    closeSettings({ fade: true });
    try { await api.signOut(); } catch {}
    signedOut();
  });
}

function openSettings() {
  if (settings || !screen?.home) return;
  const el = h('<div class="qsettings"><div class="qdim"></div><div class="qset" role="dialog" aria-modal="true" aria-label="Settings"></div></div>');
  over.appendChild(el);
  const S = (settings = { el, dim: el.querySelector(".qdim"), sheet: el.querySelector(".qset"), anim: [], key: null, dragged: 0 });
  S.fill = () => fillSettings(S);
  S.fill();
  S.dim.addEventListener("click", () => closeSettings());
  dragToClose(S);
  layer();
  // Up from the bottom, the Home dimming behind it.
  S.anim = reduced()
    ? [el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, easing: "ease" })]
    : [S.dim.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, easing: EASE }),
      S.sheet.animate([{ transform: "translateY(100%)" }, { transform: "none" }], { duration: 500, easing: EASE })];
  S.sheet.querySelector("button")?.focus({ preventScroll: true });
}
/** Down again, from wherever it is. `fade` lets it go with a quick fade (the screen is changing under it); `instant` at once. */
function closeSettings({ fade = false, instant = false } = {}) {
  const S = settings;
  if (!S) return;
  settings = null;
  const done = () => {
    S.anim.forEach((a) => a.cancel());
    S.el.remove();
    if (S.el.contains(document.activeElement) || document.activeElement === document.body) screen?.el.querySelector(".gear")?.focus({ preventScroll: true });
  };
  S.el.inert = true;
  layer();
  if (instant) return done();
  const dimFrom = +getComputedStyle(S.dim).opacity, sheetFrom = getComputedStyle(S.sheet).transform, allFrom = +getComputedStyle(S.el).opacity;
  S.anim.forEach((a) => a.cancel());
  S.sheet.style.transform = ""; S.dim.style.opacity = ""; // a drag hands over to the animation
  S.anim = reduced() || fade
    ? [S.el.animate([{ opacity: allFrom }, { opacity: 0 }], { duration: reduced() ? 200 : 250, easing: "ease", fill: "forwards" })]
    : [S.dim.animate([{ opacity: dimFrom }, { opacity: 0 }], { duration: 500, easing: EASE, fill: "forwards" }),
      S.sheet.animate([{ transform: sheetFrom === "none" ? "none" : sheetFrom }, { transform: "translateY(100%)" }], { duration: 500, easing: EASE, fill: "forwards" })];
  Promise.all(S.anim.map((a) => a.finished)).then(done, () => {});
}
/** Dragging the sheet down closes it; let go early and it settles back. A drag never counts as a tap on a row. */
function dragToClose(S) {
  const sh = S.sheet;
  let id = null, y0 = 0, dy = 0, last = [], dragging = false;
  sh.addEventListener("pointerdown", (e) => {
    if (settings !== S || (e.button ?? 0) !== 0) return;
    id = e.pointerId; y0 = e.clientY; dy = 0; dragging = false; last = [[performance.now(), 0]];
  });
  sh.addEventListener("pointermove", (e) => {
    if (e.pointerId !== id) return;
    const d = (e.clientY - y0) / K;
    if (!dragging) {
      if (d < 6) return;
      dragging = true;
      try { sh.setPointerCapture(id); } catch {}
      S.anim.forEach((a) => a.cancel()); S.anim = [];
    }
    dy = Math.max(0, d);
    last = [...last.slice(-3), [performance.now(), dy]];
    sh.style.transform = `translateY(${dy}px)`;
    S.dim.style.opacity = String(Math.max(0, 1 - dy / sh.offsetHeight));
  });
  const end = (e) => {
    if (e.pointerId !== id) return;
    id = null;
    if (!dragging) return;
    dragging = false;
    S.dragged = performance.now();
    const [t0, y1] = last[0], v = (dy - y1) / Math.max(1, performance.now() - t0); // points per ms, recent
    if (dy > 90 || (dy > 16 && v > 0.45)) return closeSettings();
    const from = sh.style.transform, op = S.dim.style.opacity;
    sh.style.transform = ""; S.dim.style.opacity = "";
    S.anim = [sh.animate([{ transform: from }, { transform: "none" }], { duration: 300, easing: EASE }),
      S.dim.animate([{ opacity: op }, { opacity: 1 }], { duration: 300, easing: EASE })];
  };
  sh.addEventListener("pointerup", end);
  sh.addEventListener("pointercancel", end);
  sh.addEventListener("click", (e) => { if (performance.now() - S.dragged < 400) { e.stopPropagation(); e.preventDefault(); } }, true);
}

/** The Home's layer follows the screen under it: settings stays over a Home, the board over a Home that offers it. */
function layer() {
  const dark = Boolean(screen?.dark);
  over.classList.toggle("nt9", dark); // the dim and the sheet in the screen's own surface
  if (settings && !screen?.home) closeSettings({ fade: true });
  if (board && !(screen?.board && posts)) closeBoard();
  settings?.fill();
  board?.update();
  if (screen) screen.el.inert = Boolean(settings || board);
  surface(dark || Boolean(board));
}
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (settings) closeSettings();
  else if (board) closeBoard();
});

// ------------------------------------------------------------------ which screen

function keyFor(st) {
  if (!st?.phase || !st.week) return "none";
  const s = st.me?.status ?? null, wasIn = s === "in" || s === "left";
  switch (st.phase) {
    case "vote": return s === "skipped" ? "vote-out" : "vote";
    case "decided": return st.board?.open ? (s === "in" ? "day" : "day-out") : s === "in" ? "sel" : "sel-out";
    case "live": return s === "in" ? "live" : "live-out";
    case "ended": return st.me?.can?.writeLine && !skippedLine(st.week.id) ? "question" : "sum-pre";
    case "told": return st.recap ? (wasIn ? "sum" : "sum-out") : wasIn ? "sum-pre" : "sum-pre-out";
    default: return "none";
  }
}

const builders = {
  none: noWeekScreen,
  vote: () => voteScreen(false), "vote-out": () => voteScreen(true),
  sel: () => dayScreen(false, false), "sel-out": () => dayScreen(false, true),
  day: () => dayScreen(true, false), "day-out": () => dayScreen(true, true),
  live: () => lockedScreen(false), "live-out": () => lockedScreen(true),
  question: questionScreen,
  sum: () => summaryScreen("sum"), "sum-out": () => summaryScreen("sum-out"),
  "sum-pre": () => summaryScreen("sum-pre"), "sum-pre-out": () => summaryScreen("sum-pre-out"),
};

function render() {
  if (!home || !st) return;
  const key = keyFor(st);
  if (screen?.key !== key) {
    const next = builders[key]();
    show(next, () => { if (posts) next.setPosts?.(posts); next.update(st); });
  } else {
    screen.update(st);
    layer();
  }
  notify();
}

// ------------------------------------------------------------------ talking to the server

let inflight = null, lastRefresh = 0, pollT = 0;
function refresh() {
  if (!home || !api.signedIn()) return Promise.resolve();
  if (inflight) return inflight;
  lastRefresh = Date.now();
  inflight = (async () => {
    try {
      const next = await api.state();
      offset = Date.parse(next.serverTime) - Date.now();
      // The board comes with the state, so a screen that shows it is drawn whole (and its pill has its count).
      let got = null;
      if (next.board?.open) got = await api.board().catch(() => null);
      st = next;
      posts = !st.board?.open ? null : got ? (got.open ? got.posts : []) : posts;
      const key = screen?.key;
      render();
      if (posts && screen?.key === key) screen?.setPosts?.(posts); // the same screen: its pill updates in place
    } catch (err) {
      if (err.status === 401) return; // signedOut() has taken over
      if (!st) show(quietScreen("error", "Can't reach Quiet Hours. Trying again."));
    } finally {
      inflight = null;
      schedule();
    }
  })();
  return inflight;
}

async function loadBoard() {
  try {
    const b = await api.board();
    posts = b.open ? b.posts : [];
    screen?.setPosts?.(posts);
    board?.update();
  } catch {}
}

function schedule() {
  clearTimeout(pollT);
  if (!home || document.hidden) return;
  let wait = !st ? 5000 : st.phase === "live" ? 15000 : 20000;
  if (st?.nextChangeAt) wait = Math.min(wait, Math.max(500, Date.parse(st.nextChangeAt) - now() + 500));
  pollT = setTimeout(refresh, wait);
}
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); else clearTimeout(pollT); });
window.addEventListener("focus", () => { if (Date.now() - lastRefresh > 2000) refresh(); });
setInterval(() => { // "In 3 hours, 12 minutes" and the posts' ages keep moving
  if (home && st && !document.hidden) { screen?.update?.(st); board?.sheet.ages(); }
}, 15000);

// ------------------------------------------------------------------ the flow

function leaveHome() { home = false; clearTimeout(pollT); }
/** Home, drawn from the state. `fresh` drops what was drawn before, so nothing stale shows while it loads. */
function goHome({ fresh = false } = {}) {
  home = true;
  if (fresh) { st = null; posts = null; }
  if (st) render();
  else if (!screen || screen.key === "signin") show(quietScreen("loading", "Loading", { late: true }));
  return refresh();
}
/** How it works; then The lock (the first time), or `next` (replayed from settings: back to the Home). */
async function showHow(next = showLock) {
  leaveHome();
  const ticket = ++shown;
  const s = await howScreen(next);
  if (ticket === shown) show(s); // nothing else was shown while it was being drawn
}
function showLock() { leaveHome(); show(lockScreen(goHome)); }
async function afterSignIn() {
  if (onboarded()) return goHome();
  return showHow();
}
function signedOut() {
  leaveHome(); st = null; posts = null;
  show(signInScreen());
}
api.onSignedOut(signedOut);

fit();
if (!api.signedIn()) show(signInScreen());
else afterSignIn();

// The dot pictures take a moment to work out; do it while nothing is happening, so How it works opens at once.
const idle = window.requestIdleCallback ?? ((fn) => setTimeout(fn, 200));
[clock, lock, bubble, phone].forEach((fn) => idle(() => fill(fn)));
[clock, bubble].forEach((fn) => idle(() => still(fn)));
idle(() => loadMoon().catch(() => {}));
idle(() => warmStars("assets/stars_quiet.png"));

if (!LIVE) {
  // The sample campus: a row of steps outside the phone, so every phase can be seen at once.
  const { mountSteps } = await import("./steps.js");
  mountSteps(page, api.demo, {
    signIn: signedOut, how: () => showHow(), lock: showLock, home: () => goHome({ fresh: true }), refresh,
    watch: (fn) => { watchers.add(fn); fn(screen?.key, st); },
  });
  fit();
} else {
  // Against the live server: the admin demo strip, only with ?demo=<admin secret>. The secret stays in memory.
  const demoSecret = new URLSearchParams(location.search).get("demo");
  if (demoSecret) {
    const { mountDemo } = await import("./demo.js");
    mountDemo(page, demoSecret, { state: () => st, now, refresh, fit });
    fit();
  }
}
