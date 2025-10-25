from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta


class RateLimitMiddleware(BaseMiddleware):
    """Middleware для защиты от флуда."""

    def __init__(self, rate_limit: int = 3):
        """
        Args:
            rate_limit: Максимум сообщений в секунду
        """
        self.rate_limit = rate_limit
        self.user_last_message: Dict[int, datetime] = {}
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        now = datetime.now()
        
        if user_id in self.user_last_message:
            time_passed = (now - self.user_last_message[user_id]).total_seconds()
            
            if time_passed < (1 / self.rate_limit):
                # Игнорируем сообщение
                return
        
        self.user_last_message[user_id] = now
        
        # Очистка старых записей (каждые 100 сообщений)
        if len(self.user_last_message) > 1000:
            cutoff = now - timedelta(minutes=5)
            self.user_last_message = {
                uid: ts for uid, ts in self.user_last_message.items()
                if ts > cutoff
            }
        
        return await handler(event, data)
