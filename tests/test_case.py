"""Case generator and case validator (Done-when 01-03)."""
import copy
import json

import pytest

import content
import generator
import logic

PIDS = [1, 2, 3, 4, 5]


def all_clues(case):
    return [c for ch in case["characters"] for c in ch["clues"]] + case["location_clues"]


def base_case(seed=1):
    case = generator.build_case(PIDS, seed)
    assert logic.validate_case(case, PIDS) == []
    return case


# ---------------------------------------------------------------- DW01
@pytest.mark.parametrize("n", [4, 5, 6])
def test_dw01_build_case_is_valid_for_200_seeds(n):
    pids = list(range(1, n + 1))
    bad = {}
    for seed in range(200):
        case = generator.build_case(pids, seed)
        problems = logic.validate_case(case, pids)
        if problems:
            bad[seed] = problems
    assert bad == {}


# ---------------------------------------------------------------- DW02
@pytest.mark.parametrize("n", [4, 5, 6])
def test_dw02_same_seed_identical_case(n):
    pids = list(range(1, n + 1))
    for seed in range(25):
        a = generator.build_case(pids, seed)
        b = generator.build_case(pids, seed)
        assert a == b
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_dw02_every_role_is_murderer_role_at_least_once_in_300_seeds():
    pids = [1, 2, 3, 4, 5, 6]
    roles = set()
    for seed in range(300):
        case = generator.build_case(pids, seed)
        m = case["murderer"]
        roles.add(next(c["role"] for c in case["characters"] if c["pid"] == m))
    assert len(content.ROLES) == 6
    assert roles == set(content.ROLES)


# ---------------------------------------------------------------- DW03
def _murderer_not_in_pids(case):
    case["murderer"] = 99


def _murderer_one_strong_clue(case):
    m = case["murderer"]
    strong = [c for c in all_clues(case)
              if c["implicates"] == m and c["kind"] in logic.STRONG_KINDS]
    assert len(strong) >= 2
    for c in strong[1:]:
        c["kind"] = "neutral"


def _innocent_with_strong_clue(case):
    inn = [p for p in PIDS if p != case["murderer"]]
    clue = next(c for c in all_clues(case) if c["kind"] not in logic.STRONG_KINDS)
    clue["implicates"] = inn[0]
    clue["kind"] = "scene"


def _unknown_location(case):
    case["location_clues"][0]["location"] = "Atlantis"


def _text_murderer(case):
    case["location_clues"][0]["text"] = "The murderer left this behind."


def _text_killer_uppercase(case):
    case["location_clues"][0]["text"] = "A KILLER was here."


def _four_location_clues(case):
    case["location_clues"].pop()


def _innocent_two_suspicious(case):
    inn = [p for p in PIDS if p != case["murderer"]]
    weak = [c for c in all_clues(case) if c["kind"] not in logic.STRONG_KINDS]
    for c in weak[:2]:
        c["implicates"] = inn[0]
        c["kind"] = "suspicious"


def _text_201_chars(case):
    case["location_clues"][0]["text"] = "x" * 201


def _empty_clue_text(case):
    case["location_clues"][0]["text"] = ""


def _one_private_clue_only(case):
    case["characters"][0]["clues"].pop()


def _unknown_role(case):
    case["characters"][0]["role"] = "The Wizard"


def _missing_character(case):
    case["characters"].pop()


MANIPULATIONS = [
    _murderer_not_in_pids,
    _murderer_one_strong_clue,
    _innocent_with_strong_clue,
    _unknown_location,
    _text_murderer,
    _text_killer_uppercase,
    _four_location_clues,
    _innocent_two_suspicious,
    _text_201_chars,
    _empty_clue_text,
    _one_private_clue_only,
    _unknown_role,
    _missing_character,
]


@pytest.mark.parametrize("manipulate", MANIPULATIONS, ids=lambda f: f.__name__.lstrip("_"))
def test_dw03_validate_case_reports_problem(manipulate):
    base = base_case()
    case = copy.deepcopy(base)
    manipulate(case)
    problems = logic.validate_case(case, PIDS)
    assert isinstance(problems, list)
    assert problems != []
    # validation does not mutate and the untouched base stays valid
    assert logic.validate_case(base, PIDS) == []


def test_dw03_clue_text_of_exactly_200_chars_is_valid():
    case = copy.deepcopy(base_case())
    case["location_clues"][0]["text"] = "x" * 200
    assert logic.validate_case(case, PIDS) == []
