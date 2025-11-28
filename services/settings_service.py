"""
Сервис для работы с настройками пользователей.
Отвечает за: валидацию, форматирование, сложную бизнес-логику настроек.
"""
import logging
from typing import Optional, Tuple

from core.enums import SortMode
from core.entities import User
from infrastructure.user_repository import UserRepository
from services.pvz_finder import get_dest_by_address
from constants import DEFAULT_DEST
from utils.cache import settings_cache

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

    async def update_discount(
        self,
        user_id: int,
        discount: int
    ) -> Tuple[bool, str]:
        """
        Обновить скидку WB кошелька.

        Args:
            user_id: ID пользователя
            discount: Процент скидки (0-100)

        Returns:
            (success, message)
        """
        user: User = await self.user_repo.get_by_id(user_id)
        if not user:
            return False, "Пользователь не найден"

        ok, message = user.validate_discount(discount)
        if not ok:
            return False, message

        await self.user_repo.update_discount(user_id, discount)

        return True, f"Ваша скидка обновлена: {discount}%"

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
        success = await self.user_repo.update_pvz(user_id, dest, address)

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
        success = await self.user_repo.update_pvz(user_id, DEFAULT_DEST, None)

        if success:
            _invalidate_settings_cache(user_id)
            return True, "ПВЗ сброшен. Установлен регион по умолчанию: Москва"
        else:
            return False, "Ошибка при сбросе ПВЗ"

    async def update_sort_mode(
            self, user_id: int, mode: str
    ) -> Tuple[bool, str]:
        """Установить режим сортировки: updated / savings."""

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False, "Пользователь не найден"

        try:
            sort_enum = SortMode(mode)
        except ValueError:
            return False, "Неверный режим сортировки"

        await self.user_repo.update_sort_mode(user_id, sort_enum.value)

        if sort_enum == SortMode.SAVINGS:
            return True, "Сортировка изменена: по экономии"
        else:
            return True, "Сортировка изменена: по дате обновления"
