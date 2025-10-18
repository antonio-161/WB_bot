from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.user_states import AddProductState
from services.db import DB
from services.price_fetcher import PriceFetcher
from utils.wb_utils import extract_nm_id
from keyboards.kb import products_inline, main_inline_kb, sizes_inline_kb
from decimal import Decimal
import logging

router = Router()
logger = logging.getLogger(__name__)


# ---------------- Добавление товара ----------------
@router.callback_query(F.data == "add_product")
async def cb_add_product(query: CallbackQuery, state: FSMContext):
    """Запрос ссылки для отслеживания товара через InlineKeyboard."""
    await query.message.answer(
        "📎 Отправьте ссылку на товар Wildberries для отслеживания.\n"
        "Лимит зависит от вашего тарифа."
    )
    await state.set_state(AddProductState.waiting_for_url)
    await query.answer()


@router.message(AddProductState.waiting_for_url)
async def add_url(message: Message, state: FSMContext, db: DB, price_fetcher: PriceFetcher):
    url = message.text.strip()
    nm = extract_nm_id(url)

    if not nm:
        await message.answer("❌ Не удалось извлечь артикул из ссылки WB. Пришлите правильную ссылку.")
        return

    await db.ensure_user(message.from_user.id)
    user = await db.get_user(message.from_user.id)
    prods = await db.list_products(message.from_user.id)
    max_links = user.get("max_links", 5)

    if len(prods) >= max_links:
        await message.answer(
            f"⛔ Достигнут лимит ({max_links}) товаров.\nУдалите старый товар или обновите тариф.",
            reply_markup=main_inline_kb()
        )
        await state.clear()
        return

    status_msg = await message.answer("⏳ Получаю информацию о товаре...")

    try:
        product_data = await price_fetcher.get_product_data(nm)
        if not product_data:
            await status_msg.edit_text("❌ Не удалось получить данные о товаре. Попробуйте позже.")
            await state.clear()
            return

        product_name = product_data.get("name", f"Товар {nm}")
        sizes = product_data.get("sizes", [])

        # Если есть размеры — переходим в выбор размера
        if sizes:
            # Сохраняем временные данные в FSM
            await state.update_data(url=url, nm=nm, product_name=product_name)
            valid_sizes = [s for s in sizes if s.get("name") not in ("", "0") and s.get("origName") not in ("", "0")]

            await status_msg.edit_text(
                f"📦 <b>{product_name}</b>\n"
                f"🔢 Артикул: {nm}\n\n"
                "Выберите размер для отслеживания:",
                reply_markup=sizes_inline_kb(nm, valid_sizes),
                parse_mode="HTML"
            )
            await state.set_state(AddProductState.waiting_for_size)
        else:
            # Товар без размеров — добавляем сразу
            product_id = await db.add_product(message.from_user.id, url, nm, product_name)
            if not product_id:
                await status_msg.edit_text("⚠️ Этот товар уже в отслеживании.", reply_markup=main_inline_kb())
                await state.clear()
                return

            await db.update_prices(
                product_id=product_id,
                basic=Decimal(str(product_data["price"]["basic"])),
                product=Decimal(str(product_data["price"]["product"]))
            )

            await status_msg.edit_text(
                f"✅ Товар добавлен!\n\n"
                f"📦 {product_name}\n"
                f"🔢 Артикул: {nm}\n"
                f"💰 Текущая цена: {product_data['price']['product']:.2f} ₽\n\n"
                "Я буду отслеживать изменения цены.",
                reply_markup=main_inline_kb()
            )
            await state.clear()

    except Exception as e:
        logger.exception(f"Ошибка при добавлении товара {nm}: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при добавлении товара. Попробуйте позже.")
        await state.clear()

# ---------------- Список товаров ----------------
@router.callback_query(F.data == "list_products")
async def cb_list_products(query: CallbackQuery, db: DB):
    """Список отслеживаемых товаров через InlineKeyboard."""
    products = await db.list_products(query.from_user.id)
    
    if not products:
        await query.message.edit_text(
            "📭 Список пуст.\n"
            "Добавьте товар для отслеживания!",
            reply_markup=main_inline_kb()
        )
        await query.answer()
        return

    text = "📦 <b>Отслеживаемые товары:</b>\n\n"
    products_data = []
    
    for i, p in enumerate(products, 1):
        price_info = ""
        if p.last_product_price:
            price_info = f" — {float(p.last_product_price):.2f} ₽"
        
        text += f'{i}. <a href="{p.url_product}">{p.name_product}</a>{price_info}\n'
        products_data.append({"nm_id": p.nm_id, "name": p.name_product})

    await query.message.edit_text(
        text,
        reply_markup=products_inline(products_data),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await query.answer()


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
        text += f'{i}. {p.name_product}\n'
        kb_buttons.append([
            {
                "text": f"❌ {p.name_product[:30]}...",
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
async def cb_remove(query: CallbackQuery, db: DB):
    """Удаление товара через InlineKeyboard."""
    nm = int(query.data.split(":", 1)[1])
    ok = await db.remove_product(query.from_user.id, nm)
    
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


@router.callback_query(lambda c: c.data and c.data.startswith("select_size:"), AddProductState.waiting_for_size)
async def select_size_cb(query: CallbackQuery, state: FSMContext, db: DB):
    """Пользователь выбрал размер для товара."""
    try:
        _, nm_str, size_name = query.data.split(":")
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
        product_data = await PriceFetcher().get_product_data(nm)
        if product_data and product_data.get("sizes"):
            size_data = next((s for s in product_data["sizes"] if s["name"] == size_name), None)
            if size_data:
                await db.update_prices(
                    product_id=product_id,
                    basic=Decimal(str(size_data["price"]["basic"])),
                    product=Decimal(str(size_data["price"]["product"]))
                )

        await query.message.edit_text(
            f"✅ Товар <b>{product_name}</b>\n"
            f"🔢 Артикул: {nm}\n"
            f"🔘 Размер выбран: <b>{size_name}</b>\n\n"
            "Теперь я буду отслеживать цены и остатки для этого размера.",
            parse_mode="HTML",
            reply_markup=main_inline_kb()
        )
        await query.answer("Размер выбран!")
        await state.clear()

    except Exception as e:
        logger.exception(f"Ошибка при выборе размера: {e}")
        await query.answer("❌ Произошла ошибка при выборе размера.", show_alert=True)
        await state.clear()


@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(query: CallbackQuery):
    """Возврат в главное меню."""
    await query.message.edit_text(
        "🏠 Главное меню",
        reply_markup=main_inline_kb()
    )
    await query.answer()
