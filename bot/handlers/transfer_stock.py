# bot/handlers/transfer_stock.py
"""
Передача остатков сотруднику.
"""

from sqlalchemy.orm import joinedload
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from bot.db import Session
from bot.keyboards import home_kb
from bot.models import Product, Stock, User, Log

SELECT_PRODUCT, SELECT_EMPLOYEE, ENTER_QTY = range(3)


async def transfer_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        q = update.callback_query
        await q.answer()

        session = Session()
        stock_product_ids = (
            session.query(Stock.product_id)
            .filter(Stock.user_id == None, Stock.quantity > 0)
            .distinct()
            .all()
        )
        product_ids = [pid for (pid,) in stock_product_ids]

        if not product_ids:
            session.close()
            await q.edit_message_text("❗ Нет свободных остатков для передачи.", reply_markup=home_kb())
            return ConversationHandler.END

        products = (
            session.query(Product)
            .filter(Product.id.in_(product_ids))
            .order_by(Product.name)
            .all()
        )
        session.close()

        kb = [[InlineKeyboardButton(p.name, callback_data=str(p.id))] for p in products]
        await q.edit_message_text(
            "📦 Выберите товар для передачи:", reply_markup=InlineKeyboardMarkup(kb + list(home_kb().inline_keyboard))
        )
        return SELECT_PRODUCT

    except Exception as e:
        print("‼️ ОШИБКА В transfer_start:", e)
        await update.effective_chat.send_message("❌ Ошибка при запуске передачи.", reply_markup=home_kb())
        return ConversationHandler.END


async def select_product(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        q = update.callback_query
        await q.answer()

        pid = int(q.data)
        ctx.user_data["product_id"] = pid

        session = Session()
        product = session.get(Product, pid)
        ctx.user_data["product_name"] = product.name
        users = session.query(User).filter_by(role="employee").order_by(User.full_name).all()
        session.close()

        if not users:
            await q.edit_message_text("❗ Нет сотрудников для передачи.", reply_markup=home_kb())
            return ConversationHandler.END

        kb = [[InlineKeyboardButton(u.full_name, callback_data=str(u.id))] for u in users]
        await q.edit_message_text(
            f"👤 Кому передать " + product.name + "?",
            reply_markup=InlineKeyboardMarkup(kb + list(home_kb().inline_keyboard))
        )
        return SELECT_EMPLOYEE

    except Exception as e:
        print("‼️ ОШИБКА В select_product:", e)
        await update.effective_chat.send_message("❌ Ошибка при выборе товара.", reply_markup=home_kb())
        return ConversationHandler.END


async def select_employee(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        q = update.callback_query
        await q.answer()

        ctx.user_data["employee_id"] = int(q.data)

        pid = ctx.user_data["product_id"]

        session = Session()
        available = (
            session.query(Stock)
            .filter_by(product_id=pid, user_id=None)
            .with_entities(Stock.quantity)
            .all()
        )
        total = sum(qty for (qty,) in available)
        session.close()

        if total == 0:
            await q.edit_message_text("❗ Нет доступного количества для передачи.", reply_markup=home_kb())
            return ConversationHandler.END

        ctx.user_data["available_qty"] = total

        await q.edit_message_text(f"🔢 Сколько передать? Доступно: {total} шт.")
        return ENTER_QTY

    except Exception as e:
        print("‼️ ОШИБКА В select_employee:", e)
        await update.effective_chat.send_message("❌ Ошибка при выборе сотрудника.", reply_markup=home_kb())
        return ConversationHandler.END


async def enter_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        qty = int(update.message.text.strip())
        if qty <= 0 or qty > ctx.user_data["available_qty"]:
            raise ValueError
    except ValueError:
        await update.message.reply_text(f"❗ Введите число от 1 до {ctx.user_data['available_qty']}")
        return ENTER_QTY

    pid = ctx.user_data["product_id"]
    uid = ctx.user_data["employee_id"]
    qty_requested = qty

    session = Session()
    product = session.get(Product, pid)
    recipient = session.get(User, uid)

    # 1. Добавим остатки сотруднику
    stock = session.query(Stock).filter_by(product_id=pid, user_id=uid).first()
    if stock:
        stock.quantity += qty
    else:
        stock = Stock(product_id=pid, user_id=uid, quantity=qty)
        session.add(stock)

    # 2. Уменьшаем остатки склада
    remaining = qty
    free_stocks = (
        session.query(Stock)
        .filter_by(product_id=pid, user_id=None)
        .order_by(Stock.id)
        .all()
    )
    for s in free_stocks:
        if remaining <= 0:
            break
        if s.quantity > remaining:
            s.quantity -= remaining
            remaining = 0
        else:
            remaining -= s.quantity
            session.delete(s)

    session.add(Log(
        action="transfer_stock",
        user_id=str(update.effective_user.id),
        info=f"Передано {qty_requested} шт. {product.name} сотруднику {recipient.full_name}"
    ))
    session.commit()
    session.close()

    await update.message.reply_text("✅ Передача выполнена.", reply_markup=home_kb())
    return ConversationHandler.END


def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(transfer_start, pattern="^transfer_stock$")],
        states={
            SELECT_PRODUCT: [CallbackQueryHandler(select_product, pattern=r"^\d+$")],
            SELECT_EMPLOYEE: [CallbackQueryHandler(select_employee, pattern=r"^\d+$")],
            ENTER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_qty)],
        },
        fallbacks=[],
        per_message=True  # ← нужно True, иначе одни и те же кнопки игнорируются
    )