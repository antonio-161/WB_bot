"""
Обработчики команды /start.
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from services.user_service import UserService
from services.product_service import ProductService
from keyboards.kb import create_smart_menu, start_kb

router = Router()


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    user_service: UserService,
    product_service: ProductService
):
    """Команда /start с value-first подходом."""
    
    user_id = message.from_user.id
    
    # Получаем или создаём пользователя
    user = await user_service.get_user_info(user_id)
    
    # ===== НОВЫЙ ПОЛЬЗОВАТЕЛЬ =====
    if not user:
        await user_service.ensure_user_exists(user_id)
        
        await message.answer(
            "🎯 <b>Переплачиваете за покупки на Wildberries?</b>\n\n"
            "Представьте: вы следите за курткой за 8 000₽.\n"
            "Через 3 дня цена падает до 5 200₽.\n"
            "<b>Вы экономите 2 800₽ на одной покупке!</b> 💰\n\n"
            "❌ Без бота: вы этого не увидите\n"
            "✅ С ботом: вы получите уведомление и купите дешевле\n\n"
            "🎁 <b>Попробуйте БЕСПЛАТНО:</b>\n"
            "Добавьте первый товар прямо сейчас 👇",
            parse_mode="HTML",
            reply_markup=start_kb()
        )
        return
    
    # ===== СУЩЕСТВУЮЩИЙ ПОЛЬЗОВАТЕЛЬ =====
    plan_name = user.get("plan_name", "Бесплатный")
    max_links = user.get("max_links", 5)
    
    # Получаем товары с аналитикой
    products_analytics = await product_service.get_products_with_analytics(user_id)
    products_count = len(products_analytics)
    
    # Формируем статус
    if products_count == 0:
        status = "🎯 Начните экономить - добавьте первый товар!"
    elif products_count < max_links:
        slots_left = max_links - products_count
        status = f"📦 У вас {products_count} товар(ов). Осталось {slots_left} слот(ов)"
    else:
        status = f"⚠️ Лимит достигнут ({max_links}/{max_links})"
    
    # Подсчёт потенциальной экономии
    total_savings = sum(
        item["savings_amount"]
        for item in products_analytics
        if item["savings_amount"] > 0
    )
    
    savings_text = ""
    if total_savings > 0:
        savings_text = (
            f"💰 <b>Вы можете сэкономить {total_savings}₽</b>\n"
            f"если купите товары по текущим ценам!\n\n"
        )
    elif products_count > 0:
        savings_text = "📈 Пока нет снижений, но я слежу за ценами!\n\n"
    
    await message.answer(
        f"👋 <b>С возвращением, {message.from_user.first_name}!</b>\n\n"
        f"📋 Тариф: <b>{plan_name}</b>\n"
        f"{status}\n\n"
        f"{savings_text}"
        "Продолжайте мониторинг 👇",
        reply_markup=create_smart_menu(products_count, max_links, plan_name),
        parse_mode="HTML"
    )