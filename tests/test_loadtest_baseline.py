"""The load-test baseline file (tools/loadtest.py --record): rows are read back and compared."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import loadtest
except ImportError:  # no Streamlit (the base Python 3.8)
    loadtest = None
finally:
    sys.path.pop(0)


def row(cpu="30", answered="100", p50="8.0", per_poll="3.0", page="70.0", machine="M1", options="-"):
    return ["2026-11-19", "abc1234", machine, "3.9 / 1.48", "100 every 1 s", "200", cpu,
            f"100 / {answered}", f"{p50} / 20.0", per_poll, page, "50", options]


@unittest.skipIf(loadtest is None, "Streamlit is not installed")
class TestBaselineFile(unittest.TestCase):
    def test_rows_are_written_and_read_back(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "LOADTEST.md")
            loadtest.record(path, row())
            loadtest.record(path, row(cpu="31"))
            self.assertEqual([r[6] for r in loadtest.read_rows(path)], ["30", "31"])

    def test_the_repository_file_parses(self):
        rows = loadtest.read_rows(os.path.join(ROOT, "docs", "LOADTEST.md"))
        self.assertTrue(rows)
        self.assertTrue(all(len(r) == len(loadtest.COLUMNS) for r in rows))

    def test_a_slower_release_is_flagged(self):
        same = loadtest.compare(row(cpu="31"), [row()])
        self.assertIn("No slowdown.", same[-1])
        slower = loadtest.compare(row(cpu="45", answered="70"), [row()])
        self.assertIn("WORSE", "\n".join(slower))
        self.assertIn("look into it", slower[-1])

    def test_only_comparable_rows_count(self):
        lines = loadtest.compare(row(machine="Cloud"), [row()])
        self.assertIn("No earlier row", lines[0])
        lines = loadtest.compare(row(options="runner.postScriptGC=true"), [row()])
        self.assertIn("No earlier row", lines[0])


if __name__ == "__main__":
    unittest.main()
