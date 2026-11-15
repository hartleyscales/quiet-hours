// Exports the app's true dot layouts (read-only import of the app's own drawing code).
import { readFileSync, writeFileSync } from "node:fs";
import { moonDots } from "../../../web/moon.js";
import { clock, still, fill } from "../../../web/dotart.js";
const data = JSON.parse(readFileSync(new URL("../../../web/assets/moon-col-dark.png.cells.json", import.meta.url)));
const N = 3098; // "3,098 Trojans in" on the Locked screenshot
const dots = moonDots(data, N).map((k) => { const c = data.cells[k]; return [c[0], c[1], c[4], c[5], c[6], c[3]]; });
writeFileSync("data/moon_3098.json", JSON.stringify({ cw: data.cw, ch: data.ch, cx: data.cx, cy: data.cy, r: data.r, dots }));
const st = Array.from(still(clock)), fl = Array.from(fill(clock));
writeFileSync("data/clock.json", JSON.stringify({ still: st, full: fl }));
console.log(dots.length, st.length / 2, fl.length / 2);
