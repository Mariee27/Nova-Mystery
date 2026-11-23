"""The two extra mini-games (minigames_extra.py) and the two new places, Canteen and Garage."""
import copy
import xml.etree.ElementTree as ET

import pytest

import content
import exhibits
import logic
import minigames
import minigames_extra as extra
from test_case_minigames import ai_story, game_with

KINDS7 = ("code", "scratch", "puzzle", "cipher", "order", "spot", "find")


def game_showing(kind, variant):
    """A game in round 1 whose place of this kind shows this variant: (game, place)."""
    for seed in range(400):
        game = game_with(seed=seed)
        for spec in minigames.specs(game):
            if (spec["kind"] == kind and extra.variant_of(game, spec["location"], kind) == variant
                    and logic.locked_until(game, spec["location"]) is None):
                return game, spec["location"]
    raise AssertionError(f"no game shows {kind} variant {variant}")


# ---------------------------------------------------------------- registered, the old five unchanged

def test_seven_kinds_and_the_first_five_are_the_old_ones():
    assert minigames.KINDS == KINDS7
    assert [minigames.KIND_INFO[k]["name"] for k in KINDS7] == [
        "Crack the code", "Rub to reveal", "Reassemble the still", "Decode the note", "Order the evening",
        "Spot the difference", "Find the object"]
    assert extra.MIN_SECONDS == {"spot": 5, "find": 3}         # (conftest empties minigames.MIN_SECONDS for the tests)


def test_both_new_games_come_up_in_games_and_never_twice_in_one():
    seen = set()
    for seed in range(30):
        kinds = [s["kind"] for s in minigames.specs(game_with(seed=seed))]
        assert len(kinds) == len(set(kinds)) == 5
        seen |= set(kinds)
    assert seen == set(KINDS7)


# ---------------------------------------------------------------- spot the difference

@pytest.mark.parametrize("variant", range(5))
def test_every_spot_the_difference_variant_works(variant):
    game, place = game_showing("spot", variant)
    spec = minigames.spec(game, place)
    look = extra.SPOT[variant]
    assert spec["name"] == "Spot the difference" and len(spec["hints"]) == 3 and place in spec["story"]
    assert 3 <= len(spec["spots"]) <= 4 and spec["left"] != spec["right"]
    ET.fromstring(spec["left"]), ET.fromstring(spec["right"])                  # both are valid pictures
    assert spec["left"] == exhibits._asset(f"puzzles/{look['scene']}.svg")
    proof = minigames.solve(game, place)
    assert minigames.verify(game, place, proof)
    assert not minigames.verify(game, place, {"taps": proof["taps"][:-1]})     # one change not found
    misses = [[5, 5]] * (extra.SPARE_TAPS + 1)
    assert not minigames.verify(game, place, {"taps": proof["taps"] + misses})  # tapping everywhere
    assert "of" in minigames.feedback(game, place, {"taps": proof["taps"][:1]})
    after = logic.search(game, "t1", place, 2, proof=proof)                    # the reward as always
    assert place in after["searched"]


def test_the_five_spot_variants_are_five_different_scenes():
    assert len(extra.SPOT) == 5 and len({look["scene"] for look in extra.SPOT}) == 5


# ---------------------------------------------------------------- find the object

@pytest.mark.parametrize("variant", range(5))
def test_every_find_the_object_variant_works(variant):
    game, place = game_showing("find", variant)
    spec = minigames.spec(game, place)
    look = extra.FIND[variant]
    assert spec["name"] == "Find the object" and len(spec["hints"]) == 3 and place in spec["story"]
    ET.fromstring(spec["image"])
    assert len(spec["objects"]) == 5 and spec["ask"].lower().endswith(look["target"])
    proof = minigames.solve(game, place)
    assert minigames.verify(game, place, proof)
    for name, x, y, _ in look["objects"]:
        if name != look["target"]:
            assert not minigames.verify(game, place, {"tap": [x, y]})          # a distractor is not it
    assert not minigames.verify(game, place, {"tap": [1, 1]})
    after = logic.search(game, "t1", place, 2, proof=proof)
    assert place in after["searched"]


def test_find_objects_lie_far_enough_apart_to_tell_them_apart():
    for look in extra.FIND:
        spots = [(x, y) for _, x, y, _ in look["objects"]]
        for i, (x1, y1) in enumerate(spots):
            for x2, y2 in spots[i + 1:]:
                assert ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5 >= 2 * extra.FIND_RADIUS


# ---------------------------------------------------------------- variants: random per game, stable

def test_a_variant_is_stable_for_a_game_and_changes_between_games():
    game, place = game_showing("spot", 2)
    assert {extra.variant_of(game, place, "spot") for _ in range(10)} == {2}
    assert minigames.spec(game, place) == minigames.spec(copy.deepcopy(game), place)    # every rerun, every phone
    variants = {extra.variant_of(game_with(seed=s), "Horizon Hall", "spot") for s in range(40)}
    assert variants == set(range(5))          # a place without a picture of its own: any photo


@pytest.mark.parametrize("kind", ["spot", "find"])
def test_a_place_with_its_own_picture_shows_itself(kind):
    looks = extra.SPOT if kind == "spot" else extra.FIND
    for place, scene in extra.PICTURE_OF.items():
        for seed in range(10):
            look = looks[extra.variant_of(game_with(seed=seed), place, kind)]
            if any(other["scene"] == scene for other in looks):
                assert look["scene"] == scene
    game, place = game_showing(kind, 0)
    story = minigames.spec(game, place)["story"]
    if looks[0]["scene"] == extra.PICTURE_OF.get(place):
        assert "this room" in story
    else:
        assert "took of" in story             # a photo from somewhere else says where it was taken


@pytest.mark.parametrize("proof", [None, {}, {"taps": "x"}, {"taps": [[1]]}, {"taps": [[-5, 999]]},
                                   {"taps": [[True, 1]]}, {"tap": None}, {"tap": [1, 2, 3]}, {"tap": "a"}])
def test_rubbish_never_solves_or_crashes_the_new_games(proof):
    for kind in ("spot", "find"):
        game, place = game_showing(kind, 0)
        assert minigames.verify(game, place, proof) is False
        assert isinstance(minigames.feedback(game, place, proof), str)


# ---------------------------------------------------------------- the new places

def test_the_canteen_and_the_garage_are_places_with_their_own_camera_picture():
    for place, picture in (("Canteen", "canteen"), ("Garage", "garage")):
        assert place in content.PLACES and place not in content.OPEN_AIR
        assert exhibits.still_picture(place) == picture
        svg = exhibits.camera_still(place, 3, "23:21:40", "Motion detected")
        ET.fromstring(svg)
        assert place.upper() in svg


def test_an_ai_case_at_the_canteen_and_the_garage_can_be_searched():
    story = ai_story()
    old = story["locations"][:2]
    rename = dict(zip(old, ["Canteen", "Garage"]))
    story["locations"] = [rename.get(p, p) for p in story["locations"]]
    for key in ("location_flavor", "location_icons", "neutral_location_clues"):
        story[key] = {rename.get(p, p): v for p, v in story[key].items()}
    story["location_icons"].update({p: content.PLACES[p]["icon"] for p in ("Canteen", "Garage")})
    assert logic.validate_story(story) == []
    for seed in range(6):
        game = game_with(story, seed=seed)
        for place in ("Canteen", "Garage"):
            if logic.locked_until(game, place) is None:
                after = logic.search(game, "t1", place, 2, proof=minigames.solve(game, place))
                assert place in after["searched"]


def test_case_001_still_plays_its_own_five_places():
    assert content.LOCATIONS == ["Santander Hall", "Library", "Horizon Hall", "Auditorium", "Main Deck"]
