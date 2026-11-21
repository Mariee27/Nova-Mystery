"""Case #001 is handcrafted and must not change by accident: not its story, roles, culprit,
places or solution. These fingerprints guard it.

They were set once more on purpose when the clue cards were repaired (the cards gave the
culprit away by their kind, and some sightings were physically impossible). Story, roles,
culprit, crime scene and false alibi stayed exactly the same; only the cards and the place
clues changed. The story text changed in two words: the campus is in Carcavelos, not Lisbon. AI cases additionally get difficulty balancing (balance.py); case #001 never does.
The words of the mini-games (story["minigames"]) are not part of the story fingerprint: they
decide nothing about the case and are checked in tests/test_case_minigames.py.
"""
import hashlib
import json

import pytest

import content
import generator
import logic

FINGERPRINTS = {
    "demo-4": "5ca9df2c6853a2c9",
    "story001-4-1": "547b015e3ef4bc42",
    "story001-4-7": "705795f9638bb913",
    "story001-4-12345": "74971e2cfad399c0",
    "demo-5": "5c96cfdaacc07f3a",
    "story001-5-1": "7b7c7712562d9d83",
    "story001-5-7": "bc081b9465c18175",
    "story001-5-12345": "bba6e10794f49d0a",
    "demo-6": "7b7514cff1592f55",
    "story001-6-1": "ac2875708971b025",
    "story001-6-7": "2022961f623c8c70",
    "story001-6-12345": "9310613691b05d93",
}
STORY_FINGERPRINT = "7d4dc5ce8c5e370e"   # "Carcavelos" instead of "Lisbon" in the intro and an ending


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def without_minigames(story):
    return {key: value for key, value in story.items() if key != "minigames"}


def test_the_story_of_case_001_is_unchanged():
    assert fingerprint(without_minigames(content.DEFAULT_STORY)) == STORY_FINGERPRINT


@pytest.mark.parametrize("n", [4, 5, 6])
@pytest.mark.parametrize("seed", ["demo", 1, 7, 12345])
def test_case_001_is_built_exactly_as_before(n, seed):
    pids = list(range(1, n + 1))
    number = logic.DEMO_SEED if seed == "demo" else seed
    key = f"demo-{n}" if seed == "demo" else f"story001-{n}-{seed}"
    assert fingerprint(generator.build_valid_case(pids, number, content.DEFAULT_STORY)) == FINGERPRINTS[key]


@pytest.mark.parametrize("n", [4, 5, 6])
def test_the_demo_switch_starts_exactly_the_same_game_as_before(n):
    game = logic.new_game("ABCD", 0)
    for i in range(1, n + 1):
        game = logic.join(game, f"P{i}", f"t{i}", 0)
    game = logic.start(game, "t1", set(range(1, n + 1)), 0, seed=logic.DEMO_SEED, fixed_case=True)
    assert game["story"] is content.DEFAULT_STORY or fingerprint(without_minigames(game["story"])) == STORY_FINGERPRINT
    assert fingerprint(game["case"]) == FINGERPRINTS[f"demo-{n}"]
    assert "solution" not in game["case"] and "balance" not in game["case"]


# Who did it, where, and what they claim: the same as before the cards were repaired.
FACTS_BEFORE_THE_REPAIR = {
    4: (4, "Main Deck", "Santander Hall"), 5: (5, "Main Deck", "Santander Hall"), 6: (5, "Auditorium", "Main Deck"),
}


@pytest.mark.parametrize("n", [4, 5, 6])
def test_the_demo_keeps_its_culprit_scene_and_false_alibi(n):
    case = generator.build_valid_case(list(range(1, n + 1)), logic.DEMO_SEED, content.DEFAULT_STORY)
    culprit = next(c for c in case["characters"] if c["pid"] == case["murderer"])
    assert (case["murderer"], case["murder_location"], culprit["alibi_location"]) == FACTS_BEFORE_THE_REPAIR[n]
