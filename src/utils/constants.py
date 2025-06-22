from src.models.api_models import IngredientDefinition
from typing import Dict

# CLOCK_URL = "https://coffee-empire-clock.vercel.app"

ONE_DAY = 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4

EXPECTED_DELIVERY = ONE_DAY
UNLIMITED_STOCK = 100000
QUOTE_CLEANUP_THRESHOLD = 1000

# In‐memory "database" of ingredients
_INGREDIENTS: Dict[str, IngredientDefinition] = {
    "espresso_beans": IngredientDefinition(
        ingredient_id="espresso_beans",
        name="Premium Espresso Coffee Beans",
        description="High-quality arabica beans specifically roasted for espresso, with rich crema and balanced flavor profile.",
        unit_of_measure="kg",
        currency="USD",
        base_price=12.50,
        use_by_date=ONE_WEEK,
        stock=UNLIMITED_STOCK,
    ),
    "dark_roast_beans": IngredientDefinition(
        ingredient_id="dark_roast_beans",
        name="Standard Robusta Dark Roast Coffee Beans",
        description="Basic dark roast robusta beans, suitable for general use with bold, full-bodied flavor.",
        unit_of_measure="kg",
        currency="USD",
        base_price=8.00,
        use_by_date=ONE_WEEK,
        stock=UNLIMITED_STOCK,
    ),
    "light_roast_beans": IngredientDefinition(
        ingredient_id="light_roast_beans",
        name="Premium Robusta Light Roast Coffee Beans",
        description="Premium light roast robusta beans, suitable for premium use with bright, acidic notes.",
        unit_of_measure="kg",
        currency="USD",
        base_price=10.00,
        use_by_date=ONE_WEEK,
        stock=UNLIMITED_STOCK,
    ),
    "whole_milk": IngredientDefinition(
        ingredient_id="whole_milk",
        name="Fresh Whole Milk",
        description="Fresh whole milk with 3.25% fat content, perfect for lattes and cappuccinos.",
        unit_of_measure="L",
        currency="USD",
        base_price=2.50,
        use_by_date=ONE_DAY * 3,
        stock=UNLIMITED_STOCK,
    ),
    "almond_milk": IngredientDefinition(
        ingredient_id="almond_milk",
        name="Unsweetened Almond Milk",
        description="Creamy unsweetened almond milk, dairy-free alternative for specialty drinks.",
        unit_of_measure="L",
        currency="USD",
        base_price=4.00,
        use_by_date=ONE_DAY * 7,
        stock=UNLIMITED_STOCK,
    ),
    "cups": IngredientDefinition(
        ingredient_id="cups",
        name="Disposable Coffee Cups",
        description="12oz disposable paper cups with lids, suitable for hot beverages.",
        unit_of_measure="unit",
        currency="USD",
        base_price=0.10,
        use_by_date=ONE_MONTH,
        stock=UNLIMITED_STOCK,
    ),
    "fresh_fruit": IngredientDefinition(
        ingredient_id="fresh_fruit",
        name="Assorted Fresh Fruit",
        description="Seasonal fresh fruit selection including berries, citrus, and tropical fruits for smoothies and garnishes.",
        unit_of_measure="kg",
        currency="USD",
        base_price=7.00,
        use_by_date=ONE_DAY * 2,
        stock=UNLIMITED_STOCK,
    ),
    "pre-packaged_sandwiches": IngredientDefinition(
        ingredient_id="pre_packaged_sandwiches",
        name="Pre-packaged Gourmet Sandwiches",
        description="Fresh pre-packaged sandwiches with premium ingredients, various fillings available.",
        unit_of_measure="unit",
        currency="USD",
        base_price=1,
        use_by_date=ONE_DAY * 3,
        stock=UNLIMITED_STOCK,
    ),
}

VOLUME_DISCOUNT_TIERS: Dict[str, list] = {
    "espresso_beans": [
        (5.0, 0.08),    # 8% off for ≥5 kg
        (15.0, 0.15),   # 15% off for ≥15 kg
        (30.0, 0.25),   # 25% off for ≥30 kg
    ],
    "dark_roast_beans": [
        (10.0, 0.10),   # 10% off for ≥10 kg
        (25.0, 0.20),   # 20% off for ≥25 kg
        (50.0, 0.30),   # 30% off for ≥50 kg
    ],
    "light_roast_beans": [
        (10.0, 0.05),   # 5% off for ≥10 kg
        (20.0, 0.15),   # 15% off for ≥20 kg
        (40.0, 0.25),   # 25% off for ≥40 kg
    ],
    "whole_milk": [
        (20.0, 0.05),   # 5% off for ≥20 L
        (50.0, 0.12),   # 12% off for ≥50 L
        (100.0, 0.20),  # 20% off for ≥100 L
    ],
    "almond_milk": [
        (15.0, 0.08),   # 8% off for ≥15 L
        (30.0, 0.15),   # 15% off for ≥30 L
        (60.0, 0.25),   # 25% off for ≥60 L
    ],
    "cups": [
        (5.0, 0.10),    # 10% off for ≥5 packs
        (15.0, 0.20),   # 20% off for ≥15 packs
        (30.0, 0.30),   # 30% off for ≥30 packs
    ],
    "fresh_fruit": [
        (10.0, 0.05),   # 5% off for ≥10 kg
        (25.0, 0.12),   # 12% off for ≥25 kg
        (50.0, 0.20),   # 20% off for ≥50 kg
    ],
    "pre_packaged_sandwiches": [
        (20.0, 0.08),   # 8% off for ≥20 units
        (50.0, 0.15),   # 15% off for ≥50 units
        (100.0, 0.25),  # 25% off for ≥100 units
    ],
}

# Demand-based pricing parameters
DEMAND_WINDOW_HOURS = 4
DEMAND_PRICE_HIKES = {
    "espresso_beans": {
        "quote_threshold": 3,
        "price_hike_percent": 0.10,
    },
    "dark_roast_beans": {
        "quote_threshold": 5,
        "price_hike_percent": 0.05,
    },
    "light_roast_beans": {
        "quote_threshold": 3,
        "price_hike_percent": 0.08,
    },
    "whole_milk": {
        "quote_threshold": 8,
        "price_hike_percent": 0.06,
    },
    "almond_milk": {
        "quote_threshold": 5,
        "price_hike_percent": 0.08,
    },
    "cups": {
        "quote_threshold": 10,
        "price_hike_percent": 0.04,
    },
    "fresh_fruit": {
        "quote_threshold": 6,
        "price_hike_percent": 0.12,
    },
    "pre_packaged_sandwiches": {
        "quote_threshold": 15,
        "price_hike_percent": 0.07,
    },
}