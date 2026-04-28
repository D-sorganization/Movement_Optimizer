"""Track checked-in ``# type: ignore[...]`` suppressions.

The baseline is intentionally explicit so new suppressions are reviewed as
typing debt, not hidden in a broad source scan.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "docs" / "typing" / "type_ignore_suppressions.json"
TRACKED_ROOTS = ("src", "tests")
TYPE_IGNORE_RE = re.compile(r"#\s*type:\s*ignore(?:\[(?P<codes>[^\]]+)\])?")


@dataclass(frozen=True, order=True)
class Suppression:
    path: str
    line: int
    codes: tuple[str, ...]
    text: str


def _tracked_python_files() -> list[Path]:
    files: list[Path] = []
    for root in TRACKED_ROOTS:
        files.extend((REPO_ROOT / root).rglob("*.py"))
    return sorted(files)


def collect_suppressions() -> list[Suppression]:
    suppressions: list[Suppression] = []
    for path in _tracked_python_files():
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = TYPE_IGNORE_RE.search(line)
            if not match:
                continue
            codes = tuple(
                code.strip() for code in (match.group("codes") or "").split(",") if code.strip()
            )
            suppressions.append(
                Suppression(
                    path=rel_path,
                    line=line_no,
                    codes=codes,
                    text=line.strip(),
                )
            )
    return sorted(suppressions)


def _to_json(suppressions: list[Suppression]) -> str:
    payload = {
        "tracked_roots": list(TRACKED_ROOTS),
        "description": (
            "Baseline for checked-in # type: ignore[...] suppressions. "
            "Run python scripts/check_type_ignore_suppressions.py --write "
            "after deliberately adding, removing, or relocating suppressions."
        ),
        "suppressions": [asdict(item) for item in suppressions],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _load_baseline() -> list[Suppression]:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return [
        Suppression(
            path=item["path"],
            line=int(item["line"]),
            codes=tuple(item["codes"]),
            text=item["text"],
        )
        for item in payload["suppressions"]
    ]


def _format_diff(expected: list[Suppression], actual: list[Suppression]) -> str:
    expected_set = set(expected)
    actual_set = set(actual)
    added = sorted(actual_set - expected_set)
    removed = sorted(expected_set - actual_set)
    lines: list[str] = []
    if added:
        lines.append("Untracked type-ignore suppressions:")
        lines.extend(f"  + {item.path}:{item.line} {item.codes} {item.text}" for item in added[:20])
    if removed:
        lines.append("Baseline entries no longer present:")
        lines.extend(
            f"  - {item.path}:{item.line} {item.codes} {item.text}" for item in removed[:20]
        )
    if len(added) > 20 or len(removed) > 20:
        lines.append("  ...")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="refresh the committed baseline")
    args = parser.parse_args()

    actual = collect_suppressions()
    if args.write:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(_to_json(actual), encoding="utf-8")
        print(f"Wrote {len(actual)} suppressions to {BASELINE_PATH.relative_to(REPO_ROOT)}")
        return 0

    expected = _load_baseline()
    if actual != expected:
        print(_format_diff(expected, actual))
        print("Refresh the baseline only after reviewing the type-ignore change.")
        return 1

    missing_codes = [item for item in actual if not item.codes]
    if missing_codes:
        print("Bare type-ignore suppressions require explicit error codes:")
        for item in missing_codes:
            print(f"  {item.path}:{item.line} {item.text}")
        return 1

    print(f"Tracked {len(actual)} type-ignore suppressions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
