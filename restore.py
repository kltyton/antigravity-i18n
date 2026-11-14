# coding: utf-8
"""Quick interactive/standalone uninstaller entry point for antigravity-i18n."""

import argparse
import sys
from pathlib import Path

from ag_i18n import PROJECT_NAME, VERSION
from ag_i18n.patcher import restore_patch


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Restore {PROJECT_NAME} v{VERSION}")
    parser.add_argument("--app-dir", help="Custom Antigravity installation directory.")
    parser.add_argument(
        "--hard",
        action="store_true",
        help="Restore raw app.asar.bak backup (removes all ASAR patches including other mods).",
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Do not wait for Enter on completion.")
    args = parser.parse_args()

    try:
        asar_path = restore_patch(
            app_dir=Path(args.app_dir) if args.app_dir else None,
            hard=bool(args.hard),
        )
        mode = "hard backup restore" if args.hard else "surgical unpatch"
        print(f"[{PROJECT_NAME} v{VERSION}] Restored successfully ({mode}): {asar_path}")
        code = 0
    except Exception as exc:
        print(f"[{PROJECT_NAME} v{VERSION}] Restore failed: {exc}", file=sys.stderr)
        code = 1

    if not args.yes and sys.stdin.isatty():
        try:
            input("\nPress Enter to exit...")
        except EOFError:
            pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
