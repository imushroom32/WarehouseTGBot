from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

from bot.db import Session
from bot.keyboards import home_kb
from bot.models import Product, Stock, Log

SELECT_PRODUCT = 0


async def delete_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()

        session = Session()
        subquery = session.query(Stock.product_id).distinct()
        products = (
            session.query(Product)
            .filter(Product.id.notin_(subquery))
            .order_by(Product.name)
            .all()
        )
        session.close()

        if not products:
            await query.edit_message_text(
                "❗ Нет товаров, доступных для удаления.",
                reply_markup=home_kb()
            )
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton(p.name, callback_data=str(p.id))] for p in products
        ]
        full_kb = InlineKeyboardMarkup(keyboard + list(home_kb().inline_keyboard))
        await query.edit_message_text(
            "🗑️ Выберите товар для удаления:", reply_markup=full_kb
        )
        return SELECT_PRODUCT

    except Exception as e:
        print("‼️ ОШИБКА В delete_product_start:", e)
        await update.effective_chat.send_message(
            "❌ Ошибка при загрузке товаров для удаления.",
            reply_markup=home_kb()
        )
        return ConversationHandler.END


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()

        if not query.data.isdigit():
            return SELECT_PRODUCT

        pid = int(query.data)

        session = Session()
        product = session.get(Product, pid)
        name = product.name
        session.delete(product)

        log = Log(
            action="delete_product",
            user_id=str(update.effective_user.id),
            info=f"Удалён товар: {name}"
        )
        session.add(log)

        session.commit()
        session.close()

        await query.edit_message_text(f"✅ Товар '{name}' удалён.")

        keyboard = [
            [InlineKeyboardButton("🧹 Удалить другой товар", callback_data="delete_product")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        ]
        await query.message.reply_text("Что дальше?", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    except Exception as e:
        print("‼️ ОШИБКА В confirm_delete:", e)
        await update.effective_chat.send_message(
            "❌ Ошибка при удалении товара.",
            reply_markup=home_kb()
        )
        return ConversationHandler.END


def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_product_start, pattern="^delete_product$")],
        states={
            SELECT_PRODUCT: [CallbackQueryHandler(confirm_delete, pattern=r"^\d+$")],
        },
        fallbacks=[],
    )
