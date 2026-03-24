#!/usr/bin/env python3
"""setup_dev.py — One-command developer environment bootstrapper."""

import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 10)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENDOR_UD_TOOLS = PROJECT_ROOT / "vendor" / "ud-tools"

def main() -> None:
    if sys.version_info < MIN_PYTHON:
        sys.exit(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required.")

    print("[INFO] Initialising git submodules...")
    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=PROJECT_ROOT, check=True)

    print("[INFO] Installing movement-optimizer[dev] in editable mode...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"], cwd=PROJECT_ROOT, check=True)

    if not VENDOR_UD_TOOLS.is_dir():
        sys.exit(f"vendor/ud-tools not found at {VENDOR_UD_TOOLS}.")

    print("[INFO] Installing vendor/ud-tools in editable mode...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(VENDOR_UD_TOOLS)], cwd=PROJECT_ROOT, check=True)

    print("[ OK ] Development environment ready!")

if __name__ == "__main__":
    main()
