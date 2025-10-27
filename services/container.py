"""
Контейнер зависимостей (Dependency Injection Container).
"""
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot

from services.db import DB
from services.price_fetcher import PriceFetcher
from repositories.user_repository import UserRepository
from repositories.product_repository import ProductRepository
from repositories.price_history_repository import PriceHistoryRepository

# Импорты сервисов
from services.user_service import UserService
from services.product_service import ProductService
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
        self._product_service: Optional[ProductService] = None
        self._settings_service: Optional[SettingsService] = None
        
        # Высокоуровневые сервисы
        self._monitor_service: Optional['MonitorService'] = None
        self._background_service: Optional['BackgroundService'] = None
        self._reporting_service: Optional['ReportingService'] = None

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
    
    def get_product_service(self) -> ProductService:
        """Получить сервис товаров."""
        if self._product_service is None:
            self._product_service = ProductService(
                self.get_product_repo(),
                self.get_price_history_repo(),
                self.price_fetcher
            )
        return self._product_service
    
    def get_settings_service(self) -> SettingsService:
        """Получить сервис настроек."""
        if self._settings_service is None:
            self._settings_service = SettingsService(
                self.get_user_repo()
            )
        return self._settings_service
    
    # ===== Высокоуровневые сервисы =====
    
    def get_monitor_service(self, bot: 'Bot') -> 'MonitorService':
        if self._monitor_service is None:
            from services.monitor_service import MonitorService
            self._monitor_service = MonitorService(self, bot)
        return self._monitor_service
    
    def get_background_service(self, bot: 'Bot') -> 'BackgroundService':
        if self._background_service is None:
            from services.background_service import BackgroundService
            self._background_service = BackgroundService(self, bot)
        return self._background_service
    
    def get_reporting_service(
            self, bot: 'Bot', poll_interval: int
    ) -> 'ReportingService':
        if self._reporting_service is None:
            from services.reporting_service import ReportingService
            self._reporting_service = ReportingService(bot, poll_interval)
        return self._reporting_service
