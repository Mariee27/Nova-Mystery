"""Public alibi statements in the discussion: every player taps where they SAY they were.
It is the player's own public claim, never the secret alibi on the card."""
import json

import pytest

import logic
from conftest import make_started, online_all


def discussion():
    game = make_started(5)
    while game["phase"] != "DISCUSSION":
        game = logic.end_phase(game, "t1", online_all(game), 10)
    return game


def test_a_player_states_a_place_and_may_change_it():
    game = discussion()
    places = logic.story_of(game)["locations"]
    game = logic.state_alibi(game, "t2", places[0], 20)
    assert logic.alibi_statements(game) == {2: places[0]}
    game = logic.state_alibi(game, "t2", places[1], 21)
    assert logic.alibi_statements(game) == {2: places[1]}


def test_a_statement_may_be_a_lie_it_is_the_players_choice():
    game = discussion()
    murderer = game["case"]["murderer"]
    token = next(p["token"] for p in game["players"] if p["pid"] == murderer)
    place = logic.story_of(game)["locations"][-1]
    game = logic.state_alibi(game, token, place, 20)         # any place is allowed, true or not
    assert logic.alibi_statements(game)[murderer] == place


def test_only_real_places_and_only_in_the_discussion():
    game = discussion()
    with pytest.raises(logic.Rejected):
        logic.state_alibi(game, "t2", "The Moon", 20)
    with pytest.raises(logic.Rejected):
        logic.state_alibi(make_started(5), "t2", logic.story_of(game)["locations"][0], 5)
    with pytest.raises(logic.Rejected):
        logic.state_alibi(game, "nobody", logic.story_of(game)["locations"][0], 20)


def test_nobody_has_said_anything_before_the_discussion():
    assert logic.alibi_statements(make_started(5)) == {}


def test_statements_never_reveal_the_secret_alibi_on_the_card():
    game = discussion()
    text = json.dumps(logic.alibi_statements(game))
    for character in game["case"]["characters"]:
        assert character["alibi"] not in text
    assert "statements" not in logic.public_view(game, online_all(game))   # the contract is unchanged


def test_demo_bots_state_the_alibi_on_their_card():
    lobby = logic.new_game("DEMO", 0)
    lobby = logic.join(lobby, "Ana", "human", 0)
    for _ in range(4):
        lobby = logic.add_bot(lobby, "human", 0)
    online = {p["pid"] for p in lobby["players"]}
    game = logic.start(lobby, "human", online, 0, seed=1)
    while game["phase"] != "DISCUSSION":
        game = logic.end_phase(game, "human", online, 10)
    game = logic.bot_moves(game, 10 + 60)                    # all bots are due
    said = logic.alibi_statements(game)
    assert set(said) == {2, 3, 4, 5}                         # every bot, not the human
    for character in game["case"]["characters"]:
        if character["pid"] in said:
            assert said[character["pid"]] == character["alibi_location"]
