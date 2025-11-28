"""
Domain Entities - бизнес-сущности с логикой.
Используются в сервисах и бизнес-логике.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from enums import Plan, NotifyMode, PriceTrend, SortMode
from constants import DEFAULT_DEST


@dataclass
class User:
    """
    Бизнес-сущность пользователя с логикой.
    """
    id: int
    plan: Plan = Plan.FREE
    discount_percent: int = 0
    max_links: int = 5
    dest: int = DEFAULT_DEST
    pvz_address: Optional[str] = None
    sort_mode: SortMode = SortMode.UPDATED
    created_at: Optional[datetime] = None

    @property
    def plan_name(self) -> str:
        """Человекочитаемое название тарифа."""
        return {
            Plan.FREE: "Бесплатный",
            Plan.BASIC: "Базовый",
            Plan.PRO: "Продвинутый",
        }.get(self.plan, "Неизвестный")

    @property
    def is_premium(self) -> bool:
        """Является ли пользователь премиум."""
        return self.plan in (Plan.BASIC, Plan.PRO)

    @property
    def has_custom_pvz(self) -> bool:
        """Установлен ли кастомный ПВЗ."""
        return self.dest != DEFAULT_DEST and self.dest is not None

    def get_pvz_display(self) -> str:
        """Форматирование информации о ПВЗ."""
        if not self.has_custom_pvz:
            return "Москва (по умолчанию)"
        elif self.pvz_address:
            return self.pvz_address
        else:
            return f"Код: {self.dest}"

    def can_add_product(self, current_count: int) -> tuple[bool, str]:
        """Проверка возможности добавить товар."""
        if current_count >= self.max_links:
            return False, f"Достигнут лимит ({self.max_links}) товаров"
        return True, ""

    def apply_wallet_discount(self, price: int) -> int:
        """Применить скидку WB кошелька."""
        if self.discount_percent <= 0:
            return price

        discounted = price * (1 - self.discount_percent / 100.0)
        return int(discounted)

    def validate_discount(self, discount: int) -> tuple[bool, str]:
        """Валидация скидки."""
        if not isinstance(discount, int):
            return False, "Скидка должна быть целым числом"

        if not 0 <= discount <= 100:
            return False, "Скидка должна быть от 0 до 100%"

        return True, ""


@dataclass
class Product:
    """
    Бизнес-сущность товара с логикой.
    """
    id: int
    user_id: int
    url: str
    nm_id: int
    name: str
    custom_name: Optional[str]
    last_basic_price: Optional[int]
    last_product_price: Optional[int]
    selected_size: Optional[str]
    notify_mode: NotifyMode
    notify_value: Optional[int]
    last_qty: int
    out_of_stock: bool
    created_at: datetime
    updated_at: datetime

    @property
    def display_name(self) -> str:
        """Отображаемое имя товара."""
        return self.custom_name or self.name

    @property
    def is_available(self) -> bool:
        """Есть ли товар в наличии."""
        return not self.out_of_stock and self.last_qty > 0

    @property
    def has_size(self) -> bool:
        return self.selected_size is not None

    @property
    def has_custom_name(self) -> bool:
        return self.custom_name is not None

    def should_notify_price_drop(self, old_price: int, new_price: int) -> bool:
        """Определение, нужно ли уведомление о снижении цены."""
        if new_price >= old_price:
            return False

        # Любое снижение
        if self.notify_mode is NotifyMode.ANY:
            return True

        # По проценту
        if self.notify_mode is NotifyMode.PERCENT and self.notify_value:
            percent_drop = ((old_price - new_price) / old_price) * 100
            return percent_drop >= self.notify_value

        # По порогу
        if self.notify_mode is NotifyMode.THRESHOLD and self.notify_value:
            return new_price <= self.notify_value

        return True

    def validate_custom_name(self, name: str) -> tuple[bool, str]:
        """Валидация пользовательского названия."""
        if len(name) < 3:
            return False, "Название слишком короткое (минимум 3 символа)"
        if len(name) > 200:
            return False, "Название слишком длинное (максимум 200 символов)"
        return True, ""

    def validate_notify_settings(
            self, mode: NotifyMode, value: Optional[int]
    ) -> tuple[bool, str]:
        """Валидация настроек уведомлений."""
        if mode is NotifyMode.PERCENT:
            if not value or value <= 0 or value > 100:
                return False, "Процент должен быть от 1 до 100"

        elif mode is NotifyMode.THRESHOLD:
            if not value or value <= 0:
                return False, "Порог должен быть положительным числом"

        return True, ""


@dataclass
class PriceHistory:
    """
    Бизнес-сущность записи истории цен.
    """
    id: int
    product_id: int
    basic_price: int
    product_price: int
    qty: int
    recorded_at: datetime

    def calculate_savings(self, current_price: int) -> int:
        """Расчёт экономии относительно текущей цены."""
        if current_price < self.product_price:
            return self.product_price - current_price
        return 0

    @staticmethod
    def calculate_trend(prices: list[int]) -> PriceTrend:
        if len(prices) < 3:
            return PriceTrend.STABLE

        # Берём последние 3 записи: [newest, middle, oldest]
        recent = prices[:3]

        newest_price = recent[0]
        oldest_price = recent[-1]

        if newest_price < oldest_price:
            return PriceTrend.FALLING
        elif newest_price > oldest_price:
            return PriceTrend.RISING
        else:
            return PriceTrend.STABLE
