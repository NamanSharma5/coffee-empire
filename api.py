# api.py
from fastapi import FastAPI, HTTPException
from models import (
    QuoteRequest,
    QuoteResponse,
    BuyRequest,
    OrderResponse,
)
from services import DemandBasedPricingService, VolumeDiscountPricingService, InventoryService, OrderService
from engine import EngineFacade
import uvicorn
from constants import _INGREDIENTS, VOLUME_DISCOUNT_TIERS, DEMAND_WINDOW_HOURS, DEMAND_PRICE_HIKES
from clock_adapter import ClockAdapter, FoundryClockAdapter
import os
from dotenv import load_dotenv
from storage import InMemoryStorage, SqlStorage
from database_service import DatabaseService

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize the clock adapter (adjust URL as needed)
if os.environ.get("CLOCK") is not None and os.environ.get("CLOCK") .lower() == "foundry":
    clock = FoundryClockAdapter()
    logger.info("Using Foundry as the simulation clock")
else:
    CLOCK_URL = os.environ.get("CLOCK_URL") or "https://coffee-empire-clock.vercel.app"
    clock = ClockAdapter(base_url=CLOCK_URL)
    logger.info("Using Vercel as simulation clock")

# initialise state
USE_DATABASE: bool = os.getenv("USE_DATABASE","false").lower() == "true"

if USE_DATABASE:
    logger.info("Using postgres database for orders")
    db_url = os.getenv("POSTGRES_CONNECTION_URL")
    db_service = DatabaseService(db_url)
    session = db_service.get_session()
    storage = SqlStorage(session)
else:
    logger.info("All data structures are in-memory")
    storage = InMemoryStorage()

app = FastAPI()

# pricing_service = DefaultPricingService(_INGREDIENTS, clock=clock)
volumeDiscountService = VolumeDiscountPricingService(clock,_INGREDIENTS, VOLUME_DISCOUNT_TIERS)
demandBasedPricingService = DemandBasedPricingService(clock,_INGREDIENTS, volumeDiscountService, DEMAND_WINDOW_HOURS, DEMAND_PRICE_HIKES)
inventory_service = InventoryService(_INGREDIENTS)
order_service = OrderService(clock=clock, storage=storage)
engine = EngineFacade(demandBasedPricingService, inventory_service, order_service, clock, storage)


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


@app.post("/reset-database")
def reset_database():
    if not USE_DATABASE:
        raise HTTPException(status_code=400, detail="Database is not enabled")
    db_url = os.getenv("POSTGRES_CONNECTION_URL")
    db_service = DatabaseService(db_url)
    return db_service.reset_tables()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
