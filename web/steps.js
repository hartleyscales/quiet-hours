// The sample campus's controls: outside the phone, in the order a student meets the app. Each step puts the
// sample week in that situation and shows its screen; "Opted out" shows the opted-out version where there is one.

const STEPS = [
  ["signin", "Sign in"],
  ["how", "How it works"],
  ["lock", "The lock"],
  ["vote", "Voting"],
  ["decided", "Decided"],
  ["day", "The day"],
  ["live", "Quiet hours on"],
  ["ended", "Just ended"],
  ["told", "Told back"],
];

/** Which step a screen belongs to. */
function stepOf(key, st) {
  switch (key) {
    case "signin": case "how": case "lock": return key;
    case "vote": case "vote-out": return "vote";
    case "sel": case "sel-out": return "decided";
    case "day": case "day-out": return "day";
    case "live": case "live-out": return "live";
    case "question": return "ended";
    case "sum": case "sum-out": case "sum-pre": case "sum-pre-out": return st?.phase === "ended" ? "ended" : "told";
    default: return null;
  }
}

export function mountSteps(page, demo, flow) {
  const el = document.createElement("nav");
  el.className = "steps";
  el.setAttribute("aria-label", "Sample data steps");
  el.innerHTML = `<div class="row">${STEPS.map(([k, label]) => `<button type="button" data-step="${k}">${label}</button>`).join("")}` +
    '<button type="button" class="out" role="switch" aria-checked="false">Opted out</button></div>' +
    '<p class="note">Sample data. Every screen here is the real interface; the iPhone app runs the same screens on the live server.</p>';
  page.appendChild(el);
  const buttons = [...el.querySelectorAll("[data-step]")], sw = el.querySelector(".out");

  function mark(step) {
    if (!step) return;
    buttons.forEach((b) => {
      const on = b.dataset.step === step;
      b.classList.toggle("on", on);
      if (on) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
    });
  }
  function markOut() {
    const out = demo.out;
    sw.classList.toggle("on", out);
    sw.setAttribute("aria-checked", out ? "true" : "false");
  }

  buttons.forEach((b) => b.addEventListener("click", () => {
    const step = b.dataset.step;
    if (step === "signin") { demo.reset(); flow.signIn(); }
    else if (step === "how") { demo.step("vote"); flow.how(); } // finishing the lock lands on Voting
    else if (step === "lock") { demo.step("vote"); flow.lock(); }
    else { demo.step(step); flow.home(); }
    mark(step); markOut();
  }));
  sw.addEventListener("click", async () => {
    demo.setOut(!demo.out);
    markOut();
    await flow.refresh();
  });

  flow.watch((key, st) => { mark(stepOf(key, st)); markOut(); });
}
