"""Investigation rounds and the campus map.

Every rule is checked on the server (logic.py), not only in the interface. For each
rule there is a test for the allowed case and one for the refused case.
"""
import copy
import json

import pytest
from conftest import (
    assert_rejected_unchanged,
    locked_places,
    make_lobby,
    make_started,
    murderer_token,
    open_places,
    pids_of,
    started_in,
    to_last_round,
    token_of,
)

import content
import generator
import logic
import ui

ON5 = {1, 2, 3, 4, 5}


def next_round(game, now=0):
    return logic.end_phase(game, "t1", ON5, now)


def round_where(game, place):
    """Advance until `place` is unlocked."""
    while logic.locked_until(game, place) is not None:
        game = next_round(game)
    return game


# ---------------------------------------------------------------- one move per player per round

def test_allowed_the_first_move_of_a_round():
    g = started_in("INVESTIGATION")
    g = logic.search(g, "t1", open_places(g)[0], 5)
    assert g["acted"] == [1]


def test_refused_a_second_move_in_the_same_round():
    g = started_in("INVESTIGATION")
    g = logic.search(g, "t1", open_places(g)[0], 5)
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", open_places(x)[0], 6), g)
    assert_rejected_unchanged(lambda x: logic.question(x, "t1", 2, "Where were you?", 6), g)


def test_allowed_a_new_move_in_the_next_round():
    g = started_in("INVESTIGATION")
    g = logic.search(g, "t1", open_places(g)[0], 5)
    g = next_round(g)
    assert g["round"] == 2 and g["acted"] == []
    g = logic.search(g, "t1", open_places(g)[0], 6)
    assert g["acted"] == [1]


# ---------------------------------------------------------------- locked places

def test_refused_searching_a_locked_place():
    g = started_in("INVESTIGATION")
    for place in locked_places(g):
        with pytest.raises(logic.Rejected, match="locked"):
            logic.search(g, "t1", place, 5)


def test_allowed_searching_a_place_once_its_round_has_come():
    g = started_in("INVESTIGATION")
    for place, opens in g["case"]["locked"].items():
        later = round_where(g, place)
        assert later["round"] == opens
        assert logic.search(later, "t1", place, 5)["searched"] == [place]


def test_the_crime_scene_starts_locked_and_opens_in_round_2_or_3():
    for seed in range(50):
        g = make_started(5, seed)
        locked = g["case"]["locked"]
        assert g["case"]["murder_location"] in locked
        assert sorted(locked.values()) == [2, 3]


def test_refused_planting_in_a_locked_place():
    g = started_in("INVESTIGATION")
    place = locked_places(g)[0]
    assert place not in logic.plant_locations(g)
    assert_rejected_unchanged(
        lambda x: logic.plant(x, murderer_token(x), next(p for p in pids_of(x) if p != x["case"]["murderer"]),
                              place, 5), g)


# ---------------------------------------------------------------- one clue per place

def test_allowed_the_first_search_of_a_place_finds_its_clue():
    g = started_in("INVESTIGATION")
    place = open_places(g)[0]
    g = logic.search(g, "t1", place, 5)
    entry = g["log"][-1]
    assert entry["location"] == place and entry["clue_id"].startswith("L") and entry["round"] == 1


def test_refused_searching_a_place_that_was_already_searched():
    g = started_in("INVESTIGATION")
    place = open_places(g)[0]
    g = logic.search(g, "t1", place, 5)
    with pytest.raises(logic.Rejected, match="already been searched"):
        logic.search(g, "t2", place, 6)
    assert_rejected_unchanged(lambda x: logic.search(x, "t2", place, 6), g)


def test_cases_have_no_second_clue_per_place():
    for seed in range(30):
        case = generator.build_case([1, 2, 3, 4, 5], seed)
        assert "closer_looks" not in case
        assert sorted(c["location"] for c in case["location_clues"]) == sorted(content.LOCATIONS)


# ---------------------------------------------------------------- interrogate

def test_allowed_a_question_of_five_characters():
    g = logic.question(started_in("INVESTIGATION"), "t1", 2, "Where", 5)
    assert g["log"][-1]["text"] == "Where" and g["log"][-1]["round"] == 1


def test_refused_a_question_shorter_than_five_characters():
    g = started_in("INVESTIGATION")
    with pytest.raises(logic.Rejected, match="at least 5 characters"):
        logic.question(g, "t1", 2, "  Why ", 5)


def test_refused_questioning_yourself_or_a_player_from_another_room():
    g = started_in("INVESTIGATION")
    assert_rejected_unchanged(lambda x: logic.question(x, "t1", 1, "Where were you?", 5), g)
    assert_rejected_unchanged(lambda x: logic.question(x, "t1", 99, "Where were you?", 5), g)


def test_allowed_confronting_with_public_evidence_and_refused_with_hidden_evidence():
    g = started_in("INVESTIGATION")
    g = logic.search(g, "t1", open_places(g)[0], 5)
    exhibit = g["log"][-1]["id"]
    assert logic.question(g, "t2", 3, "Explain this.", 6, evidence_id=exhibit)["log"][-1]["evidence"] == exhibit
    assert_rejected_unchanged(lambda x: logic.question(x, "t2", 3, "Explain this.", 6, evidence_id=999), g)


# ---------------------------------------------------------------- share a clue

def my_clues(g, token):
    return [c["id"] for c in logic.private_view(g, token)["clues"]]


def test_allowed_sharing_one_of_your_own_clues():
    g = started_in("INVESTIGATION")
    g = logic.share(g, "t1", my_clues(g, "t1")[0], 5)
    assert g["log"][-1]["kind"] == "share" and g["acted"] == [1]


def test_refused_sharing_somebody_elses_clue():
    g = started_in("INVESTIGATION")
    assert_rejected_unchanged(lambda x: logic.share(x, "t1", my_clues(x, "t2")[0], 5), g)


def test_refused_sharing_the_same_clue_twice():
    g = started_in("INVESTIGATION")
    clue = my_clues(g, "t1")[0]
    g = next_round(logic.share(g, "t1", clue, 5))
    assert_rejected_unchanged(lambda x: logic.share(x, "t1", clue, 6), g)


def test_a_player_never_receives_other_players_cards_and_the_board_only_public_data():
    g = started_in("INVESTIGATION")
    mine = logic.private_view(g, "t1")
    text = json.dumps(mine)
    for other in g["case"]["characters"]:
        if other["pid"] != 1:
            assert all(c["text"] not in text for c in other["clues"])
            assert other["secret"] is None or other["secret"] not in text
    board = json.dumps(logic.public_view(g, ON5))
    for character in g["case"]["characters"]:
        assert all(c["text"] not in board for c in character["clues"])
    assert '"murderer"' not in board


# ---------------------------------------------------------------- only in the investigation

@pytest.mark.parametrize("phase", ["REVEAL", "DISCUSSION", "VOTE"])
def test_refused_searching_outside_the_investigation(phase):
    g = started_in(phase)
    place = content.LOCATIONS[0]
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", place, 5), g)


def test_refused_searching_in_the_lobby():
    assert_rejected_unchanged(lambda x: logic.search(x, "t1", content.LOCATIONS[0], 0), make_lobby(5))


def test_allowed_searching_in_every_round_of_the_investigation():
    g = started_in("INVESTIGATION")
    for _ in range(logic.ROUNDS):
        places = open_places(g)
        if places:
            g = logic.search(g, "t1", places[0], 5)
            assert 1 in g["acted"]
        g = next_round(g)
    assert g["phase"] == "DISCUSSION"


# ---------------------------------------------------------------- rounds and timers

def test_there_are_three_rounds_of_at_most_five_minutes():
    assert logic.ROUNDS == 3 and logic.DURATIONS["INVESTIGATION"] == 300
    g = started_in("INVESTIGATION")
    assert g["round"] == 1 and g["deadline"] - g["phase_started"] == 300


def everybody_asks(g, now=5):
    for pid in pids_of(g):
        g = logic.question(g, token_of(g, pid), 1 if pid != 1 else 2, "Where were you?", now)
    return g


def answer_all(g, now=6):
    for e in [e for e in g["log"] if e["kind"] == "question" and not e["answered"]]:
        g = logic.answer(g, token_of(g, e["target"]), e["id"], "In the Library.", now)
    return g


def test_refused_ending_a_round_early_while_a_question_of_this_round_is_unanswered():
    g = everybody_asks(started_in("INVESTIGATION"))
    assert logic.tick(g, ON5, 6)["round"] == 1                       # waits for the answers
    assert logic.tick(g, ON5, g["deadline"])["round"] == 2            # but never past the timer


def test_allowed_a_round_ends_early_when_everybody_moved_and_every_question_is_answered():
    g = answer_all(everybody_asks(started_in("INVESTIGATION")))
    assert logic.tick(g, ON5, 7)["round"] == 2


def test_allowed_the_round_does_not_wait_for_an_answer_from_a_player_who_is_offline():
    g = everybody_asks(started_in("INVESTIGATION"))
    for e in g["log"]:
        if e["kind"] == "question" and e["target"] != 2:
            g = logic.answer(g, token_of(g, e["target"]), e["id"], "Home.", 6)
    assert logic.tick(g, ON5, 7)["round"] == 1                        # player 2 has not answered
    assert logic.tick(g, ON5 - {2}, 7)["round"] == 2                  # ... and is offline now


def test_allowed_answering_does_not_use_up_your_move():
    g = logic.question(started_in("INVESTIGATION"), "t1", 2, "Where were you?", 5)
    g = logic.answer(g, "t2", g["log"][-1]["id"], "Library.", 6)
    assert g["acted"] == [1]
    assert logic.search(g, "t2", open_places(g)[0], 7)["acted"] == [1, 2]


def test_allowed_a_player_who_misses_the_timer_simply_loses_the_move():
    g = started_in("INVESTIGATION")
    g = logic.search(g, "t1", open_places(g)[0], 5)
    g = logic.tick(g, ON5, g["deadline"])
    assert g["round"] == 2 and g["acted"] == []


def test_after_the_last_round_comes_a_3_minute_discussion_and_a_1_minute_vote():
    g = to_last_round(started_in("INVESTIGATION"))
    g = logic.tick(g, ON5, g["deadline"])
    assert g["phase"] == "DISCUSSION" and g["deadline"] - g["phase_started"] == 180
    g = logic.tick(g, ON5, g["deadline"])
    assert g["phase"] == "VOTE" and g["deadline"] - g["phase_started"] == 60


def test_demo_suspects_still_end_every_round_when_nothing_is_left_to_search():
    g = make_lobby(1)
    for _ in range(5):
        g = logic.add_bot(g, "t1", 0)
    g = logic.start(g, "t1", logic.with_bots(g, {1}), 0, seed=2)
    g = logic.end_phase(g, "t1", logic.with_bots(g, {1}), 0)
    now = 0
    while g["phase"] == "INVESTIGATION":
        g = logic.search(g, "t1", open_places(g)[0], now) if open_places(g) and 1 not in g["acted"] else (
            g if 1 in g["acted"] else logic.question(g, "t1", 2, "Where?", now))
        now += 30
        g = logic.bot_moves(logic.tick(g, logic.with_bots(g, {1}), now), now)
        g = logic.tick(g, logic.with_bots(g, {1}), now)
        assert now < 6 * 60 * 5, "a round waited for a bot that could not move"
    assert g["phase"] == "DISCUSSION"


# ---------------------------------------------------------------- the map shows only public facts

def test_the_map_shows_every_state_of_a_place():
    g = started_in("INVESTIGATION")
    states = {p["name"]: p["state"] for p in logic.map_view(g)["places"]}
    assert sorted(states.values()).count("locked") == 2 and set(states.values()) == {"open", "locked"}
    place = open_places(g)[0]
    g = logic.search(g, "t1", place, 5)
    view = {p["name"]: p for p in logic.map_view(g)["places"]}
    assert view[place]["state"] == "done" and len(view[place]["found"]) == 1
    assert view[place]["found_in"] == 1
    assert view[locked_places(g)[0]]["opens_in"] in (2, 3)


@pytest.mark.parametrize("phase", ["LOBBY", "REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE"])
def test_the_map_never_gives_the_solution_away(phase):
    g = make_lobby(5) if phase == "LOBBY" else started_in(phase)
    text = json.dumps(logic.map_view(g))
    for word in ("murderer", "implicates", "clue_kind", "true_location", "token", '"by"'):
        assert word not in text
    if g["case"]:
        for clue in g["case"]["location_clues"]:
            assert clue["text"] not in text


# ---------------------------------------------------------------- only your own room

def test_refused_searching_with_a_token_from_another_room():
    room_a = logic.end_phase(make_started(5, 1), "t1", ON5, 0)
    room_b = make_started(5, 2, tokens=[f"b{i}" for i in range(1, 6)])
    assert token_of(room_b, 1) == "b1"
    assert_rejected_unchanged(lambda x: logic.search(x, "b1", open_places(x)[0], 5), room_a)


def test_allowed_a_player_sees_only_their_own_rooms_map():
    room_a = logic.end_phase(make_started(5, 1), "t1", ON5, 0)
    room_b = copy.deepcopy(room_a)
    room_b["code"] = "WXYZ"
    room_b = logic.search(room_b, "t1", open_places(room_b)[0], 5)
    # A search in room B changes nothing in room A's map.
    assert all(p["state"] != "done" for p in logic.map_view(room_a)["places"])
    assert any(p["state"] == "done" for p in logic.map_view(room_b)["places"])


# ---------------------------------------------------------------- the map on the screen

def test_the_campus_plan_places_pins_by_percent_and_links_only_when_given():
    g = started_in("INVESTIGATION")
    view = logic.map_view(g)
    html = ui.campus_map(g["searched"], view=view)
    for place in content.LOCATIONS:
        spot = content.PLACES[place]
        assert f"left:{spot['x']}%;top:{spot['y']}%" in html
    assert "<a " not in html                                    # the board: nothing to tap
    links = {open_places(g)[0]: "?room=ABCD&t=t1&step=search&place=x"}
    tappable = ui.campus_map(g["searched"], view=view, links=links)
    assert tappable.count("<a ") == 1 and 'target="_self"' in tappable
    assert "\n\n" not in html


def test_the_plan_draws_every_building_and_the_beach_from_the_data():
    html = ui.campus_map([])
    for label, (left, top, width, height) in content.BUILDINGS.items():
        assert f'left:{left}%;top:{top}%;width:{width}%;height:{height}%' in html
        assert f"<span>{label}</span>" in html
    assert 'class="beach"' in html and "Floor 0" in html


def test_pins_show_open_searched_and_locked_and_the_board_says_when():
    g = started_in("INVESTIGATION")
    place = open_places(g)[0]
    g = logic.search(g, "t1", place, 5)
    board = ui.campus_map(g["searched"], view=logic.map_view(g), board=True)
    assert board.count('class="pin2 open') == 2 and board.count('class="pin2 locked') == 2
    assert 'class="pin2 done now"' in board and "Just now" in board
    assert board.count("Opens round") == 2
    assert "t1" not in board and "P1" not in board               # never who searched


def test_the_plan_is_greyed_out_after_the_players_move_and_marks_the_selected_place():
    g = started_in("INVESTIGATION")
    view = logic.map_view(g)
    assert 'class="plan2 off"' in ui.campus_map(g["searched"], view=view, active=False)
    place = open_places(g)[0]
    assert 'class="pin2 open sel"' in ui.campus_map(g["searched"], view=view, selected=place)


def test_every_place_on_the_campus_has_a_spot_on_the_map():
    assert len(content.PLACES) == 8
    for place in content.PLACES.values():
        assert 0 <= place["x"] <= 100 and 0 <= place["y"] <= 100 and place["icon"] and place["letter"]
    assert all(place in content.PLACES for place in content.LOCATIONS)


# ---------------------------------------------------------------- the phone's screens

def test_the_place_card_shows_each_state_and_escapes_text():
    assert "No place selected" in ui.place_card(None)
    assert "Not searched yet" in ui.place_card("Library", {"state": "open", "opens_in": None})
    assert "opens in round 3" in ui.place_card("Library", {"state": "locked", "opens_in": 3})
    html = ui.place_card("Library", {"state": "done", "found_in": 2}, [{"id": 3, "text": "<script>x</script>"}])
    assert "round 2" in html and "Exhibit 3" in html and "<script>" not in html


def test_action_cards_are_links_only_when_the_action_is_possible():
    html = ui.action_cards([
        {"href": "?step=search", "icon": "search", "title": "Search a place", "text": "t", "info": "5 places open"},
        {"href": None, "icon": "share", "title": "Share a clue", "text": "t", "info": "All shared"}])
    assert html.count("<a ") == 1 and 'aria-disabled="true"' in html


def test_rows_chips_and_clue_cards_mark_what_is_selected():
    rows = ui.pick_rows([("?a=1", "Sofia", "The Dean", True), ("?a=2", "Tiago", "The Guard", False)])
    assert rows.count('class="pick sel"') == 1 and 'aria-checked="true"' in rows
    assert ui.chips([("?e=1", "Torn sheet", True)]).count('class="chip sel"') == 1
    cards = ui.clue_cards([("?c=1", 1, "Wet shoes", True), (None, 2, "Old clue", False)])
    assert "paper clue sel" in cards and "already shared" in cards


def test_clue_cards_are_one_block_with_one_card_per_clue():
    """Bare <a> cards end up in a <p> in st.markdown, and the browser splits them into extra boxes."""
    cards = ui.clue_cards([("?c=1", 1, "At 23:25 you saw someone.", False),
                           ("?c=2", 2, "At 23:30 you saw someone else.", False)])
    assert cards.startswith('<div class="clues">') and cards.endswith("</div>")
    assert cards.count('class="paper clue') == 2 and cards.count("<a ") == 2
    assert cards.count("Private clue 1") == 1 and cards.count("Private clue 2") == 1
    assert cards.count("At 23:25 you saw someone.") == 1


def test_the_move_made_card_is_stamped_and_the_waiting_list_names_no_action():
    assert "Logged" in ui.move_made("Clue shared", "Exhibit 4", "<b>x</b>")
    players = [{"pid": 1, "name": "Laura", "online": True, "acted": True},
               {"pid": 2, "name": "Sofia", "online": True, "acted": False}]
    html = ui.waiting_list(players, 1)
    assert "Waiting for 1 player" in html and "Laura (you)" in html and "choosing" in html
    assert "search" not in html.lower() and "shared" not in html.lower()


def test_last_move_is_only_the_players_own_move_of_this_round():
    g = started_in("INVESTIGATION")
    place = open_places(g)[0]
    g = logic.search(g, "t1", place, 5)
    assert logic.private_view(g, "t1")["last_move"]["location"] == place
    assert logic.private_view(g, "t2")["last_move"] is None
    assert logic.private_view(next_round(g), "t1")["last_move"] is None


# ---------------------------------------------------------------- the board

def test_the_board_header_shows_room_round_and_timer():
    html = ui.board_head("K7QX", 2, 3, 165)
    assert "K7QX" in html and "Round 2 of 3" in html and "2:45" in html


def test_the_evidence_board_is_newest_first_and_never_names_who_searched():
    g = started_in("INVESTIGATION")
    g = logic.search(g, "t1", open_places(g)[0], 5)
    g = logic.share(g, "t2", my_clues(g, "t2")[0], 6)
    log = logic.public_view(g, ON5)["log"]
    html = ui.evidence_board(log, lambda pid: f"Name{pid}")
    assert html.index("Shared by Name2") < html.index("Exhibit 1")
    assert "Name1" not in html and "R1" in html


def test_the_live_interrogation_shows_the_question_and_then_the_answer():
    g = started_in("INVESTIGATION")
    g = logic.question(g, "t1", 2, "Where were you?", 5)
    name, role = (lambda pid: f"Name{pid}"), (lambda pid: f"Role{pid}")
    waiting = ui.interrogation(logic.public_view(g, ON5)["log"], name, role)
    assert "Name1 (Role1) asks Name2 (Role2)" in waiting and "is typing" in waiting
    g = logic.answer(g, "t2", g["log"][-1]["id"], "In the Library.", 6)
    assert "In the Library." in ui.interrogation(logic.public_view(g, ON5)["log"], name, role)


def test_demo_suspects_leave_the_last_open_place_to_a_human_who_has_not_moved():
    g = make_lobby(1)
    for _ in range(4):
        g = logic.add_bot(g, "t1", 0)
    g = logic.start(g, "t1", logic.with_bots(g, {1}), 0, seed=2)
    g = logic.end_phase(g, "t1", logic.with_bots(g, {1}), 0)
    g = logic.bot_moves(g, 10_000)                     # every bot moves at once
    assert len(open_places(g)) == 1 and 1 not in g["acted"]
    g = logic.search(g, "t1", open_places(g)[0], 10_001)
    assert 1 in g["acted"]
