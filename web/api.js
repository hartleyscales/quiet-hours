// The live Quiet Hours API (docs/API.md). The page uses it only when told where it is: ?api=<base url>
// (empty for this page's own origin, as with web/dev.mjs), window.QH_API, or <meta name="qh-api">.
// Otherwise the page runs on the sample campus in demo-api.js, which offers the same calls.

const meta = document.querySelector('meta[name="qh-api"]')?.content || null;
const param = new URLSearchParams(location.search).get("api");
export const BASE = String(param ?? window.QH_API ?? meta ?? "").replace(/\/+$/, "");

const KEY = "qh.session";
function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; }
}
let session = load(); // { token, email }

/** Small things this device remembers (onboarding done, a skipped question). */
export const prefs = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
};

export const signedIn = () => Boolean(session?.token);
export const email = () => session?.email ?? "";
export function forget() {
  session = null;
  try { localStorage.removeItem(KEY); } catch {}
}

/** A failed call. `code` is the API's stable error code, or "network" when the server could not be reached. */
export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message || code);
    this.status = status; this.code = code; this.details = details;
  }
}

/** Listeners for a session the server no longer accepts. */
const lost = new Set();
export const onSignedOut = (fn) => lost.add(fn);

export async function call(method, path, { body, admin } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (admin) headers["X-Admin-Secret"] = admin;
  else if (session?.token) headers.Authorization = `Bearer ${session.token}`;
  let res;
  try {
    res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store" });
  } catch (e) {
    throw new ApiError(0, "network", e?.message);
  }
  const json = await res.json().catch(() => null);
  if (!res.ok) {
    const err = json?.error ?? {};
    if (res.status === 401 && !admin && session) { forget(); lost.forEach((fn) => fn()); }
    throw new ApiError(res.status, err.code ?? `http_${res.status}`, err.message, err.details);
  }
  return json;
}

export const startSignIn = (address) => call("POST", "/v1/auth/start", { body: { email: address } });
export async function verify(address, code) {
  const out = await call("POST", "/v1/auth/verify", { body: { email: address, code } });
  session = { token: out.token, email: out.user?.email ?? address };
  try { localStorage.setItem(KEY, JSON.stringify(session)); } catch {}
  return out;
}
export async function signOut() {
  try { await call("POST", "/v1/auth/sign-out"); } finally { forget(); }
}

export const state = () => call("GET", "/v1/state");
export const vote = (optionId, weekId) => call("POST", "/v1/vote", { body: { optionId, weekId } });
export const skip = (weekId) => call("POST", "/v1/me/skip", { body: { weekId } });
export const rejoin = (weekId) => call("POST", "/v1/me/rejoin", { body: { weekId } });
export const leave = (weekId) => call("POST", "/v1/me/leave", { body: { weekId } });
export const board = () => call("GET", "/v1/board?limit=200");
export const post = (text, place, weekId) => call("POST", "/v1/board", { body: { text, place, weekId } });
export const takeDown = (postId) => call("DELETE", `/v1/board/${encodeURIComponent(postId)}`);
export const writeLine = (text, weekId) => call("POST", "/v1/lines", { body: { text, weekId } });

// Admin, for the demo strip only. The secret is passed in by the caller, never kept here.
export const admin = {
  weeks: (secret) => call("GET", "/v1/admin/weeks", { admin: secret }),
  week: (secret, id) => call("GET", `/v1/admin/weeks/${id}`, { admin: secret }),
  jump: (secret, id, jumpTo) => call("POST", `/v1/admin/weeks/${id}/timeline`, { admin: secret, body: { jumpTo } }),
  shift: (secret, id, shiftSeconds) => call("POST", `/v1/admin/weeks/${id}/timeline`, { admin: secret, body: { shiftSeconds } }),
  seed: (secret, step) => call("POST", "/v1/admin/demo/seed", { admin: secret, body: { step } }),
  recap: (secret, id) => call("POST", `/v1/admin/weeks/${id}/recap`, { admin: secret }),
};
