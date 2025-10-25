"""
Низкоуровневая обёртка над asyncpg.
Только технические методы для работы с БД.
"""
import asyncpg
from typing import Any, List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DB:
    """
    Низкоуровневая обёртка над asyncpg.
    
    Отвечает ТОЛЬКО за подключение и выполнение запросов.
    НЕ содержит бизнес-логику!
    """
    
    def __init__(self, dsn: str):
        self._dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Создаёт пул подключений."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self._dsn,
                min_size=2,
                max_size=10,
                max_inactive_connection_lifetime=300,
                max_queries=10000,
                command_timeout=60
            )
            logger.info("✅ Database pool created")
    
    async def close(self):
        """Закрывает пул."""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")
    
    # ===== SELECT запросы =====
    
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """
        Выполнить SELECT-запрос и вернуть все строки.
        
        Example:
            rows = await db.fetch("SELECT * FROM users WHERE plan = $1", "plan_free")
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """
        Выполнить SELECT-запрос и вернуть одну строку.
        
        Example:
            user = await db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args) -> Any:
        """
        Выполнить SELECT-запрос и вернуть одно значение.
        
        Example:
            count = await db.fetchval("SELECT COUNT(*) FROM users")
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    # ===== INSERT/UPDATE/DELETE запросы =====
    
    async def execute(self, query: str, *args) -> str:
        """
        Выполнить INSERT/UPDATE/DELETE-запрос.
        
        Returns:
            str: Результат выполнения (например, "UPDATE 1")
        
        Example:
            await db.execute("UPDATE users SET plan = $1 WHERE id = $2", "plan_pro", 123)
        """
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    # ===== Дополнительные полезные методы =====
    
    async def execute_many(self, query: str, args_list: List[tuple]) -> None:
        """
        Выполнить один запрос с несколькими наборами параметров (batch insert).
        
        Example:
            await db.execute_many(
                "INSERT INTO products (user_id, nm_id) VALUES ($1, $2)",
                [(1, 123), (1, 456), (2, 789)]
            )
        """
        async with self.pool.acquire() as conn:
            await conn.executemany(query, args_list)
    
    async def transaction(self):
        """
        Контекстный менеджер для транзакций.
        
        Example:
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO users ...")
                await conn.execute("INSERT INTO products ...")
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    # ===== Вспомогательные методы =====
    
    def dict_from_row(self, row: Optional[asyncpg.Record]) -> Optional[Dict]:
        """
        Конвертировать asyncpg.Record в dict.
        
        Example:
            row = await db.fetchrow("SELECT * FROM users WHERE id = $1", 123)
            user_dict = db.dict_from_row(row)
        """
        return dict(row) if row else None
    
    def dicts_from_rows(self, rows: List[asyncpg.Record]) -> List[Dict]:
        """
        Конвертировать список asyncpg.Record в список dict.
        
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
            Dict с информацией о подключении
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
