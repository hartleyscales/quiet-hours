// The dot pictures from the mocks: the moon's coloured dots re-forming into a clock, a lock and two speech
// bubbles (How it works), and the still pictures on The lock, Home and The question.
// Same shapes, same ordered dither, same timing as design/screens.html.

// Signed distances (negative inside), so edges can be bevelled and lit like the app's buttons.
function sdRR(x, y, x0, y0, x1, y1, r) {
  const qx = Math.abs(x - (x0 + x1) / 2) - ((x1 - x0) / 2 - r), qy = Math.abs(y - (y0 + y1) / 2) - ((y1 - y0) / 2 - r);
  return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - r;
}
const sdC = (x, y, cx, cy, r) => Math.hypot(x - cx, y - cy) - r;
function sdSeg(x, y, ax, ay, bx, by, w) {
  const px = x - ax, py = y - ay, vx = bx - ax, vy = by - ay, h = Math.max(0, Math.min(1, (px * vx + py * vy) / (vx * vx + vy * vy)));
  return Math.hypot(px - vx * h, py - vy * h) - w;
}
const LX = -0.7071, LY = -0.7071; // light from the upper left
function emboss(sd, x, y, w, mid, amt) { // darker where the edge faces away from the light
  const d = sd(x, y);
  if (d > 0) return 0;
  const gx = sd(x + 1, y) - sd(x - 1, y), gy = sd(x, y + 1) - sd(x, y - 1), g = Math.hypot(gx, gy) || 1;
  return Math.min(0.97, Math.max(0.1, mid - amt * Math.max(0, 1 + d / w) * ((gx / g) * LX + (gy / g) * LY)));
}
function cast(sd, x, y) { const d = sd(x - 12, y - 16); return d < 8 ? 0.2 * Math.max(0, Math.min(1, (8 - d) / 16)) : 0; }

export function clock(x, y) {
  const dc = Math.hypot(x - 195, y - 224);
  const rim = (a, b) => Math.abs(Math.hypot(a - 195, b - 224) - 117) - 12;
  let v = emboss(rim, x, y, 12, 0.62, 0.42);
  if (v) return v;
  if (dc < 105) {
    const mh = (a, b) => sdSeg(a, b, 195, 224, 195, 142, 5), hh = (a, b) => sdSeg(a, b, 195, 224, 242, 197, 6);
    v = emboss(hh, x, y, 6, 0.86, 0.22); if (v) return v;
    v = emboss(mh, x, y, 5, 0.86, 0.22); if (v) return v;
    if (dc < 10) return 0.95;
    const k = Math.round(Math.atan2(y - 224, x - 195) / (Math.PI / 6)), a12 = k * (Math.PI / 6), major = k % 3 === 0;
    const off = Math.hypot(x - (195 + Math.cos(a12) * dc), y - (224 + Math.sin(a12) * dc));
    if (dc > (major ? 78 : 86) && dc < 98 && off < (major ? 3.2 : 2.2)) return 0.9;
    const toward = ((x - 195) * LX + (y - 224) * LY) / Math.max(dc, 1);
    const rimShadow = Math.max(0, 1 - (105 - dc) / 18) * Math.max(0, toward);
    const handShadow = Math.min(mh(x - 5, y - 6), hh(x - 5, y - 6)) < 0 ? 0.28 : 0;
    return Math.min(0.6, 0.09 + 0.36 * rimShadow + handShadow);
  }
  return cast((a, b) => sdC(a, b, 195, 224, 129), x, y);
}
export function lock(x, y) {
  const body = (a, b) => sdRR(a, b, 101, 206, 289, 346, 28);
  const shackle = (a, b) => { const d = Math.abs(Math.hypot(a - 195, b - 210) - 64) - 13; return b < 214 ? d : Math.max(d, b - 214); };
  const hole = (a, b) => Math.min(sdC(a, b, 195, 262, 15), sdRR(a, b, 188, 262, 202, 308, 7));
  if (body(x, y) <= 0) {
    const hd = hole(x, y);
    if (hd <= 0) {
      const gx = hole(x + 1, y) - hole(x - 1, y), gy = hole(x, y + 1) - hole(x, y - 1), g = Math.hypot(gx, gy) || 1;
      return hd > -4 && (gx / g) * LX + (gy / g) * LY > 0.2 ? 0.78 : 0.05;
    }
    let v = emboss(body, x, y, 22, 0.6, 0.44);
    if (Math.abs(y - 238) < 1.7 && x > 114 && x < 276) v = Math.max(0.12, v - 0.42);
    return v;
  }
  return emboss(shackle, x, y, 13, 0.62, 0.44) || cast(body, x, y);
}
export function bubble(x, y) {
  const front = (a, b) => {
    const tail = Math.max(b - 344, 296 - b, 108 - a, (a - 168) + (b - 296) * 1.1);
    return Math.min(sdRR(a, b, 72, 142, 290, 300, 36), tail);
  };
  const back = (a, b) => sdRR(a, b, 162, 92, 326, 216, 30);
  const lines = [[106, 178, 256, 192], [106, 214, 256, 228], [106, 250, 200, 264]];
  if (front(x, y) <= 0) {
    for (const L of lines) {
      if (sdRR(x, y, L[0], L[1], L[2], L[3], 7) <= 0) return sdRR(x, y - 2.6, L[0], L[1], L[2], L[3], 7) > 0 ? 0.72 : 0.1;
    }
    return emboss(front, x, y, 22, 0.62, 0.44);
  }
  if (back(x, y) <= 0) {
    const under = front(x - 10, y - 12) < 6 ? 0.22 : 0;
    return Math.min(0.9, emboss(back, x, y, 18, 0.34, 0.3) + under);
  }
  return Math.max(cast(front, x, y), cast(back, x, y) * 0.7);
}
export function phone(x, y) {
  const outer = (a, b) => sdRR(a, b, 121, 46, 269, 376, 32);
  const frame = (a, b) => Math.abs(sdRR(a, b, 126, 51, 264, 371, 27)) - 6;
  const v = emboss(frame, x, y, 6, 0.72, 0.4);
  if (v) return v;
  if (outer(x, y) > 0) return cast(outer, x, y);
  if (sdRR(x, y, 176, 64, 214, 74, 5) <= 0) return 0.8; // the island
  const col = Math.floor((x - 141) / 38), row = Math.floor((y - 92) / 44);
  if (col < 0 || col > 2 || row < 0 || row > 5) return 0.05;
  const x0 = 141 + col * 38, y0 = 92 + row * 44;
  const tile = (a, b) => sdRR(a, b, x0, y0, x0 + 30, y0 + 30, 8);
  if (tile(x, y) > 0) return 0.05;
  const open = (row === 0 && col === 0) || (row === 2 && col === 1) || (row === 4 && col === 2);
  return open ? emboss(tile, x, y, 9, 0.8, 0.3) : 0.24; // three stay solid, the rest fade
}

// 8 x 8 ordered dither.
const M8 = (() => {
  let m = [[0]];
  while (m.length < 8) {
    const s2 = m.length, o = [];
    for (let y = 0; y < s2 * 2; y++) {
      o.push([]);
      for (let x = 0; x < s2 * 2; x++) o[y].push(4 * m[y % s2][x % s2] + [[0, 2], [3, 1]][Math.floor(y / s2)][Math.floor(x / s2)]);
    }
    m = o;
  }
  return m;
})();

/** Dot positions (in points, top-left of each 1.33pt dot) for a picture on the 390 x 460 area. Kept once made. */
const filled = new Map();
export function fill(fn) {
  if (filled.has(fn)) return filled.get(fn);
  const pts = [];
  for (let j = 0; j < 230; j++) for (let i = 0; i < 195; i++) {
    const x = i * 2 + 1, y = j * 2 + 1, d = fn(x, y);
    if (d > 0 && (M8[j & 7][i & 7] + 0.5) / 64 < d) pts.push(x - 0.67, y - 0.67);
  }
  const out = new Float32Array(pts);
  filled.set(fn, out);
  return out;
}

/**
 * A Home's picture: the same shape drawn at 0.8 of its size, centred in the 390 x 340 area under the gear, with
 * the dither laid on that area's own grid (as the Homes mock draws it). Dot positions in points; kept once made.
 */
const stills = new Map();
export function still(fn) {
  if (stills.has(fn)) return stills.get(fn);
  const pts = [], scale = 0.8, cx = 195, cy = 196;
  for (let j = 0; j < 170; j++) for (let i = 0; i < 195; i++) {
    const x = i * 2 + 1, y = j * 2 + 1, d = fn(195 + (x - cx) / scale, 224 + (y - cy) / scale);
    if (d > 0 && (M8[j & 7][i & 7] + 0.5) / 64 < d) pts.push(x - 0.67, y - 0.67);
  }
  const out = new Float32Array(pts);
  stills.set(fn, out);
  return out;
}

/** The sign-in moon as dots: positions top to bottom and each dot's colour (moon-col-light.png.json). */
export function lightMoon(light) {
  const mp = light.map(([i, j, r, g, b]) => [i * 2 + 0.33, j * 2 + 0.33, r, g, b]);
  mp.sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  const n = mp.length, pts = new Float32Array(n * 2), cols = new Uint8Array(n * 3);
  mp.forEach((p, q) => { pts[q * 2] = p[0]; pts[q * 2 + 1] = p[1]; cols[q * 3] = p[2]; cols[q * 3 + 1] = p[3]; cols[q * 3 + 2] = p[4]; });
  return { pts, cols };
}

const INK = "#3A342E";

/** One picture in ink on a canvas drawn at 3x, as in the mocks. `pts` defaults to the full-size picture. */
export function drawFilled(canvas, fn, pts = fill(fn)) {
  const g = canvas.getContext("2d"), p = pts;
  g.clearRect(0, 0, canvas.width, canvas.height);
  g.fillStyle = INK;
  for (let w = 0; w < p.length / 2; w++) g.fillRect(p[w * 2] * 3, p[w * 2 + 1] * 3, 4, 4);
}
/** A Home's picture (still) in ink on its canvas. */
export const drawStill = (canvas, fn) => drawFilled(canvas, fn, still(fn));

const COPY = [
  ["Quiet Hours", "", "Next"],
  ["Vote on the hour.", "Each week the campus picks one window of time. You get a say.", "Next"],
  ["Then it goes quiet.", "When it starts, your distracting apps lock. So do everyone else's.", "Next"],
  ["Hear how it went.", "Afterwards, read what people did with the time.", "Got it"],
];

/**
 * How it works. `box` is the screen (.s.hw) holding canvas, .step, .sub, .pips and .go; `light` is
 * moon-col-light.png.json ([i, j, r, g, b] per dot). Calls onDone after "Got it".
 * Returns { stop, snapshot }: snapshot() is the picture as it stands (for a transition to carry on from).
 */
export function howItWorks(box, light, onDone) {
  const { pts: moon, cols: mcol } = lightMoon(light); // the moon's dots carry colour
  const n = moon.length / 2;

  const states = [moon, fill(clock), fill(lock), fill(bubble)];
  const cv = box.querySelector("canvas"), ctx = cv.getContext("2d");
  const h = box.querySelector(".step"), s = box.querySelector(".sub"), btn = box.querySelector(".go"), pips = box.querySelectorAll(".pips i");
  let MAXK = 0;
  states.forEach((st) => { MAXK = Math.max(MAXK, st.length / 2); });
  const jitter = new Float32Array(MAXK);
  for (let r = 0; r < MAXK; r++) jitter[r] = Math.random() * 0.1;
  let cur = new Float32Array(states[0]), from = cur, to = cur, K = cur.length / 2, target = states[0], step = 0, start = 0, running = false, stopped = false;
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  let tint = 1, tintFrom = 1, tintTo = 1; // 1 = the moon's own colours, 0 = ink

  function draw() {
    const c = cur.length / 2;
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.fillStyle = INK;
    if (tint <= 0.01) { for (let i = 0; i < c; i++) ctx.fillRect(cur[i * 2] * 3, cur[i * 2 + 1] * 3, 4, 4); return; }
    for (let i = 0; i < c; i++) {
      const m = Math.floor((i * n) / c) * 3;
      ctx.fillStyle = `rgb(${Math.round(58 + (mcol[m] - 58) * tint)},${Math.round(52 + (mcol[m + 1] - 52) * tint)},${Math.round(46 + (mcol[m + 2] - 46) * tint)})`;
      ctx.fillRect(cur[i * 2] * 3, cur[i * 2 + 1] * 3, 4, 4);
    }
  }
  function frame(now) {
    if (!running || stopped) return;
    const p = Math.min(1, (now - start) / 1100);
    if (p >= 1) { cur = new Float32Array(target); running = false; tint = tintTo; draw(); return; }
    tint = tintFrom + (tintTo - tintFrom) * ease(Math.min(1, p / 0.7));
    for (let i = 0; i < K; i++) {
      const e = ease(Math.min(1, Math.max(0, (p - (i / K) * 0.3 - jitter[i]) / 0.6)));
      cur[i * 2] = from[i * 2] + (to[i * 2] - from[i * 2]) * e;
      cur[i * 2 + 1] = from[i * 2 + 1] + (to[i * 2 + 1] - from[i * 2 + 1]) * e;
    }
    draw();
    requestAnimationFrame(frame);
  }
  function label() {
    h.textContent = COPY[step][0]; s.textContent = COPY[step][1]; btn.textContent = COPY[step][2];
    for (let i = 0; i < pips.length; i++) pips[i].className = i === step - 1 ? "on" : "";
    box.classList.remove("in"); void box.offsetWidth; box.classList.add("in");
  }
  function go(next) {
    step = next; version++; label();
    const A = cur, B = states[step], a = A.length / 2, b = B.length / 2;
    target = B; tintFrom = tint; tintTo = step === 0 ? 1 : 0;
    if (reduce) { running = false; cur = new Float32Array(B); tint = tintTo; draw(); return; }
    K = Math.max(a, b); from = new Float32Array(K * 2); to = new Float32Array(K * 2);
    for (let i = 0; i < K; i++) {
      const ia = Math.floor((i * a) / K), ib = Math.floor((i * b) / K);
      from[i * 2] = A[ia * 2]; from[i * 2 + 1] = A[ia * 2 + 1]; to[i * 2] = B[ib * 2]; to[i * 2 + 1] = B[ib * 2 + 1];
    }
    cur = new Float32Array(from); running = true; start = performance.now(); requestAnimationFrame(frame);
  }
  btn.addEventListener("click", () => (step === 3 ? onDone() : go(step + 1)));
  label(); draw();
  let first = setTimeout(() => { if (step === 0) go(1); }, 900), version = 0;
  const KINDS = ["moon-light", "clock", "lock", "bubble"];
  return {
    stop() { stopped = true; clearTimeout(first); },
    /** The picture is busy arriving for `ms`: the first step waits for it, then runs as it always does. */
    delayFirst(ms) {
      if (!ms || step !== 0 || running || stopped) return;
      clearTimeout(first);
      first = setTimeout(() => { if (step === 0) go(1); }, ms + 900);
    },
    version: () => version,
    snapshot() {
      const c = cur.length / 2;
      let cols = null;
      if (tint > 0.01) {
        cols = new Uint8Array(c * 3);
        for (let i = 0; i < c; i++) {
          const m = Math.floor((i * n) / c) * 3;
          cols[i * 3] = Math.round(58 + (mcol[m] - 58) * tint); cols[i * 3 + 1] = Math.round(52 + (mcol[m + 1] - 52) * tint); cols[i * 3 + 2] = Math.round(46 + (mcol[m + 2] - 46) * tint);
        }
      }
      return { kind: running ? "how-moving" : KINDS[step], pts: new Float32Array(cur), cols, scale: 3 };
    },
  };
}
