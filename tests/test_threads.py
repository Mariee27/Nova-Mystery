"""Red threads: a player connects a note on the evidence wall to a suspect. Free, anonymous,
movable; the murderer may cut one connection in the discussion; demo suspects pin threads too."""
import pytest

import logic
from conftest import (
    assert_rejected_unchanged, murderer_pid, murderer_token, open_places, started_in, token_of,
)


def with_evidence(phase="INVESTIGATION"):
    """A game with two notes on the wall (a search result and a shared clue), in `phase`."""
    game = started_in("INVESTIGATION")
    game = logic.search(game, "t1", open_places(game)[0], 5)
    clue = logic._character(game, 2)["clues"][0]["id"]
    game = logic.share(game, "t2", clue, 6)
    while game["phase"] != phase:
        game = logic.end_phase(game, "t1", {1, 2, 3, 4, 5}, 7)
    return game


def notes(game):
    return [e["id"] for e in game["log"] if e["kind"] in logic.EVIDENCE_KINDS]


def an_innocent_other_than(game, *pids):
    return next(p for p in logic._player_ids(game) if p != murderer_pid(game) and p not in pids)


def test_a_thread_is_counted_anonymously_and_can_be_moved_or_taken_down():
    game = with_evidence()
    note = notes(game)[0]
    game = logic.pin_thread(game, "t1", note, 3, 10)
    game = logic.pin_thread(game, "t2", note, 3, 11)
    assert logic.thread_view(game) == [{"entry": note, "pid": 3, "count": 2, "at": 11}]
    game = logic.pin_thread(game, "t2", note, 4, 12)                 # moved: still one per note
    assert {(t["pid"], t["count"]) for t in logic.thread_view(game)} == {(3, 1), (4, 1)}
    game = logic.unpin_thread(game, "t1", note, 13)
    assert [t["pid"] for t in logic.thread_view(game)] == [4]
    public = logic.public_view(game, {1, 2, 3, 4, 5})
    assert public["threads"] == logic.thread_view(game) and "t2" not in repr(public["threads"])
    assert logic.private_view(game, "t2")["threads"] == {note: 4}


def test_threads_need_a_note_another_player_and_the_right_phase():
    game = with_evidence()
    note = notes(game)[0]
    assert_rejected_unchanged(lambda g: logic.pin_thread(g, "t1", 999, 2, 10), game)     # no such note
    assert_rejected_unchanged(lambda g: logic.pin_thread(g, "t1", note, 1, 10), game)    # yourself
    assert_rejected_unchanged(lambda g: logic.pin_thread(g, "t1", note, 99, 10), game)   # nobody
    assert_rejected_unchanged(lambda g: logic.pin_thread(g, "nope", note, 2, 10), game)  # unknown token
    assert_rejected_unchanged(lambda g: logic.unpin_thread(g, "t1", note, 10), game)     # nothing to take down
    vote = with_evidence("VOTE")
    assert_rejected_unchanged(lambda g: logic.pin_thread(g, "t1", notes(g)[0], 2, 10), vote)
    discussion = with_evidence("DISCUSSION")
    assert logic.thread_view(logic.pin_thread(discussion, "t1", notes(discussion)[0], 2, 10))


def test_the_murderer_cuts_one_connection_once_in_the_discussion():
    game = with_evidence("DISCUSSION")
    killer = murderer_pid(game)
    a, b = an_innocent_other_than(game), an_innocent_other_than(game, an_innocent_other_than(game))
    note = notes(game)[0]
    game = logic.pin_thread(game, token_of(game, a), note, killer, 10)
    game = logic.pin_thread(game, token_of(game, b), note, killer, 11)
    assert logic.private_view(game, murderer_token(game))["can_cut"] is True
    assert logic.private_view(game, token_of(game, a))["can_cut"] is False
    assert_rejected_unchanged(lambda g: logic.cut_thread(g, token_of(g, a), note, killer, 12), game)
    game = logic.cut_thread(game, murderer_token(game), note, killer, 12)
    assert logic.thread_view(game) == [] and game["cut"] == {"entry": note, "pid": killer, "at": 12}
    assert logic.public_view(game, set())["cut"] == game["cut"]               # what, never by whom
    assert_rejected_unchanged(lambda g: logic.pin_thread(g, token_of(g, a), note, killer, 13), game)
    game = logic.pin_thread(game, token_of(game, a), notes(game)[1], killer, 14)
    assert_rejected_unchanged(lambda g: logic.cut_thread(g, murderer_token(g), notes(g)[1], killer, 15), game)
    assert logic.private_view(game, murderer_token(game))["can_cut"] is False


def test_the_murderer_cannot_cut_during_the_rounds_or_a_thread_that_does_not_exist():
    game = with_evidence()
    killer = murderer_pid(game)
    other = an_innocent_other_than(game)
    game = logic.pin_thread(game, token_of(game, other), notes(game)[0], killer, 10)
    assert_rejected_unchanged(lambda g: logic.cut_thread(g, murderer_token(g), notes(g)[0], killer, 11), game)
    game = logic.end_phase(game, "t1", {1, 2, 3, 4, 5}, 12)
    while game["phase"] != "DISCUSSION":
        game = logic.end_phase(game, "t1", {1, 2, 3, 4, 5}, 12)
    assert_rejected_unchanged(lambda g: logic.cut_thread(g, murderer_token(g), notes(g)[1], killer, 13), game)


def test_pinning_does_not_use_the_move_of_the_round():
    game = with_evidence()
    game = logic.end_phase(game, "t1", {1, 2, 3, 4, 5}, 8)            # a fresh round
    game = logic.pin_thread(game, "t3", notes(game)[0], 1, 9)
    assert 3 not in game["acted"]


def demo_room(phase):
    lobby = logic.join(logic.new_game("DEMO", 0), "Ana", "human", 0)
    for _ in range(4):
        lobby = logic.add_bot(lobby, "human", 0)
    everybody = {p["pid"] for p in lobby["players"]}
    game = logic.start(lobby, "human", everybody, 0, seed=logic.DEMO_SEED)
    game = logic.end_phase(game, "human", everybody, 0)
    game = logic.search(game, "human", open_places(game)[0], 1)
    for now in range(1, 120):                     # round 1: the demo suspects search and share
        game = logic.bot_moves(game, now)
    game = logic.end_phase(game, "human", everybody, 300)
    if phase == "DISCUSSION":
        while game["phase"] != phase:
            game = logic.end_phase(game, "human", everybody, 300)
    return game


@pytest.mark.parametrize("phase", ["INVESTIGATION", "DISCUSSION"])
def test_demo_suspects_pin_threads_one_at_a_time(phase):
    game = demo_room(phase)
    before = sum(t["count"] for t in logic.thread_view(game))
    start = game["phase_started"]
    game = logic.bot_moves(game, start + 1)                                # too early
    assert sum(t["count"] for t in logic.thread_view(game)) == before
    for now in range(int(start) + 1, int(start) + 120, 2):
        game = logic.bot_moves(game, now)
    pinned = sum(t["count"] for t in logic.thread_view(game))
    assert pinned > before or "cut" in game
    assert pinned - before <= 4 * (120 // logic.BOT_THREAD_GAP + 1)           # one at a time
    for mine in game.get("threads", {}).values():                         # never to themselves
        assert all(str(t["pid"]) != pid for pid, t in mine.items())


def test_a_guilty_demo_suspect_cuts_the_thickest_thread_against_itself():
    game = demo_room("DISCUSSION")
    killer = murderer_pid(game)
    if not game["players"][killer - 1].get("bot"):
        pytest.skip("the human is the murderer in this seed")
    note = notes(game)[0]
    game = logic.pin_thread(game, "human", note, killer, game["phase_started"])
    for now in range(int(game["phase_started"]), int(game["phase_started"]) + 120, 2):
        game = logic.bot_moves(game, now)
    assert game["cut"]["pid"] == killer


def test_the_hall_of_fame_names_hunters_witnesses_oracles_and_the_liar():
    game = with_evidence("DISCUSSION")
    killer = murderer_pid(game)
    oracle = an_innocent_other_than(game)
    game = logic.pin_thread(game, token_of(game, oracle), notes(game)[0], killer, 10)
    game = logic.end_phase(game, "t1", {1, 2, 3, 4, 5}, 11)                 # → VOTE
    scene = game["case"]["murder_location"]
    game = logic.vote(game, token_of(game, oracle), killer, 12, scene=scene)
    game = logic.end_phase(game, "t1", {1, 2, 3, 4, 5}, 13)                 # → RESULT
    awards = {a["key"]: a for a in game["result"]["awards"]}
    assert awards["detective"]["pids"] == [oracle] and awards["detective"]["title"].endswith("Sharpest detective")
    assert awards["hunter"]["pids"] == [1] and awards["witness"]["pids"] == [2]
    assert awards["oracle"]["pids"] == [oracle] and awards["oracle"]["detail"] == "1 thread to the culprit."
    assert awards["liar"]["pids"] == [killer]


def test_a_title_shared_by_more_than_two_players_is_left_out():
    game = with_evidence("DISCUSSION")
    for pid in (3, 4, 5):                                              # three more statements, one each
        clue = logic._character(game, pid)["clues"][0]["id"]
        game = dict(game, phase="INVESTIGATION")
        game = logic.share(game, token_of(game, pid), clue, 8)
        game = dict(game, phase="DISCUSSION")
    game = logic.end_phase(game, "t1", {1, 2, 3, 4, 5}, 11)
    game = logic.end_phase(game, "t1", {1, 2, 3, 4, 5}, 12)
    assert "witness" not in {a["key"] for a in game["result"]["awards"]}
