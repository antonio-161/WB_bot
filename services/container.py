"""
Контейнер зависимостей (Dependency Injection Container).
"""
from typing import Optional

from infrastructure.db import DB
from services.price_fetcher import PriceFetcher
from infrastructure.user_repository import UserRepository
from infrastructure.product_repository import ProductRepository
from infrastructure.price_history_repository import PriceHistoryRepository

# Импорты сервисов
from services.user_service import UserService
from services.product_analytics_service import ProductAnalyticsService
from services.product_manager_service import ProductManagerService
from services.price_history_service import PriceHistoryService
from services.settings_service import SettingsService


class Container:
    """Контейнер всех зависимостей приложения."""

    def __init__(self, db: DB, price_fetcher: PriceFetcher):
        self.db = db
        self.price_fetcher = price_fetcher

        # Репозитории
        self._user_repo: Optional[UserRepository] = None
        self._product_repo: Optional[ProductRepository] = None
        self._price_history_repo: Optional[PriceHistoryRepository] = None

        # Бизнес-сервисы
        self._user_service: Optional[UserService] = None
        self._settings_service: Optional[SettingsService] = None
        self._product_manager_service: Optional[ProductManagerService] = None
        self._price_history_service: Optional[PriceHistoryService] = None
        self._product_analytics_service: Optional[ProductAnalyticsService] = None

    # ===== Репозитории =====

    def get_user_repo(self) -> UserRepository:
        if self._user_repo is None:
            self._user_repo = UserRepository(self.db)
        return self._user_repo

    def get_product_repo(self) -> ProductRepository:
        if self._product_repo is None:
            self._product_repo = ProductRepository(self.db)
        return self._product_repo

    def get_price_history_repo(self) -> PriceHistoryRepository:
        if self._price_history_repo is None:
            self._price_history_repo = PriceHistoryRepository(self.db)
        return self._price_history_repo

    # ===== Бизнес-сервисы =====

    def get_user_service(self) -> UserService:
        """Получить сервис пользователей."""
        if self._user_service is None:
            self._user_service = UserService(
                self.get_user_repo(),
                self.get_product_repo()
            )
        return self._user_service

    def get_settings_service(self) -> SettingsService:
        """Получить сервис настроек."""
        if self._settings_service is None:
            self._settings_service = SettingsService(
                self.get_user_repo()
            )
        return self._settings_service

    def get_product_manager_service(self) -> ProductManagerService:
        """Получить сервис управления товарами."""
        if self._product_manager_service is None:
            self._product_manager_service = ProductManagerService(
                self.get_product_repo(),
                self.get_price_history_repo(),
                self.price_fetcher
            )
        return self._product_manager_service

    def get_price_history_service(self) -> PriceHistoryService:
        """Получить сервис истории цен."""
        if self._price_history_service is None:
            self._price_history_service = PriceHistoryService(
                self.get_price_history_repo()
            )
        return self._price_history_service

    def get_product_analytics_service(self) -> ProductAnalyticsService:
        """Получить сервис аналитики товаров."""
        if self._product_analytics_service is None:
            self._product_analytics_service = ProductAnalyticsService(
                self.get_product_repo(),
                self.get_price_history_service()
            )
        return self._product_analytics_service
