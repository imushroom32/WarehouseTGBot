"""
Хендлеры для добавления нового товара.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.db import Session
from bot.keyboards import home_kb
from bot.models import Product, Log

# состояние разговора
ENTER_NAME = 0


async def add_product_start(
        update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Шаг 1: Запрашивает название нового товара.
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🆕 Введите название товара:")
    return ENTER_NAME


async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    session = Session()

    try:
        product = Product(name=name)
        session.add(product)

        log = Log(
            action="add_product",
            user_id=str(update.effective_user.id),
            info=f"Добавлен товар: {name}"
        )
        session.add(log)

        session.commit()
        await update.message.reply_text(f"✅ Товар «{name}» добавлен!", reply_markup=home_kb())

        # ── новая клавиатура ───────────────────────────────────────────
        keyboard = [
            [
                InlineKeyboardButton("🆕 Добавить ещё", callback_data="add_product"),
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"),
            ]
        ]
        await update.message.reply_text(
            "Что дальше?", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        session.rollback()
        await update.message.reply_text(f"❗ Ошибка: {e}")
    finally:
        session.close()
    return ConversationHandler.END


def get_handler() -> ConversationHandler:
    """
    Возвращает ConversationHandler для добавления товара.
    """
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(add_product_start, pattern="^add_product$")],
        states={ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)]},
        fallbacks=[]
    )
