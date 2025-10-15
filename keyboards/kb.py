from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup
)


# 🔹 Главное меню (ReplyKeyboard)
def main_inline_kb() -> InlineKeyboardMarkup:
    """Главное меню пользователя через InlineKeyboard."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить товар", callback_data="add_product"),
                InlineKeyboardButton(text="📦 Мои товары", callback_data="list_products"),
            ],
            [
                InlineKeyboardButton(text="💰 Установить скидку", callback_data="set_discount"),
                InlineKeyboardButton(text="❌ Удалить товар", callback_data="remove_product"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
                InlineKeyboardButton(text="💳 Мой тариф", callback_data="my_plan"),
            ],
        ]
    )
    return kb


# 🔹 Выбор тарифа (InlineKeyboard)
def choose_plan_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора тарифа."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎁 Бесплатный (5 товаров)",
                    callback_data="plan_free",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💼 Базовый (50 товаров)",
                    callback_data="plan_basic",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Продвинутый (250 товаров)",
                    callback_data="plan_pro",
                )
            ],
        ]
    )
    return kb


# 🔹 Список отслеживаемых товаров (InlineKeyboard)
def products_inline(products: list[dict]) -> InlineKeyboardMarkup:
    """Клавиатура с отслеживаемыми товарами."""
    inline_rows = []

    for p in products:
        inline_rows.append([
            InlineKeyboardButton(
                text=f"🛍 {p['nm_id']}",
                callback_data=f"product_{p['nm_id']}"
            )
        ])

    # Добавляем кнопку “Назад” или “Добавить товар”
    inline_rows.append([
        InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_product"),
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=inline_rows)
    return kb


# 🔹 Клавиатура подтверждения удаления
def confirm_remove_kb(nm_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления товара."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Удалить", callback_data=f"confirm_remove_{nm_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data="cancel_remove"
                ),
            ]
        ]
    )
    return kb
