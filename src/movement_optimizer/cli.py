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
from pathlib import Path

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
    """Build the argument parser for the CLI.

    Returns:
        Configured ArgumentParser instance with all CLI flags registered.
    """
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
    # Extract arrays first (LoD: avoid chaining .attribute.method())
    t_list = result.t.tolist()
    q_list = result.q.tolist()
    qd_list = result.qd.tolist()
    qdd_list = result.qdd.tolist()
    torques_list = result.torques.tolist()
    power_list = result.power.tolist()
    com_list = result.com.tolist()
    bar_list = result.bar.tolist()
    summary["arrays"] = {
        "t": t_list,
        "q": q_list,
        "qd": qd_list,
        "qdd": qdd_list,
        "torques": torques_list,
        "power": power_list,
        "com": com_list,
        "bar": bar_list,
    }
    return summary


def _emit_cli_summary(summary: dict) -> None:
    """Write the human-facing CLI summary to stdout.

    The CLI contract is a plain JSON payload on stdout, so this uses
    ``sys.stdout.write`` instead of logging to avoid log prefixes that would
    break downstream parsing.
    """
    sys.stdout.write(f"{json.dumps(summary, indent=2)}\n")


def main(argv: list[str] | None = None) -> int:
    """Run CLI optimization.

    Args:
        argv: Argument list (uses sys.argv if None).

    Returns:
        0 on successful optimization, 1 on failure.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # DbC: validate numeric CLI arguments
    if args.body_mass <= 0:
        parser.error(f"--body-mass must be positive, got {args.body_mass}")
    if args.height <= 0:
        parser.error(f"--height must be positive, got {args.height}")
    if args.bar_mass < 0:
        parser.error(f"--bar-mass must be non-negative, got {args.bar_mass}")
    if args.duration <= 0:
        parser.error(f"--duration must be positive, got {args.duration}")

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
        dyn,  # type: ignore[arg-type]
        exercise,
        bar_mass,
        qs,  # type: ignore[arg-type]
        qe,  # type: ignore[arg-type]
        qb,  # type: ignore[arg-type]
        q_via=q_via,  # type: ignore[arg-type]
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
        Path(args.output).write_text(json.dumps(full_data, indent=2), encoding="utf-8")
        logger.info("Results saved to %s", args.output)
    else:
        _emit_cli_summary(_result_to_summary(result, exercise))

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
