"""
simulation/run_simulation.py

Master simulation runner.
Launches SUMO for each junction type and traffic scenario,
collects vehicle counts per lane per second via TraCI,
and saves CSV files that compare.py and the RL training use.

Two modes:
  1. SUMO mode   — real SUMO simulator (install SUMO first)
  2. Fallback    — built-in Python simulator (no SUMO needed, good for testing)

Usage:
    # Full SUMO simulation (needs SUMO installed)
    python simulation/run_simulation.py --sumo

    # Python fallback (no SUMO needed)
    python simulation/run_simulation.py

    # Specific scenario only
    python simulation/run_simulation.py --junction 4way --scenario medium

    # With real-time visualisation (needs SUMO GUI)
    python simulation/run_simulation.py --sumo --gui --junction 4way

Install SUMO:
    Ubuntu:  sudo apt install sumo sumo-tools sumo-doc
    Mac:     brew install sumo
    Windows: https://sumo.dlr.de/docs/Downloads.php
"""

import os
import sys
import csv
import json
import time
import argparse
import random
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

BASE_DIR  = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs" / "csvs"
LOG_DIR    = BASE_DIR / "outputs" / "logs"
CONFIG_DIR = BASE_DIR / "configs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True,    exist_ok=True)

JUNCTION_TYPES = ["2way", "3way", "4way"]
SCENARIOS      = ["light", "medium", "heavy", "emergency"]

LANE_IDS = {
    "2way": ["N", "S"],
    "3way": ["N", "S", "W"],
    "4way": ["N", "S", "E", "W"],
}

EDGE_IDS = {
    "2way": {"N": "N_in", "S": "S_in"},
    "3way": {"N": "N_in", "S": "S_in", "W": "W_in"},
    "4way": {"N": "N_in", "S": "S_in", "E": "E_in", "W": "W_in"},
}

# Spawn rates (vehicles per second per lane) per scenario
SPAWN_RATES = {
    "light":     {"N": 0.08, "S": 0.08, "E": 0.06, "W": 0.06},
    "medium":    {"N": 0.20, "S": 0.20, "E": 0.15, "W": 0.15},
    "heavy":     {"N": 0.40, "S": 0.40, "E": 0.30, "W": 0.30},
    "emergency": {"N": 0.20, "S": 0.20, "E": 0.15, "W": 0.15},
}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class TickData:
    """One second of simulation data for one junction."""
    timestep:         int
    junction_type:    str
    scenario:         str
    lane_counts:      Dict[str, int] = field(default_factory=dict)
    emergency_active: bool = False
    emergency_lane:   Optional[str] = None


@dataclass
class SimSummary:
    junction_type:       str
    scenario:            str
    total_steps:         int
    total_vehicles:      int
    avg_queue_per_lane:  float
    peak_queue:          int
    emergency_events:    int
    csv_path:            str


# ── SUMO runner (real SUMO via TraCI) ────────────────────────────────────────

def run_sumo(
    junction_type: str,
    scenario:      str,
    gui:           bool = False,
    duration:      int  = 3600,
) -> List[TickData]:
    """
    Run real SUMO simulation via TraCI and collect per-second lane counts.
    Requires SUMO to be installed and SUMO_HOME environment variable set.
    """
    try:
        if "SUMO_HOME" not in os.environ:
            sumo_home = _find_sumo_home()
            if sumo_home:
                os.environ["SUMO_HOME"] = sumo_home
            else:
                raise EnvironmentError("SUMO_HOME not set. Install SUMO first.")

        sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
        import traci
    except ImportError:
        raise ImportError("TraCI not found. Install SUMO: https://sumo.dlr.de/docs/Downloads.php")

    cfg_file = CONFIG_DIR / f"sim_{junction_type}_{scenario}.sumocfg"
    if not cfg_file.exists():
        cfg_file = CONFIG_DIR / f"sim_{junction_type}_medium.sumocfg"

    sumo_bin = "sumo-gui" if gui else "sumo"
    cmd = [sumo_bin, "-c", str(cfg_file), "--no-warnings", "--seed", "42"]

    traci.start(cmd)
    lanes  = LANE_IDS[junction_type]
    edges  = EDGE_IDS[junction_type]
    ticks  = []
    step   = 0

    print(f"  SUMO running: {junction_type} / {scenario}  (duration={duration}s)")

    while step < duration:
        traci.simulationStep()

        # Count vehicles on each incoming edge
        counts = {}
        for lane_id, edge_id in edges.items():
            try:
                counts[lane_id] = traci.edge.getLastStepVehicleNumber(edge_id)
            except Exception:
                counts[lane_id] = 0

        # Check for emergency vehicles
        em_active = False
        em_lane   = None
        for veh_id in traci.vehicle.getIDList():
            try:
                vclass = traci.vehicle.getVehicleClass(veh_id)
                if vclass == "emergency":
                    em_active = True
                    road = traci.vehicle.getRoadID(veh_id)
                    for lid, eid in edges.items():
                        if eid in road:
                            em_lane = lid
                            break
                    break
            except Exception:
                pass

        ticks.append(TickData(
            timestep         = step,
            junction_type    = junction_type,
            scenario         = scenario,
            lane_counts      = counts,
            emergency_active = em_active,
            emergency_lane   = em_lane,
        ))
        step += 1

    traci.close()
    return ticks


# ── Python fallback simulator ─────────────────────────────────────────────────

class PythonSimulator:
    """
    Pure-Python traffic simulator — no SUMO needed.
    Mimics lane queue dynamics:
      - Vehicles arrive with Poisson-distributed inter-arrivals
      - Green phase drains queue at ~2 vehicles/second
      - Phases cycle with configurable timing
    """

    def __init__(self, junction_type: str, scenario: str, seed: int = 42):
        self.junction_type  = junction_type
        self.scenario       = scenario
        self.lanes          = LANE_IDS[junction_type]
        self.rates          = SPAWN_RATES.get(scenario, SPAWN_RATES["medium"])
        self.rng            = random.Random(seed)
        self.np_rng         = __import__("numpy").random.default_rng(seed)

        # Phase cycling
        self._phase_idx     = 0
        self._phase_timer   = 0
        self._phase_green   = self._build_phases()
        self._phase_dur     = 30   # seconds per phase

        # Vehicle queues per lane
        self._queues        = {l: self.rng.randint(0, 5) for l in self.lanes}

        # Emergency state
        self._em_active     = False
        self._em_lane       = None
        self._em_timer      = 0
        self._em_prob       = 0.003 if scenario == "emergency" else 0.001

    def _build_phases(self) -> List[List[str]]:
        """Returns list of green-lane lists per phase."""
        from ml.gym_envs.traffic_env import PHASE_DEFS  # reuse existing defs
        try:
            return [p[0] for p in PHASE_DEFS[self.junction_type]]
        except Exception:
            return [self.lanes[:len(self.lanes)//2], self.lanes[len(self.lanes)//2:]]

    def step(self, timestep: int) -> TickData:
        """Advance simulation by 1 second and return lane counts."""
        # Phase advance
        self._phase_timer += 1
        if self._phase_timer >= self._phase_dur:
            self._phase_timer = 0
            self._phase_idx   = (self._phase_idx + 1) % len(self._phase_green)

        green_lanes = self._phase_green[self._phase_idx]

        # Emergency logic
        if not self._em_active and self.rng.random() < self._em_prob:
            self._em_active = True
            self._em_lane   = self.rng.choice(self.lanes)
            self._em_timer  = 0

        if self._em_active:
            self._em_timer += 1
            if self._em_timer > 60:
                self._em_active = False
                self._em_lane   = None

        # Update queues
        for lane in self.lanes:
            rate     = self.rates.get(lane, 0.15)
            arrivals = int(self.np_rng.poisson(rate))
            self._queues[lane] = min(100, self._queues[lane] + arrivals)

            if lane in green_lanes and not self._em_active:
                departures = min(self._queues[lane], 2)
                self._queues[lane] -= departures

        return TickData(
            timestep         = timestep,
            junction_type    = self.junction_type,
            scenario         = self.scenario,
            lane_counts      = dict(self._queues),
            emergency_active = self._em_active,
            emergency_lane   = self._em_lane,
        )


def run_python_sim(
    junction_type: str,
    scenario:      str,
    duration:      int = 3600,
) -> List[TickData]:
    """Run the Python fallback simulator for `duration` steps."""

    # Must resolve PHASE_DEFS import path
    ml_dir = BASE_DIR.parent / "ml"
    if str(ml_dir) not in sys.path:
        sys.path.insert(0, str(ml_dir))

    sim   = PythonSimulator(junction_type, scenario)
    ticks = []
    print(f"  Python sim: {junction_type} / {scenario}  (duration={duration}s)", end=" ", flush=True)
    t0 = time.time()

    for step in range(duration):
        ticks.append(sim.step(step))

    print(f"→ done in {time.time()-t0:.1f}s")
    return ticks


# ── CSV writer ────────────────────────────────────────────────────────────────

def save_csv(ticks: List[TickData], junction_type: str, scenario: str) -> str:
    """Save tick data to a CSV file. Returns the file path."""
    lanes    = LANE_IDS[junction_type]
    filename = OUTPUT_DIR / f"{junction_type}_{scenario}.csv"

    with open(filename, "w", newline="") as f:
        fieldnames = ["timestep", "junction_type", "scenario",
                      *[f"{l}_count" for l in lanes],
                      "emergency_active", "emergency_lane"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for t in ticks:
            row = {
                "timestep":      t.timestep,
                "junction_type": t.junction_type,
                "scenario":      t.scenario,
                "emergency_active": int(t.emergency_active),
                "emergency_lane":   t.emergency_lane or "",
            }
            for l in lanes:
                row[f"{l}_count"] = t.lane_counts.get(l, 0)
            writer.writerow(row)

    return str(filename)


def summarise(ticks: List[TickData], csv_path: str) -> SimSummary:
    lanes     = list(ticks[0].lane_counts.keys()) if ticks else []
    all_counts= [sum(t.lane_counts.values()) for t in ticks]
    avg_q     = (sum(all_counts) / len(all_counts) / max(len(lanes), 1)) if all_counts else 0
    peak_q    = max(all_counts) if all_counts else 0
    em_events = sum(1 for t in ticks if t.emergency_active and
                    (ticks.index(t) == 0 or not ticks[ticks.index(t)-1].emergency_active))

    return SimSummary(
        junction_type      = ticks[0].junction_type if ticks else "",
        scenario           = ticks[0].scenario if ticks else "",
        total_steps        = len(ticks),
        total_vehicles     = sum(all_counts),
        avg_queue_per_lane = round(avg_q, 2),
        peak_queue         = peak_q,
        emergency_events   = em_events,
        csv_path           = csv_path,
    )


def _find_sumo_home() -> Optional[str]:
    """Try to auto-detect SUMO installation."""
    candidates = [
        "/usr/share/sumo",
        "/opt/homebrew/share/sumo",
        r"C:\Program Files (x86)\Eclipse\Sumo",
        r"C:\sumo",
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run SUMO traffic simulation and generate CSV datasets",
    )
    parser.add_argument("--sumo",     action="store_true", help="Use real SUMO (needs install)")
    parser.add_argument("--gui",      action="store_true", help="Open SUMO-GUI (needs --sumo)")
    parser.add_argument("--junction", type=str, default=None, choices=JUNCTION_TYPES)
    parser.add_argument("--scenario", type=str, default=None, choices=SCENARIOS)
    parser.add_argument("--duration", type=int, default=3600, help="Simulation seconds (default 3600)")
    args = parser.parse_args()

    junctions = [args.junction] if args.junction else JUNCTION_TYPES
    scenarios = [args.scenario] if args.scenario else SCENARIOS

    print("\n" + "=" * 60)
    print("  SMART TRAFFIC — SIMULATION RUNNER")
    print(f"  Mode     : {'SUMO (real)' if args.sumo else 'Python fallback'}")
    print(f"  Junctions: {junctions}")
    print(f"  Scenarios: {scenarios}")
    print(f"  Duration : {args.duration}s per run")
    print("=" * 60 + "\n")

    summaries = []
    total_runs = len(junctions) * len(scenarios)
    run_num    = 0

    for jt in junctions:
        for sc in scenarios:
            run_num += 1
            print(f"[{run_num}/{total_runs}] Simulating {jt} / {sc}…")

            try:
                if args.sumo:
                    ticks = run_sumo(jt, sc, gui=args.gui, duration=args.duration)
                else:
                    ticks = run_python_sim(jt, sc, duration=args.duration)

                csv_path = save_csv(ticks, jt, sc)
                summary  = summarise(ticks, csv_path)
                summaries.append(asdict(summary))

                print(f"  ✓ {csv_path}")
                print(f"    steps={summary.total_steps}  "
                      f"avg_queue/lane={summary.avg_queue_per_lane}  "
                      f"peak={summary.peak_queue}  "
                      f"emergencies={summary.emergency_events}")

            except Exception as e:
                print(f"  ✗ Error: {e}")

    # Save summary JSON
    summary_path = OUTPUT_DIR / "simulation_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summaries, f, indent=2)

    print(f"\nAll CSVs saved to: {OUTPUT_DIR}")
    print(f"Summary saved to : {summary_path}")
    print(f"\nTotal runs completed: {len(summaries)}/{total_runs}")

    if summaries:
        print("\nQuick summary:")
        print(f"  {'Junction':<10} {'Scenario':<12} {'Avg Queue/Lane':>15} {'Peak':>8} {'Emergencies':>12}")
        print("  " + "-" * 60)
        for s in summaries:
            print(f"  {s['junction_type']:<10} {s['scenario']:<12} "
                  f"{s['avg_queue_per_lane']:>15.2f} {s['peak_queue']:>8} "
                  f"{s['emergency_events']:>12}")


if __name__ == "__main__":
    main()
