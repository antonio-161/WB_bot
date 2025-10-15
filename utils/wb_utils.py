"""Утилиты для Wildberries — извлечение nm_id из ссылки и расчёты."""
import re
from typing import Optional
import math


def extract_nm_id(text: str) -> Optional[int]:
    """
    Извлекает nm_id (артикул Wildberries) из текста или ссылки.
    Поддерживаются ссылки из браузера и приложения.
    Возвращает int или None.
    """
    # Ищем шаблон /catalog/<число>/detail.aspx
    match = re.search(r"/catalog/(\d{5,12})/detail\.aspx", text)
    if match:
        return int(match.group(1))

    # fallback: ищем большие числа, которые могут быть nm_id (на всякий случай)
    match = re.search(r"\b(\d{6,12})\b", text)
    if match:
        return int(match.group(1))

    return None


def apply_wallet_discount(price: float, discount_percent: int) -> float:
    """
    Применяет скидку WB кошелька и всегда округляет вниз до копеек.
    """
    discounted = price * (1 - discount_percent / 100.0)
    # округляем вниз до 2 знаков
    floored = math.floor(discounted * 100) / 100.0
    return floored
