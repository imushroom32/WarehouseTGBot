# bot/handlers/start.py
"""
Главное меню
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    CommandHandler,
)

from bot.config import MANAGER_TELEGRAM_IDS
from bot.keyboards import main_menu_markup
from bot.db import Session
from bot.models import User, JoinRequest


def get_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(start, pattern="^start$")


def get_handlers():
    return [
        CommandHandler("start", start),
        CallbackQueryHandler(start, pattern="^main_menu$"),
    ]

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    tg_id = str(update.effective_user.id)
    full  = update.effective_user.full_name or "No name"

    session = Session()
    user = session.query(User).filter_by(telegram_id=tg_id).one_or_none()
    req  = session.query(JoinRequest).filter_by(telegram_id=tg_id).one_or_none()

    # ── 1. есть аккаунт → обычный запуск ──────────────────────────────
    if user:
        kb = main_menu_markup(user.role)
        await (update.message or update.callback_query.message).reply_text("🏠 Главное меню", reply_markup=kb)
        session.close()
        return ConversationHandler.END

    # ── 2. уже подал заявку → напоминалка ─────────────────────────────
    if req:
        await update.effective_chat.send_message("⌛ Ваша заявка ещё не рассмотрена.")
        session.close()
        return ConversationHandler.END

    # ── 3. новый человек → записываем запрос и шлём админу ────────────
    session.add(JoinRequest(telegram_id=tg_id, full_name=full))
    session.commit()
    session.close()

    await update.effective_chat.send_message(
        "👋 Привет! Доступ к боту выдаёт администратор. "
        "Я отправил заявку — ожидайте подтверждения."
    )

    # ► всем администраторам
    for admin_id in MANAGER_TELEGRAM_IDS:
        try:
            await ctx.bot.send_message(
                admin_id,
                f"🆕 <b>{full}</b> (<code>{tg_id}</code>) просит доступ.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Одобрить", callback_data=f"join_ok:{tg_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"join_no:{tg_id}"),
                    ]
                ])
            )
        except Exception:
            pass

    return ConversationHandler.END