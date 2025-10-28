import functools
import asyncio
import logging
from typing import List
from aiogram.types import CallbackQuery

logger = logging.getLogger(__name__)


def retry_on_error(max_attempts=3, delay=2, exceptions=(Exception,)):
    """
    Декоратор для повторных попыток при ошибках.
    
    Args:
        max_attempts: Максимум попыток
        delay: Базовая задержка (секунды)
        exceptions: Кортеж исключений для retry
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            func_name = func.__name__
            
            for attempt in range(1, max_attempts + 1):
                try:
                    result = await func(*args, **kwargs)
                    
                    # Логируем успех после retry
                    if attempt > 1:
                        logger.info(f"✅ {func_name} успешно выполнена с попытки {attempt}")
                    
                    return result
                    
                except exceptions as e:
                    last_error = e
                    
                    if attempt < max_attempts:
                        wait_time = delay * (2 ** (attempt - 1))  # Экспоненциальная задержка
                        logger.warning(
                            f"⚠️ {func_name} попытка {attempt}/{max_attempts} провалилась: {e}. "
                            f"Повтор через {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"❌ {func_name} все {max_attempts} попытки провалились. "
                            f"Последняя ошибка: {e}"
                        )
            
            raise last_error
        
        return wrapper
    return decorator


def require_plan(allowed_plans: List[str], error_message: str = None):
    """
    Декоратор для проверки тарифного плана.
    
    Args:
        allowed_plans: Список разрешённых планов ['plan_basic', 'plan_pro']
        error_message: Кастомное сообщение об ошибке
    
    Usage:
        @require_plan(['plan_basic', 'plan_pro'], "⛔ Только для платных тарифов")
        async def my_handler(query: CallbackQuery, user_service: UserService):
            # Код выполнится только если тариф подходит
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(query: CallbackQuery, *args, **kwargs):
            # Получаем user_service из kwargs (DI middleware его добавляет)
            user_service = kwargs.get("user_service")
            
            if not user_service:
                logger.error(f"UserService not found in handler {func.__name__}")
                await query.answer("❌ Внутренняя ошибка. Попробуйте позже.", show_alert=True)
                return

            # Проверка тарифа через сервис
            user = await user_service.get_user_info(query.from_user.id)
            user_plan = user.get("plan", "plan_free") if user else "plan_free"

            if user_plan not in allowed_plans:
                default_msg = (
                    f"⛔ Эта функция доступна только на тарифах: "
                    f"{', '.join([p.replace('plan_', '').title() for p in allowed_plans])}"
                )
                await query.answer(error_message or default_msg, show_alert=True)
                return

            return await func(query, *args, **kwargs)
        return wrapper
    return decorator