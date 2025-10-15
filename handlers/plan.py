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
        await query.answer("Неизвестный тариф.")
        return

    # Сохраняем тариф в БД
    await db.set_plan(
        query.from_user.id, plan_key, plan["name"], plan["max_links"]
    )

    # Редактируем сообщение с подтверждением и новым меню
    await query.message.edit_text(
        text=(
            f"✅ Тариф <b>{plan['name']}</b> активирован!\n\n"
            f"Теперь вы можете отслеживать до <b>{plan['max_links']}</b> товаров.\n\n"
            "Выберите действие 👇"
        ),
        parse_mode="HTML",
        reply_markup=main_inline_kb()  # Inline-кнопки для действий
    )