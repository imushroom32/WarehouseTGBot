from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler, ConversationHandler, MessageHandler,
    ContextTypes, filters
)

from bot.db import Session
from bot.models import Log
from bot.keyboards import home_kb

CHOOSE_PERIOD, ASK_DAYS = range(2)


def _build_period_kb():
    kb = [
        [InlineKeyboardButton("🗓 За неделю", callback_data="week"),
         InlineKeyboardButton("📅 За месяц", callback_data="month")],
        [InlineKeyboardButton("⌨ Указать кол-во дней", callback_data="manual")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(kb)


async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("📄 Выберите период для отчёта:", reply_markup=_build_period_kb())
        return CHOOSE_PERIOD
    except Exception as e:
        print("‼️ ОШИБКА В start_report:", e)
        await update.effective_chat.send_message("❌ Ошибка при открытии отчёта.", reply_markup=home_kb())
        return ConversationHandler.END


async def choose_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        await update.callback_query.answer()
        choice = update.callback_query.data
        now = datetime.now()

        if choice == "week":
            start = now - timedelta(days=7)
            return await _generate_and_send_report(update, context, start, now)

        if choice == "month":
            start = now - timedelta(days=30)
            return await _generate_and_send_report(update, context, start, now)

        if choice == "manual":
            await update.callback_query.edit_message_text("⌨ Введите количество дней в прошлое (1-365):")
            return ASK_DAYS

        return ConversationHandler.END

    except Exception as e:
        print("‼️ ОШИБКА В choose_period:", e)
        await update.effective_chat.send_message("❌ Ошибка при выборе периода.", reply_markup=home_kb())
        return ConversationHandler.END


async def ask_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        days = int(update.message.text.strip())
        if days <= 0 or days > 365:
            raise ValueError
        now = datetime.now()
        start = now - timedelta(days=days)
        return await _generate_and_send_report(update, context, start, now)

    except ValueError:
        await update.message.reply_text("❌ Введите целое число от 1 до 365.")
        return ConversationHandler.END
    except Exception as e:
        print("‼️ ОШИБКА В ask_days:", e)
        await update.effective_chat.send_message("❌ Ошибка при вводе периода.", reply_markup=home_kb())
        return ConversationHandler.END


async def _generate_and_send_report(update: Update, context: ContextTypes.DEFAULT_TYPE, start: datetime,
                                    end: datetime) -> int:
    try:
        session = Session()
        rows = session.query(Log).filter(Log.timestamp.between(start, end)).order_by(Log.timestamp).all()
        session.close()

        if not rows:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="📄 За указанный период действий не найдено.",
                reply_markup=home_kb()
            )
            return ConversationHandler.END

        # Формируем таблицу в моноширинном формате
        header = f"{'Время':<17} | {'Действие':<12} | {'Пользователь':<10} | Детали"
        line = "-" * 70
        out = ["<pre>" + header, line]

        for log in rows:
            out.append(
                f"{log.timestamp.strftime('%Y-%m-%d %H:%M')} | {log.action:<12} | {log.user_id:<10} | {log.info}")

        out.append("</pre>")
        chunks = ["\n".join(out[i:i + 40]) for i in range(0, len(out), 40)]
        for chunk in chunks:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=chunk,
                parse_mode="HTML"
            )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Новый отчёт", callback_data="report")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        ])
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Что дальше?", reply_markup=keyboard)

        return ConversationHandler.END

    except Exception as e:
        print("‼️ ОШИБКА В _generate_and_send_report:", e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Ошибка при формировании отчёта.",
            reply_markup=home_kb()
        )
        return ConversationHandler.END


def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_report, pattern="^report$")],
        states={
            CHOOSE_PERIOD: [CallbackQueryHandler(choose_period, pattern="^(week|month|manual)$")],
            ASK_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_days)],
        },
        fallbacks=[]
    )