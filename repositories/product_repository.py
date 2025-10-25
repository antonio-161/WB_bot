"""
Репозиторий для работы с товарами.
"""
from typing import Optional, Dict, List
from services.db import DB
from utils.decorators import retry_on_error


class ProductRepository:
    """
    Репозиторий товаров.
    Отвечает за таблицу products.
    """
    
    def __init__(self, db: DB):
        self.db = db
    
    # ===== CRUD операции =====
    
    async def get_by_id(self, product_id: int) -> Optional[Dict]:
        """Получить товар по ID."""
        row = await self.db.fetchrow(
            """SELECT id, user_id, url_product, nm_id, name_product, custom_name,
                      selected_size, last_basic_price, last_product_price,
                      last_qty, out_of_stock, notify_mode, notify_value,
                      created_at, updated_at
               FROM products 
               WHERE id = $1""",
            product_id
        )
        return dict(row) if row else None

    @retry_on_error(max_attempts=3, delay=0.5)
    async def create(
        self,
        user_id: int,
        url: str,
        nm_id: int,
        name: str = "Загрузка...",
        selected_size: Optional[str] = None
    ) -> Optional[int]:
        """
        Создать товар.
        
        Returns:
            ID созданного товара или None если уже существует
        """
        try:
            product_id = await self.db.fetchval(
                """INSERT INTO products (user_id, url_product, nm_id, name_product, selected_size)
                   VALUES ($1, $2, $3, $4, $5)
                   RETURNING id""",
                user_id, url, nm_id, name, selected_size
            )
            return product_id
        except Exception as e:
            # Уникальное нарушение (user_id, nm_id)
            return None
    
    async def delete(self, product_id: int) -> bool:
        """Удалить товар."""
        result = await self.db.execute(
            "DELETE FROM products WHERE id = $1",
            product_id
        )
        return result == "DELETE 1"
    
    async def delete_by_nm_id(self, user_id: int, nm_id: int) -> bool:
        """Удалить товар по артикулу."""
        result = await self.db.execute(
            "DELETE FROM products WHERE user_id = $1 AND nm_id = $2",
            user_id, nm_id
        )
        return result == "DELETE 1"
    
    # ===== Поиск =====
    
    async def get_all(self) -> List[Dict]:
        """Получить все товары (для мониторинга)."""
        rows = await self.db.fetch(
            """SELECT * FROM products 
               ORDER BY updated_at ASC NULLS FIRST"""
        )
        return [dict(r) for r in rows]
    
    async def get_by_user(self, user_id: int) -> List[Dict]:
        """Получить товары пользователя."""
        rows = await self.db.fetch(
            """SELECT * FROM products 
               WHERE user_id = $1 
               ORDER BY created_at DESC""",
            user_id
        )
        return [dict(r) for r in rows]
    
    async def get_by_nm_id(self, user_id: int, nm_id: int) -> Optional[Dict]:
        """Получить товар по артикулу."""
        row = await self.db.fetchrow(
            """SELECT * FROM products 
               WHERE user_id = $1 AND nm_id = $2""",
            user_id, nm_id
        )
        return dict(row) if row else None
    
    # ===== Статистика =====
    
    async def count_by_user(self, user_id: int) -> int:
        """Количество товаров у пользователя."""
        return await self.db.fetchval(
            "SELECT COUNT(*) FROM products WHERE user_id = $1",
            user_id
        )
    
    async def count_total(self) -> int:
        """Общее количество товаров."""
        return await self.db.fetchval("SELECT COUNT(*) FROM products")
    
    async def count_out_of_stock(self, user_id: int) -> int:
        """Количество товаров без наличия."""
        return await self.db.fetchval(
            "SELECT COUNT(*) FROM products WHERE user_id = $1 AND out_of_stock = true",
            user_id
        )
    
    # ===== Обновление =====
    
    async def update_name(self, product_id: int, name: str) -> bool:
        """Обновить название товара."""
        result = await self.db.execute(
            "UPDATE products SET name_product = $1 WHERE id = $2",
            name, product_id
        )
        return result == "UPDATE 1"
    
    async def set_custom_name(self, product_id: int, custom_name: Optional[str]) -> bool:
        """Установить пользовательское название."""
        result = await self.db.execute(
            "UPDATE products SET custom_name = $1 WHERE id = $2",
            custom_name, product_id
        )
        return result == "UPDATE 1"
    
    async def set_size(self, product_id: int, size: str) -> bool:
        """Установить выбранный размер."""
        result = await self.db.execute(
            "UPDATE products SET selected_size = $1, updated_at = NOW() WHERE id = $2",
            size, product_id
        )
        return result == "UPDATE 1"

    @retry_on_error(max_attempts=3, delay=0.5)
    async def update_prices(
        self,
        product_id: int,
        basic_price: int,
        product_price: int,
        qty: Optional[int] = None,
        out_of_stock: Optional[bool] = None
    ) -> bool:
        """Обновить цены и остатки."""
        result = await self.db.execute(
            """UPDATE products 
               SET last_basic_price = $1, 
                   last_product_price = $2, 
                   last_qty = $3, 
                   out_of_stock = $4, 
                   updated_at = NOW()
               WHERE id = $5""",
            basic_price, product_price, qty, out_of_stock, product_id
        )
        return result == "UPDATE 1"
    
    async def set_notify_settings(
        self,
        product_id: int,
        mode: Optional[str],
        value: Optional[int]
    ) -> bool:
        """Установить настройки уведомлений."""
        result = await self.db.execute(
            "UPDATE products SET notify_mode = $1, notify_value = $2 WHERE id = $3",
            mode, value, product_id
        )
        return result == "UPDATE 1"
