# coding: utf-8
"""Validation tests for all bundled locale JSON packs."""

import json
import subprocess
import unittest

from ag_i18n.paths import LOCALES_DIR, REPO_ROOT
from ag_i18n.validator import validate_locales_dir

EXPECTED_LOCALES = {
    "en-US",
    "zh-CN",
    "zh-TW",
    "ja",
    "ko",
    "es",
    "fr",
    "de",
    "pt-BR",
    "ru",
}


class LocaleValidationTests(unittest.TestCase):
    def test_all_mainstream_locales_exist_and_pass_validation(self):
        reports, baseline_count = validate_locales_dir(LOCALES_DIR, require_full_coverage=True)
        present = {r.locale for r in reports}
        missing_packs = sorted(EXPECTED_LOCALES - present)
        self.assertEqual(missing_packs, [], f"Missing mainstream locale packs: {missing_packs}")
        self.assertGreater(baseline_count, 3000)

        failures = [f"{r.file_name}: {r.errors}" for r in reports if not r.ok]
        self.assertEqual(failures, [], f"Locale validation errors: {failures}")

    def test_node_core_loads_and_translates_every_locale(self):
        script = r"""
const fs = require('fs');
const path = require('path');
const core = require('./runtime/core');

const dir = './locales';
const out = {};
for (const file of fs.readdirSync(dir)) {
  if (!file.endsWith('.json') || file.startsWith('_')) continue;
  const bundle = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
  const t = core.createTranslator(bundle);
  out[bundle.meta.locale] = {
    projectSettings: t.translate('Project Settings', { context: 'menu' }),
    changeEllipsis: t.translate('Change\u2026'),
    worked: t.translate('Worked for 5s')
  };
}
console.log(JSON.stringify(out));
"""
        proc = subprocess.run(
            ["node", "-"],
            input=script,
            cwd=str(REPO_ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        res = json.loads(proc.stdout.strip().splitlines()[-1])
        for loc in EXPECTED_LOCALES:
            self.assertIn(loc, res)
            if loc != "en-US":
                self.assertNotEqual(res[loc]["projectSettings"], "Project Settings", f"{loc} did not translate Project Settings")
                self.assertNotEqual(res[loc]["changeEllipsis"], "Change\u2026", f"{loc} did not translate Change...")


if __name__ == "__main__":
    unittest.main()
