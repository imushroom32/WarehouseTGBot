# bot/handlers/join_approve.py
from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes
from bot.db import Session
from bot.models import JoinRequest, User

async def handle_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    action, tg_id = q.data.split(":", 1)

    session = Session()
    req = session.query(JoinRequest).filter_by(telegram_id=tg_id).one_or_none()

    if not req:
        await q.edit_message_text("⛔ Заявка уже обработана.")
        session.close()
        return

    if action == "join_ok":
        session.add(User(telegram_id=tg_id, full_name=req.full_name, role="employee"))
        txt_admin = "✅ Доступ выдан."
        txt_user  = "🎉 Доступ к боту открыт! Введите /start."
    else:
        txt_admin = "❌ Заявка отклонена."
        txt_user  = "😔 Администратор отклонил заявку."

    session.delete(req)
    session.commit()
    session.close()

    await q.edit_message_text(txt_admin)
    try:
        await ctx.bot.send_message(tg_id, txt_user)
    except Exception:
        pass

def get_handler():
    return CallbackQueryHandler(handle_join, pattern=r"^join_(ok|no):")
