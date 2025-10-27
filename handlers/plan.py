"""
Обработчики для работы с тарифами.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from services.user_service import UserService
from handlers.settings import start_onboarding
from keyboards.kb import main_inline_kb, plan_detail_kb, choose_plan_kb
from constants import PLAN_DESCRIPTIONS

router = Router()

PLANS = {
    "plan_free": {"name": "Бесплатный", "max_links": 5},
    "plan_basic": {"name": "Базовый", "max_links": 50},
    "plan_pro": {"name": "Продвинутый", "max_links": 250},
}


@router.callback_query(F.data.startswith("plan_"))
async def show_plan_details(query: CallbackQuery):
    """Показать детальное описание тарифа."""
    plan_key = query.data
    
    if plan_key not in PLAN_DESCRIPTIONS:
        await query.answer("❌ Неизвестный тариф", show_alert=True)
        return
    
    plan_info = PLAN_DESCRIPTIONS[plan_key]
    
    text = (
        f"{plan_info['name']}\n"
        f"💰 <b>Стоимость:</b> {plan_info['price']}\n\n"
        f"{plan_info['description']}"
    )
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=plan_detail_kb(plan_key)
    )
    await query.answer()


@router.callback_query(F.data.startswith("confirm_plan_"))
async def confirm_plan_callback(
    query: CallbackQuery,
    user_service: UserService
):
    """Подтверждение выбора тарифа."""
    plan_key = query.data.replace("confirm_", "")
    plan = PLANS.get(plan_key)

    if not plan:
        await query.answer("❌ Неизвестный тариф", show_alert=True)
        return

    user_id = query.from_user.id

    # Обновляем тариф через сервис
    success = await user_service.update_plan(
        user_id,
        plan_key,
        plan["name"],
        plan["max_links"]
    )
    
    if not success:
        await query.answer("❌ Ошибка при обновлении тарифа", show_alert=True)
        return

    # Формируем персонализированное сообщение
    if plan_key == "plan_free":
        next_steps = (
            "🎯 <b>Что дальше?</b>\n"
            "1️⃣ Добавьте до 5 товаров для отслеживания\n"
            "2️⃣ Настройте скидку WB кошелька (опционально)\n"
            "3️⃣ Получайте уведомления о снижении цен\n\n"
            "💡 Когда понадобится больше слотов — улучшите тариф!"
        )
    elif plan_key == "plan_basic":
        next_steps = (
            "🎯 <b>Рекомендуем настроить:</b>\n"
            "1️⃣ Добавьте товары (до 50 шт)\n"
            "2️⃣ Установите свой ПВЗ для точных цен\n"
            "3️⃣ Настройте скидку WB кошелька\n"
            "4️⃣ Настройте умные уведомления (по % или порогу)\n\n"
            "🔥 Максимум пользы от тарифа!"
        )
    else:  # pro
        next_steps = (
            "🎯 <b>Используйте все возможности:</b>\n"
            "1️⃣ Добавьте до 250 товаров\n"
            "2️⃣ Установите свой ПВЗ\n"
            "3️⃣ Настройте скидку WB кошелька\n"
            "4️⃣ Отслеживайте остатки на складах\n"
            "5️⃣ Экспортируйте данные в Excel/CSV\n\n"
            "💎 У вас максимальный функционал!"
        )

    await query.message.edit_text(
        text=(
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"📋 Активирован тариф: <b>{plan['name']}</b>\n"
            f"📊 Лимит товаров: <b>{plan['max_links']}</b>\n\n"
            f"{next_steps}"
        ),
        parse_mode="HTML",
        reply_markup=main_inline_kb()
    )

    # Запускаем онбординг для платных тарифов
    if plan_key in ["plan_basic", "plan_pro"]:
        await start_onboarding(query.message, user_service, user_id, plan_key)

    await query.answer(f"✅ Тариф {plan['name']} активирован!", show_alert=False)


@router.callback_query(F.data == "back_to_plan_choice")
async def back_to_plan_choice(query: CallbackQuery):
    """Возврат к выбору тарифа."""
    await query.message.edit_text(
        "📋 <b>Выберите тариф:</b>\n\n"
        "Нажмите на тариф чтобы увидеть подробности 👇",
        parse_mode="HTML",
        reply_markup=choose_plan_kb()
    )
    await query.answer()
