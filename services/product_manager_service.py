# services/product_manager_service.py
"""
Сервис управления жизненным циклом товаров.
Отвечает за CRUD операции.
"""
import logging
from typing import Dict, Optional, Tuple

from core.dto import ProductDTO
from infrastructure.product_repository import ProductRepository
from infrastructure.price_history_repository import PriceHistoryRepository
from services.price_fetcher import PriceFetcher
from constants import DEFAULT_DEST
from utils.cache import product_cache

logger = logging.getLogger(__name__)


class ProductValidationError(Exception):
    """Ошибка валидации товара."""
    pass


class ProductManagerService:
    """
    Сервис управления товарами.

    Отвечает за:
    - Добавление/удаление товаров
    - Обновление атрибутов (размер, название, настройки)
    - Валидацию бизнес-правил
    """

    def __init__(
        self,
        product_repo: ProductRepository,
        price_history_repo: PriceHistoryRepository,
        price_fetcher: PriceFetcher
    ):
        self.product_repo = product_repo
        self.price_history_repo = price_history_repo
        self.price_fetcher = price_fetcher

    async def add_product(
        self,
        user_id: int,
        nm_id: int,
        url: str,
        dest: Optional[int] = None,
        size_name: Optional[str] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Добавить товар в отслеживание.

        Args:
            user_id: ID пользователя
            nm_id: Артикул товара
            url: URL товара
            dest: Регион доставки
            size_name: Название размера (опционально)

        Returns:
            (success, message, product_id)

        Raises:
            ProductValidationError: При ошибке валидации
        """
        # 1. Проверяем существование
        existing = await self.product_repo.get_by_nm_id(user_id, nm_id)
        if existing:
            return False, "Товар уже в отслеживании", None

        # 2. Получаем данные о товаре
        product_data = await self._fetch_product_data(nm_id, dest, size_name)
        if not product_data:
            return False, "Не удалось получить данные о товаре", None

        # Формируем DTO (не Entity!)
        dto = ProductDTO(
            id=None,
            user_id=user_id,
            url_product=product_data["url"],
            nm_id=product_data["nm_id"],
            name_product=product_data["name"],
            custom_name=None,
            last_basic_price=product_data["basic_price"],
            last_product_price=product_data["product_price"],
            selected_size=product_data["size_name"],
            notify_mode=None,
            notify_value=None,
            last_qty=product_data["qty"],
            out_of_stock=product_data["out_of_stock"],
            created_at=None,
            updated_at=None,
        )

        # 3. Создаём товар в БД
        product_id = await self.product_repo.create(dto)

        if not product_id:
            return False, "Ошибка при создании товара", None

        # 4. Сохраняем начальные цены
        try:
            await self._save_product_prices(product_id, product_data)
            logger.info(
                f"Товар добавлен: user={user_id}, nm_id={nm_id}, "
                f"product_id={product_id}, size={product_data.size_name}"
            )
            return True, "Товар добавлен", product_id
        except Exception as e:
            # Откатываем создание товара
            await self.product_repo.delete(product_id)
            logger.exception(f"Ошибка при сохранении цен для {nm_id}: {e}")
            return False, "Ошибка при сохранении данных о товаре", None

    async def _fetch_product_data(
        self,
        nm_id: int,
        dest: Optional[int],
        size_name: Optional[str]
    ) -> Optional[Dict]:
        """
        Получить данные о товаре из API и преобразовать в доменную модель.

        Изолирует сервис от структуры API.
        """
        raw_data = await self.price_fetcher.get_product_data(nm_id, dest)
        if not raw_data:
            return None

        sizes = raw_data.get("sizes", [])
        if not sizes:
            logger.warning(f"Товар {nm_id} не имеет размеров")
            return None

        # Находим нужный размер или берём первый
        if size_name:
            size_data = next(
                (s for s in sizes if s.get("name") == size_name),
                None
            )
            if not size_data:
                raise ProductValidationError(
                    f"Размер '{size_name}' не найден для товара {nm_id}"
                )
        else:
            size_data = sizes[0]
            size_name = size_data.get("name")

        # Извлекаем данные
        price_info = size_data.get("price", {})
        stocks = size_data.get("stocks", [])
        qty = sum(stock.get("qty", 0) for stock in stocks)

        return {
            "nm_id": nm_id,
            "name": raw_data.get("name"),
            "size_name": size_name,
            "basic_price": price_info.get("basic"),
            "product_price": price_info.get("product"),
            "qty": qty,
            "out_of_stock": qty == 0,
            "url": raw_data.get("url")
        }

    async def _save_product_prices(
        self,
        product_id: int,
        data: Dict
    ) -> None:
        """
        Сохранить цены товара в БД и историю.

        Универсальный метод для любых сценариев.
        """
        # Обновляем товар
        await self.product_repo.update_prices_and_stock(
            product_id,
            data.get("basic_price"),
            data.get("product_price"),
            data.get("qty"),
            data.get("out_of_stock")
        )

        # Добавляем в историю
        await self.price_history_repo.add(
            product_id,
            data.get("basic_price"),
            data.get("product_price"),
            data.get("qty"),
        )

        # Инвалидируем кэш
        self._invalidate_product_cache(product_id, data.nm_id)

    async def update_product_size(
        self,
        product_id: int,
        size_name: str,
        nm_id: int,
        dest: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Обновить размер товара и цены для него.
        """
        try:
            # Получаем данные для нового размера
            product_data = await self._fetch_product_data(nm_id, dest, size_name)
            if not product_data:
                return False, "Не удалось получить данные о товаре"

            # Устанавливаем размер
            await self.product_repo.update_size(product_id, size_name)

            # Сохраняем цены
            await self._save_product_prices(product_id, product_data)

            logger.info(f"Размер обновлён: product_id={product_id}, size={size_name}")
            return True, "Размер обновлён"

        except ProductValidationError as e:
            return False, str(e)
        except Exception as e:
            logger.exception(f"Ошибка при обновлении размера {product_id}: {e}")
            return False, "Ошибка при обновлении размера"

    async def rename_product(
        self,
        product_id: int,
        new_name: str
    ) -> Tuple[bool, str]:
        """
        Переименовать товар.

        Returns:
            (success, message)
        """
        # Валидация
        if len(new_name) < 3:
            return False, "Название слишком короткое (минимум 3 символа)"

        if len(new_name) > 200:
            return False, "Название слишком длинное (максимум 200 символов)"

        # Получаем nm_id для инвалидации кэша
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            return False, "Товар не найден"

        success = await self.product_repo.set_custom_name(product_id, new_name)

        if success:
            self._invalidate_product_cache(product_id, product['nm_id'])
            logger.info(f"Товар переименован: product_id={product_id}, new_name={new_name}")
            return True, "Товар переименован"
        else:
            return False, "Ошибка при переименовании"

    async def set_notify_settings(
        self,
        product_id: int,
        mode: Optional[str],
        value: Optional[int]
    ) -> Tuple[bool, str]:
        """
        Установить настройки уведомлений.
        """
        # Валидация
        if mode == "percent" and (value <= 0 or value > 100):
            return False, "Процент должен быть от 1 до 100"

        if mode == "threshold" and value <= 0:
            return False, "Порог должен быть положительным числом"

        success = await self.product_repo.set_notify_settings(
            product_id,
            mode,
            value
        )

        if success:
            logger.info(
                f"Настройки уведомлений обновлены: "
                f"product_id={product_id}, mode={mode}, value={value}"
            )
            return True, "Настройки уведомлений обновлены"
        else:
            return False, "Ошибка при сохранении настроек"

    async def remove_product(
        self,
        user_id: int,
        nm_id: int
    ) -> Tuple[bool, str]:
        """
        Удалить товар из отслеживания.

        Проверяет владение товаром.
        """
        # Проверяем существование и владение
        product = await self.product_repo.get_by_nm_id(user_id, nm_id)
        if not product:
            return False, "Товар не найден или вам не принадлежит"

        product_id = product['id']

        success = await self.product_repo.delete_by_nm_id(user_id, nm_id)

        if success:
            self._invalidate_product_cache(product_id, nm_id)
            logger.info(f"Товар удалён: user_id={user_id}, nm_id={nm_id}")
            return True, "Товар удалён из отслеживания"
        else:
            return False, "Ошибка при удалении товара"

    def _invalidate_product_cache(self, product_id: int, nm_id: int):
        """Очистить кэш товара."""
        product_cache.remove(f"get_product_detail:{product_id}")
        product_cache.remove(f"product_{nm_id}_{DEFAULT_DEST}")
