from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from states.user_states import AddProductState, RenameProductState, SetNotifyState
from services.db import DB
from services.price_fetcher import PriceFetcher
from utils.wb_utils import extract_nm_id, apply_wallet_discount
from keyboards.kb import (
    products_inline, main_inline_kb, sizes_inline_kb,
    product_detail_kb, confirm_remove_kb, back_to_product_kb, notify_mode_kb,
    export_format_kb, onboarding_kb, upsell_kb, products_list_kb,
    remove_products_kb
)
from utils.decorators import require_plan
from utils.graph_generator import generate_price_graph
import logging
from utils.export_utils import generate_excel, generate_csv
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)


# ---------------- Добавление товара ----------------
@router.callback_query(F.data == "add_product")
async def cb_add_product(query: CallbackQuery, state: FSMContext):
    """Запрос ссылки или артикула для отслеживания товара."""
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
async def add_url(message: Message, state: FSMContext, db: DB, price_fetcher: PriceFetcher):
    url_or_nm = message.text.strip()
    nm = extract_nm_id(url_or_nm)

    if not nm:
        await message.answer(
            "❌ Не удалось распознать артикул.\n\n"
            "Отправьте:\n"
            "• Ссылку на товар WB\n"
            "• Артикул (6-12 цифр)"
        )
        return

    await db.ensure_user(message.from_user.id)
    user = await db.get_user(message.from_user.id)
    prods = await db.list_products(message.from_user.id)
    max_links = user.get("max_links", 5)

    if len(prods) >= max_links:
        await message.answer(
            f"⛔ Достигнут лимит ({max_links}) товаров.\n"
            "Удалите старый товар или обновите тариф.",
            reply_markup=main_inline_kb()
        )
        await state.clear()
        return

    status_msg = await message.answer("⏳ Получаю информацию о товаре...")

    try:
        product_data = await price_fetcher.get_product_data(nm)
        if not product_data:
            await status_msg.edit_text(
                "❌ Не удалось получить данные о товаре.\n"
                "Проверьте артикул и попробуйте позже."
            )
            await state.clear()
            return

        product_name = product_data.get("name", f"Товар {nm}")
        sizes = product_data.get("sizes", [])

        # Формируем URL товара
        url = f"https://www.wildberries.ru/catalog/{nm}/detail.aspx"

        # Проверяем, есть ли реальные размеры (не пустые name и origName)
        valid_sizes = []
        if sizes:
            valid_sizes = [
                s for s in sizes 
                if s.get("name") not in ("", "0", None)
                and s.get("origName") not in ("", "0", None)
            ]

        # Если есть реальные размеры — переходим в выбор размера
        if valid_sizes:
            await state.update_data(url=url, nm=nm, product_name=product_name)

            await status_msg.edit_text(
                f"📦 <b>{product_name}</b>\n"
                f"🔢 Артикул: <code>{nm}</code>\n\n"
                "Выберите размер для отслеживания:",
                reply_markup=sizes_inline_kb(nm, valid_sizes),
                parse_mode="HTML"
            )
            await state.set_state(AddProductState.waiting_for_size)
        else:
            # Товар без размеров — добавляем сразу
            product_id = await db.add_product(message.from_user.id, url, nm, product_name)
            if not product_id:
                await status_msg.edit_text(
                    "⚠️ Этот товар уже в отслеживании.",
                    reply_markup=main_inline_kb()
                )
                await state.clear()
                return

            # Сохраняем цены и добавляем в историю
            # Для товаров без размеров цена находится в первом элементе sizes
            size_data = sizes[0] if sizes else {}
            price_info = size_data.get("price", {})
            price_basic = price_info.get("basic", 0)
            price_product = price_info.get("product", 0)
            qty = sum(stock.get("qty", 0) for stock in size_data.get("stocks", []))

            await db.update_prices_and_stock(
                product_id=product_id,
                basic=price_basic,
                product=price_product,
                last_qty=qty,
                out_of_stock=(qty == 0)
            )

            # Добавляем первую запись в историю
            await db.add_price_history(product_id, price_basic, price_product, qty)

            # Получаем скидку пользователя для отображения
            user = await db.get_user(message.from_user.id)
            discount = user.get("discount_percent", 0) if user else 0

            display_price = int(price_product)
            price_text = f"💰 Текущая цена: {display_price} ₽"

            if discount > 0:
                final_price = apply_wallet_discount(display_price, discount)
                price_text = f"💰 Цена: {display_price} ₽\n💳 С кошельком ({discount}%): {int(final_price)} ₽"

            # Проверяем, это онбординг или обычное добавление
            data = await state.get_data()
            is_onboarding = data.get("onboarding", False)

            if is_onboarding:
                # Онбординг: показываем ценность + предлагаем тариф
                await status_msg.edit_text(
                    f"🎉 <b>Отлично! Товар добавлен</b>\n\n"
                    f"📦 {product_name}\n"
                    f"🔢 Артикул: <code>{nm}</code>\n"
                    f"{price_text}\n\n"
                    "✅ Теперь я буду отслеживать цену каждый день\n"
                    "🔔 Вы получите уведомление при снижении\n\n"
                    "💡 <b>Что дальше?</b>\n"
                    "🎁 У вас ещё <b>4 бесплатных слота</b>\n"
                    "Добавьте больше товаров или выберите тариф для расширения возможностей 👇",
                    reply_markup=onboarding_kb(),
                    parse_mode="HTML"
                )
            else:
                # Обычное добавление
                await status_msg.edit_text(
                    f"✅ <b>Товар добавлен!</b>\n\n"
                    f"📦 {product_name}\n"
                    f"🔢 Артикул: <code>{nm}</code>\n"
                    f"{price_text}\n\n"
                    "Я буду отслеживать изменения цены.",
                    reply_markup=main_inline_kb(),
                    parse_mode="HTML"
                )

            await state.clear()

    except Exception as e:
        logger.exception(f"Ошибка при добавлении товара {nm}: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при добавлении товара. Попробуйте позже.")
        await state.clear()


@router.callback_query(F.data.startswith("select_size:"), AddProductState.waiting_for_size)
async def select_size_cb(query: CallbackQuery, state: FSMContext, db: DB, price_fetcher: PriceFetcher):
    """Пользователь выбрал размер для товара."""
    try:
        _, nm_str, size_name = query.data.split(":", 2)
        nm = int(nm_str)
        user_id = query.from_user.id

        data = await state.get_data()
        url = data.get("url")
        product_name = data.get("product_name")

        if not url or not product_name:
            await query.answer("❌ Произошла ошибка, попробуйте добавить товар заново.", show_alert=True)
            await state.clear()
            return

        # Добавляем товар с выбранным размером
        product_id = await db.add_product(user_id, url, nm, product_name)
        if not product_id:
            await query.answer("⚠️ Этот товар уже в отслеживании.", show_alert=True)
            await state.clear()
            return

        await db.set_selected_size(product_id, size_name)

        # Сохраняем текущие цены
        product_data = await price_fetcher.get_product_data(nm)
        if product_data and product_data.get("sizes"):
            size_data = next((s for s in product_data["sizes"] if s["name"] == size_name), None)
            if size_data:
                price_info = size_data.get("price", {})
                price_basic = price_info.get("basic", 0)
                price_product = price_info.get("product", 0)
                qty = sum(stock.get("qty", 0) for stock in size_data.get("stocks", []))
                
                await db.update_prices_and_stock(
                    product_id=product_id,
                    basic=price_basic,
                    product=price_product,
                    last_qty=qty,
                    out_of_stock=(qty == 0)
                )
                
                # Добавляем в историю
                await db.add_price_history(product_id, price_basic, price_product, qty)

        await query.message.edit_text(
            f"✅ <b>Товар добавлен!</b>\n\n"
            f"📦 {product_name}\n"
            f"🔢 Артикул: <code>{nm}</code>\n"
            f"🔘 Размер: <b>{size_name}</b>\n\n"
            "Теперь я буду отслеживать цены для этого размера.",
            parse_mode="HTML",
            reply_markup=main_inline_kb()
        )
        await query.answer("Размер выбран!")
        await state.clear()

    except Exception as e:
        logger.exception(f"Ошибка при выборе размера: {e}")
        await query.answer("❌ Произошла ошибка при выборе размера.", show_alert=True)
        await state.clear()


# ---------------- Список товаров ----------------
@router.callback_query(F.data == "list_products")
async def cb_list_products(query: CallbackQuery, db: DB):
    """Улучшенный список отслеживаемых товаров с аналитикой."""
    
    products = await db.list_products(query.from_user.id)
    
    if not products:
        await query.message.edit_text(
            "📭 <b>Список пуст</b>\n\n"
            "Вы ещё не добавили товары для отслеживания.\n\n"
            "💡 Добавьте первый товар, чтобы начать экономить!",
            parse_mode="HTML",
            reply_markup=products_inline()
        )
        await query.answer()
        return
    
    # Получаем данные пользователя
    user = await db.get_user(query.from_user.id)
    discount = user.get("discount_percent", 0) if user else 0
    plan = user.get("plan", "plan_free")
    max_links = user.get("max_links", 5)
    
    # ===== АНАЛИТИКА ТОВАРОВ =====
    products_with_analytics = []
    total_current_price = 0
    total_potential_savings = 0
    best_deal = None
    best_deal_percent = 0
    
    for p in products:
        # Получаем историю для анализа
        history = await db.get_price_history(p.id, limit=30)
        
        analytics = {
            "product": p,
            "trend": "neutral",  # up, down, neutral
            "savings_percent": 0,
            "savings_amount": 0,
            "has_history": len(history) >= 2
        }
        
        if len(history) >= 2:
            prices = [h.product_price for h in history]
            max_price = max(prices)
            min_price = min(prices)
            current_price = p.last_product_price or max_price
            
            # Расчёт экономии
            savings = max_price - current_price
            if savings > 0 and max_price > 0:
                savings_percent = (savings / max_price) * 100
                analytics["savings_percent"] = savings_percent
                analytics["savings_amount"] = savings
                
                # Лучшая сделка
                if savings_percent > best_deal_percent:
                    best_deal_percent = savings_percent
                    best_deal = p
            
            # Тренд (последние 3 записи)
            recent_prices = [h.product_price for h in history[:3]]
            if len(recent_prices) >= 2:
                if recent_prices[0] < recent_prices[-1]:
                    analytics["trend"] = "down"  # Цена падает
                elif recent_prices[0] > recent_prices[-1]:
                    analytics["trend"] = "up"    # Цена растёт
            
            total_potential_savings += savings
        
        if p.last_product_price:
            total_current_price += p.last_product_price
        
        products_with_analytics.append(analytics)
    
    # ===== СОРТИРОВКА ПО ВЫГОДНОСТИ =====
    products_with_analytics.sort(
        key=lambda x: x["savings_percent"], 
        reverse=True
    )
    
    # ===== ФОРМИРУЕМ СООБЩЕНИЕ =====
    
    # Заголовок с общей статистикой
    text = "📦 <b>Ваши товары</b>\n"
    text += f"{'═'*25}\n\n"
    
    # Мини-дашборд
    text += f"📊 Товаров: <b>{len(products)}/{max_links}</b>\n"
    
    if discount > 0:
        total_with_discount = sum(
            apply_wallet_discount(p.last_product_price or 0, discount) 
            for p in products
        )
        text += f"💰 Общая стоимость: <b>{total_with_discount}₽</b> (с WB кошельком)\n"
    else:
        text += f"💰 Общая стоимость: <b>{total_current_price}₽</b>\n"
    
    if total_potential_savings > 0:
        text += f"💎 Можно сэкономить: <b>{total_potential_savings}₽</b>\n"
    
    text += "\n"
    
    # Лучшая сделка (если есть)
    if best_deal:
        text += (
            f"🔥 <b>Лучшая сделка сейчас:</b>\n"
            f"{best_deal.display_name[:35]}...\n"
            f"└ Скидка {best_deal_percent:.0f}% от пика цены!\n\n"
        )
    
    # Сортировка и фильтры
    text += "📋 <b>Список товаров:</b>\n"
    text += "<i>Отсортировано по выгодности</i>\n\n"
    
    # ===== СПИСОК ТОВАРОВ =====
    products_data = []
    
    for i, item in enumerate(products_with_analytics[:10], 1):  # Показываем топ-10
        p = item["product"]
        
        # Эмодзи статуса
        if item["savings_percent"] >= 30:
            status_emoji = "🔥"
        elif item["savings_percent"] >= 15:
            status_emoji = "💰"
        elif item["trend"] == "down":
            status_emoji = "📉"
        elif item["trend"] == "up":
            status_emoji = "📈"
        else:
            status_emoji = "📦"
        
        # Наличие
        stock_emoji = "✅" if not p.out_of_stock else "❌"
        
        # Название
        display_name = p.display_name[:30]
        if len(p.display_name) > 30:
            display_name += "..."
        
        # Цена
        if p.last_product_price:
            if discount > 0:
                final_price = apply_wallet_discount(p.last_product_price, discount)
                price_str = f"{final_price}₽"
            else:
                price_str = f"{p.last_product_price}₽"
        else:
            price_str = "—"
        
        # Экономия
        if item["savings_percent"] > 0:
            savings_str = f" (-{item['savings_percent']:.0f}%)"
        else:
            savings_str = ""
        
        text += f"{status_emoji} <b>{i}.</b> {display_name}\n"
        text += f"   {stock_emoji} {price_str}{savings_str}\n"
        
        products_data.append({
            "nm_id": p.nm_id,
            "name": display_name
        })
    
    # Если товаров больше 10
    if len(products_with_analytics) > 10:
        text += f"\n<i>... и ещё {len(products_with_analytics) - 10} товаров</i>\n"
    
    # ===== ПОДСКАЗКИ И МОТИВАЦИЯ =====
    text += "\n💡 <b>Подсказки:</b>\n"
    
    # Подсказка о наличии
    out_of_stock_count = sum(1 for p in products if p.out_of_stock)
    if out_of_stock_count > 0:
        text += f"• {out_of_stock_count} товар(ов) нет в наличии\n"
    
    # Подсказка о лимите
    if plan == "plan_free" and len(products) >= max_links - 1:
        text += f"• Осталось {max_links - len(products)} слот(ов)\n"
    
    # Подсказка об апгрейде
    if plan == "plan_free" and len(products) >= 3:
        text += "• 💎 Улучшите тариф для отслеживания до 50 товаров\n"
    
    # ===== КНОПКИ ДЕЙСТВИЙ =====
    keyboard_rows = []
    
    # Фильтры (для платных тарифов)
    if plan in ["plan_basic", "plan_pro"]:
        keyboard_rows.append([
            InlineKeyboardButton(
                text="🔥 Лучшие скидки",
                callback_data="filter_best_deals"
            ),
            InlineKeyboardButton(
                text="📉 Падающие цены",
                callback_data="filter_price_drops"
            )
        ])
    
    # Формируем данные для клавиатуры
    products_data = [
        {'nm_id': p.nm_id, 'display_name': p.display_name}
        for p in products
    ]

    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=products_list_kb(
            products=products_data,
            has_filters=(plan in ["plan_basic", "plan_pro"]),
            show_export=(plan == "plan_pro"),
            show_upgrade=(plan == "plan_free" and len(products) >= 3)
        )
    )


# ===== ФИЛЬТРЫ =====

@router.callback_query(F.data == "filter_best_deals")
@require_plan(['plan_basic', 'plan_pro'], "⛔ Фильтры доступны только на платных тарифах")
async def filter_best_deals(query: CallbackQuery, db: DB):
    """Показать только товары с лучшими скидками."""
    
    products = await db.list_products(query.from_user.id)
    user = await db.get_user(query.from_user.id)
    discount = user.get("discount_percent", 0) if user else 0
    
    # Фильтруем товары со скидкой >= 15%
    filtered = []
    for p in products:
        history = await db.get_price_history(p.id, limit=30)
        if len(history) >= 2:
            prices = [h.product_price for h in history]
            max_price = max(prices)
            current = p.last_product_price or max_price
            
            if max_price > 0:
                savings_percent = ((max_price - current) / max_price) * 100
                if savings_percent >= 15:
                    filtered.append((p, savings_percent))
    
    if not filtered:
        await query.answer(
            "😔 Сейчас нет товаров со значительными скидками.\n"
            "Продолжайте мониторинг!",
            show_alert=True
        )
        return
    
    # Сортируем по скидке
    filtered.sort(key=lambda x: x[1], reverse=True)
    
    text = (
        "🔥 <b>Лучшие скидки сейчас</b>\n"
        f"{'═'*25}\n\n"
        f"Найдено товаров: <b>{len(filtered)}</b>\n\n"
    )
    
    products_data = []
    for i, (p, savings_percent) in enumerate(filtered[:15], 1):
        display_name = p.display_name[:35]
        if len(p.display_name) > 35:
            display_name += "..."
        
        if p.last_product_price:
            if discount > 0:
                final_price = apply_wallet_discount(p.last_product_price, discount)
                price_str = f"{final_price}₽"
            else:
                price_str = f"{p.last_product_price}₽"
        else:
            price_str = "—"
        
        text += (
            f"🔥 <b>{i}.</b> {display_name}\n"
            f"   💰 {price_str} <b>(-{savings_percent:.0f}%)</b>\n"
        )
        
        products_data.append({"nm_id": p.nm_id, "name": display_name})
    
    text += "\n💡 Отличное время для покупки!"
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=products_inline(products_data)
    )
    await query.answer()


@router.callback_query(F.data == "filter_price_drops")
@require_plan(['plan_basic', 'plan_pro'], "⛔ Фильтры доступны только на платных тарифах")
async def filter_price_drops(query: CallbackQuery, db: DB):
    """Показать товары с падающими ценами."""
    
    products = await db.list_products(query.from_user.id)
    
    # Фильтруем товары с падающим трендом
    filtered = []
    for p in products:
        history = await db.get_price_history(p.id, limit=7)
        if len(history) >= 3:
            prices = [h.product_price for h in history]
            # Проверяем тренд
            if prices[0] < prices[-1]:  # Последняя цена ниже первой
                drop = prices[-1] - prices[0]
                filtered.append((p, drop))
    
    if not filtered:
        await query.answer(
            "📈 Сейчас цены стабильны или растут.\n"
            "Следим дальше!",
            show_alert=True
        )
        return
    
    # Сортируем по величине падения
    filtered.sort(key=lambda x: x[1], reverse=True)
    
    text = (
        "📉 <b>Цены падают</b>\n"
        f"{'═'*25}\n\n"
        f"Найдено товаров: <b>{len(filtered)}</b>\n\n"
    )
    
    products_data = []
    for i, (p, drop) in enumerate(filtered[:15], 1):
        display_name = p.display_name[:35]
        if len(p.display_name) > 35:
            display_name += "..."
        
        text += (
            f"📉 <b>{i}.</b> {display_name}\n"
            f"   ↓ Падение: <b>{drop}₽</b> за неделю\n"
        )
        
        products_data.append({"nm_id": p.nm_id, "name": display_name})
    
    text += "\n💡 Возможно, стоит подождать ещё!"
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=products_inline(products_data)
    )
    await query.answer()


@router.callback_query(F.data == "show_detailed_list")
async def show_detailed_list(query: CallbackQuery, db: DB):
    """Показать все товары с кнопками для детального просмотра."""
    
    products = await db.list_products(query.from_user.id)
    
    products_data = []
    for p in products:
        products_data.append({
            "nm_id": p.nm_id,
            "name": p.display_name
        })
    
    text = (
        "📋 <b>Все товары</b>\n"
        f"{'═'*25}\n\n"
        "Нажмите на товар, чтобы увидеть детальную информацию:"
    )
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=products_inline(products_data)
    )
    await query.answer()


@router.callback_query(F.data == "upsell_from_products_list")
async def upsell_from_products_list(query: CallbackQuery, db: DB):
    """Upsell с контекстом списка товаров."""
    
    user = await db.get_user(query.from_user.id)
    products = await db.list_products(query.from_user.id)
    
    additional_slots = 50 - len(products)
    
    await query.message.edit_text(
        f"🚀 <b>Расширьте возможности!</b>\n\n"
        f"📦 Сейчас: <b>{len(products)}/5</b> товаров\n\n"
        "😔 <b>Что вы упускаете:</b>\n"
        "❌ Не можете добавить больше товаров\n"
        "❌ История только за месяц\n"
        "❌ Базовые уведомления\n\n"
        f"✅ <b>С тарифом Базовый:</b>\n"
        f"• Ещё <b>+{additional_slots} слотов</b>\n"
        "• История за 3 месяца\n"
        "• Умные уведомления\n"
        "• Ваш ПВЗ\n\n"
        "💰 Всего 199₽/мес — окупается с 1 покупки!",
        parse_mode="HTML",
        reply_markup=upsell_kb()
    )
    await query.answer()


# ---------------- Детальная информация о товаре ----------------
@router.callback_query(F.data == "product_detail")
async def cb_product_detail(query: CallbackQuery, db: DB):
    """Показать детальную информацию о товаре."""
    nm_id = int(query.data.split(":", 1)[1])
    
    product = await db.get_product_by_nm(query.from_user.id, nm_id)
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    # Получаем скидку пользователя
    user = await db.get_user(query.from_user.id)
    discount = user.get("discount_percent", 0) if user else 0
    
    # Получаем историю для статистики
    history = await db.get_price_history(product.id, limit=100)
    
    text = f"📦 <b>{product.display_name}</b>\n\n"
    text += f"🔢 Артикул: <code>{nm_id}</code>\n"
    
    if product.selected_size:
        text += f"🔘 Размер: <b>{product.selected_size}</b>\n"
    
    if product.last_product_price:
        price = product.last_product_price
        if discount > 0:
            final_price = apply_wallet_discount(price, discount)
            text += f"💰 Цена: {price} ₽\n"
            text += f"💳 С кошельком ({discount}%): <b>{final_price} ₽</b>\n"
        else:
            text += f"💰 Текущая цена: <b>{price} ₽</b>\n"

    # Проверяем тариф для отображения остатков
    if product.last_qty is not None:
        if user and user.get("plan") == "plan_pro":
            # Только для продвинутого тарифа показываем количество
            if product.out_of_stock:
                text += "📦 Остаток: <b>Нет в наличии</b>\n"
            else:
                text += f"📦 Остаток: <b>{product.last_qty} шт.</b>\n"
        else:
            # Для остальных тарифов — только наличие/отсутствие
            if product.out_of_stock:
                text += f"📦 <b>Нет в наличии</b>\n"
            else:
                text += f"📦 <b>В наличии</b>\n"

    # Статистика из истории
    if history:
        prices = [h.product_price for h in history]
        min_price = min(prices)
        max_price = max(prices)
        text += f"\n📊 <b>Статистика:</b>\n"

        if discount > 0:
            min_with_discount = apply_wallet_discount(min_price, discount)
            max_with_discount = apply_wallet_discount(max_price, discount)
            text += f"• Мин. цена: {min_price} ₽ (с WB кошельком {min_with_discount} ₽)\n"
            text += f"• Макс. цена: {max_price} ₽ (с WB кошельком {max_with_discount} ₽)\n"
        else:
            text += f"• Мин. цена: {min_price} ₽\n"
            text += f"• Макс. цена: {max_price} ₽\n"

        # Настройки уведомлений
    if product.notify_mode == "percent":
        text += f"\n🔔 Уведомления: при снижении на {product.notify_value}%"
    elif product.notify_mode == "threshold":
        text += f"\n🔔 Уведомления: при цене ≤ {product.notify_value} ₽"
    else:
        text += "\n🔔 Уведомления: все изменения цены"

    text += f"\n🕐 Добавлен: {product.created_at.strftime('%d.%m.%Y %H:%M')}"

    await query.message.edit_text(
        text,
        reply_markup=product_detail_kb(nm_id),
        parse_mode="HTML"
    )
    await query.answer()


# ---------------- График цен ----------------
@router.callback_query(F.data.startswith("show_graph:"))
async def cb_show_graph(query: CallbackQuery, db: DB):
    """Показать график изменения цены."""
    nm_id = int(query.data.split(":", 1)[1])

    product = await db.get_product_by_nm(query.from_user.id, nm_id)
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return

    history = await db.get_price_history(product.id, limit=100)

    if len(history) < 2:
        await query.answer(
            "📊 Недостаточно данных для графика.\n"
            "Нужно минимум 2 записи цен.",
            show_alert=True
        )
        return

    await query.answer("⏳ Генерирую график...")

    try:
        # Получаем скидку пользователя
        user = await db.get_user(query.from_user.id)
        discount = user.get("discount_percent", 0) if user else 0

        # Генерируем график
        graph_buffer = await generate_price_graph(history, product.display_name, discount)

        # Отправляем как фото
        photo = BufferedInputFile(graph_buffer.read(), filename=f"price_graph_{nm_id}.png")

        caption = (
            f"📈 <b>График цен</b>\n\n"
            f"📦 {product.display_name}\n"
            f"🔢 Артикул: <code>{nm_id}</code>\n"
            f"📊 Записей: {len(history)}"
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


# ---------------- Переименование товара ----------------
@router.callback_query(F.data.startswith("rename:"))
@require_plan(['plan_basic', 'plan_pro'], "⛔ Переименование доступно только на платных тарифах")
async def cb_rename_start(query: CallbackQuery, state: FSMContext, db: DB):
    """Начать переименование товара."""
    nm_id = int(query.data.split(":", 1)[1])
    
    product = await db.get_product_by_nm(query.from_user.id, nm_id)
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    await state.update_data(nm_id=nm_id, product_id=product.id)
    await state.set_state(RenameProductState.waiting_for_name)
    
    current_name = product.display_name
    
    await query.message.answer(
        f"✏️ <b>Переименование товара</b>\n\n"
        f"Текущее название:\n<i>{current_name}</i>\n\n"
        f"Отправьте новое название или /cancel для отмены.",
        parse_mode="HTML"
    )
    await query.answer()


@router.message(RenameProductState.waiting_for_name)
async def process_rename(message: Message, state: FSMContext, db: DB):
    """Обработка нового названия товара."""
    if message.text == "/cancel":
        await message.answer("❌ Переименование отменено", reply_markup=main_inline_kb())
        await state.clear()
        return
    
    new_name = message.text.strip()
    
    if len(new_name) < 3:
        await message.answer("❌ Название слишком короткое (минимум 3 символа)")
        return
    
    if len(new_name) > 200:
        await message.answer("❌ Название слишком длинное (максимум 200 символов)")
        return
    
    data = await state.get_data()
    product_id = data.get("product_id")
    nm_id = data.get("nm_id")
    
    try:
        await db.set_custom_name(product_id, new_name)
        
        await message.answer(
            f"✅ <b>Товар переименован!</b>\n\n"
            f"Новое название:\n<i>{new_name}</i>",
            parse_mode="HTML",
            reply_markup=product_detail_kb(nm_id)
        )
        
    except Exception as e:
        logger.exception(f"Ошибка при переименовании товара {product_id}: {e}")
        await message.answer(
            "❌ Ошибка при переименовании товара",
            reply_markup=main_inline_kb()
        )
    
    await state.clear()


# ---------------- Удаление товара ----------------
@router.callback_query(F.data == "remove_product")
async def cb_start_remove(query: CallbackQuery, db: DB):
    """Начало процесса удаления - показываем список."""
    products = await db.list_products(query.from_user.id)
    
    if not products:
        await query.answer("📭 Нет товаров для удаления", show_alert=True)
        return

    # Формируем список для клавиатуры
    products_data = [
        {'nm_id': p.nm_id, 'display_name': p.display_name}
        for p in products
    ]
    
    text = (
        "🗑 <b>Выберите товар для удаления:</b>\n\n"
        f"Всего товаров: {len(products)}"
    )

    await query.message.edit_text(
        text,
        reply_markup=remove_products_kb(products_data),
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data.startswith("rm:"))
async def cb_confirm_remove(query: CallbackQuery, db: DB):
    """Подтверждение удаления товара."""
    nm_id = int(query.data.split(":", 1)[1])
    
    product = await db.get_product_by_nm(query.from_user.id, nm_id)
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    await query.message.edit_text(
        f"❓ <b>Удалить товар?</b>\n\n"
        f"📦 {product.display_name}\n"
        f"🔢 Артикул: <code>{nm_id}</code>\n\n"
        f"⚠️ История цен также будет удалена.",
        reply_markup=confirm_remove_kb(nm_id),
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data.startswith("confirm_remove:"))
async def cb_remove(query: CallbackQuery, db: DB):
    """Удаление товара после подтверждения."""
    nm_id = int(query.data.split(":", 1)[1])
    ok = await db.remove_product(query.from_user.id, nm_id)
    
    if ok:
        await query.message.edit_text(
            "✅ Товар успешно удалён из отслеживания.",
            reply_markup=main_inline_kb()
        )
        await query.answer("Товар удалён")
    else:
        await query.message.edit_text(
            "❌ Не удалось удалить товар.\n"
            "Возможно, он уже был удалён.",
            reply_markup=main_inline_kb()
        )
        await query.answer("Ошибка удаления", show_alert=True)


@router.callback_query(F.data.startswith("back_to_product:"))
async def cb_back_to_product(query: CallbackQuery, db: DB):
    nm_id = int(query.data.split(":", 1)[1])
    product = await db.get_product_by_nm(query.from_user.id, nm_id)

    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return

    await query.message.delete()  # Убираем график
    await query.message.answer(
        text=(
            f"📦 <b>{product.display_name}</b>\n"
            f"💰 Цена: {int(product.last_product_price or 0)} ₽\n"
            f"🔢 Артикул: <code>{product.nm_id}</code>"
        ),
        parse_mode="HTML",
        reply_markup=product_detail_kb(product.nm_id)
    )

    await query.answer()


@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(query: CallbackQuery):
    """Возврат в главное меню."""
    await query.message.edit_text(
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_inline_kb()
    )
    await query.answer()



# ---------------- Настройка уведомлений ----------------
@router.callback_query(F.data.startswith("notify_settings:"))
@require_plan(['plan_basic', 'plan_pro'], "⛔ Гибкие уведомления доступны с тарифа Базовый")
async def cb_notify_settings(query: CallbackQuery, db: DB):
    """Показать меню настройки уведомлений."""

    nm_id = int(query.data.split(":", 1)[1])
    
    product = await db.get_product_by_nm(query.from_user.id, nm_id)
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    current_settings = "Все изменения цены"
    if product.notify_mode == "percent":
        current_settings = f"При снижении на {product.notify_value}%"
    elif product.notify_mode == "threshold":
        current_settings = f"При цене ≤ {product.notify_value} ₽"
    
    await query.message.edit_text(
        f"🔔 <b>Настройка уведомлений</b>\n\n"
        f"📦 {product.display_name}\n\n"
        f"Текущая настройка: <b>{current_settings}</b>\n\n"
        f"Выберите режим уведомлений:",
        parse_mode="HTML",
        reply_markup=notify_mode_kb(nm_id)
    )
    await query.answer()


@router.callback_query(F.data.startswith("notify_percent:"))
async def cb_notify_percent(query: CallbackQuery, state: FSMContext, db: DB):
    """Установка процента снижения."""
    nm_id = int(query.data.split(":", 1)[1])
    
    product = await db.get_product_by_nm(query.from_user.id, nm_id)
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    await state.update_data(nm_id=nm_id, product_id=product.id, notify_mode="percent")
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
async def cb_notify_threshold(query: CallbackQuery, state: FSMContext, db: DB):
    """Установка целевой цены."""
    nm_id = int(query.data.split(":", 1)[1])
    
    product = await db.get_product_by_nm(query.from_user.id, nm_id)
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    await state.update_data(nm_id=nm_id, product_id=product.id, notify_mode="threshold")
    await state.set_state(SetNotifyState.waiting_for_value)
    
    current_price = product.last_product_price or 0
    
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
async def cb_notify_all(query: CallbackQuery, db: DB):
    """Включить все уведомления."""
    nm_id = int(query.data.split(":", 1)[1])

    product = await db.get_product_by_nm(query.from_user.id, nm_id)
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return

    await db.set_notify_settings(product.id, None, None)

    await query.message.edit_text(
        f"✅ <b>Настройки уведомлений обновлены</b>\n\n"
        f"📦 {product.display_name}\n\n"
        f"🔔 Теперь вы будете получать уведомления о <b>всех</b> изменениях цены.",
        parse_mode="HTML",
        reply_markup=product_detail_kb(nm_id)
    )
    await query.answer("Все уведомления включены")


@router.message(SetNotifyState.waiting_for_value)
async def process_notify_value(message: Message, state: FSMContext, db: DB):
    """Обработка введённого значения (процент или порог)."""
    if message.text == "/cancel":
        await message.answer("❌ Настройка уведомлений отменена", reply_markup=main_inline_kb())
        await state.clear()
        return

    try:
        value = int(message.text.strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное целое число")
        return

    data = await state.get_data()
    product_id = data.get("product_id")
    nm_id = data.get("nm_id")
    notify_mode = data.get("notify_mode")

    # Проверка диапазонов
    if notify_mode == "percent" and value > 100:
        await message.answer("❌ Процент не может быть больше 100")
        return

    try:
        await db.set_notify_settings(product_id, notify_mode, value)

        if notify_mode == "percent":
            msg = f"✅ Уведомления настроены!\n\nВы будете получать уведомления при снижении цены на <b>{value}%</b> и более."
        else:
            msg = f"✅ Уведомления настроены!\n\nВы будете получать уведомления когда цена станет <b>{value} ₽</b> или ниже."

        await message.answer(
            msg,
            parse_mode="HTML",
            reply_markup=product_detail_kb(nm_id)
        )

    except Exception as e:
        logger.exception(f"Ошибка при сохранении настроек уведомлений: {e}")
        await message.answer(
            "❌ Ошибка при сохранении настроек",
            reply_markup=main_inline_kb()
        )

    await state.clear()


# ---------------- Экспорт данных ----------------
@router.callback_query(F.data == "export_menu")
@require_plan(['plan_pro'], "⛔ Экспорт доступен только на тарифе Продвинутый")
async def cb_export_menu(query: CallbackQuery, db: DB):
    """Меню выбора формата экспорта."""
    products = await db.list_products(query.from_user.id)
    
    if not products:
        await query.answer("📭 Нет товаров для экспорта", show_alert=True)
        return
    
    await query.message.edit_text(
        f"📊 <b>Экспорт товаров</b>\n\n"
        f"📦 Всего товаров: {len(products)}\n\n"
        f"Выберите формат файла:",
        parse_mode="HTML",
        reply_markup=export_format_kb()
    )
    await query.answer()


@router.callback_query(F.data == "export_excel")
@require_plan(['plan_pro'], "⛔ Экспорт доступен только на тарифе Продвинутый")
async def cb_export_excel(query: CallbackQuery, db: DB):
    """Выгрузка товаров в Excel."""
    products = await db.list_products(query.from_user.id)
    
    if not products:
        await query.answer("📭 Нет товаров для экспорта", show_alert=True)
        return
    
    await query.answer("⏳ Формирую файл...")
    
    try:
        # Получаем скидку пользователя
        user = await db.get_user(query.from_user.id)
        discount = user.get("discount_percent", 0) if user else 0
        
        # Генерируем Excel
        excel_buffer = await generate_excel(products, discount)
        
        # Формируем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"wb_products_{timestamp}.xlsx"
        
        # Отправляем файл
        document = BufferedInputFile(excel_buffer.read(), filename=filename)
        
        caption = (
            f"📊 <b>Экспорт товаров</b>\n\n"
            f"📦 Товаров: {len(products)}\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        if discount > 0:
            caption += f"\n💳 С учётом скидки кошелька: {discount}%"
        
        await query.message.answer_document(
            document=document,
            caption=caption,
            parse_mode="HTML"
        )
        
        logger.info(f"Пользователь {query.from_user.id} экспортировал {len(products)} товаров в Excel")
        
    except Exception as e:
        logger.exception(f"Ошибка при экспорте в Excel: {e}")
        await query.message.answer(
            "❌ Произошла ошибка при формировании файла.\nПопробуйте позже."
        )


@router.callback_query(F.data == "export_csv")
@require_plan(['plan_pro'], "⛔ Экспорт доступен только на тарифе Продвинутый")
async def cb_export_csv(query: CallbackQuery, db: DB):
    """Выгрузка товаров в CSV."""
    products = await db.list_products(query.from_user.id)
    
    if not products:
        await query.answer("📭 Нет товаров для экспорта", show_alert=True)
        return
    
    await query.answer("⏳ Формирую файл...")
    
    try:
        # Получаем скидку пользователя
        user = await db.get_user(query.from_user.id)
        discount = user.get("discount_percent", 0) if user else 0
        
        # Генерируем CSV
        csv_buffer = await generate_csv(products, discount)
        
        # Формируем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"wb_products_{timestamp}.csv"
        
        # Отправляем файл
        document = BufferedInputFile(csv_buffer.read(), filename=filename)
        
        caption = (
            f"📊 <b>Экспорт товаров (CSV)</b>\n\n"
            f"📦 Товаров: {len(products)}\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        if discount > 0:
            caption += f"\n💳 С учётом скидки кошелька: {discount}%"
        
        await query.message.answer_document(
            document=document,
            caption=caption,
            parse_mode="HTML"
        )
        
        logger.info(f"Пользователь {query.from_user.id} экспортировал {len(products)} товаров в CSV")
        
    except Exception as e:
        logger.exception(f"Ошибка при экспорте в CSV: {e}")
        await query.message.answer(
            "❌ Произошла ошибка при формировании файла.\nПопробуйте позже."
        )
