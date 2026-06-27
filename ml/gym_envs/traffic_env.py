"""
ml/gym_envs/traffic_env.py

Custom OpenAI Gymnasium environment for training the RL signal timing agent.

The agent controls one junction. Each step it decides:
  - Which phase to activate (N/S green OR E/W green)
  - How long to hold that phase (mapped to 10–90 seconds)

Reward = negative total vehicle wait time + bonus for clearing queues.
Emergency scenarios are injected randomly during training so the agent
learns to handle them too.

Install deps:
    pip install gymnasium stable-baselines3 numpy
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Optional


# ── Constants ─────────────────────────────────────────────────────────────────

LANE_CONFIGS = {
    "2way": ["N", "S"],
    "3way": ["N", "S", "E"],
    "4way": ["N", "S", "E", "W"],
}

# Phase definitions: (green_lanes, red_lanes)
PHASE_DEFS = {
    "2way": [
        (["N", "S"], []),
        (["S"], ["N"]),
    ],
    "3way": [
        (["N"], ["S", "E"]),
        (["S", "E"], ["N"]),
        (["E"], ["N", "S"]),
    ],
    "4way": [
        (["N", "S"], ["E", "W"]),
        (["E", "W"], ["N", "S"]),
    ],
}

MIN_GREEN = 10   # seconds
MAX_GREEN = 90
SPAWN_RATE = 0.3  # avg vehicles arriving per lane per second


class TrafficJunctionEnv(gym.Env):
    """
    Observation space (8 floats):
        [N_count, S_count, E_count, W_count,
         current_phase_index, time_in_phase,
         emergency_active, emergency_direction_encoded]

    Action space (Box, 2 floats in [0,1]):
        action[0] → which phase to activate (mapped to phase index)
        action[1] → how long to hold it    (mapped to MIN_GREEN–MAX_GREEN seconds)

    Episode: 3600 simulated seconds (1 hour of traffic)
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        junction_type: str = "4way",
        render_mode: Optional[str] = None,
        emergency_probability: float = 0.001,  # chance per second of an emergency
    ):
        super().__init__()
        assert junction_type in LANE_CONFIGS, f"Unknown junction type: {junction_type}"

        self.junction_type = junction_type
        self.lanes = LANE_CONFIGS[junction_type]
        self.phases = PHASE_DEFS[junction_type]
        self.n_phases = len(self.phases)
        self.render_mode = render_mode
        self.emergency_prob = emergency_probability

        # Always use 4 lane slots; pad missing lanes with 0
        self.obs_dim = 8
        self.observation_space = spaces.Box(
            low=np.zeros(self.obs_dim, dtype=np.float32),
            high=np.array([100, 100, 100, 100, self.n_phases - 1, MAX_GREEN, 1, 3], dtype=np.float32),
        )

        # [phase_choice (0-1), duration_fraction (0-1)]
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(2,), dtype=np.float32)

        # State variables initialised in reset()
        self.vehicle_counts: dict = {}
        self.current_phase: int = 0
        self.time_in_phase: float = 0.0
        self.phase_duration: float = 30.0
        self.total_wait: float = 0.0
        self.elapsed: float = 0.0
        self.emergency_active: bool = False
        self.emergency_direction: int = 0
        self.episode_length: float = 3600.0  # 1 simulated hour

    # ── Gymnasium API ─────────────────────────────────────────────────────────

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.vehicle_counts = {lane: self.np_random.integers(0, 10) for lane in self.lanes}
        self.current_phase = 0
        self.time_in_phase = 0.0
        self.phase_duration = 30.0
        self.total_wait = 0.0
        self.elapsed = 0.0
        self.emergency_active = False
        self.emergency_direction = 0
        return self._get_obs(), {}

    def step(self, action: np.ndarray):
        # Decode action
        phase_idx = int(action[0] * self.n_phases)
        phase_idx = min(phase_idx, self.n_phases - 1)
        duration = MIN_GREEN + float(action[1]) * (MAX_GREEN - MIN_GREEN)

        # Apply action only if current phase is done
        if self.time_in_phase >= self.phase_duration:
            self.current_phase = phase_idx
            self.phase_duration = duration
            self.time_in_phase = 0.0

        # Simulate 1 second of traffic
        tick = 1.0
        self._simulate_tick(tick)
        self.elapsed += tick

        # Compute reward
        reward = self._compute_reward()

        terminated = self.elapsed >= self.episode_length
        truncated = False
        info = {
            "total_wait": self.total_wait,
            "vehicle_counts": dict(self.vehicle_counts),
            "emergency_active": self.emergency_active,
        }

        return self._get_obs(), reward, terminated, truncated, info

    def render(self):
        if self.render_mode == "human":
            green = self.phases[self.current_phase][0]
            print(
                f"t={self.elapsed:.0f}s | Phase={self.current_phase} GREEN={green} "
                f"| Counts={self.vehicle_counts} | Wait={self.total_wait:.1f}s"
            )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _simulate_tick(self, dt: float):
        """Update vehicle counts and wait time for one second."""
        green_lanes = self.phases[self.current_phase][0]

        # Random emergency trigger
        if not self.emergency_active and self.np_random.random() < self.emergency_prob:
            self.emergency_active = True
            self.emergency_direction = self.np_random.integers(0, max(len(self.lanes) - 1, 1))

        # Clear emergency after 60 seconds (simplified)
        if self.emergency_active and self.time_in_phase > 60:
            self.emergency_active = False

        for lane in self.lanes:
            # Vehicles arrive randomly
            arrivals = self.np_random.poisson(SPAWN_RATE * dt)
            self.vehicle_counts[lane] = min(100, self.vehicle_counts.get(lane, 0) + arrivals)

            if lane in green_lanes and not self.emergency_active:
                # Vehicles depart — green lane clears ~2 vehicles/second
                departures = min(self.vehicle_counts[lane], int(2 * dt))
                self.vehicle_counts[lane] -= departures
            else:
                # Waiting vehicles accumulate wait time
                self.total_wait += self.vehicle_counts.get(lane, 0) * dt

        self.time_in_phase += dt

    def _compute_reward(self) -> float:
        """
        Reward = -(total vehicles waiting) + bonus for clearing the busiest lane.
        Penalty if emergency vehicle is blocked.
        """
        waiting = sum(
            count for lane, count in self.vehicle_counts.items()
            if lane not in self.phases[self.current_phase][0]
        )
        reward = -float(waiting)

        # Bonus for clearing queues
        if all(c < 3 for c in self.vehicle_counts.values()):
            reward += 10.0

        # Emergency penalty — blocked emergency vehicle
        if self.emergency_active:
            em_lane = self.lanes[self.emergency_direction]
            if em_lane not in self.phases[self.current_phase][0]:
                reward -= 50.0  # big penalty for blocking ambulance / fire truck

        return reward

    def _get_obs(self) -> np.ndarray:
        """Build the observation vector (always 8 floats)."""
        counts = [float(self.vehicle_counts.get(l, 0)) for l in ["N", "S", "E", "W"]]
        return np.array([
            *counts,
            float(self.current_phase),
            float(self.time_in_phase),
            float(self.emergency_active),
            float(self.emergency_direction),
        ], dtype=np.float32)
