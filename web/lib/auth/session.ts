const encoder = new TextEncoder();
export const SESSION_COOKIE = "measurement_session";

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

async function hmac(value: string, secret: string): Promise<string> {
  if (!secret) throw new Error("SESSION_SECRET не задан");
  const key = await crypto.subtle.importKey(
    "raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(value));
  return toBase64Url(new Uint8Array(signature));
}

function constantTimeEqual(left: string, right: string): boolean {
  const a = encoder.encode(left);
  const b = encoder.encode(right);
  const length = Math.max(a.length, b.length);
  let mismatch = a.length ^ b.length;
  for (let index = 0; index < length; index += 1) {
    mismatch |= (a[index] ?? 0) ^ (b[index] ?? 0);
  }
  return mismatch === 0;
}

export async function createSessionToken(secret: string, expiresAt: number): Promise<string> {
  const payload = String(expiresAt);
  return `${payload}.${await hmac(payload, secret)}`;
}

export async function verifySession(token: string | undefined, secret: string): Promise<boolean> {
  if (!token || !secret) return false;
  const separator = token.indexOf(".");
  if (separator < 1) return false;
  const payload = token.slice(0, separator);
  const supplied = token.slice(separator + 1);
  const expiresAt = Number(payload);
  if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) return false;
  return constantTimeEqual(supplied, await hmac(payload, secret));
}

export async function passwordMatches(supplied: string, expected: string): Promise<boolean> {
  const salt = "postupashki-dashboard-password-v1";
  const [left, right] = await Promise.all([hmac(supplied, salt), hmac(expected, salt)]);
  return constantTimeEqual(left, right);
}
