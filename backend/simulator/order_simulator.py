import time
import random
import threading
import sqlite3
from datetime import datetime, timedelta
import os
import sys

# Add backend directory to path if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database.db import get_db_connection

# Lists of mock entities
CUSTOMERS = [
    {"id": "CUST_001", "name": "Emily Watson", "city": "San Francisco"},
    {"id": "CUST_002", "name": "Marcus Aurelius", "city": "San Francisco"},
    {"id": "CUST_003", "name": "Sarah Connor", "city": "San Francisco"},
    {"id": "CUST_004", "name": "David Miller", "city": "San Francisco"},
    {"id": "CUST_005", "name": "Sophia Martinez", "city": "San Francisco"},
    {"id": "CUST_006", "name": "James Bond", "city": "San Francisco"},
    {"id": "CUST_007", "name": "Elena Rostova", "city": "San Francisco"},
    {"id": "CUST_008", "name": "Ken Tanaka", "city": "San Francisco"}
]

RESTAURANTS = [
    {"id": "REST_101", "name": "The Gourmet Burger", "cuisine": "American", "city": "San Francisco"},
    {"id": "REST_102", "name": "Szechuan Garden", "cuisine": "Chinese", "city": "San Francisco"},
    {"id": "REST_103", "name": "Bella Italia", "cuisine": "Italian", "city": "San Francisco"},
    {"id": "REST_104", "name": "Taco Loco", "cuisine": "Mexican", "city": "San Francisco"},
    {"id": "REST_105", "name": "Sakura Sushi", "cuisine": "Japanese", "city": "San Francisco"}
]

RIDERS = [
    {"id": "RIDER_201", "name": "Alex Carter", "vehicle": "E-Bike"},
    {"id": "RIDER_202", "name": "Jordan Smith", "vehicle": "Scooter"},
    {"id": "RIDER_203", "name": "Casey Jones", "vehicle": "Bicycle"},
    {"id": "RIDER_204", "name": "Taylor Swift", "vehicle": "Car"},
    {"id": "RIDER_205", "name": "Morgan Freeman", "vehicle": "E-Bike"}
]

class OrderSimulator:
    def __init__(self):
        self.weather = "Clear"  # Clear, Rain, Storm
        self.order_rate = 1.0   # Orders generated per simulated minute
        self.speed_multiplier = 60.0  # 1 real second = 1 simulated minute
        
        self.running = False
        self.thread = None
        self.active_order_count = 0
        self.simulation_time = datetime.now()
        
        self.scheduled_events = []  # List of dicts: {"time": datetime, "event": dict}
        self.lock = threading.Lock()
        
        # Track generated orders for reporting - loaded from DB to prevent duplicate collisions on restart
        self.order_counter = self._get_start_counter()

    def _get_start_counter(self) -> int:
        """Finds the maximum NNNN suffix from existing order IDs in the DB."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT order_id FROM order_events")
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                return 0
            
            nums = []
            for row in rows:
                parts = row[0].split('_')
                if len(parts) >= 3:
                    try:
                        nums.append(int(parts[2]))
                    except ValueError:
                        pass
            return max(nums) if nums else 0
        except Exception:
            return 0


    def set_config(self, weather=None, order_rate=None, speed_multiplier=None):
        if weather is not None:
            self.weather = weather
        if order_rate is not None:
            self.order_rate = order_rate
        if speed_multiplier is not None:
            self.speed_multiplier = speed_multiplier
        print(f"Simulator config updated: Weather={self.weather}, OrderRate={self.order_rate}, Speed={self.speed_multiplier}x")

    def start(self):
        with self.lock:
            if not self.running:
                self.running = True
                self.simulation_time = datetime.now()
                self.thread = threading.Thread(target=self._run_loop, daemon=True)
                self.thread.start()
                print("Order Simulator started.")

    def stop(self):
        with self.lock:
            if self.running:
                self.running = False
                print("Stopping Order Simulator...")

    def _run_loop(self):
        last_tick = time.time()
        order_generation_timer = 0.0

        while self.running:
            now = time.time()
            dt = now - last_tick
            last_tick = now

            # Advance simulation clock
            sim_dt = timedelta(seconds=dt * self.speed_multiplier)
            self.simulation_time += sim_dt

            # Increment order generator timer
            order_generation_timer += dt * self.speed_multiplier / 60.0  # in simulated minutes

            # Generate new orders if timer exceeds interval (1 / order_rate)
            interval = 1.0 / max(self.order_rate, 0.1)
            if order_generation_timer >= interval:
                num_orders_to_gen = int(order_generation_timer / interval)
                for _ in range(num_orders_to_gen):
                    self._create_new_order()
                order_generation_timer %= interval

            # Process scheduled events
            self._process_events()

            time.sleep(0.5)

    def _create_new_order(self):
        self.order_counter += 1
        order_id = f"ORD_{self.simulation_time.strftime('%Y%m%d')}_{self.order_counter:04d}"
        
        cust = random.choice(CUSTOMERS)
        rest = random.choice(RESTAURANTS)
        rider = random.choice(RIDERS)
        
        # Determine current active load (approximate based on order rate)
        self.active_order_count = len([e for e in self.scheduled_events if e["event"]["event_type"] != "DELIVERED"])
        
        # Calculate timestamps for order lifecycle based on system conditions
        # 1. Placement Time
        placement_time = self.simulation_time
        
        # 2. Acceptance Time (affected by Peak Demand)
        acceptance_delay = random.uniform(1, 3)  # minutes
        if self.active_order_count > 15:  # Simulated threshold for peak demand
            acceptance_delay += random.uniform(4, 8)  # delay assignment
        acceptance_time = placement_time + timedelta(minutes=acceptance_delay)
        
        # 3. Food Prep Start Time
        prep_start_time = acceptance_time + timedelta(seconds=15)
        
        # 4. Food Prep Duration (affected by Restaurant operational delays)
        # 15% chance of a kitchen operational backup delay
        is_kitchen_delay = random.random() < 0.15
        prep_delay = random.uniform(8, 12)
        if is_kitchen_delay:
            prep_delay += random.uniform(10, 15)  # add extra kitchen delay
        ready_time = prep_start_time + timedelta(minutes=prep_delay)
        
        # 5. Rider Arrives at Store (independent travel)
        rider_arrive_delay = random.uniform(3, 8)
        rider_arrived_time = acceptance_time + timedelta(minutes=rider_arrive_delay)
        
        # Pickup time is max of when food is ready or when rider arrives
        pickup_time = max(ready_time, rider_arrived_time) + timedelta(minutes=random.uniform(0.5, 1.5))
        
        # 6. Rider Travel to Customer (affected by Weather)
        base_transit_time = random.uniform(8, 12)
        weather_multiplier = 1.0
        if self.weather == "Rain":
            weather_multiplier = 1.5
        elif self.weather == "Storm":
            weather_multiplier = 2.5
            
        transit_time = base_transit_time * weather_multiplier
        delivered_time = pickup_time + timedelta(minutes=transit_time)
        
        # Build event sequence
        events = [
            {"type": "ORDER_PLACED", "time": placement_time},
            {"type": "ORDER_ACCEPTED", "time": acceptance_time},
            {"type": "FOOD_PREPARING", "time": prep_start_time},
            {"type": "RIDER_ARRIVED_AT_STORE", "time": rider_arrived_time},
            {"type": "ORDER_PICKED_UP", "time": pickup_time},
            {"type": "DELIVERED", "time": delivered_time}
        ]
        
        # Introduce a 2% chance of a "Data Quality Issue" - e.g., out-of-order timestamps
        # to test our data quality layer!
        if random.random() < 0.02:
            # Swap timestamps of ORDER_PICKED_UP and DELIVERED or write DELIVERED before PICKED UP
            events[4]["time"], events[5]["time"] = events[5]["time"], events[4]["time"]
            print(f"!!! DQ Anomalous Order created: {order_id}")
            
        # Introduce 1% chance of duplicate events
        is_duplicate = random.random() < 0.01

        # Schedule all events in our calendar
        with self.lock:
            for ev in events:
                event_data = {
                    "order_id": order_id,
                    "event_type": ev["type"],
                    "timestamp": ev["time"].isoformat(),
                    "weather": self.weather,
                    "order_volume": self.active_order_count,
                    "customer_id": cust["id"],
                    "restaurant_id": rest["id"],
                    "rider_id": rider["id"],
                    "latitude": 37.7749 + random.uniform(-0.02, 0.02),
                    "longitude": -122.4194 + random.uniform(-0.02, 0.02)
                }
                self.scheduled_events.append({
                    "time": ev["time"],
                    "event": event_data
                })
                
                # Insert a duplicate event 5 seconds later
                if is_duplicate and ev["type"] == "ORDER_PLACED":
                    self.scheduled_events.append({
                        "time": ev["time"] + timedelta(seconds=5),
                        "event": event_data.copy()
                    })

            print(f"Scheduled order {order_id} ({cust['name']} -> {rest['name']})")

    def _process_events(self):
        with self.lock:
            now = self.simulation_time
            # Find events that are due
            due_events = [e for e in self.scheduled_events if e["time"] <= now]
            # Keep remaining
            self.scheduled_events = [e for e in self.scheduled_events if e["time"] > now]

        if due_events:
            # Sort due events by time to process in order
            due_events.sort(key=lambda x: x["time"])
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            for ev in due_events:
                event = ev["event"]
                cursor.execute('''
                    INSERT INTO order_events (
                        order_id, event_type, timestamp, weather, order_volume,
                        customer_id, restaurant_id, rider_id, latitude, longitude
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event["order_id"], event["event_type"], event["timestamp"], event["weather"],
                    event["order_volume"], event["customer_id"], event["restaurant_id"],
                    event["rider_id"], event["latitude"], event["longitude"]
                ))
                print(f"[{event['timestamp']}] Event emitted: {event['order_id']} - {event['event_type']} ({event['weather']})")
                
            conn.commit()
            conn.close()

if __name__ == "__main__":
    # Test simulator execution standalone
    from database.db import init_db
    init_db()
    
    sim = OrderSimulator()
    sim.set_config(weather="Rain", order_rate=2.0, speed_multiplier=120.0) # 1 sec = 2 mins
    sim.start()
    
    try:
        # Run for 15 seconds to see events flow
        for i in range(15):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sim.stop()
