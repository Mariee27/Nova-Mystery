"""The hot seat between two investigation rounds: pick a suspect, grill them out loud, rate
believe or lie. Allowed and refused cases for every rule, the views (counts only), the clock,
the switch in start()."""
import json

import pytest

import logic
from conftest import make_lobby, token_of, online_all

ONLINE = {1, 2, 3, 4, 5}


def started(hot_seat=True, n=5):
    game = make_lobby(n)
    return logic.start(game, "t1", set(range(1, n + 1)), 0, seed=1, hot_seat=hot_seat)


def break_after_round_1(n=5):
    """REVEAL → round 1 → the host ends round 1 at now=100: the break begins."""
    game = logic.end_phase(started(n=n), "t1", ONLINE, 10)          # → round 1
    return logic.end_phase(game, "t1", ONLINE, 100)                  # → hot seat


def pick_all(game, target, now=110, but=()):
    """Everybody picks `target`; the target themself picks player 1 (or 2)."""
    for pid in logic._player_ids(game):
        if pid not in but:
            choice = target if pid != target else (1 if target != 1 else 2)
            game = logic.pick_hot_seat(game, token_of(game, pid), choice, now)
    return game


def seated(target=3):
    return logic.tick(pick_all(break_after_round_1(), target), ONLINE, 111)


# ------------------------------------------------------------------ when it happens

def test_without_the_switch_the_rounds_follow_each_other_directly():
    game = logic.end_phase(started(hot_seat=False), "t1", ONLINE, 10)
    game = logic.end_phase(game, "t1", ONLINE, 100)
    assert game["round"] == 2 and logic.hot_seat_view(game) is None


def test_after_round_1_comes_a_break_with_the_hot_seat():
    game = break_after_round_1()
    view = logic.hot_seat_view(game)
    assert game["phase"] == "INVESTIGATION" and game["round"] == 1      # round 1 is finished
    assert view["after_round"] == 1 and view["seat"] is None and view["picked"] == 0
    assert view["until"] == 100 + logic.HOT_SEAT_PICK_SECONDS


def test_after_the_last_round_comes_the_discussion_without_a_hot_seat():
    game = started()
    while game["phase"] != "DISCUSSION":
        game = logic.end_phase(game, "t1", ONLINE, 10)
    assert logic.hot_seat_view(game) is None
    # Two breaks (after round 1 and 2) were opened on the way, none after round 3.
    with pytest.raises(logic.Rejected):
        logic.pick_hot_seat(game, "t1", 2, 20)


def test_nobody_can_search_or_share_during_the_break():
    game = break_after_round_1()
    place = logic.story_of(game)["locations"][0]
    with pytest.raises(logic.Rejected):
        logic.search(game, "t2", place, 101)


def test_the_host_can_end_the_break_and_the_next_round_starts():
    game = logic.end_phase(seated(), "t1", ONLINE, 120)
    assert game["round"] == 2 and logic.hot_seat_view(game) is None and game["acted"] == []
    assert game["hot_seat"]["history"][0]["pid"] == 3


# ------------------------------------------------------------------ picking

def test_you_cannot_pick_yourself():
    with pytest.raises(logic.Rejected):
        logic.pick_hot_seat(break_after_round_1(), "t2", 2, 110)


def test_the_seat_starts_when_everybody_online_has_picked():
    game = pick_all(break_after_round_1(), 3, but={1})
    assert logic.tick(game, ONLINE, 111) is game            # player 1 has not picked yet
    game = logic.pick_hot_seat(game, "t1", 3, 112)
    game = logic.tick(game, ONLINE, 113)
    assert game["hot_seat"]["seat"] == 3
    assert game["deadline"] == 113 + logic.HOT_SEAT_SECONDS


def test_after_the_picking_time_the_picks_so_far_count():
    game = logic.pick_hot_seat(break_after_round_1(), "t2", 4, 105)
    assert logic.tick(game, ONLINE, 100 + logic.HOT_SEAT_PICK_SECONDS - 1) is game
    game = logic.tick(game, ONLINE, 100 + logic.HOT_SEAT_PICK_SECONDS)
    assert game["hot_seat"]["seat"] == 4                   # nobody waits for a slow player


def test_with_no_pick_at_all_the_next_round_simply_starts():
    game = logic.tick(break_after_round_1(), ONLINE, 100 + logic.HOT_SEAT_PICK_SECONDS)
    assert game["round"] == 2 and logic.hot_seat_view(game) is None
    assert game["hot_seat"]["history"] == []


def test_most_picks_win():
    game = break_after_round_1()
    for voter, target in [(1, 4), (2, 4), (3, 2), (4, 2), (5, 4)]:
        game = logic.pick_hot_seat(game, token_of(game, voter), target, 110)
    assert logic.tick(game, ONLINE, 111)["hot_seat"]["seat"] == 4


def test_a_tie_is_decided_by_chance_but_the_same_game_always_gives_the_same_answer():
    game = break_after_round_1()
    for voter, target in [(1, 4), (2, 3), (3, 4), (4, 3)]:
        game = logic.pick_hot_seat(game, token_of(game, voter), target, 110)
    seat = logic.start_hot_seat(game, "t1", 111)["hot_seat"]["seat"]
    assert seat in (3, 4)                                   # 2 : 2, one of the two
    assert logic.start_hot_seat(game, "t1", 112)["hot_seat"]["seat"] == seat   # reproducible
    winners = {logic.hot_seat_tie(dict(game, code=code), [3, 4])
               for code in ["ABCD", "BCDF", "CDFG", "DFGH", "FGHJ", "GHJK", "HJKL", "JKLM"]}
    assert winners == {3, 4}                                # over many rooms both get it


def test_only_the_host_can_start_early_and_only_with_a_pick():
    game = break_after_round_1()
    with pytest.raises(logic.Rejected):
        logic.start_hot_seat(game, "t1", 110)              # nobody has picked
    game = logic.pick_hot_seat(game, "t2", 5, 110)
    with pytest.raises(logic.Rejected):
        logic.start_hot_seat(game, "t2", 111)              # not the host
    assert logic.start_hot_seat(game, "t1", 111)["hot_seat"]["seat"] == 5


# ------------------------------------------------------------------ rating and the clock

def test_rating_rules():
    game = seated(3)
    with pytest.raises(logic.Rejected):
        logic.rate_hot_seat(game, "t3", "lie", 112)        # the suspect cannot rate themselves
    with pytest.raises(logic.Rejected):
        logic.rate_hot_seat(game, "t1", "maybe", 112)      # only believe or lie
    with pytest.raises(logic.Rejected):
        logic.pick_hot_seat(game, "t1", 2, 112)            # no new pick while someone sits there
    game = logic.rate_hot_seat(game, "t1", "lie", 112)
    game = logic.rate_hot_seat(game, "t1", "believe", 113)  # you may change your mind
    game = logic.rate_hot_seat(game, "t2", "lie", 113)
    view = logic.hot_seat_view(game)
    assert (view["believe"], view["lie"]) == (1, 1)


def test_rating_before_anybody_sits_there_is_refused():
    with pytest.raises(logic.Rejected):
        logic.rate_hot_seat(break_after_round_1(), "t1", "lie", 110)


def test_on_time_the_counts_are_kept_and_round_2_starts():
    game = logic.rate_hot_seat(seated(3), "t1", "lie", 112)
    end = game["deadline"]
    assert logic.tick(game, ONLINE, end - 1)["hot_seat"]["seat"] == 3
    game = logic.tick(game, ONLINE, end)
    assert game["round"] == 2 and game["deadline"] == end + logic.DURATIONS["INVESTIGATION"]
    assert game["hot_seat"]["history"] == [{"pid": 3, "after_round": 1, "believe": 0, "lie": 1}]


def test_nobody_sits_there_twice():
    game = logic.end_phase(seated(3), "t1", ONLINE, 120)        # → round 2
    game = logic.end_phase(game, "t1", ONLINE, 200)             # → second break
    assert 3 not in logic.hot_seat_view(game)["candidates"]
    with pytest.raises(logic.Rejected):
        logic.pick_hot_seat(game, "t1", 3, 201)


# ------------------------------------------------------------------ views

def test_the_board_sees_how_many_picked_but_never_whom():
    game = logic.pick_hot_seat(break_after_round_1(), "t1", 4, 110)
    view = logic.hot_seat_view(game)
    assert view["picked"] == 1 and "picks" not in view
    assert "t1" not in json.dumps(view)
    assert logic.my_hot_seat(game, "t1") == {"pick": 4, "rating": None}
    assert logic.my_hot_seat(game, "t2") == {"pick": None, "rating": None}
    assert logic.my_hot_seat(game, "nobody") is None


def test_the_public_and_private_views_keep_their_contract():
    game = logic.pick_hot_seat(break_after_round_1(), "t1", 4, 110)
    assert "hot_seat" not in logic.public_view(game, online_all(game))
    assert "hot_seat" not in json.dumps(logic.private_view(game, "t1"))


# ---------------------------------------------------------------- the hot seat waits for the reader

def test_the_picking_clock_waits_for_the_player_who_reads_their_evidence():
    import minigames
    g = logic.new_game("ABCD", 0, minigames=True)
    for i in range(1, 5):
        g = logic.join(g, f"P{i}", f"t{i}", 0)
    g = logic.start(g, "t1", {1, 2, 3, 4}, 0, seed=7, hot_seat=True)
    g = logic.end_phase(g, "t1", {1, 2, 3, 4}, 1)
    place = next(s["location"] for s in minigames.specs(g) if logic.locked_until(g, s["location"]) is None)
    g = logic.search(g, "t1", place, 10, proof=minigames.solve(g, place))
    assert g["reading"] == [1]                                   # "Access granted" on P1's phone
    g = logic.end_phase(g, "t1", {1, 2, 3, 4}, 11)               # the round ends: the break opens
    assert logic.hot_seat_open(g)
    assert logic.hot_seat_view(g)["reading"] and g["deadline"] == 11 + logic.READING_MAX + logic.HOT_SEAT_PICK_SECONDS
    g = logic.done_reading(g, "t1", 20)                          # P1 taps Continue
    assert g["deadline"] == 20 + logic.HOT_SEAT_PICK_SECONDS and not logic.hot_seat_view(g)["reading"]
    assert logic.done_reading(g, "t2", 21) is g                  # somebody who was not reading: nothing


def test_without_a_reader_the_picking_clock_starts_at_once():
    g = logic.new_game("ABCD", 0, minigames=True)
    for i in range(1, 5):
        g = logic.join(g, f"P{i}", f"t{i}", 0)
    g = logic.start(g, "t1", {1, 2, 3, 4}, 0, seed=7, hot_seat=True)
    g = logic.end_phase(g, "t1", {1, 2, 3, 4}, 1)
    g = logic.end_phase(g, "t1", {1, 2, 3, 4}, 5)
    assert logic.hot_seat_open(g) and g["deadline"] == 5 + logic.HOT_SEAT_PICK_SECONDS
