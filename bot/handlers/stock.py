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
from bot.models import Product, Stock, Log
from datetime import datetime

SELECT_PRODUCT, ENTER_QTY = range(2)


async def add_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()
        session = Session()
        products = session.query(Product).order_by(Product.name).all()
        session.close()

        if not products:
            await query.edit_message_text("❗ Нет товаров. Сперва добавьте новый товар.", reply_markup=home_kb())
            return ConversationHandler.END

        keyboard = [[InlineKeyboardButton(p.name, callback_data=str(p.id))] for p in products]
        await query.edit_message_text(
            "➕ Выберите товар для пополнения:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECT_PRODUCT

    except Exception as e:
        print("‼️ ОШИБКА В add_stock_start:", e)
        await update.effective_chat.send_message("❌ Ошибка при открытии меню.", reply_markup=home_kb())
        return ConversationHandler.END


async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()

        if not query.data.isdigit():
            return SELECT_PRODUCT

        pid = int(query.data)
        context.user_data["pid"] = pid

        await query.edit_message_text("➕ Введите количество для пополнения:")
        return ENTER_QTY

    except Exception as e:
        print("‼️ ОШИБКА В select_product:", e)
        await update.effective_chat.send_message("❌ Ошибка при выборе товара.", reply_markup=home_kb())
        return ConversationHandler.END


async def enter_qty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        if not update.message:
            await update.effective_chat.send_message("❗ Не удалось прочитать сообщение. Попробуйте ещё раз.")
            return ENTER_QTY

        text = update.message.text.strip()
        try:
            qty = int(text)
            if qty <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❗ Введите целое положительное число!")
            return ENTER_QTY

        pid = context.user_data['pid']
        session = Session()
        stock = session.query(Stock).filter_by(product_id=pid, user_id=None).first()

        if stock:
            stock.quantity += qty
            final_qty = stock.quantity
        else:
            stock = Stock(product_id=pid, quantity=qty)
            session.add(stock)
            final_qty = qty

        product = session.get(Product, pid)
        product_name = product.name

        log = Log(
            action="add_stock",
            user_id=str(update.effective_user.id),
            info=f"Пополнено: {product_name} +{qty} шт. Итого: {final_qty} шт."
        )
        session.add(log)

        session.commit()
        session.close()

        try:
            await update.message.reply_text(
                f"✅ {product_name}: +{qty}шт. Итого: {final_qty}шт.",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("➕ Пополнить ещё", callback_data="add_stock"),
                        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                    ]
                ])
            )
        except Exception as e:
            print("‼️ Ошибка при отправке сообщения пользователю:", e)

        return ConversationHandler.END

    except Exception as e:
        print("‼️ ОШИБКА В enter_qty (stock.py):", e)
        return ConversationHandler.END


def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(add_stock_start, pattern="^add_stock$")],
        states={
            SELECT_PRODUCT: [CallbackQueryHandler(select_product, pattern=r"^\d+$")],
            ENTER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_qty)],
        },
        fallbacks=[]
    )
