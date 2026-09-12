import type { Repository } from "@/lib/db/repository";
import { hashTelegramId } from "@/lib/measurement/tracking";

type TelegramUpdate = {
  update_id: number;
  message?: { chat: { id: number }; from?: { id: number }; text?: string };
  callback_query?: { id: string; from: { id: number }; data?: string; message?: { chat: { id: number } } };
};
type BotConfig = { token: string; userSecret: string };
export type TelegramSender = (method: string, payload: Record<string, unknown>) => Promise<void>;

export function telegramSender(token: string): TelegramSender {
  return async (method, payload) => {
    const response = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`Telegram API: ${response.status}`);
  };
}

export async function handleTelegramUpdate(update: TelegramUpdate, repo: Repository, config: BotConfig, send = telegramSender(config.token)) {
  if (!await repo.claimTelegramUpdate(update.update_id)) return;
  if (update.message?.text?.startsWith("/start")) {
    const telegramId = update.message.from?.id ?? update.message.chat.id;
    const userKey = await hashTelegramId(telegramId, config.userSecret);
    await repo.ensureUser(userKey);
    const token = update.message.text.trim().split(/\s+/)[1] ?? "";
    const placement = token ? await repo.placementByToken(token) : null;
    await repo.recordTouch({ userKey, placementId: placement?.placementId ?? null, source: placement ? "telegram_deeplink" : "telegram_organic", confidence: placement ? "deterministic" : "unknown", dataOrigin: placement?.dataOrigin ?? "real" });
    await send("sendMessage", {
      chat_id: update.message.chat.id,
      text: placement?.targetCourse ? `Расскажем о курсе «${placement.targetCourse}». Что вас интересует?` : "Поможем подобрать программу. Что вас интересует?",
      reply_markup: { inline_keyboard: [[{ text: "Узнать про курс", callback_data: "course" }], [{ text: "Написать менеджеру", callback_data: "manager" }]] },
    });
    return;
  }
  const query = update.callback_query;
  if (query && (query.data === "course" || query.data === "manager")) {
    const userKey = await hashTelegramId(query.from.id, config.userSecret);
    await repo.ensureUser(userKey);
    const touch = await repo.latestTouch(userKey);
    const placement = touch?.placementId ? await repo.placementById(touch.placementId) : null;
    await repo.upsertOpenLead(userKey, placement?.targetCourse ?? null, placement?.dataOrigin ?? "real");
    await send("answerCallbackQuery", { callback_query_id: query.id, text: "Интерес зафиксирован" });
    if (query.message) await send("sendMessage", { chat_id: query.message.chat.id, text: query.data === "manager" ? "Спасибо! Мы сохранили ваш интерес. Контакт менеджера появится здесь после подключения CRM." : `Отлично! Мы сохранили интерес${placement?.targetCourse ? ` к курсу «${placement.targetCourse}»` : ""}.` });
  }
}
