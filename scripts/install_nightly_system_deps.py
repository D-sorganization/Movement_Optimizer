#!/usr/bin/env python3
"""Install nightly workflow system dependencies with lock-aware retries."""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable, Sequence
from shutil import which

LOCK_ERROR_TOKENS = (
    "Could not get lock /var/lib/dpkg/lock-frontend",
    "Unable to acquire the dpkg frontend lock",
)
DEFAULT_MAX_ATTEMPTS = 20
DEFAULT_RETRY_DELAY_SECONDS = 15.0

logger = logging.getLogger(__name__)


def run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        capture_output=True,
        check=False,
        text=True,
    )


def has_passwordless_sudo(
    run: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] = run_command,
) -> bool:
    if which("sudo") is None:
        return False
    return run(["sudo", "-n", "true"]).returncode == 0


def is_dpkg_lock_error(result: subprocess.CompletedProcess[str]) -> bool:
    combined_output = f"{result.stdout}\n{result.stderr}"
    return any(token in combined_output for token in LOCK_ERROR_TOKENS)


def run_with_lock_retries(
    command: Sequence[str],
    *,
    attempts: int = DEFAULT_MAX_ATTEMPTS,
    delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    run: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] = run_command,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    for attempt in range(1, attempts + 1):
        result = run(command)
        if result.returncode == 0:
            return

        if attempt < attempts and is_dpkg_lock_error(result):
            logger.warning(
                "dpkg lock held while running %s; retrying in %.0f seconds (%s/%s)",
                " ".join(command),
                delay_seconds,
                attempt,
                attempts,
            )
            sleep(delay_seconds)
            continue

        raise subprocess.CalledProcessError(
            result.returncode,
            list(command),
            output=result.stdout,
            stderr=result.stderr,
        )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not has_passwordless_sudo():
        logger.info(
            "Skipping nightly system dependency install because passwordless sudo is unavailable."
        )
        return 0

    run_with_lock_retries(["sudo", "apt-get", "update"])
    run_with_lock_retries(["sudo", "apt-get", "install", "-y", "libegl1", "xvfb"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
