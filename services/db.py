"""Обёртки для операций над пользователем и продуктами с поддержкой остатков и выбранного размера."""
from typing import Optional, List, Dict, Any
import asyncpg
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime


class ProductRow(BaseModel):
    """Модель продукта."""
    id: int
    user_id: int
    url_product: str
    nm_id: int
    name_product: str
    selected_size: Optional[str] = None
    last_basic_price: Optional[Decimal] = None
    last_product_price: Optional[Decimal] = None
    last_qty: Optional[int] = None
    out_of_stock: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DB:
    """Обёртка для работы с базой данных."""
    def __init__(self, dsn: str):
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            self._dsn, min_size=2, max_size=10
        )

    async def close(self):
        if self.pool:
            await self.pool.close()

    # --- Users ---
    async def ensure_user(self, user_id: int) -> dict:
        """Создаёт пользователя при первом входе, возвращает запись."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, plan, plan_name, max_links)
                VALUES ($1, 'plan_free', 'Бесплатный', 5)
                ON CONFLICT (id) DO NOTHING
                """,
                user_id,
            )
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            return dict(row) if row else {}

    async def set_discount(self, user_id: int, discount_percent: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET discount_percent = $1 WHERE id = $2",
                discount_percent, user_id
            )

    async def set_region(self, user_id: int, dest: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET dest = $1 WHERE id = $2",
                dest, user_id
            )

    async def set_pvz(self, user_id: int, dest: int, address: Optional[str] = None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET dest = $1, pvz_address = $2 WHERE id = $3",
                dest, address, user_id
            )

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, plan, plan_name, discount_percent, max_links, dest, pvz_address 
                   FROM users WHERE id = $1""",
                user_id
            )
            return dict(row) if row else None

    async def set_plan(self, user_id: int, plan_key: str, plan_name: str, max_links: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET plan = $1, plan_name = $2, max_links = $3
                WHERE id = $4
                """,
                plan_key, plan_name, max_links, user_id
            )

    # --- Products ---
    async def add_product(
            self, user_id: int, url_product: str, nm_id: int,
            name_product: str = "Загрузка...", selected_size: Optional[str] = None
    ) -> Optional[int]:
        """Добавить товар в базу данных. Возвращает ID или None."""
        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """INSERT INTO products
                       (user_id, url_product, nm_id, name_product, selected_size)
                       VALUES ($1, $2, $3, $4, $5)
                       RETURNING id""",
                    user_id, url_product, nm_id, name_product, selected_size
                )
                return row['id'] if row else None
            except asyncpg.UniqueViolationError:
                return None

    async def remove_product(self, user_id: int, nm_id: int) -> bool:
        async with self.pool.acquire() as conn:
            res = await conn.execute(
                "DELETE FROM products WHERE user_id = $1 AND nm_id = $2",
                user_id, nm_id
            )
            return res.endswith("1")

    async def list_products(self, user_id: int) -> List[ProductRow]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, user_id, url_product, nm_id, name_product,
                          selected_size, last_basic_price, last_product_price,
                          last_qty, out_of_stock, created_at, updated_at
                   FROM products WHERE user_id = $1 ORDER BY created_at DESC""",
                user_id,
            )
            return [ProductRow(**dict(r)) for r in rows]

    async def all_products(self) -> List[ProductRow]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, user_id, url_product, nm_id, name_product,
                          selected_size, last_basic_price, last_product_price,
                          last_qty, out_of_stock, created_at, updated_at
                   FROM products ORDER BY updated_at ASC NULLS FIRST"""
            )
            return [ProductRow(**dict(r)) for r in rows]

    async def update_prices_and_stock(
            self, product_id: int, basic: Decimal, product: Decimal,
            last_qty: Optional[int] = None, out_of_stock: Optional[bool] = None
    ):
        """Обновить цены и остатки товара."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE products
                   SET last_basic_price=$1,
                       last_product_price=$2,
                       last_qty=$3,
                       out_of_stock=$4,
                       updated_at=now()
                   WHERE id = $5""",
                basic, product, last_qty, out_of_stock, product_id
            )

    async def update_product_name(self, product_id: int, name: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE products SET name_product = $1 WHERE id = $2",
                name, product_id
            )

    async def get_product_by_id(self, product_id: int) -> Optional[ProductRow]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, user_id, url_product, nm_id, name_product,
                          selected_size, last_basic_price, last_product_price,
                          last_qty, out_of_stock, created_at, updated_at
                   FROM products WHERE id = $1""",
                product_id
            )
            return ProductRow(**dict(row)) if row else None
        
    async def set_selected_size(self, product_id: int, size_name: str):
        """Сохраняет выбранный размер для товара."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE products SET selected_size=$1, updated_at=now() WHERE id=$2",
                size_name, product_id
            )
