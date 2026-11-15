// Random ids with a readable type prefix, e.g. "ln_k3v9q2m7xd4h".
// Crockford-style base32 without look-alike characters.
const ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz";

export type IdPrefix = "us" | "wk" | "op" | "po" | "ln" | "ch";

export function newId(prefix: IdPrefix, length = 14): string {
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  let out = "";
  for (const b of bytes) out += ALPHABET[b & 31];
  return `${prefix}_${out}`;
}

/** A uniformly random 6-digit code (rejection sampling, no modulo bias). */
export function newSigninCode(): string {
  const limit = Math.floor(0xffffffff / 1_000_000) * 1_000_000;
  for (;;) {
    const [n] = crypto.getRandomValues(new Uint32Array(1));
    if (n !== undefined && n < limit) return String(n % 1_000_000).padStart(6, "0");
  }
}

/** 32 random bytes, base64url. Used as the bearer session token. */
export function newSessionToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

export async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Constant-time comparison of two strings (compares their SHA-256 digests). */
export async function safeEqual(a: string, b: string): Promise<boolean> {
  const [ha, hb] = await Promise.all([sha256Hex(a), sha256Hex(b)]);
  let diff = 0;
  for (let i = 0; i < ha.length; i++) diff |= ha.charCodeAt(i) ^ hb.charCodeAt(i);
  return diff === 0;
}
