// The Locked moon: one fixed drawing of N dots (the app always asks for the same N).
// A port of design/scripts/color_moon.py, mode "dark" with N: a serpentine Floyd-Steinberg dither of
// min(0.97, density * gain), a bisection on the gain so the dot count reaches N, an even rim that follows the
// density just inside it, then trimming or topping up the inside so the count is exactly N.
// Seeded, so the same N always gives the same moon. Works in the browser and in Node (for checking).

/** A small seeded generator (mulberry32). Returns floats in [0, 1). */
function seeded(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let x = Math.imul(a ^ (a >>> 15), 1 | a);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}
const below = (rnd, n) => Math.floor(rnd() * n);

/** The cell indices (into data.cells) that carry a dot for N people. */
export function moonDots(data, N) {
  const { cw: CW, ch: CH, cx: MX, cy: MY, r: MR, cells } = data;
  const total = cells.length;
  N = Math.max(0, Math.floor(N || 0));
  if (N === 0) return [];
  if (N >= total) return cells.map((_, k) => k);

  const grid = new Int32Array(CW * CH).fill(-1);
  cells.forEach((c, k) => (grid[c[1] * CW + c[0]] = k));
  const at = (i, j) => (i >= 0 && i < CW && j >= 0 && j < CH ? grid[j * CW + i] : -1);
  const density = Float64Array.from(cells, (c) => c[2]);
  const err = new Float64Array(CW * CH);

  function dither(gain) {
    err.fill(0);
    const on = [];
    for (let j = 0; j < CH; j++) {
      const s = j % 2 === 0 ? 1 : -1;
      for (let n = 0; n < CW; n++) {
        const i = s === 1 ? n : CW - 1 - n;
        const k = grid[j * CW + i];
        if (k < 0) continue;
        const v = Math.min(0.97, density[k] * gain) + err[j * CW + i];
        const o = v >= 0.5 ? 1 : 0;
        const e = v - o;
        if (o) on.push(k);
        if (at(i + s, j) >= 0) err[j * CW + i + s] += (e * 7) / 16;
        if (j + 1 < CH) {
          if (at(i - s, j + 1) >= 0) err[(j + 1) * CW + i - s] += (e * 3) / 16;
          if (at(i, j + 1) >= 0) err[(j + 1) * CW + i] += (e * 5) / 16;
          if (at(i + s, j + 1) >= 0) err[(j + 1) * CW + i + s] += (e * 1) / 16;
        }
      }
    }
    return on;
  }

  // The gain that brings the dither to N dots.
  let lo = 0.05, hi = 3.0;
  for (let q = 0; q < 30; q++) {
    const g = (lo + hi) / 2;
    if (dither(g).length < N) lo = g;
    else hi = g;
  }
  const on = dither(hi);
  const r7 = seeded(7);
  while (on.length > N) on.splice(below(r7, on.length), 1);

  // The rim: dots exactly on the disc's edge, evenly spaced, their spacing following the density just inside.
  const isRim = (k) => cells[k][3] === 1;
  const ring = [];
  cells.forEach((c, k) => { if (c[3] === 1) ring.push(k); });          // row-major, as the original builds it
  const angle = (k) => Math.atan2(cells[k][1] - MY, cells[k][0] - MX);
  ring.sort((a, b) => angle(a) - angle(b));
  const onset = new Set(on);
  const local = (k) => {
    const [i, j] = cells[k];
    let tot = 0, hit = 0;
    for (let b = -4; b <= 4; b++) for (let a = -4; a <= 4; a++) {
      const q = at(i + a, j + b);
      if (q >= 0 && !isRim(q)) { tot++; if (onset.has(q)) hit++; }
    }
    return tot ? hit / tot : 0;
  };
  const m = ring.length;
  const raw = ring.map(local);
  const dens = raw.map((_, k) => { let s = 0; for (let d = -3; d <= 3; d++) s += raw[(((k + d) % m) + m) % m]; return s / 7; });
  const edge = [];
  let acc = 0.5;
  ring.forEach((k, n) => {
    acc += Math.min(1, Math.max(0.3, Math.sqrt(dens[n]) * 1.1));
    if (acc >= 1) { edge.push(k); acc -= 1; }
  });

  const keep = new Set(on.filter((k) => !isRim(k)));
  edge.forEach((k) => keep.add(k));
  const r5 = seeded(5);
  if (keep.size > N) {
    // Trim the inside first (shuffled, from a fixed order).
    const inner = [...keep].filter((k) => !isRim(k)).sort((a, b) => cells[a][0] - cells[b][0] || cells[a][1] - cells[b][1]);
    for (let i = inner.length - 1; i > 0; i--) { const j = below(r5, i + 1); [inner[i], inner[j]] = [inner[j], inner[i]]; }
    while (keep.size > N && inner.length) keep.delete(inner.pop());
    // So few people that even the rim is too many: keep N rim dots, evenly spaced around it.
    if (keep.size > N) {
      keep.clear();
      for (let q = 0; q < N; q++) keep.add(edge[Math.floor(((q + 0.5) * edge.length) / N)]);
    }
  } else if (keep.size < N) {
    // Top up the inside, brightest cells first, with a little randomness.
    const spare = [];
    cells.forEach((c, k) => { if (!isRim(k) && !keep.has(k)) spare.push(k); });
    const key = new Map(spare.map((k) => [k, -brightness(cells[k], MX, MY, MR) + r5() * 0.2]));
    spare.sort((a, b) => key.get(a) - key.get(b));
    for (const k of spare) { if (keep.size >= N) break; keep.add(k); }
    // Every inside cell is lit and still short: light the rest of the rim, evenly.
    if (keep.size < N) {
      const rest = ring.filter((k) => !keep.has(k));
      const need = N - keep.size;
      for (let q = 0; q < need; q++) keep.add(rest[Math.floor(((q + 0.5) * rest.length) / need)]);
    }
  }
  return [...keep].sort((a, b) => cells[a][1] - cells[b][1] || cells[a][0] - cells[b][0]);
}

/** A cell's brightness before shading (the original's `a`), recovered from its stored density. */
function brightness(c, MX, MY, MR) {
  const x = (c[0] - MX) / MR, y = -(c[1] - MY) / MR;
  const z = Math.sqrt(Math.max(0, 1 - x * x - y * y));
  const s = Math.min(1, Math.max(0, (c[2] / (1 - 0.3 * Math.pow(1 - z, 2.2)) - 0.1) / 0.82));
  const u = 0.5 - Math.sin(Math.asin(1 - 2 * s) / 3);            // inverse smoothstep
  return 0.18 + 0.64 * u;
}

/**
 * Draws the dots on a canvas whose CSS box is 390 x 240 (points), at `scale` device pixels per point.
 * Cells are 2pt, dots are 1.33pt squares, each in its own colour.
 */
export function drawMoon(canvas, data, dots, scale) {
  const W = Math.round(390 * scale), H = Math.round(240 * scale);
  if (canvas.width !== W) canvas.width = W;
  if (canvas.height !== H) canvas.height = H;
  const g = canvas.getContext("2d");
  g.clearRect(0, 0, W, H);
  // Whole-pixel squares when the 2pt pitch is a whole number of pixels; otherwise rounding would space the dots
  // unevenly (a visible beat), so they are drawn where they fall and the edges are smoothed, as a scaled image is.
  const crisp = Math.abs(2 * scale - Math.round(2 * scale)) < 0.01;
  const size = crisp ? Math.max(1, Math.round((4 / 3) * scale)) : (4 / 3) * scale;
  const at = crisp ? (v) => Math.round(v * scale) : (v) => v * scale;
  for (const k of dots) {
    const c = data.cells[k];
    g.fillStyle = `rgb(${c[4]},${c[5]},${c[6]})`;
    g.fillRect(at(c[0] * 2 + 1 / 3), at(c[1] * 2 + 1 / 3), size, size);
  }
}
