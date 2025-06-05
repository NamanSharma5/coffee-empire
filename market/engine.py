# engine.py
from typing import Dict, Optional
from fastapi import HTTPException
from models import QuoteRequest, QuoteResponse, BuyRequest, OrderItem, OrderResponse
from models import IngredientDefinition
from services import PricingService, InventoryService, OrderService
from constants import _INGREDIENTS, ONE_DAY, EXPECTED_DELIVERY
import uuid


class EngineFacade:
    def __init__(
        self,
        pricing_service: PricingService,
        inventory_service: InventoryService,
        order_service: OrderService,
        clock,
    ):
        self._pricing = pricing_service
        self._inventory = inventory_service
        self._orders = order_service
        self._clock = clock
        self._quote_store: Dict[str, Dict] = {}

    def _generate_quote_id(self) -> str:
        return str(uuid.uuid4())

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
            cached = self._quote_store.get(req.quote_id)
            if (
                cached
                and cached["quote"].ingredient_id == req.ingredient_id
                # you have to spend at least the total price of your quote (no low quantity at cheaper prices)
                and cached["quote"].price_per_unit * req.quantity >= cached["quote"].total_price
                and cached["expires_at"] > now
            ):
                price_per_unit = cached["quote"].price_per_unit
            else:
                return self._failed_order(
                    business_id=req.business_id,
                    ingredient_id=req.ingredient_id,
                    quantity=req.quantity,
                    use_by_date=ing_def.use_by_date,
                    expected_delivery=now,
                    status="FAILED_INVALID_QUOTE",
                    failure_reason="Quote not found, expired or under expected spend.",
                    quote_id=req.quote_id,
                )
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
            use_by_date=ing_def.use_by_date,
        )

        expected_delivery = now + EXPECTED_DELIVERY

        # evict quote from cache if order successfuly created
        del self._quote_store[req.quote_id]

        return self._orders.create_order(
            business_id=req.business_id,
            item=item,
            expected_delivery=expected_delivery,
            status="CONFIRMED",
            quote_id=req.quote_id,
        )

    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        return self._orders.get_order(order_id)
