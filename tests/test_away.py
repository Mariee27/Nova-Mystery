"""Away players: a phone without a sign of life for more than OFFLINE_AFTER seconds is away.
Nobody plays for them: the game simply goes on without them (rounds, the hot seat and the
vote do not wait), and as soon as their phone is back they play on in their own seat."""
import logic
from conftest import make_lobby, open_places, started_in, token_of

AWAY = logic.OFFLINE_AFTER + 1


def presence(game, now, away=(), away_for=AWAY):
    """Everybody was seen just now, except the players in `away`."""
    return {p["pid"]: (now - away_for if p["pid"] in away else now) for p in game["players"]}


def step(game, seen, now):
    """What every screen does on each poll (app.sync)."""
    return logic.tick(game, logic.online_ids(seen, now), now)


def in_round_1(n=4):
    game = make_lobby(n)
    game = logic.start(game, "t1", set(range(1, n + 1)), 0, seed=1)
    return logic.end_phase(game, "t1", set(range(1, n + 1)), 0)      # → round 1 at now=0


def test_away_means_more_than_15_seconds_without_a_sign():
    assert logic.OFFLINE_AFTER == 15
    game = started_in("INVESTIGATION", n=4)
    assert logic.online_ids(presence(game, 100, away=[3], away_for=15), 100) == {1, 2, 3, 4}
    assert logic.online_ids(presence(game, 100, away=[3]), 100) == {1, 2, 4}


def test_nobody_plays_for_an_away_player_and_the_game_never_pauses_or_ends():
    game = in_round_1()
    for now in range(1, 200, 5):                              # three of four away for minutes
        game = step(game, presence(game, now, away=[2, 3, 4]), now)
    assert game["phase"] == "INVESTIGATION" and game["round"] == 1
    assert game["acted"] == [] and "paused" not in game
    assert "stand_ins" not in game and not any(p.get("bot") for p in game["players"])


def test_the_round_ends_early_when_everybody_who_is_there_has_moved():
    game = in_round_1()
    for pid in (1, 2):
        game = logic.search(game, token_of(game, pid), open_places(game)[0], 1)
    game = step(game, presence(game, 20, away=[3, 4]), 20)
    assert game["round"] == 2
    assert 3 not in game["searched"] and 4 not in game["acted"]   # they simply missed the round


def test_the_round_still_waits_for_players_who_are_there():
    game = in_round_1()
    game = logic.search(game, token_of(game, 1), open_places(game)[0], 1)
    game = step(game, presence(game, 20, away=[3, 4]), 20)
    assert game["round"] == 1                                 # player 2 is there and has not moved


def test_with_nobody_there_the_clock_runs_out_instead_of_ending_the_round_at_once():
    game = in_round_1()
    game = step(game, {}, 10)
    assert game["round"] == 1
    game = step(game, {}, logic.DURATIONS["INVESTIGATION"] + 1)
    assert game["round"] == 2 or logic.hot_seat_open(game) or game["phase"] != "INVESTIGATION"


def test_a_returning_player_plays_on_in_their_own_seat():
    game = in_round_1()
    game = step(game, presence(game, 20, away=[3]), 20)       # away for a while ...
    game = step(game, presence(game, 30), 30)                 # ... and back
    place = open_places(game)[0]
    game = logic.search(game, token_of(game, 3), place, 31)
    assert 3 in game["acted"] and place in game["searched"]


def test_the_vote_ends_early_without_the_away_players():
    game = started_in("VOTE", n=4)
    game = logic.vote(game, "t1", 2, 1)
    game = logic.vote(game, "t2", 1, 1)
    game = step(game, presence(game, 20, away=[3, 4]), 20)
    assert game["phase"] == "RESULT"
    assert set(game["votes"]) == {"1", "2"}                   # nobody voted for them


def test_the_host_role_moves_to_a_player_who_is_there():
    game = started_in("INVESTIGATION", n=4)
    game = step(game, presence(game, 100, away=[1]), 100)
    assert game["host"] == 2


def test_the_board_and_the_phones_show_who_is_away():
    game = started_in("INVESTIGATION", n=4)
    public = logic.public_view(game, logic.online_ids(presence(game, 100, away=[3]), 100))
    by_pid = {p["pid"]: p for p in public["players"]}
    assert by_pid[3]["online"] is False and by_pid[1]["online"] is True
    assert "stand_in" not in by_pid[3] and "paused_since" not in public and "demo" not in public


def test_no_demo_suspects_any_more():
    for name in ("add_bot", "bot_moves", "with_bots", "as_demo", "update_stand_ins"):
        assert not hasattr(logic, name)
    lobby = make_lobby(3)
    try:
        logic.start(lobby, "t1", {1, 2, 3}, 0)
    except logic.Rejected:
        pass
    else:
        raise AssertionError("a game needs MIN_PLAYERS people")
