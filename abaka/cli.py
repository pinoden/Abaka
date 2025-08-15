from .engine import GameEngine
from .models import Category
import re
from typing import List  # <-- add this

def _parse_indices(raw: str, n: int) -> List[int]:  # <-- List[int], not list[int]
    # accept digits anywhere; e.g. "012", "0 1,2", "0;1:2"
    idxs = sorted({int(ch) for ch in re.findall(r"[0-9]", raw)})
    idxs = [i for i in idxs if 0 <= i < n]
    return idxs

def _parse_category(s: str) -> Category:
    s = s.strip().lower()
    aliases = {
        'd': Category.PAIR, 'pair': Category.PAIR,
        'dd': Category.TWO_PAIRS, 'two_pairs': Category.TWO_PAIRS, '2pair': Category.TWO_PAIRS,
        't': Category.TRIPS, 'trips': Category.TRIPS,
        'ls': Category.SMALL_STRAIGHT, 'small': Category.SMALL_STRAIGHT,
        'bs': Category.LARGE_STRAIGHT, 'large': Category.LARGE_STRAIGHT,
        'f': Category.FULL, 'full': Category.FULL,
        'c': Category.KARE, 'kare': Category.KARE,
        'a': Category.ABAKA, 'abaka': Category.ABAKA,
        'sum': Category.SUM, 'σ': Category.SUM, 'sigma': Category.SUM,
    }
    if s in aliases: return aliases[s]
    if s.startswith('school') or s.startswith('школа'):
        num = ''.join(ch for ch in s if ch.isdigit())
        if num in '123456':
            return getattr(Category, f'SCHOOL_{num}')
    return Category[s.upper()]

def _available_rows(engine: GameEngine, player):
    return [cat for cat, slots in player.table.items() if any(v is None for v in slots[:3])]

def main():
    names = input("Enter player names (comma-separated): ").strip()
    players = [n.strip() for n in names.split(',') if n.strip()] or ["Player1", "Player2"]
    g = GameEngine(players)
    print("=== Abaka CLI ===")
    print("Rules: leftmost slot fills automatically; first roll doubles base+bonus.")
    while not g.is_game_over():
        player = g.players[g.current]
        g.start_turn()
        print(f"\n-- {player.name}'s turn --")
        while True:
            faces = ' '.join(f"[{i}:{repr(d)}]" for i, d in enumerate(g.dice))
            print(f"Dice: {faces}")
            if g.first_roll: print("(First roll: everything doubles if you score now)")
            avail = _available_rows(g, player)
            print("Available rows:", ', '.join(g._category_label(c) for c in avail))
            action = input("Action: (r)eroll, (s)core, (x)cross: ").strip().lower()
            if action == 'r':
                if g.rolls_left <= 0:
                    print("No rerolls left")
                    continue
                while True:
                    raw = input("Indices to reroll (e.g. 0 2 4), or empty to skip: ").strip()
                    if not raw:
                        break
                    try:
                        idxs = _parse_indices(raw, n=len(g.dice))
                        if not idxs:
                            raise ValueError("No valid indices 0..4 found")
                        g.reroll(idxs)
                        break  # success -> exit the inner while, continue the turn
                    except Exception as e:
                        print("Invalid indices. Try again (examples: 0 1 2  |  012  |  0,1,2).")
                continue
            elif action == 'x':
                try:
                    cat = _parse_category(input("Row to cross (e.g. d, dd, t, ls, bs, f, c, a, or school 3): "))
                    slot = g.leftmost_slot(player, cat)
                    g.record_cross(cat, slot)
                    g.print_scoreboard()
                    break
                except Exception as e:
                    print("Error:", e); continue
            elif action == 's':
                try:
                    cat = _parse_category(input("Row to score (sum/d/dd/t/ls/bs/f/c/a or school n): "))
                    slot = g.leftmost_slot(player, cat)
                    g.record_score(cat, slot)
                    g.print_scoreboard()
                    break
                except Exception as e:
                    print("Error:", e); continue
            else:
                print("Unknown action"); continue
    print("\n=== Game over! ===")
    scores = g.calculate_final_scores()
    for name, sc in scores.items():
        print(f"{name}: {sc}")
    print("Winner:", max(scores.items(), key=lambda kv: kv[1])[0])
