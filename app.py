"""Screens of NOVA MYSTERY (Streamlit).

This file only shows things and passes clicks on. All rules are in logic.py,
all storage is in db.py, all HTML building blocks are in ui.py, and the only
call to an AI service is in ai.py.

Three kinds of screens, chosen by the link:
  ?room=CODE&view=board   the projector board (public data only)
  ?room=CODE&t=TOKEN      one player's phone
  ?room=CODE              the join form
"""

import io
import os
import threading
import time
from contextlib import contextmanager
from urllib.parse import urlencode

import streamlit as st

import ai
import content
import db
import logic
import minigame_ui
import minigames
import ui

DB_PATH = os.environ.get("MURDER_DB", "data/murder.db")
POLL_SECONDS = 2   # every open screen asks for the current state this often

PHASE_TITLES = {
    "LOBBY": "Lobby – the suspects arrive",
    "REVEAL": "Read your file",
    "INVESTIGATION": "Investigation – round {round} of {rounds}",
    "DISCUSSION": "Discussion – who is lying?",
    "VOTE": "The final accusation",
    "RESULT": "Case closed",
    "ABORTED": "Investigation suspended",
}

PHASE_SUBTITLES = {
    "LOBBY": "Scan the code or enter the room code on your phone. 4 to 6 suspects.",
    "REVEAL": "Every phone now holds a private file. One of you is lying about everything.",
    "INVESTIGATION": "One move per round: search a place on the map or share what you know. "
                     "Question each other out loud.",
    "DISCUSSION": "Question each other face to face. Compare the alibis. Everybody may lie.",
    "VOTE": "Name the suspect – and the place where {victim} really died.",
    "RESULT": "",
    "ABORTED": "",
}


# ---------------------------------------------------------------- plumbing

def db_target():
    """Where the rooms live: DATABASE_URL (a postgresql:// address, so rooms survive a restart
    of the app) if it is set, otherwise the SQLite file MURDER_DB."""
    return setting("DATABASE_URL") or DB_PATH


@contextmanager
def open_db():
    """This thread's database connection (reused, see db.shared). After a database error the
    connection is dropped, so the next call starts a fresh one."""
    target = db_target()
    try:
        yield db.shared(target)
    except Exception as problem:
        if type(problem).__module__.split(".")[0] in ("sqlite3", "psycopg"):
            db.forget(target)
        raise


def sync(code, token=None):
    """Heartbeat, timers, and the current views. Returns (public, private) or (None, None)."""
    now = time.time()
    with open_db() as conn:
        game, seen = db.snapshot(conn, code, now, key=db_target())
        if game is None:
            return None, None
        me = logic.private_view(game, token)
        if me is not None:
            db.heartbeat(conn, code, me["pid"], now)
            seen = {**seen, me["pid"]: now}
        online = logic.with_bots(game, logic.online_ids(seen, now))

        def step(g):   # timers first, then whatever the demo suspects have to do
            return logic.bot_moves(logic.tick(g, online, now), now)

        # Only write when the timers or the bots really change something.
        if step(game) is not game:
            game = db.apply(conn, code, step)
        return views(game, online, token)


def views(game, online, token=None):
    """The public view plus the story everybody may read, and the player's own view."""
    public = logic.public_view(game, online)
    public["story"] = logic.story_view(game)
    public["map"] = logic.map_view(game)
    me = logic.private_view(game, token)
    if me is not None:
        me["host_note"] = logic.host_note(game, token)
        me["ai_status"] = logic.ai_status(game, token)
    return public, me


def act(code, action):
    """Run one action. action(game, online, now) -> game. Rejections are shown to the player."""
    attempt(code, action)
    st.rerun()


def attempt(code, action):
    """Like act, without the rerun. True if the action was saved."""
    now = time.time()
    try:
        with open_db() as conn:
            presence = db.presence(conn, code)
            db.apply(conn, code, lambda g: action(
                g, logic.with_bots(g, logic.online_ids(presence, now)), now))
    except logic.Rejected as problem:
        st.session_state["flash"] = str(problem)
        return False
    return True


def show(html):
    """Show an HTML block from ui.py (all text in it is already escaped)."""
    st.markdown(html, unsafe_allow_html=True)


def play_case_intro(code, public):
    """The intro of this room's case plays once on each screen, when the game starts."""
    key = f"case_intro_{code}"
    if public["phase"] == "REVEAL" and not st.session_state.get(key):
        st.session_state[key] = True
        show(ui.case_intro(public["story"], suspects=len(public["players"])))


def case_kicker(public):
    """'Case #ABCD · Title' once the game runs. In the lobby the case is still sealed."""
    if public["phase"] == "LOBBY":
        return "Murder Mystery · sealed case"
    story = public["story"]
    return f"Case #{story['case_number']} · {story['case_title']}"


def valid_code(code):
    """A room code is exactly 4 letters from the room-code alphabet."""
    return len(code) == db.CODE_LENGTH and all(ch in db.CODE_LETTERS for ch in code)


def seconds_left(public):
    if public["deadline"] is None:
        return None
    return max(0, int(round(public["deadline"] - time.time())))


def name_of(public, pid):
    for player in public["players"]:
        if player["pid"] == pid:
            return player["name"]
    return "Someone"


def base_url():
    """Address of this app, needed for the QR code. Set APP_BASE_URL when deployed."""
    url = os.environ.get("APP_BASE_URL", "")
    if not url:
        try:
            url = st.secrets.get("APP_BASE_URL", "")
        except Exception:
            url = ""
    if not url:
        try:
            url = st.context.url.split("?")[0]
        except Exception:
            url = ""
    return url.rstrip("/")


# ---------------------------------------------------------------- AI case (background)

def setting(name):
    """A setting from the environment or from .streamlit/secrets.toml (None if missing)."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except Exception:   # no secrets file at all
        return None


def begin_ai_case(code):
    """Let the AI write a new case for this room while the players join.

    The writing runs in a background thread, so nobody has to wait for it. When it
    is done, the thread stores the result in the game (logic.ai_case_ready or
    logic.ai_case_failed). The host clicks Start whenever they like: if the AI case
    is not ready by then, the game plays case #001.
    """
    settings = ai.settings(setting)
    now = time.time()
    with open_db() as conn:
        if settings is None:
            db.apply(conn, code, lambda g: logic.ai_case_failed(g, "no AI key is set up", now))
            return
        if not db.claim_ai_case(conn, now):     # protects the AI quota from a flood of rooms
            db.apply(conn, code, lambda g: logic.ai_case_failed(g, "the AI limit for this hour is reached", now))
            return
        db.apply(conn, code, lambda g: logic.ai_case_writing(g, now))
    threading.Thread(target=write_ai_case, args=(code, settings), daemon=True).start()


def write_ai_case(code, settings):
    """Runs in the background thread: ask the AI, then save what came back."""
    try:
        story = ai.write_story(settings["key"], settings["model"])
        change = lambda g: logic.ai_case_ready(g, story, time.time())
    except ai.AIError as problem:
        reason = str(problem)
        change = lambda g: logic.ai_case_failed(g, reason, time.time())
    try:
        with open_db() as conn:
            db.apply(conn, code, change)
    except logic.Rejected:
        pass   # the room is gone


# ---------------------------------------------------------------- shared pieces

def show_phase(public, big_timer=False):
    """Phase title and timer. The board (big_timer=True) shows the countdown in large numbers
    next to the title; phones keep the thin bar."""
    phase = public["phase"]
    subtitle = PHASE_SUBTITLES.get(phase, "").format(victim=public["story"]["victim_short"])
    title = PHASE_TITLES[phase].format(round=public["map"]["round"], rounds=public["map"]["rounds"])
    banner = ui.banner(title, subtitle)
    left = seconds_left(public)
    if left is None:
        show(banner)
    elif big_timer:
        title, clock = st.columns([3, 1])
        with title:
            show(banner)
        with clock:
            show(ui.big_timer(left, logic.DURATIONS[phase]))
    else:
        show(banner)
        show(ui.timer(left, logic.DURATIONS[phase]))


def show_rules(expanded=False):
    with st.expander("How to play", expanded=expanded):
        st.markdown(content.HOW_TO_PLAY)


def show_players(public):
    show(ui.suspects(public["players"], public["phase"], story=public["story"]))


def show_log(public):
    if not public["log"]:
        st.caption("Nothing has been found yet.")
        return
    # Oldest first: a new entry is added at the bottom and only that card animates in.
    for entry in public["log"]:
        show(ui.log_entry(entry, lambda pid: name_of(public, pid), story=public["story"]))


def show_result(public):
    result = public["result"]
    characters = public["characters"]
    who = lambda pid: name_of(public, pid)   # noqa: E731
    story = public["story"]
    show(ui.reveal(result, characters, who, story=story))
    # The ballots come right after the culprit, over the full width: the moment everybody reacts to.
    st.markdown("### How everyone voted")
    show(ui.vote_table(result, public["players"], who))
    left, right = st.columns([3, 2])
    with left:
        st.markdown("### Reconstruction of the night")
        show(ui.reconstruction(result, characters, who, story=story))
        st.markdown("### Every alibi, checked")
        show(ui.alibi_table(result, characters, who))
        if result.get("red_herrings"):
            st.markdown("### The false trails")
            show(ui.red_herrings(result["red_herrings"]))
    with right:
        # The ballots above already show who accused whom and where, so no vote bars here.
        st.markdown("### Where it happened")
        show(ui.campus_map(public["searched"], scene=result["murder_location"], story=story,
                           view=public["map"]))
    st.markdown("### The evidence, re-examined")
    st.caption("Now that the case is closed, every exhibit shows how reliable it really was.")
    show_log(public)


# ---------------------------------------------------------------- home and join

def home_screen():
    # Presentation link ?demo=1: go straight into a demo game, without the intro.
    if st.query_params.get("demo"):
        del st.query_params["demo"]
        start_demo()
        return
    # The opening plays once per browser session. It is pure CSS, works without sound,
    # and is switched off for people who ask their system for reduced motion.
    if not st.session_state.get("intro_seen"):
        st.session_state["intro_seen"] = True
        show(ui.intro())
        if st.button("Skip intro ›", key="skip_intro"):
            st.rerun()
    show(ui.brand())
    left, right = st.columns([3, 2])
    with left:
        show(ui.teaser())
    with right:
        st.markdown("#### Open the investigation")
        st.caption("One screen becomes the board (a laptop or projector). "
                   "Everybody else joins on their phone.")
        if st.button("Create room", type="primary", use_container_width=True):
            try:
                with open_db() as conn:
                    code = db.create_room(conn, time.time(), minigames=True)
            except logic.Rejected as problem:
                st.error(str(problem))
                return
            st.query_params["room"] = code
            st.query_params["view"] = "board"
            st.rerun()
        if st.button("Play a demo", use_container_width=True,
                     help="Presentation mode: you play together with 4 demo suspects."):
            start_demo()
        with st.form("goto"):
            code = st.text_input("Room code", max_chars=4, placeholder="ABCD")
            if st.form_submit_button("Join room", use_container_width=True):
                st.query_params["room"] = code.strip().upper()
                st.rerun()
        show_rules()


DEMO_BOTS = 4   # with you as host: 5 players, enough for every phase


def start_demo():
    """New room, you as host, plus demo suspects. You land on your phone screen in the lobby."""
    st.session_state["intro_seen"] = True   # a demo never shows the intro, not even later
    token = logic.new_token()
    now = time.time()
    try:
        with open_db() as conn:
            code = db.create_room(conn, now, minigames=True)
            game = db.apply(conn, code, lambda g: logic.join(g, "Detective", token, now))
            db.heartbeat(conn, code, logic.private_view(game, token)["pid"], now)
            for _ in range(DEMO_BOTS):
                db.apply(conn, code, lambda g: logic.add_bot(g, token, now))
    except logic.Rejected as problem:
        st.error(str(problem))
        return
    st.query_params["room"] = code
    st.query_params["t"] = token
    st.rerun()


def join_screen(code):
    public, _ = sync(code)
    show(ui.brand())
    if public is None:
        st.error(f"Room {code} does not exist.")
        if st.button("Back"):
            st.query_params.clear()
            st.rerun()
        return
    st.markdown(f'<div class="kicker">Room {ui.h(code)} · {ui.h(case_kicker(public))}</div>',
                unsafe_allow_html=True)
    if public["phase"] != "LOBBY":
        st.warning("This investigation has already started. You can watch on the board.")
        if st.button("Open the board"):
            st.query_params["view"] = "board"
            st.rerun()
        return
    with st.form("join"):
        name = st.text_input("Your name", max_chars=logic.MAX_NAME)
        submitted = st.form_submit_button("Join", type="primary")
    show_rules()
    if submitted:
        token = logic.new_token()
        now = time.time()
        try:
            with open_db() as conn:
                game = db.apply(conn, code, lambda g: logic.join(g, name, token, now))
                db.heartbeat(conn, code, logic.private_view(game, token)["pid"], now)
        except logic.Rejected as problem:
            st.error(str(problem))
            return
        # The token lives in the link. Reloading this page keeps the seat.
        st.query_params["t"] = token
        st.rerun()


# ---------------------------------------------------------------- board (projector)

@st.fragment(run_every=POLL_SECONDS)
def board_live(code):
    public, _ = sync(code)
    if public is None:
        st.error(f"Room {code} does not exist.")
        return
    if public["phase"] != st.session_state.get("board_phase"):
        st.rerun()   # a new phase: redraw the whole board (and play the case intro at the start)
    story = public["story"]
    phase = public["phase"]
    if phase == "INVESTIGATION":
        board_round(code, public)
        return
    st.markdown(f'<div class="kicker">{ui.h(case_kicker(public))} · Room {ui.h(code)}</div>',
                unsafe_allow_html=True)
    show_phase(public, big_timer=True)
    if phase == "ABORTED":
        st.error(public["abort_reason"])
    if phase == "RESULT":
        show_result(public)
        return
    if phase == "LOBBY":
        left, right = st.columns([2, 3])
        with left:
            st.markdown('<div class="kicker">Room code</div>', unsafe_allow_html=True)
            show(f'<div class="lobby-code">{ui.h(code)}</div>')
            url = base_url()
            if url:
                link = f"{url}/?room={code}"
                try:
                    import qrcode
                    picture = io.BytesIO()
                    qrcode.make(link, border=2).save(picture, format="PNG")
                    st.image(picture.getvalue(), width=230)
                except ImportError:
                    pass
                st.caption(link)
            else:
                st.caption("Open this app on your phone and enter the room code.")
        with right:
            st.markdown('<div class="kicker">The suspects</div>', unsafe_allow_html=True)
            show_players(public)
            # The projector has room for the rules while everybody joins.
            st.markdown("**How to play**")
            st.markdown(content.HOW_TO_PLAY)
        return
    st.markdown('<div class="kicker">The suspects</div>', unsafe_allow_html=True)
    show_players(public)
    # The map gets the full width, so the five equal tiles are big enough to read on a projector.
    st.markdown('<div class="kicker">Campus map</div>', unsafe_allow_html=True)
    show(ui.campus_map(public["searched"], story=story, view=public["map"], board=True))
    left, right = st.columns([2, 3])
    with left:
        st.markdown(f'<div class="place">{ui.h(story["briefing"])}</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="kicker">Evidence wall</div>', unsafe_allow_html=True)
        # The board shows the log as a cork board; phones keep the simple list (show_log).
        show(ui.evidence_wall(public["log"], lambda pid: name_of(public, pid), story=story))


def board_round(code, public):
    """The board during the rounds: header with room, round and timer; the campus plan on
    the left; on the right who has moved and the evidence board."""
    story = public["story"]
    show(ui.board_head(code, public["map"]["round"], public["map"]["rounds"], seconds_left(public)))
    st.markdown(f'<div class="kicker">{ui.h(case_kicker(public))}</div>', unsafe_allow_html=True)
    left, right = st.columns([3, 2])
    with left:
        show(ui.campus_map(public["searched"], story=story, view=public["map"], board=True))
    with right:
        show(ui.detectives(public["players"]))
        show(ui.evidence_board(public["log"], lambda pid: name_of(public, pid), story=story))


def board_screen(code):
    show(ui.brand())
    public, _ = sync(code)
    if public is not None:
        st.session_state["board_phase"] = public["phase"]
        play_case_intro(code, public)
    board_live(code)


# ---------------------------------------------------------------- player (phone)

def signature(public, me):
    """Changes whenever the buttons on the phone have to change: also when new evidence
    arrives, so that the search list stays current."""
    evidence = sum(1 for e in public["log"] if e["kind"] in logic.EVIDENCE_KINDS)
    # Who is in the room and online: the host's Start button depends on it.
    players = tuple((p["pid"], p["online"]) for p in public["players"])
    # The round and the state of every place: the map's markers depend on them.
    places = (public["map"]["round"],) + tuple(p["state"] for p in public["map"]["places"])
    return (public["phase"], me["acted"], me["voted"], me["is_host"], me["can_plant"],
            evidence, me["host_note"], me.get("ai_status"), players, places)


@st.fragment(run_every=POLL_SECONDS)
def player_status(code, token):
    public, me = sync(code, token)
    if public is None or me is None:
        st.rerun()
    show_phase(public)
    if signature(public, me) != st.session_state.get("signature"):
        st.rerun()   # redraw the whole page so that the right buttons appear


@st.fragment(run_every=POLL_SECONDS)
def player_suspects(code, my_pid):
    """The suspects as a short list. The phone has no room for the board's big tiles."""
    with open_db() as conn:
        game, seen = db.snapshot(conn, code, time.time(), key=db_target())
        online = logic.online_ids(seen, time.time())
    if game is not None:
        public = logic.public_view(game, logic.with_bots(game, online))
        st.markdown('<div class="kicker">The suspects</div>', unsafe_allow_html=True)
        show(ui.suspect_list(public["players"], public["phase"], my_pid))


@st.fragment(run_every=POLL_SECONDS)
def player_log(code):
    with open_db() as conn:
        game, seen = db.snapshot(conn, code, time.time(), key=db_target())
        online = logic.online_ids(seen, time.time())
    if game is not None:
        st.markdown('<div class="kicker" id="evidence-log">Evidence &amp; statements</div>',
                    unsafe_allow_html=True)
        show_log(views(game, online)[0])


def show_card(me, expanded):
    with st.expander(f"Your card: {ui.md(me['role'])}", expanded=expanded):
        show(ui.dossier(me))


def sealed_card(code, me, story):
    """REVEAL: first a sealed envelope, the file only after "Open your file".
    session_state remembers the envelope per room and player within one browser session.
    A real page reload starts a new session, so the envelope is sealed again and the player
    opens it once more (the card itself is the same). States: missing = sealed, "opening" =
    play the animation once, "open" = just show it."""
    key = f"envelope_{code}_{me['pid']}"
    st.markdown('<div class="kicker">Your card</div>', unsafe_allow_html=True)
    if key not in st.session_state:
        show(ui.envelope(me["name"], story=story))
        if st.button("Open your file", type="primary", use_container_width=True):
            st.session_state[key] = "opening"
            st.rerun()
        return
    animate = st.session_state[key] == "opening"
    st.session_state[key] = "open"            # the next redraw shows the file without animation
    show(ui.opened_file(me, animate, slam=stamp_slams_now(code, me)))


def stamp_slams_now(code, me):
    """True only the first time this browser session shows the open file, so the stamp
    lands once and stays still on every later redraw (the board polls every 2 seconds)."""
    key = f"stamp_{code}_{me['pid']}"
    if st.session_state.get(key):
        return False
    st.session_state[key] = True
    return True


REHEARSAL_LABEL = "Rehearsal mode: same case and culprit every time"
CASE_CHOICES = {     # what the host can play; the AI is only asked when the host picks "ai"
    "rehearsal": REHEARSAL_LABEL,
    "shuffled": "Case #001 with the roles shuffled",
    "ai": "A new case written by the AI",
}
CASE_HELP = ("Rehearsal mode plays case #001 with the same roles and clues every time, so a presentation "
             "can be rehearsed. With the roles shuffled, case #001 gets a new culprit. The AI writes a "
             "brand-new case for this room; that takes one to three minutes.")


def add_demo_suspect_button(code, token, full):
    if st.button("Add demo suspect", disabled=full,
                 help="A computer player for presentations. It plays by the same rules "
                      "and only knows its own card and the public evidence."):
        act(code, lambda g, on, now: logic.add_bot(g, token, now))


def case_choice(code, me):
    """The host picks the case. Returns (choice, waiting): waiting is True while an AI case
    the host asked for is not ready yet (Start waits for it, or the host switches back)."""
    has_ai = ai.settings(setting) is not None
    choices = ["rehearsal", "shuffled"] + (["ai"] if has_ai else [])
    choice = st.radio("Which case?", choices, index=1, format_func=CASE_CHOICES.get, help=CASE_HELP,
                      key=f"case-{code}")
    if not has_ai:
        st.caption("AI-written cases need an OpenRouter key (see the README).")
    if choice != "ai":
        return choice, False
    status = me.get("ai_status")
    if status is None:                                   # picked just now: start writing
        begin_ai_case(code)
        st.rerun()
    if status == "writing":
        st.info("The AI is writing your case … one to three minutes. You can switch to case #001 any time.")
        return choice, True
    if status == "failed":
        if st.button("Try again", key="ai-again"):
            begin_ai_case(code)
            st.rerun()
        return choice, True
    if st.button("Write a different AI case", key="ai-other"):
        begin_ai_case(code)
        st.rerun()
    return choice, False


def host_controls(code, token, public, me):
    if not me["is_host"]:
        return
    if me["host_note"]:
        st.caption(f"Host only: {me['host_note']}")
    if public["phase"] == "LOBBY":
        online = sum(1 for p in public["players"] if p["online"])
        url = base_url()
        if url:
            st.caption(f"Board for the projector: {url}/?room={code}&view=board")
        choice, waiting = case_choice(code, me)
        players = public["players"]
        full = len(players) >= logic.MAX_PLAYERS
        missing = logic.MIN_PLAYERS - online
        ready = logic.MIN_PLAYERS <= online <= logic.MAX_PLAYERS
        if not ready:
            if missing > 0:
                st.warning(f"{online} online – the game needs {logic.MIN_PLAYERS} to {logic.MAX_PLAYERS} "
                           f"players, so {missing} more. Let them join with the room code {code}, "
                           f"or click “Add demo suspect” to fill up with computer players.")
            else:
                st.warning(f"{online} online – at most {logic.MAX_PLAYERS} players can play. "
                           "Remove a player below.")
        if st.button("Start game", type="primary", disabled=not ready or waiting):
            rehearsal = choice == "rehearsal"
            seed = logic.DEMO_SEED if rehearsal else None
            act(code, lambda g, on, now: logic.start(g, token, on, now, seed=seed, fixed_case=rehearsal,
                                                     use_ai=choice == "ai"))
        # "Add demo suspect" is rendered exactly once per run: in plain sight while players
        # are missing, otherwise folded into the expander (and not at all once the room is full).
        if missing > 0:
            add_demo_suspect_button(code, token, full)
        others = [p["pid"] for p in players if p["pid"] != me["pid"]]
        can_add = missing <= 0 and not full
        if can_add or others:
            title = "Add or remove players" if can_add else "Remove a player"
            with st.expander(f"{title} ({len(players)} of {logic.MAX_PLAYERS})"):
                if can_add:
                    add_demo_suspect_button(code, token, full)
                if others:
                    victim = st.selectbox("Player", others, key="kick_target",
                                          format_func=lambda pid: name_of(public, pid))
                    if st.button("Remove from room"):
                        act(code, lambda g, on, now: logic.kick(g, token, victim, now))
    elif public["phase"] in logic.DURATIONS:
        if st.button("End phase (host)"):
            act(code, lambda g, on, now: logic.end_phase(g, token, on, now))


# ---------------------------------------------------------------- the move, step by step
#
# Every tap on the phone (an action card, a pin, a player row, an evidence chip, a clue)
# is a link: the page reloads with ?step=...&place=... . handle_move_links copies those
# parameters into session_state["move"] and removes them from the address at once.
# Every link carries the whole selection, so nothing gets lost on the reload.

MOVE_STEPS = ("search", "share", "plant", "vote")
MOVE_KEYS = ("place", "clue", "blame", "accuse")
NUMBER_KEYS = ("blame", "accuse")


def move_link(code, token, move):
    """The link for a selection. move: {"step": ..., "place": ..., ...}; {} = choose an action."""
    params = {"room": code, "t": token, "step": move.get("step") or "home"}
    params.update({key: move[key] for key in MOVE_KEYS if move.get(key) is not None})
    return "?" + urlencode(params)


def handle_move_links():
    if "step" not in st.query_params:
        return
    move = {}
    step = st.query_params.get("step")
    if step in MOVE_STEPS:
        move["step"] = step
        for key in MOVE_KEYS:
            value = st.query_params.get(key)
            if not value:
                continue
            if key in NUMBER_KEYS:
                try:
                    value = int(value)
                except ValueError:
                    continue
            move[key] = value
    for key in ("step",) + MOVE_KEYS:
        if key in st.query_params:
            del st.query_params[key]
    st.session_state["move"] = move


def choose_action(code, token, public, me):
    """'Your move.': two big cards (three for the murderer while planting is possible).
    Interrogations are not a move in the app: the players question each other out loud."""
    open_places = sum(1 for p in public["map"]["places"] if p["state"] == "open")
    unshared = sum(1 for c in me["clues"] if not c["shared"])
    cards = [
        {"href": move_link(code, token, {"step": "search"}) if open_places else None, "icon": "search",
         "title": "Search a place", "text": "Look for evidence somewhere on campus.",
         "info": f"{open_places} place{'s' if open_places != 1 else ''} open" if open_places else "Nothing open"},
        {"href": move_link(code, token, {"step": "share"}) if unshared else None, "icon": "share",
         "title": "Share a clue", "text": "Reveal one of your private clues to everyone.",
         "info": f"{unshared} private clue{'s' if unshared != 1 else ''}" if unshared else "All shared"},
    ]
    if open_places or unshared:
        show(ui.step_head("Your move.", "One action per round. Choose wisely."))
    else:
        show(ui.step_head("Nothing left to search or share.",
                          "The round goes on without you. Question the others out loud."))
    if me["can_plant"]:
        cards.append(plant_card(code, token))
    show(ui.action_cards(cards))
    show('<div class="hint">Interrogations happen face to face: ask, accuse, defend your alibi.</div>')


def plant_card(code, token):
    return {"href": move_link(code, token, {"step": "plant"}), "icon": "plant", "css": "dark",
            "title": "Plant a false clue", "text": "Once per game. Does not use your move.",
            "info": "Only you see this"}


def search_step(code, token, public, me, move):
    show(ui.back_link(move_link(code, token, {})))
    show(ui.step_head("Search a place", "Tap a red pin on the campus plan."))
    places = {p["name"]: p for p in public["map"]["places"]}
    place = move.get("place") if move.get("place") in places else None
    links = {name: move_link(code, token, {"step": "search", "place": name}) for name in places}
    show(ui.campus_map(public["searched"], story=public["story"], view=public["map"],
                       links=links, selected=place))
    found = [e for e in public["log"] if e["kind"] == "search" and e.get("location") == place]
    show(ui.place_card(place, places.get(place), found, story=public["story"]))
    sealed = me["puzzles"].get(place)
    if sealed and places[place]["state"] == "open":
        show(minigame_ui.sealed_line(sealed))
    if (place and places[place]["state"] == "open"
            and st.button(f"Search {ui.md(place)}", type="primary", use_container_width=True)):
        if sealed:      # the clue is sealed: open its mini-game first
            st.session_state["move"] = dict(move, play=place)
            st.rerun()
        act(code, lambda g, on, now: logic.search(g, token, place, now))


# ---------------------------------------------------------------- evidence mini-games

def mg_renderer(name="nova_minigame"):
    """The mini-game component (registered once per server process)."""
    v2 = getattr(getattr(st, "components", None), "v2", None)
    if v2 is None:
        return None
    cache = minigame_ui.RENDERERS
    key = (id(v2), name)
    if key not in cache:
        if name == "nova_chime":
            cache[key] = v2.component(name, js=minigame_ui.CHIME_JS)
        else:
            cache[key] = v2.component(name, css=minigame_ui.COMPONENT_CSS, js=minigame_ui.COMPONENT_JS)
    return cache[key]


def _ignore():
    pass


def evidence_progress(public):
    places = public["map"]["places"]
    return sum(1 for p in places if p["state"] == "done"), len(places)


def pending_reward(code, public):
    """'ACCESS GRANTED' after a solved exhibit. Stays until Continue, also when the round or
    the phase has moved on in the meantime. Returns True while it is shown."""
    reward = st.session_state.get("reward")
    if not reward or reward.get("code") != code:
        return False
    spec = reward["spec"]
    entry = next((e for e in public["log"] if e["kind"] == "search" and e.get("location") == spec["location"]), None)
    if entry is None:
        st.session_state.pop("reward", None)
        return False
    done, total = evidence_progress(public)
    show(minigame_ui.reward(spec, entry["text"], entry["id"], done, total, reward["celebrate"]))
    if reward["celebrate"]:
        reward["celebrate"] = False                   # the big moment plays once
        chime = mg_renderer("nova_chime")
        if chime is not None:
            chime(key=f"chime-{code}-{entry['id']}", data={"id": f"{code}-{entry['id']}"})
    if st.button("Continue ▸", key="reward-continue", type="primary", use_container_width=True):
        st.session_state.pop("reward", None)
        st.session_state["move"] = {}
        st.rerun()
    return True


def puzzle_step(code, token, public, me, move):
    """A sealed exhibit: solve the mini-game, and the search happens (logic checks the proof)."""
    place = move["play"]
    spec = me["puzzles"].get(place)
    show(ui.back_link(move_link(code, token, {"step": "search", "place": place})))
    state = next((p["state"] for p in public["map"]["places"] if p["name"] == place), None)
    if spec is None or state != "open":
        show(ui.step_head("Too late.", "Someone else searched this place first, or it is not open. "
                                       "Pick another pin on the map."))
        return
    done, total = evidence_progress(public)
    show(minigame_ui.puzzle_head(spec, done, total))
    puzzle_panel(code, token, spec)


@st.fragment
def puzzle_panel(code, token, spec):
    """The game itself. A fragment, so taps only redraw this part of the page."""
    key = f"{code}:{spec['id']}"
    state = st.session_state.setdefault("mg", {}).setdefault(
        key, {"seq": 0, "note": "", "hints": 0, "attempts": 0, "swaps": [], "opened": time.time()})
    renderer = mg_renderer()
    if renderer is None:
        st.warning("This puzzle cannot be shown here.")
        return
    data = {k: v for k, v in spec.items() if k != "hints"}
    data["state"] = {"seq": state["seq"], "note": state["note"], "swaps": state["swaps"]}
    result = renderer(key=f"mg-{key}", data=data, on_submit_change=_ignore, on_progress_change=_ignore)
    progress = getattr(result, "progress", None)
    if spec["kind"] == "puzzle" and isinstance(progress, list):
        state["swaps"] = progress[:minigames.MAX_SWAPS]
    proof = getattr(result, "submit", None)
    if isinstance(proof, dict):
        check_proof(code, token, spec, state, proof)
    puzzle_hints(key, spec, state)


def check_proof(code, token, spec, state, proof):
    """Python decides, never the phone: a wrong answer only costs an attempt. Wrong answers
    are limited per round (counted in the game), and an answer faster than a person could
    solve the puzzle is ignored."""
    with open_db() as conn:
        game = db.load(conn, code)
    if game is None:
        st.rerun()
    me = logic.private_view(game, token)
    location = spec["location"]
    if me is None:
        st.rerun()
    if logic.wrong_tries(game, me["pid"], location) >= logic.MAX_WRONG_TRIES:
        state["seq"] += 1
        state["note"] = "Too many wrong answers. The seal holds until the next round."
        st.rerun(scope="fragment")
    if time.time() - state.get("opened", 0) < minigames.MIN_SECONDS.get(spec["kind"], 0):
        state["seq"] += 1
        state["note"] = "Not so fast – take a proper look first."
        st.rerun(scope="fragment")
    if minigames.verify(game, location, proof):
        if attempt(code, lambda g, on, now: logic.search(g, token, spec["location"], now, proof=proof)):
            # Kept until the player taps Continue: the round may end the very same second.
            st.session_state["reward"] = {"code": code, "spec": spec, "celebrate": True}
            st.session_state.get("mg", {}).pop(f"{code}:{spec['id']}", None)
        st.rerun()
    attempt(code, lambda g, on, now: logic.note_wrong_try(g, token, location, now))
    state["attempts"] += 1
    state["seq"] += 1
    state["note"] = minigames.feedback(game, location, proof)
    st.rerun(scope="fragment")


def puzzle_hints(key, spec, state):
    texts = list(spec["hints"][:state["hints"]])
    if spec["kind"] == "puzzle" and len(texts) == 3:
        move = minigames.first_misplaced(spec, state["swaps"])
        texts[2] = (f"The piece now in slot {move[0]} belongs in slot {move[1]}." if move
                    else "Every piece is in place.")
    show(minigame_ui.hints(texts))
    used = state["hints"]
    if used < len(spec["hints"]):
        if state["attempts"] >= 2 and used == 0:
            st.caption("Stuck? A hint costs nothing but a little pride.")
        if st.button(f"💡 Hint {used + 1} of {len(spec['hints'])}", key=f"hint-{key}", use_container_width=True):
            state["hints"] = used + 1
            st.rerun(scope="fragment")


def share_step(code, token, public, me, move):
    show(ui.back_link(move_link(code, token, {})))
    show(ui.step_head("Share a clue", "Only you know these. Once shared, everyone sees it."))
    mine = {c["id"]: c for c in me["clues"]}
    clue = move.get("clue") if move.get("clue") in mine and not mine[move["clue"]]["shared"] else None
    show(ui.clue_cards([(None if c["shared"] else move_link(code, token, dict(move, clue=c["id"])),
                         number, c["text"], c["id"] == clue)
                        for number, c in enumerate(me["clues"], start=1)]))
    show('<div class="hint">Sharing builds trust. It can also point at someone else.</div>')
    if st.button("Share with everyone", type="primary", use_container_width=True):
        if clue is None:
            st.error("Choose a clue to share.")
        else:
            act(code, lambda g, on, now: logic.share(g, token, clue, now))


def plant_step(code, token, public, me, move):
    show(ui.back_link(move_link(code, token, {})))
    show(ui.step_head("Plant a false clue",
                      "It appears on the board exactly like a real search result. Does not use your move."))
    others = [p for p in public["players"] if p["pid"] != me["pid"]]
    blame = move.get("blame") if any(p["pid"] == move.get("blame") for p in others) else None
    place = move.get("place") if move.get("place") in me["plant_locations"] else None
    show(ui.label("Blame"))
    show(ui.pick_rows([(move_link(code, token, dict(move, blame=p["pid"])), p["name"], p.get("role"),
                        p["pid"] == blame) for p in others]))
    show(ui.label("Where"))
    show(ui.chips([(move_link(code, token, dict(move, place=name)), name, name == place)
                   for name in me["plant_locations"]]))
    if st.button("Plant it", type="primary", use_container_width=True):
        if blame is None:
            st.error("Choose who you want to blame.")
        elif place is None:
            st.error("Choose where to plant it.")
        else:
            st.session_state["move"] = {}
            act(code, lambda g, on, now: logic.plant(g, token, blame, place, now))


def move_made(code, token, public, me):
    """'Move made.': what you did this round, and who is still choosing."""
    show(ui.step_head("Move made."))
    last = me["last_move"]
    if last is None:
        show(ui.move_made("Move logged", "", "The next round starts when everybody has moved."))
    elif last["kind"] == "search" and me["puzzles"].get(last.get("location")):
        done, total = evidence_progress(public)
        show(minigame_ui.reward(me["puzzles"][last["location"]], last["text"], last["id"], done, total, False))
    elif last["kind"] == "search":
        show(ui.move_made(f"New evidence · {last.get('location', '')}", f"Exhibit {last['id']}", last["text"]))
    else:
        show(ui.move_made("Clue shared", f"Exhibit {last['id']}", last["text"]))
    show(ui.waiting_list(public["players"], me["pid"]))
    if me["can_plant"]:
        show(ui.action_cards([plant_card(code, token)]))


def investigation_actions(code, token, public, me):
    if pending_reward(code, public):
        return
    move = st.session_state.get("move") or {}
    if move and move.setdefault("round", public["map"]["round"]) != public["map"]["round"]:
        move = st.session_state["move"] = {}     # a new round starts with "Your move."
    step = move.get("step")
    if step == "plant" and me["can_plant"]:
        plant_step(code, token, public, me, move)
    elif me["acted"]:
        st.session_state["move"] = {}
        move_made(code, token, public, me)
    elif step == "search" and move.get("play"):
        puzzle_step(code, token, public, me, move)
    elif step == "search":
        search_step(code, token, public, me, move)
    elif step == "share":
        share_step(code, token, public, me, move)
    else:
        choose_action(code, token, public, me)


def vote_form(code, token, public, me):
    if me["voted"]:
        st.success("Your accusation is filed. Wait for the others.")
        return
    # Tap a suspect and, if you like, a place: the same cards and chips as during the rounds.
    # Nothing is chosen in advance, so a quick tap on "Vote" never accuses anybody by accident.
    move = st.session_state.get("move") or {}
    if move.get("step") != "vote":
        move = {"step": "vote"}
    others = [p for p in public["players"] if p["pid"] != me["pid"]]
    accused = move.get("accuse") if any(p["pid"] == move.get("accuse") for p in others) else None
    story = public["story"]
    scene = move.get("place") if move.get("place") in story["locations"] else None
    show(ui.step_head("Who did it?", "Name the right suspect for a win – and the right place for the full truth."))
    show(ui.pick_rows([(move_link(code, token, dict(move, accuse=p["pid"])), p["name"], p.get("role"),
                        p["pid"] == accused) for p in others]))
    show(ui.label(f"Where did {story['victim_short']} really die? · optional"))
    show(ui.chips([(move_link(code, token, dict(move, place=None if loc == scene else loc)), loc, loc == scene)
                   for loc in story["locations"]]))
    if st.button("Vote", type="primary", use_container_width=True):
        if accused is None:
            st.error("Choose who did it.")
        else:
            act(code, lambda g, on, now: logic.vote(g, token, accused, now, scene=scene))


def player_screen(code, token):
    handle_move_links()
    public, me = sync(code, token)
    if public is None:
        st.error(f"Room {code} does not exist.")
        return
    if me is None:
        st.error("You are not a player in this game.")
        if st.button("Open the board"):
            st.query_params.clear()
            st.query_params["room"] = code
            st.query_params["view"] = "board"
            st.rerun()
        return
    st.session_state["signature"] = signature(public, me)
    phase = public["phase"]
    play_case_intro(code, public)

    st.markdown(f'<div class="kicker">Room {ui.h(code)} · you are {ui.h(me["name"])}</div>',
                unsafe_allow_html=True)
    player_status(code, token)

    flash = st.session_state.pop("flash", None)
    if flash:
        st.error(flash)

    # Mobile first: in every phase, the thing you have to do or read right now comes first.
    # Your card follows (folded away once you have read it), then the suspects, then the evidence.
    if phase == "LOBBY":
        host_controls(code, token, public, me)   # the host's "Start game" is the main thing here
        if not me["is_host"]:
            st.info("Keep this page open. The host starts the game.")
        show(ui.sealed_file())
        player_suspects(code, me["pid"])         # who has joined so far
        show_rules(expanded=True)
    elif phase == "ABORTED":
        st.error(public["abort_reason"])
    elif phase == "RESULT":
        show_result(public)
    elif phase == "REVEAL":
        sealed_card(code, me, public["story"])
        st.info("Read your file. The investigation starts in a moment.")
    elif phase == "INVESTIGATION":
        investigation_actions(code, token, public, me)
        show_card(me, expanded=False)
    elif phase == "DISCUSSION":
        pending_reward(code, public)             # an exhibit solved in the very last second
        st.info("Talk to each other. Compare the alibis. Who is lying?")
        show_card(me, expanded=False)
    elif phase == "VOTE":
        vote_form(code, token, public, me)
        show_card(me, expanded=False)

    if phase in logic.DURATIONS:                 # REVEAL, INVESTIGATION, DISCUSSION, VOTE
        host_controls(code, token, public, me)   # "End phase" sits below the player's own move
        player_suspects(code, me["pid"])
    if phase != "RESULT":
        st.divider()
        player_log(code)


# ---------------------------------------------------------------- entry point

def main():
    st.set_page_config(page_title="NOVA MYSTERY", page_icon="🩸", layout="wide")
    show(ui.page_style())
    code = st.query_params.get("room", "").strip().upper()
    token = st.query_params.get("t", "")
    view = st.query_params.get("view", "")
    if not code:
        home_screen()
    elif not valid_code(code):
        # Never echo an unchecked code: it could carry links or other Markdown.
        show(ui.brand())
        st.error("This is not a valid room code.")
        if st.button("Back"):
            st.query_params.clear()
            st.rerun()
    elif view == "board":
        board_screen(code)
    elif token:
        player_screen(code, token)
    else:
        join_screen(code)


main()
