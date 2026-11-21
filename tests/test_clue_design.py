"""The cards and places of every case, case #001 and AI cases alike, are true, physically
possible and give nobody away by their kind:
- every player, the culprit too, holds one sighting (or the witness account) and one more card;
- a sighting is always of somebody at the observer's own place, at the time on the card;
- at the start the culprit is never the only one without an alibi;
- open-air places have a night camera, not a keycard log."""
import pytest

import balance
import content
import generator
import logic
from test_ai_cases import fake_story

STORIES = {"case 001": content.DEFAULT_STORY, "AI": None}
SEEDS = list(range(120)) + [logic.DEMO_SEED]


def cases(story_name):
    story = STORIES[story_name] or fake_story()
    for n in (4, 5, 6):
        for seed in SEEDS:
            yield generator.build_case(list(range(1, n + 1)), seed, story)


@pytest.mark.parametrize("story", STORIES)
def test_every_case_is_valid_and_its_timeline_holds_together(story):
    for case in cases(story):
        pids = [c["pid"] for c in case["characters"]]
        assert logic.validate_case(case, pids, STORIES[story] or fake_story()) == []
        assert balance.timeline_problems(case) == []


@pytest.mark.parametrize("story", STORIES)
def test_the_kind_of_cards_gives_the_culprit_away_in_no_case(story):
    for case in cases(story):
        kinds = {c["pid"]: tuple(sorted(clue["kind"] for clue in c["clues"])) for c in case["characters"]}
        culprit = case["murderer"]
        assert any(kinds[pid] == kinds[culprit] for pid in kinds if pid != culprit)
        assert "confirms" in kinds[culprit]                       # the culprit has a sighting, too


@pytest.mark.parametrize("story", STORIES)
def test_the_culprit_is_never_the_only_one_without_an_alibi_at_the_start(story):
    for case in cases(story):
        no_alibi = balance.analyze(case)["no_alibi_round_1"]
        assert case["murderer"] in no_alibi and len(no_alibi) >= 2
        assert balance.analyze(case)["no_alibi_at_the_end"] == [case["murderer"]]   # but it all clears up


@pytest.mark.parametrize("story", STORIES)
def test_every_sighting_is_of_somebody_at_the_observers_own_place(story):
    for case in cases(story):
        place_of = {c["pid"]: c["true_location"] for c in case["characters"]}
        for c in case["characters"]:
            for clue in c["clues"]:
                if clue["kind"] == "confirms":
                    assert clue["at"] in clue["text"] and clue["time"] in clue["text"]
                    if c["pid"] != case["murderer"] and clue["seen"] != case["murderer"]:
                        assert place_of[c["pid"]] == place_of[clue["seen"]] == clue["at"]
                    else:                                         # the culprit's walk at 23:05
                        assert clue["time"] == generator.EARLY_TIME


def test_open_air_places_have_a_camera_and_buildings_a_keycard_log():
    assert content.OPEN_AIR == {"Beach"}                 # the Main Deck is an indoor hall
    seen = set()
    for case in cases("AI"):
        for clue in case["location_clues"]:
            if clue["kind"] in ("alibi_broken", "confirms"):
                open_air = clue["location"] in content.OPEN_AIR
                assert ("camera" in clue["text"]) == open_air and ("keycard" in clue["text"]) != open_air
                seen.add(open_air)
    assert seen == {True, False}


def test_private_views_never_show_who_was_seen_where_as_data():
    g = logic.new_game("ABCD", 0)
    for i in range(1, 6):
        g = logic.join(g, f"P{i}", f"t{i}", 0)
    g = logic.start(g, "t1", {1, 2, 3, 4, 5}, 0, seed=logic.DEMO_SEED, fixed_case=True)
    for i in range(1, 6):
        for clue in logic.private_view(g, f"t{i}")["clues"]:
            assert set(clue) == {"id", "text", "shared"}
