"""
DTO (Data Transfer Objects) -
чистые структуры данных для передачи между слоями.
Используются ТОЛЬКО в infrastructure слое для маппинга из/в БД.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class UserDTO:
    """DTO для пользователя - только данные из БД."""
    id: int
    plan: str
    discount_percent: int
    max_links: int
    dest: int
    pvz_address: Optional[str]
    sort_mode: str
    created_at: datetime


@dataclass
class ProductDTO:
    """DTO для товара - только данные из БД."""
    id: int
    user_id: int
    url_product: str
    nm_id: int
    name_product: str
    custom_name: Optional[str]
    last_basic_price: Optional[int]
    last_product_price: Optional[int]
    selected_size: Optional[str]
    notify_mode: Optional[str]
    notify_value: Optional[int]
    last_qty: int
    out_of_stock: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class PriceHistoryDTO:
    """DTO для истории цен - только данные из БД."""
    id: int
    product_id: int
    basic_price: int
    product_price: int
    qty: int
    recorded_at: datetime
