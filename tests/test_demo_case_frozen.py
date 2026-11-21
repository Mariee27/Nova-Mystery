"""Case #001 is handcrafted and must never change: not its story, roles, culprit, clues,
places or solution. These fingerprints were taken before AI cases got their difficulty
balancing; balancing applies to AI-written stories only."""
import hashlib
import json

import pytest

import content
import generator
import logic

FINGERPRINTS = {
    "demo-4": "ca73330b6af4664b", "demo-5": "29bb973c5b1a3d57", "demo-6": "ef5b03484005da3f",
    "story001-4-1": "e05d5f9916bffa78", "story001-4-7": "c1132b743bdd54d0", "story001-4-12345": "9836cb185671be12",
    "story001-5-1": "1e948ac03d43e65c", "story001-5-7": "59a066a2e0244d93", "story001-5-12345": "d95ef2d58795a928",
    "story001-6-1": "e0d910bb42aaad9a", "story001-6-7": "0e255b35e410078c", "story001-6-12345": "e135009e60fbdc68",
}
STORY_FINGERPRINT = "dc68ddb572c94dc1"


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def test_the_story_of_case_001_is_unchanged():
    assert fingerprint(content.DEFAULT_STORY) == STORY_FINGERPRINT


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
    assert game["story"] is content.DEFAULT_STORY or fingerprint(game["story"]) == STORY_FINGERPRINT
    assert fingerprint(game["case"]) == FINGERPRINTS[f"demo-{n}"]
    assert "solution" not in game["case"] and "balance" not in game["case"]
