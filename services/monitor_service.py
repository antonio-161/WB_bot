"""
Сервис мониторинга цен товаров.
Вся бизнес-логика мониторинга вынесена сюда.
"""
import asyncio
import logging
from typing import Dict, Optional
from aiogram import Bot
from aiogram import exceptions

from infrastructure.models import ProductRow
from services.container import Container
from constants import DEFAULT_DEST
from utils.cache import product_cache
from utils.wb_utils import apply_wallet_discount

logger = logging.getLogger(__name__)


class MonitorService:
    """
    Сервис мониторинга цен.
    
    Отвечает за:
    - Обработку товаров
    - Проверку изменений цен/остатков
    - Формирование и отправку уведомлений
    """
    
    def __init__(self, container: Container, bot: Bot):
        self.container = container
        self.bot = bot
        self.product_repo = container.get_product_repo()
        self.price_history_repo = container.get_price_history_repo()
        self.user_repo = container.get_user_repo()
        self.price_fetcher = container.price_fetcher
    
    async def process_product(
        self,
        product: ProductRow,
        metrics: Dict[str, int]
    ) -> None:
        """
        Обработать один товар: получить новые данные, проверить изменения,
        отправить уведомления.
        
        Args:
            product: Товар для обработки
            metrics: Словарь с метриками (processed, errors, notifications)
        """
        try:
            # Получаем пользователя для dest
            user = await self.user_repo.get_by_id(product.user_id)
            dest = user.get("dest", DEFAULT_DEST) if user else DEFAULT_DEST
            
            # Получаем данные о товаре
            new_data = await self.price_fetcher.get_product_data(
                product.nm_id,
                dest=dest
            )
            
            if not new_data:
                metrics["errors"] += 1
                logger.info(
                    f"[nm={product.nm_id}] Данные не получены (возможно challenge), "
                    f"пропускаем обновление"
                )
                return
            
            # Извлекаем цены и остатки
            price_data = self._extract_price_data(product, new_data)
            
            if not price_data:
                metrics["errors"] += 1
                logger.warning(
                    f"[nm={product.nm_id}] Не удалось извлечь данные о ценах"
                )
                return
            
            # Обновляем название если нужно
            await self._update_product_name_if_needed(product, new_data)
            
            # Проверяем нужны ли уведомления
            notifications = await self._check_notifications(
                product,
                price_data,
                user
            )
            
            # Сохраняем новые данные
            await self._save_product_data(product.id, price_data)
            
            # Добавляем в историю при изменении цены
            if (product.last_product_price is None or 
                price_data['product_price'] != product.last_product_price):
                await self.price_history_repo.add(
                    product.id,
                    price_data['basic_price'],
                    price_data['product_price'],
                    price_data['qty']
                )
            
            metrics["processed"] += 1
            
            # Отправляем уведомления
            if notifications:
                await self._send_notifications(
                    product,
                    notifications,
                    price_data,
                    user
                )
                metrics["notifications"] += 1
            
        except Exception as e:
            logger.exception(
                f"[nm={product.nm_id}] Ошибка при обработке товара: {e}"
            )
            metrics["errors"] += 1
    
    def _extract_price_data(
        self,
        product: ProductRow,
        new_data: Dict
    ) -> Optional[Dict]:
        """
        Извлечь данные о ценах и остатках из ответа API.
        
        Returns:
            Dict с ключами: basic_price, product_price, qty, out_of_stock
            или None при ошибке
        """
        sizes = new_data.get("sizes", [])
        
        # Проверяем наличие реальных размеров
        has_real_sizes = any(
            s.get("name") not in ("", "0", None)
            for s in sizes
        )
        
        # Товар с размерами
        if has_real_sizes:
            selected_size = product.selected_size
            if not selected_size:
                logger.info(
                    f"[nm={product.nm_id}] Размер не выбран, пропуск"
                )
                return None
            
            # Находим выбранный размер
            size_data = next(
                (s for s in sizes if s.get("name") == selected_size),
                None
            )
            
            if not size_data:
                logger.warning(
                    f"[nm={product.nm_id}] Выбранный размер "
                    f"'{selected_size}' не найден"
                )
                return None
            
            price_info = size_data.get("price", {})
            stocks = size_data.get("stocks", [])
        
        # Товар без размеров
        else:
            size_data = sizes[0] if sizes else {}
            price_info = size_data.get("price", new_data.get("price", {}))
            stocks = size_data.get("stocks", new_data.get("stocks", []))
            
            if not price_info:
                logger.warning(
                    f"[nm={product.nm_id}] Нет данных о цене "
                    f"(товар без размеров)"
                )
                return None
        
        # Формируем результат
        basic_price = price_info.get("basic", 0)
        product_price = price_info.get("product", 0)
        qty = sum(stock.get("qty", 0) for stock in stocks)
        
        return {
            "basic_price": basic_price,
            "product_price": product_price,
            "qty": qty,
            "out_of_stock": qty == 0
        }
    
    async def _update_product_name_if_needed(
        self,
        product: ProductRow,
        new_data: Dict
    ) -> None:
        """Обновить название товара если оно placeholder."""
        if product.name_product == "Загрузка..." and new_data.get("name"):
            await self.product_repo.update_name(
                product.id,
                new_data["name"]
            )
    
    async def _check_notifications(
        self,
        product: ProductRow,
        price_data: Dict,
        user: Optional[Dict]
    ) -> Dict[str, bool]:
        """
        Проверить нужны ли уведомления.
        
        Returns:
            Dict с флагами: price_drop, stock_out, stock_in
        """
        notifications = {
            "price_drop": False,
            "stock_out": False,
            "stock_in": False
        }
        
        old_price = product.last_product_price
        new_price = price_data['product_price']
        old_qty = product.last_qty
        new_qty = price_data['qty']
        
        # Проверка снижения цены
        if old_price is not None and new_price < old_price:
            if product.notify_mode == "percent":
                percent_drop = ((old_price - new_price) / old_price) * 100
                notifications["price_drop"] = percent_drop >= product.notify_value
            
            elif product.notify_mode == "threshold":
                notifications["price_drop"] = new_price <= product.notify_value
            
            else:
                # Уведомлять о любом снижении
                notifications["price_drop"] = True
        
        # Проверка наличия (только для basic/pro)
        user_plan = user.get("plan", "plan_free") if user else "plan_free"
        
        if user_plan in ["plan_basic", "plan_pro"]:
            # Товар закончился
            if old_qty is not None and old_qty > 0 and new_qty == 0:
                notifications["stock_out"] = True
            
            # Товар появился
            if old_qty is not None and old_qty == 0 and new_qty > 0:
                notifications["stock_in"] = True
        
        return notifications
    
    async def _save_product_data(
        self,
        product_id: int,
        price_data: Dict
    ) -> None:
        """Сохранить новые данные о товаре."""
        
        # ✅ ДОБАВИТЬ: Не сохраняем нулевую цену если товара нет
        if price_data['out_of_stock']:
            # Получаем текущий товар
            product = await self.product_repo.get_by_id(product_id)
            
            # Сохраняем старую цену или оставляем как есть
            if product and product.get('last_product_price'):
                price_data['product_price'] = product['last_product_price']
                price_data['basic_price'] = product.get('last_basic_price', price_data['basic_price'])
        
        await self.product_repo.update_prices(
            product_id,
            price_data['basic_price'],
            price_data['product_price'],
            price_data['qty'],
            price_data['out_of_stock']
        )
        
        # ✅ ИЗМЕНИТЬ: Не добавляем в историю если товара нет и цена не изменилась
        product = await self.product_repo.get_by_id(product_id)
        if product:
            should_save_history = (
                not price_data['out_of_stock'] and  # Товар в наличии
                (product.get('last_product_price') is None or 
                price_data['product_price'] != product['last_product_price'])
            )
            
            if should_save_history:
                await self.price_history_repo.add(
                    product_id,
                    price_data['basic_price'],
                    price_data['product_price'],
                    price_data['qty']
                )
            
            product_cache.remove(f"get_product_detail:{product_id}")

    async def _send_notifications(
        self,
        product: ProductRow,
        notifications: Dict[str, bool],
        price_data: Dict,
        user: Optional[Dict]
    ) -> None:
        """Сформировать и отправить уведомления."""
        message = ""
        
        # Уведомление о снижении цены
        if notifications["price_drop"]:
            message += self._format_price_drop_message(
                product,
                price_data,
                user
            )
        
        # Уведомление о наличии
        if notifications["stock_out"]:
            message += self._format_stock_out_message(product)
        
        if notifications["stock_in"]:
            message += self._format_stock_in_message(
                product,
                price_data,
                user
            )
        
        if message:
            await self._send_telegram_message(product.user_id, message)
    
    def _format_price_drop_message(
        self,
        product: ProductRow,
        price_data: Dict,
        user: Optional[Dict]
    ) -> str:
        """Форматировать сообщение о снижении цены."""
        discount = user.get("discount_percent", 0) if user else 0
        
        old_price = product.last_product_price
        new_price = price_data['product_price']
        
        # Применяем скидку если есть
        if discount > 0:
            old_display = apply_wallet_discount(old_price, discount)
            new_display = apply_wallet_discount(new_price, discount)
        else:
            old_display = old_price
            new_display = new_price
        
        diff = old_display - new_display
        diff_percent = (diff / old_display * 100) if old_display > 0 else 0
        
        message = (
            f"🔔 <b>Цена снизилась!</b>\n\n"
            f"📦 {product.display_name}\n"
            f"🔗 <a href='{product.url_product}'>Открыть товар</a>\n\n"
        )
        
        if discount > 0:
            message += (
                f"💳 <b>Цена с WB кошельком ({discount}%):</b>\n"
                f"✅ <b>Сейчас:</b> {new_display} ₽\n"
                f"📉 <b>Было:</b> {old_display} ₽\n"
                f"💰 <b>Экономия:</b> {diff} ₽ ({diff_percent:.1f}%)\n\n"
                f"<i>Без кошелька: {new_price} ₽ (было {old_price} ₽)</i>\n"
            )
        else:
            message += (
                f"💰 <b>Новая цена:</b> {new_display} ₽\n"
                f"📉 <b>Было:</b> {old_display} ₽\n"
                f"✅ <b>Экономия:</b> {diff} ₽ ({diff_percent:.1f}%)\n"
            )
        
        return message
    
    def _format_stock_out_message(self, product: ProductRow) -> str:
        """Форматировать сообщение о том что товар закончился."""
        return (
            f"\n⚠️ <b>Товар закончился!</b>\n\n"
            f"📦 {product.display_name}\n"
            f"🔗 <a href='{product.url_product}'>Открыть товар</a>\n"
        )
    
    def _format_stock_in_message(
        self,
        product: ProductRow,
        price_data: Dict,
        user: Optional[Dict]
    ) -> str:
        """Форматировать сообщение о появлении товара."""
        user_plan = user.get("plan", "plan_free") if user else "plan_free"
        qty = price_data['qty']
        
        message = (
            f"\n✅ <b>Товар снова в наличии!</b>\n\n"
            f"📦 {product.display_name}\n"
            f"🔗 <a href='{product.url_product}'>Открыть товар</a>\n"
        )
        
        # Показываем количество только для Pro
        if user_plan == "plan_pro" and qty:
            message += f"📦 <b>Остаток:</b> {qty} шт.\n"
        
        return message
    
    async def _send_telegram_message(
        self,
        user_id: int,
        message: str
    ) -> None:
        """Отправить сообщение в Telegram с обработкой ошибок."""
        try:
            await self.bot.send_message(
                user_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            logger.info(f"Отправлено уведомление пользователю {user_id}")
            
        except exceptions.TelegramForbiddenError:
            logger.warning(f"Пользователь {user_id} заблокировал бота")
            
        except exceptions.TelegramBadRequest as e:
            logger.warning(
                f"Ошибка отправки пользователю {user_id}: {e}"
            )
            
        except Exception as e:
            logger.exception(
                f"Неожиданная ошибка при отправке уведомления: {e}"
            )
    
    async def process_batch(
        self,
        products: list[ProductRow],
        batch_size: int = 50,
        delay_between_batches: float = 1.0
    ) -> Dict[str, int]:
        """
        Обработать список товаров пакетами.
        
        Args:
            products: Список товаров
            batch_size: Размер пакета
            delay_between_batches: Задержка между пакетами (секунды)
        
        Returns:
            Dict с метриками: processed, errors, notifications
        """
        metrics = {"processed": 0, "errors": 0, "notifications": 0}
        
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            
            tasks = [
                asyncio.create_task(self.process_product(p, metrics))
                for p in batch
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Задержка между пакетами (кроме последнего)
            if i + batch_size < len(products):
                await asyncio.sleep(delay_between_batches)
        
        return metrics
