# services.py
from typing import Dict, Optional
from models import IngredientDefinition
from models import OrderResponse, OrderItem
from constants import ONE_DAY


# PricingService
class PricingService:
    def __init__(self, ingredients: Dict[str, IngredientDefinition], clock):
        self._ingredients = ingredients
        self._clock = clock

    def get_price(
        self, ingredient_id: str, quantity: float
    ) -> Optional[Dict[str, any]]:
        ing = self._ingredients.get(ingredient_id)
        if not ing:
            return None

        now = self._clock.now()
        return {
            "price_per_unit": ing.base_price,
            "price_valid_until": now + ONE_DAY,
        }


# InventoryService
class InventoryService:
    def __init__(self, ingredients: Dict[str, IngredientDefinition]):
        self._ingredients = ingredients

    def get_stock(self, ingredient_id: str) -> Optional[float]:
        ing = self._ingredients.get(ingredient_id)
        return ing.stock if ing else None

    def consume_stock(self, ingredient_id: str, quantity: float) -> bool:
        ing = self._ingredients.get(ingredient_id)
        if not ing:
            return False
        if ing.stock < quantity:
            return False
        ing.stock -= quantity
        return True

    def get_use_by_date(self, ingredient_id: str) -> Optional[int]:
        ing = self._ingredients.get(ingredient_id)
        return ing.use_by_date if ing else None


# OrderService
class OrderService:
    def __init__(self, clock):
        self._orders: Dict[str, OrderResponse] = {}
        self._clock = clock

    def create_order(
        self,
        business_id: Optional[str],
        item: OrderItem,
        expected_delivery: int,
        status: str,
        failure_reason: Optional[str] = None,
    ) -> OrderResponse:
        import uuid

        order_id = str(uuid.uuid4())
        now = self._clock.now()
        total_cost = item.total_price if status == "CONFIRMED" else 0.0
        order = OrderResponse(
            order_id=order_id,
            business_id=business_id,
            items={item.ingredient_id: item},
            total_cost=total_cost,
            order_placed_at=now,
            expected_delivery=expected_delivery,
            status=status,
            failure_reason=failure_reason,
        )
        self._orders[order_id] = order
        return order

    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        return self._orders.get(order_id)
