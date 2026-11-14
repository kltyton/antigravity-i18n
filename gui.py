# coding: utf-8
"""Desktop GUI manager for antigravity-i18n (zero third-party dependencies)."""

import ctypes
import locale as py_locale
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from ag_i18n import PROJECT_NAME, VERSION
from ag_i18n.patcher import (
    deploy_locales,
    inspect_install_status,
    install_patch,
    restore_patch,
    set_configured_locale,
)
from ag_i18n.paths import get_user_i18n_dir


UI_STRINGS: Dict[str, Dict[str, str]] = {
    "zh": {
        "title": f"{PROJECT_NAME} v{VERSION} — 多语言安装与管理工具",
        "subtitle": "非破坏性 Antigravity 桌面端多语言框架 · 兼容第三方 ASAR 插件",
        "ui_lang_label": "界面语言:",
        "app_dir_label": "Antigravity 安装目录",
        "browse_btn": "浏览...",
        "detect_btn": "自动检测",
        "lang_label": "目标显示语言",
        "status_heading": "当前状态",
        "status_installed": "i18n 运行时状态: 已安装",
        "status_not_installed": "i18n 运行时状态: 未安装",
        "status_dir_missing": "安装目录: 未找到（请点击“浏览”手动选择 Antigravity 根目录）",
        "status_ctx_yes": "第三方插件兼容: 已检测到 Antigravity Context Meter（卸载时自动保留）",
        "status_ctx_no": "第三方插件兼容: 支持并保留第三方 ASAR 插件",
        "status_running": "运行状态: 检测到 Antigravity 正在运行（安装/卸载前请先退出）",
        "status_stopped": "运行状态: 未检测到占用进程，可安全读写 app.asar",
        "close_app_btn": "关闭 Antigravity",
        "install_btn": "安装 / 更新 i18n 运行时",
        "apply_lang_btn": "仅切换语言",
        "restore_soft_btn": "卸载 i18n（保留其他插件）",
        "restore_hard_btn": "恢复原始备份 (--hard)",
        "open_locales_btn": "打开语言包目录",
        "refresh_btn": "刷新状态",
        "log_heading": "执行日志",
        "busy": "正在执行操作，请稍候...",
        "confirm_close": "确定要关闭所有正在运行的 Antigravity 进程吗？请确保没有未保存的工作。",
        "confirm_hard": "确定要执行完全恢复 (--hard) 吗？这会恢复原始 app.asar 备份并清除所有第三方 ASAR 补丁。",
        "err_running_install": "Antigravity 正在运行，Windows 会锁定 app.asar。请先退出 Antigravity 或点击“关闭 Antigravity”，然后再安装/卸载。",
        "install_ok": "安装 / 更新成功！重新打开 Antigravity 后，可在 设置 → 常规 → 语言 或托盘右键菜单中实时切换语言。",
        "lang_ok": "默认语言配置已更新；若 Antigravity 正在运行，也可直接在 设置 → 常规 → 语言 中即时切换。",
        "restore_ok": "卸载完成！已完成处理，重启 Antigravity 后生效。",
        "auto_label": "跟随系统 (auto)",
    },
    "en": {
        "title": f"{PROJECT_NAME} v{VERSION} — Multi-Language Manager",
        "subtitle": "Non-destructive i18n runtime for Google Antigravity Desktop · Compatible with 3rd-party ASAR mods",
        "ui_lang_label": "Manager UI:",
        "app_dir_label": "Antigravity App Directory",
        "browse_btn": "Browse...",
        "detect_btn": "Auto-Detect",
        "lang_label": "Display Language",
        "status_heading": "Status",
        "status_installed": "i18n Runtime: Installed",
        "status_not_installed": "i18n Runtime: Not installed",
        "status_dir_missing": "Install Directory: Not found (click Browse to locate Antigravity root folder)",
        "status_ctx_yes": "Third-Party Mods: Antigravity Context Meter detected (preserved automatically)",
        "status_ctx_no": "Third-Party Mods: Safe non-destructive patching enabled",
        "status_running": "Process State: Antigravity is currently running (close before modifying ASAR)",
        "status_stopped": "Process State: No running lock detected — ready to patch ASAR",
        "close_app_btn": "Close Antigravity",
        "install_btn": "Install / Update i18n",
        "apply_lang_btn": "Apply Language Only",
        "restore_soft_btn": "Surgical Uninstall",
        "restore_hard_btn": "Full Backup Restore",
        "open_locales_btn": "Open Locales Folder",
        "refresh_btn": "Refresh",
        "log_heading": "Activity Log",
        "busy": "Working, please wait...",
        "confirm_close": "Close all running Antigravity processes? Make sure unsaved work is saved first.",
        "confirm_hard": "Restore the raw app.asar backup (--hard)? This removes ALL ASAR patches including third-party mods.",
        "err_running_install": "Antigravity is currently running and locks app.asar. Exit Antigravity or click 'Close Antigravity' first.",
        "install_ok": "Installation succeeded! Launch Antigravity and switch languages live in Settings -> General -> Language or the tray menu.",
        "lang_ok": "Language preference saved! If Antigravity is open, you can also switch live in Settings -> General -> Language.",
        "restore_ok": "Restore completed! Restart Antigravity to apply changes.",
        "auto_label": "Follow System (auto)",
    },
}


def _enable_hidpi() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def _default_ui_lang() -> str:
    try:
        loc, _ = py_locale.getlocale()
        if loc and str(loc).lower().startswith(("zh", "chinese")):
            return "zh"
    except Exception:
        pass
    lang_env = (os.environ.get("LANG") or "").lower()
    if lang_env.startswith("zh"):
        return "zh"
    if sys.platform == "win32":
        try:
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if (lcid & 0xFF) == 0x04:  # LANG_CHINESE
                return "zh"
        except Exception:
            pass
    return "en"


def _is_antigravity_running() -> bool:
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", "IMAGENAME eq Antigravity.exe", "/NH"],
                text=True,
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return "Antigravity.exe" in out
        except Exception:
            return False
    try:
        subprocess.check_call(["pgrep", "-f", "[Aa]ntigravity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _stop_antigravity_process() -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/IM", "Antigravity.exe"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        subprocess.run(["pkill", "-f", "[Aa]ntigravity"], check=False)


def _open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class AntigravityI18nApp:
    """Tkinter desktop manager window for installing, switching, and removing antigravity-i18n."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.ui_lang = _default_ui_lang()
        self.busy = False
        self.app_dir_var = tk.StringVar()
        self.locale_var = tk.StringVar()
        self.ui_lang_var = tk.StringVar(value="中文" if self.ui_lang == "zh" else "English")
        self.locale_map: Dict[str, str] = {}
        self.reverse_locale_map: Dict[str, str] = {}

        self.root.geometry("720x590")
        self.root.minsize(640, 520)
        self._build_ui()
        self._apply_ui_text()
        self.refresh_status(auto_detect=True)

    def t(self, key: str) -> str:
        return UI_STRINGS[self.ui_lang].get(key, key)

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            if "vista" in style.theme_names():
                style.theme_use("vista")
            elif "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        main = ttk.Frame(self.root, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        header = ttk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 12))
        title_box = ttk.Frame(header)
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.title_lbl = ttk.Label(title_box, font=("Segoe UI", 14, "bold"))
        self.title_lbl.pack(anchor="w")
        self.subtitle_lbl = ttk.Label(title_box, foreground="#555555")
        self.subtitle_lbl.pack(anchor="w", pady=(2, 0))

        ui_box = ttk.Frame(header)
        ui_box.pack(side=tk.RIGHT, anchor="ne")
        self.ui_lang_lbl = ttk.Label(ui_box)
        self.ui_lang_lbl.pack(side=tk.LEFT, padx=(0, 6))
        ui_combo = ttk.Combobox(
            ui_box,
            textvariable=self.ui_lang_var,
            values=["中文", "English"],
            state="readonly",
            width=9,
        )
        ui_combo.pack(side=tk.LEFT)
        ui_combo.bind("<<ComboboxSelected>>", self._on_ui_lang_change)

        # Directory & Language settings frame
        cfg_frame = ttk.LabelFrame(main, padding=12)
        cfg_frame.pack(fill=tk.X, pady=(0, 10))
        self.cfg_frame = cfg_frame

        row1 = ttk.Frame(cfg_frame)
        row1.pack(fill=tk.X, pady=(0, 8))
        self.app_dir_lbl = ttk.Label(row1, width=22)
        self.app_dir_lbl.pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.app_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.browse_btn = ttk.Button(row1, command=self._browse_app_dir)
        self.browse_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.detect_btn = ttk.Button(row1, command=lambda: self.refresh_status(auto_detect=True))
        self.detect_btn.pack(side=tk.LEFT)

        row2 = ttk.Frame(cfg_frame)
        row2.pack(fill=tk.X)
        self.lang_lbl = ttk.Label(row2, width=22)
        self.lang_lbl.pack(side=tk.LEFT)
        self.locale_combo = ttk.Combobox(row2, textvariable=self.locale_var, state="readonly")
        self.locale_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Status frame
        st_frame = ttk.LabelFrame(main, padding=12)
        st_frame.pack(fill=tk.X, pady=(0, 10))
        self.st_frame = st_frame

        self.st_install_lbl = ttk.Label(st_frame)
        self.st_install_lbl.pack(anchor="w", pady=2)
        self.st_ctx_lbl = ttk.Label(st_frame)
        self.st_ctx_lbl.pack(anchor="w", pady=2)
        proc_row = ttk.Frame(st_frame)
        proc_row.pack(fill=tk.X, pady=2)
        self.st_proc_lbl = ttk.Label(proc_row)
        self.st_proc_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.close_app_btn = ttk.Button(proc_row, command=self._close_antigravity)
        self.close_app_btn.pack(side=tk.RIGHT)

        # Action buttons grid
        btn_row1 = ttk.Frame(main)
        btn_row1.pack(fill=tk.X, pady=(0, 6))
        self.install_btn = ttk.Button(btn_row1, command=self._do_install)
        self.install_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.apply_lang_btn = ttk.Button(btn_row1, command=self._do_apply_lang)
        self.apply_lang_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.refresh_btn = ttk.Button(btn_row1, command=lambda: self.refresh_status(auto_detect=False))
        self.refresh_btn.pack(side=tk.LEFT)

        btn_row2 = ttk.Frame(main)
        btn_row2.pack(fill=tk.X, pady=(0, 10))
        self.restore_soft_btn = ttk.Button(btn_row2, command=lambda: self._do_restore(hard=False))
        self.restore_soft_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.restore_hard_btn = ttk.Button(btn_row2, command=lambda: self._do_restore(hard=True))
        self.restore_hard_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.open_locales_btn = ttk.Button(btn_row2, command=self._do_open_locales)
        self.open_locales_btn.pack(side=tk.LEFT)

        # Log output
        log_frame = ttk.LabelFrame(main, padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_frame = log_frame
        self.log_text = tk.Text(log_frame, height=9, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 9))
        scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_ui_lang_change(self, _event=None) -> None:
        self.ui_lang = "zh" if self.ui_lang_var.get() == "中文" else "en"
        self._apply_ui_text()
        self.refresh_status(auto_detect=False)

    def _apply_ui_text(self) -> None:
        self.root.title(self.t("title"))
        self.title_lbl.config(text=f"{PROJECT_NAME} v{VERSION}")
        self.subtitle_lbl.config(text=self.t("subtitle"))
        self.ui_lang_lbl.config(text=self.t("ui_lang_label"))
        self.cfg_frame.config(text=" " + self.t("app_dir_label") + " ")
        self.app_dir_lbl.config(text=self.t("app_dir_label"))
        self.browse_btn.config(text=self.t("browse_btn"))
        self.detect_btn.config(text=self.t("detect_btn"))
        self.lang_lbl.config(text=self.t("lang_label"))
        self.st_frame.config(text=" " + self.t("status_heading") + " ")
        self.close_app_btn.config(text=self.t("close_app_btn"))
        self.install_btn.config(text=self.t("install_btn"))
        self.apply_lang_btn.config(text=self.t("apply_lang_btn"))
        self.refresh_btn.config(text=self.t("refresh_btn"))
        self.restore_soft_btn.config(text=self.t("restore_soft_btn"))
        self.restore_hard_btn.config(text=self.t("restore_hard_btn"))
        self.open_locales_btn.config(text=self.t("open_locales_btn"))
        self.log_frame.config(text=" " + self.t("log_heading") + " ")

    def log(self, msg: str) -> None:
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg.rstrip() + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _browse_app_dir(self) -> None:
        chosen = filedialog.askdirectory(title=self.t("app_dir_label"))
        if chosen:
            self.app_dir_var.set(chosen)
            self.refresh_status(auto_detect=False)

    def refresh_status(self, auto_detect: bool = False) -> None:
        custom = None if auto_detect or not self.app_dir_var.get().strip() else Path(self.app_dir_var.get().strip())
        st = inspect_install_status(app_dir=custom)
        if st.get("appDir"):
            self.app_dir_var.set(st["appDir"])

        if not st.get("appDirFound"):
            self.st_install_lbl.config(text=self.t("status_dir_missing"), foreground="#b45309")
        elif st.get("installed"):
            self.st_install_lbl.config(text=self.t("status_installed"), foreground="#15803d")
        else:
            self.st_install_lbl.config(text=self.t("status_not_installed"), foreground="#374151")

        self.st_ctx_lbl.config(
            text=self.t("status_ctx_yes") if st.get("hasContextMeter") else self.t("status_ctx_no")
        )

        running = _is_antigravity_running()
        if running:
            self.st_proc_lbl.config(text=self.t("status_running"), foreground="#b91c1c")
            self.close_app_btn.config(state=tk.NORMAL)
        else:
            self.st_proc_lbl.config(text=self.t("status_stopped"), foreground="#15803d")
            self.close_app_btn.config(state=tk.DISABLED)

        self.locale_map.clear()
        self.reverse_locale_map.clear()
        auto_disp = self.t("auto_label")
        self.locale_map[auto_disp] = "auto"
        self.reverse_locale_map["auto"] = auto_disp
        display_values: List[str] = [auto_disp]
        for loc in st.get("locales", []):
            code = loc["locale"]
            label = f"{loc.get('nativeName', code)} ({code})"
            self.locale_map[label] = code
            self.reverse_locale_map[code] = label
            display_values.append(label)

        self.locale_combo.config(values=display_values)
        cur_code = st.get("configuredLocale", "auto")
        self.locale_var.set(self.reverse_locale_map.get(cur_code, auto_disp))

    def _selected_locale(self) -> str:
        return self.locale_map.get(self.locale_var.get(), "auto")

    def _set_busy(self, flag: bool) -> None:
        self.busy = flag
        state = tk.DISABLED if flag else tk.NORMAL
        for btn in (
            self.install_btn,
            self.apply_lang_btn,
            self.restore_soft_btn,
            self.restore_hard_btn,
            self.refresh_btn,
        ):
            btn.config(state=state)

    def _run_bg(self, fn) -> None:
        if self.busy:
            return
        self._set_busy(True)
        self.log(self.t("busy"))

        def worker() -> None:
            try:
                fn()
            except Exception as exc:
                self.root.after(0, lambda e=exc: (self.log(f"[ERROR] {e}"), messagebox.showerror(PROJECT_NAME, str(e))))
            finally:
                self.root.after(0, lambda: (self._set_busy(False), self.refresh_status(auto_detect=False)))

        threading.Thread(target=worker, daemon=True).start()

    def _close_antigravity(self) -> None:
        if messagebox.askyesno(PROJECT_NAME, self.t("confirm_close")):
            _stop_antigravity_process()
            self.root.after(500, lambda: self.refresh_status(auto_detect=False))

    def _do_install(self) -> None:
        if _is_antigravity_running():
            messagebox.showwarning(PROJECT_NAME, self.t("err_running_install"))
            return
        app_path = Path(self.app_dir_var.get().strip()) if self.app_dir_var.get().strip() else None
        chosen_loc = self._selected_locale()

        def task() -> None:
            res = install_patch(app_dir=app_path, locale=chosen_loc)
            msg = (
                f"[OK] ASAR: {res.asar_path}\n"
                f"     Locale: {res.active_locale} | Packs: {', '.join(res.deployed_locales)}"
            )
            self.root.after(0, lambda: (self.log(msg), messagebox.showinfo(PROJECT_NAME, self.t("install_ok"))))

        self._run_bg(task)

    def _do_apply_lang(self) -> None:
        chosen_loc = self._selected_locale()

        def task() -> None:
            deploy_locales(selected_locale=chosen_loc)
            cfg = set_configured_locale(chosen_loc)
            self.root.after(
                0,
                lambda: (
                    self.log(f"[OK] Config updated -> {cfg} (locale={chosen_loc})"),
                    messagebox.showinfo(PROJECT_NAME, self.t("lang_ok")),
                ),
            )

        self._run_bg(task)

    def _do_restore(self, hard: bool) -> None:
        if _is_antigravity_running():
            messagebox.showwarning(PROJECT_NAME, self.t("err_running_install"))
            return
        if hard and not messagebox.askyesno(PROJECT_NAME, self.t("confirm_hard")):
            return
        app_path = Path(self.app_dir_var.get().strip()) if self.app_dir_var.get().strip() else None

        def task() -> None:
            asar_path = restore_patch(app_dir=app_path, hard=hard)
            self.root.after(
                0,
                lambda: (
                    self.log(f"[OK] Restored ({'hard' if hard else 'surgical'}): {asar_path}"),
                    messagebox.showinfo(PROJECT_NAME, self.t("restore_ok")),
                ),
            )

        self._run_bg(task)

    def _do_open_locales(self) -> None:
        deploy_locales()
        _open_folder(get_user_i18n_dir() / "locales")


def main() -> int:
    _enable_hidpi()
    root = tk.Tk()
    AntigravityI18nApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
