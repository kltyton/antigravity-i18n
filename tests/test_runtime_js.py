# coding: utf-8
"""Node-executed runtime tests for core.js, menu-i18n.js, electron-i18n.js, and preload-i18n.js."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from ag_i18n.paths import LOCALES_DIR, REPO_ROOT


def _run_node(script: str) -> dict:
    proc = subprocess.run(
        ["node", "-"],
        input=script,
        cwd=str(REPO_ROOT),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


class RuntimeJsTests(unittest.TestCase):
    def test_core_matching_rules_and_cjk_punctuation(self):
        script = r"""
const core = require('./runtime/core');
const fs = require('fs');
const zh = JSON.parse(fs.readFileSync('./locales/zh-CN.json', 'utf8'));
const t = core.createTranslator(zh);

const checks = {
  change_unicode: t.translate('Change\u2026'),
  change_ascii: t.translate('Change...'),
  lowercase_project_settings: t.translate('project settings', { context: 'menu' }),
  accelerator_file: t.translate('&File', { context: 'menu' }),
  trailing_shortcut: t.translate('Settings Ctrl+,', { context: 'menu' }),
  dynamic_worked: t.translate('Worked for 12s'),
  dynamic_breakdowns: t.translate('Show 3 breakdowns'),
  dynamic_upgrade: t.translate('You can upgrade to a higher Google AI Ultra plan to receive the highest rate limits.'),
  dynamic_weekly_quota: t.translate('You have used some of your weekly limit, it will fully refresh in 6 days, 16 hours.'),
  browser_subagent_desc: t.translate('Configure allowed and denied URLs for the browser subagent. It runs in the built-in browser, so no separate browser install is needed.'),
  url_untouched: t.translate('https://github.com/kltyton/antigravity-i18n'),
  win_path_untouched: t.translate('C:\\Users\\demo\\project'),
  identity_check: core.createTranslator(JSON.parse(fs.readFileSync('./locales/en-US.json', 'utf8'))).translate('Project Settings')
};
console.log(JSON.stringify(checks));
"""
        res = _run_node(script)
        self.assertEqual(res["change_unicode"], "更改…")
        self.assertEqual(res["change_ascii"], "更改…")
        self.assertEqual(res["lowercase_project_settings"], "项目设置")
        self.assertEqual(res["accelerator_file"], "文件(&F)")
        self.assertIn("Ctrl+,", res["trailing_shortcut"])
        self.assertEqual(res["dynamic_worked"], "运行耗时 12 秒")
        self.assertEqual(res["dynamic_breakdowns"], "显示 3 项明细")
        self.assertEqual(res["dynamic_upgrade"], "您可以升级到更高级别的 Google AI Ultra 套餐，以获得最高的速率限制。")
        self.assertEqual(res["dynamic_weekly_quota"], "您已使用部分每周限额，它将在 6 天 16 小时 后完全重置。")
        self.assertEqual(res["browser_subagent_desc"], "为浏览器子智能体配置允许和拒绝的 URL。它会在内置浏览器中运行，无需单独安装浏览器。")
        self.assertEqual(res["url_untouched"], "https://github.com/kltyton/antigravity-i18n")
        self.assertEqual(res["win_path_untouched"], "C:\\Users\\demo\\project")
        self.assertEqual(res["identity_check"], "Project Settings")

    def test_preload_weakmap_live_locale_switch_and_protection(self):
        script = r"""
const core = require('./runtime/core');
const preload = require('./runtime/preload-i18n');

const zhBundle = {
  meta: { locale: 'zh-CN', punctuationStyle: 'cjk' },
  exact: { 'Project Settings': '项目设置', 'Change…': '更改…', 'Search…': '搜索…' },
  patterns: []
};
const esBundle = {
  meta: { locale: 'es', punctuationStyle: 'ascii' },
  exact: { 'Project Settings': 'Configuración del proyecto', 'Change…': 'Cambiar…', 'Search…': 'Buscar…' },
  patterns: []
};
const enBundle = { meta: { locale: 'en-US', punctuationStyle: 'ascii' }, exact: {}, patterns: [] };

function makeNode(tag, attrs, textVal, closestMatch) {
  const el = {
    nodeType: 1,
    tagName: tag.toUpperCase(),
    _attrs: Object.assign({}, attrs || {}),
    childNodes: [],
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this._attrs, k); },
    getAttribute(k) { return this._attrs[k]; },
    setAttribute(k, v) { this._attrs[k] = String(v); },
    closest(sel) { return closestMatch && sel.includes(closestMatch) ? this : null; }
  };
  if (textVal !== undefined) {
    el.childNodes.push({
      nodeType: 3,
      nodeValue: textVal,
      parentElement: el
    });
  }
  return el;
}

const root = makeNode('div', {}, undefined, null);
const btn = makeNode('button', { 'aria-label': 'Project Settings' }, 'Project Settings', null);
const inp = makeNode('input', { placeholder: 'Search…' }, undefined, null);
const code = makeNode('code', {}, 'Project Settings', 'code');
const modelBadge = makeNode('span', {}, 'Project Settings', '[data-testid^="model-selector"]');
root.childNodes.push(btn, inp, code, modelBadge);

const doc = { documentElement: root };
const domT = preload.createDomTranslator(zhBundle, core);
domT.scanSubtree(root);
const afterZh = {
  btn: btn.childNodes[0].nodeValue,
  aria: btn.getAttribute('aria-label'),
  placeholder: inp.getAttribute('placeholder'),
  code: code.childNodes[0].nodeValue,
  model: modelBadge.childNodes[0].nodeValue
};

domT.updateBundle(esBundle, doc);
const afterEs = {
  btn: btn.childNodes[0].nodeValue,
  aria: btn.getAttribute('aria-label'),
  placeholder: inp.getAttribute('placeholder')
};

domT.updateBundle(enBundle, doc);
const afterEn = {
  btn: btn.childNodes[0].nodeValue,
  aria: btn.getAttribute('aria-label'),
  placeholder: inp.getAttribute('placeholder')
};

console.log(JSON.stringify({
  afterZh,
  afterEs,
  afterEn,
  allowLocalhost: preload.isAntigravityUiLocation({ protocol: 'https:', hostname: '127.0.0.1' }),
  blockExternal: preload.isAntigravityUiLocation({ protocol: 'https:', hostname: 'github.com' })
}));
"""
        res = _run_node(script)
        self.assertEqual(res["afterZh"]["btn"], "项目设置")
        self.assertEqual(res["afterZh"]["aria"], "项目设置")
        self.assertEqual(res["afterZh"]["placeholder"], "搜索…")
        self.assertEqual(res["afterZh"]["code"], "Project Settings")
        self.assertEqual(res["afterZh"]["model"], "Project Settings")

        # Switching directly from zh-CN -> es uses stored English original without double-translating!
        self.assertEqual(res["afterEs"]["btn"], "Configuración del proyecto")
        self.assertEqual(res["afterEs"]["aria"], "Configuración del proyecto")
        self.assertEqual(res["afterEs"]["placeholder"], "Buscar…")

        # Switching back to en-US cleanly restores original English strings!
        self.assertEqual(res["afterEn"]["btn"], "Project Settings")
        self.assertEqual(res["afterEn"]["aria"], "Project Settings")
        self.assertEqual(res["afterEn"]["placeholder"], "Search…")

        self.assertTrue(res["allowLocalhost"])
        self.assertFalse(res["blockExternal"])

    def test_electron_main_hooks_live_switching_and_data_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            i18n_dir = Path(tmp) / "i18n"
            locales_sub = i18n_dir / "locales"
            locales_sub.mkdir(parents=True, exist_ok=True)
            for name in ("en-US.json", "zh-CN.json"):
                (locales_sub / name).write_text((LOCALES_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
            (i18n_dir / "config.json").write_text('{"locale":"zh-CN"}', encoding="utf-8")

            script = f"""
process.env.AG_I18N_NO_AUTO_INIT = '1';
const {{ initElectronI18n, translateDataUrlIfHtml }} = require('./runtime/electron-i18n');
const core = require('./runtime/core');

class MockMenuItem {{
  constructor(tpl) {{ Object.assign(this, tpl); }}
}}
const symLabelDesc = Object.getOwnPropertyDescriptor(MockMenuItem.prototype, 'label');
// Provide prototype accessor so updater-style item.label = ... interception is exercised
let _protoStore = new WeakMap();
Object.defineProperty(MockMenuItem.prototype, 'label', {{
  configurable: true,
  get() {{ return _protoStore.has(this) ? _protoStore.get(this) : this._rawLbl; }},
  set(v) {{ _protoStore.set(this, v); }}
}});

let currentAppMenu = null;
class MockMenu {{
  constructor(items) {{ this.items = items || []; }}
  insert(pos, item) {{ this.items.splice(pos, 0, item); }}
  append(item) {{ this.items.push(item); }}
  popup() {{}}
  getMenuItemById(id) {{
    for (const it of this.items) {{
      if (it.id === id) return it;
      if (it.submenu && it.submenu.getMenuItemById) {{
        const hit = it.submenu.getMenuItemById(id);
        if (hit) return hit;
      }}
    }}
    return null;
  }}
  static buildFromTemplate(tpl) {{
    const items = tpl.map(t => {{
      const mi = new MockMenuItem(Object.assign({{}}, t));
      if (Array.isArray(t.submenu)) mi.submenu = MockMenu.buildFromTemplate(t.submenu);
      return mi;
    }});
    return new MockMenu(items);
  }}
  static setApplicationMenu(m) {{ currentAppMenu = m; }}
  static getApplicationMenu() {{ return currentAppMenu; }}
}}

let currentTrayMenu = null;
let trayTip = '';
class MockTray {{
  setToolTip(s) {{ trayTip = s; }}
  setContextMenu(m) {{ currentTrayMenu = m; }}
}}

let lastDialogOpts = null;
const fakeElectron = {{
  Menu: MockMenu,
  MenuItem: MockMenuItem,
  Tray: MockTray,
  dialog: {{ showMessageBox: async (opts) => {{ lastDialogOpts = opts; return {{ response: 1 }}; }} }},
  Notification: function(opts) {{ this.opts = opts; }},
  BrowserWindow: {{ prototype: {{ setTitle(t) {{ this.t = t; }} }}, getAllWindows: () => [] }},
  ipcMain: {{ on() {{}}, handle() {{}} }},
  app: {{ getLocale: () => 'zh-CN', on() {{}} }},
  shell: {{ openPath: async () => '' }}
}};

const mgr = initElectronI18n({{ electron: fakeElectron, baseDir: {json.dumps(str(i18n_dir))} }});
const appMenu = fakeElectron.Menu.buildFromTemplate([
  {{ label: 'View', submenu: [{{ id: 'check-for-updates', label: 'Check for Updates' }}] }}
]);
fakeElectron.Menu.setApplicationMenu(appMenu);
const viewOrigPreserved = currentAppMenu.items[0]._agI18nOrigLabel;
const viewTranslated = currentAppMenu.items[0].label;
const hasLangMenu = currentAppMenu.items.some(i => i.id === 'ag-i18n-language-menu');

// Simulate dist/updater.js assigning directly onto the live menu item
const updItem = fakeElectron.Menu.getApplicationMenu().getMenuItemById('check-for-updates');
updItem.label = 'Checking for Updates...';
const updaterTranslated = updItem.label;

// Simulate dist/tray.js
const tray = new fakeElectron.Tray();
tray.setToolTip('Antigravity');
const rawTray = fakeElectron.Menu.buildFromTemplate([
  {{ id: 'running-agents', label: 'No agents running' }},
  {{ label: 'Quit' }}
]);
tray.setContextMenu(rawTray);
const trayAgentBefore = currentTrayMenu.items[0].label;

// Simulate dialog.showMessageBox
fakeElectron.dialog.showMessageBox({{ title: 'Confirm Quit', message: 'Are you sure you want to quit?', buttons: ['Cancel', 'Quit'] }});

// Simulate data:text/html overlay
const htmlUrl = 'data:text/html;charset=utf-8,' + encodeURIComponent('<html><body><div>Loading Antigravity</div></body></html>');
const outHtmlUrl = translateDataUrlIfHtml(htmlUrl, core.createTranslator(mgr.getState().bundle));

// Live switch back to en-US
mgr.setLocale('en-US');
const viewAfterEn = currentAppMenu.items[0].label;
const updaterAfterEn = fakeElectron.Menu.getApplicationMenu().getMenuItemById('check-for-updates').label;
const trayAgentAfterEn = currentTrayMenu.items[0].label;

console.log(JSON.stringify({{
  viewOrigPreserved,
  viewTranslated,
  hasLangMenu,
  updaterTranslated,
  trayAgentBefore,
  dialogTitle: lastDialogOpts.title,
  dialogButtons: lastDialogOpts.buttons,
  htmlTranslated: decodeURIComponent(outHtmlUrl).includes('正在加载 Antigravity'),
  viewAfterEn,
  updaterAfterEn,
  trayAgentAfterEn
}}));
"""
            res = _run_node(script)
            self.assertEqual(res["viewOrigPreserved"], "View")
            self.assertEqual(res["viewTranslated"], "查看")
            self.assertTrue(res["hasLangMenu"])
            self.assertEqual(res["updaterTranslated"], "正在检查更新...")
            self.assertEqual(res["trayAgentBefore"], "暂无运行中的智能体")
            self.assertEqual(res["dialogTitle"], "确认退出")
            self.assertEqual(res["dialogButtons"], ["取消", "退出"])
            self.assertTrue(res["htmlTranslated"])
            self.assertEqual(res["viewAfterEn"], "View")
            self.assertEqual(res["updaterAfterEn"], "Checking for Updates...")
            self.assertEqual(res["trayAgentAfterEn"], "No agents running")


if __name__ == "__main__":
    unittest.main()
