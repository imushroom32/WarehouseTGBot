# bot/handlers/start.py
"""
Главное меню
"""

from telegram import Update
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    CommandHandler,
)
from bot.keyboards import main_menu_markup, home_kb
from bot.db import Session
from bot.models import User


def get_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(start, pattern="^start$")


def get_handlers():
    return [
        CommandHandler("start", start),
        CallbackQueryHandler(start, pattern="^main_menu$"),
    ]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data.clear()

        telegram_id = str(update.effective_user.id)
        session = Session()
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        session.close()

        if not user:
            await update.effective_chat.send_message("❌ Вы не зарегистрированы в системе.")
            return ConversationHandler.END

        kb = main_menu_markup(user.role)

        if update.callback_query:
            query = update.callback_query
            await query.answer()

            try:
                if query.message:
                    await query.message.edit_text("🏠 Главное меню", reply_markup=kb)
                else:
                    await update.effective_chat.send_message("🏠 Главное меню", reply_markup=kb)
            except Exception as e:
                print("‼️ Не удалось отредактировать сообщение:", e)
                try:
                    await query.message.delete()
                except:
                    pass
                await update.effective_chat.send_message("🏠 Главное меню", reply_markup=kb)

        elif update.message:
            await update.message.reply_text("🏠 Главное меню", reply_markup=kb)

        return ConversationHandler.END

    except Exception as e:
        print("‼️ ОШИБКА В start:", e)
        await update.effective_chat.send_message("❌ Ошибка при открытии меню.")
        return ConversationHandler.END