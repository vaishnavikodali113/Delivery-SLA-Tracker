import pytest
from datetime import datetime, timedelta
import os
import sys

# Isolate databases during testing to prevent locking issues
os.environ["TESTING"] = "true"


# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.dq_layer import DataQualityChecker
from engine.sla_engine import SLAEngine
from database.db import init_db

# Initialize the db for testing log queries (needed since DQ Checker writes log to SQL DB)
@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()

def test_dq_valid_sequence():
    checker = DataQualityChecker(run_id="test_run_1")
    t0 = datetime(2026, 6, 11, 12, 0, 0)
    
    events = [
        {"order_id": "ORD_TEST_01", "event_type": "ORDER_PLACED", "timestamp": t0.isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_01", "event_type": "ORDER_ACCEPTED", "timestamp": (t0 + timedelta(minutes=2)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_01", "event_type": "FOOD_PREPARING", "timestamp": (t0 + timedelta(minutes=3)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_01", "event_type": "RIDER_ARRIVED_AT_STORE", "timestamp": (t0 + timedelta(minutes=7)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_01", "event_type": "ORDER_PICKED_UP", "timestamp": (t0 + timedelta(minutes=10)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_01", "event_type": "DELIVERED", "timestamp": (t0 + timedelta(minutes=25)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"}
    ]
    
    assert checker.validate_order("ORD_TEST_01", events) == True

def test_dq_invalid_chronology():
    checker = DataQualityChecker(run_id="test_run_2")
    t0 = datetime(2026, 6, 11, 12, 0, 0)
    
    # RIDER_ARRIVED_AT_STORE timestamp is earlier than ORDER_PLACED
    events = [
        {"order_id": "ORD_TEST_02", "event_type": "ORDER_PLACED", "timestamp": t0.isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_02", "event_type": "ORDER_ACCEPTED", "timestamp": (t0 + timedelta(minutes=2)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_02", "event_type": "RIDER_ARRIVED_AT_STORE", "timestamp": (t0 - timedelta(minutes=5)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_02", "event_type": "DELIVERED", "timestamp": (t0 + timedelta(minutes=25)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"}
    ]
    
    assert checker.validate_order("ORD_TEST_02", events) == False

def test_dq_duplicate_events():
    checker = DataQualityChecker(run_id="test_run_3")
    t0 = datetime(2026, 6, 11, 12, 0, 0)
    
    # Two ORDER_PLACED events
    events = [
        {"order_id": "ORD_TEST_03", "event_type": "ORDER_PLACED", "timestamp": t0.isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_03", "event_type": "ORDER_PLACED", "timestamp": (t0 + timedelta(seconds=5)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_03", "event_type": "DELIVERED", "timestamp": (t0 + timedelta(minutes=25)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"}
    ]
    
    assert checker.validate_order("ORD_TEST_03", events) == False

def test_dq_state_transition_violation():
    checker = DataQualityChecker(run_id="test_run_4")
    t0 = datetime(2026, 6, 11, 12, 0, 0)
    
    # ORDER_PICKED_UP happens after DELIVERED in flow index (even though timestamps are sequential)
    # i.e., delivered then picked up (which doesn't make sense chronologically but let's test transition logic)
    events = [
        {"order_id": "ORD_TEST_04", "event_type": "ORDER_PLACED", "timestamp": t0.isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_04", "event_type": "DELIVERED", "timestamp": (t0 + timedelta(minutes=10)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"},
        {"order_id": "ORD_TEST_04", "event_type": "ORDER_PICKED_UP", "timestamp": (t0 + timedelta(minutes=20)).isoformat(), "customer_id": "C1", "restaurant_id": "RE1", "rider_id": "RI1"}
    ]
    
    assert checker.validate_order("ORD_TEST_04", events) == False

def test_sla_no_breach():
    engine = SLAEngine()
    t0 = datetime(2026, 6, 11, 12, 0, 0)
    
    events = [
        {"event_type": "ORDER_PLACED", "timestamp": t0.isoformat(), "weather": "Clear", "order_volume": 5},
        {"event_type": "ORDER_ACCEPTED", "timestamp": (t0 + timedelta(minutes=1)).isoformat()},
        {"event_type": "FOOD_PREPARING", "timestamp": (t0 + timedelta(minutes=1)).isoformat()},
        {"event_type": "RIDER_ARRIVED_AT_STORE", "timestamp": (t0 + timedelta(minutes=5)).isoformat()},
        {"event_type": "ORDER_PICKED_UP", "timestamp": (t0 + timedelta(minutes=10)).isoformat()},
        {"event_type": "DELIVERED", "timestamp": (t0 + timedelta(minutes=25)).isoformat()}
    ]
    
    result = engine.calculate_sla(events)
    assert result["is_completed"] == True
    assert result["is_breached"] == False
    assert result["breach_reason"] == "No Breach"

def test_sla_weather_breach():
    engine = SLAEngine()
    t0 = datetime(2026, 6, 11, 12, 0, 0)
    
    # Total time = 40 mins, weather = Rain, transit time = 29 mins (> 15 mins target)
    events = [
        {"event_type": "ORDER_PLACED", "timestamp": t0.isoformat(), "weather": "Rain", "order_volume": 5},
        {"event_type": "ORDER_ACCEPTED", "timestamp": (t0 + timedelta(minutes=1)).isoformat(), "weather": "Rain", "order_volume": 5},
        {"event_type": "FOOD_PREPARING", "timestamp": (t0 + timedelta(minutes=1)).isoformat(), "weather": "Rain", "order_volume": 5},
        {"event_type": "RIDER_ARRIVED_AT_STORE", "timestamp": (t0 + timedelta(minutes=5)).isoformat(), "weather": "Rain", "order_volume": 5},
        {"event_type": "ORDER_PICKED_UP", "timestamp": (t0 + timedelta(minutes=11)).isoformat(), "weather": "Rain", "order_volume": 5},
        {"event_type": "DELIVERED", "timestamp": (t0 + timedelta(minutes=40)).isoformat(), "weather": "Rain", "order_volume": 5}
    ]
    
    result = engine.calculate_sla(events)
    assert result["is_breached"] == True
    assert "Weather Delay" in result["breach_reason"]

def test_sla_peak_demand_breach():
    engine = SLAEngine()
    t0 = datetime(2026, 6, 11, 12, 0, 0)
    
    # Total time = 35 mins, volume = 25 (> 15), acceptance delay = 6 mins (> 4 mins)
    events = [
        {"event_type": "ORDER_PLACED", "timestamp": t0.isoformat(), "weather": "Clear", "order_volume": 25},
        {"event_type": "ORDER_ACCEPTED", "timestamp": (t0 + timedelta(minutes=6)).isoformat(), "weather": "Clear", "order_volume": 25},
        {"event_type": "FOOD_PREPARING", "timestamp": (t0 + timedelta(minutes=6)).isoformat(), "weather": "Clear", "order_volume": 25},
        {"event_type": "ORDER_PICKED_UP", "timestamp": (t0 + timedelta(minutes=12)).isoformat(), "weather": "Clear", "order_volume": 25},
        {"event_type": "DELIVERED", "timestamp": (t0 + timedelta(minutes=35)).isoformat(), "weather": "Clear", "order_volume": 25}
    ]
    
    result = engine.calculate_sla(events)
    assert result["is_breached"] == True
    assert result["breach_reason"] == "Peak Demand Delay"

def test_sla_kitchen_breach():
    engine = SLAEngine()
    t0 = datetime(2026, 6, 11, 12, 0, 0)
    
    # Total time = 36 mins, prep time = 20 mins (> 15 mins), weather = Clear, volume = 5
    events = [
        {"event_type": "ORDER_PLACED", "timestamp": t0.isoformat(), "weather": "Clear", "order_volume": 5},
        {"event_type": "ORDER_ACCEPTED", "timestamp": (t0 + timedelta(minutes=1)).isoformat(), "weather": "Clear", "order_volume": 5},
        {"event_type": "FOOD_PREPARING", "timestamp": (t0 + timedelta(minutes=1)).isoformat(), "weather": "Clear", "order_volume": 5},
        {"event_type": "ORDER_PICKED_UP", "timestamp": (t0 + timedelta(minutes=21)).isoformat(), "weather": "Clear", "order_volume": 5},
        {"event_type": "DELIVERED", "timestamp": (t0 + timedelta(minutes=36)).isoformat(), "weather": "Clear", "order_volume": 5}
    ]
    
    result = engine.calculate_sla(events)
    assert result["is_breached"] == True
    assert result["breach_reason"] == "Kitchen Operational Delay"
