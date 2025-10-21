from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import DB
from keyboards.kb import back_to_menu_kb

router = Router()


@router.callback_query(F.data == "my_stats")
async def show_stats(query: CallbackQuery, db: DB):
    """Показать статистику пользователя."""
    user = await db.get_user(query.from_user.id)
    products = await db.list_products(query.from_user.id)
    
    if not user:
        await query.answer("Ошибка получения данных", show_alert=True)
        return
    
    # Подсчёт статистики
    total_products = len(products)
    in_stock = sum(1 for p in products if not p.out_of_stock)
    out_of_stock = total_products - in_stock
    
    # Средняя цена
    avg_price = 0
    if products:
        prices = [p.last_product_price for p in products if p.last_product_price]
        if prices:
            avg_price = sum(prices) // len(prices)
    
    # Самый дешёвый и дорогой товар
    cheapest = None
    most_expensive = None
    if products:
        sorted_by_price = sorted(
            [p for p in products if p.last_product_price],
            key=lambda x: x.last_product_price
        )
        if sorted_by_price:
            cheapest = sorted_by_price[0]
            most_expensive = sorted_by_price[-1]
    
    text = (
        f"📊 <b>Ваша статистика</b>\n\n"
        f"📦 <b>Всего товаров:</b> {total_products}\n"
        f"✅ <b>В наличии:</b> {in_stock}\n"
        f"❌ <b>Нет в наличии:</b> {out_of_stock}\n\n"
        f"💰 <b>Средняя цена:</b> {avg_price} ₽\n"
    )
    
    if cheapest:
        text += f"\n🔽 <b>Самый дешёвый:</b>\n{cheapest.display_name[:40]} — {cheapest.last_product_price} ₽\n"
    
    if most_expensive:
        text += f"\n🔼 <b>Самый дорогой:</b>\n{most_expensive.display_name[:40]} — {most_expensive.last_product_price} ₽\n"
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_menu_kb()
    )
    await query.answer()
