/*
 * antigravity-i18n — Main Process Runtime for Antigravity IDE
 * MIT License — Registers scoped vscode:ag-i18n IPC channels and manages external locale bundles
 * without modifying or overriding VS Code's own workbench localization.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');

const CHANNEL_PREFIX = 'vscode:ag-i18n:';
const FALLBACK_LOCALE = 'en-US';
const INIT_FLAG = '__AG_I18N_IDE_MAIN_INITIALIZED__';

const EMPTY_BUNDLE = Object.freeze({
  meta: { locale: FALLBACK_LOCALE, name: 'English (US)', nativeName: 'English (US)' },
  exact: {},
  menu: {},
  patterns: [],
  units: {},
});

function resolveUserI18nDir() {
  if (process.platform === 'win32') {
    const appData = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
    return path.join(appData, 'antigravity', 'i18n');
  }
  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', 'antigravity', 'i18n');
  }
  const xdg = process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config');
  return path.join(xdg, 'antigravity', 'i18n');
}

function normalizeTag(raw) {
  if (!raw || typeof raw !== 'string') return '';
  return raw.trim().replace(/_/g, '-');
}

function resolveAvailableLocale(requested, availableTags, osLocale) {
  const tagMap = new Map();
  for (const tag of availableTags) {
    tagMap.set(tag.toLowerCase(), tag);
  }
  const tryMatch = (candidate) => {
    const norm = normalizeTag(candidate).toLowerCase();
    if (!norm || norm === 'auto') return null;
    if (tagMap.has(norm)) return tagMap.get(norm);
    if (norm === 'zh-hans' || norm === 'zh-sg' || norm === 'zh') {
      if (tagMap.has('zh-cn')) return tagMap.get('zh-cn');
    }
    if (norm === 'zh-hant' || norm === 'zh-hk' || norm === 'zh-mo') {
      if (tagMap.has('zh-tw')) return tagMap.get('zh-tw');
    }
    const base = norm.split('-')[0];
    if (tagMap.has(base)) return tagMap.get(base);
    for (const [lower, canon] of tagMap.entries()) {
      if (lower.split('-')[0] === base) return canon;
    }
    return null;
  };

  const explicit = tryMatch(requested);
  if (explicit) return explicit;
  const sys = tryMatch(osLocale);
  if (sys) return sys;
  return tagMap.get(FALLBACK_LOCALE.toLowerCase()) || availableTags[0] || FALLBACK_LOCALE;
}

function readJsonSafe(filePath) {
  try {
    const raw = fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, '');
    return JSON.parse(raw);
  } catch (_e) {
    return null;
  }
}

function createIdeI18nManager(options) {
  const opts = options || {};
  const bundledLocalesDir = opts.bundledLocalesDir || path.join(__dirname, 'locales');
  const userI18nDir = opts.userI18nDir || resolveUserI18nDir();
  const userLocalesDir = path.join(userI18nDir, 'locales');
  const configPath = path.join(userI18nDir, 'config.json');

  function ensureUserDirs() {
    try {
      fs.mkdirSync(userLocalesDir, { recursive: true });
    } catch (_e) {
      // Ignore permission errors in read-only environments
    }
  }

  function collectLocales() {
    const byLocale = new Map();
    for (const dir of [bundledLocalesDir, userLocalesDir]) {
      try {
        if (!fs.existsSync(dir)) continue;
        for (const entry of fs.readdirSync(dir)) {
          if (!entry.endsWith('.json') || entry.startsWith('_')) continue;
          const filePath = path.join(dir, entry);
          const data = readJsonSafe(filePath);
          if (!data || typeof data !== 'object') continue;
          const tag = (data.meta && data.meta.locale) || path.basename(entry, '.json');
          if (!tag || tag.startsWith('_')) continue;
          byLocale.set(tag, { tag, filePath, data });
        }
      } catch (_e) {
        // Skip unreadable directory
      }
    }
    return byLocale;
  }

  function readConfig() {
    const cfg = readJsonSafe(configPath);
    if (cfg && typeof cfg === 'object') {
      return cfg;
    }
    return { locale: 'auto', fallbackLocale: FALLBACK_LOCALE };
  }

  function writeConfig(nextLocale) {
    ensureUserDirs();
    const cur = readConfig();
    const next = Object.assign({}, cur, {
      locale: nextLocale,
      fallbackLocale: cur.fallbackLocale || FALLBACK_LOCALE,
    });
    try {
      fs.writeFileSync(configPath, JSON.stringify(next, null, 2) + '\n', 'utf8');
    } catch (_e) {
      // Best-effort write
    }
    return next;
  }

  function getOsLocale(electronApp) {
    try {
      if (electronApp && typeof electronApp.getLocale === 'function') {
        const l = electronApp.getLocale();
        if (l) return l;
      }
    } catch (_e) {}
    try {
      const intlLocale = Intl.DateTimeFormat().resolvedOptions().locale;
      if (intlLocale) return intlLocale;
    } catch (_e) {}
    return process.env.LANG || FALLBACK_LOCALE;
  }

  function getState(electronApp) {
    const cfg = readConfig();
    const localeMap = collectLocales();
    const availableTags = Array.from(localeMap.keys()).sort();
    const activeLocale = resolveAvailableLocale(cfg.locale, availableTags, getOsLocale(electronApp));
    const chosen = localeMap.get(activeLocale);
    const bundle = (chosen && chosen.data) || EMPTY_BUNDLE;
    const locales = availableTags.map((tag) => {
      const meta = (localeMap.get(tag) && localeMap.get(tag).data && localeMap.get(tag).data.meta) || {};
      return {
        locale: tag,
        name: meta.name || tag,
        nativeName: meta.nativeName || meta.name || tag,
      };
    });
    return {
      locale: activeLocale,
      config: cfg,
      locales,
      bundle,
      userI18nDir,
    };
  }

  return {
    getState,
    writeConfig,
    userI18nDir,
    userLocalesDir,
    configPath,
  };
}

function init(options) {
  if (globalThis[INIT_FLAG]) {
    return globalThis[INIT_FLAG];
  }

  let electron = null;
  try {
    electron = (options && options.electron) || require('electron');
  } catch (_e) {
    return null;
  }
  if (!electron || !electron.ipcMain) return null;

  const { app, ipcMain, webContents, BrowserWindow, shell } = electron;
  const manager = createIdeI18nManager(options);

  function broadcastState(state) {
    const targets = new Set();
    try {
      if (webContents && typeof webContents.getAllWebContents === 'function') {
        for (const wc of webContents.getAllWebContents()) {
          targets.add(wc);
        }
      }
    } catch (_e) {}
    try {
      if (BrowserWindow && typeof BrowserWindow.getAllWindows === 'function') {
        for (const win of BrowserWindow.getAllWindows()) {
          if (win && win.webContents) targets.add(win.webContents);
        }
      }
    } catch (_e) {}
    for (const wc of targets) {
      try {
        if (wc && !wc.isDestroyed()) {
          wc.send(CHANNEL_PREFIX + 'locale-changed', state);
        }
      } catch (_e) {}
    }
  }

  try {
    ipcMain.on(CHANNEL_PREFIX + 'get-state-sync', (event) => {
      try {
        event.returnValue = manager.getState(app);
      } catch (_e) {
        event.returnValue = { locale: FALLBACK_LOCALE, config: { locale: 'auto' }, locales: [], bundle: EMPTY_BUNDLE };
      }
    });
  } catch (_e) {}

  try {
    ipcMain.handle(CHANNEL_PREFIX + 'list-locales', () => manager.getState(app).locales);
  } catch (_e) {}

  try {
    ipcMain.handle(CHANNEL_PREFIX + 'set-locale', (_event, nextLocale) => {
      const target = typeof nextLocale === 'string' && nextLocale.trim() ? nextLocale.trim() : 'auto';
      manager.writeConfig(target);
      const state = manager.getState(app);
      broadcastState(state);
      return state;
    });
  } catch (_e) {}

  try {
    ipcMain.handle(CHANNEL_PREFIX + 'open-locales-folder', async () => {
      if (shell && typeof shell.openPath === 'function') {
        await shell.openPath(manager.userLocalesDir);
      }
      return manager.userLocalesDir;
    });
  } catch (_e) {}

  // Keep Antigravity IDE live-synced if config.json is updated externally (CLI, GUI, or Desktop).
  try {
    let debounceTimer = null;
    if (fs.existsSync(manager.userI18nDir)) {
      const watcher = fs.watch(manager.userI18nDir, (_eventType, filename) => {
        if (filename && filename !== 'config.json') return;
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          broadcastState(manager.getState(app));
        }, 120);
      });
      if (watcher && typeof watcher.unref === 'function') {
        watcher.unref();
      }
    }
  } catch (_e) {}

  const handle = { manager, broadcastState };
  globalThis[INIT_FLAG] = handle;
  return handle;
}

module.exports = {
  CHANNEL_PREFIX,
  createIdeI18nManager,
  init,
  resolveAvailableLocale,
  resolveUserI18nDir,
};
