"""Screens of NOVA MYSTERY (Streamlit).

This file only shows things and passes clicks on. All rules are in logic.py,
all storage is in db.py, all HTML building blocks are in ui.py.

Three kinds of screens, chosen by the link:
  ?room=CODE&view=board   the projector board (public data only)
  ?room=CODE&t=TOKEN      one player's phone
  ?room=CODE              the join form
"""

import io
import os
import time
from contextlib import contextmanager

import streamlit as st

import content
import db
import logic
import ui

DB_PATH = os.environ.get("MURDER_DB", "data/murder.db")
POLL_SECONDS = 2   # every open screen asks for the current state this often

PHASE_TITLES = {
    "LOBBY": "Lobby – the suspects arrive",
    "REVEAL": "Read your file",
    "INVESTIGATION": "Investigation – one action each",
    "DISCUSSION": "Discussion – who is lying?",
    "VOTE": "The final accusation",
    "RESULT": "Case closed",
    "ABORTED": "Investigation suspended",
}

PHASE_SUBTITLES = {
    "LOBBY": "Scan the code or enter the room code on your phone. 4 to 6 suspects.",
    "REVEAL": "Every phone now holds a private file. One of you is lying about everything.",
    "INVESTIGATION": "Search a location, interrogate a suspect, or share what you know. One move only.",
    "DISCUSSION": "Answer the open questions. Compare the alibis. Everybody may lie.",
    "VOTE": "Name the suspect – and the place where Vale really died.",
    "RESULT": "",
    "ABORTED": "",
}


# ---------------------------------------------------------------- plumbing

@contextmanager
def open_db():
    conn = db.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def sync(code, token=None):
    """Heartbeat, timers, and the current views. Returns (public, private) or (None, None)."""
    now = time.time()
    with open_db() as conn:
        game = db.load(conn, code)
        if game is None:
            return None, None
        me = logic.private_view(game, token)
        if me is not None:
            db.heartbeat(conn, code, me["pid"], now)
        online = logic.with_bots(game, logic.online_ids(db.presence(conn, code), now))

        def step(g):   # timers first, then whatever the demo suspects have to do
            return logic.bot_moves(logic.tick(g, online, now), now)

        # Only write when the timers or the bots really change something.
        if step(game) is not game:
            game = db.apply(conn, code, step)
        return logic.public_view(game, online), logic.private_view(game, token)


def act(code, action):
    """Run one action. action(game, online, now) -> game. Rejections are shown to the player."""
    now = time.time()
    try:
        with open_db() as conn:
            presence = db.presence(conn, code)
            db.apply(conn, code, lambda g: action(
                g, logic.with_bots(g, logic.online_ids(presence, now)), now))
    except logic.Rejected as problem:
        st.session_state["flash"] = str(problem)
    st.rerun()


def show(html):
    """Show an HTML block from ui.py (all text in it is already escaped)."""
    st.markdown(html, unsafe_allow_html=True)


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


def player_label(public, pid):
    for player in public["players"]:
        if player["pid"] == pid:
            if player["role"]:
                return f"{player['name']} – {player['role']}"
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


# ---------------------------------------------------------------- shared pieces

def show_phase(public):
    phase = public["phase"]
    show(ui.banner(PHASE_TITLES[phase], PHASE_SUBTITLES.get(phase, "")))
    left = seconds_left(public)
    if left is not None:
        show(ui.timer(left, logic.DURATIONS[phase]))


def show_rules(expanded=False):
    with st.expander("How to play", expanded=expanded):
        st.markdown(content.HOW_TO_PLAY)


def show_players(public):
    show(ui.suspects(public["players"], public["phase"]))


def show_log(public):
    if not public["log"]:
        st.caption("Nothing has been found yet.")
        return
    by_id = {entry["id"]: entry for entry in public["log"]}
    # Oldest first: a new entry is added at the bottom and only that card animates in.
    for entry in public["log"]:
        show(ui.log_entry(entry, lambda pid: name_of(public, pid), by_id))


def show_result(public):
    result = public["result"]
    characters = public["characters"]
    who = lambda pid: name_of(public, pid)   # noqa: E731
    show(ui.reveal(result, characters, who))
    left, right = st.columns([3, 2])
    with left:
        st.markdown("### Reconstruction of the night")
        show(ui.reconstruction(result, characters, who))
        st.markdown("### Every alibi, checked")
        show(ui.alibi_table(result, characters, who))
    with right:
        st.markdown("### Who the room accused")
        labels = [(str(p["pid"]), p["name"]) for p in public["players"]]
        show(ui.bars(result["tally"], labels, hit=str(result["murderer"])))
        st.markdown("### Where it happened")
        places = [(loc, loc) for loc in content.LOCATIONS]
        show(ui.bars(result.get("scene_tally", {}), places, hit=result["murder_location"]))
        show(ui.campus_map(public["searched"], scene=result["murder_location"]))
    st.markdown("### The evidence, re-examined")
    st.caption("Now that the case is closed, every exhibit shows how reliable it really was.")
    show_log(public)


# ---------------------------------------------------------------- home and join

def home_screen():
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
        show(ui.case_file())
    with right:
        st.markdown("#### Open the investigation")
        st.caption("One screen becomes the board (a laptop or projector). "
                   "Everybody else joins on their phone.")
        if st.button("Create room", type="primary", use_container_width=True):
            try:
                with open_db() as conn:
                    code = db.create_room(conn, time.time())
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
    token = logic.new_token()
    now = time.time()
    try:
        with open_db() as conn:
            code = db.create_room(conn, now)
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
    st.markdown(f'<div class="kicker">Room {ui.h(code)} · Case #{content.CASE_NUMBER}</div>',
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
    phase = public["phase"]
    show_phase(public)
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
    left, right = st.columns([2, 3])
    with left:
        st.markdown('<div class="kicker">Campus map</div>', unsafe_allow_html=True)
        show(ui.campus_map(public["searched"]))
        st.markdown(f'<div class="place">{ui.h(content.BRIEFING)}</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="kicker">Evidence wall</div>', unsafe_allow_html=True)
        # The board shows the log as a cork board; phones keep the simple list (show_log).
        show(ui.evidence_wall(public["log"], lambda pid: name_of(public, pid)))


def board_screen(code):
    show(ui.brand())
    st.markdown(f'<div class="kicker">Case #{content.CASE_NUMBER} · {ui.h(content.CASE_TITLE)} · '
                f'Room {ui.h(code)}</div>', unsafe_allow_html=True)
    board_live(code)


# ---------------------------------------------------------------- player (phone)

def signature(public, me):
    """Changes whenever the buttons on the phone have to change: also when new evidence
    arrives, so that the search list and the 'confront with evidence' list stay current."""
    evidence = sum(1 for e in public["log"] if e["kind"] in logic.EVIDENCE_KINDS)
    return (public["phase"], me["acted"], me["voted"], me["is_host"], me["can_plant"],
            tuple(q["id"] for q in me["open_questions"]), evidence)


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
        game = db.load(conn, code)
        online = logic.online_ids(db.presence(conn, code), time.time())
    if game is not None:
        public = logic.public_view(game, logic.with_bots(game, online))
        st.markdown('<div class="kicker">The suspects</div>', unsafe_allow_html=True)
        show(ui.suspect_list(public["players"], public["phase"], my_pid))


@st.fragment(run_every=POLL_SECONDS)
def player_log(code):
    with open_db() as conn:
        game = db.load(conn, code)
        online = logic.online_ids(db.presence(conn, code), time.time())
    if game is not None:
        st.markdown('<div class="kicker">Evidence &amp; statements</div>', unsafe_allow_html=True)
        show_log(logic.public_view(game, online))


def show_card(me, expanded):
    with st.expander(f"Your card: {me['role']}", expanded=expanded):
        show(ui.dossier(me))


def sealed_card(code, me):
    """REVEAL: first a sealed envelope, the file only after "Open your file".
    session_state remembers the envelope per room and player, so a page refresh never seals it
    again. States: missing = sealed, "opening" = play the animation once, "open" = just show it."""
    key = f"envelope_{code}_{me['pid']}"
    st.markdown('<div class="kicker">Your card</div>', unsafe_allow_html=True)
    if key not in st.session_state:
        show(ui.envelope(me["name"]))
        if st.button("Open your file", type="primary", use_container_width=True):
            st.session_state[key] = "opening"
            st.rerun()
        return
    animate = st.session_state[key] == "opening"
    st.session_state[key] = "open"            # the next redraw shows the file without animation
    show(ui.opened_file(me, animate))


def host_controls(code, token, public, me):
    if not me["is_host"]:
        return
    if public["phase"] == "LOBBY":
        online = sum(1 for p in public["players"] if p["online"])
        url = base_url()
        if url:
            st.caption(f"Board for the projector: {url}/?room={code}&view=board")
        demo = st.checkbox("Use the fixed demo case",
                           help="Presentation mode: always the same case, so a demo can be rehearsed.")
        ready = logic.MIN_PLAYERS <= online <= logic.MAX_PLAYERS
        if not ready:
            st.caption(f"{online} online. The game needs "
                       f"{logic.MIN_PLAYERS} to {logic.MAX_PLAYERS} players.")
        if st.button("Start game", type="primary", disabled=not ready):
            seed = logic.DEMO_SEED if demo else None
            act(code, lambda g, on, now: logic.start(g, token, on, now, seed=seed))
        full = len(public["players"]) >= logic.MAX_PLAYERS
        if st.button("Add demo suspect", disabled=full,
                     help="A computer player for presentations. It plays by the same rules "
                          "and only knows its own card and the public evidence."):
            act(code, lambda g, on, now: logic.add_bot(g, token, now))
        others = [p["pid"] for p in public["players"] if p["pid"] != me["pid"]]
        if others:
            with st.expander("Remove a player"):
                victim = st.selectbox("Player", others, key="kick_target",
                                      format_func=lambda pid: name_of(public, pid))
                if st.button("Remove from room"):
                    act(code, lambda g, on, now: logic.kick(g, token, victim, now))
    elif public["phase"] in logic.DURATIONS:
        if st.button("End phase (host)"):
            act(code, lambda g, on, now: logic.end_phase(g, token, on, now))


def answer_forms(code, token, public, me):
    by_id = {entry["id"]: entry for entry in public["log"]}
    for asked in me["open_questions"]:
        with st.form(f"answer_{asked['id']}", clear_on_submit=True):
            entry = by_id.get(asked["id"], dict(asked, kind="question", target=me["pid"]))
            show(ui.log_entry(entry, lambda pid: name_of(public, pid), by_id))
            text = st.text_input("Your answer (you may lie)", max_chars=logic.MAX_TEXT)
            if st.form_submit_button("Answer"):
                question_id = asked["id"]
                act(code, lambda g, on, now: logic.answer(g, token, question_id, text, now))


def evidence_options(public):
    """Public exhibits a player can confront someone with. None means: no evidence."""
    exhibits = {e["id"]: e["text"] for e in public["log"] if e["kind"] in logic.EVIDENCE_KINDS}
    label = lambda eid: "No evidence – just ask" if eid is None else (   # noqa: E731
        f"Exhibit {eid}: {exhibits[eid][:70]}{'…' if len(exhibits[eid]) > 70 else ''}")
    return [None] + list(exhibits), label


def investigation_actions(code, token, public, me):
    others = [p["pid"] for p in public["players"] if p["pid"] != me["pid"]]
    label = lambda pid: player_label(public, pid)   # noqa: E731
    if me["acted"]:
        st.success("You have made your move. Watch the evidence come in.")
    else:
        st.markdown('<div class="kicker">Your move – pick one</div>', unsafe_allow_html=True)
        tab_search, tab_question, tab_share = st.tabs(["Search", "Interrogate", "Share a clue"])
        with tab_search:
            free = [loc for loc in content.LOCATIONS if loc not in public["searched"]]
            if free:
                location = st.selectbox(
                    "Location", free,
                    format_func=lambda loc: f"{content.LOCATION_ICONS.get(loc, '')} {loc}")
                st.markdown(f'<div class="place">{ui.h(content.LOCATION_FLAVOR[location])}</div>',
                            unsafe_allow_html=True)
                if st.button("Search this location", type="primary"):
                    act(code, lambda g, on, now: logic.search(g, token, location, now))
            else:
                st.caption("Every location has been searched.")
        with tab_question:
            with st.form("question", clear_on_submit=True):
                target = st.selectbox("Ask", others, format_func=label)
                options, evidence_label = evidence_options(public)
                evidence = st.selectbox("Confront with evidence (optional)", options,
                                        format_func=evidence_label)
                text = st.text_input("Your question", max_chars=logic.MAX_TEXT,
                                     placeholder="Where were you at 23:30?")
                if st.form_submit_button("Ask in public"):
                    act(code, lambda g, on, now:
                        logic.question(g, token, target, text, now, evidence_id=evidence))
        with tab_share:
            mine = {c["id"]: c["text"] for c in me["clues"] if not c["shared"]}
            if mine:
                clue_id = st.selectbox("Clue", list(mine), format_func=mine.get)
                if st.button("Make this clue public"):
                    act(code, lambda g, on, now: logic.share(g, token, clue_id, now))
            else:
                st.caption("You have already shared everything you know.")
    if me["can_plant"]:
        with st.expander("Plant a false clue (once per game, does not use your action)"):
            st.caption("It appears on the board exactly like a real search result.")
            victim = st.selectbox("Blame", others, format_func=label, key="plant_target")
            place = st.selectbox("Where", me["plant_locations"], key="plant_place")
            if st.button("Plant it"):
                act(code, lambda g, on, now: logic.plant(g, token, victim, place, now))


def vote_form(code, token, public, me):
    if me["voted"]:
        st.success("Your accusation is filed. Wait for the others.")
        return
    others = [p["pid"] for p in public["players"] if p["pid"] != me["pid"]]
    suspect = st.selectbox("Who did it?", others,
                           format_func=lambda pid: player_label(public, pid))
    scene = st.selectbox("Where did Vale really die?", [None] + content.LOCATIONS,
                         format_func=lambda loc: "Not sure" if loc is None else loc)
    st.caption("Name the right suspect for a win – and the right place for the full truth.")
    if st.button("Vote", type="primary"):
        act(code, lambda g, on, now: logic.vote(g, token, suspect, now, scene=scene))


def player_screen(code, token):
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
        st.info("Keep this page open. The host starts the game.")
        player_suspects(code, me["pid"])         # who has joined so far
        show(ui.case_file())
        show_rules(expanded=True)
    elif phase == "ABORTED":
        st.error(public["abort_reason"])
    elif phase == "RESULT":
        show_result(public)
    elif phase == "REVEAL":
        sealed_card(code, me)
        st.info("Read your file. The investigation starts in a moment.")
    elif phase == "INVESTIGATION":
        investigation_actions(code, token, public, me)
        answer_forms(code, token, public, me)
        show_card(me, expanded=False)
    elif phase == "DISCUSSION":
        answer_forms(code, token, public, me)
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
