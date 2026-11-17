"""Detective notebook: a private grid of suspects × places with ✓ / ✗ / ?."""
import json

import pytest

import logic
from conftest import (
    LOC, advance_to, innocent_pids, make_lobby, murderer_pid,
    online_all, pids_of, started_in, token_of,
)

PIDS = [1, 2, 3]
PLACES = ["Hall", "Lab"]


def notes(cells=None, suspects=None, places=None):
    return {"cells": cells or {}, "suspects": suspects or {}, "places": places or {}}


# ---------------------------------------------------------------- set_notes

def test_set_notes_saves_only_for_this_player_and_drops_empty_marks():
    g = started_in("INVESTIGATION")
    a, b = pids_of(g)[:2]
    mine = notes(cells={str(b): {LOC[0]: "✗", LOC[1]: ""}}, suspects={str(b): "?"},
                 places={LOC[2]: "✓", LOC[3]: None})
    g2 = logic.set_notes(g, token_of(g, a), mine, 5)
    assert g is not g2 and "notes" not in g                     # pure
    assert logic.private_view(g2, token_of(g2, a))["notes"] == notes(
        cells={str(b): {LOC[0]: "✗"}}, suspects={str(b): "?"}, places={LOC[2]: "✓"})
    assert logic.private_view(g2, token_of(g2, b))["notes"] == logic.empty_notes()


def test_notes_never_reach_the_public_view():
    g = started_in("DISCUSSION")
    a = pids_of(g)[0]
    g = logic.set_notes(g, token_of(g, a), notes(places={LOC[0]: "✓"}), 5)
    for phase in ("DISCUSSION", "VOTE", "RESULT"):
        g = advance_to(g, phase)
        assert "✓" not in json.dumps(logic.public_view(g, online_all(g)), ensure_ascii=False)


@pytest.mark.parametrize("bad", [
    notes(cells={"1": {LOC[0]: "X"}}),          # not a mark
    notes(cells={"99": {LOC[0]: "✗"}}),         # not a player
    notes(cells={"1": {"Moon": "✗"}}),          # not a place
    notes(suspects={"99": "✗"}),
    notes(places={"Moon": "✓"}),
])
def test_set_notes_rejects_bad_marks(bad):
    g = started_in("INVESTIGATION")
    with pytest.raises(logic.Rejected):
        logic.set_notes(g, token_of(g, 1), bad, 5)


def test_set_notes_needs_a_running_game_and_a_real_player():
    with pytest.raises(logic.Rejected):
        logic.set_notes(make_lobby(4), "t1", notes(), 0)
    g = started_in("INVESTIGATION")
    with pytest.raises(logic.Rejected):
        logic.set_notes(g, "nobody", notes(), 0)


# ---------------------------------------------------------------- deduce_notes

def test_no_marks_leave_everything_open():
    d = logic.deduce_notes(notes(), PIDS, PLACES)
    assert len(d["possible"]) == 6 and d["solved"] is None and not d["conflict"]
    assert all(mark == ("", False) for row in d["cells"].values() for mark in row.values())


def test_innocent_player_strikes_their_own_row():
    d = logic.deduce_notes(notes(), PIDS, PLACES, innocent_pid=1)
    assert d["cells"][1] == {"Hall": ("✗", True), "Lab": ("✗", True)}
    assert (1, "Hall") not in d["possible"] and len(d["possible"]) == 4


def test_whole_suspect_and_whole_place_marks_strike_rows_and_columns():
    d = logic.deduce_notes(notes(suspects={"2": "✗"}, places={"Lab": "✗"}), PIDS, PLACES)
    assert d["possible"] == [(1, "Hall"), (3, "Hall")]
    assert d["cells"][2]["Hall"] == ("✗", True) and d["cells"][1]["Lab"] == ("✗", True)


def test_a_ticked_cell_rules_out_every_other_combination():
    d = logic.deduce_notes(notes(cells={"3": {"Lab": "✓"}}), PIDS, PLACES)
    assert d["possible"] == [(3, "Lab")] and d["solved"] == (3, "Lab")
    assert d["cells"][3]["Lab"] == ("✓", False)                 # the player's own mark
    assert d["cells"][1]["Hall"] == ("✗", True)


def test_the_last_open_combination_is_ticked_automatically():
    marks = notes(suspects={"1": "✗", "2": "✗"}, cells={"3": {"Hall": "✗"}})
    d = logic.deduce_notes(marks, PIDS, PLACES)
    assert d["solved"] == (3, "Lab") and d["cells"][3]["Lab"] == ("✓", True)


def test_question_marks_change_nothing_and_stay_visible():
    d = logic.deduce_notes(notes(cells={"2": {"Hall": "?"}}), PIDS, PLACES)
    assert len(d["possible"]) == 6 and d["cells"][2]["Hall"] == ("?", False)


@pytest.mark.parametrize("marks", [
    notes(suspects={"1": "✓", "2": "✓"}),
    notes(places={"Hall": "✓", "Lab": "✓"}),
    notes(cells={"1": {"Hall": "✓"}, "2": {"Lab": "✓"}}),
    notes(suspects={"1": "✗", "2": "✗", "3": "✗"}),
    notes(suspects={"1": "✗"}, cells={"1": {"Hall": "✓"}}),
])
def test_contradicting_marks_are_reported(marks):
    d = logic.deduce_notes(marks, PIDS, PLACES)
    assert d["conflict"] and d["solved"] is None


def test_the_real_solution_survives_honest_marks():
    g = started_in("INVESTIGATION")
    m = murderer_pid(g)
    scene = g["case"]["murder_location"]
    others = [pid for pid in innocent_pids(g)]
    marks = notes(suspects={str(pid): "✗" for pid in others[1:]},
                  places={loc: "✗" for loc in LOC if loc != scene})
    me = others[0]
    d = logic.deduce_notes(marks, pids_of(g), LOC, innocent_pid=me)
    assert d["solved"] == (m, scene)
