from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from states.user_states import AddProductState, RenameProductState
from services.db import DB
from services.price_fetcher import PriceFetcher
from utils.wb_utils import extract_nm_id
from keyboards.kb import (
    products_inline, main_inline_kb, sizes_inline_kb,
    product_detail_kb, confirm_remove_kb, back_to_product_kb
)
from utils.graph_generator import generate_price_graph
from decimal import Decimal
import logging

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
            price_basic = Decimal(str(price_info.get("basic", 0)))
            price_product = Decimal(str(price_info.get("product", 0)))
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
                from utils.wb_utils import apply_wallet_discount
                final_price = apply_wallet_discount(display_price, discount)
                price_text = f"💰 Цена: {display_price} ₽\n💳 С кошельком ({discount}%): {int(final_price)} ₽"

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
                price_basic = Decimal(str(price_info.get("basic", 0)))
                price_product = Decimal(str(price_info.get("product", 0)))
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
    """Список отслеживаемых товаров."""
    products = await db.list_products(query.from_user.id)
    
    if not products:
        await query.message.edit_text(
            "📭 Список пуст.\n"
            "Добавьте товар для отслеживания!",
            reply_markup=main_inline_kb()
        )
        await query.answer()
        return

    # Получаем скидку пользователя
    user = await db.get_user(query.from_user.id)
    discount = user.get("discount_percent", 0) if user else 0

    text = "📦 <b>Отслеживаемые товары:</b>\n\n"
    products_data = []
    
    for i, p in enumerate(products, 1):
        display_name = p.display_name
        price_info = ""
        if p.last_product_price:
            price = float(p.last_product_price)
            if discount > 0:
                from utils.wb_utils import apply_wallet_discount
                final_price = apply_wallet_discount(price, discount)
                price_info = f" — {final_price:.2f} ₽"
            else:
                price_info = f" — {price:.2f} ₽"
        
        text += f'{i}. {display_name[:45]}{price_info}\n'
        products_data.append({"nm_id": p.nm_id, "name": display_name})

    if discount > 0:
        text += f"\n💳 <i>Цены с учётом скидки кошелька {discount}%</i>"

    await query.message.edit_text(
        text,
        reply_markup=products_inline(products_data),
        parse_mode="HTML"
    )
    await query.answer()


# ---------------- Детальная информация о товаре ----------------
@router.callback_query(F.data.startswith("product_detail:"))
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
        price = float(product.last_product_price)
        if discount > 0:
            from utils.wb_utils import apply_wallet_discount
            final_price = apply_wallet_discount(price, discount)
            text += f"💰 Цена: {price:.2f} ₽\n"
            text += f"💳 С кошельком ({discount}%): <b>{final_price:.2f} ₽</b>\n"
        else:
            text += f"💰 Текущая цена: <b>{price:.2f} ₽</b>\n"
    
    if product.last_qty is not None:
        if product.out_of_stock:
            text += f"📦 Остаток: <b>Нет в наличии</b>\n"
        else:
            text += f"📦 Остаток: <b>{product.last_qty} шт.</b>\n"
    
    # Статистика из истории
    if history:
        prices = [float(h.product_price) for h in history]
        min_price = min(prices)
        max_price = max(prices)
        text += f"\n📊 <b>Статистика:</b>\n"
        
        if discount > 0:
            from utils.wb_utils import apply_wallet_discount
            min_with_discount = apply_wallet_discount(min_price, discount)
            max_with_discount = apply_wallet_discount(max_price, discount)
            text += f"• Мин. цена: {min_with_discount:.2f} ₽ (было {min_price:.2f} ₽)\n"
            text += f"• Макс. цена: {max_with_discount:.2f} ₽ (было {max_price:.2f} ₽)\n"
        else:
            text += f"• Мин. цена: {min_price:.2f} ₽\n"
            text += f"• Макс. цена: {max_price:.2f} ₽\n"
    
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
        # Генерируем график
        graph_buffer = await generate_price_graph(history, product.display_name)
        
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

    text = "🗑 <b>Выберите товар для удаления:</b>\n\n"
    kb_buttons = []
    
    for i, p in enumerate(products, 1):
        display_name = p.display_name
        text += f'{i}. {display_name}\n'
        kb_buttons.append([
            {
                "text": f"❌ {display_name[:30]}...",
                "callback_data": f"rm:{p.nm_id}"
            }
        ])
    
    kb_buttons.append([{"text": "« Назад", "callback_data": "back_to_menu"}])
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])]
            for row in kb_buttons for btn in row
        ]
    )
    
    await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
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
        "🏠 Главное меню",
        reply_markup=main_inline_kb()
    )
    await query.answer()

