"""
Сервис для работы с товарами.
Содержит бизнес-логику управления товарами.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from constants import DEFAULT_DEST
from repositories.product_repository import ProductRepository
from repositories.price_history_repository import PriceHistoryRepository
from services.price_fetcher import PriceFetcher
from utils.cache import cached, product_cache, user_cache
from utils.wb_utils import apply_wallet_discount

logger = logging.getLogger(__name__)


def _invalidate_product_cache(product_id: int, nm_id: int, dest: Optional[int] = None):
    """Очистить кэш товара."""
    dest = dest or DEFAULT_DEST
    # Очищаем кэш API WB
    product_cache.remove(f"product_{nm_id}_{dest}")
    # Очищаем кэш деталей товара (если кэшировали get_product_detail)
    product_cache.remove(f"get_product_detail:{product_id}")


class ProductService:
    """Сервис для работы с товарами."""
    
    def __init__(
        self,
        product_repo: ProductRepository,
        price_history_repo: PriceHistoryRepository,
        price_fetcher: PriceFetcher
    ):
        self.product_repo = product_repo
        self.price_history_repo = price_history_repo
        self.price_fetcher = price_fetcher
    
    async def add_product(
        self,
        user_id: int,
        nm_id: int,
        url: str,
        dest: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int], Optional[Dict]]:
        """
        Добавить товар в отслеживание.
        
        Returns:
            (success, message, product_id, product_data)
        """
        # Получаем данные о товаре
        product_data = await self.price_fetcher.get_product_data(nm_id, dest)
        
        if not product_data:
            return False, "Не удалось получить данные о товаре", None, None
        
        product_name = product_data.get("name", f"Товар {nm_id}")
        
        # Создаём товар в БД
        product_id = await self.product_repo.create(
            user_id,
            url,
            nm_id,
            product_name
        )
        
        if not product_id:
            return False, "Товар уже в отслеживании", None, None
        
        # Сохраняем начальные цены
        await self._save_initial_prices(product_id, product_data)
        
        return True, "Товар добавлен", product_id, product_data
    
    async def add_product_with_size(
        self,
        user_id: int,
        nm_id: int,
        url: str,
        size_name: str,
        dest: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Добавить товар с выбранным размером.
        
        Returns:
            (success, message, product_id)
        """
        # Создаём товар
        success, message, product_id, product_data = await self.add_product(
            user_id, nm_id, url, dest
        )
        
        if not success:
            return False, message, None
        
        # Устанавливаем размер
        await self.product_repo.set_size(product_id, size_name)
        
        # Сохраняем цены для выбранного размера
        if product_data:
            await self._save_prices_for_size(product_id, product_data, size_name)
        
        return True, "Товар добавлен с размером", product_id
    
    async def update_product_size(
        self,
        product_id: int,
        size_name: str,
        nm_id: int,
        dest: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Обновить размер товара и цены для него.
        
        Returns:
            (success, message)
        """
        # Устанавливаем размер
        await self.product_repo.set_size(product_id, size_name)
        
        # Получаем данные о товаре
        product_data = await self.price_fetcher.get_product_data(nm_id, dest)
        
        if product_data:
            await self._save_prices_for_size(product_id, product_data, size_name)
            return True, "Размер обновлён"
        else:
            return False, "Не удалось обновить цены для выбранного размера"
    
    async def _save_initial_prices(
        self,
        product_id: int,
        product_data: Dict
    ) -> None:
        """Сохранить начальные цены товара."""
        sizes = product_data.get("sizes", [])
        
        if not sizes:
            logger.warning(f"Нет данных о размерах для товара {product_id}")
            return
        
        # Для товара без размеров берём первый элемент
        size_data = sizes[0]
        price_info = size_data.get("price", {})
        
        basic_price = price_info.get("basic", 0)
        product_price = price_info.get("product", 0)
        qty = sum(stock.get("qty", 0) for stock in size_data.get("stocks", []))
        
        # Обновляем товар
        await self.product_repo.update_prices(
            product_id,
            basic_price,
            product_price,
            qty,
            qty == 0
        )
        
        # Добавляем в историю
        await self.price_history_repo.add(
            product_id,
            basic_price,
            product_price,
            qty
        )
    
    async def _save_prices_for_size(
        self,
        product_id: int,
        product_data: Dict,
        size_name: str
    ) -> None:
        """Сохранить цены для конкретного размера."""
        sizes = product_data.get("sizes", [])
        
        size_data = next(
            (s for s in sizes if s.get("name") == size_name),
            None
        )
        
        if not size_data:
            logger.warning(
                f"Размер {size_name} не найден для товара {product_id}"
            )
            return
        
        price_info = size_data.get("price", {})
        basic_price = price_info.get("basic", 0)
        product_price = price_info.get("product", 0)
        qty = sum(stock.get("qty", 0) for stock in size_data.get("stocks", []))
        
        await self.product_repo.update_prices(
            product_id,
            basic_price,
            product_price,
            qty,
            qty == 0
        )
        
        await self.price_history_repo.add(
            product_id,
            basic_price,
            product_price,
            qty
        )
    
    @cached(ttl=600, cache_instance=user_cache)
    async def get_product_detail(
        self,
        product_id: int,
        discount: int = 0
    ) -> Optional[Dict]:
        """
        Получить детальную информацию о товаре.
        
        Returns:
            Dict с информацией о товаре, истории, статистике
        """
        product = await self.product_repo.get_by_id(product_id)
        
        if not product:
            return None
        
        # Получаем историю
        history = await self.price_history_repo.get_by_product(product_id, limit=100)
        
        # Подсчёт статистики
        stats = None
        if history:
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
        
        return {
            "product": product,
            "history": history,
            "stats": stats
        }
    
    async def rename_product(
        self,
        product_id: int,
        new_name: str
    ) -> Tuple[bool, str]:
        """
        Переименовать товар.
        
        Returns:
            (success, message)
        """
        if len(new_name) < 3:
            return False, "Название слишком короткое (минимум 3 символа)"
        
        if len(new_name) > 200:
            return False, "Название слишком длинное (максимум 200 символов)"
        
        success = await self.product_repo.set_custom_name(product_id, new_name)
        
        if success:
            product = await self.product_repo.get_by_id(product_id)
            if product:
                _invalidate_product_cache(product_id, product['nm_id'])
            return True, "Товар переименован"
        else:
            return False, "Ошибка при переименовании"
    
    async def set_notify_settings(
        self,
        product_id: int,
        mode: Optional[str],
        value: Optional[int]
    ) -> Tuple[bool, str]:
        """
        Установить настройки уведомлений.
        
        Returns:
            (success, message)
        """
        # Валидация
        if mode == "percent" and (value <= 0 or value > 100):
            return False, "Процент должен быть от 1 до 100"
        
        if mode == "threshold" and value <= 0:
            return False, "Порог должен быть положительным числом"
        
        success = await self.product_repo.set_notify_settings(
            product_id,
            mode,
            value
        )
        
        if success:
            return True, "Настройки уведомлений обновлены"
        else:
            return False, "Ошибка при сохранении настроек"
    
    async def remove_product(
        self,
        user_id: int,
        nm_id: int
    ) -> Tuple[bool, str]:
        """
        Удалить товар из отслеживания.
        
        Returns:
            (success, message)
        """
        success = await self.product_repo.delete_by_nm_id(user_id, nm_id)
        
        if success:
            _invalidate_product_cache(0, nm_id)
            return True, "Товар удалён из отслеживания"
        else:
            return False, "Товар не найден или уже удалён"
    
    async def get_products_with_analytics(
        self,
        user_id: int,
        discount: int = 0,
        sort_mode: str = "savings"
    ) -> List[Dict]:
        """
        Получить список товаров с аналитикой.
        
        Returns:
            Список товаров с данными о трендах и экономии
        """
        products = await self.product_repo.get_by_user(user_id)
        
        result = []
        
        for product in products:
            # Получаем историю для анализа
            history = await self.price_history_repo.get_by_product(
                product['id'],
                limit=30
            )
            
            analytics = {
                "product": product,
                "trend": "neutral",
                "savings_percent": 0,
                "savings_amount": 0,
                "has_history": len(history) >= 2
            }
            
            if len(history) >= 2:
                prices = [h['product_price'] for h in history]
                max_price = max(prices)
                min_price = min(prices)
                current_price = product['last_product_price'] or max_price
                
                # Расчёт экономии
                savings = max_price - current_price
                if savings > 0 and max_price > 0:
                    savings_percent = (savings / max_price) * 100
                    analytics["savings_percent"] = savings_percent
                    analytics["savings_amount"] = savings
                
                # Определение тренда
                recent_prices = [h['product_price'] for h in history[:3]]
                if len(recent_prices) >= 2:
                    if recent_prices[0] < recent_prices[-1]:
                        analytics["trend"] = "down"
                    elif recent_prices[0] > recent_prices[-1]:
                        analytics["trend"] = "up"
            
            result.append(analytics)
        
        # Сортируем по выгодности
        result.sort(key=lambda x: x["savings_percent"], reverse=True)
        
        # Сортировка в зависимости от режима
        if sort_mode == "savings":
            result.sort(key=lambda x: x["savings_percent"], reverse=True)
        else:  # date
            result.sort(key=lambda x: x["product"].get("created_at", datetime.min), reverse=True)

        return result
    
    async def filter_best_deals(
        self,
        user_id: int,
        min_savings_percent: float = 15.0
    ) -> List[Tuple[Dict, float]]:
        """
        Получить товары с лучшими скидками.
        
        Returns:
            Список кортежей (product, savings_percent)
        """
        products = await self.product_repo.get_by_user(user_id)
        
        filtered = []
        
        for product in products:
            history = await self.price_history_repo.get_by_product(
                product['id'],
                limit=30
            )
            
            if len(history) >= 2:
                prices = [h['product_price'] for h in history]
                max_price = max(prices)
                current = product['last_product_price'] or max_price
                
                if max_price > 0:
                    savings_percent = ((max_price - current) / max_price) * 100
                    
                    if savings_percent >= min_savings_percent:
                        filtered.append((product, savings_percent))
        
        # Сортируем по проценту скидки
        filtered.sort(key=lambda x: x[1], reverse=True)
        
        return filtered
    
    async def filter_price_drops(self, user_id: int) -> List[Tuple[Dict, int]]:
        """
        Получить товары с падающими ценами.
        
        Returns:
            Список кортежей (product, price_drop)
        """
        products = await self.product_repo.get_by_user(user_id)
        
        filtered = []
        
        for product in products:
            history = await self.price_history_repo.get_by_product(
                product['id'],
                limit=7
            )
            
            if len(history) >= 3:
                prices = [h['product_price'] for h in history]
                
                # Проверяем тренд
                if prices[0] < prices[-1]:  # Цена падает
                    drop = prices[-1] - prices[0]
                    filtered.append((product, drop))
        
        # Сортируем по величине падения
        filtered.sort(key=lambda x: x[1], reverse=True)
        
        return filtered
