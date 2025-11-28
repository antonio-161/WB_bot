"""
Репозиторий пользователей - работа с БД через DTO.
"""
from typing import Optional, List
from infrastructure.db import DB
from core.dto import UserDTO
from core.entities import User
from core.mappers import UserMapper
from core.enums import Plan, SortMode
from utils.cache import cached, SimpleCache


_repo_cache = SimpleCache(ttl_seconds=300)


class UserRepository:
    """
    Репозиторий пользователей.
    Принимает DTO, возвращает Entities.
    """

    _BASE_QUERY = """
        SELECT id, plan, discount_percent, max_links,
               dest, pvz_address, sort_mode, created_at
        FROM users
    """

    def __init__(self, db: DB):
        self.db = db
        self.mapper = UserMapper()

    # ===== Приватные утилиты =====

    def _row_to_entity(self, row) -> User:
        """Конвертировать asyncpg.Record в User."""
        dto = UserDTO(**dict(row))
        return self.mapper.to_entity(dto)

    def _rows_to_entities(self, rows) -> List[User]:
        """Конвертировать список asyncpg.Record в список User."""
        return [self._row_to_entity(row) for row in rows]

    # ===== CRUD =====

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID."""
        row = await self.db.fetchrow(
            self._BASE_QUERY + " WHERE id = $1",
            user_id
        )
        return self._row_to_entity(row) if row else None

    async def create(self, entity: User) -> User:
        """Создать пользователя."""
        dto = self.mapper.to_dto(entity)

        try:
            row = await self.db.fetchrow(
                """INSERT INTO users (id, plan, discount_percent, max_links,
                                    dest, pvz_address, sort_mode)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO NOTHING
                RETURNING id, plan, discount_percent, max_links,
                         dest, pvz_address, sort_mode""",
                dto.id, dto.plan, dto.discount_percent, dto.max_links,
                dto.dest, dto.pvz_address, dto.sort_mode,
            )
        except Exception as e:
            raise RuntimeError(f"Ошибка при создании пользователя: {e}")

        return self._row_to_entity(row) if row else await self.get_by_id(
            dto.id
        )

    async def update(self, entity: User) -> bool:
        """Обновить пользователя."""
        dto = self.mapper.to_dto(entity)

        result = await self.db.execute(
            """UPDATE users
               SET plan = $2, discount_percent = $3, max_links = $4,
                   dest = $5, pvz_address = $6, sort_mode = $7
               WHERE id = $1""",
            dto.id, dto.plan, dto.discount_percent, dto.max_links,
            dto.dest, dto.pvz_address, dto.sort_mode,
        )

        return result == "UPDATE 1"

    async def delete(self, user_id: int) -> bool:
        """Удалить пользователя."""
        result = await self.db.execute(
            "DELETE FROM users WHERE id = $1", user_id
        )
        return result == "DELETE 1"

    # ===== Специфичные запросы =====

    async def get_all(self) -> List[User]:
        """Получить всех пользователей."""
        rows = await self.db.fetch(
            self._BASE_QUERY + " ORDER BY created_at DESC"
        )
        return self._rows_to_entities(rows)

    async def get_by_plan(self, plan: Plan) -> List[User]:
        """Получить пользователей по тарифному плану."""
        rows = await self.db.fetch(
            self._BASE_QUERY + " WHERE plan = $1",
            plan.value,
        )
        return self._rows_to_entities(rows)

    # ===== Статистика =====

    @cached(cache_instance=_repo_cache)
    async def count_total(self) -> int:
        """Общее количество пользователей."""
        return await self.db.fetchval("SELECT COUNT(*) FROM users")

    async def count_recent(self, days: int) -> int:
        """Количество пользователей добавленных за последние N дней."""
        return await self.db.fetchval(
            """SELECT COUNT(*) FROM users
               WHERE created_at >= NOW() - $1::INTERVAL""",
            f"{days} days",
        )

    @cached(cache_instance=_repo_cache)
    async def get_plan_stats(self) -> List[dict]:
        """Статистика по тарифам."""
        rows = await self.db.fetch(
            """SELECT plan, COUNT(*) as count
               FROM users
               GROUP BY plan
               ORDER BY count DESC"""
        )
        return [dict(r) for r in rows]

    # ===== Обновление отдельных полей =====

    async def update_plan(
            self, user_id: int, plan: Plan, max_links: int
    ) -> bool:
        """Обновить тарифный план."""
        result = await self.db.execute(
            """UPDATE users SET plan = $2, max_links = $3 WHERE id = $1""",
            user_id, plan.value, max_links
        )
        return result == "UPDATE 1"

    async def update_discount(self, user_id: int, discount: int) -> bool:
        """Обновить процент скидки."""
        result = await self.db.execute(
            "UPDATE users SET discount_percent = $1 WHERE id = $2",
            discount, user_id
        )
        return result == "UPDATE 1"

    async def update_pvz(
            self, user_id: int, dest: int, address: Optional[str]
    ) -> bool:
        """Обновить адрес ПВЗ."""
        result = await self.db.execute(
            "UPDATE users SET dest = $1, pvz_address = $2 WHERE id = $3",
            dest, address, user_id
        )
        return result == "UPDATE 1"

    async def update_sort_mode(
            self, user_id: int, sort_mode: SortMode
    ) -> bool:
        """Обновить режим сортировки."""
        result = await self.db.execute(
            "UPDATE users SET sort_mode = $1 WHERE id = $2",
            sort_mode.value, user_id
        )
        return result == "UPDATE 1"
