"""Улучшенная система кэширования с декоратором."""
import time
import hashlib
import json
import functools
from typing import Optional, Dict, Callable


class SimpleCache:
    """In-memory кэш с TTL."""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, tuple] = {}
        self._ttl: int = ttl_seconds
    
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
    
    def get_stats(self) -> Dict:
        """Получить статистику кэша."""
        return {
            "total_keys": len(self._cache),
            "size_bytes": sum(
                len(str(k)) + len(str(v[0])) 
                for k, v in self._cache.items()
            )
        }


def make_cache_key(*args, **kwargs) -> str:
    """
    Создать уникальный ключ кэша из аргументов.
    
    Примеры:
        make_cache_key(123, "test", foo="bar") 
        -> "d41d8cd98f00b204e9800998ecf8427e"
    """
    # Сериализуем аргументы
    key_data = {
        "args": args,
        "kwargs": kwargs
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    
    # Хешируем для компактности
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(ttl: int = 300, cache_instance: Optional[SimpleCache] = None):
    """
    Декоратор для кэширования результатов функций.
    
    Args:
        ttl: Время жизни кэша в секундах
        cache_instance: Экземпляр кэша (если None, создаётся новый)
    
    Usage:
        @cached(ttl=600)
        async def get_product_data(nm_id: int):
            return await fetch_data(nm_id)
    """
    if cache_instance is None:
        cache_instance = SimpleCache(ttl_seconds=ttl)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Создаём ключ кэша
            cache_key = f"{func.__name__}:{make_cache_key(*args, **kwargs)}"
            
            # Проверяем кэш
            cached_value = cache_instance.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Вызываем функцию
            result = await func(*args, **kwargs)
            
            # Сохраняем в кэш
            if result is not None:
                cache_instance.set(cache_key, result)
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{make_cache_key(*args, **kwargs)}"
            
            cached_value = cache_instance.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            result = func(*args, **kwargs)
            
            if result is not None:
                cache_instance.set(cache_key, result)
            
            return result
        
        # Возвращаем правильную обёртку
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Глобальные кэши для разных целей
product_cache = SimpleCache(ttl_seconds=300)  # 5 минут для товаров
user_cache = SimpleCache(ttl_seconds=600)     # 10 минут для пользователей
settings_cache = SimpleCache(ttl_seconds=300) # 5 минут для настроек
