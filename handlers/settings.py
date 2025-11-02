"""
Обработчики настроек пользователя.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.user_states import SetDiscountState
from services.user_service import UserService
from services.product_service import ProductService
from services.settings_service import SettingsService
from keyboards.kb import (
    settings_kb, back_to_settings_kb, upgrade_plan_kb, choose_plan_kb,
    main_inline_kb, onboarding_pvz_kb, onboarding_discount_kb, sort_mode_kb,
    simple_kb, btn
)
from handlers.region import cb_set_pvz

router = Router()


# ===== Онбординг =====

async def start_onboarding(
    message: Message,
    user_service: UserService,
    user_id: int,
    plan_key: str
):
    """Начать процесс онбординга нового пользователя."""
    if plan_key == "plan_free":
        intro = (
            "🎯 <b>Давайте настроим бота</b>\n\n"
            "Установите скидку WB кошелька для точного расчёта финальной цены.\n\n"
            "💡 Найти в приложении: WB → Профиль → WB Кошелёк"
        )
    else:
        intro = (
            "🎯 <b>Настроим ваш тариф</b>\n\n"
            "Шаг 1: Установите скидку WB кошелька\n"
            "Это поможет видеть реальную цену с учётом вашей персональной скидки.\n\n"
            "💡 Найти в приложении: WB → Профиль → WB Кошелёк\n\n"
            "⏭ После этого настроим ваш ПВЗ для точных региональных цен"
        )

    await message.answer(
        intro,
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
        parse_mode="HTML",
        reply_markup=simple_kb([btn("⏭ Пропустить", "onboarding_skip_discount")])
    )
    await state.set_state(SetDiscountState.waiting_for_discount)
    await state.update_data(onboarding=True)
    await query.answer()


@router.callback_query(F.data == "onboarding_skip_discount")
async def onboarding_skip_discount(query: CallbackQuery, user_service: UserService):
    """Пропуск установки скидки."""
    user_id = query.from_user.id
    user = await user_service.get_user_info(user_id)
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
async def onboarding_pvz(query: CallbackQuery, state: FSMContext, settings_service: SettingsService):
    """Установка ПВЗ в процессе онбординга."""
    await state.update_data(onboarding=True)
    await cb_set_pvz(query, state, settings_service)


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


# ===== Просмотр настроек =====

@router.callback_query(F.data == "settings")
async def cb_settings(
    query: CallbackQuery,
    state: FSMContext,
    settings_service: SettingsService,
    product_service: ProductService
):
    """Показать настройки пользователя."""
    await state.clear()
    user_id = query.from_user.id
    
    # Получаем настройки
    settings = await settings_service.get_user_settings(user_id)
    
    if not settings.get("exists"):
        await query.answer("Ошибка получения данных", show_alert=True)
        return
    
    # Получаем количество товаров
    products_analytics = await product_service.get_products_with_analytics(user_id)
    used_slots = len(products_analytics)
    
    # ← ДОБАВЛЕНО: Форматируем режим сортировки
    sort_mode = settings.get("sort_mode", "savings")
    sort_mode_text = "По выгодности" if sort_mode == "savings" else "По дате добавления"
    
    text = (
        "⚙️ <b>Ваши настройки</b>\n\n"
        f"📋 Тариф: <b>{settings['plan_name']}</b>\n"
        f"📊 Использовано слотов: <b>{used_slots}/{settings['max_links']}</b>\n"
        f"💳 Скидка WB кошелька: <b>{settings['discount']}%</b>\n"
        f"📍 ПВЗ: <b>{settings['pvz_info']}</b>\n"
        f"🔄 Сортировка: <b>{sort_mode_text}</b>\n\n"  # ← Добавь эту строку
        "Используйте кнопки ниже для изменения настроек."
    )

    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=settings_kb()
    )
    await query.answer()


# ===== Изменение скидки =====

@router.callback_query(F.data == "set_discount")
async def cb_set_discount(
    query: CallbackQuery,
    state: FSMContext,
    settings_service: SettingsService
):
    """Начало установки скидки через callback."""
    user_id = query.from_user.id
    
    settings = await settings_service.get_user_settings(user_id)
    current_discount = settings.get("discount", 0) if settings.get("exists") else 0

    await query.message.answer(
        "💳 <b>Установка скидки WB кошелька</b>\n\n"
        f"Текущая скидка: <b>{current_discount}%</b>\n\n"
        "Введите размер скидки в процентах (целое число от 0 до 100).\n"
        "Например: <code>7</code>\n\n"
        "Эта скидка будет учитываться при расчёте финальной цены.\n\n"
        "Нажмите Назад для отмены.",
        parse_mode="HTML",
        reply_markup=back_to_settings_kb()
    )
    await state.set_state(SetDiscountState.waiting_for_discount)
    await query.answer()


@router.message(SetDiscountState.waiting_for_discount)
async def process_discount(
    message: Message,
    state: FSMContext,
    settings_service: SettingsService,
    user_service: UserService
):
    """Обработка ввода скидки."""
    if message.text == "/cancel":
        await message.answer(
            "❌ Установка скидки отменена",
            reply_markup=settings_kb()
        )
        await state.clear()
        return

    try:
        discount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите целое число от 0 до 100")
        return
    
    # Обновляем скидку через сервис
    success, msg = await settings_service.update_discount(message.from_user.id, discount)
    
    if not success:
        await message.answer(f"❌ {msg}")
        return
    
    await message.answer(
        f"✅ <b>{msg}</b>\n\n"
        "Она будет учитываться при отображении цен.",
        parse_mode="HTML",
        reply_markup=back_to_settings_kb()
    )
    
    # Проверяем онбординг
    data = await state.get_data()
    is_onboarding = data.get("onboarding", False)

    if is_onboarding:
        user = await user_service.get_user_info(message.from_user.id)
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


# ===== Просмотр тарифа =====

@router.callback_query(F.data == "my_plan")
async def cb_my_plan(
    query: CallbackQuery,
    user_service: UserService,
    product_service: ProductService
):
    """Показать информацию о текущем тарифе."""
    user_id = query.from_user.id
    
    user = await user_service.get_user_info(user_id)
    
    if not user:
        await query.answer("Ошибка получения данных", show_alert=True)
        return

    plan_name = user.get("plan_name", "Не установлен")
    max_links = user.get("max_links", 5)

    products_analytics = await product_service.get_products_with_analytics(user_id)
    used_slots = len(products_analytics)

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


# ===== Сортировка товаров =====
@router.callback_query(F.data == "set_sort_mode")
async def cb_set_sort_mode(query: CallbackQuery, settings_service: SettingsService):
    """Выбор режима сортировки товаров."""
    user_id = query.from_user.id
    
    # ← ИСПРАВЛЕНО: Получаем из БД через сервис
    settings = await settings_service.get_user_settings(user_id)
    current_mode = settings.get("sort_mode", "savings")
    
    current_text = "По выгодности" if current_mode == "savings" else "По дате добавления"
    
    text = (
        "📊 <b>Сортировка товаров</b>\n\n"
        f"Текущий режим: <b>{current_text}</b>\n\n"
        "Выберите режим сортировки:"
    )

    await query.message.edit_text(text, parse_mode="HTML", reply_markup=sort_mode_kb(current_mode))
    await query.answer()


@router.callback_query(F.data.startswith("sort_mode:"))
async def cb_apply_sort_mode(
    query: CallbackQuery,
    settings_service: SettingsService
):
    """Применить режим сортировки."""
    mode = query.data.split(":", 1)[1]  # "savings" или "date"
    user_id = query.from_user.id

    success, msg = await settings_service.update_sort_mode(user_id, mode)

    if success:
        mode_name = "По выгодности" if mode == "savings" else "По дате добавления"
        await query.answer(f"✅ Сортировка: {mode_name}")

        await query.message.edit_text(
            f"✅ <b>Режим сортировки обновлён</b>\n\n"
            f"Теперь товары сортируются: <b>{mode_name}</b>",
            parse_mode="HTML",
            reply_markup=back_to_settings_kb()
        )
    else:
        await query.answer(f"❌ {msg}", show_alert=True)
