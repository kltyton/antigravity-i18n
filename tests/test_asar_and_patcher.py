# coding: utf-8
"""Tests for ASAR packing/extraction, third-party mod preservation, legacy migration, and restore."""

import json
import tempfile
import unittest
from pathlib import Path

from ag_i18n.asar import extract_asar, pack_asar, read_asar_header
from ag_i18n.patcher import (
    MAIN_START,
    PRELOAD_START,
    VIEW_MENU_PATCHED,
    deploy_locales,
    inspect_install_status,
    install_patch,
    list_locales,
    restore_patch,
    set_configured_locale,
)


def _create_fake_antigravity_app(root: Path, with_legacy: bool = False) -> Path:
    app_dir = root / "FakeAntigravity"
    src_dir = root / "fake_asar_src"
    dist = src_dir / "dist"
    (dist / "remote").mkdir(parents=True, exist_ok=True)
    (src_dir / "node_modules" / "native").mkdir(parents=True, exist_ok=True)

    main_body = '"use strict";\nconst electron_1 = require("electron");\n'
    if with_legacy:
        main_body += "const box = { title: '确认退出', message: '确定要退出吗？', buttons: ['取消', '退出'] };\n"
    else:
        main_body += "const box = { title: 'Confirm Quit', message: 'Are you sure you want to quit?', buttons: ['Cancel', 'Quit'] };\n"
    (dist / "main.js").write_text(main_body, encoding="utf-8")

    menu_body = (
        '"use strict";\n'
        "function configureViewZoomMenu(appMenu) {\n"
        "  const viewMenuItem = appMenu.items?.find((item) => item.label === 'View');\n"
        "  return viewMenuItem;\n"
        "}\n"
        "function addItemToSubmenu(appMenu, submenuLabel, item) {\n"
        "  const submenuItem = appMenu.items.find((item) => item.label === submenuLabel);\n"
        "  return submenuItem;\n"
        "}\n"
    )
    if with_legacy:
        menu_body += (
            "// Antigravity Chinese Localization Engine - Menu\n"
            "console.log('legacy menu');\n"
            "// Antigravity Chinese Localization Engine - Menu END\n"
        )
    (dist / "menu.js").write_text(menu_body, encoding="utf-8")

    preload_body = (
        '"use strict";\n'
        "const electron_1 = require('electron');\n"
        "// --- Antigravity Context Meter preload Injection Start ---\n"
        "electron_1.contextBridge.exposeInMainWorld('contextMeterAPI', { ping: () => 1 });\n"
        "// --- Antigravity Context Meter preload Injection End ---\n"
    )
    if with_legacy:
        preload_body += (
            "// Antigravity Chinese Localization Engine\n"
            "console.log('legacy preload 1');\n"
            "// Antigravity Chinese Localization Engine END\n"
        )
    (dist / "preload.js").write_text(preload_body, encoding="utf-8")

    # Simulate an extra third-party plugin file + unpacked native asset
    (dist / "meter-main.js").write_text("exports.installContextMeter = () => {};\n", encoding="utf-8")
    (src_dir / "node_modules" / "native" / "addon.node").write_bytes(b"\x00\x01NATIVE")

    res_dir = app_dir / "resources"
    res_dir.mkdir(parents=True, exist_ok=True)
    asar_path = res_dir / "app.asar"
    unpacked_meta = {
        "node_modules/native/addon.node": {
            "unpacked": True,
            "size": 7,
            "integrity": {"algorithm": "SHA256", "hash": "00", "blockSize": 4194304, "blocks": ["00"]},
        }
    }
    pack_asar(src_dir, asar_path, unpacked_info=unpacked_meta)
    return app_dir


class AsarAndPatcherTests(unittest.TestCase):
    def test_asar_roundtrip_preserves_unpacked_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_dir = _create_fake_antigravity_app(root, with_legacy=False)
            asar_path = app_dir / "resources" / "app.asar"
            header, _ = read_asar_header(asar_path)
            addon = header["files"]["node_modules"]["files"]["native"]["files"]["addon.node"]
            self.assertTrue(addon["unpacked"])

            out = root / "extracted"
            unpacked = extract_asar(asar_path, out)
            self.assertIn("node_modules/native/addon.node", unpacked)
            self.assertEqual((out / "dist" / "meter-main.js").read_text(encoding="utf-8"), "exports.installContextMeter = () => {};\n")

    def test_install_migrates_legacy_preserves_third_party_and_surgical_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_dir = _create_fake_antigravity_app(root, with_legacy=True)
            user_dir = root / "user_i18n"

            res = install_patch(app_dir=app_dir, locale="ja", user_i18n_dir=user_dir)
            self.assertEqual(res.active_locale, "ja")
            self.assertIn("dist/main.js", res.legacy_reverted_files)
            self.assertTrue((user_dir / "locales" / "ja.json").is_file())
            self.assertEqual(json.loads((user_dir / "config.json").read_text(encoding="utf-8"))["locale"], "ja")

            verify_dir = root / "verify_installed"
            extract_asar(res.asar_path, verify_dir)
            main_txt = (verify_dir / "dist" / "main.js").read_text(encoding="utf-8")
            menu_txt = (verify_dir / "dist" / "menu.js").read_text(encoding="utf-8")
            preload_txt = (verify_dir / "dist" / "preload.js").read_text(encoding="utf-8")

            # New modular runtime installed
            self.assertTrue((verify_dir / "dist" / "ag-i18n" / "core.js").is_file())
            self.assertTrue((verify_dir / "dist" / "ag-i18n" / "electron-i18n.js").is_file())
            self.assertIn(MAIN_START, main_txt)
            self.assertIn("title: 'Confirm Quit'", main_txt)
            self.assertNotIn("title: '确认退出'", main_txt)
            self.assertIn(VIEW_MENU_PATCHED, menu_txt)
            self.assertNotIn("Antigravity Chinese Localization Engine", menu_txt)
            self.assertIn(PRELOAD_START, preload_txt)
            self.assertIn("AntigravityI18nSettingsUi", preload_txt)
            self.assertNotIn("Antigravity Chinese Localization Engine", preload_txt)

            status_before_restore = inspect_install_status(app_dir=app_dir, user_i18n_dir=user_dir)
            self.assertTrue(status_before_restore["installed"])
            self.assertTrue(status_before_restore["hasContextMeter"])
            self.assertEqual(status_before_restore["configuredLocale"], "ja")

            # Third-party Context Meter remains completely untouched
            self.assertIn("Antigravity Context Meter preload Injection Start", preload_txt)
            self.assertTrue((verify_dir / "dist" / "meter-main.js").is_file())

            # Surgical restore removes only antigravity-i18n while keeping Context Meter
            restore_patch(app_dir=app_dir, hard=False)
            verify_restored = root / "verify_restored"
            extract_asar(res.asar_path, verify_restored)
            self.assertFalse((verify_restored / "dist" / "ag-i18n").exists())
            restored_preload = (verify_restored / "dist" / "preload.js").read_text(encoding="utf-8")
            restored_menu = (verify_restored / "dist" / "menu.js").read_text(encoding="utf-8")
            self.assertNotIn(PRELOAD_START, restored_preload)
            self.assertIn("Antigravity Context Meter preload Injection Start", restored_preload)
            self.assertNotIn(VIEW_MENU_PATCHED, restored_menu)
            self.assertIn("item.label === 'View'", restored_menu)

    def test_config_locale_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp) / "user_i18n"
            deploy_locales(user_i18n_dir=user_dir, selected_locale="auto")
            cfg, items = list_locales(user_i18n_dir=user_dir)
            self.assertEqual(cfg, "auto")
            self.assertGreaterEqual(len(items), 1)
            set_configured_locale("zh-CN", user_i18n_dir=user_dir)
            cfg2, _ = list_locales(user_i18n_dir=user_dir)
            self.assertEqual(cfg2, "zh-CN")
            with self.assertRaises(ValueError):
                set_configured_locale("xx-INVALID", user_i18n_dir=user_dir)


if __name__ == "__main__":
    unittest.main()
