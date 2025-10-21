from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.user_states import SetPVZState
from services.db import DB
from services.pvz_finder import get_dest_by_address
from keyboards.kb import reset_pvz_kb, back_to_settings_kb, main_inline_kb
from utils.decorators import require_plan
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "set_pvz")
@require_plan(['plan_basic', 'plan_pro'], "⛔ Установка ПВЗ доступна только на платных тарифах")
async def cb_set_pvz(query: CallbackQuery, state: FSMContext, db: DB):
    """Начало установки ПВЗ через callback."""
    user = await db.get_user(query.from_user.id)

    current_dest = user.get('dest') if user else None
    current_info = ""

    if current_dest and current_dest != -1257786:
        current_info = f"\n\n📍 <b>Текущий ПВЗ:</b> установлен (код: {current_dest})"
    else:
        current_info = "\n\n📍 <b>Текущий ПВЗ:</b> не установлен (используется Москва по умолчанию)"

    await query.message.answer(
        "📍 <b>Установка адреса пункта выдачи</b>\n\n"
        "Введите адрес Вашего пункта выдачи заказов "
        "<b>точно так же, как в приложении или на сайте Wildberries</b>.\n\n"
        "📝 <b>Примеры:</b>\n"
        "• <code>Москва, ул. Ленина, 10</code>\n"
        "• <code>Санкт-Петербург, Невский проспект, 28</code>\n"
        "• <code>Екатеринбург, ул. Мира, 5</code>\n\n"
        "💡 <b>Важно:</b> Адрес должен быть максимально точным, "
        "как вы вводите его при поиске ПВЗ на сайте WB."
        f"{current_info}\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML"
    )

    await state.set_state(SetPVZState.waiting_for_address)
    await query.answer()


@router.message(SetPVZState.waiting_for_address)
async def process_pvz_address(message: Message, state: FSMContext, db: DB):
    """Обработка ввода адреса ПВЗ."""
    if message.text == "/cancel":
        await message.answer("❌ Установка ПВЗ отменена", reply_markup=back_to_settings_kb())
        await state.clear()
        return
    
    address = message.text.strip()

    if len(address) < 5:
        await message.answer(
            "❌ Адрес слишком короткий.\n"
            "Введите полный адрес ПВЗ.",
            reply_markup=back_to_settings_kb()
        )
        await state.clear()
        return

    # Отправляем статус сообщение
    status_msg = await message.answer(
        "🔄 <b>Ищу ваш пункт выдачи...</b>\n\n"
        "⏳ Это может занять до 30 секунд.\n"
        "Пожалуйста, подождите...",
        parse_mode="HTML"
    )

    try:
        # Запускаем Playwright скрипт
        dest = await get_dest_by_address(address)

        if not dest:
            await status_msg.edit_text(
                "❌ <b>Не удалось найти пункт выдачи</b>\n\n"
                "Возможные причины:\n"
                "• Адрес введён некорректно\n"
                "• ПВЗ по этому адресу не найден на WB\n"
                "• Технические проблемы с сайтом WB\n\n"
                "💡 <b>Попробуйте:</b>\n"
                "1. Проверить адрес на сайте wildberries.ru\n"
                "2. Ввести адрес по-другому\n"
                "3. Указать более точный адрес",
                parse_mode="HTML",
                reply_markup=back_to_settings_kb()
            )
            await state.clear()
            return

        # Сохраняем в БД
        await db.ensure_user(message.from_user.id)
        await db.set_pvz(message.from_user.id, dest, address)

        await status_msg.edit_text(
            f"✅ <b>Пункт выдачи установлен!</b>\n\n"
            f"📍 <b>Адрес:</b> {address}\n"
            f"🔢 <b>Код региона:</b> <code>{dest}</code>\n\n"
            f"Теперь все цены товаров будут отображаться для вашего региона доставки.",
            parse_mode="HTML",
            reply_markup=back_to_settings_kb()
        )

        logger.info(
            f"Пользователь {message.from_user.id} установил ПВЗ: "
            f"dest={dest}, address={address}"
        )

    except Exception as e:
        logger.exception(f"Ошибка при установке ПВЗ: {e}")
        await status_msg.edit_text(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Не удалось определить пункт выдачи.\n"
            "Попробуйте позже или используйте другой адрес.",
            parse_mode="HTML",
            reply_markup=back_to_settings_kb()
        )

    data = await state.get_data()
    is_onboarding = data.get("onboarding", False)

    if is_onboarding:
        await message.answer(
            "✅ <b>Настройка завершена!</b>\n\n"
            "Теперь вы можете добавлять товары для отслеживания 👇",
            parse_mode="HTML",
            reply_markup=main_inline_kb()
        )

    await state.clear()


@router.callback_query(F.data == "show_pvz")
async def cb_show_pvz(query: CallbackQuery, db: DB):
    """Показать текущий ПВЗ."""
    user = await db.get_user(query.from_user.id)

    if not user:
        await query.answer("Ошибка получения данных", show_alert=True)
        return

    dest = user.get("dest")
    pvz_address = user.get("pvz_address")

    from constants import DEFAULT_DEST

    if dest == DEFAULT_DEST or not dest:
        text = (
            f"📍 <b>Пункт выдачи не установлен</b>\n\n"
            f"По умолчанию используется: <b>Москва</b>\n"
            f"Код региона: <code>{DEFAULT_DEST}</code>\n\n"
            f"💡 Установите ваш ПВЗ, чтобы видеть точные цены для вашего региона."
        )
    else:
        text = (
            f"📍 <b>Ваш пункт выдачи</b>\n\n"
            f"Адрес: <b>{pvz_address or 'Установлен'}</b>\n"
            f"Код региона: <code>{dest}</code>\n\n"
            f"💡 Цены отображаются для вашего региона."
        )

    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=reset_pvz_kb()
    )
    await query.answer()


@router.callback_query(F.data == "reset_pvz")
async def cb_reset_pvz(query: CallbackQuery, db: DB):
    """Сброс ПВЗ на Москву по умолчанию."""
    from constants import DEFAULT_DEST

    await db.ensure_user(query.from_user.id)
    await db.set_pvz(query.from_user.id, DEFAULT_DEST, None)

    await query.message.edit_text(
        "✅ <b>ПВЗ сброшен</b>\n\n"
        "Установлен регион по умолчанию: <b>Москва</b>\n"
        f"Код региона: <code>{DEFAULT_DEST}</code>",
        parse_mode="HTML",
        reply_markup=back_to_settings_kb()
    )
    await query.answer("ПВЗ сброшен на Москву")
