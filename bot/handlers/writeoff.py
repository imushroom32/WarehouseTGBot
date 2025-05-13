# bot/handlers/writeoff.py
"""
Списание остатков.
• Сотрудник списывает свои товары.
• Менеджер выбирает сотрудника → товар → qty.
После списания сотрудника менеджеру приходит уведомление.

В модуле учтены недавние правки:
  • защита от BadRequest «Message is not modified»;
  • очистка context.user_data при каждой новой операции;
  • предотвращение DetachedInstanceError (данные берём до закрытия сессии);
  • ConversationHandler per_message=True + allow_reentry=True;
  • fallback — возврат к writeoff_start при повторном нажатии на кнопку.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from sqlalchemy.orm import joinedload

from bot.config import MANAGER_TELEGRAM_IDS
from bot.db import Session
from bot.keyboards import home_kb
from bot.models import User, Product, Stock, Log

# ── состояния ────────────────────────────────────────────────────────────────
CHOOSE_EMPLOYEE, CHOOSE_PRODUCT, ENTER_QTY, ENTER_REASON = range(4)

# ─────────────────────────────────────────────────────────────────────────────
async def writeoff_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Точка входа: определяем, чьи остатки будем списывать."""
    try:
        q = update.callback_query
        await q.answer()
        ctx.user_data.clear()

        session = Session()
        current = session.query(User).filter_by(telegram_id=str(q.from_user.id)).one()
        uid = current.id

        # ── сотрудник списывает свои товары сразу ────────────────────────────
        if current.role == "employee":
            ctx.user_data["target_uid"] = uid
            session.close()
            return await _show_products(q, ctx)

        # ── менеджер выбирает источник списания ──────────────────────────────
        employees = (
            session.query(User)
            .join(Stock)
            .filter(User.role == "employee", Stock.quantity > 0)
            .group_by(User.id)
            .order_by(User.full_name)
            .all()
        )
        has_unassigned = session.query(Stock).filter(
            Stock.user_id.is_(None), Stock.quantity > 0
        ).count() > 0
        session.close()

        if not employees and not has_unassigned:
            await q.edit_message_text("❗ Нет остатков для списания.", reply_markup=home_kb())
            return ConversationHandler.END

        kb = [[InlineKeyboardButton(e.full_name, callback_data=str(e.id))] for e in employees]
        if has_unassigned:
            kb.append([InlineKeyboardButton("📦 Склад (без ответственного)", callback_data="unassigned")])

        try:
            await q.edit_message_text(
                "👤 Выберите источник списания:", reply_markup=InlineKeyboardMarkup(kb)
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return CHOOSE_EMPLOYEE

    except Exception as e:
        print("‼️ ОШИБКА В writeoff_start:", e)
        await update.effective_chat.send_message("❌ Ошибка при выборе источника.", reply_markup=home_kb())
        return ConversationHandler.END

# ─────────────────────────────────────────────────────────────────────────────
async def select_employee(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        q = update.callback_query
        await q.answer()

        ctx.user_data["target_uid"] = None if q.data == "unassigned" else int(q.data)
        return await _show_products(q, ctx)

    except Exception as e:
        print("‼️ ОШИБКА В select_employee:", e)
        await update.effective_chat.send_message("❌ Ошибка при выборе сотрудника.", reply_markup=home_kb())
        return ConversationHandler.END

# ─────────────────────────────────────────────────────────────────────────────
async def _show_products(query, ctx) -> int:
    """Показываем товары, доступные к списанию у выбранного источника."""
    try:
        uid = ctx.user_data["target_uid"]
        session = Session()
        stocks = (
            session.query(Stock)
            .options(joinedload(Stock.product))
            .join(Product, Stock.product_id == Product.id)
            .filter((Stock.user_id == uid) if uid is not None else Stock.user_id.is_(None), Stock.quantity > 0)
            .order_by(Product.name)
            .all()
        )

        if not stocks:
            session.close()
            await query.edit_message_text("❗ Нет остатков для списания.", reply_markup=home_kb())
            return ConversationHandler.END

        kb = [[InlineKeyboardButton(f"{s.product.name}: {s.quantity} шт.", callback_data=str(s.id))] for s in stocks]
        session.close()

        try:
            await query.edit_message_text(
                "📦 Выберите товар:", reply_markup=InlineKeyboardMarkup(kb + list(home_kb().inline_keyboard))
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return CHOOSE_PRODUCT

    except Exception as e:
        print("‼️ ОШИБКА В _show_products:", e)
        await query.message.reply_text("❌ Ошибка при загрузке товаров.", reply_markup=home_kb())
        return ConversationHandler.END

# ─────────────────────────────────────────────────────────────────────────────
async def select_product(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        q = update.callback_query
        await q.answer()

        stock_id = int(q.data)
        ctx.user_data["stock_id"] = stock_id

        session = Session()
        stock = session.query(Stock).get(stock_id)
        ctx.user_data["available_qty"] = stock.quantity
        session.close()

        await q.edit_message_text(f"🔢 Введите количество (доступно: {stock.quantity} шт.):")
        return ENTER_QTY

    except Exception as e:
        print("‼️ ОШИБКА В select_product:", e)
        await update.effective_chat.send_message("❌ Ошибка при выборе товара.", reply_markup=home_kb())
        return ConversationHandler.END

# ─────────────────────────────────────────────────────────────────────────────
async def enter_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        qty = int(update.message.text.strip())
        if qty <= 0 or qty > ctx.user_data["available_qty"]:
            raise ValueError
        ctx.user_data["writeoff_qty"] = qty
        await update.message.reply_text("📝 Укажите причину списания:")
        return ENTER_REASON

    except Exception:
        await update.message.reply_text(
            f"❗ Введите число от 1 до {ctx.user_data.get('available_qty', '?')}"
        )
        return ENTER_QTY

# ─────────────────────────────────────────────────────────────────────────────
async def enter_reason(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        reason = update.message.text
        qty = ctx.user_data["writeoff_qty"]
        stock_id = ctx.user_data["stock_id"]

        session = Session()
        stock = session.query(Stock).get(stock_id)
        product_name = stock.product.name  # берём до закрытия сессии
        user_fullname = stock.user.full_name if stock.user else "Склад"

        stock.quantity -= qty
        if stock.quantity == 0:
            session.delete(stock)

        session.add(Log(
            action="writeoff",
            user_id=str(update.effective_user.id),
            info=f"Списано {qty} шт. {product_name} ({user_fullname}). Причина: {reason}"
        ))
        session.commit()
        session.close()

        await update.message.reply_text(f"✅ Списано {qty} шт. ({product_name}).", reply_markup=home_kb())

        # уведомляем менеджеров (если есть)
        for mgr_id in MANAGER_TELEGRAM_IDS:
            try:
                await update.get_bot().send_message(
                    mgr_id,
                    f"🔔 <b>{user_fullname}</b> списал {qty} шт. <i>{product_name}</i>.\nПричина: {reason}",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        return ConversationHandler.END

    except Exception as e:
        print("‼️ ОШИБКА В enter_reason:", e)
        await update.effective_chat.send_message("❌ Ошибка при списании.", reply_markup=home_kb())
        return ConversationHandler.END

# ─────────────────────────────────────────────────────────────────────────────

def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(writeoff_start, pattern="^write_off$")],
        states={
            CHOOSE_EMPLOYEE: [CallbackQueryHandler(select_employee, pattern=r"^\d+$|^unassigned$")],
            CHOOSE_PRODUCT:  [CallbackQueryHandler(select_product,  pattern=r"^\d+$")],
            ENTER_QTY:       [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_qty)],
            ENTER_REASON:    [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_reason)],
        },
        fallbacks=[CallbackQueryHandler(writeoff_start, pattern="^write_off$")],
        per_message=True,
        allow_reentry=True,
    )
