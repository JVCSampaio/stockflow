from typing import Literal

from pydantic import BaseModel


class ProductView(BaseModel):
    id: int
    sku: str
    name: str
    category: str
    unit_cost_cents: int
    reorder_point: int
    quantity: int
    created_at: str
    low_stock: bool


class ProductList(BaseModel):
    items: list[ProductView]
    total: int
    limit: int
    offset: int


class MovementView(BaseModel):
    id: int
    product_id: int
    kind: Literal["in", "out"]
    quantity: int
    unit_cost_cents: int
    balance_after: int
    note: str
    idempotency_key: str
    created_at: str


class MovementWithProduct(MovementView):
    sku: str
    name: str


class MovementList(BaseModel):
    items: list[MovementWithProduct]
    total: int
    limit: int
    offset: int


class MetricsView(BaseModel):
    products: int
    units: int
    value_cents: int
    low_stock: int
    empty: int
