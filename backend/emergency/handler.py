"""
emergency/handler.py
Determines which signal phase to show during an emergency.
Each emergency type has its own strategy — all are rule-based (not ML)
for guaranteed speed and reliability.
"""

import logging
from core.schemas import SignalPhase

logger = logging.getLogger(__name__)


class EmergencyHandler:
    """Dispatches emergency override phase logic based on emergency type."""

    def get_phase(self, lane_ids: list, emergency_type: str, direction: str | None) -> list:
        """
        Returns a lane state list with emergency phases applied.

        Args:
            lane_ids:       All lane IDs at the junction, e.g. ["N", "S", "E", "W"]
            emergency_type: "ambulance", "fire_truck", "accident", "construction"
            direction:      Which lane the emergency vehicle is coming from (optional)

        Returns:
            List of dicts: [{"lane_id": "N", "phase": "GREEN", "vehicle_count": 0}, ...]
        """
        strategies = {
            "ambulance":    self._ambulance,
            "fire_truck":   self._fire_truck,
            "accident":     self._accident,
            "construction": self._construction,
        }

        strategy = strategies.get(emergency_type, self._fire_truck)
        result = strategy(lane_ids, direction)
        logger.warning(f"Emergency phase active: {emergency_type} | direction={direction}")
        return result

    def _ambulance(self, lane_ids: list, direction: str | None) -> list:
        """
        Ambulance corridor: give green ONLY to the ambulance's lane.
        All crossing lanes go red to clear the path.
        """
        return [
            {
                "lane_id":       lane,
                "phase":         SignalPhase.GREEN.value if lane == direction else SignalPhase.RED.value,
                "vehicle_count": 0,
                "emergency":     True,
            }
            for lane in lane_ids
        ]

    def _fire_truck(self, lane_ids: list, direction: str | None) -> list:
        """
        Full intersection clear: ALL lanes go RED.
        Fire trucks are too large to squeeze past — clear everything.
        """
        return [
            {
                "lane_id":       lane,
                "phase":         SignalPhase.RED.value,
                "vehicle_count": 0,
                "emergency":     True,
            }
            for lane in lane_ids
        ]

    def _accident(self, lane_ids: list, direction: str | None) -> list:
        """
        Accident mode: the accident lane goes RED (blocked).
        All other lanes cycle normally — here we just set them to RED too
        until the controller reroutes. In a full system, you'd pass reroute
        commands to adjacent junctions.
        """
        return [
            {
                "lane_id":       lane,
                "phase":         SignalPhase.RED.value if lane == direction else SignalPhase.YELLOW.value,
                "vehicle_count": 0,
                "emergency":     True,
            }
            for lane in lane_ids
        ]

    def _construction(self, lane_ids: list, direction: str | None) -> list:
        """
        Construction merge mode: the construction lane goes red,
        the remaining lanes get extended green (simulated by leaving GREEN).
        """
        active_lanes = [l for l in lane_ids if l != direction]
        return [
            {
                "lane_id":       lane,
                "phase":         SignalPhase.RED.value if lane == direction else SignalPhase.GREEN.value,
                "vehicle_count": 0,
                "emergency":     True,
            }
            for lane in lane_ids
        ]
