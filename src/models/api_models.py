# models.py
from typing import Dict, Optional
from pydantic import BaseModel, Field


# Pydantic models for request/response payloads
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
    ingredient_id: Optional[str] = None
    quantity: float = Field(..., gt=0)
    max_acceptable_price_per_unit: Optional[float] = None
    business_id: Optional[str] = None


class NegotiateRequest(BaseModel):
    quote_id: str
    proposed_price_per_unit: float = Field(..., gt=0)
    rationale: str = Field(..., min_length=1, max_length=1000)


class NegotiateResponse(BaseModel):
    original_quote: QuoteResponse
    proposed_price_per_unit: float
    final_price_per_unit: float
    accepted: bool
    llm_rationale: str
    new_quote: Optional[QuoteResponse] = None


class OrderItem(BaseModel):
    ingredient_id: str
    quantity: float
    price_per_unit_paid: float
    total_price: float
    use_by_date: int


class OrderResponse(BaseModel):
    order_id: str
    business_id: Optional[str]
    items: Dict[str, "OrderItem"]
    total_cost: float
    order_placed_at: int
    expected_delivery: int
    status: str
    failure_reason: Optional[str] = None
    quote_id: Optional[str] = None


# IngredientDefinition (not a Pydantic model)
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
