"""The evidence mini-games on the phone, through app.py with the Streamlit stand-in."""

import db
import logic
import minigames
from test_app_smoke import Browser, game_db, tap  # noqa: F401  (game_db is a fixture)


def demo_round(game_db):
    """A demo room (you + 4 bots) in round 1 of the investigation, case #001."""
    phone = Browser()
    phone.run(press=["Play a demo"])
    code = phone.st.query_params["room"]
    phone.run(press=["Start game"], **{"Use the fixed demo case": True})
    phone.run(press=["End phase (host)"])
    conn = db.connect(game_db)
    assert db.load(conn, code)["phase"] == "INVESTIGATION"
    return phone, code, conn


def open_puzzle(phone, conn, code, kind):
    game = db.load(conn, code)
    place = next(s["location"] for s in minigames.specs(game) if s["kind"] == kind
                 and logic.locked_until(game, s["location"]) is None and s["location"] not in game["searched"])
    tap(phone, step="search", place=place)
    page = phone.run(press=[f"Search {place}"])
    return place, page


def last_data(phone):
    return [d for name, _, d in phone.st.mounted if name == "nova_minigame"][-1]


def test_the_place_card_shows_the_seal(game_db):
    phone, code, conn = demo_round(game_db)
    game = db.load(conn, code)
    place = next(s["location"] for s in minigames.specs(game) if logic.locked_until(game, s["location"]) is None)
    page = tap(phone, step="search", place=place)
    assert "Sealed exhibit #" in page
    conn.close()


def test_wrong_answer_unlocks_nothing_and_hints_come_one_by_one(game_db):
    phone, code, conn = demo_round(game_db)
    place, page = open_puzzle(phone, conn, code, "code")
    assert "Crack the code" in page and "Evidence unlocked" in page
    data = last_data(phone)
    assert data["kind"] == "code" and "hints" not in data and data["state"]["seq"] == 0
    assert minigames.solve(db.load(conn, code), place)["code"] not in str(data)

    page = phone.run(component={"submit": {"code": "2347"}})
    assert place not in db.load(conn, code)["searched"]            # no evidence for a wrong code
    data = last_data(phone)
    assert data["state"]["seq"] == 1 and "one time from the case file" in data["state"]["note"]

    page = phone.run(press=["💡 Hint 1 of 3"])
    assert "Hint 1" in page and "timeline" in page and "Hint 2</b>" not in page
    page = phone.run(press=["💡 Hint 2 of 3"])
    assert "Hint 2" in page and "Hint 3</b>" not in page
    page = phone.run(press=["💡 Hint 3 of 3"])
    assert "Hint 3" in page and "47 − 30 = 17" in page
    conn.close()


def test_solving_unlocks_the_evidence_with_a_reward_and_continue(game_db):
    phone, code, conn = demo_round(game_db)
    place, _ = open_puzzle(phone, conn, code, "cipher")
    proof = minigames.solve(db.load(conn, code), place)
    page = phone.run(component={"submit": proof})
    game = db.load(conn, code)
    entries = [e for e in game["log"] if e["kind"] == "search" and e["location"] == place]
    assert len(entries) == 1
    assert "Access granted" in page and "New evidence discovered" in page
    assert "The shifted-letter note" in page and entries[0]["text"] in page
    assert any(name == "nova_chime" for name, _, _ in phone.st.mounted)      # optional sound, once
    page = phone.run()                                                       # the reward stays …
    assert "Access granted" in page and 'class="mg-reward celebrate"' not in page   # … calm now
    phone.run(press=["Continue ▸"])
    assert "reward" not in phone.st.session_state
    page = phone.run(component={"submit": proof})                           # replaying the proof
    assert len([e for e in db.load(conn, code)["log"] if e.get("location") == place]) == 1
    conn.close()


def test_the_reward_survives_the_end_of_the_round(game_db):
    phone, code, conn = demo_round(game_db)
    place, _ = open_puzzle(phone, conn, code, "code")
    phone.run(component={"submit": minigames.solve(db.load(conn, code), place)})
    phone.run(press=["End phase (host)"])                                    # round 2 starts
    assert db.load(conn, code)["round"] == 2
    page = phone.run()
    assert "Access granted" in page and "Your move.</div>" not in page
    page = phone.run(press=["Continue ▸"])
    page = phone.run()
    assert "Your move.</div>" in page
    conn.close()


def test_puzzle_progress_survives_reruns(game_db):
    phone, code, conn = demo_round(game_db)
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
    phone, code, conn = demo_round(game_db)
    place, _ = open_puzzle(phone, conn, code, "code")
    game = db.load(conn, code)
    bot = next(p for p in game["players"] if p.get("bot"))
    db.apply(conn, code, lambda g: logic.search(g, bot["token"], place, 1))
    page = phone.run()
    assert "Too late." in page
    page = phone.run(component={"submit": minigames.solve(game, place)})
    conn.close()


def test_a_forged_proof_from_the_phone_is_rejected(game_db):
    phone, code, conn = demo_round(game_db)
    place, _ = open_puzzle(phone, conn, code, "puzzle")
    phone.run(component={"submit": {"swaps": [], "solved": True, "order": list(range(9))}})
    assert place not in db.load(conn, code)["searched"]
    conn.close()
