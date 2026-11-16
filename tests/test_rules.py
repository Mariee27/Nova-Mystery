"""Lobby, phases, timers, actions, votes, result, drop-out (Done-when 04-16)."""
import json

import pytest

import content
import logic
from conftest import (
    LOC, advance_to, assert_rejected_unchanged, cast_votes, character, host_token,
    innocent_pids, innocent_token, last_log_id, make_lobby, make_started,
    murderer_pid, murderer_token, online_all, own_clue_ids, pids_of, plant_spot,
    started_in, token_of,
)

ON5 = {1, 2, 3, 4, 5}


# ================================================================ DW04
def test_dw04_start_with_3_online_rejected():
    assert_rejected_unchanged(lambda g: logic.start(g, "t1", {1, 2, 3}, 0, seed=1), make_lobby(4))
    assert_rejected_unchanged(lambda g: logic.start(g, "t1", {1, 2, 3}, 0, seed=1), make_lobby(3))


@pytest.mark.parametrize("n", [4, 6])
def test_dw04_start_with_4_and_6_players_works(n):
    g = make_started(n)
    assert g["phase"] == "REVEAL"
    assert g["phase_started"] == 0 and g["deadline"] == 30
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
    assert logic.end_phase(g, "t1", ON5, 1)["phase"] != phase


def _inv():
    return started_in("INVESTIGATION")


def _inv_question():
    return logic.question(started_in("INVESTIGATION"), "t1", 2, "Where?", 5)


UNKNOWN = "nope"
UNKNOWN_TOKEN_CASES = {
    "start": (lambda: make_lobby(4), lambda g: logic.start(g, UNKNOWN, {1, 2, 3, 4}, 0, seed=1)),
    "end_phase": (lambda: make_started(5), lambda g: logic.end_phase(g, UNKNOWN, ON5, 1)),
    "search": (_inv, lambda g: logic.search(g, UNKNOWN, LOC[0], 5)),
    "question": (_inv, lambda g: logic.question(g, UNKNOWN, 2, "Hi", 5)),
    "answer": (_inv_question,
               lambda g: logic.answer(g, UNKNOWN, last_log_id(g), "x", 6)),
    "share": (_inv, lambda g: logic.share(g, UNKNOWN, own_clue_ids(g, 1)[0], 5)),
    "plant": (_inv, lambda g: logic.plant(g, UNKNOWN, 2, LOC[0], 5)),
    "vote": (lambda: started_in("VOTE"), lambda g: logic.vote(g, UNKNOWN, 2, 5)),
}


@pytest.mark.parametrize("name", sorted(UNKNOWN_TOKEN_CASES))
def test_dw05_unknown_token_rejected(name):
    build, call = UNKNOWN_TOKEN_CASES[name]
    assert_rejected_unchanged(call, build())


# ================================================================ DW06
def test_dw06_timers_30_90_60_30():
    g = make_started(5)
    assert g["phase"] == "REVEAL"
    assert logic.tick(g, ON5, 29)["phase"] == "REVEAL"
    g = logic.tick(g, ON5, 30)
    assert g["phase"] == "INVESTIGATION" and g["phase_started"] == 30 and g["deadline"] == 120
    assert logic.tick(g, ON5, 119)["phase"] == "INVESTIGATION"
    g = logic.tick(g, ON5, 120)
    assert g["phase"] == "DISCUSSION" and g["phase_started"] == 120 and g["deadline"] == 180
    assert logic.tick(g, ON5, 179)["phase"] == "DISCUSSION"
    g = logic.tick(g, ON5, 180)
    assert g["phase"] == "VOTE" and g["phase_started"] == 180 and g["deadline"] == 210
    assert logic.tick(g, ON5, 209)["phase"] == "VOTE"
    g = logic.tick(g, ON5, 210)
    assert g["phase"] == "RESULT"
    assert g["result"] is not None


def test_dw06_new_phase_starts_at_now_of_the_switching_tick():
    g = logic.tick(make_started(5), ON5, 35)
    assert g["phase"] == "INVESTIGATION"
    assert g["phase_started"] == 35 and g["deadline"] == 125
    g = logic.tick(g, ON5, 130)
    assert g["phase"] == "DISCUSSION"
    assert g["phase_started"] == 130 and g["deadline"] == 190


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
    g = logic.search(_inv(), "t1", LOC[0], 5)
    assert g["acted"] == [1]
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", LOC[1], 6), g)
    assert_rejected_unchanged(lambda x: logic.question(x, "t1", 2, "Hi", 6), g)
    assert_rejected_unchanged(lambda x: logic.share(x, "t1", own_clue_ids(x, 1)[0], 6), g)


@pytest.mark.parametrize("phase", ["REVEAL", "DISCUSSION", "VOTE"])
def test_dw07_action_in_wrong_phase_rejected(phase):
    g = started_in(phase)
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", LOC[0], 5), g)
    assert_rejected_unchanged(lambda x: logic.question(x, "t1", 2, "Hi", 5), g)
    assert_rejected_unchanged(lambda x: logic.share(x, "t1", own_clue_ids(x, 1)[0], 5), g)


def test_dw07_action_in_lobby_rejected():
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", LOC[0], 5), make_lobby(4))


def test_dw07_search_already_searched_location_rejected_and_action_not_used_up():
    g = logic.search(_inv(), "t1", LOC[0], 5)
    assert g["searched"] == [LOC[0]]
    assert_rejected_unchanged(lambda x: logic.search(x, "t2", LOC[0], 6), g)
    assert 2 not in g["acted"]
    g2 = logic.search(g, "t2", LOC[1], 7)
    assert g2["searched"] == [LOC[0], LOC[1]]
    assert sorted(g2["acted"]) == [1, 2]


def test_dw07_search_unknown_location_rejected():
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", "Atlantis", 5), _inv())


def test_dw07_search_appends_log_entry_and_marks_acted():
    g = logic.search(_inv(), "t3", LOC[2], 5)
    assert g["acted"] == [3]
    entry = g["log"][-1]
    assert entry["kind"] == "search" and entry["location"] == LOC[2]
    assert entry["by"] == 3


def test_dw07_question_and_share_use_up_the_action():
    g = logic.question(_inv(), "t1", 2, "Hi", 5)
    assert g["acted"] == [1]
    g = logic.share(g, "t2", own_clue_ids(g, 2)[0], 6)
    assert sorted(g["acted"]) == [1, 2]
    assert g["log"][-1]["kind"] == "share"


# ================================================================ DW08
def test_dw08_question_to_oneself_rejected():
    assert_rejected_unchanged(lambda x: logic.question(x, "t1", 1, "Hi", 5), _inv())


def test_dw08_question_to_unknown_target_rejected():
    assert_rejected_unchanged(lambda x: logic.question(x, "t1", 99, "Hi", 5), _inv())


@pytest.mark.parametrize("text", ["", "   ", "x" * 141])
def test_dw08_question_text_length_out_of_range_rejected(text):
    assert_rejected_unchanged(lambda x: logic.question(x, "t1", 2, text, 5), _inv())


def test_dw08_question_text_140_chars_accepted():
    g = logic.question(_inv(), "t1", 2, "x" * 140, 5)
    q = g["log"][-1]
    assert q["kind"] == "question" and q["target"] == 2 and q["by"] == 1
    assert q["answered"] is False
    assert len(q["text"]) == 140


def test_dw08_second_answer_to_same_question_rejected():
    g = _inv_question()
    qid = last_log_id(g)
    g = logic.answer(g, "t2", qid, "Library.", 6)
    assert g["log"][-1]["kind"] == "answer"
    assert_rejected_unchanged(lambda x: logic.answer(x, "t2", qid, "Again", 7), g)


def test_dw08_answer_by_player_not_asked_rejected():
    g = _inv_question()
    qid = last_log_id(g)
    assert_rejected_unchanged(lambda x: logic.answer(x, "t3", qid, "Not me", 6), g)
    assert_rejected_unchanged(lambda x: logic.answer(x, "t1", qid, "Self", 6), g)


@pytest.mark.parametrize("text", ["", "x" * 141])
def test_dw08_answer_text_length_out_of_range_rejected(text):
    g = _inv_question()
    qid = last_log_id(g)
    assert_rejected_unchanged(lambda x: logic.answer(x, "t2", qid, text, 6), g)


def test_dw08_answer_unknown_question_id_rejected():
    assert_rejected_unchanged(lambda x: logic.answer(x, "t2", 9999, "x", 6), _inv_question())


def test_dw08_answer_does_not_use_up_action_and_allowed_in_discussion():
    g = _inv_question()
    qid = last_log_id(g)
    g = logic.answer(g, "t2", qid, "Library.", 6)
    assert 2 not in g["acted"]
    g = logic.search(g, "t2", LOC[0], 7)
    assert 2 in g["acted"]
    g2 = advance_to(_inv_question(), "DISCUSSION")
    g2 = logic.answer(g2, "t2", qid, "Late answer", 8)
    assert g2["log"][-1]["kind"] == "answer"


def _no_answer_entries(g):
    return [e for e in g["log"] if e["kind"] == "system" and "no answer" in e["text"]]


def test_dw08_unanswered_question_gets_no_answer_entry_when_discussion_ends():
    g = _inv_question()
    qid = last_log_id(g)
    g = advance_to(g, "DISCUSSION")
    assert _no_answer_entries(g) == []
    g = logic.end_phase(g, "t1", ON5, 0)
    assert g["phase"] == "VOTE"
    assert len(_no_answer_entries(g)) == 1
    q = [e for e in g["log"] if e["id"] == qid][0]
    assert q["answered"] is True


def test_dw08_answered_question_gets_no_no_answer_entry():
    g = _inv_question()
    g = logic.answer(g, "t2", last_log_id(g), "Library.", 6)
    g = advance_to(g, "VOTE")
    assert _no_answer_entries(g) == []


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
    free = next(loc for loc in LOC if loc not in g2["searched"])
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
def test_dw12_investigation_ends_when_all_online_players_acted():
    g = started_in("INVESTIGATION")
    for i, pid in enumerate(pids_of(g)[:4]):
        g = logic.search(g, token_of(g, pid), LOC[i], 10)
    assert logic.tick(g, ON5, 10)["phase"] == "INVESTIGATION"
    g = logic.search(g, "t5", LOC[4], 10)
    g = logic.tick(g, ON5, 10)
    assert g["phase"] == "DISCUSSION"
    assert g["phase_started"] == 10 and g["deadline"] == 70


def test_dw12_offline_player_who_has_not_acted_does_not_block_investigation():
    g = started_in("INVESTIGATION")
    for i in range(4):
        g = logic.search(g, "t%d" % (i + 1), LOC[i], 10)
    g = logic.tick(g, {1, 2, 3, 4}, 10)
    assert g["phase"] == "DISCUSSION"


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
def test_dw13_online_ids_21s_offline_20s_online():
    presence = {1: 79, 2: 80, 3: 100, 4: 0}
    assert logic.online_ids(presence, 100) == {2, 3}
    assert logic.online_ids({1: 79}, 100) == set()
    assert logic.online_ids({1: 80}, 100) == {1}
    assert logic.OFFLINE_AFTER == 20


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
def test_dw15_two_online_aborts_game(phase):
    g = logic.tick(started_in(phase), {1, 2}, 1)
    assert g["phase"] == "ABORTED"
    assert g["abort_reason"]


@pytest.mark.parametrize("phase", ["REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE"])
def test_dw15_three_online_continues(phase):
    g = logic.tick(started_in(phase), {1, 2, 3}, 1)
    assert g["phase"] == phase
    assert g["abort_reason"] is None


# ================================================================ DW16
def _vote_with_vote():
    return logic.vote(started_in("VOTE"), "t1", 2, 5)


def _inv_searched():
    return logic.search(_inv(), "t1", LOC[0], 5)


def _inv_planted():
    g = _inv()
    return logic.plant(g, murderer_token(g), innocent_pids(g)[0], plant_spot(g), 5)


def _answered():
    g = _inv_question()
    return logic.answer(g, "t2", last_log_id(g), "Library.", 6)


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
    "search_second_action": (_inv_searched, lambda g: logic.search(g, "t1", LOC[1], 6)),
    "search_wrong_phase": (lambda: started_in("DISCUSSION"), lambda g: logic.search(g, "t1", LOC[0], 6)),
    "search_already_searched": (_inv_searched, lambda g: logic.search(g, "t2", LOC[0], 6)),
    "question_to_self": (_inv, lambda g: logic.question(g, "t1", 1, "Hi", 5)),
    "question_empty": (_inv, lambda g: logic.question(g, "t1", 2, "", 5)),
    "question_141": (_inv, lambda g: logic.question(g, "t1", 2, "x" * 141, 5)),
    "answer_twice": (_answered, lambda g: logic.answer(g, "t2", last_log_id(g) - 1, "again", 7)),
    "answer_not_asked": (_inv_question, lambda g: logic.answer(g, "t3", last_log_id(g), "x", 6)),
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
    g2 = logic.search(g, "t1", LOC[0], 5)
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
