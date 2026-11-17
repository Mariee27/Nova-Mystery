"""Smoke test for app.py WITHOUT a real Streamlit.

A tiny stand-in for the `streamlit` module records what would be shown and
"presses" the buttons we tell it to. This proves that every screen can be
drawn in every phase and that the screens call the rules correctly.
It does NOT prove how the page looks in a browser.
"""

import pathlib
import runpy
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db      # noqa: E402
import logic   # noqa: E402


class Rerun(Exception):
    pass


class Block:
    """Stands in for columns, tabs, expanders and forms."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class QueryParams(dict):
    pass


class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.query_params = QueryParams()
        self.session_state = {}
        self.secrets = {}
        self.context = types.SimpleNamespace(url="http://localhost:8501/")
        self.press = set()     # labels of buttons that are clicked in the next run
        self.values = {}       # label -> value for inputs
        self.shown = []        # everything that was written to the page

    def _pressed(self, label):
        if label in self.press:
            self.press.discard(label)
            return True
        return False

    def button(self, label, **kwargs):
        return (not kwargs.get("disabled")) and self._pressed(label)

    def form_submit_button(self, label, **kwargs):
        return self._pressed(label)

    def text_input(self, label, **kwargs):
        return self.values.get(label, "")

    def checkbox(self, label, **kwargs):
        return self.values.get(label, False)

    def selectbox(self, label, options, format_func=str, **kwargs):
        options = list(options)
        self.shown.extend(str(format_func(option)) for option in options)
        return self.values.get(label, options[0])

    def columns(self, spec):
        return [Block() for _ in range(len(spec) if isinstance(spec, list) else spec)]

    def tabs(self, labels):
        return [Block() for _ in labels]

    def expander(self, label, **kwargs):
        self.shown.append(str(label))
        return Block()

    def form(self, key, **kwargs):
        return Block()

    def fragment(self, func=None, **kwargs):
        if func is not None:
            return func
        return lambda f: f

    def rerun(self, **kwargs):
        raise Rerun()

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.shown.extend(str(a) for a in args)
            if "text" in kwargs:
                self.shown.append(str(kwargs["text"]))
        return record


class Browser:
    """One browser tab: keeps its link (query params) and its session."""

    def __init__(self, **params):
        self.st = FakeStreamlit()
        self.st.query_params.update(params)

    def run(self, press=(), **values):
        self.st.press = set(press)
        self.st.values = values
        self.st.shown = []
        sys.modules["streamlit"] = self.st
        try:
            for _ in range(5):     # follow st.rerun() like the real thing
                try:
                    runpy.run_path(str(ROOT / "app.py"), run_name="app_under_test")
                    break
                except Rerun:
                    continue
        finally:
            del sys.modules["streamlit"]
        return "\n".join(self.st.shown)


@pytest.fixture
def game_db(tmp_path, monkeypatch):
    path = tmp_path / "smoke.db"
    monkeypatch.setenv("MURDER_DB", str(path))
    return path


def test_full_game_through_the_screens(game_db):
    assert "How to play" in Browser().run()      # the rules are on the start page
    board = Browser()
    board.run(press=["Create room"])
    code = board.st.query_params["room"]
    assert board.st.query_params["view"] == "board"
    page = board.run()
    assert code in page
    assert "only that player knows" in page               # the rules are on the board in the lobby

    phones = []
    for name in ["Ana", "Ben", "Caro", "Dev", "Eli"]:
        phone = Browser(room=code)
        phone.run(press=["Join"], **{"Your name": name})
        assert phone.st.query_params.get("t"), f"{name} got no token"
        phones.append(phone)

    # a second Ana is rejected and gets no seat
    twin = Browser(room=code)
    assert "already taken" in twin.run(press=["Join"], **{"Your name": "ana"})
    assert "t" not in twin.st.query_params

    host = phones[0]
    conn = db.connect(game_db)
    try:
        def phase():
            return db.load(conn, code)["phase"]

        # only the host has a start button: pressing it elsewhere does nothing
        phones[1].run(press=["Start game"])
        assert phase() == "LOBBY"
        host.run(press=["Start game"], **{"Use the fixed demo case": True})
        assert phase() == "REVEAL"
        game = db.load(conn, code)
        murderer_pid = game["case"]["murderer"]
        assert game["case"]["seed"] == logic.DEMO_SEED

        for phone in phones:
            page = phone.run()
            assert "Your card" in page
        host.run(press=["End phase (host)"])
        assert phase() == "INVESTIGATION"

        phones[1].run(press=["Search this location"])
        # free text arrives escaped on the page
        asked_pid = 4
        phones[2].run(press=["Ask in public"], **{"Ask": asked_pid, "Your question": "<b>x</b>"})
        phones[3].run(press=["Answer"], **{"Your answer (you may lie)": "I was *not* there"})
        phones[4].run(press=["Make this clue public"])
        murderer_phone = phones[murderer_pid - 1]
        target = 1 if murderer_pid != 1 else 2
        murderer_phone.run(press=["Plant it"], **{"Blame": target})
        game = db.load(conn, code)
        assert game["planted"] is True
        assert sorted(game["acted"]) == [2, 3, 5]
        kinds = [entry["kind"] for entry in game["log"]]
        assert kinds.count("search") == 2 and "question" in kinds and "answer" in kinds

        page = board.run()
        assert "&lt;b&gt;x&lt;/b&gt;" in page      # shown as text, not as HTML
        assert "<b>x</b>" not in page
        assert "planted" not in page                 # the fake clue does not stand out
        assert "acted" not in page                   # no "acted" marks that give it away

        host.run(press=["End phase (host)"])
        assert phase() == "DISCUSSION"
        host.run(press=["End phase (host)"])
        assert phase() == "VOTE"

        for index, phone in enumerate(phones, start=1):
            suspect = murderer_pid if index != murderer_pid else target
            phone.run(press=["Vote"], **{"Who did it?": suspect})
        page = board.run()                           # the board's poll closes the vote
        assert phase() == "RESULT"
        assert "The detectives win" in page
        assert "planted by the murderer" in page
        assert "Case closed" in phones[2].run()
    finally:
        conn.close()


def test_unknown_room_and_unknown_token(game_db):
    assert "does not exist" in Browser(room="ZZZZ").run()
    page = Browser(room="[CLICK](https://evil.example)").run()
    assert "not a valid room code" in page
    assert "evil" not in page.lower()
    board = Browser()
    board.run(press=["Create room"])
    code = board.st.query_params["room"]
    stranger = Browser(room=code, t="not-a-real-token")
    assert "not a player" in stranger.run()


def test_play_a_demo_seats_you_with_four_demo_suspects(game_db):
    phone = Browser()
    phone.run(press=["Play a demo"])
    code, token = phone.st.query_params["room"], phone.st.query_params.get("t")
    assert token, "the demo gave no seat"
    conn = db.connect(game_db)
    try:
        game = db.load(conn, code)
        assert len(game["players"]) == 5
        assert sum(1 for p in game["players"] if p.get("bot")) == 4
        assert game["host"] == 1 and not game["players"][0].get("bot")
        assert "Board for the projector" in phone.run()     # the host is told where the board is
        phone.run(press=["Start game"], **{"Use the fixed demo case": True})
        assert db.load(conn, code)["phase"] == "REVEAL"      # bots count as online
    finally:
        conn.close()


def test_demo_link_starts_a_demo_without_the_intro(game_db):
    home = Browser()
    assert 'class="intro"' in home.run()                 # a normal first visit plays the intro
    phone = Browser(demo="1")
    page = phone.run()
    assert 'class="intro"' not in page                   # ?demo=1 skips it completely
    assert phone.st.query_params.get("t") and "demo" not in phone.st.query_params
    assert phone.st.session_state["intro_seen"] is True
    phone.st.query_params.clear()
    assert 'class="intro"' not in phone.run()            # not even when you go back home


def test_board_shows_the_big_timer_and_phones_the_thin_bar(game_db):
    phone = Browser()
    phone.run(press=["Play a demo"])
    code = phone.st.query_params["room"]
    phone.run(press=["Start game"])
    board = Browser(room=code, view="board")
    assert 'class="bigtimer' in board.run()
    page = phone.run()
    assert 'class="timer' in page and 'class="bigtimer' not in page
def test_phone_shows_the_most_important_thing_first(game_db):
    """Mobile first: the phone puts the current task on top; the board keeps the big tiles."""
    phone = Browser()
    phone.run(press=["Play a demo"])
    code = phone.st.query_params["room"]
    board = Browser(room=code, view="board")
    conn = db.connect(game_db)
    try:
        phone.run(press=["Start game"], **{"Use the fixed demo case": True})
        assert db.load(conn, code)["phase"] == "REVEAL"
        page = phone.run()
        assert page.index("Your card") < page.index('class="slist"') < page.index("Evidence &amp; statements")
        assert 'class="suspects"' not in page                   # no big tiles on the phone
        assert 'class="suspects"' in board.run()                # the board keeps them

        phone.run(press=["End phase (host)"])
        assert db.load(conn, code)["phase"] == "INVESTIGATION"
        page = phone.run()
        assert page.index("Your move") < page.index("Your card") < page.index("Evidence &amp; statements")

        phone.run(press=["End phase (host)"])
        phone.run(press=["End phase (host)"])
        assert db.load(conn, code)["phase"] == "VOTE"
        page = phone.run()
        assert page.index("Name the right suspect") < page.index("Your card")
    finally:
        conn.close()


def test_reveal_shows_a_sealed_envelope_that_stays_open_during_the_session(game_db):
    phone = Browser()
    phone.run(press=["Play a demo"])
    code = phone.st.query_params["room"]
    phone.run(press=["Start game"], **{"Use the fixed demo case": True})
    conn = db.connect(game_db)
    try:
        game = db.load(conn, code)
    finally:
        conn.close()
    assert game["phase"] == "REVEAL"
    sealed = phone.run()
    assert 'class="envelope"' in sealed and "CONFIDENTIAL – for Detective only" in sealed
    assert 'class="dossier' not in sealed                 # the card is not shown yet
    opened = phone.run(press=["Open your file"])
    assert ' play"' in opened                             # class="unseal ... play": the opening plays once ...
        again = phone.run()                                   # ... a redraw in the same session keeps it open (a real reload seals it again)
    assert 'class="dossier' in again and ' play"' not in again and 'class="envelope"' not in again
    guilty = game["case"]["murderer"] == 1                # pid 1 is the human "Detective"
    assert ("unseal guilty" in again) == guilty
