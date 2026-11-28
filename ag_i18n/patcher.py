# coding: utf-8
"""ASAR patching, legacy-migration, locale deployment, and restoration for Antigravity Desktop."""

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .asar import extract_asar, pack_asar, read_asar_header, replace_file_safe
from .paths import (
    LOCALES_DIR,
    RUNTIME_DIR,
    detect_antigravity_app_dir,
    get_all_user_i18n_dirs,
    get_resources_dir,
    get_user_i18n_dir,
)

MAIN_START = "// --- antigravity-i18n main Start ---"
MAIN_END = "// --- antigravity-i18n main End ---"
PRELOAD_START = "// --- antigravity-i18n preload Start ---"
PRELOAD_END = "// --- antigravity-i18n preload End ---"

LEGACY_MARKER_BLOCKS: List[Tuple[str, str]] = [
    ("// Antigravity Chinese Localization Engine - Menu", "// Antigravity Chinese Localization Engine - Menu END"),
    ("// Antigravity Chinese Localization Engine", "// Antigravity Chinese Localization Engine END"),
    ("// --- Antigravity Chinese Localization Injection Start ---", "// --- Antigravity Chinese Localization Injection End ---"),
    (MAIN_START, MAIN_END),
    (PRELOAD_START, PRELOAD_END),
]

# Reverses hardcoded literal Chinese strings written by older legacy patchers
# so external locale packs handle all languages uniformly.
LEGACY_LITERAL_ROLLBACKS: Dict[str, List[Tuple[str, str]]] = {
    "dist/tray.js": [
        ("'显示 Antigravity'", "'Show Antigravity'"),
        ("'退出'", "'Quit'"),
        (
            "(count > 0 ? `${count} 个智能体正在运行` : '暂无运行中的智能体')",
            "(count > 0 ? `${count}` : 'No') + ' agent' + (count === 1 ? '' : 's') + ' running'",
        ),
    ],
    "dist/loadingOverlay.js": [
        (">正在加载 Antigravity<", ">Loading Antigravity<"),
    ],
    "dist/provisionSplash.js": [
        ("<div>正在配置 WSL: ${escapeHtml(distro)}</div>", "<div>Setting up WSL: ${escapeHtml(distro)}</div>"),
    ],
    "dist/main.js": [
        ("title: '未找到 WSL 分发版'", "title: 'WSL distro not found'"),
        (
            "message: `未找到 WSL 分发版 \"${WSL_DISTRO}\"，或该分发版已被卸载。`",
            "message: `The WSL distro \"${WSL_DISTRO}\" is no longer installed.`",
        ),
        ("detail: 'Antigravity 已改为在 Windows 上打开。'", "detail: 'Antigravity opened on Windows instead.'"),
        ("label: '新建窗口'", "label: 'New Window'"),
        ("label: '暂无运行中的智能体'", "label: 'No agents running'"),
        ("label: `打开 ${electron_1.app.getName()}`", "label: `Open ${electron_1.app.getName()}`"),
        ("label: '退出'", "label: 'Quit'"),
        ("buttons: ['取消', '退出']", "buttons: ['Cancel', 'Quit']"),
        ("title: '确认退出'", "title: 'Confirm Quit'"),
        ("message: '确定要退出吗？'", "message: 'Are you sure you want to quit?'"),
        (
            "detail: '当前可能有智能体或后台任务正在运行。'",
            "detail: 'There may be agents or background tasks running.'",
        ),
    ],
    "dist/updater.js": [
        ('MenuUpdateStep["CheckForUpdates"] = "检查更新";', 'MenuUpdateStep["CheckForUpdates"] = "Check for Updates";'),
        (
            'MenuUpdateStep["CheckingForUpdates"] = "正在检查更新...";',
            'MenuUpdateStep["CheckingForUpdates"] = "Checking for Updates...";',
        ),
        (
            'MenuUpdateStep["DownloadingUpdate"] = "正在下载更新...";',
            'MenuUpdateStep["DownloadingUpdate"] = "Downloading Update...";',
        ),
        ('MenuUpdateStep["RestartToUpdate"] = "重启以更新";', 'MenuUpdateStep["RestartToUpdate"] = "Restart to Update";'),
        ("title: '检查更新'", "title: 'Check for Updates'"),
        ("message: '当前已是最新版本'", "message: 'No updates available'"),
        ("buttons: ['确定']", "buttons: ['OK']"),
    ],
    "dist/deviceChooser.js": [
        ("'未知设备'", "'Unknown device'"),
        ("title: '连接设备'", "title: 'Connect a device'"),
        (
            "buttons: [...snapshot.map(({ label }) => label), '取消']",
            "buttons: [...snapshot.map(({ label }) => label), 'Cancel']",
        ),
    ],
    "dist/webviewPopupSecurity.js": [
        ("label: '连接信息…'", "label: 'Connection info…'"),
        ("title: '连接信息'", "title: 'Connection info'"),
        ("buttons: ['确定']", "buttons: ['OK']"),
    ],
    "dist/webauthn.js": [
        ("title: '选择通行密钥'", "title: 'Choose a Passkey'"),
        ("message: `登录到 ${rpLabel}`", "message: `Sign in to ${rpLabel}`"),
        ("detail: '请选择一个通行密钥账号以继续：'", "detail: 'Select a passkey account to continue:'"),
        ("buttons: [...accountLabels, '取消']", "buttons: [...accountLabels, 'Cancel']"),
    ],
    "dist/ipcHandlers.js": [
        ("message: '文件夹位于 Windows 文件系统中'", "message: 'Folder is on the Windows filesystem'"),
        ("title: '打开工作区'", "title: 'Open workspace'"),
        ("title: '打开工作区'", "title: 'Open workspaces'"),
        ("title: '选择下载文件夹'", "title: 'Select Download Folder'"),
    ],
    "dist/remote/disconnectedPage.js": [
        (
            "const title = connecting ? '正在重新连接…' : '连接已断开';",
            "const title = connecting ? 'Reconnecting…' : 'Disconnected';",
        ),
        (
            "? `正在重新连接到 ${host}…`\n        : `已断开与 ${host} 的连接`;",
            "? `Reconnecting to ${host}…`\n        : `Disconnected from ${host}`;",
        ),
        (
            "? `智能体仍在 ${host} 上继续运行。`\n        : `除非服务器已停止，否则智能体仍会在 ${host} 上继续运行。`;",
            "? `Agents keep running on ${host}.`\n        : `Agents keep running on ${host} unless its server stopped.`;",
        ),
        (">重新连接</a>", ">Reconnect</a>"),
    ],
    "dist/remote/remoteManager.js": [
        ("title: '选择 SSH 配置文件'", "title: 'Choose an SSH config file'"),
        ("title: 'SSH 连接失败'", "title: 'SSH connection failed'"),
        ("buttons: ['停止服务器', '取消']", "buttons: ['Stop Server', 'Cancel']"),
        ("title: '停止 SSH 服务器'", "title: 'Stop SSH server'"),
        (
            "message: `确定要停止 ${entry.label} 上的 Antigravity 服务器吗？`",
            "message: `Stop the Antigravity server on ${entry.label}?`",
        ),
        ("message: `尚未连接到 ${label}`", "message: `Not connected to ${label}`"),
        ("detail: '请先重新连接，然后再停止其服务器。'", "detail: 'Reconnect first, then stop its server.'"),
        ("buttons: ['登录', '取消']", "buttons: ['Sign In', 'Cancel']"),
        ("title: '登录'", "title: 'Sign in'"),
        (
            "message: `是否登录到 ${entry.label} 所在的组织？`",
            "message: `Sign in to your organization for ${entry.label}?`",
        ),
    ],
    "dist/remote/sshPrompts.js": [
        (
            "message: confirm ? `${label} 请求确认：` : '请轻触您的安全密钥'",
            "message: confirm ? `${label} asks:` : 'Touch your security key'",
        ),
        ("buttons: confirm ? ['是', '否'] : ['取消']", "buttons: confirm ? ['Yes', 'No'] : ['Cancel']"),
    ],
}

VIEW_MENU_ORIG = "item.label === 'View'"
VIEW_MENU_PATCHED = "(item.label === 'View' || item._agI18nOrigLabel === 'View')"
SUBMENU_ORIG = "item.label === submenuLabel"
SUBMENU_PATCHED = "(item.label === submenuLabel || item._agI18nOrigLabel === submenuLabel)"


@dataclass
class PatchResult:
    """Structured summary of an install or restore operation."""

    asar_path: Path
    user_i18n_dir: Path
    active_locale: str
    deployed_locales: List[str] = field(default_factory=list)
    backup_path: Optional[Path] = None
    legacy_reverted_files: List[str] = field(default_factory=list)
    patched_files: List[str] = field(default_factory=list)


def strip_marker_blocks(text: str) -> str:
    """Remove paired localization marker blocks while preserving all other code/mods."""
    out = text
    for start_m, end_m in LEGACY_MARKER_BLOCKS:
        pattern = re.compile(
            r"\n?" + re.escape(start_m) + r"[\s\S]*?" + re.escape(end_m) + r"\n?",
            re.MULTILINE,
        )
        out = pattern.sub("\n", out)
    # Collapse excessive blank lines around stripped regions cleanly
    return re.sub(r"\n{3,}", "\n\n", out)


def revert_legacy_literals(extracted_root: Path) -> List[str]:
    """Revert old hardcoded literal Chinese strings back to English source strings."""
    touched: List[str] = []
    for rel_path, pairs in LEGACY_LITERAL_ROLLBACKS.items():
        fp = extracted_root / rel_path
        if not fp.is_file():
            continue
        content = fp.read_text(encoding="utf-8", errors="replace")
        updated = content
        for legacy_zh, orig_en in pairs:
            if legacy_zh in updated:
                # Special handling for ambiguous 'Open workspace' vs 'Open workspaces' in ipcHandlers
                if rel_path == "dist/ipcHandlers.js" and legacy_zh == "title: '打开工作区'":
                    continue
                updated = updated.replace(legacy_zh, orig_en)

        if rel_path == "dist/ipcHandlers.js" and "title: '打开工作区'" in updated:
            # First occurrence in Antigravity ipcHandlers is single workspace, second is multiple workspaces
            updated = updated.replace("title: '打开工作区'", "title: 'Open workspace'", 1)
            updated = updated.replace("title: '打开工作区'", "title: 'Open workspaces'", 1)

        if updated != content:
            fp.write_text(updated, encoding="utf-8")
            touched.append(rel_path)
    return touched


def clean_existing_i18n(extracted_root: Path) -> List[str]:
    """Remove all previous antigravity-i18n and legacy Chinese patches cleanly."""
    for rel in ("dist/main.js", "dist/preload.js", "dist/menu.js"):
        fp = extracted_root / rel
        if fp.is_file():
            orig = fp.read_text(encoding="utf-8", errors="replace")
            cleaned = strip_marker_blocks(orig)
            if rel == "dist/menu.js":
                cleaned = cleaned.replace(VIEW_MENU_PATCHED, VIEW_MENU_ORIG)
                cleaned = cleaned.replace(SUBMENU_PATCHED, SUBMENU_ORIG)
            if cleaned != orig:
                fp.write_text(cleaned, encoding="utf-8")

    ag_runtime_dir = extracted_root / "dist" / "ag-i18n"
    if ag_runtime_dir.exists():
        shutil.rmtree(ag_runtime_dir, ignore_errors=True)

    return revert_legacy_literals(extracted_root)


def _atomic_write_json(target: Path, data: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def _deploy_single_i18n_dir(
    src_dir: Path,
    dest_base: Path,
    selected_locale: Optional[str] = None,
) -> Tuple[List[str], str]:
    dest_locales = dest_base / "locales"
    dest_locales.mkdir(parents=True, exist_ok=True)

    deployed: List[str] = []
    if src_dir.is_dir():
        for src_file in sorted(src_dir.glob("*.json")):
            shutil.copy2(src_file, dest_locales / src_file.name)
            if not src_file.name.startswith("_"):
                deployed.append(src_file.stem)

    config_path = dest_base / "config.json"
    config_data: dict = {"locale": "auto"}
    if config_path.is_file():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config_data.update(loaded)
        except Exception:
            pass

    if selected_locale is not None:
        config_data["locale"] = selected_locale

    _atomic_write_json(config_path, config_data)
    return deployed, str(config_data.get("locale", "auto"))


def deploy_locales(
    locales_src: Optional[Path] = None,
    user_i18n_dir: Optional[Path] = None,
    selected_locale: Optional[str] = None,
) -> Tuple[List[str], str]:
    """Copy locale JSON packs to all detected user i18n directories and ensure config.json exists."""
    src_dir = locales_src or LOCALES_DIR
    targets = [user_i18n_dir] if user_i18n_dir is not None else get_all_user_i18n_dirs()
    deployed: List[str] = []
    active_locale = "auto"
    for idx, dest_base in enumerate(targets):
        cur_deployed, cur_locale = _deploy_single_i18n_dir(src_dir, dest_base, selected_locale)
        if idx == 0:
            deployed, active_locale = cur_deployed, cur_locale
    return deployed, active_locale


def build_preload_bundle(runtime_dir: Path, prelude_js: str = "") -> str:
    """Wrap pure-JS core + settings UI + preload DOM observer in one sandbox-safe marker block."""
    core_js = (runtime_dir / "core.js").read_text(encoding="utf-8")
    settings_js_path = runtime_dir / "settings-ui.js"
    settings_js = settings_js_path.read_text(encoding="utf-8") if settings_js_path.is_file() else ""
    preload_js = (runtime_dir / "preload-i18n.js").read_text(encoding="utf-8")
    prelude_section = f"{prelude_js.rstrip()}\n" if prelude_js.strip() else ""
    return (
        f"\n{PRELOAD_START}\n"
        f";(function() {{\n"
        f"{prelude_section}"
        f"{core_js}\n"
        f"{settings_js}\n"
        f"{preload_js}\n"
        f"}})();\n"
        f"{PRELOAD_END}\n"
    )


_build_preload_bundle = build_preload_bundle


def _patch_main_js(main_js_path: Path) -> bool:
    content = main_js_path.read_text(encoding="utf-8", errors="replace")
    loader_block = (
        f"{MAIN_START}\n"
        f"try {{ require('./ag-i18n/electron-i18n'); }} catch (_agI18nErr) {{}}\n"
        f"{MAIN_END}\n"
    )
    if '"use strict";' in content:
        updated = content.replace('"use strict";', f'"use strict";\n{loader_block}', 1)
    elif "'use strict';" in content:
        updated = content.replace("'use strict';", f"'use strict';\n{loader_block}", 1)
    else:
        updated = loader_block + content
    main_js_path.write_text(updated, encoding="utf-8")
    return True


def _patch_menu_js(menu_js_path: Path) -> bool:
    content = menu_js_path.read_text(encoding="utf-8", errors="replace")
    updated = content
    if VIEW_MENU_PATCHED not in updated:
        updated = updated.replace(VIEW_MENU_ORIG, VIEW_MENU_PATCHED)
    if SUBMENU_PATCHED not in updated:
        updated = updated.replace(SUBMENU_ORIG, SUBMENU_PATCHED)
    if updated != content:
        menu_js_path.write_text(updated, encoding="utf-8")
        return True
    return False


def install_patch(
    app_dir: Optional[Path] = None,
    locale: Optional[str] = None,
    locales_src: Optional[Path] = None,
    runtime_src: Optional[Path] = None,
    user_i18n_dir: Optional[Path] = None,
) -> PatchResult:
    """Install the antigravity-i18n runtime into app.asar and deploy external locale packs."""
    resolved_app = Path(app_dir) if app_dir else detect_antigravity_app_dir()
    resources_dir = get_resources_dir(resolved_app)
    asar_path = resources_dir / "app.asar"
    if not asar_path.is_file():
        raise FileNotFoundError(f"Could not locate Antigravity app.asar at: {asar_path}")

    rt_dir = runtime_src or RUNTIME_DIR
    user_dir = user_i18n_dir or get_user_i18n_dir()

    deployed_locales, active_locale = deploy_locales(
        locales_src=locales_src or LOCALES_DIR,
        user_i18n_dir=user_i18n_dir,
        selected_locale=locale,
    )

    backup_path = resources_dir / "app.asar.ag-i18n.bak"
    created_backup: Optional[Path] = None

    with tempfile.TemporaryDirectory(prefix="ag_i18n_build_") as tmp_str:
        work_dir = Path(tmp_str)
        unpacked_info = extract_asar(asar_path, work_dir)

        main_text = (work_dir / "dist" / "main.js").read_text(encoding="utf-8", errors="replace")
        preload_text = (work_dir / "dist" / "preload.js").read_text(encoding="utf-8", errors="replace")
        has_any_i18n = (
            MAIN_START in main_text
            or PRELOAD_START in preload_text
            or "Antigravity Chinese Localization" in preload_text
        )
        if not backup_path.exists() and not has_any_i18n:
            shutil.copy2(asar_path, backup_path)
            created_backup = backup_path

        reverted = clean_existing_i18n(work_dir)

        # Copy main-process runtime modules into dist/ag-i18n/
        dest_runtime = work_dir / "dist" / "ag-i18n"
        dest_runtime.mkdir(parents=True, exist_ok=True)
        for mod_name in ("core.js", "menu-i18n.js", "electron-i18n.js"):
            shutil.copy2(rt_dir / mod_name, dest_runtime / mod_name)

        patched_files: List[str] = ["dist/ag-i18n/*"]

        _patch_main_js(work_dir / "dist" / "main.js")
        patched_files.append("dist/main.js")

        if _patch_menu_js(work_dir / "dist" / "menu.js"):
            patched_files.append("dist/menu.js")

        preload_path = work_dir / "dist" / "preload.js"
        preload_orig = preload_path.read_text(encoding="utf-8", errors="replace")
        preload_bundle = _build_preload_bundle(rt_dir)
        preload_path.write_text(preload_orig.rstrip() + "\n" + preload_bundle, encoding="utf-8")
        patched_files.append("dist/preload.js")

        pack_asar(work_dir, asar_path, unpacked_info)

    return PatchResult(
        asar_path=asar_path,
        user_i18n_dir=user_dir,
        active_locale=active_locale,
        deployed_locales=deployed_locales,
        backup_path=created_backup or (backup_path if backup_path.exists() else None),
        legacy_reverted_files=reverted,
        patched_files=patched_files,
    )


def restore_patch(
    app_dir: Optional[Path] = None,
    hard: bool = False,
) -> Path:
    """Remove antigravity-i18n from app.asar while preserving third-party mods by default."""
    resolved_app = Path(app_dir) if app_dir else detect_antigravity_app_dir()
    resources_dir = get_resources_dir(resolved_app)
    asar_path = resources_dir / "app.asar"
    if not asar_path.is_file():
        raise FileNotFoundError(f"Could not locate Antigravity app.asar at: {asar_path}")

    if hard:
        for candidate in (resources_dir / "app.asar.ag-i18n.bak", resources_dir / "app.asar.disabled"):
            if candidate.is_file():
                tmp_target = asar_path.with_name(f".{asar_path.name}.{os.getpid()}.restore")
                shutil.copy2(candidate, tmp_target)
                replace_file_safe(tmp_target, asar_path)
                return asar_path
        raise FileNotFoundError(f"No original ASAR backup found under: {resources_dir}")

    with tempfile.TemporaryDirectory(prefix="ag_i18n_restore_") as tmp_str:
        work_dir = Path(tmp_str)
        unpacked_info = extract_asar(asar_path, work_dir)
        clean_existing_i18n(work_dir)
        pack_asar(work_dir, asar_path, unpacked_info)
    return asar_path


def set_configured_locale(locale: str, user_i18n_dir: Optional[Path] = None) -> Path:
    """Update external user config.json across detected i18n dirs to the requested locale."""
    targets = [user_i18n_dir] if user_i18n_dir is not None else get_all_user_i18n_dirs()
    base_dir = targets[0]
    locales_dir = base_dir / "locales"
    if locale != "auto":
        if not (locales_dir / f"{locale}.json").is_file():
            # Also check repo bundled locales before rejecting
            if not (LOCALES_DIR / f"{locale}.json").is_file():
                available = sorted(
                    p.stem for p in (locales_dir if locales_dir.is_dir() else LOCALES_DIR).glob("*.json")
                    if not p.name.startswith("_")
                )
                raise ValueError(f"Unknown locale {locale!r}. Available: auto, {', '.join(available)}")

    primary_config_path = base_dir / "config.json"
    for idx, target_dir in enumerate(targets):
        config_path = target_dir / "config.json"
        config_data: dict = {}
        if config_path.is_file():
            try:
                loaded = json.loads(config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    config_data = loaded
            except Exception:
                pass
        config_data["locale"] = locale
        _atomic_write_json(config_path, config_data)
        if idx == 0:
            primary_config_path = config_path
    return primary_config_path


def list_locales(user_i18n_dir: Optional[Path] = None) -> Tuple[str, List[dict]]:
    """Return active config locale and available locale metadata dictionaries."""
    base_dir = user_i18n_dir or get_user_i18n_dir()
    config_path = base_dir / "config.json"
    configured = "auto"
    if config_path.is_file():
        try:
            configured = str(json.loads(config_path.read_text(encoding="utf-8")).get("locale", "auto"))
        except Exception:
            pass

    search_dir = base_dir / "locales"
    if not search_dir.is_dir() or not any(search_dir.glob("*.json")):
        search_dir = LOCALES_DIR

    items: List[dict] = []
    if search_dir.is_dir():
        for path in sorted(search_dir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                meta = data.get("meta", {})
                items.append({
                    "locale": meta.get("locale", path.stem),
                    "name": meta.get("name", path.stem),
                    "nativeName": meta.get("nativeName", path.stem),
                    "exactCount": len(data.get("exact", {})),
                    "patternCount": len(data.get("patterns", [])),
                })
            except Exception:
                continue
    return configured, items


def _asar_has_path(header_node: dict, parts: Tuple[str, ...]) -> bool:
    cur = header_node
    for part in parts:
        files = cur.get("files") if isinstance(cur, dict) else None
        if not isinstance(files, dict) or part not in files:
            return False
        cur = files[part]
    return True


def inspect_install_status(
    app_dir: Optional[Path] = None,
    user_i18n_dir: Optional[Path] = None,
) -> dict:
    """Fast header-only status inspection without extracting ASAR contents."""
    status: dict = {
        "appDirFound": False,
        "appDir": "",
        "asarPath": "",
        "installed": False,
        "hasSettingsUi": False,
        "hasContextMeter": False,
        "hasBackup": False,
        "configuredLocale": "auto",
        "userI18nDir": str(user_i18n_dir or get_user_i18n_dir()),
        "locales": [],
    }
    try:
        resolved_app = Path(app_dir) if app_dir else detect_antigravity_app_dir()
        resources_dir = get_resources_dir(resolved_app)
        asar_path = resources_dir / "app.asar"
        status["appDirFound"] = asar_path.is_file()
        status["appDir"] = str(resolved_app)
        status["asarPath"] = str(asar_path)
        status["hasBackup"] = (
            (resources_dir / "app.asar.ag-i18n.bak").is_file()
            or (resources_dir / "app.asar.disabled").is_file()
        )
        if asar_path.is_file():
            header, _ = read_asar_header(asar_path)
            status["installed"] = _asar_has_path(header, ("dist", "ag-i18n", "electron-i18n.js"))
            status["hasContextMeter"] = _asar_has_path(header, ("dist", "meter-main.js"))
    except Exception as exc:
        status["error"] = str(exc)

    configured, locales = list_locales(user_i18n_dir=user_i18n_dir)
    status["configuredLocale"] = configured
    status["locales"] = locales
    return status
