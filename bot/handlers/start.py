# start.py (обновлённая версия с регистрацией пользователей)
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
)
from telegram.ext import ContextTypes

from bot.db import Session  # добавили
from bot.keyboards import main_menu_markup
from bot.models import User  # добавили


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = Session()
    user = User.get_or_create(session, update.effective_user)
    role = user.role
    session.close()

    markup = main_menu_markup(role)

    # -- вывод меню (как и раньше) --
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text("👋 Главное меню:", reply_markup=markup)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
    else:
        await update.message.reply_text("👋 Главное меню:", reply_markup=markup)


def get_handlers():
    return [
        CommandHandler("start", start),
        CallbackQueryHandler(start, pattern="^main_menu$"),
    ]
