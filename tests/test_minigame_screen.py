"""The evidence mini-games on the phone, through app.py with the Streamlit stand-in."""

import time

import db
import logic
import minigames
import ui
from test_app_smoke import HOST_SKIP, Browser, game_db, host_room, tap  # noqa: F401  (game_db is a fixture)


def first_round(game_db):
    """A room (you + 4 other players) in round 1 of the investigation, case #001."""
    phone = host_room()
    code = phone.st.query_params["room"]
    phone.run(press=["Start game"], **{"Which case?": "rehearsal"})
    phone.run(press=[HOST_SKIP])
    conn = db.connect(game_db)
    assert db.load(conn, code)["phase"] == "INVESTIGATION"
    return phone, code, conn


def open_puzzle(phone, conn, code, kind=None):
    """Open the sealed exhibit of a place that can be searched now (of the given kind, if any).
    If that kind's place is still locked, the host ends rounds until it opens."""
    def candidates(game):
        return [s["location"] for s in minigames.specs(game) if kind in (None, s["kind"])
                and logic.locked_until(game, s["location"]) is None and s["location"] not in game["searched"]]
    game = db.load(conn, code)
    if kind and kind not in {s["kind"] for s in minigames.specs(game)}:
        # A game shows five of the seven kinds: give this room a seed whose five include this one.
        k = minigames.KINDS.index(kind)
        seed = game["case"]["seed"] - game["case"]["seed"] % len(minigames.KINDS) + k
        game = db.apply(conn, code, lambda g: {**g, "case": {**g["case"], "seed": seed}})
    while not candidates(game):
        phone.run(press=[HOST_SKIP])
        game = db.load(conn, code)
    place = candidates(game)[0]
    tap(phone, step="search", place=place)
    page = phone.run(press=[f"Search {place}"])
    return place, page


def last_data(phone):
    return [d for name, _, d in phone.st.mounted if name == "nova_minigame"][-1]


def test_the_place_card_shows_the_seal(game_db):
    phone, code, conn = first_round(game_db)
    game = db.load(conn, code)
    place = next(s["location"] for s in minigames.specs(game) if logic.locked_until(game, s["location"]) is None)
    page = tap(phone, step="search", place=place)
    assert "Sealed exhibit #" in page
    conn.close()


def test_wrong_answer_unlocks_nothing_and_hints_come_one_by_one(game_db):
    phone, code, conn = first_round(game_db)
    place, page = open_puzzle(phone, conn, code, "code")
    assert "Crack the code" in page and "Evidence unlocked" in page
    data = last_data(phone)
    assert data["kind"] == "code" and "hints" not in data and data["state"]["seq"] == 0
    assert minigames.solve(db.load(conn, code), place)["code"] not in str(data)

    page = phone.run(component={"submit": {"code": "2347"}})
    assert place not in db.load(conn, code)["searched"]            # no evidence for a wrong code
    data = last_data(phone)
    assert data["state"]["seq"] == 1 and "one time from the note" in data["state"]["note"]

    hints = minigames.spec(db.load(conn, code), place)["hints"]
    page = phone.run(press=["💡 Hint 1 of 3"])
    assert "Hint 1" in page and ui.h(hints[0]) in page and "Hint 2</b>" not in page
    page = phone.run(press=["💡 Hint 2 of 3"])
    assert "Hint 2" in page and "Hint 3</b>" not in page
    page = phone.run(press=["💡 Hint 3 of 3"])
    assert "Hint 3" in page and ui.h(hints[2]) in page
    conn.close()


def test_solving_unlocks_the_evidence_with_a_reward_and_continue(game_db):
    phone, code, conn = first_round(game_db)
    place, _ = open_puzzle(phone, conn, code, "cipher")
    proof = minigames.solve(db.load(conn, code), place)
    page = phone.run(component={"submit": proof})
    game = db.load(conn, code)
    entries = [e for e in game["log"] if e["kind"] == "search" and e["location"] == place]
    assert len(entries) == 1
    assert "Access granted" in page and "New evidence discovered" in page
    assert "Vale&#x27;s coded note" in page and entries[0]["text"] in page      # case #001's own exhibit
    assert any(name == "nova_chime" for name, _, _ in phone.st.mounted)      # optional sound, once
    page = phone.run()                                                       # the reward stays …
    assert "Access granted" in page and 'class="mg-reward celebrate"' not in page   # … calm now
    phone.run(press=["Continue ▸"])
    assert "reward" not in phone.st.session_state
    page = phone.run(component={"submit": proof})                           # replaying the proof
    assert len([e for e in db.load(conn, code)["log"] if e.get("location") == place]) == 1
    conn.close()


def test_the_reward_survives_the_end_of_the_round(game_db):
    phone, code, conn = first_round(game_db)
    place, _ = open_puzzle(phone, conn, code)
    phone.run(component={"submit": minigames.solve(db.load(conn, code), place)})
    phone.run(press=[HOST_SKIP])                                    # round 2 starts
    assert db.load(conn, code)["round"] == 2
    page = phone.run()
    assert "Access granted" in page and "Your move.</div>" not in page
    page = phone.run(press=["Continue ▸"])
    page = phone.run()
    assert "Your move.</div>" in page
    conn.close()


def test_puzzle_progress_survives_reruns(game_db):
    phone, code, conn = first_round(game_db)
    place, _ = open_puzzle(phone, conn, code, "puzzle")
    phone.run(component={"progress": [[0, 1], [2, 3]]})
    phone.run()
    assert last_data(phone)["state"]["swaps"] == [[0, 1], [2, 3]]
    page = phone.run(press=["💡 Hint 1 of 3"])
    page = phone.run(press=["💡 Hint 2 of 3"])
    page = phone.run(press=["💡 Hint 3 of 3"])
    assert "belongs in slot" in page
    conn.close()


def test_too_late_when_someone_else_searched_first(game_db):
    phone, code, conn = first_round(game_db)
    place, _ = open_puzzle(phone, conn, code)
    game = db.load(conn, code)
    later = time.time() + logic.HOLD_SECONDS + 1          # the reservation ran out meanwhile ...
    db.apply(conn, code, lambda g: logic.search(g, "other-2", place, later,  # ... and Sofia was faster
                                                 proof=minigames.solve(g, place)))
    page = phone.run()
    assert "Too late." in page
    page = phone.run(component={"submit": minigames.solve(game, place)})
    conn.close()


def test_a_forged_proof_from_the_phone_is_rejected(game_db):
    phone, code, conn = first_round(game_db)
    place, _ = open_puzzle(phone, conn, code, "puzzle")
    phone.run(component={"submit": {"swaps": [], "solved": True, "order": list(range(9))}})
    assert place not in db.load(conn, code)["searched"]
    conn.close()


def test_wrong_answers_are_limited_per_round_also_in_a_new_browser_tab(game_db):
    """No trying all 10 000 codes: after MAX_WRONG_TRIES wrong answers the seal holds until the
    next round, and the count lives in the game, so a fresh tab does not reset it."""
    phone, code, conn = first_round(game_db)
    place, _ = open_puzzle(phone, conn, code, "code")
    right = minigames.solve(db.load(conn, code), place)
    wrong = {"code": "0000" if right["code"] != "0000" else "1111"}
    for _ in range(logic.MAX_WRONG_TRIES):
        phone.run(component={"submit": wrong})
    game = db.load(conn, code)
    assert logic.wrong_tries(game, 1, place) == logic.MAX_WRONG_TRIES
    phone.run(component={"submit": right})                       # even the right code waits now
    assert place not in db.load(conn, code)["searched"]
    assert "seal holds until the next round" in str(last_data(phone)["state"]["note"])
    tab = Browser(room=code, t=phone.st.query_params["t"])          # a new tab, same seat
    tap(tab, step="search", place=place)
    tab.run(press=[f"Search {place}"])
    tab.run(component={"submit": right})
    assert place not in db.load(conn, code)["searched"]
    conn.close()


def test_an_answer_faster_than_a_person_could_solve_it_is_ignored(game_db, monkeypatch):
    phone, code, conn = first_round(game_db)
    place, _ = open_puzzle(phone, conn, code)
    kind = minigames.spec(db.load(conn, code), place)["kind"]
    monkeypatch.setattr(minigames, "MIN_SECONDS", {kind: 60})
    phone.run(component={"submit": minigames.solve(db.load(conn, code), place)})
    assert place not in db.load(conn, code)["searched"]
    assert "Not so fast" in str(last_data(phone)["state"]["note"])
    assert logic.wrong_tries(db.load(conn, code), 1, place) == 0     # not counted as a wrong answer
    conn.close()
