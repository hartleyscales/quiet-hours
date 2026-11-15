// icons.mjs: the app's own dot pictures (web/dotart.js) written out as SVGs for the deck.
import { clock, lock, bubble, fill } from "../../../web/dotart.js";
import { writeFileSync } from "node:fs";
for (const [name, fn] of [["clock", clock], ["lock", lock], ["bubble", bubble]]) {
  const p = fill(fn); let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (let i = 0; i < p.length; i += 2) { x0 = Math.min(x0, p[i]); x1 = Math.max(x1, p[i]); y0 = Math.min(y0, p[i + 1]); y1 = Math.max(y1, p[i + 1]); }
  x0 -= 4; y0 -= 4; x1 += 6; y1 += 6;
  let r = "";
  for (let i = 0; i < p.length; i += 2) r += `<rect x="${Math.round((p[i] - x0) * 3)}" y="${Math.round((p[i + 1] - y0) * 3)}" width="4" height="4"/>`;
  const W = Math.round((x1 - x0) * 3), H = Math.round((y1 - y0) * 3);
  writeFileSync(`../assets/icon_${name}.svg`, `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" fill="#3A342E">${r}</svg>`);
  console.log(name, p.length / 2, "dots", W, H);
}
