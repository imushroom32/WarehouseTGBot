# bot/handlers/delete_product.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

from bot.db import Session
from bot.keyboards import home_kb
from bot.models import Product, Stock

SELECT_PRODUCT = 0


async def delete_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    session = Session()
    # Выбираем товары, у которых нет стока
    subquery = session.query(Stock.product_id).distinct()
    products = (
        session.query(Product)
        .filter(Product.id.notin_(subquery))
        .order_by(Product.name)
        .all()
    )
    session.close()

    if not products:
        await query.edit_message_text("❗ Нет товаров, доступных для удаления.", reply_markup=home_kb())
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(p.name, callback_data=str(p.id))] for p in products]
    await query.edit_message_text("🗑️ Выберите товар для удаления:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_PRODUCT


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not query.data.isdigit():  # ← дополнительная защита
        return SELECT_PRODUCT  # игнорируем «не‑число»

    pid = int(query.data)

    session = Session()
    product = session.get(Product, pid)
    name = product.name
    session.delete(product)
    session.commit()
    session.close()

    await query.edit_message_text(f"✅ Товар '{name}' удалён.")

    # Предложение следующего действия
    keyboard = [
        [InlineKeyboardButton("🧹 Удалить другой товар", callback_data="delete_product")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ]
    await query.message.reply_text("Что дальше?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END


def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_product_start, pattern="^delete_product$")],
        states={
            # принимаем только цифры
            SELECT_PRODUCT: [CallbackQueryHandler(confirm_delete, pattern=r"^\d+$")],
        },
        fallbacks=[],
    )
