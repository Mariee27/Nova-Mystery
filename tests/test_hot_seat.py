"""The hot seat in the discussion: pick a suspect, grill them out loud, rate believe or lie.
Allowed and refused cases for every rule, the views (counts only) and the demo bots."""
import json

import pytest

import logic
from conftest import make_started, token_of, online_all

ONLINE = {1, 2, 3, 4, 5}


def discussion(n=5):
    """A started game whose host has ended every step up to the discussion (at now=10)."""
    game = make_started(n)
    while game["phase"] != "DISCUSSION":
        game = logic.end_phase(game, "t1", online_all(game), 10)
    return game


def pick_all(game, target, now=20, but=()):
    """Everybody picks `target`; the target themself picks player 1 (or 2)."""
    for pid in logic._player_ids(game):
        if pid not in but:
            choice = target if pid != target else (1 if target != 1 else 2)
            game = logic.pick_hot_seat(game, token_of(game, pid), choice, now)
    return game


def test_every_discussion_starts_with_an_empty_hot_seat():
    game = discussion()
    view = logic.hot_seat_view(game)
    assert view["seat"] is None and view["picked"] == 0 and view["history"] == []
    assert view["candidates"] == [1, 2, 3, 4, 5]


def test_hot_seat_only_exists_in_the_discussion():
    game = make_started(5)
    assert logic.hot_seat_view(game) is None
    with pytest.raises(logic.Rejected):
        logic.pick_hot_seat(game, "t1", 2, 5)


def test_you_cannot_pick_yourself():
    with pytest.raises(logic.Rejected):
        logic.pick_hot_seat(discussion(), "t2", 2, 20)


def test_the_seat_starts_when_everybody_online_has_picked():
    game = pick_all(discussion(), 3, but={1})
    assert logic.tick(game, ONLINE, 21) is game            # player 1 has not picked yet: nothing
    game = logic.pick_hot_seat(game, "t1", 3, 22)
    game = logic.tick(game, ONLINE, 23)
    assert game["hot_seat"]["seat"] == 3
    assert game["hot_seat"]["until"] == 23 + logic.HOT_SEAT_SECONDS
    assert game["phase"] == "DISCUSSION"


def test_most_picks_win():
    game = discussion()
    for voter, target in [(1, 4), (2, 4), (3, 2), (4, 2), (5, 4)]:
        game = logic.pick_hot_seat(game, token_of(game, voter), target, 20)
    assert logic.tick(game, ONLINE, 21)["hot_seat"]["seat"] == 4


def test_a_tie_is_decided_by_chance_but_the_same_game_always_gives_the_same_answer():
    game = discussion()
    for voter, target in [(1, 4), (2, 3), (3, 4), (4, 3)]:
        game = logic.pick_hot_seat(game, token_of(game, voter), target, 20)
    seat = logic.start_hot_seat(game, "t1", 21)["hot_seat"]["seat"]
    assert seat in (3, 4)                                     # 2 : 2, one of the two
    assert logic.start_hot_seat(game, "t1", 22)["hot_seat"]["seat"] == seat   # reproducible
    # Over many rooms both tied suspects get the seat sometimes: it is not always the same one.
    winners = set()
    for code in ["ABCD", "BCDF", "CDFG", "DFGH", "FGHJ", "GHJK", "HJKL", "JKLM"]:
        room = dict(game, code=code)
        winners.add(logic.hot_seat_tie(room, [3, 4]))
    assert winners == {3, 4}


def test_no_tie_means_no_chance():
    assert logic.hot_seat_tie(discussion(), [5]) == 5


def test_only_the_host_can_start_early_and_only_with_a_pick():
    game = discussion()
    with pytest.raises(logic.Rejected):
        logic.start_hot_seat(game, "t1", 20)                 # nobody has picked
    game = logic.pick_hot_seat(game, "t2", 5, 20)
    with pytest.raises(logic.Rejected):
        logic.start_hot_seat(game, "t2", 21)                 # not the host
    assert logic.start_hot_seat(game, "t1", 21)["hot_seat"]["seat"] == 5


def test_rating_rules():
    game = logic.tick(pick_all(discussion(), 3), ONLINE, 21)
    with pytest.raises(logic.Rejected):
        logic.rate_hot_seat(game, "t3", "lie", 22)           # the suspect cannot rate themselves
    with pytest.raises(logic.Rejected):
        logic.rate_hot_seat(game, "t1", "maybe", 22)         # only believe or lie
    with pytest.raises(logic.Rejected):
        logic.pick_hot_seat(game, "t1", 2, 22)               # no new pick while someone sits there
    game = logic.rate_hot_seat(game, "t1", "lie", 22)
    game = logic.rate_hot_seat(game, "t1", "believe", 23)    # you may change your mind
    game = logic.rate_hot_seat(game, "t2", "lie", 23)
    view = logic.hot_seat_view(game)
    assert (view["believe"], view["lie"]) == (1, 1)


def test_rating_without_a_seat_is_refused():
    with pytest.raises(logic.Rejected):
        logic.rate_hot_seat(discussion(), "t1", "lie", 20)


def test_the_seat_ends_on_time_and_nobody_sits_there_twice():
    game = logic.tick(pick_all(discussion(), 3), ONLINE, 21)
    game = logic.rate_hot_seat(game, "t1", "lie", 22)
    until = game["hot_seat"]["until"]
    assert logic.tick(game, ONLINE, until - 1)["hot_seat"]["seat"] == 3
    game = logic.tick(game, ONLINE, until)
    hot = logic.hot_seat_view(game)
    assert hot["seat"] is None and hot["history"] == [{"pid": 3, "believe": 0, "lie": 1}]
    assert 3 not in hot["candidates"]
    with pytest.raises(logic.Rejected):
        logic.pick_hot_seat(game, "t1", 3, until + 1)


def test_the_board_sees_counts_but_never_who_picked_or_rated_whom():
    game = logic.pick_hot_seat(discussion(), "t1", 4, 20)
    view = logic.hot_seat_view(game)
    assert view["picks"] == {4: 1} and view["picked"] == 1
    text = json.dumps(view)
    assert "t1" not in text and '"1"' not in text            # no voter ids, no tokens
    assert logic.my_hot_seat(game, "t1") == {"pick": 4, "rating": None}
    assert logic.my_hot_seat(game, "t2") == {"pick": None, "rating": None}
    assert logic.my_hot_seat(game, "nobody") is None


def test_the_public_and_private_views_keep_their_contract():
    game = logic.pick_hot_seat(discussion(), "t1", 4, 20)
    assert "hot_seat" not in logic.public_view(game, ONLINE)
    assert "hot_seat" not in json.dumps(logic.private_view(game, "t1"))


def test_demo_bots_pick_and_rate():
    lobby = logic.new_game("DEMO", 0)
    lobby = logic.join(lobby, "Ana", "human", 0)
    for _ in range(4):
        lobby = logic.add_bot(lobby, "human", 0)
    online = {p["pid"] for p in lobby["players"]}
    game = logic.start(lobby, "human", online, 0, seed=1)
    while game["phase"] != "DISCUSSION":
        game = logic.end_phase(game, "human", online, 10)
    game = logic.bot_moves(game, 10 + 60)                    # all bots are due
    assert len(game["hot_seat"]["picks"]) == 4               # every bot has picked, the human not yet
    game = logic.pick_hot_seat(game, "human", game["hot_seat"]["picks"]["2"], 71)
    game = logic.tick(game, online, 72)
    seat = game["hot_seat"]["seat"]
    assert seat is not None
    game = logic.bot_moves(game, 73)
    raters = set(game["hot_seat"]["ratings"])
    assert str(seat) not in raters and len(raters) == (4 if seat == 1 else 3)
