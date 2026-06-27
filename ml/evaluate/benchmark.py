"""
ml/evaluate/benchmark.py

Evaluates and compares three signal timing strategies:
  1. AI (PPO RL agent)          ← our trained model
  2. Fixed timing               ← traditional fixed 30s green cycles
  3. Proportional (rule-based)  ← simple vehicle-count ratio

Metrics:
  - Average vehicle wait time (seconds)
  - Average throughput (vehicles cleared per episode)
  - Emergency response time (seconds to clear path)
  - Reward score

Run:
    python ml/evaluate/benchmark.py

Output:
    Prints a comparison table
    Saves results to ml/logs/benchmark_results.json
"""

import os
import sys
import json
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from gym_envs.traffic_env import TrafficJunctionEnv

EPISODES        = 100
JUNCTION_TYPE   = "4way"
RL_MODEL_PATH   = "../../backend/models/traffic_rl_agent.zip"
RESULTS_PATH    = "../logs/benchmark_results.json"

os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)


# ── Strategy implementations ──────────────────────────────────────────────────

class RLAgent:
    """Loads and runs the trained PPO model."""
    name = "PPO RL Agent"

    def __init__(self, model_path: str):
        from stable_baselines3 import PPO
        self.model = PPO.load(model_path)

    def predict(self, obs):
        action, _ = self.model.predict(obs, deterministic=True)
        return action


class FixedTimingAgent:
    """
    Baseline: alternates phases every 30 seconds regardless of traffic.
    Represents traditional fixed-cycle signal controllers.
    """
    name = "Fixed Timing (30s)"

    def __init__(self, n_phases: int = 2, fixed_duration: float = 30.0):
        self.n_phases = n_phases
        self.fixed_duration = fixed_duration
        self._phase = 0
        self._timer = 0.0

    def predict(self, obs):
        self._timer += 1
        if self._timer >= self.fixed_duration:
            self._timer = 0
            self._phase = (self._phase + 1) % self.n_phases
        # Encode as action: phase_fraction, fixed duration fraction
        phase_frac = self._phase / max(self.n_phases - 1, 1)
        duration_frac = (self.fixed_duration - 10) / (90 - 10)
        return np.array([phase_frac, duration_frac], dtype=np.float32)


class ProportionalAgent:
    """
    Rule-based: gives green to the lane with most vehicles.
    Duration proportional to queue length ratio.
    """
    name = "Proportional Rule-Based"

    def predict(self, obs):
        counts = obs[:4]  # N, S, E, W
        total  = counts.sum()
        if total == 0:
            return np.array([0.0, 0.2], dtype=np.float32)

        # NS vs EW
        ns = counts[0] + counts[1]
        ew = counts[2] + counts[3]
        phase_frac    = 0.0 if ns >= ew else 0.99
        duration_frac = min(max(max(ns, ew) / total, 0), 1)
        return np.array([phase_frac, duration_frac], dtype=np.float32)


# ── Evaluation runner ─────────────────────────────────────────────────────────

def evaluate_agent(agent, episodes: int = EPISODES) -> dict:
    """Run N episodes and collect metrics."""
    env = TrafficJunctionEnv(junction_type=JUNCTION_TYPE, emergency_probability=0.002)

    rewards, waits, throughputs, emergency_times = [], [], [], []

    for ep in range(episodes):
        obs, _ = env.reset()
        total_reward = 0.0
        ep_emergency_time = None
        emergency_started = None
        done = False

        while not done:
            action = agent.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            done = terminated or truncated

            # Track emergency response time
            if info["emergency_active"] and emergency_started is None:
                emergency_started = env.elapsed
            elif not info["emergency_active"] and emergency_started is not None:
                ep_emergency_time = env.elapsed - emergency_started
                emergency_started = None

        rewards.append(total_reward)
        waits.append(info["total_wait"])

        # Throughput: initial vehicles - remaining
        throughputs.append(max(0, sum(info["vehicle_counts"].values())))
        if ep_emergency_time:
            emergency_times.append(ep_emergency_time)

    env.close()

    return {
        "agent":                agent.name,
        "avg_reward":           round(float(np.mean(rewards)), 1),
        "std_reward":           round(float(np.std(rewards)), 1),
        "avg_total_wait_s":     round(float(np.mean(waits)), 1),
        "avg_remaining_vehicles": round(float(np.mean(throughputs)), 1),
        "avg_emergency_clear_s": round(float(np.mean(emergency_times)), 1) if emergency_times else None,
        "episodes":             episodes,
    }


def print_table(results: list[dict]):
    """Print a formatted comparison table."""
    print("\n" + "=" * 72)
    print(f"{'BENCHMARK RESULTS':^72}")
    print(f"Junction: {JUNCTION_TYPE} | Episodes: {EPISODES}")
    print("=" * 72)

    header = f"{'Strategy':<28} {'Avg Reward':>12} {'Avg Wait(s)':>12} {'Emrg Clear(s)':>14}"
    print(header)
    print("-" * 72)

    for r in results:
        emrg = f"{r['avg_emergency_clear_s']:.1f}s" if r['avg_emergency_clear_s'] else "N/A"
        print(
            f"{r['agent']:<28} {r['avg_reward']:>12.1f} "
            f"{r['avg_total_wait_s']:>12.1f} {emrg:>14}"
        )

    print("=" * 72)

    # Highlight best
    best = max(results, key=lambda r: r["avg_reward"])
    print(f"\nBest strategy: {best['agent']} (reward {best['avg_reward']:.1f})\n")


def main():
    agents = [ProportionalAgent(), FixedTimingAgent()]

    # Try loading RL model — skip gracefully if not trained yet
    if os.path.exists(RL_MODEL_PATH + ".zip") or os.path.exists(RL_MODEL_PATH):
        try:
            agents.insert(0, RLAgent(RL_MODEL_PATH))
            print("RL model loaded.")
        except Exception as e:
            print(f"Could not load RL model: {e} — skipping.")
    else:
        print(f"RL model not found at {RL_MODEL_PATH} — skipping. Train first.")

    results = []
    for agent in agents:
        print(f"Evaluating: {agent.name} ...")
        t0 = time.time()
        r = evaluate_agent(agent, episodes=EPISODES)
        r["eval_time_s"] = round(time.time() - t0, 1)
        results.append(r)
        print(f"  Done in {r['eval_time_s']}s | Avg reward: {r['avg_reward']:.1f}")

    print_table(results)

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
