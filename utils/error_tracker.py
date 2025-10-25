"""
Система отслеживания и анализа ошибок API Wildberries.
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Типы ошибок API."""
    HTTP_403 = "403_forbidden"
    HTTP_429 = "429_rate_limit"
    HTTP_5XX = "5xx_server_error"
    TIMEOUT = "timeout"
    CONNECTION = "connection_error"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"


@dataclass
class ErrorEvent:
    """Событие ошибки."""
    timestamp: datetime
    error_type: ErrorType
    nm_id: Optional[int] = None
    details: Optional[str] = None


class ErrorTracker:
    """
    Трекер ошибок с автоматическими алертами.
    
    Отслеживает:
    - Частоту ошибок (общую и по типам)
    - Критические пороги
    - Тренды
    """
    
    def __init__(
        self,
        window_minutes: int = 60,
        error_threshold_percent: float = 5.0,
        critical_threshold_percent: float = 10.0,
        min_requests_for_alert: int = 50
    ):
        """
        Args:
            window_minutes: Окно анализа в минутах
            error_threshold_percent: Порог для warning (%)
            critical_threshold_percent: Порог для critical alert (%)
            min_requests_for_alert: Минимум запросов для срабатывания алерта
        """
        self.window = timedelta(minutes=window_minutes)
        self.error_threshold = error_threshold_percent
        self.critical_threshold = critical_threshold_percent
        self.min_requests = min_requests_for_alert
        
        # Хранилище событий (deque для эффективного удаления старых)
        self.errors: deque[ErrorEvent] = deque(maxlen=10000)
        self.successes: deque[datetime] = deque(maxlen=10000)
        
        # Статистика по типам ошибок
        self.error_counts: Dict[ErrorType, int] = {et: 0 for et in ErrorType}
        
        # Для предотвращения спама алертов
        self.last_alert_time: Optional[datetime] = None
        self.alert_cooldown = timedelta(minutes=15)
        
        # Callbacks для алертов
        self.alert_callbacks: List[callable] = []
    
    def register_alert_callback(self, callback: callable):
        """Зарегистрировать функцию для отправки алертов."""
        self.alert_callbacks.append(callback)
    
    def track_success(self):
        """Отметить успешный запрос."""
        self.successes.append(datetime.now())
    
    def track_error(
        self,
        error_type: ErrorType,
        nm_id: Optional[int] = None,
        details: Optional[str] = None
    ):
        """Отметить ошибку."""
        event = ErrorEvent(
            timestamp=datetime.now(),
            error_type=error_type,
            nm_id=nm_id,
            details=details
        )
        self.errors.append(event)
        self.error_counts[error_type] += 1
        
        logger.warning(
            f"API Error tracked: {error_type.value} "
            f"(nm_id={nm_id}, details={details})"
        )
    
    def _cleanup_old_events(self):
        """Удалить события старше окна анализа."""
        cutoff = datetime.now() - self.window
        
        # Очистка ошибок
        while self.errors and self.errors[0].timestamp < cutoff:
            old_event = self.errors.popleft()
            self.error_counts[old_event.error_type] -= 1
        
        # Очистка успехов
        while self.successes and self.successes[0] < cutoff:
            self.successes.popleft()
    
    def get_statistics(self) -> Dict:
        """Получить текущую статистику."""
        self._cleanup_old_events()
        
        total_errors = len(self.errors)
        total_successes = len(self.successes)
        total_requests = total_errors + total_successes
        
        error_rate = (
            (total_errors / total_requests * 100)
            if total_requests > 0 else 0
        )
        
        # Статистика по типам
        error_breakdown = {
            et.value: count
            for et, count in self.error_counts.items()
            if count > 0
        }
        
        return {
            "window_minutes": self.window.total_seconds() / 60,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "total_successes": total_successes,
            "error_rate_percent": round(error_rate, 2),
            "error_breakdown": error_breakdown,
            "is_healthy": error_rate < self.error_threshold,
            "is_critical": error_rate >= self.critical_threshold
        }
    
    async def check_and_alert(self) -> Optional[Dict]:
        """
        Проверить метрики и отправить алерт если нужно.
        
        Returns:
            Dict с информацией об алерте или None
        """
        stats = self.get_statistics()
        
        # Проверяем минимальное количество запросов
        if stats['total_requests'] < self.min_requests:
            return None
        
        # Проверяем cooldown
        now = datetime.now()
        if (self.last_alert_time and 
            now - self.last_alert_time < self.alert_cooldown):
            return None
        
        # Определяем severity
        severity = None
        if stats['is_critical']:
            severity = "CRITICAL"
        elif not stats['is_healthy']:
            severity = "WARNING"
        
        if severity:
            self.last_alert_time = now
            
            alert_data = {
                "severity": severity,
                "timestamp": now,
                "statistics": stats,
                "message": self._format_alert_message(severity, stats)
            }
            
            # Вызываем callbacks
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert_data)
                    else:
                        callback(alert_data)
                except Exception as e:
                    logger.exception(f"Error in alert callback: {e}")
            
            return alert_data
        
        return None
    
    def _format_alert_message(self, severity: str, stats: Dict) -> str:
        """Форматировать сообщение алерта."""
        icon = "🚨" if severity == "CRITICAL" else "⚠️"
        
        message = (
            f"{icon} <b>{severity}: Проблемы с API Wildberries</b>\n\n"
            f"📊 <b>Статистика за {stats['window_minutes']:.0f} минут:</b>\n"
            f"• Всего запросов: {stats['total_requests']}\n"
            f"• Ошибок: {stats['total_errors']}\n"
            f"• Процент ошибок: <b>{stats['error_rate_percent']}%</b>\n\n"
        )
        
        if stats['error_breakdown']:
            message += "📋 <b>Типы ошибок:</b>\n"
            for error_type, count in stats['error_breakdown'].items():
                message += f"• {error_type}: {count}\n"
            message += "\n"
        
        if severity == "CRITICAL":
            message += (
                "⚠️ <b>Действия:</b>\n"
                "• Проверьте статус API WB\n"
                "• Возможно, нужно увеличить задержки\n"
                "• Рассмотрите использование прокси\n"
            )
        else:
            message += "💡 Мониторим ситуацию..."
        
        return message


# Глобальный трекер
_error_tracker: Optional[ErrorTracker] = None


def get_error_tracker() -> ErrorTracker:
    """Получить глобальный экземпляр трекера."""
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker(
            window_minutes=60,
            error_threshold_percent=5.0,
            critical_threshold_percent=10.0,
            min_requests_for_alert=50
        )
    return _error_tracker
