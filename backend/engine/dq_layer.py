import sqlite3
from datetime import datetime
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database.db import get_db_connection

# Define the standard lifecycle sequence
EVENT_SEQUENCE = [
    "ORDER_PLACED",
    "ORDER_ACCEPTED",
    "FOOD_PREPARING",
    "RIDER_ARRIVED_AT_STORE",
    "ORDER_PICKED_UP",
    "DELIVERED"
]

class DataQualityChecker:
    def __init__(self, run_id: str):
        self.run_id = run_id

    def log_check(self, conn, order_id: str, rule_name: str, status: str, error_message: str = None):
        """Logs a DQ check result into the dq_logs table."""
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO dq_logs (run_id, order_id, rule_name, status, error_message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            self.run_id,
            order_id,
            rule_name,
            status,
            error_message,
            datetime.now().isoformat()
        ))

    def validate_order(self, order_id: str, events: list) -> bool:
        """
        Validates the event history for a single order.
        events: A list of dicts/Rows containing keys: event_type, timestamp, etc.
        """
        conn = get_db_connection()
        is_order_valid = True
        
        # Sort events by timestamp to see chronological order
        events_sorted_by_time = sorted(events, key=lambda x: x["timestamp"])
        
        # 1. Mandatory Fields Check
        fields_ok = True
        for ev in events:
            for field in ["order_id", "event_type", "timestamp", "customer_id", "restaurant_id", "rider_id"]:
                if not ev.get(field):
                    fields_ok = False
                    is_order_valid = False
                    self.log_check(
                        conn, order_id, "MANDATORY_FIELDS", "FAIL",
                        f"Missing mandatory field '{field}' in event '{ev.get('event_type')}'"
                    )
                    break
        if fields_ok:
            self.log_check(conn, order_id, "MANDATORY_FIELDS", "PASS")

        # 2. Duplicate Event Check
        event_types = [ev["event_type"] for ev in events]
        duplicates = set([x for x in event_types if event_types.count(x) > 1])
        if duplicates:
            is_order_valid = False
            self.log_check(
                conn, order_id, "DUPLICATE_EVENTS", "FAIL",
                f"Duplicate events found for types: {', '.join(duplicates)}"
            )
        else:
            self.log_check(conn, order_id, "DUPLICATE_EVENTS", "PASS")

        # 3. State Transition Sequence Check
        # Check that events follow a logical chronological progression.
        # We index the events by their natural flow.
        flow_indices = []
        for ev in events_sorted_by_time:
            etype = ev["event_type"]
            if etype in EVENT_SEQUENCE:
                flow_indices.append((etype, EVENT_SEQUENCE.index(etype), ev["timestamp"]))
                
        # Validate sequential indexing
        seq_ok = True
        for i in range(len(flow_indices) - 1):
            curr_event, curr_idx, curr_time = flow_indices[i]
            next_event, next_idx, next_time = flow_indices[i + 1]
            
            # Index check: natural event ordering should be ascending
            # (allow skipping states e.g. RIDER_ARRIVED, but not going backward like PICKED_UP before ACCEPTED)
            if next_idx < curr_idx:
                seq_ok = False
                is_order_valid = False
                self.log_check(
                    conn, order_id, "STATE_TRANSITION", "FAIL",
                    f"Invalid state transition: '{curr_event}' occurred before '{next_event}' in timeline"
                )
                break
        if seq_ok:
            self.log_check(conn, order_id, "STATE_TRANSITION", "PASS")

        # 4. Chronological Timestamp Check
        # Check that actual timestamps are strictly non-decreasing
        time_ok = True
        for i in range(len(events_sorted_by_time) - 1):
            curr_time = events_sorted_by_time[i]["timestamp"]
            next_time = events_sorted_by_time[i + 1]["timestamp"]
            if next_time < curr_time:
                time_ok = False
                is_order_valid = False
                self.log_check(
                    conn, order_id, "CHRONOLOGICAL_TIMELINE", "FAIL",
                    f"Timestamp anomaly: event '{events_sorted_by_time[i+1]['event_type']}' timestamp ({next_time}) "
                    f"is earlier than prior event '{events_sorted_by_time[i]['event_type']}' ({curr_time})"
                )
                break
        if time_ok:
            self.log_check(conn, order_id, "CHRONOLOGICAL_TIMELINE", "PASS")

        conn.commit()
        conn.close()
        return is_order_valid
