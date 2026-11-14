# coding: utf-8
"""Validation and coverage reporting for antigravity-i18n locale bundles."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REQUIRED_META_FIELDS = ("locale", "name", "nativeName", "direction", "punctuationStyle")
VALID_DIRECTIONS = {"ltr", "rtl"}
VALID_PUNCT_STYLES = {"ascii", "cjk"}
PLACEHOLDER_RE = re.compile(r"\$\d+|\{[A-Za-z0-9_]+\}")


@dataclass
class LocaleReport:
    """Validation summary for one locale JSON file."""

    file_name: str
    locale: str = ""
    name: str = ""
    native_name: str = ""
    exact_count: int = 0
    menu_count: int = 0
    pattern_count: int = 0
    missing_exact: List[str] = field(default_factory=list)
    missing_patterns: int = 0
    empty_values: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def coverage_percent(self, baseline_exact_count: int) -> float:
        if baseline_exact_count <= 0:
            return 100.0
        covered = max(0, baseline_exact_count - len(self.missing_exact))
        return round((covered * 100.0) / baseline_exact_count, 2)


def _extract_placeholders(text: str) -> List[str]:
    return sorted(PLACEHOLDER_RE.findall(text))


def load_template_keys(locales_dir: Path) -> Tuple[Set[str], int]:
    """Return baseline exact keys and pattern count from _template.json if present."""
    tpl_path = locales_dir / "_template.json"
    if not tpl_path.is_file():
        return set(), 0
    data = json.loads(tpl_path.read_text(encoding="utf-8"))
    exact = data.get("exact", {})
    patterns = data.get("patterns", [])
    return set(exact.keys()), len(patterns)


def validate_locale_file(
    locale_path: Path,
    baseline_exact: Optional[Set[str]] = None,
    baseline_pattern_count: int = 0,
    require_full_coverage: bool = True,
) -> LocaleReport:
    """Validate structure, metadata, regex syntax, placeholders, and baseline coverage."""
    report = LocaleReport(file_name=locale_path.name)
    try:
        raw_data = json.loads(locale_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report.errors.append(f"Invalid JSON: {exc}")
        return report

    if not isinstance(raw_data, dict):
        report.errors.append("Root JSON value must be an object.")
        return report

    meta = raw_data.get("meta")
    if not isinstance(meta, dict):
        report.errors.append("Missing or invalid 'meta' object.")
        return report

    for field_name in REQUIRED_META_FIELDS:
        val = meta.get(field_name)
        if not isinstance(val, str) or not val.strip():
            report.errors.append(f"Missing required meta.{field_name}")

    report.locale = str(meta.get("locale", ""))
    report.name = str(meta.get("name", ""))
    report.native_name = str(meta.get("nativeName", ""))

    direction = meta.get("direction", "ltr")
    if direction not in VALID_DIRECTIONS:
        report.errors.append(f"Invalid meta.direction: {direction!r}")

    punct = meta.get("punctuationStyle", "ascii")
    if punct not in VALID_PUNCT_STYLES:
        report.errors.append(f"Invalid meta.punctuationStyle: {punct!r}")

    exact = raw_data.get("exact", {})
    if not isinstance(exact, dict):
        report.errors.append("'exact' must be an object mapping English -> localized strings.")
        exact = {}
    else:
        for k, v in exact.items():
            if not isinstance(v, str) or not v.strip():
                report.empty_values.append(f"exact[{k!r}]")
        report.exact_count = len(exact)

    menu = raw_data.get("menu", {})
    if menu is not None and not isinstance(menu, dict):
        report.errors.append("'menu' must be an object if provided.")
    elif isinstance(menu, dict):
        for k, v in menu.items():
            if not isinstance(v, str) or not v.strip():
                report.empty_values.append(f"menu[{k!r}]")
        report.menu_count = len(menu)

    patterns = raw_data.get("patterns", [])
    if not isinstance(patterns, list):
        report.errors.append("'patterns' must be a list of [regex, flags, replacement] tuples.")
        patterns = []
    else:
        report.pattern_count = len(patterns)
        for idx, pat in enumerate(patterns):
            if not isinstance(pat, list) or len(pat) not in (2, 3):
                report.errors.append(f"patterns[{idx}] must have length 2 or 3.")
                continue
            regex_src = pat[0]
            flags_str = pat[1] if len(pat) == 3 else ""
            repl = pat[-1]
            if not isinstance(regex_src, str) or not regex_src:
                report.errors.append(f"patterns[{idx}] regex source must be a non-empty string.")
                continue
            if not isinstance(flags_str, str) or any(ch not in "imsux" for ch in flags_str):
                report.errors.append(f"patterns[{idx}] has unsupported JS/Python flags: {flags_str!r}")
            if not isinstance(repl, str):
                report.errors.append(f"patterns[{idx}] replacement must be a string.")
                continue
            re_flags = re.IGNORECASE if "i" in flags_str else 0
            try:
                compiled = re.compile(regex_src, re_flags)
            except re.error as exc:
                report.errors.append(f"patterns[{idx}] invalid regex {regex_src!r}: {exc}")
                continue
            # Check capture group bounds ($1..$9) against regex group count
            group_refs = [int(m) for m in re.findall(r"\$(\d+)", repl)]
            if any(ref > compiled.groups for ref in group_refs):
                report.errors.append(
                    f"patterns[{idx}] replacement references ${max(group_refs)}, "
                    f"but regex only defines {compiled.groups} capture group(s)."
                )

    if report.empty_values:
        sample = ", ".join(report.empty_values[:5])
        report.errors.append(f"Found {len(report.empty_values)} empty translation value(s): {sample}")

    is_english_source = report.locale.lower().startswith("en") or locale_path.name.startswith("_")
    if baseline_exact and not is_english_source:
        missing = sorted(baseline_exact - set(exact.keys()))
        report.missing_exact = missing
        if missing:
            msg = f"Missing {len(missing)}/{len(baseline_exact)} baseline keys from _template.json"
            if require_full_coverage:
                report.errors.append(msg)
            else:
                report.warnings.append(msg)

    if baseline_pattern_count > 0 and not is_english_source:
        if report.pattern_count < baseline_pattern_count:
            report.missing_patterns = baseline_pattern_count - report.pattern_count
            msg = f"Expected {baseline_pattern_count} patterns matching _template.json, found {report.pattern_count}"
            if require_full_coverage:
                report.errors.append(msg)
            else:
                report.warnings.append(msg)

    # Check placeholder mismatch between English keys and values for non-template bundles
    if not locale_path.name.startswith("_"):
        for k, v in exact.items():
            k_ph = _extract_placeholders(k)
            if k_ph and _extract_placeholders(v) != k_ph:
                report.warnings.append(f"Placeholder mismatch for {k!r}: expected {k_ph}")

    return report


def validate_locales_dir(
    locales_dir: Path,
    require_full_coverage: bool = True,
) -> Tuple[List[LocaleReport], int]:
    """Validate all non-template locale JSON files under locales_dir."""
    baseline_exact, baseline_patterns = load_template_keys(locales_dir)
    reports: List[LocaleReport] = []
    if not locales_dir.is_dir():
        return reports, 0

    for path in sorted(locales_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        reports.append(
            validate_locale_file(
                path,
                baseline_exact=baseline_exact,
                baseline_pattern_count=baseline_patterns,
                require_full_coverage=require_full_coverage,
            )
        )
    return reports, len(baseline_exact)
