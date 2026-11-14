# coding: utf-8
"""Surgical runtime injection, extension NLS generation, and restoration for Antigravity IDE."""

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .patcher import (
    _atomic_write_json,
    build_preload_bundle,
    deploy_locales,
    list_locales,
    strip_marker_blocks,
)
from .paths import (
    LOCALES_DIR,
    RUNTIME_DIR,
    detect_antigravity_ide_dir,
    get_ide_app_resources_dir,
    get_user_i18n_dir,
    is_ide_app_dir,
)

IDE_MAIN_START = "/* ag-i18n-ide-main:start */"
IDE_MAIN_END = "/* ag-i18n-ide-main:end */"
IDE_MAIN_REL = "out/main.js"
IDE_PRELOAD_REL = "out/vs/base/parts/sandbox/electron-browser/preload.js"
IDE_RUNTIME_REL = "out/ag-i18n"
IDE_BACKUP_DIRNAME = ".ag-i18n-backup"

IDE_PRELOAD_PRELUDE_JS = r"""
globalThis.__AG_I18N_PRELOAD_CONFIG__ = function (win) {
  var href = '';
  try {
    href = String((win && win.location && win.location.href) || '');
  } catch (_e) {}
  if (/workbench-jetski-agent(?:-dev)?\.html/i.test(href)) {
    return {
      enabled: true,
      ipcPrefix: 'vscode:ag-i18n:',
      scopeSelectors: null,
      translateTitle: true,
      injectSettingsCard: true,
      exposeGlobal: false
    };
  }
  if (/workbench(?:-dev)?\.html/i.test(href)) {
    return {
      enabled: true,
      ipcPrefix: 'vscode:ag-i18n:',
      scopeSelectors: 'ide-antigravity',
      translateTitle: false,
      injectSettingsCard: false,
      exposeGlobal: false
    };
  }
  return { enabled: false };
};
""".strip()


@dataclass
class IdePatchResult:
    """Structured summary of an Antigravity IDE install operation."""

    app_dir: Path
    resources_app_dir: Path
    user_i18n_dir: Path
    active_locale: str
    deployed_locales: List[str] = field(default_factory=list)
    backup_dir: Optional[Path] = None
    patched_files: List[str] = field(default_factory=list)
    localized_extensions: List[str] = field(default_factory=list)


def _strip_ide_main_markers(text: str) -> str:
    pattern = re.compile(
        re.escape(IDE_MAIN_START) + r"[\s\S]*?" + re.escape(IDE_MAIN_END) + r"(?:\r?\n)?",
        re.MULTILINE,
    )
    return pattern.sub("", text)


def _inject_ide_main_loader(content: str) -> str:
    cleaned = _strip_ide_main_markers(content)
    block = f'{IDE_MAIN_START}\nimport "./ag-i18n/ide-bootstrap.mjs";\n{IDE_MAIN_END}\n'
    if cleaned.startswith("/*!"):
        end_idx = cleaned.find("*/")
        if end_idx != -1:
            insert_at = end_idx + 2
            if insert_at < len(cleaned) and cleaned[insert_at : insert_at + 2] == "\r\n":
                insert_at += 2
            elif insert_at < len(cleaned) and cleaned[insert_at : insert_at + 1] in ("\n", "\r"):
                insert_at += 1
            return cleaned[:insert_at] + block + cleaned[insert_at:]
    elif cleaned.startswith("#!"):
        nl = cleaned.find("\n")
        if nl != -1:
            return cleaned[: nl + 1] + block + cleaned[nl + 1 :]
    return block + cleaned


def _inject_ide_preload_bundle(content: str, bundle: str) -> str:
    cleaned = strip_marker_blocks(content)
    lines = cleaned.splitlines(keepends=True)
    sourcemap_tail = ""
    if lines and lines[-1].lstrip().startswith("//# sourceMappingURL="):
        sourcemap_tail = lines.pop()
    body = "".join(lines).rstrip()
    out = body + "\n" + bundle.lstrip("\n")
    if sourcemap_tail:
        if not out.endswith("\n"):
            out += "\n"
        out += sourcemap_tail
    return out


def _find_antigravity_extensions(resources_app: Path) -> List[Path]:
    ext_root = resources_app / "extensions"
    if not ext_root.is_dir():
        return []
    targets: List[Path] = []
    for child in sorted(ext_root.iterdir()):
        if not child.is_dir():
            continue
        if (child.name == "agy" or child.name.startswith("antigravity-")) and (child / "package.json").is_file():
            targets.append(child)
    return targets


def _load_all_locale_packs(locales_src: Path) -> Dict[str, dict]:
    packs: Dict[str, dict] = {}
    if not locales_src.is_dir():
        return packs
    for path in sorted(locales_src.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            packs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return packs


def _lookup_locale_text(pack: dict, english: str) -> str:
    exact = pack.get("exact")
    if isinstance(exact, dict) and isinstance(exact.get(english), str):
        return exact[english]
    menu = pack.get("menu")
    if isinstance(menu, dict) and isinstance(menu.get(english), str):
        return menu[english]
    return english


def _templatize_extension_manifest(manifest: dict, ext_slug: str) -> Tuple[dict, Dict[str, str]]:
    """Replace user-facing Antigravity strings in extension package.json with %key% placeholders."""
    nls_en: Dict[str, str] = {}
    counter = 0

    def register_text(value: Any) -> Any:
        nonlocal counter
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped or (stripped.startswith("%") and stripped.endswith("%")):
            return value
        counter += 1
        key = f"ag.i18n.{ext_slug}.{counter}"
        nls_en[key] = value
        return f"%{key}%"

    data = json.loads(json.dumps(manifest))

    for top_field in ("displayName", "description"):
        if top_field in data:
            data[top_field] = register_text(data[top_field])

    contributes = data.get("contributes")
    if isinstance(contributes, dict):
        if isinstance(contributes.get("customEditors"), list):
            for editor in contributes["customEditors"]:
                if isinstance(editor, dict) and "displayName" in editor:
                    editor["displayName"] = register_text(editor["displayName"])

        if isinstance(contributes.get("views"), dict):
            for view_list in contributes["views"].values():
                if isinstance(view_list, list):
                    for view in view_list:
                        if isinstance(view, dict) and "name" in view:
                            view["name"] = register_text(view["name"])

        if isinstance(contributes.get("viewsContainers"), dict):
            for slot_list in contributes["viewsContainers"].values():
                if isinstance(slot_list, list):
                    for container in slot_list:
                        if isinstance(container, dict) and "title" in container:
                            container["title"] = register_text(container["title"])

        if isinstance(contributes.get("commands"), list):
            for cmd in contributes["commands"]:
                if isinstance(cmd, dict):
                    if "title" in cmd:
                        cmd["title"] = register_text(cmd["title"])
                    if "category" in cmd:
                        cmd["category"] = register_text(cmd["category"])

        if isinstance(contributes.get("submenus"), list):
            for sub in contributes["submenus"]:
                if isinstance(sub, dict) and "label" in sub:
                    sub["label"] = register_text(sub["label"])

        cfg = contributes.get("configuration")
        cfg_list = cfg if isinstance(cfg, list) else ([cfg] if isinstance(cfg, dict) else [])
        for cfg_item in cfg_list:
            if not isinstance(cfg_item, dict):
                continue
            if "title" in cfg_item:
                cfg_item["title"] = register_text(cfg_item["title"])
            props = cfg_item.get("properties")
            if isinstance(props, dict):
                for prop_schema in props.values():
                    if not isinstance(prop_schema, dict):
                        continue
                    for field_name in (
                        "description",
                        "markdownDescription",
                        "deprecationMessage",
                        "markdownDeprecationMessage",
                    ):
                        if field_name in prop_schema:
                            prop_schema[field_name] = register_text(prop_schema[field_name])
                    for list_field in ("enumDescriptions", "markdownEnumDescriptions"):
                        if isinstance(prop_schema.get(list_field), list):
                            prop_schema[list_field] = [
                                register_text(item) for item in prop_schema[list_field]
                            ]

    return data, nls_en


def _backup_file_once(resources_app: Path, rel_path: str, backup_root: Path, manifest: dict) -> None:
    backed_files: List[str] = manifest.setdefault("backedUpFiles", [])
    if rel_path in backed_files:
        return
    src = resources_app / rel_path
    dst = backup_root / "files" / rel_path
    if src.is_file() and not dst.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        backed_files.append(rel_path)


def install_ide_patch(
    app_dir: Optional[Path] = None,
    locale: Optional[str] = None,
    locales_src: Optional[Path] = None,
    runtime_src: Optional[Path] = None,
    user_i18n_dir: Optional[Path] = None,
) -> IdePatchResult:
    """Install surgical Antigravity-only localization into Antigravity IDE."""
    resolved_app = Path(app_dir) if app_dir else detect_antigravity_ide_dir()
    if resolved_app is None or not is_ide_app_dir(resolved_app):
        raise FileNotFoundError(
            "Could not locate Antigravity IDE installation directory (unpacked resources/app)."
        )

    resources_app = get_ide_app_resources_dir(resolved_app)
    main_js_path = resources_app / IDE_MAIN_REL
    preload_js_path = resources_app / IDE_PRELOAD_REL
    if not main_js_path.is_file() or not preload_js_path.is_file():
        raise FileNotFoundError(f"Expected Antigravity IDE entrypoints under: {resources_app}")

    rt_dir = runtime_src or RUNTIME_DIR
    loc_dir = locales_src or LOCALES_DIR
    user_dir = user_i18n_dir or get_user_i18n_dir()

    deployed_locales, active_locale = deploy_locales(
        locales_src=loc_dir,
        user_i18n_dir=user_dir,
        selected_locale=locale,
    )

    backup_root = resources_app / IDE_BACKUP_DIRNAME
    manifest_path = backup_root / "manifest.json"
    manifest: dict = {"backedUpFiles": [], "createdFiles": []}
    if manifest_path.is_file():
        try:
            loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded_manifest, dict):
                manifest.update(loaded_manifest)
        except Exception:
            pass

    main_orig = main_js_path.read_text(encoding="utf-8", errors="replace")
    if IDE_MAIN_START not in main_orig:
        _backup_file_once(resources_app, IDE_MAIN_REL, backup_root, manifest)

    preload_orig = preload_js_path.read_text(encoding="utf-8", errors="replace")
    if "antigravity-i18n preload Start" not in preload_orig:
        _backup_file_once(resources_app, IDE_PRELOAD_REL, backup_root, manifest)

    # Deploy main-process runtime modules & bundled locales fallback into out/ag-i18n/
    dest_runtime = resources_app / IDE_RUNTIME_REL
    dest_runtime.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rt_dir / "core.js", dest_runtime / "core.js")
    shutil.copy2(rt_dir / "ide-main-i18n.cjs", dest_runtime / "electron-ide-i18n.cjs")
    shutil.copy2(rt_dir / "ide-bootstrap.mjs", dest_runtime / "ide-bootstrap.mjs")

    bundled_locales_dir = dest_runtime / "locales"
    bundled_locales_dir.mkdir(parents=True, exist_ok=True)
    if loc_dir.is_dir():
        for src_file in sorted(loc_dir.glob("*.json")):
            shutil.copy2(src_file, bundled_locales_dir / src_file.name)

    patched_files: List[str] = [f"{IDE_RUNTIME_REL}/*"]

    # Patch out/main.js
    main_js_path.write_text(_inject_ide_main_loader(main_orig), encoding="utf-8")
    patched_files.append(IDE_MAIN_REL)

    # Patch preload.js (scoped in workbench.html, full + settings card in workbench-jetski-agent.html)
    preload_bundle = build_preload_bundle(rt_dir, prelude_js=IDE_PRELOAD_PRELUDE_JS)
    preload_js_path.write_text(
        _inject_ide_preload_bundle(preload_orig, preload_bundle),
        encoding="utf-8",
    )
    patched_files.append(IDE_PRELOAD_REL)

    # Localize only Antigravity built-in extensions via native VS Code package.nls*.json
    packs = _load_all_locale_packs(loc_dir)
    created_files = set(manifest.get("createdFiles", []))
    localized_extensions: List[str] = []

    for ext_dir in _find_antigravity_extensions(resources_app):
        ext_rel = f"extensions/{ext_dir.name}/package.json"
        pkg_path = ext_dir / "package.json"

        # Always start from clean backed-up original package.json on reinstall
        backed_pkg = backup_root / "files" / ext_rel
        if backed_pkg.is_file():
            orig_pkg_text = backed_pkg.read_text(encoding="utf-8")
        else:
            orig_pkg_text = pkg_path.read_text(encoding="utf-8")
            if "%ag.i18n." not in orig_pkg_text:
                _backup_file_once(resources_app, ext_rel, backup_root, manifest)

        orig_pkg = json.loads(orig_pkg_text)
        slug = re.sub(r"[^a-zA-Z0-9]+", ".", ext_dir.name).strip(".")
        templated_pkg, nls_en = _templatize_extension_manifest(orig_pkg, slug)
        if not nls_en:
            continue

        pkg_path.write_text(
            json.dumps(templated_pkg, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        patched_files.append(ext_rel)

        en_nls_rel = f"extensions/{ext_dir.name}/package.nls.json"
        (ext_dir / "package.nls.json").write_text(
            json.dumps(nls_en, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        created_files.add(en_nls_rel)

        for loc_tag, pack in packs.items():
            if loc_tag == "en-US":
                continue
            translated_nls = {k: _lookup_locale_text(pack, v) for k, v in nls_en.items()}
            vscode_tag = loc_tag.lower()
            nls_rel = f"extensions/{ext_dir.name}/package.nls.{vscode_tag}.json"
            (ext_dir / f"package.nls.{vscode_tag}.json").write_text(
                json.dumps(translated_nls, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            created_files.add(nls_rel)

        localized_extensions.append(ext_dir.name)

    manifest["createdFiles"] = sorted(created_files)
    _atomic_write_json(manifest_path, manifest)

    return IdePatchResult(
        app_dir=resolved_app,
        resources_app_dir=resources_app,
        user_i18n_dir=user_dir,
        active_locale=active_locale,
        deployed_locales=deployed_locales,
        backup_dir=backup_root,
        patched_files=patched_files,
        localized_extensions=localized_extensions,
    )


def restore_ide_patch(app_dir: Optional[Path] = None, hard: bool = False) -> Path:
    """Restore Antigravity IDE files cleanly and remove injected antigravity-i18n runtime."""
    resolved_app = Path(app_dir) if app_dir else detect_antigravity_ide_dir()
    if resolved_app is None or not is_ide_app_dir(resolved_app):
        raise FileNotFoundError(
            "Could not locate Antigravity IDE installation directory (unpacked resources/app)."
        )

    resources_app = get_ide_app_resources_dir(resolved_app)
    backup_root = resources_app / IDE_BACKUP_DIRNAME
    manifest_path = backup_root / "manifest.json"
    manifest: dict = {}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
        except Exception:
            pass

    if hard:
        backed = manifest.get("backedUpFiles", [])
        if not backed:
            raise FileNotFoundError(f"No original IDE backup found under: {backup_root}")
        for rel in backed:
            src = backup_root / "files" / rel
            dst = resources_app / rel
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
    else:
        main_js_path = resources_app / IDE_MAIN_REL
        if main_js_path.is_file():
            orig = main_js_path.read_text(encoding="utf-8", errors="replace")
            cleaned = _strip_ide_main_markers(orig)
            if cleaned != orig:
                main_js_path.write_text(cleaned, encoding="utf-8")

        preload_js_path = resources_app / IDE_PRELOAD_REL
        if preload_js_path.is_file():
            orig = preload_js_path.read_text(encoding="utf-8", errors="replace")
            cleaned = strip_marker_blocks(orig).rstrip() + "\n"
            if cleaned != orig:
                preload_js_path.write_text(cleaned, encoding="utf-8")

        for ext_dir in _find_antigravity_extensions(resources_app):
            ext_rel = f"extensions/{ext_dir.name}/package.json"
            backed_pkg = backup_root / "files" / ext_rel
            pkg_path = ext_dir / "package.json"
            if backed_pkg.is_file():
                shutil.copy2(backed_pkg, pkg_path)
            elif (ext_dir / "package.nls.json").is_file() and pkg_path.is_file():
                # Fallback if backup dir was deleted manually: expand %ag.i18n.*% placeholders back.
                try:
                    nls_en = json.loads((ext_dir / "package.nls.json").read_text(encoding="utf-8"))
                    pkg_text = pkg_path.read_text(encoding="utf-8")
                    for key, val in nls_en.items():
                        if isinstance(key, str) and key.startswith("ag.i18n.") and isinstance(val, str):
                            pkg_text = pkg_text.replace(f'"%{key}%"', json.dumps(val, ensure_ascii=False))
                    pkg_path.write_text(pkg_text, encoding="utf-8")
                except Exception:
                    pass

    for rel in manifest.get("createdFiles", []):
        target = resources_app / rel
        if target.is_file():
            target.unlink()

    # Fallback cleanup for extension package.nls*.json if manifest was partially removed
    for ext_dir in _find_antigravity_extensions(resources_app):
        if (ext_dir / "package.nls.json").is_file():
            # Only remove if manifest didn't track pre-existing ones (IDE ships with zero package.nls*)
            for nls_file in ext_dir.glob("package.nls*.json"):
                nls_file.unlink()

    runtime_dir = resources_app / IDE_RUNTIME_REL
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir, ignore_errors=True)

    if backup_root.exists():
        shutil.rmtree(backup_root, ignore_errors=True)

    return resources_app


def inspect_ide_install_status(
    app_dir: Optional[Path] = None,
    user_i18n_dir: Optional[Path] = None,
) -> dict:
    """Fast status inspection for Antigravity IDE installation without mutating files."""
    status: dict = {
        "appDirFound": False,
        "appDir": "",
        "resourcesAppDir": "",
        "installed": False,
        "hasBackup": False,
        "localizedExtensions": [],
        "configuredLocale": "auto",
        "userI18nDir": str(user_i18n_dir or get_user_i18n_dir()),
        "locales": [],
    }
    try:
        resolved_app = Path(app_dir) if app_dir else detect_antigravity_ide_dir()
        if resolved_app and is_ide_app_dir(resolved_app):
            resources_app = get_ide_app_resources_dir(resolved_app)
            main_js_path = resources_app / IDE_MAIN_REL
            preload_js_path = resources_app / IDE_PRELOAD_REL
            status["appDirFound"] = main_js_path.is_file() and preload_js_path.is_file()
            status["appDir"] = str(resolved_app)
            status["resourcesAppDir"] = str(resources_app)
            status["hasBackup"] = (resources_app / IDE_BACKUP_DIRNAME / "manifest.json").is_file()
            status["installed"] = (
                (resources_app / IDE_RUNTIME_REL / "electron-ide-i18n.cjs").is_file()
                and main_js_path.is_file()
                and IDE_MAIN_START in main_js_path.read_text(encoding="utf-8", errors="replace")
            )
            status["localizedExtensions"] = [
                ext_dir.name
                for ext_dir in _find_antigravity_extensions(resources_app)
                if (ext_dir / "package.nls.json").is_file()
            ]
    except Exception as exc:
        status["error"] = str(exc)

    configured, locales = list_locales(user_i18n_dir=user_i18n_dir)
    status["configuredLocale"] = configured
    status["locales"] = locales
    return status
