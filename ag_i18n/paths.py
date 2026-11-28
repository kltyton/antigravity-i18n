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


def get_all_user_i18n_dirs() -> List[Path]:
    """Return the primary user i18n dir plus any secondary multi-instance profile dirs (e.g. Cockpit Tools)."""
    dirs: List[Path] = [get_user_i18n_dir()]
    if sys.platform == "win32":
        app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        cockpit_root = app_data / ".cockpit_tools" / "instances" / "antigravity-legacy"
        if cockpit_root.is_dir():
            for profile in sorted(cockpit_root.iterdir()):
                if not profile.is_dir():
                    continue
                if (
                    (profile / "i18n").is_dir()
                    or (profile / "Preferences").is_file()
                    or (profile / "Local State").is_file()
                ):
                    dirs.append(profile / "i18n")

    deduped: List[Path] = []
    seen = set()
    for p in dirs:
        key = os.path.normcase(os.path.abspath(str(p)))
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


def get_browser_cache_dir() -> Path:
    """Return the Chromium Cache_Data directory used by Antigravity Desktop."""
    if sys.platform == "win32":
        app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        return app_data / "antigravity" / "Cache" / "Cache_Data"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "antigravity" / "Cache" / "Cache_Data"
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg / "antigravity" / "Cache" / "Cache_Data"


def get_ide_app_resources_dir(app_dir: Path) -> Path:
    """Return the unpacked resources/app directory for an Antigravity IDE install."""
    if app_dir.name == "app" and (app_dir / "product.json").is_file():
        return app_dir
    if app_dir.name == "resources" and (app_dir / "app" / "product.json").is_file():
        return app_dir / "app"
    if sys.platform == "darwin":
        if (app_dir / "Contents" / "Resources" / "app" / "product.json").is_file():
            return app_dir / "Contents" / "Resources" / "app"
        if app_dir.name == "Resources" and (app_dir / "app" / "product.json").is_file():
            return app_dir / "app"
    return app_dir / "resources" / "app"


def is_desktop_app_dir(app_dir: Path) -> bool:
    """Return True if *app_dir* points to an Antigravity Desktop installation (ASAR layout)."""
    return (get_resources_dir(app_dir) / "app.asar").is_file()


def is_ide_app_dir(app_dir: Path) -> bool:
    """Return True if *app_dir* points to an unpacked Antigravity IDE installation."""
    import json

    if (get_resources_dir(app_dir) / "app.asar").is_file():
        return False
    res_app = get_ide_app_resources_dir(app_dir)
    product_file = res_app / "product.json"
    if not product_file.is_file() or not (res_app / "out" / "main.js").is_file():
        return False
    try:
        data = json.loads(product_file.read_text(encoding="utf-8"))
    except Exception:
        return False
    app_name = str(data.get("applicationName", "")).lower()
    name_short = str(data.get("nameShort", "")).lower()
    return "antigravity-ide" in app_name or "antigravity ide" in name_short


def _iter_windows_ide_registry_candidates() -> list[Path]:
    """Query Windows Uninstall registry keys for Antigravity IDE install paths."""
    if sys.platform != "win32":
        return []
    import winreg

    out: list[Path] = []
    subkey_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            root_key = winreg.OpenKey(hive, subkey_path)
        except OSError:
            continue
        with root_key:
            idx = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(root_key, idx)
                    idx += 1
                except OSError:
                    break
                try:
                    with winreg.OpenKey(root_key, sub_name) as item:
                        display_name, _ = winreg.QueryValueEx(item, "DisplayName")
                        if "antigravity ide" not in str(display_name).lower():
                            continue
                        for val_name in ("InstallLocation", "DisplayIcon"):
                            try:
                                raw_val, _ = winreg.QueryValueEx(item, val_name)
                            except OSError:
                                continue
                            raw_str = str(raw_val).strip().strip('"').split(",")[0].strip()
                            if not raw_str:
                                continue
                            cand = Path(raw_str)
                            if cand.is_file():
                                cand = cand.parent
                            out.append(cand)
                except OSError:
                    continue
    return out


def detect_antigravity_ide_dir() -> Optional[Path]:
    """Auto-detect the unpacked Antigravity IDE installation directory, or None if not installed."""
    env = os.environ.get("ANTIGRAVITY_IDE_APP_DIR")
    if env:
        env_path = Path(env)
        if is_ide_app_dir(env_path):
            return env_path
        return env_path

    candidates: list[Path] = []
    if sys.platform == "win32":
        candidates.extend(_iter_windows_ide_registry_candidates())
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        prog = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        candidates.extend([
            local / "Programs" / "Antigravity IDE",
            prog / "Antigravity IDE",
        ])
    elif sys.platform == "darwin":
        candidates.extend([
            Path("/Applications/Antigravity IDE.app"),
            Path.home() / "Applications" / "Antigravity IDE.app",
        ])
    else:
        candidates.extend([
            Path("/usr/share/antigravity-ide"),
            Path("/opt/Antigravity IDE"),
            Path("/opt/antigravity-ide"),
            Path.home() / ".local" / "share" / "antigravity-ide",
        ])

    for cand in candidates:
        if is_ide_app_dir(cand):
            return cand
    return None


def detect_antigravity_targets() -> dict[str, Path]:
    """Return mapping of detected installations: {'desktop': Path, 'ide': Path}."""
    targets: dict[str, Path] = {}
    desktop = detect_antigravity_app_dir()
    if is_desktop_app_dir(desktop):
        targets["desktop"] = desktop
    ide = detect_antigravity_ide_dir()
    if ide is not None and is_ide_app_dir(ide):
        targets["ide"] = ide
    return targets


def is_process_running(target_kind: str) -> bool:
    """Best-effort check whether Antigravity Desktop or Antigravity IDE is currently running."""
    import subprocess

    if sys.platform == "win32":
        image = "Antigravity IDE.exe" if target_kind == "ide" else "Antigravity.exe"
        try:
            res = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return image.lower() in (res.stdout or "").lower()
        except Exception:
            return False
    pattern = "Antigravity IDE" if target_kind == "ide" else "Antigravity"
    try:
        res = subprocess.run(["pgrep", "-f", pattern], capture_output=True, timeout=5, check=False)
        return res.returncode == 0
    except Exception:
        return False
