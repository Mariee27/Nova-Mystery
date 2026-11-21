"""Mini-games that fit the case: five kinds for the five places (no game twice), the words
of each game from the case (case #001's own, or the AI's after the checks, else the fallback),
and the new kind "order the evening"."""
import copy
import json
import xml.etree.ElementTree as ET

import pytest

import ai
import content
import exhibits
import logic
import minigames
from test_ai_cases import FAKE_ANSWER, FAKE_ROLES

AI_MINIGAMES = {
    "code": {"exhibit": "Moreau's jewellery case",
             "story": "A velvet jewellery case on a shelf in the {location}, with a brass keypad. A note is tucked inside:"},
    "cipher": {"exhibit": "Moreau's coded postcard",
               "story": "A postcard pinned up in the {location}. Its letters are shifted along the alphabet.",
               "message": "THE GALA ENDS AT MIDNIGHT"},
    "scratch": {"exhibit": "A dusty receipt", "story": "A receipt under a table in the {location}, grey with dust.",
                "style": "printout", "title": "Gala bar", "lines": ["2x Champagne", "1x Espresso", "Paid in cash"]},
    "puzzle": {"exhibit": "The torn camera still", "story": "The night camera of the {location}, torn into {pieces} pieces.",
               "caption": "Door left open"},
    "order": {"exhibit": "{victim}'s gala evening", "story": "The gala programme from the {location}, torn apart.",
              "events": [["20:30", "{victim} gives the welcome speech"], ["21:10", "The string quartet starts"],
                         ["22:00", "{victim} leaves the dinner early"], ["23:00", "The last taxi drives off"]]},
}


def game_with(story=None, seed=11, n=5):
    g = logic.new_game("ABCD", 0, minigames=True)
    for i in range(1, n + 1):
        g = logic.join(g, f"P{i}", f"t{i}", 0)
    if story is not None:
        g = logic.ai_case_ready(logic.ai_case_writing(g, 0), story, 0)
    g = logic.start(g, "t1", set(range(1, n + 1)), 0, seed=seed)
    return logic.end_phase(g, "t1", set(range(1, n + 1)), 1)


def ai_story(minigames_raw=None):
    answer = copy.deepcopy(FAKE_ANSWER)
    if minigames_raw is not None:
        answer["minigames"] = minigames_raw
    return ai.parse_story(json.dumps(answer))


# ---------------------------------------------------------------- no game twice

@pytest.mark.parametrize("n", [4, 5, 6])
def test_the_five_places_always_have_five_different_games(n):
    for seed in range(40):
        for story in (None, ai_story(AI_MINIGAMES)):
            kinds = [s["kind"] for s in minigames.specs(game_with(story, seed=seed, n=n))]
            assert len(kinds) == 5 and sorted(kinds) == sorted(minigames.KINDS)


def test_which_place_gets_which_game_changes_from_game_to_game():
    seen = {tuple(s["kind"] for s in minigames.specs(game_with(seed=seed))) for seed in range(20)}
    assert len(seen) == 5


@pytest.mark.parametrize("seed", range(12))
def test_every_game_of_a_case_can_be_solved_and_is_not_solved_by_rubbish(seed):
    g = game_with(ai_story(AI_MINIGAMES), seed=seed)
    for s in minigames.specs(g):
        assert minigames.verify(g, s["location"], minigames.solve(g, s["location"]))
        for wrong in ({}, {"order": [0, 1, 2, 3]} if s["kind"] != "order" else {"order": [9]}, None):
            assert not minigames.verify(g, s["location"], wrong)


# ---------------------------------------------------------------- the words come from the case

def test_case_001_has_its_own_mini_games():
    g = game_with()
    by_kind = {s["kind"]: s for s in minigames.specs(g)}
    assert by_kind["code"]["exhibit"] == "Vale's grade cabinet"
    assert by_kind["scratch"]["exhibit"] == "Vale's phone" and "No second chances." in by_kind["scratch"]["image"]
    plain = minigames.shift_text(by_kind["cipher"]["cipher"], -minigames.solve(g, by_kind["cipher"]["location"])["shift"])
    assert plain == "NOBODY PASSES WITHOUT ME VALE"
    assert minigames.clean_content(content.CASE_MINIGAMES, content.DEFAULT_STORY) == content.CASE_MINIGAMES
    for kind, s in by_kind.items():
        assert s["location"] in s["story"] and "{" not in s["story"]


def test_an_ai_case_brings_its_own_mini_games():
    story = ai_story(AI_MINIGAMES)
    assert set(story["minigames"]) == set(minigames.KINDS)
    g = game_with(story)
    by_kind = {s["kind"]: s for s in minigames.specs(g)}
    victim = story["victim_short"]
    assert by_kind["code"]["exhibit"] == "Moreau's jewellery case"
    assert "Champagne" in by_kind["scratch"]["image"] and "GALA BAR" in by_kind["scratch"]["image"]
    assert "DOOR LEFT OPEN" in by_kind["puzzle"]["image"]
    assert by_kind["order"]["exhibit"] == f"{victim}'s gala evening"
    assert any(f"{victim} gives the welcome speech" == i["text"] for i in by_kind["order"]["items"])
    plain = minigames.shift_text(by_kind["cipher"]["cipher"], -minigames.solve(g, by_kind["cipher"]["location"])["shift"])
    assert plain.startswith("THE GALA ENDS AT MIDNIGHT ")


def test_a_bad_piece_falls_back_and_the_rest_is_kept():
    raw = copy.deepcopy(AI_MINIGAMES)
    raw["scratch"]["lines"] = [f"{FAKE_ROLES[0]} paid for it"]          # names a suspect
    story = ai_story(raw)
    assert "scratch" not in story["minigames"] and "code" in story["minigames"]
    by_kind = {s["kind"]: s for s in minigames.specs(game_with(story))}
    assert by_kind["scratch"]["exhibit"] == content.MINIGAME_FALLBACK["scratch"]["exhibit"]
    assert by_kind["code"]["exhibit"] == "Moreau's jewellery case"


def test_an_ai_case_without_mini_games_uses_the_fallback_everywhere():
    story = ai_story()
    assert story["minigames"] == {}
    g = game_with(story)
    for s in minigames.specs(g):
        assert s["exhibit"] == minigames._fill(content.MINIGAME_FALLBACK[s["kind"]]["exhibit"], s["location"],
                                               story["victim_short"])
        assert "Vale" not in s["story"] + s.get("image", "")                 # never case #001's victim
        assert minigames.verify(g, s["location"], minigames.solve(g, s["location"]))


def test_old_games_whose_story_has_no_mini_games_still_work():
    g = game_with()
    g["story"] = {k: v for k, v in content.DEFAULT_STORY.items() if k != "minigames"}
    for s in minigames.specs(g):
        assert minigames.verify(g, s["location"], minigames.solve(g, s["location"]))


def change(kind, **values):
    raw = copy.deepcopy(AI_MINIGAMES[kind])
    raw.update(values)
    return raw


BAD_PIECES = [
    ("code", change("code", story="A box with a keypad.")),                                  # no {location}
    ("code", change("code", exhibit="x" * 41)),
    ("code", change("code", story="The murder weapon lies in the {location}.")),
    ("code", change("code", story=f"{FAKE_ROLES[1]} hid a box in the {{location}}.")),
    ("code", "not a dict"),
    ("cipher", change("cipher", message="HI")),
    ("cipher", change("cipher", message="ONLYONEWORDHERE")),
    ("scratch", change("scratch", style="poster")),
    ("scratch", change("scratch", lines=["x" * 31, "ok"])),
    ("scratch", change("scratch", lines=["only one line"])),
    ("scratch", change("scratch", lines="not a list")),
    ("scratch", change("scratch", lines=["<script>", "ok"])),
    ("puzzle", change("puzzle", caption="x" * 27)),
    ("order", change("order", events=[["21:00", "a"], ["20:00", "b"], ["22:00", "c"], ["23:00", "d"]])),   # unsorted
    ("order", change("order", events=[["21:00", "a"], ["21:05", "b"], ["22:00", "c"], ["23:00", "d"]])),   # too close
    ("order", change("order", events=[["21:00", "a"], ["22:00", "b"], ["23:00", "c"], ["23:45", "d"]])),   # after death
    ("order", change("order", events=[["21:00", "a"], ["22:00", "b"], ["23:00", "c"]])),                   # three
    ("order", change("order", events=[["9 pm", "a"], ["22:00", "b"], ["22:30", "c"], ["23:00", "d"]])),
]


@pytest.mark.parametrize("kind, raw", BAD_PIECES)
def test_a_piece_that_breaks_a_rule_is_refused(kind, raw):
    assert minigames.clean_piece(kind, raw, ai_story()) is None


@pytest.mark.parametrize("kind", minigames.KINDS)
def test_every_good_ai_piece_is_accepted(kind):
    assert minigames.clean_piece(kind, AI_MINIGAMES[kind], ai_story()) is not None


def test_clean_content_survives_rubbish():
    for rubbish in (None, [], "text", {"code": None, "order": {"events": "x"}}):
        assert minigames.clean_content(rubbish, ai_story()) == {}


# ---------------------------------------------------------------- the pictures

@pytest.mark.parametrize("style", exhibits.STYLES)
@pytest.mark.parametrize("place", ["Library", "Beach", "Santander Hall"])
def test_every_document_is_a_valid_picture_and_escapes_its_words(style, place):
    svg = exhibits.document(style, "Head & <b>", ["Line <one> & two", "it's \"here\""], place)
    root = ET.fromstring(svg)
    assert root.get("viewBox") == "0 0 400 500"
    assert "<b>" not in svg and "<one>" not in svg and "&lt;one&gt;" in svg


@pytest.mark.parametrize("place", list(content.PLACES))
def test_the_camera_still_shows_the_place_with_the_camera_overlay(place):
    svg = exhibits.camera_still(place, 3, "23:21:40", "Motion <detected>")
    ET.fromstring(svg)
    assert "CAM 03" in svg and place.upper() in svg and "23:21:40" in svg and "MOTION &lt;DETECTED&gt;" in svg


# ---------------------------------------------------------------- order the evening

def test_the_diary_is_shuffled_and_checked_on_the_server():
    g = game_with(seed=3)
    s = next(s for s in minigames.specs(g) if s["kind"] == "order")
    assert len(s["items"]) == 4 and [i["letter"] for i in s["items"]] == ["A", "B", "C", "D"]
    assert set(s["items"][0]) == {"letter", "when", "text"}                     # no order index is sent
    answer = minigames.solve(g, s["location"])["order"]
    assert answer != [0, 1, 2, 3]                                               # never already in order
    assert minigames.verify(g, s["location"], {"order": answer})
    wrong = list(reversed(answer))
    assert not minigames.verify(g, s["location"], {"order": wrong})
    assert "entries are in the right place" in minigames.feedback(g, s["location"], {"order": wrong})
    assert "Tap every entry once" in minigames.feedback(g, s["location"], {"order": [0, 0, 1]})
    assert s["hints"][-1] == "The right order: " + ", ".join("ABCD"[i] for i in answer) + "."
    assert len({i["when"] for i in s["items"]}) == 4


def test_the_diary_shows_plain_24_hour_times():
    g = game_with(seed=4)
    s = next(s for s in minigames.specs(g) if s["kind"] == "order")
    assert sorted(i["when"] for i in s["items"]) == [e[0] for e in content.CASE_MINIGAMES["order"]["events"]]
