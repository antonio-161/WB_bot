"""
Обработчики для статистики пользователя.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from services.user_service import UserService
from keyboards.kb import back_to_menu_kb

router = Router()


@router.callback_query(F.data == "my_stats")
async def show_stats(
    query: CallbackQuery,
    user_service: UserService
):
    """Показать статистику пользователя."""
    user_id = query.from_user.id
    
    # Получаем статистику через сервис
    stats = await user_service.get_user_statistics(user_id)
    
    if not stats.get("exists"):
        await query.answer("Ошибка получения данных", show_alert=True)
        return
    
    total_products = stats["total_products"]
    in_stock = stats["in_stock"]
    out_of_stock = stats["out_of_stock"]
    avg_price = stats["avg_price"]
    cheapest = stats["cheapest"]
    most_expensive = stats["most_expensive"]
    
    text = (
        f"📊 <b>Ваша статистика</b>\n\n"
        f"📦 <b>Всего товаров:</b> {total_products}\n"
        f"✅ <b>В наличии:</b> {in_stock}\n"
        f"❌ <b>Нет в наличии:</b> {out_of_stock}\n\n"
        f"💰 <b>Средняя цена:</b> {avg_price} ₽\n"
    )
    
    if cheapest:
        cheapest_name = cheapest.get("custom_name") or cheapest.get("name_product", "")
        cheapest_price = cheapest.get("last_product_price", 0)
        text += (
            f"\n🔽 <b>Самый дешёвый:</b>\n"
            f"{cheapest_name[:40]} — {cheapest_price} ₽\n"
        )
    
    if most_expensive:
        expensive_name = most_expensive.get("custom_name") or most_expensive.get("name_product", "")
        expensive_price = most_expensive.get("last_product_price", 0)
        text += (
            f"\n🔼 <b>Самый дорогой:</b>\n"
            f"{expensive_name[:40]} — {expensive_price} ₽\n"
        )
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_menu_kb()
    )
    await query.answer()
