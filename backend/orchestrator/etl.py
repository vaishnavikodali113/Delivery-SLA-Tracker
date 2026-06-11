import os
import sys
import uuid
from datetime import datetime
import sqlite3
import duckdb

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db import get_db_connection
from database.warehouse import get_warehouse_connection
from engine.dq_layer import DataQualityChecker
from engine.sla_engine import SLAEngine

def run_etl_pipeline():
    """Runs the ETL batch process from SQLite to DuckDB."""
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"[{datetime.now().isoformat()}] Starting ETL run {run_id}...")

    # Initialize engines
    dq_checker = DataQualityChecker(run_id)
    sla_engine = SLAEngine()

    # Connections
    oltp_conn = get_db_connection()
    olap_conn = get_warehouse_connection()

    try:
        # 1. Extract: Get all unique order IDs that have a 'DELIVERED' or 'CANCELLED' event
        oltp_cursor = oltp_conn.cursor()
        oltp_cursor.execute('''
            SELECT DISTINCT order_id 
            FROM order_events 
            WHERE event_type IN ('DELIVERED', 'CANCELLED')
        ''')
        completed_orders = [row['order_id'] for row in oltp_cursor.fetchall()]
        
        if not completed_orders:
            print("No completed orders found to process.")
            return {
                "run_id": run_id,
                "status": "success",
                "processed_count": 0,
                "dq_pass_count": 0,
                "dq_fail_count": 0,
                "breach_count": 0
            }

        print(f"Found {len(completed_orders)} completed orders in transactional database.")

        # 2. Track metrics
        dq_pass = 0
        dq_fail = 0
        breaches = 0

        # Mapping for breach reasons to dimension keys
        reason_key_map = {
            "No Breach": "NO_BREACH",
            "Weather Delay (Rain)": "WEATHER_RAIN",
            "Weather Delay (Storm)": "WEATHER_STORM",
            "Peak Demand Delay": "PEAK_DEMAND",
            "Kitchen Operational Delay": "KITCHEN_DELAY",
            "Rider Dispatch Delay": "RIDER_DISPATCH",
            "Order Incomplete": "INCOMPLETE"
        }

        # 3. Transform & Load loop
        for order_id in completed_orders:
            # Get all events for this order
            oltp_cursor.execute('''
                SELECT * FROM order_events WHERE order_id = ? ORDER BY timestamp ASC
            ''', (order_id,))
            events = [dict(row) for row in oltp_cursor.fetchall()]
            
            if not events:
                continue

            # Run Data Quality Checks
            is_valid = dq_checker.validate_order(order_id, events)
            dq_status = "PASS" if is_valid else "FAIL"
            
            if is_valid:
                dq_pass += 1
            else:
                dq_fail += 1

            # Run SLA Engine Calculations
            sla_result = sla_engine.calculate_sla(events)
            
            # Extract attributes
            placed_str = sla_result.get("placed_time")
            delivery_str = sla_result.get("delivery_time")
            
            if not placed_str or not delivery_str:
                # Can't calculate SLA because start or end is missing
                continue
                
            placed_dt = datetime.fromisoformat(placed_str)
            delivery_dt = datetime.fromisoformat(delivery_str)

            # Generate Date Key: YYYYMMDDHH
            date_key = int(placed_dt.strftime("%Y%m%d%H"))
            
            # Generate / Insert Date Dimension row
            is_weekend = placed_dt.weekday() >= 5
            day_name = placed_dt.strftime("%A")
            olap_conn.execute('''
                INSERT OR IGNORE INTO dim_dates (date_key, date, day_of_week, hour, is_weekend)
                VALUES (?, ?, ?, ?, ?)
            ''', (date_key, placed_dt.date(), day_name, placed_dt.hour, is_weekend))

            # Retrieve first event metadata for entity references
            first_event = events[0]
            customer_id = first_event.get("customer_id")
            restaurant_id = first_event.get("restaurant_id")
            rider_id = first_event.get("rider_id")

            # Determine breach reason key
            breach_reason = sla_result.get("breach_reason", "No Breach")
            breach_reason_key = reason_key_map.get(breach_reason, "INCOMPLETE")
            
            if sla_result.get("is_breached", False):
                breaches += 1

            # Upsert into Fact Table
            olap_conn.execute('''
                INSERT OR REPLACE INTO fact_orders (
                    order_key, order_id, customer_id, restaurant_id, rider_id, date_key,
                    placement_time, delivery_time, actual_duration_mins, target_duration_mins,
                    acceptance_delay_mins, prep_duration_mins, transit_duration_mins,
                    dispatch_delay_mins, is_breached, breach_reason_key, dq_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order_id, # order_key can simply be the order_id
                order_id,
                customer_id,
                restaurant_id,
                rider_id,
                date_key,
                placed_dt,
                delivery_dt,
                sla_result.get("total_duration_mins", 0.0),
                sla_result.get("target_duration_mins", 30.0),
                sla_result.get("acceptance_delay_mins", 0.0),
                sla_result.get("prep_duration_mins", 0.0),
                sla_result.get("transit_duration_mins", 0.0),
                sla_result.get("dispatch_delay_mins", 0.0),
                sla_result.get("is_breached", False),
                breach_reason_key,
                dq_status
            ))

        # Optimize query planner statistics in both databases
        try:
            olap_conn.execute("ANALYZE fact_orders;")
            oltp_cursor.execute("ANALYZE order_events;")
        except Exception as maint_err:
            print(f"[Maintenance Warning] Failed to update query stats: {maint_err}")

        olap_conn.commit()
        print(f"[{datetime.now().isoformat()}] ETL run completed successfully.")
        print(f"Processed: {len(completed_orders)} | DQ Pass: {dq_pass} | DQ Fail: {dq_fail} | Breaches: {breaches}")


        return {
            "run_id": run_id,
            "status": "success",
            "processed_count": len(completed_orders),
            "dq_pass_count": dq_pass,
            "dq_fail_count": dq_fail,
            "breach_count": breaches
        }

    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ETL pipeline failed with error: {e}")
        olap_conn.rollback()
        raise e
    finally:
        oltp_conn.close()
        olap_conn.close()

if __name__ == "__main__":
    run_etl_pipeline()
