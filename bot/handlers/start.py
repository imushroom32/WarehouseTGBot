# start.py (обновлённая версия с регистрацией пользователей и защитой от сбоев)
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
)
from telegram.ext import ContextTypes

from bot.db import Session
from bot.keyboards import main_menu_markup
from bot.models import User


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        session = Session()
        user = User.get_or_create(session, update.effective_user)
        role = user.role
        session.close()

        markup = main_menu_markup(role)

        if update.callback_query:
            await update.callback_query.answer()
            try:
                await update.callback_query.edit_message_text("👋 Главное меню:", reply_markup=markup)
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
        elif update.message:
            await update.message.reply_text("👋 Главное меню:", reply_markup=markup)
        else:
            await update.effective_chat.send_message("👋 Главное меню:", reply_markup=markup)

    except Exception as e:
        print("‼️ ОШИБКА В start:", e)
        try:
            await update.effective_chat.send_message("❌ Ошибка при открытии меню.")
        except Exception:
            pass


def get_handlers():
    return [
        CommandHandler("start", start),
        CallbackQueryHandler(start, pattern="^main_menu$"),
    ]