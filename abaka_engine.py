import random
from enum import Enum, auto
from collections import Counter


class Category(Enum):
    PAIR = auto()
    TWO_PAIRS = auto()
    TRIPS = auto()
    SMALL_STRAIGHT = auto()
    LARGE_STRAIGHT = auto()
    FULL = auto()
    KARE = auto()
    ABAKA = auto()
    SUM = auto()
    SCHOOL_1 = auto()
    SCHOOL_2 = auto()
    SCHOOL_3 = auto()
    SCHOOL_4 = auto()
    SCHOOL_5 = auto()
    SCHOOL_6 = auto()


class Die:
    def __init__(self, value, is_joker=False):
        self.value = value
        self.is_joker = is_joker

    def __repr__(self):
        return f"J({self.value})" if self.is_joker else f"{self.value}"


def roll_dice():
    """Roll 4 normal dice and 1 joker die (random 1-6)."""
    dice = [Die(random.randint(1, 6)) for _ in range(4)]
    # Joker die: if it rolls 1 -> wild, else fixed
    joker_value = random.randint(1, 6)
    dice.append(Die(joker_value, is_joker=True))
    random.shuffle(dice)
    return dice


def score_category(dice, category, first_roll=False):
    """
    Compute best score for a category. `dice` is a list[Die].
    Joker is wild ONLY if its face is 1 (then we try assignments 1..6).
    Bonuses: KARE +20, ABAKA +50, Royal Full (1,1,1,2,2) +50; doubled on first roll.
    SCHOOL rows score as (count(denom) - 3), allowing negative values.
    """
    def _calc(values, cat):
        cnt = Counter(values)
        total = sum(values)
        bonus = 0

        if cat == Category.PAIR:
            pairs = [v for v, c in cnt.items() if c >= 2]
            score = max((v * 2 for v in pairs), default=0)

        elif cat == Category.TWO_PAIRS:
            pairs = [v for v, c in cnt.items() if c >= 2]
            if len(pairs) >= 2:
                top2 = sorted(pairs, reverse=True)[:2]
                score = sum(v * 2 for v in top2)
            else:
                score = 0

        elif cat == Category.TRIPS:
            trips = [v for v, c in cnt.items() if c >= 3]
            score = trips[0] * 3 if trips else 0

        elif cat == Category.FULL:
            # strictly 3+2 of different ranks
            if sorted(cnt.values()) == [2, 3]:
                score = total
                # Royal Full: 1,1,1,2,2
                if cnt.get(1, 0) == 3 and cnt.get(2, 0) == 2:
                    bonus = 50
            else:
                score = 0

        elif cat == Category.SMALL_STRAIGHT:
            s = set(values)
            smalls = [{1, 2, 3, 4}, {2, 3, 4, 5}, {3, 4, 5, 6}]
            score = total if any(seq.issubset(s) for seq in smalls) else 0

        elif cat == Category.LARGE_STRAIGHT:
            s = set(values)
            score = total if (s == {1, 2, 3, 4, 5} or s == {2, 3, 4, 5, 6}) else 0

        elif cat == Category.KARE:
            kare = [v for v, c in cnt.items() if c >= 4]
            if kare:
                score = kare[0] * 4
                bonus = 20
            else:
                score = 0

        elif cat == Category.ABAKA:
            if any(c == 5 for c in cnt.values()):
                score = total
                bonus = 50
            else:
                score = 0

        elif cat == Category.SUM:
            score = total

        elif cat in (Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
                     Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6):
            denom = int(cat.name.split('_')[1])
            # school cell value can be negative (shortage) or positive (excess over 3)
            score = cnt.get(denom, 0) - 3

        else:
            score = 0
        return score, bonus

    joker = next((d for d in dice if d.is_joker), None)
    if joker and joker.value == 1:
        best = 0
        for v in range(1, 7):
            vals = [v if d.is_joker else d.value for d in dice]
            base, bonus = _calc(vals, category)
            total_score = (base + bonus) * (2 if first_roll else 1)
            best = max(best, total_score)
        return best
    else:
        vals = [d.value for d in dice]
        base, bonus = _calc(vals, category)
        return (base + bonus) * (2 if first_roll else 1)


class PlayerState:
    def __init__(self, name):
        self.name = name
        self.table = {cat: [None, None, None, None] for cat in Category}  # 3 score slots + 1 bonus slot
        self.column_bonus = [None, None, None]  # bonuses for columns 0..2
        self.school_balance = 0
        self.school_balance_loc = None  # (Category, slot_index) where current balance is stored

    def record(self, category, slot_index, score):
        # only slots 0..2 are player-editable; slot 3 is row bonus and managed by engine
        if slot_index not in (0, 1, 2):
            raise ValueError("Slot index must be 0,1,2")
        if any(v is None for v in self.table[category][:slot_index]):
            raise ValueError("Must fill the leftmost free slot in this row")
        if self.table[category][slot_index] is not None:
            raise ValueError("Slot already filled")
        self.table[category][slot_index] = score

    def cross(self, category, slot_index):
        if slot_index not in (0, 1, 2):
            raise ValueError("Slot index must be 0,1,2")
        if any(v is None for v in self.table[category][:slot_index]):
            raise ValueError("Must fill the leftmost free slot in this row")
        if self.table[category][slot_index] is not None:
            raise ValueError("Slot already filled")
        self.table[category][slot_index] = 'X'

    def is_complete(self):
        # game is complete when all players filled the first three slots of every row
        return all(all(v is not None for v in slots[:3]) for slots in self.table.values())

    def non_school_complete(self):
        for cat, slots in self.table.items():
            if cat not in (Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
                           Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6):
                if not all(v is not None for v in slots[:3]):
                    return False
        return True

    def calculate_score(self):
        total = 0
        # sum all numeric cells including bonus slot (slot 3)
        for cat, slots in self.table.items():
            for val in slots:
                if isinstance(val, int):
                    total += val
        # add column bonuses
        for v in self.column_bonus:
            if isinstance(v, int):
                total += v
        return total



class GameEngine:
    def __init__(self, player_names):
        self.players = [PlayerState(n) for n in player_names]
        self.current = 0
        self.dice = []
        self.rolls_left = 0
        self.first_roll = True
        # global bonus claims (first-completion wins)
        self.row_bonus_claimed = {cat: False for cat in Category}
        self.col_bonus_claimed = [False, False, False]  # for columns 0..2

    def next_player(self):
        self.current = (self.current + 1) % len(self.players)

    def start_turn(self):
        self.dice = roll_dice()
        self.rolls_left = 2
        self.first_roll = True

    def reroll(self, indices):
        if self.rolls_left <= 0:
            raise RuntimeError("No rerolls left")
        for i in indices:
            if i < 0 or i >= len(self.dice):
                raise IndexError("Bad die index")
            self.dice[i].value = random.randint(1, 6)
        self.rolls_left -= 1
        if self.rolls_left < 2:
            self.first_roll = False

    def record_score(self, category, slot_index):
        # school rows use balance logic, others use category scoring
        if category in (Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
                        Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6):
            self._record_school(category, slot_index)
        else:
            score = score_category(self.dice, category, first_roll=self.first_roll)
            self.players[self.current].record(category, slot_index, score)
        # after any record, check bonuses
        self._after_record(category, slot_index)
        self.next_player()

    def record_cross(self, category, slot_index):
        self.players[self.current].cross(category, slot_index)
        # crossing may complete row/column and still claim (as X) and block others
        self._after_record(category, slot_index)
        self.next_player()

    def is_game_over(self):
        return all(p.is_complete() for p in self.players)

    def calculate_final_scores(self):
        return {p.name: p.calculate_score() for p in self.players}

    # ==== Scoreboard rendering ====
    def _category_label(self, cat: Category) -> str:
        if cat in (Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
                   Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6):
            return cat.name.split('_')[1]  # '1'..'6'
        mapping = {
            Category.PAIR: 'D',        # pair
            Category.TWO_PAIRS: 'DD',  # two pairs
            Category.TRIPS: 'T',       # trips
            Category.SMALL_STRAIGHT: 'LS',  # little straight
            Category.LARGE_STRAIGHT: 'BS',  # big straight
            Category.FULL: 'F',
            Category.KARE: 'C',
            Category.ABAKA: 'A',
            Category.SUM: 'Σ',
        }
        return mapping.get(cat, cat.name)

    def _fmt_cell(self, v) -> str:
        if v is None:
            return ' . '
        if v == 'X':
            return ' X '
        return f"{int(v):>3}"

    def print_scoreboard(self):
        # Fixed-width pretty table with short labels and a divider after school
        ROW_W = 6
        COL_W = 15  # 4 cells (3 chars each) + 3 spaces between = 15

        school_rows = [
            Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
            Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6,
        ]
        combo_rows = [
            Category.PAIR, Category.TWO_PAIRS, Category.TRIPS,
            Category.SMALL_STRAIGHT, Category.LARGE_STRAIGHT,
            Category.FULL, Category.KARE, Category.ABAKA,
            Category.SUM,
        ]

        header = f"{'Row':>{ROW_W}} " + ''.join(f"| {p.name:^{COL_W}} " for p in self.players)
        print("\n" + header)
        sep = '-' * len(header)
        print(sep)

        def print_row(cat):
            label = self._category_label(cat)
            line = f"{label:>{ROW_W}} "
            for p in self.players:
                cells = ' '.join(self._fmt_cell(v) for v in p.table[cat])
                line += f"| {cells:<{COL_W}} "
            print(line)

        # school section
        for cat in school_rows:
            print_row(cat)

        # divider between school and combos
        print(sep)

        for cat in combo_rows:
            print_row(cat)

        # column bonuses row (B)
        label = 'B'
        line = f"{label:>{ROW_W}} "
        for p in self.players:
            cells3 = ' '.join(self._fmt_cell(v) for v in p.column_bonus)
            # add a filler cell to align with 4 cells
            cells = f"{cells3} {' . ':>3}"
            line += f"| {cells:<{COL_W}} "
        print(line)

        # totals at the end
        print(sep)
        total_line = f"{'TOT':>{ROW_W}} " + ''.join(
            f"| {p.calculate_score():>{COL_W}} " for p in self.players
        )
        print(total_line)

    def _leftmost_slot(self, player, category):
        slots = player.table[category][:3]  # only first three are editable
        for i, v in enumerate(slots):
            if v is None:
                return i
        raise ValueError("Row already complete")

    # ===== Bonus logic =====
    def _after_record(self, category, slot_index):
        # row bonus
        self._check_row_bonus(self.current, category)
        # column bonus (only for columns 0..2)
        if slot_index in (0, 1, 2):
            self._check_col_bonus(self.current, slot_index)

    def _check_row_bonus(self, player_idx, category):
        if self.row_bonus_claimed.get(category):
            return
        player = self.players[player_idx]
        # row completed for this player?
        if all(v is not None for v in player.table[category][:3]):
            self.row_bonus_claimed[category] = True
            # compute value for this player
            row = player.table[category][:3]
            if any(v == 'X' for v in row):
                val = 'X'
            else:
                if category in (Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
                                Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6):
                    num = int(category.name.split('_')[1])
                    val = num * 3
                else:
                    vals = [v for v in row if isinstance(v, int)]
                    val = max(vals) if vals else 'X'
            # assign to owner
            player.table[category][3] = val
            # others get X if not already set
            for i, other in enumerate(self.players):
                if i == player_idx:
                    continue
                if other.table[category][3] is None:
                    other.table[category][3] = 'X'

    def _check_col_bonus(self, player_idx, col):
        if self.col_bonus_claimed[col]:
            return
        player = self.players[player_idx]
        # column complete for this player across all categories?
        col_vals = [player.table[cat][col] for cat in Category]
        if all(v is not None for v in col_vals):
            self.col_bonus_claimed[col] = True
            if any(v == 'X' for v in col_vals):
                val = 'X'
            else:
                vals = [v for v in col_vals if isinstance(v, int)]
                val = max(vals) if vals else 'X'
            player.column_bonus[col] = val
            # others get X
            for i, other in enumerate(self.players):
                if i == player_idx:
                    continue
                if other.column_bonus[col] is None:
                    other.column_bonus[col] = 'X'

    # ===== School logic with balance =====
    def _record_school(self, category, slot_index):
        player = self.players[self.current]
        denom = int(category.name.split('_')[1])
        # count of denom in dice; joker counts as +1 if face is 1 (wild)
        k = sum(1 for d in self.dice if (not d.is_joker and d.value == denom))
        if any(d.is_joker and d.value == 1 for d in self.dice):
            k += 1
        # Case: exactly 3 -> cross
        if k == 3:
            player.cross(category, slot_index)
            return
        # move existing balance from previous cell if we will write a number
        def move_balance(new_value):
            # cross previous balance cell if exists
            if player.school_balance_loc is not None:
                pc, ps = player.school_balance_loc
                player.table[pc][ps] = 'X'
            # write new value into current leftmost slot
            val = new_value * (2 if self.first_roll else 1)
            player.record(category, slot_index, val)
            player.school_balance = val
            player.school_balance_loc = (category, slot_index)

        if k > 3:
            delta = (k - 3) * denom
            move_balance(player.school_balance + delta)
            return
        # k < 3
        required = (3 - k) * denom
        if k == 0:
            # special rule: allow with cost 2*n if no dice of denom
            required = max(required, 2 * denom)
        if player.school_balance >= required:
            move_balance(player.school_balance - required)
            return
        # not enough balance
        raise ValueError("Not enough school balance to write this row")

    def _parse_category(self, s):
        s = s.strip().lower()
        aliases = {
            'd': Category.PAIR, 'pair': Category.PAIR, 'пара': Category.PAIR,
            'dd': Category.TWO_PAIRS, 'two_pairs': Category.TWO_PAIRS, '2pair': Category.TWO_PAIRS,
            't': Category.TRIPS, 'trips': Category.TRIPS, 'set': Category.TRIPS,
            'ls': Category.SMALL_STRAIGHT, 'small': Category.SMALL_STRAIGHT,
            'bs': Category.LARGE_STRAIGHT, 'large': Category.LARGE_STRAIGHT,
            'f': Category.FULL, 'full': Category.FULL,
            'c': Category.KARE, 'kare': Category.KARE,
            'a': Category.ABAKA, 'abaka': Category.ABAKA,
            'sum': Category.SUM, 'σ': Category.SUM, 'sigma': Category.SUM,
        }
        if s in aliases:
            return aliases[s]
        if s.startswith('school') or s.startswith('школа'):
            num = ''.join(ch for ch in s if ch.isdigit())
            if num and num in '123456':
                return getattr(Category, f'SCHOOL_{num}')
        try:
            return Category[s.upper()]
        except Exception:
            raise ValueError('Unknown category name')

    def _available_rows(self, player):
        avail = []
        for cat, slots in player.table.items():
            if any(v is None for v in slots[:3]):
                avail.append(cat)
        return avail

    def run_cli(self):
        print("=== Abaka CLI ===")
        print("Rules: leftmost slot fills automatically; first roll doubles base+bonus.")
        while not self.is_game_over():
            player = self.players[self.current]
            self.start_turn()
            print(f"-- {player.name}'s turn --")
            while True:
                # Show dice
                faces = ' '.join(f"[{i}:{repr(d)}]" for i, d in enumerate(self.dice))
                print(f"Dice: {faces}")
                if self.first_roll:
                    print("(First roll: everything doubles if you score now)")
                # Show available rows
                avail = self._available_rows(player)
                print("Available rows:", ', '.join(self._category_label(c) for c in avail))
                # Action
                action = input("Action: (r)eroll, (s)core, (x)cross: ").strip().lower()
                if action == 'r':
                    if self.rolls_left <= 0:
                        print("No rerolls left")
                        continue
                    raw = input("Indices to reroll (e.g. 0 2 4), or empty to skip: ").strip()
                    if not raw:
                        continue
                    try:
                        idxs = [int(t) for t in raw.split()]
                        self.reroll(idxs)
                    except Exception as e:
                        print("Error:", e)
                    continue
                elif action == 'x':
                    try:
                        cat_in = input("Row to cross (e.g. d, dd, t, ls, bs, f, c, a, or school 3): ")
                        cat = self._parse_category(cat_in)
                        slot = self._leftmost_slot(player, cat)
                        self.record_cross(cat, slot)
                        self.print_scoreboard()
                        break
                    except Exception as e:
                        print("Error:", e)
                        continue
                elif action == 's':
                    try:
                        cat_in = input("Row to score (e.g. sum, d, dd, t, ls, bs, f, c, a, or school 1): ")
                        cat = self._parse_category(cat_in)
                        slot = self._leftmost_slot(player, cat)
                        self.record_score(cat, slot)
                        self.print_scoreboard()
                        break
                    except Exception as e:
                        print("Error:", e)
                        continue
                else:
                    print("Unknown action")
                    continue
        print("=== Game over! ===")
        scores = self.calculate_final_scores()
        for name, sc in scores.items():
            print(f"{name}: {sc}")
        print("Winner:", max(scores.items(), key=lambda kv: kv[1])[0])

if __name__ == "__main__":
    try:
        names = input("Enter player names (comma-separated): ").strip()
        players = [n.strip() for n in names.split(',') if n.strip()] or ["Player1", "Player2"]
        GameEngine(players).run_cli()
    except KeyboardInterrupt:
        print("Bye")
