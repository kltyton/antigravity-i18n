# coding: utf-8
"""Unified CLI for antigravity-i18n."""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from ag_i18n import PROJECT_NAME, VERSION
from ag_i18n.extractor import extract_all_ui_strings
from ag_i18n.patcher import list_locales, set_configured_locale
from ag_i18n.paths import LOCALES_DIR, get_user_i18n_dir
from ag_i18n.targets import TARGET_CHOICES, install_targets, restore_targets
from ag_i18n.validator import validate_locales_dir


def cmd_install(args: argparse.Namespace) -> int:
    app_dir = Path(args.app_dir) if args.app_dir else None
    user_dir = Path(args.user_dir) if args.user_dir else None
    results = install_targets(
        target=args.target,
        app_dir=app_dir,
        locale=args.lang,
        user_i18n_dir=user_dir,
    )
    print(f"[{PROJECT_NAME} v{VERSION}] Installed runtime cleanly.")
    for kind, res in results:
        if kind == "ide":
            print(f"  [IDE] Target  : {res.resources_app_dir}")
            if res.localized_extensions:
                print(f"        Exts    : {', '.join(res.localized_extensions)}")
            if res.backup_dir:
                print(f"        Backup  : {res.backup_dir}")
        else:
            print(f"  [Desktop] ASAR: {res.asar_path}")
            if res.legacy_reverted_files:
                print(f"        Migrated: {', '.join(res.legacy_reverted_files)}")
            if res.backup_path:
                print(f"        Backup  : {res.backup_path}")
        print(f"  User i18n dir : {res.user_i18n_dir}")
        print(f"  Active locale : {res.active_locale}")
        print(f"  Locales synced: {', '.join(res.deployed_locales)}")
    print("Restart Antigravity / Antigravity IDE (or switch language in Antigravity Settings) to take effect.")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    app_dir = Path(args.app_dir) if args.app_dir else None
    restored = restore_targets(target=args.target, app_dir=app_dir, hard=args.hard)
    mode = "hard backup" if args.hard else "surgical (preserving other mods)"
    for kind, target_path in restored:
        print(f"[{PROJECT_NAME} v{VERSION}] Restored {kind}: {target_path} ({mode}).")
    return 0


def cmd_lang(args: argparse.Namespace) -> int:
    user_dir = Path(args.user_dir) if args.user_dir else get_user_i18n_dir()
    cfg = set_configured_locale(args.locale, user_i18n_dir=user_dir)
    print(f"[{PROJECT_NAME}] Active locale updated to {args.locale!r} in {cfg}")
    print("Tip: You can also switch languages live from Antigravity's Language menu without restarting.")
    return 0


def cmd_langs(args: argparse.Namespace) -> int:
    user_dir = Path(args.user_dir) if args.user_dir else None
    configured, items = list_locales(user_i18n_dir=user_dir)
    print(f"Configured locale: {configured}")
    for it in items:
        print(
            f"  {it['locale']:<8}  {it['nativeName']} ({it['name']})  "
            f"[{it['exactCount']} strings, {it['patternCount']} patterns]"
        )
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    asar_path = Path(args.asar) if args.asar else None
    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    ui_strings, menu_strings = extract_all_ui_strings(asar_path=asar_path, cache_dir=cache_dir)
    out_path = Path(args.output)
    payload = {
        "meta": {
            "locale": "_template",
            "name": "Antigravity Extracted UI Template",
            "nativeName": "English (Extracted)",
            "direction": "ltr",
            "punctuationStyle": "ascii",
        },
        "exact": {s: s for s in sorted(ui_strings)},
        "menu": {s: s for s in sorted(menu_strings)},
        "patterns": [],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(ui_strings)} UI strings + {len(menu_strings)} menu/dialog strings -> {out_path}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    loc_dir = Path(args.locales_dir) if args.locales_dir else LOCALES_DIR
    reports, baseline_count = validate_locales_dir(loc_dir, require_full_coverage=not args.allow_partial)
    if not reports:
        print(f"No locale JSON files found under {loc_dir}", file=sys.stderr)
        return 1

    has_error = False
    print(f"Checking {len(reports)} locale bundle(s) in {loc_dir} (baseline keys: {baseline_count}):")
    for r in reports:
        cov = r.coverage_percent(baseline_count)
        status = "PASS" if r.ok else "FAIL"
        print(
            f"  [{status}] {r.file_name:<12} ({r.native_name or r.locale}) — "
            f"{r.exact_count} exact ({cov:.1f}%), {r.pattern_count} patterns, {r.menu_count} menu overrides"
        )
        for w in r.warnings[:3]:
            print(f"         WARN: {w}")
        if len(r.warnings) > 3:
            print(f"         ... and {len(r.warnings) - 3} more warning(s)")
        for e in r.errors:
            print(f"         ERROR: {e}")
            has_error = True
    return 1 if has_error else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROJECT_NAME,
        description="Universal multi-language i18n framework & external locale runtime for Antigravity Desktop and Antigravity IDE.",
    )
    parser.add_argument("--version", action="version", version=f"{PROJECT_NAME} {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inst = sub.add_parser("install", help="Install runtime i18n engine and deploy locales.")
    p_inst.add_argument(
        "--target",
        choices=TARGET_CHOICES,
        default="auto",
        help="Target product: auto (all detected), desktop, ide, or all (default: auto).",
    )
    p_inst.add_argument("--app-dir", help="Custom Antigravity Desktop or IDE installation directory.")
    p_inst.add_argument("--lang", help="Set initial locale (e.g. auto, zh-CN, zh-TW, ja, ko, es, fr, de, pt-BR, ru).")
    p_inst.add_argument("--user-dir", help="Override target user i18n directory.")
    p_inst.set_defaults(func=cmd_install)

    p_rest = sub.add_parser("restore", help="Remove antigravity-i18n runtime cleanly.")
    p_rest.add_argument(
        "--target",
        choices=TARGET_CHOICES,
        default="auto",
        help="Target product: auto (all detected), desktop, ide, or all (default: auto).",
    )
    p_rest.add_argument("--app-dir", help="Custom Antigravity Desktop or IDE installation directory.")
    p_rest.add_argument("--hard", action="store_true", help="Restore exact backups instead of surgical clean.")
    p_rest.set_defaults(func=cmd_restore)

    p_lang = sub.add_parser("lang", help="Change configured default language in config.json.")
    p_lang.add_argument("locale", help="Target locale tag or 'auto'.")
    p_lang.add_argument("--user-dir", help="Override user i18n directory.")
    p_lang.set_defaults(func=cmd_lang)

    p_langs = sub.add_parser("langs", help="List available installed language packs.")
    p_langs.add_argument("--user-dir", help="Override user i18n directory.")
    p_langs.set_defaults(func=cmd_langs)

    p_ext = sub.add_parser("extract", help="Extract live Antigravity UI & menu strings into a template JSON.")
    p_ext.add_argument("--asar", help="Path to Antigravity app.asar.")
    p_ext.add_argument("--cache-dir", help="Path to Chromium Cache_Data directory.")
    p_ext.add_argument("--output", default=str(LOCALES_DIR / "_extracted.json"), help="Output template JSON path.")
    p_ext.set_defaults(func=cmd_extract)

    p_chk = sub.add_parser("check", help="Validate all locale bundles (JSON schema, regexes, placeholders, coverage).")
    p_chk.add_argument("--locales-dir", help="Directory containing locale JSON files.")
    p_chk.add_argument("--allow-partial", action="store_true", help="Treat missing template keys as warnings instead of errors.")
    p_chk.set_defaults(func=cmd_check)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
