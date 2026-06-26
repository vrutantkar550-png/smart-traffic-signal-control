"""
engine/phases.py
Defines which lanes get GREEN in each phase, for every junction type.

2-way: Phase 0 → N/S green, Phase 1 → E/W green  (like a straight road)
3-way: Phase 0 → N green, Phase 1 → S/E green, Phase 2 → W green
4-way: Phase 0 → N/S green, Phase 1 → E/W green  (with yellow gap)
"""

from core.schemas import SignalPhase
from core.config import settings


# Phase definitions: each entry is a set of lane IDs that get GREEN
PHASE_SEQUENCES = {
    "2way": [
        {"green": ["N", "S"], "red": ["E", "W"]},
        {"green": ["E", "W"], "red": ["N", "S"]},
    ],
    "3way": [
        {"green": ["N"],      "red": ["S", "E"]},
        {"green": ["S", "E"], "red": ["N"]},
        {"green": ["W"],      "red": ["N", "S", "E"]},  # if 3rd arm is W
    ],
    "4way": [
        {"green": ["N", "S"], "red": ["E", "W"]},
        {"green": ["E", "W"], "red": ["N", "S"]},
    ],
}


class PhaseManager:
    """
    Tracks which phase the junction is currently in and advances through them.
    Also handles the YELLOW transition gap between green phases.
    """

    def __init__(self, junction_type: str, lane_ids: list):
        self.junction_type = junction_type
        self.lane_ids      = lane_ids
        self.phases        = PHASE_SEQUENCES.get(junction_type, PHASE_SEQUENCES["4way"])
        self._index        = 0       # current phase index
        self._in_yellow    = False   # True during yellow transition

    def advance(self):
        """Move to the next phase. Inserts a yellow step between greens."""
        if self._in_yellow:
            # Yellow is done → move to next green phase
            self._index = (self._index + 1) % len(self.phases)
            self._in_yellow = False
        else:
            # Green is done → go yellow first
            self._in_yellow = True

    def current_green_lane(self) -> str | None:
        """Returns the first green lane ID in the current phase (for RL timing decisions)."""
        if self._in_yellow:
            return None
        green_lanes = self.phases[self._index]["green"]
        return green_lanes[0] if green_lanes else None

    def current_phase_dict(self, vehicle_counts: dict) -> list:
        """
        Returns a list of lane states in the format expected by the WebSocket payload.
        e.g. [{"lane_id": "N", "phase": "GREEN", "vehicle_count": 12}, ...]
        """
        phase = self.phases[self._index]
        result = []

        for lane in self.lane_ids:
            if self._in_yellow:
                # All lanes that were green become yellow; rest stay red
                was_green = lane in phase["green"]
                signal = SignalPhase.YELLOW if was_green else SignalPhase.RED
            elif lane in phase["green"]:
                signal = SignalPhase.GREEN
            else:
                signal = SignalPhase.RED

            result.append({
                "lane_id":       lane,
                "phase":         signal.value,
                "vehicle_count": vehicle_counts.get(lane, 0),
            })

        return result
