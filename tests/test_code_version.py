"""
code_version: the app reloads the game's modules when their files changed on disk
(a commit pulled by Streamlit Cloud while no browser had the app open).
"""

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import code_version


def own_modules():
    return {n: m for n, m in sys.modules.items() if n.split(".")[0] in code_version.PACKAGES}


class TestLoadCurrent(unittest.TestCase):
    def setUp(self):
        import abaka.engine  # noqa: F401  (make sure the package is loaded)
        saved = own_modules()

        def restore():  # other tests keep using the modules they imported
            for name in own_modules():
                del sys.modules[name]
            sys.modules.update(saved)

        self.addCleanup(restore)

    def test_unchanged_files_keep_the_loaded_modules(self):
        engine = sys.modules["abaka.engine"]
        code_version.mark_current()
        self.assertFalse(code_version.load_current())
        self.assertIs(sys.modules["abaka.engine"], engine)

    def test_changed_files_are_loaded_again(self):
        engine = sys.modules["abaka.engine"]
        sys.modules["abaka"].code_fingerprint = "an older commit"  # the files changed after loading
        self.assertTrue(code_version.load_current())
        self.assertIsNot(importlib.import_module("abaka.engine"), engine)
        self.assertEqual(sys.modules["abaka"].code_fingerprint, code_version.fingerprint())
        self.assertFalse(code_version.load_current())  # current now: nothing more to do

    def test_modules_loaded_without_a_fingerprint_are_loaded_again(self):
        engine = sys.modules["abaka.engine"]
        if hasattr(sys.modules["abaka"], "code_fingerprint"):
            del sys.modules["abaka"].code_fingerprint
        self.assertTrue(code_version.load_current())
        self.assertIsNot(importlib.import_module("abaka.engine"), engine)


class TestFingerprint(unittest.TestCase):
    def test_changes_with_any_file_of_either_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for package, module in (("abaka", "engine.py"), ("ui_components", "dice.py")):
                (root / package).mkdir()
                (root / package / module).write_text("x = 1\n")
            (root / "notes.md").write_text("not code")
            with mock.patch.object(code_version, "APP_DIR", root):
                first = code_version.fingerprint()
                self.assertEqual(code_version.fingerprint(), first)
                (root / "notes.md").write_text("still not code")
                self.assertEqual(code_version.fingerprint(), first)
                (root / "ui_components" / "dice.py").write_text("x = 2\n")
                second = code_version.fingerprint()
                self.assertNotEqual(second, first)
                (root / "abaka" / "new.py").write_text("")
                self.assertNotEqual(code_version.fingerprint(), second)


if __name__ == "__main__":
    unittest.main()
