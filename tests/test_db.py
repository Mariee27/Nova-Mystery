"""Storage (Done-when 16 (db part), 19, 21)."""
import json
import threading

import pytest

import db
import logic
from conftest import LOC

ALPHABET = set("ABCDEFGHJKLMNPQRSTUVWXYZ")
ON5 = {1, 2, 3, 4, 5}


@pytest.fixture
def path(tmp_path):
    return str(tmp_path / "game.sqlite")


@pytest.fixture
def conn(path):
    c = db.connect(path)
    yield c
    try:
        c.close()
    except Exception:
        pass


def join_players(conn, code, n):
    game = None
    for i in range(1, n + 1):
        game = db.apply(conn, code, lambda g, i=i: logic.join(g, "P%d" % i, "t%d" % i, 0))
    return game


def room_in_investigation(conn, n=5):
    code = db.create_room(conn, 0)
    join_players(conn, code, n)
    db.apply(conn, code, lambda g: logic.start(g, "t1", set(range(1, n + 1)), 0, seed=1))
    return code, db.apply(conn, code, lambda g: logic.end_phase(g, "t1", ON5, 0))


# ---------------------------------------------------------------- DW21
def test_dw21_create_room_returns_4_letter_code_from_allowed_alphabet(conn):
    codes = [db.create_room(conn, i) for i in range(60)]
    assert len(set(codes)) == 60
    for code in codes:
        assert isinstance(code, str) and len(code) == 4
        assert set(code) <= ALPHABET
    game = db.load(conn, codes[0])
    assert game["code"] == codes[0]
    assert game["phase"] == "LOBBY"


def test_dw21_persistence_across_connections(path):
    c1 = db.connect(path)
    code = db.create_room(c1, 0)
    game = join_players(c1, code, 4)
    c1.close()
    c2 = db.connect(path)
    try:
        loaded = db.load(c2, code)
        assert loaded == game
        assert json.dumps(loaded, sort_keys=True) == json.dumps(game, sort_keys=True)
        assert [p["name"] for p in loaded["players"]] == ["P1", "P2", "P3", "P4"]
        assert json.loads(db.raw_state(c2, code)) == loaded
    finally:
        c2.close()


def test_dw21_started_game_survives_reconnect(path):
    c1 = db.connect(path)
    code, game = room_in_investigation(c1)
    c1.close()
    c2 = db.connect(path)
    try:
        assert db.load(c2, code) == game
    finally:
        c2.close()


def test_dw21_load_unknown_code_is_none(conn):
    assert db.load(conn, "ZZZZ") is None
    assert db.raw_state(conn, "ZZZZ") is None


def test_dw21_presence_returns_heartbeats(path):
    c1 = db.connect(path)
    code = db.create_room(c1, 0)
    assert db.presence(c1, code) == {}
    db.heartbeat(c1, code, 1, 5.0)
    db.heartbeat(c1, code, 2, 7.5)
    assert db.presence(c1, code) == {1: 5.0, 2: 7.5}
    db.heartbeat(c1, code, 1, 9)
    assert db.presence(c1, code) == {1: 9, 2: 7.5}
    c1.close()
    c2 = db.connect(path)
    try:
        assert db.presence(c2, code) == {1: 9, 2: 7.5}
    finally:
        c2.close()


def test_dw21_presence_is_per_room(conn):
    a = db.create_room(conn, 0)
    b = db.create_room(conn, 0)
    db.heartbeat(conn, a, 1, 3)
    assert db.presence(conn, b) == {}


def test_dw21_apply_unknown_room_raises_rejected(conn):
    with pytest.raises(logic.Rejected):
        db.apply(conn, "ZZZZ", lambda g: g)


# ---------------------------------------------------------------- DW16 (db)
def test_dw16_rejected_apply_leaves_raw_state_identical(conn):
    code = db.create_room(conn, 0)
    join_players(conn, code, 2)
    before = db.raw_state(conn, code)
    assert isinstance(before, str)
    with pytest.raises(logic.Rejected):
        db.apply(conn, code, lambda g: logic.join(g, "p1", "tz", 0))  # duplicate name
    assert db.raw_state(conn, code) == before
    with pytest.raises(logic.Rejected):
        db.apply(conn, code, lambda g: logic.start(g, "t1", {1, 2}, 0, seed=1))  # too few
    assert db.raw_state(conn, code) == before
    with pytest.raises(logic.Rejected):
        db.apply(conn, code, lambda g: logic.start(g, "t2", ON5, 0, seed=1))  # not host
    assert db.raw_state(conn, code) == before


def test_dw16_apply_rolls_back_when_fn_raises_rejected_after_changing_game(conn):
    code = db.create_room(conn, 0)
    join_players(conn, code, 2)
    before = db.raw_state(conn, code)

    def fn(game):
        game["phase"] = "VOTE"
        game["players"].clear()
        raise logic.Rejected("nope")

    with pytest.raises(logic.Rejected):
        db.apply(conn, code, fn)
    assert db.raw_state(conn, code) == before
    assert db.load(conn, code)["phase"] == "LOBBY"


def test_dw16_rejected_game_action_in_started_room_leaves_raw_state(conn):
    code, _ = room_in_investigation(conn)
    db.apply(conn, code, lambda g: logic.search(g, "t1", LOC[0], 5))
    before = db.raw_state(conn, code)
    with pytest.raises(logic.Rejected):
        db.apply(conn, code, lambda g: logic.search(g, "t1", LOC[1], 6))  # second action
    with pytest.raises(logic.Rejected):
        db.apply(conn, code, lambda g: logic.search(g, "t2", LOC[0], 6))  # already searched
    assert db.raw_state(conn, code) == before


def test_dw16_successful_apply_changes_raw_state_and_returns_game(conn):
    code = db.create_room(conn, 0)
    before = db.raw_state(conn, code)
    game = db.apply(conn, code, lambda g: logic.join(g, "Anna", "ta", 0))
    assert db.raw_state(conn, code) != before
    assert game["players"][0]["name"] == "Anna"
    assert db.load(conn, code) == game


# ---------------------------------------------------------------- DW19
def _race(path, code, loc, rounds_label):
    barrier = threading.Barrier(2)
    outcome = {}

    def worker(token):
        c = db.connect(path)
        try:
            barrier.wait(timeout=10)
            try:
                db.apply(c, code, lambda g: logic.search(g, token, loc, 10))
                outcome[token] = "ok"
            except logic.Rejected:
                outcome[token] = "rejected"
            except Exception as exc:  # e.g. sqlite3.OperationalError: must not happen
                outcome[token] = repr(exc)
        finally:
            c.close()

    threads = [threading.Thread(target=worker, args=(t,)) for t in ("t1", "t2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads)
    return outcome


def test_dw19_two_concurrent_searches_of_same_location_exactly_one_succeeds(path):
    main = db.connect(path)
    try:
        for r in range(8):
            code, _ = room_in_investigation(main)
            loc = LOC[r % len(LOC)]
            outcome = _race(path, code, loc, r)
            assert sorted(outcome.values()) == ["ok", "rejected"], outcome
            game = db.load(main, code)
            assert game["searched"] == [loc]
            assert len(game["acted"]) == 1
            assert len([e for e in game["log"] if e["kind"] == "search"]) == 1
    finally:
        main.close()
