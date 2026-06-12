import duckdb
import os
import sys

# Path to the DuckDB analytical file
WAREHOUSE_PATH = os.environ.get("DUCKDB_PATH")
if not WAREHOUSE_PATH:
    WAREHOUSE_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "delivery_warehouse.db")
    )
if os.environ.get("TESTING") == "true":
    WAREHOUSE_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "delivery_warehouse_test.db")
    )
# Ensure directory for DuckDB warehouse exists
warehouse_dir = os.path.dirname(WAREHOUSE_PATH)
if warehouse_dir:
    os.makedirs(warehouse_dir, exist_ok=True)


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from simulator.order_simulator import CUSTOMERS, RESTAURANTS, RIDERS

def get_warehouse_connection():
    """Returns a connection to the DuckDB warehouse database."""
    return duckdb.connect(WAREHOUSE_PATH)

def init_warehouse():
    """Creates the Star Schema tables in the DuckDB warehouse."""
    conn = get_warehouse_connection()
    
    # 1. Create Dimensions
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dim_customers (
            customer_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            city VARCHAR
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dim_restaurants (
            restaurant_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            cuisine VARCHAR,
            city VARCHAR
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dim_riders (
            rider_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            vehicle_type VARCHAR
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dim_dates (
            date_key BIGINT PRIMARY KEY,
            date DATE,
            day_of_week VARCHAR,
            hour INTEGER,
            is_weekend BOOLEAN
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dim_breach_reasons (
            breach_reason_key VARCHAR PRIMARY KEY,
            reason_category VARCHAR,
            description VARCHAR
        )
    ''')
    
    # 2. Create Fact Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS fact_orders (
            order_key VARCHAR PRIMARY KEY,
            order_id VARCHAR,
            customer_id VARCHAR,
            restaurant_id VARCHAR,
            rider_id VARCHAR,
            date_key BIGINT,
            placement_time TIMESTAMP,
            delivery_time TIMESTAMP,
            actual_duration_mins DOUBLE,
            target_duration_mins DOUBLE,
            acceptance_delay_mins DOUBLE,
            prep_duration_mins DOUBLE,
            transit_duration_mins DOUBLE,
            dispatch_delay_mins DOUBLE,
            is_breached BOOLEAN,
            breach_reason_key VARCHAR,
            dq_status VARCHAR
        )
    ''')

    # Create Indexes for Star Schema joins
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_orders_customer ON fact_orders(customer_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_orders_restaurant ON fact_orders(restaurant_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_orders_rider ON fact_orders(rider_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_orders_date ON fact_orders(date_key)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_orders_breach ON fact_orders(breach_reason_key)')

    
    # 3. Pre-populate dimensions with reference data
    # Pre-populate customers
    for c in CUSTOMERS:
        conn.execute('''
            INSERT OR IGNORE INTO dim_customers (customer_id, name, city)
            VALUES (?, ?, ?)
        ''', (c["id"], c["name"], c["city"]))
        
    # Pre-populate restaurants
    for r in RESTAURANTS:
        conn.execute('''
            INSERT OR IGNORE INTO dim_restaurants (restaurant_id, name, cuisine, city)
            VALUES (?, ?, ?, ?)
        ''', (r["id"], r["name"], r["cuisine"], r["city"]))
        
    # Pre-populate riders
    for r in RIDERS:
        conn.execute('''
            INSERT OR IGNORE INTO dim_riders (rider_id, name, vehicle_type)
            VALUES (?, ?, ?)
        ''', (r["id"], r["name"], r["vehicle"]))
        
    # Pre-populate static SLA Breach Reasons
    breach_reasons = [
        ("NO_BREACH", "No Breach", "The delivery was completed successfully within the SLA target."),
        ("WEATHER_RAIN", "Weather Delay (Rain)", "SLA breached due to slow transit speeds caused by rain."),
        ("WEATHER_STORM", "Weather Delay (Storm)", "SLA breached due to severe transit speeds reduction caused by storm conditions."),
        ("PEAK_DEMAND", "Peak Demand Delay", "SLA breached due to low rider availability and high order backlog."),
        ("KITCHEN_DELAY", "Kitchen Operational Delay", "SLA breached due to delays in food preparation at the restaurant."),
        ("RIDER_DISPATCH", "Rider Dispatch Delay", "SLA breached due to delays in rider assignment or arrival at the restaurant."),
        ("INCOMPLETE", "Order Incomplete", "The order was cancelled or did not reach final delivery status.")
    ]
    
    for br_key, category, desc in breach_reasons:
        conn.execute('''
            INSERT OR IGNORE INTO dim_breach_reasons (breach_reason_key, reason_category, description)
            VALUES (?, ?, ?)
        ''', (br_key, category, desc))
        
    conn.commit()
    conn.close()
    print(f"DuckDB Star Schema initialized at: {WAREHOUSE_PATH}")

if __name__ == "__main__":
    init_warehouse()
