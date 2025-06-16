from models import IngredientDefinition
from typing import Dict

# CLOCK_URL = "https://coffee-empire-clock.vercel.app"

ONE_DAY = 24
ONE_WEEK = ONE_DAY * 7

EXPECTED_DELIVERY = ONE_DAY

## espresso beans, dark roast beans, light roast beans, whole milk, almond milk, cups, fresh fruit, pre-packaged sandwiches

# In‐memory “database” of ingredients
_INGREDIENTS: Dict[str, IngredientDefinition] = {
    "DARK-ROAST-BEANS-STD-KG": IngredientDefinition(
        ingredient_id="DARK-ROAST-BEANS-STD-KG",
        name="Standard Robusta Dark Roast Coffee Beans",
        description="Basic dark roast robusta beans, suitable for general use.",
        unit_of_measure="kg",
        currency="USD",
        base_price=8.00, # price used by default pricing service
        use_by_date=ONE_WEEK,
        stock=250,
    ),
    "LIGHT-ROAST-BEANS-STD-KG": IngredientDefinition(
        ingredient_id="LIGHT-ROAST-BEANS-STD-KG",
        name="Premium Robusta Light Roast Coffee Beans",
        description="Premium light roast robusta beans, suitable for premium use.",
        unit_of_measure="kg",
        currency="USD",
        base_price=10.00, # price used by default pricing service
        use_by_date=ONE_WEEK,
        stock=250,
    ),
}

VOLUME_DISCOUNT_TIERS: Dict[str, list] = {
    "DARK-ROAST-BEANS-STD-KG": [
        (10.0, 0.10),   # 10% off for ≥10 kg
        (25.0, 0.20),   # 20% off for ≥25 kg
        (50.0, 0.30),   # 30% off for ≥50 kg
    ],
    "LIGHT-ROAST-BEANS-STD-KG": [
        (10.0, 0.05),    # 5% off for ≥5 kg
        (20.0, 0.15),   # 15% off for ≥20 kg
    ],
}