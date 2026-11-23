"""Evidence mini-games: puzzles, the Python-side check, and how logic.search uses it."""

import json
import re

import pytest

import content
import logic
import minigames
from conftest import host_token, make_started, online_all, token_of

NOW = 0


def investigation(n=5, seed=7, on=True):
    """A started game with mini-games, in round 1 of the investigation. A game shows five of the
    seven kinds; with a seed that is a multiple of 7 they are the first five (code ... order)."""
    game = make_started(n=n, seed=seed)
    game = dict(game, minigames=on)
    game = logic.end_phase(game, host_token(game), online_all(game), NOW)
    assert game["phase"] == "INVESTIGATION"
    return game


def open_places(game):
    return [p["name"] for p in logic.map_view(game)["places"] if p["state"] == "open"]


def human_token(game, k=0):
    return token_of(game, game["players"][k]["pid"])


# ---------------------------------------------------------------- the puzzles

def test_every_place_gets_a_puzzle_and_all_four_kinds_appear():
    game = investigation()
    specs = minigames.specs(game)
    assert [s["location"] for s in specs] == logic.story_of(game)["locations"]
    assert {s["kind"] for s in specs} == set(minigames.KINDS)                # seven places, seven different kinds
    assert len({s["id"] for s in specs}) == len(specs)                       # unique ids
    for s in specs:
        clue = next(c for c in game["case"]["location_clues"] if c["location"] == s["location"])
        assert s["evidence_id"] == clue["id"]
        assert len(s["hints"]) == 3 and s["story"]


def test_specs_are_deterministic_for_everybody_in_the_room():
    assert minigames.specs(investigation()) == minigames.specs(investigation())


def test_kinds_rotate_with_the_case_seed():
    first = {minigames.specs(investigation(seed=s))[0]["kind"] for s in range(1, 12)}
    assert len(first) > 1


@pytest.mark.parametrize("seed", range(1, 25))
def test_the_spec_never_contains_the_answer(seed):
    game = investigation(seed=seed)
    for loc in logic.story_of(game)["locations"]:
        spec = minigames.spec(game, loc)
        solution = minigames.solve(game, loc)
        dumped = json.dumps({k: v for k, v in spec.items() if k != "hints"})
        assert "answer" not in spec and "key" not in spec and "solution" not in spec
        if spec["kind"] == "code":
            assert solution["code"] not in dumped
        if spec["kind"] == "cipher":
            plain = minigames.shift_text(spec["cipher"], -solution["shift"])
            assert plain not in dumped                      # only the shifted text is sent
            assert plain.endswith(minigames._signature(game))


def test_mini_games_off_means_no_specs():
    game = investigation(on=False)
    assert minigames.specs(game) == [] and minigames.spec(game, open_places(game)[0]) is None
    assert minigames.verify(game, open_places(game)[0], {"code": "1723"}) is False


# ---------------------------------------------------------------- solvable from the story

def lock_of(game):
    loc = place_of(game, "code")
    return loc, minigames.spec(game, loc), minigames.solve(game, loc)["code"]


def solve_from_the_note(facts, riddle):
    """Solve a lock like a player: only from what the phone shows (the note and its last line)."""
    times = {fact[0][0]: fact[1] for fact in facts}             # "A · ..." -> "21:15"

    def minutes(letter):
        hours, mins = times[letter].split(":")
        return int(hours) * 60 + int(mins)
    if " read backwards." in riddle:
        return times[riddle[0]].replace(":", "")[::-1]
    if "twelve-hour clock" in riddle:
        hours, mins = times[riddle[0]].split(":")
        return f"{int(hours) - 12:02d}{mins}"
    letters = re.findall(r"\b([ABCD])\b", riddle)
    if riddle.startswith("The minutes of"):
        a, b, c = letters
        return f"{int(times[a][3:]) + int(times[b][3:]):02d}{times[c][3:]}"
    if riddle.startswith("The minutes from"):
        a, b, c = letters
        return f"{minutes(b) - minutes(a):02d}{times[c][:2]}"
    c, a, b = letters                                           # "The hour of C – then the minutes from A to B."
    return f"{times[c][:2]}{minutes(b) - minutes(a):02d}"


@pytest.mark.parametrize("seed", range(40))
def test_the_code_can_be_worked_out_from_the_note_alone(seed):
    game = investigation(seed=seed * 7)                                   # a game with the lock
    _, spec, answer = lock_of(game)
    assert len(spec["facts"]) == 4 and [f[0][0] for f in spec["facts"]] == list("ABCD")
    assert any(f[1] == content.FOUND_TIME for f in spec["facts"])                 # the discovery is always there
    assert solve_from_the_note(spec["facts"], spec["riddle"]) == answer
    assert re.fullmatch(r"\d{4}", answer)
    assert answer not in {f[1].replace(":", "") for f in spec["facts"]}         # never just a time from the note
    assert answer not in spec["hints"][0]                                         # the first hint is a nudge


def test_the_code_changes_from_game_to_game():
    codes = {lock_of(investigation(seed=seed * 7))[2] for seed in range(60)}
    riddles = {lock_of(investigation(seed=seed * 7))[1]["riddle"].split()[1] for seed in range(60)}
    assert len(codes) >= 20 and len(riddles) >= 3


def test_the_code_of_an_ai_case_uses_its_own_evening():
    from test_case_minigames import AI_MINIGAMES, ai_story, game_with
    game = game_with(ai_story(AI_MINIGAMES), seed=3)
    loc = place_of(game, "code")
    spec = minigames.spec(game, loc)
    diary = {clock for clock, _ in AI_MINIGAMES["order"]["events"]} | {content.FOUND_TIME}
    assert {f[1] for f in spec["facts"]} <= diary
    assert solve_from_the_note(spec["facts"], spec["riddle"]) == minigames.solve(game, loc)["code"]


def test_cipher_is_a_shift_whose_signature_is_the_victim():
    game = investigation()
    loc = next(s["location"] for s in minigames.specs(game) if s["kind"] == "cipher")
    spec = minigames.spec(game, loc)
    key = minigames.solve(game, loc)["shift"]
    assert 3 <= key <= 23 and key != 13
    plain = minigames.shift_text(spec["cipher"], -key)
    assert plain.split()[-1] == "VALE"
    assert plain == "NOBODY PASSES WITHOUT ME VALE"            # case #001's own note
    assert spec["signature_length"] == 4


def test_shift_text_round_trip_and_spaces():
    assert minigames.shift_text("ABC XYZ", 3) == "DEF ABC"
    assert minigames.shift_text(minigames.shift_text("THE NOTE", 11), -11) == "THE NOTE"


def test_signature_of_an_odd_victim_name():
    game = investigation()
    game["story"] = dict(logic.story_of(game), victim_short="Dr. O'Neil-3")
    assert minigames._signature(game) == "DRONEIL"


# ---------------------------------------------------------------- verify: right and wrong

@pytest.mark.parametrize("seed", range(1, 31))
def test_the_solution_of_every_place_verifies(seed):
    game = investigation(seed=seed)
    for loc in logic.story_of(game)["locations"]:
        assert minigames.verify(game, loc, minigames.solve(game, loc)), (seed, loc)


def place_of(game, kind):
    return next(s["location"] for s in minigames.specs(game) if s["kind"] == kind)


@pytest.mark.parametrize("proof", [
    None, "1723", {}, {"code": "2347"}, {"code": "2330"}, {"code": "17230"}, {"code": 1723}, {"code": "abcd"}])
def test_wrong_codes_fail(proof):
    game = investigation()
    loc = place_of(game, "code")
    if proof == {"code": 1723} and minigames.solve(game, loc)["code"] == "1723":   # pragma: no cover
        assert minigames.verify(game, loc, proof)      # "1723" as a number is the same digits
        return
    assert not minigames.verify(game, loc, proof)


def test_scratch_needs_enough_distinct_valid_cells():
    game = investigation()
    loc = place_of(game, "scratch")
    need = -(-int(minigames.SCRATCH_NEEDED * 100) * minigames.MAX_PROOF_ITEMS // 100)
    assert minigames.verify(game, loc, {"cells": list(range(need))})
    assert not minigames.verify(game, loc, {"cells": list(range(need - 1))})
    assert not minigames.verify(game, loc, {"cells": [1] * 140})                    # duplicates
    assert not minigames.verify(game, loc, {"cells": list(range(60)) + list(range(500, 560))})
    assert not minigames.verify(game, loc, {"cells": [True] * 100})
    assert not minigames.verify(game, loc, {"cells": "everything"})
    assert not minigames.verify(game, loc, {"cells": list(range(141))})            # too many items


def test_puzzle_swaps_are_replayed_from_the_server_order():
    game = investigation()
    loc = place_of(game, "puzzle")
    good = minigames.solve(game, loc)["swaps"]
    assert minigames.verify(game, loc, {"swaps": good})
    assert not minigames.verify(game, loc, {"swaps": []})                 # the start is never solved
    assert not minigames.verify(game, loc, {"swaps": good[:-1]})
    assert not minigames.verify(game, loc, {"swaps": good + [[0, 1]]})
    assert not minigames.verify(game, loc, {"swaps": [[0, 99]]})
    assert not minigames.verify(game, loc, {"swaps": [[0]]})
    assert not minigames.verify(game, loc, {"swaps": [["0", "1"]]})
    assert not minigames.verify(game, loc, {"swaps": [[0, 1]] * (minigames.MAX_SWAPS + 1)})
    assert not minigames.verify(game, loc, {"order": list(range(9))})     # the client cannot send an order


def test_puzzle_start_is_scrambled():
    for seed in range(1, 40):
        game = investigation(seed=seed)
        for spec in minigames.specs(game):
            if spec["kind"] == "puzzle":
                start = spec["start"]
                assert sorted(start) == list(range(spec["cols"] * spec["rows"]))
                assert sum(1 for i, p in enumerate(start) if i == p) <= 1
                assert spec["cols"] * spec["rows"] in (6, 9)


def test_cipher_needs_the_exact_shift():
    game = investigation()
    loc = place_of(game, "cipher")
    key = minigames.solve(game, loc)["shift"]
    assert minigames.verify(game, loc, {"shift": key})
    assert minigames.verify(game, loc, {"shift": key + 26})
    for wrong in ({"shift": key + 1}, {"shift": str(key)}, {"shift": True}, {"shift": None}, {}):
        assert not minigames.verify(game, loc, wrong)


def test_a_proof_for_one_place_does_not_open_another():
    game = investigation()
    places = logic.story_of(game)["locations"]
    for a in places:
        for b in places:
            if a != b and minigames.assignment(game)[a][0] == minigames.assignment(game)[b][0] != "scratch":
                if minigames.solve(game, a) != minigames.solve(game, b):
                    assert not minigames.verify(game, b, minigames.solve(game, a))
    assert not minigames.verify(game, "Beach", minigames.solve(game, places[0]))     # not in this case


# ---------------------------------------------------------------- contextual feedback and hints

def test_feedback_is_helpful_but_never_the_answer():
    game = investigation()
    loc = place_of(game, "code")
    answer = minigames.solve(game, loc)["code"]
    assert "one time from the note" in minigames.feedback(game, loc, {"code": content.FOUND_TIME.replace(":", "")})
    assert "four digits" in minigames.feedback(game, loc, {"code": "12"})
    assert "halfway" in minigames.feedback(game, loc, {"code": answer[:2] + "00"})
    for code in ("0000", "2347", answer[:2] + "00"):
        assert answer not in minigames.feedback(game, loc, {"code": code})
    cip = place_of(game, "cipher")
    note = minigames.feedback(game, cip, {"shift": 0})
    assert "signature reads" in note and "VALE" not in note


def test_first_misplaced_names_a_real_move():
    game = investigation()
    spec = minigames.spec(game, place_of(game, "puzzle"))
    slot, target = minigames.first_misplaced(spec, [])
    order = spec["start"]
    assert order[slot - 1] == target - 1 and slot != target
    assert minigames.first_misplaced(spec, minigames.solve(game, spec["location"])["swaps"]) is None
    assert minigames.first_misplaced(spec, [["x"]]) is not None          # bad input: falls back to the start


# ---------------------------------------------------------------- logic.search with mini-games

def test_search_is_refused_without_a_valid_proof():
    game = investigation()
    loc = open_places(game)[0]
    token = human_token(game)
    for proof in (None, {}, {"code": "0000"}, {"swaps": []}, {"shift": -1}):
        with pytest.raises(logic.Rejected, match="still sealed"):
            logic.search(game, token, loc, NOW, proof=proof)
    assert game["searched"] == [] and game["log"] == []


def test_a_solved_puzzle_hands_out_the_evidence_exactly_once():
    game = investigation()
    loc = open_places(game)[0]
    proof = minigames.solve(game, loc)
    after = logic.search(game, human_token(game, 0), loc, NOW, proof=proof)
    entries = [e for e in after["log"] if e["kind"] == "search" and e["location"] == loc]
    clue = next(c for c in game["case"]["location_clues"] if c["location"] == loc)
    assert len(entries) == 1 and entries[0]["clue_id"] == clue["id"]
    with pytest.raises(logic.Rejected):                          # the same proof again, another player
        logic.search(after, human_token(after, 1), loc, NOW, proof=proof)
    with pytest.raises(logic.Rejected, match="already used"):    # the same player, another place
        other = open_places(after)[0]
        logic.search(after, human_token(after, 0), other, NOW, proof=minigames.solve(after, other))


def test_locked_places_stay_locked_even_with_a_proof():
    game = investigation()
    locked = next(p["name"] for p in logic.map_view(game)["places"] if p["state"] == "locked")
    with pytest.raises(logic.Rejected, match="locked"):
        logic.search(game, human_token(game), locked, NOW, proof=minigames.solve(game, locked))


def test_rooms_without_mini_games_search_as_before():
    game = investigation(on=False)
    loc = open_places(game)[0]
    after = logic.search(game, human_token(game), loc, NOW)
    assert loc in after["searched"]


def test_new_rooms_default_to_no_mini_games():
    assert logic.new_game("ABCD", 0)["minigames"] is False
    assert logic.new_game("ABCD", 0, minigames=True)["minigames"] is True


# ---------------------------------------------------------------- the private view

def test_private_view_lists_the_puzzles_only_during_the_investigation():
    game = investigation()
    view = logic.private_view(game, human_token(game))
    assert set(view["puzzles"]) == set(logic.story_of(game)["locations"])
    answers = [minigames.solve(game, loc) for loc in view["puzzles"]]
    dumped = json.dumps({loc: {k: v for k, v in s.items() if k != "hints"} for loc, s in view["puzzles"].items()})
    for answer in answers:
        if "code" in answer:
            assert answer["code"] not in dumped
    lobby = logic.new_game("ABCD", 0, minigames=True)
    lobby = logic.join(lobby, "Ana", "tok-a", 0)
    assert logic.private_view(lobby, "tok-a")["puzzles"] == {}
    assert "puzzles" not in logic.public_view(game, online_all(game))


# ---------------------------------------------------------------- demo bots

def bot_game():
    game = logic.new_game("ABCD", 0, minigames=True)
    game = logic.join(game, "Human", "tok-human", 0)
    for _ in range(4):
        game = logic.add_bot(game, "tok-human", 0)
    online = {p["pid"] for p in game["players"]}
    game = logic.start(game, "tok-human", online, 0, seed=logic.DEMO_SEED)
    return logic.end_phase(game, "tok-human", online, 0)


def test_bots_wait_while_a_human_is_solving():
    game = bot_game()
    later = logic.bot_moves(game, 600)
    assert later["acted"] == [] and later["log"] == game["log"]
    loc = open_places(game)[0]
    game = logic.search(game, "tok-human", loc, 1, proof=minigames.solve(game, loc))
    bots = [p["pid"] for p in game["players"] if p.get("bot")]
    after = logic.bot_moves(game, 600)                            # everybody in person has moved ...
    assert not any(pid in after["acted"] for pid in bots)
    after = logic.bot_moves(after, 600 + logic.BOT_AFTER_HUMANS)  # ... then the first bot moves
    assert sum(pid in after["acted"] for pid in bots) == 1
    for t in range(600, 660):
        after = logic.bot_moves(after, t)
    assert all(pid in after["acted"] for pid in bots)            # one after another, without proofs
