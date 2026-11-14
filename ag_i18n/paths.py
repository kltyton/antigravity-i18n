# coding: utf-8
"""Cross-platform path discovery for Antigravity Desktop and user i18n data."""

import os
import sys
from pathlib import Path
from typing import List, Optional


REPO_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
RUNTIME_DIR = REPO_ROOT / "runtime"
LOCALES_DIR = REPO_ROOT / "locales"


def detect_antigravity_app_dir(custom_dir: Optional[str] = None) -> Path:
    """Resolve the Antigravity desktop application root directory."""
    if custom_dir:
        candidate = Path(custom_dir).expanduser().resolve()
        if (candidate / "resources").is_dir():
            return candidate
        if candidate.name == "resources" and candidate.is_dir():
            return candidate.parent
        raise FileNotFoundError(f"Antigravity resources directory not found under: {candidate}")

    candidates: List[Path] = []
    if sys.platform == "win32":
        local_app = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        prog_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        candidates.extend([
            local_app / "Programs" / "antigravity",
            prog_files / "antigravity",
            prog_files / "Google Antigravity",
        ])
    elif sys.platform == "darwin":
        candidates.extend([
            Path("/Applications/Antigravity.app"),
            Path.home() / "Applications" / "Antigravity.app",
        ])
    else:
        candidates.extend([
            Path("/opt/antigravity"),
            Path("/usr/lib/antigravity"),
            Path("/usr/share/antigravity"),
            Path.home() / ".local" / "share" / "antigravity",
        ])

    for cand in candidates:
        if get_resources_dir(cand).is_dir():
            return cand

    # Return platform default even if missing so callers get a clear expected path.
    return candidates[0]


def get_resources_dir(app_dir: Optional[Path] = None) -> Path:
    """Return the Electron resources directory inside the Antigravity app bundle."""
    base = app_dir or detect_antigravity_app_dir()
    if sys.platform == "darwin":
        if base.name == "Resources":
            return base
        return base / "Contents" / "Resources"
    return base / "resources"


def get_user_i18n_dir() -> Path:
    """Return the external persistent user directory where locale JSONs and config.json live."""
    if sys.platform == "win32":
        app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        return app_data / "antigravity" / "i18n"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "antigravity" / "i18n"
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg / "antigravity" / "i18n"


def get_browser_cache_dir() -> Path:
    """Return the Chromium Cache_Data directory used by Antigravity Desktop."""
    if sys.platform == "win32":
        app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        return app_data / "antigravity" / "Cache" / "Cache_Data"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "antigravity" / "Cache" / "Cache_Data"
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg / "antigravity" / "Cache" / "Cache_Data"
