const encoder = new TextEncoder();

export async function hashTelegramId(
  telegramId: string | number,
  secret: string,
): Promise<string> {
  if (!secret) throw new Error("USER_HASH_SECRET не задан");
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(String(telegramId)),
  );
  return Array.from(new Uint8Array(signature))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
}

export function buildDeepLink(botUsername: string, token: string): string {
  const username = botUsername.trim().replace(/^@/, "");
  if (!username) throw new Error("BOT_USERNAME не задан");
  if (!token.trim()) throw new Error("Tracking token не задан");
  return `https://t.me/${username}?start=${encodeURIComponent(token.trim())}`;
}

export function newTrackingToken(): string {
  return `p_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
}
