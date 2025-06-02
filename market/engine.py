# engine.py
from typing import Dict, Optional
from fastapi import HTTPException
from models import QuoteRequest, QuoteResponse, BuyRequest, OrderItem, OrderResponse
from models import IngredientDefinition
from services import PricingService, InventoryService, OrderService
from constants import _INGREDIENTS, ONE_DAY


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
        import uuid

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

    def buy(self, req: BuyRequest) -> OrderResponse:

        ing_def = _INGREDIENTS.get(req.ingredient_id)
        if ing_def is None:
            return self._orders.create_order(
                business_id=req.business_id,
                item=OrderItem(
                    ingredient_id=req.ingredient_id,
                    quantity=req.quantity,
                    price_per_unit_paid=0.0,
                    total_price=0.0,
                    use_by_date=self._clock.now(),
                ),
                expected_delivery=self._clock.now(),
                status="FAILED_INVALID_ITEM",
                failure_reason=f"Ingredient {req.ingredient_id} not found.",
            )
        now = self._clock.now()
        price_per_unit: float
        if req.quote_id:
            cached = self._quote_store.get(req.quote_id)
            if (
                cached
                and cached["quote"].ingredient_id == req.ingredient_id
                and cached["quote"].total_price / req.quantity
                == cached["quote"].price_per_unit
                and cached["expires_at"] > now
            ):
                price_per_unit = cached["quote"].price_per_unit
            else:
                return self._orders.create_order(
                    business_id=req.business_id,
                    item=OrderItem(
                        ingredient_id=req.ingredient_id,
                        quantity=req.quantity,
                        price_per_unit_paid=0.0,
                        total_price=0.0,
                        use_by_date=ing_def.use_by_date,
                    ),
                    expected_delivery=now,
                    status="FAILED_INVALID_QUOTE",
                    failure_reason="Quote not found or expired.",
                )
        else:
            pinfo = self._pricing.get_price(req.ingredient_id, req.quantity)
            if not pinfo:
                return self._orders.create_order(
                    business_id=req.business_id,
                    item=OrderItem(
                        ingredient_id=req.ingredient_id,
                        quantity=req.quantity,
                        price_per_unit_paid=0.0,
                        total_price=0.0,
                        use_by_date=ing_def.use_by_date,
                    ),
                    expected_delivery=now,
                    status="FAILED_SYSTEM_ERROR",
                    failure_reason="Could not compute price.",
                )
            price_per_unit = pinfo["price_per_unit"]
        if req.max_acceptable_price_per_unit is not None:
            if price_per_unit > req.max_acceptable_price_per_unit:
                return self._orders.create_order(
                    business_id=req.business_id,
                    item=OrderItem(
                        ingredient_id=req.ingredient_id,
                        quantity=req.quantity,
                        price_per_unit_paid=0.0,
                        total_price=0.0,
                        use_by_date=ing_def.use_by_date,
                    ),
                    expected_delivery=now,
                    status="FAILED_PRICE_TOO_HIGH",
                    failure_reason=f"Price {price_per_unit:.2f} > max acceptable {req.max_acceptable_price_per_unit:.2f}",
                )
        available = self._inventory.get_stock(req.ingredient_id)
        if available is None or available < req.quantity:
            return self._orders.create_order(
                business_id=req.business_id,
                item=OrderItem(
                    ingredient_id=req.ingredient_id,
                    quantity=req.quantity,
                    price_per_unit_paid=0.0,
                    total_price=0.0,
                    use_by_date=ing_def.use_by_date,
                ),
                expected_delivery=now,
                status="FAILED_NO_STOCK",
                failure_reason=f"Insufficient stock. Available: {available or 0:.2f}",
            )
        ok = self._inventory.consume_stock(req.ingredient_id, req.quantity)
        if not ok:
            return self._orders.create_order(
                business_id=req.business_id,
                item=OrderItem(
                    ingredient_id=req.ingredient_id,
                    quantity=req.quantity,
                    price_per_unit_paid=0.0,
                    total_price=0.0,
                    use_by_date=ing_def.use_by_date,
                ),
                expected_delivery=now,
                status="FAILED_SYSTEM_ERROR",
                failure_reason="Race condition: stock consumption failed.",
            )
        total_price = round(price_per_unit * req.quantity, 2)
        item = OrderItem(
            ingredient_id=req.ingredient_id,
            quantity=req.quantity,
            price_per_unit_paid=price_per_unit,
            total_price=total_price,
            use_by_date=ing_def.use_by_date,
        )
        expected_delivery = now + 300  # 5 minutes lead time
        return self._orders.create_order(
            business_id=req.business_id,
            item=item,
            expected_delivery=expected_delivery,
            status="CONFIRMED",
        )

    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        return self._orders.get_order(order_id)
