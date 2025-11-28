"""
Сервис для работы с пользователями.
Отвечает за: создание, получение, статистику, проверки лимитов.
НЕ отвечает за: изменение настроек (это делает SettingsService).
"""
import logging
from typing import Dict, Optional

from core.entities import User
from core.enums import Plan
from core.views import UserView
from infrastructure.user_repository import UserRepository
from infrastructure.product_repository import ProductRepository
from utils.cache import cached, user_cache

logger = logging.getLogger(__name__)


def _invalidate_user_cache(user_id: int):
    """Очистить кэш пользователя."""
    user_cache.remove(f"get_user_info:{user_id}")


class UserService:
    """
    Сервис для работы с пользователями.

    Ответственность:
    - Создание и получение пользователей
    - Статистика пользователя
    - Проверки лимитов (can_add_product)
    - Управление тарифами
    """

    def __init__(
            self, user_repo: UserRepository, product_repo: ProductRepository
    ):
        self.user_repo = user_repo
        self.product_repo = product_repo

    # ===== Базовые операции с пользователем =====

    async def get_or_create_user(self, user_id: int) -> UserView:
        """Убедиться что пользователь существует, создать если нет."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            user = User(id=user_id)
            user = await self.user_repo.create(user_id)
        return UserView.from_entity(user)

    @cached(ttl=600, cache_instance=user_cache)
    async def get_user_info(self, user_id: int) -> Optional[UserView]:
        """Получить полную информацию о пользователе."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None
        return UserView.from_entity(user)

    # ===== Тарифы =====

    async def update_plan(
        self,
        user_id: int,
        plan: Plan,
        max_links: int
    ) -> bool:
        """
        Обновить тарифный план.

        Returns:
            True если успешно обновлено
        """
        success = await self.user_repo.update_plan(
            user_id, plan, max_links
        )

        if success:
            _invalidate_user_cache(user_id)

        return success

    # ===== Статистика =====

    @cached(ttl=180, cache_instance=user_cache)
    async def get_user_statistics(self, user_id: int) -> Dict:
        """
        Получить статистику пользователя.

        Returns:
            Dict со статистикой или {"exists": False}
        """
        user = await self.get_user_info(user_id)
        if not user:
            return {"exists": False}

        # Используем методы репозитория для получения данных
        total_products = await self.product_repo.count_by_user(user_id)
        out_of_stock = await self.product_repo.count_out_of_stock(user_id)
        in_stock = total_products - out_of_stock

        avg_price = await self.product_repo.get_average_price(user_id)
        cheapest = await self.product_repo.get_cheapest(user_id)
        most_expensive = await self.product_repo.get_most_expensive(user_id)

        return {
            "exists": True,
            "total_products": total_products,
            "in_stock": in_stock,
            "out_of_stock": out_of_stock,
            "avg_price": avg_price or 0,
            "cheapest": cheapest,
            "most_expensive": most_expensive
        }

    # ===== Проверки и лимиты =====

    async def can_add_product(self, user_id: int) -> tuple[bool, str]:
        """
        Проверить может ли пользователь добавить товар.
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False, "Пользователь не найден"

        current_count = await self.product_repo.count_by_user(user_id)
        return user.can_add_product(current_count)
