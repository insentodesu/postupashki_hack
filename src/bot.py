"""
Tracking bot. /start <token> создаёт deterministic touch.
Без TELEGRAM_BOT_TOKEN не запускается — используйте offline simulation в дашборде.
"""
import logging
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes,
)

import db
import tracking

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tracking_bot")


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uk = tracking.user_key_from_telegram_id(user.id)
    db.ensure_user(uk)

    token = ctx.args[0] if ctx.args else None
    placement = db.get_placement_by_token(token) if token else None

    if placement:
        db.add_touch(uk, placement["placement_id"],
                     source="bot_deeplink", confidence="deterministic")
        course = placement.get("target_course") or "не указан"
        text = (f"Привет! Ты пришёл из размещения {placement['placement_id']}.\n"
                f"Курс: {course}.")
    else:
        db.add_touch(uk, None, source="organic", confidence="unknown")
        text = "Привет! Ты пришёл без трекинговой ссылки — источник неизвестен."

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Узнать про курс", callback_data="learn"),
        InlineKeyboardButton("Написать менеджеру", callback_data="manager"),
    ]])
    await update.message.reply_text(text, reply_markup=kb)


async def lead(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uk = tracking.user_key_from_telegram_id(user.id)
    course = " ".join(ctx.args) if ctx.args else None
    lead_id = db.add_lead(uk, course=course)
    await update.message.reply_text(f"Лид #{lead_id} создан. Курс: {course or '—'}")


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    uk = tracking.user_key_from_telegram_id(user.id)
    touch = db.latest_touch(uk)
    course = touch.get("target_course") if touch else None
    if q.data == "learn":
        lead_id = db.add_lead(uk, course=course)
        label = f" к курсу «{course}»" if course else ""
        await q.edit_message_text(f"Записал тебя как лид #{lead_id}{label}.")
    elif q.data == "manager":
        lead_id = db.add_lead(uk, course=course)
        await q.edit_message_text(
            f"Интерес сохранён как лид #{lead_id}. Контакт менеджера "
            "появится после подключения CRM."
        )


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    if not os.environ.get("USER_HASH_SECRET", "").strip():
        raise RuntimeError("USER_HASH_SECRET is required")
    db.init_db()
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lead", lead))
    app.add_handler(CallbackQueryHandler(on_callback))
    log.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
