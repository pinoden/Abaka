"""
The phone app's texts (mobile/): the export of abaka/i18n.py the app reads
(mobile/src/texts.json, written by tools/export_texts.py) is up to date, and every text
the app passes to t("...") has a Russian version, as tests/test_i18n.py checks for the
web app. Needs no Node, so it runs in every CI job, Python 3.8 included.
"""

import re
import sys
import unittest
from pathlib import Path

from abaka.i18n import RU

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
try:
    import export_texts
finally:
    sys.path.pop(0)

SOURCES = ROOT / "mobile" / "src"
# t('...') or t("..."): the first argument, when it is a string literal.
T_CALL = re.compile(r"""\bt\(\s*(?:'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)")""")
# Comments, which may show t() in examples: /* ... */ blocks and whole // lines.
COMMENTS = re.compile(r"/\*.*?\*/|^\s*//[^\n]*", re.DOTALL | re.MULTILINE)


def texts_passed_to_t():
    found = {}
    for path in sorted(SOURCES.rglob("*.ts*")):
        # Blank out comments, keeping their line breaks so line numbers stay right.
        source = COMMENTS.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), path.read_text(encoding="utf-8"))
        for match in T_CALL.finditer(source):
            text = match.group(1) if match.group(1) is not None else match.group(2)
            line = source.count("\n", 0, match.start()) + 1
            found.setdefault(text, f"{path.relative_to(ROOT)}:{line}")
    return found


class TestMobileTexts(unittest.TestCase):
    def test_the_export_is_up_to_date(self):
        current = export_texts.OUT.read_text(encoding="utf-8")
        self.assertEqual(current, export_texts.export(),
                         "mobile/src/texts.json is out of date: run python tools/export_texts.py")

    def test_every_text_has_a_russian_version(self):
        texts = texts_passed_to_t()
        self.assertGreater(len(texts), 50)  # the scan found the app's texts
        missing = {text: where for text, where in texts.items() if text not in RU}
        self.assertEqual(missing, {}, "add these to abaka/i18n.py, then run python tools/export_texts.py")

    def test_the_scan_reads_both_quotes(self):
        sample = """t('Score') + t("Join a friend's game") + t( 'Roll {n} of 3', { n })"""
        self.assertEqual([m.group(1) or m.group(2) for m in T_CALL.finditer(sample)],
                         ["Score", "Join a friend's game", "Roll {n} of 3"])


if __name__ == "__main__":
    unittest.main()
