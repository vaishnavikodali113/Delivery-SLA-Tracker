from datetime import datetime
import os
import sys

# Targets in minutes
TOTAL_SLA_TARGET_MINS = 30.0
PREP_SLA_TARGET_MINS = 15.0
TRANSIT_SLA_TARGET_MINS = 15.0

class SLAEngine:
    def __init__(self):
        pass

    def calculate_sla(self, events: list) -> dict:
        """
        Processes events for a single order and determines SLA outcomes.
        events: list of dicts with keys: event_type, timestamp, weather, order_volume
        """
        # Create map of event_type -> datetime
        event_map = {}
        weather_conditions = []
        max_order_volume = 0
        
        for ev in events:
            etype = ev["event_type"]
            try:
                dt = datetime.fromisoformat(ev["timestamp"])
                event_map[etype] = dt
            except (ValueError, TypeError):
                # Invalid timestamp format
                pass
            
            weather_conditions.append(ev.get("weather", "Clear"))
            max_order_volume = max(max_order_volume, ev.get("order_volume", 0))

        # Check for start and end of lifecycle
        if "ORDER_PLACED" not in event_map or "DELIVERED" not in event_map:
            return {
                "is_completed": False,
                "is_breached": False,
                "breach_reason": "Order Incomplete"
            }

        placed_time = event_map["ORDER_PLACED"]
        delivered_time = event_map["DELIVERED"]

        # 1. Calculate durations in minutes
        total_duration = (delivered_time - placed_time).total_seconds() / 60.0
        
        # Helper segment calculations
        acceptance_delay = 0.0
        if "ORDER_ACCEPTED" in event_map:
            acceptance_delay = (event_map["ORDER_ACCEPTED"] - placed_time).total_seconds() / 60.0

        prep_duration = 0.0
        if "ORDER_PICKED_UP" in event_map and "ORDER_ACCEPTED" in event_map:
            prep_duration = (event_map["ORDER_PICKED_UP"] - event_map["ORDER_ACCEPTED"]).total_seconds() / 60.0

        transit_duration = 0.0
        if "ORDER_PICKED_UP" in event_map:
            transit_duration = (delivered_time - event_map["ORDER_PICKED_UP"]).total_seconds() / 60.0

        dispatch_delay = 0.0
        if "RIDER_ARRIVED_AT_STORE" in event_map and "ORDER_ACCEPTED" in event_map:
            dispatch_delay = (event_map["RIDER_ARRIVED_AT_STORE"] - event_map["ORDER_ACCEPTED"]).total_seconds() / 60.0

        # Primary weather condition is the modal or worst case
        primary_weather = "Clear"
        if "Storm" in weather_conditions:
            primary_weather = "Storm"
        elif "Rain" in weather_conditions:
            primary_weather = "Rain"

        is_breached = total_duration > TOTAL_SLA_TARGET_MINS
        breach_reason = "No Breach"

        # 2. Heuristic Breach Reason Classification
        if is_breached:
            # Check Weather first: Storm or Rain causing high transit times
            if primary_weather in ["Rain", "Storm"] and transit_duration > TRANSIT_SLA_TARGET_MINS:
                breach_reason = f"Weather Delay ({primary_weather})"
            
            # Check Peak Demand: high order volume causing long rider assignment delays
            elif max_order_volume > 15 and acceptance_delay > 4.0:
                breach_reason = "Peak Demand Delay"
                
            # Check Kitchen Operational Delay: food prep took too long
            elif prep_duration > PREP_SLA_TARGET_MINS:
                breach_reason = "Kitchen Operational Delay"
                
            # Check Rider Dispatch Delay: rider took long to arrive at store
            elif dispatch_delay > 8.0:
                breach_reason = "Rider Dispatch Delay"
                
            # Fallback
            else:
                # Decide based on where the biggest portion of the delay occurred
                delays = {
                    "Rider Dispatch Delay": dispatch_delay,
                    "Kitchen Operational Delay": prep_duration,
                    "Transit Delay": transit_duration,
                    "Peak Demand Delay": acceptance_delay
                }
                breach_reason = max(delays, key=delays.get)

        return {
            "is_completed": True,
            "placed_time": placed_time.isoformat(),
            "delivery_time": delivered_time.isoformat(),
            "total_duration_mins": round(total_duration, 2),
            "target_duration_mins": TOTAL_SLA_TARGET_MINS,
            "acceptance_delay_mins": round(acceptance_delay, 2),
            "prep_duration_mins": round(prep_duration, 2),
            "transit_duration_mins": round(transit_duration, 2),
            "dispatch_delay_mins": round(dispatch_delay, 2),
            "is_breached": is_breached,
            "breach_reason": breach_reason,
            "primary_weather": primary_weather,
            "max_order_volume": max_order_volume
        }
