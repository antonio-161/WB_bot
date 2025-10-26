"""
Низкоуровневая обёртка над asyncpg.
Только технические методы для работы с БД.

Принципы:
- НЕ содержит бизнес-логику
- Только fetch, execute, transaction
- Бизнес-логика в repositories и services
"""
import asyncpg
import asyncio
from typing import Any, List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DB:
    """
    Низкоуровневая обёртка над asyncpg.
    
    Отвечает ТОЛЬКО за подключение и выполнение запросов.
    НЕ содержит бизнес-логику!
    
    Пример использования:
        db = DB("postgresql://user:pass@localhost/dbname")
        await db.connect()
        
        # SELECT
        rows = await db.fetch("SELECT * FROM users WHERE id = $1", user_id)
        
        # INSERT/UPDATE/DELETE
        await db.execute("UPDATE users SET plan = $1 WHERE id = $2", "plan_pro", user_id)
        
        # Транзакция
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("INSERT ...")
                await conn.execute("UPDATE ...")
    """
    
    def __init__(self, dsn: str):
        """
        Args:
            dsn: Строка подключения к PostgreSQL
                 Пример: postgresql://user:pass@localhost:5432/dbname
        """
        self._dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """
        Создаёт пул подключений к БД.
        
        Raises:
            Exception: Если не удалось подключиться
        """
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    self._dsn,
                    min_size=2,
                    max_size=10,
                    max_inactive_connection_lifetime=300,
                    max_queries=10000,
                    command_timeout=60
                )
                logger.info("✅ Database pool created")
            except Exception as e:
                logger.exception(f"Failed to connect to database: {e}")
                raise
    
    async def close(self):
        """Закрывает пул подключений."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")
    
    # ===== SELECT запросы =====
    
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """
        Выполнить SELECT-запрос и вернуть все строки.
        
        Args:
            query: SQL запрос с плейсхолдерами $1, $2, ...
            *args: Параметры для подстановки
        
        Returns:
            Список записей (asyncpg.Record)
        
        Example:
            rows = await db.fetch(
                "SELECT * FROM users WHERE plan = $1",
                "plan_free"
            )
            for row in rows:
                print(row['id'], row['plan'])
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """
        Выполнить SELECT-запрос и вернуть одну строку.
        
        Args:
            query: SQL запрос
            *args: Параметры
        
        Returns:
            Одна запись или None если не найдено
        
        Example:
            user = await db.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )
            if user:
                print(user['plan'])
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args) -> Any:
        """
        Выполнить SELECT-запрос и вернуть одно значение.
        
        Args:
            query: SQL запрос
            *args: Параметры
        
        Returns:
            Одно значение (первый столбец первой строки)
        
        Example:
            count = await db.fetchval("SELECT COUNT(*) FROM users")
            print(f"Total users: {count}")
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    # ===== INSERT/UPDATE/DELETE запросы =====
    
    async def execute(self, query: str, *args) -> str:
        """
        Выполнить INSERT/UPDATE/DELETE-запрос.
        
        Args:
            query: SQL запрос
            *args: Параметры
        
        Returns:
            Результат выполнения (например, "UPDATE 1", "DELETE 5")
        
        Example:
            result = await db.execute(
                "UPDATE users SET plan = $1 WHERE id = $2",
                "plan_pro",
                123
            )
            print(result)  # "UPDATE 1"
        """
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    # ===== Batch операции =====
    
    async def execute_many(self, query: str, args_list: List[tuple]) -> None:
        """
        Выполнить один запрос с несколькими наборами параметров (batch insert).
        
        Args:
            query: SQL запрос
            args_list: Список кортежей с параметрами
        
        Example:
            await db.execute_many(
                "INSERT INTO products (user_id, nm_id) VALUES ($1, $2)",
                [(1, 123), (1, 456), (2, 789)]
            )
        """
        async with self.pool.acquire() as conn:
            await conn.executemany(query, args_list)
    
    # ===== Утилиты =====
    
    def dict_from_row(self, row: Optional[asyncpg.Record]) -> Optional[Dict]:
        """
        Конвертировать asyncpg.Record в dict.
        
        Args:
            row: Запись из БД
        
        Returns:
            Dict или None
        
        Example:
            row = await db.fetchrow("SELECT * FROM users WHERE id = $1", 123)
            user_dict = db.dict_from_row(row)
        """
        return dict(row) if row else None
    
    def dicts_from_rows(self, rows: List[asyncpg.Record]) -> List[Dict]:
        """
        Конвертировать список asyncpg.Record в список dict.
        
        Args:
            rows: Список записей
        
        Returns:
            Список dict
        
        Example:
            rows = await db.fetch("SELECT * FROM users")
            users = db.dicts_from_rows(rows)
        """
        return [dict(row) for row in rows]
    
    # ===== Health check =====
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья БД.
        
        Returns:
            Dict с информацией о состоянии подключения:
            {
                'status': 'healthy' | 'unhealthy',
                'response_time_ms': float,
                'pool_size': int,
                'pool_free': int,
                'pool_used': int
            }
        
        Example:
            health = await db.health_check()
            if health['status'] == 'healthy':
                print(f"DB OK, response: {health['response_time_ms']}ms")
        """
        try:
            start_time = asyncio.get_event_loop().time()
            await self.fetchval("SELECT 1")
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            pool_size = self.pool.get_size() if self.pool else 0
            pool_free = self.pool.get_idle_size() if self.pool else 0
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "pool_size": pool_size,
                "pool_free": pool_free,
                "pool_used": pool_size - pool_free
            }
        except Exception as e:
            logger.exception(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }