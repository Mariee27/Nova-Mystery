"""Stand-ins: a player whose phone drops out for more than STAND_IN_AFTER seconds is played by
the computer (like a demo suspect) until they are back, so the game goes on for everybody else."""
import logic
import minigames
from conftest import make_lobby, open_places, started_in, token_of

AWAY = logic.STAND_IN_AFTER + 1


def presence(game, now, away=(), away_for=AWAY):
    """Everybody was seen just now, except the players in `away`."""
    return {p["pid"]: (now - away_for if p["pid"] in away else now) for p in game["players"]}


def step(game, seen, now):
    """What every screen does on each poll (app.sync): stand-ins, timers, computer moves."""
    game = logic.update_stand_ins(game, seen, now)
    online = logic.with_bots(game, logic.online_ids(seen, now))
    return logic.bot_moves(logic.tick(game, online, now), now)


def in_round_1(minigames_on=False, n=4):
    game = make_lobby(n)
    if minigames_on:
        game["minigames"] = True
    game = logic.start(game, "t1", set(range(1, n + 1)), 0, seed=1)
    return logic.end_phase(game, "t1", set(range(1, n + 1)), 0)      # → round 1 at now=0


# ------------------------------------------------------------------ who gets a stand-in

def test_a_player_away_for_more_than_15_seconds_gets_a_stand_in():
    game = started_in("INVESTIGATION", n=4)
    assert logic.update_stand_ins(game, presence(game, 100, away=[3], away_for=15), 100) is game
    game = logic.update_stand_ins(game, presence(game, 100, away=[3]), 100)
    assert logic.stand_in_ids(game) == [3]


def test_nothing_changes_while_everybody_is_there():
    game = started_in("INVESTIGATION", n=4)
    assert logic.update_stand_ins(game, presence(game, 100), 100) is game


def test_a_player_who_never_sent_a_sign_of_life_also_gets_one():
    game = started_in("REVEAL", n=4)
    seen = presence(game, 100)
    del seen[2]
    assert logic.stand_in_ids(logic.update_stand_ins(game, seen, 100)) == [2]


def test_the_player_is_back_and_plays_again():
    game = started_in("INVESTIGATION", n=4)
    game = logic.update_stand_ins(game, presence(game, 100, away=[3]), 100)
    game = logic.update_stand_ins(game, presence(game, 101), 101)
    assert logic.stand_in_ids(game) == []


def test_no_stand_ins_in_the_lobby_or_after_the_game():
    lobby = make_lobby(4)
    assert logic.update_stand_ins(lobby, {}, 100) is lobby
    result = started_in("RESULT", n=4)
    assert logic.stand_in_ids(logic.update_stand_ins(result, {}, 100)) == []


def test_demo_suspects_never_get_a_stand_in():
    game = make_lobby(3)
    game = logic.add_bot(game, "t1", 0)
    game = logic.start(game, "t1", {1, 2, 3, 4}, 0, seed=1)
    seen = presence(game, 100)
    del seen[4]                                               # bots send no heartbeat
    assert logic.update_stand_ins(game, seen, 100) is game


def test_update_stand_ins_does_not_change_its_input():
    game = started_in("INVESTIGATION", n=4)
    before = repr(game)
    logic.update_stand_ins(game, presence(game, 100, away=[2]), 100)
    assert repr(game) == before


# ------------------------------------------------------------------ the game goes on

def test_two_of_four_away_does_not_pause_the_game():
    game = in_round_1()
    game = step(game, presence(game, 30, away=[3, 4]), 30)
    assert game.get("paused") is None and game["phase"] == "INVESTIGATION"


def test_the_stand_in_moves_and_the_round_ends_early():
    game = in_round_1()
    for pid in (1, 2):                                        # the two players who are there
        place = open_places(game)[0]
        game = logic.search(game, token_of(game, pid), place, 1)
    seen = presence(game, 20, away=[3, 4])
    for now in range(20, 40):                                 # the screens poll; stand-ins are due
        game = step(game, seen, now)
        if game.get("round") == 2:
            break
    assert game["round"] == 2


def test_with_mini_games_stand_ins_wait_for_the_players_who_are_there():
    game = in_round_1(minigames_on=True)
    for now in (30, 40, 50):                                  # players 1-3 are here, solving
        game = step(game, presence(game, now, away=[4]), now)
    assert 4 not in game["acted"]                             # players 1-3 are still solving
    for pid in (1, 2, 3):
        place = open_places(game)[0] if open_places(game) else None
        if place is not None:
            game = logic.search(game, token_of(game, pid), place, 31, proof=minigames.solve(game, place))
        else:
            clue = logic._character(game, pid)["clues"][0]["id"]
            game = logic.share(game, token_of(game, pid), clue, 31)
    for now in range(31, 45):
        game = step(game, presence(game, now, away=[4]), now)
    assert game.get("round") == 2                           # the stand-in moved, the round ended


def test_a_stand_in_searches_without_solving_the_puzzle():
    game = in_round_1(minigames_on=True, n=4)
    game = logic.update_stand_ins(game, presence(game, 30, away=[2]), 30)
    place = open_places(game)[0]
    game = logic.search(game, token_of(game, 2), place, 30)   # no proof needed for the computer
    assert 2 in game["acted"]


def test_a_returning_player_needs_the_puzzle_again():
    game = in_round_1(minigames_on=True, n=4)
    game = logic.update_stand_ins(game, presence(game, 30, away=[2]), 30)
    game = logic.update_stand_ins(game, presence(game, 31), 31)
    place = open_places(game)[0]
    try:
        logic.search(game, token_of(game, 2), place, 31)
    except logic.Rejected:
        pass
    else:
        raise AssertionError("a player who is back must solve the puzzle again")


def test_stand_ins_vote_and_the_vote_ends_early():
    game = started_in("VOTE", n=4)
    game = logic.vote(game, "t1", 2, 1)
    game = logic.vote(game, "t2", 1, 1)
    seen = presence(game, 20, away=[3, 4])
    for now in range(20, 40):
        game = step(game, seen, now)
        if game["phase"] == "RESULT":
            break
    assert game["phase"] == "RESULT"
    assert set(game["votes"]) == {"1", "2", "3", "4"}


def test_the_host_role_moves_to_a_player_who_is_there():
    game = started_in("INVESTIGATION", n=4)
    game = step(game, presence(game, 100, away=[1]), 100)
    assert game["host"] == 2


def test_the_board_and_the_phone_show_the_stand_in():
    game = started_in("INVESTIGATION", n=4)
    game = logic.update_stand_ins(game, presence(game, 100, away=[3]), 100)
    public = logic.public_view(game, logic.with_bots(game, {1, 2, 4}))
    by_pid = {p["pid"]: p for p in public["players"]}
    assert by_pid[3]["stand_in"] is True and by_pid[3]["online"] is True
    assert by_pid[1]["stand_in"] is False
    assert logic.private_view(game, "t3")["stand_in"] is True
    assert logic.private_view(game, "t1")["stand_in"] is False
