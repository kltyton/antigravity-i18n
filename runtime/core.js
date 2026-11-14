/*
 * antigravity-i18n — Pure JavaScript Runtime Core Engine
 * MIT License — Universal i18n matcher shared by main process, preload, and browser.
 */
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && typeof module.exports === 'object') {
    module.exports = factory();
  }
  if (root) {
    root.AntigravityI18nCore = factory();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var MAX_CACHE_ENTRIES = 4096;
  var URL_RE = /^(?:https?:|mailto:|file:|data:|vscode-webview:|about:)\S+$/i;
  var WIN_PATH_RE = /^[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\?)*$/;
  var POSIX_PATH_RE = /^\/(?:Users|home|usr|opt|etc|var|tmp|Applications|Library)\//;
  var PURE_NUM_RE = /^[\d.,:%+\-*/()\[\]\s]+$/;
  var VERSION_RE = /^v?\d+\.\d+(?:\.\d+)*(?:-[\w.]+)?$/i;
  var ACCEL_KEY_RE = /&([A-Za-z0-9])/;
  var TRAILING_SHORTCUT_RE = /^(.+?)\s+((?:Ctrl|Cmd|Alt|Shift|Meta|Opt)(?:\+(?:Ctrl|Cmd|Alt|Shift|Meta|Opt|[A-Za-z0-9,=.\-/\\`[\]';]|Up|Down|Left|Right|Enter|Tab|Esc|Space|Backspace|Delete|PageUp|PageDown|Home|End|F\d{1,2}))+)$/;
  var ELLIPSIS_CHAR = '\u2026';

  function isPlainObject(val) {
    return val !== null && typeof val === 'object' && !Array.isArray(val);
  }

  function hasLetters(str) {
    return /[A-Za-z]/.test(str);
  }

  function shouldSkipRaw(trimmed) {
    if (!trimmed || trimmed.length > 1500) return true;
    if (!hasLetters(trimmed)) return true;
    if (URL_RE.test(trimmed)) return true;
    if (WIN_PATH_RE.test(trimmed) || POSIX_PATH_RE.test(trimmed)) return true;
    if (PURE_NUM_RE.test(trimmed) || VERSION_RE.test(trimmed)) return true;
    return false;
  }

  function normalizePunctStyle(style) {
    return style === 'cjk' ? 'cjk' : 'ascii';
  }

  function mapTrailingPunct(punct, style) {
    if (punct === '...' || punct === ELLIPSIS_CHAR) {
      return style === 'cjk' ? '\u2026' : punct;
    }
    if (style === 'cjk') {
      if (punct === ':') return '\uFF1A';
      if (punct === '?') return '\uFF1F';
      if (punct === '!') return '\uFF01';
    }
    return punct;
  }

  function compilePatterns(rawPatterns) {
    var out = [];
    if (!Array.isArray(rawPatterns)) return out;
    for (var i = 0; i < rawPatterns.length; i++) {
      var entry = rawPatterns[i];
      if (!Array.isArray(entry) || entry.length < 2) continue;
      var src = String(entry[0] || '');
      var flags = '';
      var repl = '';
      if (entry.length === 2) {
        repl = String(entry[1] == null ? '' : entry[1]);
      } else {
        flags = String(entry[1] || '');
        repl = String(entry[2] == null ? '' : entry[2]);
      }
      if (!src) continue;
      try {
        // Avoid global sticky state across calls by disallowing 'g'/'y'
        var safeFlags = flags.replace(/[gy]/g, '');
        out.push({ re: new RegExp(src, safeFlags), repl: repl });
      } catch (_err) {
        // Skip invalid user regex without breaking the app
      }
    }
    return out;
  }

  function buildMaps(bundle) {
    var exactMap = Object.create(null);
    var lowerMap = Object.create(null);
    var menuMap = Object.create(null);
    var menuLowerMap = Object.create(null);

    function ingest(source, targetExact, targetLower) {
      if (!isPlainObject(source)) return;
      var keys = Object.keys(source);
      for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        var v = source[k];
        if (typeof v !== 'string' || !v) continue;
        targetExact[k] = v;
        if (k.length >= 4 || k.indexOf(' ') !== -1) {
          var lk = k.toLowerCase();
          if (!(lk in targetLower)) {
            targetLower[lk] = v;
          }
        }
      }
    }

    if (isPlainObject(bundle)) {
      ingest(bundle.exact, exactMap, lowerMap);
      ingest(bundle.menu, menuMap, menuLowerMap);
    }

    return {
      exactMap: exactMap,
      lowerMap: lowerMap,
      menuMap: menuMap,
      menuLowerMap: menuLowerMap
    };
  }

  function createTranslator(bundle) {
    var safeBundle = isPlainObject(bundle) ? bundle : {};
    var meta = isPlainObject(safeBundle.meta) ? safeBundle.meta : {};
    var locale = typeof meta.locale === 'string' && meta.locale ? meta.locale : 'en-US';
    var punctStyle = normalizePunctStyle(meta.punctuationStyle);
    var maps = buildMaps(safeBundle);
    var compiledPatterns = compilePatterns(safeBundle.patterns);
    var unitMap = isPlainObject(safeBundle.units) ? safeBundle.units : null;
    var identityMode =
      Object.keys(maps.exactMap).length === 0 &&
      Object.keys(maps.menuMap).length === 0 &&
      compiledPatterns.length === 0;

    var uiCache = new Map();
    var menuCache = new Map();

    function cacheSet(cache, key, val) {
      if (cache.size >= MAX_CACHE_ENTRIES) {
        var firstKey = cache.keys().next().value;
        if (firstKey !== undefined) cache.delete(firstKey);
      }
      cache.set(key, val);
    }

    function directLookup(str, isMenu) {
      if (isMenu) {
        if (Object.prototype.hasOwnProperty.call(maps.menuMap, str)) {
          return maps.menuMap[str];
        }
      }
      if (Object.prototype.hasOwnProperty.call(maps.exactMap, str)) {
        return maps.exactMap[str];
      }
      if (str.length >= 4 || str.indexOf(' ') !== -1) {
        var lower = str.toLowerCase();
        if (isMenu && Object.prototype.hasOwnProperty.call(maps.menuLowerMap, lower)) {
          return maps.menuLowerMap[lower];
        }
        if (Object.prototype.hasOwnProperty.call(maps.lowerMap, lower)) {
          return maps.lowerMap[lower];
        }
      }
      return null;
    }

    function localizeDurationCapture(cap) {
      if (!unitMap || typeof cap !== 'string') return cap;
      if (!/(?:^|[\s,])\d+(?:\.\d+)?\s*(?:days?|hours?|hrs?|minutes?|mins?|seconds?|secs?|ms|[dhms])\b/i.test(cap)) {
        return cap;
      }
      var replaced = cap.replace(/(^|[\s,])(\d+(?:\.\d+)?)\s*(days?|hours?|hrs?|minutes?|mins?|seconds?|secs?|ms|[dhms])\b/gi, function (whole, prefix, num, unit) {
        var mapped = unitMap[unit.toLowerCase()];
        if (!mapped) return whole;
        return prefix + num + ' ' + mapped;
      });
      if (punctStyle === 'cjk') {
        replaced = replaced.replace(/,\s*/g, ' ').replace(/\s{2,}/g, ' ').trim();
      }
      return replaced;
    }

    function applyRegexPatterns(str) {
      for (var i = 0; i < compiledPatterns.length; i++) {
        var item = compiledPatterns[i];
        var m = item.re.exec(str);
        if (!m) continue;
        return item.repl.replace(/\$(\d+)/g, function (_full, idxStr) {
          var idx = parseInt(idxStr, 10);
          var cap = (idx >= 1 && idx < m.length && m[idx] !== undefined) ? m[idx] : '';
          return localizeDurationCapture(cap);
        });
      }
      return null;
    }

    function lookupSingleSegment(seg, isMenu, depth) {
      // 1. Direct exact / lowercase lookup
      var hit = directLookup(seg, isMenu);
      if (hit !== null) return hit;

      // 2. Normalized internal whitespace lookup
      var collapsed = seg.replace(/\s+/g, ' ').trim();
      if (collapsed !== seg) {
        hit = directLookup(collapsed, isMenu);
        if (hit !== null) return hit;
      }

      // 3. Menu accelerator (&File / E&xit) stripping & CJK/Latin mnemonic preservation
      if (isMenu && ACCEL_KEY_RE.test(collapsed) && collapsed.indexOf('&&') === -1) {
        var accelMatch = collapsed.match(ACCEL_KEY_RE);
        var noAmp = collapsed.replace(/&([A-Za-z0-9])/g, '$1');
        hit = directLookup(noAmp, true);
        if (hit !== null) {
          if (hit.indexOf('&') !== -1 || !accelMatch) return hit;
          var keyChar = accelMatch[1].toUpperCase();
          // Preserve keyboard mnemonic on Latin UI or append (&K) cleanly if short CJK label
          if (/^[A-Za-z0-9]/.test(hit)) {
            var idx = hit.toUpperCase().indexOf(keyChar);
            if (idx !== -1) {
              return hit.slice(0, idx) + '&' + hit.slice(idx);
            }
          }
          if (punctStyle === 'cjk') {
            return hit + '(&' + keyChar + ')';
          }
          return hit;
        }
      }

      // 4. Ellipsis variant parity ("..." <-> "\u2026" or stripping trailing ellipsis/punctuation)
      if (collapsed.endsWith('...')) {
        var withUniEllip = collapsed.slice(0, -3) + ELLIPSIS_CHAR;
        hit = directLookup(withUniEllip, isMenu);
        if (hit !== null) return hit;
      } else if (collapsed.endsWith(ELLIPSIS_CHAR)) {
        var withAsciiEllip = collapsed.slice(0, -1) + '...';
        hit = directLookup(withAsciiEllip, isMenu);
        if (hit !== null) return hit;
      }

      // 5. Trailing punctuation fallback ("Change..." -> "Change" + ellipsis, "Settings:" -> "Settings" + "：")
      var punctMatch = collapsed.match(/^(.*?)(\.\.\.|\u2026|:|\?|!)$/);
      if (punctMatch && punctMatch[1].trim()) {
        var stem = punctMatch[1].trim();
        var punct = punctMatch[2];
        var stemHit = directLookup(stem, isMenu);
        if (stemHit !== null) {
          var cleanStem = stemHit.replace(/(\.\.\.|\u2026|:|\uFF1A|\?|\uFF1F|!|\uFF01)$/, '');
          return cleanStem + mapTrailingPunct(punct, punctStyle);
        }
      }

      // 6. Trailing shortcut split ("Settings Cmd+,")
      var scMatch = collapsed.match(TRAILING_SHORTCUT_RE);
      if (scMatch && scMatch[1]) {
        var labelHit = directLookup(scMatch[1].trim(), isMenu);
        if (labelHit !== null) {
          return labelHit + ' ' + scMatch[2];
        }
      }

      // 7. Compiled regex patterns (dynamic counts, timestamps, version labels, etc.)
      var patHit = applyRegexPatterns(collapsed);
      if (patHit !== null) return patHit;

      // 8. Safe multi-sentence / multi-line decomposition (only when every alpha chunk translates!)
      if (depth < 1 && collapsed.length <= 420 && /(?:\n|[.!?]\s+)/.test(collapsed)) {
        var parts = collapsed.split(/(\n+|(?<=[.!?])\s+)/);
        if (parts.length >= 3 && parts.length <= 9) {
          var allTranslated = true;
          var rebuilt = [];
          for (var i = 0; i < parts.length; i++) {
            var p = parts[i];
            if (!p || /^\s+$/.test(p) || !hasLetters(p)) {
              rebuilt.push(p);
              continue;
            }
            var tPart = lookupSingleSegment(p.trim(), isMenu, depth + 1);
            if (tPart === null) {
              allTranslated = false;
              break;
            }
            rebuilt.push(tPart);
          }
          if (allTranslated) {
            return rebuilt.join('');
          }
        }
      }

      return null;
    }

    function translate(raw, options) {
      if (typeof raw !== 'string' || !raw || identityMode) return raw;
      var trimmed = raw.trim();
      if (shouldSkipRaw(trimmed)) return raw;

      var isMenu = Boolean(options && options.context === 'menu');
      var cache = isMenu ? menuCache : uiCache;
      var cached = cache.get(raw);
      if (cached !== undefined) return cached;

      var leadMatch = raw.match(/^\s*/);
      var trailMatch = raw.match(/\s*$/);
      var leading = leadMatch ? leadMatch[0] : '';
      var trailing = trailMatch ? trailMatch[0] : '';

      var translatedCore = lookupSingleSegment(trimmed, isMenu, 0);
      var result = translatedCore !== null ? leading + translatedCore + trailing : raw;
      cacheSet(cache, raw, result);
      return result;
    }

    return {
      locale: locale,
      meta: meta,
      isIdentity: identityMode,
      translate: translate,
      clearCache: function () {
        uiCache.clear();
        menuCache.clear();
      }
    };
  }

  return {
    createTranslator: createTranslator,
    hasLetters: hasLetters
  };
});
