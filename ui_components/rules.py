"""The rules on the web page: the text is the game's own (abaka/rules.py), shown as Markdown."""

import streamlit as st

from abaka.i18n import t
from abaka.rules import RULES_MD, RULES_MD_RU, rules_md  # noqa: F401 (RULES_MD*: older imports)


def rules_dialog() -> None:
    """Open the rules in a dialog (its title is in the page's language)."""
    @st.dialog(t("How to play"), width="large")
    def _show() -> None:
        st.markdown(rules_md())
    _show()
