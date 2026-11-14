# coding: utf-8
"""Unified target discovery and dispatch for Antigravity Desktop and Antigravity IDE."""

from pathlib import Path
from typing import Any, List, Optional, Tuple

from .ide_patcher import (
    inspect_ide_install_status,
    install_ide_patch,
    restore_ide_patch,
)
from .patcher import (
    inspect_install_status,
    install_patch,
    restore_patch,
)
from .paths import (
    detect_antigravity_targets,
    get_user_i18n_dir,
    is_desktop_app_dir,
    is_ide_app_dir,
)

TARGET_CHOICES = ("auto", "desktop", "ide", "all")


def resolve_targets(
    target: str = "auto",
    app_dir: Optional[Path] = None,
) -> List[Tuple[str, Path]]:
    """Resolve requested target mode ('auto', 'desktop', 'ide', 'all') to concrete directories."""
    norm = (target or "auto").lower()
    if norm not in TARGET_CHOICES:
        raise ValueError(f"Unknown target {target!r}. Expected one of: {', '.join(TARGET_CHOICES)}")

    if app_dir is not None:
        resolved = Path(app_dir)
        if norm == "desktop":
            return [("desktop", resolved)]
        if norm == "ide":
            return [("ide", resolved)]
        if is_ide_app_dir(resolved):
            return [("ide", resolved)]
        if is_desktop_app_dir(resolved):
            return [("desktop", resolved)]
        raise FileNotFoundError(
            f"Directory does not look like Antigravity Desktop or Antigravity IDE: {resolved}"
        )

    detected = detect_antigravity_targets()
    if norm == "desktop":
        if "desktop" not in detected:
            raise FileNotFoundError("Could not locate Antigravity Desktop installation directory.")
        return [("desktop", detected["desktop"])]
    if norm == "ide":
        if "ide" not in detected:
            raise FileNotFoundError("Could not locate Antigravity IDE installation directory.")
        return [("ide", detected["ide"])]

    if not detected:
        raise FileNotFoundError(
            "Could not locate any Antigravity Desktop or Antigravity IDE installation directory."
        )
    return [(kind, detected[kind]) for kind in ("desktop", "ide") if kind in detected]


def install_targets(
    target: str = "auto",
    app_dir: Optional[Path] = None,
    locale: Optional[str] = None,
    user_i18n_dir: Optional[Path] = None,
) -> List[Tuple[str, Any]]:
    """Install i18n runtime into one or both resolved targets."""
    results: List[Tuple[str, Any]] = []
    for kind, target_dir in resolve_targets(target=target, app_dir=app_dir):
        if kind == "ide":
            res = install_ide_patch(app_dir=target_dir, locale=locale, user_i18n_dir=user_i18n_dir)
        else:
            res = install_patch(app_dir=target_dir, locale=locale, user_i18n_dir=user_i18n_dir)
        results.append((kind, res))
    return results


def restore_targets(
    target: str = "auto",
    app_dir: Optional[Path] = None,
    hard: bool = False,
) -> List[Tuple[str, Path]]:
    """Restore one or both resolved targets cleanly."""
    restored: List[Tuple[str, Path]] = []
    for kind, target_dir in resolve_targets(target=target, app_dir=app_dir):
        if kind == "ide":
            out_path = restore_ide_patch(app_dir=target_dir, hard=hard)
        else:
            out_path = restore_patch(app_dir=target_dir, hard=hard)
        restored.append((kind, out_path))
    return restored


def inspect_all_targets(
    desktop_dir: Optional[Path] = None,
    ide_dir: Optional[Path] = None,
    user_i18n_dir: Optional[Path] = None,
) -> dict:
    """Return combined status dictionary covering both Antigravity Desktop and Antigravity IDE."""
    user_dir = user_i18n_dir or get_user_i18n_dir()
    desktop_status = inspect_install_status(app_dir=desktop_dir, user_i18n_dir=user_dir)
    ide_status = inspect_ide_install_status(app_dir=ide_dir, user_i18n_dir=user_dir)
    return {
        "desktop": desktop_status,
        "ide": ide_status,
        "configuredLocale": desktop_status.get("configuredLocale") or ide_status.get("configuredLocale", "auto"),
        "locales": desktop_status.get("locales") or ide_status.get("locales", []),
        "userI18nDir": str(user_dir),
    }
