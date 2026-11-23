"""Fixes from the first real playtest: a place is held while somebody solves its mini-game,
and a hot-seat pick is locked in."""
import json

import pytest

import logic
from conftest import make_started, token_of, online_all

ON5 = {1, 2, 3, 4, 5}


def round_1():
    return logic.end_phase(make_started(5), "t1", ON5, 10)          # REVEAL → round 1


def open_place_name(game):
    return next(p["name"] for p in logic.map_view(game)["places"] if p["state"] == "open")


# ------------------------------------------------------------------ holding a place

def test_opening_a_place_holds_it_for_the_player():
    game = round_1()
    place = open_place_name(game)
    game = logic.open_place(game, "t2", place, 20)
    assert logic.place_holder(game, place, 21) == 2
    assert logic.my_hold(game, "t2", 21) == place and logic.my_hold(game, "t3", 21) is None


def test_nobody_else_can_open_or_search_a_held_place():
    game = round_1()
    place = open_place_name(game)
    game = logic.open_place(game, "t2", place, 20)
    with pytest.raises(logic.Rejected):
        logic.open_place(game, "t3", place, 21)
    with pytest.raises(logic.Rejected):
        logic.search(game, "t3", place, 21)
    assert place in logic.search(game, "t2", place, 22)["searched"]   # the holder can


def test_a_hold_runs_out():
    game = logic.open_place(round_1(), "t2", open_place_name(round_1()), 20)
    place = open_place_name(round_1())
    assert logic.place_holder(game, place, 20 + logic.HOLD_SECONDS) is None
    assert place in logic.search(game, "t3", place, 20 + logic.HOLD_SECONDS)["searched"]


def test_one_place_per_player():
    game = round_1()
    open_now = [p["name"] for p in logic.map_view(game)["places"] if p["state"] == "open"]
    game = logic.open_place(game, "t2", open_now[0], 20)
    game = logic.open_place(game, "t2", open_now[1], 21)          # changed their mind
    assert logic.place_holder(game, open_now[0], 22) is None
    assert logic.place_holder(game, open_now[1], 22) == 2


def test_holds_end_with_the_round_and_with_the_search():
    game = round_1()
    place = open_place_name(game)
    held = logic.open_place(game, "t2", place, 20)
    assert logic.busy_places(logic.search(held, "t2", place, 21), 22) == []
    assert logic.busy_places(logic.end_phase(held, "t1", ON5, 30), 31) == []   # round 2


def test_nobody_learns_who_holds_a_place():
    game = logic.open_place(round_1(), "t2", open_place_name(round_1()), 20)
    busy = logic.busy_places(game, 21)
    assert busy == [open_place_name(round_1())] and "2" not in json.dumps(busy)
    assert "holds" not in logic.public_view(game, online_all(game))


def test_a_player_who_has_moved_cannot_hold_a_place():
    game = round_1()
    clue = next(c for c in game["case"]["characters"] if c["pid"] == 2)["clues"][0]["id"]
    game = logic.share(game, "t2", clue, 20)
    with pytest.raises(logic.Rejected):
        logic.open_place(game, "t2", open_place_name(game), 21)


def test_demo_bots_leave_a_held_place_alone():
    lobby = logic.new_game("DEMO", 0)
    lobby = logic.join(lobby, "Ana", "human", 0)
    for _ in range(4):
        lobby = logic.add_bot(lobby, "human", 0)
    online = {p["pid"] for p in lobby["players"]}
    game = logic.start(lobby, "human", online, 0, seed=1)
    game = logic.end_phase(game, "human", online, 10)
    held = [p["name"] for p in logic.map_view(game)["places"] if p["state"] == "open"]
    # Every open place is held by somebody (set directly: one player can hold only one place).
    game["holds"] = {place: {"pid": 1, "until": 1000} for place in held}
    game = logic.bot_moves(game, 60)
    assert not set(game["searched"]) & set(held)


# ------------------------------------------------------------------ hot seat pick locked in

def test_a_hot_seat_pick_is_locked_in():
    game = make_lobby_hot()
    game = logic.pick_hot_seat(game, "t2", 3, 110)
    with pytest.raises(logic.Rejected):
        logic.pick_hot_seat(game, "t2", 4, 111)
    assert logic.my_hot_seat(game, "t2")["pick"] == 3


def make_lobby_hot():
    from conftest import make_lobby
    game = logic.start(make_lobby(5), "t1", ON5, 0, seed=1, hot_seat=True)
    game = logic.end_phase(game, "t1", ON5, 10)                 # → round 1
    return logic.end_phase(game, "t1", ON5, 100)                # → the hot seat break


# ------------------------------------------------------------------ "Create room" is quick

def test_creating_a_room_needs_few_database_round_trips_however_many_old_rooms_exist(tmp_path):
    import db
    real = db.connect(tmp_path / "rooms.db")
    long_ago = 1000.0
    for _ in range(12):                                          # yesterday's rooms
        db.create_room(real, long_ago)
    now = long_ago + db.ROOM_LIFETIME + 1

    class Counting:                                              # counts every statement sent
        def __init__(self, conn):
            self.conn, self.statements = conn, 0

        def execute(self, sql, params=()):
            self.statements += 1
            return self.conn.execute(sql, params)

    conn = Counting(real)
    code = db.create_room(conn, now)
    assert conn.statements <= 7                                  # was 3 + 2 per old room
    assert [row[0] for row in real.execute("SELECT code FROM rooms")] == [code]
    assert real.execute("SELECT COUNT(*) FROM presence").fetchone()[0] == 0


# ------------------------------------------------------------------ the board's suspect cards

def test_suspect_cards_come_quickly_and_then_stay_up_with_a_reading_note():
    import re
    import ui
    players = [{"pid": i, "name": f"P{i}", "role": ""} for i in range(1, 7)]
    html = ui.lineup(players)
    landed = [float(x) for x in re.findall(r"--in:([0-9.]+)s", html)]
    assert landed[-1] - landed[0] <= 5 * 0.7 + 0.01               # six cards in about 3.5 seconds
    assert ui.SUSPECTS_UNTIL - landed[-1] >= 14                    # then on screen for 14 s or more
    assert "Everybody is reading their file now" in html


# ------------------------------------------------------------------ watch the board, then read

def test_the_reveal_lasts_a_minute_twenty_seconds_watching_then_forty_reading():
    import ui
    assert logic.DURATIONS["REVEAL"] == 60
    assert logic.DURATIONS["REVEAL"] - ui.SUSPECTS_LAST_IN >= 40


def test_the_board_marks_the_start_of_its_intro_once_and_only_early():
    game = make_started(5)                                       # REVEAL from now = 0
    marked = logic.mark_board_intro(game, 2)
    assert logic.board_intro_at(marked) == 2
    assert logic.mark_board_intro(marked, 3) is marked           # only once
    assert logic.mark_board_intro(game, logic.BOARD_INTRO_LATE + 1) is game   # a late board: no wait
    later = logic.end_phase(marked, "t1", ON5, 30)
    assert logic.board_intro_at(later) is None                   # only in the reveal
