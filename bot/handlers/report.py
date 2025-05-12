from telegram import Update
from telegram.ext import CallbackQueryHandler, ConversationHandler, ContextTypes, MessageHandler, filters

from bot.db import Session
from bot.models import Log
from bot.keyboards import home_kb

ASK_START, ASK_END = range(2)

async def start_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("📅 Введите дату начала (в формате ГГГГ-ММ-ДД):")
    return ASK_START

async def ask_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["report_start"] = update.message.text.strip()
    await update.message.reply_text("📅 Теперь введите дату конца (в формате ГГГГ-ММ-ДД):")
    return ASK_END

async def ask_end(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    start = ctx.user_data["report_start"]
    end = update.message.text.strip()

    session = Session()
    rows = session.query(Log).filter(Log.timestamp.between(start, end)).order_by(Log.timestamp).all()
    session.close()

    if not rows:
        await update.message.reply_text("❗ За указанный период действий не найдено.", reply_markup=home_kb())
        return ConversationHandler.END

    out = ["📄 <b>Отчёт</b>\n"]
    for log in rows:
        out.append(f"🕒 <i>{log.timestamp.strftime('%Y-%m-%d %H:%M')}</i>\n👤 <code>{log.user_id}</code>\n🔧 {log.action}\n📝 {log.info}\n")

    await update.message.reply_text("\n".join(out), parse_mode="HTML", reply_markup=home_kb())
    return ConversationHandler.END

def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_report, pattern="^report$")],
        states={
            ASK_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_start)],
            ASK_END:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_end)],
        },
        fallbacks=[],
    )
