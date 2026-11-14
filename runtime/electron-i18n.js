/*
 * antigravity-i18n — Electron Main Process i18n Runtime
 * MIT License — Loaded early from dist/main.js.
 * Loads external locale bundles from <userData>/i18n/ and translates native menus,
 * context menus, tray items, dialogs, notifications, window titles, and splash HTML.
 */
'use strict';

var fs = require('fs');
var path = require('path');
var core = require('./core');
var menuHelper = require('./menu-i18n');

var INIT_FLAG = Symbol.for('antigravity.i18n.main.initialized');
var HTML_TRANSLATE_TAG = 'data-ag-i18n-html';

function safeReadJson(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    var raw = fs.readFileSync(filePath, 'utf8');
    return JSON.parse(raw);
  } catch (_err) {
    return null;
  }
}

function safeWriteJson(filePath, data) {
  try {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    var tmp = filePath + '.tmp-' + process.pid;
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2) + '\n', 'utf8');
    fs.renameSync(tmp, filePath);
    return true;
  } catch (_err) {
    return false;
  }
}

function resolveI18nBaseDir(electron, explicitDir) {
  if (explicitDir) return explicitDir;
  if (process.env.AG_I18N_DIR) return process.env.AG_I18N_DIR;
  try {
    if (electron && electron.app && typeof electron.app.getPath === 'function') {
      return path.join(electron.app.getPath('userData'), 'i18n');
    }
  } catch (_err) {
    // Fallback below if called before app paths are ready
  }
  if (process.platform === 'win32') {
    return path.join(process.env.APPDATA || path.join(process.env.USERPROFILE || '', 'AppData', 'Roaming'), 'antigravity', 'i18n');
  }
  if (process.platform === 'darwin') {
    return path.join(process.env.HOME || '', 'Library', 'Application Support', 'antigravity', 'i18n');
  }
  return path.join(process.env.XDG_CONFIG_HOME || path.join(process.env.HOME || '', '.config'), 'antigravity', 'i18n');
}

function normalizeLocaleTag(tag) {
  if (!tag || typeof tag !== 'string') return '';
  return tag.trim().replace(/_/g, '-');
}

function detectSystemLocale(electron, availableLocales) {
  var candidates = [];
  try {
    if (electron && electron.app) {
      if (typeof electron.app.getPreferredSystemLanguages === 'function') {
        var sysLangs = electron.app.getPreferredSystemLanguages();
        if (Array.isArray(sysLangs)) {
          candidates = candidates.concat(sysLangs);
        }
      }
      if (typeof electron.app.getLocale === 'function') {
        candidates.push(electron.app.getLocale());
      }
    }
  } catch (_err) {
    // Ignore early getLocale errors
  }
  try {
    candidates.push(Intl.DateTimeFormat().resolvedOptions().locale);
  } catch (_err) {
    // Ignore
  }

  var byLower = Object.create(null);
  var byBase = Object.create(null);
  for (var i = 0; i < availableLocales.length; i++) {
    var code = availableLocales[i].locale;
    byLower[code.toLowerCase()] = code;
    var base = code.split('-')[0].toLowerCase();
    if (!(base in byBase)) byBase[base] = code;
  }

  for (var j = 0; j < candidates.length; j++) {
    var norm = normalizeLocaleTag(candidates[j]);
    if (!norm) continue;
    var lower = norm.toLowerCase();
    if (lower in byLower) return byLower[lower];

    // Special handling for Traditional Chinese regions
    if (lower.startsWith('zh-hant') || lower === 'zh-tw' || lower === 'zh-hk' || lower === 'zh-mo') {
      if ('zh-tw' in byLower) return byLower['zh-tw'];
    }
    if (lower.startsWith('zh')) {
      if ('zh-cn' in byLower) return byLower['zh-cn'];
    }

    var shortBase = lower.split('-')[0];
    if (shortBase in byBase) return byBase[shortBase];
  }

  return ('en-us' in byLower) ? byLower['en-us'] : (availableLocales[0] ? availableLocales[0].locale : 'en-US');
}

function decodeHtmlEntities(str) {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/gi, "'")
    .replace(/&nbsp;/g, '\u00a0');
}

function encodeHtmlEntities(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function translateInlineHtml(html, translator) {
  if (!html || typeof html !== 'string' || translator.isIdentity) return html;
  if (html.indexOf(HTML_TRANSLATE_TAG) !== -1) return html;

  // Tokenize HTML into tags/script/style blocks vs plain text segments
  var tokens = html.split(/(<script\b[^>]*>[\s\S]*?<\/script>|<style\b[^>]*>[\s\S]*?<\/style>|<[^>]+>)/gi);
  for (var i = 0; i < tokens.length; i++) {
    var tok = tokens[i];
    if (!tok || tok[0] === '<') continue;
    var decoded = decodeHtmlEntities(tok);
    var translated = translator.translate(decoded, { context: 'ui' });
    if (translated !== decoded) {
      tokens[i] = encodeHtmlEntities(translated);
    }
  }

  var out = tokens.join('');
  return out.replace(/<html\b/i, '<html ' + HTML_TRANSLATE_TAG + '="1"');
}

function translateDataUrlIfHtml(url, translator) {
  if (typeof url !== 'string' || translator.isIdentity) return url;
  var match = url.match(/^(data:text\/html[^,]*,)([\s\S]*)$/i);
  if (!match) return url;

  var prefix = match[1];
  var payload = match[2];
  var isBase64 = /;base64,/i.test(prefix);
  if (isBase64) return url; // Skip binary base64 documents safely

  var decoded;
  try {
    decoded = decodeURIComponent(payload);
  } catch (_err) {
    return url;
  }

  var translatedHtml = translateInlineHtml(decoded, translator);
  if (translatedHtml === decoded) return url;
  return prefix + encodeURIComponent(translatedHtml);
}

function initElectronI18n(options) {
  options = options || {};
  var electron = options.electron || require('electron');
  if (!electron) return null;

  if (!options.forceReinit && electron[INIT_FLAG]) {
    return electron[INIT_FLAG];
  }

  var baseDir = resolveI18nBaseDir(electron, options.baseDir);
  var localesDir = path.join(baseDir, 'locales');
  var configPath = path.join(baseDir, 'config.json');

  var state = {
    baseDir: baseDir,
    localesDir: localesDir,
    configPath: configPath,
    config: { locale: 'auto' },
    locales: [],
    locale: 'en-US',
    bundle: { meta: { locale: 'en-US', name: 'English', nativeName: 'English', punctuationStyle: 'ascii' }, exact: {}, menu: {}, patterns: [] },
    translator: null
  };

  function discoverLocales() {
    var found = [];
    try {
      if (fs.existsSync(localesDir)) {
        var entries = fs.readdirSync(localesDir);
        for (var i = 0; i < entries.length; i++) {
          var fname = entries[i];
          if (!fname.endsWith('.json') || fname.startsWith('_')) continue;
          var parsed = safeReadJson(path.join(localesDir, fname));
          if (!parsed || typeof parsed !== 'object') continue;
          var meta = parsed.meta && typeof parsed.meta === 'object' ? parsed.meta : {};
          var code = typeof meta.locale === 'string' && meta.locale ? meta.locale : fname.slice(0, -5);
          found.push({
            locale: code,
            name: meta.name || code,
            nativeName: meta.nativeName || meta.name || code,
            direction: meta.direction || 'ltr',
            punctuationStyle: meta.punctuationStyle || 'ascii',
            file: fname
          });
        }
      }
    } catch (_err) {
      // Ignore read errors gracefully
    }

    if (found.length === 0) {
      found.push({
        locale: 'en-US',
        name: 'English',
        nativeName: 'English',
        direction: 'ltr',
        punctuationStyle: 'ascii',
        file: 'en-US.json'
      });
    }

    found.sort(function (a, b) {
      if (a.locale === 'en-US') return -1;
      if (b.locale === 'en-US') return 1;
      return a.locale.localeCompare(b.locale);
    });
    return found;
  }

  function loadConfig() {
    var loaded = safeReadJson(configPath);
    if (loaded && typeof loaded === 'object' && typeof loaded.locale === 'string') {
      state.config = Object.assign({ locale: 'auto' }, loaded);
    } else {
      state.config = { locale: 'auto' };
      safeWriteJson(configPath, state.config);
    }
  }

  function loadBundleForLocale(targetLocale) {
    state.locales = discoverLocales();
    var resolved = targetLocale;
    if (!resolved || resolved === 'auto') {
      resolved = detectSystemLocale(electron, state.locales);
    } else {
      var match = state.locales.find(function (l) {
        return l.locale.toLowerCase() === resolved.toLowerCase();
      });
      resolved = match ? match.locale : detectSystemLocale(electron, state.locales);
    }

    var metaInfo = state.locales.find(function (l) { return l.locale === resolved; });
    var bundle = null;
    if (metaInfo && metaInfo.file) {
      bundle = safeReadJson(path.join(localesDir, metaInfo.file));
    }
    if (!bundle) {
      bundle = {
        meta: { locale: resolved, name: resolved, nativeName: resolved, punctuationStyle: 'ascii' },
        exact: {},
        menu: {},
        patterns: []
      };
    }

    state.locale = resolved;
    state.bundle = bundle;
    state.translator = core.createTranslator(bundle);
  }

  // Track live native objects so language switch updates everything immediately
  var trackedAppMenuSource = null;
  var trackedTrays = new Set();
  var trackedTraySourceMenu = new WeakMap();
  var trackedTrayOrigTip = new WeakMap();
  var trackedWindowOrigTitle = new WeakMap();

  var Menu = electron.Menu;
  var MenuItem = electron.MenuItem;
  var Tray = electron.Tray;
  var dialog = electron.dialog;
  var ipcMain = electron.ipcMain;
  var BrowserWindow = electron.BrowserWindow;
  var shell = electron.shell;
  var app = electron.app;

  var origBuildFromTemplate = Menu && typeof Menu.buildFromTemplate === 'function' ? Menu.buildFromTemplate.bind(Menu) : null;
  var origSetApplicationMenu = Menu && typeof Menu.setApplicationMenu === 'function' ? Menu.setApplicationMenu.bind(Menu) : null;
  var origMenuInsert = Menu && Menu.prototype && Menu.prototype.insert ? Menu.prototype.insert : null;
  var origMenuAppend = Menu && Menu.prototype && Menu.prototype.append ? Menu.prototype.append : null;
  var origMenuPopup = Menu && Menu.prototype && Menu.prototype.popup ? Menu.prototype.popup : null;
  var origTraySetContextMenu = Tray && Tray.prototype && Tray.prototype.setContextMenu ? Tray.prototype.setContextMenu : null;
  var origTraySetToolTip = Tray && Tray.prototype && Tray.prototype.setToolTip ? Tray.prototype.setToolTip : null;

  var labelDesc = MenuItem && MenuItem.prototype
    ? Object.getOwnPropertyDescriptor(MenuItem.prototype, 'label')
    : null;

  function wrapMenuItemLabelAccessor(item) {
    if (!item || typeof item !== 'object' || item._agI18nAccessorWrapped) return;
    if (item.id === menuHelper.LANGUAGE_MENU_ID) return;
    menuHelper.preserveMenuItemOriginal(item);

    if (labelDesc && typeof labelDesc.get === 'function' && typeof labelDesc.set === 'function') {
      try {
        Object.defineProperty(item, 'label', {
          configurable: true,
          enumerable: true,
          get: function () {
            return labelDesc.get.call(this);
          },
          set: function (nextVal) {
            if (typeof nextVal === 'string') {
              this._agI18nOrigLabel = nextVal;
              var translated = state.translator.translate(nextVal, { context: 'menu' });
              this._agI18nLastTranslated = translated;
              labelDesc.set.call(this, translated);
              return;
            }
            labelDesc.set.call(this, nextVal);
          }
        });
        item._agI18nAccessorWrapped = true;
      } catch (_err) {
        // Ignore if native object disallows defineProperty
      }
    }

    if (item.submenu && Array.isArray(item.submenu.items)) {
      for (var i = 0; i < item.submenu.items.length; i++) {
        wrapMenuItemLabelAccessor(item.submenu.items[i]);
      }
    }
  }

  function wrapMenuItems(menu) {
    if (!menu || !Array.isArray(menu.items)) return;
    for (var i = 0; i < menu.items.length; i++) {
      wrapMenuItemLabelAccessor(menu.items[i]);
    }
  }

  function serializeMenuItemsToTemplate(menu) {
    if (!menu || !Array.isArray(menu.items)) return [];
    var out = [];
    for (var i = 0; i < menu.items.length; i++) {
      var it = menu.items[i];
      if (!it || it.id === menuHelper.LANGUAGE_MENU_ID) continue;
      menuHelper.preserveMenuItemOriginal(it);
      var entry = {
        type: it.type || 'normal'
      };
      if (it.id) entry.id = it.id;
      if (it._agI18nOrigLabel !== undefined) entry.label = it._agI18nOrigLabel;
      else if (it.label !== undefined) entry.label = it.label;
      if (it._agI18nOrigSublabel !== undefined) entry.sublabel = it._agI18nOrigSublabel;
      if (it._agI18nOrigToolTip !== undefined) entry.toolTip = it._agI18nOrigToolTip;
      if (it.role) entry.role = it.role;
      if (it.accelerator) entry.accelerator = it.accelerator;
      if (typeof it.registerAccelerator === 'boolean') entry.registerAccelerator = it.registerAccelerator;
      if (typeof it.enabled === 'boolean') entry.enabled = it.enabled;
      if (typeof it.visible === 'boolean') entry.visible = it.visible;
      if (it.type === 'checkbox' || it.type === 'radio') entry.checked = Boolean(it.checked);
      if (typeof it.click === 'function') entry.click = it.click;
      if (it.submenu && Array.isArray(it.submenu.items)) {
        entry.submenu = serializeMenuItemsToTemplate(it.submenu);
      }
      out.push(entry);
    }
    return out;
  }

  function getMenuCallbacksState() {
    return {
      locale: state.locale,
      config: state.config,
      locales: state.locales,
      onSelectLocale: function (nextLocale) {
        setLocale(nextLocale);
      },
      onOpenLocalesFolder: function () {
        if (shell && typeof shell.openPath === 'function') {
          fs.mkdirSync(state.localesDir, { recursive: true });
          void shell.openPath(state.localesDir);
        }
      }
    };
  }

  function buildDisplayMenuFromSource(sourceMenu, includeLangSubmenu, isTray) {
    if (!origBuildFromTemplate) return sourceMenu;
    var tpl = serializeMenuItemsToTemplate(sourceMenu);
    if (includeLangSubmenu) {
      tpl = menuHelper.appendOrReplaceLanguageInTemplate(tpl, getMenuCallbacksState(), isTray);
    }
    var translated = menuHelper.translateMenuTemplateArray(tpl, state.translator);
    var built = origBuildFromTemplate(translated);
    wrapMenuItems(built);
    return built;
  }

  function refreshNativeMenus() {
    var liveAppMenu = (Menu && typeof Menu.getApplicationMenu === 'function' ? Menu.getApplicationMenu() : null) || trackedAppMenuSource;
    if (liveAppMenu && origSetApplicationMenu && Menu) {
      try {
        var rebuiltApp = buildDisplayMenuFromSource(liveAppMenu, true, false);
        trackedAppMenuSource = rebuiltApp;
        origSetApplicationMenu(rebuiltApp);
      } catch (_err) {
        // Ignore transient rebuild error
      }
    }
    if (origTraySetContextMenu) {
      trackedTrays.forEach(function (tray) {
        try {
          if (tray.isDestroyed && tray.isDestroyed()) {
            trackedTrays.delete(tray);
            return;
          }
          var srcTrayMenu = trackedTraySourceMenu.get(tray);
          if (srcTrayMenu) {
            var rebuiltTray = buildDisplayMenuFromSource(srcTrayMenu, true, true);
            origTraySetContextMenu.call(tray, rebuiltTray);
          }
          if (origTraySetToolTip && trackedTrayOrigTip.has(tray)) {
            var origTip = trackedTrayOrigTip.get(tray);
            origTraySetToolTip.call(tray, state.translator.translate(origTip, { context: 'menu' }));
          }
        } catch (_err) {
          // Ignore tray refresh error
        }
      });
    }
  }

  function refreshBrowserWindows() {
    if (!BrowserWindow || typeof BrowserWindow.getAllWindows !== 'function') return;
    var wins = BrowserWindow.getAllWindows();
    var payload = getSerializableState();
    for (var i = 0; i < wins.length; i++) {
      var win = wins[i];
      if (!win || (win.isDestroyed && win.isDestroyed())) continue;
      if (trackedWindowOrigTitle.has(win) && typeof win.setTitle === 'function') {
        try {
          win.setTitle(trackedWindowOrigTitle.get(win));
        } catch (_err) {
          // Ignore title update errors
        }
      }
      try {
        var wc = win.webContents;
        if (wc && !wc.isDestroyed() && typeof wc.send === 'function') {
          wc.send('ag-i18n:locale-changed', payload);
        }
      } catch (_err) {
        // Ignore closed webContents
      }
    }
    // Also notify any extra WebContents (e.g. WebContentsView in BaseWindow!)
    if (electron.webContents && typeof electron.webContents.getAllWebContents === 'function') {
      var allWc = electron.webContents.getAllWebContents();
      for (var j = 0; j < allWc.length; j++) {
        var cur = allWc[j];
        if (!cur || (cur.isDestroyed && cur.isDestroyed())) continue;
        try {
          if (typeof cur.send === 'function') {
            cur.send('ag-i18n:locale-changed', payload);
          }
        } catch (_err) {
          // Ignore
        }
      }
    }
  }

  function getSerializableState() {
    return {
      locale: state.locale,
      config: state.config,
      locales: state.locales,
      bundle: state.bundle
    };
  }

  function setLocale(nextLocale) {
    if (!nextLocale || typeof nextLocale !== 'string') {
      return getSerializableState();
    }
    state.config = Object.assign({}, state.config, { locale: nextLocale });
    safeWriteJson(state.configPath, state.config);
    loadBundleForLocale(nextLocale);
    refreshNativeMenus();
    refreshBrowserWindows();
    return getSerializableState();
  }

  function translateDialogOptions(opts) {
    if (!opts || typeof opts !== 'object') return opts;
    var cloned = Object.assign({}, opts);
    var fields = ['title', 'message', 'detail', 'checkboxLabel', 'buttonLabel'];
    for (var i = 0; i < fields.length; i++) {
      var key = fields[i];
      if (typeof cloned[key] === 'string' && cloned[key]) {
        cloned[key] = state.translator.translate(cloned[key], { context: 'menu' });
      }
    }
    if (Array.isArray(cloned.buttons)) {
      cloned.buttons = cloned.buttons.map(function (b) {
        return typeof b === 'string' ? state.translator.translate(b, { context: 'menu' }) : b;
      });
    }
    if (Array.isArray(cloned.filters)) {
      cloned.filters = cloned.filters.map(function (f) {
        if (!f || typeof f !== 'object') return f;
        var cf = Object.assign({}, f);
        if (typeof cf.name === 'string') {
          cf.name = state.translator.translate(cf.name, { context: 'menu' });
        }
        return cf;
      });
    }
    return cloned;
  }

  function installHooks() {
    if (Menu && origBuildFromTemplate) {
      Menu.buildFromTemplate = function (template) {
        var translated = menuHelper.translateMenuTemplateArray(template, state.translator);
        var built = origBuildFromTemplate(translated);
        wrapMenuItems(built);
        return built;
      };
    }

    if (Menu && origSetApplicationMenu) {
      Menu.setApplicationMenu = function (menu) {
        if (!menu) {
          trackedAppMenuSource = null;
          return origSetApplicationMenu(menu);
        }
        trackedAppMenuSource = menu;
        menuHelper.translateMenuInstanceLive(menu, state.translator);
        wrapMenuItems(menu);
        var rebuilt = buildDisplayMenuFromSource(menu, true, false);
        return origSetApplicationMenu(rebuilt);
      };
    }

    if (Menu && origMenuInsert) {
      Menu.prototype.insert = function (pos, menuItem) {
        if (menuItem && typeof menuItem === 'object') {
          menuHelper.translateMenuItemLive(menuItem, state.translator);
          wrapMenuItemLabelAccessor(menuItem);
        }
        return origMenuInsert.call(this, pos, menuItem);
      };
    }

    if (Menu && origMenuAppend) {
      Menu.prototype.append = function (menuItem) {
        if (menuItem && typeof menuItem === 'object') {
          menuHelper.translateMenuItemLive(menuItem, state.translator);
          wrapMenuItemLabelAccessor(menuItem);
        }
        return origMenuAppend.call(this, menuItem);
      };
    }

    if (Menu && origMenuPopup) {
      Menu.prototype.popup = function (popupOpts) {
        menuHelper.translateMenuInstanceLive(this, state.translator);
        return origMenuPopup.call(this, popupOpts);
      };
    }

    if (Tray && origTraySetContextMenu) {
      Tray.prototype.setContextMenu = function (menu) {
        trackedTrays.add(this);
        if (menu) {
          trackedTraySourceMenu.set(this, menu);
          menuHelper.translateMenuInstanceLive(menu, state.translator);
          wrapMenuItems(menu);
          var displayTrayMenu = buildDisplayMenuFromSource(menu, true, true);
          return origTraySetContextMenu.call(this, displayTrayMenu);
        }
        return origTraySetContextMenu.call(this, menu);
      };
    }

    if (Tray && origTraySetToolTip) {
      Tray.prototype.setToolTip = function (toolTip) {
        trackedTrays.add(this);
        if (typeof toolTip === 'string') {
          trackedTrayOrigTip.set(this, toolTip);
          return origTraySetToolTip.call(this, state.translator.translate(toolTip, { context: 'menu' }));
        }
        return origTraySetToolTip.call(this, toolTip);
      };
    }

    if (dialog) {
      var dialogMethods = [
        'showMessageBox',
        'showMessageBoxSync',
        'showOpenDialog',
        'showOpenDialogSync',
        'showSaveDialog',
        'showSaveDialogSync'
      ];
      dialogMethods.forEach(function (methodName) {
        var origFn = dialog[methodName];
        if (typeof origFn !== 'function') return;
        dialog[methodName] = function () {
          var args = Array.prototype.slice.call(arguments);
          if (args.length === 1 && args[0] && typeof args[0] === 'object') {
            args[0] = translateDialogOptions(args[0]);
          } else if (args.length >= 2 && args[1] && typeof args[1] === 'object') {
            args[1] = translateDialogOptions(args[1]);
          }
          return origFn.apply(this, args);
        };
      });
    }

    if (electron.Notification) {
      var OrigNotification = electron.Notification;
      var WrappedNotification = function (opts) {
        var nextOpts = opts;
        if (opts && typeof opts === 'object') {
          nextOpts = Object.assign({}, opts);
          if (typeof nextOpts.title === 'string') {
            nextOpts.title = state.translator.translate(nextOpts.title, { context: 'menu' });
          }
          if (typeof nextOpts.subtitle === 'string') {
            nextOpts.subtitle = state.translator.translate(nextOpts.subtitle, { context: 'menu' });
          }
          if (typeof nextOpts.body === 'string') {
            nextOpts.body = state.translator.translate(nextOpts.body, { context: 'menu' });
          }
        }
        return new OrigNotification(nextOpts);
      };
      WrappedNotification.prototype = OrigNotification.prototype;
      if (typeof OrigNotification.isSupported === 'function') {
        WrappedNotification.isSupported = OrigNotification.isSupported.bind(OrigNotification);
      }
      electron.Notification = WrappedNotification;
    }

    if (BrowserWindow && BrowserWindow.prototype && typeof BrowserWindow.prototype.setTitle === 'function') {
      var origSetTitle = BrowserWindow.prototype.setTitle;
      BrowserWindow.prototype.setTitle = function (title) {
        if (typeof title === 'string') {
          trackedWindowOrigTitle.set(this, title);
          return origSetTitle.call(this, state.translator.translate(title, { context: 'menu' }));
        }
        return origSetTitle.call(this, title);
      };
    }

    if (app && typeof app.on === 'function') {
      app.on('web-contents-created', function (_event, contents) {
        if (!contents || typeof contents.loadURL !== 'function') return;
        var origLoadUrl = contents.loadURL.bind(contents);
        contents.loadURL = function (url, loadOpts) {
          var nextUrl = translateDataUrlIfHtml(url, state.translator);
          return origLoadUrl(nextUrl, loadOpts);
        };
      });
    }

    if (ipcMain && typeof ipcMain.on === 'function') {
      ipcMain.on('ag-i18n:get-state-sync', function (event) {
        event.returnValue = getSerializableState();
      });
    }
    if (ipcMain && typeof ipcMain.handle === 'function') {
      ipcMain.handle('ag-i18n:list-locales', function () {
        state.locales = discoverLocales();
        return { locale: state.locale, config: state.config, locales: state.locales };
      });
      ipcMain.handle('ag-i18n:set-locale', function (_event, nextLocale) {
        return setLocale(nextLocale);
      });
      ipcMain.handle('ag-i18n:open-locales-folder', function () {
        if (shell && typeof shell.openPath === 'function') {
          fs.mkdirSync(state.localesDir, { recursive: true });
          return shell.openPath(state.localesDir);
        }
        return '';
      });
    }
  }

  loadConfig();
  loadBundleForLocale(state.config.locale || 'auto');
  installHooks();

  var instance = {
    getState: getSerializableState,
    setLocale: setLocale,
    reload: function () {
      loadConfig();
      loadBundleForLocale(state.config.locale || 'auto');
      refreshNativeMenus();
      refreshBrowserWindows();
      return getSerializableState();
    },
    translate: function (text, opts) {
      return state.translator.translate(text, opts);
    }
  };

  electron[INIT_FLAG] = instance;
  return instance;
}

if (!process.env.AG_I18N_NO_AUTO_INIT) {
  try {
    initElectronI18n();
  } catch (err) {
    if (typeof console !== 'undefined' && console.warn) {
      console.warn('[antigravity-i18n] Main init error:', err && err.message ? err.message : err);
    }
  }
}

module.exports = {
  initElectronI18n: initElectronI18n,
  translateInlineHtml: translateInlineHtml,
  translateDataUrlIfHtml: translateDataUrlIfHtml
};
