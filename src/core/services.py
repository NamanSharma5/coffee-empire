# services.py
from typing import Dict, Optional, Tuple, List
from abc import ABC, abstractmethod
from ..models.api_models import IngredientDefinition
from ..models.api_models import OrderResponse, OrderItem
from ..utils.constants import ONE_DAY
from ..storage.storage import AbstractStorage


# Abstract base class for PricingService
class PricingService(ABC):
    @abstractmethod
    def get_price(
        self, ingredient_id: str, quantity: float
    ) -> Optional[Dict[str, any]]:
        pass

class DefaultPricingService(PricingService):
    def __init__(self, clock, ingredients: Dict[str, IngredientDefinition]):
        self._clock = clock
        self._ingredients = ingredients

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
        clock,
        ingredients: Dict[str, IngredientDefinition],
        discount_tiers: Dict[str, List[Tuple[float, float]]],
    ):
        """
        :param ingredients: same IngredientDefinition dict you already use.
        :param clock: a TimeProvider (ClockAdapter) so we can stamp price_valid_until.
        :param discount_tiers: mapping ingredient_id → sorted list of (min_qty, discount_rate).
                               discount_rate is a decimal: e.g. 0.10 for 10% off.
        """
        self._clock = clock
        self._ingredients = ingredients
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


class DemandBasedPricingService(PricingService):
    """
    PricingService that adjusts prices based on quote demand within a time window.
    Composes with VolumeDiscountPricingService to apply both demand-based and volume-based pricing.
    """

    def __init__(
        self,
        clock,
        ingredients: Dict[str, IngredientDefinition],
        volume_discount_service: VolumeDiscountPricingService,
        demand_window_hours: int,
        demand_price_hikes: Dict[str, Dict[str, float]],
    ):
        """
        :param ingredients: IngredientDefinition dict
        :param clock: TimeProvider (ClockAdapter)
        :param volume_discount_service: Instance of VolumeDiscountPricingService
        :param demand_window_hours: Time window in hours to track quotes
        :param demand_price_hikes: Dict mapping ingredient_id to quote threshold and price hike percentage
        """
        self._clock = clock
        self._ingredients = ingredients
        self._volume_discount_service = volume_discount_service
        self._demand_window_hours = demand_window_hours
        self._demand_price_hikes = demand_price_hikes
        self._quote_history: Dict[str, List[int]] = {}  # ingredient_id -> list of quote timestamps

    def record_quote(self, ingredient_id: str) -> None:
        """Record a quote for an ingredient at the current time."""
        now = self._clock.now()
        if ingredient_id not in self._quote_history:
            self._quote_history[ingredient_id] = []
        self._quote_history[ingredient_id].append(now)

    # TURNED OFF FOR NOW: Check if total quote count exceeds threshold and cleanup if needed
    #     total_quotes = sum(len(quotes) for quotes in self._quote_history.values())
    #     if total_quotes > QUOTE_CLEANUP_THRESHOLD:
    #         self._cleanup_all_quotes()

    # def _cleanup_all_quotes(self) -> None:
    #     """Clean up all quotes across all ingredients when threshold is exceeded."""
    #     now = self._clock.now()
    #     cutoff_time = now - self._demand_window_hours

    #     for ingredient_id in list(self._quote_history.keys()):
    #         self._quote_history[ingredient_id] = [
    #             timestamp for timestamp in self._quote_history[ingredient_id]
    #             if timestamp >= cutoff_time
    #         ]
    #         # Remove empty lists to keep the dict clean
    #         if not self._quote_history[ingredient_id]:
    #             del self._quote_history[ingredient_id]

    def _clean_old_quotes(self, ingredient_id: str) -> None:
        """Remove quotes older than the demand window."""
        if ingredient_id not in self._quote_history:
            return

        now = self._clock.now()
        cutoff_time = now - self._demand_window_hours
        self._quote_history[ingredient_id] = [
            timestamp for timestamp in self._quote_history[ingredient_id]
            if timestamp >= cutoff_time
        ]

    def get_price(
        self, ingredient_id: str, quantity: float
    ) -> Optional[Dict[str, any]]:

        # First get the volume-discounted price
        volume_price = self._volume_discount_service.get_price(ingredient_id, quantity)
        if not volume_price:
            return None

        # Clean old quotes and count recent ones
        self._clean_old_quotes(ingredient_id)
        # Record this quote request
        self.record_quote(ingredient_id)
        recent_quotes = len(self._quote_history.get(ingredient_id, []))

        # Get demand-based pricing parameters
        demand_params = self._demand_price_hikes.get(ingredient_id, {})
        quote_threshold = demand_params.get("quote_threshold", float("inf"))
        price_hike_percent = demand_params.get("price_hike_percent", 0.0)

        # Calculate demand-based price adjustment
        if recent_quotes >= quote_threshold:
            hikes = recent_quotes // quote_threshold
            demand_multiplier = (1 + price_hike_percent) ** hikes
            adjusted_price = round(volume_price["price_per_unit"] * demand_multiplier, 2)
        else:
            adjusted_price = volume_price["price_per_unit"]

        return {
            "price_per_unit": adjusted_price,
            "price_valid_until": volume_price["price_valid_until"],
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
    def __init__(self, clock, storage: AbstractStorage):
        self._orders: Dict[str, OrderResponse] = {}
        self._clock = clock
        self._storage = storage

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
        if status == "CONFIRMED":
            self._storage.save_order(order)
        return order

    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        return self._storage.get_order(order_id)
