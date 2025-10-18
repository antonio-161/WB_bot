from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_inline_kb() -> InlineKeyboardMarkup:
    """Главное меню пользователя через InlineKeyboard."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить товар",
                    callback_data="add_product"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📦 Мои товары",
                    callback_data="list_products"
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить товар",
                    callback_data="remove_product"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💳 Скидка кошелька",
                    callback_data="set_discount"
                ),
                InlineKeyboardButton(
                    text="📍 Мой ПВЗ",
                    callback_data="show_pvz"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Настройки",
                    callback_data="settings"
                ),
                InlineKeyboardButton(
                    text="💰 Мой тариф",
                    callback_data="my_plan"
                ),
            ],
        ]
    )
    return kb


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


def products_inline(products: list[dict]) -> InlineKeyboardMarkup:
    """Клавиатура с отслеживаемыми товарами."""
    inline_rows = []

    for p in products:
        name = p.get("name", f"Товар {p['nm_id']}")
        # Обрезаем слишком длинные названия
        display_name = name[:40] + "..." if len(name) > 40 else name

        inline_rows.append([
            InlineKeyboardButton(
                text=f"🛍 {display_name}",
                url=f"https://www.wildberries.ru/catalog/{p['nm_id']}/detail.aspx"
            )
        ])

    # Кнопки действий
    inline_rows.append([
        InlineKeyboardButton(
            text="➕ Добавить ещё",
            callback_data="add_product"
        ),
    ])
    inline_rows.append([
        InlineKeyboardButton(
            text="« Назад",
            callback_data="back_to_menu"
        ),
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=inline_rows)
    return kb


def confirm_remove_kb(nm_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления товара."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=f"confirm_remove_{nm_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_remove"
                ),
            ]
        ]
    )
    return kb


def reset_pvz_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Изменить ПВЗ",
                    callback_data="set_pvz"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="back_to_menu"
                ),
            ],
        ]
    )
    return kb


def sizes_inline_kb(nm: int, sizes: list[dict]) -> InlineKeyboardMarkup:
    """
    Генерация inline-клавиатуры с размерами товара.

    sizes: [{'name': 'M', 'origName': 'M'}, ...]
    """
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=s.get("name"), callback_data=f"select_size:{nm}:{s.get('name')}")]
            for s in sizes
        ]
    )
    return kb
