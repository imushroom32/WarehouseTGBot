from telegram import InlineKeyboardButton, InlineKeyboardMarkup

_MANAGER = [
    [InlineKeyboardButton("🆕 Добавить товар", callback_data="add_product"),
     InlineKeyboardButton("🗑️ Удалить товар", callback_data="delete_product")],
    [InlineKeyboardButton("➕ Пополнить", callback_data="add_stock"),
     InlineKeyboardButton("📦 Передать сотруднику", callback_data="transfer_stock")],
    [InlineKeyboardButton("📊 Все остатки", callback_data="show_stock")],
    [InlineKeyboardButton("🗑️ Списать у сотрудника", callback_data="write_off")],
]

_EMPLOYEE = [
    [InlineKeyboardButton("📦 Мои остатки", callback_data="show_stock")],
    [InlineKeyboardButton("🗑️ Списать",     callback_data="write_off")],
]


def main_menu_markup(role: str) -> InlineKeyboardMarkup:
    btns = _MANAGER if role == "manager" else _EMPLOYEE
    btns = btns + [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
    return InlineKeyboardMarkup(btns)

def home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu") ]
    ])