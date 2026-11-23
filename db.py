"""Storage for NOVA MYSTERY: a SQLite file, or PostgreSQL.

One row per room holds the whole game as JSON text. Heartbeats ("I am still
here") live in their own table so that they never touch the game itself.
No game rules belong in here.

connect(target) takes a file path (SQLite) or a postgresql:// address. A SQLite file on
Streamlit Community Cloud is lost whenever the app restarts (a new commit, or after it
slept), and every running game with it; a free PostgreSQL database (Neon, Supabase)
keeps the rooms. Both behave the same: every change of a game happens in one write
transaction, so two phones acting at the same moment never overwrite each other.
"""

import json
import os
import secrets
import sqlite3
import threading

import logic

CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # no I and no O: easy to read from a projector
CODE_LENGTH = 4
ROOM_LIFETIME = 24 * 60 * 60                 # rooms older than one day are deleted
MAX_NEW_ROOMS_PER_HOUR = 200                 # stops anyone from filling the database
IDLE_ROOM_SECONDS = 5 * 60                   # a lobby nobody was active in for this long is abandoned
MAX_AI_CASES_PER_HOUR = 5                    # AI cases for the whole app ...
MAX_AI_CASES_PER_DAY = 10                    # ... a case takes up to 5 requests, the free plan allows 50 a day
# Nobody can be recognised reliably (the app runs behind a proxy, and Streamlit warns that the
# visitor's address can be spoofed), so both limits work without knowing who is asking:
# - when the room limit is reached, abandoned lobbies are freed instead of refusing everyone
#   for an hour; flooding the app therefore blocks new rooms for minutes at most;
# - the AI quota has its own limit, so a flood of rooms cannot use it up.


def is_postgres(target):
    return str(target).startswith(("postgres://", "postgresql://"))


class _Postgres:
    """A PostgreSQL connection that understands the SQLite statements of this module:
    ? placeholders, BEGIN IMMEDIATE (one writer at a time, like SQLite) and PRAGMA."""

    def __init__(self, url):
        import psycopg   # only needed when a PostgreSQL address is configured

        self.raw = psycopg.connect(url, autocommit=True)   # we write BEGIN / COMMIT ourselves

    def execute(self, sql, params=()):
        if sql.startswith("PRAGMA"):
            return self.raw.execute("SELECT 1")
        if sql == "BEGIN IMMEDIATE":
            # One writer at a time while readers carry on: the same as SQLite's write lock.
            # Both statements in one round trip to the database (it may be far away).
            return self.raw.execute("BEGIN; LOCK TABLE rooms, ai_requests IN EXCLUSIVE MODE")
        return self.raw.execute(sql.replace("?", "%s"), params)

    def close(self):
        self.raw.close()


SCHEMA = [
    "CREATE TABLE IF NOT EXISTS rooms (code TEXT PRIMARY KEY, state TEXT NOT NULL, created_at {time} NOT NULL)",
    "CREATE TABLE IF NOT EXISTS presence (code TEXT NOT NULL, pid INTEGER NOT NULL, last_seen {time} NOT NULL,"
    " PRIMARY KEY (code, pid))",
    "CREATE TABLE IF NOT EXISTS ai_requests (at {time} NOT NULL)",
]


def connect(path):
    """A new connection to a SQLite file or a postgresql:// database; tables are created if needed."""
    target = str(path)
    if is_postgres(target):
        conn = _Postgres(target)
        time_type = "DOUBLE PRECISION"     # REAL has 4 bytes in PostgreSQL: too coarse for timestamps
    else:
        folder = os.path.dirname(target)
        if folder:
            os.makedirs(folder, exist_ok=True)
        # isolation_level=None: we write BEGIN / COMMIT ourselves, see apply().
        # check_same_thread=False: shared() hands a connection to one thread at a time only.
        conn = sqlite3.connect(target, timeout=10, isolation_level=None, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        time_type = "REAL"
    for statement in SCHEMA:
        conn.execute(statement.format(time=time_type))
    return conn


_local = threading.local()


def shared(target):
    """This thread's open connection to `target`: made once, then reused. Every screen asks
    for the current state every 2 seconds, and opening a new connection (and checking the
    tables) each time was most of that work. Streamlit runs a session's code in one thread at
    a time, so a thread never uses its connection twice at once."""
    connections = getattr(_local, "connections", None)
    if connections is None:
        connections = _local.connections = {}
    conn = connections.get(str(target))
    if conn is None:
        conn = connections[str(target)] = connect(target)
    return conn


def forget(target):
    """Close and drop this thread's connection to `target` (after an error), so the next
    call to shared() starts a fresh one."""
    conn = getattr(_local, "connections", {}).pop(str(target), None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _dump(game):
    return json.dumps(game, sort_keys=True, ensure_ascii=False)


def create_room(conn, now, minigames=False):
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Expired rooms go in two statements, however many there are. Every statement is a
        # round trip to the database, which may be far away: one by one (2 per room) made
        # "Create room" slow after a quiet day with many old rooms (playtest).
        cutoff = now - ROOM_LIFETIME
        conn.execute("DELETE FROM presence WHERE code IN (SELECT code FROM rooms WHERE created_at < ?)",
                     (cutoff,))
        conn.execute("DELETE FROM rooms WHERE created_at < ?", (cutoff,))
        recent = _recent_rooms(conn, now)
        if recent >= MAX_NEW_ROOMS_PER_HOUR:
            for code in _abandoned_lobbies(conn, now):
                conn.execute("DELETE FROM presence WHERE code = ?", (code,))
                conn.execute("DELETE FROM rooms WHERE code = ?", (code,))
            recent = _recent_rooms(conn, now)
        if recent >= MAX_NEW_ROOMS_PER_HOUR:
            raise logic.Rejected("Too many new rooms right now. Please try again later.")
        while True:
            code = "".join(secrets.choice(CODE_LETTERS) for _ in range(CODE_LENGTH))
            if conn.execute("SELECT 1 FROM rooms WHERE code = ?", (code,)).fetchone() is None:
                break
        conn.execute("INSERT INTO rooms (code, state, created_at) VALUES (?, ?, ?)",
                     (code, _dump(logic.new_game(code, now, minigames=minigames)), now))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return code


def _recent_rooms(conn, now):
    return conn.execute(
        "SELECT COUNT(*) FROM rooms WHERE created_at > ?", (now - 60 * 60,)).fetchone()[0]


def _abandoned_lobbies(conn, now):
    """Rooms still in the lobby, older than IDLE_ROOM_SECONDS, with no player seen since then."""
    rows = conn.execute(
        "SELECT code, state FROM rooms WHERE created_at < ? AND code NOT IN"
        " (SELECT code FROM presence WHERE last_seen > ?)",
        (now - IDLE_ROOM_SECONDS, now - IDLE_ROOM_SECONDS)).fetchall()
    return [code for code, state in rows if json.loads(state).get("phase") == "LOBBY"]


def claim_ai_case(conn, now):
    """True (and counted) if the app may ask the AI for one more case (hourly and daily limit)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DELETE FROM ai_requests WHERE at < ?", (now - 24 * 60 * 60,))
        today = conn.execute("SELECT COUNT(*) FROM ai_requests").fetchone()[0]
        this_hour = conn.execute("SELECT COUNT(*) FROM ai_requests WHERE at > ?", (now - 60 * 60,)).fetchone()[0]
        allowed = today < MAX_AI_CASES_PER_DAY and this_hour < MAX_AI_CASES_PER_HOUR
        if allowed:
            conn.execute("INSERT INTO ai_requests (at) VALUES (?)", (now,))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return allowed


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
    if new_text != text:
        forget_snapshot(code)
    return game


def heartbeat(conn, code, pid, now):
    conn.execute(
        "INSERT INTO presence (code, pid, last_seen) VALUES (?, ?, ?)"
        " ON CONFLICT (code, pid) DO UPDATE SET last_seen = excluded.last_seen",
        (code, pid, now))


def presence(conn, code):
    rows = conn.execute("SELECT pid, last_seen FROM presence WHERE code = ?", (code,))
    return {pid: last_seen for pid, last_seen in rows}


# ---------------------------------------------------------------- one read per room and second
#
# Every phone and the board ask for their room's state every 2 seconds, each in up to three
# places. They all see the same game, so one read per room and second serves them all.
# Every write through apply() drops the room's snapshot, so whoever acts sees the result at
# once; the others see it within a second.

SNAPSHOT_SECONDS = 1.0
_snapshots = {}
_snapshot_lock = threading.Lock()


def snapshot(conn, code, now, key=""):
    """(game, presence) of a room, read at most once per SNAPSHOT_SECONDS for the whole app.
    key: which database (the app may serve tests with different files). Do not change the
    returned game in place: logic functions always return a copy."""
    with _snapshot_lock:
        hit = _snapshots.get((key, code))
    if hit is not None and 0 <= now - hit[0] < SNAPSHOT_SECONDS:
        return hit[1], hit[2]
    game, seen = load(conn, code), presence(conn, code)
    with _snapshot_lock:
        _snapshots[(key, code)] = (now, game, seen)
    return game, seen


def forget_snapshot(code):
    with _snapshot_lock:
        for entry in [entry for entry in _snapshots if entry[1] == code]:
            del _snapshots[entry]
