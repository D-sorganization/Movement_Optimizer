# Copyright (c) 2026 D-Sorganization. All rights reserved.
"""Internationalisation helpers for Movement Optimizer.

Usage::

    from movement_optimizer.i18n import setup_translations, tr

    # Call once at startup (before any widgets are created):
    setup_translations()          # auto-detect system locale
    setup_translations("de")      # force German
    setup_translations(None)      # auto-detect system locale (same as no-arg)

    # Wrap every user-visible string:
    label = tr("Body Mass")
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_translator = None  # holds the active QTranslator instance, if any

_LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locale")


def setup_translations(locale: str | None = None) -> None:
    """Install a QTranslator for *locale* into the running QApplication.

    When *locale* is ``None`` (the default), the system locale is used
    automatically (e.g. ``"de_DE"``).  Pass an explicit IETF tag such as
    ``"de"`` or ``"fr_FR"`` to force a specific language.

    If no QApplication exists yet, or no matching .qm file is found for the
    requested locale, the function returns silently and English strings are
    used as fallback.

    Any previously installed translator is removed before the new one is
    loaded, so calling this function a second time cleanly switches languages.

    Preconditions:
        locale is None or isinstance(locale, str)
    """
    global _translator

    try:
        from PyQt6.QtCore import QCoreApplication, QLocale, QTranslator
    except ImportError:
        logger.debug("PyQt6 not available; skipping translation setup")
        return

    app = QCoreApplication.instance()
    if app is None:
        logger.debug("No QApplication instance; skipping translation setup")
        return

    # Remove any previously installed translator.
    if _translator is not None:
        app.removeTranslator(_translator)
        _translator = None

    locale_str = QLocale.system().name() if locale is None else locale  # e.g. "de_DE"

    translator = QTranslator(app)
    # Try exact match first, then language-only prefix.
    candidates = [locale_str, locale_str.split("_")[0]]
    for candidate in candidates:
        qm_path = os.path.join(_LOCALE_DIR, f"movement_optimizer_{candidate}.qm")
        if translator.load(qm_path):
            app.installTranslator(translator)
            _translator = translator
            logger.debug("Loaded translation: %s", qm_path)
            return

    logger.debug(
        "No compiled .qm file found for locale %r in %s; using English fallback",
        locale_str,
        _LOCALE_DIR,
    )


def tr(source: str) -> str:
    """Return the translation of *source* in the active locale.

    Falls back to *source* unchanged when no translation is loaded or when
    *source* is not in the translation catalogue.

    Preconditions:
        isinstance(source, str)
    """
    if not isinstance(source, str):
        raise TypeError(f"tr() expects a str, got {type(source).__name__!r}")

    try:
        from PyQt6.QtCore import QCoreApplication

        translated = QCoreApplication.translate("movement_optimizer", source)
        # Qt returns the source string unchanged when no translation is found.
        return translated
    except ImportError:
        return source
