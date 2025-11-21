"""Утилиты для Wildberries — извлечение nm_id из ссылки и расчёты."""
import re
from typing import Optional
from infrastructure.db import DB


def extract_nm_id(text: str) -> Optional[int]:
    """
    Извлекает nm_id (артикул Wildberries) из текста, ссылки или чистого артикула.
    Поддерживаются:
    - Ссылки: /catalog/<число>/detail.aspx
    - Чистые артикулы: просто число 6-12 цифр
    - Текст с артикулом

    Возвращает int или None.
    """
    # Сначала ищем шаблон ссылки /catalog/<число>/detail.aspx
    match = re.search(r"/catalog/(\d{5,12})/detail\.aspx", text)
    if match:
        return int(match.group(1))

    # Если это просто число (артикул без ссылки)
    text_stripped = text.strip()
    if text_stripped.isdigit() and 5 <= len(text_stripped) <= 12:
        return int(text_stripped)

    # Fallback: ищем числа 6-12 цифр в тексте
    match = re.search(r"\b(\d{6,12})\b", text)
    if match:
        return int(match.group(1))

    return None


def apply_wallet_discount(price: int, discount_percent: int) -> int:
    """
    Применяет скидку WB кошелька и округляет вниз (int).
    """
    if discount_percent <= 0:
        return price

    discounted = price * (1 - discount_percent / 100.0)
    return int(discounted)  # Округление вниз


def format_price_change(old_price: float, new_price: float) -> dict:
    """
    Форматирует изменение цены для отображения.

    Returns:
        dict: {
            'diff': float - абсолютная разница,
            'percent': float - процентная разница,
            'is_decrease': bool - снижение или нет
        }
    """
    diff = old_price - new_price
    percent = (diff / old_price) * 100 if old_price > 0 else 0

    return {
        'diff': abs(diff),
        'percent': abs(percent),
        'is_decrease': diff > 0
    }


async def calculate_potential_savings(db: DB, user_id: int) -> str:
    """Подсчет потенциальной экономии на основе истории."""
    products = await db.list_products(user_id)

    if not products:
        return ""

    total_savings = 0
    for p in products:
        history = await db.get_price_history(p.id, limit=30)
        if len(history) >= 2:
            prices = [h.product_price for h in history]
            max_price = max(prices)
            current_price = p.last_product_price or max_price
            savings = max_price - current_price
            if savings > 0:
                total_savings += savings

    if total_savings > 0:
        return (
            f"💰 <b>Вы уже можете сэкономить {total_savings}₽</b>\n"
            f"если купите товары по текущим ценам!\n\n"
        )

    return "📈 Пока нет снижений, но я слежу за ценами!\n\n"
