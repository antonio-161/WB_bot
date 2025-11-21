# services/price_history_service.py
"""
Сервис работы с историей цен.
"""
import logging
from typing import Dict, List, Optional
from collections import defaultdict

from infrastructure.price_history_repository import PriceHistoryRepository
from infrastructure.models import PriceHistoryRow

logger = logging.getLogger(__name__)


class PriceHistoryService:
    """
    Сервис истории цен.
    
    Отвечает за:
    - Получение истории
    - Batch-операции
    - Базовую аналитику по истории
    """
    
    def __init__(self, price_history_repo: PriceHistoryRepository):
        self.price_history_repo = price_history_repo
    
    async def add(
        self,
        product_id: int,
        basic_price: int,
        product_price: int,
        qty: int = 0
    ) -> int:
        """Добавить запись в историю."""
        return await self.price_history_repo.add(
            product_id,
            basic_price,
            product_price,
            qty
        )
    
    async def get_by_product(
        self,
        product_id: int,
        limit: int = 100
    ) -> List[Dict]:
        """
        Получить историю цен товара.
        
        Returns:
            Список записей (от новых к старым)
        """
        return await self.price_history_repo.get_by_product(product_id, limit)
    
    async def get_history_for_products(
        self,
        product_ids: List[int],
        limit: int = 30
    ) -> Dict[int, List[Dict]]:
        """
        Batch-метод: получить историю для нескольких товаров.
        
        Returns:
            Dict[product_id -> список записей]
        """
        if not product_ids:
            return {}
        
        # Batch-запрос из репозитория
        all_history = await self.price_history_repo.get_by_products_batch(
            product_ids,
            limit
        )
        
        # Группируем по product_id
        grouped = defaultdict(list)
        for record in all_history:
            grouped[record['product_id']].append(record)
        
        return dict(grouped)
    
    async def calculate_basic_stats(
        self,
        history: List[Dict],
        discount: int = 0
    ) -> Optional[Dict]:
        """
        Базовая статистика по истории.
        
        Returns:
            Dict с min/max/avg или None
        """
        if not history:
            return None
        
        from utils.wb_utils import apply_wallet_discount
        
        prices = [h['product_price'] for h in history]
        
        stats = {
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) // len(prices),
            "history_count": len(history)
        }
        
        if discount > 0:
            stats["min_with_discount"] = apply_wallet_discount(
                stats["min_price"], discount
            )
            stats["max_with_discount"] = apply_wallet_discount(
                stats["max_price"], discount
            )
        
        return stats
