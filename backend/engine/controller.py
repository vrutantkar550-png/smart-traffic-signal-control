"""
engine/controller.py
The core signal control loop.
Every tick it:
  1. Reads vehicle counts from Redis
  2. Checks for emergency overrides
  3. Asks the RL model for the best phase + duration
  4. Advances the signal phase if time is up
  5. Writes the new state to Redis (for WebSocket broadcast)
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict

from core.config import settings
from db.redis_client import (
    get_vehicle_counts, set_signal_state,
    get_emergency_flag
)
from engine.phases import PhaseManager
from engine.timing import TimingDecider
from emergency.handler import EmergencyHandler

logger = logging.getLogger(__name__)


class JunctionState:
    """Tracks the live state of one junction."""

    def __init__(self, junction_id: int, junction_type: str, lane_ids: list):
        self.junction_id    = junction_id
        self.junction_type  = junction_type
        self.lane_ids       = lane_ids
        self.phase_manager  = PhaseManager(junction_type, lane_ids)
        self.timer          = 0       # seconds spent in current phase
        self.phase_duration = 30      # how long the current green phase lasts
        self.emergency_mode = False


class SignalController:
    """
    Manages all registered junctions.
    Call run_loop() as an asyncio background task.
    """

    def __init__(self):
        self._running   = False
        self._junctions: Dict[int, JunctionState] = {}
        self.timing_decider   = TimingDecider()
        self.emergency_handler = EmergencyHandler()

    def register_junction(self, junction_id: int, junction_type: str, lane_ids: list):
        """Add a junction to the controller. Called when a new junction is created."""
        self._junctions[junction_id] = JunctionState(junction_id, junction_type, lane_ids)
        logger.info(f"Registered junction {junction_id} ({junction_type})")

    def stop(self):
        self._running = False

    async def run_loop(self):
        """Main control loop — runs forever until stop() is called."""
        self._running = True
        logger.info("Signal control loop started.")

        while self._running:
            try:
                await self._tick_all()
            except Exception as e:
                logger.error(f"Controller tick error: {e}")

            await asyncio.sleep(settings.CONTROLLER_TICK)

    async def _tick_all(self):
        """Process one tick for every registered junction."""
        for jid, state in self._junctions.items():
            await self._tick_junction(jid, state)

    async def _tick_junction(self, junction_id: int, state: JunctionState):
        """One tick for a single junction."""

        # 1. Check for emergency override
        emergency_type = await get_emergency_flag(junction_id)

        if emergency_type:
            if not state.emergency_mode:
                state.emergency_mode = True
                logger.warning(f"Junction {junction_id}: emergency override — {emergency_type}")

            phase_dict = self.emergency_handler.get_phase(
                state.lane_ids, emergency_type,
                direction=None  # Could be extended to pass direction
            )
            state.timer = 0  # Hold in emergency phase

        else:
            state.emergency_mode = False

            # 2. Get latest vehicle counts per lane
            counts = await get_vehicle_counts(junction_id)

            # 3. Advance timer; switch phase when duration expires
            state.timer += settings.CONTROLLER_TICK
            if state.timer >= state.phase_duration:
                state.timer = 0
                state.phase_manager.advance()

                # 4. Ask timing decider for how long the next green should run
                state.phase_duration = self.timing_decider.decide(
                    counts,
                    state.phase_manager.current_green_lane(),
                    state.junction_type,
                )

            phase_dict = state.phase_manager.current_phase_dict(counts)

        # 5. Build the signal state payload
        signal_state = {
            "junction_id":       junction_id,
            "lanes":             phase_dict,
            "emergency_active":  state.emergency_mode,
            "emergency_type":    emergency_type,
            "timestamp":         datetime.utcnow().isoformat(),
        }

        # 6. Write to Redis so the WebSocket can broadcast it
        await set_signal_state(junction_id, signal_state)
