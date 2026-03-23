"""CLI for headless batch optimization.

Usage:
    python3 -m movement_optimizer.cli --exercise squat --body-mass 80 --bar-mass 100
    python3 -m movement_optimizer.cli --exercise deadlift --output results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

import numpy as np

from .exercises import make_clean_config, make_jerk_config, make_snatch_config
from .models import (
    BodyModel,
    make_bench_press_config,
    make_deadlift_config,
    make_full_squat_config,
    make_squat_config,
)
from .trajectory import OptimizationResult, TrajectoryOptimizer

logger = logging.getLogger(__name__)

EXERCISE_FACTORIES = {
    "squat": make_squat_config,
    "full_squat": make_full_squat_config,
    "deadlift": make_deadlift_config,
    "bench_press": make_bench_press_config,
    "clean": make_clean_config,
    "jerk": make_jerk_config,
    "snatch": make_snatch_config,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="movement-optimizer-cli",
        description="Headless batch optimization for barbell exercises.",
    )
    parser.add_argument(
        "--exercise",
        choices=list(EXERCISE_FACTORIES.keys()),
        required=True,
        help="Exercise type to optimize.",
    )
    parser.add_argument(
        "--body-mass",
        type=float,
        default=75.0,
        help="Body mass in kg (default: 75.0).",
    )
    parser.add_argument(
        "--height",
        type=float,
        default=1.75,
        help="Height in metres (default: 1.75).",
    )
    parser.add_argument(
        "--bar-mass",
        type=float,
        default=60.0,
        help="Barbell mass in kg (default: 60.0).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Movement duration in seconds (default: 2.0).",
    )
    parser.add_argument(
        "--smoothness",
        type=float,
        default=1.0,
        help="Smoothness weight (default: 1.0).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save results as JSON. If omitted, prints summary to stdout.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser


def _result_to_summary(result: OptimizationResult, exercise: str) -> dict:
    """Convert an OptimizationResult to a summary dict."""
    peak_torques = np.max(np.abs(result.torques), axis=0)
    return {
        "exercise": exercise,
        "success": result.success,
        "cost": float(result.cost),
        "n_evals": result.n_evals,
        "elapsed_s": float(result.elapsed_s),
        "com_horizontal_range_cm": float(result.com_horizontal_range_cm),
        "peak_torques_Nm": {
            "ankle": float(peak_torques[0]),
            "knee": float(peak_torques[1]),
            "hip": float(peak_torques[2]),
        },
    }


def _result_to_full_dict(result: OptimizationResult, exercise: str) -> dict:
    """Convert to full JSON-serializable dict including arrays."""
    summary = _result_to_summary(result, exercise)
    summary["arrays"] = {
        "t": result.t.tolist(),
        "q": result.q.tolist(),
        "qd": result.qd.tolist(),
        "qdd": result.qdd.tolist(),
        "torques": result.torques.tolist(),
        "power": result.power.tolist(),
        "com": result.com.tolist(),
        "bar": result.bar.tolist(),
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    """Run CLI optimization."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    body = BodyModel(body_mass=args.body_mass, height=args.height)
    bar_mass = args.bar_mass
    exercise = args.exercise
    duration = args.duration
    smoothness = args.smoothness

    factory = EXERCISE_FACTORIES[exercise]
    config = factory(body, bar_mass)

    if len(config) == 5:
        dyn, qs, qe, qb, q_via = config
    else:
        dyn, qs, qe, qb = config
        q_via = None

    # Enforce minimum duration for multi-phase exercises
    if exercise in ("full_squat", "snatch"):
        duration = max(duration, 3.0)
    elif exercise in ("clean", "jerk"):
        duration = max(duration, 2.0)

    logger.info(
        "Optimizing %s: body=%.0fkg, height=%.2fm, bar=%.0fkg, dur=%.1fs",
        exercise,
        args.body_mass,
        args.height,
        bar_mass,
        duration,
    )

    t_start = time.perf_counter()
    opt = TrajectoryOptimizer(
        body,
        dyn,
        exercise,
        bar_mass,
        qs,
        qe,
        qb,
        q_via=q_via,
        duration=duration,
        n_waypoints=12,
        smoothness=smoothness,
    )
    result = opt.optimize()
    elapsed = time.perf_counter() - t_start

    logger.info(
        "Optimization completed in %.1fs (cost=%.2f, success=%s)",
        elapsed,
        result.cost,
        result.success,
    )

    if args.output:
        full_data = _result_to_full_dict(result, exercise)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(full_data, f, indent=2)
        logger.info("Results saved to %s", args.output)
    else:
        summary = _result_to_summary(result, exercise)
        print(json.dumps(summary, indent=2))

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
