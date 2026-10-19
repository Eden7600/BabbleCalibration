"""Check the shipped overlay table without Godot or external Python packages."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import string
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OverlayLocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = json.loads((ROOT / 'translations.review.json').read_text(encoding='utf-8'))
        cls.text = (ROOT / 'translations.csv').read_text(encoding='utf-8')
        reader = csv.DictReader(io.StringIO(cls.text))
        cls.columns = reader.fieldnames
        cls.rows = list(reader)
        cls.by_key = {row['keys']: row for row in cls.rows}

    def test_table_is_complete_and_valid_utf8(self):
        self.assertEqual(['keys'] + self.review['locales'], self.columns)
        self.assertEqual(29, len(self.review['locales']))
        self.assertEqual(len(self.rows), len(self.by_key))
        self.assertNotIn('\ufffd', self.text)
        for row in self.rows:
            self.assertEqual(set(self.columns), set(row))
            for locale in self.review['locales']:
                self.assertTrue(row[locale] and row[locale].strip(), (row['keys'], locale))

    def test_format_placeholders_match_source_for_every_locale(self):
        def fields(value):
            return sorted((name, spec, conversion) for _, name, spec, conversion
                          in string.Formatter().parse(value) if name is not None)
        for row in self.rows:
            expected = fields(row['en'])
            for locale in self.review['locales']:
                self.assertEqual(expected, fields(row[locale]), (row['keys'], locale))
                row[locale].format(3, 10)  # Exercise the actual positional format syntax.

    def test_changed_and_restored_prompts_do_not_silently_fall_back_to_english(self):
        keys = self.review['new_keys'] + self.review['revised_keys'] + self.review['restored_existing_keys']
        for key in keys:
            row = self.by_key[key]
            for locale in self.review['locales']:
                if locale != 'en':
                    self.assertNotEqual(row['en'], row[locale], (key, locale))

    def test_concise_prompts_and_shared_briefing_survive_csv_round_trip(self):
        capture_keys = {key for key in self.by_key if key.startswith('CaptureInstruction')}
        expected_keys = capture_keys | {'GazeTutorial', 'GazeTutorialShort',
                                        'FreshCheckComplete', 'TrainingFailed'}
        self.assertEqual(expected_keys, set(self.review['concise_prompt_keys']))
        for key in expected_keys:
            for locale in self.review['locales']:
                text = self.by_key[key][locale]
                self.assertLessEqual(len(text.split()), 30, (key, locale))
                self.assertEqual(1, len(text.splitlines()), (key, locale))
                # These prompts contain no abbreviations or decimal numbers. Include
                # East Asian and Arabic sentence marks; semicolons join clauses.
                sentences = [part.strip() for part in re.split(r'[.!?。！？؟]+', text) if part.strip()]
                self.assertTrue(1 <= len(sentences) <= 2, (key, locale))
                self.assertRegex(text, r'[.!?。！？؟]$', (key, locale))
                self.assertNotIn('{', text, (key, locale))
                self.assertNotIn('}', text, (key, locale))
        for locale in self.review['locales']:
            self.assertEqual(self.by_key['GazeTutorial'][locale], self.by_key['GazeTutorialShort'][locale], locale)
        for key in capture_keys:
            self.assertLessEqual(len(self.by_key[key]['en'].split()), 11, key)
            self.assertNotRegex(self.by_key[key]['en'].lower(),
                                r'tone|countdown|read now|text disappears|target|head|ring', key)
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=self.columns)
        writer.writeheader()
        writer.writerows(self.rows)
        self.assertEqual(self.rows, list(csv.DictReader(io.StringIO(stream.getvalue()))))

    def test_existing_valid_translations_are_preserved_and_review_status_is_honest(self):
        for key, expected in self.review['preserved_row_sha256'].items():
            locales = [locale for locale in self.review['locales']
                       if expected['locales'] == 'all' or locale != 'en']
            values = [self.by_key[key][locale] for locale in locales]
            digest = hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(expected['sha256'], digest, key)
        self.assertEqual([], self.review['human_reviewed_locales'])
        self.assertIn('not reviewed', self.review['translation_method'])


if __name__ == '__main__':
    unittest.main()
