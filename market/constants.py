from models import IngredientDefinition
from typing import Dict

CLOCK_URL = "http://127.0.0.1:8000"

ONE_DAY = 24

# In‐memory “database” of ingredients
_INGREDIENTS: Dict[str, IngredientDefinition] = {
    "COFB-ROBUSTA-STD-KG": IngredientDefinition(
        ingredient_id="COFB-ROBUSTA-STD-KG",
        name="Standard Robusta Coffee Beans",
        description="Basic robusta beans, suitable for general use.",
        unit_of_measure="kg",
        currency="USD",
        base_price=8.50,  # $8.50 per kg
        use_by_date=ONE_DAY,
        stock=250.75,  # 250.75 kg in stock
    )
}
