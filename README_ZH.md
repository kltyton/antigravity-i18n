# antigravity-i18n

[English](README.md) | 简体中文

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![支持语言](https://img.shields.io/badge/%E6%94%AF%E6%8C%81%E8%AF%AD%E8%A8%80-10%20%E7%A7%8D%E4%B8%BB%E6%B5%81%E8%AF%AD%E8%A8%80-brightgreen.svg)](locales)

面向 **Google Antigravity Desktop** 与 **Google Antigravity IDE** 的开源、数据驱动型 **通用多语言国际化（i18n）框架与运行时引擎**。

与将单一译文硬编码进程序文件的传统脚本补丁不同，`antigravity-i18n` 将轻量级国际化运行时引擎与外部 JSON 语言包彻底解耦——支持 **跟随系统语言自动切换**、**应用内实时无重启切换语言**，并与第三方扩展干净共存。

针对基于 VS Code 的 **Antigravity IDE**：本工具**仅汉化 / 本地化其中 Google Antigravity 专属部分**（Agent Manager / Settings 独立窗口、Workbench 中的 Antigravity 面板与浮层，以及 `agy` / `antigravity-*` 内置扩展的 `package.nls*.json`），**完全不覆盖、不重复处理 VS Code 原生界面或官方语言包**。

---

## 核心特性

- **开箱支持 10 种主流语言**：
  | 语言代码 | 语言 | 语言代码 | 语言 |
  | --- | --- | --- | --- |
  | `en-US` | English | `es` | Español |
  | `zh-CN` | 简体中文 | `fr` | Français |
  | `zh-TW` | 繁體中文 | `de` | Deutsch |
  | `ja` | 日本語 | `pt-BR` | Português (Brasil) |
  | `ko` | 한국어 | `ru` | Русский |
- **外部数据驱动架构**：所有语言包（`locales/*.json`）与配置文件（`config.json`）存放在应用外的用户配置目录（Windows 为 `%APPDATA%\antigravity\i18n\`，macOS 为 `~/Library/Application Support/antigravity/i18n/`，Linux 为 `~/.config/antigravity/i18n/`），升级语言包或调整译文无需反复重打 `app.asar`。
- **应用内设置 + 托盘实时切换**：在 **设置 → 常规 → 语言 (Language)** 面板及系统托盘右键菜单、原生菜单栏中直接切换，支持随时无重启热切换任意语言或恢复为跟随系统自动检测。
- **前端界面 + Electron 原生进程全覆盖**：
  - **渲染进程与设置界面 (`runtime/preload-i18n.js`, `runtime/settings-ui.js`)**：基于 `WeakMap` 记录英文原文（多次切换语言无二次翻译污染），在 **设置 → 常规** 底部原风格嵌入显示语言切换卡片与语言包目录入口；支持 Open Shadow DOM 与同源 `iframe`，通过 `requestAnimationFrame` 合批刷新，并自动跳过代码块、Monaco 编辑器、终端与模型选择器等区域。
  - **Electron 主进程运行时 (`runtime/electron-i18n.js`, `runtime/menu-i18n.js`)**：统一接管应用主菜单、右键上下文菜单（如“项目设置”等）、系统托盘菜单与动态智能体计数、系统对话框（`showMessageBox` / `showOpenDialog` / `showSaveDialog`）、桌面通知、窗口标题以及 `data:text/html` 加载/断连提示页，同时保留菜单项内部索引查找逻辑不被破坏。
  - **通用匹配引擎 (`runtime/core.js`)**：支持精确词条、菜单上下文覆盖、省略号与中英文标点归一化（`...` / `…`）、助记快捷键（`&File`）、快捷键后缀拆分以及声明式动态正则规则（`patterns`）。
- **第三方 ASAR 插件兼容共存**：采用成对起止标记及独立 `dist/ag-i18n/` 命名空间，保留 `app.asar.unpacked` 元信息与第三方扩展（如 `antigravity-context-viewer` 等）；使用 `restore.py` 可仅外科手术式卸载 `antigravity-i18n` 而完整保留其他插件，升级自旧版硬编码汉化脚本时也会自动平滑迁移。
- **零第三方依赖**：纯 Python 标准库（Python 3.9+）实现 ASAR 解包/重打包与 SHA-256 块完整性校验。

---

## 目录结构

```text
antigravity-i18n/
├── gui.py                  # 桌面图形化管理工具（基于 Tkinter，支持双击运行或打包为 .exe）
├── cli.py                  # 统一命令行入口（install / restore / lang / langs / extract / check）
├── install.py              # 一键安装入口
├── restore.py              # 一键恢复入口（默认保留其他 ASAR 插件，支持 --hard 原档恢复）
├── ag_i18n/
│   ├── asar.py             # 纯 Python ASAR 解析、打包与 SHA-256 完整性计算
│   ├── extractor.py        # 词法/语法级前端与 Electron 菜单词条提取器
│   ├── ide_patcher.py      # Antigravity IDE 外科手术式接入与扩展 package.nls 生成器
│   ├── patcher.py          # Desktop ASAR 成对标记安装器、旧版迁移与卸载器
│   ├── paths.py            # Windows / macOS / Linux 跨平台路径与双产品检测
│   ├── targets.py          # Desktop + IDE 统一目标调度模块
│   └── validator.py        # 语言包 JSON 结构、正则语法、占位符与覆盖率校验器
├── runtime/
│   ├── core.js             # 前后端共用的通用 UMD i18n 匹配引擎
│   ├── electron-i18n.js    # Desktop 主进程统一 Hook（菜单、托盘、对话框、通知、HTML 提示页）
│   ├── ide-bootstrap.mjs   # Antigravity IDE out/main.js ESM 引导入口
│   ├── ide-main-i18n.cjs   # Antigravity IDE 作用域隔离的 vscode:ag-i18n IPC 服务
│   ├── menu-i18n.js        # 实时“语言”子菜单构造与状态同步工具
│   ├── settings-ui.js      # 应用内“设置 → 常规 → 语言”切换面板注入器
│   └── preload-i18n.js     # 兼容沙箱与作用域隔离的 WeakMap DOM 翻译运行时
├── locales/
│   ├── _template.json      # 标准英文源文本模板
│   ├── en-US.json          # 原生英文还原包
│   ├── zh-CN.json          # 简体中文
│   ├── zh-TW.json          # 繁體中文
│   ├── ja.json             # 日本語
│   ├── ko.json             # 한국어
│   ├── es.json             # Español
│   ├── fr.json             # Français
│   ├── de.json             # Deutsch
│   ├── pt-BR.json          # Português (Brasil)
│   └── ru.json             # Русский
└── tests/                  # Python 单元测试、ASAR 兼容测试、语言包校验与 Node 运行时测试
```

---

## 快速开始

### 1. 安装运行环境（推荐下载安装包或源码运行）

**方式 A — 直接运行 Windows 可执行程序（免安装 Python）：**

前往 [GitHub Releases](https://github.com/kltyton/antigravity-i18n/releases) 下载 `antigravity-i18n-gui-windows-x64.exe`（或包含全部工具的 `.zip` 压缩包），彻底退出 Antigravity 桌面端后双击打开工具，选择目标语言并点击 **安装 / 更新 i18n 运行时**。

**方式 B — 通过源码安装（Windows / macOS / Linux）：**

完全退出 **Antigravity Desktop** 后，在仓库根目录运行 `python gui.py` 打开图形界面，或使用命令行安装：

```bash
python cli.py install
```

如需在安装时指定默认语言（默认为 `auto`，即自动跟随操作系统语言）：

```bash
python cli.py install --lang zh-CN
```

如需指定自定义安装路径：

```bash
python cli.py install --target ide --lang zh-CN     # 仅安装到 Antigravity IDE
python cli.py install --target desktop --lang zh-CN # 仅安装到 Antigravity Desktop
python cli.py install --app-dir "D:\Apps\Antigravity"
```

> 也可以直接运行简化入口：`python install.py` 与 `python restore.py`。

### 2. 切换语言

启动 Antigravity 后，可在 **设置 → 常规 → 语言 (Language)** 下拉菜单中随时切换语言，或在系统托盘图标 / 原生菜单栏的 **语言 (Language)** 子菜单中即时切换；也可通过命令行修改配置：

```bash
# 查看已安装语言包
python cli.py langs

# 切换默认语言（如切换为日语或英语）
python cli.py lang ja
python cli.py lang en-US

# 恢复为跟随系统语言自动检测
python cli.py lang auto
```

### 3. 卸载与恢复

默认执行无损卸载（仅移除 `antigravity-i18n`，保留其他已安装的 ASAR 插件）：

```bash
python cli.py restore
```

如需逐字节恢复至安装前备份的原始 `app.asar`：

```bash
python cli.py restore --hard
```

---

## 维护与贡献命令

```bash
# 校验全部语言包（JSON 格式、正则有效性、占位符匹配与 100% 键覆盖率）
python cli.py check

# 从本机 Antigravity 客户端提取最新界面与菜单文本模板
python cli.py extract --output locales/_extracted.json

# 运行全套自动化测试（需 Python 3.9+ 与 Node.js 18+）
python -m unittest discover -s tests -v
```

新增语言或补充新版本词条请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 开源协议

基于 [MIT License](LICENSE) 开源。
