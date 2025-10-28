"""
Обработчики для экспорта данных.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from datetime import datetime

from services.product_service import ProductService
from services.settings_service import SettingsService
from services.user_service import UserService
from utils.export_utils import generate_excel, generate_csv
from utils.decorators import require_plan
from keyboards.kb import export_format_kb
from models import ProductRow
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "export_menu")
@require_plan(['plan_pro'], "⛔ Экспорт доступен только на тарифе Продвинутый")
async def cb_export_menu(
    query: CallbackQuery,
    product_service: ProductService,
    user_service: UserService
):
    """Меню выбора формата экспорта."""
    user_id = query.from_user.id
    
    products_analytics = await product_service.get_products_with_analytics(user_id)
    
    if not products_analytics:
        await query.answer("📭 Нет товаров для экспорта", show_alert=True)
        return
    
    await query.message.edit_text(
        f"📊 <b>Экспорт товаров</b>\n\n"
        f"📦 Всего товаров: {len(products_analytics)}\n\n"
        f"Выберите формат файла:",
        parse_mode="HTML",
        reply_markup=export_format_kb()
    )
    await query.answer()


@router.callback_query(F.data == "export_excel")
@require_plan(['plan_pro'], "⛔ Экспорт доступен только на тарифе Продвинутый")
async def cb_export_excel(
    query: CallbackQuery,
    product_service: ProductService,
    settings_service: SettingsService,
    user_service: UserService
):
    """Выгрузка товаров в Excel."""
    user_id = query.from_user.id
    
    products_analytics = await product_service.get_products_with_analytics(user_id)
    
    if not products_analytics:
        await query.answer("📭 Нет товаров для экспорта", show_alert=True)
        return
    
    await query.answer("⏳ Формирую файл...")
    
    try:
        # Получаем скидку пользователя
        settings = await settings_service.get_user_settings(user_id)
        discount = settings.get("discount", 0)
        
        # Конвертируем в ProductRow
        products = [
            ProductRow(**item["product"])
            for item in products_analytics
        ]
        
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
        
        logger.info(f"Пользователь {user_id} экспортировал {len(products)} товаров в Excel")
        
    except Exception as e:
        logger.exception(f"Ошибка при экспорте в Excel: {e}")
        await query.message.answer(
            "❌ Произошла ошибка при формировании файла.\nПопробуйте позже."
        )


@router.callback_query(F.data == "export_csv")
@require_plan(['plan_pro'], "⛔ Экспорт доступен только на тарифе Продвинутый")
async def cb_export_csv(
    query: CallbackQuery,
    product_service: ProductService,
    settings_service: SettingsService,
    user_service: UserService
):
    """Выгрузка товаров в CSV."""
    user_id = query.from_user.id
    
    products_analytics = await product_service.get_products_with_analytics(user_id)
    
    if not products_analytics:
        await query.answer("📭 Нет товаров для экспорта", show_alert=True)
        return
    
    await query.answer("⏳ Формирую файл...")
    
    try:
        # Получаем скидку пользователя
        settings = await settings_service.get_user_settings(user_id)
        discount = settings.get("discount", 0)
        
        # Конвертируем в ProductRow
        products = [
            ProductRow(**item["product"])
            for item in products_analytics
        ]
        
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
        
        logger.info(f"Пользователь {user_id} экспортировал {len(products)} товаров в CSV")
        
    except Exception as e:
        logger.exception(f"Ошибка при экспорте в CSV: {e}")
        await query.message.answer(
            "❌ Произошла ошибка при формировании файла.\nПопробуйте позже."
        )
