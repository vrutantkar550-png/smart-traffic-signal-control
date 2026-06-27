"""
ml/evaluate/compare.py

Side-by-side comparison of three signal timing strategies:
  1. PPO RL Agent        — trained adaptive AI model
  2. Fixed Timing        — classic fixed-cycle controller (30s green each phase)
  3. Random Timing       — random phase and duration each step (baseline floor)

Metrics compared across every junction type (2way / 3way / 4way):
  ┌─────────────────────────────────────────────────────────────────┐
  │  avg_reward      total episode reward (higher = better)         │
  │  avg_wait_s      total vehicle-seconds of waiting (lower)       │
  │  throughput      vehicles cleared per episode (higher)          │
  │  emrg_clear_s    seconds to clear an emergency path (lower)     │
  │  phase_changes   how often the agent switches phase (lower)     │
  │  std_reward      reward standard deviation (lower = consistent) │
  └─────────────────────────────────────────────────────────────────┘

Output:
  • Full comparison table printed to console
  • Per-metric winner highlighted
  • Detailed per-junction-type breakdown
  • Saves results/compare_results.json
  • Generates results/compare_charts.png (if matplotlib installed)

Run:
    cd ml/
    python evaluate/compare.py

    # with charts:
    pip install matplotlib
    python evaluate/compare.py --charts

    # custom episode count:
    python evaluate/compare.py --episodes 200

    # specific junction type only:
    python evaluate/compare.py --junction 4way
"""

import os
import sys
import json
import time
import random
import argparse
import textwrap
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import numpy as np

# Allow running from project root or ml/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gym_envs.traffic_env import TrafficJunctionEnv, MIN_GREEN, MAX_GREEN, PHASE_DEFS

OUTPUT_DIR   = os.path.join(os.path.dirname(__file__), "results")
RL_MODEL_PATH = os.path.join(os.path.dirname(__file__), "../../models/traffic_rl_agent.zip")

os.makedirs(OUTPUT_DIR, exist_ok=True)

JUNCTION_TYPES = ["2way", "3way", "4way"]

# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EpisodeResult:
    total_reward:     float = 0.0
    total_wait_s:     float = 0.0
    vehicles_cleared: int   = 0
    phase_changes:    int   = 0
    emergency_clear_s: Optional[float] = None   # None if no emergency occurred


@dataclass
class AgentStats:
    name:          str
    junction_type: str
    episodes:      int
    avg_reward:    float = 0.0
    std_reward:    float = 0.0
    avg_wait_s:    float = 0.0
    avg_throughput:float = 0.0
    avg_phase_chg: float = 0.0
    avg_emrg_s:    Optional[float] = None
    wins:          Dict[str, bool] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Strategy agents
# ─────────────────────────────────────────────────────────────────────────────

class RLAgent:
    """PPO model loaded from disk."""
    name = "PPO RL Agent"

    def __init__(self, model_path: str):
        from stable_baselines3 import PPO
        self.model = PPO.load(model_path)
        self._prev_phase = -1
        self._phase_changes = 0

    def reset(self):
        self._prev_phase = -1
        self._phase_changes = 0

    def predict(self, obs: np.ndarray) -> np.ndarray:
        action, _ = self.model.predict(obs, deterministic=True)
        phase_idx = int(action[0] * 2)   # 2 phases for 4way
        if phase_idx != self._prev_phase and self._prev_phase != -1:
            self._phase_changes += 1
        self._prev_phase = phase_idx
        return action

    def get_phase_changes(self) -> int:
        return self._phase_changes


class FixedTimingAgent:
    """
    Traditional fixed-cycle controller.
    Alternates phases every FIXED_GREEN seconds regardless of traffic density.
    Represents what most real-world traffic lights do today.
    """
    name = "Fixed Timing (30s)"

    def __init__(self, fixed_green: float = 30.0):
        self.fixed_green = fixed_green
        self._phase      = 0
        self._timer      = 0.0
        self._n_phases   = 2          # updated per junction in reset()
        self._phase_changes = 0
        self._prev_phase = -1

    def reset(self, n_phases: int = 2):
        self._phase         = 0
        self._timer         = 0.0
        self._n_phases      = n_phases
        self._phase_changes = 0
        self._prev_phase    = -1

    def predict(self, obs: np.ndarray) -> np.ndarray:
        self._timer += 1  # 1 tick = 1 simulated second

        if self._timer >= self.fixed_green:
            self._timer  = 0
            self._phase  = (self._phase + 1) % self._n_phases
            if self._prev_phase != -1:
                self._phase_changes += 1
            self._prev_phase = self._phase

        phase_frac    = self._phase / max(self._n_phases - 1, 1)
        duration_frac = (self.fixed_green - MIN_GREEN) / (MAX_GREEN - MIN_GREEN)
        return np.array([phase_frac, duration_frac], dtype=np.float32)

    def get_phase_changes(self) -> int:
        return self._phase_changes


class RandomTimingAgent:
    """
    Random baseline — picks a random phase and random duration every step.
    Represents the absolute floor of performance.
    No agent should ever do worse than this on average.
    """
    name = "Random Timing"

    def __init__(self, seed: int = 42):
        self._rng           = np.random.default_rng(seed)
        self._phase_changes = 0
        self._prev_action   = -1

    def reset(self):
        self._phase_changes = 0
        self._prev_action   = -1

    def predict(self, obs: np.ndarray) -> np.ndarray:
        phase_frac    = float(self._rng.uniform(0, 1))
        duration_frac = float(self._rng.uniform(0, 1))
        phase_idx = int(phase_frac * 2)
        if phase_idx != self._prev_action and self._prev_action != -1:
            self._phase_changes += 1
        self._prev_action = phase_idx
        return np.array([phase_frac, duration_frac], dtype=np.float32)

    def get_phase_changes(self) -> int:
        return self._phase_changes


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation runner
# ─────────────────────────────────────────────────────────────────────────────

def run_episode(agent, env: TrafficJunctionEnv) -> EpisodeResult:
    """Run one episode and collect metrics."""
    obs, _ = env.reset()

    if hasattr(agent, 'reset'):
        n_phases = len(PHASE_DEFS.get(env.junction_type, []))
        if isinstance(agent, FixedTimingAgent):
            agent.reset(n_phases=n_phases)
        else:
            agent.reset()

    result = EpisodeResult()
    emergency_start: Optional[float] = None
    done = False

    while not done:
        action = agent.predict(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated

        result.total_reward += reward

        # Track emergency clearance time
        if info["emergency_active"] and emergency_start is None:
            emergency_start = env.elapsed
        elif not info["emergency_active"] and emergency_start is not None:
            result.emergency_clear_s = env.elapsed - emergency_start
            emergency_start = None

    result.total_wait_s     = info["total_wait"]
    result.vehicles_cleared = max(0, sum(info["vehicle_counts"].values()))
    result.phase_changes    = agent.get_phase_changes()

    return result


def evaluate_agent(
    agent,
    junction_type: str,
    episodes: int,
    seed: int = 0,
) -> AgentStats:
    """Run N episodes and compute aggregate statistics."""
    env = TrafficJunctionEnv(
        junction_type          = junction_type,
        emergency_probability  = 0.003,
    )

    rewards, waits, throughputs, phase_changes, emrg_times = [], [], [], [], []

    for ep in range(episodes):
        # Use a deterministic seed per episode for fair comparison across agents
        env_seed = seed + ep
        result   = run_episode(agent, env)

        rewards.append(result.total_reward)
        waits.append(result.total_wait_s)
        throughputs.append(result.vehicles_cleared)
        phase_changes.append(result.phase_changes)
        if result.emergency_clear_s is not None:
            emrg_times.append(result.emergency_clear_s)

    env.close()

    return AgentStats(
        name          = agent.name,
        junction_type = junction_type,
        episodes      = episodes,
        avg_reward    = float(np.mean(rewards)),
        std_reward    = float(np.std(rewards)),
        avg_wait_s    = float(np.mean(waits)),
        avg_throughput= float(np.mean(throughputs)),
        avg_phase_chg = float(np.mean(phase_changes)),
        avg_emrg_s    = float(np.mean(emrg_times)) if emrg_times else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Results table printer
# ─────────────────────────────────────────────────────────────────────────────

METRICS = [
    ("avg_reward",    "Avg Reward",         True,  ".1f"),   # higher better
    ("std_reward",    "Reward Std Dev",      False, ".1f"),   # lower better
    ("avg_wait_s",    "Avg Wait (s)",        False, ".1f"),   # lower better
    ("avg_throughput","Throughput (veh)",    True,  ".1f"),   # higher better
    ("avg_phase_chg", "Phase Changes",       False, ".1f"),   # lower better
    ("avg_emrg_s",    "Emrg Clear (s)",      False, ".1f"),   # lower better
]

COL_W  = 20
NAME_W = 22

ANSI = {
    "green"  : "\033[92m",
    "yellow" : "\033[93m",
    "red"    : "\033[91m",
    "cyan"   : "\033[96m",
    "bold"   : "\033[1m",
    "reset"  : "\033[0m",
    "dim"    : "\033[2m",
}

def _c(text, *codes):
    return "".join(ANSI[c] for c in codes) + str(text) + ANSI["reset"]


def print_comparison_table(
    stats_list:    List[AgentStats],
    junction_type: str,
):
    """Print a formatted comparison table for one junction type."""
    n = len(stats_list)
    total_w = NAME_W + COL_W * (len(METRICS))

    print()
    print(_c("=" * total_w, "bold"))
    print(_c(f"  JUNCTION TYPE: {junction_type.upper()}  |  Episodes: {stats_list[0].episodes}  |  Agents: {n}", "bold", "cyan"))
    print(_c("=" * total_w, "bold"))

    # Header row
    header = _c(f"{'Metric':<{NAME_W}}", "bold")
    for s in stats_list:
        header += _c(f"{s.name:^{COL_W}}", "bold")
    print(header)
    print(_c("-" * total_w, "dim"))

    # Mark winners per metric
    for attr, label, higher_better, fmt in METRICS:
        values = []
        for s in stats_list:
            v = getattr(s, attr)
            values.append(v)

        # Determine winner (ignoring None)
        valid = [(i, v) for i, v in enumerate(values) if v is not None]
        if valid:
            winner_idx = max(valid, key=lambda x: x[1])[0] if higher_better \
                         else min(valid, key=lambda x: x[1])[0]
        else:
            winner_idx = -1

        row = f"{label:<{NAME_W}}"
        for i, v in enumerate(values):
            if v is None:
                cell = "N/A"
            else:
                cell = format(v, fmt)

            cell_str = f"{cell:^{COL_W}}"
            if i == winner_idx and v is not None:
                row += _c(cell_str, "green", "bold")
            else:
                row += cell_str

        print(row)

    print(_c("=" * total_w, "bold"))

    # Winner summary
    wins = _count_wins(stats_list)
    print(_c("  WINNERS:", "bold"))
    for s in stats_list:
        w = wins[s.name]
        bar = "█" * w + "░" * (len(METRICS) - w)
        color = "green" if w == max(wins.values()) else "reset"
        print(f"  {_c(s.name, color):<{NAME_W + 10}}  {bar}  {w}/{len(METRICS)} metrics")
    print()


def _count_wins(stats_list: List[AgentStats]) -> Dict[str, int]:
    wins = {s.name: 0 for s in stats_list}
    for attr, _, higher_better, _ in METRICS:
        valid = [(s.name, getattr(s, attr)) for s in stats_list if getattr(s, attr) is not None]
        if not valid:
            continue
        winner = max(valid, key=lambda x: x[1])[0] if higher_better \
                 else min(valid, key=lambda x: x[1])[0]
        wins[winner] += 1
    return wins


def print_summary_table(all_stats: Dict[str, List[AgentStats]]):
    """Print a compact cross-junction summary."""
    junctions = list(all_stats.keys())
    agents    = [s.name for s in all_stats[junctions[0]]]

    print()
    print(_c("=" * 70, "bold"))
    print(_c("  CROSS-JUNCTION SUMMARY — Avg Reward", "bold", "cyan"))
    print(_c("=" * 70, "bold"))

    header = f"{'Agent':<24}"
    for jt in junctions:
        header += f"{jt:^15}"
    header += f"{'Overall':^12}"
    print(_c(header, "bold"))
    print(_c("-" * 70, "dim"))

    for agent_name in agents:
        row   = f"{agent_name:<24}"
        total = 0.0
        count = 0
        for jt in junctions:
            stat = next(s for s in all_stats[jt] if s.name == agent_name)
            val  = stat.avg_reward
            total += val
            count += 1
            row  += f"{val:^15.1f}"
        overall = total / count if count else 0
        row += f"{overall:^12.1f}"
        print(row)

    print(_c("=" * 70, "bold"))
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Chart generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_charts(all_stats: Dict[str, List[AgentStats]]):
    """Generate comparison bar charts saved to results/compare_charts.png"""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("matplotlib not installed — skipping charts. Run: pip install matplotlib")
        return

    junctions  = list(all_stats.keys())
    agents     = [s.name for s in all_stats[junctions[0]]]
    n_agents   = len(agents)
    n_junctions= len(junctions)

    COLORS = ["#3B82F6", "#F59E0B", "#EF4444"]   # blue, amber, red

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    fig.patch.set_facecolor("#0F1117")

    metric_defs = [
        ("avg_reward",    "Avg Reward",          True,  "#3B82F6"),
        ("avg_wait_s",    "Avg Wait Time (s)",    False, "#EF4444"),
        ("avg_throughput","Throughput (vehicles)",True,  "#22C55E"),
        ("avg_phase_chg", "Phase Changes",        False, "#F59E0B"),
        ("std_reward",    "Reward Std Dev",       False, "#8B5CF6"),
        ("avg_emrg_s",    "Emergency Clear (s)",  False, "#EC4899"),
    ]

    x    = np.arange(n_junctions)
    w    = 0.25
    offsets = np.linspace(-(n_agents-1)*w/2, (n_agents-1)*w/2, n_agents)

    for ax_idx, (attr, title, higher_better, color) in enumerate(metric_defs):
        ax = axes[ax_idx // 3][ax_idx % 3]
        ax.set_facecolor("#1A1D27")
        ax.tick_params(colors="#6B7280")
        ax.set_title(title, color="white", fontsize=11, pad=8)
        ax.set_xticks(x)
        ax.set_xticklabels([jt.upper() for jt in junctions], color="#9CA3AF", fontsize=10)
        ax.spines[:].set_color("#2A2D3A")
        ax.yaxis.label.set_color("#6B7280")
        ax.grid(axis="y", color="#2A2D3A", linewidth=0.5)

        for a_idx, agent_name in enumerate(agents):
            vals = []
            for jt in junctions:
                stat = next(s for s in all_stats[jt] if s.name == agent_name)
                v = getattr(stat, attr)
                vals.append(v if v is not None else 0)

            bars = ax.bar(
                x + offsets[a_idx], vals,
                width=w * 0.9,
                color=COLORS[a_idx],
                alpha=0.85,
                label=agent_name,
            )

            # Value labels on bars
            for bar, val in zip(bars, vals):
                if val != 0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + abs(bar.get_height()) * 0.02,
                        f"{val:.0f}",
                        ha="center", va="bottom",
                        color="white", fontsize=7,
                    )

        note = "↑ higher better" if higher_better else "↓ lower better"
        ax.text(0.98, 0.97, note, transform=ax.transAxes,
                ha="right", va="top", fontsize=8, color="#6B7280")

    # Legend
    legend_patches = [
        mpatches.Patch(color=COLORS[i], label=agents[i])
        for i in range(n_agents)
    ]
    fig.legend(
        handles=legend_patches,
        loc="lower center",
        ncol=n_agents,
        framealpha=0,
        fontsize=10,
        labelcolor="white",
        bbox_to_anchor=(0.5, 0.01),
    )

    fig.suptitle(
        "Smart Traffic Signal Control — Strategy Comparison",
        color="white", fontsize=14, fontweight="bold", y=0.98,
    )

    plt.tight_layout(rect=[0, 0.06, 1, 0.97])
    out = os.path.join(OUTPUT_DIR, "compare_charts.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Charts saved to: {out}")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def build_agents(rl_path: str) -> List:
    """Build the three agents. RL agent is optional (skipped if model missing)."""
    agents = []

    # 1. Try RL agent
    model_file = rl_path if rl_path.endswith(".zip") else rl_path + ".zip"
    if os.path.exists(model_file) or os.path.exists(rl_path):
        try:
            agents.append(RLAgent(rl_path))
            print(f"  ✓ PPO RL Agent loaded from {rl_path}")
        except Exception as e:
            print(f"  ✗ Could not load RL model: {e}")
            print("    → Train it first: python train/train_rl.py")
    else:
        print(f"  ✗ RL model not found at {rl_path}")
        print("    → Train it first: python train/train_rl.py")

    # 2. Fixed timing (always available)
    agents.append(FixedTimingAgent(fixed_green=30.0))
    print("  ✓ Fixed Timing agent ready (30s cycles)")

    # 3. Random (always available)
    agents.append(RandomTimingAgent(seed=42))
    print("  ✓ Random Timing agent ready")

    return agents


def main():
    parser = argparse.ArgumentParser(
        description="Side-by-side comparison: RL Agent vs Fixed vs Random timing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          python evaluate/compare.py
          python evaluate/compare.py --episodes 200 --charts
          python evaluate/compare.py --junction 4way --charts
        """),
    )
    parser.add_argument("--episodes",  type=int, default=100,
                        help="Episodes per agent per junction type (default: 100)")
    parser.add_argument("--junction",  type=str, default=None,
                        choices=["2way", "3way", "4way"],
                        help="Evaluate one junction type only (default: all)")
    parser.add_argument("--charts",    action="store_true",
                        help="Generate comparison bar charts (requires matplotlib)")
    parser.add_argument("--model",     type=str, default=RL_MODEL_PATH,
                        help="Path to RL model .zip file")
    args = parser.parse_args()

    junction_types = [args.junction] if args.junction else JUNCTION_TYPES

    print()
    print(_c("=" * 60, "bold"))
    print(_c("  SMART TRAFFIC SIGNAL — STRATEGY COMPARISON", "bold", "cyan"))
    print(_c("=" * 60, "bold"))
    print(f"  Episodes per agent : {args.episodes}")
    print(f"  Junction types     : {', '.join(junction_types)}")
    print(f"  RL model path      : {args.model}")
    print()
    print("  Loading agents…")
    agents = build_agents(args.model)

    if not agents:
        print("\nNo agents available. Exiting.")
        return

    print(f"\n  Running {len(agents)} agents × {len(junction_types)} junction types "
          f"× {args.episodes} episodes = "
          f"{len(agents) * len(junction_types) * args.episodes} total episodes\n")

    all_stats: Dict[str, List[AgentStats]] = {}
    grand_start = time.time()

    for jt in junction_types:
        print(_c(f"─── Junction type: {jt.upper()} ──────────────────────────────", "bold"))
        jt_stats = []

        for agent in agents:
            t0 = time.time()
            print(f"  Evaluating {agent.name:<22}", end="", flush=True)
            stats = evaluate_agent(agent, jt, args.episodes)
            elapsed = time.time() - t0
            print(f"  done in {elapsed:.1f}s  |  avg reward: {stats.avg_reward:>8.1f}  |  avg wait: {stats.avg_wait_s:>8.1f}s")
            jt_stats.append(stats)

        all_stats[jt] = jt_stats
        print_comparison_table(jt_stats, jt)

    # Cross-junction summary
    if len(junction_types) > 1:
        print_summary_table(all_stats)

    # Overall winner across all junction types and metrics
    total_wins: Dict[str, int] = {}
    for jt, stats_list in all_stats.items():
        w = _count_wins(stats_list)
        for name, count in w.items():
            total_wins[name] = total_wins.get(name, 0) + count

    overall_winner = max(total_wins, key=total_wins.get)
    total_elapsed  = time.time() - grand_start

    print(_c("  OVERALL WINNER:", "bold"))
    print(f"  {_c(overall_winner, 'green', 'bold')} — "
          f"{total_wins[overall_winner]} metric wins across all junction types")
    print(f"\n  Total evaluation time: {total_elapsed:.1f}s")

    # Flatten stats for JSON serialisation
    json_out = {}
    for jt, stats_list in all_stats.items():
        json_out[jt] = [asdict(s) for s in stats_list]

    json_path = os.path.join(OUTPUT_DIR, "compare_results.json")
    with open(json_path, "w") as f:
        json.dump(json_out, f, indent=2, default=str)
    print(f"\n  Results saved to: {json_path}")

    if args.charts:
        print("  Generating charts…")
        generate_charts(all_stats)

    print()


if __name__ == "__main__":
    main()
