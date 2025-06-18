# test_postgresql_direct.py
import psycopg2
import json
from sqlmodel import SQLModel, create_engine, Session
from database_models import Quote, Order

# Railway PostgreSQL connection string
DATABASE_URL = "postgresql://postgres:CCIeWPMHNnpHPvxMjNzTeCidnBOOQMuq@caboose.proxy.rlwy.net:33627/railway"

def test_postgresql_connection():
    """Test direct PostgreSQL connection using psycopg2"""

    print("Testing Direct PostgreSQL Connection")
    print("=" * 50)

    # Test 1: Basic connection test
    print("\n1. Testing basic PostgreSQL connection...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"PostgreSQL Version: {version[0]}")
        cur.close()
        conn.close()
        print("✓ Connection successful!")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return

    # Test 2: Create tables using SQLModel
    print("\n2. Creating tables using SQLModel...")
    try:
        engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        SQLModel.metadata.create_all(engine)
        print("✓ Tables created successfully!")
    except Exception as e:
        print(f"✗ Table creation failed: {e}")
        return

    # Test 3: Check table existence
    print("\n3. Checking table existence...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Check if tables exist
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('quotes', 'orders')
        """)
        tables = cur.fetchall()
        print(f"Found tables: {[table[0] for table in tables]}")

        # Get table structure
        for table_name in ['quotes', 'orders']:
            cur.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            print(f"\n{table_name} table structure:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")

        cur.close()
        conn.close()
        print("✓ Table check successful!")
    except Exception as e:
        print(f"✗ Table check failed: {e}")

    # Test 4: Test SQLModel session
    print("\n4. Testing SQLModel session...")
    try:
        with Session(engine) as session:
            # Try to query tables
            quote_count = session.query(Quote).count()
            order_count = session.query(Order).count()
            print(f"Quotes in database: {quote_count}")
            print(f"Orders in database: {order_count}")
        print("✓ SQLModel session test successful!")
    except Exception as e:
        print(f"✗ SQLModel session test failed: {e}")

    # Test 5: Reset tables
    print("\n5. Resetting tables...")
    try:
        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)
        print("✓ Tables reset successfully!")
    except Exception as e:
        print(f"✗ Table reset failed: {e}")

def test_database_operations():
    """Test basic database operations"""

    print("\n\nTesting Database Operations")
    print("=" * 50)

    try:
        engine = create_engine(DATABASE_URL, echo=False)

        # Test inserting a quote
        print("\n1. Testing quote insertion...")
        with Session(engine) as session:
            quote = Quote(
                quote_id="test-quote-001",
                ingredient_id="DARK-ROAST-BEANS-STD-KG",
                name="Dark Roast Beans",
                description="Premium dark roast coffee beans",
                unit_of_measure="kg",
                price_per_unit=15.99,
                total_price=159.90,
                currency="USD",
                available_stock=100.0,
                use_by_date=1735689600,  # Example timestamp
                price_valid_until=1735689600,
                delivery_time=86400,  # 24 hours in seconds
                created_at=1735603200
            )
            session.add(quote)
            session.commit()
            print("✓ Quote inserted successfully!")

            # Query the quote
            retrieved_quote = session.query(Quote).filter_by(quote_id="test-quote-001").first()
            if retrieved_quote:
                print(f"✓ Retrieved quote: {retrieved_quote.name} - ${retrieved_quote.total_price}")
            else:
                print("✗ Failed to retrieve quote")

        # Test inserting an order
        print("\n2. Testing order insertion...")
        with Session(engine) as session:
            order = Order(
                order_id="test-order-001",
                business_id="test-business-001",
                quote_id="test-quote-001",
                items={
                    "DARK-ROAST-BEANS-STD-KG": {
                        "ingredient_id": "DARK-ROAST-BEANS-STD-KG",
                        "quantity": 10.0,
                        "price_per_unit_paid": 15.99,
                        "total_price": 159.90,
                        "use_by_date": 1735689600
                    }
                },
                total_cost=159.90,
                order_placed_at=1735603200,
                expected_delivery=1735689600,
                status="confirmed"
            )
            session.add(order)
            session.commit()
            print("✓ Order inserted successfully!")

            # Query the order
            retrieved_order = session.query(Order).filter_by(order_id="test-order-001").first()
            if retrieved_order:
                print(f"✓ Retrieved order: {retrieved_order.order_id} - ${retrieved_order.total_cost}")
            else:
                print("✗ Failed to retrieve order")

        # Clean up test data
        # print("\n3. Cleaning up test data...")
        # with Session(engine) as session:
        #     session.query(Quote).filter_by(quote_id="test-quote-001").delete()
        #     session.query(Order).filter_by(order_id="test-order-001").delete()
        #     session.commit()
        #     print("✓ Test data cleaned up!")

    except Exception as e:
        print(f"✗ Database operations failed: {e}")

if __name__ == "__main__":
    # test_postgresql_connection()
    test_database_operations()