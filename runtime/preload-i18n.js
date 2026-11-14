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
    module.exports = factory(coreMod || (root && root.AntigravityI18nCore));
  }
  if (typeof globalThis !== 'undefined' && globalThis.window && globalThis.document) {
    // Auto-bootstrap when bundled inside dist/preload.js
    var preloadedCore = (globalThis.AntigravityI18nCore) || null;
    if (preloadedCore && !globalThis.__AG_I18N_PRELOAD_STARTED__) {
      globalThis.__AG_I18N_PRELOAD_STARTED__ = true;
      var mod = factory(preloadedCore);
      mod.bootstrapBrowserPreload(globalThis);
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function (Core) {
  'use strict';

  var ALLOWED_PROTOCOLS = { 'file:': 1, 'data:': 1, 'about:': 1, 'vscode-webview:': 1, 'chrome-extension:': 1 };
  var ALLOWED_HOSTS = { '127.0.0.1': 1, 'localhost': 1, '[::1]': 1 };
  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, CODE: 1, PRE: 1, KBD: 1, SAMP: 1, SVG: 1 };
  var SKIP_CLOSEST = 'pre, code, kbd, samp, .monaco-editor, .xterm, [contenteditable="true"], [data-ag-i18n-ignore], [data-testid^="model-selector"]';
  var TRANSLATABLE_ATTRS = ['title', 'placeholder', 'aria-label', 'alt', 'data-tooltip'];

  function isAntigravityUiLocation(loc) {
    if (!loc || !loc.protocol) return true;
    if (ALLOWED_PROTOCOLS[loc.protocol]) return true;
    if (loc.hostname && ALLOWED_HOSTS[loc.hostname]) return true;
    return false;
  }

  function createDomTranslator(initialBundle, coreLib) {
    var activeCore = coreLib || Core;
    var translator = activeCore.createTranslator(initialBundle);

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
        if (pendingNodes.size === 0) return;
        var batch = Array.from(pendingNodes);
        pendingNodes.clear();
        for (var i = 0; i < batch.length; i++) {
          scanSubtree(batch[i]);
        }
      });
    }

    function observeRoot(root, win) {
      if (!root || observedRoots.has(root)) return;
      observedRoots.add(root);
      scanSubtree(root);

      var Observer = (win && win.MutationObserver) || (typeof MutationObserver !== 'undefined' ? MutationObserver : null);
      if (!Observer) return;

      var obs = new Observer(function (mutations) {
        for (var i = 0; i < mutations.length; i++) {
          var m = mutations[i];
          if (m.type === 'characterData') {
            pendingNodes.add(m.target);
          } else if (m.type === 'attributes') {
            pendingNodes.add(m.target);
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
        if (doc.title) {
          if (!attrOriginals.has(doc.documentElement)) {
            attrOriginals.set(doc.documentElement, Object.create(null));
          }
        }
        scanSubtree(doc.documentElement);
      }
    }

    return {
      translateTextNode: translateTextNode,
      translateElementAttributes: translateElementAttributes,
      scanSubtree: scanSubtree,
      observeRoot: observeRoot,
      updateBundle: updateBundle,
      getTranslator: function () { return translator; }
    };
  }

  function bootstrapBrowserPreload(win) {
    if (!win || !win.document) return null;
    if (!isAntigravityUiLocation(win.location)) return null;

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
        var syncState = ipcRenderer.sendSync('ag-i18n:get-state-sync');
        if (syncState && typeof syncState === 'object') {
          initialState = syncState;
        }
      } catch (_err) {
        // Fallback cleanly if main IPC is not active
      }
    }

    var domTranslator = createDomTranslator(initialState.bundle, Core);

    if (contextBridge && typeof contextBridge.exposeInMainWorld === 'function' && ipcRenderer) {
      try {
        contextBridge.exposeInMainWorld('agI18n', {
          getLocale: function () { return initialState.locale; },
          listLocales: function () { return ipcRenderer.invoke('ag-i18n:list-locales'); },
          setLocale: function (locale) { return ipcRenderer.invoke('ag-i18n:set-locale', locale); },
          openLocalesFolder: function () { return ipcRenderer.invoke('ag-i18n:open-locales-folder'); }
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
          setTimeout(function () { domTranslator.observeRoot(shadow, win); }, 0);
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
    }

    if (win.document.readyState === 'loading') {
      win.addEventListener('DOMContentLoaded', startObserving, { once: true });
    } else {
      startObserving();
    }

    if (ipcRenderer && typeof ipcRenderer.on === 'function') {
      ipcRenderer.on('ag-i18n:locale-changed', function (_event, nextState) {
        if (!nextState || typeof nextState !== 'object') return;
        initialState = nextState;
        if (nextState.bundle) {
          domTranslator.updateBundle(nextState.bundle, win.document, win);
        }
      });
    }

    return domTranslator;
  }

  return {
    isAntigravityUiLocation: isAntigravityUiLocation,
    createDomTranslator: createDomTranslator,
    bootstrapBrowserPreload: bootstrapBrowserPreload
  };
});
