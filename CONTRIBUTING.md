# Contributing to antigravity-i18n

Welcome! `antigravity-i18n` separates the lightweight JS/Python localization runtime from language data files under [`locales/`](locales), so adding or improving a language **never requires touching Python or JavaScript code**.

## Adding a New Language Pack

1. Copy [`locales/_template.json`](locales/_template.json) to `locales/<bcp47-tag>.json` (for example `locales/it.json`, `locales/vi.json`, `locales/pl.json`, `locales/uk.json`).
2. Update the `"meta"` header accurately:
   ```json
   "meta": {
     "locale": "it",
     "name": "Italian",
     "nativeName": "Italiano",
     "direction": "ltr",
     "punctuationStyle": "ascii"
   }
   ```
   - Use `"punctuationStyle": "cjk"` for Chinese (`zh-CN`, `zh-TW`), and `"ascii"` otherwise.
   - Use `"direction": "rtl"` only for right-to-left locales (`ar`, `he`, `fa`).
3. Translate:
   - `"exact"`: key -> localized string (never alter English keys).
   - `"menu"`: menu-specific overrides (keys only, no manual `&` accelerators needed).
   - `"patterns"`: `[regexSource, flags, localizedReplacement]` tuples (keep elements `0` and `1` unchanged, translate element `2` preserving `$1`, `$2`, etc.).
4. Keep technical proper nouns, slash commands (`/browser`), and placeholders (`$1`, `$2`) intact.

## Validating Before Submitting a PR

Run the automated validation and test suite from the repository root:

```bash
python cli.py check
python -m unittest discover -s tests -v
```

Both commands check JSON syntax, metadata completeness, regex validity, capture group bounds, placeholder parity, and runtime translation behavior using Python stdlib and Node.js.

## Refreshing Template Keys After an Antigravity Update

When a new version of Antigravity Desktop introduces new UI strings, extract candidates from your local installation:

```bash
python cli.py extract --output locales/_extracted.json
```

Compare newly extracted keys against `locales/_template.json`, add curated UI strings to `_template.json`, and update locale files accordingly.
