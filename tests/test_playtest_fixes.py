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
