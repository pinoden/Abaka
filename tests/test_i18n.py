"""
Russian interface text: every text the code passes to t() has a Russian version with the
same {placeholders}, every error the rooms can show is translated, and plurals are right.
"""

import ast
import re
import string
import unittest
from pathlib import Path

from abaka.models import Category
from abaka.rooms import RoomStore
from abaka import i18n
from abaka.i18n import RU, error, players_count, reroll_dice, rerolls_left, set_language, t
from abaka.moves import ROW_HINTS, _COMBO_NAMES, Move, row_hint, row_name

ROOT = Path(__file__).resolve().parent.parent
# The web app, and the game package (move texts, and the API that gives them to apps).
UI_FILES = ([ROOT / "abaka_ui.py"] + sorted((ROOT / "ui_components").glob("*.py"))
            + sorted((ROOT / "abaka").glob("*.py")))


def texts_passed_to_t():
    """Every string literal passed as the first argument of t(...) in the code players see."""
    found = {}
    for path in UI_FILES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "t"
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                found.setdefault(node.args[0].value, f"{path.name}:{node.lineno}")
    return found


def fields(template):
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


class TestRussianText(unittest.TestCase):
    def tearDown(self):
        set_language("en")

    def test_every_text_has_a_russian_version(self):
        texts = texts_passed_to_t()
        self.assertGreater(len(texts), 100)  # the scan found the code's texts
        missing = {text: where for text, where in texts.items() if text not in RU}
        self.assertEqual(missing, {})
        try:
            from ui_components.effects import REACTIONS  # needs Streamlit
            labels = [label for _, label in REACTIONS.values()]
        except ImportError:
            labels = []
        for text in list(_COMBO_NAMES.values()) + list(ROW_HINTS.values()) + labels:  # passed to t() through variables
            self.assertIn(text, RU)

    def test_placeholders_match(self):
        for english, russian in RU.items():
            self.assertEqual(fields(english), fields(russian), english)

    def test_room_errors_are_translated(self):
        source = (ROOT / "abaka" / "rooms.py").read_text(encoding="utf-8")
        messages = set(re.findall(r'RoomError\("([^"{]+)"\)', source))
        self.assertGreater(len(messages), 10)
        set_language("ru")
        for message in messages:
            self.assertNotEqual(error(message), message, message)
        self.assertEqual(error("Not enough school balance to write this row (need 6, have 2)"),
                         "Не хватает баланса школы для этой строки (нужно 6, есть 2).")
        with self.assertRaises(Exception) as caught:
            RoomStore().create("Ann", players=9)
        self.assertNotEqual(error(str(caught.exception)), str(caught.exception))

    def test_plurals(self):
        set_language("ru")
        self.assertEqual([rerolls_left(n) for n in (1, 2, 5)], ["1 переброс", "2 переброса", "5 перебросов"])
        self.assertEqual([reroll_dice(n) for n in (1, 3, 5)],
                         ["Перебросить 1 кубик", "Перебросить 3 кубика", "Перебросить 5 кубиков"])
        self.assertEqual(players_count(4), "4 игрока")
        set_language("en")
        self.assertEqual([rerolls_left(n) for n in (1, 2)], ["1 reroll", "2 rerolls"])
        self.assertEqual([reroll_dice(n) for n in (1, 2)], ["Reroll 1 die", "Reroll 2 dice"])

    def test_moves_in_russian(self):
        set_language("ru")
        self.assertEqual(row_name(Category.SCHOOL_4), "Школа 4")
        self.assertEqual(row_name(Category.KARE), "Каре")
        self.assertIn("бонус этой строки зачёркивается", row_hint(Category.SCHOOL_2))
        pay = Move(Category.SCHOOL_4, 0, False, 6, -4, bonus_lost=True)
        self.assertEqual(pay.action_text, "Записать «Школа 4» (−4 из баланса, бонус строки сгорает)")
        self.assertEqual(Move(Category.SUM, 0, False, 23).action_text, "Записать 23 в «Сумма»")
        self.assertEqual(Move(Category.PAIR, 1, True, "X").action_text, "Зачеркнуть «Пара»")
        set_language("en")
        self.assertEqual(pay.action_text, "Write School 4 (pay 4 from balance, lose the row bonus)")

    def test_language_is_per_thread(self):
        import threading
        set_language("ru")
        seen = []
        other = threading.Thread(target=lambda: seen.append(t("Roll dice")))
        other.start()
        other.join()
        self.assertEqual(seen, ["Roll dice"])  # another session's thread is not affected
        self.assertEqual(t("Roll dice"), "Бросить кубики")
        self.assertEqual(i18n.get_language(), "ru")


if __name__ == "__main__":
    unittest.main()
