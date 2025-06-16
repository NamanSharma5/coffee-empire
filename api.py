# api.py
from fastapi import FastAPI, HTTPException
from models import (
    QuoteRequest,
    QuoteResponse,
    BuyRequest,
    OrderResponse,
)
from services import DefaultPricingService, VolumeDiscountPricingService, InventoryService, OrderService
from engine import EngineFacade
import uvicorn
from constants import _INGREDIENTS, VOLUME_DISCOUNT_TIERS
from clock_adapter import ClockAdapter
import os
from dotenv import load_dotenv

load_dotenv()
CLOCK_URL = os.environ.get("CLOCK_URL") or "https://coffee-empire-clock.vercel.app"
print(CLOCK_URL)

app = FastAPI()

# Initialize the clock adapter (adjust URL as needed)
clock = ClockAdapter(base_url=CLOCK_URL)

# pricing_service = DefaultPricingService(_INGREDIENTS, clock=clock)
pricing_service = VolumeDiscountPricingService(_INGREDIENTS, clock, VOLUME_DISCOUNT_TIERS)
inventory_service = InventoryService(_INGREDIENTS)
order_service = OrderService(clock=clock)
engine = EngineFacade(pricing_service, inventory_service, order_service, clock)


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


@app.get("/stock/{ingredient_id}")
def check_stock(ingredient_id: str):
    stock = inventory_service.get_stock(ingredient_id)
    if stock is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return {"ingredient_id": ingredient_id, "stock_available": stock}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
