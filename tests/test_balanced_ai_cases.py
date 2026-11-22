"""AI cases with balanced difficulty: neither obvious from the start nor unreasonably hard,
fair (the solution follows from the clues), and case #001 never touched (see
test_demo_case_frozen.py). Every AI answer here is a stand-in: nothing goes online."""
import copy
import json

import pytest

import ai
import balance
import content
import generator
import logic
import ui
from test_ai_cases import FAKE_ANSWER, SequenceClient, fake_story

PLAYER_COUNTS = [4, 5, 6]


def balanced(n, seed, story=None):
    return balance.build_balanced_case(list(range(1, n + 1)), seed, story or fake_story())


# ---------------------------------------------------------------- the balance itself

@pytest.mark.parametrize("n", PLAYER_COUNTS)
def test_every_ai_case_is_medium_difficulty_and_fair(n):
    for seed in range(60):
        case = balanced(n, seed)
        m = case["balance"]
        assert logic.validate_case(case, list(range(1, n + 1)), fake_story()) == []
        assert balance.problems(case) == []
        # not obvious: after round 1 the culprit is suspicious but not clearly ahead,
        # and two or three people look guilty
        assert m["start_margin"] <= balance.MAX_START_MARGIN
        assert 2 <= len(m["plausible_suspects_round_1"]) <= 3
        # not too hard: with everything found and shared, the culprit clearly stands out
        assert m["end_margin"] >= balance.MIN_END_MARGIN
        # fair: three independent pieces of evidence, the case never hangs on one of them
        assert len(m["strong_sources"]) >= 3 and m["after_losing_one"] >= 2
        assert any(s.startswith("place:") for s in m["strong_sources"])
        assert any(s.startswith("player:") for s in m["strong_sources"])     # sharing matters
        # controlled misdirection: one or two red herrings, and the revelation in the middle
        assert 1 <= len(m["suspected_innocents"]) <= 2
        assert m["scene_opens"] == 2


def test_the_checks_find_what_the_plain_builder_gets_wrong():
    """Without the adjustment, the crime scene often opens only in the last round."""
    found = set()
    for seed in range(40):
        found |= set(balance.problems(generator.build_case([1, 2, 3, 4], seed, fake_story())))
    assert "too hard: the crime scene opens only in the last round" in found


def test_a_case_with_the_scene_open_from_the_start_is_too_easy():
    case = balanced(5, 3)
    case["locked"] = {k: v for k, v in case["locked"].items() if k != case["murder_location"]}
    assert any(p.startswith("too easy") for p in balance.problems(case))


@pytest.mark.parametrize("break_it, expected", [
    (lambda c: c["characters"][0].update(true_location="Nowhere"), "inconsistent"),
    (lambda c: next(x for x in c["characters"] if x["pid"] == c["murderer"]).update(
        alibi_location=c["murder_location"]), "inconsistent"),
    (lambda c: [cl.update(implicates=None, kind="neutral") for cl in c["location_clues"]
                if cl["kind"] == "alibi_broken"], "unfair"),
])
def test_contradictions_and_missing_evidence_are_found(break_it, expected):
    case = copy.deepcopy(balanced(5, 11))
    break_it(case)
    assert any(p.startswith(expected) for p in balance.problems(case))


def test_the_solution_is_complete_and_matches_the_case():
    case = balanced(5, 42)
    s = case["solution"]
    culprit = next(c for c in case["characters"] if c["pid"] == case["murderer"])
    assert s["culprit"] == culprit["pid"] and s["culprit_role"] == culprit["role"]
    assert s["motive"] == culprit["intro"] and s["scene"] == case["murder_location"]
    assert s["false_alibi"] == culprit["alibi_location"] != s["scene"]
    assert "23:15–23:45" in [e["time"] for e in s["timeline"]]
    assert s["timeline"][-1]["time"] == content.FOUND_TIME
    assert len(s["evidence"]) >= 3
    for herring in s["red_herrings"]:
        assert herring["explained_by"] and herring["points_at"] != culprit["role"]


def test_the_same_seed_gives_the_same_balanced_case():
    assert balanced(6, 99) == balanced(6, 99)


# ---------------------------------------------------------------- in the game

def ai_game(n=5, seed=8):
    g = logic.new_game("ABCD", 0)
    for i in range(1, n + 1):
        g = logic.join(g, f"P{i}", f"t{i}", 0)
    g = logic.ai_case_ready(logic.ai_case_writing(g, 0), fake_story(), 1)
    return logic.start(g, "t1", set(range(1, n + 1)), 0, seed=seed)


def test_an_ai_game_is_balanced_and_case_001_is_not():
    g = ai_game()
    assert g["story"]["source"] != "fixed" and "solution" in g["case"] and "balance" in g["case"]
    demo = logic.start(logic.join(logic.join(logic.join(logic.join(logic.new_game("ABCD", 0), "A", "t1", 0),
                                                                   "B", "t2", 0), "C", "t3", 0), "D", "t4", 0),
                       "t1", {1, 2, 3, 4}, 0, seed=8)
    assert "solution" not in demo["case"]                   # no AI story: case #001, as always


def test_nobody_sees_the_solution_before_the_result():
    g = logic.end_phase(ai_game(), "t1", {1, 2, 3, 4, 5}, 1)
    secret_bits = [g["case"]["solution"]["method"], "solution", "start_margin", "red_herrings"]
    seen = json.dumps([logic.public_view(g, {1, 2, 3, 4, 5}), logic.story_view(g)]
                      + [logic.private_view(g, f"t{i}") for i in range(1, 6)], ensure_ascii=False)
    for bit in secret_bits:
        assert bit not in seen


def test_the_result_explains_the_red_herrings_of_an_ai_case():
    g = ai_game()
    on = {1, 2, 3, 4, 5}
    while g["phase"] != "RESULT":
        g = logic.end_phase(g, "t1", on, 1)
    herrings = g["result"]["red_herrings"]
    assert 1 <= len(herrings) <= 2 and all(h["explained_by"] for h in herrings)
    html = ui.red_herrings(herrings)
    assert all(ui.h(h["points_at"]) in html for h in herrings) and "Why they looked guilty" in html


# ---------------------------------------------------------------- the test reading

def sample():
    story = ai.parse_story(json.dumps(FAKE_ANSWER))
    case = balance.build_balanced_case(ai.REVIEW_PLAYERS, ai.REVIEW_SEED, story)
    roles = [c["role"] for c in case["characters"]]
    culprit = next(c["role"] for c in case["characters"] if c["pid"] == case["murderer"])
    return story, case, roles, culprit


def review(culprit, top=None, sure_start=2, sure_end=4, plausible=None, leap=False, explained=True,
           clarity=4, suspense=4, notes=()):
    _, _, roles, _ = sample()
    others = [r for r in roles if r != culprit]
    return {"after_round_1": {"top_suspect": top or others[0], "confidence": sure_start,
                              "plausible_suspects": plausible if plausible is not None else [culprit, others[0]]},
            "after_all_rounds": {"culprit": culprit, "confidence": sure_end, "key_reasoning": "x"},
            "needs_unreasonable_leap": leap, "red_herrings_have_innocent_explanations": explained,
            "clarity": clarity, "suspense": suspense, "problems": list(notes)}


def test_the_test_player_never_sees_the_solution():
    story, case, roles, culprit = sample()
    text = ai.player_file(story, case)
    solution = balance.solution(case, story)
    assert "murderer" not in text.lower() and solution["method"] not in text
    assert f"you saw {culprit} at the {case['murder_location']}" not in text   # nobody places them at the scene
    for c in case["characters"]:
        assert c["role"] in text and story["roles"][c["role"]]["secret"] in text   # the culprit's too
    culprit_place = case["murder_location"]
    assert f"Round 2: places that can be searched from now on:\n- {culprit_place}" in text


def test_a_good_test_reading_passes():
    _, _, roles, culprit = sample()
    assert ai.judge(review(culprit), culprit, roles) == []


@pytest.mark.parametrize("change, finding", [
    (dict(wrong=True), "too hard"),
    (dict(sure_end=2), "too hard"),
    (dict(top="culprit", sure_start=5), "too easy"),
    (dict(plausible=[]), "too easy"),
    (dict(leap=True), "too hard"),
    (dict(explained=False), "unfair"),
    (dict(clarity=2), "unclear"),
    (dict(suspense=1), "dull"),
])
def test_a_test_reading_that_finds_a_problem_fails(change, finding):
    _, _, roles, culprit = sample()
    change = dict(change)
    named = next(r for r in roles if r != culprit) if change.pop("wrong", False) else culprit
    if change.get("top") == "culprit":
        change["top"] = culprit
    problems = ai.judge(review(named, **change), culprit, roles)
    assert any(p.startswith(finding) for p in problems)
    assert all(culprit not in p for p in problems)          # findings never name the culprit


@pytest.mark.parametrize("answer", [{}, {"after_round_1": "x"}, {"after_round_1": {}, "after_all_rounds": {}}])
def test_an_unusable_test_reading_is_ignored(answer):
    _, _, roles, culprit = sample()
    assert ai.judge(answer, culprit, roles) is None


def test_write_story_passes_a_case_the_test_player_could_solve():
    _, _, _, culprit = sample()
    client = SequenceClient([json.dumps(FAKE_ANSWER), json.dumps(review(culprit))])
    story = ai.write_story("fake-key", client=client)
    assert logic.validate_story(story) == [] and len(client.calls) == 2
    reading = client.calls[1]
    assert reading["messages"][0]["content"] == ai.REVIEW_SYSTEM_PROMPT and reading["temperature"] < 1


def test_a_failed_test_reading_gets_one_revision_with_the_findings():
    _, _, _, culprit = sample()
    bad = review(culprit, top=culprit, sure_start=5, notes=["The trace names its owner."])
    client = SequenceClient([json.dumps(FAKE_ANSWER), json.dumps(bad), json.dumps(FAKE_ANSWER), json.dumps(review(culprit))])
    story = ai.write_story("fake-key", client=client)
    assert logic.validate_story(story) == []
    revision = client.author_calls[1]["messages"][-1]["content"]
    assert "too easy" in revision and "The trace names its owner." in revision and culprit not in revision


def test_a_case_the_test_player_misreads_twice_is_still_played(caplog):
    """The test player is a free model too: its verdict improves a case (one revision) but does
    not throw away a case that passed every code check."""
    _, _, _, culprit = sample()
    bad = json.dumps(review(culprit, leap=True))
    client = SequenceClient([json.dumps(FAKE_ANSWER), bad, json.dumps(FAKE_ANSWER), bad])
    story = ai.write_story("fake-key", client=client)
    assert logic.validate_story(story) == [] and len(client.calls) == 4      # it was revised once
    assert "test reading found" in caplog.text


def test_a_story_from_which_no_fair_case_can_be_built_is_not_played(monkeypatch):
    def no_fair_case(*args, **kwargs):
        raise logic.Rejected("No fair case could be built.")
    monkeypatch.setattr(balance, "build_balanced_case", no_fair_case)
    client = SequenceClient([json.dumps(FAKE_ANSWER), json.dumps(FAKE_ANSWER)])
    with pytest.raises(ai.AIError, match="no fair case could be built"):
        ai.write_story("fake-key", client=client)


def test_a_broken_revision_is_not_played():
    _, _, _, culprit = sample()
    broken = copy.deepcopy(FAKE_ANSWER)
    broken["suspects"] = broken["suspects"][:3]
    client = SequenceClient([json.dumps(FAKE_ANSWER), json.dumps(review(culprit, clarity=1)), json.dumps(broken)])
    with pytest.raises(ai.AIError, match="broke the rules"):
        ai.write_story("fake-key", client=client)


@pytest.mark.parametrize("reading", ["not json at all", json.dumps({"after_round_1": {}}), None])
def test_when_the_test_reading_is_unavailable_the_code_checks_suffice(reading):
    answers = [json.dumps(FAKE_ANSWER)] + ([reading] if reading is not None else [])
    client = SequenceClient(answers)      # None: the service fails on the second request
    story = ai.write_story("fake-key", client=client)
    assert logic.validate_story(story) == []


# ---------------------------------------------------------------- the host's choice and the AI's status

def lobby_with_ready_ai_case():
    g = logic.new_game("ABCD", 0)
    for i in range(1, 6):
        g = logic.join(g, f"P{i}", f"t{i}", 0)
    return logic.ai_case_ready(logic.ai_case_writing(g, 0), fake_story(), 1)


def test_the_host_can_play_case_001_although_an_ai_case_is_ready():
    g = lobby_with_ready_ai_case()
    assert logic.start(g, "t1", {1, 2, 3, 4, 5}, 0, seed=3, use_ai=False)["story"]["source"] == "fixed"
    assert logic.start(g, "t1", {1, 2, 3, 4, 5}, 0, seed=3, use_ai=True)["story"]["source"] == "ai"


def test_only_the_host_learns_how_the_ai_case_is_doing():
    g = lobby_with_ready_ai_case()
    assert logic.ai_status(g, "t1") == "ready"
    assert logic.ai_status(g, "t2") is None and logic.ai_status(g, "nope") is None


def test_an_ai_case_that_takes_too_long_is_given_up_so_the_lobby_never_hangs():
    g = logic.new_game("ABCD", 0)
    g = logic.join(g, "P1", "t1", 0)
    g = logic.ai_case_writing(g, 100)
    assert logic.tick(g, {1}, 100 + logic.AI_WRITING_TIMEOUT)["ai_case"]["status"] == "writing"
    late = logic.tick(g, {1}, 101 + logic.AI_WRITING_TIMEOUT)
    assert late["ai_case"] == {"status": "failed", "reason": "the AI took too long"}
    assert logic.ai_case_ready(late, fake_story(), 500)["ai_case"]["status"] == "ready"   # a late case still counts


def test_an_ai_story_must_give_a_balanced_case_for_every_player_count():
    g = lobby_with_ready_ai_case()
    assert g["ai_case"]["status"] == "ready"
    for n in PLAYER_COUNTS:
        balance.build_balanced_case(list(range(1, n + 1)), n, g["ai_case"]["story"])
