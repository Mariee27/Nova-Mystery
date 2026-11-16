"""Storage for Murder at NOVA (SQLite).

One row per room holds the whole game as JSON text. Heartbeats ("I am still
here") live in their own table so that they never touch the game itself.
No game rules belong in here.
"""

import json
import os
import secrets
import sqlite3

import logic

CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # no I and no O: easy to read from a projector
CODE_LENGTH = 4
ROOM_LIFETIME = 24 * 60 * 60                 # rooms older than one day are deleted
MAX_NEW_ROOMS_PER_HOUR = 200                 # stops anyone from filling the database


def connect(path):
    folder = os.path.dirname(str(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    # isolation_level=None: we write BEGIN / COMMIT ourselves, see apply().
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS rooms ("
        " code TEXT PRIMARY KEY, state TEXT NOT NULL, created_at REAL NOT NULL)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS presence ("
        " code TEXT NOT NULL, pid INTEGER NOT NULL, last_seen REAL NOT NULL,"
        " PRIMARY KEY (code, pid))")
    return conn


def _dump(game):
    return json.dumps(game, sort_keys=True, ensure_ascii=False)


def create_room(conn, now):
    conn.execute("BEGIN IMMEDIATE")
    try:
        old = [row[0] for row in conn.execute(
            "SELECT code FROM rooms WHERE created_at < ?", (now - ROOM_LIFETIME,))]
        for code in old:
            conn.execute("DELETE FROM presence WHERE code = ?", (code,))
            conn.execute("DELETE FROM rooms WHERE code = ?", (code,))
        recent = conn.execute(
            "SELECT COUNT(*) FROM rooms WHERE created_at > ?", (now - 60 * 60,)).fetchone()[0]
        if recent >= MAX_NEW_ROOMS_PER_HOUR:
            raise logic.Rejected("Too many new rooms right now. Please try again later.")
        while True:
            code = "".join(secrets.choice(CODE_LETTERS) for _ in range(CODE_LENGTH))
            if conn.execute("SELECT 1 FROM rooms WHERE code = ?", (code,)).fetchone() is None:
                break
        conn.execute("INSERT INTO rooms (code, state, created_at) VALUES (?, ?, ?)",
                     (code, _dump(logic.new_game(code, now)), now))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return code


def raw_state(conn, code):
    row = conn.execute("SELECT state FROM rooms WHERE code = ?", (code,)).fetchone()
    return row[0] if row else None


def load(conn, code):
    text = raw_state(conn, code)
    return json.loads(text) if text is not None else None


def apply(conn, code, fn):
    """Run game = fn(game) and save the result, all inside one write transaction.

    BEGIN IMMEDIATE takes the write lock first. A second phone that acts at the
    same moment has to wait and then sees the already changed game. If fn raises
    (for example logic.Rejected), nothing is saved.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        text = raw_state(conn, code)
        if text is None:
            raise logic.Rejected("This room does not exist.")
        game = fn(json.loads(text))
        new_text = _dump(game)
        if new_text != text:
            conn.execute("UPDATE rooms SET state = ? WHERE code = ?", (new_text, code))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return game


def heartbeat(conn, code, pid, now):
    conn.execute(
        "INSERT INTO presence (code, pid, last_seen) VALUES (?, ?, ?)"
        " ON CONFLICT (code, pid) DO UPDATE SET last_seen = excluded.last_seen",
        (code, pid, now))


def presence(conn, code):
    rows = conn.execute("SELECT pid, last_seen FROM presence WHERE code = ?", (code,))
    return {pid: last_seen for pid, last_seen in rows}
