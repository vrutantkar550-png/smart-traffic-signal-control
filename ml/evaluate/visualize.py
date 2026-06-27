"""
ml/evaluate/visualize.py

Plots training curves, signal timing decisions, and vehicle queue
visualisations from logged training data.

Generates:
  - Learning curve (reward over time)
  - Episode vehicle queue heatmap
  - Signal timing histogram
  - Emergency response comparison bar chart

Run:
    pip install matplotlib seaborn pandas
    python ml/evaluate/visualize.py
"""

import os
import sys
import json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    HAS_MPL = True
except ImportError:
    print("matplotlib not installed. Run: pip install matplotlib")
    HAS_MPL = False

LOGS_DIR        = "../logs/"
BENCHMARK_FILE  = "../logs/benchmark_results.json"
OUTPUT_DIR      = "../logs/plots/"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def plot_learning_curve(monitor_csv: str = None):
    """
    Plot reward over training timesteps from Stable-Baselines3 monitor CSV.
    The CSV is generated automatically by the Monitor wrapper during training.
    """
    if not HAS_MPL:
        return

    if monitor_csv is None:
        # Find monitor CSV in logs
        for root, _, files in os.walk(LOGS_DIR):
            for f in files:
                if f.endswith(".monitor.csv"):
                    monitor_csv = os.path.join(root, f)
                    break

    if not monitor_csv or not os.path.exists(monitor_csv):
        print("No monitor.csv found. Train first.")
        return

    import pandas as pd
    df = pd.read_csv(monitor_csv, comment="#")
    df["cumulative_steps"] = df["l"].cumsum()

    # Smooth with rolling average
    window = max(1, len(df) // 50)
    df["smooth_r"] = df["r"].rolling(window=window, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["cumulative_steps"], df["r"], alpha=0.2, color="steelblue", label="Episode reward")
    ax.plot(df["cumulative_steps"], df["smooth_r"], color="steelblue", linewidth=2, label=f"Smoothed (window={window})")
    ax.set_xlabel("Training timesteps")
    ax.set_ylabel("Episode reward")
    ax.set_title("PPO Agent — Learning Curve")
    ax.legend()
    ax.grid(alpha=0.3)

    path = os.path.join(OUTPUT_DIR, "learning_curve.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved: {path}")
    plt.close(fig)


def plot_benchmark_comparison():
    """Bar chart comparing RL vs Fixed vs Proportional strategies."""
    if not HAS_MPL:
        return

    if not os.path.exists(BENCHMARK_FILE):
        print(f"Benchmark file not found: {BENCHMARK_FILE}. Run benchmark.py first.")
        return

    with open(BENCHMARK_FILE) as f:
        results = json.load(f)

    agents   = [r["agent"] for r in results]
    rewards  = [r["avg_reward"] for r in results]
    waits    = [r["avg_total_wait_s"] for r in results]
    emrg     = [r["avg_emergency_clear_s"] or 0 for r in results]

    x = np.arange(len(agents))
    width = 0.25

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle("Strategy Comparison — Smart Traffic Signal Control", fontsize=13)

    # Reward
    axes[0].bar(x, rewards, color=["steelblue", "coral", "mediumseagreen"])
    axes[0].set_title("Average Episode Reward")
    axes[0].set_ylabel("Reward (higher = better)")
    axes[0].set_xticks(x); axes[0].set_xticklabels(agents, rotation=15, ha="right")
    axes[0].grid(axis="y", alpha=0.3)

    # Wait time
    axes[1].bar(x, waits, color=["steelblue", "coral", "mediumseagreen"])
    axes[1].set_title("Total Vehicle Wait Time")
    axes[1].set_ylabel("Total wait (s, lower = better)")
    axes[1].set_xticks(x); axes[1].set_xticklabels(agents, rotation=15, ha="right")
    axes[1].grid(axis="y", alpha=0.3)

    # Emergency
    axes[2].bar(x, emrg, color=["steelblue", "coral", "mediumseagreen"])
    axes[2].set_title("Emergency Clear Time")
    axes[2].set_ylabel("Seconds to clear (lower = better)")
    axes[2].set_xticks(x); axes[2].set_xticklabels(agents, rotation=15, ha="right")
    axes[2].grid(axis="y", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "benchmark_comparison.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved: {path}")
    plt.close(fig)


def plot_signal_episode(model_path: str = "../../backend/models/traffic_rl_agent.zip"):
    """
    Runs one episode with the RL agent and plots:
      - Vehicle queue per lane over time
      - Active signal phase over time
    """
    if not HAS_MPL:
        return

    from gym_envs.traffic_env import TrafficJunctionEnv

    try:
        from stable_baselines3 import PPO
        model = PPO.load(model_path)
    except Exception as e:
        print(f"Could not load RL model: {e}")
        return

    env = TrafficJunctionEnv(junction_type="4way")
    obs, _ = env.reset()

    history = {"N": [], "S": [], "E": [], "W": [], "phase": [], "t": []}
    done = False
    t = 0

    while not done and t < 500:
        action, _ = model.predict(obs, deterministic=True)
        obs, _, terminated, truncated, info = env.step(action)
        done = terminated or truncated

        for lane in ["N", "S", "E", "W"]:
            history[lane].append(info["vehicle_counts"].get(lane, 0))
        history["phase"].append(int(obs[4]))
        history["t"].append(t)
        t += 1

    env.close()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

    for lane, color in zip(["N", "S", "E", "W"], ["#2196F3", "#F44336", "#4CAF50", "#FF9800"]):
        ax1.plot(history["t"], history[lane], label=f"Lane {lane}", color=color, linewidth=1.5)
    ax1.set_ylabel("Vehicle queue length")
    ax1.set_title("RL Agent — One Episode (4-way junction, 500 seconds)")
    ax1.legend(ncol=4, loc="upper right")
    ax1.grid(alpha=0.3)

    ax2.step(history["t"], history["phase"], where="post", color="purple", linewidth=2)
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["N/S green", "E/W green"])
    ax2.set_xlabel("Simulated seconds")
    ax2.set_ylabel("Active phase")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "episode_visualisation.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved: {path}")
    plt.close(fig)


if __name__ == "__main__":
    print("Generating visualisations...\n")
    plot_learning_curve()
    plot_benchmark_comparison()
    plot_signal_episode()
    print("\nAll plots saved to:", OUTPUT_DIR)
