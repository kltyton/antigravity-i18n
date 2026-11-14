# coding: utf-8
"""Quick interactive/standalone uninstaller entry point for antigravity-i18n."""

import argparse
import sys
from pathlib import Path

from ag_i18n import PROJECT_NAME, VERSION
from ag_i18n.targets import TARGET_CHOICES, restore_targets


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Restore {PROJECT_NAME} v{VERSION}")
    parser.add_argument(
        "--target",
        choices=TARGET_CHOICES,
        default="auto",
        help="Target product: auto (all detected), desktop, ide, or all (default: auto).",
    )
    parser.add_argument("--app-dir", help="Custom Antigravity Desktop or IDE installation directory.")
    parser.add_argument(
        "--hard",
        action="store_true",
        help="Restore raw backups (removes all patches including other mods).",
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Do not wait for Enter on completion.")
    args = parser.parse_args()

    try:
        restored = restore_targets(
            target=args.target,
            app_dir=Path(args.app_dir) if args.app_dir else None,
            hard=bool(args.hard),
        )
        mode = "hard backup restore" if args.hard else "surgical unpatch"
        for kind, out_path in restored:
            print(f"[{PROJECT_NAME} v{VERSION}] Restored {kind} ({mode}): {out_path}")
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
