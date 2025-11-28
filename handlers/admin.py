"""
Обработчики для администратора бота.
"""
import logging

from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, BaseFilter

from keyboards.kb import (
    admin_menu_kb, back_to_admin_menu_kb, user_management_kb, 
    plan_selection_kb
)
from infrastructure.user_repository import UserRepository
from infrastructure.product_repository import ProductRepository
from config import settings
from utils.error_tracker import get_error_tracker
from utils.health_monitor import get_health_monitor

router = Router()
logger = logging.getLogger(__name__)


# ============= ФИЛЬТРЫ =============

class IsAdmin(BaseFilter):
    """Фильтр для проверки, является ли пользователь администратором."""

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id == settings.ADMIN_CHAT_ID


class IsAdminCallback(BaseFilter):
    """Фильтр для callback query от администратора."""

    async def __call__(self, query: CallbackQuery) -> bool:
        return query.from_user.id == settings.ADMIN_CHAT_ID


# ============= КОМАНДЫ =============
@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: Message):
    """Главное меню администратора."""
    text = (
        "🔧 <b>Панель администратора</b>\n\n"
        f"👤 Администратор: {message.from_user.full_name}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        "Выберите действие:"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin_menu", IsAdminCallback())
async def cb_admin_menu(query: CallbackQuery):
    """Обновление главного меню."""
    text = (
        "🔧 <b>Панель администратора</b>\n\n"
        f"👤 Администратор: {query.from_user.full_name}\n"
        f"🆔 ID: <code>{query.from_user.id}</code>\n"
        f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        "Выберите действие:"
    )
    
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=admin_menu_kb())
    await query.answer()


# ============= СТАТИСТИКА =============

@router.message(Command("stats"), IsAdmin())
@router.callback_query(F.data == "admin_stats", IsAdminCallback())
async def show_stats(
    event, 
    user_repo: UserRepository,
    product_repo: ProductRepository,
    price_history_repo
):
    """Показать общую статистику бота."""
    # Определяем тип события
    is_callback = isinstance(event, CallbackQuery)
    message = event.message if is_callback else event
    
    try:
        # Получаем статистику через репозитории
        total_users = await user_repo.count_total()
        users_today = await user_repo.count_recent(1)
        users_week = await user_repo.count_recent(7)
        
        # Товары
        total_products = await product_repo.count_total()
        
        # Тарифы
        plans_stats = await user_repo.get_plan_stats_with_names()
        
        # История цен
        history_count = await price_history_repo.count_total()
        history_today = await price_history_repo.count_recent(1)
        
        # Формируем сообщение
        text = (
            "📊 <b>Статистика бота</b>\n\n"
            
            "👥 <b>Пользователи:</b>\n"
            f"• Всего: {total_users}\n"
            f"• За сегодня: +{users_today}\n"
            f"• За неделю: +{users_week}\n\n"
            
            "📦 <b>Товары:</b>\n"
            f"• Всего: {total_products}\n"
            f"• Среднее на юзера: {total_products / total_users if total_users > 0 else 0:.1f}\n\n"
            
            "💳 <b>Тарифы:</b>\n"
        )
        
        for plan in plans_stats:
            percentage = (plan['count'] / total_users * 100) if total_users > 0 else 0
            text += f"• {plan['plan_name']}: {plan['count']} ({percentage:.1f}%)\n"
        
        text += (
            f"\n📈 <b>История цен:</b>\n"
            f"• Всего записей: {history_count}\n"
            f"• За сегодня: +{history_today}\n\n"
            f"⏰ Обновлено: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        if is_callback:
            await message.edit_text(text, parse_mode="HTML", reply_markup=back_to_admin_menu_kb())
            await event.answer()
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=back_to_admin_menu_kb())
            
    except Exception as e:
        logger.exception(f"Ошибка при получении статистики: {e}")
        error_text = "❌ Ошибка при получении статистики"
        
        if is_callback:
            await event.answer(error_text, show_alert=True)
        else:
            await message.answer(error_text)


# ============= ЗДОРОВЬЕ СИСТЕМЫ =============

@router.message(Command("health"), IsAdmin())
@router.callback_query(F.data == "admin_health", IsAdminCallback())
async def show_health(event, container):
    """Показать здоровье системы."""
    is_callback = isinstance(event, CallbackQuery)
    message = event.message if is_callback else event
    
    if is_callback:
        await event.answer("⏳ Проверяю здоровье системы...")
    else:
        status_msg = await message.answer("🔄 Проверяю здоровье системы...")
    
    try:
        monitor = get_health_monitor()
        health_data = await monitor.perform_full_check(container.db)
        formatted_message = monitor.format_status_message(health_data)
        
        if is_callback:
            await message.edit_text(
                formatted_message,
                parse_mode="HTML",
                reply_markup=back_to_admin_menu_kb()
            )
        else:
            await status_msg.edit_text(
                formatted_message,
                parse_mode="HTML",
                reply_markup=back_to_admin_menu_kb()
            )
            
    except Exception as e:
        logger.exception(f"Ошибка при проверке здоровья: {e}")
        error_text = f"❌ Ошибка при проверке: {str(e)}"
        
        if is_callback:
            await event.answer(error_text, show_alert=True)
        else:
            await message.answer(error_text)


# ============= ОШИБКИ API =============

@router.message(Command("errors"), IsAdmin())
@router.callback_query(F.data == "admin_errors", IsAdminCallback())
async def show_api_errors(event):
    """Показать статистику ошибок API."""
    is_callback = isinstance(event, CallbackQuery)
    message = event.message if is_callback else event
    
    try:
        tracker = get_error_tracker()
        stats = tracker.get_statistics()
        
        status_icon = "✅" if stats['is_healthy'] else "⚠️"
        if stats['is_critical']:
            status_icon = "🚨"
        
        text = (
            f"{status_icon} <b>Статистика API Wildberries</b>\n\n"
            f"⏱ Окно: {stats['window_minutes']:.0f} минут\n"
            f"📊 Всего запросов: {stats['total_requests']}\n"
            f"✅ Успешных: {stats['total_successes']}\n"
            f"❌ Ошибок: {stats['total_errors']}\n"
            f"📈 Процент ошибок: <b>{stats['error_rate_percent']}%</b>\n\n"
        )
        
        if stats['error_breakdown']:
            text += "📋 <b>Типы ошибок:</b>\n"
            for error_type, count in stats['error_breakdown'].items():
                text += f"• {error_type}: {count}\n"
            text += "\n"
        
        # Статус
        if stats['is_critical']:
            text += "🚨 <b>Статус: КРИТИЧЕСКИЙ</b>\n"
            text += "Требуется вмешательство!"
        elif not stats['is_healthy']:
            text += "⚠️ <b>Статус: ПРЕДУПРЕЖДЕНИЕ</b>\n"
            text += "Повышенный уровень ошибок"
        else:
            text += "✅ <b>Статус: ЗДОРОВ</b>\n"
            text += "Всё работает нормально"
        
        if is_callback:
            await message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=back_to_admin_menu_kb()
            )
            await event.answer()
        else:
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=back_to_admin_menu_kb()
            )
            
    except Exception as e:
        logger.exception(f"Ошибка при получении статистики ошибок: {e}")
        error_text = "❌ Ошибка при получении статистики"
        
        if is_callback:
            await event.answer(error_text, show_alert=True)
        else:
            await message.answer(error_text)


# ============= УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ =============

@router.callback_query(F.data == "admin_users", IsAdminCallback())
async def show_users_menu(query: CallbackQuery, user_repo: UserRepository):
    """Меню управления пользователями."""
    try:
        total = await user_repo.count_total()
        recent = await user_repo.get_all()  # Уже отсортировано
        recent = recent[:10]  # Берём первые 10
        
        text = (
            "👥 <b>Управление пользователями</b>\n\n"
            f"Всего пользователей: {total}\n\n"
            "<b>Последние 10 пользователей:</b>\n"
        )
        
        for i, user in enumerate(recent, 1):
            user_id_masked = str(user['id'])[:4] + "****"
            created = user['created_at'].strftime('%d.%m %H:%M')
            text += f"{i}. ID: {user_id_masked} | {user['plan_name']} | {created}\n"
        
        text += "\n💡 Используйте /user <id> для управления пользователем"
        
        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=back_to_admin_menu_kb()
        )
        await query.answer()
        
    except Exception as e:
        logger.exception(f"Ошибка при получении списка пользователей: {e}")
        await query.answer("❌ Ошибка при получении данных", show_alert=True)


@router.message(Command("user"), IsAdmin())
async def cmd_user_manage(
    message: Message, 
    user_repo: UserRepository,
    product_repo: ProductRepository
):
    """Управление конкретным пользователем."""
    try:
        # Извлекаем user_id из команды
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer(
                "❌ Укажите ID пользователя\n"
                "Использование: /user <id>"
            )
            return
        
        try:
            user_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат ID")
            return
        
        # Получаем данные пользователя
        user = await user_repo.get_by_id(user_id)
        
        if not user:
            await message.answer(f"❌ Пользователь {user_id} не найден")
            return
        
        products_count = await product_repo.count_by_user(user_id)
        
        text = (
            f"👤 <b>Пользователь {user_id}</b>\n\n"
            f"📋 Тариф: {user.get('plan_name', 'Неизвестно')}\n"
            f"📊 Лимит товаров: {user.get('max_links', 0)}\n"
            f"📦 Используется: {products_count}\n"
            f"💳 Скидка WB: {user.get('discount_percent', 0)}%\n"
            f"📍 Регион (dest): {user.get('dest', 'Не установлен')}\n"
            f"📅 Регистрация: {user.get('created_at', 'N/A')}\n\n"
            "Выберите действие:"
        )
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=user_management_kb(user_id)
        )
        
    except Exception as e:
        logger.exception(f"Ошибка при управлении пользователем: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("admin_change_plan:"), IsAdminCallback())
async def cb_change_plan(query: CallbackQuery):
    """Изменить тариф пользователя."""
    user_id = int(query.data.split(":")[1])
    
    text = (
        f"💳 <b>Изменение тарифа</b>\n\n"
        f"Пользователь: <code>{user_id}</code>\n\n"
        "Выберите новый тариф:"
    )
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=plan_selection_kb(user_id)
    )
    await query.answer()


@router.callback_query(F.data.startswith("admin_set_plan:"), IsAdminCallback())
async def cb_set_plan(query: CallbackQuery, user_repo: UserRepository):
    """Установить тариф пользователю."""
    try:
        parts = query.data.split(":")
        user_id = int(parts[1])
        plan_key = parts[2]
        max_links = int(parts[3])
        
        plan_names = {
            "plan_free": "Бесплатный",
            "plan_basic": "Базовый",
            "plan_pro": "Продвинутый"
        }
        
        plan_name = plan_names.get(plan_key, "Неизвестный")
        
        await user_repo.set_plan(user_id, plan_key, plan_name, max_links)
        
        await query.answer(
            f"✅ Тариф изменён на {plan_name} ({max_links} товаров)",
            show_alert=True
        )
        
        # Возвращаемся к управлению пользователем
        # Вызываем handler напрямую
        class FakeMessage:
            def __init__(self):
                self.text = f"/user {user_id}"
                self.from_user = query.from_user
            
            async def answer(self, *args, **kwargs):
                await query.message.edit_text(*args, **kwargs)
        
        fake_msg = FakeMessage()
        await cmd_user_manage(fake_msg, user_repo, None)
        
    except Exception as e:
        logger.exception(f"Ошибка при установке тарифа: {e}")
        await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


# ============= ПЛАТЕЖИ (ЗАГЛУШКИ) =============

@router.callback_query(F.data == "admin_payments", IsAdminCallback())
async def show_payments(query: CallbackQuery):
    """Статистика платежей (заглушка)."""
    text = (
        "💳 <b>Платежи и подписки</b>\n\n"
        "🚧 <b>Модуль в разработке</b>\n\n"
        "Планируемый функционал:\n"
        "• 📊 Статистика платежей\n"
        "• 💰 Общая выручка\n"
        "• 📈 Конверсия в платные тарифы\n"
        "• 🔄 Управление подписками\n"
        "• 💳 Возвраты и отмены\n\n"
        "📅 Запуск: Q1 2025"
    )
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_admin_menu_kb()
    )
    await query.answer()


# ============= РАССЫЛКА =============

@router.callback_query(F.data == "admin_broadcast", IsAdminCallback())
async def show_broadcast_menu(query: CallbackQuery):
    """Меню рассылки."""
    text = (
        "📨 <b>Рассылка сообщений</b>\n\n"
        "🚧 <b>Функция в разработке</b>\n\n"
        "Для рассылки используйте команду:\n"
        "<code>/broadcast Текст сообщения</code>\n\n"
        "⚠️ Будьте осторожны с рассылками!\n"
        "Telegram может заблокировать бота за спам."
    )
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_admin_menu_kb()
    )
    await query.answer()


# ============= СИСТЕМА =============

@router.callback_query(F.data == "admin_system", IsAdminCallback())
async def show_system_info(query: CallbackQuery):
    """Системная информация."""
    import sys
    import platform
    
    text = (
        "🔧 <b>Системная информация</b>\n\n"
        f"🐍 Python: {sys.version.split()[0]}\n"
        f"💻 ОС: {platform.system()} {platform.release()}\n"
        f"🏗 Архитектура: {platform.machine()}\n\n"
        f"📦 Версия бота: 1.0.0\n"
        f"⏰ Запущен: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    )
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_admin_menu_kb()
    )
    await query.answer()


@router.callback_query(F.data == "admin_products", IsAdminCallback())
async def show_products_stats(query: CallbackQuery, product_repo: ProductRepository):
    """Статистика по товарам."""
    try:
        total = await product_repo.count_total()
        out_of_stock = await product_repo.count_out_of_stock_total()
        
        text = (
            "📦 <b>Статистика товаров</b>\n\n"
            f"Всего товаров в мониторинге: {total}\n"
            f"Нет в наличии: {out_of_stock}\n\n"
        )
        
        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=back_to_admin_menu_kb()
        )
        await query.answer()
        
    except Exception as e:
        logger.exception(f"Ошибка при получении статистики товаров: {e}")
        await query.answer("❌ Ошибка при получении данных", show_alert=True)
