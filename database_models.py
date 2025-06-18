from typing import Optional, Dict
from sqlmodel import SQLModel, Field, Column, JSON, Index

class Quote(SQLModel, table=True):
    """
    Stores each generated quote and its metadata. Time fields use integer timestamps.
    """
    __tablename__ = "quotes"

    quote_id: str = Field(default=None, primary_key=True)
    ingredient_id: str = Field(index=True, nullable=False)
    name: str
    description: str
    unit_of_measure: str
    price_per_unit: float
    total_price: float
    currency: str
    available_stock: float
    use_by_date: int  # integer timestamp
    price_valid_until: int  # integer timestamp
    delivery_time: int
    created_at: int = Field(
        default=0,
        nullable=False,
        index=True,
        description="Integer timestamp when quote was created"
    )

    __table_args__ = (
        Index("ix_quotes_ingredient_created", "ingredient_id", "created_at"),
    )

class Order(SQLModel, table=True):
    """
    Persists each order, optionally linked to a quote.
    Time fields use integer timestamps.
    """
    __tablename__ = "orders"

    order_id: str = Field(default=None, primary_key=True)
    business_id: Optional[str] = Field(index=True, nullable=True)
    quote_id: Optional[str] = Field(
        foreign_key="quotes.quote_id",
        index=True,
        nullable=True
    )
    items: Dict[str, Dict] = Field(
        sa_column=Column(JSON),
        description="Mapping of ingredient_id → OrderItem dict"
    )
    total_cost: float
    order_placed_at: int = Field(
        default=0,
        nullable=False,
        description="Integer timestamp when order was placed"
    )
    expected_delivery: int  # integer timestamp
    status: str
    failure_reason: Optional[str] = None
