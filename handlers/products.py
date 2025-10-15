from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.user_states import AddProductState
from services.db import DB
from services.price_fetcher import PriceFetcher
from utils.wb_utils import extract_nm_id
from keyboards.kb import products_inline, main_inline_kb
from decimal import Decimal


router = Router()


# ---------------- Добавление товара ----------------
@router.callback_query(F.data == "add_product")
async def cb_add_product(query: CallbackQuery, state: FSMContext):
    """Запрос ссылки для отслеживания товара через InlineKeyboard."""
    await query.message.answer(
        "Отправь ссылку на товар Wildberries для отслеживания (лимит зависит от вашего тарифа)."
    )
    await state.set_state(AddProductState.waiting_for_url)
    await query.answer()


@router.message(AddProductState.waiting_for_url)
async def add_url(message: Message, state: FSMContext, db: DB):
    """Добавление ссылки после запроса через InlineKeyboard."""
    url = message.text.strip()
    nm = extract_nm_id(url)
    if not nm:
        await message.answer(
            "Не удалось извлечь nm_id из ссылки. Пришли валидную ссылку WB."
        )
        await state.clear()
        return

    await db.ensure_user(message.from_user.id)
    user = await db.get_user(message.from_user.id)
    prods = await db.list_products(message.from_user.id)
    max_links = user.get("max_links", 3)
    if len(prods) >= max_links:
        await message.answer(
            f"Достигнут лимит ({max_links}) ссылок. "
            "Удалите старую или обновите подписку."
        )
        await state.clear()
        return

    added = await db.add_product(message.from_user.id, url, nm)
    if not added:
        await message.answer("Этот товар уже в отслеживании.")
        await state.clear()
        return

    # Сразу сохраняем текущую цену
    fetcher = PriceFetcher()
    try:
        prices = await fetcher.get_price(nm)
        last_id = (await db.list_products(message.from_user.id))[-1].id
        await db.update_prices(
            product_id=last_id,
            basic=Decimal(str(prices["basic"])),
            product=Decimal(str(prices["product"]))
        )
    except Exception:
        pass

    await message.answer(
        f"Добавлен товар nm={nm}. Я буду отслеживать цену.",
        reply_markup=main_inline_kb()
    )
    await state.clear()


# ---------------- Список товаров ----------------
@router.callback_query(F.data == "list_products")
async def cb_list_products(query: CallbackQuery, db: DB):
    """Список отслеживаемых товаров через InlineKeyboard."""
    products = await db.list_products(query.from_user.id)
    if not products:
        await query.message.answer(
            "Список пуст. Добавьте товар через кнопку ➕ Добавить товар."
        )
        await query.answer()
        return

    text = "Отслеживаемые товары:\n"
    arr = []
    for p in products:
        text += f'<a href="{p.url_product}">🛍 {p.name_product}</a>\n'
        arr.append({"name": p.name_product})

    await query.message.answer(
        text,
        reply_markup=products_inline(arr),  # твоя inline клавиатура
        parse_mode="HTML"
    )
    await query.answer()


# ---------------- Удаление товара ----------------
@router.callback_query(F.data.startswith("rm:"))
async def cb_remove(query: CallbackQuery, db: DB):
    """Удаление товара через InlineKeyboard."""
    await query.answer()
    nm = int(query.data.split(":", 1)[1])
    ok = await db.remove_product(query.from_user.id, nm)
    if ok:
        await query.message.edit_text(
            "✅ Товар удалён.", reply_markup=main_inline_kb()
        )
    else:
        await query.message.edit_text(
            "❌ Не получилось удалить или запись не найдена.",
            reply_markup=main_inline_kb()
        )
