"""Shared helpers for the NOVA MYSTERY test suite.

All tests are written against docs/CONTRACT.md only.
"""
import json
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402

import content  # noqa: E402
import logic  # noqa: E402


@pytest.fixture(autouse=True)
def no_thread_outlives_its_test(monkeypatch):
    """The app writes AI cases in a background thread. Wait for every thread a test started,
    so it cannot run on into the next test (and call that test's stand-in for the AI).
    It asks for monkeypatch so that it is torn down first: the test's stand-ins for the AI
    are still in place while the thread finishes (otherwise it would try the real AI)."""
    before = set(threading.enumerate())
    yield
    for thread in set(threading.enumerate()) - before:
        thread.join(timeout=10)

LOC = content.LOCATIONS

# Long, distinctive tokens for the security tests (so substring checks cannot
# produce false positives such as "t1" inside ordinary words).
SECURE_TOKENS = ["tok%d_" % i + "QzXw" * 4 for i in range(1, 7)]


# --------------------------------------------------------------------------
# building games
# --------------------------------------------------------------------------
def make_lobby(n, tokens=None):
    """new_game("ABCD", 0) plus n players P1..Pn with tokens t1..tn at now=0."""
    game = logic.new_game("ABCD", 0)
    for i in range(1, n + 1):
        token = tokens[i - 1] if tokens else "t%d" % i
        game = logic.join(game, "P%d" % i, token, 0)
    return game


def online_all(game):
    return {p["pid"] for p in game["players"]}


def make_started(n=5, seed=1, tokens=None):
    """Lobby with n players, started by the host at now=0 with all online."""
    game = make_lobby(n, tokens)
    host_token = tokens[0] if tokens else "t1"
    return logic.start(game, host_token, set(range(1, n + 1)), 0, seed=seed)


def token_of(game, pid):
    for p in game["players"]:
        if p["pid"] == pid:
            return p["token"]
    raise KeyError(pid)


def host_token(game):
    return token_of(game, game["host"])


def pids_of(game):
    return [p["pid"] for p in game["players"]]


def murderer_pid(game):
    return game["case"]["murderer"]


def murderer_token(game):
    return token_of(game, murderer_pid(game))


def innocent_pids(game):
    m = murderer_pid(game)
    return [p for p in pids_of(game) if p != m]


def innocent_token(game, k=0):
    return token_of(game, innocent_pids(game)[k])


def character(game, pid):
    for c in game["case"]["characters"]:
        if c["pid"] == pid:
            return c
    raise KeyError(pid)


def own_clue_ids(game, pid):
    return [c["id"] for c in character(game, pid)["clues"]]


def open_places(game):
    """Places that can be searched for the first time right now (not locked, not searched)."""
    return [p["name"] for p in logic.map_view(game)["places"] if p["state"] == "open"]


def locked_places(game):
    """Places that are still locked in the current round."""
    return [p["name"] for p in logic.map_view(game)["places"] if p["state"] == "locked"]


def to_last_round(game, online=None, now=0):
    """Advance an investigation (host ends rounds) to its last round."""
    online = online if online is not None else online_all(game)
    while game["phase"] == "INVESTIGATION" and game["round"] < logic.ROUNDS:
        game = logic.end_phase(game, host_token(game), online, now)
    return game


def plant_spot(game):
    """A location where the murderer may plant a clue in this game."""
    return logic.plant_locations(game)[0]


def last_log_id(game):
    return game["log"][-1]["id"]


def advance_to(game, phase, online=None, now=0):
    """Call logic.end_phase with the host token until `phase` is reached."""
    if online is None:
        online = online_all(game)
    for _ in range(10 + logic.ROUNDS):   # the investigation has ROUNDS rounds
        if game["phase"] == phase:
            return game
        assert game["phase"] in ("REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE"), (
            "cannot advance from %s to %s" % (game["phase"], phase)
        )
        game = logic.end_phase(game, host_token(game), online, now)
    raise AssertionError("phase %s not reached" % phase)


def started_in(phase, n=5, seed=1, tokens=None):
    """A started game advanced (via end_phase) to `phase`."""
    return advance_to(make_started(n, seed, tokens), phase)


def cast_votes(game, votes, now=0):
    """votes: {voter_pid: target_pid}"""
    for voter, target in votes.items():
        game = logic.vote(game, token_of(game, voter), target, now)
    return game


# --------------------------------------------------------------------------
# rejected == unchanged
# --------------------------------------------------------------------------
def assert_rejected_unchanged(fn, game):
    """fn(game) must raise logic.Rejected and must not mutate the input dict."""
    before = json.dumps(game, sort_keys=True)
    with pytest.raises(logic.Rejected):
        fn(game)
    after = json.dumps(game, sort_keys=True)
    assert after == before, "a rejected call mutated the game"


@pytest.fixture(autouse=True)
def puzzles_can_be_solved_at_once(monkeypatch):
    """Tests submit a puzzle's answer right after opening it; the minimum solving time
    (minigames.MIN_SECONDS) has its own test in test_minigame_screen.py."""
    import minigames
    monkeypatch.setattr(minigames, "MIN_SECONDS", {})
