"""
Построители динамических клавиатур.
Для случаев когда нужна более гибкая генерация.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Optional


class KeyboardBuilder:
    """Построитель клавиатур с fluent API."""
    
    def __init__(self):
        self.rows: List[List[InlineKeyboardButton]] = []
    
    def add_button(self, text: str, callback_data: str) -> 'KeyboardBuilder':
        """Добавить кнопку в новый ряд."""
        self.rows.append([
            InlineKeyboardButton(text=text, callback_data=callback_data)
        ])
        return self
    
    def add_url_button(self, text: str, url: str) -> 'KeyboardBuilder':
        """Добавить URL кнопку в новый ряд."""
        self.rows.append([
            InlineKeyboardButton(text=text, url=url)
        ])
        return self
    
    def add_row(self, *buttons: InlineKeyboardButton) -> 'KeyboardBuilder':
        """Добавить ряд кнопок."""
        self.rows.append(list(buttons))
        return self
    
    def add_buttons_row(self, buttons: List[tuple]) -> 'KeyboardBuilder':
        """Добавить ряд из списка (text, callback_data)."""
        row = [
            InlineKeyboardButton(text=text, callback_data=callback)
            for text, callback in buttons
        ]
        self.rows.append(row)
        return self
    
    def add_back_button(self, callback_data: str = "back_to_menu") -> 'KeyboardBuilder':
        """Добавить кнопку 'Назад'."""
        return self.add_button("« Назад", callback_data)
    
    def build(self) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        return InlineKeyboardMarkup(inline_keyboard=self.rows)


class ListKeyboard:
    """Построитель списочных клавиатур (товары, пользователи и т.д.)."""
    
    def __init__(
        self,
        items: List[Dict],
        callback_prefix: str,
        id_field: str = "id",
        name_field: str = "name",
        max_name_length: int = 40,
        emoji: str = "📌"
    ):
        """
        Args:
            items: Список элементов
            callback_prefix: Префикс для callback_data
            id_field: Поле с ID элемента
            name_field: Поле с названием
            max_name_length: Макс длина названия
            emoji: Эмодзи перед названием
        """
        self.items = items
        self.callback_prefix = callback_prefix
        self.id_field = id_field
        self.name_field = name_field
        self.max_name_length = max_name_length
        self.emoji = emoji
        self.builder = KeyboardBuilder()
        self.actions: List[tuple] = []
    
    def add_action(self, text: str, callback_data: str) -> 'ListKeyboard':
        """Добавить действие внизу списка."""
        self.actions.append((text, callback_data))
        return self
    
    def add_back_button(self, callback_data: str = "back_to_menu") -> 'ListKeyboard':
        """Добавить кнопку назад."""
        self.actions.append(("« Назад", callback_data))
        return self
    
    def build(self, limit: Optional[int] = None) -> InlineKeyboardMarkup:
        """Построить клавиатуру."""
        items_to_show = self.items[:limit] if limit else self.items
        
        # Добавляем элементы
        for item in items_to_show:
            item_id = item[self.id_field]
            name = item[self.name_field]
            
            # Обрезаем название
            if len(name) > self.max_name_length:
                name = name[:self.max_name_length-3] + "..."
            
            self.builder.add_button(
                f"{self.emoji} {name}",
                f"{self.callback_prefix}:{item_id}"
            )
        
        # Если показали не все
        if limit and len(self.items) > limit:
            self.builder.add_button(
                f"📋 Показать все ({len(self.items)})",
                f"{self.callback_prefix}_show_all"
            )
        
        # Добавляем действия
        for text, callback in self.actions:
            self.builder.add_button(text, callback)
        
        return self.builder.build()


class PaginatedKeyboard:
    """Построитель клавиатур с пагинацией."""
    
    def __init__(
        self,
        items: List[Dict],
        callback_prefix: str,
        page: int = 1,
        per_page: int = 5,
        id_field: str = "id",
        name_field: str = "name"
    ):
        self.items = items
        self.callback_prefix = callback_prefix
        self.page = page
        self.per_page = per_page
        self.id_field = id_field
        self.name_field = name_field
        self.total_pages = (len(items) + per_page - 1) // per_page
    
    def build(self) -> InlineKeyboardMarkup:
        """Построить клавиатуру с пагинацией."""
        builder = KeyboardBuilder()
        
        # Элементы текущей страницы
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        page_items = self.items[start:end]
        
        for item in page_items:
            item_id = item[self.id_field]
            name = item[self.name_field]
            builder.add_button(name, f"{self.callback_prefix}:{item_id}")
        
        # Навигация
        if self.total_pages > 1:
            nav_buttons = []
            
            if self.page > 1:
                nav_buttons.append(
                    InlineKeyboardButton(text="⬅️", callback_data=f"page:{self.page-1}")
                )
            
            nav_buttons.append(
                InlineKeyboardButton(
                    text=f"• {self.page}/{self.total_pages} •",
                    callback_data="noop"
                )
            )
            
            if self.page < self.total_pages:
                nav_buttons.append(
                    InlineKeyboardButton(text="➡️", callback_data=f"page:{self.page+1}")
                )
            
            builder.add_row(*nav_buttons)
        
        return builder.build()


class FilterKeyboard:
    """Построитель клавиатуры с фильтрами."""
    
    def __init__(self, active_filters: Dict[str, bool] = None):
        self.active_filters = active_filters or {}
        self.builder = KeyboardBuilder()
    
    def add_filter(
        self,
        name: str,
        callback_data: str,
        icon_active: str = "✅",
        icon_inactive: str = "☐"
    ) -> 'FilterKeyboard':
        """Добавить фильтр."""
        is_active = self.active_filters.get(callback_data, False)
        icon = icon_active if is_active else icon_inactive
        
        self.builder.add_button(
            f"{icon} {name}",
            f"filter:{callback_data}"
        )
        return self
    
    def add_apply_button(self, callback_data: str = "apply_filters") -> 'FilterKeyboard':
        """Добавить кнопку применения."""
        self.builder.add_button("🔍 Применить", callback_data)
        return self
    
    def add_reset_button(self, callback_data: str = "reset_filters") -> 'FilterKeyboard':
        """Добавить кнопку сброса."""
        self.builder.add_button("🔄 Сбросить", callback_data)
        return self
    
    def build(self) -> InlineKeyboardMarkup:
        return self.builder.build()


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

def create_confirmation_kb(
    confirm_text: str = "✅ Да",
    confirm_callback: str = "confirm",
    cancel_text: str = "❌ Нет",
    cancel_callback: str = "cancel"
) -> InlineKeyboardMarkup:
    """Создать клавиатуру подтверждения."""
    return KeyboardBuilder() \
        .add_buttons_row([
            (confirm_text, confirm_callback),
            (cancel_text, cancel_callback)
        ]) \
        .build()


def create_numbered_list_kb(
    items: List[str],
    callback_prefix: str,
    back_callback: str = "back_to_menu"
) -> InlineKeyboardMarkup:
    """Создать пронумерованный список."""
    builder = KeyboardBuilder()
    
    for i, item in enumerate(items, 1):
        builder.add_button(f"{i}. {item}", f"{callback_prefix}:{i}")
    
    builder.add_back_button(back_callback)
    return builder.build()


def create_yes_no_kb(
    yes_callback: str = "yes",
    no_callback: str = "no"
) -> InlineKeyboardMarkup:
    """Создать клавиатуру Да/Нет."""
    return create_confirmation_kb(
        "✅ Да", yes_callback,
        "❌ Нет", no_callback
    )


# ============= ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ =============

# Пример 1: Простой builder
def example_builder():
    return KeyboardBuilder() \
        .add_button("Действие 1", "action_1") \
        .add_button("Действие 2", "action_2") \
        .add_buttons_row([
            ("⬅️ Назад", "back"),
            ("➡️ Далее", "next")
        ]) \
        .build()


# Пример 2: Список товаров
def example_products_list(products: List[Dict]):
    return ListKeyboard(
        items=products,
        callback_prefix="product",
        id_field="nm_id",
        name_field="name",
        emoji="📦"
    ) \
        .add_action("➕ Добавить товар", "add_product") \
        .add_back_button() \
        .build(limit=10)


# Пример 3: Пагинация
def example_paginated(items: List[Dict], page: int = 1):
    return PaginatedKeyboard(
        items=items,
        callback_prefix="item",
        page=page,
        per_page=10
    ).build()


# Пример 4: Фильтры
def example_filters(active_filters: Dict[str, bool]):
    return FilterKeyboard(active_filters) \
        .add_filter("В наличии", "in_stock") \
        .add_filter("Со скидкой", "on_sale") \
        .add_filter("Избранное", "favorite") \
        .add_apply_button() \
        .add_reset_button() \
        .build()
