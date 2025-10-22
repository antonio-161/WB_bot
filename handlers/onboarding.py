"""
Обработчики для онбординга новых пользователей.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from services.db import DB
from states.user_states import AddProductState
from keyboards.kb import choose_plan_kb, show_plans_kb, upsell_kb

router = Router()


@router.callback_query(F.data == "onboarding_add_first")
async def onboarding_add_first_product(query: CallbackQuery, state: FSMContext):
    """Пользователь решил сначала добавить товар."""

    await query.message.edit_text(
        "🎯 <b>Отлично! Давайте добавим первый товар</b>\n\n"
        "📎 Отправьте:\n"
        "• Ссылку на товар Wildberries\n"
        "• Артикул товара (например: 123456789)\n\n"
        "💡 <b>Например:</b>\n"
        "<code>https://www.wildberries.ru/catalog/12345678/detail.aspx</code>\n\n"
        "После добавления я покажу текущую цену и предложу выбрать тариф.",
        parse_mode="HTML"
    )

    # Переходим в состояние добавления товара
    await state.set_state(AddProductState.waiting_for_url)
    await state.update_data(onboarding=True)
    await query.answer()


@router.callback_query(F.data == "show_plans_first")
async def show_plans_before_product(query: CallbackQuery):
    """Пользователь хочет сначала посмотреть тарифы."""

    await query.message.edit_text(
        "📋 <b>Выберите тариф:</b>\n\n"
        "Нажмите на тариф, чтобы увидеть подробности 👇",
        parse_mode="HTML",
        reply_markup=choose_plan_kb()
    )
    await query.answer()


@router.callback_query(F.data == "show_upgrade_benefits")
async def show_upgrade_benefits(query: CallbackQuery, db: DB):
    """Показать преимущества платных тарифов."""

    user = await db.get_user(query.from_user.id)
    products = await db.list_products(query.from_user.id)
    current_plan = user.get("plan", "plan_free")

    if current_plan != "plan_free":
        await query.answer("У вас уже активен платный тариф!", show_alert=True)
        return

    # Подсчитываем упущенную выгоду
    potential_items = 50 - len(products)  # Базовый тариф

    await query.message.edit_text(
        "🚀 <b>Расширьте возможности!</b>\n\n"
        f"📦 Сейчас у вас: <b>{len(products)}/5</b> товаров\n\n"
        "💡 <b>С тарифом Базовый (199₽/мес):</b>\n"
        f"✅ До <b>50 товаров</b> (+{potential_items} слотов!)\n"
        "✅ История за <b>3 месяца</b>\n"
        "✅ Ваш <b>ПВЗ</b> для точных цен\n"
        "✅ <b>Умные уведомления</b>\n"
        "✅ <b>Алерты о наличии</b>\n\n"
        "🎯 Окупается с одной покупки!\n\n"
        "Выберите тариф для подробностей:",
        parse_mode="HTML",
        reply_markup=show_plans_kb()
    )
    await query.answer()


@router.callback_query(F.data == "upsell_limit_reached")
async def upsell_when_limit_reached(query: CallbackQuery, db: DB):
    """Показать upsell при достижении лимита."""

    # user = await db.get_user(query.from_user.id)
    products = await db.list_products(query.from_user.id)

    # Подсчитываем потенциальную экономию
    total_savings = 0
    for p in products:
        history = await db.get_price_history(p.id, limit=30)
        if len(history) >= 2:
            prices = [h.product_price for h in history]
            savings = max(prices) - min(prices)
            if savings > 0:
                total_savings += savings

    avg_savings = total_savings // len(products) if products else 0

    msg = (
        "⛔️ <b>Лимит товаров достигнут</b>\n\n"
        f"📦 Вы отслеживаете: <b>{len(products)}/5</b> товаров\n"
    )

    if avg_savings > 0:
        msg += f"💰 Средняя экономия на товар: <b>{avg_savings}₽</b>\n\n"
    else:
        msg += "\n"

    msg += (
        "😔 <b>Что вы упускаете:</b>\n"
        "❌ Не можете добавить новые выгодные товары\n"
        "❌ Теряете потенциальные скидки\n"
        "❌ Видите историю только за месяц\n\n"
        "💡 <b>Решение:</b>\n"
        "С тарифом <b>Базовый</b> (199₽/мес):\n"
        "✅ До 50 товаров (в 10 раз больше!)\n"
        "✅ История за 3 месяца\n"
        "✅ Умные уведомления\n\n"
        "🎁 <b>Окупится с 1 покупки!</b>"
    )

    await query.message.edit_text(
        msg,
        parse_mode="HTML",
        reply_markup=upsell_kb()
    )
    await query.answer()
