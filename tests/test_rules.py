"""Lobby, phases, timers, actions, votes, result, drop-out (Done-when 04-16)."""
import json

import pytest

import content
import logic
from conftest import (
    LOC, advance_to, assert_rejected_unchanged, cast_votes, character, host_token,
    innocent_pids, innocent_token, make_lobby, make_started,
    murderer_pid, murderer_token, own_clue_ids, pids_of, plant_spot,
    started_in, token_of, open_places, locked_places, to_last_round)

ON5 = {1, 2, 3, 4, 5}


# ================================================================ DW04
def test_dw04_start_with_3_online_rejected():
    assert_rejected_unchanged(lambda g: logic.start(g, "t1", {1, 2, 3}, 0, seed=1), make_lobby(4))
    assert_rejected_unchanged(lambda g: logic.start(g, "t1", {1, 2, 3}, 0, seed=1), make_lobby(3))


@pytest.mark.parametrize("n", [4, 6])
def test_dw04_start_with_4_and_6_players_works(n):
    g = make_started(n)
    assert g["phase"] == "REVEAL"
    assert g["phase_started"] == 0 and g["deadline"] == 60
    assert pids_of(g) == list(range(1, n + 1))
    assert g["case"]["murderer"] in pids_of(g)


def test_dw04_start_removes_offline_lobby_players():
    g = logic.start(make_lobby(5), "t1", {1, 2, 3, 4}, 0, seed=1)
    assert pids_of(g) == [1, 2, 3, 4]
    assert g["phase"] == "REVEAL"


def test_dw04_seventh_join_rejected():
    assert_rejected_unchanged(lambda g: logic.join(g, "P7", "t7", 0), make_lobby(6))


def test_dw04_join_after_start_rejected():
    assert_rejected_unchanged(lambda g: logic.join(g, "Late", "t9", 1), make_started(5))


def test_dw04_duplicate_name_ignoring_case_rejected():
    g = logic.join(logic.new_game("ABCD", 0), "Anna", "ta", 0)
    assert_rejected_unchanged(lambda x: logic.join(x, "anna", "tb", 0), g)
    assert_rejected_unchanged(lambda x: logic.join(x, "  ANNA  ", "tb", 0), g)


def test_dw04_duplicate_token_rejected():
    g = logic.join(logic.new_game("ABCD", 0), "Anna", "ta", 0)
    assert_rejected_unchanged(lambda x: logic.join(x, "Bob", "ta", 0), g)


def test_dw04_name_length_21_rejected_20_accepted():
    g = logic.new_game("ABCD", 0)
    assert_rejected_unchanged(lambda x: logic.join(x, "a" * 21, "ta", 0), g)
    g = logic.join(g, "a" * 20, "ta", 0)
    assert g["players"][0]["name"] == "a" * 20


@pytest.mark.parametrize("name", ["", " ", "   ", "\t "])
def test_dw04_empty_or_whitespace_name_rejected(name):
    assert_rejected_unchanged(lambda x: logic.join(x, name, "ta", 0), logic.new_game("ABCD", 0))


@pytest.mark.parametrize("name", ["Ana\u200b", "\u200b", "Ana\u202e", "A\u00adna", "\u2800", "Ana\u2800",
                                  "\u3164", "Z\u0334\u0321\u031b\u034da", "\ufeffAna", "🙂"])
def test_names_with_invisible_or_special_characters_are_refused(name):
    """Such a name could pass for another player's, or be invisible on every screen."""
    assert_rejected_unchanged(lambda g: logic.join(g, name, "tx", 0), make_lobby(1))


@pytest.mark.parametrize("name", ["Аna", "ΑΝΑ", "Ána", "Ａｎａ", "ana ", "ANA", "Ana\u3000"])
def test_a_name_that_only_looks_like_a_taken_one_is_refused(name):
    g = logic.join(logic.new_game("ABCD", 0), "Ana", "t1", 0)
    with pytest.raises(logic.Rejected, match="already taken"):
        logic.join(g, name, "t2", 0)


@pytest.mark.parametrize("name", ["Zoë", "Анна", "李雷", "María José", "O'Neil", "Ana🙂", "<b>x</b>"])
def test_real_names_from_everywhere_are_accepted_as_typed(name):
    g = logic.join(logic.new_game("ABCD", 0), "Ben", "t1", 0)
    assert logic.join(g, name, "t2", 0)["players"][-1]["name"] == name


def test_dw04_name_is_stripped_and_first_player_is_host():
    g = logic.join(logic.new_game("ABCD", 0), "  Bob  ", "ta", 0)
    assert g["players"][0]["name"] == "Bob"
    assert g["players"][0]["pid"] == 1
    assert g["host"] == 1
    g = logic.join(g, "Cy", "tb", 0)
    assert g["players"][1]["pid"] == 2 and g["host"] == 1


def test_dw04_start_twice_rejected():
    assert_rejected_unchanged(lambda g: logic.start(g, "t1", ON5, 1, seed=1), make_started(5))


# ================================================================ DW05
def test_dw05_only_host_can_start():
    assert_rejected_unchanged(lambda g: logic.start(g, "t2", {1, 2, 3, 4}, 0, seed=1), make_lobby(4))


@pytest.mark.parametrize("phase", ["REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE"])
def test_dw05_only_host_can_end_phase(phase):
    g = started_in(phase)
    assert_rejected_unchanged(lambda x: logic.end_phase(x, "t2", ON5, 1), g)
    after = logic.end_phase(g, "t1", ON5, 1)
    # Rounds: in the investigation the host ends the round, the phase changes after the last one.
    assert after["phase"] != phase or after["round"] == g["round"] + 1


def _inv():
    return started_in("INVESTIGATION")


UNKNOWN = "nope"
UNKNOWN_TOKEN_CASES = {
    "start": (lambda: make_lobby(4), lambda g: logic.start(g, UNKNOWN, {1, 2, 3, 4}, 0, seed=1)),
    "end_phase": (lambda: make_started(5), lambda g: logic.end_phase(g, UNKNOWN, ON5, 1)),
    "search": (_inv, lambda g: logic.search(g, UNKNOWN, LOC[0], 5)),
    "share": (_inv, lambda g: logic.share(g, UNKNOWN, own_clue_ids(g, 1)[0], 5)),
    "plant": (_inv, lambda g: logic.plant(g, UNKNOWN, 2, LOC[0], 5)),
    "vote": (lambda: started_in("VOTE"), lambda g: logic.vote(g, UNKNOWN, 2, 5)),
}


@pytest.mark.parametrize("name", sorted(UNKNOWN_TOKEN_CASES))
def test_dw05_unknown_token_rejected(name):
    build, call = UNKNOWN_TOKEN_CASES[name]
    assert_rejected_unchanged(call, build())


# ================================================================ DW06
def test_dw06_timers_60_then_rounds_of_300_then_180_60():
    g = make_started(5)
    assert g["phase"] == "REVEAL"
    assert logic.tick(g, ON5, 59)["phase"] == "REVEAL"
    g = logic.tick(g, ON5, 60)
    assert g["phase"] == "INVESTIGATION" and g["round"] == 1
    assert g["phase_started"] == 60 and g["deadline"] == 360
    now = 60
    for round_number in range(2, logic.ROUNDS + 1):      # each round lasts at most 300 s
        assert logic.tick(g, ON5, now + 299)["round"] == round_number - 1
        now += 300
        g = logic.tick(g, ON5, now)
        assert g["phase"] == "INVESTIGATION" and g["round"] == round_number
        assert g["phase_started"] == now and g["deadline"] == now + 300
    now += 300
    g = logic.tick(g, ON5, now)
    assert g["phase"] == "DISCUSSION" and g["phase_started"] == now and g["deadline"] == now + 180
    assert logic.tick(g, ON5, now + 179)["phase"] == "DISCUSSION"
    now += 180
    g = logic.tick(g, ON5, now)
    assert g["phase"] == "VOTE" and g["deadline"] == now + 60
    assert logic.tick(g, ON5, now + 59)["phase"] == "VOTE"
    g = logic.tick(g, ON5, now + 60)
    assert g["phase"] == "RESULT"
    assert g["result"] is not None


def test_dw06_new_phase_starts_at_now_of_the_switching_tick():
    g = logic.tick(make_started(5), ON5, 65)
    assert g["phase"] == "INVESTIGATION"
    assert g["phase_started"] == 65 and g["deadline"] == 365
    g = logic.tick(g, ON5, 370)                          # next round starts at the switching tick
    assert g["round"] == 2
    assert g["phase_started"] == 370 and g["deadline"] == 670
    g = to_last_round(g, now=420)
    g = logic.tick(g, ON5, 820)
    assert g["phase"] == "DISCUSSION"
    assert g["phase_started"] == 820 and g["deadline"] == 1000


def test_dw06_only_one_step_per_tick():
    g = logic.tick(make_started(5), ON5, 1000)
    assert g["phase"] == "INVESTIGATION"


def test_dw06_tick_does_not_mutate_input():
    g = make_started(5)
    before = json.dumps(g, sort_keys=True)
    logic.tick(g, ON5, 30)
    assert json.dumps(g, sort_keys=True) == before


# ================================================================ DW07
def test_dw07_second_action_rejected():
    g = logic.search(_inv(), "t1", open_places(_inv())[0], 5)
    assert g["acted"] == [1]
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", open_places(x)[0], 6), g)
    assert_rejected_unchanged(lambda x: logic.share(x, "t1", own_clue_ids(x, 1)[0], 6), g)


@pytest.mark.parametrize("phase", ["REVEAL", "DISCUSSION", "VOTE"])
def test_dw07_action_in_wrong_phase_rejected(phase):
    g = started_in(phase)
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", LOC[0], 5), g)
    assert_rejected_unchanged(lambda x: logic.share(x, "t1", own_clue_ids(x, 1)[0], 5), g)


def test_dw07_action_in_lobby_rejected():
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", LOC[0], 5), make_lobby(4))


def test_dw07_a_place_gives_its_one_clue_then_nothing():
    g = _inv()
    place = open_places(g)[0]
    g = logic.search(g, "t1", place, 5)
    assert g["searched"] == [place]
    assert_rejected_unchanged(lambda x: logic.search(x, "t2", place, 6), g)   # nothing left
    assert 2 not in g["acted"]
    g2 = logic.search(g, "t2", open_places(g)[0], 6)
    assert sorted(g2["acted"]) == [1, 2]


def test_dw07_search_unknown_location_rejected():
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", "Atlantis", 5), _inv())


def test_dw07_search_appends_log_entry_and_marks_acted():
    g = _inv()
    place = open_places(g)[0]
    g = logic.search(g, "t3", place, 5)
    assert g["acted"] == [3]
    entry = g["log"][-1]
    assert entry["kind"] == "search" and entry["location"] == place
    assert entry["by"] == 3


def test_dw07_search_and_share_use_up_the_action():
    g = logic.search(_inv(), "t1", open_places(_inv())[0], 5)
    assert g["acted"] == [1]
    g = logic.share(g, "t2", own_clue_ids(g, 2)[0], 6)
    assert sorted(g["acted"]) == [1, 2]
    assert g["log"][-1]["kind"] == "share"
    assert_rejected_unchanged(lambda x: logic.share(x, "t2", own_clue_ids(x, 2)[1], 7), g)


def test_dw07_interrogations_are_not_an_action_in_the_app():
    """The players question each other out loud. The rules have no question or answer."""
    assert not hasattr(logic, "question") and not hasattr(logic, "answer")


# ================================================================ DW09
def test_dw09_plant_by_innocent_rejected():
    g = _inv()
    inn = innocent_pids(g)
    assert_rejected_unchanged(
        lambda x: logic.plant(x, innocent_token(x, 0), inn[1], LOC[0], 5), g)


def test_dw09_second_plant_by_murderer_rejected():
    g = _inv()
    inn = innocent_pids(g)
    g = logic.plant(g, murderer_token(g), inn[0], plant_spot(g), 5)
    assert_rejected_unchanged(
        lambda x: logic.plant(x, murderer_token(x), inn[1], LOC[1], 6), g)


def test_dw09_plant_against_oneself_rejected():
    g = _inv()
    assert_rejected_unchanged(
        lambda x: logic.plant(x, murderer_token(x), murderer_pid(x), LOC[0], 5), g)


def test_dw09_plant_unknown_target_or_location_rejected():
    g = _inv()
    assert_rejected_unchanged(lambda x: logic.plant(x, murderer_token(x), 99, LOC[0], 5), g)
    inn = innocent_pids(g)
    assert_rejected_unchanged(
        lambda x: logic.plant(x, murderer_token(x), inn[0], "Atlantis", 5), g)


def test_dw09_plant_in_wrong_phase_rejected():
    g = started_in("DISCUSSION")
    inn = innocent_pids(g)
    assert_rejected_unchanged(
        lambda x: logic.plant(x, murderer_token(x), inn[0], LOC[0], 5), g)


def test_dw09_successful_plant_does_not_use_up_murderers_action():
    g = _inv()
    m = murderer_pid(g)
    inn = innocent_pids(g)
    g2 = logic.plant(g, murderer_token(g), inn[0], plant_spot(g), 5)
    assert g2["planted"] is True
    assert m not in g2["acted"]
    e = g2["log"][-1]
    assert e["kind"] == "search" and e["planted"] is True
    assert e["implicates"] == inn[0] and e["clue_kind"] == "suspicious"
    free = open_places(g2)[0]
    g3 = logic.search(g2, murderer_token(g2), free, 6)
    assert m in g3["acted"]


# ================================================================ DW10
def test_dw10_vote_for_oneself_rejected():
    assert_rejected_unchanged(lambda x: logic.vote(x, "t1", 1, 5), started_in("VOTE"))


def test_dw10_second_vote_rejected():
    g = logic.vote(started_in("VOTE"), "t1", 2, 5)
    assert g["votes"] == {"1": 2}
    assert_rejected_unchanged(lambda x: logic.vote(x, "t1", 3, 6), g)
    assert_rejected_unchanged(lambda x: logic.vote(x, "t1", 2, 6), g)


@pytest.mark.parametrize("phase", ["REVEAL", "INVESTIGATION", "DISCUSSION"])
def test_dw10_vote_outside_vote_phase_rejected(phase):
    assert_rejected_unchanged(lambda x: logic.vote(x, "t1", 2, 5), started_in(phase))


def test_dw10_vote_for_unknown_player_rejected():
    assert_rejected_unchanged(lambda x: logic.vote(x, "t1", 99, 5), started_in("VOTE"))


# ================================================================ DW11
def _finish(g):
    g = logic.end_phase(g, host_token(g), ON5, 50)
    assert g["phase"] == "RESULT"
    return g


def test_dw11_murderer_3_votes_other_2_detectives_win():
    g = started_in("VOTE")
    m, inn = murderer_pid(g), innocent_pids(g)
    g = cast_votes(g, {inn[0]: m, inn[1]: m, inn[2]: m, inn[3]: inn[0], m: inn[0]}, 40)
    r = _finish(g)["result"]
    assert r["winner"] == "detectives"
    assert r["murderer"] == m
    assert r["murder_location"] == g["case"]["murder_location"]
    assert r["tally"] == {str(m): 3, str(inn[0]): 2}


def test_dw11_tie_2_vs_2_murderer_wins():
    g = started_in("VOTE")
    m, inn = murderer_pid(g), innocent_pids(g)
    g = cast_votes(g, {inn[0]: m, inn[1]: m, inn[2]: inn[0], inn[3]: inn[0], m: inn[1]}, 40)
    r = _finish(g)["result"]
    assert r["winner"] == "murderer"
    assert r["tally"][str(m)] == 2 and r["tally"][str(inn[0])] == 2


def test_dw11_zero_votes_murderer_wins():
    r = _finish(started_in("VOTE"))["result"]
    assert r["winner"] == "murderer"
    assert r["tally"].get(str(r["murderer"]), 0) == 0


def test_dw11_strictly_more_than_every_other_even_with_few_votes():
    g = started_in("VOTE")
    m, inn = murderer_pid(g), innocent_pids(g)
    g = cast_votes(g, {inn[0]: m, inn[1]: m, inn[2]: inn[0]}, 40)
    assert _finish(g)["result"]["winner"] == "detectives"


def test_dw11_result_via_timer():
    g = started_in("VOTE")
    m, inn = murderer_pid(g), innocent_pids(g)
    g = cast_votes(g, {inn[0]: m, inn[1]: m}, 40)
    g = logic.tick(g, ON5, g["deadline"])
    assert g["phase"] == "RESULT" and g["result"]["winner"] == "detectives"


def test_dw11_secrets_kept_lists_innocents_without_suspicious_entry():
    g = started_in("INVESTIGATION")
    inn = innocent_pids(g)
    r = advance_to(g, "RESULT")["result"]
    assert sorted(r["secrets_kept"]) == sorted(inn)
    g = logic.plant(g, murderer_token(g), inn[0], plant_spot(g), 5)
    r = advance_to(g, "RESULT")["result"]
    assert sorted(r["secrets_kept"]) == sorted(inn[1:])


# ================================================================ DW12
def _everybody_asks(g, pids, now):
    """Every player in pids makes a move: shares a clue."""
    for pid in pids:
        clue = next(c["id"] for c in logic.private_view(g, token_of(g, pid))["clues"] if not c["shared"])
        g = logic.share(g, token_of(g, pid), clue, now)
    return g


def test_dw12_a_round_ends_when_all_online_players_acted():
    g = started_in("INVESTIGATION")
    g = _everybody_asks(g, pids_of(g)[:4], 10)
    assert logic.tick(g, ON5, 10)["round"] == 1          # one player has not acted yet
    g = _everybody_asks(g, [5], 10)
    g = logic.tick(g, ON5, 10)
    assert g["phase"] == "INVESTIGATION" and g["round"] == 2
    assert g["acted"] == [] and g["phase_started"] == 10 and g["deadline"] == 310


def test_dw12_the_investigation_ends_after_the_last_round_when_all_acted():
    g = to_last_round(started_in("INVESTIGATION"))
    g = _everybody_asks(g, pids_of(g), 10)
    g = logic.tick(g, ON5, 10)
    assert g["phase"] == "DISCUSSION"
    assert g["phase_started"] == 10 and g["deadline"] == 190


def test_dw12_offline_player_who_has_not_acted_does_not_block_investigation():
    g = started_in("INVESTIGATION")
    g = _everybody_asks(g, [1, 2, 3, 4], 10)
    g = logic.tick(g, {1, 2, 3, 4}, 10)
    assert g["round"] == 2                               # player 5 is offline and does not block


def test_dw12_vote_ends_when_all_online_players_voted():
    g = started_in("VOTE")
    pids = pids_of(g)
    votes = {p: pids[(i + 1) % 5] for i, p in enumerate(pids)}
    g = cast_votes(g, {p: votes[p] for p in pids[:4]}, 5)
    assert logic.tick(g, ON5, 5)["phase"] == "VOTE"
    g = cast_votes(g, {pids[4]: votes[pids[4]]}, 5)
    g = logic.tick(g, ON5, 5)
    assert g["phase"] == "RESULT" and g["result"] is not None


def test_dw12_offline_player_who_has_not_voted_does_not_block_vote():
    g = started_in("VOTE")
    g = cast_votes(g, {1: 2, 2: 3, 3: 4, 4: 1}, 5)
    g = logic.tick(g, {1, 2, 3, 4}, 5)
    assert g["phase"] == "RESULT"


# ================================================================ DW13
def test_dw13_online_ids_46s_offline_45s_online():
    presence = {1: 54, 2: 55, 3: 100, 4: 0}
    assert logic.online_ids(presence, 100) == {2, 3}
    assert logic.online_ids({1: 54}, 100) == set()
    assert logic.online_ids({1: 55}, 100) == {1}
    assert logic.OFFLINE_AFTER == 45          # a glance at another app does not count as leaving


# ================================================================ DW14
def test_dw14_host_offline_next_online_player_in_join_order_becomes_host():
    g = make_started(5)
    assert g["host"] == 1
    g = logic.tick(g, {2, 3, 4, 5}, 5)
    assert g["host"] == 2


def test_dw14_old_host_does_not_get_role_back():
    g = logic.tick(make_started(5), {2, 3, 4, 5}, 5)
    g = logic.tick(g, ON5, 6)
    assert g["host"] == 2
    g = logic.tick(g, ON5, 7)
    assert g["host"] == 2


def test_dw14_skips_offline_players_in_join_order():
    g = logic.tick(make_started(5), {3, 4, 5}, 5)
    assert g["host"] == 3
    assert g["phase"] == "REVEAL"


def test_dw14_handover_also_in_lobby_and_reflected_in_public_view():
    g = logic.tick(make_lobby(3), {2, 3}, 5)
    assert g["host"] == 2
    view = logic.public_view(g, {2, 3})
    assert [p["pid"] for p in view["players"] if p["is_host"]] == [2]


def test_dw14_new_host_can_end_phase_old_host_cannot():
    g = logic.tick(make_started(5), {2, 3, 4, 5}, 5)
    assert_rejected_unchanged(lambda x: logic.end_phase(x, "t1", ON5, 6), g)
    assert logic.end_phase(g, "t2", ON5, 6)["phase"] == "INVESTIGATION"


# ================================================================ DW15
@pytest.mark.parametrize("phase", ["REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE"])
def test_dw15_two_online_pauses_the_game_and_stops_the_clock(phase):
    g = started_in(phase)
    left = g["deadline"] - 1
    g = logic.tick(g, {1, 2}, 1)
    assert g["phase"] == phase and g["deadline"] is None and g["abort_reason"] is None
    assert logic.public_view(g, {1, 2})["paused_since"] == 1
    g = logic.tick(g, {1, 2}, 1 + logic.PAUSE_LIMIT - 1)        # still waiting, nothing moves on
    assert g["phase"] == phase and g["deadline"] is None


@pytest.mark.parametrize("phase", ["REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE"])
def test_dw15_the_clock_runs_on_when_the_players_are_back(phase):
    g = started_in(phase)
    left = g["deadline"] - 1
    g = logic.tick(g, {1, 2}, 1)
    g = logic.tick(g, {1, 2, 3}, 100)                            # back after 99 seconds
    assert g["phase"] == phase and "paused" not in g
    assert g["deadline"] == pytest.approx(100 + left)            # the time left is the same as before
    assert logic.public_view(g, {1, 2, 3})["paused_since"] is None


@pytest.mark.parametrize("phase", ["REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE"])
def test_dw15_the_game_ends_when_nobody_comes_back(phase):
    g = logic.tick(started_in(phase), {1, 2}, 1)
    g = logic.tick(g, {1, 2}, 1 + logic.PAUSE_LIMIT)
    assert g["phase"] == "ABORTED" and g["abort_reason"]


def test_dw15_the_host_can_still_end_a_paused_phase():
    g = logic.tick(started_in("DISCUSSION"), {1, 2}, 1)
    g = logic.end_phase(g, "t1", {1, 2}, 5)
    assert g["phase"] == "VOTE" and "paused" not in g and g["deadline"] is not None


@pytest.mark.parametrize("phase", ["REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE"])
def test_dw15_three_online_continues(phase):
    g = logic.tick(started_in(phase), {1, 2, 3}, 1)
    assert g["phase"] == phase
    assert g["abort_reason"] is None


# ================================================================ DW16
def _vote_with_vote():
    return logic.vote(started_in("VOTE"), "t1", 2, 5)


def _inv_searched():
    g = _inv()
    return logic.search(g, "t1", open_places(g)[0], 5)


def _inv_planted():
    g = _inv()
    return logic.plant(g, murderer_token(g), innocent_pids(g)[0], plant_spot(g), 5)


REJECTED_CALLS = {
    "join_duplicate_name": (lambda: logic.join(logic.new_game("ABCD", 0), "Anna", "ta", 0),
                            lambda g: logic.join(g, "anna", "tb", 0)),
    "join_name_21": (lambda: make_lobby(4), lambda g: logic.join(g, "a" * 21, "tx", 0)),
    "join_empty_name": (lambda: make_lobby(4), lambda g: logic.join(g, "  ", "tx", 0)),
    "join_seventh": (lambda: make_lobby(6), lambda g: logic.join(g, "P7", "t7", 0)),
    "join_after_start": (lambda: make_started(5), lambda g: logic.join(g, "Late", "t9", 1)),
    "start_3_online": (lambda: make_lobby(4), lambda g: logic.start(g, "t1", {1, 2, 3}, 0, seed=1)),
    "start_non_host": (lambda: make_lobby(4), lambda g: logic.start(g, "t2", {1, 2, 3, 4}, 0, seed=1)),
    "start_unknown_token": (lambda: make_lobby(4), lambda g: logic.start(g, "zz", {1, 2, 3, 4}, 0, seed=1)),
    "end_phase_non_host": (lambda: make_started(5), lambda g: logic.end_phase(g, "t2", ON5, 1)),
    "search_second_action": (_inv_searched, lambda g: logic.search(g, "t1", open_places(g)[0], 6)),
    "search_wrong_phase": (lambda: started_in("DISCUSSION"), lambda g: logic.search(g, "t1", LOC[0], 6)),
    "search_already_searched": (_inv_searched, lambda g: logic.search(g, "t2", g["searched"][0], 6)),
    "search_locked_place": (_inv, lambda g: logic.search(g, "t1", locked_places(g)[0], 5)),
    "share_someone_elses_clue": (_inv, lambda g: logic.share(g, "t1", own_clue_ids(g, 2)[0], 5)),
    "share_second_action": (_inv_searched, lambda g: logic.share(g, "t1", own_clue_ids(g, 1)[0], 6)),
    "plant_by_innocent": (_inv, lambda g: logic.plant(g, innocent_token(g, 0), innocent_pids(g)[1], LOC[0], 5)),
    "plant_twice": (_inv_planted, lambda g: logic.plant(g, murderer_token(g), innocent_pids(g)[1], LOC[1], 6)),
    "plant_self": (_inv, lambda g: logic.plant(g, murderer_token(g), murderer_pid(g), LOC[0], 5)),
    "vote_self": (lambda: started_in("VOTE"), lambda g: logic.vote(g, "t1", 1, 5)),
    "vote_twice": (_vote_with_vote, lambda g: logic.vote(g, "t1", 3, 6)),
    "vote_outside_vote": (_inv, lambda g: logic.vote(g, "t1", 2, 5)),
}


@pytest.mark.parametrize("name", sorted(REJECTED_CALLS))
def test_dw16_rejected_call_leaves_game_unchanged(name):
    build, call = REJECTED_CALLS[name]
    assert_rejected_unchanged(call, build())


def test_dw16_successful_calls_return_new_dict_and_do_not_mutate_input():
    g = _inv()
    before = json.dumps(g, sort_keys=True)
    g2 = logic.search(g, "t1", open_places(g)[0], 5)
    assert g2 is not g
    assert json.dumps(g, sort_keys=True) == before
    assert g2["acted"] == [1] and g["acted"] == []


# ================================================================ planted clue does not stand out
def test_plant_uses_real_herring_wording():
    g = started_in("INVESTIGATION")
    inn = innocent_pids(g)
    spot = plant_spot(g)
    g = logic.plant(g, murderer_token(g), inn[0], spot, 5)
    role = character(g, inn[0])["role"]
    expected = content.TEMPLATES["herring"].format(
        location=spot, rumor=content.ROLES[role]["rumor"])
    assert g["log"][-1]["text"] == expected


def test_plant_marks_location_as_searched():
    g = started_in("INVESTIGATION")
    spot = plant_spot(g)
    g = logic.plant(g, murderer_token(g), innocent_pids(g)[0], spot, 5)
    assert spot in g["searched"]
    # The planted note covers the real clue: nobody can search there any more.
    assert_rejected_unchanged(lambda x: logic.search(x, innocent_token(x, 0), spot, 6), g)


def test_plant_at_already_searched_location_rejected():
    g = started_in("INVESTIGATION")
    spot = plant_spot(g)
    g = logic.search(g, innocent_token(g, 0), spot, 5)
    assert spot not in logic.plant_locations(g)
    assert_rejected_unchanged(
        lambda x: logic.plant(x, murderer_token(x), innocent_pids(x)[1], spot, 6), g)


def test_plant_cannot_cover_strong_clue_against_murderer():
    g = started_in("INVESTIGATION")
    m = murderer_pid(g)
    strong = [c["location"] for c in g["case"]["location_clues"]
              if c["implicates"] == m and c["kind"] in logic.STRONG_KINDS]
    assert strong
    for loc in strong:
        assert loc not in logic.plant_locations(g)
        assert_rejected_unchanged(
            lambda x: logic.plant(x, murderer_token(x), innocent_pids(x)[0], loc, 5), g)


# ================================================================ host removes a player
def test_host_can_remove_player_in_lobby():
    g = make_lobby(4)
    g2 = logic.kick(g, host_token(g), 3, 0)
    assert pids_of(g2) == [1, 2, 4]
    assert logic.private_view(g2, token_of(g, 3)) is None


@pytest.mark.parametrize("token,target", [("t2", 3), ("t1", 1), ("t1", 99)])
def test_kick_by_non_host_self_or_unknown_rejected(token, target):
    assert_rejected_unchanged(lambda g: logic.kick(g, token, target, 0), make_lobby(4))


def test_kick_after_start_rejected():
    g = started_in("INVESTIGATION")
    assert_rejected_unchanged(lambda x: logic.kick(x, host_token(x), innocent_pids(x)[0], 5), g)
