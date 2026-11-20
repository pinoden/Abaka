"""
The game as JSON for apps (abaka/api.py, Backlog item 25): complete games played only
through the API, what each player may see, refusals and their codes, languages, clubs,
and docs/API.md covering every operation.
"""

import json
import random
import re
import unittest
from pathlib import Path
from unittest import mock

from abaka import api
from abaka.api import ApiError
from abaka.clubs import ClubStore
from abaka.i18n import get_language, set_language
from abaka.models import Die
from abaka.rooms import RoomStore
from abaka.saving import engine_to_data

ROOT = Path(__file__).resolve().parent.parent


class Server:
    """A store, its clubs, and the API in front of them, as an app would reach them."""

    def __init__(self, starting_throw=True):
        self.clubs = ClubStore()
        self.store = RoomStore(starting_throw=starting_throw, on_game_over=self.clubs.record)
        self.tokens = []

    def __call__(self, **request):
        response = api.handle(request, self.store, self.clubs)
        text = json.dumps(response, ensure_ascii=False)
        assert json.loads(text) == response, "the response is not plain JSON data"
        for token in self.tokens:  # a state never shows a seat's token
            assert "state" not in response or token not in json.dumps(response["state"]), "a token leaked"
        if "token" in response:
            self.tokens.append(response["token"])
        return response

    def refused(self, **request):
        try:
            api.handle(request, self.store, self.clubs)
        except ApiError as e:
            return e.code, e.message
        raise AssertionError(f"not refused: {request}")


def online(server, players=2, names=("Ann", "Bob", "Cy", "Dee", "Eve")):
    first = server(op="create", name=names[0], players=players)
    code, tokens = first["code"], [first["token"]]
    for name in names[1:players]:
        tokens.append(server(op="join", code=code, name=name)["token"])
    return code, tokens


def play(server, code, tokens, rng, local=False, until=None):
    """
    Play the game to its end (or until `until(state)`) through the API, choosing at random
    among what each state offers, and check every move against what the state promised.
    """
    state = server(op="state", code=code, token=tokens[0])["state"]
    while state["phase"] != "over" and not (until and until(state)):
        mover = 0 if local else state["game"]["current"]
        state = server(op="state", code=code, token=tokens[mover])["state"]
        can, version = state["can"], state["version"]
        ask = dict(code=code, token=tokens[mover], version=version)
        if "throw" in can:
            state = server(op="throw", **ask)["state"]
            continue
        if "roll" in can:
            state = server(op="roll", **ask)["state"]
            assert len(state["game"]["dice"]) == 5 and state["game"]["rolls_left"] == 2
            continue
        moves = state["moves"]
        assert ("score" in can) == bool(moves["score"]) and ("cross" in can) == bool(moves["cross"])
        points = [m["points"] for m in moves["score"]]
        assert [m["best"] for m in moves["score"]] == [p == max(points) for p in points]
        if "reroll" in can and rng.random() < 0.35:
            dice = rng.sample(range(5), rng.randint(1, 5))
            state = server(op="reroll", dice=dice, **ask)["state"]
            assert sorted(state["game"]["rerolled"]) == sorted(dice)
            continue
        cross = not moves["score"] or (moves["cross"] and rng.random() < 0.15)
        move = rng.choice(moves["cross"] if cross else moves["score"])
        seat = state["game"]["current"]
        before = state["game"]["players"][seat]["total"]
        state = server(op="cross" if cross else "score", row=move["row"], slot=move["slot"], **ask)["state"]
        after = state["game"]["players"][seat]
        assert state["game"]["last_move"] == {"seat": seat, "row": move["row"], "slot": move["slot"]}
        assert after["rows"][move["row"]][move["slot"]] == move["value"]  # the preview was exact
        if not cross:
            assert after["total"] - before == move["points"], (move, before, after["total"])
    return state


class TestBasics(unittest.TestCase):
    def setUp(self):
        self.server = Server()

    def test_info(self):
        info = self.server(op="info")
        self.assertEqual(info["protocol"], api.PROTOCOL)
        self.assertEqual(info["players"], {"min": 2, "max": 5})
        self.assertEqual([r["row"] for r in info["rows"]][:7], ["SCHOOL_1", "SCHOOL_2", "SCHOOL_3", "SCHOOL_4",
                                                                "SCHOOL_5", "SCHOOL_6", "PAIR"])
        self.assertEqual(len(info["rows"]), 15)
        self.assertIn("lucky", info["reactions"])
        self.assertEqual(self.server(op="info", lang="ru")["rows"][6]["name"], "Пара")

    def test_malformed_requests(self):
        for request in (["op", "info"], {"op": "fly"}, {}, {"op": "state"}, {"op": "state", "code": 7},
                        {"op": "create", "players": True}, {"op": "create", "players": 9},
                        {"op": "create_local", "names": "Ann, Bob"}):
            with self.subTest(request=request):
                with self.assertRaises(ApiError) as caught:
                    api.handle(request, self.server.store)
                self.assertEqual(caught.exception.code, "bad_request")

    def test_another_protocol_is_refused_in_the_players_language(self):
        code, message = self.server.refused(op="info", protocol=2, lang="ru")
        self.assertEqual(code, "protocol")
        self.assertIn("Обновите приложение", message)

    def test_unknown_games_and_clubs(self):
        for request in ({"op": "state", "code": "ZZZZZ"}, {"op": "seen", "code": "zzz zz"},
                        {"op": "state", "code": "../../etc"}, {"op": "join", "code": "QQQQQ", "name": "Ann"},
                        {"op": "club", "club": "ZZZZZZ"}, {"op": "create", "name": "Ann", "club": "ZZZZZZ"}):
            with self.subTest(request=request):
                self.assertEqual(self.server.refused(**request)[0], "not_found")

    def test_the_language_of_a_request_is_its_own(self):
        set_language("ru")
        try:
            self.assertEqual(self.server(op="info", lang="en")["rows"][6]["name"], "Pair")
            self.assertEqual(get_language(), "ru")  # the thread's own language is left as it was
        finally:
            set_language("en")


class TestOnline(unittest.TestCase):
    def setUp(self):
        self.server = Server()
        self.code, self.tokens = online(self.server, players=3)

    def state(self, seat=None, **extra):
        token = self.tokens[seat] if seat is not None else None
        return self.server(op="state", code=self.code, token=token, **extra)["state"]

    def test_waiting_room(self):
        server = Server()
        first = server(op="create", name="Ann", players=3)
        code = first["code"]
        self.assertEqual((first["state"]["phase"], first["state"]["you"], first["state"]["can"]),
                         ("waiting", 0, ["leave"]))
        guest = server(op="join", code=code, name="Ann")  # names are made distinct
        self.assertEqual(guest["state"]["names"], ["Ann", "Ann (2)"])
        self.assertEqual(server(op="state", code=code, token=first["token"])["state"]["can"], ["leave", "start_now"])
        self.assertEqual(server(op="state", code=code)["state"]["can"], ["join", "rejoin"])
        self.assertEqual(server.refused(op="start_now", code=code, token=guest["token"])[0], "refused")
        state = server(op="start_now", code=code, token=first["token"])["state"]
        self.assertEqual((state["phase"], state["capacity"]), ("starting_throw", 2))

    def test_leaving_the_waiting_room(self):
        server = Server()
        first = server(op="create", name="Ann", players=3)
        server(op="join", code=first["code"], name="Bob")
        self.assertEqual(server(op="leave", code=first["code"], token=first["token"]), {"left": True})
        self.assertEqual(server(op="state", code=first["code"])["state"]["names"], ["Bob"])

    def test_what_each_player_sees(self):
        state = self.state(1)
        self.assertEqual((state["phase"], state["you"], state["seated"]), ("starting_throw", 1, True))
        thrower = state["game"]["current"]
        self.assertIn("throw", self.state(thrower)["can"])
        self.assertNotIn("throw", self.state((thrower + 1) % 3)["can"])
        # Someone with only the code sees what the invite page shows, and how to take a seat.
        outsider = self.state()
        self.assertEqual((outsider["seated"], outsider["game"], outsider["can"]), (False, None, ["rejoin"]))
        self.assertEqual(outsider["names"], ["Ann", "Bob", "Cy"])

    def test_moves_need_the_turn_and_the_latest_version(self):
        thrower = self.state(0)["game"]["current"]
        other = (thrower + 1) % 3
        version = self.state(0)["version"]
        code, message = self.server.refused(op="throw", code=self.code, token=self.tokens[other], version=version,
                                            lang="ru")
        self.assertEqual((code, message), ("refused", "Сейчас не ваш ход."))
        self.server(op="throw", code=self.code, token=self.tokens[thrower], version=version)
        # The same tap again (a double tap) names the old version: refused, nothing changes.
        after = self.state(0)
        self.assertEqual(self.server.refused(op="throw", code=self.code, token=self.tokens[thrower],
                                             version=version)[0], "outdated")
        self.assertEqual(self.state(0)["version"], after["version"])

    def test_a_seat_taken_back_on_another_device(self):
        token = self.server(op="rejoin", code=self.code, seat=1)["token"]
        self.assertNotEqual(token, self.tokens[1])
        old = self.server(op="state", code=self.code, token=self.tokens[1])["state"]
        self.assertFalse(old["seated"])
        self.assertEqual(self.server.refused(op="say", code=self.code, token=self.tokens[1], text="hi")[0],
                         "not_seated")
        self.assertEqual(self.server(op="state", code=self.code, token=token)["state"]["you"], 1)

    def test_web_and_app_players_share_the_game(self):
        while self.state(0)["phase"] == "starting_throw":
            self.server.store.throw_for_start(self.code, self.tokens[self.state(0)["game"]["current"]])
        mover = self.state(0)["game"]["current"]
        with mock.patch("abaka.engine.roll_dice", lambda: [Die(6), Die(6), Die(6), Die(6), Die(6, is_joker=True)]):
            self.server.store.roll(self.code, self.tokens[mover])  # as the web app does
        state = self.state((mover + 1) % 3)
        self.assertEqual([d["value"] for d in state["game"]["dice"]], [6] * 5)
        fireworks = [e for e in state["events"] if e["kind"] == "effect"]
        self.assertEqual((fireworks[-1]["effect"], fireworks[-1]["what"]), ("grand_fireworks", "ABAKA"))
        self.assertIsNone(state["moves"])  # the moves are for the player whose turn it is
        moves = self.state(mover)["moves"]["score"]
        self.assertEqual([m["row"] for m in moves if m["best"]], ["ABAKA"])
        self.assertEqual(next(m for m in moves if m["row"] == "ABAKA")["points"], 160)

    def test_picks_reactions_and_chat(self):
        while self.state(0)["phase"] == "starting_throw":
            current = self.state(0)["game"]["current"]
            self.server(op="throw", code=self.code, token=self.tokens[current], version=self.state(0)["version"])
        mover = self.state(0)["game"]["current"]
        watcher = (mover + 1) % 3
        self.server(op="roll", code=self.code, token=self.tokens[mover], version=self.state(0)["version"])
        seen = self.server(op="seen", code=self.code)["seen"]
        self.server(op="pick", code=self.code, token=self.tokens[mover], dice=[0, 3])
        self.assertNotEqual(self.server(op="seen", code=self.code)["seen"], seen)
        self.assertEqual(self.state(watcher)["game"]["picked"], [0, 3])
        self.assertEqual(self.server.refused(op="pick", code=self.code, token=self.tokens[watcher], dice=[1])[0],
                         "refused")

        self.server(op="react", code=self.code, token=self.tokens[watcher], reaction="lucky", to=mover)
        self.assertEqual(self.server.refused(op="react", code=self.code, token=self.tokens[watcher],
                                             reaction="nice")[0], "too_fast")
        state = self.server(op="say", code=self.code, token=self.tokens[watcher], text="  <b>gg</b>‮ ")["state"]
        reaction = [e for e in state["events"] if e["kind"] == "reaction"][-1]
        self.assertEqual((reaction["seat"], reaction["to"], reaction["reaction"]), (watcher, mover, "lucky"))
        message = state["chat"][-1]
        self.assertEqual((message["seat"], message["text"]), (watcher, "<b>gg</b>"))  # cleaned, never interpreted
        # `since`: only what came after the latest id the app already has.
        latest = max([e["id"] for e in state["events"]] + [m["id"] for m in state["chat"]])
        self.assertEqual(self.state(mover, since=latest)["chat"], [])
        self.assertEqual(self.state(mover, since=latest)["events"], [])

    def test_drawing_a_state_never_changes_the_game(self):
        while self.state(0)["phase"] == "starting_throw":
            current = self.state(0)["game"]["current"]
            self.server(op="throw", code=self.code, token=self.tokens[current], version=self.state(0)["version"])
        mover = self.state(0)["game"]["current"]
        self.server(op="roll", code=self.code, token=self.tokens[mover], version=self.state(0)["version"])
        engine = self.server.store.view(self.code).engine
        before = engine_to_data(engine)
        for seat in range(3):
            self.state(seat)
        self.assertIs(self.server.store.view(self.code).engine, engine)
        self.assertEqual(engine_to_data(engine), before)


class TestCompleteGames(unittest.TestCase):
    """Whole games through the API only: every move offered is accepted and its preview was exact."""

    def test_online_games_for_two_to_five(self):
        for players in (2, 5):
            with self.subTest(players=players):
                server = Server()
                code, tokens = online(server, players)
                state = play(server, code, tokens, random.Random(players))
                engine = server.store.view(code).engine
                totals = [p.calculate_score() for p in engine.players]
                self.assertEqual([p["total"] for p in state["game"]["players"]], totals)
                self.assertEqual(state["game"]["winners"], [i for i, x in enumerate(totals) if x == max(totals)])
                self.assertEqual(state["table"]["games"], 1)
                self.assertEqual(state["chat"], [])  # the chat ends with the game
                self.assertEqual(state["can"], ["rematch", "react"])
                again = server(op="rematch", code=code, token=tokens[1])["state"]
                self.assertEqual((again["phase"], again["game"]["number"]), ("starting_throw", 2))
                # A second rematch tap (someone else was quicker) just shows the new game.
                self.assertEqual(server(op="rematch", code=code, token=tokens[0])["state"]["game"]["number"], 2)

    def test_a_same_device_game(self):
        server = Server()
        made = server(op="create_local", names=["Ann", " ", "Cy"], lang="ru")
        code, token = made["code"], made["token"]
        self.assertEqual(made["state"]["names"], ["Ann", "Игрок 2", "Cy"])
        self.assertEqual((made["state"]["you"], made["state"]["local"]), (None, True))
        self.assertEqual(server(op="state", code=code)["state"]["can"], ["resume"])
        self.assertEqual(server(op="resume", code=code)["token"], token)
        state = play(server, code, [token], random.Random(3), local=True)
        self.assertEqual(state["phase"], "over")
        self.assertNotIn("react", state["can"])

    def test_without_the_starting_throw_and_with_the_slot_left_out(self):
        server = Server(starting_throw=False)
        code, tokens = online(server, 2)
        version = server(op="state", code=code, token=tokens[0])["state"]["version"]
        state = server(op="roll", code=code, token=tokens[0], version=version)["state"]
        state = server(op="score", code=code, token=tokens[0], version=state["version"], row="SUM")["state"]
        self.assertEqual(state["game"]["last_move"], {"seat": 0, "row": "SUM", "slot": 0})
        self.assertEqual(server.refused(op="score", code=code, token=tokens[1], version=state["version"],
                                        row="FLY")[0], "bad_request")


class TestClubs(unittest.TestCase):
    def test_a_club_game_from_start_to_table(self):
        server = Server()
        club = server(op="create_club", name="  Friday   dice ")["club"]
        self.assertEqual((club["name"], club["members"], club["games"]), ("Friday dice", [], []))
        self.assertEqual(server.refused(op="create_club", name="  ", lang="ru")[1], "Дайте клубу название.")
        self.assertEqual(server.refused(op="create_local", names=["Ann", "ann "], club=club["code"])[0], "refused")
        made = server(op="create_local", names=["Ann", "Bob"], club=club["code"].lower())
        self.assertEqual(made["state"]["club"], club["code"])
        state = play(server, made["code"], [made["token"]], random.Random(7), local=True)
        result = state["club_result"]
        self.assertEqual(result["club"], "Friday dice")
        self.assertAlmostEqual(sum(p["change"] for p in result["players"]), 0.0)
        table = server(op="club", club=club["code"])["club"]
        self.assertEqual(sorted(m["name"] for m in table["members"]), ["Ann", "Bob"])
        self.assertEqual(len(table["games"]), 1)
        self.assertEqual(table["members"][0]["rating"], max(p["rating"] for p in result["players"]))


class TestDocs(unittest.TestCase):
    def test_docs_describe_every_operation_and_error(self):
        text = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
        documented = set(re.findall(r"^#### `(\w+)`", text, re.M))
        self.assertEqual(documented, set(api.OPERATIONS))
        for code in api.ERRORS:
            self.assertIn(f"`{code}`", text)


if __name__ == "__main__":
    unittest.main()
