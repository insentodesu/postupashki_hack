async function main() {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const secret = process.env.TELEGRAM_WEBHOOK_SECRET;
  const appUrl = process.env.APP_URL?.replace(/\/$/, "");
  if (!token || !secret || !appUrl) throw new Error("Нужны TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET и APP_URL");
  const response = await fetch(`https://api.telegram.org/bot${token}/setWebhook`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ url: `${appUrl}/api/telegram/webhook`, secret_token: secret, allowed_updates: ["message", "callback_query"] }),
  });
  if (!response.ok) throw new Error(`Telegram API: ${response.status}`);
  console.log("Telegram webhook зарегистрирован");
}

main().catch((error) => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1; });
