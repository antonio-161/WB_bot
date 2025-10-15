"""Обёртки для операций над пользователем и продуктами."""
from typing import Optional, List, Dict, Any
import asyncpg
from pydantic import BaseModel
from decimal import Decimal


class ProductRow(BaseModel):
    """Модель продукта."""
    id: int
    user_id: int
    url_product: str
    nm_id: int
    name_product: str
    last_basic_price: Optional[Decimal]
    last_product_price: Optional[Decimal]


class DB:
    """Обёртка для работы с базой данных."""
    def __init__(self, dsn: str):
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            self._dsn, min_size=1, max_size=5
        )

    async def close(self):
        if self.pool:
            await self.pool.close()

    # --- Users ---
    async def ensure_user(self, user_id: int) -> dict:
        """Создает пользователя при первом входе, возвращает запись."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                user_id,
            )
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            return dict(row) if row else None

    async def set_discount(self, user_id: int, discount_percent: int):
        """Установить скидку для пользователя."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET discount_percent = $1 WHERE id = $2",
                discount_percent,
                user_id,
            )

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить информацию о пользователе."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, discount_percent, max_links FROM users WHERE id = $1",
                user_id
            )
            if not row:
                return None
            return dict(row)

    # --- Products ---
    async def add_product(
            self, user_id: int, url_product: str, nm_id: int
    ) -> bool:
        """Добавить товар в базу данных."""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    "INSERT INTO products (user_id, url_product, nm_id) VALUES ($1, $2, $3)",
                    user_id,
                    url_product,
                    nm_id,
                )
                return True
            except asyncpg.UniqueViolationError:
                return False

    async def remove_product(self, user_id: int, nm_id: int) -> bool:
        """Удалить товар из базы данных."""
        async with self.pool.acquire() as conn:
            res = await conn.execute(
                "DELETE FROM products WHERE user_id = $1 AND nm_id = $2",
                user_id,
                nm_id
            )
            return res.endswith("1")

    async def list_products(self, user_id: int) -> List[ProductRow]:
        """Список отслеживаемых товаров."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, user_id, url_product, nm_id, last_basic_price, last_product_price FROM products WHERE user_id = $1",
                user_id,
            )
            return [ProductRow(**dict(r)) for r in rows]

    async def all_products(self) -> List[ProductRow]:
        """Список всех товаров."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, user_id, url_product, nm_id, last_basic_price, last_product_price FROM products"
            )
            return [ProductRow(**dict(r)) for r in rows]

    async def update_prices(
            self, product_id: int, basic: Decimal, product: Decimal
    ):
        """Обновить цены товара."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE products SET last_basic_price=$1, last_product_price=$2 WHERE id = $3",
                basic,
                product,
                product_id,
            )

    async def set_plan(
            self, user_id: int, plan_name: str, max_links: int
    ):
        """Обновление тарифа пользователя."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET plan = $1, max_links = $2
                WHERE id = $3
                """,
                plan_name, max_links, user_id
            )
