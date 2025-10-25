"""
Репозиторий для работы с историей цен.
"""
from typing import List, Dict
from services.db import DB
from utils.decorators import retry_on_error


class PriceHistoryRepository:
    """
    Репозиторий истории цен.
    Отвечает за таблицу price_history.
    """

    def __init__(self, db: DB):
        self.db = db

    @retry_on_error(max_attempts=3, delay=0.5)
    async def add(
        self,
        product_id: int,
        basic_price: int,
        product_price: int,
        qty: int = 0
    ) -> int:
        """
        Добавить запись в историю.
        
        Returns:
            ID созданной записи
        """
        record_id = await self.db.fetchval(
            """INSERT INTO price_history (product_id, basic_price, product_price, qty)
               VALUES ($1, $2, $3, $4)
               RETURNING id""",
            product_id, basic_price, product_price, qty
        )
        return record_id
    
    async def get_by_product(self, product_id: int, limit: int = 100) -> List[Dict]:
        """
        Получить историю цен товара.
        
        Args:
            product_id: ID товара
            limit: Максимум записей
        
        Returns:
            Список записей (от новых к старым)
        """
        rows = await self.db.fetch(
            """SELECT id, product_id, basic_price, product_price, qty, recorded_at
               FROM price_history
               WHERE product_id = $1
               ORDER BY recorded_at DESC
               LIMIT $2""",
            product_id, limit
        )
        return [dict(r) for r in rows]
    
    async def cleanup_old(self, days: int) -> int:
        """
        Удалить записи старше N дней.
        
        Returns:
            Количество удалённых записей
        """
        result = await self.db.execute(
            "DELETE FROM price_history WHERE recorded_at < NOW() - INTERVAL '%s days'",
            days
        )
        # Извлекаем число из "DELETE 123"
        deleted_count = int(result.split()[-1]) if result != "DELETE 0" else 0
        return deleted_count
    
    async def cleanup_by_plan(self) -> Dict[str, int]:
        """
        Очистить историю согласно тарифам пользователей.
        
        Returns:
            Dict с количеством удалённых записей по тарифам
        """
        # Free: 30 дней
        result_free = await self.db.execute(
            """DELETE FROM price_history ph
               WHERE ph.id IN (
                   SELECT ph2.id FROM price_history ph2
                   JOIN products p ON ph2.product_id = p.id
                   JOIN users u ON p.user_id = u.id
                   WHERE u.plan = 'plan_free' 
                   AND ph2.recorded_at < NOW() - INTERVAL '30 days'
               )"""
        )
        
        # Basic: 90 дней
        result_basic = await self.db.execute(
            """DELETE FROM price_history ph
               WHERE ph.id IN (
                   SELECT ph2.id FROM price_history ph2
                   JOIN products p ON ph2.product_id = p.id
                   JOIN users u ON p.user_id = u.id
                   WHERE u.plan = 'plan_basic' 
                   AND ph2.recorded_at < NOW() - INTERVAL '90 days'
               )"""
        )
        
        # Pro: 365 дней
        result_pro = await self.db.execute(
            """DELETE FROM price_history ph
               WHERE ph.id IN (
                   SELECT ph2.id FROM price_history ph2
                   JOIN products p ON ph2.product_id = p.id
                   JOIN users u ON p.user_id = u.id
                   WHERE u.plan = 'plan_pro' 
                   AND ph2.recorded_at < NOW() - INTERVAL '365 days'
               )"""
        )
        
        def extract_count(result: str) -> int:
            return int(result.split()[-1]) if result != "DELETE 0" else 0
        
        return {
            "plan_free": extract_count(result_free),
            "plan_basic": extract_count(result_basic),
            "plan_pro": extract_count(result_pro)
        }
    
    async def count_total(self) -> int:
        """Общее количество записей."""
        return await self.db.fetchval("SELECT COUNT(*) FROM price_history")
