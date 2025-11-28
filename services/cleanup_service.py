"""
Сервис очистки данных.
Знает о бизнес-правилах (планы, сроки хранения).
"""
import logging
from datetime import datetime, timedelta
from typing import Dict
from infrastructure.user_repository import UserRepository
from infrastructure.product_repository import ProductRepository
from infrastructure.price_history_repository import PriceHistoryRepository

logger = logging.getLogger(__name__)


# Конфигурация сроков хранения истории по планам
HISTORY_RETENTION_DAYS = {
    "plan_free": 30,
    "plan_basic": 90,
    "plan_pro": 365,
}


class CleanupService:
    """
    Сервис очистки устаревших данных.

    Отвечает за:
    - Очистку истории цен по правилам тарифов
    - Удаление старых данных
    """

    def __init__(
        self,
        user_repo: UserRepository,
        product_repo: ProductRepository,
        price_history_repo: PriceHistoryRepository
    ):
        self.user_repo = user_repo
        self.product_repo = product_repo
        self.price_history_repo = price_history_repo

    async def cleanup_history_by_plans(self) -> Dict[str, int]:
        """
        Очистить историю согласно тарифам пользователей.

        Процесс:
        1. Получить всех пользователей
        2. Сгруппировать по планам
        3. Для каждого плана - найти товары и удалить старую историю

        Returns:
            Dict с количеством удалённых записей по планам
        """
        logger.info("Начинаю очистку истории по планам")

        results = {
            "plan_free": 0,
            "plan_basic": 0,
            "plan_pro": 0,
        }

        # Обрабатываем каждый план
        for plan_key, retention_days in HISTORY_RETENTION_DAYS.items():
            try:
                deleted = await self._cleanup_for_plan(
                    plan_key, retention_days
                )
                results[plan_key] = deleted

                logger.info(
                    f"План {plan_key}: удалено {deleted} записей "
                    f"(старше {retention_days} дней)"
                )

            except Exception as e:
                logger.exception(
                    f"Ошибка при очистке истории для плана {plan_key}: {e}"
                )

        total_deleted = sum(results.values())
        logger.info(
            f"Очистка завершена. Всего удалено: {total_deleted} записей"
        )

        return results

    async def _cleanup_for_plan(
        self,
        plan_key: str,
        retention_days: int
    ) -> int:
        """
        Очистить историю для конкретного плана.

        Args:
            plan_key: Ключ плана (plan_free, plan_basic, plan_pro)
            retention_days: Срок хранения в днях

        Returns:
            Количество удалённых записей
        """
        # 1. Получаем пользователей с этим планом
        users = await self.user_repo.get_by_plan(plan_key)

        if not users:
            logger.debug(f"Нет пользователей с планом {plan_key}")
            return 0

        user_ids = [user.id for user in users]

        # 2. Получаем все товары этих пользователей
        all_product_ids = []
        for user_id in user_ids:
            products = await self.product_repo.get_by_user(user_id)
            all_product_ids.extend([p.id for p in products])

        if not all_product_ids:
            logger.debug(f"Нет товаров у пользователей с планом {plan_key}")
            return 0

        # 3. Удаляем историю старше N дней для этих товаров
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        deleted = await self.price_history_repo.delete_older_than(
            all_product_ids,
            cutoff_date
        )

        return deleted

    async def cleanup_old_data(self, days: int = 365) -> int:
        """
        Глобальная очистка ВСЕЙ истории старше N дней.
        Используется для emergency cleanup.

        Args:
            days: Количество дней

        Returns:
            Количество удалённых записей
        """
        logger.warning(f"Глобальная очистка истории старше {days} дней")

        deleted = await self.price_history_repo.delete_all_older_than(days)

        logger.info(f"Глобальная очистка: удалено {deleted} записей")

        return deleted

    async def cleanup_orphaned_history(self) -> int:
        """
        Удалить историю для несуществующих товаров.

        Returns:
            Количество удалённых записей
        """
        logger.info("Поиск и удаление осиротевших записей истории")

        result = await self.price_history_repo.db.execute(
            """DELETE FROM price_history
               WHERE product_id NOT IN (SELECT id FROM products)"""
        )

        deleted = (
            int(result.split()[-1])
            if result != "DELETE 0"
            else 0
        )

        if deleted > 0:
            logger.info(f"Удалено {deleted} осиротевших записей истории")

        return deleted
