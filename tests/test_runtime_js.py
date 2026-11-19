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
  copy_project_name: t.translate('Copy Project Name'),
  see_all_count: t.translate('See all (12)'),
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
        self.assertEqual(res["copy_project_name"], "复制项目名称")
        self.assertEqual(res["see_all_count"], "查看全部 (12)")
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
const syncHandlers = {{}};
const invokeHandlers = {{}};
const MockNotification = function(opts) {{ this.opts = opts; }};
MockNotification.isSupported = () => true;
const mockDialog = {{ showMessageBox: async (opts) => {{ lastDialogOpts = opts; return {{ response: 1 }}; }} }};
const mockBrowserWindow = {{ prototype: {{ setTitle(t) {{ this.t = t; }} }}, getAllWindows: () => [] }};
const mockBaseWindow = {{ prototype: {{ setTitle(t) {{ this.t = t; }} }}, getAllWindows: () => [] }};
const mockIpcMain = {{ on(ch, fn) {{ syncHandlers[ch] = fn; }}, handle(ch, fn) {{ invokeHandlers[ch] = fn; }} }};
const mockApp = {{ getLocale: () => 'zh-CN', on() {{}} }};
const mockShell = {{ openPath: async () => '' }};
const fakeElectron = {{}};
Object.defineProperties(fakeElectron, {{
  Menu: {{ get: () => MockMenu, enumerable: true, configurable: false }},
  MenuItem: {{ get: () => MockMenuItem, enumerable: true, configurable: false }},
  Tray: {{ get: () => MockTray, enumerable: true, configurable: false }},
  dialog: {{ get: () => mockDialog, enumerable: true, configurable: false }},
  Notification: {{ get: () => MockNotification, enumerable: true, configurable: false }},
  BrowserWindow: {{ get: () => mockBrowserWindow, enumerable: true, configurable: false }},
  BaseWindow: {{ get: () => mockBaseWindow, enumerable: true, configurable: false }},
  ipcMain: {{ get: () => mockIpcMain, enumerable: true, configurable: false }},
  app: {{ get: () => mockApp, enumerable: true, configurable: false }},
  shell: {{ get: () => mockShell, enumerable: true, configurable: false }},
}});

const mgr = initElectronI18n({{ electron: fakeElectron, baseDir: {json.dumps(str(i18n_dir))} }});
if (!mgr) throw new Error('initElectronI18n returned null on getter-only Electron exports!');
const syncEvt = {{}};
syncHandlers['ag-i18n:get-state-sync'](syncEvt);
const startupLocale = syncEvt.returnValue && syncEvt.returnValue.locale;
const hasSetLocaleHandler = typeof invokeHandlers['ag-i18n:set-locale'] === 'function';
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
  startupLocale,
  hasSetLocaleHandler,
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
            self.assertEqual(res["startupLocale"], "zh-CN")
            self.assertTrue(res["hasSetLocaleHandler"])
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

    def test_settings_ui_mounts_in_general_and_switches_live(self):
        script = f"""
const path = require('path');
const fs = require('fs');
const core = require('./runtime/core.js');
const preload = require('./runtime/preload-i18n.js');
const settingsUi = require('./runtime/settings-ui.js');

const zhBundle = JSON.parse(fs.readFileSync(path.join({json.dumps(str(LOCALES_DIR))}, 'zh-CN.json'), 'utf8'));
const enBundle = JSON.parse(fs.readFileSync(path.join({json.dumps(str(LOCALES_DIR))}, 'en-US.json'), 'utf8'));
const jaBundle = JSON.parse(fs.readFileSync(path.join({json.dumps(str(LOCALES_DIR))}, 'ja.json'), 'utf8'));

function makeEl(tag) {{
  const attrs = {{}};
  const listeners = {{}};
  const el = {{
    tagName: tag.toUpperCase(),
    nodeType: 1,
    className: '',
    id: '',
    value: '',
    disabled: false,
    childNodes: [],
    parentElement: null,
    style: {{}},
    get firstChild() {{ return this.childNodes[0] || null; }},
    get children() {{ return this.childNodes.filter(c => c.nodeType === 1); }},
    setAttribute(k, v) {{ attrs[k] = String(v); }},
    getAttribute(k) {{ return k in attrs ? attrs[k] : null; }},
    hasAttribute(k) {{ return k in attrs; }},
    appendChild(child) {{
      child.parentElement = this;
      this.childNodes.push(child);
      return child;
    }},
    removeChild(child) {{
      const i = this.childNodes.indexOf(child);
      if (i !== -1) this.childNodes.splice(i, 1);
      child.parentElement = null;
      return child;
    }},
    addEventListener(evt, fn) {{
      (listeners[evt] = listeners[evt] || []).push(fn);
    }},
    dispatchEvent(evt) {{
      const list = listeners[evt.type] || [];
      list.forEach(fn => fn(evt));
    }},
    closest(sel) {{
      if (sel.includes('[data-ag-i18n-ignore]')) {{
        let p = this;
        while (p) {{
          if (p.hasAttribute && p.hasAttribute('data-ag-i18n-ignore')) return p;
          p = p.parentElement;
        }}
      }}
      if (sel === '.max-w-2xl') {{
        let p = this;
        while (p) {{
          if (String(p.className || '').includes('max-w-2xl')) return p;
          p = p.parentElement;
        }}
      }}
      return null;
    }},
    querySelectorAll(sel) {{
      const out = [];
      const walk = (node) => {{
        for (const c of node.childNodes || []) {{
          if (c.nodeType === 1) {{
            if (sel === 'h2' && c.tagName === 'H2') out.push(c);
            walk(c);
          }}
        }}
      }};
      walk(this);
      return out;
    }},
    querySelector(sel) {{
      const mAttr = sel.match(/^\\[([a-zA-Z0-9_-]+)(?:="([^"]*)")?\\]$/);
      const walk = (node) => {{
        for (const c of node.childNodes || []) {{
          if (c.nodeType === 1) {{
            if (mAttr) {{
              if (c.hasAttribute(mAttr[1]) && (mAttr[2] === undefined || c.getAttribute(mAttr[1]) === mAttr[2])) {{
                return c;
              }}
            }}
            const found = walk(c);
            if (found) return found;
          }}
        }}
        return null;
      }};
      return walk(this);
    }},
    get textContent() {{
      return this.childNodes.map(c => c.nodeType === 3 ? c.nodeValue : c.textContent).join('');
    }},
    set textContent(v) {{
      this.childNodes = [];
      if (v !== '' && v !== null && v !== undefined) {{
        const t = {{ nodeType: 3, nodeValue: String(v), parentElement: this }};
        this.childNodes.push(t);
      }}
    }},
  }};
  return el;
}}

const docRoot = makeEl('div');
const maxW = makeEl('div');
maxW.className = 'p-6 flex flex-col gap-4 w-full max-w-2xl mx-auto';
const headerBox = makeEl('div');
const h2 = makeEl('h2');
h2.className = 'text-2xl m-0 font-medium truncate flex-1 text-foreground';
h2.textContent = 'General';
headerBox.appendChild(h2);
const sectionsWrap = makeEl('div');
sectionsWrap.className = 'flex flex-col gap-8 w-full';
maxW.appendChild(headerBox);
maxW.appendChild(sectionsWrap);
docRoot.appendChild(maxW);

const fakeDoc = {{
  documentElement: docRoot,
  createElement: makeEl,
  querySelectorAll: (s) => docRoot.querySelectorAll(s),
}};

const bundles = {{ 'zh-CN': zhBundle, 'en-US': enBundle, 'ja': jaBundle }};
let state = {{
  locale: 'zh-CN',
  config: {{ locale: 'zh-CN' }},
  locales: [
    {{ locale: 'en-US', name: 'English', nativeName: 'English' }},
    {{ locale: 'zh-CN', name: 'Chinese (Simplified)', nativeName: '简体中文' }},
    {{ locale: 'ja', name: 'Japanese', nativeName: '日本語' }}
  ],
  bundle: zhBundle
}};

const dom = preload.createDomTranslator(state.bundle, core);
dom.observeRoot(docRoot, {{}});

const ctrl = settingsUi.createSettingsController({{
  document: fakeDoc,
  getState: () => state,
  getOriginalText: dom.getOriginalText,
  onSelectLocale: (nextLoc) => {{
    const nextBundle = bundles[nextLoc];
    state = Object.assign({{}}, state, {{ locale: nextLoc, config: {{ locale: nextLoc }}, bundle: nextBundle }});
    dom.updateBundle(nextBundle, fakeDoc, {{}});
    ctrl.sync();
    return Promise.resolve(state);
  }}
}});

ctrl.sync();
ctrl.sync(); // verify idempotence (only 1 injected card)
const h2Zh = h2.textContent;
const countZh = sectionsWrap.children.length;
const titleZh = sectionsWrap.querySelector('[data-ag-i18n-role="section-title"]').textContent;
const sel = sectionsWrap.querySelector('[data-testid="ag-i18n-language-select"]');
const valZh = sel.value;

// Switch via dropdown to 'ja'
sel.value = 'ja';
sel.dispatchEvent({{ type: 'change' }});
const h2Ja = h2.textContent;
const titleJa = sectionsWrap.querySelector('[data-ag-i18n-role="section-title"]').textContent;
const valJa = sel.value;

// Switch back to 'en-US'
dom.updateBundle(enBundle, fakeDoc, {{}});
state = Object.assign({{}}, state, {{ locale: 'en-US', config: {{ locale: 'en-US' }}, bundle: enBundle }});
ctrl.sync();
const h2En = h2.textContent;
const titleEn = sectionsWrap.querySelector('[data-ag-i18n-role="section-title"]').textContent;

console.log(JSON.stringify({{ h2Zh, countZh, titleZh, valZh, h2Ja, titleJa, valJa, h2En, titleEn }}));
"""
        res = _run_node(script)
        self.assertEqual(res["h2Zh"], "常规")
        self.assertEqual(res["countZh"], 1)
        self.assertEqual(res["titleZh"], "语言 (Language)")
        self.assertEqual(res["valZh"], "zh-CN")
        self.assertEqual(res["h2Ja"], "一般")
        self.assertEqual(res["titleJa"], "言語 (Language)")
        self.assertEqual(res["valJa"], "ja")
        self.assertEqual(res["h2En"], "General")
        self.assertEqual(res["titleEn"], "Language")

    def test_ide_scoped_dom_isolation_and_vscode_file_protocol(self):
        script = r"""
const core = require('./runtime/core');
const preload = require('./runtime/preload-i18n');

const zhBundle = {
  meta: { locale: 'zh-CN', punctuationStyle: 'cjk' },
  exact: { 'General': '常规', 'Extensions': '扩展', 'Review Policy': '审查策略', 'Sign in to Antigravity': '登录 Antigravity' },
  patterns: []
};
const enBundle = { meta: { locale: 'en-US', punctuationStyle: 'ascii' }, exact: {}, patterns: [] };

function makeTree(tag, attrs, textVal, scopedHit) {
  const el = {
    nodeType: 1,
    tagName: tag.toUpperCase(),
    _attrs: Object.assign({}, attrs || {}),
    _scopedHit: !!scopedHit,
    childNodes: [],
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this._attrs, k); },
    getAttribute(k) { return this._attrs[k]; },
    setAttribute(k, v) { this._attrs[k] = String(v); },
    closest(sel) {
      if (this._scopedHit && String(sel).indexOf('.antigravity-') !== -1) return this;
      return null;
    },
    querySelectorAll(sel) {
      const out = [];
      const walk = (node) => {
        for (const ch of (node.childNodes || [])) {
          if (ch.nodeType === 1) {
            if (ch._scopedHit && String(sel).indexOf('.antigravity-') !== -1) {
              out.push(ch);
            } else {
              walk(ch);
            }
          }
        }
      };
      walk(this);
      return out;
    }
  };
  if (textVal !== undefined) {
    el.childNodes.push({ nodeType: 3, nodeValue: textVal, parentElement: el });
  }
  return el;
}

const workbenchRoot = makeTree('div', { class: 'monaco-workbench' }, undefined, false);
const vscodeExplorerTitle = makeTree('span', { class: 'explorer-title' }, 'Extensions', false);
const vscodeSettingTitle = makeTree('span', { class: 'setting-title' }, 'General', false);
const agPanelText = makeTree('span', {}, 'Review Policy', true);
const agPortalText = makeTree('span', {}, 'Sign in to Antigravity', true);
workbenchRoot.childNodes.push(vscodeExplorerTitle, vscodeSettingTitle, agPanelText, agPortalText);

const fakeDoc = { documentElement: workbenchRoot };
const scopeOpts = { scopeSelectors: preload.IDE_ANTIGRAVITY_SCOPE_SELECTORS, translateTitle: false };
const domT = preload.createDomTranslator(zhBundle, core, scopeOpts);

domT.scanSubtree(workbenchRoot);
const afterZh = {
  vscodeExplorer: vscodeExplorerTitle.childNodes[0].nodeValue,
  vscodeSetting: vscodeSettingTitle.childNodes[0].nodeValue,
  agPanel: agPanelText.childNodes[0].nodeValue,
  agPortal: agPortalText.childNodes[0].nodeValue,
};

domT.updateBundle(enBundle, fakeDoc);
const afterEn = {
  vscodeExplorer: vscodeExplorerTitle.childNodes[0].nodeValue,
  vscodeSetting: vscodeSettingTitle.childNodes[0].nodeValue,
  agPanel: agPanelText.childNodes[0].nodeValue,
  agPortal: agPortalText.childNodes[0].nodeValue,
};

const origCfg = globalThis.__AG_I18N_PRELOAD_CONFIG__;
globalThis.__AG_I18N_PRELOAD_CONFIG__ = function (win) {
  const href = String((win && win.location && win.location.href) || '');
  if (/workbench-jetski-agent\.html/.test(href)) {
    return { enabled: true, ipcPrefix: 'vscode:ag-i18n:', scopeSelectors: null, translateTitle: true, injectSettingsCard: true, exposeGlobal: false };
  }
  return { enabled: true, ipcPrefix: 'vscode:ag-i18n:', scopeSelectors: 'ide-antigravity', translateTitle: false, injectSettingsCard: false, exposeGlobal: false };
};
const cfgJetski = preload.resolvePreloadConfig({ location: { href: 'vscode-file://vscode-app/out/vs/code/electron-browser/workbench/workbench-jetski-agent.html' } });
const cfgWb = preload.resolvePreloadConfig({ location: { href: 'vscode-file://vscode-app/out/vs/code/electron-browser/workbench/workbench.html' } });
globalThis.__AG_I18N_PRELOAD_CONFIG__ = origCfg;

console.log(JSON.stringify({
  afterZh,
  afterEn,
  allowVscodeFile: preload.isAntigravityUiLocation({ protocol: 'vscode-file:', hostname: 'vscode-app' }),
  cfgJetski,
  cfgWb
}));
"""
        res = _run_node(script)
        self.assertTrue(res["allowVscodeFile"])
        # VS Code workbench nodes MUST stay untouched in English
        self.assertEqual(res["afterZh"]["vscodeExplorer"], "Extensions")
        self.assertEqual(res["afterZh"]["vscodeSetting"], "General")
        # Antigravity nodes inside workbench MUST be translated
        self.assertEqual(res["afterZh"]["agPanel"], "审查策略")
        self.assertEqual(res["afterZh"]["agPortal"], "登录 Antigravity")
        # Switching back to en-US restores Antigravity nodes while leaving VS Code nodes untouched
        self.assertEqual(res["afterEn"]["vscodeExplorer"], "Extensions")
        self.assertEqual(res["afterEn"]["vscodeSetting"], "General")
        self.assertEqual(res["afterEn"]["agPanel"], "Review Policy")
        self.assertEqual(res["afterEn"]["agPortal"], "Sign in to Antigravity")
        # Config resolver assertions
        self.assertEqual(res["cfgJetski"]["ipcPrefix"], "vscode:ag-i18n:")
        self.assertIsNone(res["cfgJetski"]["scopeSelectors"])
        self.assertTrue(res["cfgJetski"]["injectSettingsCard"])
        self.assertEqual(res["cfgWb"]["scopeSelectors"], preload_list := res["cfgWb"]["scopeSelectors"])
        self.assertIsInstance(preload_list, list)
        self.assertFalse(res["cfgWb"]["translateTitle"])
        self.assertFalse(res["cfgWb"]["injectSettingsCard"])

    def test_ide_main_i18n_ipc_and_broadcast(self):
        with tempfile.TemporaryDirectory() as tmp:
            i18n_dir = Path(tmp) / "i18n"
            locales_sub = i18n_dir / "locales"
            locales_sub.mkdir(parents=True, exist_ok=True)
            for name in ("en-US.json", "zh-CN.json", "ja.json"):
                (locales_sub / name).write_text((LOCALES_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
            (i18n_dir / "config.json").write_text('{"locale":"zh-CN"}', encoding="utf-8")

            script = f"""
process.env.AG_I18N_NO_AUTO_INIT = '1';
const ideMain = require('./runtime/ide-main-i18n.cjs');
const core = require('./runtime/core');

const handlers = {{}};
const onHandlers = {{}};
const sentMessages = [];
const wc = {{
  isDestroyed: () => false,
  send: (ch, payload) => sentMessages.push({{ ch, locale: payload && payload.locale }})
}};
const mockElectron = {{
  app: {{ getLocale: () => 'zh-CN', getPath: () => {json.dumps(tmp)} }},
  ipcMain: {{
    on: (ch, fn) => {{ onHandlers[ch] = fn; }},
    handle: (ch, fn) => {{ handlers[ch] = fn; }}
  }},
  webContents: {{ getAllWebContents: () => [wc] }},
  BrowserWindow: {{ getAllWindows: () => [] }},
  shell: {{ openPath: async () => '' }}
}};

ideMain.init({{
  electron: mockElectron,
  core,
  userI18nDir: {json.dumps(str(i18n_dir))},
  bundledLocalesDir: {json.dumps(str(locales_sub))}
}});

const ev = {{}};
onHandlers['vscode:ag-i18n:get-state-sync'](ev);
const syncLocale = ev.returnValue && ev.returnValue.locale;

Promise.resolve(handlers['vscode:ag-i18n:set-locale']({{}}, 'ja')).then((res) => {{
  const fs = require('fs');
  const saved = JSON.parse(fs.readFileSync({json.dumps(str(i18n_dir / 'config.json'))}, 'utf8'));
  console.log(JSON.stringify({{
    syncLocale,
    handlerKeys: Object.keys(handlers).sort(),
    nextLocale: res.locale,
    savedLocale: saved.locale,
    broadcasts: sentMessages
  }}));
}});
"""
            res = _run_node(script)
            self.assertEqual(res["syncLocale"], "zh-CN")
            self.assertEqual(
                res["handlerKeys"],
                ["vscode:ag-i18n:list-locales", "vscode:ag-i18n:open-locales-folder", "vscode:ag-i18n:set-locale"],
            )
            self.assertEqual(res["nextLocale"], "ja")
            self.assertEqual(res["savedLocale"], "ja")
            self.assertTrue(any(m["ch"] == "vscode:ag-i18n:locale-changed" and m["locale"] == "ja" for m in res["broadcasts"]))


if __name__ == "__main__":
    unittest.main()
