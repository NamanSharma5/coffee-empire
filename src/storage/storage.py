# storage.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, List
from src.models.api_models import OrderResponse, QuoteResponse
from src.models.database_models import Order as OrderORM, Quote as QuoteORM
from sqlmodel import Session, select
import json, uuid

class AbstractStorage(ABC):
    @abstractmethod
    def save_order(self, order: OrderResponse) -> None:
        pass
    @abstractmethod
    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        pass
    @abstractmethod
    def get_orders_by_business_id(self, business_id: str) -> List[OrderResponse]:
        pass
    @abstractmethod
    def save_quote(self, quote: QuoteResponse) -> None:
        pass

# ------------------------------------------------------------------
class InMemoryStorage(AbstractStorage):
    def __init__(self) -> None:
        self._orders: Dict[str, OrderResponse] = {}
        self._quote_store: Dict[str, QuoteResponse] = {}

    def save_order(self, order: OrderResponse) -> None:
        self._orders[order.order_id] = order

    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        return self._orders.get(order_id)

    def get_orders_by_business_id(self, business_id: str) -> List[OrderResponse]:
        return [order for order in self._orders.values() if order.business_id == business_id]

    def save_quote(self, quote: QuoteResponse) -> None:
        self._quote_store[quote.quote_id] = quote

# ------------------------------------------------------------------
class SqlStorage(AbstractStorage):
    def __init__(self, session: Session):
        self._session = session

    def save_order(self, order: OrderResponse) -> None:
        orm = OrderORM(
            order_id=order.order_id,
            business_id=order.business_id,
            quote_id=order.quote_id,
            items=json.loads(order.json(include={"items"}))["items"],
            total_cost=order.total_cost,
            order_placed_at=order.order_placed_at,
            expected_delivery=order.expected_delivery,
            status=order.status,
            failure_reason=order.failure_reason,
        )
        self._session.add(orm)
        self._session.commit()

    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        orm = self._session.get(OrderORM, order_id)
        return OrderResponse(**orm.dict()) if orm else None

    def get_orders_by_business_id(self, business_id: str) -> List[OrderResponse]:
        statement = select(OrderORM).where(OrderORM.business_id == business_id)
        orms = self._session.exec(statement).all()
        return [OrderResponse(**orm.dict()) for orm in orms]

    def save_quote(self, quote: QuoteResponse) -> None:
        orm = QuoteORM(
            quote_id=quote.quote_id,
            ingredient_id=quote.ingredient_id,
            name=quote.name,
            description=quote.description,
            unit_of_measure=quote.unit_of_measure,
            price_per_unit=quote.price_per_unit,
            total_price=quote.total_price,
            currency=quote.currency,
            available_stock=quote.available_stock,
            use_by_date=quote.use_by_date,
            price_valid_until=quote.price_valid_until,
            delivery_time=quote.delivery_time,
            created_at=quote.price_valid_until,  # You may want to use a real timestamp here
        )
        self._session.add(orm)
        self._session.commit()
