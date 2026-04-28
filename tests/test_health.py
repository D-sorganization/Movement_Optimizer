"""Tests for movement_optimizer.health."""

import json

from movement_optimizer.health import health_check


def test_health_returns_ok() -> None:
    """Health check should report ok when deps are present."""
    result = health_check()
    assert result.status == "ok"
    assert result.version == "1.0.0"
    assert result.checks["numpy"] == "ok"
    assert result.checks["physics_backend"] == "ok"


def test_health_json_roundtrip() -> None:
    """JSON serialization should round-trip cleanly."""
    result = health_check()
    parsed = json.loads(result.to_json())
    assert parsed["status"] == "ok"
    assert "version" in parsed
    assert "timestamp" in parsed
    assert "checks" in parsed


def test_health_dict_contains_all_fields() -> None:
    """to_dict() should expose every field."""
    result = health_check()
    d = result.to_dict()
    assert set(d.keys()) >= {"status", "version", "python_version", "timestamp", "checks"}
