"""
Контейнер зависимостей (Dependency Injection Container).

Зачем:
- Единое место создания всех объектов
- Легко тестировать (можно заменить на моки)
- Легко менять реализации
- Контроль жизненного цикла объектов
"""
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot
    from services.monitor_service import MonitorService
    from services.background_service import BackgroundService
    from services.reporting_service import ReportingService

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
        
        # Высокоуровневые сервисы (создаём лениво)
        self._monitor_service: Optional['MonitorService'] = None
        self._background_service: Optional['BackgroundService'] = None
        self._reporting_service: Optional['ReportingService'] = None

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
    
    # ===== Высокоуровневые сервисы =====
    
    def get_monitor_service(self, bot: 'Bot') -> 'MonitorService':
        """
        Получить сервис мониторинга.
        
        Args:
            bot: Экземпляр Telegram бота
        
        Returns:
            MonitorService
        """
        if self._monitor_service is None:
            from services.monitor_service import MonitorService
            self._monitor_service = MonitorService(self, bot)
        return self._monitor_service
    
    def get_background_service(self, bot: 'Bot') -> 'BackgroundService':
        """
        Получить сервис фоновых задач.
        
        Args:
            bot: Экземпляр Telegram бота
        
        Returns:
            BackgroundService
        """
        if self._background_service is None:
            from services.background_service import BackgroundService
            self._background_service = BackgroundService(self, bot)
        return self._background_service
    
    def get_reporting_service(self, bot: 'Bot', poll_interval: int) -> 'ReportingService':
        """
        Получить сервис отчётов.
        
        Args:
            bot: Экземпляр Telegram бота
            poll_interval: Интервал опроса в секундах
        
        Returns:
            ReportingService
        """
        if self._reporting_service is None:
            from services.reporting_service import ReportingService
            self._reporting_service = ReportingService(bot, poll_interval)
        return self._reporting_service
