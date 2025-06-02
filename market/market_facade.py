import uuid
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
from clock_adapter import ClockAdapter

app = FastAPI()

# Initialize the clock adapter (adjust URL as needed)
clock = ClockAdapter(base_url="http://127.0.0.1:8000")

ONE_DAY = 24
# ──────────────────────────────────────────────────────────────────────────────
# STEP 1. Pydantic models for request/response payloads
# ──────────────────────────────────────────────────────────────────────────────


class QuoteRequest(BaseModel):
    ingredient_id: str
    quantity: float = Field(..., gt=0)


class QuoteResponse(BaseModel):
    quote_id: str
    ingredient_id: str
    name: str
    description: str
    unit_of_measure: str
    price_per_unit: float
    total_price: float
    currency: str
    available_stock: float
    delivery_time: int
    use_by_date: int
    price_valid_until: int


class BuyRequest(BaseModel):
    quote_id: Optional[str] = None
    ingredient_id: str
    quantity: float = Field(..., gt=0)
    max_acceptable_price_per_unit: Optional[float] = None
    business_id: Optional[str] = None


class OrderItem(BaseModel):
    ingredient_id: str
    quantity: float
    price_per_unit_paid: float
    total_price: float
    use_by_date: int


class OrderResponse(BaseModel):
    order_id: str
    business_id: Optional[str]
    items: Dict[str, OrderItem]
    total_cost: float
    order_placed_at: int
    expected_delivery: int
    status: str
    failure_reason: Optional[str] = None

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2. In‐memory “database” of ingredients
# ──────────────────────────────────────────────────────────────────────────────


class IngredientDefinition:
    def __init__(
        self,
        ingredient_id: str,
        name: str,
        description: str,
        unit_of_measure: str,
        currency: str,
        base_price: float,
        use_by_date: int,
        stock: float,
    ):
        self.ingredient_id = ingredient_id
        self.name = name
        self.description = description
        self.unit_of_measure = unit_of_measure
        self.currency = currency
        self.base_price = base_price
        self.use_by_date = use_by_date
        self.stock = stock


# TODO: we support one hard‐coded ingredient: Standard Robusta Coffee Beans
_INGREDIENTS: Dict[str, IngredientDefinition] = {
    "COFB-ROBUSTA-STD-KG": IngredientDefinition(
        ingredient_id="COFB-ROBUSTA-STD-KG",
        name="Standard Robusta Coffee Beans",
        description="Basic robusta beans, suitable for general use.",
        unit_of_measure="kg",
        currency="USD",
        base_price=8.50,  # $8.50 per kg
        use_by_date=clock.now() + ONE_DAY,
        stock=250.75,  # 250.75 kg in stock
    )
}

# ──────────────────────────────────────────────────────────────────────────────
# STEP 3. PricingService (super‐simple)
# ──────────────────────────────────────────────────────────────────────────────


class PricingService:
    def __init__(self, ingredients: Dict[str, IngredientDefinition]):
        self._ingredients = ingredients

    def get_price(
        self, ingredient_id: str, quantity: float
    ) -> Optional[Dict[str, any]]:
        """
        Return:
          {
            "price_per_unit": float,
            "price_valid_until": int
          }
        """
        ing = self._ingredients.get(ingredient_id)
        if not ing:
            return None

        # In a real market, price might depend on supply/shocks. Here, we just return base_price
        now = clock.now()
        return {
            "price_per_unit": ing.base_price,
            "price_valid_until": now + ONE_DAY,
        }

# ──────────────────────────────────────────────────────────────────────────────
# STEP 4. InventoryService (in‐memory, very basic)
# ──────────────────────────────────────────────────────────────────────────────


class InventoryService:
    def __init__(self, ingredients: Dict[str, IngredientDefinition]):
        self._ingredients = ingredients

    def get_stock(self, ingredient_id: str) -> Optional[float]:
        ing = self._ingredients.get(ingredient_id)
        return ing.stock if ing else None

    def consume_stock(self, ingredient_id: str, quantity: float) -> bool:
        """
        Try to consume `quantity` from stock. Return True if successful, False otherwise.
        """
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

# ──────────────────────────────────────────────────────────────────────────────
# STEP 5. OrderService (in‐memory, very basic)
# ──────────────────────────────────────────────────────────────────────────────


class OrderService:
    def __init__(self):
        # order_id → OrderResponse
        self._orders: Dict[str, OrderResponse] = {}

    def create_order(
        self,
        business_id: Optional[str],
        item: OrderItem,
        expected_delivery: int,
        status: str,
        failure_reason: Optional[str] = None,
    ) -> OrderResponse:
        order_id = str(uuid.uuid4())
        now = clock.now()

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

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6. EngineFacade (glue code)
# ──────────────────────────────────────────────────────────────────────────────


class EngineFacade:
    def __init__(
        self,
        pricing_service: PricingService,
        inventory_service: InventoryService,
        order_service: OrderService,
    ):
        self._pricing = pricing_service
        self._inventory = inventory_service
        self._orders = order_service
        self._quote_store: Dict[str, Dict] = {}

    def _generate_quote_id(self) -> str:
        return str(uuid.uuid4())

    def get_quote(self, ingredient_id: str, quantity: float) -> QuoteResponse:
        # 1. Validate ingredient exists
        ing_def = _INGREDIENTS.get(ingredient_id)
        if ing_def is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")

        # 2. Get price
        price_info = self._pricing.get_price(ingredient_id, quantity)
        if price_info is None:
            raise HTTPException(status_code=500, detail="Pricing failed")

        # 3. Check stock
        stock_available = self._inventory.get_stock(ingredient_id)
        if stock_available is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        if stock_available < quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock. Available: {stock_available:.2f}",
            )

        # 4. Build a quote object
        quote_id = self._generate_quote_id()
        now = clock.now()
        price_valid_until: int = price_info["price_valid_until"]
        total_price = round(price_info["price_per_unit"] * quantity, 2)
        delivery_time = now + ONE_DAY

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

        # 5. Store the quote temporarily (valid for 10 minutes)
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
                    use_by_date=clock.now(),
                ),
                expected_delivery=clock.now(),
                status="FAILED_INVALID_ITEM",
                failure_reason=f"Ingredient {req.ingredient_id} not found.",
            )

        now = clock.now()

        # 1. If client provided quote_id, check validity
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
                # invalid or expired quote → reject
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
            # 2. No quote_id: re‐compute price now
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

        # 3. Check max_acceptable_price_per_unit (if provided)
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

        # 4. Check and consume stock
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

        # 5. Everything’s good → build an OrderItem and place a CONFIRMED order
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

# ──────────────────────────────────────────────────────────────────────────────
# STEP 7. Instantiate services and mount FastAPI endpoints
# ──────────────────────────────────────────────────────────────────────────────


pricing_service = PricingService(_INGREDIENTS)
inventory_service = InventoryService(_INGREDIENTS)
order_service = OrderService()
engine = EngineFacade(pricing_service, inventory_service, order_service)


@app.post("/quote", response_model=QuoteResponse)
def quote_endpoint(req: QuoteRequest):
    return engine.get_quote(req.ingredient_id, req.quantity)


@app.post("/buy", response_model=OrderResponse)
def buy_endpoint(req: BuyRequest):
    return engine.buy(req)


@app.get("/order/{order_id}", response_model=OrderResponse)
def get_order(order_id: str):
    order = engine.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


# Optional: peek at current in‐memory stock
@app.get("/stock/{ingredient_id}")
def check_stock(ingredient_id: str):
    stock = inventory_service.get_stock(ingredient_id)
    if stock is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return {"ingredient_id": ingredient_id, "stock_available": stock}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
