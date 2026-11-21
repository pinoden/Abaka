"""
Leaderboards (owner, 2026-11-19): the running score at a table (every room remembers
its finished games) and clubs (a rating table for a group of friends, abaka/clubs.py).
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka.clubs import (START_RATING, ClubError, ClubStore, is_club_code, member_key,
                         rating_changes)
from abaka.repository import FileRepository
from abaka.rooms import RoomStore
from abaka.moves import cross_options, score_options

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # the base Python 3.8
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def type_new_option(box, text):
    """
    Type `text`, which is not one of its options, into a select box that takes new ones.
    AppTest can only pick a listed option (it looks the value up in the options, on
    Streamlit 1.48 and 1.67 alike), so this sends what a browser sends for a typed one:
    the text itself.
    """
    from streamlit.proto.WidgetStates_pb2 import WidgetState

    class Typed(type(box)):
        @property
        def _widget_state(self):
            state = WidgetState()
            state.id = self.id
            state.string_value = text
            return state

    box.__class__ = Typed


def finish_game(store, code, token):
    """Play a same-device game to its end with the moves the UI offers. Returns the final scores."""
    for _ in range(2000):
        engine = store.view(code).engine
        if engine.is_game_over():
            return [p.calculate_score() for p in engine.players]
        if engine.choosing_first_player:
            store.throw_for_start(code, token)
        elif not engine.dice:
            store.roll(code, token)
        else:
            move = (score_options(engine) or cross_options(engine))[0]
            (store.cross if move.cross else store.score)(code, token, move.category, move.slot)
    raise AssertionError("the game did not finish")


class TestRatings(unittest.TestCase):
    def test_two_players(self):
        self.assertEqual(rating_changes([1000, 1000], [300, 200]), [16.0, -16.0])
        self.assertEqual(rating_changes([1000, 1000], [250, 250]), [0.0, 0.0])
        favourite, outsider = rating_changes([1200, 1000], [300, 200])
        self.assertLess(favourite, 16)  # beating a weaker player earns less...
        upset, _ = rating_changes([1000, 1200], [300, 200])
        self.assertGreater(upset, 16)  # ...than beating a stronger one
        self.assertAlmostEqual(favourite + outsider, 0)

    def test_more_players_add_up_to_zero_and_follow_the_order(self):
        changes = rating_changes([1000, 1050, 980, 1010, 1000], [310, 205, 260, 260, 150])
        self.assertAlmostEqual(sum(changes), 0)
        self.assertEqual(max(changes), changes[0])  # the winner gains most
        self.assertEqual(min(changes), changes[4])  # the last loses most
        self.assertLessEqual(abs(changes[0]), 32)  # a game is worth at most K, however many play

    def test_names_match_whatever_the_capitals_and_spaces(self):
        self.assertEqual(member_key("  Ann  Lee "), member_key("ann lee"))
        self.assertNotEqual(member_key("Ann"), member_key("Ann (2)"))


class TestRunningScore(unittest.TestCase):
    def test_every_finished_game_counts_and_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RoomStore(save_dir=folder)
            code, key = store.create_local(["Ann", "Bob"])
            first = finish_game(store, code, key)
            view = store.view(code)
            self.assertEqual(view.results, [{"game": 0, "scores": first}])
            store.rematch(code, key)
            second = finish_game(store, code, key)
            wins, draws = store.view(code).series()
            expected = [0, 0]
            ties = 0
            for scores in (first, second):
                if scores[0] == scores[1]:
                    ties += 1
                else:
                    expected[scores.index(max(scores))] += 1
            self.assertEqual((wins, draws), (expected, ties))
            again = RoomStore(save_dir=folder)  # saved with the room
            self.assertEqual(again.view(code).series(), (expected, ties))

    def test_a_broken_listener_never_stops_the_game(self):
        def broken(result):
            raise RuntimeError("boom")

        store = RoomStore(on_game_over=broken)
        code, key = store.create_local(["Ann", "Bob"])
        with self.assertLogs("abaka", level="WARNING"):
            finish_game(store, code, key)
        self.assertTrue(store.view(code).engine.is_game_over())


class TestClubs(unittest.TestCase):
    def setUp(self):
        self.clubs = ClubStore()
        self.store = RoomStore(on_game_over=self.clubs.record)
        self.club = self.clubs.create("Friday dice")

    def test_a_club_game_updates_the_table(self):
        code, key = self.store.create_local(["Ann", "Bob"], club=self.club)
        scores = finish_game(self.store, code, key)
        club = self.clubs.get(self.club)
        ann, bob = club["members"]["ann"], club["members"]["bob"]
        self.assertEqual((ann["games"], bob["games"]), (1, 1))
        self.assertAlmostEqual(ann["rating"] + bob["rating"], 2 * START_RATING)
        self.assertEqual(ann["rating"] > bob["rating"], scores[0] > scores[1])
        self.assertEqual(ann["wins"] + bob["wins"], 0 if scores[0] == scores[1] else 1)
        self.assertEqual((ann["best"], bob["best"]), tuple(scores))
        game = self.clubs.game(self.club, code, 0)
        self.assertEqual([p["score"] for p in game["players"]], scores)

        # The same players again, typed differently, in a new room: one table row each.
        other, key2 = self.store.create_local([" ANN ", "bob", "Cy"], club=self.club)
        finish_game(self.store, other, key2)
        club = self.clubs.get(self.club)
        self.assertEqual(sorted(club["members"]), ["ann", "bob", "cy"])
        self.assertEqual(club["members"]["ann"]["games"], 2)
        self.assertEqual(len(club["games"]), 2)

    def test_a_result_counts_once_and_only_for_club_games(self):
        code, key = self.store.create_local(["Ann", "Bob"], club=self.club)
        finish_game(self.store, code, key)
        result = {"room": code, "game": 0, "club": self.club, "names": ["Ann", "Bob"], "scores": [1, 2],
                  "at": time.time()}
        self.assertFalse(self.clubs.record(result))  # already recorded
        plain, key = self.store.create_local(["Dee", "Eve"])
        finish_game(self.store, plain, key)
        self.assertNotIn("dee", self.clubs.get(self.club)["members"])
        self.assertFalse(self.clubs.record(dict(result, club="NOSUCH")))

    def test_a_member_plays_once_in_an_online_club_game(self):
        """'ann' joining 'Ann' was seated, and the club then counted one member twice, against herself."""
        code, ann = self.store.create("Ann", 3, club=self.club)
        for name in (" ann ", "ANN", "Ann"):
            with self.subTest(name=name), self.assertRaises(rooms.RoomError) as refused:
                self.store.join(code, name)
            self.assertEqual(str(refused.exception), "Each player needs a different name.")
        self.store.join(code, "Bob")
        self.assertEqual(self.store.view(code).names, ["Ann", "Bob"])
        # Outside a club, nothing changed: an exact twin is told apart, another spelling is kept.
        plain, _ = self.store.create("Ann", 3)
        self.store.join(plain, "Ann")
        self.store.join(plain, "ann")
        self.assertEqual(self.store.view(plain).names, ["Ann", "Ann (2)", "ann"])

    def test_codes_and_names(self):
        self.assertTrue(is_club_code(self.club))
        self.assertFalse(is_club_code("ABCDE"))  # a room code
        self.assertIsNone(self.clubs.get("../../x"))
        with self.assertRaises(ClubError):
            self.clubs.create("  ‮ ")
        long_name = self.clubs.create("A" * 50)
        self.assertEqual(len(self.clubs.get(long_name)["name"]), 30)
        copy = self.clubs.get(self.club)
        copy["members"]["x"] = {}
        self.assertNotIn("x", self.clubs.get(self.club)["members"])  # get() hands out a copy

    def test_clubs_are_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            clubs = ClubStore(repository=FileRepository(Path(folder) / "clubs"))
            store = RoomStore(on_game_over=clubs.record)
            club = clubs.create("Saved")
            code, key = store.create_local(["Ann", "Bob"], club=club)
            finish_game(store, code, key)
            again = ClubStore(repository=FileRepository(Path(folder) / "clubs"))  # after a restart
            self.assertEqual(again.get(club), clubs.get(club))


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestClubPages(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        stores = self.stores = []
        base = rooms.RoomStore

        class FreshRoomStore(base):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                stores.append(self)

        rooms.RoomStore = FreshRoomStore
        code_version.mark_current()

        # AppTest 1.48 reads every button group's value as a list, but the app's single-choice
        # segmented controls hold one value (as in test_ui_reruns.py; 1.67 needs no help).
        from streamlit.testing.v1 import element_tree
        if not hasattr(element_tree.ButtonGroup, "_is_single_select"):
            group_value = element_tree.ButtonGroup.value.fget

            def one_or_more(group):
                value = group_value(group)
                return [] if value is None else value if isinstance(value, list) else [value]

            patcher = mock.patch.object(element_tree.ButtonGroup, "value", property(one_or_more))
            patcher.start()
            self.addCleanup(patcher.stop)

    def page(self, **params):
        at = AppTest.from_file(APP, default_timeout=30)
        for name, value in params.items():
            at.query_params[name] = value
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    @staticmethod
    def html(at):
        return "\n".join(n.proto.body for n in at.get("html"))

    def test_create_a_club_play_a_game_and_see_the_table(self):
        at = self.page()
        self.assertIn("Clubs", self.html(at))
        at.text_input(key="club_name").input("Friday <b>dice</b>")
        next(b for b in at.button if b.label == "Create club").click().run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        club = at.query_params["club"]
        club = club[0] if isinstance(club, list) else club
        html = self.html(at)
        self.assertIn("Friday &lt;b&gt;dice&lt;/b&gt;", html)  # the name is escaped
        self.assertIn("No games yet", html)

        store = self.stores[-1]
        clubs = store.on_game_over.__self__
        code, key = store.create_local(["Ann", "Bob <i>"], club=club)
        finish_game(store, code, key)

        html = self.html(self.page(club=club))
        self.assertIn("Ann", html)
        self.assertIn("Bob &lt;i&gt;", html)
        self.assertIn("Latest games", html)
        ratings = sorted(round(m["rating"]) for m in clubs.get(club)["members"].values())
        for rating in ratings:
            self.assertIn(f"<b>{rating}</b>", html)

        results = self.page(room=code)  # the same-device game opens on its results screen
        html = self.html(results)
        self.assertIn("Club rating · Friday &lt;b&gt;dice&lt;/b&gt;", html)
        self.assertIn("Games at this table: 1", html)
        self.assertTrue(any(b.label == "Club table" for b in results.button))


    def test_club_players_are_offered_by_name(self):
        """Owner (2026-11-19): in a club with games, pick a player or type a new name."""
        self.page()
        store = self.stores[-1]
        clubs = store.on_game_over.__self__
        club = clubs.create("Friday dice")
        page = self.page(club=club)
        self.assertTrue(any(w.key == "club_p1" for w in page.text_input))  # no players yet: a text box
        code, key = store.create_local(["Ann", "Bob"], club=club)
        finish_game(store, code, key)

        page = self.page(club=club)
        first, second = page.selectbox(key="club_p1-pick"), page.selectbox(key="club_p2-pick")
        self.assertEqual(sorted(first.options), ["Ann", "Bob"])
        first.select("Ann")
        second.select("Ann")
        next(b for b in page.button if b.label == "Start game").click().run()
        self.assertIn("Each player needs a different name.", [e.value for e in page.error])
        self.assertEqual(len(store._rooms), 1)  # no game started

        # Someone joining an online club game is offered the players not seated yet.
        online, _ = store.create("Bob", players=2, club=club)
        invite = self.page(room=online)
        self.assertEqual(invite.selectbox(key="join_name-pick").options, ["Ann"])

        type_new_option(page.selectbox(key="club_p2-pick"), "Zed")  # a new player, typed in
        next(b for b in page.button if b.label == "Start game").click().run()
        self.assertFalse(page.exception, [e.value for e in page.exception])
        room = store.view(page.session_state["room_code"])
        self.assertEqual((room.names, room.club), (["Ann", "Zed"], club))


if __name__ == "__main__":
    unittest.main()
