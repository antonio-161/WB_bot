"""
Сервис для работы с настройками пользователей.
"""
import logging
from typing import Dict, Optional, Tuple
from repositories.user_repository import UserRepository
from services.pvz_finder import get_dest_by_address
from constants import DEFAULT_DEST
from utils.cache import cached, settings_cache, user_cache

logger = logging.getLogger(__name__)


def _invalidate_user_settings_cache():
    prefix = "get_user_settings:"
    for key in list(settings_cache._cache.keys()):
        if key.startswith(prefix):
            settings_cache.remove(key)


class SettingsService:
    """Сервис для работы с настройками."""
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    @cached(ttl=600, cache_instance=settings_cache)
    async def get_user_settings(self, user_id: int) -> Dict:
        """Получить настройки пользователя."""
        user = await self.user_repo.get_by_id(user_id)
        
        if not user:
            return {
                "exists": False
            }
        
        discount = user.get("discount_percent", 0)
        plan_name = user.get("plan_name", "Не установлен")
        max_links = user.get("max_links", 5)
        dest = user.get("dest", DEFAULT_DEST)
        pvz_address = user.get("pvz_address")
        sort_mode = user.get("sort_mode", "savings")
        
        # Определяем информацию о ПВЗ
        if dest == DEFAULT_DEST or not dest:
            pvz_info = "Москва (по умолчанию)"
        elif pvz_address:
            pvz_info = pvz_address
        else:
            pvz_info = f"Код: {dest}"
        
        return {
            "exists": True,
            "discount": discount,
            "plan_name": plan_name,
            "max_links": max_links,
            "dest": dest,
            "pvz_address": pvz_address,
            "pvz_info": pvz_info,
            "sort_mode": sort_mode
        }
    
    async def update_discount(
        self,
        user_id: int,
        discount: int
    ) -> Tuple[bool, str]:
        """
        Обновить скидку WB кошелька.
        
        Returns:
            (success, message)
        """
        if not 0 <= discount <= 100:
            return False, "Скидка должна быть от 0 до 100%"
        
        success = await self.user_repo.set_discount(user_id, discount)
        
        if success:
            _invalidate_user_settings_cache()
            return True, f"Скидка установлена: {discount}%"
        else:
            return False, "Ошибка при сохранении скидки"
    
    async def update_pvz_by_address(
        self,
        user_id: int,
        address: str
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Обновить ПВЗ по адресу.
        
        Returns:
            (success, message, dest)
        """
        if len(address) < 5:
            return False, "Адрес слишком короткий", None
        
        # Получаем dest через Playwright
        dest = await get_dest_by_address(address)
        
        if not dest:
            return (
                False,
                "Не удалось найти пункт выдачи по указанному адресу",
                None
            )
        
        # Сохраняем в БД
        success = await self.user_repo.set_pvz(user_id, dest, address)
        
        if success:
            _invalidate_user_settings_cache()
            return True, f"ПВЗ установлен (dest={dest})", dest
        else:
            return False, "Ошибка при сохранении ПВЗ", None
    
    async def reset_pvz(self, user_id: int) -> Tuple[bool, str]:
        """
        Сбросить ПВЗ на значение по умолчанию.
        
        Returns:
            (success, message)
        """
        success = await self.user_repo.set_pvz(user_id, DEFAULT_DEST, None)
        
        if success:
            _invalidate_user_settings_cache()
            return True, "ПВЗ сброшен на Москву"
        else:
            return False, "Ошибка при сбросе ПВЗ"
    
    @cached(ttl=600, cache_instance=settings_cache)
    async def get_pvz_info(self, user_id: int) -> Dict:
        """Получить информацию о текущем ПВЗ."""
        user = await self.user_repo.get_by_id(user_id)
        
        if not user:
            return {"exists": False}
        
        dest = user.get("dest", DEFAULT_DEST)
        pvz_address = user.get("pvz_address")
        
        is_default = dest == DEFAULT_DEST or not dest
        
        return {
            "exists": True,
            "dest": dest,
            "address": pvz_address,
            "is_default": is_default
        }
    
    async def update_sort_mode(self, user_id: int, mode: str) -> Tuple[bool, str]:
        """
        Обновить режим сортировки.
        
        Args:
            mode: "savings" или "date"
        
        Returns:
            (success, message)
        """
        if mode not in ["savings", "date"]:
            return False, "Неверный режим сортировки"
        
        # ← ИЗМЕНЕНО: Сохраняем в БД, а не в кэш
        success = await self.user_repo.set_sort_mode(user_id, mode)
        
        if success:
            _invalidate_user_settings_cache()
            return True, "Режим сортировки обновлён"
        else:
            return False, "Ошибка при сохранении"
