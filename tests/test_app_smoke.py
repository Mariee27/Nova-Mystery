"""Smoke test for app.py WITHOUT a real Streamlit.

A tiny stand-in for the `streamlit` module records what would be shown and
"presses" the buttons we tell it to. This proves that every screen can be
drawn in every phase and that the screens call the rules correctly.
It does NOT prove how the page looks in a browser.
"""

import pathlib
import runpy
import sys
import time
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ai      # noqa: E402
import db      # noqa: E402
import logic   # noqa: E402
import minigames  # noqa: E402


class Rerun(Exception):
    pass


class Stop(Exception):
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
        self.mounted = []      # (name, key, data) of every custom component
        # One fixed st.components object per stand-in, like the real module. app.mg_renderer
        # caches components by id(st.components.v2); a new object on every access would be
        # freed at once, and a later test could get the same id and an earlier test's component.
        self.components = self._make_components()

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

    def radio(self, label, options, index=0, format_func=str, **kwargs):
        options = list(options)
        self.shown.extend(str(format_func(option)) for option in options)
        return self.values.get(label, options[index])

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

    def stop(self):
        raise Stop()

    def _make_components(self):
        """st.components.v2: a component returns the trigger values the test put in
        values["component"] (e.g. a puzzle's proof), and records what it was given."""
        fake = self

        def component(name, **kwargs):
            def mount(key=None, data=None, **callbacks):
                fake.mounted.append((name, key, data))
                # like Streamlit's trigger values: delivered once, not again on the next rerun
                events = fake.values.pop("component", {}) if callbacks else {}
                return types.SimpleNamespace(**{e[3:-7]: events.get(e[3:-7]) for e in callbacks
                                                if e.startswith("on_") and e.endswith("_change")})
            return mount
        return types.SimpleNamespace(v2=types.SimpleNamespace(component=component))

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.shown.extend(str(a) for a in args)
            if "text" in kwargs:
                self.shown.append(str(kwargs["text"]))
        return record


def tap(phone, **params):
    """A tap on a card, pin, row or chip: its link reloads the page with ?step=...
    (see app.move_link). handle_move_links stores the selection and cleans the address."""
    phone.st.query_params.update({key: str(value) for key, value in params.items()})
    return phone.run()


def tap_on_map(phone, conn, code):
    """Choose 'Search a place', tap the first open pin, press 'Search <place>', and solve the
    place's sealed exhibit (the mini-game sends its proof, Python checks it)."""
    game = db.load(conn, code)
    place = next(p["name"] for p in logic.map_view(game)["places"] if p["state"] == "open")
    tap(phone, step="search", place=place)
    phone.run(press=[f"Search {place}"])
    if game.get("minigames"):
        assert any(name == "nova_minigame" for name, _, _ in phone.st.mounted), "the puzzle did not open"
        phone.run(component={"submit": minigames.solve(game, place)})
    return place


def end_investigation(host, conn, code):
    """The host ends every round of the investigation."""
    while db.load(conn, code)["phase"] == "INVESTIGATION":
        host.run(press=["End phase (host)"])


def token_of_phone(phone):
    return phone.st.query_params["t"]


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
                except Stop:       # st.stop(): the page ends here
                    break
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
    for name in ["Ana", "Ben", "<b>Caro</b>", "Dev", "Eli"]:   # a name is the only free text
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
        assert "Which case?" not in host.run()                # no AI key: case #001, nothing to choose
        host.run(press=["Start game"])
        assert phase() == "REVEAL"
        game = db.load(conn, code)
        murderer_pid = game["case"]["murderer"]

        for phone in phones:
            page = phone.run()
            assert "Your card" in page
        host.run(press=["End phase (host)"])
        assert phase() == "INVESTIGATION"

        tap_on_map(phones[1], conn, code)
        assert "step" not in phones[1].st.query_params        # a reload does not search twice
        assert "Access granted" in phones[1].run()               # the solved exhibit, until Continue
        assert "Move made." in phones[1].run(press=["Continue ▸"])
        game = db.load(conn, code)
        for phone in (phones[2], phones[4]):
            clue = logic.private_view(game, token_of_phone(phone))["clues"][0]["id"]
            tap(phone, step="share", clue=clue)
            phone.run(press=["Share with everyone"])
        murderer_phone = phones[murderer_pid - 1]
        target = 1 if murderer_pid != 1 else 2
        spot = logic.plant_locations(db.load(conn, code))[0]
        tap(murderer_phone, step="plant", blame=target, place=spot)
        murderer_phone.run(press=["Plant it"])
        game = db.load(conn, code)
        assert game["planted"] is True
        assert sorted(game["acted"]) == [2, 3, 5]
        kinds = [entry["kind"] for entry in game["log"]]
        assert kinds.count("search") == 2 and kinds.count("share") == 2
        assert "question" not in kinds and "answer" not in kinds   # interrogations happen out loud

        page = board.run()
        assert "&lt;b&gt;Caro&lt;/b&gt;" in page      # a name is shown as text, not as HTML
        assert "<b>Caro</b>" not in page
        assert "planted" not in page                 # the fake clue does not stand out
        assert "acted" not in page                   # no "acted" marks that give it away

        end_investigation(host, conn, code)                  # all rounds
        assert phase() == "DISCUSSION"
        host.run(press=["End phase (host)"])
        assert phase() == "VOTE"

        for index, phone in enumerate(phones, start=1):
            suspect = murderer_pid if index != murderer_pid else target
            assert "Choose who did it." in phone.run(press=["Vote"])     # nothing is chosen in advance
            tap(phone, step="vote", accuse=suspect)
            phone.run(press=["Vote"])
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
        phone.run(press=["Start game"], **{"Which case?": "rehearsal"})
        assert db.load(conn, code)["phase"] == "REVEAL"      # bots count as online
    finally:
        conn.close()


def test_home_page_names_the_real_number_of_rounds(game_db):
    page = Browser().run()
    assert f"{logic.ROUNDS} rounds, up to {logic.max_minutes()} minutes" in page and "5 rounds" not in page
    assert logic.max_minutes() == 20       # 30 s card + 3 rounds of 5 min + 3 min discussion + 1 min vote


def test_host_lobby_folds_away_add_demo_suspect_once_there_are_enough_players(game_db):
    phone = Browser()
    phone.run(press=["Play a demo"])
    code = phone.st.query_params["room"]
    page = phone.run()
    assert "Add or remove players (5 of 6)" in page
    assert "Keep this page open" not in page             # the host starts the game, so no hint
    page = phone.run(press=["Add demo suspect"])
    conn = db.connect(game_db)
    try:
        assert len(db.load(conn, code)["players"]) == 6
    finally:
        conn.close()
    page = phone.run()
    assert "Remove a player (6 of 6)" in page
    assert "Add or remove" not in page


def test_board_shows_the_evidence_board_and_the_phone_the_move_made(game_db):
    phone = Browser()
    phone.run(press=["Play a demo"])
    code = phone.st.query_params["room"]
    phone.run(press=["Start game"], **{"Which case?": "rehearsal"})
    phone.run(press=["End phase (host)"])                     # on to INVESTIGATION
    conn = db.connect(game_db)
    try:
        place = tap_on_map(phone, conn, code)
    finally:
        conn.close()
    board = Browser(room=code, view="board")
    page = board.run()
    assert 'class="ebs"' in page and "Exhibit 1" in page       # the evidence board, newest first
    assert 'class="plan2 board"' in page and "Just now" in page
    phone_page = phone.run()
    assert "Access granted" in phone_page and "New evidence discovered" in phone_page   # the solved exhibit
    assert place in phone_page
    assert "Move made." in phone.run(press=["Continue ▸"])     # then the move, with who is still choosing
    assert 'class="ebs"' not in phone_page
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
        phone.run(press=["Start game"], **{"Which case?": "rehearsal"})
        assert db.load(conn, code)["phase"] == "REVEAL"
        page = phone.run()
        assert page.index("Your card") < page.index('class="slist"') < page.index("Evidence &amp; statements")
        assert 'class="suspects"' not in page                   # no big tiles on the phone
        assert 'class="suspects"' in board.run()                # the board keeps them

        phone.run(press=["End phase (host)"])
        assert db.load(conn, code)["phase"] == "INVESTIGATION"
        page = phone.run()
        assert page.index("Your move.") < page.index("Your card") < page.index("Evidence &amp; statements")

        end_investigation(phone, conn, code)                  # all rounds
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
    phone.run(press=["Start game"], **{"Which case?": "rehearsal"})
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


def test_only_the_murderer_sees_the_murderer_stamp_and_the_board_never(game_db):
    board = Browser()
    board.run(press=["Create room"])
    code = board.st.query_params["room"]
    phones = []
    for name in ["Ana", "Ben", "Caro", "Dev", "Eli"]:
        phone = Browser(room=code)
        phone.run(press=["Join"], **{"Your name": name})
        phones.append(phone)
    phones[0].run(press=["Start game"], **{"Which case?": "rehearsal"})
    conn = db.connect(game_db)
    try:
        murderer = db.load(conn, code)["case"]["murderer"]
    finally:
        conn.close()

    for pid, phone in enumerate(phones, start=1):
        card = phone.run(press=["Open your file"])            # REVEAL: the file comes out of the envelope
        if pid == murderer:
            assert 'class="dstamp murderer slam"' in card and "MURDERER</div>" in card
            again = phone.run()                                # the stamp lands only once per session
            assert 'class="dstamp murderer"' in again and "dstamp murderer slam" not in again
        else:
            assert 'class="dstamp innocent"' in card and "MURDERER</div>" not in card
            assert 'class="dstamp murderer' not in card

    for _ in range(3):                                         # REVEAL → INVESTIGATION → DISCUSSION → VOTE
        page = board.run()
        assert 'class="dstamp' not in page                     # the board never shows a stamp
        phones[0].run(press=["End phase (host)"])
    assert 'class="dstamp' not in board.run()


def test_the_phone_guides_through_one_move_and_explains_mistakes(game_db):
    phone = Browser()
    phone.run(press=["Play a demo"])
    code = phone.st.query_params["room"]
    phone.run(press=["Start game"], **{"Which case?": "rehearsal"})
    phone.run(press=["End phase (host)"])                     # on to INVESTIGATION
    page = phone.run()
    assert "Your move." in page and page.count('class="act') >= 2
    assert "Interrogate" not in page and "Interrogations happen face to face" in page
    page = tap(phone, step="share")
    assert "Change action" in page
    assert "Your move." in tap(phone, step="home")            # "Change action" goes back
    tap(phone, step="share")
    assert "Choose a clue to share." in phone.run(press=["Share with everyone"])
    conn = db.connect(game_db)
    try:
        assert db.load(conn, code)["acted"] == []             # no mistake used up the move
    finally:
        conn.close()


def test_only_the_board_plays_the_crime_scene_moment_at_the_start(game_db):
    board = Browser()
    board.run(press=["Create room"])
    code = board.st.query_params["room"]
    board_tab = Browser(room=code, view="board")
    board_tab.run()                                            # the board is open in the lobby
    phones = []
    for name in ["Ana", "Ben", "Caro", "Dev"]:
        phone = Browser(room=code)
        phone.run(press=["Join"], **{"Your name": name})
        phones.append(phone)
    phones[0].run(press=["Start game"], **{"Which case?": "rehearsal"})
    intro = board_tab.run()                                    # REVEAL: the board shows who died where ...
    assert 'class="scene"' in intro
    assert 'class="lineup"' in intro and all(name in intro for name in ["Ana", "Ben", "Caro", "Dev"])
    assert 'class="scene"' not in board_tab.run()              # only once per session
    assert 'class="scene"' not in phones[1].run()              # phones keep the short intro


def test_the_stand_in_keeps_one_components_object_like_streamlit():
    """app.mg_renderer caches by id(st.components.v2). A fresh object per access let a later
    test reuse a freed id and get an earlier test's component (a flaky mini-game test)."""
    fake = FakeStreamlit()
    assert fake.components is fake.components and fake.components.v2 is fake.components.v2


def test_interrogations_are_out_loud_and_an_old_question_link_goes_back_to_your_move(game_db):
    phone = Browser()
    phone.run(press=["Play a demo"])
    code = phone.st.query_params["room"]
    phone.run(press=["Start game"], **{"Which case?": "rehearsal"})
    phone.run(press=["End phase (host)"])                     # on to INVESTIGATION
    page = tap(phone, step="question", ask=2)                 # a link from before the change
    assert "Your move." in page and "Ask in public" not in page and "Your question" not in page

    def nothing_left_for_player_1(g):
        g["searched"] = list(logic.story_of(g)["locations"])
        for clue in next(c for c in g["case"]["characters"] if c["pid"] == 1)["clues"]:
            g["log"].append({"id": len(g["log"]) + 1, "kind": "share", "by": 1, "text": clue["text"],
                             "clue_id": clue["id"], "round": g["round"]})
        return g

    conn = db.connect(game_db)
    try:
        db.apply(conn, code, nothing_left_for_player_1)
        page = phone.run()
        assert "Nothing left to search or share." in page and "Question the others out loud." in page
        for _ in range(logic.ROUNDS + 1):                      # end every round, at most once each
            if db.load(conn, code)["phase"] == "DISCUSSION":
                break
            phone.run(press=["End phase (host)"])
        assert db.load(conn, code)["phase"] == "DISCUSSION"
    finally:
        conn.close()
    page = phone.run()
    assert "Question each other face to face" in page and "Your answer" not in page


def host_of_a_room():
    """A room made on the board, and the phone of its first player (the host)."""
    board = Browser()
    board.run(press=["Create room"])
    code = board.st.query_params["room"]
    phone = Browser(room=code)
    phone.run(press=["Join"], **{"Your name": "Host"})
    return code, phone


def test_the_ai_is_only_asked_when_the_host_picks_an_ai_case(game_db, monkeypatch):
    """Creating rooms and demos never uses the AI quota; picking "A new case written by the AI" does."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-never-used")
    asked = []
    monkeypatch.setattr(ai, "write_story", lambda *args, **kwargs: asked.append(args) or {})
    demo = Browser()
    demo.run(press=["Play a demo"])
    code, phone = host_of_a_room()
    conn = db.connect(game_db)
    try:
        assert db.load(conn, code).get("ai_case") is None
        assert db.load(conn, demo.st.query_params["room"]).get("ai_case") is None
        page = phone.run()
        assert "A new case written by the AI" in page                    # offered, not started
        phone.run(**{"Which case?": "ai"})                               # picked: now it writes
        assert db.load(conn, code)["ai_case"]["status"] in ("writing", "failed", "ready")
    finally:
        conn.close()


def test_a_demo_always_plays_the_same_case_and_offers_no_choice(game_db, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-never-used")
    murderers = set()
    conn = db.connect(game_db)
    try:
        for _ in range(3):
            phone = Browser()
            phone.run(press=["Play a demo"])
            page = phone.run()
            assert "Which case?" not in page and "the same culprit every time" in page
            phone.run(press=["Start game"])
            game = db.load(conn, phone.st.query_params["room"])
            assert game["case"]["seed"] == logic.DEMO_SEED and game["story"]["source"] == "fixed"
            murderers.add(game["case"]["murderer"])
    finally:
        conn.close()
    assert len(murderers) == 1


def test_when_the_ai_limit_is_reached_the_host_is_told_and_can_play_case_001(game_db, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-never-used")
    asked = []
    monkeypatch.setattr(ai, "write_story", lambda *args, **kwargs: asked.append(args) or {})
    conn = db.connect(game_db)
    try:
        for i in range(db.MAX_AI_CASES_PER_HOUR):
            assert db.claim_ai_case(conn, time.time())
        code, phone = host_of_a_room()
        for name in ("Ben", "Caro", "Dev"):
            Browser(room=code).run(press=["Join"], **{"Your name": name})
        page = phone.run(**{"Which case?": "ai"})
        assert "No AI case (the AI limit for this hour is reached)." in page and asked == []
        phone.run(press=["Start game"], **{"Which case?": "ai"})        # waits: the AI case failed
        assert db.load(conn, code)["phase"] == "LOBBY"
        phone.run(press=["Start game"], **{"Which case?": "shuffled"})  # case #001 works any time
        assert db.load(conn, code)["phase"] == "REVEAL"
    finally:
        conn.close()


def test_a_database_error_shows_a_short_message_and_no_details(game_db, monkeypatch):
    import sqlite3

    def broken(target):
        raise sqlite3.OperationalError("unable to open database file /srv/xyzzy/murder.db")
    monkeypatch.setattr(db, "shared", broken)
    board = Browser()
    page = board.run(press=["Create room"])
    assert "cannot reach its database" in page
    assert "xyzzy" not in page and "OperationalError" not in page


def test_players_never_see_the_details_of_an_error():
    import tomllib
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["client"]["showErrorDetails"] == "none"


def test_hot_seat_between_rounds_on_the_board_and_the_phones(game_db):
    board = Browser()
    board.run(press=["Create room"])
    code = board.st.query_params["room"]
    board_tab = Browser(room=code, view="board")
    phones = []
    for name in ["Ana", "Ben", "Caro", "Dev"]:
        phone = Browser(room=code)
        phone.run(press=["Join"], **{"Your name": name})
        phones.append(phone)
    phones[0].run(press=["Start game"], **{"Which case?": "rehearsal", "🔥 Hot seat between rounds": True})
    conn = db.connect(game_db)
    try:
        phones[0].run(press=["End phase (host)"])               # REVEAL → round 1
        phones[0].run(press=["End phase (host)"])               # round 1 → the break
        assert logic.hot_seat_open(db.load(conn, code))
        assert "Who goes in the hot seat?" in board_tab.run()
        page = phones[1].run()
        assert "Hot seat – who should be grilled?" in page and "Your move." not in page

        # Everybody picks Caro (pid 3); Caro picks Ana. The seat starts on the next tick.
        now = time.time()
        for pid, target in [(1, 3), (2, 3), (3, 1), (4, 3)]:
            token = token_of_phone(phones[pid - 1])
            db.apply(conn, code, lambda g, t=token, x=target: logic.pick_hot_seat(g, t, x, now))
        board_page = board_tab.run()
        assert "Ask out loud!" in board_page and "Caro" in board_page
        assert "You are in the hot seat!" in phones[2].run()     # Caro's phone: answer out loud
        phones[0].run(press=["👎 Lying"])                        # Ana rates
        assert db.load(conn, code)["hot_seat"]["ratings"] == {"1": "lie"}
        assert "👎 1" in board_tab.run()                         # the board shows the count only
        phones[0].run(press=["End phase (host)"])               # the host ends the break
        game = db.load(conn, code)
        assert game["round"] == 2 and not logic.hot_seat_open(game)
        assert "Your move." in phones[1].run()
    finally:
        conn.close()


def test_a_phone_that_reloads_late_in_the_reveal_skips_the_intro(game_db):
    phone = Browser()
    phone.run(press=["Play a demo"])
    code, token = phone.st.query_params["room"], phone.st.query_params["t"]
    phone.run(press=["Start game"], **{"Which case?": "rehearsal"})
    early = Browser(room=code, t=token).run()                    # a fresh session right at the start
    assert 'class="intro case short"' in early
    conn = db.connect(game_db)
    try:
        now = time.time()                                        # 20 of the 30 seconds are gone
        db.apply(conn, code, lambda g: dict(g, deadline=now + 10))
    finally:
        conn.close()
    late = Browser(room=code, t=token).run()                     # the phone reloads now
    assert 'class="intro case short"' not in late and 'class="envelope"' in late   # the envelope is there
