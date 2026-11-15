// How one screen becomes the next.
//
// Choreographed, both ways: Sign in ↔ How it works ↔ The lock ↔ Voting, every pair of neighbouring Homes
// (docs/HOMES-QUIET.md, "Motion"), and opting out or back in on any Home. Within those:
//   - what is on both screens stays put: the gear, a line whose words are the same, the pill when both Homes
//     have it (it changes its look in place, light to dark on the way into Locked);
//   - a picture made of dots re-forms into the next one as How it works does, drifts apart, gathers, or gives
//     way to the next while its dots arrive a few at a time (the daylight moon into the night moon); the stars
//     come out, or go out, a few at a time;
//   - the statement and the lines under it cross-fade where they stand;
//   - raised things (the pills) rise out of the surface or fade and sink back into it; pressed-in things sink in
//     or fill back up.
// Light to dark (The day ↔ Locked, Locked → the question or the Summary) is the one slow change.
// Every other change of screen is a quick cross-fade of the whole stage; with prefers-reduced-motion, all are.
//
// Nothing here leaves a trace: every effect is a Web Animation, a canvas or a copy of old content that is
// cancelled or removed when the change is over, so the screen at rest is exactly what its own render made. A
// change that arrives mid-way freezes the one in progress and cross-fades from wherever it was to the newest.
// The Home's own layer (`over`: the board and settings) sits above every screen and is never part of a change.

const EASE = "cubic-bezier(.2,.8,.2,1)";
const INK = [58, 52, 46];
const reduced = () => Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);

// The neighbours with their own choreography, keyed "from>to". Delays are ms; [delay, stagger] staggers siblings
// top first. `pairs` matches a part of one screen to a differently named part of the other.
const SEAMS = {
  "signin>how": { pairs: { name: "step" }, glide: ["step"], in: { go: 200, pips: 240 } },
  "how>signin": { pairs: { step: "name" }, glide: ["name"], dots: { dur: 900 }, in: { sub: 160, rowf: 180, go: 230, fine: 280 } },
  "how>lock": { dots: { dur: 1100 }, glide: ["go"], in: { fine: 180 } },
  "lock>how": { dots: { dur: 1100 }, glide: ["go"], in: { pips: 160 } },
  "lock>vote": { dots: { dur: 1100 }, in: { bar: 200, qbig: 380, qline: 440, opts: 520, pill: 520 } },
  "vote>lock": { dots: { dur: 1100 }, in: { step: 380, sub: 440, go: 520, fine: 560 } },
  // Between Homes the picture re-forms over How it works' own 1.1 s; the words cross-fade in a quarter of that.
  "vote>sel": { dots: { dur: 1100 } }, "sel>vote": { dots: { dur: 1100 } }, "vote>day": { dots: { dur: 1100 } }, "day>vote": { dots: { dur: 1100 } },
  "sel>day": {}, "day>sel": {}, "pre>told": {}, "told>pre": {},
  "told>vote": { dots: { dur: 1100 } }, "vote>told": { dots: { dur: 1100 } },
  "day>live": { slow: true, dots: { mode: "swap", dur: 1100, delay: 100 }, stars: { dur: 1300, delay: 250 } },
  "live>day": { slow: true, dots: { mode: "swap", dur: 900 }, stars: { dur: 700 } },
  "live>question": { slow: true, dots: { mode: "morph", dur: 950 }, stars: { dur: 800 }, in: { lab: 380, step: 420, sub: 460, qf: 420, go: 480, skip: 520 } },
  "question>live": { slow: true, dots: { mode: "morph", dur: 950 }, stars: { dur: 1200, delay: 200 }, in: { bar: 300, qbig: 420, qline: 480, pill: 520 } },
  "live>pre": { slow: true, dots: { mode: "morph", dur: 950 }, stars: { dur: 800 }, in: { bar: 300, qbig: 420, qline: 480 } },
  "pre>live": { slow: true, dots: { mode: "morph", dur: 950 }, stars: { dur: 1200, delay: 200 }, in: { qbig: 420, qline: 480, pill: 520 } },
  "question>pre": { dots: { mode: "morph", dur: 900 }, in: { bar: 200, qbig: 360, qline: 420 } },
  "pre>question": { dots: { mode: "morph", dur: 900 }, in: { lab: 200, step: 240, sub: 280, qf: 280, go: 320, skip: 360 } },
};
const GROUP = {
  signin: "signin", how: "how", lock: "lock", question: "question",
  vote: "vote", "vote-out": "vote", sel: "sel", "sel-out": "sel", day: "day", "day-out": "day", live: "live", "live-out": "live",
  "sum-pre": "pre", "sum-pre-out": "pre", sum: "told", "sum-out": "told",
};

// The parts of a screen: [class, key, kind]. kind: text (cross-fades), raised (rises, sinks back), pressed (sinks
// in, fills back up). Parts with the same key on two screens are the same part: the Homes' one pill is "pill"
// whichever it is (the board's count, "Opt back in", "Join until 7:00").
const PARTS = [
  ["bar", "bar", "text"], ["name", "name", "text"], ["step", "step", "text"], ["sub", "sub", "text"], ["pips", "pips", "text"],
  ["fine", "fine", "text"], ["lab", "lab", "text"], ["skip", "skip", "text"], ["quiet", "quiet", "text"],
  ["go", "go", "raised"], ["rowf", "rowf", "pressed"], ["qf", "qf", "pressed"], ["stars", "stars", "stars"],
  ["qbig", "qbig", "text"], ["qsub", "qsub", "text"], ["qline", "qline", "text"], ["qpips", "qpips", "text"],
  ["qopts", "opts", "raised"], ["qrow", "pill", "raised"], ["qgo", "pill", "raised"], ["golight", "pill", "raised"],
];

export function createMotion({ stage, scale, over = null }) {
  let run = null;
  const frozen = [];

  /** Stage coordinates (points) of an element as it is drawn right now. */
  function rectIn(el) {
    const r = el.getBoundingClientRect(), s = stage.getBoundingClientRect(), k = scale();
    return { x: (r.left - s.left) / k, y: (r.top - s.top) / k, w: r.width / k, h: r.height / k };
  }

  /**
   * Puts `next` on the stage in place of `prev`. `prepare` fills the new screen once it is on the stage and
   * before anything is measured.
   */
  function present(prev, next, prepare) {
    const interrupted = run && !run.done ? run : null;
    if (interrupted) { interrupted.freeze(); frozen.push(interrupted); }
    stage.insertBefore(next.el, over);
    prepare?.();
    const outgoing = [...stage.children].filter((c) => c !== next.el && c !== over);
    const R = new Run();
    run = R;
    R.cleanups.push(() => outgoing.forEach((c) => c.remove()));
    outgoing.forEach((c) => { c.inert = true; c.style.pointerEvents = "none"; });
    if (!prev || !outgoing.length) return complete(R);

    let plan = null;
    if (!reduced() && !interrupted) {
      const ga = GROUP[prev.key], gb = GROUP[next.key];
      if (ga && ga === gb && prev.key !== next.key && !["how", "lock", "signin", "question"].includes(ga)) plan = { toggle: true };
      else plan = SEAMS[`${ga}>${gb}`] ?? null;
    }
    const quick = reduced() ? 200 : 250;
    const dark = (el) => luma(getComputedStyle(el).backgroundColor) < 0.3;
    const slow = plan && dark(prev.el) !== dark(next.el);
    const surface = !plan ? quick : slow ? 900 : plan.toggle ? 300 : 450;
    document.documentElement.style.setProperty("--surface-ms", `${surface}ms`);
    R.cleanups.push(() => document.documentElement.style.removeProperty("--surface-ms"));
    if (plan) seam(R, prev, next, { ...plan, slow, surface });
    else R.animate(next.el, [{ opacity: 0 }, { opacity: 1 }], { duration: quick, easing: "ease" });
    next.arrived?.(R.dotsEnd);
    R.after(R.end + 30, () => complete(R));
  }

  function complete(R) {
    R.finish();
    while (frozen.length) frozen.pop().finish();
    if (run === R) run = null;
  }

  // ---------------------------------------------------------------- one choreographed change

  function seam(R, A, B, plan) {
    const fx = document.createElement("div");
    fx.className = "fx";
    stage.insertBefore(fx, over);
    R.cleanups.push(() => fx.remove());
    R.hold(B.el, { backgroundColor: "transparent" }); // the old screen's surface shows through, and changes colour
    const ca = getComputedStyle(A.el).backgroundColor, cb = getComputedStyle(B.el).backgroundColor;
    if (ca !== cb) R.animate(A.el, [{ backgroundColor: ca }, { backgroundColor: cb }], { duration: plan.surface, easing: "ease-in-out", fill: "both" });

    dots(R, A, B, plan);
    const pa = parts(A.el), pb = parts(B.el);
    for (const [ka, kb] of Object.entries(plan.pairs ?? {})) { // a part known by another name on the other screen
      if (pa.has(ka) && pb.has(kb)) { pa.set(kb, { ...pa.get(ka), key: kb }); pa.delete(ka); }
    }
    stars(R, pa.get("stars"), pb.get("stars"), plan);
    pa.delete("stars"); pb.delete("stars");

    const count = { in: {}, out: {} };
    const timing = (dir, part) => { // the delay for a part arriving or leaving; staggers count per kind of part
      const base = part.base, spec = plan[dir]?.[base];
      const i = (count[dir][base] = (count[dir][base] ?? -1) + 1);
      if (Array.isArray(spec)) return spec[0] + spec[1] * i;
      if (typeof spec === "number") return spec;
      if (dir === "out") return 0;
      if (plan.slow) return 450;
      return part.kind === "text" ? 120 : 100;
    };
    const keys = [...new Set([...pb.keys(), ...pa.keys()])];
    for (const key of keys) {
      const a = pa.get(key), b = pb.get(key);
      if (a && b) match(R, fx, a, b, plan, timing);
      else if (a) leave(R, a, timing("out", a), plan);
      else arrive(R, b, timing("in", b), plan);
    }
  }

  function parts(root) {
    const map = new Map();
    const add = (key, base, el, kind) => map.set(key, { key, base, el, kind, rect: rectIn(el), text: norm(el.textContent) });
    const take = (el) => {
      if (!visible(el) || el.tagName === "CANVAS" || el.classList.contains("art")) return; // pictures go by their dots
      const c = el.classList;
      if (c.contains("foot") || el.tagName === "FORM") { [...el.children].forEach(take); return; }
      const rule = PARTS.find(([cls]) => c.contains(cls));
      if (rule) add(rule[1], rule[1], el, rule[2]);
    };
    [...root.children].forEach(take);
    return map;
  }

  /** A part on both screens. */
  function match(R, fx, a, b, plan, timing) {
    const here = near(a.rect, b.rect), quick = plan.toggle ? 300 : 450, easing = plan.slow ? "ease-in-out" : EASE;
    if (plan.glide?.includes(b.key) && !here) glideTo(R, fx, a, b);
    else if (a.text === b.text && here) morphTree(R, fx, a.el, b.el, { dur: plan.slow ? 900 : quick, xdur: 250, toggle: plan.toggle, easing });
    else if (a.kind === "text" && b.kind === "text") { crossfade(R, a, b, plan); return; } // new words, each where it stands
    else if (b.kind !== "text" && here) { // the same control with a new label (and look), in place
      morphStyle(R, a.el, b.el, plan.slow ? 900 : quick, 0, null, easing);
      relabel(R, fx, a, b, null, plan.toggle ? 300 : 450);
    } else { leave(R, a, timing("out", a), plan); arrive(R, b, timing("in", b), plan); return; } // each where it stands, by its own physics
    R.hold(a.el, { opacity: 0 }); // the old copy gives way to the new one at once (a hold outranks the old screen's own animations)
  }

  /** Changed words: the old fade out and the new fade in, each where it stands, at the same time. */
  function crossfade(R, a, b, plan) {
    const d = plan.toggle ? 300 : plan.slow ? 700 : 250, delay = plan.slow ? 200 : 0;
    R.animate(a.el, [{ opacity: +getComputedStyle(a.el).opacity }, { opacity: 0 }], { duration: d, easing: "ease", fill: "both" });
    R.animate(b.el, [{ opacity: 0 }, { opacity: restOpacity(b.el) }], { duration: d, delay, easing: "ease" });
  }

  /** The same part, moved (and for text, resized): it travels from where it was. Changed text cross-fades on the way. */
  function glideTo(R, fx, a, b) {
    const ra = a.rect, rb = b.rect;
    const s = b.kind === "text" ? parseFloat(getComputedStyle(a.el).fontSize) / parseFloat(getComputedStyle(b.el).fontSize) : 1;
    const dx = ra.x + ra.w / 2 - (rb.x + rb.w / 2), dy = ra.y + ra.h / 2 - (rb.y + rb.h / 2);
    const rest = restTransform(b.el);
    R.animate(b.el, [
      { transform: `translate(${dx}px, ${dy}px) scale(${s}) ${rest}`.trim(), transformOrigin: "50% 50%" },
      { transform: rest || "none", transformOrigin: "50% 50%" },
    ], { duration: 450 });
    if (b.kind === "text") {
      morphStyle(R, a.el, b.el, 450, 0, ["color"]);
      if (a.text !== b.text) {
        const g = ghost(fx, a.el);
        R.animate(g, [
          { transform: "none", opacity: 1 },
          { transform: `translate(${-dx}px, ${-dy}px) scale(${1 / s})`, opacity: 0, offset: 0.55 },
          { transform: `translate(${-dx}px, ${-dy}px) scale(${1 / s})`, opacity: 0 },
        ], { duration: 450, fill: "both" });
        R.animate(b.el, [{ opacity: 0 }, { opacity: 0, offset: 0.2 }, { opacity: restOpacity(b.el) }], { duration: 450, easing: "ease" });
      } else R.animate(b.el, [{ opacity: 1 }, { opacity: restOpacity(b.el) }], { duration: 450 }); // overrides any arrival of its own
    } else {
      morphStyle(R, a.el, b.el, 450, 0);
      if (a.text !== b.text) relabel(R, fx, a, b, { dx: -dx, dy: -dy });
    }
  }

  /** A control's label changing in place: the old label as a ghost fading out (moving with the control if it moves), the new one fading in. */
  function relabel(R, fx, a, b, move, duration = 450) {
    const g = ghost(fx, a.el, true);
    const end = move ? `translate(${move.dx}px, ${move.dy}px)` : "none";
    R.animate(g, [{ transform: "none", opacity: 1 }, { transform: end, opacity: 0, offset: 0.5 }, { transform: end, opacity: 0 }], { duration, fill: "both" });
    const color = getComputedStyle(b.el).color;
    R.animate(b.el, [{ color: "transparent" }, { color: "transparent", offset: 0.25 }, { color }], { duration, easing: "ease" });
  }

  /**
   * Something that stays, with its insides matched: whatever differs in look eases; changed text cross-fades in
   * place; children only on one side fade.
   */
  function morphTree(R, fx, a, b, o) {
    morphStyle(R, a, b, o.dur, 0, null, o.easing);
    if (leaf(a) || leaf(b)) {
      if (norm(a.textContent) === norm(b.textContent)) return;
      const g = ghostDeep(fx, a);
      fadeGhost(R, g, o);
      if (busy(b)) { const color = getComputedStyle(b).color; R.animate(b, [{ color: "transparent" }, { color }], { duration: o.xdur, easing: "ease" }); }
      else R.animate(b, [{ opacity: 0 }, { opacity: restOpacity(b) }], { duration: o.xdur, easing: "ease" });
      return;
    }
    const ka = childMap(a), kb = childMap(b);
    const going = [...ka.keys()].some((k) => !kb.has(k)); // something here leaves: it gets out of the way before the rest close up
    const ya = rectIn(a).y, yb = rectIn(b).y;
    for (const [k, cb] of kb) {
      const ca = ka.get(k);
      if (!ca) { if (visible(cb)) R.animate(cb, [{ opacity: 0 }, { opacity: restOpacity(cb) }], { duration: o.xdur, easing: "ease" }); continue; }
      ka.delete(k);
      // Inside something that stays, a part that moved slides to its new place rather than jumping.
      const dy = (rectIn(ca).y - ya) - (rectIn(cb).y - yb);
      if (Math.abs(dy) > 0.5) R.animate(cb, [{ transform: `translateY(${dy}px)` }, { transform: restTransform(cb) || "none" }], { duration: o.dur, delay: going ? 80 : 0, easing: o.easing ?? EASE });
      morphTree(R, fx, ca, cb, o);
    }
    for (const ca of ka.values()) if (visible(ca)) fadeGhost(R, ghostDeep(fx, ca), { ...o, xdur: Math.min(o.xdur, 180) });
  }

  function fadeGhost(R, g, o) {
    R.animate(g, [{ opacity: 1 }, { opacity: 0 }], { duration: o.xdur, fill: "both", easing: "linear" });
  }

  // ---------------------------------------------------------------- physics

  /** Raised things rise out of the surface; pressed things sink in; text fades in. */
  function arrive(R, p, delay, plan = {}) {
    const el = p.el, cs = getComputedStyle(el), op = restOpacity(el), rest = restTransform(el);
    if (p.kind === "text") return R.animate(el, [{ opacity: 0 }, { opacity: op }], { duration: plan.toggle ? 300 : plan.slow ? 400 : 300, delay, easing: "ease" });
    const sh = cs.boxShadow, duration = plan.toggle ? 300 : 450;
    if (p.kind === "raised") {
      return R.animate(el, [
        { opacity: 0, transform: `translateY(8px) ${rest}`.trim(), boxShadow: flat(sh) },
        { opacity: op, offset: 0.45 },
        { opacity: op, transform: rest || "none", boxShadow: sh },
      ], { duration, delay });
    }
    return R.animate(el, [ // pressed: the hollow appears, then its inner shadow deepens
      { opacity: 0, boxShadow: flat(sh) },
      { opacity: op, boxShadow: flat(sh), offset: 0.35 },
      { opacity: op, boxShadow: sh },
    ], { duration, delay });
  }

  /** The opposite way out: raised things fade and sink back, pressed things fill back up, text fades. */
  function leave(R, p, delay, plan = {}) {
    const el = p.el, cs = getComputedStyle(el), op = +cs.opacity, rest = restTransform(el);
    const fade = (duration) => R.animate(el, [{ opacity: op }, { opacity: 0 }], { duration, delay, easing: "ease", fill: "both" });
    if (p.kind === "text") return fade(plan.toggle ? 300 : plan.slow ? 300 : 220);
    const sh = cs.boxShadow;
    if (p.kind === "raised") {
      return R.animate(el, [
        { opacity: op, transform: rest || "none", boxShadow: sh },
        { opacity: op * 0.8, boxShadow: flat(sh), offset: 0.5 },
        { opacity: 0, transform: `translateY(6px) ${rest}`.trim(), boxShadow: flat(sh) },
      ], { duration: plan.toggle ? 300 : 380, delay, fill: "both" });
    }
    return R.animate(el, [{ opacity: op, boxShadow: sh }, { opacity: op, boxShadow: flat(sh), offset: 0.55 }, { opacity: 0, boxShadow: flat(sh) }], { duration: 380, delay, fill: "both" });
  }

  /** Eases whatever differs in colour, shadow, borders or opacity from the old copy's look to the new one's. */
  function morphStyle(R, a, b, duration, delay, only, easing = EASE) {
    const ca = getComputedStyle(a), cb = getComputedStyle(b);
    const from = {}, to = {};
    for (const p of only ?? ["color", "backgroundColor", "boxShadow", "opacity", "textDecorationColor", "borderTopColor", "borderBottomColor", "borderLeftColor"]) {
      let x = ca[p], y = cb[p];
      if (x === y) continue;
      if (p === "boxShadow") { // to or from no shadow: the same shadows with no colour
        if (y === "none") y = flat(x); else if (x === "none") x = flat(y);
        if (!sameShape(x, y)) continue;
      }
      if (p === "opacity") y = String(restOpacity(b));
      from[p] = x; to[p] = y;
    }
    if (Object.keys(from).length) R.animate(b, [from, to], { duration, delay, easing });
  }

  // ---------------------------------------------------------------- dots

  /**
   * The picture. The same one in the same place: the new copy takes over (its opacity eased if that differs).
   * Otherwise the dots re-form as How it works does (paired top to bottom, each on its own staggered clock, the
   * count changing quietly, colours blending), drift apart and fade, gather from scattered, arrive or go a few at
   * a time, swap (the old picture's dots go a few at a time while the new one's arrive), or, for the moon with a
   * new count, settle: dots on both stay, the others fade in or out.
   */
  function dots(R, A, B, plan) {
    const opt = plan.dots ?? {}, a = A.pic?.(), b = B.pic?.();
    if (!a && !b) return;
    const pa = a && place(a), pb = b && place(b);
    if (a && b && a.kind === b.kind && same(pa.xy, pb.xy)) { // the same picture: nothing to re-form
      R.hold(a.el, { opacity: 0 });
      if (Math.abs(pa.alpha - pb.alpha) > 0.001) R.animate(b.el, [{ opacity: pa.alpha }, { opacity: pb.alpha }], { duration: plan.toggle ? 300 : 450 });
      return;
    }
    // With one picture only, re-forming means drifting apart or gathering, and swapping means going or arriving.
    const alone = a ? { morph: "disperse", swap: "vanish" } : { morph: "gather", swap: "appear" };
    const mode = a && b ? (a.kind === b.kind && a.kind === "moon-dark" ? "settle" : opt.mode ?? "morph") : alone[opt.mode] ?? opt.mode ?? (a ? "disperse" : "gather");
    const dur = plan.toggle ? 300 : opt.dur ?? 750, delay = opt.delay ?? 0;
    // A picture that is an image (the daylight moon) is scaled by the browser more softly than a canvas is, except
    // at 3x: the dots and the image hand over to each other with a short cross-fade rather than a cut.
    const soft = 160, imgA = a?.el.tagName === "IMG", imgB = b?.el.tagName === "IMG";
    if (a && !imgA) R.hold(a.el, { opacity: 0 });
    const hold = b && R.hold(b.el, { opacity: 0 });
    const P = particles(mode, pa, pb);
    const f = (pb ?? pa).scale; // drawn as the picture it ends as (or starts from), so the hand-over is exact
    const cv = document.createElement("canvas"); // on the surface: under the new screen's text and cards, over the old screen
    cv.className = "fx-dots";
    cv.width = Math.round(390 * f); cv.height = Math.round(844 * f);
    B.el.before(cv);
    R.cleanups.push(() => cv.remove());
    if (imgA) {
      R.animate(a.el, [{ opacity: pa.alpha }, { opacity: 0 }], { duration: soft, easing: "ease", fill: "forwards" });
      R.animate(cv, [{ opacity: 0 }, { opacity: 1 }], { duration: soft, easing: "ease" });
    }
    const g = cv.getContext("2d"), crisp = f === 3 || Math.abs(2 * f - Math.round(2 * f)) < 0.01;
    const size = f === 3 ? 4 : crisp ? Math.max(1, Math.round((4 / 3) * f)) : (4 / 3) * f;
    const at = f === 3 ? (v) => v * 3 : crisp ? (v) => Math.round(v * f) : (v) => v * f;
    const version = B.picVersion?.();
    let t0 = 0, ending = false, landing = false;
    const draw = (p) => {
      const tint = ease(Math.min(1, p / 0.7)), K = P.n;
      g.clearRect(0, 0, cv.width, cv.height);
      let style = "";
      for (let i = 0; i < K; i++) {
        const e = p >= 1 ? 1 : ease(Math.min(1, Math.max(0, (p - P.S[i]) / P.D[i])));
        const c = P.global ? tint : e, q = i * 3;
        const alpha = P.A0[i] + (P.A1[i] - P.A0[i]) * (P.global ? tint : e);
        if (alpha <= 0.003) continue;
        const s = `rgba(${Math.round(P.C0[q] + (P.C1[q] - P.C0[q]) * c)},${Math.round(P.C0[q + 1] + (P.C1[q + 1] - P.C0[q + 1]) * c)},${Math.round(P.C0[q + 2] + (P.C1[q + 2] - P.C0[q + 2]) * c)},${alpha.toFixed(3)})`;
        if (s !== style) { g.fillStyle = s; style = s; }
        g.fillRect(at(P.X0[i] + (P.X1[i] - P.X0[i]) * e), at(P.Y0[i] + (P.Y1[i] - P.Y0[i]) * e), size, size);
      }
    };
    draw(0);
    R.loop((now) => {
      if (!t0) t0 = now + delay;
      if (version !== undefined && B.picVersion() !== version && !ending) { // the new screen moved its picture on: let it show
        ending = true;
        hold?.cancel();
        R.animate(cv, [{ opacity: 1 }, { opacity: 0 }], { duration: 160, fill: "forwards" }).finished.then(() => cv.remove(), () => {});
        return false;
      }
      const p = Math.max(0, Math.min(1, (now - t0) / dur));
      draw(p);
      if (p >= 1 && imgB && !landing) { // the image fades in over the dots as they fade out
        landing = true;
        hold.cancel();
        R.animate(b.el, [{ opacity: 0 }, { opacity: pb.alpha }], { duration: soft, easing: "ease" });
        R.animate(cv, [{ opacity: 1 }, { opacity: 0 }], { duration: soft, easing: "ease", fill: "forwards" }).finished.then(() => cv.remove(), () => {});
        return false;
      }
      if (p >= 1) { hold?.cancel(); cv.remove(); return false; } // the new screen's own canvas takes over, the same picture
    }, delay + dur + (imgB ? soft : 0));
    R.dotsEnd = delay + dur;
  }

  /** A screen's picture in stage points, with its colours (null: ink) and its opacity. */
  function place(pic) {
    const r = rectIn(pic.el), n = pic.pts.length / 2, xy = new Float64Array(n * 2);
    for (let i = 0; i < n; i++) { xy[i * 2] = pic.pts[i * 2] + r.x; xy[i * 2 + 1] = pic.pts[i * 2 + 1] + r.y; }
    return { xy, cols: pic.cols, alpha: +getComputedStyle(pic.el).opacity, scale: pic.scale ?? 3, n };
  }

  /** Where each dot starts and ends, its colours, its opacity, and when within the change it moves. */
  function particles(mode, a, b) {
    const n = mode === "morph" ? Math.max(a.n, b.n) : mode === "settle" ? null : mode === "swap" ? a.n + b.n : (a ?? b).n;
    const make = (k) => ({ n: k, X0: new Float32Array(k), Y0: new Float32Array(k), X1: new Float32Array(k), Y1: new Float32Array(k), C0: new Uint8Array(k * 3), C1: new Uint8Array(k * 3), A0: new Float32Array(k), A1: new Float32Array(k), S: new Float32Array(k), D: new Float32Array(k), global: false });
    const col = (pic, i, out, j) => { for (let c = 0; c < 3; c++) out[j * 3 + c] = pic.cols ? pic.cols[i * 3 + c] : INK[c]; };
    if (mode === "morph") { // as How it works does
      const P = make(n); P.global = true;
      for (let i = 0; i < n; i++) {
        const ia = Math.floor((i * a.n) / n), ib = Math.floor((i * b.n) / n);
        P.X0[i] = a.xy[ia * 2]; P.Y0[i] = a.xy[ia * 2 + 1]; P.X1[i] = b.xy[ib * 2]; P.Y1[i] = b.xy[ib * 2 + 1];
        col(a, ia, P.C0, i); col(b, ib, P.C1, i); P.A0[i] = a.alpha; P.A1[i] = b.alpha;
        P.S[i] = (i / n) * 0.3 + Math.random() * 0.1; P.D[i] = 0.6;
      }
      return P;
    }
    if (mode === "swap") { // the old picture's dots go a few at a time, and the new one's arrive the same way, a little after
      const P = make(n);
      for (let q = 0; q < n; q++) {
        const old = q < a.n, pic = old ? a : b, i = old ? q : q - a.n;
        P.X0[q] = P.X1[q] = pic.xy[i * 2]; P.Y0[q] = P.Y1[q] = pic.xy[i * 2 + 1];
        col(pic, i, P.C0, q); col(pic, i, P.C1, q);
        P.A0[q] = old ? pic.alpha : 0; P.A1[q] = old ? 0 : pic.alpha;
        P.S[q] = old ? Math.random() * 0.55 : 0.2 + Math.random() * 0.6; P.D[q] = old ? 0.25 : 0.2;
      }
      return P;
    }
    if (mode === "settle") { // the moon with a new count: dots on both stay, the rest fade
      const key = (x, y) => `${Math.round(x * 2)},${Math.round(y * 2)}`, inB = new Map();
      for (let i = 0; i < b.n; i++) inB.set(key(b.xy[i * 2], b.xy[i * 2 + 1]), i);
      const list = [];
      for (let i = 0; i < a.n; i++) { const k = key(a.xy[i * 2], a.xy[i * 2 + 1]), j = inB.get(k); if (j !== undefined) { list.push([i, j]); inB.delete(k); } else list.push([i, -1]); }
      inB.forEach((j) => list.push([-1, j]));
      const P = make(list.length);
      list.forEach(([i, j], q) => {
        const src = i >= 0 ? i : j, pic = i >= 0 ? a : b;
        P.X0[q] = P.X1[q] = pic.xy[src * 2]; P.Y0[q] = P.Y1[q] = pic.xy[src * 2 + 1];
        col(pic, src, P.C0, q); col(j >= 0 ? b : a, j >= 0 ? j : i, P.C1, q);
        P.A0[q] = i >= 0 ? a.alpha : 0; P.A1[q] = j >= 0 ? b.alpha : 0;
        if (i >= 0 && j >= 0) { P.S[q] = 0; P.D[q] = 1; } else { P.S[q] = Math.random() * 0.5; P.D[q] = 0.5; }
      });
      return P;
    }
    const pic = a ?? b, P = make(n);
    let cx = 0, cy = 0;
    for (let i = 0; i < n; i++) { cx += pic.xy[i * 2]; cy += pic.xy[i * 2 + 1]; }
    cx /= n; cy /= n;
    for (let i = 0; i < n; i++) {
      const x = pic.xy[i * 2], y = pic.xy[i * 2 + 1];
      col(pic, i, P.C0, i); col(pic, i, P.C1, i);
      if (mode === "appear" || mode === "vanish") { // a few at a time, where they are
        P.X0[i] = P.X1[i] = x; P.Y0[i] = P.Y1[i] = y;
        P.S[i] = Math.random() * 0.8; P.D[i] = 0.2;
        P.A0[i] = mode === "appear" ? 0 : pic.alpha; P.A1[i] = mode === "appear" ? pic.alpha : 0;
        continue;
      }
      // drift apart (or gather): outward from the picture's middle, a little scattered
      const ang = Math.atan2(y - cy, x - cx) + (Math.random() - 0.5) * 0.9, dist = 10 + Math.random() * 34;
      const sx = x + Math.cos(ang) * dist, sy = y + Math.sin(ang) * dist;
      P.S[i] = Math.random() * 0.25; P.D[i] = 0.75;
      if (mode === "disperse") { P.X0[i] = x; P.Y0[i] = y; P.X1[i] = sx; P.Y1[i] = sy; P.A0[i] = pic.alpha; P.A1[i] = 0; }
      else { P.X0[i] = sx; P.Y0[i] = sy; P.X1[i] = x; P.Y1[i] = y; P.A0[i] = 0; P.A1[i] = pic.alpha; }
    }
    return P;
  }

  // ---------------------------------------------------------------- stars

  /** The stars come out, or go out, a few at a time. Both screens with stars: only their opacity eases. */
  function stars(R, a, b, plan) {
    if (a && b) { R.hold(a.el, { opacity: 0 }); morphStyle(R, a.el, b.el, plan.toggle ? 300 : 450, 0, ["opacity"]); return; }
    const p = a ?? b;
    if (!p) return;
    const img = p.el, list = starsFound;
    if (!list || !starsImg) { if (a) leave(R, a, 0, plan); else arrive(R, b, 300, plan); return; } // not ready yet: just fade
    const opt = plan.stars ?? {}, dur = opt.dur ?? 1000, delay = opt.delay ?? 0, out = Boolean(a);
    const cv = document.createElement("canvas");
    cv.className = "stars";
    cv.width = img.naturalWidth; cv.height = img.naturalHeight;
    img.after(cv);
    R.cleanups.push(() => cv.remove());
    const hold = R.hold(img, { opacity: 0 });
    const g = cv.getContext("2d"), when = list.map(() => Math.random() * 0.8);
    let t0 = 0;
    const draw = (p) => {
      g.clearRect(0, 0, cv.width, cv.height);
      list.forEach(([x, y], i) => {
        const q = Math.min(1, Math.max(0, (p - when[i]) / 0.2)), alpha = out ? 1 - q : q;
        if (alpha <= 0) return;
        g.globalAlpha = alpha;
        g.drawImage(starsImg, x, y, 4, 4, x, y, 4, 4);
      });
      g.globalAlpha = 1;
    };
    draw(0);
    R.loop((now) => {
      if (!t0) t0 = now + delay;
      const p = Math.max(0, Math.min(1, (now - t0) / dur));
      draw(p);
      if (p >= 1) { if (!out) { hold.cancel(); cv.remove(); } return false; }
    }, delay + dur);
  }

  function same(a, b) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (Math.abs(a[i] - b[i]) > 0.01) return false;
    return true;
  }

  return { present };
}

// ---------------------------------------------------------------- the bookkeeping of one change

class Run {
  constructor() {
    this.anims = []; this.holds = []; this.loops = new Set(); this.timers = []; this.cleanups = [];
    this.end = 0; this.dotsEnd = 0; this.done = false;
  }
  animate(el, frames, o) {
    const opts = { duration: 450, easing: EASE, fill: "backwards", ...o };
    const a = el.animate(frames, opts);
    this.anims.push(a);
    this.end = Math.max(this.end, (opts.delay ?? 0) + opts.duration);
    return a;
  }
  /** A state kept until the change is over. */
  hold(el, props) {
    const a = el.animate([props, props], { duration: 1e7, fill: "both" });
    this.holds.push(a);
    return a;
  }
  /** fn(now) each frame until it returns false. */
  loop(fn, duration) {
    const tok = { id: 0 };
    this.loops.add(tok);
    this.end = Math.max(this.end, duration);
    const tick = (now) => {
      if (!this.loops.has(tok)) return;
      if (fn(now) === false) { this.loops.delete(tok); return; }
      tok.id = requestAnimationFrame(tick);
    };
    tok.id = requestAnimationFrame(tick);
  }
  after(ms, fn) { this.timers.push(setTimeout(fn, ms)); }
  stopClocks() {
    this.loops.forEach((t) => cancelAnimationFrame(t.id)); this.loops.clear();
    this.timers.forEach(clearTimeout); this.timers = [];
  }
  /** Interrupted: everything stays exactly where it is, to be faded out by the next change. */
  freeze() { this.stopClocks(); this.anims.forEach((a) => a.pause()); }
  finish() {
    if (this.done) return;
    this.done = true;
    this.stopClocks();
    [...this.anims, ...this.holds].forEach((a) => a.cancel());
    this.cleanups.reverse().forEach((fn) => fn());
  }
}

// ---------------------------------------------------------------- small helpers

function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
const norm = (s) => String(s ?? "").replace(/\s+/g, " ").trim();
const visible = (el) => !el.hidden && el.getClientRects().length > 0;
const near = (a, b) => Math.abs(a.x - b.x) < 0.75 && Math.abs(a.y - b.y) < 0.75 && Math.abs(a.w - b.w) < 0.75 && Math.abs(a.h - b.h) < 0.75;
/** No children but text (or a drawn icon). */
const leaf = (el) => [...el.children].every((c) => c.tagName === "BR" || c.tagName.toLowerCase() === "svg");
/** Has a surface of its own (a button, a card): its label fades by colour, not by opacity. */
const busy = (el) => { const cs = getComputedStyle(el); return cs.boxShadow !== "none" || !/rgba\(.*,\s*0\)$|transparent/.test(cs.backgroundColor); };
function luma(c) { const m = c.match(/[\d.]+/g); if (!m) return 1; const [r, g, b, a = 1] = m.map(Number); return a < 0.5 ? 1 : (0.299 * r + 0.587 * g + 0.114 * b) / 255; }

/** The children of an element by a key that survives a re-render: by kind and order. */
function childMap(el) {
  const map = new Map(), n = {};
  for (const c of el.children) {
    const base = `${c.tagName}.${c.classList[0] ?? ""}`;
    map.set(`${base}#${(n[base] = (n[base] ?? -1) + 1)}`, c);
  }
  return map;
}

/** The same shadows with no colour: what a raised or pressed thing has before it rises or sinks. */
function flat(shadow) {
  if (!shadow || shadow === "none") return "none";
  return shadow.replace(/rgba?\(([^)]*)\)/g, (_, inner) => { const p = inner.split(",").map((s) => s.trim()); return `rgba(${p[0]}, ${p[1]}, ${p[2]}, 0)`; });
}
function sameShape(a, b) { // shadows interpolate only between lists of the same length and kind
  const shape = (s) => (s === "none" ? "none" : s.replace(/rgba?\([^)]*\)/g, "").replace(/-?[\d.]+px/g, "").replace(/\s+/g, " ").trim());
  return shape(a) === shape(b);
}
function restTransform(el) { const t = getComputedStyle(el).transform; return t === "none" || el.getAnimations().length ? "" : t; }
/** Where an element's opacity comes to rest. Its own entrance animation (How it works has one) ends at 1. */
function restOpacity(el) { return el.getAnimations().length ? 1 : +getComputedStyle(el).opacity; }

/** The stars in the stars picture: 4 x 4 squares, found once from its pixels (call while nothing is happening). */
let starsFound = null, starsImg = null;
export function warmStars(src) {
  if (starsImg) return;
  const img = new Image();
  img.onload = () => { starsImg = img; starsFound = starList(img); };
  img.src = src;
}
function starList(img) {
  const c = document.createElement("canvas");
  c.width = img.naturalWidth; c.height = img.naturalHeight;
  const g = c.getContext("2d", { willReadFrequently: true });
  g.drawImage(img, 0, 0);
  const d = g.getImageData(0, 0, c.width, c.height).data, w = c.width, list = [];
  const on = (x, y) => x >= 0 && y >= 0 && d[(y * w + x) * 4 + 3] > 0;
  for (let y = 0; y < c.height; y++) for (let x = 0; x < w; x++) if (on(x, y) && !on(x - 1, y) && !on(x, y - 1)) list.push([x, y]);
  return list;
}

/** A copy of an element's text, drawn where the element is, to fade out over the new one. */
function ghost(fx, el, textOnly = false) {
  const stage = fx.parentElement, k = stage.getBoundingClientRect().width / stage.offsetWidth;
  const r = el.getBoundingClientRect(), s = stage.getBoundingClientRect(), cs = getComputedStyle(el);
  const g = document.createElement("div");
  if (textOnly) g.textContent = el.textContent; else g.innerHTML = el.innerHTML;
  Object.assign(g.style, {
    position: "absolute", left: `${(r.left - s.left) / k}px`, top: `${(r.top - s.top) / k}px`, width: `${r.width / k}px`, height: `${r.height / k}px`,
    margin: "0", boxSizing: "border-box", padding: textOnly ? "0" : cs.padding, color: cs.color, textAlign: cs.textAlign, whiteSpace: cs.whiteSpace,
    fontFamily: cs.fontFamily, fontSize: cs.fontSize, fontStyle: cs.fontStyle, fontWeight: cs.fontWeight, lineHeight: cs.lineHeight,
    letterSpacing: cs.letterSpacing, textShadow: cs.textShadow, textDecoration: cs.textDecoration, transformOrigin: "50% 50%",
  });
  if (textOnly) Object.assign(g.style, { display: "flex", alignItems: "center", justifyContent: "center" });
  fx.appendChild(g);
  return g;
}

const LOOK = ["display", "boxSizing", "width", "height", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "marginTop", "marginRight", "marginBottom", "marginLeft",
  "fontFamily", "fontSize", "fontStyle", "fontWeight", "lineHeight", "letterSpacing", "color", "textAlign", "whiteSpace", "overflow", "textOverflow",
  "textDecorationLine", "textDecorationColor", "textUnderlineOffset", "backgroundColor", "borderTopWidth", "borderTopStyle", "borderTopColor",
  "borderBottomWidth", "borderBottomStyle", "borderBottomColor", "borderLeftWidth", "borderLeftStyle", "borderLeftColor", "borderRightWidth",
  "borderRightStyle", "borderRightColor", "borderRadius", "boxShadow", "flexDirection", "justifyContent", "alignItems", "gap", "flexGrow", "flexShrink",
  "flexBasis", "minWidth", "placeItems", "verticalAlign", "fill", "stroke"];
/** A whole copy of an element as it looks now (its look written onto it, so no stylesheet rule can move it), drawn where it is. */
function ghostDeep(fx, el) {
  const stage = fx.parentElement, k = stage.getBoundingClientRect().width / stage.offsetWidth;
  const r = el.getBoundingClientRect(), s = stage.getBoundingClientRect();
  const g = el.cloneNode(true);
  const copy = (src, dst) => {
    if (!(src instanceof Element)) return;
    const cs = getComputedStyle(src);
    if (dst instanceof HTMLElement) { dst.removeAttribute("class"); dst.removeAttribute("id"); for (const p of LOOK) dst.style[p] = cs[p]; }
    for (let i = 0; i < src.children.length; i++) copy(src.children[i], dst.children[i]);
  };
  copy(el, g);
  Object.assign(g.style, { position: "absolute", left: `${(r.left - s.left) / k}px`, top: `${(r.top - s.top) / k}px`, width: `${r.width / k}px`, height: `${r.height / k}px`, margin: "0", boxSizing: "border-box", transformOrigin: "50% 50%", pointerEvents: "none" });
  fx.appendChild(g);
  return g;
}
