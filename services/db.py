"""Обёртки для операций над пользователем и продуктами с поддержкой истории цен."""
from typing import Optional, List, Dict, Any
import asyncpg
from pydantic import BaseModel
from datetime import datetime

from utils.decorators import retry_on_error


class ProductRow(BaseModel):
    """Модель продукта."""
    id: int
    user_id: int
    url_product: str
    nm_id: int
    name_product: str
    custom_name: Optional[str] = None
    selected_size: Optional[str] = None
    notify_mode: Optional[str] = None
    notify_value: Optional[int] = None
    last_basic_price: Optional[int] = None
    last_product_price: Optional[int] = None
    last_qty: Optional[int] = None
    out_of_stock: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def display_name(self) -> str:
        """Возвращает пользовательское имя или оригинальное."""
        return self.custom_name if self.custom_name else self.name_product


class PriceHistoryRow(BaseModel):
    """Модель записи истории цен."""
    id: int
    product_id: int
    basic_price: int
    product_price: int
    qty: int
    recorded_at: datetime


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
    @retry_on_error(max_attempts=3, delay=0.5)
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
                        custom_name, selected_size, last_basic_price,
                        last_product_price, last_qty, out_of_stock,
                        notify_mode, notify_value, created_at, updated_at
                FROM products WHERE user_id = $1 ORDER BY created_at DESC""",
                user_id,
            )
            return [ProductRow(**dict(r)) for r in rows]

    async def all_products(self) -> List[ProductRow]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, user_id, url_product, nm_id, name_product,
                        custom_name, selected_size, last_basic_price,
                        last_product_price, last_qty, out_of_stock,
                        notify_mode, notify_value, created_at, updated_at
                FROM products ORDER BY updated_at ASC NULLS FIRST"""
            )
            return [ProductRow(**dict(r)) for r in rows]

    @retry_on_error(max_attempts=3, delay=0.5)
    async def update_prices_and_stock(
            self,
            product_id: int,
            basic: int,
            product: int,
            last_qty: Optional[int] = None,
            out_of_stock: Optional[bool] = None
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

    async def set_custom_name(self, product_id: int, custom_name: Optional[str]):
        """Установить пользовательское имя товара."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE products SET custom_name = $1 WHERE id = $2",
                custom_name, product_id
            )

    async def get_product_by_id(self, product_id: int) -> Optional[ProductRow]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, user_id, url_product, nm_id, name_product,
                        custom_name, selected_size, last_basic_price,
                        last_product_price, last_qty, out_of_stock,
                        notify_mode, notify_value, created_at, updated_at
                FROM products WHERE id = $1""",
                product_id
            )
            return ProductRow(**dict(row)) if row else None

    async def get_product_by_nm(
            self, user_id: int, nm_id: int
    ) -> Optional[ProductRow]:
        """Получить товар по артикулу."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, user_id, url_product, nm_id, name_product,
                        custom_name, selected_size, last_basic_price,
                        last_product_price, last_qty, out_of_stock,
                        notify_mode, notify_value, created_at, updated_at
                FROM products WHERE user_id = $1 AND nm_id = $2""",
                user_id, nm_id
            )
            return ProductRow(**dict(row)) if row else None

    async def set_selected_size(self, product_id: int, size_name: str):
        """Сохраняет выбранный размер для товара."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE products SET selected_size=$1, updated_at=now() WHERE id=$2",
                size_name, product_id
            )

    # --- Price History ---
    @retry_on_error(max_attempts=3, delay=0.5)
    async def add_price_history(
            self, product_id: int, basic: int, product: int, qty: int = 0
    ):
        """Добавить запись в историю цен."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO price_history (product_id, basic_price, product_price, qty)
                   VALUES ($1, $2, $3, $4)""",
                product_id, basic, product, qty
            )

    async def get_price_history(
            self, product_id: int, limit: int = 100
    ) -> List[PriceHistoryRow]:
        """Получить историю цен товара."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, product_id, basic_price, product_price, qty, recorded_at
                   FROM price_history
                   WHERE product_id = $1
                   ORDER BY recorded_at DESC
                   LIMIT $2""",
                product_id, limit
            )
            return [PriceHistoryRow(**dict(r)) for r in rows]

    async def cleanup_old_history_by_plan(self):
        """Удалить историю согласно тарифам пользователей."""
        async with self.pool.acquire() as conn:
            # Для бесплатного тарифа — 1 месяц (30 дней)
            await conn.execute(
                """DELETE FROM price_history ph
                WHERE ph.id IN (
                    SELECT ph2.id FROM price_history ph2
                    JOIN products p ON ph2.product_id = p.id
                    JOIN users u ON p.user_id = u.id
                    WHERE u.plan = 'plan_free' 
                    AND ph2.recorded_at < now() - interval '30 days'
                )"""
            )
            
            # Для базового — 3 месяца (90 дней)
            await conn.execute(
                """DELETE FROM price_history ph
                WHERE ph.id IN (
                    SELECT ph2.id FROM price_history ph2
                    JOIN products p ON ph2.product_id = p.id
                    JOIN users u ON p.user_id = u.id
                    WHERE u.plan = 'plan_basic' 
                    AND ph2.recorded_at < now() - interval '90 days'
                )"""
            )
            
            # Для продвинутого — 12 месяцев (365 дней)
            await conn.execute(
                """DELETE FROM price_history ph
                WHERE ph.id IN (
                    SELECT ph2.id FROM price_history ph2
                    JOIN products p ON ph2.product_id = p.id
                    JOIN users u ON p.user_id = u.id
                    WHERE u.plan = 'plan_pro' 
                    AND ph2.recorded_at < now() - interval '365 days'
                )"""
            )

    async def set_notify_settings(
        self, product_id: int, mode: Optional[str], value: Optional[int]
    ):
        """Установить настройки уведомлений для товара."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE products SET notify_mode = $1, notify_value = $2 WHERE id = $3",
                mode, value, product_id
            )

    async def cleanup_expired_products(self):
        """Удалить товары старше 3 месяцев для бесплатного тарифа."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """DELETE FROM products
                WHERE id IN (
                    SELECT p.id FROM products p
                    JOIN users u ON p.user_id = u.id
                    WHERE u.plan = 'plan_free' 
                    AND p.created_at < now() - interval '90 days'
                )"""
            )
            # Извлекаем количество удалённых строк
            deleted_count = int(result.split()[-1]) if result else 0
            return deleted_count
