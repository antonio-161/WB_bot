from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from services.db import DB
from keyboards.kb import create_smart_menu, start_kb
from utils.wb_utils import calculate_potential_savings

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, db: DB):
    """Новый онбординг: Value-First подход."""

    existing_user = await db.get_user(message.from_user.id)

    # ===== НОВЫЙ ПОЛЬЗОВАТЕЛЬ - показываем ценность СРАЗУ =====
    if not existing_user:
        await db.ensure_user(message.from_user.id)

        # Эмоциональный хук + конкретный пример
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
    plan = existing_user.get("plan_name", "Бесплатный")
    products = await db.list_products(message.from_user.id)
    max_links = existing_user.get("max_links", 5)

    # Персонализированное приветствие с достижениями
    if len(products) == 0:
        status = "🎯 Начните экономить - добавьте первый товар!"
    elif len(products) < max_links:
        slots_left = max_links - len(products)
        status = f"📦 У вас {len(products)} товар(ов). Осталось {slots_left} слот(ов)"
    else:
        status = f"⚠️ Лимит достигнут ({max_links}/{max_links})"

    # Добавляем статистику потенциальной экономии
    savings_text = await calculate_potential_savings(db, message.from_user.id)

    await message.answer(
        f"👋 <b>С возвращением, {message.from_user.first_name}!</b>\n\n"
        f"📋 Тариф: <b>{plan}</b>\n"
        f"{status}\n\n"
        f"{savings_text}"
        "Продолжайте мониторинг 👇",
        reply_markup=create_smart_menu(len(products), max_links, plan),
        parse_mode="HTML"
    )
