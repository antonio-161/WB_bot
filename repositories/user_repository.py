"""
Репозиторий для работы с пользователями.
Содержит ВСЮ логику работы с таблицей users.
"""
from typing import Optional, Dict, List
from services.db import DB


class UserRepository:
    """
    Репозиторий пользователей.
    Отвечает ТОЛЬКО за доступ к данным, БЕЗ бизнес-логики.
    """
    
    def __init__(self, db: DB):
        self.db = db
    
    # ===== CRUD операции =====
    
    async def get_by_id(self, user_id: int) -> Optional[Dict]:
        """
        Получить пользователя по ID.
        
        Returns:
            Dict с данными пользователя или None
        """
        row = await self.db.fetchrow(
            """SELECT id, plan, plan_name, discount_percent, max_links, 
                      dest, pvz_address, created_at 
               FROM users 
               WHERE id = $1""",
            user_id
        )
        return dict(row) if row else None
    
    async def create(self, user_id: int) -> Dict:
        """
        Создать пользователя с дефолтными значениями.
        
        Returns:
            Dict с данными созданного пользователя
        """
        await self.db.execute(
            """INSERT INTO users (id, plan, plan_name, max_links)
               VALUES ($1, 'plan_free', 'Бесплатный', 5)
               ON CONFLICT (id) DO NOTHING""",
            user_id
        )
        return await self.get_by_id(user_id)
    
    async def ensure_exists(self, user_id: int) -> Dict:
        """
        Создать пользователя если не существует, иначе вернуть существующего.
        
        Returns:
            Dict с данными пользователя
        """
        user = await self.get_by_id(user_id)
        if user:
            return user
        return await self.create(user_id)
    
    async def delete(self, user_id: int) -> bool:
        """
        Удалить пользователя.
        
        Returns:
            True если удалён, False если не существовал
        """
        result = await self.db.execute(
            "DELETE FROM users WHERE id = $1",
            user_id
        )
        return result == "DELETE 1"
    
    # ===== Специфичные методы для User =====
    
    async def get_all(self) -> List[Dict]:
        """Получить всех пользователей."""
        rows = await self.db.fetch("SELECT * FROM users ORDER BY created_at DESC")
        return [dict(r) for r in rows]
    
    async def get_by_plan(self, plan_key: str) -> List[Dict]:
        """Получить пользователей по тарифу."""
        rows = await self.db.fetch(
            "SELECT * FROM users WHERE plan = $1",
            plan_key
        )
        return [dict(r) for r in rows]
    
    async def count_total(self) -> int:
        """Общее количество пользователей."""
        return await self.db.fetchval("SELECT COUNT(*) FROM users")
    
    async def count_by_plan(self) -> Dict[str, int]:
        """Статистика по тарифам."""
        rows = await self.db.fetch(
            """SELECT plan, COUNT(*) as count 
               FROM users 
               GROUP BY plan"""
        )
        return {r['plan']: r['count'] for r in rows}
    
    # ===== Обновление полей =====
    
    async def set_plan(
        self,
        user_id: int,
        plan_key: str,
        plan_name: str,
        max_links: int
    ) -> bool:
        """Установить тариф пользователю."""
        result = await self.db.execute(
            """UPDATE users 
               SET plan = $1, plan_name = $2, max_links = $3 
               WHERE id = $4""",
            plan_key, plan_name, max_links, user_id
        )
        return result == "UPDATE 1"
    
    async def set_discount(self, user_id: int, discount: int) -> bool:
        """Установить скидку WB кошелька."""
        result = await self.db.execute(
            "UPDATE users SET discount_percent = $1 WHERE id = $2",
            discount, user_id
        )
        return result == "UPDATE 1"
    
    async def set_pvz(self, user_id: int, dest: int, address: Optional[str] = None) -> bool:
        """Установить пункт выдачи."""
        result = await self.db.execute(
            "UPDATE users SET dest = $1, pvz_address = $2 WHERE id = $3",
            dest, address, user_id
        )
        return result == "UPDATE 1"