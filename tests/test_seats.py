"""
A seat belongs to the device that took it (owner, 2026-11-27, Backlog item 37: "We can't go to
google play having that"). Until then anyone with a game's link took any seat by tapping its
name. Now the device keeps a secret and the room its hash: the device comes back to its seat by
itself, and any other device has to be let in, by the seat's own device while that is here, by
another player once it is not.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka import api
from abaka.api import ApiError
from abaka.i18n import set_language
from abaka.repository import FileRepository
from abaka.rooms import (ASK_AGAIN_SECONDS, ASK_KEPT_SECONDS, SEAT_HERE_SECONDS, NotYours, RoomError, RoomStore,
                         TooFast, is_device, new_device)
from abaka.seats import requests_for

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # the base Python 3.8
    AppTest = None

APP = str(Path(__file__).resolve().parent.parent / "abaka_ui.py")
ANN, BOB, NEW, OTHER = "anns-phone-000000001", "bobs-phone-000000001", "a-new-phone-00000001", "someone-elses-000001"


class Clock:
    """The store's clock, moved by hand."""

    def __init__(self, test):
        self.now = rooms.time.time()
        patcher = mock.patch.object(rooms.time, "time", lambda: self.now)
        patcher.start()
        test.addCleanup(patcher.stop)

    def pass_(self, seconds):
        self.now += seconds


class TestSeats(unittest.TestCase):
    def setUp(self):
        self.clock = Clock(self)
        self.store = RoomStore(starting_throw=False)
        self.code, self.ann = self.store.create("Ann", device=ANN)
        self.key = self.store.view(self.code).key
        self.bob = self.store.join(self.code, "Bob", self.key, BOB)

    def here(self, token):
        self.store.seen(self.code, token)

    def asks(self):
        return [(a["seat"], a["open"]) for a in self.store.view(self.code).asks]

    def test_the_link_alone_takes_no_seat(self):
        for device in (None, "", OTHER, BOB, "short", ANN + "!", 7):
            with self.subTest(device=device):
                with self.assertRaises(NotYours):
                    self.store.reclaim(self.code, 0, self.key, device)
        self.assertEqual(self.store.seat_of(self.code, self.ann), 0)  # Ann plays on
        self.assertIsNone(self.store.device_seat(self.code, self.key, OTHER))

    def test_a_device_comes_back_to_its_own_seat(self):
        self.assertEqual(self.store.device_seat(self.code, self.key, BOB), 1)
        again = self.store.reclaim(self.code, 1, self.key, BOB)
        self.assertIsNone(self.store.seat_of(self.code, self.bob))  # the tab it had before lost the seat
        self.assertEqual(self.store.seat_of(self.code, again), 1)
        self.store.roll(self.code, self.ann)

    def test_the_seats_devices_are_saved_as_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RoomStore(repository=FileRepository(folder), starting_throw=False)
            code, _ = store.create("Ann", device=ANN)
            key = store.view(code).key
            store.join(code, "Bob", key, BOB)
            saved = "".join(p.read_text() for p in Path(folder).glob("*.json"))
            self.assertNotIn(ANN, saved)
            self.assertNotIn(BOB, saved)
            later = RoomStore(repository=FileRepository(folder), starting_throw=False)
            self.assertEqual(later.device_seat(code, key, BOB), 1)
            with self.assertRaises(NotYours):
                later.reclaim(code, 1, key, ANN)
            self.assertEqual(later.seat_of(code, later.reclaim(code, 1, key, BOB)), 1)

    def test_a_game_saved_before_keeps_the_device_its_page_is_on(self):
        store = RoomStore(starting_throw=False)
        code, ann = store.create("Ann")              # no device: as a game saved before
        key = store.view(code).key
        store.join(code, "Bob", key)
        with self.assertRaises(NotYours):
            store.reclaim(code, 0, key, ANN)
        version = store.view(code).version
        store.own(code, ann, ANN)                    # Ann's open page says which browser it is
        store.own(code, "not a token", OTHER)
        self.assertEqual(store.view(code).version, version)  # not a move: no click is refused for it
        self.assertEqual(store.device_seat(code, key, ANN), 0)
        self.assertIsNone(store.device_seat(code, key, OTHER))

    def test_the_seats_own_device_lets_another_in(self):
        self.here(self.bob)
        seen = self.store.seen(self.code)
        ticket = self.store.ask(self.code, 1, self.key, NEW)
        self.assertNotEqual(self.store.seen(self.code), seen)  # the pages notice
        self.assertEqual(self.asks(), [(1, False)])
        view = self.store.view(self.code)
        self.assertEqual(requests_for(view.asks, view.names, 0), [])  # Bob is here: not Ann's to answer
        mine = requests_for(view.asks, view.names, 1)
        self.assertEqual([(r["seat"], r["yours"], r["title"]) for r in mine], [(1, True, "Is this you on another device?")])
        with self.assertRaisesRegex(RoomError, "is here and decides"):
            self.store.answer(self.code, self.ann, 1, True)
        self.assertEqual(self.store.asked(self.code, 1, self.key, ticket, NEW), ("waiting", None))
        self.store.answer(self.code, self.bob, 1, True)
        # Let in, but not come yet: Bob's old device still plays, so nobody is locked out by a yes.
        self.assertEqual(self.store.seat_of(self.code, self.bob), 1)
        status, token = self.store.asked(self.code, 1, self.key, ticket, NEW)
        self.assertEqual((status, self.store.seat_of(self.code, token)), ("in", 1))
        self.assertIsNone(self.store.seat_of(self.code, self.bob))
        self.assertEqual(self.asks(), [])
        # The seat is the new device's now, and no longer the old one's.
        self.assertEqual(self.store.device_seat(self.code, self.key, NEW), 1)
        with self.assertRaises(NotYours):
            self.store.reclaim(self.code, 1, self.key, BOB)

    def test_the_table_decides_once_the_seats_device_is_not_here(self):
        self.here(self.bob)
        self.clock.pass_(SEAT_HERE_SECONDS + 1)
        ticket = self.store.ask(self.code, 1, self.key, NEW)
        self.assertEqual(self.asks(), [(1, True)])
        view = self.store.view(self.code)
        theirs = requests_for(view.asks, view.names, 0)
        self.assertEqual([(r["seat"], r["yours"], r["title"]) for r in theirs], [(1, False, "Bob asks to come back")])
        # Bob's device shows up again before anyone answered: it is his to answer after all.
        self.here(self.bob)
        self.assertEqual(self.asks(), [(1, False)])
        with self.assertRaises(RoomError):
            self.store.answer(self.code, self.ann, 1, True)
        self.clock.pass_(SEAT_HERE_SECONDS + 1)
        self.store.asked(self.code, 1, self.key, ticket, NEW)
        seen = self.store.seen(self.code, self.ann)   # Ann's page checks the game: it notices
        self.assertEqual(self.asks(), [(1, True)])
        self.store.answer(self.code, self.ann, 1, True)
        self.assertNotEqual(self.store.seen(self.code), seen)
        self.assertEqual(self.store.asked(self.code, 1, self.key, ticket, NEW)[0], "in")

    def test_only_a_seated_player_answers(self):
        self.clock.pass_(SEAT_HERE_SECONDS + 1)
        self.store.ask(self.code, 1, self.key, NEW)
        with self.assertRaisesRegex(RoomError, "not seated"):
            self.store.answer(self.code, "not a token", 1, True)
        with self.assertRaisesRegex(RoomError, "Nobody is asking"):
            self.store.answer(self.code, self.bob, 0, True)

    def test_a_refusal(self):
        ticket = self.store.ask(self.code, 1, self.key, NEW)
        self.store.answer(self.code, self.bob, 1, False)
        self.assertEqual(self.store.asked(self.code, 1, self.key, ticket, NEW), ("refused", None))
        self.assertEqual(self.store.seat_of(self.code, self.bob), 1)
        with self.assertRaises(TooFast):   # no nagging: not at once again, from any device
            self.store.ask(self.code, 1, self.key, OTHER)
        self.clock.pass_(ASK_AGAIN_SECONDS + 1)
        self.store.ask(self.code, 1, self.key, NEW)

    def test_one_request_per_seat_and_per_device(self):
        first = self.store.ask(self.code, 1, self.key, NEW)
        with self.assertRaises(TooFast):
            self.store.ask(self.code, 1, self.key, OTHER)
        second = self.store.ask(self.code, 0, self.key, NEW)   # it asks for the other seat instead
        self.assertEqual(self.asks(), [(0, True)])
        self.assertEqual(self.store.asked(self.code, 1, self.key, first, NEW), ("gone", None))
        # Another device's ticket, or this one's with another device, is nobody's request.
        self.assertEqual(self.store.asked(self.code, 0, self.key, second, OTHER), ("gone", None))
        self.assertEqual(self.store.asked(self.code, 0, self.key, "x" * 22, NEW), ("gone", None))
        self.assertEqual(self.store.asked(self.code, 0, self.key, second, NEW), ("waiting", None))

    def test_a_request_nobody_asks_about_lapses(self):
        ticket = self.store.ask(self.code, 1, self.key, NEW)
        self.clock.pass_(ASK_KEPT_SECONDS + 1)
        self.store.seen(self.code, self.ann)
        self.assertEqual(self.asks(), [])
        self.assertEqual(self.store.asked(self.code, 1, self.key, ticket, NEW), ("gone", None))

    def test_asking_needs_the_key_a_device_and_an_online_game(self):
        with self.assertRaisesRegex(RoomError, "Game not found"):
            self.store.ask(self.code, 1, "WRONGKEY", NEW)
        for device, seat in ((None, 1), ("short", 1), (NEW, 5), (NEW, -1)):
            with self.assertRaises(RoomError):
                self.store.ask(self.code, seat, self.key, device)
        local, token = self.store.create_local(["Ann", "Bob"])
        key = self.store.view(local).key
        with self.assertRaises(RoomError):
            self.store.ask(local, 0, key, NEW)
        self.assertEqual(self.store.reclaim(local, 0, key), token)  # one device plays it: its link carries on

    def test_leaving_the_waiting_room_moves_the_devices_up(self):
        code, ann = self.store.create("Ann", players=3, device=ANN)
        key = self.store.view(code).key
        self.store.join(code, "Bob", key, BOB)
        self.store.ask(code, 0, key, NEW)
        self.store.leave(code, ann)
        self.assertEqual(self.store.view(code).asks, ())
        self.assertEqual(self.store.device_seat(code, key, BOB), 0)
        self.assertIsNone(self.store.device_seat(code, key, ANN))

    def test_a_secret_for_a_device(self):
        secrets = {new_device() for _ in range(50)}
        self.assertEqual(len(secrets), 50)
        self.assertTrue(all(is_device(s) for s in secrets))
        for bad in (None, "", "short", "with space 0000000000", "x" * 129, "кириллица-0000000000", 12345678901234567):
            self.assertFalse(is_device(bad), bad)


class TestApi(unittest.TestCase):
    def setUp(self):
        self.store = RoomStore(starting_throw=False)
        self.addCleanup(set_language, "en")

    def call(self, **request):
        return api.handle(request, self.store)

    def refused(self, **request):
        with self.assertRaises(ApiError) as caught:
            self.call(**request)
        return caught.exception.code

    def test_the_device_takes_and_holds_the_seat(self):
        device = self.call(op="device")["device"]
        self.assertTrue(is_device(device))
        made = self.call(op="create", name="Ann", device=device)
        code, key = made["code"], made["state"]["key"]
        self.call(op="join", code=code, key=key, name="Bob", device=BOB)
        invite = self.call(op="state", code=code, key=key, device=device)["state"]
        self.assertEqual((invite["held"], invite["can"]), (0, ["rejoin", "ask"]))
        self.assertIsNone(self.call(op="state", code=code, key=key, device=OTHER)["state"]["held"])
        self.assertIsNone(self.call(op="state", code=code, key=key)["state"]["held"])
        for wrong in ({}, {"device": OTHER}, {"device": BOB}):
            self.assertEqual(self.refused(op="rejoin", code=code, key=key, seat=0, **wrong), "not_yours")
        self.assertEqual(self.refused(op="rejoin", code=code, key=key, seat=0, device="short"), "bad_request")
        self.assertEqual(self.refused(op="ask", code=code, key=key, seat=0), "bad_request")
        back = self.call(op="rejoin", code=code, key=key, seat=0, device=device)
        self.assertEqual(back["state"]["you"], 0)
        self.assertEqual(self.refused(op="roll", code=code, token=made["token"], version=back["state"]["version"]),
                         "not_seated")

    def test_the_words_of_a_request_in_the_players_language(self):
        made = self.call(op="create", name="Ann", device=ANN)
        code, key = made["code"], made["state"]["key"]
        bob = self.call(op="join", code=code, key=key, name="Bob", device=BOB)["token"]
        ticket = self.call(op="ask", code=code, key=key, seat=0, device=NEW)["ticket"]
        state = self.call(op="state", code=code, token=bob, lang="ru")["state"]   # Ann's device is not here
        self.assertEqual([(a["seat"], a["name"], a["yours"]) for a in state["asks"]], [(0, "Ann", False)])
        self.assertIn("Ann", state["asks"][0]["title"])
        self.assertIn("другом устройстве", state["asks"][0]["text"])
        self.assertIn("answer", state["can"])
        self.assertEqual(self.refused(op="answer", code=code, token=bob, seat=0, let_in="yes"), "bad_request")
        after = self.call(op="answer", code=code, token=bob, seat=0, let_in=False)["state"]
        self.assertEqual((after["asks"], "answer" in after["can"]), ([], False))
        self.assertEqual(self.call(op="asked", code=code, key=key, seat=0, ticket=ticket, device=NEW), {"status": "refused"})
        self.assertEqual(self.refused(op="ask", code=code, key=key, seat=0, device=NEW), "too_fast")
        outsider = self.call(op="state", code=code, key=key)["state"]
        self.assertEqual(outsider["asks"], [])   # only the table sees who asks


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestPages(unittest.TestCase):
    def setUp(self):
        stores = self.stores = []

        class FreshRoomStore(rooms.RoomStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                stores.append(self)

        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        rooms.RoomStore = FreshRoomStore
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": ""})
        env.start()
        self.addCleanup(env.stop)
        code_version.mark_current()
        # AppTest 1.48 reads every button group's value as a list (see test_shown_dice.py).
        from streamlit.testing.v1 import element_tree
        if not hasattr(element_tree.ButtonGroup, "_is_single_select"):
            group_value = element_tree.ButtonGroup.value.fget

            def one_or_more(group):
                value = group_value(group)
                return [] if value is None else value if isinstance(value, list) else [value]

            patcher = mock.patch.object(element_tree.ButtonGroup, "value", property(one_or_more))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.page()
        self.store = self.stores[-1]

    def page(self, room=None, **state):
        at = AppTest.from_file(APP, default_timeout=30)
        if room is not None:
            at.query_params["room"] = room
        for name, value in state.items():
            at.session_state[name] = value
        return self.go(at)

    def go(self, at):
        at = at.run()  # a page, or a button of it that was just clicked
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    @staticmethod
    def html(at):
        return "\n".join(n.proto.body for n in at.get("html"))

    @staticmethod
    def keys(at):
        return {b.key for b in at.button if b.key}

    def game(self, started=True):
        code, ann = self.store.create("Ann", players=2 if started else 3, device=ANN)
        key = self.store.view(code).key
        bob = self.store.join(code, "Bob <b>", key, BOB)
        return code, ann, bob, rooms.full_code(code, key)

    def test_a_visitor_with_the_link_has_to_be_let_in(self):
        code, ann, bob, link = self.game()
        bobs = self.page(room=link, room_code=code, seat_token=bob, device=BOB)   # Bob's page is open
        anns = self.page(room=link, room_code=code, seat_token=ann, device=ANN)
        visitor = self.page(room=link, device=NEW)
        self.assertIsNone(visitor.session_state["room_code"])       # the link alone seats nobody
        self.assertEqual(self.keys(visitor) & {"come-back", "rejoin-0", "rejoin-1"}, {"rejoin-0", "rejoin-1"})
        self.go(visitor.button(key="rejoin-1").click())
        self.assertIsNone(visitor.session_state["room_code"])
        self.assertEqual(self.store.seat_of(code, bob), 1)          # Bob plays on
        self.assertIn("Asked to come back as Bob &lt;b&gt;", self.html(visitor))
        self.assertNotIn("rejoin-0", self.keys(visitor))
        # Bob's own page asks him, and Ann's does not: Bob is here.
        self.go(bobs)
        self.assertIn("Is this you on another device?", self.html(bobs))
        self.assertIn("ask-yes-1", self.keys(bobs))
        self.go(anns)
        self.assertNotIn("ask-yes-1", self.keys(anns))
        self.go(bobs.button(key="ask-yes-1").click())
        self.go(visitor)                                           # its check finds it was let in
        self.assertEqual(visitor.session_state["room_code"], code)
        self.assertEqual(self.store.seat_of(code, visitor.session_state["seat_token"]), 1)
        self.assertIsNone(self.store.seat_of(code, bob))

    def test_another_player_lets_in_once_the_seats_device_is_gone_and_names_stay_text(self):
        code, ann, bob, link = self.game()
        anns = self.page(room=link, room_code=code, seat_token=ann, device=ANN)
        visitor = self.page(room=link, device=NEW)
        self.go(visitor.button(key="rejoin-1").click())            # Bob's page was never open here
        self.go(anns)
        html = self.html(anns)
        self.assertIn("Bob &lt;b&gt; asks to come back", html)
        self.assertNotIn("Bob <b> asks", html)
        self.go(anns.button(key="ask-no-1").click())
        self.assertNotIn("ask-no-1", self.keys(anns))
        self.go(visitor)
        self.assertIsNone(visitor.session_state["room_code"])
        self.assertIn("The request was refused.", [w.value for w in visitor.warning])
        self.assertIn("rejoin-1", self.keys(visitor))               # back at the invite

    def test_the_same_browser_comes_straight_back_after_a_reload(self):
        code, ann, bob, link = self.game()
        reloaded = self.page(room=link, device=BOB)                 # a new session, the browser's cookie
        self.assertEqual(reloaded.session_state["room_code"], code)
        self.assertEqual(self.store.seat_of(code, reloaded.session_state["seat_token"]), 1)
        self.assertIsNone(self.store.seat_of(code, bob))

    def test_a_tab_that_lost_its_seat_to_another_tab_does_not_take_it_back_by_itself(self):
        code, ann, bob, link = self.game()
        second = self.store.reclaim(code, 1, self.store.view(code).key, BOB)   # the same browser's other tab
        first = self.page(room=link, room_code=code, seat_token=bob, device=BOB)
        self.assertIsNone(first.session_state["room_code"])
        self.assertTrue(any("another tab" in w.value for w in first.warning))
        self.go(first)                                             # a later run of that tab
        self.assertIsNone(first.session_state["room_code"])
        self.assertEqual(self.store.seat_of(code, second), 1)
        self.assertIn("come-back", self.keys(first))                # one tap, if the player wants it here
        self.go(first.button(key="come-back").click())
        self.assertEqual(first.session_state["room_code"], code)

    def test_in_the_waiting_room_the_browsers_seat_is_one_tap_away(self):
        code, ann, bob, link = self.game(started=False)
        back = self.page(room=link, device=BOB)
        self.assertIsNone(back.session_state["room_code"])          # the page still offers to join as someone new
        self.assertEqual(self.keys(back) & {"come-back", "rejoin-0", "rejoin-1"}, {"come-back", "rejoin-0"})
        self.go(back.button(key="come-back").click())
        self.assertEqual(self.store.seat_of(code, back.session_state["seat_token"]), 1)

    def test_a_page_open_since_before_keeps_its_browser_for_its_seat(self):
        code, ann = self.store.create("Ann")                        # seats taken before devices were remembered
        key = self.store.view(code).key
        self.store.join(code, "Bob", key)
        self.page(room=rooms.full_code(code, key), room_code=code, seat_token=ann, device=ANN)
        self.assertEqual(self.store.device_seat(code, key, ANN), 0)
        reloaded = self.page(room=rooms.full_code(code, key), device=ANN)
        self.assertEqual(reloaded.session_state["room_code"], code)


if __name__ == "__main__":
    unittest.main()
