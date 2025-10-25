"""
Контейнер зависимостей (Dependency Injection Container).

Зачем:
- Единое место создания всех объектов
- Легко тестировать (можно заменить на моки)
- Легко менять реализации
- Контроль жизненного цикла объектов
"""
from typing import Optional
from services.db import DB
from services.price_fetcher import PriceFetcher
from repositories.user_repository import UserRepository
from repositories.product_repository import ProductRepository
from repositories.price_history_repository import PriceHistoryRepository


class Container:
    """
    Контейнер всех зависимостей приложения.

    Принцип: Создаём объекты один раз,
    переиспользуем везде (Singleton pattern).
    """

    def __init__(self, db: DB, price_fetcher: PriceFetcher):
        """
        Args:
            db: Подключение к БД (уже инициализировано)
            price_fetcher: Сервис получения цен (уже инициализирован)
        """
        self.db = db
        self.price_fetcher = price_fetcher

        # Репозитории (создаём лениво)
        self._user_repo: Optional[UserRepository] = None
        self._product_repo: Optional[ProductRepository] = None
        self._price_history_repo: Optional[PriceHistoryRepository] = None

    # ===== Репозитории (Lazy Initialization) =====

    def get_user_repo(self) -> UserRepository:
        """Получить репозиторий пользователей."""
        if self._user_repo is None:
            self._user_repo = UserRepository(self.db)
        return self._user_repo

    def get_product_repo(self) -> ProductRepository:
        """Получить репозиторий товаров."""
        if self._product_repo is None:
            self._product_repo = ProductRepository(self.db)
        return self._product_repo

    def get_price_history_repo(self) -> PriceHistoryRepository:
        """Получить репозиторий истории цен."""
        if self._price_history_repo is None:
            self._price_history_repo = PriceHistoryRepository(self.db)
        return self._price_history_repo
