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
        return f"{'J' if self.is_joker else self.value}"


def roll_dice():
    """Roll 4 normal dice and 1 joker die (random 1-6)."""
    dice = [Die(random.randint(1, 6)) for _ in range(4)]
    # Joker die: if it rolls 1 -> wild, else fixed
    joker_value = random.randint(1, 6)
    dice.append(Die(joker_value, is_joker=True))
    random.shuffle(dice)
    return dice


from collections import Counter

def score_category(dice, category, first_roll=False):
    """
    Joker is wild ONLY if its face is 1 (then try 1..6).
    Bonuses: KARE +20, ABAKA +50, Royal Full (1,1,1,2,2) +50.
    On first roll, bonuses are doubled.
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
            # строго 3+2 разных рангов
            if sorted(cnt.values()) == [2, 3]:
                score = total
                # Королевский фулл: 1,1,1,2,2
                if cnt.get(1, 0) == 3 and cnt.get(2, 0) == 2:
                    bonus = 50
            else:
                score = 0

        elif cat == Category.SMALL_STRAIGHT:
            s = set(values)
            smalls = [{1,2,3,4}, {2,3,4,5}, {3,4,5,6}]
            score = total if any(seq.issubset(s) for seq in smalls) else 0

        elif cat == Category.LARGE_STRAIGHT:
            s = set(values)
            score = total if (s == {1,2,3,4,5} or s == {2,3,4,5,6}) else 0

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
            score = cnt.get(denom, 0)

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
        # должны быть заполнены ВСЕ слоты слева от выбранного
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

    def calculate_score(self):
        total = 0
        bonus = 0
        for cat, slots in self.table.items():
            for val in slots:
                if isinstance(val, int):
                    total += val
        for cat in (Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
                    Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6):
            if self.table[cat][2] is not None:
                num = int(cat.name.split('_')[1])
                bonus += num * 3
        return total + bonus


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
        joker_idx = next(i for i, d in enumerate(self.dice) if d.is_joker)
        for i in indices:
            if i == joker_idx:
                continue  # cannot reroll joker
            self.dice[i].value = random.randint(1, 6)
        self.rolls_left -= 1
        if self.rolls_left < 2:
            self.first_roll = False

    def record_score(self, category, slot_index):
        score = score_category(self.dice, category, first_roll=self.first_roll)
        self.players[self.current].record(category, slot_index, score)
        self.next_player()

    def record_cross(self, category, slot_index):
        self.players[self.current].cross(category, slot_index)
        self.next_player()

    def is_game_over(self):
        return all(p.is_complete() for p in self.players)

    def calculate_final_scores(self):
        return {p.name: p.calculate_score() for p in self.players}

    def run_cli(self):
        print("Starting Abaka game")
        while not self.is_game_over():
            player = self.players[self.current]
            print(f"\n{player.name}'s turn")
            self.start_turn()
            while True:
                print("Dice:", self.dice)
                if self.rolls_left > 0:
                    action = input("(r)eroll, (s)core, or (x)cross? ").strip().lower()
                else:
                    action = input("(s)core or (x)cross? ").strip().lower()
                if action == 'r' and self.rolls_left > 0:
                    idxs = input("Indices to reroll (e.g. 0 2): ").split()
                    self.reroll([int(i) for i in idxs])
                elif action == 's':
                    cat = Category[input("Category: ").strip().upper()]
                    slot = int(input("Slot (0-2): "))
                    self.record_score(cat, slot)
                    break
                elif action == 'x':
                    cat = Category[input("Category for cross: ").strip().upper()]
                    slot = int(input("Slot (0-2): "))
                    self.record_cross(cat, slot)
                    break
                else:
                    print("Invalid action")
        print("Game over! Scores:")
        for name, sc in self.calculate_final_scores().items():
            print(f"{name}: {sc}")
