from __future__ import annotations

from scripts.check_type_ignore_suppressions import collect_suppressions


def test_type_ignore_suppressions_match_tracked_baseline() -> None:
    from scripts.check_type_ignore_suppressions import _load_baseline

    assert collect_suppressions() == _load_baseline()


def test_type_ignore_suppressions_use_explicit_error_codes() -> None:
    bare_suppressions = [item for item in collect_suppressions() if not item.codes]

    assert bare_suppressions == []
