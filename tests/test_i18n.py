# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Tests for i18n infrastructure (issue #410)."""

from __future__ import annotations

import os

import pytest

# Ensure Qt uses the offscreen platform so the test suite runs without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication

    _QT_AVAILABLE = True
    _app = QApplication.instance()
    if _app is None:
        _app = QApplication([])
except (ImportError, OSError):
    _QT_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _QT_AVAILABLE, reason="Qt not available")


def test_locale_directory_exists() -> None:
    """The locale directory must be present in the package."""
    import movement_optimizer

    pkg_dir = os.path.dirname(movement_optimizer.__file__)
    locale_dir = os.path.join(pkg_dir, "locale")
    assert os.path.isdir(locale_dir), f"locale directory not found at {locale_dir}"


def test_locale_gitkeep_exists() -> None:
    """The .gitkeep file must be present to track the empty locale directory."""
    import movement_optimizer

    pkg_dir = os.path.dirname(movement_optimizer.__file__)
    gitkeep = os.path.join(pkg_dir, "locale", ".gitkeep")
    assert os.path.isfile(gitkeep), f".gitkeep not found at {gitkeep}"


def test_german_ts_file_exists() -> None:
    """A minimal German translation file must be present as proof of concept."""
    import movement_optimizer

    pkg_dir = os.path.dirname(movement_optimizer.__file__)
    ts_file = os.path.join(pkg_dir, "locale", "movement_optimizer_de.ts")
    assert os.path.isfile(ts_file), f"German TS file not found at {ts_file}"


def test_tr_returns_string() -> None:
    """tr() must return a plain str."""
    from movement_optimizer.i18n import tr

    result = tr("Body Mass")
    assert isinstance(result, str)


def test_tr_english_fallback() -> None:
    """tr() must return a non-empty string (English fallback when no .qm loaded)."""
    from movement_optimizer.i18n import tr

    result = tr("Body Mass")
    assert result  # non-empty string


def test_setup_translations_does_not_raise() -> None:
    """setup_translations() must not raise for any locale, even without .qm files."""
    from movement_optimizer.i18n import setup_translations

    # Falls back gracefully when no compiled .qm file is present.
    setup_translations(locale="de")
    setup_translations(locale="en_US")
    setup_translations(locale=None)


def test_tr_unknown_key_returns_source() -> None:
    """tr() must return the source string unchanged for untranslated keys."""
    from movement_optimizer.i18n import tr

    key = "This string has no translation registered anywhere"
    assert tr(key) == key
