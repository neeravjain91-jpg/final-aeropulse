#!/usr/bin/env python3
"""AeroPulse-X Embedded Edge Compute Benchmark CLI.

Reproducible benchmark execution for onboard UAV edge digital twin analytics.
Profiles microsecond stage latencies, memory footprint, throughput, sustained load,
and failure resilience across host desktop and physical ARM SBC environments.
"""
import argparse
import json
import sys
from pathlib import Path

# Ensure root repository is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.edge_benchmark import run_benchmark_and_get_summary


def main():
    parser = argparse.ArgumentParser(description="AeroPulse-X Edge Compute Benchmark")
    parser.add_argument("--samples", type=int, default=10000, help="Number of benchmark samples (default: 10000)")
    parser.add_argument("--warmup", type=int, default=500, help="Number of warmup iterations (default: 500)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSON filepath")
    args = parser.parse_args()

    print(f"[AEROPULSE-X] Executing Edge Benchmark ({args.samples} samples, {args.warmup} warmup)...")
    report = run_benchmark_and_get_summary(samples=args.samples, warmup=args.warmup)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("\n" + report.render_summary() + "\n")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"[AEROPULSE-X] Benchmark results exported to: {out_path}")


if __name__ == "__main__":
    main()
