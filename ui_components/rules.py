"""Short, player-facing rules, matching the engine in abaka/."""

import streamlit as st

RULES_MD = """
**Players.** 2 to 5, taking turns in order.

**Who starts.** Before the first round, each player throws all five dice. The lowest
total goes first (dice count their face value); players who tie for the lowest throw
again. Then turns go round the table.

**Your turn.** Roll five dice: four white and one dark **joker**. You may roll any
of them again (or all of them), up to two more times. Then write the roll into one row. Each row
has three cells that fill from left to right.

**The joker** is wild when it shows 1: it counts as whatever number helps you most.

**Combinations**

| Row | Needs | Scores |
|---|---|---|
| Pair | two of a number | the pair |
| Two pairs | two different pairs | both pairs |
| Three of a kind | three of a number | the three |
| Small straight | exactly 1-2-3-4-5 | 15 |
| Large straight | exactly 2-3-4-5-6 | 20 |
| Full house | three of one number + two of another | all dice (1-1-1-2-2: +50) |
| Four of a kind | four of a number | the four + 20 |
| Abaka | all five the same | all dice + 50 |
| Sum | anything | all dice |

Scoring a combination on your **first roll** (no rerolls) doubles it.
If your dice don't fit anything you want, **cross out** a combination cell instead.
That gives up the row's bonus and that column's bonus for you.

**School (rows 1-6).** Three dice of the row's number is par. Each extra die adds
that number to your **school balance**; each missing die is paid from it. You
need at least one die of the number until all your combinations are filled. Ending with a negative balance costs 100 points
per point below zero.

**Bonuses.** The first player to complete a row decides its bonus: 3 x the number
for school rows, the best cell for combinations, nothing if they crossed out a
cell in it. Complete a column with no crossed-out combinations for its best value;
columns I and II go only to the first player to complete them.

**The end.** When every cell is filled, the highest total wins.
"""


@st.dialog("How to play", width="large")
def rules_dialog() -> None:
    st.markdown(RULES_MD)
