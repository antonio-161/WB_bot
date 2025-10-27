"""
Форматирование сообщений для пользователя.
Вся логика форматирования вынесена из handlers.
"""
from typing import Dict, List, Optional
from utils.wb_utils import apply_wallet_discount


def format_product_added_message(
    product_name: str,
    nm_id: int,
    price: int,
    discount: int = 0,
    is_onboarding: bool = False
) -> str:
    """Форматирование сообщения о добавленном товаре."""
    
    price_text = f"💰 Текущая цена: {price} ₽"
    
    if discount > 0:
        final_price = apply_wallet_discount(price, discount)
        price_text = (
            f"💰 Цена: {price} ₽\n"
            f"💳 С кошельком ({discount}%): {int(final_price)} ₽"
        )
    
    if is_onboarding:
        return (
            f"🎉 <b>Отлично! Товар добавлен</b>\n\n"
            f"📦 {product_name}\n"
            f"🔢 Артикул: <code>{nm_id}</code>\n"
            f"{price_text}\n\n"
            "✅ Теперь я буду отслеживать цену каждый день\n"
            "🔔 Вы получите уведомление при снижении\n\n"
            "💡 <b>Что дальше?</b>\n"
            "🎁 У вас ещё <b>4 бесплатных слота</b>\n"
            "Добавьте больше товаров или выберите тариф для расширения возможностей 👇"
        )
    else:
        return (
            f"✅ <b>Товар добавлен!</b>\n\n"
            f"📦 {product_name}\n"
            f"🔢 Артикул: <code>{nm_id}</code>\n"
            f"{price_text}\n\n"
            "Я буду отслеживать изменения цены."
        )


def format_product_with_size_added(
    product_name: str,
    nm_id: int,
    size_name: str
) -> str:
    """Форматирование сообщения о товаре с размером."""
    return (
        f"✅ <b>Товар добавлен!</b>\n\n"
        f"📦 {product_name}\n"
        f"🔢 Артикул: <code>{nm_id}</code>\n"
        f"🔘 Размер: <b>{size_name}</b>\n\n"
        "Теперь я буду отслеживать цены для этого размера."
    )


def format_products_list(
    products_analytics: List[Dict],
    total_current_price: int,
    total_potential_savings: int,
    best_deal: Optional[Dict],
    best_deal_percent: float,
    discount: int,
    plan: str,
    max_links: int
) -> str:
    """Форматирование списка товаров с аналитикой."""
    
    text = "📦 <b>Ваши товары</b>\n"
    text += f"{'═'*25}\n\n"
    
    # Мини-дашборд
    text += f"📊 Товаров: <b>{len(products_analytics)}/{max_links}</b>\n"
    
    if discount > 0:
        total_with_discount = sum(
            apply_wallet_discount(p["product"].get("last_product_price", 0), discount)
            for p in products_analytics
        )
        text += f"💰 Общая стоимость: <b>{total_with_discount}₽</b> (с WB кошельком)\n"
    else:
        text += f"💰 Общая стоимость: <b>{total_current_price}₽</b>\n"
    
    if total_potential_savings > 0:
        text += f"💎 Можно сэкономить: <b>{total_potential_savings}₽</b>\n"
    
    text += "\n"
    
    # Лучшая сделка
    if best_deal:
        best_name = best_deal.get("custom_name") or best_deal.get("name_product", "")
        text += (
            f"🔥 <b>Лучшая сделка сейчас:</b>\n"
            f"{best_name[:35]}...\n"
            f"└ Скидка {best_deal_percent:.0f}% от пика цены!\n\n"
        )
    
    text += "📋 <b>Список товаров:</b>\n"
    text += "<i>Отсортировано по выгодности</i>\n\n"
    
    # Топ-10 товаров
    for i, item in enumerate(products_analytics[:10], 1):
        product = item["product"]
        
        # Эмодзи статуса
        if item["savings_percent"] >= 30:
            status_emoji = "🔥"
        elif item["savings_percent"] >= 15:
            status_emoji = "💰"
        elif item["trend"] == "down":
            status_emoji = "📉"
        elif item["trend"] == "up":
            status_emoji = "📈"
        else:
            status_emoji = "📦"
        
        stock_emoji = "✅" if not product.get("out_of_stock") else "❌"
        
        display_name = product.get("custom_name") or product.get("name_product", "")
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
        
        price = product.get("last_product_price")
        if price:
            if discount > 0:
                final_price = apply_wallet_discount(price, discount)
                price_str = f"{final_price}₽"
            else:
                price_str = f"{price}₽"
        else:
            price_str = "—"
        
        savings_str = ""
        if item["savings_percent"] > 0:
            savings_str = f" (-{item['savings_percent']:.0f}%)"
        
        text += f"{status_emoji} <b>{i}.</b> {display_name}\n"
        text += f"   {stock_emoji} {price_str}{savings_str}\n"
    
    if len(products_analytics) > 10:
        text += f"\n<i>... и ещё {len(products_analytics) - 10} товаров</i>\n"
    
    # Подсказки
    text += "\n💡 <b>Подсказки:</b>\n"
    
    out_of_stock_count = sum(
        1 for p in products_analytics 
        if p["product"].get("out_of_stock")
    )
    if out_of_stock_count > 0:
        text += f"• {out_of_stock_count} товар(ов) нет в наличии\n"
    
    if plan == "plan_free" and len(products_analytics) >= max_links - 1:
        text += f"• Осталось {max_links - len(products_analytics)} слот(ов)\n"
    
    if plan == "plan_free" and len(products_analytics) >= 3:
        text += "• 💎 Улучшите тариф для отслеживания до 50 товаров\n"
    
    return text


def format_product_detail(
    product: Dict,
    stats: Optional[Dict],
    discount: int,
    plan: str
) -> str:
    """Форматирование детальной информации о товаре."""
    
    display_name = product.get("custom_name") or product.get("name_product", "")
    nm_id = product["nm_id"]
    
    text = f"📦 <b>{display_name}</b>\n\n"
    text += f"🔢 Артикул: <code>{nm_id}</code>\n"
    
    if product.get("selected_size"):
        text += f"🔘 Размер: <b>{product['selected_size']}</b>\n"
    
    # Цена
    price = product.get("last_product_price")
    if price:
        if discount > 0:
            final_price = apply_wallet_discount(price, discount)
            text += f"💰 Цена: {price} ₽\n"
            text += f"💳 С кошельком ({discount}%): <b>{final_price} ₽</b>\n"
        else:
            text += f"💰 Текущая цена: <b>{price} ₽</b>\n"
    
    # Остатки
    qty = product.get("last_qty")
    if qty is not None:
        if plan == "plan_pro":
            if product.get("out_of_stock"):
                text += "📦 Остаток: <b>Нет в наличии</b>\n"
            else:
                text += f"📦 Остаток: <b>{qty} шт.</b>\n"
        else:
            if product.get("out_of_stock"):
                text += "📦 <b>Нет в наличии</b>\n"
            else:
                text += "📦 <b>В наличии</b>\n"
    
    # Статистика
    if stats:
        text += f"\n📊 <b>Статистика:</b>\n"
        
        if discount > 0:
            text += f"• Мин. цена: {stats['min_price']} ₽ (с WB кошельком {stats['min_with_discount']} ₽)\n"
            text += f"• Макс. цена: {stats['max_price']} ₽ (с WB кошельком {stats['max_with_discount']} ₽)\n"
        else:
            text += f"• Мин. цена: {stats['min_price']} ₽\n"
            text += f"• Макс. цена: {stats['max_price']} ₽\n"
    
    # Уведомления
    notify_mode = product.get("notify_mode")
    notify_value = product.get("notify_value")
    
    if notify_mode == "percent":
        text += f"\n🔔 Уведомления: при снижении на {notify_value}%"
    elif notify_mode == "threshold":
        text += f"\n🔔 Уведомления: при цене ≤ {notify_value} ₽"
    else:
        text += "\n🔔 Уведомления: все изменения цены"
    
    created_at = product.get("created_at")
    if created_at:
        text += f"\n🕐 Добавлен: {created_at.strftime('%d.%m.%Y %H:%M')}"
    
    return text


def format_filtered_products(
    title: str,
    products_with_data: List[tuple],
    discount: int,
    show_percent: bool = False
) -> str:
    """Форматирование отфильтрованного списка товаров."""
    
    text = (
        f"{title}\n"
        f"{'═'*25}\n\n"
        f"Найдено товаров: <b>{len(products_with_data)}</b>\n\n"
    )
    
    for i, item in enumerate(products_with_data[:15], 1):
        product, value = item
        
        display_name = product.get("custom_name") or product.get("name_product", "")
        if len(display_name) > 35:
            display_name = display_name[:32] + "..."
        
        price = product.get("last_product_price")
        if price:
            if discount > 0:
                final_price = apply_wallet_discount(price, discount)
                price_str = f"{final_price}₽"
            else:
                price_str = f"{price}₽"
        else:
            price_str = "—"
        
        if show_percent:
            emoji = "🔥"
            detail = f"<b>(-{value:.0f}%)</b>"
        else:
            emoji = "📉"
            detail = f"<b>{value}₽</b> за неделю"
        
        text += (
            f"{emoji} <b>{i}.</b> {display_name}\n"
            f"   💰 {price_str} {detail}\n"
        )
    
    return text


def format_settings(
    settings: Dict,
    products_count: int
) -> str:
    """Форматирование настроек пользователя."""
    
    return (
        "⚙️ <b>Ваши настройки</b>\n\n"
        f"📋 Тариф: <b>{settings['plan_name']}</b>\n"
        f"📊 Использовано слотов: <b>{products_count}/{settings['max_links']}</b>\n"
        f"💳 Скидка WB кошелька: <b>{settings['discount']}%</b>\n"
        f"📍 ПВЗ: <b>{settings['pvz_info']}</b>\n\n"
        "Используйте кнопки ниже для изменения настроек."
    )


def format_user_stats(stats: Dict) -> str:
    """Форматирование статистики пользователя."""
    
    text = (
        f"📊 <b>Ваша статистика</b>\n\n"
        f"📦 <b>Всего товаров:</b> {stats['total_products']}\n"
        f"✅ <b>В наличии:</b> {stats['in_stock']}\n"
        f"❌ <b>Нет в наличии:</b> {stats['out_of_stock']}\n\n"
        f"💰 <b>Средняя цена:</b> {stats['avg_price']} ₽\n"
    )
    
    if stats['cheapest']:
        cheapest_name = stats['cheapest'].get("custom_name") or stats['cheapest'].get("name_product", "")
        cheapest_price = stats['cheapest'].get("last_product_price", 0)
        text += (
            f"\n🔽 <b>Самый дешёвый:</b>\n"
            f"{cheapest_name[:40]} — {cheapest_price} ₽\n"
        )
    
    if stats['most_expensive']:
        expensive_name = stats['most_expensive'].get("custom_name") or stats['most_expensive'].get("name_product", "")
        expensive_price = stats['most_expensive'].get("last_product_price", 0)
        text += (
            f"\n🔼 <b>Самый дорогой:</b>\n"
            f"{expensive_name[:40]} — {expensive_price} ₽\n"
        )
    
    return text
