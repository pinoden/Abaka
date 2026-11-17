"""
Random complete games, played the way the UI plays them, with rule checks after every move.

  python tools/simulate.py ENGINE_GAMES ROOM_GAMES [--board]
  python tools/simulate.py 200 40            # about 2-3 minutes
  python tools/simulate.py 20 5 --board      # quick, also builds the scoreboard (needs Streamlit)

Games are played through the same move lists the UI offers (ui_components/moves.py),
directly on GameEngine and through RoomStore/RoomEngine, plus several rooms played at
once from many threads while other threads keep trying moves out of turn. After every
move it checks the written cell, the last move, the turn order, the school balance, the
starting throw and the bonus rules; at game end, the bonuses and totals.
"""
import copy
import random
import re
import sys
import threading
import time

import os  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abaka.constants import COMBO_CATS, SCHOOL_CATS  # noqa: E402
from abaka.engine import GameEngine  # noqa: E402
from abaka.models import Category  # noqa: E402
from abaka.rooms import RoomEngine, RoomError, RoomStore  # noqa: E402
from ui_components.moves import cross_options, is_school, school_number, score_options  # noqa: E402

BOARD = "--board" in sys.argv
if BOARD:
    from ui_components.scoreboard import build_scoreboard_html, describe_move  # noqa: E402

CELLS = len(Category) * 3  # 45 cells per player
stats = {"games": 0, "moves": 0, "crosses": 0, "school_paid": 0, "school_bonus_won": 0, "school_bonus_lost_by_payer": 0,
         "negative_end": 0, "first_roll_scores": 0, "reroll_all": 0, "joker_wild": 0,
         "dead_ends": 0, "boards": 0, "room_refusals": 0}


def expected_score(p):
    total = sum(v for slots in p.table.values() for v in slots if isinstance(v, int))
    total += sum(v for v in p.column_bonus if isinstance(v, int))
    if p.school_balance < 0:
        total += p.school_balance * 100
    return total


def pick_move(engine, policy, rng):
    scores, crosses = score_options(engine), cross_options(engine)
    if not scores and not crosses:
        stats["dead_ends"] += 1
        raise AssertionError("no legal move for player %d" % engine.current)
    if policy == "cross" and crosses and rng.random() < 0.5:
        return rng.choice(crosses)
    if policy == "greedy" and scores:
        return max(scores, key=lambda m: m.value if isinstance(m.value, int) else 0)
    pool = scores + (crosses if rng.random() < 0.15 or not scores else [])
    return rng.choice(pool)


def play_turn(eng, plain, rng, policy, paid_rows):
    """One full turn through `eng` (GameEngine or RoomEngine). `plain()` returns the current GameEngine."""
    cur = plain().current
    eng.start_turn()
    g = plain()
    assert len(g.dice) == 5 and sum(d.is_joker for d in g.dice) == 1 and g.rolls_left == 2 and g.first_roll
    for _ in range(rng.choice([0, 0, 1, 2])):
        if rng.random() < 0.25:
            idx = list(range(5))
            stats["reroll_all"] += 1
        else:
            idx = rng.sample(range(5), rng.randint(1, 5))
        eng.reroll(idx)
        g = plain()
        assert not g.first_roll
    g = plain()
    if any(d.is_joker and d.value == 1 for d in g.dice):
        stats["joker_wild"] += 1
    first = g.first_roll
    move = pick_move(g, policy, rng)
    p_before = copy.deepcopy(g.players[cur])
    if move.cross:
        eng.record_cross(move.category, move.slot)
        stats["crosses"] += 1
        after_cross = plain().players[cur]
        # Crossing out gives up the row's and the column's bonus at once (owner, 2026-11-16).
        assert after_cross.table[move.category][3] == "X" and after_cross.column_bonus[move.slot] == "X"
        assert move.bonus_lost == (p_before.table[move.category][3] is None)
        assert move.column_bonus_lost == (p_before.column_bonus[move.slot] is None)
    else:
        eng.record_score(move.category, move.slot)
        if first and not is_school(move.category):
            stats["first_roll_scores"] += 1
    g = plain()
    p = g.players[cur]
    # the cell the preview promised is the cell that was written
    assert p.table[move.category][move.slot] == move.value, (move, p.table[move.category])
    assert p_before.table[move.category][move.slot] is None
    assert tuple(g.last_move) == (cur, move.category, move.slot), g.last_move
    assert g.dice == [] and g.current == (cur + 1) % len(g.players)
    if is_school(move.category) and move.balance_change is not None and move.balance_change < 0:
        stats["school_paid"] += 1
        paid_rows.setdefault(cur, set()).add(move.category)
        # Owner's rule (2026-11-16): paying from the balance crosses out the row bonus at once.
        assert p.table[move.category][3] == "X", "payment did not cross out the row bonus"
        assert move.bonus_lost == (p_before.table[move.category][3] is None), move
    elif not move.cross:
        assert not move.bonus_lost, move
    assert p.school_balance == p_before.school_balance + (move.balance_change or 0) if is_school(move.category) \
        else p.school_balance == p_before.school_balance
    if p.school_balance_loc is not None:
        c, s = p.school_balance_loc
        assert p.table[c][s] == p.school_balance
    stats["moves"] += 1
    return move


def check_board(g, me):
    if not BOARD:
        return
    html_ = build_scoreboard_html(g, me=me)
    stats["boards"] += 1
    n_last = len(re.findall(r'class="[^"]*\bab-last\b', html_))
    assert n_last == (1 if g.last_move else 0), n_last
    if g.last_move:
        assert "Last move: " in html_
        describe_move(g, g.last_move, me)
    for p in g.players:
        if "<" in p.name:
            assert p.name not in html_, "player name reached the HTML unescaped"


def check_end(g, paid_rows):
    assert g.is_game_over()
    n = len(g.players)
    for p in g.players:
        assert all(v is not None for slots in p.table.values() for v in slots[:3])
        assert all(slots[3] is not None for slots in p.table.values()), "a row bonus cell is still empty"
        assert all(v is not None for v in p.column_bonus), "a column bonus cell is still empty"
        assert p.calculate_score() == expected_score(p)
        if p.school_balance < 0:
            stats["negative_end"] += 1
    for cat in Category:
        bonuses = [p.table[cat][3] for p in g.players]
        ints = [b for b in bonuses if isinstance(b, int)]
        assert len(ints) <= 1, (cat, bonuses)
        if is_school(cat):
            # At most one player gets it (3 x the number), and never one who paid from the balance in it.
            assert ints in ([], [3 * school_number(cat)]), (cat, bonuses)
            for i, b in enumerate(bonuses):
                if cat in paid_rows.get(i, set()):
                    assert b == "X", (cat, i, bonuses)
            if ints:
                stats["school_bonus_won"] += 1
            else:  # the first to complete the row had paid in it: nobody gets the bonus
                assert any(cat in paid_rows.get(i, set()) for i in range(n)), (cat, bonuses)
                stats["school_bonus_lost_by_payer"] += 1
        else:
            for i, p in enumerate(g.players):
                if isinstance(p.table[cat][3], int):
                    assert "X" not in p.table[cat][:3], (cat, p.table[cat])
                    assert p.table[cat][3] == max(p.table[cat][:3])
    for col in (0, 1):
        assert sum(isinstance(p.column_bonus[col], int) for p in g.players) <= 1
    for p in g.players:
        for col in range(3):
            if isinstance(p.column_bonus[col], int):
                assert all(p.table[c][col] != "X" for c in COMBO_CATS)
    stats["games"] += 1


def check_starting_throw(g):
    assert not g.choosing_first_player and g.first_player is not None
    last = max(t["round"] for t in g.starting_throws)
    final = [t for t in g.starting_throws if t["round"] == last]
    low = min(t["total"] for t in final)
    assert [t["player"] for t in final if t["total"] == low] == [g.first_player]
    for t in g.starting_throws:
        assert t["total"] == sum(v for v, _ in t["dice"]) and len(t["dice"]) == 5
    stats["starting_throws"] = stats.get("starting_throws", 0) + 1
    if last > 1:
        stats["starting_ties"] = stats.get("starting_ties", 0) + 1


def engine_game(n, rng):
    opening = rng.random() < 0.5
    g = GameEngine(["P%d" % i for i in range(n)], starting_throw=opening)
    if opening:
        while g.choosing_first_player:
            g.throw_for_start()
        check_starting_throw(g)
        assert g.current == g.first_player
    policy = rng.choice(["random", "greedy", "cross"])
    paid = {}
    turns = 0
    while not g.is_game_over():
        play_turn(g, lambda: g, rng, policy, paid)
        turns += 1
        if turns % 7 == 0:
            check_board(g, me=None)
        assert turns <= CELLS * n
    assert turns == CELLS * n, turns
    check_board(g, me=0)
    check_end(g, paid)


def room_game(store, n, rng, rematches=1):
    code, host = store.create("<b>Host</b>", n)
    tokens = [host] + [store.join(code, "Guest") for _ in range(n - 1)]
    view = store.view(code)
    assert view.started and len(set(view.names)) == n, view.names  # names made distinct
    for game_no in range(rematches + 1):
        while store.view(code).engine.choosing_first_player:
            cur = store.view(code).engine.current
            for bad in (lambda: store.throw_for_start(code, tokens[(cur + 1) % n]), lambda: store.roll(code, tokens[cur])):
                try:
                    bad()
                except (RoomError, ValueError):
                    stats["room_refusals"] += 1
                else:
                    raise AssertionError("room accepted an illegal action during the starting throw")
            store.throw_for_start(code, tokens[cur])
        check_starting_throw(store.view(code).engine)
        assert store.view(code).engine.current == store.view(code).engine.first_player
        paid, turns = {}, 0
        while True:
            view = store.view(code)
            g = view.engine
            if g.is_game_over():
                break
            cur = g.current
            other = tokens[(cur + 1) % n]
            v0 = store.version(code)
            for bad in (lambda: store.roll(code, other), lambda: store.score(code, tokens[cur], Category.SUM, 0)):
                try:
                    bad()
                except RoomError:
                    stats["room_refusals"] += 1
                else:
                    raise AssertionError("room accepted an illegal action")
            assert store.version(code) == v0, "a refused action changed the room"
            eng = RoomEngine(store, code, tokens[cur], g)

            def plain():
                return store.view(code).engine
            play_turn(eng, plain, rng, "random", paid)
            turns += 1
            if turns % 11 == 0:
                check_board(store.view(code).engine, me=cur)
        assert turns == CELLS * n
        check_end(store.view(code).engine, paid)
        try:
            store.roll(code, tokens[0])
        except RoomError as e:
            assert "over" in str(e)
        if game_no < rematches:
            store.rematch(code, tokens[rng.randrange(n)])
    return code


def concurrent_rooms(rng_seed, threads=6):
    """Several rooms played at once from many threads, plus threads that keep acting out of turn."""
    store = RoomStore()
    errors = []

    def worker(k):
        try:
            room_game(store, 2 + k % 4, random.Random(rng_seed + k), rematches=0)
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    stop = threading.Event()

    def heckler():
        while not stop.is_set():
            for code in list(store._rooms):
                try:
                    store.roll(code, "not-a-token")
                except RoomError:
                    pass
                else:
                    errors.append("stranger rolled in " + code)

    ts = [threading.Thread(target=worker, args=(k,)) for k in range(threads)]
    h = threading.Thread(target=heckler)
    h.start()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    stop.set()
    h.join()
    assert not errors, errors


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        raise SystemExit(__doc__)
    engine_games, room_games = int(args[0]), int(args[1])
    rng = random.Random(20261116)
    t0 = time.time()
    for k in range(engine_games):
        engine_game(2 + k % 4, rng)
    t1 = time.time()
    store = RoomStore()
    for k in range(room_games):
        room_game(store, 2 + k % 4, rng)
    t2 = time.time()
    concurrent_rooms(99)
    t3 = time.time()
    print("engine games %.1fs, room games %.1fs, concurrent rooms %.1fs" % (t1 - t0, t2 - t1, t3 - t2))
    for k, v in stats.items():
        print("  %-24s %d" % (k, v))
    print("SIMULATION OK")


if __name__ == "__main__":
    main()
