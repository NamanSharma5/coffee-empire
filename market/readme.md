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
