from aiogram import Router, F
from aiogram.types import CallbackQuery
from handlers.settings import start_onboarding
from services.db import DB
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
async def confirm_plan_callback(query: CallbackQuery, db: DB):
    """Подтверждение выбора тарифа."""
    plan_key = query.data.replace("confirm_", "")
    plan = PLANS.get(plan_key)

    if not plan:
        await query.answer("❌ Неизвестный тариф", show_alert=True)
        return

    # Сохраняем тариф в БД
    await db.set_plan(
        user_id=query.from_user.id,
        plan_key=plan_key,
        plan_name=plan["name"],
        max_links=plan["max_links"]
    )

    # Редактируем сообщение с подтверждением
    await query.message.edit_text(
        text=(
            f"✅ <b>Тариф активирован!</b>\n\n"
            f"📋 Выбран: <b>{plan['name']}</b>\n"
            f"📊 Лимит товаров: <b>{plan['max_links']}</b>\n\n"
            "Теперь настроим параметры отслеживания 👇"
        ),
        parse_mode="HTML",
        reply_markup=main_inline_kb()
    )

    # Запускаем процесс настройки (импорт внутри функции чтобы избежать циклических импортов)
    await start_onboarding(query.message, db, query.from_user.id, plan_key)

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
