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
            total_score = base + (bonus * (2 if first_roll else 1))
            best = max(best, total_score)
        return best
    else:
        vals = [d.value for d in dice]
        base, bonus = _calc(vals, category)
        return base + (bonus * (2 if first_roll else 1))


class PlayerState:
    def __init__(self, name):
        self.name = name
        self.table = {cat: [None, None, None] for cat in Category}

    def record(self, category, slot_index, score):
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
        return all(all(v is not None for v in slots) for slots in self.table.values())

    def non_school_complete(self):
        for cat, slots in self.table.items():
            if cat not in (Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
                           Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6):
                if not all(v is not None for v in slots):
                    return False
        return True

    def calculate_score(self):
        total = 0
        school_bonus = 0
        school_penalty = 0

        # Sum all numeric cells
        for cat, slots in self.table.items():
            for val in slots:
                if isinstance(val, int):
                    total += val

        # School x3 bonuses (everyone may get it in the last column)
        for cat in (Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
                    Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6):
            if self.table[cat][2] is not None:  # third column filled by this player
                num = int(cat.name.split('_')[1])
                school_bonus += num * 3

        # School penalties: -100 for each negative point in a row's total
        for cat in (Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
                    Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6):
            row_sum = sum(v for v in self.table[cat] if isinstance(v, int))
            if row_sum < 0:
                school_penalty += (-row_sum) * 100

        return total + school_bonus - school_penalty



class GameEngine:
    def __init__(self, player_names):
        self.players = [PlayerState(n) for n in player_names]
        self.current = 0
        self.dice = []
        self.rolls_left = 0
        self.first_roll = True

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
        # compute score first
        score = score_category(self.dice, category, first_roll=self.first_roll)
        # enforce school top-up constraint (need at least one matching die unless non-school complete)
        if category in (Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
                        Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6):
            denom = int(category.name.split('_')[1])
            player = self.players[self.current]
            if score < 0:
                raw_has = any((not d.is_joker and d.value == denom) or (d.is_joker and d.value == denom) for d in self.dice)
                if not raw_has and not player.non_school_complete():
                    raise ValueError("Cannot top-up school without at least one die of that denomination (unless all non-school rows are complete)")
        self.players[self.current].record(category, slot_index, score)
        self.next_player()

    def record_cross(self, category, slot_index):
        self.players[self.current].cross(category, slot_index)
        self.next_player()

    def is_game_over(self):
        return all(p.is_complete() for p in self.players)

    def calculate_final_scores(self):
        return {p.name: p.calculate_score() for p in self.players}

    def _leftmost_slot(self, player, category):
        slots = player.table[category]
        for i, v in enumerate(slots):
            if v is None:
                return i
        raise ValueError("Row already complete")

    def _parse_category(self, s):
        s = s.strip().lower()
        aliases = {
            'pair': Category.PAIR, 'пара': Category.PAIR,
            'two_pairs': Category.TWO_PAIRS, 'две пары': Category.TWO_PAIRS, '2pair': Category.TWO_PAIRS,
            'trips': Category.TRIPS, 'трипс': Category.TRIPS, 'set': Category.TRIPS,
            'small': Category.SMALL_STRAIGHT, 'малый': Category.SMALL_STRAIGHT, 'mstraight': Category.SMALL_STRAIGHT,
            'large': Category.LARGE_STRAIGHT, 'большой': Category.LARGE_STRAIGHT, 'lstraight': Category.LARGE_STRAIGHT,
            'full': Category.FULL, 'фулл': Category.FULL,
            'kare': Category.KARE, 'каре': Category.KARE,
            'abaka': Category.ABAKA, 'абака': Category.ABAKA,
            'sum': Category.SUM, 'сумма': Category.SUM,
        }
        if s in aliases:
            return aliases[s]
        if s.startswith('school') or s.startswith('школа'):
            num = ''.join(ch for ch in s if ch.isdigit())
            if num and num in '123456':
                return getattr(Category, f'SCHOOL_{num}')
        # Also allow exact enum name
        try:
            return Category[s.upper()]
        except Exception:
            raise ValueError('Unknown category name')

    def _available_rows(self, player):
        avail = []
        for cat, slots in player.table.items():
            if any(v is None for v in slots):
                avail.append(cat)
        return avail

    def run_cli(self):
        print("=== Abaka CLI ===")
        print("Rules: leftmost slot fills automatically; first roll bonuses doubled.")
        while not self.is_game_over():
            player = self.players[self.current]
            self.start_turn()
            print(f"{player.name}'s turn --")
            while True:
                # Show dice
                faces = ' '.join(f"[{i}:{repr(d)}]" for i, d in enumerate(self.dice))
                print(f"Dice: {faces}")
                if self.first_roll:
                    print("(First roll: bonuses doubled if you score now)")
                # Show available rows
                avail = self._available_rows(player)
                print("Available rows:", ', '.join(c.name for c in avail))
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
                        cat_in = input("Row to cross (e.g. pair, full, school 3): ")
                        cat = self._parse_category(cat_in)
                        slot = self._leftmost_slot(player, cat)
                        self.record_cross(cat, slot)
                        break
                    except Exception as e:
                        print("Error:", e)
                        continue
                elif action == 's':
                    try:
                        cat_in = input("Row to score (e.g. sum, kare, school 1): ")
                        cat = self._parse_category(cat_in)
                        slot = self._leftmost_slot(player, cat)
                        self.record_score(cat, slot)
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
