"""Seven places per case (instead of five), the two new kinds of place clue, and the map showing
which places somebody else is searching right now."""
import pytest
from conftest import make_started, open_places, started_in, token_of

import balance
import content
import generator
import logic
import ui
from test_ai_cases import fake_story

SEEDS = range(60)


def built(n, seed, story=None):
    return generator.build_valid_case(list(range(1, n + 1)), seed, story)


def clue_of_kind(case, kind):
    return [c for c in case["location_clues"] if c["kind"] == kind]


# ---------------------------------------------------------------- seven places

def test_every_case_has_seven_places_and_case_001_the_two_new_ones():
    assert logic.NUMBER_OF_LOCATIONS == 7 == len(content.LOCATIONS)
    assert {"Hovione Atrium", "Beach"} <= set(content.LOCATIONS)
    assert all(place in content.PLACES for place in content.LOCATIONS)     # every one has a pin
    assert logic.validate_story(content.DEFAULT_STORY) == []


@pytest.mark.parametrize("n", [4, 5, 6])
@pytest.mark.parametrize("story", ["001", "ai"])
def test_seven_place_clues_one_per_place(n, story):
    story = None if story == "001" else fake_story()
    locations = (story or content.DEFAULT_STORY)["locations"]
    for seed in SEEDS:
        case = built(n, seed, story)
        assert sorted(c["location"] for c in case["location_clues"]) == sorted(locations)
        assert len(case["locked"]) == logic.LOCKED_PLACES          # still two locked places


def test_a_story_with_five_places_is_refused():
    story = fake_story()
    story["locations"] = story["locations"][:5]
    assert "There must be exactly 7 locations." in logic.validate_story(story)


# ---------------------------------------------------------------- the culprit's way to the scene

@pytest.mark.parametrize("n", [4, 5, 6])
def test_the_route_leads_through_an_empty_place_with_the_culprits_object(n):
    for seed in SEEDS:
        case = built(n, seed)
        [route] = clue_of_kind(case, "route")
        culprit = next(c for c in case["characters"] if c["pid"] == case["murderer"])
        assert route["implicates"] == case["murderer"]
        assert content.ROLES[culprit["role"]]["trace"] in route["text"]       # the same object as at the scene
        assert culprit["role"] not in route["text"]                          # but no name
        nobody_there = {c["true_location"] for c in case["characters"]} | {culprit["alibi_location"]}
        assert route["location"] not in nobody_there
        assert "23:24" in route["text"] and len(route["text"]) <= logic.MAX_CLUE_TEXT
        assert balance.timeline_problems(case) == []


def test_an_open_air_route_has_a_camera_and_a_building_a_keycard_log():
    seen = set()
    for seed in range(200):
        [route] = clue_of_kind(built(5, seed), "route")
        open_air = route["location"] in content.OPEN_AIR
        assert ("keycard" in route["text"].lower()) != open_air
        seen.add(open_air)
    assert seen == {True, False}


def test_a_route_through_a_place_where_somebody_was_is_inconsistent():
    case = built(5, 1)
    [route] = clue_of_kind(case, "route")
    innocent = next(c for c in case["characters"] if c["pid"] != case["murderer"])
    route["location"] = innocent["true_location"]
    assert any("route" in problem for problem in balance.timeline_problems(case))


def test_the_route_counts_only_once_the_scene_is_known():
    case = built(5, 1)
    culprit = case["murderer"]
    without = {k: v for k, v in case.items()}
    without["location_clues"] = [c for c in case["location_clues"] if c["kind"] != "route"]
    scene_round = balance.opens_in(case, case["murder_location"])
    before = scene_round - 1
    assert balance.suspicion(case, before)[culprit] == balance.suspicion(without, before)[culprit]
    assert balance.suspicion(case, scene_round)[culprit] == balance.suspicion(without, scene_round)[culprit] + 1


def test_demo_suspects_read_the_route_as_pointing_at_the_owner_of_the_object():
    game = make_started(5)
    case = game["case"]
    [route] = clue_of_kind(case, "route")
    assert logic._pointed_at(game, route["text"]) == {case["murderer"]: 2}


# ---------------------------------------------------------------- the log that clears a pair

@pytest.mark.parametrize("n", [4, 5, 6])
def test_the_log_of_a_pairs_place_clears_both_who_were_there(n):
    for seed in SEEDS:
        case = built(n, seed)
        logs = [c for c in clue_of_kind(case, "confirms") if "seen_also" in c]
        assert len(logs) == 1
        log = logs[0]
        place_of = {c["pid"]: c["true_location"] for c in case["characters"]}
        role_of = {c["pid"]: c["role"] for c in case["characters"]}
        assert case["murderer"] not in (log["seen"], log["seen_also"])
        assert place_of[log["seen"]] == place_of[log["seen_also"]] == log["location"]
        assert role_of[log["seen"]] in log["text"] and role_of[log["seen_also"]] in log["text"]
        assert {log["seen"], log["seen_also"]} <= balance.alibied(case, logic.ROUNDS)


def test_the_cleared_pair_is_the_one_a_rumor_points_at_when_there_is_one():
    hits = 0
    for seed in SEEDS:
        case = built(5, seed)
        log = next(c for c in clue_of_kind(case, "confirms") if "seen_also" in c)
        rumored = {c["implicates"] for ch in case["characters"] for c in ch["clues"] if c["kind"] == "suspicious"}
        hits += bool(rumored & {log["seen"], log["seen_also"]})
    assert hits > len(SEEDS) // 2


def test_a_pair_log_naming_somebody_who_was_elsewhere_is_inconsistent():
    case = built(5, 1)
    log = next(c for c in clue_of_kind(case, "confirms") if "seen_also" in c)
    log["seen_also"] = case["murderer"]
    assert any("vouches for somebody" in problem for problem in balance.timeline_problems(case))


# ---------------------------------------------------------------- AI cases with seven places

def test_ai_cases_with_seven_places_are_balanced_for_every_number_of_players():
    assert logic.story_problems(fake_story()) == []


# ---------------------------------------------------------------- "Being searched" on the map

def round_1():
    return started_in("INVESTIGATION")


def test_a_place_somebody_else_holds_shows_as_being_searched_and_cannot_be_tapped():
    game = round_1()
    place = open_places(game)[0]
    game = logic.open_place(game, "t2", place, 20)
    busy = logic.busy_places(game, 21)
    assert busy == [place]
    links = {name: f"?step=search&place={name}" for name in content.LOCATIONS}
    html = ui.campus_map(game["searched"], view=logic.map_view(game), links=links, busy=busy)
    assert 'class="pin2 busy"' in html and "Being searched" in html
    assert f"place={place}" not in html                       # not tappable
    other = next(p for p in open_places(game) if p != place)
    assert f"place={other}" in html                            # the others still are
    assert "P2" not in html and "t2" not in html               # never who


def test_my_own_held_place_is_not_shown_as_busy_to_me():
    game = logic.open_place(round_1(), "t2", open_places(round_1())[0], 20)
    me = logic.my_hold(game, "t2", 21)
    busy = set(logic.busy_places(game, 21)) - {me}
    assert busy == set()


def test_a_place_held_by_somebody_else_cannot_be_opened_or_searched():
    game = round_1()
    place = open_places(game)[0]
    game = logic.open_place(game, "t2", place, 20)
    with pytest.raises(logic.Rejected):
        logic.open_place(game, "t3", place, 21)
    assert logic.busy_places(game, 20 + logic.HOLD_SECONDS + 1) == []   # the hold runs out


def test_busy_only_marks_open_places():
    game = round_1()
    view = logic.map_view(game)
    locked = next(p["name"] for p in view["places"] if p["state"] == "locked")
    html = ui.campus_map(game["searched"], view=view, busy={locked})
    assert "Being searched" not in html


def test_without_busy_places_the_map_is_unchanged():
    game = round_1()
    view = logic.map_view(game)
    assert ui.campus_map(game["searched"], view=view) == ui.campus_map(game["searched"], view=view, busy=())


def test_the_phone_redraws_when_a_place_becomes_busy():
    import runpy
    import sys
    from pathlib import Path
    from test_app_smoke import FakeStreamlit
    sys.modules["streamlit"] = FakeStreamlit()
    try:
        app = runpy.run_path(str(Path(__file__).parent.parent / "app.py"), run_name="app_under_test")
    finally:
        del sys.modules["streamlit"]
    game = round_1()
    public, me = app["views"](game, {1, 2, 3, 4, 5}, token_of(game, 1))
    held = logic.open_place(game, "t2", open_places(game)[0], __import__("time").time())
    public2, me2 = app["views"](held, {1, 2, 3, 4, 5}, token_of(held, 1))
    assert app["signature"](public, me) != app["signature"](public2, me2)
