"""
Клавиатуры для бота.
Оптимизированная версия с фабриками и переиспользованием кода.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict

from keyboards.builders import PaginatedKeyboard


# ============= ФАБРИКИ КНОПОК =============

def btn(text: str, callback_data: str) -> InlineKeyboardButton:
    """Создать inline кнопку."""
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def btn_url(text: str, url: str) -> InlineKeyboardButton:
    """Создать кнопку с URL."""
    return InlineKeyboardButton(text=text, url=url)


def back_btn(callback_data: str = "back_to_menu") -> InlineKeyboardButton:
    """Кнопка 'Назад'."""
    return btn("« Назад", callback_data)
# def back_btn(context: str = "default") -> InlineKeyboardButton:
#     """
#     Создаёт кнопку назад.
#     context: уникальный идентификатор, чтобы различать разные разделы.
#     """
#     return InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back:{context}")


def cancel_btn() -> InlineKeyboardButton:
    """Кнопка 'Отмена'."""
    return btn("❌ Отмена", "cancel")


# ============= БАЗОВЫЕ КЛАВИАТУРЫ =============

def simple_kb(*buttons_rows: List[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    """Создать клавиатуру из списка рядов кнопок."""
    return InlineKeyboardMarkup(inline_keyboard=list(buttons_rows))


def single_button_kb(text: str, callback_data: str) -> InlineKeyboardMarkup:
    """Клавиатура с одной кнопкой."""
    return simple_kb([btn(text, callback_data)])


def back_kb(callback_data: str = "back_to_menu") -> InlineKeyboardMarkup:
    """Клавиатура только с кнопкой 'Назад'."""
    return simple_kb([back_btn(callback_data)])


# ============= ГЛАВНОЕ МЕНЮ =============

def main_inline_kb() -> InlineKeyboardMarkup:
    """Главное меню."""
    return simple_kb(
        [btn("➕ Добавить товар", "add_product")],
        [btn("📦 Мои товары", "list_products")],
        [btn("🗑 Удалить товар", "remove_product")],
        [btn("📋 Экспорт в Excel/CSV", "export_menu")],
        [btn("📊 Моя статистика", "my_stats")],
        [btn("⚙️ Настройки", "settings")]
    )


def create_smart_menu(products_count: int, max_links: int, plan: str) -> InlineKeyboardMarkup:
    """Умное меню в зависимости от контекста."""
    buttons = []
    
    # Логика добавления
    if products_count == 0:
        buttons.append([btn("🎯 Добавить первый товар", "add_product")])
    elif products_count < max_links:
        buttons.extend([
            [btn("➕ Добавить товар", "add_product")],
            [btn("📦 Мои товары", "list_products")]
        ])
    else:
        buttons.extend([
            [btn("⚠️ Лимит достигнут - Улучшить тариф", "upsell_limit_reached")],
            [btn("📦 Мои товары", "list_products")]
        ])
    
    # Дополнительные кнопки
    buttons.append([
        btn("📊 Статистика", "my_stats"),
        btn("⚙️ Настройки", "settings")
    ])
    
    # Апсейл для бесплатного тарифа
    if plan == "Бесплатный" and products_count >= 3:
        buttons.append([btn("🚀 Хотите больше возможностей?", "show_upgrade_benefits")])
    
    return simple_kb(*buttons)


# ============= ОНБОРДИНГ =============

def start_kb() -> InlineKeyboardMarkup:
    """Стартовая клавиатура для новых пользователей."""
    return simple_kb(
        [btn("➕ Добавить товар и начать экономить", "onboarding_add_first")],
        [btn("📋 Сначала выбрать тариф", "show_plans_first")]
    )


def onboarding_kb() -> InlineKeyboardMarkup:
    """Клавиатура после добавления первого товара."""
    return simple_kb(
        [btn("➕ Добавить ещё товар", "add_product")],
        [btn("📋 Выбрать тариф", "show_plans_first")],
        [btn("📦 Мои товары", "list_products")]
    )


def onboarding_discount_kb() -> InlineKeyboardMarkup:
    """Онбординг: настройка скидки."""
    return simple_kb(
        [btn("💳 Установить скидку", "onboarding_set_discount")],
        [btn("⏭ Пропустить", "onboarding_skip_discount")]
    )


def onboarding_pvz_kb() -> InlineKeyboardMarkup:
    """Онбординг: настройка ПВЗ."""
    return simple_kb(
        [btn("📍 Установить ПВЗ", "onboarding_set_pvz")],
        [btn("⏭ Пропустить (Москва)", "onboarding_skip_pvz")]
    )


# ============= ТАРИФЫ =============

def choose_plan_kb() -> InlineKeyboardMarkup:
    """Выбор тарифа."""
    return simple_kb(
        [btn("🎁 Бесплатный (5 товаров)", "plan_free")],
        [btn("💼 Базовый (50 товаров)", "plan_basic")],
        [btn("🚀 Продвинутый (250 товаров)", "plan_pro")]
    )


def show_plans_kb() -> InlineKeyboardMarkup:
    """Просмотр тарифов."""
    return simple_kb(
        [btn("💼 Смотреть тариф Базовый", "plan_basic")],
        [btn("🚀 Смотреть тариф Продвинутый", "plan_pro")],
        [back_btn()]
    )


def plan_detail_kb(plan_key: str) -> InlineKeyboardMarkup:
    """Детали тарифа с подтверждением."""
    return simple_kb(
        [btn("✅ Выбрать этот тариф", f"confirm_{plan_key}")],
        [btn("« Назад к выбору", "back_to_plan_choice")]
    )


def upgrade_plan_kb() -> InlineKeyboardMarkup:
    """Улучшение тарифа."""
    return simple_kb(
        [btn("⬆️ Улучшить тариф", "upgrade_plan")],
        [back_btn()]
    )


def upsell_kb() -> InlineKeyboardMarkup:
    """Upsell клавиатура."""
    return simple_kb(
        [btn("🚀 Улучшить до Базового (199₽/мес)", "plan_basic")],
        [btn("💎 Смотреть все тарифы", "show_plans_first")],
        [btn("🗑 Удалить старый товар", "remove_product")],
        [back_btn()]
    )


# ============= НАСТРОЙКИ =============

def settings_kb() -> InlineKeyboardMarkup:
    """Меню настроек."""
    return simple_kb(
        [btn("💳 Скидка кошелька", "set_discount")],
        [btn("📍 Мой ПВЗ", "show_pvz")],
        [btn("💰 Мой тариф", "my_plan")],
        [back_btn()]
    )


def back_to_settings_kb() -> InlineKeyboardMarkup:
    """Возврат к настройкам."""
    return back_kb("settings")


def reset_pvz_kb() -> InlineKeyboardMarkup:
    """Управление ПВЗ."""
    return simple_kb(
        [btn("🔄 Изменить ПВЗ", "set_pvz")],
        [btn("🔙 Назад", "settings")]
    )


# ============= ТОВАРЫ =============

def sizes_inline_kb(nm: int, sizes: List[Dict]) -> InlineKeyboardMarkup:
    """Выбор размера товара."""
    buttons = [[btn(s.get("name"), f"select_size:{nm}:{s.get('name')}")] for s in sizes]
    return simple_kb(*buttons)


def products_inline(products: List[Dict]) -> InlineKeyboardMarkup:
    """Список товаров с кнопками."""
    buttons = []
    
    # Кнопки товаров
    for p in products:
        name = p.get("name", f"Товар {p['nm_id']}")
        display_name = name[:40] + "..." if len(name) > 40 else name
        buttons.append([btn(f"📊 {display_name}", f"product_detail:{p['nm_id']}")])
    
    # Действия
    buttons.extend([
        [btn("➕ Добавить товар", "add_product")],
        [back_btn()]
    ])
    
    return simple_kb(*buttons)


def products_list_kb(
    products: List[Dict],
    has_filters: bool = False,
    show_export: bool = False,
    show_upgrade: bool = False,
    page: int = 1
) -> InlineKeyboardMarkup:
    """Расширенный список товаров с фильтрами."""

    prepared_products = []
    for p in products:
        name = p.get("display_name", "")
        if len(name) > 35:
            name = name[:32] + "..."
        # 🛍️ Добавляем эмодзи перед названием
        p = p.copy()
        p["display_name"] = f"🛍️ {name}"
        prepared_products.append(p)

    paginated_kb = PaginatedKeyboard(
        items=prepared_products,
        callback_prefix="product_detail",
        page=page,
        per_page=5,
        id_field="nm_id",
        name_field="display_name"
    ).build()

    buttons = []
    
    # Фильтры
    if has_filters:
        buttons.append([
            btn("🔥 Лучшие скидки", "filter_best_deals"),
            btn("📉 Падающие цены", "filter_price_drops")
        ])
    
    # Действия
    buttons.append([
        btn("➕ Добавить товар", "add_product"),
        btn("🗑 Удалить товар", "remove_product")
    ])
    
    # # Экспорт для Pro
    # if show_export:
    #     buttons.append([btn("📋 Экспорт в Excel/CSV", "export_menu")])
    
    # Апгрейд для Free
    if show_upgrade:
        buttons.append([btn("🚀 Улучшить тариф (до 50 товаров)", "upsell_from_products_list")])

    # Пагинация
    if paginated_kb and paginated_kb.inline_keyboard:
        buttons.extend(paginated_kb.inline_keyboard)
    
    buttons.append([back_btn()])
    
    return simple_kb(*buttons)


def product_detail_kb(nm_id: int) -> InlineKeyboardMarkup:
    """Детальная карточка товара."""
    return simple_kb(
        [btn("📈 График цен", f"show_graph:{nm_id}")],
        [btn("🔔 Настроить уведомления", f"notify_settings:{nm_id}")],
        [btn("✏️ Переименовать", f"rename:{nm_id}")],
        [btn_url("🔗 Открыть на WB", f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx")],
        [btn("🗑 Удалить", f"rm:{nm_id}")],
        [btn("📋 Вернуться к списку", "list_products")]
    )


def remove_products_kb(products: List[Dict]) -> InlineKeyboardMarkup:
    """Список товаров для удаления."""
    buttons = []
    
    for product in products:
        display_name = product['display_name']
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
        buttons.append([btn(f"❌ {display_name}", f"rm:{product['nm_id']}")])
    
    buttons.append([back_btn()])
    return simple_kb(*buttons)


def confirm_remove_kb(nm_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления."""
    return simple_kb(
        [
            btn("✅ Да, удалить", f"confirm_remove:{nm_id}"),
            btn("❌ Отмена", "list_products")
        ]
    )


def back_to_product_kb(nm_id: int) -> InlineKeyboardMarkup:
    """Возврат к карточке товара."""
    return back_kb(f"back_to_product:{nm_id}")


# ============= УВЕДОМЛЕНИЯ =============

def notify_mode_kb(nm_id: int) -> InlineKeyboardMarkup:
    """Выбор режима уведомлений."""
    return simple_kb(
        [btn("📊 По проценту снижения", f"notify_percent:{nm_id}")],
        [btn("💰 По целевой цене", f"notify_threshold:{nm_id}")],
        [btn("🔕 Отключить (все уведомления)", f"notify_all:{nm_id}")],
        [btn("« Назад", f"product_detail:{nm_id}")]
    )


# ============= ЭКСПОРТ =============

def export_format_kb() -> InlineKeyboardMarkup:
    """Выбор формата экспорта."""
    return simple_kb(
        [btn("📗 Excel (.xlsx)", "export_excel")],
        [btn("📄 CSV (.csv)", "export_csv")],
        [back_btn()]
    )


# ============= НАВИГАЦИЯ =============

def back_to_menu_kb() -> InlineKeyboardMarkup:
    """Возврат в главное меню."""
    return back_kb()


# ============= АДМИН ПАНЕЛЬ =============

def admin_menu_kb() -> InlineKeyboardMarkup:
    """Админ панель."""
    return simple_kb(
        [
            btn("📊 Статистика", "admin_stats"),
            btn("🏥 Здоровье", "admin_health")
        ],
        [
            btn("👥 Пользователи", "admin_users"),
            btn("📦 Товары", "admin_products")
        ],
        [
            btn("⚠️ Ошибки API", "admin_errors"),
            btn("🔧 Система", "admin_system")
        ],
        [
            btn("💳 Платежи", "admin_payments"),
            btn("📨 Рассылка", "admin_broadcast")
        ],
        [btn("🔄 Обновить", "admin_menu")]
    )


def back_to_admin_menu_kb() -> InlineKeyboardMarkup:
    """Возврат в админ меню."""
    return back_kb("admin_menu")


def user_management_kb(user_id: int) -> InlineKeyboardMarkup:
    """Управление пользователем."""
    return simple_kb(
        [
            btn("📋 Изменить тариф", f"admin_change_plan:{user_id}"),
            btn("🚫 Заблокировать", f"admin_ban_user:{user_id}")
        ],
        [
            btn("📊 Детали", f"admin_user_details:{user_id}"),
            btn("🗑 Удалить данные", f"admin_delete_user:{user_id}")
        ],
        [btn("« Назад", "admin_users")]
    )


def plan_selection_kb(user_id: int) -> InlineKeyboardMarkup:
    """Выбор тарифа для пользователя (админ)."""
    return simple_kb(
        [btn("🎁 Free (5)", f"admin_set_plan:{user_id}:plan_free:5")],
        [btn("💼 Basic (50)", f"admin_set_plan:{user_id}:plan_basic:50")],
        [btn("🚀 Pro (250)", f"admin_set_plan:{user_id}:plan_pro:250")],
        [btn("« Отмена", f"admin_user_manage:{user_id}")]
    )
