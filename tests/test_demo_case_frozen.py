"""Case #001 is handcrafted and must not change by accident: not its story, roles, culprit,
places or solution. These fingerprints guard it.

They were set once more on purpose when the clue cards were repaired (the cards gave the
culprit away by their kind, and some sightings were physically impossible). Story, roles,
culprit, crime scene and false alibi stayed exactly the same; only the cards and the place
clues changed. The story text changed in two words: the campus is in Carcavelos, not Lisbon. The Main Deck became an indoor hall (keycard log instead of night camera): only the wording of
those clues changed, in the cases marked by the changed fingerprints. AI cases additionally get difficulty balancing (balance.py); case #001 never does.
Set again on purpose when the key evidence stopped naming the culprit: the object at the scene has no
owner (the dossiers say who carries what), the empty log names nobody (compare the alibis), and the
culprit's walk before the keycard window has two times of its own instead of 23:05 on both cards.
Only those texts and times changed; every fact, card and lock stayed the same.
Set again on purpose when every case got seven places instead of five (the team agreed): case #001
gained the Hovione Atrium and the Beach, and two new place clues (the culprit's way to the scene and
the log that clears a pair). With seven places the dice fall differently, so the demo has new facts.
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
    "demo-4": "114c801b1aa70426",
    "story001-4-1": "171c31c26140b5fb",
    "story001-4-7": "a8b34c74a2da1348",
    "story001-4-12345": "96b7450104dbd4f0",
    "demo-5": "caf0cae2df2b4d6d",
    "story001-5-1": "70ec9d41f3fdfd87",
    "story001-5-7": "9e6e689d3386c3f1",
    "story001-5-12345": "24137cffa910cb79",
    "demo-6": "9c0f5512b1b8fa17",
    "story001-6-1": "457cd98c5485ffa3",
    "story001-6-7": "857c47abd8c142fa",
    "story001-6-12345": "12f417df19ee5846",
}
STORY_FINGERPRINT = "d19dea8790399080"   # seven places: Hovione Atrium and Beach added


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


# Who did it, where, and what they claim in the demo: set anew with the seven places.
FACTS_BEFORE_THE_REPAIR = {
    4: (4, "Beach", "Santander Hall"), 5: (5, "Main Deck", "Library"), 6: (5, "Auditorium", "Horizon Hall"),
}


@pytest.mark.parametrize("n", [4, 5, 6])
def test_the_demo_keeps_its_culprit_scene_and_false_alibi(n):
    case = generator.build_valid_case(list(range(1, n + 1)), logic.DEMO_SEED, content.DEFAULT_STORY)
    culprit = next(c for c in case["characters"] if c["pid"] == case["murderer"])
    assert (case["murderer"], case["murder_location"], culprit["alibi_location"]) == FACTS_BEFORE_THE_REPAIR[n]
