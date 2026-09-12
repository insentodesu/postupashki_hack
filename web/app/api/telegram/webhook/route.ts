import { jsonError, repository } from "@/lib/api";
import { handleTelegramUpdate } from "@/lib/telegram";

export const runtime = "nodejs";
function safeEqual(left: string, right: string) {
  if (!left || left.length !== right.length) return false;
  let diff = 0; for (let i = 0; i < left.length; i += 1) diff |= left.charCodeAt(i) ^ right.charCodeAt(i);
  return diff === 0;
}

export async function POST(request: Request) {
  const secret = process.env.TELEGRAM_WEBHOOK_SECRET ?? "";
  if (!safeEqual(request.headers.get("x-telegram-bot-api-secret-token") ?? "", secret)) return new Response("Unauthorized", { status: 401 });
  try {
    const token = process.env.TELEGRAM_BOT_TOKEN ?? ""; const userSecret = process.env.USER_HASH_SECRET ?? "";
    if (!token || !userSecret) throw new Error("Telegram environment is incomplete");
    await handleTelegramUpdate(await request.json(), repository(), { token, userSecret });
    return Response.json({ ok: true });
  } catch (error) { return jsonError(error, 500); }
}
