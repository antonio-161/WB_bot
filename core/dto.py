from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# ==============================
# DTO — Data Transfer Objects
# Используются ИСКЛЮЧИТЕЛЬНО для слоя Infrastructure
# ==============================


@dataclass
class UserDTO:
    id: int
    plan: str
    plan_name: str
    discount_percent: int
    max_links: int
    dest: int
    pvz_address: Optional[str]
    sort_mode: str
    created_at: datetime


@dataclass
class ProductDTO:
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
    id: int
    product_id: int
    basic_price: int
    product_price: int
    qty: int
    recorded_at: datetime
