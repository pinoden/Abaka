"""
The texts of the phone app (mobile/), exported from abaka/i18n.py.

The app is written with English texts in t("..."), like the web app, and shows the
Russian versions from mobile/src/texts.json, which this writes: the Russian texts, and
the plural forms the app uses, worked out by i18n's own functions. The export is
committed, so building the app needs no Python, and tests/test_mobile_texts.py fails when
it is out of date. Texts the server sends (move labels, row names, errors) come with its
answers instead.

    python tools/export_texts.py          # write mobile/src/texts.json
    python tools/export_texts.py --check  # exit 1 if it is out of date
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from abaka import i18n  # noqa: E402

OUT = ROOT / "mobile" / "src" / "texts.json"

# Plural forms: i18n's function, and the numbers the app needs.
PLURALS = {
    "rerolls_left": (i18n.rerolls_left, range(0, 3)),
    "reroll_dice": (i18n.reroll_dice, range(1, 6)),
    "players_count": (i18n.players_count, range(2, 6)),
}


def export() -> str:
    plurals = {}
    for name, (function, numbers) in PLURALS.items():
        plurals[name] = {}
        for lang in ("en", "ru"):
            i18n.set_language(lang)
            plurals[name][lang] = {str(n): function(n) for n in numbers}
    i18n.set_language("en")
    data = {"ru": dict(sorted(i18n.RU.items())), "plurals": plurals}
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main() -> None:
    text = export()
    if "--check" in sys.argv[1:]:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            sys.exit(f"{OUT.relative_to(ROOT)} is out of date: run python tools/export_texts.py")
        print(f"{OUT.relative_to(ROOT)} is up to date")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
