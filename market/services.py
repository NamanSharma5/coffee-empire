# services.py
from typing import Dict, Optional, Tuple, List
from models import IngredientDefinition
from models import OrderResponse, OrderItem
from constants import ONE_DAY
from abc import ABC, abstractmethod


# Abstract base class for PricingService
class PricingService(ABC):
    @abstractmethod
    def get_price(
        self, ingredient_id: str, quantity: float
    ) -> Optional[Dict[str, any]]:
        pass

class DefaultPricingService(PricingService):
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


class VolumeDiscountPricingService(PricingService):
    """
    PricingService that applies tiered discounts based on quantity.

    discount_tiers should be a dict mapping ingredient_id to a list of
    (min_quantity, discount_rate) tuples, sorted by min_quantity ascending.

    Example:
      {
        "DARK-ROAST-BEANS-STD-KG": [
            (10.0, 0.10),   # 10% off if qty >= 10
            (25.0, 0.20),   # 20% off if qty >= 25
            (50.0, 0.30),   # 30% off if qty >= 50
        ],
      }
    """

    def __init__(
        self,
        ingredients: Dict[str, IngredientDefinition],
        clock,
        discount_tiers: Dict[str, List[Tuple[float, float]]],
    ):
        """
        :param ingredients: same IngredientDefinition dict you already use.
        :param clock: a TimeProvider (ClockAdapter) so we can stamp price_valid_until.
        :param discount_tiers: mapping ingredient_id → sorted list of (min_qty, discount_rate).
                               discount_rate is a decimal: e.g. 0.10 for 10% off.
        """
        self._ingredients = ingredients
        self._clock = clock
        self._tiers = discount_tiers

        # Ensure each tier list is sorted by ascending min_qty
        for ing_id, tiers in self._tiers.items():
            self._tiers[ing_id] = sorted(tiers, key=lambda x: x[0])

    def get_price(
        self, ingredient_id: str, quantity: float
    ) -> Optional[Dict[str, any]]:
        ing = self._ingredients.get(ingredient_id)
        if not ing:
            return None

        now = self._clock.now()
        base_price = ing.base_price

        # Look up discount tiers for this ingredient (if any)
        tiers_for_ing = self._tiers.get(ingredient_id, [])

        # Determine the best (highest) applicable discount
        applied_discount = 0.0
        for min_qty, discount_rate in tiers_for_ing:
            if quantity >= min_qty:
                applied_discount = discount_rate
            else:
                break

        # Compute the discounted price
        discounted_price = round(base_price * (1 - applied_discount), 2)

        return {
            "price_per_unit": discounted_price,
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
        quote_id: Optional[str] = None,
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
            quote_id=quote_id,
        )
        self._orders[order_id] = order
        return order

    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        return self._orders.get(order_id)
