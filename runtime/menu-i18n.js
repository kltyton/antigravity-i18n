/*
 * antigravity-i18n — Electron Native Menu & Language Switcher Helper
 * MIT License — Runs in the Electron main process alongside electron-i18n.js.
 */
'use strict';

var LANGUAGE_MENU_ID = 'ag-i18n-language-menu';

var UI_LABELS = {
  languageMenu: {
    'en-US': 'Language',
    'zh-CN': '语言 (Language)',
    'zh-TW': '語言 (Language)',
    'ja': '言語 (Language)',
    'ko': '언어 (Language)',
    'es': 'Idioma (Language)',
    'fr': 'Langue (Language)',
    'de': 'Sprache (Language)',
    'pt-BR': 'Idioma (Language)',
    'ru': 'Язык (Language)'
  },
  autoDetect: {
    'en-US': 'Follow System (Auto)',
    'zh-CN': '跟随系统 (自动)',
    'zh-TW': '跟隨系統 (自動)',
    'ja': 'システム設定に従う (自動)',
    'ko': '시스템 설정 따름 (자동)',
    'es': 'Seguir idioma del sistema (Auto)',
    'fr': 'Suivre le système (Auto)',
    'de': 'Systemsprache verwenden (Auto)',
    'pt-BR': 'Seguir idioma do sistema (Auto)',
    'ru': 'Как в системе (Авто)'
  },
  openFolder: {
    'en-US': 'Open Language Packs Folder...',
    'zh-CN': '打开语言包目录...',
    'zh-TW': '開啟語言包資料夾...',
    'ja': '言語パックフォルダを開く...',
    'ko': '언어 팩 폴더 열기...',
    'es': 'Abrir carpeta de idiomas...',
    'fr': 'Ouvrir le dossier des langues...',
    'de': 'Sprachpaket-Ordner öffnen...',
    'pt-BR': 'Abrir pasta de pacotes de idioma...',
    'ru': 'Открыть папку языковых пакетов...'
  }
};

function pickUiLabel(table, locale, fallback) {
  if (table && Object.prototype.hasOwnProperty.call(table, locale)) {
    return table[locale];
  }
  return fallback;
}

function preserveMenuItemOriginal(item) {
  if (!item || typeof item !== 'object') return;
  if (typeof item.label === 'string') {
    if (item._agI18nOrigLabel === undefined || item._agI18nLastTranslated !== item.label) {
      item._agI18nOrigLabel = item.label;
    }
  }
  if (typeof item.sublabel === 'string') {
    if (item._agI18nOrigSublabel === undefined || item._agI18nLastSublabel !== item.sublabel) {
      item._agI18nOrigSublabel = item.sublabel;
    }
  }
  if (typeof item.toolTip === 'string') {
    if (item._agI18nOrigToolTip === undefined || item._agI18nLastToolTip !== item.toolTip) {
      item._agI18nOrigToolTip = item.toolTip;
    }
  }
}

function translateMenuTemplateArray(template, translator) {
  if (!Array.isArray(template)) return template;
  return template.map(function (entry) {
    if (!entry || typeof entry !== 'object') return entry;
    if (entry.id === LANGUAGE_MENU_ID) return entry;
    var cloned = Object.assign({}, entry);
    if (typeof cloned.label === 'string' && cloned.label) {
      cloned._agI18nOrigLabel = cloned.label;
      cloned.label = translator.translate(cloned.label, { context: 'menu' });
      cloned._agI18nLastTranslated = cloned.label;
    }
    if (typeof cloned.sublabel === 'string' && cloned.sublabel) {
      cloned._agI18nOrigSublabel = cloned.sublabel;
      cloned.sublabel = translator.translate(cloned.sublabel, { context: 'menu' });
      cloned._agI18nLastSublabel = cloned.sublabel;
    }
    if (typeof cloned.toolTip === 'string' && cloned.toolTip) {
      cloned._agI18nOrigToolTip = cloned.toolTip;
      cloned.toolTip = translator.translate(cloned.toolTip, { context: 'menu' });
      cloned._agI18nLastToolTip = cloned.toolTip;
    }
    if (Array.isArray(cloned.submenu)) {
      cloned.submenu = translateMenuTemplateArray(cloned.submenu, translator);
    }
    return cloned;
  });
}

function translateMenuItemLive(item, translator) {
  if (!item || typeof item !== 'object') return;
  if (item.id === LANGUAGE_MENU_ID) return;

  preserveMenuItemOriginal(item);

  if (typeof item._agI18nOrigLabel === 'string' && item._agI18nOrigLabel) {
    var translatedLabel = translator.translate(item._agI18nOrigLabel, { context: 'menu' });
    if (item.label !== translatedLabel) {
      item.label = translatedLabel;
    }
    item._agI18nLastTranslated = translatedLabel;
  }
  if (typeof item._agI18nOrigSublabel === 'string' && item._agI18nOrigSublabel) {
    var translatedSublabel = translator.translate(item._agI18nOrigSublabel, { context: 'menu' });
    if (item.sublabel !== translatedSublabel) {
      item.sublabel = translatedSublabel;
    }
    item._agI18nLastSublabel = translatedSublabel;
  }
  if (typeof item._agI18nOrigToolTip === 'string' && item._agI18nOrigToolTip) {
    var translatedTip = translator.translate(item._agI18nOrigToolTip, { context: 'menu' });
    if (item.toolTip !== translatedTip) {
      item.toolTip = translatedTip;
    }
    item._agI18nLastToolTip = translatedTip;
  }

  if (item.submenu && Array.isArray(item.submenu.items)) {
    for (var i = 0; i < item.submenu.items.length; i++) {
      translateMenuItemLive(item.submenu.items[i], translator);
    }
  }
}

function translateMenuInstanceLive(menu, translator) {
  if (!menu || !Array.isArray(menu.items)) return;
  for (var i = 0; i < menu.items.length; i++) {
    translateMenuItemLive(menu.items[i], translator);
  }
}

function buildLanguageSubmenuTemplate(state) {
  var activeLocale = state.locale || 'en-US';
  var configuredLocale = (state.config && state.config.locale) || 'auto';
  var isAuto = configuredLocale === 'auto';
  var locales = Array.isArray(state.locales) ? state.locales : [];

  var items = [
    {
      label: pickUiLabel(UI_LABELS.autoDetect, activeLocale, 'Follow System (Auto)'),
      type: 'radio',
      checked: isAuto,
      click: function () {
        if (typeof state.onSelectLocale === 'function') {
          state.onSelectLocale('auto');
        }
      }
    },
    { type: 'separator' }
  ];

  for (var i = 0; i < locales.length; i++) {
    (function (loc) {
      var title = loc.nativeName && loc.nativeName !== loc.name
        ? loc.nativeName + ' (' + loc.locale + ')'
        : (loc.nativeName || loc.name || loc.locale) + ' (' + loc.locale + ')';
      items.push({
        label: title,
        type: 'radio',
        checked: !isAuto && activeLocale === loc.locale,
        click: function () {
          if (typeof state.onSelectLocale === 'function') {
            state.onSelectLocale(loc.locale);
          }
        }
      });
    })(locales[i]);
  }

  if (typeof state.onOpenLocalesFolder === 'function') {
    items.push({ type: 'separator' });
    items.push({
      label: pickUiLabel(UI_LABELS.openFolder, activeLocale, 'Open Language Packs Folder...'),
      click: function () {
        state.onOpenLocalesFolder();
      }
    });
  }

  return {
    id: LANGUAGE_MENU_ID,
    label: pickUiLabel(UI_LABELS.languageMenu, activeLocale, 'Language'),
    submenu: items
  };
}

function appendOrReplaceLanguageInTemplate(template, state, isTray) {
  if (!Array.isArray(template)) return template;
  var langEntry = buildLanguageSubmenuTemplate(state);
  var filtered = template.filter(function (it) {
    return !(it && it.id === LANGUAGE_MENU_ID);
  });

  if (isTray) {
    var quitIdx = -1;
    for (var i = 0; i < filtered.length; i++) {
      var rawOrig = filtered[i] && (filtered[i]._agI18nOrigLabel || filtered[i].label);
      if (rawOrig === 'Quit' || (filtered[i] && filtered[i].role === 'quit')) {
        quitIdx = i;
        break;
      }
    }
    if (quitIdx >= 0) {
      filtered.splice(quitIdx, 0, langEntry);
    } else {
      filtered.push(langEntry);
    }
    return filtered;
  }

  // Place Language submenu cleanly right before Help if present, otherwise at the end
  var helpIdx = -1;
  for (var j = 0; j < filtered.length; j++) {
    var lbl = filtered[j] && (filtered[j]._agI18nOrigLabel || filtered[j].label);
    if (lbl === 'Help' || (filtered[j] && filtered[j].role === 'help')) {
      helpIdx = j;
      break;
    }
  }
  if (helpIdx >= 0) {
    filtered.splice(helpIdx, 0, langEntry);
  } else {
    filtered.push(langEntry);
  }
  return filtered;
}

module.exports = {
  LANGUAGE_MENU_ID: LANGUAGE_MENU_ID,
  UI_LABELS: UI_LABELS,
  preserveMenuItemOriginal: preserveMenuItemOriginal,
  translateMenuTemplateArray: translateMenuTemplateArray,
  translateMenuItemLive: translateMenuItemLive,
  translateMenuInstanceLive: translateMenuInstanceLive,
  buildLanguageSubmenuTemplate: buildLanguageSubmenuTemplate,
  appendOrReplaceLanguageInTemplate: appendOrReplaceLanguageInTemplate
};
