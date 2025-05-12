# bot/handlers/stock_list.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes
from sqlalchemy import func
from bot.db import Session
from bot.keyboards import home_kb
from bot.models import User, Product, Stock

EMP, PROD = "show_stock_emp", "show_stock_prod"

async def show_stock(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        await query.answer()
        data = query.data

        session = Session()
        cur_user = session.query(User).filter_by(
            telegram_id=str(query.from_user.id)
        ).one()
        role = cur_user.role

        if role == "employee":
            rows = (
                session.query(Product.name, func.sum(Stock.quantity))
                .join(Stock)
                .filter(Stock.user_id == cur_user.id)
                .group_by(Product.name)
                .order_by(Product.name)
                .all()
            )
            session.close()

            if not rows:
                await query.edit_message_text("📦 У вас нет остатков.", reply_markup=home_kb())
                return

            text = ["📦 <b>Мои остатки</b>"]
            text += [f"• {p}: <code>{q} шт.</code>" for p, q in rows]
            await query.edit_message_text("\n".join(text), parse_mode="HTML", reply_markup=home_kb())
            return

        if data == "show_stock":
            kb = [
                [InlineKeyboardButton("👤 По сотрудникам", callback_data=EMP)],
                [InlineKeyboardButton("📦 По товарам",    callback_data=PROD)],
                [InlineKeyboardButton("🏠 Главное меню",  callback_data="main_menu")],
            ]
            await query.edit_message_text(
                "Как представить остатки?", reply_markup=InlineKeyboardMarkup(kb)
            )
            session.close()
            return

        if data == EMP:
            rows = (
                session.query(User.full_name, Product.name, func.sum(Stock.quantity))
                .select_from(Stock)
                .join(User,    User.id == Stock.user_id)
                .join(Product, Product.id == Stock.product_id)
                .group_by(User.full_name, Product.name)
                .order_by(User.full_name, Product.name)
                .all()
            )
            session.close()

            if not rows:
                await query.edit_message_text("📦 Нет остатков назначенных на сотрудников.", reply_markup=home_kb())
                return

            out, cur_user = ["📊 <b>Остатки по сотрудникам</b>"], None
            for uname, prod, qty in rows:
                if uname != cur_user:
                    out.append(f"\n<u>{uname}</u>:")
                    cur_user = uname
                out.append(f" • {prod} <code>{qty} шт.</code>")
            await query.edit_message_text("\n".join(out), parse_mode="HTML", reply_markup=home_kb())
            return

        if data == PROD:
            rows = (
                session.query(
                    Product.name,
                    User.full_name,
                    func.sum(Stock.quantity)
                )
                .select_from(Stock)
                .join(Product, Stock.product_id == Product.id)
                .outerjoin(User,   User.id == Stock.user_id)
                .group_by(Product.id, Stock.user_id, User.full_name)
                .order_by(Product.name, User.full_name.nullsfirst())
                .all()
            )
            session.close()

            if not rows:
                await query.edit_message_text("📦 Нет остатков без ответственных на складе.", reply_markup=home_kb())
                return

            out, cur_prod = ["📊 <b>Остатки по товарам</b>"], None
            for prod, uname, qty in rows:
                if prod != cur_prod:
                    out.append(f"\n<u>{prod}</u>:")
                    cur_prod = prod
                holder = uname or "Не назначен"
                out.append(f" • {holder}: <code>{qty} шт.</code>")
            await query.edit_message_text("\n".join(out), parse_mode="HTML", reply_markup=home_kb())
            return

    except Exception as e:
        print("‼️ ОШИБКА В show_stock:", e)
        await update.effective_chat.send_message("❌ Ошибка при получении остатков.", reply_markup=home_kb())


# ── handler registration ────────────────────────────────────────────────────
def get_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(show_stock, pattern=r"^show_stock.*$")