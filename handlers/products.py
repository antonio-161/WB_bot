"""
Обработчики для работы с товарами.
Только получение данных, вызов сервисов, отправка ответа.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from states.user_states import AddProductState, RenameProductState, SetNotifyState
from services.container import Container
from services.user_service import UserService
from services.product_service import ProductService
from services.settings_service import SettingsService
from utils.wb_utils import extract_nm_id
from utils.formatters import (
    format_product_added_message,
    format_product_with_size_added,
    format_products_list,
    format_product_detail,
    format_filtered_products
)
from utils.graph_generator import generate_price_graph
from utils.decorators import require_plan
from keyboards.kb import (
    main_inline_kb, sizes_inline_kb, onboarding_kb,
    products_list_kb, product_detail_kb, confirm_remove_kb,
    back_to_product_kb, notify_mode_kb, remove_products_kb
)
from models import PriceHistoryRow
import logging

router = Router()
logger = logging.getLogger(__name__)


# ============= ДОБАВЛЕНИЕ ТОВАРА =============

@router.callback_query(F.data == "add_product")
async def cb_add_url_or_article(query: CallbackQuery, state: FSMContext):
    """Запрос ссылки/артикула."""
    await query.message.answer(
        "📎 <b>Добавление товара</b>\n\n"
        "Отправьте:\n"
        "• Ссылку на товар Wildberries\n"
        "• Артикул товара (например: 123456789)\n\n"
        "Лимит зависит от вашего тарифа.",
        parse_mode="HTML"
    )
    await state.set_state(AddProductState.waiting_for_url)
    await query.answer()


@router.message(AddProductState.waiting_for_url)
async def add_product(
    message: Message,
    state: FSMContext,
    user_service: UserService,
    product_service: ProductService,
    settings_service: SettingsService
):
    """Обработка ввода ссылки/артикула."""
    # Извлекаем данные
    nm = extract_nm_id(message.text.strip())
    user_id = message.from_user.id

    if not nm:
        await message.answer(
            "❌ Не удалось распознать артикул.\n\n"
            "Отправьте:\n• Ссылку на товар WB\n• Артикул (6-12 цифр)"
        )
        return

    # Проверка лимитов через сервис
    can_add, reason = await user_service.can_add_product(user_id)
    
    if not can_add:
        await message.answer(
            f"⛔ {reason}\nУдалите старый товар или обновите тариф.",
            reply_markup=main_inline_kb()
        )
        await state.clear()
        return

    status_msg = await message.answer("⏳ Получаю информацию о товаре...")

    try:
        # Получаем настройки
        settings = await settings_service.get_user_settings(user_id)
        dest = settings.get("dest")
        discount = settings.get("discount", 0)
        
        # Формируем URL
        url = f"https://www.wildberries.ru/catalog/{nm}/detail.aspx"
        
        # Добавляем товар через сервис
        success, msg, product_id, product_data = await product_service.add_product(
            user_id, nm, url, dest
        )
        
        if not success:
            await status_msg.edit_text(
                f"⚠️ {msg}",
                reply_markup=main_inline_kb()
            )
            await state.clear()
            return
        
        # Проверяем размеры
        sizes = product_data.get("sizes", [])
        valid_sizes = [
            s for s in sizes 
            if s.get("name") not in ("", "0", None)
            and s.get("origName") not in ("", "0", None)
        ]

        # Если есть размеры — предлагаем выбрать
        if valid_sizes:
            await state.update_data(
                url=url,
                nm=nm,
                product_id=product_id,
                product_name=product_data.get("name", f"Товар {nm}")
            )

            await status_msg.edit_text(
                f"📦 <b>{product_data.get('name')}</b>\n"
                f"🔢 Артикул: <code>{nm}</code>\n\n"
                "Выберите размер для отслеживания:",
                reply_markup=sizes_inline_kb(nm, valid_sizes),
                parse_mode="HTML"
            )
            await state.set_state(AddProductState.waiting_for_size)
        else:
            # Товар без размеров
            size_data = sizes[0] if sizes else {}
            price_info = size_data.get("price", {})
            product_price = price_info.get("product", 0)
            
            # Проверяем онбординг
            data = await state.get_data()
            is_onboarding = data.get("onboarding", False)

            # Форматируем и отправляем
            formatted_msg = format_product_added_message(
                product_data.get("name", f"Товар {nm}"),
                nm,
                product_price,
                discount,
                is_onboarding
            )

            await status_msg.edit_text(
                formatted_msg,
                reply_markup=onboarding_kb() if is_onboarding else main_inline_kb(),
                parse_mode="HTML"
            )

            await state.clear()

    except Exception as e:
        logger.exception(f"Ошибка при добавлении товара {nm}: {e}")
        await status_msg.edit_text(
            "❌ Произошла ошибка при добавлении товара. Попробуйте позже."
        )
        await state.clear()


@router.callback_query(F.data.startswith("select_size:"), AddProductState.waiting_for_size)
async def select_size_cb(
    query: CallbackQuery,
    state: FSMContext,
    product_service: ProductService,
    settings_service: SettingsService
):
    """Выбор размера товара."""
    # Извлекаем данные
    _, nm_str, size_name = query.data.split(":", 2)
    nm = int(nm_str)
    user_id = query.from_user.id

    data = await state.get_data()
    product_id = data.get("product_id")
    product_name = data.get("product_name")

    if not product_id or not product_name:
        await query.answer(
            "❌ Произошла ошибка, попробуйте добавить товар заново.",
            show_alert=True
        )
        await state.clear()
        return

    try:
        # Обновляем размер через сервис
        settings = await settings_service.get_user_settings(user_id)
        dest = settings.get("dest")
        
        success, msg = await product_service.update_product_size(
            product_id,
            size_name,
            nm,
            dest
        )
        
        if not success:
            await query.answer(f"❌ {msg}", show_alert=True)
            await state.clear()
            return

        # Форматируем и отправляем
        formatted_msg = format_product_with_size_added(product_name, nm, size_name)

        await query.message.edit_text(
            formatted_msg,
            parse_mode="HTML",
            reply_markup=main_inline_kb()
        )
        await query.answer("Размер выбран!")
        await state.clear()

    except Exception as e:
        logger.exception(f"Ошибка при выборе размера: {e}")
        await query.answer("❌ Произошла ошибка при выборе размера.", show_alert=True)
        await state.clear()


# ============= СПИСОК ТОВАРОВ =============

@router.callback_query(F.data == "list_products")
async def cb_list_products(
    query: CallbackQuery,
    user_service: UserService,
    product_service: ProductService,
    settings_service: SettingsService
):
    """Показать список товаров с аналитикой."""
    user_id = query.from_user.id
    
    # Получаем данные через сервисы
    products_analytics = await product_service.get_products_with_analytics(user_id)
    
    if not products_analytics:
        await query.message.edit_text(
            "📭 <b>Список пуст</b>\n\n"
            "Вы ещё не добавили товары для отслеживания.\n\n"
            "💡 Добавьте первый товар, чтобы начать экономить!",
            parse_mode="HTML",
            reply_markup=products_list_kb([], False, False, False)
        )
        await query.answer()
        return
    
    user = await user_service.get_user_info(user_id)
    settings = await settings_service.get_user_settings(user_id)
    
    discount = settings.get("discount", 0)
    plan = user.get("plan", "plan_free")
    max_links = user.get("max_links", 5)
    
    # Подсчёт аналитики
    total_current_price = sum(
        p["product"].get("last_product_price", 0)
        for p in products_analytics
    )
    
    total_potential_savings = sum(
        p["savings_amount"]
        for p in products_analytics
    )
    
    best_deal = None
    best_deal_percent = 0
    for item in products_analytics:
        if item["savings_percent"] > best_deal_percent:
            best_deal_percent = item["savings_percent"]
            best_deal = item["product"]
    
    # Форматируем сообщение
    formatted_msg = format_products_list(
        products_analytics,
        total_current_price,
        total_potential_savings,
        best_deal,
        best_deal_percent,
        discount,
        plan,
        max_links,
        page=1
    )
    
    # Формируем данные для клавиатуры
    products_data = [
        {
            "nm_id": item["product"]["nm_id"],
            "display_name": (
                item["product"].get("custom_name") or 
                item["product"].get("name_product", "")
            )
        }
        for item in products_analytics
    ]
    
    # Отправляем ответ
    await query.message.edit_text(
        formatted_msg,
        parse_mode="HTML",
        reply_markup=products_list_kb(
            products=products_data,
            has_filters=(plan in ["plan_basic", "plan_pro"]),
            show_export=(plan == "plan_pro"),
            show_upgrade=(plan == "plan_free" and len(products_analytics) >= 3)
        )
    )
    await query.answer()


@router.callback_query(F.data.startswith("page:"))
async def cb_products_page(
    query: CallbackQuery,
    user_service: UserService,
    product_service: ProductService,
    settings_service: SettingsService
):
    """Переход между страницами списка товаров."""
    user_id = query.from_user.id

    # Получаем номер страницы из callback_data
    page_str = query.data.split(":")[1]
    page = int(page_str)

    # Получаем актуальные данные пользователя
    products_analytics = await product_service.get_products_with_analytics(user_id)
    if not products_analytics:
        await query.answer("Нет товаров для отображения", show_alert=True)
        return

    user = await user_service.get_user_info(user_id)
    settings = await settings_service.get_user_settings(user_id)

    discount = settings.get("discount", 0)
    plan = user.get("plan", "plan_free")
    max_links = user.get("max_links", 5)

    # Подсчёт аналитики
    total_current_price = sum(p["product"].get("last_product_price", 0) for p in products_analytics)
    total_potential_savings = sum(p["savings_amount"] for p in products_analytics)

    best_deal = None
    best_deal_percent = 0
    for item in products_analytics:
        if item["savings_percent"] > best_deal_percent:
            best_deal_percent = item["savings_percent"]
            best_deal = item["product"]

    # Формируем список товаров для клавиатуры
    products_data = [
        {
            "nm_id": item["product"]["nm_id"],
            "display_name": item["product"].get("custom_name") or item["product"].get("name_product", "")
        }
        for item in products_analytics
    ]

    # 🧩 Форматируем текст (теперь с параметром `page`)
    formatted_msg = format_products_list(
        products_analytics,
        total_current_price,
        total_potential_savings,
        best_deal,
        best_deal_percent,
        discount,
        plan,
        max_links,
        page=page,           # <<< вот ключевое
        per_page=5
    )

    # 🎛️ Создаём клавиатуру с той же страницей
    kb = products_list_kb(
        products=products_data,
        has_filters=(plan in ["plan_basic", "plan_pro"]),
        show_export=(plan == "plan_pro"),
        show_upgrade=(plan == "plan_free" and len(products_analytics) >= 3),
        page=page
    )

    # 📝 Обновляем сообщение
    await query.message.edit_text(
        formatted_msg,
        parse_mode="HTML",
        reply_markup=kb
    )

    await query.answer()



# ============= ФИЛЬТРЫ =============

@router.callback_query(F.data == "filter_best_deals")
@require_plan(['plan_basic', 'plan_pro'], "⛔ Фильтры доступны только на платных тарифах")
async def filter_best_deals(
    query: CallbackQuery,
    product_service: ProductService,
    settings_service: SettingsService,
    user_service: UserService
):
    """Показать товары с лучшими скидками."""
    user_id = query.from_user.id
    
    # Получаем отфильтрованные товары через сервис
    filtered = await product_service.filter_best_deals(user_id, min_savings_percent=15.0)
    
    if not filtered:
        await query.answer(
            "😔 Сейчас нет товаров со значительными скидками.\nПродолжайте мониторинг!",
            show_alert=True
        )
        return
    
    settings = await settings_service.get_user_settings(user_id)
    discount = settings.get("discount", 0)
    
    # Форматируем сообщение
    formatted_msg = format_filtered_products(
        "🔥 <b>Лучшие скидки сейчас</b>",
        filtered,
        discount,
        show_percent=True
    )
    formatted_msg += "\n💡 Отличное время для покупки!"
    
    # Формируем данные для клавиатуры
    products_data = [
        {"nm_id": p[0]["nm_id"], "name": p[0].get("custom_name") or p[0].get("name_product", "")}
        for p in filtered
    ]
    
    from keyboards.kb import products_inline
    await query.message.edit_text(
        formatted_msg,
        parse_mode="HTML",
        reply_markup=products_inline(products_data)
    )
    await query.answer()


@router.callback_query(F.data == "filter_price_drops")
@require_plan(['plan_basic', 'plan_pro'], "⛔ Фильтры доступны только на платных тарифах")
async def filter_price_drops(
    query: CallbackQuery,
    product_service: ProductService,
    user_service: UserService
):
    """Показать товары с падающими ценами."""
    user_id = query.from_user.id
    
    # Получаем товары через сервис
    filtered = await product_service.filter_price_drops(user_id)
    
    if not filtered:
        await query.answer(
            "📈 Сейчас цены стабильны или растут.\nСледим дальше!",
            show_alert=True
        )
        return
    
    # Форматируем сообщение
    formatted_msg = format_filtered_products(
        "📉 <b>Цены падают</b>",
        filtered,
        discount=0,
        show_percent=False
    )
    formatted_msg += "\n💡 Возможно, стоит подождать ещё!"
    
    # Формируем данные для клавиатуры
    products_data = [
        {"nm_id": p[0]["nm_id"], "name": p[0].get("custom_name") or p[0].get("name_product", "")}
        for p in filtered
    ]
    
    from keyboards.kb import products_inline
    await query.message.edit_text(
        formatted_msg,
        parse_mode="HTML",
        reply_markup=products_inline(products_data)
    )
    await query.answer()


# ============= ДЕТАЛЬНАЯ ИНФОРМАЦИЯ =============

@router.callback_query(F.data.startswith("product_detail:"))
async def cb_product_detail(
    query: CallbackQuery,
    product_service: ProductService,
    settings_service: SettingsService,
    user_service: UserService,
    container: Container,
):
    """Показать детали товара."""
    # Извлекаем данные
    nm_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id
    
    # Получаем товар через сервис
    product_repo = container.get_product_repo()
    product_dict = await product_repo.get_by_nm_id(user_id, nm_id)
    
    if not product_dict:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    # Получаем детали через сервис
    settings = await settings_service.get_user_settings(user_id)
    user = await user_service.get_user_info(user_id)
    
    discount = settings.get("discount", 0)
    plan = user.get("plan", "plan_free")
    
    detail = await product_service.get_product_detail(product_dict["id"], discount)
    
    if not detail:
        await query.answer("❌ Ошибка получения данных", show_alert=True)
        return
    
    # Форматируем и отправляем
    formatted_msg = format_product_detail(
        detail["product"],
        detail["stats"],
        discount,
        plan
    )

    await query.message.edit_text(
        formatted_msg,
        reply_markup=product_detail_kb(nm_id),
        parse_mode="HTML"
    )
    await query.answer()


# ============= ГРАФИК ЦЕН =============

@router.callback_query(F.data.startswith("show_graph:"))
async def cb_show_graph(
    query: CallbackQuery,
    product_service: ProductService,
    settings_service: SettingsService,
    container: Container
):
    """Показать график цен."""
    # Извлекаем данные
    nm_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id
    
    product_repo = container.get_product_repo()
    product = await product_repo.get_by_nm_id(user_id, nm_id)
    
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    # Получаем детали через сервис
    settings = await settings_service.get_user_settings(user_id)
    discount = settings.get("discount", 0)
    
    detail = await product_service.get_product_detail(product["id"], discount)
    
    if not detail or not detail.get("history") or len(detail["history"]) < 2:
        await query.answer(
            "📊 Недостаточно данных для графика.\nНужно минимум 2 записи цен.",
            show_alert=True
        )
        return

    await query.answer("⏳ Генерирую график...")

    try:
        # Конвертируем в модель
        history_rows = [PriceHistoryRow(**h) for h in detail["history"]]
        display_name = product.get("custom_name") or product.get("name_product", "")
        
        # Генерируем график
        graph_buffer = await generate_price_graph(history_rows, display_name, discount)

        # Отправляем
        photo = BufferedInputFile(
            graph_buffer.read(),
            filename=f"price_graph_{nm_id}.png"
        )

        caption = (
            f"📈 <b>График цен</b>\n\n"
            f"📦 {display_name}\n"
            f"🔢 Артикул: <code>{nm_id}</code>\n"
            f"📊 Записей: {len(detail['history'])}"
        )

        await query.message.answer_photo(
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=back_to_product_kb(nm_id)
        )

    except Exception as e:
        logger.exception(f"Ошибка при генерации графика для {nm_id}: {e}")
        await query.message.answer(
            "❌ Ошибка при генерации графика.\nПопробуйте позже."
        )


# ============= ПЕРЕИМЕНОВАНИЕ =============

@router.callback_query(F.data.startswith("rename:"))
@require_plan(['plan_basic', 'plan_pro'], "⛔ Переименование доступно только на платных тарифах")
async def cb_rename_start(
    query: CallbackQuery,
    state: FSMContext,
    container: Container,
    user_service: UserService
):
    """Начать переименование."""
    # Извлекаем данные
    nm_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id
    
    product_repo = container.get_product_repo()
    product = await product_repo.get_by_nm_id(user_id, nm_id)
    
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    await state.update_data(nm_id=nm_id, product_id=product["id"])
    await state.set_state(RenameProductState.waiting_for_name)
    
    current_name = product.get("custom_name") or product.get("name_product", "")
    
    await query.message.answer(
        f"✏️ <b>Переименование товара</b>\n\n"
        f"Текущее название:\n<i>{current_name}</i>\n\n"
        f"Отправьте новое название или /cancel для отмены.",
        parse_mode="HTML"
    )
    await query.answer()


@router.message(RenameProductState.waiting_for_name)
async def process_rename(
    message: Message,
    state: FSMContext,
    product_service: ProductService
):
    """Обработка нового названия."""
    if message.text == "/cancel":
        await message.answer("❌ Переименование отменено", reply_markup=main_inline_kb())
        await state.clear()
        return
    
    # Извлекаем данные
    new_name = message.text.strip()
    data = await state.get_data()
    product_id = data.get("product_id")
    nm_id = data.get("nm_id")
    
    # Переименовываем через сервис
    success, msg = await product_service.rename_product(product_id, new_name)
    
    if not success:
        await message.answer(f"❌ {msg}")
        return
    
    # Отправляем ответ
    await message.answer(
        f"✅ <b>{msg}</b>\n\nНовое название:\n<i>{new_name}</i>",
        parse_mode="HTML",
        reply_markup=product_detail_kb(nm_id)
    )
    
    await state.clear()


# ============= НАСТРОЙКА УВЕДОМЛЕНИЙ =============

@router.callback_query(F.data.startswith("notify_settings:"))
@require_plan(['plan_basic', 'plan_pro'], "⛔ Гибкие уведомления доступны с тарифа Базовый")
async def cb_notify_settings(
    query: CallbackQuery,
    container: Container,
    user_service: UserService
):
    """Показать меню уведомлений."""
    # Извлекаем данные
    nm_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id

    product_repo = container.get_product_repo()
    product = await product_repo.get_by_nm_id(user_id, nm_id)
    
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    # Формируем текущие настройки
    notify_mode = product.get("notify_mode")
    notify_value = product.get("notify_value")
    
    current_settings = "Все изменения цены"
    if notify_mode == "percent":
        current_settings = f"При снижении на {notify_value}%"
    elif notify_mode == "threshold":
        current_settings = f"При цене ≤ {notify_value} ₽"
    
    display_name = product.get("custom_name") or product.get("name_product", "")
    
    # Отправляем
    await query.message.edit_text(
        f"🔔 <b>Настройка уведомлений</b>\n\n"
        f"📦 {display_name}\n\n"
        f"Текущая настройка: <b>{current_settings}</b>\n\n"
        f"Выберите режим уведомлений:",
        parse_mode="HTML",
        reply_markup=notify_mode_kb(nm_id)
    )
    await query.answer()


@router.callback_query(F.data.startswith("notify_percent:"))
async def cb_notify_percent(query: CallbackQuery, state: FSMContext, container: Container):
    """Установка процента снижения."""
    # Извлекаем данные
    nm_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id

    product_repo = container.get_product_repo()
    product = await product_repo.get_by_nm_id(user_id, nm_id)
    
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    await state.update_data(nm_id=nm_id, product_id=product["id"], notify_mode="percent")
    await state.set_state(SetNotifyState.waiting_for_value)
    
    await query.message.answer(
        f"📊 <b>Установка процента снижения</b>\n\n"
        f"Введите процент (например: <code>3</code> или <code>10</code>)\n\n"
        f"При снижении цены на указанный процент или больше — вы получите уведомление.\n\n"
        f"Отправьте /cancel для отмены.",
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data.startswith("notify_threshold:"))
async def cb_notify_threshold(query: CallbackQuery, state: FSMContext, container: Container):
    """Установка целевой цены."""
    # Извлекаем данные
    nm_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id

    product_repo = container.get_product_repo()
    product = await product_repo.get_by_nm_id(user_id, nm_id)
    
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    await state.update_data(nm_id=nm_id, product_id=product["id"], notify_mode="threshold")
    await state.set_state(SetNotifyState.waiting_for_value)
    
    current_price = product.get("last_product_price", 0)
    
    await query.message.answer(
        f"💰 <b>Установка целевой цены</b>\n\n"
        f"Текущая цена: {current_price} ₽\n\n"
        f"Введите целевую цену (например: <code>3000</code>)\n\n"
        f"Когда цена станет равна или ниже — вы получите уведомление.\n\n"
        f"Отправьте /cancel для отмены.",
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data.startswith("notify_all:"))
async def cb_notify_all(query: CallbackQuery, product_service: ProductService, container: Container):
    """Включить все уведомления."""
    # Извлекаем данные
    nm_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id

    product_repo = container.get_product_repo()
    product = await product_repo.get_by_nm_id(user_id, nm_id)
    
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return

    # Сбрасываем настройки через сервис
    success, msg = await product_service.set_notify_settings(product["id"], None, None)
    
    if not success:
        await query.answer(f"❌ {msg}", show_alert=True)
        return
    
    display_name = product.get("custom_name") or product.get("name_product", "")

    # Отправляем ответ
    await query.message.edit_text(
        f"✅ <b>Настройки уведомлений обновлены</b>\n\n"
        f"📦 {display_name}\n\n"
        f"🔔 Теперь вы будете получать уведомления о <b>всех</b> изменениях цены.",
        parse_mode="HTML",
        reply_markup=product_detail_kb(nm_id)
    )
    await query.answer("Все уведомления включены")


@router.message(SetNotifyState.waiting_for_value)
async def process_notify_value(
    message: Message,
    state: FSMContext,
    product_service: ProductService
):
    """Обработка введённого значения."""
    if message.text == "/cancel":
        await message.answer("❌ Настройка уведомлений отменена", reply_markup=main_inline_kb())
        await state.clear()
        return

    # Извлекаем данные
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите положительное целое число")
        return

    data = await state.get_data()
    product_id = data.get("product_id")
    nm_id = data.get("nm_id")
    notify_mode = data.get("notify_mode")

    # Сохраняем через сервис
    success, msg = await product_service.set_notify_settings(product_id, notify_mode, value)
    
    if not success:
        await message.answer(f"❌ {msg}")
        return

    # Формируем ответ
    if notify_mode == "percent":
        result_msg = (
            f"✅ Уведомления настроены!\n\n"
            f"Вы будете получать уведомления при снижении цены на <b>{value}%</b> и более."
        )
    else:
        result_msg = (
            f"✅ Уведомления настроены!\n\n"
            f"Вы будете получать уведомления когда цена станет <b>{value} ₽</b> или ниже."
        )

    await message.answer(result_msg, parse_mode="HTML", reply_markup=product_detail_kb(nm_id))
    await state.clear()


# ============= УДАЛЕНИЕ =============

@router.callback_query(F.data == "remove_product")
async def cb_start_remove(query: CallbackQuery, product_service: ProductService):
    """Начать процесс удаления."""
    user_id = query.from_user.id
    
    # Получаем товары через сервис
    products_analytics = await product_service.get_products_with_analytics(user_id)
    
    if not products_analytics:
        await query.answer("📭 Нет товаров для удаления", show_alert=True)
        return

    # Формируем данные для клавиатуры
    products_data = [
        {
            'nm_id': item["product"]["nm_id"],
            'display_name': (
                item["product"].get("custom_name") or 
                item["product"].get("name_product", "")
            )
        }
        for item in products_analytics
    ]
    
    # Отправляем
    await query.message.edit_text(
        f"🗑 <b>Выберите товар для удаления:</b>\n\nВсего товаров: {len(products_data)}",
        reply_markup=remove_products_kb(products_data),
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data.startswith("rm:"))
async def cb_confirm_remove(query: CallbackQuery, container: Container):
    """Подтверждение удаления."""
    # Извлекаем данные
    nm_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id

    product_repo = container.get_product_repo()
    product = await product_repo.get_by_nm_id(user_id, nm_id)
    
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    display_name = product.get("custom_name") or product.get("name_product", "")
    
    # Отправляем подтверждение
    await query.message.edit_text(
        f"❓ <b>Удалить товар?</b>\n\n"
        f"📦 {display_name}\n"
        f"🔢 Артикул: <code>{nm_id}</code>\n\n"
        f"⚠️ История цен также будет удалена.",
        reply_markup=confirm_remove_kb(nm_id),
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data.startswith("confirm_remove:"))
async def cb_remove(query: CallbackQuery, product_service: ProductService):
    """Удалить товар."""
    # Извлекаем данные
    nm_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id
    
    # Удаляем через сервис
    success, msg = await product_service.remove_product(user_id, nm_id)
    
    # Отправляем ответ
    icon = "✅" if success else "❌"
    await query.message.edit_text(f"{icon} {msg}", reply_markup=main_inline_kb())
    await query.answer("Товар удалён" if success else "Ошибка удаления")


# ============= НАВИГАЦИЯ =============

@router.callback_query(F.data.startswith("back_to_product:"))
async def cb_back_to_product(query: CallbackQuery, container: Container):
    """Возврат к детальной информации."""
    # Извлекаем данные
    nm_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id

    product_repo = container.get_product_repo()
    product = await product_repo.get_by_nm_id(user_id, nm_id)

    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return

    # Удаляем график
    await query.message.delete()
    
    # Показываем карточку
    display_name = product.get("custom_name") or product.get("name_product", "")
    price = product.get("last_product_price", 0)
    
    await query.message.answer(
        text=(
            f"📦 <b>{display_name}</b>\n"
            f"💰 Цена: {int(price)} ₽\n"
            f"🔢 Артикул: <code>{product['nm_id']}</code>"
        ),
        parse_mode="HTML",
        reply_markup=product_detail_kb(product['nm_id'])
    )
    await query.answer()


@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(query: CallbackQuery):
    """Возврат в главное меню."""
    await query.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=main_inline_kb()
    )
    await query.answer()
