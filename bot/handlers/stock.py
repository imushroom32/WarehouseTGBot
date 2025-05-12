"""
Хендлер для пополнения остатков товара.
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
from bot.models import Product, Stock, Log

# состояния разговора
SELECT_PRODUCT, ENTER_QTY = range(2)


async def add_stock_start(
        update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Шаг 1: Предлагает выбрать товар для пополнения.
    """
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
        "➕ Выберите товар для пополнения:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_PRODUCT


async def select_product(
        update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Шаг 2: Сохраняет выбранный товар и запрашивает количество.
    """
    query = update.callback_query
    await query.answer()

    if not query.data.isdigit():  # ← защита
        # можно просто игнорировать или сказать пользователю
        return SELECT_PRODUCT

    pid = int(query.data)
    context.user_data["pid"] = pid

    await query.edit_message_text("➕ Введите количество для пополнения:")
    return ENTER_QTY


async def enter_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        if not update.message:
            await update.effective_chat.send_message("❗ Не удалось прочитать сообщение. Попробуйте ещё раз.")
            return ConversationHandler.END

        text = update.message.text.strip()
        try:
            qty = int(text)
            if qty <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❗ Введите целое положительное число!")
            return ConversationHandler.END

        pid = ctx.user_data["pid"]
        session = Session()

        stock = session.query(Stock).filter_by(product_id=pid, user_id=None).first()
        if stock:
            stock.quantity += qty
        else:
            stock = Stock(product_id=pid, quantity=qty)
            session.add(stock)

        product = session.get(Product, pid)

        # логируем
        log = Log(
            action="add_stock",
            user_id=str(update.effective_user.id),
            info=f"Пополнение: {product.name} +{qty} шт. Итого: {stock.quantity} шт."
        )
        session.add(log)

        session.commit()
        session.close()

        if update.message:
            await update.message.reply_text("✅ Пополнение выполнено.", reply_markup=home_kb())
        else:
            await update.effective_chat.send_message("✅ Пополнение выполнено.", reply_markup=home_kb())

        return ConversationHandler.END

    except Exception as e:
        print("‼️ ОШИБКА В enter_qty (stock.py):", e)
        return ConversationHandler.END


def get_handler() -> ConversationHandler:
    """
    Возвращает ConversationHandler для пополнения остатков.
    """
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(add_stock_start, pattern="^add_stock$")],
        states={
            # принимайте только callback_data из цифр
            SELECT_PRODUCT: [CallbackQueryHandler(select_product, pattern=r"^\d+$")],
            ENTER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_qty)],
        },
        fallbacks=[]
    )
