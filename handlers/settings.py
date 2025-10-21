from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.user_states import SetDiscountState
from services.db import DB
from keyboards.kb import (
    settings_kb, back_to_settings_kb, upgrade_plan_kb, choose_plan_kb,
    main_inline_kb, onboarding_pvz_kb
)

router = Router()


async def start_onboarding(message, db: DB, user_id: int, plan_key: str):
    """Начать процесс онбординга нового пользователя."""
    from keyboards.kb import onboarding_discount_kb

    await message.answer(
        "🎯 <b>Настройка отслеживания</b>\n\n"
        "Для более точного расчёта цен установите скидку вашего WB кошелька.\n\n"
        "💡 Найти можно в приложении WB → Профиль → WB Кошелёк",
        parse_mode="HTML",
        reply_markup=onboarding_discount_kb()
    )


@router.callback_query(F.data == "onboarding_set_discount")
async def onboarding_discount(query: CallbackQuery, state: FSMContext):
    """Установка скидки в процессе онбординга."""
    await query.message.edit_text(
        "💳 <b>Установка скидки WB кошелька</b>\n\n"
        "Введите размер скидки в процентах (целое число от 0 до 100).\n"
        "Например: <code>7</code>\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML"
    )
    await state.set_state(SetDiscountState.waiting_for_discount)
    await state.update_data(onboarding=True)
    await query.answer()


@router.callback_query(F.data == "onboarding_skip_discount")
async def onboarding_skip_discount(query: CallbackQuery, db: DB):
    """Пропуск установки скидки."""
    user = await db.get_user(query.from_user.id)
    plan = user.get("plan", "plan_free") if user else "plan_free"

    if plan in ["plan_basic", "plan_pro"]:
        await query.message.edit_text(
            "📍 <b>Настройка региона</b>\n\n"
            "Установите ваш пункт выдачи для точного отображения цен и остатков.\n\n"
            "💡 По умолчанию используется Москва",
            parse_mode="HTML",
            reply_markup=onboarding_pvz_kb()
        )
    else:
        await query.message.edit_text(
            "✅ <b>Настройка завершена!</b>\n\n"
            "Теперь вы можете добавлять товары для отслеживания 👇",
            parse_mode="HTML",
            reply_markup=main_inline_kb()
        )
    await query.answer()


@router.callback_query(F.data == "onboarding_set_pvz")
async def onboarding_pvz(query: CallbackQuery, state: FSMContext):
    """Установка ПВЗ в процессе онбординга."""
    from handlers.region import cb_set_pvz
    await state.update_data(onboarding=True)
    await cb_set_pvz(query, state, query.bot.get("db"))


@router.callback_query(F.data == "onboarding_skip_pvz")
async def onboarding_skip_pvz(query: CallbackQuery):
    """Пропуск установки ПВЗ."""
    await query.message.edit_text(
        "✅ <b>Настройка завершена!</b>\n\n"
        "Используется регион: <b>Москва</b>\n\n"
        "Теперь вы можете добавлять товары для отслеживания 👇",
        parse_mode="HTML",
        reply_markup=main_inline_kb()
    )
    await query.answer()


@router.callback_query(F.data == "settings")
async def cb_settings(query: CallbackQuery, db: DB):
    """Показать настройки пользователя."""
    user = await db.get_user(query.from_user.id)

    if not user:
        await query.answer("Ошибка получения данных", show_alert=True)
        return

    discount = user.get("discount_percent", 0)
    plan_name = user.get("plan_name", "Не установлен")
    max_links = user.get("max_links", 5)
    dest = user.get("dest", -1257786)
    pvz_address = user.get("pvz_address")

    products = await db.list_products(query.from_user.id)
    used_slots = len(products)

    # Определяем информацию о ПВЗ
    from constants import DEFAULT_DEST
    if dest == DEFAULT_DEST or not dest:
        pvz_info = "Москва (по умолчанию)"
    elif pvz_address:
        pvz_info = pvz_address
    else:
        pvz_info = f"Код: {dest}"

    text = (
        "⚙️ <b>Ваши настройки</b>\n\n"
        f"📋 Тариф: <b>{plan_name}</b>\n"
        f"📊 Использовано слотов: <b>{used_slots}/{max_links}</b>\n"
        f"💳 Скидка WB кошелька: <b>{discount}%</b>\n"
        f"📍 ПВЗ: <b>{pvz_info}</b>\n\n"
        "Используйте кнопки ниже для изменения настроек."
    )

    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=settings_kb()
    )
    await query.answer()


@router.callback_query(F.data == "set_discount")
async def cb_set_discount(query: CallbackQuery, state: FSMContext, db: DB):
    """Начало установки скидки через callback."""
    user = await db.get_user(query.from_user.id)
    current_discount = user.get("discount_percent", 0) if user else 0

    await query.message.answer(
        "💳 <b>Установка скидки WB кошелька</b>\n\n"
        f"Текущая скидка: <b>{current_discount}%</b>\n\n"
        "Введите размер скидки в процентах (целое число от 0 до 100).\n"
        "Например: <code>7</code>\n\n"
        "Эта скидка будет учитываться при расчёте финальной цены.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML"
    )
    await state.set_state(SetDiscountState.waiting_for_discount)
    await query.answer()


@router.message(SetDiscountState.waiting_for_discount)
async def process_discount(message: Message, state: FSMContext, db: DB):
    """Установка скидки."""
    if message.text == "/cancel":
        await message.answer(
            "❌ Установка скидки отменена", reply_markup=settings_kb()
        )
        await state.clear()
        return

    try:
        v = int(message.text.strip())
        if v < 0 or v > 100:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Неверный формат.\n"
            "Введите целое число от 0 до 100."
        )
        return

    await db.ensure_user(message.from_user.id)
    await db.set_discount(message.from_user.id, v)

    await message.answer(
        f"✅ Скидка WB кошелька установлена: <b>{v}%</b>\n\n"
        "Она будет учитываться при отображении цен.",
        parse_mode="HTML",
        reply_markup=back_to_settings_kb()
    )
    data = await state.get_data()
    is_onboarding = data.get("onboarding", False)

    if is_onboarding:
        user = await db.get_user(message.from_user.id)
        plan = user.get("plan", "plan_free") if user else "plan_free"

        if plan in ["plan_basic", "plan_pro"]:
            
            await message.answer(
                "📍 <b>Настройка региона</b>\n\n"
                "Установите ваш пункт выдачи для точного отображения цен и остатков.\n\n"
                "💡 По умолчанию используется Москва",
                parse_mode="HTML",
                reply_markup=onboarding_pvz_kb()
            )
        else:
            await message.answer(
                "✅ <b>Настройка завершена!</b>\n\n"
                "Теперь вы можете добавлять товары для отслеживания 👇",
                parse_mode="HTML",
                reply_markup=main_inline_kb()
            )

    await state.clear()


@router.callback_query(F.data == "my_plan")
async def cb_my_plan(query: CallbackQuery, db: DB):
    """Показать информацию о текущем тарифе."""
    user = await db.get_user(query.from_user.id)

    if not user:
        await query.answer("Ошибка получения данных", show_alert=True)
        return

    plan_name = user.get("plan_name", "Не установлен")
    max_links = user.get("max_links", 5)

    products = await db.list_products(query.from_user.id)
    used_slots = len(products)

    text = (
        f"💳 <b>Ваш тариф: {plan_name}</b>\n\n"
        f"📊 Лимит товаров: <b>{max_links}</b>\n"
        f"📦 Используется: <b>{used_slots}</b>\n"
        f"🆓 Свободно: <b>{max_links - used_slots}</b>\n\n"
    )

    if max_links == 5:
        text += (
            "🎁 Вы используете бесплатный тариф.\n\n"
            "Хотите отслеживать больше товаров?\n"
            "Обратитесь к администратору для смены тарифа."
        )

    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=upgrade_plan_kb()
    )
    await query.answer()


@router.callback_query(F.data == "upgrade_plan")
async def cb_upgrade_plan(query: CallbackQuery):
    """Показать доступные тарифы для улучшения."""
    await query.message.edit_text(
        "📋 <b>Выберите новый тариф:</b>\n\n"
        "🎁 <b>Бесплатный</b> — до 5 товаров\n"
        "💼 <b>Базовый</b> — до 50 товаров\n"
        "🚀 <b>Продвинутый</b> — до 250 товаров\n\n"
        "Для смены тарифа выберите один из вариантов ниже:",
        parse_mode="HTML",
        reply_markup=choose_plan_kb()
    )
    await query.answer()
