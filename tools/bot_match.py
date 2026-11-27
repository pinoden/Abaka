"""
The computer player (abaka/bot.py) against simpler players, over many simulated games.

  python tools/bot_match.py [GAMES] [--seed N]
  python tools/bot_match.py 200            # about 25 minutes
  python tools/bot_match.py 200 --pair medium hard    # one pairing (run several at once)

Plays two-player games on GameEngine, with the starting throw, seats alternating:
the computer against a random player, against a greedy one (the most points now, on the
first roll), against a careful one (keeps its most common number and rolls the rest, fills
School rows whenever it has three of a number, never pays from the balance while anything
else is offered), and the greedy player against itself for scale. Prints each side's average
score, its win rate, and the computer's time per decision. Then its three levels (Backlog
item 34) against each other and against the careful player: "easy", "medium" and "hard"
("computer" is hard).
"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abaka import bot  # noqa: E402
from abaka.engine import GameEngine  # noqa: E402
from abaka.models import Category  # noqa: E402
from abaka.moves import cross_options, is_school, score_options  # noqa: E402


CROSS_FIRST = [Category.ABAKA, Category.KARE, Category.LARGE_STRAIGHT, Category.SMALL_STRAIGHT, Category.FULL,
               Category.TRIPS, Category.TWO_PAIRS, Category.PAIR, Category.SUM]  # the careful player's order


def careful_step(engine, rng):
    """A careful player of simple habits (see the module's text)."""
    if engine.choosing_first_player:
        return ("throw",)
    if not engine.dice:
        return ("roll",)
    scores = score_options(engine)
    paid = [m for m in scores if is_school(m.category) and (m.balance_change or 0) < 0]
    unpaid = [m for m in scores if m not in paid]

    def worth(m):
        return m.points + (25 if is_school(m.category) else 0)  # a School row with three or more: first

    best = max(unpaid, key=worth) if unpaid else None
    if engine.rolls_left > 0 and (best is None or worth(best) < 30):
        values = [d.value for d in engine.dice]
        keep = max(set(values), key=lambda v: (values.count(v), v))
        return ("reroll", [i for i, v in enumerate(values) if v != keep] or [0])
    crosses = sorted(cross_options(engine), key=lambda m: CROSS_FIRST.index(m.category))
    move = best or (crosses[0] if crosses else max(paid, key=lambda m: m.points))
    return ("cross" if move.cross else "score", move.category, move.slot)


PLAYERS = {
    "computer": lambda engine, rng: bot.next_step(engine),
    "easy": lambda engine, rng: bot.next_step(engine, "easy", rng),
    "medium": lambda engine, rng: bot.next_step(engine, "medium", rng),
    "hard": lambda engine, rng: bot.next_step(engine, "hard", rng),
    "greedy": bot.greedy_step,
    "random": bot.random_step,
    "careful": careful_step,
}


def play(first: str, second: str, rng: random.Random, timings: list) -> list:
    """One game; returns the two players' scores (first, second)."""
    engine = GameEngine([first, second], starting_throw=True)
    policies = [PLAYERS[first], PLAYERS[second]]
    names = [first, second]
    while not engine.is_game_over():
        seat = engine.current
        started = time.perf_counter()
        step = policies[seat](engine, rng)
        if names[seat] in ("computer", "easy", "medium", "hard") and step[0] not in ("throw", "roll"):
            timings.append(time.perf_counter() - started)
        bot.apply_step(engine, step)
    return [p.calculate_score() for p in engine.players]


def match(a: str, b: str, games: int, rng: random.Random, timings: list) -> dict:
    scores = {a: [], b: []} if a != b else {a: [], a + " (2)": []}
    keys = list(scores)
    wins = {k: 0 for k in keys}
    draws = 0
    for n in range(games):
        flip = n % 2 == 1
        result = play(b, a, rng, timings) if flip else play(a, b, rng, timings)
        if flip:
            result = result[::-1]
        for k, s in zip(keys, result):
            scores[k].append(s)
        if result[0] == result[1]:
            draws += 1
        else:
            wins[keys[0 if result[0] > result[1] else 1]] += 1
    return {k: (sum(v) / len(v), wins[k] / games) for k, v in scores.items()}, draws


def main() -> None:
    pair = None
    if "--pair" in sys.argv:
        at = sys.argv.index("--pair")
        pair = tuple(sys.argv[at + 1:at + 3])
        del sys.argv[at:at + 3]
        if len(pair) != 2 or any(p not in PLAYERS for p in pair):
            sys.exit("--pair takes two of: " + ", ".join(PLAYERS))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    games = int(args[0]) if args else 100
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 1
    random.seed(seed)
    rng = random.Random(seed)
    bot.tables()
    timings: list = []
    started = time.time()
    pairs = [pair] if pair else [("computer", "random"), ("computer", "greedy"), ("computer", "careful"),
                                 ("greedy", "greedy"), ("careful", "careful"),
                                 ("medium", "hard"), ("easy", "medium"), ("easy", "hard"),
                                 ("medium", "careful"), ("easy", "careful")]
    for a, b in pairs:
        result, draws = match(a, b, games, rng, timings)
        line = " vs ".join("%s: average %.0f, wins %.0f%%" % (k, avg, 100 * w) for k, (avg, w) in result.items())
        print("%d games, %s (draws %d)" % (games, line, draws), flush=True)
    timings.sort()
    if timings:
        print("computer's decisions: %d, median %.1f ms, 95th percentile %.1f ms, slowest %.1f ms (%.0f s in all)"
              % (len(timings), 1000 * timings[len(timings) // 2], 1000 * timings[int(len(timings) * 0.95)],
                 1000 * timings[-1], time.time() - started))


if __name__ == "__main__":
    main()
