from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import DB
from keyboards.kb import main_inline_kb

router = Router()

PLANS = {
    "plan_free": {"name": "Бесплатный", "max_links": 5},
    "plan_basic": {"name": "Базовый", "max_links": 50},
    "plan_pro": {"name": "Продвинутый", "max_links": 250},
}


@router.callback_query(F.data.startswith("plan_"))
async def choose_plan_callback(query: CallbackQuery, db: DB):
    """Обработка выбора тарифа через InlineKeyboard."""
    plan_key = query.data
    plan = PLANS.get(plan_key)

    if not plan:
        await query.answer("❌ Неизвестный тариф", show_alert=True)
        return

    # Сохраняем тариф в БД (исправлено: 4 параметра)
    await db.set_plan(
        user_id=query.from_user.id,
        plan_key=plan_key,
        plan_name=plan["name"],
        max_links=plan["max_links"]
    )

    # Формируем описание тарифа
    plan_description = {
        "plan_free": "🎁 Отличный старт для знакомства с сервисом!",
        "plan_basic": "💼 Оптимальный выбор для активных покупателей.",
        "plan_pro": "🚀 Максимальные возможности для профессионалов!"
    }

    description = plan_description.get(plan_key, "")

    # Редактируем сообщение с подтверждением
    await query.message.edit_text(
        text=(
            f"✅ <b>Тариф активирован!</b>\n\n"
            f"📋 Выбран: <b>{plan['name']}</b>\n"
            f"📊 Лимит товаров: <b>{plan['max_links']}</b>\n\n"
            f"{description}\n\n"
            "Теперь вы можете добавлять товары для отслеживания 👇"
        ),
        parse_mode="HTML",
        reply_markup=main_inline_kb()
    )

    await query.answer(
        f"✅ Тариф {plan['name']} активирован!", show_alert=False
    )
