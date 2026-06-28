"""
simulation/tools/csv_to_training_data.py

Converts raw simulation CSV files (from run_simulation.py)
into the format the RL training environment uses for
initialising vehicle counts at episode start.

Also generates:
  - Per-scenario statistics summary
  - Arrival rate estimates per lane (used for training config)
  - Emergency event timestamps list

Output:
  simulation/outputs/csvs/training_data_<junction>_<scenario>.json

Usage:
    python simulation/tools/csv_to_training_data.py
    python simulation/tools/csv_to_training_data.py --junction 4way --scenario medium
"""

import os
import sys
import csv
import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

BASE_DIR   = Path(__file__).parent.parent
CSV_DIR    = BASE_DIR / "outputs" / "csvs"
OUTPUT_DIR = BASE_DIR / "outputs" / "csvs"

JUNCTION_TYPES = ["2way", "3way", "4way"]
SCENARIOS      = ["light", "medium", "heavy", "emergency"]

LANES = {
    "2way": ["N", "S"],
    "3way": ["N", "S", "W"],
    "4way": ["N", "S", "E", "W"],
}


def load_csv(junction_type: str, scenario: str) -> List[dict]:
    """Load a simulation CSV into a list of row dicts."""
    path = CSV_DIR / f"{junction_type}_{scenario}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"CSV not found: {path}\n"
            f"Run first: python simulation/run_simulation.py --junction {junction_type} --scenario {scenario}"
        )

    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def compute_arrival_rates(rows: List[dict], lanes: List[str]) -> Dict[str, float]:
    """
    Estimate mean arrival rate (vehicles/second) per lane.
    Uses delta between consecutive counts as a proxy for arrivals.
    """
    totals = defaultdict(float)
    counts = defaultdict(int)

    for i in range(1, len(rows)):
        for lane in lanes:
            key  = f"{lane}_count"
            prev = int(rows[i-1].get(key, 0))
            curr = int(rows[i].get(key, 0))
            # Positive delta = more vehicles arrived than departed
            delta = max(0, curr - prev)
            totals[lane] += delta
            counts[lane] += 1

    return {
        lane: round(totals[lane] / max(counts[lane], 1), 4)
        for lane in lanes
    }


def find_emergency_windows(rows: List[dict]) -> List[Dict]:
    """Extract time windows when emergencies were active."""
    windows = []
    in_emergency = False
    start_t = None
    em_lane = None

    for row in rows:
        active = row.get("emergency_active", "0") == "1"
        lane   = row.get("emergency_lane", "") or None
        t      = int(row.get("timestep", 0))

        if active and not in_emergency:
            in_emergency = True
            start_t = t
            em_lane = lane
        elif not active and in_emergency:
            windows.append({
                "start_s":  start_t,
                "end_s":    t,
                "duration": t - start_t,
                "lane":     em_lane,
            })
            in_emergency = False

    if in_emergency and start_t is not None:
        windows.append({"start_s": start_t, "end_s": len(rows), "duration": len(rows)-start_t, "lane": em_lane})

    return windows


def compute_percentile_queues(rows: List[dict], lanes: List[str]) -> Dict[str, dict]:
    """Compute p50/p95 queue lengths per lane for training bounds."""
    import statistics
    per_lane = defaultdict(list)
    for row in rows:
        for lane in lanes:
            per_lane[lane].append(int(row.get(f"{lane}_count", 0)))

    result = {}
    for lane, vals in per_lane.items():
        s = sorted(vals)
        n = len(s)
        result[lane] = {
            "mean":  round(statistics.mean(vals), 2),
            "p50":   s[n // 2],
            "p95":   s[int(n * 0.95)],
            "max":   max(vals),
        }
    return result


def process(junction_type: str, scenario: str) -> dict:
    """Full processing pipeline for one CSV file."""
    lanes = LANES[junction_type]
    rows  = load_csv(junction_type, scenario)

    if not rows:
        raise ValueError(f"Empty CSV for {junction_type}/{scenario}")

    arrival_rates    = compute_arrival_rates(rows, lanes)
    emergency_windows= find_emergency_windows(rows)
    queue_stats      = compute_percentile_queues(rows, lanes)

    # Sample initial states — pick rows spaced evenly for varied episode starts
    n_samples   = min(100, len(rows))
    sample_step = max(1, len(rows) // n_samples)
    init_states = []
    for i in range(0, len(rows), sample_step):
        row = rows[i]
        state = {lane: int(row.get(f"{lane}_count", 0)) for lane in lanes}
        init_states.append(state)

    result = {
        "junction_type":     junction_type,
        "scenario":          scenario,
        "total_timesteps":   len(rows),
        "lanes":             lanes,
        "arrival_rates":     arrival_rates,
        "queue_statistics":  queue_stats,
        "emergency_windows": emergency_windows,
        "n_emergencies":     len(emergency_windows),
        "init_state_samples":init_states[:50],  # first 50 for training
    }

    # Save JSON
    out_path = OUTPUT_DIR / f"training_data_{junction_type}_{scenario}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


def print_report(result: dict):
    """Print a human-readable summary of one processed CSV."""
    jt = result["junction_type"]
    sc = result["scenario"]
    print(f"\n  {jt.upper()} / {sc.upper()}")
    print(f"  {'─'*40}")
    print(f"  Timesteps     : {result['total_timesteps']}")
    print(f"  Emergencies   : {result['n_emergencies']}")
    print(f"  Arrival rates (veh/s):")
    for lane, rate in result["arrival_rates"].items():
        print(f"    Lane {lane}: {rate:.4f}")
    print(f"  Queue stats (p50 / p95 / max):")
    for lane, stats in result["queue_statistics"].items():
        print(f"    Lane {lane}: {stats['p50']} / {stats['p95']} / {stats['max']}")


def main():
    parser = argparse.ArgumentParser(description="Convert simulation CSVs to RL training data")
    parser.add_argument("--junction", type=str, default=None, choices=JUNCTION_TYPES)
    parser.add_argument("--scenario", type=str, default=None, choices=SCENARIOS)
    args = parser.parse_args()

    junctions = [args.junction] if args.junction else JUNCTION_TYPES
    scenarios = [args.scenario] if args.scenario else SCENARIOS

    print("\n" + "=" * 55)
    print("  SIMULATION DATA PROCESSOR")
    print("=" * 55)

    processed = 0
    for jt in junctions:
        for sc in scenarios:
            try:
                result = process(jt, sc)
                print_report(result)
                out = OUTPUT_DIR / f"training_data_{jt}_{sc}.json"
                print(f"  → Saved: {out}")
                processed += 1
            except FileNotFoundError as e:
                print(f"\n  ✗ {e}")
            except Exception as e:
                print(f"\n  ✗ Error processing {jt}/{sc}: {e}")

    print(f"\n  Done. {processed} files processed → {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
