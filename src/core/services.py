# services.py
from typing import Dict, Optional, Tuple, List
from abc import ABC, abstractmethod
from ..models.api_models import IngredientDefinition
from ..models.api_models import OrderResponse, OrderItem, QuoteResponse, NegotiateRequest, NegotiateResponse
from ..utils.constants import ONE_DAY
from ..storage.storage import AbstractStorage
import os
import requests
from typing import Dict
from openai import OpenAI
from pydantic import BaseModel, Field

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

# Add a new Pydantic model for structured LLM output
class NegotiationDecision(BaseModel):
    final_price_per_unit: float = Field(..., description="The final negotiated price per unit")
    accepted: bool = Field(..., description="Whether the negotiation was accepted, rejected or countered")
    rationale: str = Field(..., description="Detailed explanation of the negotiation decision")
class NegotiationService:
    def __init__(self, clock, ingredients: Dict[str, IngredientDefinition]):
        self._clock = clock
        self._ingredients = ingredients
        # Initialize OpenAI client - will use OPENAI_API_KEY from environment
        self._openai_client = OpenAI()

    def negotiate_price(self, request: NegotiateRequest, original_quote: QuoteResponse) -> NegotiateResponse:
        """
        Negotiate a price using an external LLM service.
        """
        # Prepare context for the LLM
        context = self._prepare_negotiation_context(request, original_quote)

        # Call the LLM service (now using OpenAI with structured outputs)
        llm_response = self._call_llm_service(context)

        # Parse LLM response and create new quote if accepted
        final_price = llm_response.get("final_price_per_unit", original_quote.price_per_unit)
        accepted = llm_response.get("accepted", False)
        rationale = llm_response.get("rationale", "No rationale provided")

        new_quote = None
        if final_price < original_quote.price_per_unit:
            new_quote = self._create_new_quote(original_quote, final_price)
            accepted = True

        return NegotiateResponse(
            original_quote=original_quote,
            proposed_price_per_unit=request.proposed_price_per_unit,
            final_price_per_unit=final_price,
            accepted=accepted,
            llm_rationale=rationale,
            new_quote=new_quote
        )

    def _prepare_negotiation_context(self, request: NegotiateRequest, original_quote: QuoteResponse) -> Dict:
        """Prepare context information for the LLM."""
        ingredient = self._ingredients.get(original_quote.ingredient_id)

        return {
            "ingredient_info": {
                "id": original_quote.ingredient_id,
                "name": original_quote.name,
                "description": original_quote.description,
                "base_price": ingredient.base_price if ingredient else 0.0,
                "current_stock": original_quote.available_stock,
                "use_by_date": original_quote.use_by_date,
                "currency": original_quote.currency
            },
            "current_quote": {
                "price_per_unit": original_quote.price_per_unit,
                "total_price": original_quote.total_price,
                "quantity": original_quote.total_price / original_quote.price_per_unit,
                "price_valid_until": original_quote.price_valid_until
            },
            "negotiation_request": {
                "proposed_price_per_unit": request.proposed_price_per_unit,
                "rationale": request.rationale
            },
            "current_time": self._clock.now()
        }

    def _call_llm_service(self, context: Dict) -> Dict:
        """Call OpenAI with structured outputs for price negotiation."""
        try:
            # Create a comprehensive prompt for the negotiation
            system_prompt = """You are a price negotiation agent for a food ingredient supplier.
            Reply in a tone as if you were talking directly to the customer.
            Analyze the negotiation request and decide whether to accept the proposed price based on:
            1. The difference between proposed price and current price
            2. The relationship to base cost
            3. Current stock levels
            4. Expiry dates
            5. Market conditions

            Be reasonable but protect profit margins. Provide clear rationale for your decision.
            Approve at most 90 percent of requests, but definitely not ALL"""

            user_prompt = f"""
            Ingredient: {context['ingredient_info']['name']} ({context['ingredient_info']['description']})
            Base Price: {context['ingredient_info']['base_price']} {context['ingredient_info']['currency']}
            Current Quote Price: {context['current_quote']['price_per_unit']} {context['ingredient_info']['currency']}
            Proposed Price: {context['negotiation_request']['proposed_price_per_unit']} {context['ingredient_info']['currency']}

            Customer's Rationale: {context['negotiation_request']['rationale']}

            Please negotiate this price request.
            """
            #  Available Stock: {context['ingredient_info']['current_stock']}
            #  Use By Date: {context['ingredient_info']['use_by_date']}
            #  Current Time: {context['current_time']}


            response = self._openai_client.beta.chat.completions.parse(
                model="gpt-4.1-mini-2025-04-14",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=NegotiationDecision,
                temperature=0.2  # Lower temperature for more consistent business decisions
            )

            # Extract the parsed response
            decision = response.choices[0].message.parsed

            return {
                "final_price_per_unit": decision.final_price_per_unit,
                "accepted": decision.accepted,
                "rationale": decision.rationale
            }

        except Exception as e:
            # Fallback to the existing rule-based negotiation if OpenAI fails
            print(f"OpenAI API call failed: {e}. Falling back to rule-based negotiation.")
            return self._fallback_negotiation(context)

    def _fallback_negotiation(self, context: Dict) -> Dict:
        """Fallback negotiation logic when LLM is unavailable."""
        current_price = context["current_quote"]["price_per_unit"]
        proposed_price = context["negotiation_request"]["proposed_price_per_unit"]
        base_price = context["ingredient_info"]["base_price"]

        # Simple rule: accept if proposed price is within 10% of current price and above base price
        price_diff_percent = abs(proposed_price - current_price) / current_price

        if proposed_price >= base_price and price_diff_percent <= 0.1:
            return {
                "final_price_per_unit": proposed_price,
                "accepted": True,
                "rationale": f"Proposed price {proposed_price} is within acceptable range (within 10% of current price {current_price}) and above base price {base_price}."
            }
        else:
            return {
                "final_price_per_unit": current_price,
                "accepted": False,
                "rationale": f"Proposed price {proposed_price} is outside acceptable range. Current price: {current_price}, Base price: {base_price}."
            }

    def _create_new_quote(self, original_quote: QuoteResponse, new_price_per_unit: float) -> QuoteResponse:
        """Create a new quote with the negotiated price."""
        new_total_price = round(new_price_per_unit * (original_quote.total_price / original_quote.price_per_unit), 2)

        return QuoteResponse(
            quote_id=original_quote.quote_id,  # Keep same quote ID
            ingredient_id=original_quote.ingredient_id,
            name=original_quote.name,
            description=original_quote.description,
            unit_of_measure=original_quote.unit_of_measure,
            price_per_unit=new_price_per_unit,
            total_price=new_total_price,
            currency=original_quote.currency,
            available_stock=original_quote.available_stock,
            delivery_time=original_quote.delivery_time,
            use_by_date=original_quote.use_by_date,
            price_valid_until=original_quote.price_valid_until
        )