# coding: utf-8
"""Tests for the AST/lexical JS UI string extractor."""

import unittest

from ag_i18n.extractor import extract_ui_strings_from_js


SAMPLE_MINIFIED_JS = r'''
const btn = e.createElement("button", {
  onClick: () => runCommand(),
  "aria-label": "Project Settings"
}, "Change\u2026");

const card = e.createElement(Panel, {
  description: k
    ? "Configure allowed and denied URLs for the browser subagent. It runs in the built-in browser, so no separate browser install is needed."
    : e.createElement(Sub, null, "Enable Browser Tool"),
  title: `Open workspace`,
  className: "flex items-center gap-2 text-sm",
  url: "https://example.com/docs"
}, "Verbose");
'''


class ExtractorTests(unittest.TestCase):
    def test_extracts_nested_props_ternaries_and_unicode_escapes(self):
        strings, _ = extract_ui_strings_from_js(SAMPLE_MINIFIED_JS)
        self.assertIn("Change\u2026", strings)
        self.assertIn("Project Settings", strings)
        self.assertIn("Enable Browser Tool", strings)
        self.assertIn("Verbose", strings)
        self.assertIn(
            "Configure allowed and denied URLs for the browser subagent. "
            "It runs in the built-in browser, so no separate browser install is needed.",
            strings,
        )
        # Non-UI Tailwind classes and external URLs must be filtered out
        self.assertNotIn("flex items-center gap-2 text-sm", strings)
        self.assertNotIn("https://example.com/docs", strings)

    def test_menu_mode_captures_electron_dialogs(self):
        electron_js = r'''
        dialog.showMessageBox(win, {
            type: 'question',
            buttons: ['Cancel', 'Quit'],
            title: 'Confirm Quit',
            message: 'Are you sure you want to quit?',
        });
        '''
        _, strings = extract_ui_strings_from_js(electron_js)
        self.assertIn("Cancel", strings)
        self.assertIn("Quit", strings)
        self.assertIn("Confirm Quit", strings)
        self.assertIn("Are you sure you want to quit?", strings)


if __name__ == "__main__":
    unittest.main()
