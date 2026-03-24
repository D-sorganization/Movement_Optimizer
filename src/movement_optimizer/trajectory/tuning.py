"""Tuning parameters and magical numbers for the optimiser."""

DEFAULT_JERK_WEIGHT: float = 0.05
DEFAULT_TORQUE_RATE_WEIGHT: float = 0.15
DEFAULT_ENDPOINT_WEIGHT: float = 10.0

# Balance constraint weights
BALANCE_BARRIER_WEIGHT: float = 8000.0
BALANCE_CENTER_WEIGHT: float = 12.0

# Stall detection
STALL_WINDOW: int = 80
STALL_THRESHOLD: float = 1e-4

# Multi-start
DEFAULT_N_STARTS: int = 6
MAX_ITER_PER_START: int = 500
PERTURBATION_SCALE: float = 0.08
