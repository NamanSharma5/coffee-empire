# engine.py
from typing import Dict, Optional, List
from fastapi import HTTPException
from src.models.api_models import QuoteRequest, QuoteResponse, BuyRequest, OrderItem, OrderResponse, NegotiateRequest, NegotiateResponse
from src.models.api_models import IngredientDefinition
from src.core.services import PricingService, InventoryService, OrderService, NegotiationService
from src.utils.constants import _INGREDIENTS, ONE_DAY, EXPECTED_DELIVERY, QUOTE_CLEANUP_THRESHOLD
import uuid
from src.storage.storage import AbstractStorage


class EngineFacade:
    def __init__(
        self,
        pricing_service: PricingService,
        inventory_service: InventoryService,
        order_service: OrderService,
        clock,
        storage: AbstractStorage,
    ):
        self._pricing = pricing_service
        self._inventory = inventory_service
        self._orders = order_service
        self._clock = clock
        self._quote_store: Dict[str, Dict] = {}
        self._negotiated_quote_store: Dict[str, Dict] = {}  # Separate store for negotiated quotes
        self._storage = storage
        self._negotiation_service = NegotiationService(clock, _INGREDIENTS)

    def _generate_quote_id(self) -> str:
        return str(uuid.uuid4())

    def _cleanup_quote_store(self) -> None:
        """Clean up expired quotes from both quote stores when threshold is exceeded."""
        now = self._clock.now()

        # Clean up regular quote store
        expired_quotes = [
            quote_id for quote_id, quote_data in self._quote_store.items()
            if quote_data["expires_at"] <= now
        ]
        for quote_id in expired_quotes:
            del self._quote_store[quote_id]

        # Clean up negotiated quote store
        expired_negotiated_quotes = [
            quote_id for quote_id, quote_data in self._negotiated_quote_store.items()
            if quote_data["expires_at"] <= now
        ]
        for quote_id in expired_negotiated_quotes:
            del self._negotiated_quote_store[quote_id]

    def _get_unnegotiated_quotes(self, quote_id: str) -> Optional[Dict]:
        # Check regular quotes
        if quote_id in self._quote_store:
            return self._quote_store[quote_id]

        return None

    def _get_negotiated_quotes(self, quote_id:str) -> Optional[Dict]:
        if quote_id in self._negotiated_quote_store:
            return self._negotiated_quote_store[quote_id]

        return None

    def get_quote(self, ingredient_id: str, quantity: float) -> QuoteResponse:

        ing_def = _INGREDIENTS.get(ingredient_id)
        if ing_def is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")

        price_info = self._pricing.get_price(ingredient_id, quantity)
        if price_info is None:
            raise HTTPException(status_code=500, detail="Pricing failed")

        stock_available = self._inventory.get_stock(ingredient_id)
        if stock_available is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        if stock_available < quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock. Available: {stock_available:.2f}",
            )
        quote_id = self._generate_quote_id()
        price_valid_until: int = price_info["price_valid_until"]
        total_price = round(price_info["price_per_unit"] * quantity, 2)
        delivery_time = ONE_DAY
        quote = QuoteResponse(
            quote_id=quote_id,
            ingredient_id=ingredient_id,
            name=ing_def.name,
            description=ing_def.description,
            unit_of_measure=ing_def.unit_of_measure,
            price_per_unit=price_info["price_per_unit"],
            total_price=total_price,
            currency=ing_def.currency,
            available_stock=stock_available,
            use_by_date=ing_def.use_by_date,
            price_valid_until=price_valid_until,
            delivery_time=delivery_time,
        )
        self._quote_store[quote_id] = {
            "quote": quote,
            "expires_at": price_valid_until,
        }

        # Check if quote count exceeds threshold and cleanup if needed
        if len(self._quote_store) > QUOTE_CLEANUP_THRESHOLD:
            self._cleanup_quote_store()

        # for now do not save quote to persistent storage
        # self._storage.save_quote(quote)
        return quote

    def _failed_order(
        self,
        business_id,
        ingredient_id,
        quantity,
        use_by_date,
        expected_delivery,
        status,
        failure_reason,
        quote_id=None,
    ):
        return self._orders.create_order(
            business_id=business_id,
            item=OrderItem(
                ingredient_id=ingredient_id,
                quantity=quantity,
                price_per_unit_paid=0.0,
                total_price=0.0,
                use_by_date=use_by_date,
            ),
            expected_delivery=expected_delivery,
            status=status,
            failure_reason=failure_reason,
            quote_id=quote_id,
        )

    def buy(self, req: BuyRequest) -> OrderResponse:

        # ensure that either the quote or ingredient is present
        if req.quote_id is None and req.ingredient_id is None:
            return self._failed_order(
                business_id=req.business_id,
                ingredient_id=None,
                quantity=req.quantity,
                use_by_date=self._clock.now(),
                expected_delivery=self._clock.now(),
                status="FAILED_INVALID_REQUEST",
                failure_reason="Neither quote_id nor ingredient_id provided.",
                quote_id=None,
            )

        ing_def = _INGREDIENTS.get(req.ingredient_id)
        if ing_def is None:
            return self._failed_order(
                business_id=req.business_id,
                ingredient_id=req.ingredient_id,
                quantity=req.quantity,
                use_by_date=self._clock.now(),
                expected_delivery=self._clock.now(),
                status="FAILED_INVALID_ITEM",
                failure_reason=f"Ingredient {req.ingredient_id} not found.",
                quote_id=req.quote_id,
            )
        now = self._clock.now()

        # Get price per unit
        price_per_unit: float
        if req.quote_id:
            cached = self._get_unnegotiated_quotes(req.quote_id)
            if cached is None:
                cached = self._get_negotiated_quotes(req.quote_id)

            # okay the cache really doesn't have this so just generate a new price
            if cached is None:
                # return self._failed_order(
                #     business_id=req.business_id,
                #     ingredient_id=req.ingredient_id,
                #     quantity=req.quantity,
                #     use_by_date=ing_def.use_by_date,
                #     expected_delivery=now,
                #     status="FAILED_INVALID_QUOTE:NOT_FOUND",
                #     failure_reason="Quote not found.",
                #     quote_id=req.quote_id,
                # )

                pinfo = self._pricing.get_price(req.ingredient_id, req.quantity)
                #TODO: put a premium here for not getting a quote
                if not pinfo:
                    return self._failed_order(
                        business_id=req.business_id,
                        ingredient_id=req.ingredient_id,
                        quantity=req.quantity,
                        use_by_date=ing_def.use_by_date,
                        expected_delivery=now,
                        status="FAILED_SYSTEM_ERROR",
                        failure_reason="Could not compute price.",
                        quote_id=req.quote_id,
                    )
                price_per_unit = pinfo["price_per_unit"]

            else:

                if cached["quote"].ingredient_id != req.ingredient_id:
                    return self._failed_order(
                        business_id=req.business_id,
                        ingredient_id=req.ingredient_id,
                        quantity=req.quantity,
                        use_by_date=ing_def.use_by_date,
                        expected_delivery=now,
                        status="FAILED_INVALID_QUOTE:INGREDIENT_MISMATCH",
                        failure_reason=f"Ingredient in quote ({cached['quote'].ingredient_id}) does not match requested ingredient ({req.ingredient_id}).",
                        quote_id=req.quote_id,
                    )

                # drop this constraint to simplify
                # if cached["quote"].price_per_unit * req.quantity < cached["quote"].total_price:
                #     return self._failed_order(
                #         business_id=req.business_id,
                #         ingredient_id=req.ingredient_id,
                #         quantity=req.quantity,
                #         use_by_date=ing_def.use_by_date,
                #         expected_delivery=now,
                #         status="FAILED_INVALID_QUOTE:UNDER_MINIMUM_SPEND",
                #         failure_reason=(
                #             f"Total spend ({cached['quote'].price_per_unit * req.quantity:.2f}) is less than the quoted minimum ({cached['quote'].total_price:.2f})."
                #         ),
                #         quote_id=req.quote_id,
                #     )

                if cached["expires_at"] <= now:
                    return self._failed_order(
                        business_id=req.business_id,
                        ingredient_id=req.ingredient_id,
                        quantity=req.quantity,
                        use_by_date=ing_def.use_by_date,
                        expected_delivery=now,
                        status="FAILED_INVALID_QUOTE:QUOTE_EXPIRED",
                        failure_reason="Quote has expired.",
                        quote_id=req.quote_id,
                    )

                # no failure cases so get quoted unit price
                price_per_unit = cached["quote"].price_per_unit
        else:
            pinfo = self._pricing.get_price(req.ingredient_id, req.quantity)
            #TODO: put a premium here for not getting a quote
            if not pinfo:
                return self._failed_order(
                    business_id=req.business_id,
                    ingredient_id=req.ingredient_id,
                    quantity=req.quantity,
                    use_by_date=ing_def.use_by_date,
                    expected_delivery=now,
                    status="FAILED_SYSTEM_ERROR",
                    failure_reason="Could not compute price.",
                    quote_id=req.quote_id,
                )
            price_per_unit = pinfo["price_per_unit"]

        if req.max_acceptable_price_per_unit is not None:
            if price_per_unit > req.max_acceptable_price_per_unit:
                return self._failed_order(
                    business_id=req.business_id,
                    ingredient_id=req.ingredient_id,
                    quantity=req.quantity,
                    use_by_date=ing_def.use_by_date,
                    expected_delivery=now,
                    status="FAILED_PRICE_TOO_HIGH",
                    failure_reason=f"Price {price_per_unit:.2f} > max acceptable {req.max_acceptable_price_per_unit:.2f}",
                    quote_id=req.quote_id,
                )
        available = self._inventory.get_stock(req.ingredient_id)
        if available is None or available < req.quantity:
            return self._failed_order(
                business_id=req.business_id,
                ingredient_id=req.ingredient_id,
                quantity=req.quantity,
                use_by_date=ing_def.use_by_date,
                expected_delivery=now,
                status="FAILED_NO_STOCK",
                failure_reason=f"Insufficient stock. Available: {available or 0:.2f}",
                quote_id=req.quote_id,
            )

        ok = self._inventory.consume_stock(req.ingredient_id, req.quantity)
        if not ok:
            return self._failed_order(
                business_id=req.business_id,
                ingredient_id=req.ingredient_id,
                quantity=req.quantity,
                use_by_date=ing_def.use_by_date,
                expected_delivery=now,
                status="FAILED_SYSTEM_ERROR",
                failure_reason="Race condition: stock consumption failed.",
                quote_id=req.quote_id,
            )
        total_price = round(price_per_unit * req.quantity, 2)
        item = OrderItem(
            ingredient_id=req.ingredient_id,
            quantity=req.quantity,
            price_per_unit_paid=price_per_unit,
            total_price=total_price,
            use_by_date=ing_def.use_by_date + now,
        )

        expected_delivery = now + EXPECTED_DELIVERY

        # evict quote from cache if order successfuly created
        if req.quote_id:
            # Remove from both stores
            if req.quote_id in self._quote_store:
                del self._quote_store[req.quote_id]
            if req.quote_id in self._negotiated_quote_store:
                del self._negotiated_quote_store[req.quote_id]

        return self._orders.create_order(
            business_id=req.business_id,
            item=item,
            expected_delivery=expected_delivery,
            status="CONFIRMED",
            quote_id=req.quote_id,
        )

    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        return self._orders.get_order(order_id)

    def get_orders_by_business_id(self, business_id: str) -> List[OrderResponse]:
        return self._storage.get_orders_by_business_id(business_id)

    def negotiate(self, request: NegotiateRequest) -> NegotiateResponse:
        """
        Negotiate a price for an existing quote.
        """
        # Check if quote exists and is valid
        cached = self._get_unnegotiated_quotes(request.quote_id)
        if not cached:
            raise HTTPException(
                status_code=404,
                detail="Quote not found. You need a valid unnegotiated quote before you can negotiate."
            )

        original_quote:QuoteResponse = cached["quote"]
        now = self._clock.now()

        # Check if quote has expired
        if cached["expires_at"] <= now:
            raise HTTPException(
                status_code=400,
                detail="Quote has expired. Please request a new quote before negotiating."
            )

        if original_quote.price_per_unit <= request.proposed_price_per_unit:
            raise HTTPException(
                status_code=400,
                detail="You are trying to ask for a higher price per unit ?!"
            )

        # Perform negotiation
        negotiation_result = self._negotiation_service.negotiate_price(request, original_quote)

        # If negotiation was successful, move the quote to the negotiated store
        if negotiation_result.accepted and negotiation_result.new_quote:
            # Remove from regular quote store
            if request.quote_id in self._quote_store:
                del self._quote_store[request.quote_id]

            # Add to negotiated quote store
            self._negotiated_quote_store[request.quote_id] = {
                "quote": negotiation_result.new_quote,
                "expires_at": original_quote.price_valid_until,
                "negotiated_at": now,
                "original_price": original_quote.price_per_unit,
                "negotiated_price": negotiation_result.final_price_per_unit,
            }

        return negotiation_result
