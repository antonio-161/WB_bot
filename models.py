from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProductRow(BaseModel):
    """Модель продукта."""
    id: int
    user_id: int
    url_product: str
    nm_id: int
    name_product: str
    custom_name: Optional[str] = None
    selected_size: Optional[str] = None
    notify_mode: Optional[str] = None
    notify_value: Optional[int] = None
    last_basic_price: Optional[int] = None
    last_product_price: Optional[int] = None
    last_qty: Optional[int] = None
    out_of_stock: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def display_name(self) -> str:
        """Возвращает пользовательское имя или оригинальное."""
        return self.custom_name or self.name_product


class PriceHistoryRow(BaseModel):
    """Модель записи истории цен."""
    id: int
    product_id: int
    basic_price: int
    product_price: int
    qty: int
    recorded_at: datetime
