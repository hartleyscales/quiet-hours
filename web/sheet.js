// The board, as its own screen: "Going on now" with "Close", the posts as rows (the list scrolls, fading at its
// edges) and the post field pinned at the foot. Your own post says "Yours · place" and has "Take down" where the
// others show their age. Opening and closing the screen is app.js's; this fills it and runs the field.
import { ago } from "./format.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const reduced = () => Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);

/** Splits "what, where" on the last comma or " at ". Returns null when there is no separator. */
export function splitPost(raw) {
  const v = raw.trim().replace(/\s+/g, " ");
  const comma = v.lastIndexOf(","), at = v.toLowerCase().lastIndexOf(" at ");
  const cut = Math.max(comma, at);
  if (cut < 0) return null;
  const text = v.slice(0, cut).trim(), place = v.slice(cut + (cut === at ? 4 : 1)).trim();
  return text && place ? { text, place } : null;
}

/**
 * sheet: the board's .sheet9 element. opts:
 *   now()          the server's clock, for the posts' ages
 *   take(post)     takes a post down on the server (rejects on failure)
 *   send(t, p)     posts on the server (rejects on failure)
 *   say(err)       a quiet line for a failure, or null for the default
 */
export function mountBoard(sheet, opts) {
  const list = sheet.querySelector(".s9list"), head = sheet.querySelector(".s9head span");
  const form = sheet.querySelector("form.cmp9"), input = form?.querySelector("input");
  const PLACEHOLDER = input?.placeholder, TITLE = head.textContent;
  let posts = [], rows = new Map(), held = null, busy = false, flashT = 0;

  /** A failure, said quietly where the title is for a few seconds. */
  function flash(text) {
    clearTimeout(flashT);
    head.textContent = text;
    head.classList.add("note");
    flashT = setTimeout(() => { flashT = 0; head.textContent = TITLE; head.classList.remove("note"); }, 4000);
  }

  function row(p) {
    const el = document.createElement("div");
    el.className = "r9";
    el.innerHTML = `<div><b>${esc(p.text)}</b><span>${p.mine ? "Yours · " : ""}${esc(p.place)}</span></div>` +
      (p.mine ? '<button type="button" class="td9">Take down</button>' : "<i></i>");
    if (p.mine) el.querySelector(".td9").addEventListener("click", () => takeDown(p, el));
    return el;
  }
  /** The server's list, keeping the rows of posts that are still there. */
  function setPosts(next) {
    const old = rows;
    rows = new Map();
    posts = next;
    next.forEach((p) => {
      const was = old.get(p.id);
      const keep = was && was.post.text === p.text && was.post.place === p.place && was.post.mine === p.mine;
      if (was && !keep) was.el.remove();
      rows.set(p.id, keep ? { post: p, el: was.el } : { post: p, el: row(p) });
      old.delete(p.id);
    });
    old.forEach(({ el }) => { if (!el.dataset.leaving) el.remove(); });
    rows.forEach(({ el }) => list.appendChild(el)); // newest first, as the server lists them
    ages();
  }
  function ages() {
    rows.forEach(({ post, el }) => { const i = el.querySelector("i"); if (i) { const a = ago(post.createdAt, opts.now()); if (i.textContent !== a) i.textContent = a; } });
  }

  function takeDown(p, el) { // your row leaves, the rest close the gap
    if (el.dataset.leaving) return;
    el.dataset.leaving = "1";
    const fold = reduced()
      ? el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 200, easing: "ease", fill: "forwards" })
      : el.animate([{ opacity: 1, height: "66px" }, { opacity: 0, height: "0px", borderBottomWidth: "0px" }], { duration: 260, easing: "cubic-bezier(.2,.8,.2,1)", fill: "forwards" });
    const before = posts;
    posts = posts.filter((x) => x.id !== p.id); rows.delete(p.id);
    opts.take(p).then(
      () => { fold.finished.then(() => el.remove(), () => el.remove()); },
      (err) => { // the server kept it: put it back where it was
        fold.cancel(); delete el.dataset.leaving;
        rows.set(p.id, { post: p, el });
        setPosts(before);
        flash(opts.say(err) ?? "It couldn't be taken down. Try again.");
      },
    );
  }

  async function submit() {
    if (busy || !input) return;
    const v = input.value.trim().replace(/\s+/g, " ");
    if (!v) { input.focus(); return; }
    let text, place;
    if (held !== null) { text = held; place = v; }
    else {
      const parts = splitPost(v);
      if (!parts) { // no place given: ask for it
        held = v; input.value = ""; input.placeholder = "Where?"; input.maxLength = 60; input.focus();
        return;
      }
      ({ text, place } = parts);
    }
    busy = true;
    try {
      await opts.send(text, place);
      held = null; input.value = ""; input.placeholder = PLACEHOLDER; input.maxLength = 202;
      list.scrollTop = 0;
    } catch (err) {
      held = null; input.placeholder = PLACEHOLDER; input.maxLength = 202;
      input.value = `${text}, ${place}`;
      flash(opts.say(err) ?? "That didn't go up. Try again.");
    } finally { busy = false; }
  }
  form?.addEventListener("submit", (e) => { e.preventDefault(); submit(); });
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && held !== null) { e.stopPropagation(); input.value = held; held = null; input.placeholder = PLACEHOLDER; input.maxLength = 202; }
  });
  form?.querySelector(".snd").addEventListener("pointerdown", (e) => e.preventDefault()); // keep the field focused

  return {
    setPosts, ages,
    destroy() { clearTimeout(flashT); },
  };
}
