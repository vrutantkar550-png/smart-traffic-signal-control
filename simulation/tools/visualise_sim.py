"""
simulation/tools/visualise_sim.py

Visualises simulation output CSV files.
Generates plots showing:
  - Vehicle queue per lane over time
  - Emergency event windows (red shading)
  - Phase timing (if available)
  - Scenario comparison (light vs medium vs heavy)

Usage:
    pip install matplotlib pandas
    python simulation/tools/visualise_sim.py --junction 4way --scenario medium
    python simulation/tools/visualise_sim.py --junction 4way --compare
"""

import os
import sys
import csv
import argparse
from pathlib import Path
from collections import defaultdict

BASE_DIR  = Path(__file__).parent.parent
CSV_DIR   = BASE_DIR / "outputs" / "csvs"
PLOT_DIR  = BASE_DIR / "outputs" / "videos"   # store PNGs alongside video frames
PLOT_DIR.mkdir(parents=True, exist_ok=True)

LANES = {
    "2way": ["N", "S"],
    "3way": ["N", "S", "W"],
    "4way": ["N", "S", "E", "W"],
}

LANE_COLORS = {
    "N": "#3B82F6",   # blue
    "S": "#EF4444",   # red
    "E": "#22C55E",   # green
    "W": "#F59E0B",   # amber
}

SCENARIO_STYLES = {
    "light":     ("--",  0.6),
    "medium":    ("-",   0.9),
    "heavy":     ("-",   1.0),
    "emergency": (":",   0.8),
}


def load_csv(junction_type: str, scenario: str):
    path = CSV_DIR / f"{junction_type}_{scenario}.csv"
    if not path.exists():
        print(f"CSV not found: {path}. Run run_simulation.py first.")
        return [], []

    rows, em_windows = [], []
    in_em = False
    em_start = None

    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
            active = row.get("emergency_active", "0") == "1"
            t = int(row.get("timestep", 0))
            if active and not in_em:
                in_em = True; em_start = t
            elif not active and in_em:
                em_windows.append((em_start, t)); in_em = False

    return rows, em_windows


def plot_single(junction_type: str, scenario: str):
    """Plot queue lengths over time for one CSV."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("Install matplotlib: pip install matplotlib"); return

    rows, em_windows = load_csv(junction_type, scenario)
    if not rows: return

    lanes  = LANES[junction_type]
    times  = [int(r["timestep"]) for r in rows]
    queues = {l: [int(r.get(f"{l}_count", 0)) for r in rows] for l in lanes}

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    fig.patch.set_facecolor("#0F1117")
    fig.suptitle(
        f"Traffic Simulation — {junction_type.upper()} junction / {scenario.upper()} scenario",
        color="white", fontsize=13, fontweight="bold",
    )

    for ax in (ax1, ax2):
        ax.set_facecolor("#1A1D27")
        ax.spines[:].set_color("#2A2D3A")
        ax.tick_params(colors="#6B7280")
        ax.grid(color="#2A2D3A", linewidth=0.5, linestyle="--")

    # Emergency shading
    for start, end in em_windows:
        ax1.axvspan(start, end, color="#EF4444", alpha=0.15)
        ax2.axvspan(start, end, color="#EF4444", alpha=0.15)

    # Queue lines
    for lane in lanes:
        ax1.plot(times, queues[lane],
                 color=LANE_COLORS.get(lane, "white"),
                 linewidth=1.5, label=f"Lane {lane}", alpha=0.9)

    ax1.set_ylabel("Vehicle queue length", color="#9CA3AF")
    ax1.legend(ncol=len(lanes), loc="upper right",
               labelcolor="white", framealpha=0.2, fontsize=9)

    # Rolling average (smoothed)
    window = 60
    for lane in lanes:
        vals    = queues[lane]
        smoothed= [sum(vals[max(0,i-window):i+1]) / min(i+1, window) for i in range(len(vals))]
        ax2.plot(times, smoothed,
                 color=LANE_COLORS.get(lane, "white"),
                 linewidth=2, alpha=0.85)

    ax2.set_ylabel(f"Queue (smoothed {window}s avg)", color="#9CA3AF")
    ax2.set_xlabel("Simulation time (seconds)", color="#9CA3AF")

    # Emergency legend patch
    if em_windows:
        em_patch = mpatches.Patch(color="#EF4444", alpha=0.3, label=f"Emergency ({len(em_windows)} events)")
        ax1.legend(handles=[*ax1.get_legend().legend_handles, em_patch],
                   ncol=len(lanes)+1, loc="upper right",
                   labelcolor="white", framealpha=0.2, fontsize=9)

    plt.tight_layout()
    out = PLOT_DIR / f"sim_{junction_type}_{scenario}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved: {out}")
    plt.close(fig)


def plot_compare(junction_type: str, scenarios=("light", "medium", "heavy")):
    """Overlay multiple scenarios for one lane to show load difference."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Install matplotlib: pip install matplotlib"); return

    lanes  = LANES[junction_type]
    n_lanes= len(lanes)

    fig, axes = plt.subplots(1, n_lanes, figsize=(5 * n_lanes, 5), sharey=False)
    if n_lanes == 1: axes = [axes]

    fig.patch.set_facecolor("#0F1117")
    fig.suptitle(
        f"Scenario Comparison — {junction_type.upper()} junction",
        color="white", fontsize=13, fontweight="bold",
    )

    for ax, lane in zip(axes, lanes):
        ax.set_facecolor("#1A1D27")
        ax.spines[:].set_color("#2A2D3A")
        ax.tick_params(colors="#6B7280")
        ax.grid(color="#2A2D3A", linewidth=0.5)
        ax.set_title(f"Lane {lane}", color="white", fontsize=11)
        ax.set_xlabel("Time (s)", color="#9CA3AF")
        ax.set_ylabel("Queue length", color="#9CA3AF")

        for sc in scenarios:
            rows, _ = load_csv(junction_type, sc)
            if not rows: continue
            times  = [int(r["timestep"]) for r in rows]
            vals   = [int(r.get(f"{lane}_count", 0)) for r in rows]
            ls, alpha = SCENARIO_STYLES.get(sc, ("-", 0.9))

            # Smooth for readability
            w = 30
            smooth = [sum(vals[max(0,i-w):i+1])/min(i+1,w) for i in range(len(vals))]
            ax.plot(times, smooth, linestyle=ls, alpha=alpha,
                    linewidth=1.8, label=sc.capitalize())

        ax.legend(labelcolor="white", framealpha=0.2, fontsize=9)

    plt.tight_layout()
    out = PLOT_DIR / f"compare_{junction_type}_scenarios.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved: {out}")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Visualise simulation CSV outputs")
    parser.add_argument("--junction", type=str, default="4way",
                        choices=["2way","3way","4way"])
    parser.add_argument("--scenario", type=str, default="medium",
                        choices=["light","medium","heavy","emergency"])
    parser.add_argument("--compare",  action="store_true",
                        help="Overlay light/medium/heavy for comparison")
    args = parser.parse_args()

    if args.compare:
        print(f"Generating scenario comparison for {args.junction}…")
        plot_compare(args.junction)
    else:
        print(f"Generating plot for {args.junction}/{args.scenario}…")
        plot_single(args.junction, args.scenario)


if __name__ == "__main__":
    main()
