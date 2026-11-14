# antigravity-i18n

[English](README.md) | [简体中文](README_ZH.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Supported Languages](https://img.shields.io/badge/Languages-10%20Locales-brightgreen.svg)](locales)

An open-source, data-driven **multi-language internationalization (i18n) framework and runtime engine** for **Google Antigravity Desktop**.

Instead of hardcoding translated strings inside Electron scripts or requiring re-patching whenever you want to switch languages, `antigravity-i18n` separates a lightweight runtime engine from external JSON locale bundles stored in your user configuration directory — enabling **instant live language switching**, **OS locale auto-detection**, and **compatibility with third-party ASAR extensions**.

---

## Key Features

- **10 Built-in Languages Out of the Box**:
  | Code | Language | Code | Language |
  | --- | --- | --- | --- |
  | `en-US` | English | `es` | Español |
  | `zh-CN` | 简体中文 | `fr` | Français |
  | `zh-TW` | 繁體中文 | `de` | Deutsch |
  | `ja` | 日本語 | `pt-BR` | Português (Brasil) |
  | `ko` | 한국어 | `ru` | Русский |
- **External Data-Driven Architecture**: Language bundles (`locales/*.json`) and your preference (`config.json`) live outside `app.asar` (e.g., `%APPDATA%\antigravity\i18n\` on Windows, `~/Library/Application Support/antigravity/i18n/` on macOS, `~/.config/antigravity/i18n/` on Linux).
- **Live Switching Without Restarting**: Switch languages anytime from **Settings → General → Language**, the system tray **Language** submenu, or the native top menu bar — or follow your OS language automatically (`"auto"`).
- **Full Desktop + Web UI Coverage**:
  - **Renderer DOM & Settings UI (`runtime/preload-i18n.js`, `runtime/settings-ui.js`)**: WeakMap-backed original text tracking, Shadow DOM & same-origin iframe observation, native-styled **Display Language** selector injected into **Settings → General**, smooth `requestAnimationFrame` mutation batching, and automatic exclusion of code blocks, Monaco editors, terminals, and model selectors.
  - **Electron Main Process (`runtime/electron-i18n.js`, `runtime/menu-i18n.js`)**: Hooks `Menu`, `Tray`, native context menus, system dialogs (`showMessageBox`, `showOpenDialog`, `showSaveDialog`), desktop notifications, window titles, and `data:text/html` splash/disconnected overlays while keeping internal Electron menu lookups intact.
  - **Smart Matching Engine (`runtime/core.js`)**: Handles exact phrases, context-aware menu overrides, ellipsis/punctuation normalization (`...` / `…`), keyboard accelerators (`&File`), trailing shortcut splits, and declarative regex rules (`patterns`).
- **Safe Third-Party Mod Coexistence**: Uses paired marker blocks and a dedicated `dist/ag-i18n/` namespace while preserving `app.asar.unpacked` metadata and external ASAR extensions (such as `antigravity-context-viewer`). Supports surgical uninstall (`restore.py`) without removing other mods.
- **Zero External Dependencies**: Runs on Python standard library (Python 3.9+) with a pure-Python ASAR reader/writer + integrity hash calculator.

---

## Architecture Overview

```text
antigravity-i18n/
├── gui.py                  # Standalone desktop GUI manager (Tkinter, double-click or bundle as .exe)
├── cli.py                  # Unified CLI (install / restore / lang / langs / extract / check)
├── install.py              # Standalone quick installer
├── restore.py              # Standalone restorer (surgical or --hard backup)
├── ag_i18n/
│   ├── asar.py             # Pure-Python ASAR parser, packer & SHA-256 block integrity
│   ├── extractor.py        # Lexical/AST UI & menu string extractor
│   ├── patcher.py          # Marker-safe ASAR installer, legacy migrator & restorer
│   ├── paths.py            # Cross-platform Windows / macOS / Linux path resolution
│   └── validator.py        # Locale JSON schema, regex, placeholder & coverage checker
├── runtime/
│   ├── core.js             # Shared UMD i18n lookup & regex matching engine
│   ├── electron-i18n.js    # Main-process hooks (Menu, Tray, Dialog, Notification, HTML overlays)
│   ├── menu-i18n.js        # Live "Language" submenu builder & item tracker
│   ├── settings-ui.js      # Native-styled in-app Settings -> General -> Language picker
│   └── preload-i18n.js     # Sandbox-safe renderer WeakMap DOM & Shadow DOM translator
├── locales/
│   ├── _template.json      # Canonical English source template
│   ├── en-US.json          # Native English identity pack
│   ├── zh-CN.json          # Simplified Chinese
│   ├── zh-TW.json          # Traditional Chinese
│   ├── ja.json             # Japanese
│   ├── ko.json             # Korean
│   ├── es.json             # Spanish
│   ├── fr.json             # French
│   ├── de.json             # German
│   ├── pt-BR.json          # Portuguese (Brazil)
│   └── ru.json             # Russian
└── tests/                  # Automated unit, ASAR, locale & Node runtime tests
```

---

## Quick Start

### 1. Install (GUI Executable or Source)

**Option A — Pre-built Windows Executable (No Python Required):**

Download `antigravity-i18n-gui-windows-x64.exe` (or the full `.zip` bundle) from [GitHub Releases](https://github.com/kltyton/antigravity-i18n/releases), close Antigravity Desktop, double-click the executable, pick a language, and click **Install / Update i18n**.

**Option B — From Source (Windows / macOS / Linux):**

Close **Antigravity Desktop**, then run `python gui.py` for the desktop GUI or install via CLI:

```bash
python cli.py install
```

Or specify a default language up front:

```bash
python cli.py install --lang ja
```

Custom installation path is supported via `--app-dir`:

```bash
python cli.py install --app-dir "D:\Apps\Antigravity"
```

> Standalone single-click wrappers `python install.py` and `python restore.py` are also included.

### 2. Switch Languages Anytime

Launch Antigravity and switch live in **Settings → General → Language**, or from the system tray icon / native menu bar **Language** submenu, or update via CLI:

```bash
# List installed language packs
python cli.py langs

# Switch default language
python cli.py lang zh-CN

# Revert to OS language auto-detection
python cli.py lang auto
```

### 3. Restore / Uninstall

Remove `antigravity-i18n` cleanly while keeping other ASAR modifications intact:

```bash
python cli.py restore
```

Or restore the exact pre-patch ASAR backup:

```bash
python cli.py restore --hard
```

---

## Maintainer & Contributor Commands

```bash
# Validate all locale packs (JSON schema, regexes, placeholders, 100% key coverage)
python cli.py check

# Extract UI and Electron menu/dialog strings from a local Antigravity installation
python cli.py extract --output locales/_extracted.json

# Run the full automated test suite (requires Python 3.9+ and Node.js 18+)
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for instructions on adding new language packs or updating translations for newer Antigravity releases.

---

## License

Released under the [MIT License](LICENSE).
