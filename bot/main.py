from telegram.ext import Application

from bot.config import TELEGRAM_TOKEN
from bot.db import init_db
from bot.handlers.delete_product import get_handler as delete_product_h
from bot.handlers.product import get_handler as product_h
from bot.handlers.start import get_handlers as start_handlers
from bot.handlers.stock import get_handler as stock_add_h
from bot.handlers.stock_list import get_handler as stock_list_h
from bot.handlers.transfer_stock import get_handler as transfer_h
from bot.handlers.writeoff import get_handler as writeoff_h


def main() -> None:
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # /start и кнопки меню
    for h in start_handlers():
        app.add_handler(h)

    # остальные модули
    app.add_handler(product_h())
    app.add_handler(stock_add_h())
    app.add_handler(stock_list_h())
    app.add_handler(writeoff_h())
    app.add_handler(delete_product_h())
    app.add_handler(transfer_h())

    for h in start_handlers():
        app.add_handler(h)

    app.run_polling()


if __name__ == "__main__":
    main()
