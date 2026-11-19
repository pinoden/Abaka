"""Short, player-facing rules, matching the engine in abaka/, in English and Russian."""

import streamlit as st

from ui_components.i18n import get_language, t

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
| Pair | two of a number (also in any of the combinations below) | the highest pair |
| Two pairs | two pairs (four of a kind counts) | both pairs |
| Three of a kind | three of a number | the three |
| Small straight | exactly 1-2-3-4-5 | 15 |
| Large straight | exactly 2-3-4-5-6 | 20 |
| Full house | three of one number + two of another, or five of a kind | all dice (1-1-1-2-2: +50) |
| Four of a kind | four of a number | the four + 20 |
| Abaka | all five the same | all dice + 50 |
| Sum | anything | all dice |

Scoring a combination on your **first roll** (no rerolls) doubles it.
If your dice don't fit anything you want, **cross out** a combination cell instead.
That gives up the row's bonus and that column's bonus for you: both bonus cells are
crossed out at once.

**School (rows 1-6).** Three dice of the row's number is par. Each extra die adds
that number to your **school balance**; each missing die is paid from it. Paying
from the balance gives up that row's bonus: its bonus cell is crossed out at once. You
need at least one die of the number until all your combinations are filled. Ending with a negative balance costs 100 points
per point below zero.

**Bonuses.** The first player to complete a row decides its bonus: 3 x the number
for school rows, the best cell for combinations, nothing if they crossed out a
cell in it or paid from the balance in it. A column with no crossed-out combinations
awards its best value. The first player to complete a row or column I or II closes
that bonus for everyone else, even if they earn nothing. Each player can earn
their own bonus for column III.

**The end.** When every cell is filled, the highest total wins.
"""

RULES_MD_RU = """
**Игроки.** От 2 до 5, ходят по очереди.

**Кто начинает.** Перед первым кругом каждый игрок бросает все пять кубиков. Первым
ходит тот, у кого сумма меньше (кубики считаются по выпавшему числу); если наименьшая
сумма у нескольких игроков, они бросают ещё раз. Дальше ходы идут по кругу.

**Ваш ход.** Бросьте пять кубиков: четыре белых и один тёмный — **джокер**. Любые из них
(или все) можно перебросить ещё до двух раз. Затем запишите бросок в одну строку. В каждой
строке три клетки, они заполняются слева направо.

**Джокер** с единицей — «любой»: он считается тем числом, которое вам выгоднее.

**Комбинации**

| Строка | Что нужно | Очки |
|---|---|---|
| Пара | два одинаковых числа (в любой из комбинаций ниже тоже) | сумма старшей пары |
| Две пары | две пары (каре тоже) | сумма обеих пар |
| Тройка | три одинаковых числа | сумма трёх |
| Малый стрит | ровно 1-2-3-4-5 | 15 |
| Большой стрит | ровно 2-3-4-5-6 | 20 |
| Фулл-хаус | три одного числа + два другого, или пять одинаковых | сумма всех кубиков (1-1-1-2-2: +50) |
| Каре | четыре одинаковых числа | сумма четырёх + 20 |
| Абака | все пять одинаковые | сумма всех кубиков + 50 |
| Сумма | что угодно | сумма всех кубиков |

Комбинация, записанная с **первого броска** (без перебросов), считается вдвойне.
Если кубики ни во что не подходят, можно **зачеркнуть** клетку комбинации.
Тогда вы теряете бонус этой строки и бонус этого столбца: обе клетки бонусов
сразу зачёркиваются.

**Школа (строки 1-6).** Три кубика с числом строки — норма. Каждый лишний кубик добавляет
это число к **балансу школы**; каждый недостающий оплачивается из баланса. Оплата из баланса
лишает вас бонуса этой строки: его клетка сразу зачёркивается. Пока не заполнены все ваши
комбинации, нужен хотя бы один кубик с числом строки. Если в конце баланс отрицательный,
каждое очко ниже нуля стоит 100 очков.

**Бонусы.** Бонус строки определяет тот, кто первым её заполнит: 3 × число строки для школы,
лучшая клетка для комбинаций и ничего, если в этой строке игрок что-то зачеркнул или платил
из баланса. Столбец без зачёркнутых комбинаций приносит бонус, равный его лучшему значению.
Как только кто-то заполняет строку или столбец I или II, бонус у остальных зачёркивается,
даже если первый игрок ничего не получил. Бонус столбца III каждый игрок зарабатывает сам.

**Конец игры.** Когда все клетки заполнены, побеждает тот, у кого больше очков.
"""


def rules_md() -> str:
    """The rules in the page's language."""
    return RULES_MD_RU if get_language() == "ru" else RULES_MD


def rules_dialog() -> None:
    """Open the rules in a dialog (its title is in the page's language)."""
    @st.dialog(t("How to play"), width="large")
    def _show() -> None:
        st.markdown(rules_md())
    _show()
