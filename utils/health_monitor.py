"""
Комплексная система мониторинга здоровья бота.
"""
import asyncio
import logging
import psutil
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Статусы здоровья компонентов."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthMetric:
    """Метрика здоровья."""
    name: str
    status: HealthStatus
    value: float
    threshold: float
    message: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class HealthMonitor:
    """
    Мониторинг здоровья всех компонентов бота.
    
    Отслеживает:
    - Производительность системы (CPU, RAM, disk)
    - Состояние БД (количество соединений, время отклика)
    - Качество работы с API WB
    - Скорость обработки товаров
    - Задержки в очереди уведомлений
    """
    
    def __init__(self):
        self.metrics_history: List[HealthMetric] = []
        self.alert_callbacks: List[callable] = []
        
        # Пороги
        self.cpu_threshold_warning = 70.0  # %
        self.cpu_threshold_critical = 90.0
        self.ram_threshold_warning = 80.0
        self.ram_threshold_critical = 95.0
        self.disk_threshold_warning = 85.0
        self.disk_threshold_critical = 95.0
        
        # Время последних проверок
        self.last_db_check = None
        self.last_system_check = None
        
        # Счётчики для мониторинга производительности
        self.products_processed_today = 0
        self.notifications_sent_today = 0
        self.errors_today = 0
        self.last_reset_date = datetime.now().date()
    
    def register_alert_callback(self, callback: callable):
        """Зарегистрировать callback для алертов."""
        self.alert_callbacks.append(callback)
    
    def reset_daily_counters(self):
        """Сброс ежедневных счётчиков."""
        today = datetime.now().date()
        if today > self.last_reset_date:
            logger.info("Сброс ежедневных счётчиков")
            self.products_processed_today = 0
            self.notifications_sent_today = 0
            self.errors_today = 0
            self.last_reset_date = today
    
    async def check_system_health(self) -> List[HealthMetric]:
        """Проверка здоровья системы (CPU, RAM, Disk)."""
        metrics = []
        
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = HealthStatus.HEALTHY
            if cpu_percent >= self.cpu_threshold_critical:
                cpu_status = HealthStatus.CRITICAL
            elif cpu_percent >= self.cpu_threshold_warning:
                cpu_status = HealthStatus.DEGRADED
            
            metrics.append(HealthMetric(
                name="cpu_usage",
                status=cpu_status,
                value=cpu_percent,
                threshold=self.cpu_threshold_warning,
                message=f"CPU: {cpu_percent:.1f}%"
            ))
            
            # RAM
            ram = psutil.virtual_memory()
            ram_status = HealthStatus.HEALTHY
            if ram.percent >= self.ram_threshold_critical:
                ram_status = HealthStatus.CRITICAL
            elif ram.percent >= self.ram_threshold_warning:
                ram_status = HealthStatus.DEGRADED
            
            metrics.append(HealthMetric(
                name="ram_usage",
                status=ram_status,
                value=ram.percent,
                threshold=self.ram_threshold_warning,
                message=f"RAM: {ram.percent:.1f}% ({ram.used / 1024**3:.1f}GB / {ram.total / 1024**3:.1f}GB)"
            ))
            
            # Disk
            disk = psutil.disk_usage('/')
            disk_status = HealthStatus.HEALTHY
            if disk.percent >= self.disk_threshold_critical:
                disk_status = HealthStatus.CRITICAL
            elif disk.percent >= self.disk_threshold_warning:
                disk_status = HealthStatus.DEGRADED
            
            metrics.append(HealthMetric(
                name="disk_usage",
                status=disk_status,
                value=disk.percent,
                threshold=self.disk_threshold_warning,
                message=f"Disk: {disk.percent:.1f}% ({disk.used / 1024**3:.1f}GB / {disk.total / 1024**3:.1f}GB)"
            ))
            
            self.last_system_check = datetime.now()
            
        except Exception as e:
            logger.exception(f"Ошибка при проверке системы: {e}")
            metrics.append(HealthMetric(
                name="system_check",
                status=HealthStatus.UNKNOWN,
                value=0,
                threshold=0,
                message=f"Ошибка проверки: {str(e)}"
            ))
        
        return metrics
    
    async def check_database_health(self, db) -> HealthMetric:
        """Проверка здоровья БД."""
        try:
            start_time = time.time()
            
            # Простой запрос для проверки подключения
            async with db.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
            response_time = (time.time() - start_time) * 1000  # ms
            
            # Определяем статус по времени отклика
            status = HealthStatus.HEALTHY
            if response_time > 1000:  # > 1 секунды
                status = HealthStatus.CRITICAL
            elif response_time > 500:  # > 500ms
                status = HealthStatus.DEGRADED
            
            self.last_db_check = datetime.now()
            
            return HealthMetric(
                name="database",
                status=status,
                value=response_time,
                threshold=500,
                message=f"DB отклик: {response_time:.0f}ms"
            )
            
        except Exception as e:
            logger.exception(f"Ошибка при проверке БД: {e}")
            return HealthMetric(
                name="database",
                status=HealthStatus.CRITICAL,
                value=0,
                threshold=0,
                message=f"DB недоступна: {str(e)}"
            )
    
    async def check_monitoring_lag(self, db) -> HealthMetric:
        """Проверка задержки мониторинга товаров."""
        try:
            # Получаем товар с самым старым updated_at
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT updated_at FROM products ORDER BY updated_at ASC LIMIT 1"
                )
            
            if not row:
                return HealthMetric(
                    name="monitoring_lag",
                    status=HealthStatus.HEALTHY,
                    value=0,
                    threshold=0,
                    message="Нет товаров для мониторинга"
                )
            
            last_update = row['updated_at']
            lag_minutes = (datetime.now(last_update.tzinfo) - last_update).total_seconds() / 60
            
            # Определяем статус
            status = HealthStatus.HEALTHY
            if lag_minutes > 60:  # > 1 часа
                status = HealthStatus.CRITICAL
            elif lag_minutes > 30:  # > 30 минут
                status = HealthStatus.DEGRADED
            
            return HealthMetric(
                name="monitoring_lag",
                status=status,
                value=lag_minutes,
                threshold=30,
                message=f"Задержка мониторинга: {lag_minutes:.0f} минут"
            )
            
        except Exception as e:
            logger.exception(f"Ошибка при проверке лага: {e}")
            return HealthMetric(
                name="monitoring_lag",
                status=HealthStatus.UNKNOWN,
                value=0,
                threshold=0,
                message=f"Ошибка: {str(e)}"
            )
    
    async def perform_full_check(self, db) -> Dict:
        """Полная проверка здоровья."""
        self.reset_daily_counters()
        
        # Собираем все метрики
        system_metrics = await self.check_system_health()
        db_metric = await self.check_database_health(db)
        lag_metric = await self.check_monitoring_lag(db)
        
        all_metrics = system_metrics + [db_metric, lag_metric]
        
        # Определяем общий статус
        critical_count = sum(1 for m in all_metrics if m.status == HealthStatus.CRITICAL)
        degraded_count = sum(1 for m in all_metrics if m.status == HealthStatus.DEGRADED)
        
        overall_status = HealthStatus.HEALTHY
        if critical_count > 0:
            overall_status = HealthStatus.CRITICAL
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        
        # Сохраняем в историю
        self.metrics_history.extend(all_metrics)
        
        # Ограничиваем размер истории
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-500:]
        
        result = {
            "timestamp": datetime.now(),
            "overall_status": overall_status,
            "metrics": all_metrics,
            "daily_stats": {
                "products_processed": self.products_processed_today,
                "notifications_sent": self.notifications_sent_today,
                "errors": self.errors_today
            }
        }
        
        # Проверяем нужен ли алерт
        if overall_status in [HealthStatus.CRITICAL, HealthStatus.DEGRADED]:
            await self._send_health_alert(result)
        
        return result
    
    async def _send_health_alert(self, health_data: Dict):
        """Отправка алерта о проблемах со здоровьем."""
        status = health_data['overall_status']
        icon = "🚨" if status == HealthStatus.CRITICAL else "⚠️"
        
        message = f"{icon} <b>Проблемы со здоровьем бота</b>\n\n"
        
        # Проблемные метрики
        problem_metrics = [
            m for m in health_data['metrics']
            if m.status in [HealthStatus.CRITICAL, HealthStatus.DEGRADED]
        ]
        
        if problem_metrics:
            message += "📊 <b>Проблемные компоненты:</b>\n"
            for metric in problem_metrics:
                status_icon = "🚨" if metric.status == HealthStatus.CRITICAL else "⚠️"
                message += f"{status_icon} {metric.message}\n"
            message += "\n"
        
        # Ежедневная статистика
        stats = health_data['daily_stats']
        message += (
            f"📈 <b>Сегодня:</b>\n"
            f"• Обработано товаров: {stats['products_processed']}\n"
            f"• Отправлено уведомлений: {stats['notifications_sent']}\n"
            f"• Ошибок: {stats['errors']}\n"
        )
        
        # Вызываем callbacks
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback({"message": message, "data": health_data})
                else:
                    callback({"message": message, "data": health_data})
            except Exception as e:
                logger.exception(f"Error in health alert callback: {e}")
    
    def format_status_message(self, health_data: Dict) -> str:
        """Форматировать сообщение о статусе для команды /health."""
        status = health_data['overall_status']
        
        if status == HealthStatus.HEALTHY:
            icon = "✅"
            status_text = "ЗДОРОВ"
        elif status == HealthStatus.DEGRADED:
            icon = "⚠️"
            status_text = "ДЕГРАДАЦИЯ"
        else:
            icon = "🚨"
            status_text = "КРИТИЧЕСКИЙ"
        
        message = f"{icon} <b>Статус: {status_text}</b>\n\n"
        
        # Все метрики
        message += "📊 <b>Компоненты:</b>\n"
        for metric in health_data['metrics']:
            if metric.status == HealthStatus.HEALTHY:
                icon = "✅"
            elif metric.status == HealthStatus.DEGRADED:
                icon = "⚠️"
            elif metric.status == HealthStatus.CRITICAL:
                icon = "🚨"
            else:
                icon = "❓"
            
            message += f"{icon} {metric.message}\n"
        
        message += "\n"
        
        # Статистика
        stats = health_data['daily_stats']
        message += (
            f"📈 <b>Статистика за сегодня:</b>\n"
            f"• Обработано: {stats['products_processed']} товаров\n"
            f"• Уведомлений: {stats['notifications_sent']}\n"
            f"• Ошибок: {stats['errors']}\n\n"
        )
        
        message += f"🕐 Проверено: {health_data['timestamp'].strftime('%H:%M:%S')}"
        
        return message


# Глобальный монитор
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Получить глобальный экземпляр монитора."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor
