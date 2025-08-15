from collections import Counter
from .models import Category, Die

def score_category(dice, category, first_roll=False):
    """
    Joker wild ONLY if it shows 1 (we try 1..6).
    Bonuses: KARE +20, ABAKA +50, Royal Full (1,1,1,2,2) +50.
    On first roll, (base + bonus) is doubled.
    SCHOOL rows score as count(denom) - 3 (can be negative).
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
            score = sum(v*2 for v in sorted(pairs, reverse=True)[:2]) if len(pairs) >= 2 else 0
        elif cat == Category.TRIPS:
            trips = [v for v, c in cnt.items() if c >= 3]
            score = trips[0] * 3 if trips else 0
        elif cat == Category.FULL:
            if sorted(cnt.values()) == [2, 3]:
                score = total
                if cnt.get(1, 0) == 3 and cnt.get(2, 0) == 2:
                    bonus = 50
            else:
                score = 0
        elif cat == Category.SMALL_STRAIGHT:
            s = set(values)
            score = 15 if any(seq.issubset(s) for seq in ({1,2,3,4},{2,3,4,5},{3,4,5,6})) else 0
        elif cat == Category.LARGE_STRAIGHT:
            s = set(values)
            score = 20 if (s == {1,2,3,4,5} or s == {2,3,4,5,6}) else 0
        elif cat == Category.KARE:
            ks = [v for v, c in cnt.items() if c >= 4]
            score, bonus = (ks[0]*4, 20) if ks else (0, 0)
        elif cat == Category.ABAKA:
            score, bonus = (total, 50) if any(c == 5 for c in cnt.values()) else (0, 0)
        elif cat == Category.SUM:
            score = total
        elif cat.name.startswith("SCHOOL_"):
            denom = int(cat.name.split('_')[1])
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
            best = max(best, (base + bonus) * (2 if first_roll else 1))
        return best
    vals = [d.value for d in dice]
    base, bonus = _calc(vals, category)
    return (base + bonus) * (2 if first_roll else 1)
