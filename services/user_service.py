"""
Сервис для работы с пользователями.
Содержит бизнес-логику управления пользователями.
"""
import logging
from typing import Dict, Optional

from repositories.user_repository import UserRepository
from repositories.product_repository import ProductRepository

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для работы с пользователями."""
    
    def __init__(self, user_repo: UserRepository, product_repo: ProductRepository):
        self.user_repo = user_repo
        self.product_repo = product_repo
    
    async def ensure_user_exists(self, user_id: int) -> Dict:
        """Убедиться что пользователь существует, создать если нет."""
        return await self.user_repo.ensure_exists(user_id)
    
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
        return await self.user_repo.set_plan(user_id, plan_key, plan_name, max_links)
    
    async def update_discount(self, user_id: int, discount: int) -> bool:
        """Обновить процент скидки WB кошелька."""
        if not 0 <= discount <= 100:
            raise ValueError("Скидка должна быть от 0 до 100%")
        
        await self.ensure_user_exists(user_id)
        return await self.user_repo.set_discount(user_id, discount)
    
    async def update_pvz(
        self,
        user_id: int,
        dest: int,
        address: Optional[str] = None
    ) -> bool:
        """Обновить пункт выдачи."""
        await self.ensure_user_exists(user_id)
        return await self.user_repo.set_pvz(user_id, dest, address)
    
    async def get_user_statistics(self, user_id: int) -> Dict:
        """Получить статистику пользователя."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {
                "exists": False
            }
        
        products = await self.product_repo.get_by_user(user_id)
        
        # Подсчёт статистики
        total_products = len(products)
        in_stock = sum(1 for p in products if not p.get('out_of_stock', False))
        out_of_stock = total_products - in_stock
        
        # Средняя цена
        prices = [p['last_product_price'] for p in products if p.get('last_product_price')]
        avg_price = sum(prices) // len(prices) if prices else 0
        
        # Самый дешёвый и дорогой
        cheapest = None
        most_expensive = None
        if prices:
            sorted_products = sorted(
                [p for p in products if p.get('last_product_price')],
                key=lambda x: x['last_product_price']
            )
            if sorted_products:
                cheapest = sorted_products[0]
                most_expensive = sorted_products[-1]
        
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
