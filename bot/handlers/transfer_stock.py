# bot/handlers/transfer_stock.py
"""
Менеджер передаёт свободные складские остатки (user_id = None) конкретному сотруднику.
"""

from sqlalchemy import func
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.db import Session
from bot.keyboards import home_kb
from bot.models import User, Product, Stock

# ── состояния ────────────────────────────────────────────────────────────────
SELECT_PRODUCT, SELECT_EMPLOYEE, ENTER_QTY = range(3)


# ── Шаг 1. выбор товара с незанятыми остатками ──────────────────────────────
async def transfer_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query;
    await q.answer()

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
        await q.edit_message_text("❗ Нет свободных остатков для передачи.", reply_markup=home_kb())
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(p.name, callback_data=str(p.id))] for p in products]
    await q.edit_message_text("📦 Выберите товар для передачи:", reply_markup=InlineKeyboardMarkup(kb))
    return SELECT_PRODUCT


# ── Шаг 2. выбор сотрудника ─────────────────────────────────────────────────
async def select_product(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query;
    await q.answer()
    pid = int(q.data)
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
        await q.edit_message_text("❗ Нет зарегистрированных сотрудников.", reply_markup=home_kb())
        return ConversationHandler.END

    ctx.user_data["available_qty"] = total_free
    kb = [[InlineKeyboardButton(e.full_name, callback_data=str(e.id))] for e in employees]
    await q.edit_message_text(
        f"👥 Свободно {total_free} шт. Выберите сотрудника:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return SELECT_EMPLOYEE


# ── Шаг 3. ввод количества ──────────────────────────────────────────────────
async def select_employee(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query;
    await q.answer()
    ctx.user_data["employee_id"] = int(q.data)
    available = ctx.user_data["available_qty"]

    await q.edit_message_text(f"🔢 Введите количество (доступно: {available} шт.):")
    return ENTER_QTY


async def enter_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
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

    # ── транзакция ────────────────────────────────────────────────────────────
    session = Session()

    # 1. добавляем/увеличиваем запись сотрудника
    rec = session.query(Stock).filter_by(product_id=pid, user_id=uid).first()
    if rec:
        rec.quantity += qty
    else:
        rec = Stock(product_id=pid, user_id=uid, quantity=qty)
        session.add(rec)

    # 2. вычитаем из «ничейных» остатков
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

    session.commit()
    session.close()

    await update.message.reply_text("✅ Передача выполнена.", reply_markup=home_kb())
    return ConversationHandler.END


# ── Конструктор хендлера ─────────────────────────────────────────────────────
def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(transfer_start, pattern="^transfer_stock$")],
        states={
            SELECT_PRODUCT: [CallbackQueryHandler(select_product, pattern=r"^\d+$")],
            SELECT_EMPLOYEE: [CallbackQueryHandler(select_employee, pattern=r"^\d+$")],
            ENTER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_qty)],
        },
        fallbacks=[],
    )
