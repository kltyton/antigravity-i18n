/*
 * antigravity-i18n — In-App Settings Modal Language Picker
 * MIT License — Renders a native-styled Language section inside Antigravity Settings -> General.
 */
(function (root, factory) {
  'use strict';
  var mod = factory();
  if (typeof module === 'object' && typeof module.exports === 'object') {
    module.exports = mod;
  }
  if (root) {
    root.AntigravityI18nSettingsUi = mod;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var SECTION_ATTR = 'data-ag-i18n-settings-section';
  var IGNORE_ATTR = 'data-ag-i18n-ignore';

  var LABELS = {
    'en-US': {
      sectionTitle: 'Language',
      displayLabel: 'Display Language',
      displayDesc: 'Switch Antigravity UI and native menu language immediately without restarting.',
      autoOption: 'Follow System (Auto)',
      folderLabel: 'Language Packs',
      folderDesc: 'Open the external JSON locale packs folder to customize or add languages.',
      openFolderBtn: 'Open Folder',
      switchingStatus: 'Switching language...'
    },
    'zh-CN': {
      sectionTitle: '语言 (Language)',
      displayLabel: '显示语言',
      displayDesc: '切换界面与菜单显示语言，选择后立即生效，无需重启。',
      autoOption: '跟随系统 (自动)',
      folderLabel: '语言包目录',
      folderDesc: '打开外部 JSON 语言包文件夹，可用于自定义翻译或添加新语言。',
      openFolderBtn: '打开目录',
      switchingStatus: '正在切换语言...'
    },
    'zh-TW': {
      sectionTitle: '語言 (Language)',
      displayLabel: '顯示語言',
      displayDesc: '切換介面與選單顯示語言，選擇後立即生效，無需重啟。',
      autoOption: '跟隨系統 (自動)',
      folderLabel: '語言包資料夾',
      folderDesc: '開啟外部 JSON 語言包資料夾，可用於自訂翻譯或新增語言。',
      openFolderBtn: '開啟資料夾',
      switchingStatus: '正在切換語言...'
    },
    'ja': {
      sectionTitle: '言語 (Language)',
      displayLabel: '表示言語',
      displayDesc: 'UI とメニューの表示言語を再起動なしで即座に切り替えます。',
      autoOption: 'システム設定に従う (自動)',
      folderLabel: '言語パックフォルダ',
      folderDesc: '外部 JSON 言語パックフォルダを開き、翻訳の編集や言語の追加を行えます。',
      openFolderBtn: 'フォルダを開く',
      switchingStatus: '言語を切り替えています...'
    },
    'ko': {
      sectionTitle: '언어 (Language)',
      displayLabel: '표시 언어',
      displayDesc: '재시작 없이 UI 및 메뉴 표시 언어를 즉시 전환합니다.',
      autoOption: '시스템 설정 따름 (자동)',
      folderLabel: '언어 팩 폴더',
      folderDesc: '외부 JSON 언어 팩 폴더를 열어 번역을 수정하거나 새 언어를 추가할 수 있습니다.',
      openFolderBtn: '폴더 열기',
      switchingStatus: '언어 전환 중...'
    },
    'es': {
      sectionTitle: 'Idioma (Language)',
      displayLabel: 'Idioma de la interfaz',
      displayDesc: 'Cambia al instante el idioma de la interfaz y los menús sin reiniciar.',
      autoOption: 'Seguir idioma del sistema (Auto)',
      folderLabel: 'Paquetes de idioma',
      folderDesc: 'Abre la carpeta externa de paquetes JSON para personalizar o añadir idiomas.',
      openFolderBtn: 'Abrir carpeta',
      switchingStatus: 'Cambiando idioma...'
    },
    'fr': {
      sectionTitle: 'Langue (Language)',
      displayLabel: "Langue d'affichage",
      displayDesc: 'Changez immédiatement la langue de l’interface et des menus sans redémarrer.',
      autoOption: 'Suivre le système (Auto)',
      folderLabel: 'Packs de langue',
      folderDesc: 'Ouvrez le dossier externe des packs JSON pour personnaliser ou ajouter des langues.',
      openFolderBtn: 'Ouvrir le dossier',
      switchingStatus: 'Changement de langue...'
    },
    'de': {
      sectionTitle: 'Sprache (Language)',
      displayLabel: 'Anzeigesprache',
      displayDesc: 'Sprache für Oberfläche und Menüs sofort ohne Neustart umschalten.',
      autoOption: 'Systemsprache verwenden (Auto)',
      folderLabel: 'Sprachpakete',
      folderDesc: 'Öffnet den externen JSON-Sprachpaket-Ordner zum Anpassen oder Hinzufügen von Sprachen.',
      openFolderBtn: 'Ordner öffnen',
      switchingStatus: 'Sprache wird gewechselt...'
    },
    'pt-BR': {
      sectionTitle: 'Idioma (Language)',
      displayLabel: 'Idioma de exibição',
      displayDesc: 'Altere o idioma da interface e dos menus imediatamente sem reiniciar.',
      autoOption: 'Seguir idioma do sistema (Auto)',
      folderLabel: 'Pacotes de idioma',
      folderDesc: 'Abra a pasta externa de pacotes JSON para personalizar ou adicionar idiomas.',
      openFolderBtn: 'Abrir pasta',
      switchingStatus: 'Alterando idioma...'
    },
    'ru': {
      sectionTitle: 'Язык (Language)',
      displayLabel: 'Язык интерфейса',
      displayDesc: 'Мгновенное переключение языка интерфейса и меню без перезапуска.',
      autoOption: 'Как в системе (Авто)',
      folderLabel: 'Языковые пакеты',
      folderDesc: 'Открыть папку с внешними JSON-пакетами для настройки или добавления языков.',
      openFolderBtn: 'Открыть папку',
      switchingStatus: 'Переключение языка...'
    }
  };

  var GENERAL_TITLES = {
    'General': 1,
    '常规': 1,
    '一般': 1,
    '일반': 1,
    'Allgemein': 1,
    'Général': 1,
    'Geral': 1,
    'Общие': 1
  };

  function isDarkSurface(doc) {
    try {
      if (doc && doc.documentElement && doc.documentElement.classList && doc.documentElement.classList.contains('dark')) {
        return true;
      }
      var win = doc && doc.defaultView;
      if (win && typeof win.getComputedStyle === 'function' && doc.body) {
        var bg = win.getComputedStyle(doc.body).backgroundColor || '';
        var m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
        if (m) {
          var lum = (Number(m[1]) * 299 + Number(m[2]) * 587 + Number(m[3]) * 114) / 1000;
          return lum < 128;
        }
      }
    } catch (_err) {
      // Fallback below
    }
    return true;
  }

  function getUiCopy(locale) {
    if (locale && Object.prototype.hasOwnProperty.call(LABELS, locale)) {
      return LABELS[locale];
    }
    return LABELS['en-US'];
  }

  function isGeneralHeadingText(text) {
    if (!text) return false;
    return Boolean(GENERAL_TITLES[String(text).trim()]);
  }

  function readHeadingOriginal(h2, getOriginalText) {
    if (!h2) return '';
    if (typeof getOriginalText === 'function' && h2.firstChild && h2.firstChild.nodeType === 3) {
      var orig = getOriginalText(h2.firstChild);
      if (orig) return String(orig).trim();
    }
    return (h2.textContent || '').trim();
  }

  function findGeneralSettingsContainer(doc, getOriginalText) {
    if (!doc || typeof doc.querySelectorAll !== 'function') return null;
    var headings = doc.querySelectorAll('h2');
    for (var i = 0; i < headings.length; i++) {
      var h2 = headings[i];
      if (!h2 || !h2.parentElement) continue;
      var orig = readHeadingOriginal(h2, getOriginalText);
      var visible = (h2.textContent || '').trim();
      if (!isGeneralHeadingText(orig) && !isGeneralHeadingText(visible)) continue;

      // Walk up from <h2> to the Settings screen wrapper ("p-6 flex flex-col gap-4 w-full max-w-2xl mx-auto")
      var wrapper = h2.closest ? h2.closest('.max-w-2xl') : null;
      if (!wrapper && h2.parentElement && h2.parentElement.parentElement && h2.parentElement.parentElement.parentElement) {
        wrapper = h2.parentElement.parentElement.parentElement;
      }
      if (!wrapper) continue;

      var children = wrapper.children || [];
      for (var j = 0; j < children.length; j++) {
        var child = children[j];
        if (!child || !child.className || typeof child.className !== 'string') continue;
        if (child.className.indexOf('gap-8') !== -1 && child.className.indexOf('flex-col') !== -1) {
          return child;
        }
      }
    }
    return null;
  }

  function createSettingsController(options) {
    var doc = options.document;
    var getState = options.getState;
    var getOriginalText = options.getOriginalText;
    var onSelectLocale = options.onSelectLocale;
    var onOpenFolder = options.onOpenFolder;
    var busy = false;

    function buildSectionDom() {
      var section = doc.createElement('div');
      section.setAttribute(SECTION_ATTR, '1');
      section.setAttribute(IGNORE_ATTR, '1');
      section.className = 'space-y-2';

      var titleDiv = doc.createElement('div');
      titleDiv.className = 'font-medium';
      titleDiv.setAttribute('data-ag-i18n-role', 'section-title');
      section.appendChild(titleDiv);

      var card = doc.createElement('div');
      card.className = 'agy-card bg-transparent rounded-xl border border-border overflow-hidden divide-y divide-border';

      // Row 1: Display Language selector
      var row1 = doc.createElement('div');
      row1.className = 'py-2 px-3 w-full bg-transparent flex justify-between gap-4 items-center';

      var row1Left = doc.createElement('div');
      row1Left.className = 'flex-1 flex flex-col gap-0.5';
      var row1TitleWrap = doc.createElement('div');
      row1TitleWrap.className = 'flex items-center gap-1.5';
      var row1Title = doc.createElement('span');
      row1Title.id = 'ag-i18n-settings-lang-label';
      row1Title.setAttribute('data-ag-i18n-role', 'display-label');
      row1TitleWrap.appendChild(row1Title);
      var row1Desc = doc.createElement('span');
      row1Desc.className = 'text-sm text-muted-foreground whitespace-pre-wrap';
      row1Desc.setAttribute('data-ag-i18n-role', 'display-desc');
      row1Left.appendChild(row1TitleWrap);
      row1Left.appendChild(row1Desc);

      var row1Right = doc.createElement('div');
      row1Right.className = 'shrink-0 flex items-center gap-2';
      var select = doc.createElement('select');
      select.setAttribute('data-testid', 'ag-i18n-language-select');
      select.setAttribute('aria-labelledby', 'ag-i18n-settings-lang-label');
      select.className = 'px-2.5 py-1.5 bg-secondary text-secondary-foreground hover:text-foreground rounded-md border border-border cursor-pointer min-w-[190px] text-sm outline-none';
      select.style.colorScheme = 'dark light';
      select.addEventListener('change', function () {
        if (busy || typeof onSelectLocale !== 'function') return;
        var nextLocale = select.value;
        busy = true;
        select.disabled = true;
        Promise.resolve(onSelectLocale(nextLocale)).finally(function () {
          busy = false;
          select.disabled = false;
        });
      });
      row1Right.appendChild(select);

      row1.appendChild(row1Left);
      row1.appendChild(row1Right);
      card.appendChild(row1);

      // Row 2: Open Language Packs Folder
      var row2 = doc.createElement('div');
      row2.className = 'py-2 px-3 w-full bg-transparent flex justify-between gap-4 items-center';

      var row2Left = doc.createElement('div');
      row2Left.className = 'flex-1 flex flex-col gap-0.5';
      var row2TitleWrap = doc.createElement('div');
      row2TitleWrap.className = 'flex items-center gap-1.5';
      var row2Title = doc.createElement('span');
      row2Title.setAttribute('data-ag-i18n-role', 'folder-label');
      row2TitleWrap.appendChild(row2Title);
      var row2Desc = doc.createElement('span');
      row2Desc.className = 'text-sm text-muted-foreground whitespace-pre-wrap';
      row2Desc.setAttribute('data-ag-i18n-role', 'folder-desc');
      row2Left.appendChild(row2TitleWrap);
      row2Left.appendChild(row2Desc);

      var row2Right = doc.createElement('div');
      row2Right.className = 'shrink-0';
      var openBtn = doc.createElement('button');
      openBtn.type = 'button';
      openBtn.setAttribute('data-testid', 'ag-i18n-open-folder-btn');
      openBtn.className = 'px-3 py-1 bg-secondary text-secondary-foreground hover:text-foreground rounded-md border border-border cursor-pointer text-sm outline-none';
      openBtn.addEventListener('click', function () {
        if (typeof onOpenFolder === 'function') {
          onOpenFolder();
        }
      });
      row2Right.appendChild(openBtn);

      row2.appendChild(row2Left);
      row2.appendChild(row2Right);
      card.appendChild(row2);

      section.appendChild(card);
      return section;
    }

    function updateSectionContent(section) {
      if (!section) return;
      var st = (typeof getState === 'function' ? getState() : null) || {};
      var activeLocale = st.locale || 'en-US';
      var configuredLocale = (st.config && st.config.locale) || 'auto';
      var locales = Array.isArray(st.locales) ? st.locales : [];
      var copy = getUiCopy(activeLocale);

      var q = function (role) { return section.querySelector('[data-ag-i18n-role="' + role + '"]'); };
      var titleEl = q('section-title');
      var dispLbl = q('display-label');
      var dispDesc = q('display-desc');
      var fldLbl = q('folder-label');
      var fldDesc = q('folder-desc');
      var openBtn = section.querySelector('[data-testid="ag-i18n-open-folder-btn"]');
      var select = section.querySelector('[data-testid="ag-i18n-language-select"]');

      if (titleEl) titleEl.textContent = copy.sectionTitle;
      if (dispLbl) dispLbl.textContent = copy.displayLabel;
      if (dispDesc) dispDesc.textContent = copy.displayDesc;
      if (fldLbl) fldLbl.textContent = copy.folderLabel;
      if (fldDesc) fldDesc.textContent = copy.folderDesc;
      if (openBtn) openBtn.textContent = copy.openFolderBtn;

      if (select) {
        var isDark = isDarkSurface(doc);
        select.style.colorScheme = isDark ? 'dark' : 'light';
        var optBg = isDark ? '#1f2328' : '#ffffff';
        var optFg = isDark ? '#f0f6fc' : '#1f2328';
        var desiredValue = configuredLocale === 'auto' ? 'auto' : activeLocale;
        var sigParts = ['auto:' + copy.autoOption + ':' + (isDark ? 'd' : 'l')];
        for (var i = 0; i < locales.length; i++) {
          var l = locales[i];
          var txt = (l.nativeName || l.name || l.locale) + ' (' + l.locale + ')';
          sigParts.push(l.locale + ':' + txt);
        }
        var nextSig = sigParts.join('|');
        if (select.getAttribute('data-ag-i18n-sig') !== nextSig) {
          while (select.firstChild) {
            select.removeChild(select.firstChild);
          }
          var autoOpt = doc.createElement('option');
          autoOpt.value = 'auto';
          autoOpt.textContent = copy.autoOption;
          autoOpt.style.backgroundColor = optBg;
          autoOpt.style.color = optFg;
          select.appendChild(autoOpt);

          for (var j = 0; j < locales.length; j++) {
            var item = locales[j];
            var opt = doc.createElement('option');
            opt.value = item.locale;
            opt.textContent = (item.nativeName || item.name || item.locale) + ' (' + item.locale + ')';
            opt.style.backgroundColor = optBg;
            opt.style.color = optFg;
            select.appendChild(opt);
          }
          select.setAttribute('data-ag-i18n-sig', nextSig);
        }
        if (select.value !== desiredValue) {
          select.value = desiredValue;
        }
      }
    }

    function sync() {
      var container = findGeneralSettingsContainer(doc, getOriginalText);
      if (!container) return null;
      var section = container.querySelector('[' + SECTION_ATTR + '="1"]');
      if (!section) {
        section = buildSectionDom();
        container.appendChild(section);
      }
      updateSectionContent(section);
      return section;
    }

    return {
      sync: sync
    };
  }

  return {
    SECTION_ATTR: SECTION_ATTR,
    IGNORE_ATTR: IGNORE_ATTR,
    LABELS: LABELS,
    getUiCopy: getUiCopy,
    isGeneralHeadingText: isGeneralHeadingText,
    findGeneralSettingsContainer: findGeneralSettingsContainer,
    createSettingsController: createSettingsController
  };
});
