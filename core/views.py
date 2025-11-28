"""
Views / Response Models
Плоские модели данных для передачи в хендлеры и UI.
Не содержат бизнес-логики.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

from entities import User, Product, PriceHistory


@dataclass
class UserView:
    id: int
    plan_name: str
    is_premium: bool
    discount_percent: int
    max_links: int
    pvz_display: str
    sort_mode: str
    created_at: Optional[datetime]

    @classmethod
    def from_entity(cls, user: User) -> "UserView":
        """
        Создание View-модели из доменной сущности.
        Используется в сервисах перед отдачей в хендлер.
        """
        return cls(
            id=user.id,
            plan_name=user.plan_name,
            is_premium=user.is_premium,
            discount_percent=user.discount_percent,
            max_links=user.max_links,
            pvz_display=user.get_pvz_display(),
            sort_mode=user.sort_mode.value,
            created_at=user.created_at
        )


@dataclass
class ProductView:
    id: int
    user_id: int
    display_name: str
    url: str
    nm_id: int
    selected_size: Optional[str]
    notify_mode: str
    notify_value: Optional[int]
    last_basic_price: Optional[int]
    last_product_price: Optional[int]
    last_qty: int
    is_available: bool
    out_of_stock: bool
    updated_at: datetime

    @classmethod
    def from_entity(cls, product: Product) -> "ProductView":
        return cls(
            id=product.id,
            user_id=product.user_id,
            display_name=product.display_name,
            url=product.url,
            nm_id=product.nm_id,
            selected_size=product.selected_size,
            notify_mode=product.notify_mode.value,
            notify_value=product.notify_value,
            last_basic_price=product.last_basic_price,
            last_product_price=product.last_product_price,
            last_qty=product.last_qty,
            is_available=product.is_available,
            out_of_stock=product.out_of_stock,
            updated_at=product.updated_at,
        )


@dataclass
class PriceHistoryView:
    id: int
    product_id: int
    basic_price: int
    product_price: int
    qty: int
    recorded_at: datetime

    @classmethod
    def from_entity(cls, entry: PriceHistory) -> "PriceHistoryView":
        return cls(
            id=entry.id,
            product_id=entry.product_id,
            basic_price=entry.basic_price,
            product_price=entry.product_price,
            qty=entry.qty,
            recorded_at=entry.recorded_at,
        )


@dataclass
class ProductListView:
    """
    View-модель списка товаров.
    """
    total: int
    items: List[ProductView]

    @classmethod
    def from_entities(cls, products: list[Product]) -> "ProductListView":
        return cls(
            total=len(products),
            items=[ProductView.from_entity(p) for p in products]
        )
