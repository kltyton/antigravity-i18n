# coding: utf-8
"""Quick interactive/standalone installer entry point for antigravity-i18n."""

import argparse
import sys
from pathlib import Path

from ag_i18n import PROJECT_NAME, VERSION
from ag_i18n.targets import TARGET_CHOICES, install_targets


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Install {PROJECT_NAME} v{VERSION}")
    parser.add_argument(
        "--target",
        choices=TARGET_CHOICES,
        default="auto",
        help="Target product: auto (all detected), desktop, ide, or all (default: auto).",
    )
    parser.add_argument("--app-dir", help="Custom Antigravity Desktop or IDE installation directory.")
    parser.add_argument("--lang", help="Initial locale (e.g. auto, zh-CN, ja, en-US).")
    parser.add_argument("--yes", "-y", action="store_true", help="Do not wait for Enter on completion.")
    args = parser.parse_args()

    try:
        results = install_targets(
            target=args.target,
            app_dir=Path(args.app_dir) if args.app_dir else None,
            locale=args.lang,
        )
        print(f"[{PROJECT_NAME} v{VERSION}] Installation succeeded!")
        for kind, res in results:
            if kind == "ide":
                print(f"  [IDE] App     : {res.resources_app_dir}")
                if res.localized_extensions:
                    print(f"        Exts    : {', '.join(res.localized_extensions)}")
            else:
                print(f"  [Desktop] ASAR: {res.asar_path}")
            print(f"  Locale Packs  : {', '.join(res.deployed_locales)}")
            print(f"  Config        : {res.user_i18n_dir / 'config.json'} (locale={res.active_locale})")
        code = 0
    except Exception as exc:
        print(f"[{PROJECT_NAME} v{VERSION}] Installation failed: {exc}", file=sys.stderr)
        code = 1

    if not args.yes and sys.stdin.isatty():
        try:
            input("\nPress Enter to exit...")
        except EOFError:
            pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
