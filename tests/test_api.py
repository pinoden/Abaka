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
from abaka.models import Category, Die
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

    def test_text_that_cannot_be_sent_never_gets_in(self):
        """
        JSON can carry half of a surrogate pair; UTF-8 cannot. A name or a chat message holding
        one broke the game's web page, the other players' connections and its database row.
        """
        half, other_half = json.loads('"\\ud83d"'), json.loads('"\\udc00"')
        made = self.server(op="create", name="Ann" + half, players=2)
        bob = self.server(op="join", code=made["code"], name=other_half + "Bob")["token"]
        said = self.server(op="say", code=made["code"], token=bob, text="hi " + half + " there")["state"]
        local = self.server(op="create_local", names=["Cy" + half, half])["state"]
        club = self.server(op="create_club", name="Fri" + half + "day")["club"]
        self.assertEqual((said["names"], [m["text"] for m in said["chat"]]), (["Ann", "Bob"], ["hi there"]))
        self.assertEqual((local["names"], club["name"]), (["Cy", "Player 2"], "Friday"))
        for answer in (made, said, local, club):
            json.dumps(answer, ensure_ascii=False).encode("utf-8")  # can be sent

    def test_the_rules(self):
        """The rules as the website shows them, as blocks an app draws itself, in the request's language."""
        for lang, title, first, heading in (("en", "How to play", "**Players.**", "Combinations"),
                                            ("ru", "Как играть", "**Игроки.**", "Комбинации")):
            with self.subTest(lang=lang):
                rules = self.server(op="rules", lang=lang)["rules"]
                blocks = rules["blocks"]
                self.assertEqual(rules["title"], title)
                self.assertTrue(blocks[0]["text"].startswith(first))
                self.assertIn({"heading": heading}, blocks)
                self.assertTrue(all(len(block) == 1 and set(block) <= {"heading", "text", "table"} for block in blocks))
                # The table names every combination as the board does, in board order, with what it
                # needs and what it scores.
                [table] = [block["table"] for block in blocks if "table" in block]
                combinations = [row["name"] for row in self.server(op="info", lang=lang)["rows"] if not row["school"]]
                self.assertEqual([row[0] for row in table["rows"]], combinations)
                self.assertTrue(all(len(row) == len(table["head"]) == 3 for row in table["rows"]))
                # No markup but **bold**: no table pipes, headings or links left in the text.
                text = " ".join(block.get("text", "") for block in blocks)
                self.assertFalse(re.search(r"[|#\[\]`]", text), text)
                self.assertEqual(text.count("**") % 2, 0)

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

    def test_events_come_with_their_words_for_each_player(self):
        """An app shows a reaction's and an effect's words as they are: who, to whom, in the player's language."""
        info = self.server(op="info", lang="ru")
        self.assertEqual([r["id"] for r in info["reaction_list"]], info["reactions"])
        self.assertEqual(info["reaction_list"][0], {"id": "lucky", "emoji": "\U0001F340", "label": "Повезло!"})
        while self.state(0)["phase"] == "starting_throw":
            self.server.store.throw_for_start(self.code, self.tokens[self.state(0)["game"]["current"]])
        mover = self.state(0)["game"]["current"]
        other, third = (mover + 1) % 3, (mover + 2) % 3
        names = self.state(0)["names"]
        with mock.patch("abaka.engine.roll_dice", lambda: [Die(6), Die(6), Die(6), Die(6), Die(6, is_joker=True)]):
            self.server(op="roll", code=self.code, token=self.tokens[mover], version=self.state(0)["version"])
        self.server(op="react", code=self.code, token=self.tokens[other], reaction="lucky", to=mover)

        def words(seat, lang="en"):
            effect, reaction = self.state(seat, lang=lang)["events"][-2:]
            return ((effect["title"], effect["text"]),
                    (reaction["emoji"], reaction["who"], reaction["label"], reaction["to_you"]))

        self.assertEqual(words(mover), (("Abaka!", "You · first roll"),
                                        ("\U0001F340", f"{names[other]} → you", "Lucky!", True)))
        self.assertEqual(words(other), (("Abaka!", f"{names[mover]} · first roll"),
                                        ("\U0001F340", f"You → {names[mover]}", "Lucky!", False)))
        self.assertEqual(words(third, "ru"), (("Абака!", f"{names[mover]} · с первого броска"),
                                              ("\U0001F340", f"{names[other]} → {names[mover]}", "Повезло!", False)))
        # The facts are still there for an app that draws its own.
        effect = self.state(third)["events"][-2]
        self.assertEqual((effect["effect"], effect["what"], effect["first"], effect["seat"]),
                         ("grand_fireworks", "ABAKA", True, mover))

    def test_a_bonus_says_what_it_earned(self):
        server = Server()
        made = server(op="create_local", names=["Ann", "Bob"], lang="ru")
        code, token = made["code"], made["token"]
        engine = server.store.view(code).engine
        while engine.choosing_first_player:
            server.store.throw_for_start(code, token)
            engine = server.store.view(code).engine
        # Two Sum cells written, on a copy the store then holds: the third completes the row.
        room = server.store._rooms[code]
        ready = engine.clone()
        ready.players[ready.current].table[Category.SUM][:2] = [20, 22]
        room.engine = ready
        with mock.patch("abaka.engine.roll_dice", lambda: [Die(6), Die(5), Die(4), Die(2), Die(1, is_joker=True)]):
            state = server(op="roll", code=code, token=token, version=room.version)["state"]
        mover = state["game"]["current"]
        state = server(op="score", code=code, token=token, version=state["version"], row="SUM", lang="ru")["state"]
        bonus = state["events"][-1]
        self.assertEqual((bonus["what"], bonus["title"]), ("BONUS", "Бонус!"))
        # On one device nobody is "You": the banner names the player.
        self.assertTrue(bonus["text"].startswith(["Ann", "Bob"][mover] + " · строка «Сумма» +"), bonus["text"])

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
        online = server(op="create", name="Ann", players=2, club=club["code"])
        self.assertEqual(server.refused(op="join", code=online["code"], name=" ANN", lang="ru"),
                         ("refused", "У каждого игрока должно быть своё имя."))  # one member, once a game
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


class TestHostileRequests(unittest.TestCase):
    """
    Whatever a client sends, the API answers with data that can be sent, or refuses with
    ApiError; anything else is a fault of the server. Each request starts as a well-formed
    one for a game in some phase, with a real token, so it reaches deep into its operation;
    then a field is replaced with a malformed or hostile value, or others are added. Some
    stay as they are, so the games move on. (Found this way, 2026-11-21: half of a
    surrogate pair in a name or a chat message.)
    """

    TEXTS = ["", " ", "x" * 3000, "\x00", "\u202e", "\ud800", "a\udc00b", "<b>hi</b>", "../../etc/passwd",
             "ABCDE", "ABCDEF", "ru", "xx", "PAIR", "SCHOOL_1", "lucky"]
    OTHERS = [None, True, False, 0, 1, -1, 5, 10 ** 30, 1.5, float("nan"), [], {}, [[]], {"a": 1}, [0, 1],
              [0, 0, 0], [5], [-1], ["0"], [True], ["Ann", "\ud800"], ["Ann", "ann "], ["a"] * 6, ["", ""]]
    FIELDS = ["lang", "protocol", "name", "names", "players", "seat", "version", "since", "dice", "row", "slot",
              "reaction", "to", "text", "club", "games"]
    MOVES = ("throw", "roll", "reroll", "score", "cross")
    REQUESTS = 4000

    def games(self, server, rng):
        """Games in every phase, as [code, a token per seat]: waiting, starting, under way and over."""
        def after(moves):
            asked = [0]

            def reached(state):
                asked[0] += 1
                return asked[0] > moves
            return reached

        club = server(op="create_club", name="Friday dice")["club"]["code"]
        waiting = server(op="create", name="Ann", players=5)
        games = [[waiting["code"], [waiting["token"]]]]
        for moves in (0, 4, 15, None):
            code, tokens = online(server, 2)
            play(server, code, tokens, rng, until=after(moves) if moves is not None else None)
            games.append([code, tokens])
        for moves, club_code in ((6, None), (None, club)):
            made = server(op="create_local", names=["Ann", "Bob"], club=club_code)
            play(server, made["code"], [made["token"]], rng, local=True,
                 until=after(moves) if moves is not None else None)
            games.append([made["code"], [made["token"]] * 2])
        return games, club

    def well_formed(self, op, server, code, tokens, club, rng):
        """A request for `op` that the API would take, were the game in the right phase."""
        request = {"op": op}
        if op in ("info", "create", "create_local", "club", "create_club"):
            request.update({"create": {"name": "Ann", "players": 2}, "create_local": {"names": ["Ann", "Bob"]},
                            "club": {"club": club}, "create_club": {"name": "Friday"}}.get(op, {}))
            return request
        request["code"] = code
        try:
            state = api.handle({"op": "state", "code": code, "token": tokens[0]}, server.store, server.clubs)["state"]
        except ApiError:  # an earlier request closed this game
            return request
        game = state["game"]
        mover = tokens[game["current"]] if game and game["current"] < len(tokens) else tokens[0]
        if op not in ("join", "rejoin", "resume", "seen"):
            request["token"] = mover if op in self.MOVES + ("pick",) else rng.choice(tokens)
        if op in self.MOVES:
            request["version"] = state["version"]
        request.update({"join": {"name": "Bob"}, "rejoin": {"seat": rng.randrange(len(tokens))},
                        "reroll": {"dice": rng.sample(range(5), rng.randint(1, 5))}, "pick": {"dice": [1, 3]},
                        "score": {"row": "SUM"}, "cross": {"row": "ABAKA"}, "react": {"reaction": "lucky"},
                        "say": {"text": "hi"}}.get(op, {}))
        return request

    def test_never_a_server_fault(self):
        rng = random.Random(2026)
        server = Server()
        games, club = self.games(server, rng)
        operations = list(api.OPERATIONS) + ["watch", "fly"]
        outcomes = {}
        for _ in range(self.REQUESTS):
            code, tokens = game = rng.choice(games)
            request = self.well_formed(rng.choice(operations), server, code, tokens, club, rng)
            change = rng.random()
            if change < 0.6 and len(request) > 1:  # one field of it, replaced
                field = rng.choice([f for f in request if f != "op"])
                texts = isinstance(request[field], str) and rng.random() < 0.7
                request[field] = rng.choice(self.TEXTS if texts else self.TEXTS + self.OTHERS)
            elif change < 0.8:  # fields it should not have, or malformed ones it may use
                for field in rng.sample(self.FIELDS, rng.randint(1, 3)):
                    request[field] = rng.choice(self.TEXTS + self.OTHERS)
            elif change < 0.82:  # not a request at all
                request = rng.choice(self.TEXTS + self.OTHERS)
            try:
                answer, outcome = api.handle(request, server.store, server.clubs), "answered"
            except ApiError as e:
                answer, outcome = e.to_data(), e.code
                self.assertIn(e.code, api.ERRORS)
            except Exception as e:  # noqa: BLE001 - what this test is looking for
                self.fail("a server fault on %r: %r" % (request, e))
            try:
                json.dumps(answer, ensure_ascii=False, allow_nan=False).encode("utf-8")
            except ValueError as e:
                self.fail("the answer to %r cannot be sent: %r" % (request, e))
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            # A seat taken (back) has a new token: keep it, so later requests still reach the game.
            state = answer.get("state") if isinstance(answer, dict) and "token" in answer else None
            if state and state["code"] == code and state["you"] is not None:
                tokens[state["you"]:state["you"] + 1] = [answer["token"]]
            if outcome == "not_found" and isinstance(request, dict) and request.get("code") == code and len(games) > 3:
                games.remove(game)  # closed by a leave: no longer there to ask about
        # The requests got past the first checks: every kind of answer came up.
        for outcome in ("answered", "bad_request", "protocol", "refused", "not_found", "not_seated", "outdated",
                        "too_fast"):
            self.assertGreater(outcomes.get(outcome, 0), 0, (outcome, outcomes))


class TestDocs(unittest.TestCase):
    def test_docs_describe_every_operation_and_error(self):
        text = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
        documented = set(re.findall(r"^#### `(\w+)`", text, re.M))
        self.assertEqual(documented, set(api.OPERATIONS))
        for code in api.ERRORS:
            self.assertIn(f"`{code}`", text)


if __name__ == "__main__":
    unittest.main()
