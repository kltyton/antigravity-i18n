# coding: utf-8
"""Tests for Antigravity IDE unpacked runtime injection, extension NLS, target resolution, and restore."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from ag_i18n.ide_patcher import (
    IDE_BACKUP_DIRNAME,
    IDE_MAIN_START,
    inspect_ide_install_status,
    install_ide_patch,
    restore_ide_patch,
)
from ag_i18n.patcher import PRELOAD_START
from ag_i18n.paths import is_desktop_app_dir, is_ide_app_dir
from ag_i18n.targets import resolve_targets


def _create_fake_ide_app(root: Path) -> Path:
    ide_dir = root / "FakeAntigravityIDE"
    res_app = ide_dir / "resources" / "app"
    (res_app / "out" / "vs" / "base" / "parts" / "sandbox" / "electron-browser").mkdir(parents=True, exist_ok=True)
    (res_app / "extensions" / "agy").mkdir(parents=True, exist_ok=True)
    (res_app / "extensions" / "typescript-language-features").mkdir(parents=True, exist_ok=True)

    (res_app / "package.json").write_text(
        json.dumps({"name": "antigravity-ide", "type": "module", "main": "./out/main.js"}),
        encoding="utf-8",
    )
    (res_app / "product.json").write_text(
        json.dumps({"applicationName": "antigravity-ide", "nameShort": "Antigravity IDE"}),
        encoding="utf-8",
    )
    (res_app / "out" / "main.js").write_text(
        "/*! Copyright */\nconsole.log('ide main');\n",
        encoding="utf-8",
    )
    (res_app / "out" / "vs" / "base" / "parts" / "sandbox" / "electron-browser" / "preload.js").write_text(
        '"use strict";\n// third-party mod\nconst customProp = 42;\n//# sourceMappingURL=preload.js.map\n',
        encoding="utf-8",
    )

    agy_manifest = {
        "name": "google-antigravity",
        "displayName": "Google Antigravity",
        "description": "Bring Google's agent-first development platform to Visual Studio Code.",
        "contributes": {
            "commands": [
                {"command": "antigravity.openSettings", "title": "Open Settings", "category": "Antigravity"},
                {"command": "antigravity.acceptAllChanges", "title": "Accept Changes in All Files"},
            ],
            "configuration": {
                "title": "Antigravity",
                "properties": {
                    "antigravity.autoOpenFiles": {
                        "type": "boolean",
                        "description": "Automatically open files in the editor when the agent proposes edits.",
                    }
                },
            },
        },
    }
    (res_app / "extensions" / "agy" / "package.json").write_text(
        json.dumps(agy_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    ts_manifest = {
        "name": "typescript-language-features",
        "displayName": "TypeScript and JavaScript Language Features",
        "description": "Provides rich language support for JavaScript and TypeScript.",
    }
    (res_app / "extensions" / "typescript-language-features" / "package.json").write_text(
        json.dumps(ts_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ide_dir


class IdePatcherTests(unittest.TestCase):
    def test_install_preserves_vscode_extensions_and_validates_syntax(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ide_dir = _create_fake_ide_app(root)
            user_i18n = root / "user_i18n"
            res_app = ide_dir / "resources" / "app"

            self.assertTrue(is_ide_app_dir(ide_dir))
            self.assertFalse(is_desktop_app_dir(ide_dir))
            self.assertEqual(resolve_targets(target="auto", app_dir=ide_dir), [("ide", ide_dir)])

            orig_ts_pkg = (res_app / "extensions" / "typescript-language-features" / "package.json").read_text(encoding="utf-8")

            res = install_ide_patch(app_dir=ide_dir, locale="zh-CN", user_i18n_dir=user_i18n)
            self.assertEqual(res.active_locale, "zh-CN")
            self.assertEqual(res.localized_extensions, ["agy"])
            self.assertTrue((res_app / "out" / "ag-i18n" / "ide-bootstrap.mjs").is_file())
            self.assertTrue((res_app / "out" / "ag-i18n" / "electron-ide-i18n.cjs").is_file())

            # Validate patched preload.js syntax cleanly via node --check and preserve sourcemap trailer
            preload_path = res_app / "out" / "vs" / "base" / "parts" / "sandbox" / "electron-browser" / "preload.js"
            preload_text = preload_path.read_text(encoding="utf-8")
            self.assertIn(PRELOAD_START, preload_text)
            self.assertIn("__AG_I18N_PRELOAD_CONFIG__", preload_text)
            self.assertTrue(preload_text.rstrip().endswith("//# sourceMappingURL=preload.js.map"))
            subprocess.run(["node", "--check", str(preload_path)], check=True)

            # Validate main.js injection position after license header
            main_text = (res_app / "out" / "main.js").read_text(encoding="utf-8")
            self.assertTrue(main_text.startswith("/*! Copyright */\n" + IDE_MAIN_START))

            # Validate Antigravity extension NLS was generated and VS Code built-in extension was untouched
            agy_nls_en = json.loads((res_app / "extensions" / "agy" / "package.nls.json").read_text(encoding="utf-8"))
            agy_nls_zh = json.loads((res_app / "extensions" / "agy" / "package.nls.zh-cn.json").read_text(encoding="utf-8"))
            self.assertIn("Accept Changes in All Files", agy_nls_en.values())
            self.assertIn("接受所有文件中的更改", agy_nls_zh.values())
            self.assertEqual(
                (res_app / "extensions" / "typescript-language-features" / "package.json").read_text(encoding="utf-8"),
                orig_ts_pkg,
            )
            self.assertFalse((res_app / "extensions" / "typescript-language-features" / "package.nls.json").exists())

            st = inspect_ide_install_status(app_dir=ide_dir, user_i18n_dir=user_i18n)
            self.assertTrue(st["installed"])
            self.assertTrue(st["hasBackup"])
            self.assertEqual(st["localizedExtensions"], ["agy"])

    def test_surgical_and_hard_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ide_dir = _create_fake_ide_app(root)
            user_i18n = root / "user_i18n"
            res_app = ide_dir / "resources" / "app"
            main_path = res_app / "out" / "main.js"
            preload_path = res_app / "out" / "vs" / "base" / "parts" / "sandbox" / "electron-browser" / "preload.js"
            agy_pkg_path = res_app / "extensions" / "agy" / "package.json"

            orig_main = main_path.read_text(encoding="utf-8")
            orig_agy_pkg = agy_pkg_path.read_text(encoding="utf-8")

            install_ide_patch(app_dir=ide_dir, locale="zh-CN", user_i18n_dir=user_i18n)

            # Surgical restore preserves custom third-party edit added outside markers
            preload_path.write_text(
                preload_path.read_text(encoding="utf-8").replace("const customProp = 42;", "const customProp = 99;"),
                encoding="utf-8",
            )
            restore_ide_patch(app_dir=ide_dir, hard=False)
            restored_preload = preload_path.read_text(encoding="utf-8")
            self.assertIn("const customProp = 99;", restored_preload)
            self.assertNotIn(PRELOAD_START, restored_preload)
            self.assertEqual(main_path.read_text(encoding="utf-8"), orig_main)
            self.assertEqual(agy_pkg_path.read_text(encoding="utf-8"), orig_agy_pkg)
            self.assertFalse((res_app / "out" / "ag-i18n").exists())
            self.assertFalse((res_app / IDE_BACKUP_DIRNAME).exists())
            self.assertFalse((res_app / "extensions" / "agy" / "package.nls.json").exists())

            # Hard restore brings back exact raw backed-up files (discarding edits made while installed)
            install_ide_patch(app_dir=ide_dir, locale="zh-CN", user_i18n_dir=user_i18n)
            preload_path.write_text(
                preload_path.read_text(encoding="utf-8").replace("const customProp = 99;", "const customProp = 123;"),
                encoding="utf-8",
            )
            restore_ide_patch(app_dir=ide_dir, hard=True)
            restored_hard = preload_path.read_text(encoding="utf-8")
            self.assertIn("const customProp = 99;", restored_hard)
            self.assertNotIn("const customProp = 123;", restored_hard)
            self.assertEqual(main_path.read_text(encoding="utf-8"), orig_main)
            self.assertFalse((res_app / IDE_BACKUP_DIRNAME).exists())


if __name__ == "__main__":
    unittest.main()
