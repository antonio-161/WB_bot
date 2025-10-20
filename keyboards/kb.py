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
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить товар",
                    callback_data="remove_product"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Экспорт в Excel",
                    callback_data="export_excel"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Настройки",
                    callback_data="settings"
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
        display_name = name[:40] + "..." if len(name) > 40 else name

        inline_rows.append([
            InlineKeyboardButton(
                text=f"📊 {display_name}",
                callback_data=f"product_detail:{p['nm_id']}"
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


def product_detail_kb(nm_id: int) -> InlineKeyboardMarkup:
    """Клавиатура детальной информации о товаре."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📈 График цен",
                    callback_data=f"show_graph:{nm_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔔 Настроить уведомления",
                    callback_data=f"notify_settings:{nm_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Переименовать",
                    callback_data=f"rename:{nm_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Открыть на WB",
                    url=f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"rm:{nm_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Назад к списку",
                    callback_data="list_products"
                ),
            ],
        ]
    )
    return kb


def settings_kb() -> InlineKeyboardMarkup:
    """Клавиатура настроек."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Скидка кошелька",
                    callback_data="set_discount"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📍 Мой ПВЗ",
                    callback_data="show_pvz"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 Мой тариф",
                    callback_data="my_plan"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Назад",
                    callback_data="back_to_menu"
                ),
            ],
        ]
    )
    return kb


def notify_mode_kb(nm_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора режима уведомлений."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 По проценту снижения",
                    callback_data=f"notify_percent:{nm_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 По целевой цене",
                    callback_data=f"notify_threshold:{nm_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔕 Отключить (все уведомления)",
                    callback_data=f"notify_all:{nm_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Назад",
                    callback_data=f"product_detail:{nm_id}"
                ),
            ],
        ]
    )
    return kb


def confirm_remove_kb(nm_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления товара."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=f"confirm_remove:{nm_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="list_products"
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
                    callback_data="settings"
                ),
            ],
        ]
    )
    return kb


def sizes_inline_kb(nm: int, sizes: list[dict]) -> InlineKeyboardMarkup:
    """Генерация inline-клавиатуры с размерами товара."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=s.get("name"),
                callback_data=f"select_size:{nm}:{s.get('name')}"
            )]
            for s in sizes
        ]
    )
    return kb


def back_to_settings_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата к настройкам."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Назад к настройкам",
                    callback_data="settings"
                ),
            ],
        ]
    )
    return kb


def back_to_product_kb(nm_id: int) -> InlineKeyboardMarkup:
    """Кнопка возврата к списку товаров."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Назад в карточку товара",
                    callback_data=f"back_to_product:{nm_id}"
                ),
            ],
        ]
    )
    return kb


def upgrade_plan_kb() -> InlineKeyboardMarkup:
    """Клавиатура для улучшения тарифа."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬆️ Улучшить тариф",
                    callback_data="upgrade_plan"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Назад",
                    callback_data="back_to_menu"
                ),
            ],
        ]
    )
    return kb
