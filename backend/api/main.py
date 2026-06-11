from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
import sqlite3
import duckdb

# Ensure backend directory is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db import init_db, get_db_connection
from database.warehouse import get_warehouse_connection, init_warehouse
from simulator.order_simulator import OrderSimulator, CUSTOMERS, RESTAURANTS, RIDERS
from orchestrator.etl import run_etl_pipeline

app = FastAPI(
    title="Delivery SLA Tracker API",
    description="Backend service for tracking, simulating, and auditing delivery SLAs.",
    version="1.0.0"
)

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global simulator instance
simulator = OrderSimulator()

# Pydantic models for request bodies
class SimulatorConfig(BaseModel):
    weather: str | None = None
    order_rate: float | None = None
    speed_multiplier: float | None = None

# --- AUTOMATED SCHEDULER STATE ---
auto_etl_enabled = True
scheduler_thread = None

def _auto_etl_loop():
    """Background loop to run the ETL process every 10 seconds."""
    global auto_etl_enabled
    while True:
        if auto_etl_enabled:
            try:
                run_etl_pipeline()
            except Exception as e:
                print(f"[Auto-ETL Scheduler] Error: {e}")
        time.sleep(10)

import time
import threading

@app.on_event("startup")
async def startup_event():
    # Initialize databases
    init_db()
    init_warehouse()
    
    # Start the simulator automatically with standard settings
    simulator.set_config(weather="Clear", order_rate=0.5, speed_multiplier=60.0)
    simulator.start()
    
    # Start the automated ETL background scheduler thread
    global scheduler_thread
    scheduler_thread = threading.Thread(target=_auto_etl_loop, daemon=True)
    scheduler_thread.start()
    print("Auto-ETL background scheduler thread started.")

@app.on_event("shutdown")
async def shutdown_event():
    simulator.stop()

@app.get("/")
def read_root():
    return {
        "status": "online",
        "simulator_running": simulator.running,
        "auto_etl_enabled": auto_etl_enabled,
        "current_weather": simulator.weather,
        "order_rate": simulator.order_rate,
        "speed_multiplier": simulator.speed_multiplier,
        "simulation_time": simulator.simulation_time.isoformat()
    }

# --- SIMULATOR CONTROLS ---

@app.post("/api/simulator/start")
def start_simulator():
    if simulator.running:
        return {"message": "Simulator is already running."}
    simulator.start()
    return {"message": "Simulator started."}

@app.post("/api/simulator/stop")
def stop_simulator():
    if not simulator.running:
        return {"message": "Simulator is already stopped."}
    simulator.stop()
    return {"message": "Simulator stopped."}

@app.post("/api/simulator/config")
def update_config(config: SimulatorConfig):
    simulator.set_config(
        weather=config.weather,
        order_rate=config.order_rate,
        speed_multiplier=config.speed_multiplier
    )
    return {
        "message": "Configuration updated.",
        "weather": simulator.weather,
        "order_rate": simulator.order_rate,
        "speed_multiplier": simulator.speed_multiplier
    }

@app.get("/api/simulator/status")
def get_simulator_status():
    return {
        "running": simulator.running,
        "weather": simulator.weather,
        "order_rate": simulator.order_rate,
        "speed_multiplier": simulator.speed_multiplier,
        "active_order_count": simulator.active_order_count,
        "orders_scheduled": len(simulator.scheduled_events),
        "total_orders_generated": simulator.order_counter,
        "simulation_time": simulator.simulation_time.isoformat()
    }

@app.post("/api/scheduler/toggle")
def toggle_scheduler():
    global auto_etl_enabled
    auto_etl_enabled = not auto_etl_enabled
    return {
        "message": "Scheduler toggled",
        "auto_etl_enabled": auto_etl_enabled
    }

@app.get("/api/scheduler/status")
def get_scheduler_status():
    global auto_etl_enabled
    return {
        "auto_etl_enabled": auto_etl_enabled
    }

@app.post("/api/database/reset")
def reset_database():
    global auto_etl_enabled
    # Temporarily pause scheduler thread during delete
    prev_state = auto_etl_enabled
    auto_etl_enabled = False
    
    # Give active threads 1 second to release database locks
    time.sleep(1.0)
    
    # Stop simulator to freeze event emissions
    simulator.stop()
    
    try:
        from database.db import DB_PATH
        from database.warehouse import WAREHOUSE_PATH
        
        # Delete local DB files if they exist
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        if os.path.exists(WAREHOUSE_PATH):
            os.remove(WAREHOUSE_PATH)
            
        # Re-initialize clean schemas
        init_db()
        init_warehouse()
        
        # Reset simulator tracking variables
        simulator.order_counter = 0
        with simulator.lock:
            simulator.scheduled_events = []
            simulator.active_order_count = 0
            
        # Restart simulator
        simulator.start()
        
        # Restore scheduler previous running state
        auto_etl_enabled = prev_state
        return {"message": "Databases wiped and re-initialized successfully."}
        
    except Exception as e:
        auto_etl_enabled = prev_state
        # Restart simulator just in case
        simulator.start()
        raise HTTPException(status_code=500, detail=f"Database reset failed: {str(e)}")


@app.get("/api/events")
def get_events(limit: int = 100):
    """Fetch recent order events from the SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM order_events ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    events = [dict(row) for row in rows]
    return events

# --- ETL & ORCHESTRATION ---

@app.post("/api/orchestrator/run")
def trigger_etl(background_tasks: BackgroundTasks):
    """Trigger the ETL batch process. Runs in foreground for quick updates but handles failures."""
    try:
        stats = run_etl_pipeline()
        return {
            "message": "ETL pipeline completed successfully",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETL pipeline run failed: {str(e)}")

# --- ANALYTICAL DASHBOARD ---

@app.get("/api/dashboard/summary")
def get_dashboard_summary():
    """Fetch high-level KPI card metrics from DuckDB warehouse."""
    olap_conn = get_warehouse_connection()
    
    try:
        # Metrics for clean orders (passing DQ checks)
        metrics = olap_conn.execute('''
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN is_breached = TRUE THEN 1 ELSE 0 END) as breached_orders,
                AVG(actual_duration_mins) as avg_duration,
                AVG(prep_duration_mins) as avg_prep,
                AVG(transit_duration_mins) as avg_transit,
                AVG(dispatch_delay_mins) as avg_dispatch
            FROM fact_orders
            WHERE dq_status = 'PASS'
        ''').fetchone()
        
        # Overall counts (including DQ failures)
        all_orders_count = olap_conn.execute("SELECT COUNT(*) FROM fact_orders").fetchone()[0]
        dq_fail_count = olap_conn.execute("SELECT COUNT(*) FROM fact_orders WHERE dq_status = 'FAIL'").fetchone()[0]

        if not metrics or metrics[0] == 0:
            return {
                "total_orders": 0,
                "compliance_rate": 100.0,
                "avg_duration_mins": 0.0,
                "avg_prep_mins": 0.0,
                "avg_transit_mins": 0.0,
                "avg_dispatch_mins": 0.0,
                "dq_fail_count": dq_fail_count
            }

        total_clean = metrics[0]
        breached = metrics[1] or 0
        compliance_rate = ((total_clean - breached) / total_clean) * 100.0

        return {
            "total_orders": all_orders_count,
            "total_clean_orders": total_clean,
            "compliance_rate": round(compliance_rate, 2),
            "avg_duration_mins": round(metrics[2] or 0.0, 2),
            "avg_prep_mins": round(metrics[3] or 0.0, 2),
            "avg_transit_mins": round(metrics[4] or 0.0, 2),
            "avg_dispatch_mins": round(metrics[5] or 0.0, 2),
            "dq_fail_count": dq_fail_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query warehouse metrics: {e}")
    finally:
        olap_conn.close()

@app.get("/api/dashboard/breaches")
def get_breach_breakdown():
    """Fetch breakdown of SLA breaches by reason category."""
    olap_conn = get_warehouse_connection()
    try:
        rows = olap_conn.execute('''
            SELECT 
                d.reason_category,
                COUNT(f.order_id) as breach_count
            FROM fact_orders f
            JOIN dim_breach_reasons d ON f.breach_reason_key = d.breach_reason_key
            WHERE f.is_breached = TRUE AND f.dq_status = 'PASS'
            GROUP BY d.reason_category
            ORDER BY breach_count DESC
        ''').fetchall()
        
        breakdown = [{"category": row[0], "breach_count": row[1]} for row in rows]
        return breakdown
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query breach categories: {e}")
    finally:
        olap_conn.close()

@app.get("/api/dashboard/trends")
def get_compliance_trends():
    """Fetch compliance rate grouped hourly."""
    olap_conn = get_warehouse_connection()
    try:
        rows = olap_conn.execute('''
            SELECT 
                d.date,
                d.hour,
                COUNT(f.order_id) as total_orders,
                SUM(CASE WHEN f.is_breached = TRUE THEN 1 ELSE 0 END) as breached_orders
            FROM fact_orders f
            JOIN dim_dates d ON f.date_key = d.date_key
            WHERE f.dq_status = 'PASS'
            GROUP BY d.date, d.hour
            ORDER BY d.date ASC, d.hour ASC
            LIMIT 24
        ''').fetchall()
        
        trends = []
        for r in rows:
            total = r[2]
            breached = r[3] or 0
            compliance = ((total - breached) / total) * 100 if total > 0 else 100.0
            trends.append({
                "time_label": f"{r[0]} {r[1]:02d}:00",
                "total_orders": total,
                "breached_orders": breached,
                "compliance_rate": round(compliance, 2)
            })
            
        return trends
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query compliance trends: {e}")
    finally:
        olap_conn.close()

@app.get("/api/dashboard/data-quality")
def get_dq_summary():
    """Fetch recent data quality issues from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Overall statistics
        cursor.execute('''
            SELECT 
                rule_name,
                SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as pass_count,
                SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) as fail_count
            FROM dq_logs
            GROUP BY rule_name
        ''')
        rules = [dict(row) for row in cursor.fetchall()]

        # Recent 25 failures
        cursor.execute('''
            SELECT order_id, rule_name, error_message, timestamp
            FROM dq_logs
            WHERE status = 'FAIL'
            ORDER BY timestamp DESC
            LIMIT 25
        ''')
        failures = [dict(row) for row in cursor.fetchall()]
        
        return {
            "rule_metrics": rules,
            "recent_failures": failures
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query DQ logs: {e}")
    finally:
        conn.close()

@app.get("/api/dashboard/orders")
def get_fact_orders_list(limit: int = 50):
    """Fetch detailed orders from DuckDB warehouse."""
    olap_conn = get_warehouse_connection()
    try:
        rows = olap_conn.execute('''
            SELECT 
                f.order_id,
                c.name as customer_name,
                r.name as restaurant_name,
                ri.name as rider_name,
                f.placement_time,
                f.actual_duration_mins,
                f.is_breached,
                db.reason_category,
                f.dq_status
            FROM fact_orders f
            JOIN dim_customers c ON f.customer_id = c.customer_id
            JOIN dim_restaurants r ON f.restaurant_id = r.restaurant_id
            JOIN dim_riders ri ON f.rider_id = ri.rider_id
            JOIN dim_breach_reasons db ON f.breach_reason_key = db.breach_reason_key
            ORDER BY f.placement_time DESC
            LIMIT ?
        ''', (limit,)).fetchall()
        
        orders = []
        for row in rows:
            orders.append({
                "order_id": row[0],
                "customer": row[1],
                "restaurant": row[2],
                "rider": row[3],
                "placement_time": row[4].isoformat() if row[4] else None,
                "duration": round(row[5], 2) if row[5] is not None else None,
                "is_breached": row[6],
                "breach_reason": row[7],
                "dq_status": row[8]
            })
        return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query orders list: {e}")
    finally:
        olap_conn.close()

@app.get("/api/dashboard/recommendations")
def get_operational_recommendations():
    """Generates actionable recommendations based on SLA breach distributions."""
    olap_conn = get_warehouse_connection()
    try:
        # Get breach count per category
        rows = olap_conn.execute('''
            SELECT 
                d.reason_category,
                COUNT(f.order_id) as count
            FROM fact_orders f
            JOIN dim_breach_reasons d ON f.breach_reason_key = d.breach_reason_key
            WHERE f.is_breached = TRUE AND f.dq_status = 'PASS'
            GROUP BY d.reason_category
            ORDER BY count DESC
        ''').fetchall()
        
        recs = []
        
        if not rows:
            recs.append({
                "severity": "SUCCESS",
                "title": "Optimal Delivery Performance",
                "recommendation": "All operations running within targets. No significant bottlenecks detected.",
                "action": "Maintain active dispatch density and standard routing parameters."
            })
            return recs

        # Identify leading bottleneck
        top_reason = rows[0][0]
        top_count = rows[0][1]

        if "Weather Delay" in top_reason:
            recs.append({
                "severity": "WARNING",
                "title": f"Weather Congestion ({top_count} Breaches)",
                "recommendation": "Storm/Rain is slowing transit. Estimated courier travel time is inflated by 1.5x-2.5x.",
                "action": "Trigger dynamic buffer addition (+10m) to customer promised delivery time and enable driver safety speed buffers."
            })
        elif "Peak Demand" in top_reason:
            recs.append({
                "severity": "CRITICAL",
                "title": f"Courier Shortage / Peak Backlog ({top_count} Breaches)",
                "recommendation": "Riders are taking too long to accept dispatches due to high order concurrency.",
                "action": "Raise active peak courier payouts by 1.3x in high-load regions and implement strict restaurant throttling."
            })
        elif "Kitchen" in top_reason:
            recs.append({
                "severity": "DANGER",
                "title": f"Kitchen Preparation Congestion ({top_count} Breaches)",
                "recommendation": "Restaurants are taking longer than 15 minutes to prepare food, causing riders to sit idle at store fronts.",
                "action": "Temporarily extend preparation buffer times for partner restaurants and snooze automated rider assignment by +5m."
            })
        elif "Rider Dispatch" in top_reason:
            recs.append({
                "severity": "WARNING",
                "title": f"Rider Arrival Offsets ({top_count} Breaches)",
                "recommendation": "Riders are taking too long to arrive at the restaurants after accepting the delivery task.",
                "action": "Audit rider routing offsets. Delay the courier assignment trigger until the food prep is 70% complete."
            })
            
        # Add a secondary recommendation based on general load
        metrics = olap_conn.execute("SELECT COUNT(*), SUM(CASE WHEN is_breached = TRUE THEN 1 ELSE 0 END) FROM fact_orders WHERE dq_status = 'PASS'").fetchone()
        if metrics and metrics[0] > 0:
            total_clean = metrics[0]
            breached = metrics[1] or 0
            compliance = ((total_clean - breached) / total_clean) * 100
            
            if compliance < 80.0:
                recs.append({
                    "severity": "CRITICAL",
                    "title": "Low Overall SLA Compliance",
                    "recommendation": f"SLA compliance is currently at {round(compliance,1)}% (below the 85% business standard).",
                    "action": "Scale down platform marketing or temporarily restrict deliveries to core regions until operations stabilize."
                })
            elif compliance >= 95.0:
                recs.append({
                    "severity": "SUCCESS",
                    "title": "Exceptional SLA Score",
                    "recommendation": f"System is delivering at {round(compliance,1)}% SLA efficiency.",
                    "action": "Increase order volume capacity caps or consider lowering courier incentive baselines."
                })
                
        return recs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query recommendations: {e}")
    finally:
        olap_conn.close()

