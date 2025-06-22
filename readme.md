# How to run

### Locally
`uvicorn api:app --host 0.0.0.0 --port 8080 --reload`

### Via Docker
if contained needs to be built from dockerfile in folder of command:
 `docker build -t devcon-market-api .`

`docker run -p 8080:8080 devcon-market-api:latest`

# Market Pricing System

## Overview
The market system implements a flexible pricing architecture that supports multiple pricing strategies through a service-based approach. The system is designed to be extensible, allowing for easy addition of new pricing strategies while maintaining a consistent interface.

## Pricing Strategies

### 1. Default Pricing Service
The basic pricing service that uses the base price defined for each ingredient:
- Returns the base price per unit
- No discounts applied
- Price validity period of one day (24 hours)

### 2. Volume Discount Pricing Service
A sophisticated service that implements tiered volume discounts:

#### Dark Roast Beans
- 10% discount for orders ≥ 10 kg
- 20% discount for orders ≥ 25 kg
- 30% discount for orders ≥ 50 kg

#### Light Roast Beans
- 5% discount for orders ≥ 10 kg
- 15% discount for orders ≥ 20 kg

### 3. Demand-Based Pricing Service
A dynamic pricing service that adjusts prices based on quote demand within a configurable time window. This service combines with volume discounts to provide comprehensive pricing strategies.

#### How It Works
The demand-based pricing system tracks quote requests for each ingredient within a sliding time window and automatically increases prices when demand exceeds predefined thresholds.

#### Configuration Parameters
- **Time Window**: 4 hours (future: possibly configurable per ingredient)
- **Quote Tracking**: All price quote requests are automatically recorded
- **Price Adjustments**: Applied multiplicatively on top of volume discounts

#### Current Settings

**Dark Roast Beans (DARK-ROAST-BEANS-STD-KG)**
- Quote threshold: 5 quotes within 4 hours
- Price hike: 5% increase per threshold reached
- Example: If 15 quotes are made within 4 hours, price increases by 15% (3 thresholds × 5%)

**Light Roast Beans (LIGHT-ROAST-BEANS-STD-KG)**
- Quote threshold: 3 quotes within 4 hours
- Price hike: 8% increase per threshold reached
- Example: If 9 quotes are made within 4 hours, price increases by 24% (3 thresholds × 8%)

#### Pricing Calculation Flow
1. **Volume Discount**: First applies tiered volume discounts based on order quantity
2. **Demand Adjustment**: Then applies demand-based price increases based on recent quote activity
3. **Final Price**: Combines both strategies for optimal market-responsive pricing

#### Benefits
- **Market Responsiveness**: Automatically adjusts to increased demand
- **Revenue Optimization**: Captures additional value during high-demand periods
- **Composition**: Works seamlessly with existing volume discount strategies
- **Configurable**: Easy to adjust thresholds and hike percentages per ingredient

## Pricing Flow

### Quote Generation
1. Validates ingredient existence
2. Retrieves price from configured pricing service
3. Checks stock availability
4. Generates quote with:
   - Calculated price
   - Validity period
   - Stock information
   - Delivery time

### Purchase Process
1. Price determination:
   - Uses cached quote if quote_id provided
   - Otherwise gets fresh price from pricing service (plan to make this more expensive)
2. Validates price against maximum acceptable price
3. Checks stock availability
4. Creates order with final price

## Technical Details

- All prices are stored in USD
- Financial calculations are rounded to 2 decimal places
- Price quotes are valid for 24 hours from generation
- System implements the `PricingService` abstract base class for extensibility
- New pricing strategies can be added by implementing the `get_price()` method

## Database Management

The system includes database functionality to persist quotes and orders. The database uses SQLModel (built on SQLAlchemy) with PostgreSQL hosted on Railway.

### Database Models

#### Quote Table
Stores each generated quote with metadata:
- `quote_id`: Primary key
- `ingredient_id`: Reference to ingredient
- `name`, `description`, `unit_of_measure`: Ingredient details
- `price_per_unit`, `total_price`, `currency`: Pricing information
- `available_stock`, `use_by_date`: Stock information
- `price_valid_until`, `delivery_time`: Timing information
- `created_at`: Timestamp when quote was created

#### Order Table
Persists each order, optionally linked to a quote:
- `order_id`: Primary key
- `business_id`: Optional business identifier
- `quote_id`: Optional reference to original quote
- `items`: JSON mapping of ingredient_id → OrderItem dict
- `total_cost`: Total order cost
- `order_placed_at`: Timestamp when order was placed
- `expected_delivery`: Expected delivery timestamp
- `status`: Order status
- `failure_reason`: Optional failure reason

### Usage Examples

#### Direct PostgreSQL Testing
```bash
# Test direct PostgreSQL connection and operations
python test_postgresql_direct.py

#### Environment Variables
You can set the API base URL using environment variables:
```bash
export API_BASE_URL="http://your-api-server:8080"
python test_database.py
```