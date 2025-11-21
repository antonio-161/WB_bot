# services/product_analytics_service.py
"""
Сервис аналитики товаров.
"""
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from enum import Enum

from infrastructure.product_repository import ProductRepository
from services.price_history_service import PriceHistoryService

logger = logging.getLogger(__name__)


class PriceTrend(Enum):
    """Тренд цены."""
    FALLING = "falling"  # Цена падает
    RISING = "rising"    # Цена растёт
    STABLE = "stable"    # Стабильная


class ProductAnalyticsService:
    """
    Сервис аналитики товаров.
    
    Отвечает за:
    - Расчёт экономии и трендов
    - Фильтрацию по критериям
    - Построение аналитических отчётов
    """
    
    def __init__(
        self,
        product_repo: ProductRepository,
        price_history_service: PriceHistoryService
    ):
        self.product_repo = product_repo
        self.price_history_service = price_history_service
    
    async def get_products_with_analytics(
        self,
        user_id: int,
        discount: int = 0,
        sort_mode: str = "savings"
    ) -> List[Dict]:
        """
        Получить список товаров с аналитикой (оптимизированная версия).
        
        Args:
            user_id: ID пользователя
            discount: Процент скидки WB кошелька
            sort_mode: Режим сортировки ("savings" или "date")
        
        Returns:
            Список товаров с аналитикой
        """
        # 1. Получаем все товары пользователя
        products = await self.product_repo.get_by_user(user_id)
        
        if not products:
            return []
        
        # 2. Batch-запрос истории для всех товаров
        product_ids = [p['id'] for p in products]
        histories = await self.price_history_service.get_history_for_products(
            product_ids,
            limit=30
        )
        
        # 3. Анализируем каждый товар
        result = []
        
        for product in products:
            product_id = product['id']
            history = histories.get(product_id, [])
            
            # Базовая аналитика
            analytics = {
                "product": product,
                "trend": PriceTrend.STABLE,
                "savings_percent": 0,
                "savings_amount": 0,
                "has_history": len(history) >= 2
            }
            
            if len(history) >= 2:
                # Расчёт экономии
                savings = self._calculate_savings(product, history)
                analytics.update(savings)
                
                # Определение тренда
                trend = self._calculate_trend(history)
                analytics["trend"] = trend
            
            result.append(analytics)
        
        # 4. Сортировка
        if sort_mode == "savings":
            result.sort(key=lambda x: x["savings_percent"], reverse=True)
        else:  # date
            result.sort(
                key=lambda x: x["product"].get("created_at", datetime.min),
                reverse=True
            )
        
        return result
    
    def _calculate_savings(
        self,
        product: Dict,
        history: List[Dict]
    ) -> Dict:
        """
        Рассчитать потенциальную экономию.
        
        Args:
            product: Товар
            history: История цен (newest first)
        
        Returns:
            Dict с savings_percent и savings_amount
        """
        prices = [h['product_price'] for h in history]
        max_price = max(prices)
        current_price = product['last_product_price'] or max_price
        
        savings = max_price - current_price
        
        if savings > 0 and max_price > 0:
            savings_percent = (savings / max_price) * 100
            return {
                "savings_percent": savings_percent,
                "savings_amount": savings
            }
        
        return {"savings_percent": 0, "savings_amount": 0}
    
    def _calculate_trend(self, history: List[Dict]) -> PriceTrend:
        """
        Определить тренд изменения цены.
        
        Args:
            history: История цен (гарантированно newest first)
        
        Returns:
            PriceTrend
        """
        if len(history) < 3:
            return PriceTrend.STABLE
        
        # Берём последние 3 записи: [newest, middle, oldest]
        recent = history[:3]
        prices = [h['product_price'] for h in recent]
        
        newest_price = prices[0]
        oldest_price = prices[-1]
        
        # Порог изменения (например, 2%)
        threshold = oldest_price * 0.02
        
        if newest_price < oldest_price - threshold:
            return PriceTrend.FALLING
        elif newest_price > oldest_price + threshold:
            return PriceTrend.RISING
        else:
            return PriceTrend.STABLE
    
    async def filter_best_deals(
        self,
        user_id: int,
        min_savings_percent: float = 15.0
    ) -> List[Tuple[Dict, float]]:
        """
        Получить товары с лучшими скидками (оптимизированная версия).
        
        Returns:
            Список кортежей (product, savings_percent)
        """
        # Используем существующий метод с аналитикой
        products_analytics = await self.get_products_with_analytics(user_id)
        
        # Фильтруем по проценту экономии
        filtered = [
            (item["product"], item["savings_percent"])
            for item in products_analytics
            if item["savings_percent"] >= min_savings_percent
        ]
        
        # Сортируем по проценту скидки
        filtered.sort(key=lambda x: x[1], reverse=True)
        
        return filtered
    
    async def filter_price_drops(
        self,
        user_id: int
    ) -> List[Tuple[Dict, int]]:
        """
        Получить товары с падающими ценами (оптимизированная версия).
        
        Returns:
            Список кортежей (product, price_drop_amount)
        """
        # Получаем товары с аналитикой
        products_analytics = await self.get_products_with_analytics(user_id)
        
        # Фильтруем только падающие
        filtered = []
        
        for item in products_analytics:
            if item["trend"] == PriceTrend.FALLING and item["savings_amount"] > 0:
                filtered.append((item["product"], item["savings_amount"]))
        
        # Сортируем по величине падения
        filtered.sort(key=lambda x: x[1], reverse=True)
        
        return filtered
    
    async def get_product_detail(
        self,
        product_id: int,
        discount: int = 0
    ) -> Optional[Dict]:
        """
        Получить детальную информацию о товаре.
        
        Упрощённая версия: делегирует расчёты.
        """
        product = await self.product_repo.get_by_id(product_id)
        
        if not product:
            return None
        
        # Получаем историю
        history = await self.price_history_service.get_by_product(
            product_id,
            limit=100
        )
        
        # Рассчитываем статистику
        stats = await self.price_history_service.calculate_basic_stats(
            history,
            discount
        )
        
        return {
            "product": product,
            "history": history,
            "stats": stats
        }
