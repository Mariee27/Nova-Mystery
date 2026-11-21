"""The pictures of the evidence puzzles: five motifs for the jigsaw and five for rub-to-reveal.
Only what a puzzle shows changes; how it is solved, checked and rewarded stays the same."""
import hashlib
import re
import xml.etree.ElementTree as ET

import pytest

import logic
import minigames
from test_ai_cases import fake_story

SIZES = {"puzzle": ("0 0 300 300", 1.0), "scratch": ("0 0 400 500", 0.8)}   # viewBox, width : height


def game_with(motifs=None, story=None, seed=11, n=5):
    g = logic.new_game("ABCD", 0, minigames=True)
    for i in range(1, n + 1):
        g = logic.join(g, f"P{i}", f"t{i}", 0)
    if story is not None:
        g = logic.ai_case_ready(logic.ai_case_writing(g, 0), story, 0)
    g = logic.start(g, "t1", set(range(1, n + 1)), 0, seed=seed)
    g = logic.end_phase(g, "t1", set(range(1, n + 1)), 1)
    if motifs is not None:
        g["motifs"] = motifs
    return g


def places_of(game, kind):
    return [s["location"] for s in minigames.specs(game) if s["kind"] == kind]


# ---------------------------------------------------------------- the asset library

@pytest.mark.parametrize("kind", ["puzzle", "scratch"])
def test_five_distinct_valid_pictures_per_kind(kind):
    options = minigames.MOTIFS[kind]
    assert len(options) == 5 and len({m["id"] for m in options}) == 5
    hashes = set()
    for look in options:
        path = minigames.ASSETS / look["file"]
        text = path.read_text(encoding="utf-8")
        hashes.add(hashlib.sha256(text.encode()).hexdigest())
        root = ET.fromstring(text)                                       # a well-formed SVG file
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert root.get("viewBox") == SIZES[kind][0]                     # its own fixed shape
        assert not re.search(r'(href|src)="(https?:|//)', text)          # nothing loaded from elsewhere
        slots = set(re.findall(r'data-slot="([a-z_]+)"', text))
        assert set(look["slots"]) <= slots, look["id"]                   # every word has its place
    assert len(hashes) == 5                                              # five different pictures


def test_words_are_filled_in_and_escaped():
    svg = minigames.picture("puzzles/letter.svg", victim="Dear <b>X</b> & Co,", place="Library")
    assert "Dear &lt;b&gt;X&lt;/b&gt; &amp; Co," in svg and ">Library<" in svg
    assert "<b>" not in svg
    ET.fromstring(svg)                                                   # still a valid picture


# ---------------------------------------------------------------- every motif works

@pytest.mark.parametrize("index", range(5))
def test_every_jigsaw_motif_is_shown_and_solvable(index):
    g = game_with({"puzzle": index, "scratch": 0})
    for variant, place in enumerate(places_of(g, "puzzle")):
        spec = minigames.spec(g, place)
        look = minigames.MOTIFS["puzzle"][(index + variant) % 5]
        assert spec["motif"] == look["id"] and spec["exhibit"] == look["exhibit"]
        ET.fromstring(spec["image"])
        assert place.upper() in spec["image"] or place in spec["image"]  # the place of this case
        assert len(spec["hints"]) == 3 and spec["hints"][-1] == minigames.PUZZLE_HINT_MOVE
        assert minigames.verify(g, place, minigames.solve(g, place))
        assert not minigames.verify(g, place, {"swaps": []})


@pytest.mark.parametrize("index", range(5))
def test_every_rub_to_reveal_motif_is_shown_and_can_be_revealed(index):
    g = game_with({"puzzle": 0, "scratch": index})
    for variant, place in enumerate(places_of(g, "scratch")):
        spec = minigames.spec(g, place)
        look = minigames.MOTIFS["scratch"][(index + variant) % 5]
        assert spec["motif"] == look["id"] and spec["cover"] == look["cover"]
        ET.fromstring(spec["image"])
        assert minigames.verify(g, place, minigames.solve(g, place))
        assert not minigames.verify(g, place, {"cells": [0, 1, 2]})


def test_the_reward_does_not_depend_on_the_picture():
    found = set()
    for index in range(5):
        g = game_with({"puzzle": index, "scratch": index})
        open_places = [p for p in places_of(g, "puzzle") + places_of(g, "scratch") if logic.locked_until(g, p) is None]
        for place in open_places:
            after = logic.search(g, "t1", place, 2, proof=minigames.solve(g, place))
            found.add((place, after["log"][-1]["text"]))
    assert open_places and len(found) == len(open_places)                # same clue, whatever the picture


# ---------------------------------------------------------------- chosen once per game

def test_the_motifs_are_chosen_at_the_start_and_kept_in_the_game():
    g = game_with(seed=5)
    assert g["motifs"] == minigames.choose_motifs(5)
    first = [minigames.spec(g, p)["image"] for p in places_of(g, "puzzle")]
    again = logic.tick(g, {1, 2, 3, 4, 5}, 2)                            # time passes, screens redraw
    assert [minigames.spec(again, p)["image"] for p in places_of(again, "puzzle")] == first


def test_different_games_get_different_motifs():
    seen = {"puzzle": set(), "scratch": set()}
    for seed in range(60):
        for kind, index in minigames.choose_motifs(seed).items():
            seen[kind].add(index)
    assert seen == {"puzzle": set(range(5)), "scratch": set(range(5))}


def test_two_places_of_the_same_kind_never_show_the_same_picture():
    for seed in range(40):
        g = game_with(seed=seed)
        for kind in ("puzzle", "scratch"):
            shown = [minigames.spec(g, p)["motif"] for p in places_of(g, kind)]
            assert len(shown) == len(set(shown))


def test_rehearsal_mode_and_old_games_keep_the_first_pictures():
    g = logic.new_game("ABCD", 0, minigames=True)
    for i in range(1, 6):
        g = logic.join(g, f"P{i}", f"t{i}", 0)
    g = logic.start(g, "t1", {1, 2, 3, 4, 5}, 0, seed=logic.DEMO_SEED, fixed_case=True)
    assert g["motifs"] is None
    g = logic.end_phase(g, "t1", {1, 2, 3, 4, 5}, 1)
    assert {minigames.spec(g, p)["motif"] for p in places_of(g, "puzzle")} == {"camera"}
    assert {minigames.spec(g, p)["motif"] for p in places_of(g, "scratch")} <= {"note"}
    del g["motifs"]                                                      # a game saved before motifs existed
    assert {minigames.spec(g, p)["motif"] for p in places_of(g, "puzzle")} == {"camera"}


def test_ai_cases_get_their_own_words_in_every_picture():
    story = fake_story()
    for index in range(5):
        g = game_with({"puzzle": index, "scratch": index}, story=story)
        for spec in minigames.specs(g):
            if spec["kind"] in ("puzzle", "scratch"):
                assert "Vale" not in spec["image"] and "VALE" not in spec["image"]   # never case #001's victim
                assert story["victim_short"] in spec["image"] or spec["location"].upper() in spec["image"] \
                    or spec["location"] in spec["image"]
