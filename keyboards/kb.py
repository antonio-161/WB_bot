from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Dict, List


def start_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="➕ Добавить товар и начать экономить",
                    callback_data="onboarding_add_first"
                )],
                [InlineKeyboardButton(
                    text="📋 Сначала выбрать тариф",
                    callback_data="show_plans_first"
                )]
            ])
    return kb


def create_smart_menu(
    products_count: int,
    max_links: int,
    plan: str
) -> InlineKeyboardMarkup:
    """Умное меню, адаптирующееся под контекст пользователя."""

    buttons = []

    # Если нет товаров - приоритет на добавление
    if products_count == 0:
        buttons.append([InlineKeyboardButton(
            text="🎯 Добавить первый товар",
            callback_data="add_product"
        )])
    # Если есть товары, но не лимит
    elif products_count < max_links:
        buttons.append([InlineKeyboardButton(
            text="➕ Добавить товар",
            callback_data="add_product"
        )])
        buttons.append([InlineKeyboardButton(
            text="📦 Мои товары",
            callback_data="list_products"
        )])
    # Если лимит достигнут - пушим на апгрейд
    else:
        buttons.append([InlineKeyboardButton(
            text="⚠️ Лимит достигнут - Улучшить тариф",
            callback_data="upsell_limit_reached"
        )])
        buttons.append([InlineKeyboardButton(
            text="📦 Мои товары",
            callback_data="list_products"
        )])

    # Дополнительные действия
    buttons.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")
    ])

    # Для бесплатного тарифа - ненавязчивое напоминание
    if plan == "Бесплатный" and products_count >= 3:
        buttons.append([InlineKeyboardButton(
            text="🚀 Хотите больше возможностей?",
            callback_data="show_upgrade_benefits"
        )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def show_plans_kb() -> InlineKeyboardMarkup:
    """Клавиатура с тарифами."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💼 Смотреть тариф Базовый",
            callback_data="plan_basic"
        )],
        [InlineKeyboardButton(
            text="🚀 Смотреть тариф Продвинутый",
            callback_data="plan_pro"
        )],
        [InlineKeyboardButton(
            text="« Назад",
            callback_data="back_to_menu"
        )]
    ])
    return kb


def upsell_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Улучшить до Базового (199₽/мес)",
            callback_data="plan_basic"
        )],
        [InlineKeyboardButton(
            text="💎 Смотреть все тарифы",
            callback_data="show_plans_first"
        )],
        [InlineKeyboardButton(
            text="🗑 Удалить старый товар",
            callback_data="remove_product"
        )],
        [InlineKeyboardButton(
            text="« Назад",
            callback_data="back_to_menu"
        )]
    ])
    return kb


def onboarding_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="➕ Добавить ещё товар",
                            callback_data="add_product"
                        )],
                        [InlineKeyboardButton(
                            text="📋 Выбрать тариф",
                            callback_data="show_plans_first"
                        )],
                        [InlineKeyboardButton(
                            text="📦 Мои товары",
                            callback_data="list_products"
                        )]
                    ]),
    return kb


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
                    text="📋 Экспорт данных",
                    callback_data="export_menu"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Моя статистика",
                    callback_data="my_stats"
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
            text="➕ Добавить товар",
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
                    text="📋 Вернуться к списку",
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


def export_format_kb() -> InlineKeyboardMarkup:
    """Выбор формата экспорта."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📗 Excel (.xlsx)",
                    callback_data="export_excel"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📄 CSV (.csv)",
                    callback_data="export_csv"
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


def plan_detail_kb(plan_key: str) -> InlineKeyboardMarkup:
    """Клавиатура детального описания тарифа."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Выбрать этот тариф",
                    callback_data=f"confirm_{plan_key}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="« Назад к выбору",
                    callback_data="back_to_plan_choice"
                ),
            ],
        ]
    )
    return kb


def onboarding_discount_kb() -> InlineKeyboardMarkup:
    """Клавиатура для настройки скидки при онбординге."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Установить скидку",
                    callback_data="onboarding_set_discount"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏭ Пропустить",
                    callback_data="onboarding_skip_discount"
                ),
            ],
        ]
    )
    return kb


def onboarding_pvz_kb() -> InlineKeyboardMarkup:
    """Клавиатура для настройки ПВЗ при онбординге."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📍 Установить ПВЗ",
                    callback_data="onboarding_set_pvz"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏭ Пропустить (Москва)",
                    callback_data="onboarding_skip_pvz"
                ),
            ],
        ]
    )
    return kb


def back_to_menu_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="back_to_menu"
            )]
        ]
    )
    return kb


def remove_products_kb(products: List[Dict]) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора товара на удаление.

    Args:
        products: Список словарей с ключами 'nm_id' и 'display_name'

    Returns:
        InlineKeyboardMarkup с кнопками товаров и кнопкой "Назад"
    """
    buttons = []

    for product in products:
        display_name = product['display_name']
        # Обрезаем название для удобства отображения
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."

        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {display_name}",
                callback_data=f"rm:{product['nm_id']}"
            )
        ])

    # Добавляем кнопку "Назад"
    buttons.append([
        InlineKeyboardButton(
            text="« Назад",
            callback_data="back_to_menu"
        )
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    return kb


def products_list_kb(
    products: List[Dict],
    has_filters: bool = False,
    show_export: bool = False,
    show_upgrade: bool = False,
    slots_info: str = ""
) -> InlineKeyboardMarkup:
    """
    Улучшенная клавиатура для списка товаров с поддержкой фильтров.
    
    Args:
        products: Список товаров с nm_id и display_name
        has_filters: Показывать ли кнопки фильтров
        show_export: Показывать ли кнопку экспорта (для Pro)
        show_upgrade: Показывать ли кнопку апгрейда (для Free)
        slots_info: Текст для отображения информации о слотах
    
    Returns:
        InlineKeyboardMarkup
    """
    buttons = []
    
    # Кнопки товаров (показываем первые 10 для удобства)
    for product in products[:10]:
        display_name = product['display_name']
        if len(display_name) > 35:
            display_name = display_name[:32] + "..."
        
        buttons.append([
            InlineKeyboardButton(
                text=f"📊 {display_name}",
                callback_data=f"product_detail:{product['nm_id']}"
            )
        ])
    
    # Если товаров больше 10, добавляем кнопку "Показать все"
    if len(products) > 10:
        buttons.append([
            InlineKeyboardButton(
                text=f"📋 Показать все ({len(products)} товаров)",
                callback_data="show_all_products"
            )
        ])
    
    # Фильтры (для платных тарифов)
    if has_filters:
        buttons.append([
            InlineKeyboardButton(
                text="🔥 Лучшие скидки",
                callback_data="filter_best_deals"
            ),
            InlineKeyboardButton(
                text="📉 Падающие цены",
                callback_data="filter_price_drops"
            )
        ])
    
    # Основные действия
    buttons.append([
        InlineKeyboardButton(
            text="➕ Добавить товар",
            callback_data="add_product"
        ),
        InlineKeyboardButton(
            text="🗑 Удалить товар",
            callback_data="remove_product"
        )
    ])
    
    # Экспорт для Pro
    if show_export:
        buttons.append([
            InlineKeyboardButton(
                text="📋 Экспорт в Excel/CSV",
                callback_data="export_menu"
            )
        ])
    
    # Апгрейд для Free
    if show_upgrade:
        buttons.append([
            InlineKeyboardButton(
                text="🚀 Улучшить тариф (до 50 товаров)",
                callback_data="upsell_from_products_list"
            )
        ])
    
    # Кнопка "Назад"
    buttons.append([
        InlineKeyboardButton(
            text="« Назад",
            callback_data="back_to_menu"
        )
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    return kb


def product_navigation_kb(
    nm_id: int,
    current_index: int,
    total_products: int,
    prev_nm_id: int = None,
    next_nm_id: int = None
) -> InlineKeyboardMarkup:
    """
    Клавиатура для навигации по товарам в карточке.
    
    Args:
        nm_id: Текущий артикул
        current_index: Текущий индекс товара (1-based)
        total_products: Общее количество товаров
        prev_nm_id: Артикул предыдущего товара (если есть)
        next_nm_id: Артикул следующего товара (если есть)
    
    Returns:
        InlineKeyboardMarkup с навигацией
    """
    buttons = []
    
    # Навигация (только если товаров больше 1)
    if total_products > 1:
        nav_row = []
        
        if prev_nm_id:
            nav_row.append(
                InlineKeyboardButton(
                    text="⬅️ Предыдущий",
                    callback_data=f"nav_product:{prev_nm_id}:{current_index-1}"
                )
            )
        
        # Индикатор позиции
        nav_row.append(
            InlineKeyboardButton(
                text=f"• {current_index}/{total_products} •",
                callback_data="noop"
            )
        )
        
        if next_nm_id:
            nav_row.append(
                InlineKeyboardButton(
                    text="Следующий ➡️",
                    callback_data=f"nav_product:{next_nm_id}:{current_index+1}"
                )
            )
        
        buttons.append(nav_row)
    
    # Основные действия
    buttons.extend([
        [
            InlineKeyboardButton(
                text="📈 График цен",
                callback_data=f"show_graph:{nm_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔔 Настроить уведомления",
                callback_data=f"notify_settings:{nm_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️ Переименовать",
                callback_data=f"rename:{nm_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔗 Открыть на WB",
                url=f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"rm:{nm_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Вернуться к списку",
                callback_data="list_products"
            )
        ]
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    return kb


# Обработчик "noop" для неактивных кнопок
async def handle_noop(query):
    """Заглушка для неактивных кнопок."""
    await query.answer()


def admin_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню администратора."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="🏥 Здоровье", callback_data="admin_health")
        ],
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
            InlineKeyboardButton(text="📦 Товары", callback_data="admin_products")
        ],
        [
            InlineKeyboardButton(text="⚠️ Ошибки API", callback_data="admin_errors"),
            InlineKeyboardButton(text="🔧 Система", callback_data="admin_system")
        ],
        [
            InlineKeyboardButton(text="💳 Платежи", callback_data="admin_payments"),
            InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_menu")
        ]
    ])


def back_to_admin_menu_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата в админ меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад в меню", callback_data="admin_menu")]
    ])


def user_management_kb(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления пользователем."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📋 Изменить тариф",
                callback_data=f"admin_change_plan:{user_id}"
            ),
            InlineKeyboardButton(
                text="🚫 Заблокировать",
                callback_data=f"admin_ban_user:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Детали",
                callback_data=f"admin_user_details:{user_id}"
            ),
            InlineKeyboardButton(
                text="🗑 Удалить данные",
                callback_data=f"admin_delete_user:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="« Назад",
                callback_data="admin_users"
            )
        ]
    ])


def plan_selection_kb(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора тарифа для пользователя."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎁 Free (5)",
                callback_data=f"admin_set_plan:{user_id}:plan_free:5"
            )
        ],
        [
            InlineKeyboardButton(
                text="💼 Basic (50)",
                callback_data=f"admin_set_plan:{user_id}:plan_basic:50"
            )
        ],
        [
            InlineKeyboardButton(
                text="🚀 Pro (250)",
                callback_data=f"admin_set_plan:{user_id}:plan_pro:250"
            )
        ],
        [
            InlineKeyboardButton(
                text="« Отмена",
                callback_data=f"admin_user_manage:{user_id}"
            )
        ]
    ])


def broadcast_confirm_kb(message_text: str) -> InlineKeyboardMarkup:
    """Подтверждение рассылки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Отправить всем",
                callback_data="admin_broadcast_confirm"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="admin_menu"
            )
        ]
    ])
