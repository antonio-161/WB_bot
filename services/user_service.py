"""
Сервис для работы с пользователями.
Содержит бизнес-логику управления пользователями.
"""
import logging
from typing import Dict, Optional

from repositories.user_repository import UserRepository
from repositories.product_repository import ProductRepository
from utils.cache import cached, user_cache, settings_cache

logger = logging.getLogger(__name__)


def _invalidate_user_cache(user_id: int):
    """Очистить кэш пользователя."""
    user_cache.remove(f"get_user_info:{user_id}")
    settings_cache.remove(f"get_user_settings:{user_id}")


class UserService:
    """Сервис для работы с пользователями."""
    
    def __init__(self, user_repo: UserRepository, product_repo: ProductRepository):
        self.user_repo = user_repo
        self.product_repo = product_repo
    
    async def ensure_user_exists(self, user_id: int) -> Dict:
        """Убедиться что пользователь существует, создать если нет."""
        return await self.user_repo.ensure_exists(user_id)
    
    @cached(ttl=600, cache_instance=user_cache)
    async def get_user_info(self, user_id: int) -> Optional[Dict]:
        """Получить полную информацию о пользователе."""
        return await self.user_repo.get_by_id(user_id)
    
    async def update_plan(
        self,
        user_id: int,
        plan_key: str,
        plan_name: str,
        max_links: int
    ) -> bool:
        """Обновить тарифный план."""
        await self.ensure_user_exists(user_id)
        success = await self.user_repo.set_plan(user_id, plan_key, plan_name, max_links)

        if success:
            _invalidate_user_cache(user_id)
        
        return success
    
    async def update_discount(self, user_id: int, discount: int) -> bool:
        """Обновить процент скидки WB кошелька."""
        if not 0 <= discount <= 100:
            raise ValueError("Скидка должна быть от 0 до 100%")
        
        await self.ensure_user_exists(user_id)
        success = await self.user_repo.set_discount(user_id, discount)
        
        if success:
            _invalidate_user_cache(user_id)
        
        return success
    
    async def update_pvz(
        self,
        user_id: int,
        dest: int,
        address: Optional[str] = None
    ) -> bool:
        """Обновить пункт выдачи."""
        await self.ensure_user_exists(user_id)
        success = await self.user_repo.set_pvz(user_id, dest, address)

        if success:
            _invalidate_user_cache(user_id)
        
        return success
    
    @cached(ttl=180, cache_instance=user_cache)
    async def get_user_statistics(self, user_id: int) -> Dict:
        """Получить статистику пользователя."""
        user = await self.user_repo.get_by_id(user_id)
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
            "user": user,
            "total_products": total_products,
            "in_stock": in_stock,
            "out_of_stock": out_of_stock,
            "avg_price": avg_price,
            "cheapest": cheapest,
            "most_expensive": most_expensive
        }
    
    async def can_add_product(self, user_id: int) -> tuple[bool, str]:
        """
        Проверить может ли пользователь добавить товар.
        
        Returns:
            (bool, str): (можно_добавить, причина_если_нельзя)
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False, "Пользователь не найден"
        
        max_links = user.get('max_links', 5)
        products_count = await self.product_repo.count_by_user(user_id)
        
        if products_count >= max_links:
            return False, f"Достигнут лимит ({max_links}) товаров"
        
        return True, ""
