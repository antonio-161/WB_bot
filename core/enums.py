from enum import Enum


class Plan(Enum):
    FREE = "plan_free"
    BASIC = "plan_basic"
    PRO = "plan_pro"


class NotifyMode(Enum):
    ANY = None          # Уведомлять о любом снижении
    PERCENT = "percent"
    THRESHOLD = "threshold"


class SortMode(Enum):
    SAVINGS = "savings"
    UPDATED = "updated"


class PriceTrend(Enum):
    """Тренд цены."""
    FALLING = "falling"  # Цена падает
    RISING = "rising"    # Цена растёт
    STABLE = "stable"    # Стабильная
