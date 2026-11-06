"""Validate translation resources before Home Assistant loads them."""

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1] / "custom_components" / "freshpoint"


class TranslationTests(unittest.TestCase):
    def test_translation_leaves_are_strings(self):
        """Null names crash Home Assistant's translation loader."""
        def check_leaves(value, path):
            if isinstance(value, dict):
                for key, child in value.items():
                    check_leaves(child, f"{path}.{key}")
            else:
                with self.subTest(path=path):
                    self.assertIsInstance(value, str)

        for resource in [ROOT / "strings.json", *sorted((ROOT / "translations").glob("*.json"))]:
            check_leaves(json.loads(resource.read_text()), str(resource.relative_to(ROOT)))

    def test_english_matches_source(self):
        self.assertEqual(
            json.loads((ROOT / "strings.json").read_text()),
            json.loads((ROOT / "translations/en.json").read_text()),
        )
