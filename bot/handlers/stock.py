# bot/handlers/stock.py
"""
Пополнение остатков товара.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram.error import BadRequest  # ← добавили

from bot.db import Session
from bot.keyboards import home_kb
from bot.models import Product, Stock, Log

# ── состояния ────────────────────────────────────────────────────────────────
SELECT_PRODUCT, ENTER_QTY = range(2)


# ─────────────────────────────────────────────────────────────────────────────
async def add_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Старт: показываем список товаров для пополнения."""
    try:
        query = update.callback_query
        await query.answer()
        context.user_data.clear()

        # список товаров
        session = Session()
        products = session.query(Product).order_by(Product.name).all()
        session.close()

        if not products:
            await query.edit_message_text(
                "❗ Нет товаров. Сперва добавьте новый товар.", reply_markup=home_kb()
            )
            return ConversationHandler.END

        kb = [[InlineKeyboardButton(p.name, callback_data=str(p.id))] for p in products]
        try:
            # пробуем изменить и текст, и клавиатуру
            await query.edit_message_text(
                "➕ Выберите товар для пополнения:",
                reply_markup=InlineKeyboardMarkup(kb + list(home_kb().inline_keyboard)),
            )
        except BadRequest as e:
            # если текст тот же, меняем только клавиатуру – избавляемся от «Message is not modified»
            if "Message is not modified" in str(e):
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(kb + list(home_kb().inline_keyboard))
                )
            else:
                raise

        return SELECT_PRODUCT

    except Exception as e:
        print("‼️ ОШИБКА В add_stock_start:", e)
        await update.effective_chat.send_message(
            "❌ Ошибка при открытии меню.", reply_markup=home_kb()
        )
        return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем ID товара и просим количество."""
    try:
        query = update.callback_query
        await query.answer()

        context.user_data.clear()
        context.user_data["product_id"] = int(query.data)

        await query.edit_message_text("➕ Введите количество для пополнения:")
        return ENTER_QTY

    except Exception as e:
        print("‼️ ОШИБКА В select_product:", e)
        await update.effective_chat.send_message(
            "❌ Ошибка при выборе товара.", reply_markup=home_kb()
        )
        return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
async def enter_qty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Фиксируем пополнение."""
    try:
        text = (update.message.text or "").strip()
        qty = int(text)
        if qty <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await update.message.reply_text("❗ Введите целое положительное число!")
        return ENTER_QTY

    pid = context.user_data["product_id"]

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
    product_name = product.name  # кешируем до закрытия сессии

    session.add(
        Log(
            action="add_stock",
            user_id=str(update.effective_user.id),
            info=f"Пополнено: {product_name} +{qty} шт. Итого: {final_qty} шт.",
        )
    )
    session.commit()
    session.close()

    reply_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Пополнить ещё", callback_data="add_stock"),
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"),
            ]
        ]
    )

    await update.message.reply_text(
        f"✅ {product_name}: +{qty} шт. Итого: {final_qty} шт.", reply_markup=reply_kb
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выход из диалога в главное меню."""
    from bot.handlers.start import start as start_handler  # локальный импорт, чтобы избежать циклов

    # Завершаем диалог и передаём управление хендлеру главного меню
    await start_handler(update, context)
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────────────

def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(add_stock_start, pattern="^add_stock$")],
        states={
            SELECT_PRODUCT: [CallbackQueryHandler(select_product, pattern=r"^\d+$")],
            ENTER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_qty)],
        },
        fallbacks=[CallbackQueryHandler(back_to_menu, pattern="^main_menu$")],
        allow_reentry=True,
    )
