"""Assemble the Quiet Hours screens page (artifact fragment) and a local preview copy."""
import base64, json, sys
S = sys.argv[1]

HOW_JS = """
<script>
(function () {
  var raw = atob("__DOTS__"), n = raw.length / 6, mp = [];
  for (var i = 0; i < n; i++) mp.push([raw.charCodeAt(i * 6) * 2 + 0.33, ((raw.charCodeAt(i * 6 + 1) << 8) | raw.charCodeAt(i * 6 + 2)) * 2 + 0.33, raw.charCodeAt(i * 6 + 3), raw.charCodeAt(i * 6 + 4), raw.charCodeAt(i * 6 + 5)]);
  mp.sort(function (a, b) { return a[1] - b[1] || a[0] - b[0]; });
  var moon = new Float32Array(n * 2), mcol = new Uint8Array(n * 3);   // the moon's dots carry colour; the other pictures are one ink
  for (var q = 0; q < n; q++) { moon[q * 2] = mp[q][0]; moon[q * 2 + 1] = mp[q][1]; mcol[q * 3] = mp[q][2]; mcol[q * 3 + 1] = mp[q][3]; mcol[q * 3 + 2] = mp[q][4]; }

  // Signed distances (negative inside), so edges can be bevelled and lit like the app's buttons.
  function sdRR(x, y, x0, y0, x1, y1, r) {
    var qx = Math.abs(x - (x0 + x1) / 2) - ((x1 - x0) / 2 - r), qy = Math.abs(y - (y0 + y1) / 2) - ((y1 - y0) / 2 - r);
    return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - r;
  }
  function sdC(x, y, cx, cy, r) { return Math.hypot(x - cx, y - cy) - r; }
  function sdSeg(x, y, ax, ay, bx, by, w) {
    var px = x - ax, py = y - ay, vx = bx - ax, vy = by - ay, h = Math.max(0, Math.min(1, (px * vx + py * vy) / (vx * vx + vy * vy)));
    return Math.hypot(px - vx * h, py - vy * h) - w;
  }
  var LX = -0.7071, LY = -0.7071;           // light from the upper left
  function emboss(sd, x, y, w, mid, amt) {  // darker where the edge faces away from the light
    var d = sd(x, y); if (d > 0) return 0;
    var gx = sd(x + 1, y) - sd(x - 1, y), gy = sd(x, y + 1) - sd(x, y - 1), g = Math.hypot(gx, gy) || 1;
    return Math.min(0.97, Math.max(0.1, mid - amt * Math.max(0, 1 + d / w) * ((gx / g) * LX + (gy / g) * LY)));
  }
  function cast(sd, x, y) { var d = sd(x - 12, y - 16); return d < 8 ? 0.2 * Math.max(0, Math.min(1, (8 - d) / 16)) : 0; }

  function clock(x, y) {
    var dc = Math.hypot(x - 195, y - 224);
    var rim = function (a, b) { return Math.abs(Math.hypot(a - 195, b - 224) - 117) - 12; };
    var v = emboss(rim, x, y, 12, 0.62, 0.42); if (v) return v;
    if (dc < 105) {
      var mh = function (a, b) { return sdSeg(a, b, 195, 224, 195, 142, 5); }, hh = function (a, b) { return sdSeg(a, b, 195, 224, 242, 197, 6); };
      v = emboss(hh, x, y, 6, 0.86, 0.22); if (v) return v;
      v = emboss(mh, x, y, 5, 0.86, 0.22); if (v) return v;
      if (dc < 10) return 0.95;
      var k = Math.round(Math.atan2(y - 224, x - 195) / (Math.PI / 6)), a12 = k * (Math.PI / 6), major = k % 3 === 0;
      var off = Math.hypot(x - (195 + Math.cos(a12) * dc), y - (224 + Math.sin(a12) * dc));
      if (dc > (major ? 78 : 86) && dc < 98 && off < (major ? 3.2 : 2.2)) return 0.9;
      var toward = ((x - 195) * LX + (y - 224) * LY) / Math.max(dc, 1);
      var rimShadow = Math.max(0, 1 - (105 - dc) / 18) * Math.max(0, toward);
      var handShadow = Math.min(mh(x - 5, y - 6), hh(x - 5, y - 6)) < 0 ? 0.28 : 0;
      return Math.min(0.6, 0.09 + 0.36 * rimShadow + handShadow);
    }
    return cast(function (a, b) { return sdC(a, b, 195, 224, 129); }, x, y);
  }
  function lock(x, y) {
    var body = function (a, b) { return sdRR(a, b, 101, 206, 289, 346, 28); };
    var shackle = function (a, b) { var d = Math.abs(Math.hypot(a - 195, b - 210) - 64) - 13; return b < 214 ? d : Math.max(d, b - 214); };
    var hole = function (a, b) { return Math.min(sdC(a, b, 195, 262, 15), sdRR(a, b, 188, 262, 202, 308, 7)); };
    if (body(x, y) <= 0) {
      var hd = hole(x, y);
      if (hd <= 0) {
        var gx = hole(x + 1, y) - hole(x - 1, y), gy = hole(x, y + 1) - hole(x, y - 1), g = Math.hypot(gx, gy) || 1;
        return hd > -4 && (gx / g) * LX + (gy / g) * LY > 0.2 ? 0.78 : 0.05;
      }
      var v = emboss(body, x, y, 22, 0.6, 0.44);
      if (Math.abs(y - 238) < 1.7 && x > 114 && x < 276) v = Math.max(0.12, v - 0.42);
      return v;
    }
    return emboss(shackle, x, y, 13, 0.62, 0.44) || cast(body, x, y);
  }
  function bubble(x, y) {
    var front = function (a, b) {
      var tail = Math.max(b - 344, 296 - b, 108 - a, (a - 168) + (b - 296) * 1.1);
      return Math.min(sdRR(a, b, 72, 142, 290, 300, 36), tail);
    };
    var back = function (a, b) { return sdRR(a, b, 162, 92, 326, 216, 30); };
    var lines = [[106, 178, 256, 192], [106, 214, 256, 228], [106, 250, 200, 264]];
    if (front(x, y) <= 0) {
      for (var q = 0; q < 3; q++) {
        var L = lines[q];
        if (sdRR(x, y, L[0], L[1], L[2], L[3], 7) <= 0) return sdRR(x, y - 2.6, L[0], L[1], L[2], L[3], 7) > 0 ? 0.72 : 0.1;
      }
      return emboss(front, x, y, 22, 0.62, 0.44);
    }
    if (back(x, y) <= 0) {
      var under = front(x - 10, y - 12) < 6 ? 0.22 : 0;
      return Math.min(0.9, emboss(back, x, y, 18, 0.34, 0.3) + under);
    }
    return Math.max(cast(front, x, y), cast(back, x, y) * 0.7);
  }
  function phone(x, y) {
    var outer = function (a, b) { return sdRR(a, b, 121, 46, 269, 376, 32); };
    var frame = function (a, b) { return Math.abs(sdRR(a, b, 126, 51, 264, 371, 27)) - 6; };
    var v = emboss(frame, x, y, 6, 0.72, 0.4); if (v) return v;
    if (outer(x, y) > 0) return cast(outer, x, y);
    if (sdRR(x, y, 176, 64, 214, 74, 5) <= 0) return 0.8;                      // the island
    var col = Math.floor((x - 141) / 38), row = Math.floor((y - 92) / 44);
    if (col < 0 || col > 2 || row < 0 || row > 5) return 0.05;
    var x0 = 141 + col * 38, y0 = 92 + row * 44;
    var tile = function (a, b) { return sdRR(a, b, x0, y0, x0 + 30, y0 + 30, 8); };
    if (tile(x, y) > 0) return 0.05;
    var open = (row === 0 && col === 0) || (row === 2 && col === 1) || (row === 4 && col === 2);
    return open ? emboss(tile, x, y, 9, 0.8, 0.3) : 0.24;                    // three stay solid, the rest fade
  }
  var shapes = [clock, lock, bubble];
  var M8 = (function () { var m = [[0]]; while (m.length < 8) { var s2 = m.length, o = []; for (var y = 0; y < s2 * 2; y++) { o.push([]); for (var x = 0; x < s2 * 2; x++) o[y].push(4 * m[y % s2][x % s2] + [[0, 2], [3, 1]][Math.floor(y / s2)][Math.floor(x / s2)]); } m = o; } return m; })();
  function fill(fn) {
    var pts = [];
    for (var j = 0; j < 230; j++) for (var i2 = 0; i2 < 195; i2++) {
      var x = i2 * 2 + 1, y = j * 2 + 1, d = fn(x, y);
      if (d > 0 && (M8[j & 7][i2 & 7] + 0.5) / 64 < d) pts.push(x - 0.67, y - 0.67);
    }
    return new Float32Array(pts);
  }
  var states = [moon, fill(shapes[0]), fill(shapes[1]), fill(shapes[2])];
  var copy = [
    ["Quiet Hours", "", "Next"],
    ["Vote on the hour.", "Each week the campus picks one window of time. You get a say.", "Next"],
    ["Then it goes quiet.", "When it starts, your distracting apps lock. So do everyone else's.", "Next"],
    ["Hear how it went.", "Afterwards, read what people did with the time.", "Got it"]
  ];
  var cv = document.getElementById("hwc"), ctx = cv.getContext("2d"), box = document.getElementById("hw");
  var h = document.getElementById("hwh"), s = document.getElementById("hws"), btn = document.getElementById("hwb"), pips = box.querySelectorAll(".pips i");
  var MAXK = 0; states.forEach(function (st) { MAXK = Math.max(MAXK, st.length / 2); });
  var jitter = new Float32Array(MAXK); for (var r = 0; r < MAXK; r++) jitter[r] = Math.random() * 0.1;
  var cur = new Float32Array(states[0]), from = cur, to = cur, K = cur.length / 2, target = states[0], step = 0, start = 0, running = false;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  var tint = 1, tintFrom = 1, tintTo = 1;     // 1 = the moon's own colours, 0 = ink
  function draw() {
    var c = cur.length / 2, i;
    ctx.clearRect(0, 0, cv.width, cv.height); ctx.fillStyle = "#3A342E";
    if (tint <= 0.01) { for (i = 0; i < c; i++) ctx.fillRect(cur[i * 2] * 3, cur[i * 2 + 1] * 3, 4, 4); return; }
    for (i = 0; i < c; i++) {
      var m = Math.floor(i * n / c) * 3;
      ctx.fillStyle = "rgb(" + Math.round(58 + (mcol[m] - 58) * tint) + "," + Math.round(52 + (mcol[m + 1] - 52) * tint) + "," + Math.round(46 + (mcol[m + 2] - 46) * tint) + ")";
      ctx.fillRect(cur[i * 2] * 3, cur[i * 2 + 1] * 3, 4, 4);
    }
  }
  function frame(now) {
    if (!running) return;
    var p = Math.min(1, (now - start) / 1100);
    if (p >= 1) { cur = new Float32Array(target); running = false; tint = tintTo; draw(); return; }
    tint = tintFrom + (tintTo - tintFrom) * ease(Math.min(1, p / 0.7));
    for (var i = 0; i < K; i++) {
      var e = ease(Math.min(1, Math.max(0, (p - (i / K) * 0.3 - jitter[i]) / 0.6)));
      cur[i * 2] = from[i * 2] + (to[i * 2] - from[i * 2]) * e; cur[i * 2 + 1] = from[i * 2 + 1] + (to[i * 2 + 1] - from[i * 2 + 1]) * e;
    }
    draw(); requestAnimationFrame(frame);
  }
  function label() {
    h.textContent = copy[step][0]; s.textContent = copy[step][1]; btn.textContent = copy[step][2];
    for (var i = 0; i < pips.length; i++) pips[i].className = i === step - 1 ? "on" : "";
    box.classList.remove("in"); void box.offsetWidth; box.classList.add("in");
  }
  function go(next) {
    step = next; label();
    var A = cur, B = states[step], a = A.length / 2, b = B.length / 2;
    target = B; tintFrom = tint; tintTo = step === 0 ? 1 : 0;
    if (reduce) { running = false; cur = new Float32Array(B); tint = tintTo; draw(); return; }
    K = Math.max(a, b); from = new Float32Array(K * 2); to = new Float32Array(K * 2);
    for (var i = 0; i < K; i++) {
      var ia = Math.floor(i * a / K), ib = Math.floor(i * b / K);
      from[i * 2] = A[ia * 2]; from[i * 2 + 1] = A[ia * 2 + 1]; to[i * 2] = B[ib * 2]; to[i * 2 + 1] = B[ib * 2 + 1];
    }
    cur = new Float32Array(from); running = true; start = performance.now(); requestAnimationFrame(frame);
  }
  btn.addEventListener("click", function () { go(step === 3 ? 0 : step + 1); });
  function still(id, fn, scale, cx, cy) {     // draw one picture, scaled, on a static canvas
    var c = document.getElementById(id); if (!c) return;
    var g = c.getContext("2d"), cols = Math.floor(c.width / 6), rows = Math.floor(c.height / 6);
    g.fillStyle = "#3A342E";
    for (var j = 0; j < rows; j++) for (var i2 = 0; i2 < cols; i2++) {
      var x = i2 * 2 + 1, y = j * 2 + 1, d = fn(195 + (x - cx) / scale, 224 + (y - cy) / scale);
      if (d > 0 && (M8[j & 7][i2 & 7] + 0.5) / 64 < d) g.fillRect((x - 0.67) * 3, (y - 0.67) * 3, 4, 4);
    }
  }
  still("hmc", clock, 0.56, 195, 96);
  still("hmc2", clock, 0.56, 195, 96);
  var opts = document.querySelectorAll("#hm .opt");
  function pick(el) {
    for (var i = 0; i < opts.length; i++) {
      var on = opts[i] === el, base = +opts[i].getAttribute("data-n"), n2 = base + (on ? 1 : 0);
      opts[i].classList.toggle("on", on); opts[i].setAttribute("aria-pressed", on ? "true" : "false");
      opts[i].querySelector(".n").textContent = n2.toLocaleString("en-US") + " votes";
      opts[i].querySelector(".track b").style.width = Math.round(n2 / 1204 * 100) + "%";
    }
  }
  for (var o = 0; o < opts.length; o++) opts[o].addEventListener("click", function () { pick(this); });
  Array.prototype.forEach.call(document.querySelectorAll(".brd"), function (dy) {
    var tray = dy.getAttribute("data-board") === "tr", PITCH = +dy.getAttribute("data-pitch") || 88, R = tray ? 162 : 166, LAST = tray ? 652 : (+dy.getAttribute("data-bottom") || 718) - PITCH;
    var list = Array.prototype.slice.call(dy.querySelectorAll(".pc")), sy = 0, maxS = 0, liveT = 0, drag = null;
    var lay = function () {
      maxS = Math.max(0, (list.length - 1) * PITCH - (LAST - R));
      sy = Math.max(0, Math.min(maxS, sy));
      for (var c = 0; c < list.length; c++) {
        list[c].style.setProperty("--i", c);
        list[c].style.setProperty("--y", (R + c * PITCH - sy).toFixed(1) + "px");
        list[c].classList.toggle("h", c > 2);
      }
    };
    var settle = function () { clearTimeout(liveT); liveT = setTimeout(function () { if (dy.classList.contains("open")) dy.classList.add("live"); }, 650); };
    dy.querySelector(".stkbtn").addEventListener("click", function () { sy = 0; lay(); dy.classList.add("open"); settle(); });
    dy.querySelector(".x").addEventListener("click", function () { clearTimeout(liveT); dy.classList.remove("live"); dy.classList.remove("open"); });
    dy.addEventListener("wheel", function (e) { if (!dy.classList.contains("open")) return; e.preventDefault(); dy.classList.add("live"); sy += e.deltaY; lay(); }, { passive: false });
    dy.addEventListener("pointerdown", function (e) { if (dy.classList.contains("open") && !e.target.closest("button")) drag = { y: e.clientY, s: sy }; });
    window.addEventListener("pointermove", function (e) { if (!drag) return; dy.classList.add("live"); sy = drag.s + (drag.y - e.clientY); lay(); });
    window.addEventListener("pointerup", function () { drag = null; });
    var td = dy.querySelector(".td");
    if (td) td.addEventListener("click", function () {   // your own post leaves, the rest close the gap
      var mine = this.parentNode, k = list.indexOf(mine);
      if (k < 0) return;
      clearTimeout(liveT); dy.classList.remove("live");
      list.splice(k, 1); mine.classList.add("gone");
      dy.querySelector(".n1").textContent = list.length;
      dy.querySelector(".n2").textContent = list.length;
      setTimeout(function () { mine.style.display = "none"; lay(); settle(); }, 260);
    });
    lay();
  });
  var qc = document.getElementById("qc");
  if (qc) {
    var qp = fill(shapes[2]), qx = qc.getContext("2d");
    qx.fillStyle = "#3A342E";
    for (var w = 0; w < qp.length / 2; w++) qx.fillRect(qp[w * 2] * 3, qp[w * 2 + 1] * 3, 4, 4);
  }
  // Homes, V9: choosing a window, and pulling the board's sheet up and down.
  Array.prototype.forEach.call(document.querySelectorAll("button.o9"), function (b) {
    b.addEventListener("click", function () {
      Array.prototype.forEach.call(b.parentNode.querySelectorAll(".o9"), function (o) { o.classList.toggle("on", o === b); });
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll(".board9"), function (sh) {
    var more = sh.querySelector(".s9more"), list = sh.querySelector(".s9list"), label = more.textContent;
    more.addEventListener("click", function () {
      var open = sh.classList.toggle("open");
      more.textContent = open ? "Close" : label;
      if (!open) list.scrollTop = 0;
    });
  });
  var lk = document.getElementById("lkc");
  if (lk) {
    var lp = fill(phone), lx = lk.getContext("2d");
    lx.fillStyle = "#3A342E";
    for (var z = 0; z < lp.length / 2; z++) lx.fillRect(lp[z * 2] * 3, lp[z * 2 + 1] * 3, 4, 4);
  }
  label(); draw();
  setTimeout(function () { if (step === 0) go(1); }, 900);
})();
</script>
"""

HOW_JS_PLACEHOLDER = 0
HOLES_JS = """
<script>
(function () {
  // Fill the enclosed holes of the name's letters (Q, e, o) with the surface colour, so no dots show through them.
  function run() {
    document.querySelectorAll(".s").forEach(function (s) {
      var nm = s.querySelector(".name"), cv = s.querySelector("canvas.holes");
      if (!nm || !cv) return;
      var cs = getComputedStyle(nm), fs = parseFloat(cs.fontSize), lh = parseFloat(cs.lineHeight), k = 3, pad = 20;
      var W = 390 * k, H = Math.round((lh + pad * 2) * k);
      cv.width = W; cv.height = H;
      cv.style.top = (nm.offsetTop - pad) + "px"; cv.style.height = (lh + pad * 2) + "px";
      var ctx = cv.getContext("2d", { willReadFrequently: true });
      ctx.font = cs.fontStyle + " " + cs.fontWeight + " " + (fs * k) + "px " + cs.fontFamily;
      ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
      var m = ctx.measureText(nm.textContent), asc = m.fontBoundingBoxAscent, desc = m.fontBoundingBoxDescent;
      ctx.fillStyle = "#000";
      ctx.fillText(nm.textContent, W / 2, pad * k + (lh * k - (asc + desc)) / 2 + asc);
      var img = ctx.getImageData(0, 0, W, H), d = img.data, n = W * H, out = new Uint8Array(n), stack = [];
      function push(i) { if (!out[i] && d[i * 4 + 3] < 128) { out[i] = 1; stack.push(i); } }
      for (var x = 0; x < W; x++) { push(x); push((H - 1) * W + x); }
      for (var y = 0; y < H; y++) { push(y * W); push(y * W + W - 1); }
      while (stack.length) {
        var i = stack.pop(), px = i % W, py = (i - px) / W;
        if (px > 0) push(i - 1); if (px < W - 1) push(i + 1); if (py > 0) push(i - W); if (py < H - 1) push(i + W);
      }
      for (var j = 0; j < n; j++) {
        var hole = !out[j] && d[j * 4 + 3] < 128;
        d[j * 4] = 234; d[j * 4 + 1] = 229; d[j * 4 + 2] = 222; d[j * 4 + 3] = hole ? 255 : 0;
      }
      ctx.putImageData(img, 0, 0);
    });
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(run); else window.addEventListener("load", run);
})();
</script>
"""
art = base64.b64encode(open(f"{S}/quiet-screens/signin-art-b.png", "rb").read()).decode()
artc = base64.b64encode(open(f"{S}/quiet-screens/signin-art-c.png", "rb").read()).decode()
moonn = base64.b64encode(open(f"{S}/quiet-screens/locked-moon.png", "rb").read()).decode()
starsn = base64.b64encode(open(f"{S}/quiet-screens/locked-stars.png", "rb").read()).decode()
mcd = base64.b64encode(open(f"{S}/quiet-screens/moon-col-dark.png", "rb").read()).decode()
mcl = base64.b64encode(open(f"{S}/quiet-screens/moon-col-light.png", "rb").read()).decode()
dots = json.load(open(f"{S}/quiet-screens/moon-col-light.png.json"))
flat = bytearray()
for i, j, r, g, b in dots:
    flat += bytes([i, j >> 8, j & 255, r, g, b])
dots64 = base64.b64encode(bytes(flat)).decode()

def keys(row):
    return "".join(f"<i>{k}</i>" for k in row)

keyboard = f'''<div class="kb" aria-hidden="true">
<div class="kr">{keys("qwertyuiop")}</div>
<div class="kr in">{keys("asdfghjkl")}</div>
<div class="kr"><i class="fn w">&#8679;</i>{keys("zxcvbnm")}<i class="fn w">&#9003;</i></div>
<div class="kr"><i class="fn w2">123</i><i class="sp">space</i><i>@</i><i>.</i><i class="fn w2">return</i></div>
</div>'''

page = f'''<title>Quiet Hours Screens</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Instrument+Serif:ital@0;1&family=Outfit:wght@300;400;500;600&display=swap">
<style>
/* Layout: phones at true size in a centred row that wraps, each with a short label above. Screens are added one at a time as they're agreed. */
:root{{ --bg:#D9D6D1; --fg:#1C1A18; --muted:#5F5A53; --line:rgba(28,26,24,.14);
  --sans:'Outfit',system-ui,-apple-system,'Segoe UI',sans-serif; --serif:'Instrument Serif',Georgia,serif; --mono:'DM Mono',ui-monospace,Menlo,monospace }}
@media (prefers-color-scheme: dark){{ :root:not([data-theme="light"]){{ --bg:#1B1A18; --fg:#EFEBE5; --muted:#A9A39B; --line:rgba(239,235,229,.16); color-scheme:dark }} }}
:root[data-theme="dark"]{{ --bg:#1B1A18; --fg:#EFEBE5; --muted:#A9A39B; --line:rgba(239,235,229,.16); color-scheme:dark }}
body{{background:var(--bg);color:var(--fg);font-family:var(--sans)}}
.wrap{{padding-block:32px 64px;padding-left:max(16px, env(safe-area-inset-left, 0px));padding-right:max(16px, env(safe-area-inset-right, 0px));display:flex;flex-wrap:wrap;justify-content:center;gap:40px 48px}}
.item{{display:flex;flex-direction:column;align-items:center;gap:14px;max-width:100%}}
.label{{font-size:14px;letter-spacing:.04em;color:var(--muted);margin:0;text-align:center}}
.phone{{width:390px;max-width:100%;height:844px;border-radius:52px;overflow:hidden;position:relative;box-shadow:0 0 0 1px var(--line),0 30px 60px -20px rgba(0,0,0,.35)}}
.play{{height:44px;padding:0 22px;border-radius:22px;border:1px solid var(--line);background:transparent;color:var(--fg);font:500 15px var(--sans);cursor:pointer}}
.play:focus-visible{{outline:2px solid var(--fg);outline-offset:3px}}

/* The screen. These colours are the product's own, fixed by design. */
.s{{position:absolute;inset:0;background:#EAE5DE;color:#1C1A18;font-family:var(--sans);overflow:hidden}}
.art{{position:absolute;left:0;top:0;width:390px;height:540px;max-width:none;display:block}}
.name{{position:absolute;left:0;right:0;top:340px;margin:0;text-align:center;font-family:var(--serif);font-style:italic;font-weight:400;font-size:74px;line-height:74px;letter-spacing:0;
  text-shadow:0 0 6px #EAE5DE,0 0 6px #EAE5DE,0 0 12px #EAE5DE}}
.sub{{position:absolute;left:0;right:0;top:430px;margin:0;padding:0 48px;text-align:center;font-size:18px;line-height:26px;font-weight:300;color:#6A635B}}
.s form{{position:absolute;left:24px;right:24px;bottom:34px;display:flex;flex-direction:column;gap:12px}}
.rowf{{height:58px;border-radius:29px;background:#DED8D0;display:flex;align-items:center;gap:12px;padding:0 22px;
  box-shadow:inset 0 2px 4px rgba(70,52,36,.13),0 1px 0 rgba(255,255,255,.7)}}
.rowf label{{font-size:15px;color:#6A635B;flex:none}}
.rowf input{{flex:1;min-width:0;border:0;background:transparent;text-align:right;font:400 16px var(--sans);color:#1C1A18;outline:none}}
.rowf input::placeholder{{color:#8A8279}}
.rowf:focus-within,.rowf.on{{box-shadow:inset 0 3px 6px rgba(70,52,36,.18),0 1px 0 rgba(255,255,255,.7)}}
.rowf .typed{{flex:1;text-align:right;font-size:16px}}
.rowf .typed::after{{content:"";display:inline-block;width:2px;height:20px;margin-left:2px;vertical-align:-4px;background:#1C1A18}}
.go{{height:58px;border:0;border-radius:29px;background:#1C1A18;color:#F3EFE9;font:500 17px var(--sans);cursor:pointer;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.16),0 14px 20px -10px rgba(28,26,24,.5)}}
.go:focus-visible{{outline:2px solid #990000;outline-offset:3px}}
.fine{{margin:4px 0 0;text-align:center;font-size:13px;color:#7A7269}}

.s.c .name{{top:356px}}
.s.c .sub{{top:446px}}
/* With the keyboard up: everything rides up by the same amount, the form sits on the keyboard. */
.s.k .art{{top:-214px}}
.s.k .name{{top:126px}}
.s.k .sub{{top:216px}}
.s.c.k .art{{top:-226px}}
.s.c.k .name{{top:130px}}
.s.c.k .sub{{top:220px}}
.s.d .name{{top:402px}}
.s.d .sub{{top:490px}}
.s.d.k .name{{top:176px}}
.s.d.k .sub{{top:264px}}
.s.k form{{bottom:352px}}
.kb{{position:absolute;left:0;right:0;bottom:0;height:336px;background:#D0D3D9;padding:8px 3px 0;display:flex;flex-direction:column;gap:11px;font:400 22px -apple-system,system-ui,sans-serif;color:#000}}
.kr{{display:flex;justify-content:center;gap:6px}}
.kr.in{{padding:0 19px}}
.kr i{{flex:1;height:43px;border-radius:5px;background:#fff;box-shadow:0 1px 0 rgba(0,0,0,.32);display:grid;place-items:center;font-style:normal}}
.kr i.fn{{background:#ABB0BA;font-size:16px}}
.kr i.w{{flex:1.35}}
.kr i.w2{{flex:2.6}}
.kr i.sp{{flex:5;font-size:16px}}

/* The dots test. */
.s canvas{{position:absolute;left:0;top:0;width:390px;height:844px;display:block}}
.s .cap{{position:absolute;left:24px;font-size:15px;color:#6A635B;opacity:0;transition:opacity .5s}}
.s.votes .cap{{opacity:1;transition-delay:.5s}}
.s .cap b{{display:block;font-family:var(--serif);font-style:italic;font-weight:400;font-size:28px;line-height:30px;color:#1C1A18}}
.s .title2{{position:absolute;left:24px;right:24px;top:84px;margin:0;font-family:var(--serif);font-style:italic;font-weight:400;font-size:44px;line-height:46px;opacity:0;transition:opacity .5s}}
.s.votes .title2{{opacity:1;transition-delay:.5s}}
.s .name.fade{{transition:opacity .4s}}
.s.votes .name.fade,.s.votes .sub{{opacity:0}}
.s .sub{{transition:opacity .4s}}

/* How it works: the moon's dots re-form into each step's picture. */
.s.hw canvas{{position:absolute;left:0;top:0;width:390px;height:460px;display:block}}
.s.hw .step{{position:absolute;left:0;right:0;top:404px;margin:0;padding:0 28px;text-align:center;font-family:var(--serif);font-style:italic;font-weight:400;font-size:50px;line-height:54px;transition:opacity .25s}}
.s.hw .sub{{top:470px;padding:0 44px;transition:opacity .25s}}
@keyframes hwin{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
.s.hw.in .step,.s.hw.in .sub{{animation:hwin .5s ease both}}
@media (prefers-reduced-motion: reduce){{.s.hw.in .step,.s.hw.in .sub{{animation:none}}}}
.s.hw .go{{position:absolute;left:24px;right:24px;bottom:34px}}
.s.lk .foot{{position:absolute;left:24px;right:24px;bottom:34px;display:flex;flex-direction:column;gap:12px}}
.s.lk .go{{position:static}}
.chips{{position:absolute;left:24px;right:24px;top:514px;display:flex;flex-wrap:wrap;justify-content:center;gap:10px 8px}}
.chip{{height:40px;padding:0 17px;border-radius:20px;background:#EFEBE5;font-size:15px;display:flex;align-items:center;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 7px 10px -5px rgba(70,52,36,.3),0 1px 2px rgba(70,52,36,.1)}}
.chip.add{{background:#DED8D0;color:#6A635B;border:0;font:400 15px var(--sans);cursor:pointer;box-shadow:inset 0 2px 4px rgba(70,52,36,.13),0 1px 0 rgba(255,255,255,.7)}}
/* Home. A small bar on top, the state's picture, one line, then what you can do. */
.s.hm .bar{{position:absolute;left:24px;right:24px;top:52px;display:flex;align-items:center;justify-content:space-between}}
.s.hm .wm{{font-family:var(--serif);font-style:italic;font-size:25px;line-height:1}}
.s.hm .gear{{width:42px;height:42px;border-radius:50%;border:0;background:#EFEBE5;color:#1C1A18;display:grid;place-items:center;cursor:pointer;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 8px 12px -6px rgba(70,52,36,.32),0 1px 2px rgba(70,52,36,.1)}}
.s.hm canvas{{position:absolute;left:0;top:92px;width:390px;height:190px;display:block}}
.s.hm .step{{position:absolute;left:0;right:0;top:284px;margin:0;text-align:center;font-family:var(--serif);font-style:italic;font-weight:400;font-size:46px;line-height:50px}}
.s.hm .sub{{top:338px;font-size:16px;line-height:22px}}
.opts{{position:absolute;left:24px;right:24px;top:380px;display:flex;flex-direction:column;gap:12px}}
.opt{{display:block;width:100%;text-align:left;border:0;border-radius:26px;padding:14px 18px;background:#EFEBE5;color:#1C1A18;font-family:var(--sans);cursor:pointer;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 12px 16px -9px rgba(70,52,36,.32),0 1px 2px rgba(70,52,36,.1);transition:box-shadow .2s,background .2s}}
.opt.on{{background:#E0DAD2;box-shadow:inset 0 3px 6px rgba(70,52,36,.2),0 1px 0 rgba(255,255,255,.7)}}
.opt:focus-visible{{outline:2px solid #1C1A18;outline-offset:3px}}
.opt .r1{{display:flex;align-items:baseline;justify-content:space-between;gap:12px}}
.opt .d{{font-size:19px;font-weight:500}}
.opt .t{{font-size:16px}}
.opt .why{{display:block;margin-top:2px;font-size:14px;line-height:20px;color:#6A635B}}
.opt .r3{{display:flex;align-items:center;gap:12px;margin-top:9px}}
.track{{flex:1;height:5px;border-radius:3px;background:#D8D2C9;box-shadow:inset 0 1px 2px rgba(70,52,36,.22)}}
.opt.on .track{{background:#D2CCC3}}
.track b{{display:block;height:5px;border-radius:3px;background:#1C1A18;transition:width .3s}}
.opt .n{{font-size:12px;color:#6A635B;min-width:70px;text-align:right}}
.s.hm .fine{{position:absolute;left:0;right:0;bottom:68px}}
.optout{{position:absolute;left:50%;transform:translateX(-50%);bottom:20px;height:44px;padding:0 14px;border:0;background:transparent;color:#6A635B;font:400 14px var(--sans);text-decoration:underline;text-underline-offset:3px;cursor:pointer;white-space:nowrap}}
.optout:focus-visible{{outline:2px solid #1C1A18;outline-offset:2px}}
/* Opted out: the screen stays where it was but fades right back, and one dark button is the only thing to press. */
.s.out canvas{{opacity:.16}}
.s.out .step,.s.out .time,.s.out .until,.s.out .well .num,.s.out .well p{{color:#ADA69C}}
.s.out .sub,.s.out .lab{{color:#1C1A18;font-weight:500}}
.s.out .opt{{background:transparent;box-shadow:none;border:0;cursor:default;color:#ADA69C}}
.s.out .opt .why,.s.out .opt .n{{color:#ADA69C}}
.s.out .opt .d{{font-weight:400}}
.s.out .opt .track{{box-shadow:none;background:rgba(28,26,24,.05)}}
.s.out .opt .track b{{background:#CFC8BE}}
.s.out .well{{background:transparent;box-shadow:none}}
.s.out .fine{{bottom:104px}}
.s.out .go{{position:absolute;left:24px;right:24px;bottom:34px}}
/* Home on the day: the same screen, drawn tighter, with the board appearing underneath. */
.s.day .lab{{top:124px}}
.s.day .step{{top:146px}}
.s.day .time{{top:232px}}
.s.day .until{{top:272px}}
.s.day .well{{top:318px;padding:18px 20px 20px}}
.s.day .well .num{{font-size:66px;line-height:66px}}
.s.day .well p + p{{margin-top:4px;font-size:16px;line-height:22px}}
.board{{position:absolute;left:24px;right:24px;top:468px;display:block;text-align:left;border:0;border-radius:28px;padding:16px 20px 18px;background:#EFEBE5;color:#1C1A18;font-family:var(--sans);cursor:pointer;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 12px 16px -9px rgba(70,52,36,.32),0 1px 2px rgba(70,52,36,.1)}}
.board:focus-visible{{outline:2px solid #1C1A18;outline-offset:3px}}
.board .hd{{display:flex;align-items:center;justify-content:space-between;font-size:17px;font-weight:500}}
.board .ct{{font-size:13px;font-weight:400;color:#6A635B}}
.board .ln{{display:block;margin-top:8px;font-size:15px;line-height:21px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.board .ln + .ln{{margin-top:4px}}
.board .ln i{{font-style:normal;color:#6A635B}}
.addrow{{position:absolute;left:24px;right:24px;top:590px;height:56px;border:0;border-radius:28px;background:#DED8D0;color:#6A635B;font:400 15px var(--sans);display:flex;align-items:center;justify-content:space-between;padding:0 9px 0 22px;cursor:pointer;
  box-shadow:inset 0 2px 4px rgba(70,52,36,.13),0 1px 0 rgba(255,255,255,.7)}}
.addrow:focus-visible{{outline:2px solid #1C1A18;outline-offset:3px}}
.addrow b{{width:38px;height:38px;border-radius:50%;background:#1C1A18;color:#F3EFE9;display:grid;place-items:center;box-shadow:0 6px 10px -5px rgba(28,26,24,.5)}}
/* The board as a stack of cards that opens to take over the screen. Two versions: the list in a depression (tr), or fading at the edges (fd). */
.stk{{position:absolute;left:0;right:0;top:494px;margin:0;text-align:center;font-size:15px;color:#6A635B}}
.cw{{position:absolute;inset:0;z-index:20;pointer-events:none}}
.pc{{position:absolute;left:24px;right:24px;height:76px;box-sizing:border-box;border-radius:26px;padding:15px 20px;background:#EFEBE5;z-index:calc(20 - var(--i));pointer-events:auto;
  top:calc(524px + var(--i) * 10px);transform:scale(calc(1 - var(--i) * .05));transform-origin:50% 0;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 12px 16px -9px rgba(70,52,36,.34),0 1px 2px rgba(70,52,36,.1);
  transition:top .55s cubic-bezier(.2,.8,.2,1),left .55s cubic-bezier(.2,.8,.2,1),right .55s cubic-bezier(.2,.8,.2,1),transform .55s cubic-bezier(.2,.8,.2,1),opacity .3s}}
.pc.h{{opacity:0}}
.pc b{{display:block;font-size:16px;font-weight:500;line-height:22px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.pc span{{display:block;font-size:14px;line-height:20px;color:#6A635B;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.td{{position:absolute;right:20px;top:37px;height:20px;padding:0;border:0;background:none;color:#1C1A18;font-family:inherit;font-size:14px;line-height:20px;text-decoration:underline;text-underline-offset:3px;text-decoration-color:rgba(28,26,24,.35);cursor:pointer;opacity:0;pointer-events:none;transition:opacity .3s}}
.td::after{{content:"";position:absolute;inset:-12px -14px}}
.td:focus-visible{{outline:2px solid #1C1A18;outline-offset:2px}}
.stkbtn{{position:absolute;left:24px;right:24px;top:518px;height:112px;border:0;background:transparent;border-radius:26px;cursor:pointer;z-index:30}}
.stkbtn:focus-visible{{outline:2px solid #1C1A18;outline-offset:3px}}
.home{{transition:opacity .3s}}
.bd{{opacity:0;pointer-events:none;transition:opacity .35s}}
.bd .bt{{position:absolute;left:24px;top:60px;margin:0;font-family:var(--serif);font-style:italic;font-size:44px;line-height:48px}}
.bd .bc{{position:absolute;left:24px;right:80px;top:112px;margin:0;font-size:15px;color:#6A635B}}
.bd .x{{position:absolute;right:24px;top:58px;width:44px;height:44px;border-radius:50%;border:0;background:#EFEBE5;color:#1C1A18;display:grid;place-items:center;cursor:pointer;z-index:40;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 8px 12px -6px rgba(70,52,36,.32),0 1px 2px rgba(70,52,36,.1)}}
.bd .cmp{{position:absolute;left:24px;right:24px;bottom:34px;height:58px;border-radius:29px;background:#DED8D0;color:#6A635B;font-size:15px;display:flex;align-items:center;justify-content:space-between;padding:0 10px 0 22px;z-index:40;
  box-shadow:inset 0 2px 4px rgba(70,52,36,.13),0 1px 0 rgba(255,255,255,.7)}}
.bd .cmp b{{width:38px;height:38px;border-radius:50%;background:#1C1A18;color:#F3EFE9;display:grid;place-items:center}}
.s.open .home{{opacity:0;pointer-events:none}}
.s.open .bd{{opacity:1;pointer-events:auto}}
.s.open{{touch-action:none}}
.s.open .pc{{top:var(--y, 156px);transform:none;opacity:1}}
.s.open .pc.me span{{padding-right:84px}}
.s.open .td{{opacity:1;pointer-events:auto}}
.s.open .pc.gone{{opacity:0;transform:scale(.92);pointer-events:none;transition:opacity .25s,transform .25s}}
.s.live .pc{{transition:none}}
.s.open .stkbtn{{display:none}}
/* tr: a depression holds the list; cards pass under its rim. */
.tray,.rim{{position:absolute;left:14px;right:14px;top:150px;bottom:104px;border-radius:36px}}
.tray{{display:none;background:#DED8D0}}
.rim{{display:none;z-index:25;pointer-events:none;opacity:0;transition:opacity .35s;box-shadow:inset 0 3px 7px rgba(70,52,36,.2),inset 0 0 0 1px rgba(70,52,36,.03),0 1px 0 rgba(255,255,255,.75)}}
.tr .tray,.tr .rim{{display:block}}
.tr.open .rim{{opacity:1}}
.tr .cw{{clip-path:inset(0 0 0 0 round 0);transition:clip-path .55s cubic-bezier(.2,.8,.2,1)}}
.tr.open .cw{{clip-path:inset(150px 14px 104px 14px round 36px)}}
.tr.open .pc{{left:26px;right:26px}}
/* fd: the list dissolves into the surface above and below. */
.fd .cw{{-webkit-mask-image:linear-gradient(to bottom,transparent 132px,#000 166px,#000 708px,transparent 742px);mask-image:linear-gradient(to bottom,transparent 132px,#000 166px,#000 708px,transparent 742px)}}
@media (prefers-reduced-motion: reduce){{.pc,.home,.bd,.td,.rim,.tr .cw{{transition:none}}}}
/* Home, locked: the surface goes dark and the moon comes out, one light dot for each person who is in. */
.s.nt{{background:#1B1917;color:#EAE5DE}}
.lmoon{{position:absolute;left:0;top:100px;width:390px;height:240px;display:block}}
.nl{{position:absolute;left:0;right:0;top:350px;margin:0;text-align:center;font-size:15px;color:#9B9289}}
.nu{{position:absolute;left:0;right:0;top:370px;margin:0;text-align:center;font-family:var(--serif);font-style:italic;font-weight:400;font-size:60px;line-height:64px}}
.nc{{position:absolute;left:0;right:0;top:442px;margin:0;text-align:center;font-size:15px;color:#9B9289}}
.nt .stk,.nt .fine,.nt .optout,.nt .pc span,.nt .bd .bc{{color:#9B9289}}
.s.hm.nt .gear,.nt .bd .x{{background:#27231F;color:#EAE5DE;box-shadow:inset 0 1px 0 rgba(255,255,255,.09),0 8px 12px -6px rgba(0,0,0,.75),0 1px 2px rgba(0,0,0,.4)}}
.nt .pc{{background:#27231F;box-shadow:inset 0 1px 0 rgba(255,255,255,.09),0 12px 16px -9px rgba(0,0,0,.8),0 1px 2px rgba(0,0,0,.4)}}
.nt .td{{color:#EAE5DE;text-decoration-color:rgba(234,229,222,.4)}}
.nt .bd .cmp{{background:#131110;color:#8B837A;box-shadow:inset 0 2px 4px rgba(0,0,0,.65),0 1px 0 rgba(255,255,255,.06)}}
.nt .bd .cmp b{{background:#EAE5DE;color:#1C1A18}}
.nt .stkbtn:focus-visible,.nt .optout:focus-visible,.nt .td:focus-visible{{outline-color:#EAE5DE}}
/* Locked, near-black, and the same with stars across the whole screen. */
.s.nt.nb{{background:#080706}}
.s.hm.nt.nb .gear,.nt.nb .bd .x,.nt.nb .pc{{background:#161412;box-shadow:inset 0 1px 0 rgba(255,255,255,.1),0 12px 16px -9px #000,0 0 0 1px rgba(255,255,255,.025)}}
.nt.nb .bd .cmp{{background:#020202;box-shadow:inset 0 2px 4px rgba(0,0,0,.9),0 1px 0 rgba(255,255,255,.08)}}
.stars{{position:absolute;left:0;top:0;width:390px;height:844px;display:block;pointer-events:none}}
/* The question, the moment the window ends: one picture, one line to write, one button. */
.s.q .lab{{position:absolute;left:0;right:0;top:382px;margin:0;text-align:center;font-size:15px;color:#6A635B}}
.s.q .step{{top:406px}}
.s.q .sub{{top:468px}}
.qf{{position:absolute;left:24px;right:24px;top:514px;height:128px;box-sizing:border-box;border-radius:28px;padding:16px 20px;background:#DED8D0;font-size:17px;line-height:24px;color:#8A8279;
  box-shadow:inset 0 2px 4px rgba(70,52,36,.13),0 1px 0 rgba(255,255,255,.7)}}
.qf.on{{color:#1C1A18;box-shadow:inset 0 3px 6px rgba(70,52,36,.18),0 1px 0 rgba(255,255,255,.7)}}
.qf.on::after{{content:"";display:inline-block;width:2px;height:22px;margin-left:2px;vertical-align:-4px;background:#1C1A18}}
.qn{{position:absolute;right:30px;top:332px;margin:0;font-size:13px;color:#7A7269}}
.s.q .foot{{position:absolute;left:24px;right:24px;bottom:18px;display:flex;flex-direction:column;gap:2px}}
.s.q .go{{position:static}}
.skip{{height:44px;border:0;background:transparent;color:#6A635B;font:400 14px var(--sans);text-decoration:underline;text-underline-offset:3px;cursor:pointer}}
.skip:focus-visible{{outline:2px solid #1C1A18;outline-offset:2px}}
.s.q.k .lab{{top:66px}}
.s.q.k .step{{top:90px}}
.s.q.k .sub{{top:152px}}
.s.q.k .qf{{top:196px;height:auto;min-height:104px}}
.s.q.k .foot{{bottom:352px}}
/* Home, summary: one view. The number, then a handful of highlights set as plain lines. */
.s.sel.sm .lab{{top:128px}}
.s.sel.sm .step{{top:150px;font-size:62px;line-height:66px}}
.s.sm .well{{top:232px;padding:16px 10px 15px;display:grid;grid-template-columns:repeat(3,1fr)}}
.well.three b{{display:block;font-family:var(--serif);font-style:italic;font-weight:400;font-size:34px;line-height:36px}}
.well.three span{{display:block;margin-top:2px;font-size:13px;line-height:18px;color:#6A635B}}
.s.sm .stk{{top:346px}}
.hl{{position:absolute;left:0;right:0;top:360px;padding:0 34px;text-align:center}}
.hl p{{margin:0 0 22px;font-family:var(--serif);font-style:italic;font-size:25px;line-height:30px}}
.s.hm.sm .fine{{bottom:40px}}
/* Opted out, on the day and during the window: everything stays but goes quiet; one button is the only thing to press. */
.s.out .stk,.s.out .pc,.s.out .pc span{{color:#ADA69C}}
.s.out .pc,.nt.off .pc{{background:transparent;box-shadow:none;text-align:center;pointer-events:none}}
.nt.off .lmoon{{opacity:.2}}
.nt.off .stars{{opacity:.6}}
.nt.off .nl{{color:#EAE5DE;font-weight:500}}
.nt.off .nu,.nt.off .nc,.nt.off .stk,.nt.off .pc,.nt.off .pc span,.nt.off .fine{{color:#5F5850}}
.s.hm.nt.off .fine{{bottom:104px}}
.nt.off .go{{position:absolute;left:24px;right:24px;bottom:34px;background:#EAE5DE;color:#1C1A18;box-shadow:inset 0 1px 0 rgba(255,255,255,.6),0 14px 20px -10px #000}}
.s.sel.sm .lab.me{{color:#1C1A18;font-weight:500}}
/* Home, structured: left-aligned on one edge; one headline; facts as tiles (a value and a small label); one footer row. */
.st7 .hd{{position:absolute;left:24px;top:122px;margin:0;font-family:var(--serif);font-style:italic;font-weight:400;font-size:76px;line-height:78px}}
.st7 .when{{position:absolute;left:26px;top:206px;margin:0;font-size:25px;line-height:30px}}
.tiles{{position:absolute;left:24px;right:24px;top:274px;display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.tile{{border-radius:24px;padding:14px 18px 15px;background:#DED8D0;box-shadow:inset 0 3px 7px rgba(70,52,36,.16),0 1px 0 rgba(255,255,255,.7)}}
.tile b{{display:block;font-family:var(--serif);font-style:italic;font-weight:400;font-size:36px;line-height:38px}}
.tile span{{display:block;margin-top:2px;font-size:13px;line-height:18px;color:#6A635B}}
.sec{{position:absolute;left:26px;right:26px;top:466px;margin:0;display:flex;justify-content:space-between;align-items:baseline;font-size:17px;font-weight:500}}
.sec i{{font-style:normal;font-weight:400;font-size:15px;color:#6A635B}}
.st7 .pc{{top:calc(502px + var(--i) * 10px)}}
.st7 .stkbtn{{top:496px}}
.foot7{{position:absolute;left:26px;right:26px;bottom:26px;display:flex;justify-content:space-between;align-items:center;font-size:14px;color:#6A635B}}
.foot7 button{{border:0;background:none;padding:10px 0;color:#6A635B;font:400 14px var(--sans);text-decoration:underline;text-underline-offset:3px;cursor:pointer}}
.foot7 button:focus-visible{{outline:2px solid #1C1A18;outline-offset:2px}}
/* Home as one surface: nothing boxed. A headline, then facts as rows on the page itself, parted by etched lines,
   label on the left edge and value on the right. The stack is the only raised thing, hanging from its own row. */
.st8 .hd{{position:absolute;left:24px;top:124px;margin:0;font-family:var(--serif);font-style:italic;font-weight:400;font-size:76px;line-height:78px}}
.st8 .when{{position:absolute;left:26px;top:208px;margin:0;font-size:25px;line-height:30px}}
.rows{{position:absolute;left:26px;right:26px;top:284px}}
.row{{height:60px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(70,52,36,.15);box-shadow:0 1px 0 rgba(255,255,255,.75)}}
.row:first-child{{border-top:1px solid rgba(70,52,36,.15)}}
.row.last{{border-bottom:0;box-shadow:none}}
.row > span{{font-size:17px;color:#6A635B}}
.row > b{{font-family:var(--serif);font-style:italic;font-weight:400;font-size:30px;line-height:32px}}
.st8 .pc{{top:calc(468px + var(--i) * 10px)}}
.st8 .stkbtn{{top:462px}}
.out8{{position:absolute;left:26px;bottom:22px;height:44px;border:0;background:none;padding:0;color:#6A635B;font:400 14px var(--sans);text-decoration:underline;text-underline-offset:3px;cursor:pointer}}
.out8:focus-visible{{outline:2px solid #1C1A18;outline-offset:2px}}
/* Home as a hero and a sheet. Top: one raised card that is the window itself (what, when, two figures). Bottom: one
   sheet that runs to the edges and the bottom, holding the list as rows, with the thing you do pinned at its foot.
   Nothing floats loose: every element lives in one of the two. */
.hero{{position:absolute;left:20px;right:20px;top:110px;border-radius:34px;padding:20px 22px 0;background:#EFEBE5;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 16px 22px -12px rgba(70,52,36,.34),0 1px 2px rgba(70,52,36,.1)}}
.h9top{{display:flex;justify-content:space-between;align-items:center;font-size:14px;color:#6A635B}}
.h9top button,.s9head button{{border:0;background:none;padding:6px 0;color:#6A635B;font:400 14px var(--sans);text-decoration:underline;text-underline-offset:3px;cursor:pointer}}
.h9big{{margin:6px 0 0;font-family:var(--serif);font-style:italic;font-size:64px;line-height:66px}}
.h9when{{margin:2px 0 0;font-size:23px;line-height:28px}}
.h9stats{{margin:18px -22px 0;display:grid;grid-template-columns:1fr 1fr;border-top:1px solid rgba(70,52,36,.12)}}
.h9stats > div{{padding:14px 22px 16px}}
.h9stats > div + div{{border-left:1px solid rgba(70,52,36,.12)}}
.h9stats b{{display:block;font-family:var(--serif);font-style:italic;font-weight:400;font-size:32px;line-height:34px}}
.h9stats span{{display:block;margin-top:1px;font-size:13px;line-height:18px;color:#6A635B}}
.sheet9{{position:absolute;left:0;right:0;top:392px;bottom:0;border-radius:38px 38px 0 0;background:#F1EEE8;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 -14px 26px -16px rgba(70,52,36,.3)}}
.s9head{{display:flex;justify-content:space-between;align-items:center;padding:18px 26px 6px;font-size:15px;color:#6A635B}}
.r9{{display:flex;align-items:center;justify-content:space-between;gap:14px;margin:0 26px;height:66px;border-bottom:1px solid rgba(70,52,36,.1)}}
.r9 b{{display:block;font-size:16px;font-weight:500;line-height:22px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.r9 span{{display:block;font-size:14px;line-height:20px;color:#6A635B}}
.r9 i{{font-style:normal;font-size:13px;color:#8A8279;flex:none}}
.r9 > div{{min-width:0}}
.cmp9{{position:absolute;left:20px;right:20px;bottom:30px;height:58px;border-radius:29px;background:#E2DCD4;color:#6A635B;font-size:15px;display:flex;align-items:center;justify-content:space-between;padding:0 10px 0 22px;
  box-shadow:inset 0 2px 4px rgba(70,52,36,.14),0 1px 0 rgba(255,255,255,.8)}}
.cmp9 b{{width:38px;height:38px;border-radius:50%;background:#1C1A18;color:#F3EFE9;display:grid;place-items:center}}

/* ---- Homes, V9: a hero and a sheet. Every element lives in one of the two; nothing floats loose. ---- */
.h9big.sm{{font-size:50px}}
.h9stats.three{{grid-template-columns:1fr 1fr 1fr}}
.h9stats.three > div{{padding:14px 12px 16px 18px}}
.h9stats.three b{{font-size:27px;line-height:34px}}
.h9top.me span,.out9 .h9top span,.off9 .l9cap span{{color:#1C1A18;font-weight:500}}
.s9note{{font-size:14px;color:#8A8279}}
.s9foot{{position:absolute;left:26px;right:26px;bottom:34px;margin:0;font-size:13px;line-height:18px;color:#7A7269}}
.s9wait{{margin:10px 26px 0;font-size:16px;line-height:23px;color:#6A635B}}
.go9{{position:absolute;left:20px;right:20px;bottom:30px}}
.td9{{flex:none;border:0;background:none;padding:8px 0;color:#1C1A18;font:400 14px var(--sans);text-decoration:underline;text-underline-offset:3px;text-decoration-color:rgba(28,26,24,.35);cursor:pointer}}
/* Only the board is an edge-to-edge sheet, because only it pulls up to fill the screen. Everything else that sits
   under the hero is a second card with the same margins, hugging its content. */
.sheet9.card9{{left:20px;right:20px;top:382px;bottom:auto;border-radius:34px;padding-bottom:12px;background:#EFEBE5;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 16px 22px -12px rgba(70,52,36,.34),0 1px 2px rgba(70,52,36,.1)}}
.card9 .s9head{{padding:16px 22px 6px}}
.card9 .o9{{width:calc(100% - 20px);margin-left:10px;margin-right:10px}}
.card9 .hl9{{margin:0 22px}}
.card9 .s9wait{{margin:8px 22px 10px}}
.out9 .sheet9.card9{{border-top:0}}
/* options, as rows on the sheet; the chosen one is pressed in */
.o9s{{margin-top:2px}}
.o9{{display:block;box-sizing:border-box;width:calc(100% - 28px);margin:0 14px;padding:11px 12px 13px;border:0;border-radius:22px;background:transparent;text-align:left;font-family:var(--sans);color:#1C1A18;transition:background .2s,box-shadow .2s}}
button.o9{{cursor:pointer}}
.o9 + .o9{{margin-top:4px}}
.o9.on{{background:#E4DED6;box-shadow:inset 0 2px 5px rgba(70,52,36,.17),0 1px 0 rgba(255,255,255,.85)}}
.o9 .r1{{display:flex;justify-content:space-between;align-items:baseline;gap:12px}}
.o9 .d{{font-size:17px;font-weight:500}}
.o9 .t{{font-size:15px}}
.o9 .why{{display:block;margin-top:1px;font-size:14px;line-height:20px;color:#6A635B}}
.o9 .r3{{display:flex;align-items:center;gap:12px;margin-top:8px}}
.o9 .n{{font-size:12px;color:#6A635B;min-width:70px;text-align:right}}
.o9:focus-visible{{outline:2px solid #1C1A18;outline-offset:1px}}
/* the board on the sheet: four rows at rest; the sheet pulls up to show them all */
.sheet9{{transition:top .5s cubic-bezier(.2,.8,.2,1)}}
.s9list{{height:264px;overflow:hidden}}
.board9.open{{top:104px}}
.board9.open .s9list{{position:absolute;left:0;right:0;top:50px;bottom:104px;height:auto;overflow-y:auto;scrollbar-width:none;
  -webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 26px,#000 calc(100% - 30px),transparent 100%);mask-image:linear-gradient(to bottom,transparent 0,#000 26px,#000 calc(100% - 30px),transparent 100%)}}
.board9.open .s9list::-webkit-scrollbar{{display:none}}
.board9.open .s9list .r9:first-child{{margin-top:14px}}
.board9.open .s9list .r9:last-child{{margin-bottom:22px}}
/* the summary's highlights, as rows */
.hl9s{{margin-top:2px}}
.hl9{{margin:0 26px;padding:12px 0 13px;border-bottom:1px solid rgba(70,52,36,.1);font-family:var(--serif);font-style:italic;font-size:22px;line-height:27px}}
.hl9:last-child{{border-bottom:0}}
/* opted out: both parts stay but go flat and pale; one dark button is the only thing to press */
.out9 .hero,.out9 .sheet9{{background:transparent;box-shadow:none}}
.out9 .sheet9{{border-top:1px solid rgba(70,52,36,.08)}}
.out9 .h9big,.out9 .h9when,.out9 .h9stats b,.out9 .h9stats span,.out9 .s9head,.out9 .s9note,.out9 .r9 b,.out9 .r9 span,.out9 .r9 i,.out9 .o9,.out9 .o9 .why,.out9 .o9 .n{{color:#ADA69C}}
.out9 .h9stats,.out9 .h9stats > div + div,.out9 .r9{{border-color:rgba(70,52,36,.07)}}
.out9 .o9.on{{background:transparent;box-shadow:none}}
.out9 .o9 .track{{box-shadow:none;background:rgba(28,26,24,.05)}}
.out9 .o9 .track b{{background:#CFC8BE}}
.out9 .o9 .d{{font-weight:400}}
.out9 .r9 b{{font-weight:400}}
.out9 .s9list{{height:198px}}
/* locked: the night sky is the hero, the moon its object; the sheet is dark */
.s.nt9{{background:#080706;color:#EAE5DE}}
.nt9 .lmoon{{top:92px}}
.l9cap{{position:absolute;left:26px;right:26px;top:344px;display:flex;justify-content:space-between;align-items:center;font-size:14px;color:#9B9289}}
.l9cap button{{border:0;background:none;padding:6px 0;color:#9B9289;font:400 14px var(--sans);text-decoration:underline;text-underline-offset:3px;cursor:pointer}}
.l9big{{position:absolute;left:24px;top:366px;margin:0;font-family:var(--serif);font-style:italic;font-size:58px;line-height:60px}}
.l9cnt{{position:absolute;left:26px;top:430px;margin:0;font-size:15px;color:#9B9289}}
.nt9 .sheet9{{top:478px;background:#151311;box-shadow:inset 0 1px 0 rgba(255,255,255,.1),0 -14px 26px -16px #000}}
.nt9 .s9list{{height:198px}}
.nt9 .board9.open{{top:104px}}
.nt9 .s9head,.nt9 .s9head button,.nt9 .s9note,.nt9 .r9 span,.nt9 .r9 i{{color:#9B9289}}
.nt9 .r9{{border-bottom-color:rgba(255,255,255,.07)}}
.nt9 .td9{{color:#EAE5DE;text-decoration-color:rgba(234,229,222,.4)}}
.nt9 .cmp9{{background:#070605;color:#8B837A;box-shadow:inset 0 2px 4px rgba(0,0,0,.85),0 1px 0 rgba(255,255,255,.07)}}
.nt9 .cmp9 b{{background:#EAE5DE;color:#1C1A18}}
.off9 .lmoon{{opacity:.2}}
.off9 .stars{{opacity:.6}}
.off9 .l9cap span{{color:#EAE5DE}}
.off9 .l9big,.off9 .l9cnt,.off9 .s9head,.off9 .s9note,.off9 .r9 b,.off9 .r9 span,.off9 .r9 i{{color:#5F5850}}
.off9 .sheet9{{background:transparent;box-shadow:none;border-top:1px solid rgba(255,255,255,.06)}}
.off9 .r9{{border-bottom-color:rgba(255,255,255,.04)}}
.off9 .r9 b{{font-weight:400}}
.off9 .s9list{{height:132px}}
.off9 .go9{{background:#EAE5DE;color:#1C1A18;box-shadow:inset 0 1px 0 rgba(255,255,255,.6),0 14px 20px -10px #000}}
@media (prefers-reduced-motion: reduce){{.sheet9,.o9{{transition:none}}}}
/* Alternative: the second group sits straight on the base surface, with no card. */
.sheet9.card9.flat9{{left:0;right:0;background:transparent;box-shadow:none;border-radius:0}}
.flat9 .s9head{{padding:16px 26px 6px}}
.flat9 .o9{{width:calc(100% - 28px);margin-left:14px;margin-right:14px}}
.flat9 .hl9{{margin:0 26px}}
/* Home, selected: the time itself is the subject. */
.s.sel .lab{{position:absolute;left:0;right:0;top:134px;margin:0;text-align:center;font-size:16px;color:#6A635B}}
.s.sel .step{{top:158px;font-size:80px;line-height:82px}}
.s.sel .time{{position:absolute;left:0;right:0;top:246px;margin:0;text-align:center;font-size:27px;line-height:32px}}
.s.sel .until{{position:absolute;left:0;right:0;top:288px;margin:0;text-align:center;font-size:16px;color:#6A635B}}
.well{{position:absolute;left:24px;right:24px;top:356px;border-radius:32px;padding:26px 24px 28px;background:#DED8D0;text-align:center;
  box-shadow:inset 0 3px 7px rgba(70,52,36,.16),0 1px 0 rgba(255,255,255,.7)}}
.well .num{{margin:0;font-family:var(--serif);font-style:italic;font-size:84px;line-height:84px}}
.well p + p{{margin:6px 0 0;font-size:17px;line-height:24px;color:#6A635B}}
.pips{{position:absolute;left:0;right:0;bottom:116px;display:flex;justify-content:center;gap:8px}}
.pips i{{width:8px;height:8px;border-radius:50%;background:#DED8D0;box-shadow:inset 0 1px 2px rgba(70,52,36,.2);transition:background .3s}}
.pips i.on{{background:#1C1A18;box-shadow:none}}
</style>

<div class="wrap">
<div class="item">
<p class="label">1 · Sign-in · dots carry colour</p>
<div class="phone"><div class="s c d">
<img class="art" src="data:image/png;base64,{mcl}" alt="">
<h1 class="name">Quiet Hours</h1>
<p class="sub">One window a week when USC puts its phones down, together.</p>
<form onsubmit="return false">
<div class="rowf"><label for="email-a">USC email</label><input id="email-a" type="email" placeholder="you@usc.edu" autocomplete="email"></div>
<button class="go" type="submit">Continue</button>
<p class="fine">We'll send a code to your inbox.</p>
</form>
</div></div>
</div>




<div class="item">
<p class="label">2 · How it works · V2 · press the button</p>
<div class="phone"><div class="s hw" id="hw">
<canvas id="hwc" width="1170" height="1380" aria-hidden="true"></canvas>
<p class="step" id="hwh" aria-live="polite">Quiet Hours</p>
<p class="sub" id="hws"></p>
<div class="pips" aria-hidden="true"><i></i><i></i><i></i></div>
<button class="go" id="hwb" type="button">Next</button>
</div></div>
</div>

<div class="item">
<p class="label">3 · The lock · V3 · you pick what stays open</p>
<div class="phone"><div class="s hw lk">
<canvas id="lkc" width="1170" height="1380" aria-hidden="true"></canvas>
<p class="step">Everything locks.</p>
<p class="sub">Except the apps you keep open.</p>
<div class="foot">
<button class="go" type="button">Allow the lock</button>
<p class="fine">Apple will ask you to confirm, then show your apps.</p>
</div>
</div></div>
</div>





<div class="sheet9">
<div class="s9head"><span>Going on today</span><button type="button">See all 14</button></div>
<div class="r9"><div><b>Guitar on the lawn, come sit</b><span>Yours · McCarthy Quad</span></div><i>2m</i></div>
<div class="r9"><div><b>Spikeball, anyone welcome</b><span>Alumni Park</span></div><i>9m</i></div>
<div class="r9"><div><b>Jam session, bring anything</b><span>Village fountain</span></div><i>14m</i></div>
<div class="r9"><div><b>Cooking for whoever shows up</b><span>Cale kitchen</span></div><i>21m</i></div>
<div class="cmp9"><span>What you're doing, and where</span><b aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M6 11l6-6 6 6"/></svg></b></div>
</div>
</div></div>
</div>
<div class="item">
<p class="label">4 · Home · voting · V4 · tap an option</p>
<div class="phone"><div class="s hm v9 vote9">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<div class="hero">
<div class="h9top"><span>This week's quiet hours</span><button type="button">Opt out</button></div>
<p class="h9big sm">When this week?</p>
<p class="h9when">Closes Tuesday, 8:00 PM</p>
<div class="h9stats"><div><b>1d 20h</b><span>until voting closes</span></div><div><b>3,112</b><span>Trojans in</span></div></div>
</div>
<div class="sheet9 card9 flat9">
<div class="s9head"><span>Pick a window</span><span class="s9note">2,583 votes</span></div>
<div class="o9s"><button class="o9 on" type="button"><span class="r1"><span class="d">Thursday</span><span class="t">5:00 – 7:00 PM</span></span><span class="why">Most classes are out. Sunset is at 4:48.</span><span class="r3"><span class="track"><b style="width:47%"></b></span><span class="n">1,204 votes</span></span></button>
<button class="o9" type="button"><span class="r1"><span class="d">Sunday</span><span class="t">4:00 – 5:30 PM</span></span><span class="why">No home game, and the week hasn't begun.</span><span class="r3"><span class="track"><b style="width:34%"></b></span><span class="n">867 votes</span></span></button>
<button class="o9" type="button"><span class="r1"><span class="d">Wednesday</span><span class="t">12:00 – 1:00 PM</span></span><span class="why">Lunch, when most people are on campus.</span><span class="r3"><span class="track"><b style="width:20%"></b></span><span class="n">512 votes</span></span></button></div>
</div>
<p class="s9foot">You can change your vote until it closes.</p>
</div></div>
</div>
<div class="item">
<p class="label">4b · Home · voting · opted out</p>
<div class="phone"><div class="s hm v9 vote9 out9">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<div class="hero">
<div class="h9top"><span>You're out this week.</span></div>
<p class="h9big sm">When this week?</p>
<p class="h9when">Closes Tuesday, 8:00 PM</p>
<div class="h9stats"><div><b>1d 20h</b><span>until voting closes</span></div><div><b>3,111</b><span>Trojans in</span></div></div>
</div>
<div class="sheet9 card9 flat9">
<div class="s9head"><span>The vote so far</span><span class="s9note">2,583 votes</span></div>
<div class="o9s"><div class="o9"><span class="r1"><span class="d">Thursday</span><span class="t">5:00 – 7:00 PM</span></span><span class="why">Most classes are out. Sunset is at 4:48.</span><span class="r3"><span class="track"><b style="width:47%"></b></span><span class="n">1,204 votes</span></span></div>
<div class="o9"><span class="r1"><span class="d">Sunday</span><span class="t">4:00 – 5:30 PM</span></span><span class="why">No home game, and the week hasn't begun.</span><span class="r3"><span class="track"><b style="width:34%"></b></span><span class="n">867 votes</span></span></div>
<div class="o9"><span class="r1"><span class="d">Wednesday</span><span class="t">12:00 – 1:00 PM</span></span><span class="why">Lunch, when most people are on campus.</span><span class="r3"><span class="track"><b style="width:20%"></b></span><span class="n">512 votes</span></span></div></div>
</div>
<button class="go go9" type="button">Opt back in</button>
</div></div>
</div>
<div class="item">
<p class="label">5 · Home · decided · V3</p>
<div class="phone"><div class="s hm v9 dec9">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<div class="hero">
<div class="h9top"><span>This week's quiet hours</span><button type="button">Opt out</button></div>
<p class="h9big">Thursday</p>
<p class="h9when">5:00 – 7:00 PM</p>
<div class="h9stats"><div><b>1d 20h</b><span>until it starts</span></div><div><b>3,112</b><span>Trojans in</span></div></div>
</div>
<div class="sheet9 card9 flat9">
<div class="s9head"><span>How the vote went</span><span class="s9note">2,583 votes</span></div>
<div class="o9s"><div class="o9 on"><span class="r1"><span class="d">Thursday</span><span class="t">5:00 – 7:00 PM</span></span><span class="r3"><span class="track"><b style="width:47%"></b></span><span class="n">1,204 votes</span></span></div>
<div class="o9"><span class="r1"><span class="d">Sunday</span><span class="t">4:00 – 5:30 PM</span></span><span class="r3"><span class="track"><b style="width:34%"></b></span><span class="n">867 votes</span></span></div>
<div class="o9"><span class="r1"><span class="d">Wednesday</span><span class="t">12:00 – 1:00 PM</span></span><span class="r3"><span class="track"><b style="width:20%"></b></span><span class="n">512 votes</span></span></div></div>
</div>
<p class="s9foot">The board opens Thursday morning: say what you're doing, and where.</p>
</div></div>
</div>
<div class="item">
<p class="label">5b · Home · decided · opted out</p>
<div class="phone"><div class="s hm v9 dec9 out9">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<div class="hero">
<div class="h9top"><span>You're out this week.</span></div>
<p class="h9big">Thursday</p>
<p class="h9when">5:00 – 7:00 PM</p>
<div class="h9stats"><div><b>1d 20h</b><span>until it starts</span></div><div><b>3,111</b><span>Trojans in</span></div></div>
</div>
<div class="sheet9 card9 flat9">
<div class="s9head"><span>How the vote went</span><span class="s9note">2,583 votes</span></div>
<div class="o9s"><div class="o9 on"><span class="r1"><span class="d">Thursday</span><span class="t">5:00 – 7:00 PM</span></span><span class="r3"><span class="track"><b style="width:47%"></b></span><span class="n">1,204 votes</span></span></div>
<div class="o9"><span class="r1"><span class="d">Sunday</span><span class="t">4:00 – 5:30 PM</span></span><span class="r3"><span class="track"><b style="width:34%"></b></span><span class="n">867 votes</span></span></div>
<div class="o9"><span class="r1"><span class="d">Wednesday</span><span class="t">12:00 – 1:00 PM</span></span><span class="r3"><span class="track"><b style="width:20%"></b></span><span class="n">512 votes</span></span></div></div>
</div>
<button class="go go9" type="button">Opt back in</button>
</div></div>
</div>
<div class="item">
<p class="label">6 · Home · the day · V9 · tap "See all"</p>
<div class="phone"><div class="s hm v9 day9">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<div class="hero">
<div class="h9top"><span>This week's quiet hours</span><button type="button">Opt out</button></div>
<p class="h9big">Today</p>
<p class="h9when">5:00 – 7:00 PM</p>
<div class="h9stats"><div><b>3h 12m</b><span>until it starts</span></div><div><b>3,112</b><span>Trojans in</span></div></div>
</div>
<div class="sheet9 board9">
<div class="s9head"><span>Going on today</span><button type="button" class="s9more">See all 14</button></div>
<div class="s9list">
<div class="r9"><div><b>Guitar on the lawn, come sit</b><span>Yours · McCarthy Quad</span></div><button type="button" class="td9">Take down</button></div>
<div class="r9"><div><b>Spikeball, anyone welcome</b><span>Alumni Park</span></div><i>9m</i></div>
<div class="r9"><div><b>Jam session, bring anything</b><span>Village fountain</span></div><i>14m</i></div>
<div class="r9"><div><b>Cooking for whoever shows up</b><span>Cale kitchen</span></div><i>21m</i></div>
<div class="r9"><div><b>Pickup soccer needs two more</b><span>Brittingham Field</span></div><i>26m</i></div>
<div class="r9"><div><b>Sketching on the steps</b><span>Doheny Library</span></div><i>31m</i></div>
<div class="r9"><div><b>Walking to the Rose Garden</b><span>Leaving from Tommy Trojan</span></div><i>38m</i></div>
<div class="r9"><div><b>Frisbee, all levels</b><span>Cromwell Field</span></div><i>44m</i></div>
<div class="r9"><div><b>Chess, two boards going</b><span>Campus Center patio</span></div><i>52m</i></div>
<div class="r9"><div><b>Reading on the grass</b><span>Founders Park</span></div><i>1h</i></div>
<div class="r9"><div><b>Sunset walk</b><span>Leaving Leavey at 5:30</span></div><i>1h</i></div>
<div class="r9"><div><b>Hammocks up, room for more</b><span>Trousdale by Bovard</span></div><i>1h</i></div>
<div class="r9"><div><b>Basketball, next five</b><span>Lyon Center courts</span></div><i>2h</i></div>
<div class="r9"><div><b>Board games in the lounge</b><span>Ginsburg Hall</span></div><i>2h</i></div>
</div>
<div class="cmp9"><span>What you're doing, and where</span><b aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M6 11l6-6 6 6"/></svg></b></div>
</div>
</div></div>
</div>
<div class="item">
<p class="label">6b · Home · the day · opted out</p>
<div class="phone"><div class="s hm v9 day9 out9">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<div class="hero">
<div class="h9top"><span>You're out this week.</span></div>
<p class="h9big">Today</p>
<p class="h9when">5:00 – 7:00 PM</p>
<div class="h9stats"><div><b>3h 12m</b><span>until it starts</span></div><div><b>3,111</b><span>Trojans in</span></div></div>
</div>
<div class="sheet9">
<div class="s9head"><span>Going on today</span><span class="s9note">13</span></div>
<div class="s9list">
<div class="r9"><div><b>Spikeball, anyone welcome</b><span>Alumni Park</span></div><i>9m</i></div>
<div class="r9"><div><b>Jam session, bring anything</b><span>Village fountain</span></div><i>14m</i></div>
<div class="r9"><div><b>Cooking for whoever shows up</b><span>Cale kitchen</span></div><i>21m</i></div>
<div class="r9"><div><b>Pickup soccer needs two more</b><span>Brittingham Field</span></div><i>26m</i></div>
</div>
<button class="go go9" type="button">Opt back in</button>
</div>
</div></div>
</div>
<div class="item">
<p class="label">7 · Home · locked · V3 · tap "See all"</p>
<div class="phone"><div class="s hm v9 nt nb nt9">
<img class="stars" src="data:image/png;base64,{starsn}" alt="">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<img class="lmoon" src="data:image/png;base64,{mcd}" alt="">
<div class="l9cap"><span>Quiet hours are on</span><button type="button">Leave</button></div>
<p class="l9big">Until 7:00</p>
<p class="l9cnt">3,098 Trojans in right now. One dot each.</p>
<div class="sheet9 board9">
<div class="s9head"><span>Going on now</span><button type="button" class="s9more">See all 14</button></div>
<div class="s9list">
<div class="r9"><div><b>Guitar on the lawn, come sit</b><span>Yours · McCarthy Quad</span></div><button type="button" class="td9">Take down</button></div>
<div class="r9"><div><b>Spikeball, anyone welcome</b><span>Alumni Park</span></div><i>9m</i></div>
<div class="r9"><div><b>Jam session, bring anything</b><span>Village fountain</span></div><i>14m</i></div>
<div class="r9"><div><b>Cooking for whoever shows up</b><span>Cale kitchen</span></div><i>21m</i></div>
<div class="r9"><div><b>Pickup soccer needs two more</b><span>Brittingham Field</span></div><i>26m</i></div>
<div class="r9"><div><b>Sketching on the steps</b><span>Doheny Library</span></div><i>31m</i></div>
<div class="r9"><div><b>Walking to the Rose Garden</b><span>Leaving from Tommy Trojan</span></div><i>38m</i></div>
<div class="r9"><div><b>Frisbee, all levels</b><span>Cromwell Field</span></div><i>44m</i></div>
<div class="r9"><div><b>Chess, two boards going</b><span>Campus Center patio</span></div><i>52m</i></div>
<div class="r9"><div><b>Reading on the grass</b><span>Founders Park</span></div><i>1h</i></div>
<div class="r9"><div><b>Sunset walk</b><span>Leaving Leavey at 5:30</span></div><i>1h</i></div>
<div class="r9"><div><b>Hammocks up, room for more</b><span>Trousdale by Bovard</span></div><i>1h</i></div>
<div class="r9"><div><b>Basketball, next five</b><span>Lyon Center courts</span></div><i>2h</i></div>
<div class="r9"><div><b>Board games in the lounge</b><span>Ginsburg Hall</span></div><i>2h</i></div>
</div>
<div class="cmp9"><span>What you're doing, and where</span><b aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M6 11l6-6 6 6"/></svg></b></div>
</div>
</div></div>
</div>
<div class="item">
<p class="label">7b · Home · locked · opted out, or left early</p>
<div class="phone"><div class="s hm v9 nt nb nt9 off9">
<img class="stars" src="data:image/png;base64,{starsn}" alt="">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<img class="lmoon" src="data:image/png;base64,{mcd}" alt="">
<div class="l9cap"><span>You're out this week.</span></div>
<p class="l9big">Until 7:00</p>
<p class="l9cnt">3,097 Trojans in right now.</p>
<div class="sheet9">
<div class="s9head"><span>Going on now</span><span class="s9note">13</span></div>
<div class="s9list">
<div class="r9"><div><b>Spikeball, anyone welcome</b><span>Alumni Park</span></div><i>9m</i></div>
<div class="r9"><div><b>Jam session, bring anything</b><span>Village fountain</span></div><i>14m</i></div>
<div class="r9"><div><b>Cooking for whoever shows up</b><span>Cale kitchen</span></div><i>21m</i></div>
</div>
<button class="go go9" type="button">Join until 7:00</button>
</div>
</div></div>
</div>
<div class="item">
<p class="label">8 · The question · V1 · the moment the window ends</p>
<div class="phone"><div class="s hw q">
<canvas id="qc" width="1170" height="1380" aria-hidden="true"></canvas>
<p class="lab">It's 7:00. 3,041 Trojans stayed to the end.</p>
<p class="step">What did you do?</p>
<p class="sub">It goes into the recap at 7:15.</p>
<div class="qf">It's anonymous. Say what you really did.</div>
<div class="foot">
<button class="go" type="button">Add it</button>
<button class="skip" type="button">Skip</button>
</div>
</div></div>
</div>
<div class="item">
<p class="label">8b · The question · typing</p>
<div class="phone"><div class="s hw q k">
<p class="lab">It's 7:00. 3,041 Trojans stayed to the end.</p>
<p class="step">What did you do?</p>
<p class="sub">It goes into the recap at 7:15.</p>
<div class="qf on">Finally walked the Rose Garden with my roommate, then sat on the grass until the lights came on. Nobody checked the time.</div>
<p class="qn">121 / 200</p>
<div class="foot">
<button class="go" type="button">Add it</button>
</div>
{keyboard}
</div></div>
</div>
<div class="item">
<p class="label">9 · Home · summary · V4</p>
<div class="phone"><div class="s hm v9 sum9">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<div class="hero">
<div class="h9top"><span>Today, 5:00 – 7:00 PM</span></div>
<p class="h9big sm">How it went</p>
<p class="h9when">Quiet hours are over.</p>
<div class="h9stats three"><div><b>3,041</b><span>of 3,112 stayed</span></div><div><b>6,140</b><span>hours back</span></div><div><b>1,904</b><span>reaches</span></div></div>
</div>
<div class="sheet9 card9 flat9">
<div class="s9head"><span>The hour, told back</span><span class="s9note">from 1,287 lines</span></div>
<div class="hl9s"><p class="hl9">41 people called a parent.</p>
<p class="hl9">Someone finished a painting they started in September.</p>
<p class="hl9">Spikeball on McCarthy Quad grew to about thirty.</p>
<p class="hl9">63 people took a nap.</p>
<p class="hl9">19 people cooked for someone else.</p></div>
</div>
<p class="s9foot">Voting for next week opens Sunday.</p>
</div></div>
</div>
<div class="item">
<p class="label">9b · Home · summary · before the recap lands</p>
<div class="phone"><div class="s hm v9 sum9">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<div class="hero">
<div class="h9top"><span>Today, 5:00 – 7:00 PM</span></div>
<p class="h9big sm">How it went</p>
<p class="h9when">Quiet hours are over.</p>
<div class="h9stats three"><div><b>3,041</b><span>of 3,112 stayed</span></div><div><b>6,140</b><span>hours back</span></div><div><b>1,904</b><span>reaches</span></div></div>
</div>
<div class="sheet9 card9 flat9">
<div class="s9head"><span>The hour, told back</span><span class="s9note">at 7:15</span></div>
<p class="s9wait">People are still writing what they did. 1,287 lines so far.</p>
</div>
<p class="s9foot">Voting for next week opens Sunday.</p>
</div></div>
</div>
<div class="item">
<p class="label">9c · Home · summary · opted out</p>
<div class="phone"><div class="s hm v9 sum9">
<div class="bar"><span class="wm">Quiet Hours</span><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>
<div class="hero">
<div class="h9top me"><span>You were out this week.</span></div>
<p class="h9big sm">How it went</p>
<p class="h9when">Quiet hours are over.</p>
<div class="h9stats three"><div><b>3,040</b><span>of 3,111 stayed</span></div><div><b>6,138</b><span>hours back</span></div><div><b>1,904</b><span>reaches</span></div></div>
</div>
<div class="sheet9 card9 flat9">
<div class="s9head"><span>The hour, told back</span><span class="s9note">from 1,287 lines</span></div>
<div class="hl9s"><p class="hl9">41 people called a parent.</p>
<p class="hl9">Someone finished a painting they started in September.</p>
<p class="hl9">Spikeball on McCarthy Quad grew to about thirty.</p>
<p class="hl9">63 people took a nap.</p>
<p class="hl9">19 people cooked for someone else.</p></div>
</div>
<p class="s9foot">You're in again next week. Voting opens Sunday.</p>
</div></div>
</div>
'''
page += HOW_JS.replace("__DOTS__", dots64)
open(f"{S}/quiet-screens/quiet-hours-screens.html", "w").write(page)
open("/Users/hartleyscales/quiet-hours/design/preview.html", "w").write('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>html,body{margin:0}</style></head><body>' + page + '</body></html>')
print("page bytes", len(page), "dots", len(dots))
