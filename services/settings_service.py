"""
Сервис для работы с настройками пользователей.
Отвечает за: валидацию, форматирование, сложную бизнес-логику настроек.
"""
import logging
from typing import Dict, Optional, Tuple
from infrastructure.user_repository import UserRepository
from services.pvz_finder import get_dest_by_address
from constants import DEFAULT_DEST
from utils.cache import cached, settings_cache

logger = logging.getLogger(__name__)


def _invalidate_settings_cache(user_id: int):
    """Очистить кэш настроек пользователя."""
    settings_cache.remove(f"get_user_settings:{user_id}")
    settings_cache.remove(f"get_pvz_info:{user_id}")


class SettingsService:
    """
    Сервис для работы с настройками пользователей.

    Ответственность:
    - Получение и форматирование настроек
    - Валидация изменений
    - Сложная логика (поиск ПВЗ через Playwright)
    - Кэширование настроек
    """

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    # ===== Получение настроек =====

    @cached(ttl=600, cache_instance=settings_cache)
    async def get_user_settings(self, user_id: int) -> Dict:
        """
        Получить все настройки пользователя с форматированием.

        Returns:
            Dict с настройками или {"exists": False}
        """
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            return {"exists": False}

        discount = user.get("discount_percent", 0)
        plan_name = user.get("plan_name", "Не установлен")
        max_links = user.get("max_links", 5)
        dest = user.get("dest", DEFAULT_DEST)
        pvz_address = user.get("pvz_address")
        sort_mode = user.get("sort_mode", "savings")

        # Форматируем информацию о ПВЗ
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

    @cached(ttl=600, cache_instance=settings_cache)
    async def get_pvz_info(self, user_id: int) -> Dict:
        """
        Получить информацию о текущем ПВЗ.

        Returns:
            Dict с информацией о ПВЗ
        """
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

    # ===== Изменение настроек =====

    async def update_discount(
        self,
        user_id: int,
        discount: int
    ) -> Tuple[bool, str]:
        """
        Обновить скидку WB кошелька с валидацией.

        Args:
            user_id: ID пользователя
            discount: Процент скидки (0-100)

        Returns:
            (success, message)
        """
        # Валидация
        if not isinstance(discount, int):
            return False, "Скидка должна быть целым числом"

        if not 0 <= discount <= 100:
            return False, "Скидка должна быть от 0 до 100%"

        # Сохраняем через репозиторий
        success = await self.user_repo.set_discount(user_id, discount)

        if success:
            _invalidate_settings_cache(user_id)
            return True, f"Скидка установлена: {discount}%"
        else:
            return False, "Ошибка при сохранении скидки"

    async def update_pvz_by_address(
        self,
        user_id: int,
        address: str
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Обновить ПВЗ по адресу (сложная операция с Playwright).

        Args:
            user_id: ID пользователя
            address: Адрес ПВЗ

        Returns:
            (success, message, dest)
        """
        # Валидация адреса
        if not address or len(address.strip()) < 5:
            return False, "Адрес слишком короткий (минимум 5 символов)", None

        address = address.strip()

        # Получаем dest через Playwright (может занять 10-30 секунд)
        logger.info(f"Ищу ПВЗ для адреса: {address}")
        dest = await get_dest_by_address(address)

        if not dest:
            return (
                False,
                "Не удалось найти пункт выдачи по указанному адресу. "
                "Проверьте правильность адреса на сайте WB.",
                None
            )

        # Сохраняем в БД
        success = await self.user_repo.set_pvz(user_id, dest, address)

        if success:
            _invalidate_settings_cache(user_id)
            logger.info(f"ПВЗ установлен для user_id={user_id}, dest={dest}")
            return True, f"ПВЗ установлен (dest={dest})", dest
        else:
            return False, "Ошибка при сохранении ПВЗ", None

    async def reset_pvz(self, user_id: int) -> Tuple[bool, str]:
        """
        Сбросить ПВЗ на значение по умолчанию (Москва).

        Returns:
            (success, message)
        """
        success = await self.user_repo.set_pvz(user_id, DEFAULT_DEST, None)

        if success:
            _invalidate_settings_cache(user_id)
            return True, "ПВЗ сброшен на Москву"
        else:
            return False, "Ошибка при сбросе ПВЗ"

    async def update_sort_mode(
            self, user_id: int, mode: str
    ) -> Tuple[bool, str]:
        """
        Обновить режим сортировки товаров.

        Args:
            mode: "savings" (по выгодности) или "date" (по дате)

        Returns:
            (success, message)
        """
        # Валидация
        if mode not in ["savings", "date"]:
            return False, "Неверный режим сортировки. Допустимые: savings, date"

        # Сохраняем
        success = await self.user_repo.set_sort_mode(user_id, mode)

        if success:
            _invalidate_settings_cache(user_id)
            mode_name = "по выгодности" if mode == "savings" else "по дате добавления"
            return True, f"Режим сортировки изменён: {mode_name}"
        else:
            return False, "Ошибка при сохранении режима сортировки"
