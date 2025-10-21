"""Простой кэш для данных о товарах."""
import time
from typing import Optional, Dict


class SimpleCache:
    """In-memory кэш с TTL."""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, tuple] = {}
        self._ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[any]:
        """Получить значение из кэша."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: any):
        """Сохранить значение в кэш."""
        self._cache[key] = (value, time.time())
    
    def clear(self):
        """Очистить весь кэш."""
        self._cache.clear()
    
    def remove(self, key: str):
        """Удалить ключ из кэша."""
        if key in self._cache:
            del self._cache[key]


# Глобальный кэш
product_cache = SimpleCache(ttl_seconds=300)  # 5 минут
