"""
Репозиторий товаров - работа с БД через DTO.
"""
from typing import Optional, List
from infrastructure.db import DB
from core.dto import ProductDTO
from core.enums import NotifyMode
from core.entities import Product
from core.mappers import ProductMapper
from utils.cache import cached, SimpleCache
from utils.decorators import retry_on_error

_repo_cache = SimpleCache(ttl_seconds=60)


class ProductRepository:
    """
    Репозиторий товаров.
    Принимает DTO, возвращает Entities.
    """

    def __init__(self, db: DB):
        self.db = db
        self.mapper = ProductMapper()

    def _row_to_entity(self, row) -> Product:
        """Конвертировать asyncpg.Record в Product."""
        dto = ProductDTO(**dict(row))
        return self.mapper.to_entity(dto)

    def _rows_to_entities(self, rows) -> List[Product]:
        """Конвертировать список asyncpg.Record в список Product."""
        return [self._row_to_entity(row) for row in rows]

    # ===== CRUD операции =====

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        """Получить товар по ID."""
        row = await self.db.fetchrow(
            """SELECT id, user_id, url_product, nm_id, name_product,
                      custom_name, selected_size, last_basic_price,
                      last_product_price, last_qty, out_of_stock,
                      notify_mode, notify_value, created_at, updated_at
               FROM products
               WHERE id = $1""",
            product_id
        )

        if not row:
            return None

        return self._row_to_entity(row)

    @retry_on_error(max_attempts=3, delay=0.5)
    async def create(self, dto: ProductDTO) -> Optional[int]:
        """Создать товар из DTO. Возвращает ID или None если дубликат."""
        try:
            product_id = await self.db.fetchval(
                """INSERT INTO products (
                    user_id, url_product, nm_id, name_product,
                    selected_size, last_basic_price, last_product_price,
                    last_qty, out_of_stock
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id""",
                dto.user_id, dto.url_product, dto.nm_id, dto.name_product,
                dto.selected_size, dto.last_basic_price,
                dto.last_product_price, dto.last_qty, dto.out_of_stock
            )
            return product_id
        except Exception:
            # Уникальное нарушение (user_id, nm_id)
            return None

    async def update(self, entity: Product) -> bool:
        """Обновить товар из Entity."""
        dto = self.mapper.to_dto(entity)

        result = await self.db.execute(
            """UPDATE products
               SET name_product = $2, custom_name = $3,
                   last_basic_price = $4, last_product_price = $5,
                   selected_size = $6, notify_mode = $7, notify_value = $8,
                   last_qty = $9, out_of_stock = $10, updated_at = NOW()
               WHERE id = $1""",
            dto.id, dto.name_product, dto.custom_name,
            dto.last_basic_price, dto.last_product_price,
            dto.selected_size, dto.notify_mode, dto.notify_value,
            dto.last_qty, dto.out_of_stock
        )
        return result == "UPDATE 1"

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

    async def get_all_products(self) -> List[Product]:
        """Получить ВСЕ товары (для мониторинга)."""
        rows = await self.db.fetch(
            """SELECT * FROM products
               ORDER BY updated_at ASC NULLS FIRST"""
        )
        return self._rows_to_entities(rows)

    async def get_by_user(self, user_id: int) -> List[Product]:
        """Получить товары пользователя."""
        rows = await self.db.fetch(
            """SELECT * FROM products
               WHERE user_id = $1
               ORDER BY created_at DESC""",
            user_id
        )
        return self._rows_to_entities(rows)

    async def get_by_nm_id(
            self, user_id: int, nm_id: int
    ) -> Optional[Product]:
        """Получить товар по артикулу."""
        row = await self.db.fetchrow(
            """SELECT * FROM products
               WHERE user_id = $1 AND nm_id = $2""",
            user_id, nm_id
        )

        if not row:
            return None

        return self._row_to_entity(row)

    # ===== Статистика =====

    @cached(cache_instance=_repo_cache)
    async def count_by_user(self, user_id: int) -> int:
        """Количество товаров у пользователя."""
        return await self.db.fetchval(
            "SELECT COUNT(*) FROM products WHERE user_id = $1",
            user_id
        )

    async def count_total(self) -> int:
        """Общее количество товаров."""
        return await self.db.fetchval("SELECT COUNT(*) FROM products")

    @cached(cache_instance=_repo_cache)
    async def count_out_of_stock(self, user_id: int) -> int:
        """Количество товаров без наличия у пользователя."""
        return await self.db.fetchval(
            """SELECT COUNT(*) FROM products
               WHERE user_id = $1 AND out_of_stock = true""",
            user_id
        )

    async def count_out_of_stock_total(self) -> int:
        """Общее количество товаров без наличия."""
        return await self.db.fetchval(
            "SELECT COUNT(*) FROM products WHERE out_of_stock = true"
        )

    async def get_cheapest(self, user_id: int) -> Optional[Product]:
        """Самый дешёвый товар пользователя."""
        row = await self.db.fetchrow(
            """SELECT * FROM products
               WHERE user_id = $1
                 AND last_product_price IS NOT NULL
                 AND last_product_price > 0
                 AND out_of_stock = false
               ORDER BY last_product_price ASC
               LIMIT 1""",
            user_id
        )

        if not row:
            return None

        return self._row_to_entity(row)

    async def get_most_expensive(self, user_id: int) -> Optional[Product]:
        """Самый дорогой товар пользователя."""
        row = await self.db.fetchrow(
            """SELECT * FROM products
               WHERE user_id = $1
                 AND last_product_price IS NOT NULL
                 AND last_product_price > 0
                 AND out_of_stock = false
               ORDER BY last_product_price DESC
               LIMIT 1""",
            user_id
        )

        if not row:
            return None

        return self._row_to_entity(row)

    @cached(cache_instance=_repo_cache)
    async def get_average_price(self, user_id: int) -> int:
        """Средняя цена товаров пользователя."""
        avg = await self.db.fetchval(
            """SELECT AVG(last_product_price)
               FROM products
               WHERE user_id = $1 AND last_product_price IS NOT NULL""",
            user_id
        )
        return int(avg) if avg else 0

    # ===== Обновление отдельных полей =====

    async def update_name(self, product_id: int, name: str) -> bool:
        """Обновить название."""
        result = await self.db.execute(
            "UPDATE products SET name_product = $1 WHERE id = $2",
            name, product_id
        )
        return result == "UPDATE 1"

    async def update_custom_name(
        self,
        product_id: int,
        custom_name: Optional[str]
    ) -> bool:
        """Установить пользовательское название."""
        result = await self.db.execute(
            "UPDATE products SET custom_name = $1 WHERE id = $2",
            custom_name, product_id
        )
        return result == "UPDATE 1"

    async def update_size(self, product_id: int, size: str) -> bool:
        """Установить размер."""
        result = await self.db.execute(
            """UPDATE products
               SET selected_size = $1, updated_at = NOW()
               WHERE id = $2""",
            size, product_id
        )
        return result == "UPDATE 1"

    @retry_on_error(max_attempts=3, delay=0.5)
    async def update_prices_and_stock(
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

    async def update_notify_settings(
        self,
        product_id: int,
        mode: NotifyMode,
        value: Optional[int]
    ) -> bool:
        """Установить настройки уведомлений."""
        result = await self.db.execute(
            """UPDATE products
               SET notify_mode = $1, notify_value = $2
               WHERE id = $3""",
            mode, value, product_id
        )
        return result == "UPDATE 1"
