"""
engine/timing.py
Converts vehicle counts into green phase durations.

Two modes:
  - RL mode: loads the trained Stable-Baselines3 PPO model and asks it
  - Fallback mode: uses a simple proportional formula if no model is available
"""

import os
import logging
import numpy as np
from core.config import settings

logger = logging.getLogger(__name__)


class TimingDecider:
    """
    Decides how long the next GREEN phase should last (in seconds).
    Wraps the RL model with a safe fallback.
    """

    def __init__(self):
        self._model = None
        self._load_model()

    def _load_model(self):
        """Try to load the RL model. Falls back gracefully if not found."""
        if not os.path.exists(settings.RL_MODEL_PATH):
            logger.warning(
                f"RL model not found at {settings.RL_MODEL_PATH}. "
                "Using proportional fallback."
            )
            return

        try:
            from stable_baselines3 import PPO
            self._model = PPO.load(settings.RL_MODEL_PATH)
            logger.info("RL model loaded successfully.")
        except ImportError:
            logger.warning("stable_baselines3 not installed. Using proportional fallback.")
        except Exception as e:
            logger.error(f"Failed to load RL model: {e}. Using proportional fallback.")

    def decide(self, vehicle_counts: dict, green_lane: str | None, junction_type: str) -> int:
        """
        Returns how many seconds the next green phase should last.

        Args:
            vehicle_counts: dict of {lane_id: count}, e.g. {"N": 12, "S": 4}
            green_lane:     which lane is getting green (used to build the RL observation)
            junction_type:  "2way", "3way", or "4way"

        Returns:
            Duration in seconds, clamped to [MIN_GREEN, MAX_GREEN].
        """
        if self._model and green_lane:
            return self._rl_decide(vehicle_counts, green_lane)
        return self._proportional_decide(vehicle_counts, green_lane)

    def _rl_decide(self, vehicle_counts: dict, green_lane: str) -> int:
        """Ask the RL model for a timing decision."""
        try:
            # Build observation vector: [green_lane_count, max_other_count, total_count]
            green_count = vehicle_counts.get(green_lane, 0)
            other_counts = [v for k, v in vehicle_counts.items() if k != green_lane]
            max_other = max(other_counts) if other_counts else 0
            total = sum(vehicle_counts.values())

            obs = np.array([green_count, max_other, total], dtype=np.float32)
            action, _ = self._model.predict(obs, deterministic=True)

            # Map action (0.0–1.0) to seconds
            duration = int(
                settings.MIN_GREEN_TIME
                + float(action) * (settings.MAX_GREEN_TIME - settings.MIN_GREEN_TIME)
            )
            return self._clamp(duration)

        except Exception as e:
            logger.error(f"RL prediction failed: {e}. Falling back.")
            return self._proportional_decide(vehicle_counts, green_lane)

    def _proportional_decide(self, vehicle_counts: dict, green_lane: str | None) -> int:
        """
        Simple fallback: more vehicles waiting = longer green time.
        Formula: green_time = min_green + (green_lane_ratio * range)
        """
        if not vehicle_counts or not green_lane:
            return settings.MIN_GREEN_TIME

        total = sum(vehicle_counts.values())
        if total == 0:
            return settings.MIN_GREEN_TIME

        green_count = vehicle_counts.get(green_lane, 0)
        ratio = green_count / total  # 0.0 to 1.0

        duration = int(
            settings.MIN_GREEN_TIME
            + ratio * (settings.MAX_GREEN_TIME - settings.MIN_GREEN_TIME)
        )
        return self._clamp(duration)

    def _clamp(self, value: int) -> int:
        return max(settings.MIN_GREEN_TIME, min(settings.MAX_GREEN_TIME, value))
