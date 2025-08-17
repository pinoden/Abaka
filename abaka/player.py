from .models import Category

class PlayerState:
    def __init__(self, name):
        self.name = name
        # 3 score slots + 1 bonus slot per row
        self.table = {cat: [None, None, None, None] for cat in Category}
        # column bonuses for slots 0..2
        self.column_bonus = [None, None, None]
        # school balance (value lives in the last written school cell)
        self.school_balance = 0
        self.school_balance_loc = None  # (Category, slot_index)

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
        return all(all(v is not None for v in slots[:3]) for slots in self.table.values())

    def non_school_complete(self):
        for cat, slots in self.table.items():
            if not cat.name.startswith("SCHOOL_") and not all(v is not None for v in slots[:3]):
                return False
        return True

    def calculate_score(self):
        total = 0
        # sum all numeric cells including row-bonus cells
        for _, slots in self.table.items():
            for v in slots:
                if isinstance(v, int):
                    total += v
        # add column bonuses
        for v in self.column_bonus:
            if isinstance(v, int):
                total += v

        # endgame penalty: -100 per negative point of school balance
        if isinstance(self.school_balance, int) and self.school_balance < 0:
            total += self.school_balance * 100  # e.g., -8 -> -800

        return total