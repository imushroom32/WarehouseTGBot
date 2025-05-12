# bot/handlers/transfer_stock.py
"""
Менеджер передаёт свободные складские остатки (user_id = None) конкретному сотруднику.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from sqlalchemy import func
from bot.db import Session
from bot.keyboards import home_kb
from bot.models import Product, Stock, User, Log

SELECT_PRODUCT, SELECT_EMPLOYEE, ENTER_QTY = range(3)


async def transfer_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()
        session = Session()
        products = (
            session.query(Product)
            .join(Stock)
            .filter(Stock.user_id.is_(None), Stock.quantity > 0)
            .group_by(Product.id)
            .order_by(Product.name)
            .all()
        )
        session.close()

        if not products:
            await query.edit_message_text("❗ Нет свободных остатков для передачи.", reply_markup=home_kb())
            return ConversationHandler.END

        kb = [[InlineKeyboardButton(p.name, callback_data=str(p.id))] for p in products]
        await query.edit_message_text("📦 Выберите товар для передачи:", reply_markup=InlineKeyboardMarkup(kb))
        return SELECT_PRODUCT

    except Exception as e:
        print("‼️ ОШИБКА В transfer_start:", e)
        await update.effective_chat.send_message("❌ Ошибка при выборе товара.", reply_markup=home_kb())
        return ConversationHandler.END


async def select_product(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()
        pid = int(query.data)
        ctx.user_data["product_id"] = pid

        session = Session()
        total_free = (
            session.query(func.sum(Stock.quantity))
            .filter(Stock.product_id == pid, Stock.user_id.is_(None))
            .scalar()
        ) or 0

        employees = (
            session.query(User)
            .filter(User.role == "employee")
            .order_by(User.full_name)
            .all()
        )
        session.close()

        if not employees:
            await query.edit_message_text("❗ Нет зарегистрированных сотрудников.", reply_markup=home_kb())
            return ConversationHandler.END

        ctx.user_data["available_qty"] = total_free
        kb = [[InlineKeyboardButton(e.full_name, callback_data=str(e.id))] for e in employees]
        await query.edit_message_text(
            f"👥 Свободно {total_free} шт. Выберите сотрудника:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return SELECT_EMPLOYEE

    except Exception as e:
        print("‼️ ОШИБКА В select_product:", e)
        await update.effective_chat.send_message("❌ Ошибка при выборе сотрудника.", reply_markup=home_kb())
        return ConversationHandler.END


async def select_employee(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()
        ctx.user_data["employee_id"] = int(query.data)
        available = ctx.user_data["available_qty"]

        await query.edit_message_text(f"🔢 Введите количество (доступно: {available} шт.):")
        return ENTER_QTY

    except Exception as e:
        print("‼️ ОШИБКА В select_employee:", e)
        await update.effective_chat.send_message("❌ Ошибка при выборе количества.", reply_markup=home_kb())
        return ConversationHandler.END


async def enter_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
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

        pid = ctx.user_data["product_id"]
        uid = ctx.user_data["employee_id"]
        available = ctx.user_data["available_qty"]

        if qty > available:
            await update.message.reply_text(f"❗ Недостаточно: доступно {available} шт.")
            return ENTER_QTY

        session = Session()

        # передача остатков
        rec = session.query(Stock).filter_by(product_id=pid, user_id=uid).first()
        if rec:
            rec.quantity += qty
        else:
            rec = Stock(product_id=pid, user_id=uid, quantity=qty)
            session.add(rec)

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

        product = session.get(Product, pid)
        recipient = session.get(User, uid)
        log = Log(
            action="transfer_stock",
            user_id=str(update.effective_user.id),
            info=f"Передано {qty} шт. {product.name} сотруднику {recipient.full_name}"
        )
        session.add(log)
        session.commit()
        session.close()

        await update.message.reply_text("✅ Передача выполнена.", reply_markup=home_kb())
        return ConversationHandler.END

    except Exception as e:
        print("‼️ ОШИБКА В enter_qty (transfer_stock):", e)
        await update.effective_chat.send_message("❌ Ошибка при передаче товара.", reply_markup=home_kb())
        return ConversationHandler.END


# ── Хендлер ─────────────────────────────────────────────────────────────────
def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(transfer_start, pattern="^transfer_stock$")],
        states={
            SELECT_PRODUCT: [CallbackQueryHandler(select_product, pattern=r"^\d+$")],
            SELECT_EMPLOYEE: [CallbackQueryHandler(select_employee, pattern=r"^\d+$")],
            ENTER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_qty)],
        },
        fallbacks=[]
    )