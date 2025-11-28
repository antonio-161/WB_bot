"""
Репозиторий истории цен - работа с БД через DTO.
ТОЛЬКО SQL, никакой бизнес-логики про планы!
"""
from typing import List, Optional
from datetime import datetime
from infrastructure.db import DB
from core.dto import PriceHistoryDTO
from core.entities import PriceHistory
from core.mappers import PriceHistoryMapper
from utils.cache import cached, SimpleCache
from utils.decorators import retry_on_error


_repo_cache = SimpleCache(ttl_seconds=120)


class PriceHistoryRepository:
    """
    Репозиторий истории цен.
    Принимает DTO, возвращает Entities.
    """

    def __init__(self, db: DB):
        self.db = db
        self.mapper = PriceHistoryMapper()

    # ===== CRUD операции =====

    @retry_on_error(max_attempts=3, delay=0.5)
    async def add(self, dto: PriceHistoryDTO) -> int:
        """Добавить запись из DTO. Возвращает ID."""
        record_id = await self.db.fetchval(
            """INSERT INTO price_history (
                product_id, basic_price, product_price, qty
            )
            VALUES ($1, $2, $3, $4)
            RETURNING id""",
            dto.product_id, dto.basic_price, dto.product_price, dto.qty
        )
        return record_id

    async def get_by_id(self, record_id: int) -> Optional[PriceHistory]:
        """Получить запись по ID."""
        row = await self.db.fetchrow(
            """SELECT id, product_id, basic_price, product_price,
                      qty, recorded_at
               FROM price_history
               WHERE id = $1""",
            record_id
        )

        if not row:
            return None

        dto = PriceHistoryDTO(**dict(row))
        return self.mapper.to_entity(dto)

    async def delete(self, record_id: int) -> bool:
        """Удалить запись."""
        result = await self.db.execute(
            "DELETE FROM price_history WHERE id = $1",
            record_id
        )
        return result == "DELETE 1"

    # ===== Поиск =====

    async def get_by_product(
        self,
        product_id: int,
        limit: int = 100
    ) -> List[PriceHistory]:
        """Получить историю товара (от новых к старым)."""
        rows = await self.db.fetch(
            """SELECT id, product_id, basic_price, product_price,
                      qty, recorded_at
               FROM price_history
               WHERE product_id = $1
               ORDER BY recorded_at DESC
               LIMIT $2""",
            product_id, limit
        )

        return [
            self.mapper.to_entity(PriceHistoryDTO(**dict(r)))
            for r in rows
        ]

    async def get_by_products_batch(
        self,
        product_ids: List[int],
        limit: int = 30
    ) -> List[PriceHistory]:
        """
        Batch-метод: история для нескольких товаров.
        Возвращает все записи (у каждой есть product_id).
        """
        if not product_ids:
            return []

        query = """
            SELECT ph.id, ph.product_id, ph.basic_price, ph.product_price,
                   ph.qty, ph.recorded_at
            FROM products p
            CROSS JOIN LATERAL (
                SELECT *
                FROM price_history
                WHERE product_id = p.id
                ORDER BY recorded_at DESC
                LIMIT $2
            ) ph
            WHERE p.id = ANY($1)
            ORDER BY ph.product_id, ph.recorded_at DESC
        """

        rows = await self.db.fetch(query, product_ids, limit)

        return [
            self.mapper.to_entity(PriceHistoryDTO(**dict(r)))
            for r in rows
        ]

    # ===== Статистика =====

    @cached(cache_instance=_repo_cache)
    async def count_total(self) -> int:
        """Общее количество записей."""
        return await self.db.fetchval("SELECT COUNT(*) FROM price_history")

    async def count_recent(self, days: int) -> int:
        """Количество записей за последние N дней."""
        return await self.db.fetchval(
            """SELECT COUNT(*) FROM price_history
               WHERE recorded_at >= NOW() - $1::INTERVAL""",
            f"{days} days"
        )

    async def count_by_product(self, product_id: int) -> int:
        """Количество записей для товара."""
        return await self.db.fetchval(
            """SELECT COUNT(*) FROM price_history
               WHERE product_id = $1""",
            product_id
        )

    # ===== Очистка (ПРОСТЫЕ методы без логики планов) =====

    async def delete_older_than(
        self,
        product_ids: List[int],
        cutoff_date: datetime
    ) -> int:
        """
        Удалить записи старше даты для указанных товаров.

        Args:
            product_ids: Список ID товаров
            cutoff_date: Дата отсечки

        Returns:
            Количество удалённых записей
        """
        if not product_ids:
            return 0

        result = await self.db.execute(
            """DELETE FROM price_history
               WHERE product_id = ANY($1)
                 AND recorded_at < $2""",
            product_ids, cutoff_date
        )

        # Извлекаем число из "DELETE 123"
        deleted_count = (
            int(result.split()[-1])
            if result != "DELETE 0"
            else 0
        )
        return deleted_count

    async def delete_all_older_than(self, days: int) -> int:
        """
        Удалить ВСЕ записи старше N дней (для глобальной очистки).

        Args:
            days: Количество дней

        Returns:
            Количество удалённых записей
        """
        result = await self.db.execute(
            """DELETE FROM price_history
               WHERE recorded_at < NOW() - $1::INTERVAL""",
            f"{days} days"
        )

        deleted_count = (
            int(result.split()[-1])
            if result != "DELETE 0"
            else 0
        )
        return deleted_count
