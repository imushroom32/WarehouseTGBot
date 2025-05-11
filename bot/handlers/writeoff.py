# bot/handlers/writeoff.py
"""
Списание остатков.
• Сотрудник списывает свои товары.
• Менеджер выбирает сотрудника → товар → qty.
После списания сотрудника менеджеру приходит уведомление.
"""
from sqlalchemy.orm import joinedload
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.config import MANAGER_TELEGRAM_IDS
from bot.db import Session
from bot.keyboards import home_kb
from bot.models import User, Product, Stock

# ── состояния диалога ────────────────────────────────────────────────
CHOOSE_EMPLOYEE, CHOOSE_PRODUCT, ENTER_QTY, ENTER_REASON = range(4)


# ─────────────────────────────────────────────────────────────────────
async def writeoff_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    session = Session()
    current = session.query(User).filter_by(telegram_id=str(q.from_user.id)).one()
    uid = current.id
    role = current.role

    # сотрудник → сразу к списку его товаров
    if role == "employee":
        ctx.user_data["target_uid"] = uid
        session.close()
        return await _show_products(q, ctx)

    # менеджер → показать выбор
    employees = (
        session.query(User)
        .join(Stock)
        .filter(User.role == "employee", Stock.quantity > 0)
        .group_by(User.id)
        .order_by(User.full_name)
        .all()
    )
    has_unassigned = session.query(Stock).filter(Stock.user_id.is_(None), Stock.quantity > 0).count() > 0
    session.close()

    if not employees and not has_unassigned:
        await q.edit_message_text("❗ Нет остатков для списания.")
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(e.full_name, callback_data=str(e.id))] for e in employees]
    if has_unassigned:
        kb.append([InlineKeyboardButton("📦 Склад (без ответственного)", callback_data="unassigned")])

    await q.edit_message_text("👤 Выберите источник списания:", reply_markup=InlineKeyboardMarkup(kb))
    return CHOOSE_EMPLOYEE


# ─────────────────────────────────────────────────────────────────────
async def select_employee(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    if q.data == "unassigned":
        ctx.user_data["target_uid"] = None
    else:
        ctx.user_data["target_uid"] = int(q.data)  # ← вот этого не хватает

    return await _show_products(q, ctx)  # ← обязательно вернуться в поток


# ─────────────────────────────────────────────────────────────────────
async def _show_products(query, ctx) -> int:
    uid = ctx.user_data["target_uid"]

    session = Session()
    stocks = (
        session.query(Stock)
        .options(joinedload(Stock.product))
        .join(Product, Stock.product_id == Product.id)  # ← явный JOIN
        .filter((Stock.user_id == uid) if uid is not None else Stock.user_id.is_(None), Stock.quantity > 0)
        .order_by(Product.name)  # теперь колонка существует
        .all()
    )

    if not stocks:
        session.close()
        await query.edit_message_text("❗ Нет остатков для списания.", reply_markup=home_kb())
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton(f"{s.product.name}: {s.quantity} шт.", callback_data=str(s.id))]
        for s in stocks
    ]
    session.close()  # ← закрываем ПОСЛЕ использования

    full_kb = InlineKeyboardMarkup(kb + list(home_kb().inline_keyboard))
    await query.edit_message_text("📦 Выберите товар:", reply_markup=full_kb)
    return CHOOSE_PRODUCT


# ─────────────────────────────────────────────────────────────────────
async def select_product(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    stock_id = int(q.data)
    ctx.user_data["stock_id"] = stock_id

    session = Session()
    stock = session.query(Stock).get(stock_id)
    session.close()

    ctx.user_data["available_qty"] = stock.quantity
    await q.edit_message_text(f"🔢 Введите количество (доступно: {stock.quantity} шт.):")
    return ENTER_QTY


# ─────────────────────────────────────────────────────────────────────
async def enter_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    try:
        qty = int(text)
        if qty <= 0 or qty > ctx.user_data["available_qty"]:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            f"❗ Введите число от 1 до {ctx.user_data['available_qty']}"
        )
        return ENTER_QTY

    ctx.user_data["writeoff_qty"] = qty
    await update.message.reply_text("📝 Укажите причину списания:")
    return ENTER_REASON


# ─────────────────────────────────────────────────────────────────────
async def enter_reason(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    reason = update.message.text
    qty = ctx.user_data["writeoff_qty"]
    stock_id = ctx.user_data["stock_id"]

    session = Session()
    stock = session.query(Stock).get(stock_id)
    product_name = stock.product.name
    user_fullname = stock.user.full_name if stock.user else "Склад"
    # списываем
    stock.quantity -= qty
    if stock.quantity == 0:
        session.delete(stock)
    session.commit()
    session.close()

    await update.message.reply_text(f"✅ Списано {qty} шт. ({product_name}).", reply_markup=home_kb())

    # ── уведомление менеджеру ─────────────────────────────────────────
    try:
        (await update.get_bot().send_message(
            _id,
            f"🔔 <b>{user_fullname}</b> списал {qty} шт. <i>{product_name}</i>.\nПричина: {reason}",
            parse_mode="HTML",
        ) for _id in MANAGER_TELEGRAM_IDS)
    except Exception:
        # молча игнорируем, если бот у менеджера не запущен
        pass

    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────────
def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(writeoff_start, pattern="^write_off$")],
        states={
            CHOOSE_EMPLOYEE: [CallbackQueryHandler(select_employee, pattern=r"^\d+$|^unassigned$")],
            CHOOSE_PRODUCT: [CallbackQueryHandler(select_product, pattern="^\d+$")],
            ENTER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_qty)],
            ENTER_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_reason)],
        },
        fallbacks=[],
    )
