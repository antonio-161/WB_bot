from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# ==============================
# Domain Entities — бизнес-сущности
# Используются в домене и аппликационном слое
# ==============================


@dataclass
class UserData:
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
class ProductData:
    id: int
    user_id: int
    url: str
    nm_id: int
    name: str
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
class PriceHistoryData:
    id: int
    product_id: int
    basic_price: int
    product_price: int
    qty: int
    recorded_at: datetime
