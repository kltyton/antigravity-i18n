/*
 * antigravity-i18n — Renderer Preload DOM i18n Runtime
 * MIT License — Runs in BrowserWindow preload (works under contextIsolation & sandbox).
 * Preserves React original strings via WeakMaps for glitch-free live locale switching.
 */
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && typeof module.exports === 'object') {
    var coreMod = typeof require === 'function'
      ? (function () { try { return require('./core'); } catch (_e) { return null; } })()
      : null;
    var settingsMod = typeof require === 'function'
      ? (function () { try { return require('./settings-ui'); } catch (_e) { return null; } })()
      : null;
    module.exports = factory(
      coreMod || (root && root.AntigravityI18nCore),
      settingsMod || (root && root.AntigravityI18nSettingsUi)
    );
  }
  if (typeof globalThis !== 'undefined' && globalThis.window && globalThis.document) {
    // Auto-bootstrap when bundled inside dist/preload.js
    var preloadedCore = (globalThis.AntigravityI18nCore) || null;
    var preloadedSettings = (globalThis.AntigravityI18nSettingsUi) || null;
    if (preloadedCore && !globalThis.__AG_I18N_PRELOAD_STARTED__) {
      globalThis.__AG_I18N_PRELOAD_STARTED__ = true;
      var mod = factory(preloadedCore, preloadedSettings);
      mod.bootstrapBrowserPreload(globalThis);
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function (Core, SettingsUi) {
  'use strict';

  var ALLOWED_PROTOCOLS = { 'file:': 1, 'data:': 1, 'about:': 1, 'vscode-file:': 1, 'vscode-webview:': 1, 'chrome-extension:': 1 };
  var ALLOWED_HOSTS = { '127.0.0.1': 1, 'localhost': 1, '[::1]': 1 };
  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, CODE: 1, PRE: 1, KBD: 1, SAMP: 1, SVG: 1 };
  var SKIP_CLOSEST = 'pre, code, kbd, samp, .monaco-editor, .xterm, [contenteditable="true"], [data-ag-i18n-ignore], [data-testid^="model-selector"]';
  var TRANSLATABLE_ATTRS = ['title', 'placeholder', 'aria-label', 'alt', 'data-tooltip'];

  var IDE_ANTIGRAVITY_SCOPE_SELECTORS = [
    '[id="antigravity.agentPanel"]',
    '[id="antigravity.agentSidePanel"]',
    '[id="antigravity.agentSidePanelInputBox"]',
    '[id="antigravity.agentViewContainerId"]',
    '[id="antigravity.mcpConfigFileInfoWidget"]',
    '[id^="antigravity."]',
    '.antigravity-agent-side-panel',
    '.antigravity-agent-manager',
    '.antigravity-agent-mode',
    '.antigravity-configure-plugins-page',
    '.antigravity-plugin-page',
    '.antigravity-plugin-config-modal',
    '.antigravity-ide-welcome',
    '.antigravity-welcome-container',
    '.antigravity-onboarding-container',
    '.antigravity-onboarding-locked-panel',
    '.antigravity-onboarding',
    '.antigravity-modal-panel-overlay',
    '.antigravity-statusbar-settings-panel',
    '.antigravity-debug-info-widget',
    '.antigravity-editor-info-widget',
    '.antigravity-rules-file-info-widget',
    '.antigravity-tab-info-widget',
    '.antigravity-nudge',
    '.jetski-custom-editor-pane',
    '.jetski-full-screen-view',
    '.jetski-fast-pick',
    '.cascade-bar',
    '.agent-sessions-container',
    '.agent-sessions-viewer',
    '.auxiliarybar-drop-overlay',
    '[data-floating-ui-portal]',
    '.react-tooltip'
  ];

  function isAntigravityUiLocation(loc) {
    if (!loc || !loc.protocol) return true;
    if (ALLOWED_PROTOCOLS[loc.protocol]) return true;
    if (loc.hostname && ALLOWED_HOSTS[loc.hostname]) return true;
    return false;
  }

  function createDomTranslator(initialBundle, coreLib, options) {
    var activeCore = coreLib || Core;
    var translator = activeCore.createTranslator(initialBundle);
    var opts = options || {};
    var scopeSelectors = Array.isArray(opts.scopeSelectors) && opts.scopeSelectors.length > 0
      ? opts.scopeSelectors.slice()
      : null;
    var scopeSelectorString = scopeSelectors ? scopeSelectors.join(',') : '';
    var translateTitle = opts.translateTitle !== false;

    var textOriginals = new WeakMap();
    var textLastApplied = new WeakMap();
    var attrOriginals = new WeakMap();
    var attrLastApplied = new WeakMap();
    var inputValOriginals = new WeakMap();
    var inputValLastApplied = new WeakMap();

    var observedRoots = new WeakSet();
    var observedFrames = new WeakSet();
    var pendingNodes = new Set();
    var flushScheduled = false;

    function getHostElement(node) {
      if (!node) return null;
      if (node.nodeType === 1) return node;
      if (node.parentElement) return node.parentElement;
      if (node.parentNode && node.parentNode.nodeType === 1) return node.parentNode;
      // Handle ShadowRoot boundary
      if (typeof ShadowRoot !== 'undefined' && node instanceof ShadowRoot) return node.host || null;
      var root = typeof node.getRootNode === 'function' ? node.getRootNode() : null;
      if (root && root.host) return root.host;
      return null;
    }

    function isWithinScope(node) {
      if (!scopeSelectorString) return true;
      var cur = getHostElement(node);
      while (cur) {
        if (typeof cur.closest === 'function' && cur.closest(scopeSelectorString)) {
          return true;
        }
        var root = typeof cur.getRootNode === 'function' ? cur.getRootNode() : null;
        if (root && root.host) {
          cur = root.host;
        } else {
          break;
        }
      }
      return false;
    }

    function scanNodeWithScope(node) {
      if (!node) return;
      if (!scopeSelectorString) {
        scanSubtree(node);
        return;
      }
      if (isWithinScope(node)) {
        scanSubtree(node);
        return;
      }
      if (node.nodeType === 1 && typeof node.querySelectorAll === 'function') {
        var matched = node.querySelectorAll(scopeSelectorString);
        for (var i = 0; i < matched.length; i++) {
          scanSubtree(matched[i]);
        }
      } else if (node.nodeType === 9 && node.documentElement && typeof node.documentElement.querySelectorAll === 'function') {
        var docMatched = node.documentElement.querySelectorAll(scopeSelectorString);
        for (var j = 0; j < docMatched.length; j++) {
          scanSubtree(docMatched[j]);
        }
      }
    }
    var afterFlushListeners = [];

    function onAfterFlush(fn) {
      if (typeof fn === 'function') afterFlushListeners.push(fn);
    }

    function notifyAfterFlush() {
      for (var i = 0; i < afterFlushListeners.length; i++) {
        try {
          afterFlushListeners[i]();
        } catch (_err) {
          // Ignore listener failure
        }
      }
    }

    function isNodeProtected(node) {
      if (!node) return true;
      var el = node.nodeType === 1 ? node : node.parentElement;
      if (!el) return false;
      if (SKIP_TAGS[el.tagName]) return true;
      if (typeof el.closest === 'function' && el.closest(SKIP_CLOSEST)) return true;
      return false;
    }

    function translateTextNode(node) {
      if (isNodeProtected(node)) return;
      var cur = node.nodeValue;
      if (!cur || !cur.trim()) return;

      // Capture original or update original when framework renders brand new content
      if (!textOriginals.has(node) || textLastApplied.get(node) !== cur) {
        textOriginals.set(node, cur);
      }
      var orig = textOriginals.get(node);
      var target = translator.translate(orig, { context: 'ui' });

      if (cur !== target) {
        node.nodeValue = target;
      }
      textLastApplied.set(node, target);
    }

    function translateElementAttributes(el) {
      if (!el || el.nodeType !== 1 || isNodeProtected(el)) return;

      var origAttrs = attrOriginals.get(el);
      var lastAttrs = attrLastApplied.get(el);
      if (!origAttrs) {
        origAttrs = Object.create(null);
        lastAttrs = Object.create(null);
        attrOriginals.set(el, origAttrs);
        attrLastApplied.set(el, lastAttrs);
      }

      for (var i = 0; i < TRANSLATABLE_ATTRS.length; i++) {
        var attr = TRANSLATABLE_ATTRS[i];
        if (!el.hasAttribute || !el.hasAttribute(attr)) continue;
        var cur = el.getAttribute(attr);
        if (!cur) continue;
        if (!(attr in origAttrs) || lastAttrs[attr] !== cur) {
          origAttrs[attr] = cur;
        }
        var target = translator.translate(origAttrs[attr], { context: 'ui' });
        if (cur !== target) {
          el.setAttribute(attr, target);
        }
        lastAttrs[attr] = target;
      }

      if (el.tagName === 'INPUT' && (el.type === 'button' || el.type === 'submit' || el.type === 'reset') && el.value) {
        var curVal = el.value;
        if (!inputValOriginals.has(el) || inputValLastApplied.get(el) !== curVal) {
          inputValOriginals.set(el, curVal);
        }
        var origVal = inputValOriginals.get(el);
        var nextVal = translator.translate(origVal, { context: 'ui' });
        if (curVal !== nextVal) {
          el.value = nextVal;
        }
        inputValLastApplied.set(el, nextVal);
      }
    }

    function scanSubtree(root) {
      if (!root) return;
      if (root.nodeType === 3) {
        translateTextNode(root);
        return;
      }

      if (root.nodeType === 1) {
        if (SKIP_TAGS[root.tagName]) return;
        translateElementAttributes(root);
        if (root.shadowRoot) {
          var ownerWin = root.ownerDocument && root.ownerDocument.defaultView;
          if (!observedRoots.has(root.shadowRoot)) {
            observeRoot(root.shadowRoot, ownerWin);
          } else {
            scanSubtree(root.shadowRoot);
          }
        }
        if (root.tagName === 'IFRAME') {
          if (observedFrames.has(root)) {
            try {
              var iDoc = root.contentDocument;
              if (iDoc && iDoc.documentElement) scanSubtree(iDoc.documentElement);
            } catch (_e) {}
          } else {
            attachIframe(root);
          }
        }
      }

      var childNodes = root.childNodes;
      if (childNodes && childNodes.length) {
        for (var i = 0; i < childNodes.length; i++) {
          scanSubtree(childNodes[i]);
        }
      }
    }

    function scheduleFlush(win) {
      if (flushScheduled) return;
      flushScheduled = true;
      var raf = (win && typeof win.requestAnimationFrame === 'function')
        ? win.requestAnimationFrame.bind(win)
        : function (fn) { return setTimeout(fn, 16); };

      raf(function () {
        flushScheduled = false;
        if (pendingNodes.size > 0) {
          var batch = Array.from(pendingNodes);
          pendingNodes.clear();
          for (var i = 0; i < batch.length; i++) {
            scanNodeWithScope(batch[i]);
          }
        }
        notifyAfterFlush();
      });
    }

    function observeRoot(root, win) {
      if (!root || observedRoots.has(root)) return;
      observedRoots.add(root);
      scanNodeWithScope(root);

      var Observer = (win && win.MutationObserver) || (typeof MutationObserver !== 'undefined' ? MutationObserver : null);
      if (!Observer) return;

      var obs = new Observer(function (mutations) {
        for (var i = 0; i < mutations.length; i++) {
          var m = mutations[i];
          if (m.type === 'characterData') {
            if (!scopeSelectorString || isWithinScope(m.target)) {
              pendingNodes.add(m.target);
            }
          } else if (m.type === 'attributes') {
            if (!scopeSelectorString || isWithinScope(m.target)) {
              pendingNodes.add(m.target);
            }
          } else if (m.type === 'childList') {
            for (var j = 0; j < m.addedNodes.length; j++) {
              pendingNodes.add(m.addedNodes[j]);
            }
          }
        }
        if (pendingNodes.size > 0) {
          scheduleFlush(win);
        }
      });

      obs.observe(root, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
        attributeFilter: TRANSLATABLE_ATTRS
      });
    }

    function attachIframe(iframe) {
      if (!iframe || observedFrames.has(iframe)) return;
      observedFrames.add(iframe);
      var tryAttach = function () {
        try {
          var doc = iframe.contentDocument;
          var win = iframe.contentWindow;
          if (doc && doc.documentElement) {
            observeRoot(doc.documentElement, win);
          }
        } catch (_err) {
          // Cross-origin frame — safely ignore
        }
      };
      tryAttach();
      if (typeof iframe.addEventListener === 'function') {
        iframe.addEventListener('load', tryAttach);
      }
    }

    function updateBundle(nextBundle, doc, win) {
      translator = activeCore.createTranslator(nextBundle);
      if (doc && doc.documentElement) {
        if (translateTitle && doc.title) {
          if (!attrOriginals.has(doc.documentElement)) {
            attrOriginals.set(doc.documentElement, Object.create(null));
          }
        }
        scanNodeWithScope(doc.documentElement);
      }
    }

    return {
      translateTextNode: translateTextNode,
      translateElementAttributes: translateElementAttributes,
      scanSubtree: scanNodeWithScope,
      observeRoot: observeRoot,
      updateBundle: updateBundle,
      isWithinScope: isWithinScope,
      onAfterFlush: onAfterFlush,
      getOriginalText: function (node) { return textOriginals.get(node); },
      getTranslator: function () { return translator; }
    };
  }

  function resolvePreloadConfig(win, overrideOptions) {
    var base = {
      enabled: true,
      ipcPrefix: 'ag-i18n:',
      scopeSelectors: null,
      injectSettingsCard: true,
      translateTitle: true,
      exposeGlobal: true
    };
    var cfg = globalThis.__AG_I18N_PRELOAD_CONFIG__;
    if (typeof cfg === 'function') {
      try { cfg = cfg(win); } catch (_e) { cfg = null; }
    }
    var sources = [cfg, overrideOptions];
    for (var s = 0; s < sources.length; s++) {
      var src = sources[s];
      if (!src || typeof src !== 'object') continue;
      if (src.enabled !== undefined) base.enabled = !!src.enabled;
      if (typeof src.ipcPrefix === 'string' && src.ipcPrefix) base.ipcPrefix = src.ipcPrefix;
      if (src.scopeSelectors === 'ide-antigravity') {
        base.scopeSelectors = IDE_ANTIGRAVITY_SCOPE_SELECTORS.slice();
      } else if (Array.isArray(src.scopeSelectors) || src.scopeSelectors === null) {
        base.scopeSelectors = src.scopeSelectors;
      }
      if (src.injectSettingsCard !== undefined) base.injectSettingsCard = !!src.injectSettingsCard;
      if (src.translateTitle !== undefined) base.translateTitle = !!src.translateTitle;
      if (src.exposeGlobal !== undefined) base.exposeGlobal = !!src.exposeGlobal;
    }
    return base;
  }

  function bootstrapBrowserPreload(win, overrideOptions) {
    if (!win || !win.document) return null;
    if (!isAntigravityUiLocation(win.location)) return null;

    var cfg = resolvePreloadConfig(win, overrideOptions);
    if (!cfg.enabled) return null;

    var ipcPrefix = cfg.ipcPrefix;

    var electronMod = null;
    try {
      if (typeof require === 'function') electronMod = require('electron');
    } catch (_e) {
      electronMod = null;
    }

    var ipcRenderer = electronMod && electronMod.ipcRenderer;
    var contextBridge = electronMod && electronMod.contextBridge;

    var initialState = {
      locale: 'en-US',
      locales: [],
      bundle: { meta: { locale: 'en-US' }, exact: {}, patterns: [] }
    };

    if (ipcRenderer && typeof ipcRenderer.sendSync === 'function') {
      try {
        var syncState = ipcRenderer.sendSync(ipcPrefix + 'get-state-sync');
        if (syncState && typeof syncState === 'object') {
          initialState = syncState;
        }
      } catch (_err) {
        // Fallback cleanly if main IPC is not active
      }
    }

    var domTranslator = createDomTranslator(initialState.bundle, Core, {
      scopeSelectors: cfg.scopeSelectors,
      translateTitle: cfg.translateTitle
    });
    var settingsLib = SettingsUi || (win && win.AntigravityI18nSettingsUi) || null;
    var settingsCtrl = null;
    if (cfg.injectSettingsCard && settingsLib && typeof settingsLib.createSettingsController === 'function') {
      settingsCtrl = settingsLib.createSettingsController({
        document: win.document,
        getState: function () { return initialState; },
        getOriginalText: domTranslator.getOriginalText,
        onSelectLocale: function (nextLocale) {
          if (ipcRenderer && typeof ipcRenderer.invoke === 'function') {
            return ipcRenderer.invoke(ipcPrefix + 'set-locale', nextLocale).then(function (updated) {
              if (updated && typeof updated === 'object') {
                initialState = updated;
                if (updated.bundle) {
                  domTranslator.updateBundle(updated.bundle, win.document, win);
                }
                if (settingsCtrl) settingsCtrl.sync();
              }
              return updated;
            });
          }
          return Promise.resolve(initialState);
        },
        onOpenFolder: function () {
          if (ipcRenderer && typeof ipcRenderer.invoke === 'function') {
            return ipcRenderer.invoke(ipcPrefix + 'open-locales-folder');
          }
          return Promise.resolve('');
        }
      });
      domTranslator.onAfterFlush(function () {
        if (settingsCtrl) settingsCtrl.sync();
      });
    }

    if (cfg.exposeGlobal && contextBridge && typeof contextBridge.exposeInMainWorld === 'function' && ipcRenderer) {
      try {
        contextBridge.exposeInMainWorld('agI18n', {
          getLocale: function () { return initialState.locale; },
          listLocales: function () { return ipcRenderer.invoke(ipcPrefix + 'list-locales'); },
          setLocale: function (locale) { return ipcRenderer.invoke(ipcPrefix + 'set-locale', locale); },
          openLocalesFolder: function () { return ipcRenderer.invoke(ipcPrefix + 'open-locales-folder'); }
        });
      } catch (_err) {
        // Ignore if contextIsolation is disabled or already exposed
      }
    }

    if (win.Element && win.Element.prototype && win.Element.prototype.attachShadow && !win.Element.prototype.attachShadow.__agI18nPatched) {
      var origAttachShadow = win.Element.prototype.attachShadow;
      win.Element.prototype.attachShadow = function (init) {
        var shadow = origAttachShadow.call(this, init);
        if (shadow && (!init || init.mode === 'open')) {
          var hostEl = this;
          setTimeout(function () {
            if (!cfg.scopeSelectors || domTranslator.isWithinScope(hostEl)) {
              domTranslator.observeRoot(shadow, win);
            }
          }, 0);
        }
        return shadow;
      };
      win.Element.prototype.attachShadow.__agI18nPatched = true;
    }

    function startObserving() {
      var rootEl = win.document.documentElement || win.document.body;
      if (rootEl) {
        domTranslator.observeRoot(rootEl, win);
      }
      if (settingsCtrl) {
        settingsCtrl.sync();
      }
    }

    if (win.document.readyState === 'loading') {
      win.addEventListener('DOMContentLoaded', startObserving, { once: true });
    } else {
      startObserving();
    }

    if (ipcRenderer && typeof ipcRenderer.on === 'function') {
      ipcRenderer.on(ipcPrefix + 'locale-changed', function (_event, nextState) {
        if (!nextState || typeof nextState !== 'object') return;
        initialState = nextState;
        if (nextState.bundle) {
          domTranslator.updateBundle(nextState.bundle, win.document, win);
        }
        if (settingsCtrl) {
          settingsCtrl.sync();
        }
      });
    }

    return domTranslator;
  }

  return {
    IDE_ANTIGRAVITY_SCOPE_SELECTORS: IDE_ANTIGRAVITY_SCOPE_SELECTORS,
    isAntigravityUiLocation: isAntigravityUiLocation,
    createDomTranslator: createDomTranslator,
    resolvePreloadConfig: resolvePreloadConfig,
    bootstrapBrowserPreload: bootstrapBrowserPreload
  };
});
