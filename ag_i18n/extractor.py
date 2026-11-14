# coding: utf-8
"""Lexical & structural UI string extractor for Antigravity Desktop bundles and Electron dist."""

import gzip
import hashlib
import re
from pathlib import Path
from typing import Iterable, List, Set, Tuple

from .asar import read_asar_header
from .paths import get_browser_cache_dir


UI_PROP_NAMES = {
    "label",
    "title",
    "description",
    "placeholder",
    "subtitle",
    "heading",
    "tooltip",
    "emptyText",
    "buttonText",
    "confirmText",
    "cancelText",
    "header",
    "caption",
    "aria-label",
    "ariaLabel",
    "buttons",
    "message",
    "detail",
    "resolveOptionToString",
    "optionLabel",
    "helperText",
    "errorMessage",
    "badge",
}

DIALOG_CALL_NAMES = (
    "showMessageBox",
    "showMessageBoxSync",
    "showOpenDialog",
    "showOpenDialogSync",
    "showSaveDialog",
    "showSaveDialogSync",
    "MenuItem",
)

CSS_CLASS_HINTS = re.compile(
    r"\b(?:flex|inline-flex|grid|items-|justify-|text-|bg-|px-|py-|pt-|pb-|pl-|pr-|"
    r"mt-|mb-|ml-|mr-|mx-|my-|w-|h-|min-w-|max-w-|gap-|rounded|border-|shrink-0|overflow-|cursor-)\b"
)

_HEX_OR_TECH_RE = re.compile(
    r"^(?:#[0-9a-fA-F]{3,8}|[0-9]+(?:\.[0-9]+)*(?:px|em|rem|%|ms|s)?|"
    r"exa\.[A-Za-z0-9_.]+|vscode-[A-Za-z0-9_-]+|[a-z0-9]+(?:-[a-z0-9]+)+)$"
)


def decode_js_string(raw: str) -> str:
    """Decode JS string escapes (including \\uXXXX and \\xXX) safely without crashing."""
    def _repl(match: re.Match) -> str:
        esc = match.group(1)
        if esc == "n":
            return "\n"
        if esc == "r":
            return "\r"
        if esc == "t":
            return "\t"
        if esc.startswith("u") and len(esc) == 5:
            return chr(int(esc[1:], 16))
        if esc.startswith("x") and len(esc) == 3:
            return chr(int(esc[1:], 16))
        return esc

    return re.sub(r"\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)", _repl, raw)


def looks_like_ui_text(text: str) -> bool:
    """Return True if text appears to be natural-language UI copy rather than code/CSS."""
    s = text.strip()
    if not s or len(s) < 2 or len(s) > 240 or "\n" in s:
        return False
    if "https://" in s or "http://" in s or s.startswith(("./", "../", "/", "~/", "$")):
        return False
    if "{" in s or "}" in s or "<" in s or ">" in s or "===" in s:
        return False
    if _HEX_OR_TECH_RE.match(s) or CSS_CLASS_HINTS.search(s):
        return False
    if " " not in s:
        # Single token: capitalized UI word, optionally ending with ellipsis or punctuation.
        return bool(re.match(r"^[A-Z][A-Za-z\-]{1,28}(?:\u2026|\.\.\.|:|\?)?$", s))
    return bool(re.search(r"[A-Za-z]{2,}", s))


def extract_ui_strings_from_js(code: str) -> Tuple[Set[str], Set[str]]:
    """
    Scan minified or source JS with a lightweight delimiter stack.

    Captures:
    - String literals inside `createElement(tag, props, ...children)` (arg index >= 2)
    - String literals inside UI object property values (including ternaries / arrays / arrow fns)
    - Menu/dialog strings when scanning Electron JS files
    """
    n = len(code)
    i = 0
    ui_strings: Set[str] = set()
    menu_strings: Set[str] = set()

    # Stack frames:
    #   ("call", name, arg_index)
    #   ("brace", active_prop_name_or_None)
    #   ("bracket", None)
    #   ("paren", None)
    stack: List[Tuple[str, object, int]] = []
    pending_prop: str | None = None
    last_ident = ""
    prev_non_ws = ""

    def active_ui_prop() -> str | None:
        if pending_prop in UI_PROP_NAMES:
            return pending_prop
        for kind, val, _ in reversed(stack):
            if kind in ("brace", "bracket") and val in UI_PROP_NAMES:
                return str(val)
            if kind == "call" and str(val) == "createElement":
                return None
        return None

    def in_create_element_children() -> bool:
        for kind, val, arg_idx in reversed(stack):
            if kind == "call":
                if val == "createElement" and arg_idx >= 2:
                    return True
                return False
            if kind == "brace":
                return False
        return False

    def in_dialog_or_menu_prop() -> bool:
        prop = active_ui_prop()
        if prop in {"label", "title", "message", "detail", "buttons", "cancelText", "confirmText"}:
            return True
        for kind, val, _ in reversed(stack):
            if kind == "call" and val in DIALOG_CALL_NAMES:
                return True
        return False

    while i < n:
        ch = code[i]

        # If currently inside static part of a backtick template literal (not inside ${...})
        if stack and stack[-1][0] == "template":
            if ch == "\\":
                i += 2
                continue
            if ch == "$" and i + 1 < n and code[i + 1] == "{":
                stack.append(("template_expr", None, 0))
                prev_non_ws = "{"
                last_ident = ""
                i += 2
                continue
            if ch == "`":
                stack.pop()
                prev_non_ws = "`"
                last_ident = ""
                i += 1
                continue
            i += 1
            continue

        if ch in " \t\r\n":
            i += 1
            continue

        # Skip line/block comments or single-line regex literals cleanly
        if ch == "/" and i + 1 < n:
            nxt = code[i + 1]
            if nxt == "/":
                end = code.find("\n", i + 2)
                i = n if end == -1 else end + 1
                continue
            if nxt == "*":
                end = code.find("*/", i + 2)
                i = n if end == -1 else end + 2
                continue
            if (
                prev_non_ws in ("", "(", ",", "=", ":", "[", "!", "&", "|", "?", ";", "{", "}", "~", "+", "-", "*", "%", "^", "<", ">", "/", "`")
                or last_ident in ("return", "typeof", "void", "throw", "case", "in", "of", "else")
            ):
                j = i + 1
                in_class = False
                escaped = False
                closed_regex = False
                limit = min(n, i + 400)
                while j < limit:
                    c = code[j]
                    if escaped:
                        escaped = False
                    elif c == "\\":
                        escaped = True
                    elif c == "[":
                        in_class = True
                    elif c == "]":
                        in_class = False
                    elif c == "/" and not in_class:
                        j += 1
                        while j < n and code[j].isalpha():
                            j += 1
                        closed_regex = True
                        break
                    elif c in ("\n", "\r"):
                        break
                    j += 1
                if closed_regex:
                    prev_non_ws = "A"
                    last_ident = ""
                    i = j
                    continue

        if ch == "`":
            stack.append(("template", None, 0))
            last_ident = ""
            prev_non_ws = "`"
            i += 1
            continue

        # String literal
        if ch in ('"', "'"):
            quote = ch
            j = i + 1
            buf = []
            escaped = False
            while j < n:
                c = code[j]
                if escaped:
                    buf.append("\\" + c)
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == quote:
                    break
                else:
                    buf.append(c)
                j += 1
            raw = "".join(buf)

            # Check if this string is an actual object property key (`{"foo":` or `,"foo":`),
            # never confusing ternary `cond ? "truthy" : "falsy"` with a property key!
            k = j + 1
            while k < n and code[k] in " \t\r\n":
                k += 1
            if (
                k < n
                and code[k] == ":"
                and stack
                and stack[-1][0] == "brace"
                and prev_non_ws in ("{", ",")
            ):
                decoded_key = decode_js_string(raw)
                if decoded_key in UI_PROP_NAMES:
                    pending_prop = decoded_key
                prev_non_ws = ":"
                i = k + 1
                continue

            if len(raw) >= 2 and any("A" <= c <= "z" for c in raw):
                prop = active_ui_prop()
                in_child = in_create_element_children()
                if prop or in_child:
                    decoded = decode_js_string(raw).strip()
                    if looks_like_ui_text(decoded):
                        ui_strings.add(decoded)
                        if in_dialog_or_menu_prop():
                            menu_strings.add(decoded)
            last_ident = ""
            prev_non_ws = quote
            i = j + 1
            continue

        # Identifier / property label tracking
        if ch.isalpha() or ch in ("_", "$"):
            j = i + 1
            while j < n and (code[j].isalnum() or code[j] in ("_", "$")):
                j += 1
            ident = code[i:j]
            k = j
            while k < n and code[k] in " \t\r\n":
                k += 1
            if (
                k < n
                and code[k] == ":"
                and stack
                and stack[-1][0] == "brace"
                and prev_non_ws in ("{", ",")
            ):
                pending_prop = ident
                last_ident = ""
                prev_non_ws = ":"
                i = k + 1
                continue
            last_ident = ident
            prev_non_ws = "A"
            i = j
            continue

        if ch == "(":
            stack.append(("call", last_ident, 0))
            last_ident = ""
        elif ch == ")":
            if stack and stack[-1][0] in ("call", "paren"):
                stack.pop()
            last_ident = ""
        elif ch == "{":
            stack.append(("brace", pending_prop, 0))
            pending_prop = None
            last_ident = ""
        elif ch == "}":
            while stack and stack[-1][0] not in ("brace", "template_expr"):
                stack.pop()
            if stack:
                stack.pop()
            pending_prop = None
            last_ident = ""
        elif ch == "[":
            stack.append(("bracket", pending_prop, 0))
            pending_prop = None
            last_ident = ""
        elif ch == "]":
            if stack and stack[-1][0] == "bracket":
                stack.pop()
            last_ident = ""
        elif ch == ",":
            if stack:
                top_kind, top_val, arg_idx = stack[-1]
                if top_kind == "call":
                    stack[-1] = (top_kind, top_val, arg_idx + 1)
                elif top_kind == "brace":
                    stack[-1] = ("brace", None, 0)
            pending_prop = None
            last_ident = ""
        elif ch == ";":
            pending_prop = None
            last_ident = ""

        prev_non_ws = ch
        i += 1

    return ui_strings, menu_strings


def load_cached_frontend_bundles(cache_dir: Path | None = None) -> List[Tuple[str, str]]:
    """Read unique React frontend JS bundles cached by Electron from Cache_Data."""
    target = cache_dir or get_browser_cache_dir()
    if not target.is_dir():
        return []
    seen = set()
    bundles: List[Tuple[str, str]] = []
    for entry in sorted(target.iterdir(), key=lambda p: p.stat().st_size if p.is_file() else 0, reverse=True):
        if not entry.is_file() or not entry.name.startswith("f_") or entry.stat().st_size < 10000:
            continue
        raw = entry.read_bytes()
        if raw[:2] == b"\x1f\x8b":
            try:
                raw = gzip.decompress(raw)
            except Exception:
                continue
        if b"createElement(" not in raw:
            continue
        digest = hashlib.md5(raw).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        bundles.append((entry.name, raw.decode("utf-8", errors="replace")))
    return bundles


def load_electron_dist_scripts(asar_path: Path) -> List[Tuple[str, str]]:
    """Read dist/*.js files from an ASAR archive cleanly."""
    header, base_offset = read_asar_header(asar_path)
    scripts: List[Tuple[str, str]] = []

    def walk(node: dict, prefix: str) -> None:
        for name, info in node.items():
            rel = f"{prefix}/{name}" if prefix else name
            if "files" in info:
                walk(info["files"], rel)
            elif rel.startswith("dist/") and name.endswith(".js") and "offset" in info:
                with open(asar_path, "rb") as f:
                    f.seek(base_offset + int(info["offset"]))
                    text = f.read(int(info["size"])).decode("utf-8", errors="replace")
                scripts.append((rel, text))

    walk(header.get("files", {}), "")
    return scripts


def extract_all_ui_strings(
    asar_path: Path | None = None,
    cache_dir: Path | None = None,
) -> Tuple[Set[str], Set[str]]:
    """Extract UI and menu/dialog strings from both Antigravity's web cache and ASAR dist."""
    all_ui: Set[str] = set()
    all_menu: Set[str] = set()

    for _name, code in load_cached_frontend_bundles(cache_dir):
        ui, menu = extract_ui_strings_from_js(code)
        all_ui.update(ui)
        all_menu.update(menu)

    if asar_path and asar_path.is_file():
        for rel, code in load_electron_dist_scripts(asar_path):
            ui, menu = extract_ui_strings_from_js(code)
            if rel in {"dist/menu.js", "dist/tray.js", "dist/updater.js", "dist/ipcHandlers.js"} or "remote/" in rel:
                all_menu.update(ui)
            all_ui.update(ui)
            all_menu.update(menu)

    return all_ui, all_menu
