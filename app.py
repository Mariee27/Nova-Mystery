"""Screens of Murder at NOVA (Streamlit).

This file only shows things and passes clicks on. All rules are in logic.py,
all storage is in db.py.

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

DB_PATH = os.environ.get("MURDER_DB", "data/murder.db")
POLL_SECONDS = 2   # every open screen asks for the current state this often

PHASE_TITLES = {
    "LOBBY": "Lobby – waiting for players",
    "REVEAL": "Read your card",
    "INVESTIGATION": "Investigation – one action each",
    "DISCUSSION": "Discussion – talk to each other",
    "VOTE": "Vote – who did it?",
    "RESULT": "Case closed",
    "ABORTED": "Game stopped",
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
        online = logic.online_ids(db.presence(conn, code), now)
        # Only write when the timers really change something.
        if logic.tick(game, online, now) is not game:
            game = db.apply(conn, code, lambda g: logic.tick(g, online, now))
        return logic.public_view(game, online), logic.private_view(game, token)


def act(code, action):
    """Run one action. action(game, online, now) -> game. Rejections are shown to the player."""
    now = time.time()
    try:
        with open_db() as conn:
            online = logic.online_ids(db.presence(conn, code), now)
            db.apply(conn, code, lambda g: action(g, online, now))
    except logic.Rejected as problem:
        st.session_state["flash"] = str(problem)
    st.rerun()


def esc(text):
    """Show user text literally: no HTML, no Markdown."""
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for ch in "\\`*_{}[]()#+-.!|~$:":
        text = text.replace(ch, "\\" + ch)
    return text


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
    left = seconds_left(public)
    st.subheader(PHASE_TITLES[public["phase"]])
    if left is not None:
        total = logic.DURATIONS[public["phase"]]
        st.progress(min(1.0, left / total), text=f"{left} s left")


def show_players(public):
    lines = []
    for player in public["players"]:
        dot = "🟢" if player["online"] else "⚪ offline"
        marks = ""
        if player["is_host"]:
            marks += " · host"
        if public["phase"] == "INVESTIGATION" and player["acted"]:
            marks += " · acted"
        if public["phase"] == "VOTE" and player["voted"]:
            marks += " · voted"
        role = f" – {esc(player['role'])}" if player["role"] else ""
        lines.append(f"- {dot} **{esc(player['name'])}**{role}{marks}")
    st.markdown("\n".join(lines) if lines else "_Nobody has joined yet._")


def show_log(public):
    if not public["log"]:
        st.caption("Nothing has been found yet.")
        return
    for entry in reversed(public["log"]):
        text = esc(entry["text"])
        if entry["kind"] == "search":
            fake = " _(planted by the murderer)_" if entry.get("planted") else ""
            st.markdown(f"🔎 **Evidence at {esc(entry['location'])}:** {text}{fake}")
        elif entry["kind"] == "share":
            st.markdown(f"📣 **{esc(name_of(public, entry['by']))} shares a clue:** {text}")
        elif entry["kind"] == "question":
            st.markdown(
                f"❓ **{esc(name_of(public, entry['by']))} asks "
                f"{esc(name_of(public, entry['target']))}** (#{entry['id']}): {text}")
        elif entry["kind"] == "answer":
            st.markdown(
                f"💬 **{esc(name_of(public, entry['by']))} answers** "
                f"(#{entry['question_id']}): {text}")
        else:
            st.markdown(f"ℹ️ {text}")


def show_result(public):
    result = public["result"]
    murderer_name = name_of(public, result["murderer"])
    role = next(c["role"] for c in public["characters"] if c["pid"] == result["murderer"])
    if result["winner"] == "detectives":
        st.success(f"The detectives win! It was {murderer_name} ({role}).")
    else:
        st.error(f"The murderer got away. It was {murderer_name} ({role}).")
    st.write(f"Scene of the crime: **{result['murder_location']}**, 21:30.")
    st.markdown("**Votes**")
    for player in public["players"]:
        st.markdown(f"- {esc(player['name'])}: {result['tally'].get(str(player['pid']), 0)}")
    st.markdown("**All cards**")
    for character in public["characters"]:
        with st.expander(f"{character['name']} – {character['role']}"):
            st.write(f"Said: {character['alibi']}")
            st.write(f"Really was at: {character['true_location']}")
            if character["secret"]:
                kept = character["pid"] in result["secrets_kept"]
                st.write(f"Secret: {character['secret']}")
                st.write("Secret kept ✅" if kept else "Secret came out ❌")
            for clue in character["clues"]:
                st.write(f"Clue: {clue['text']}")


# ---------------------------------------------------------------- home and join

def home_screen():
    st.title("Murder at NOVA")
    st.write("A five-minute murder mystery for 4 to 6 players.")
    if st.button("Create room", type="primary"):
        with open_db() as conn:
            code = db.create_room(conn, time.time())
        st.query_params["room"] = code
        st.query_params["view"] = "board"
        st.rerun()
    st.divider()
    with st.form("goto"):
        code = st.text_input("Room code", max_chars=4)
        if st.form_submit_button("Join room"):
            st.query_params["room"] = code.strip().upper()
            st.rerun()


def join_screen(code):
    public, _ = sync(code)
    st.title("Murder at NOVA")
    if public is None:
        st.error(f"Room {code} does not exist.")
        if st.button("Back"):
            st.query_params.clear()
            st.rerun()
        return
    st.write(f"Room **{code}**")
    if public["phase"] != "LOBBY":
        st.warning("This game has already started. You can watch on the board.")
        if st.button("Open the board"):
            st.query_params["view"] = "board"
            st.rerun()
        return
    with st.form("join"):
        name = st.text_input("Your name", max_chars=logic.MAX_NAME)
        submitted = st.form_submit_button("Join", type="primary")
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
    left, right = st.columns([1, 2])
    with left:
        st.metric("Room code", code)
        if public["phase"] == "LOBBY":
            url = base_url()
            if url:
                link = f"{url}/?room={code}"
                try:
                    import qrcode
                    picture = io.BytesIO()
                    qrcode.make(link).save(picture, format="PNG")
                    st.image(picture.getvalue(), width=260)
                except ImportError:
                    pass
                st.caption(link)
            else:
                st.caption("Open this app on your phone and enter the room code.")
        st.markdown("**Players**")
        show_players(public)
    with right:
        show_phase(public)
        if public["phase"] == "ABORTED":
            st.error(public["abort_reason"])
        if public["phase"] == "RESULT":
            show_result(public)
        st.markdown("**Public log**")
        show_log(public)


def board_screen(code):
    st.title("Murder at NOVA")
    board_live(code)


# ---------------------------------------------------------------- player (phone)

def signature(public, me):
    """Changes whenever the buttons on the phone have to change."""
    return (public["phase"], me["acted"], me["voted"], me["is_host"], me["can_plant"],
            tuple(q["id"] for q in me["open_questions"]))


@st.fragment(run_every=POLL_SECONDS)
def player_status(code, token):
    public, me = sync(code, token)
    if public is None or me is None:
        st.rerun()
    show_phase(public)
    show_players(public)
    if signature(public, me) != st.session_state.get("signature"):
        st.rerun()   # redraw the whole page so that the right buttons appear


@st.fragment(run_every=POLL_SECONDS)
def player_log(code):
    with open_db() as conn:
        game = db.load(conn, code)
        online = logic.online_ids(db.presence(conn, code), time.time())
    if game is not None:
        st.markdown("**Public log**")
        show_log(logic.public_view(game, online))


def show_card(me):
    with st.expander(f"Your card: {me['role']}", expanded=me["phase"] == "REVEAL"):
        st.write(me["intro"])
        if me["is_murderer"]:
            st.error("You did it. Do not get caught. Your cover story: " + me["alibi"])
        else:
            st.write("Your alibi: " + me["alibi"])
            st.warning("Your secret: " + me["secret"])
        for clue in me["clues"]:
            shared = " (shared)" if clue["shared"] else ""
            st.info("Only you know" + shared + ": " + clue["text"])


def host_controls(code, token, public, me):
    if not me["is_host"]:
        return
    if public["phase"] == "LOBBY":
        online = sum(1 for p in public["players"] if p["online"])
        demo = st.checkbox("Use the fixed demo case")
        ready = logic.MIN_PLAYERS <= online <= logic.MAX_PLAYERS
        if not ready:
            st.caption(f"{online} online. The game needs "
                       f"{logic.MIN_PLAYERS} to {logic.MAX_PLAYERS} players.")
        if st.button("Start game", type="primary", disabled=not ready):
            seed = logic.DEMO_SEED if demo else None
            act(code, lambda g, on, now: logic.start(g, token, on, now, seed=seed))
    elif public["phase"] in logic.DURATIONS:
        if st.button("End phase (host)"):
            act(code, lambda g, on, now: logic.end_phase(g, token, on, now))


def answer_forms(code, token, public, me):
    for asked in me["open_questions"]:
        with st.form(f"answer_{asked['id']}", clear_on_submit=True):
            st.markdown(f"**{esc(name_of(public, asked['by']))} asks you:** {esc(asked['text'])}")
            text = st.text_input("Your answer (you may lie)", max_chars=logic.MAX_TEXT)
            if st.form_submit_button("Answer"):
                question_id = asked["id"]
                act(code, lambda g, on, now: logic.answer(g, token, question_id, text, now))


def investigation_actions(code, token, public, me):
    others = [p["pid"] for p in public["players"] if p["pid"] != me["pid"]]
    label = lambda pid: player_label(public, pid)
    if me["acted"]:
        st.success("You have used your action. Watch the log.")
    else:
        st.write("Pick **one** action:")
        tab_search, tab_question, tab_share = st.tabs(["Search", "Question", "Share a clue"])
        with tab_search:
            free = [loc for loc in content.LOCATIONS if loc not in public["searched"]]
            if free:
                location = st.selectbox("Location", free)
                st.caption(content.LOCATION_FLAVOR[location])
                if st.button("Search this location", type="primary"):
                    act(code, lambda g, on, now: logic.search(g, token, location, now))
            else:
                st.caption("Every location has been searched.")
        with tab_question:
            with st.form("question", clear_on_submit=True):
                target = st.selectbox("Ask", others, format_func=label)
                text = st.text_input("Your question", max_chars=logic.MAX_TEXT)
                if st.form_submit_button("Ask in public"):
                    act(code, lambda g, on, now:
                        logic.question(g, token, target, text, now))
        with tab_share:
            mine = {c["id"]: c["text"] for c in me["clues"] if not c["shared"]}
            if mine:
                clue_id = st.selectbox("Clue", list(mine), format_func=mine.get)
                if st.button("Make this clue public"):
                    act(code, lambda g, on, now: logic.share(g, token, clue_id, now))
    if me["can_plant"]:
        with st.expander("Plant a false clue (once per game, does not use your action)"):
            victim = st.selectbox("Blame", others, format_func=label, key="plant_target")
            place = st.selectbox("Where", content.LOCATIONS, key="plant_place")
            if st.button("Plant it"):
                act(code, lambda g, on, now: logic.plant(g, token, victim, place, now))


def vote_form(code, token, public, me):
    if me["voted"]:
        st.success("Your vote is in.")
        return
    others = [p["pid"] for p in public["players"] if p["pid"] != me["pid"]]
    suspect = st.selectbox("Who did it?", others,
                           format_func=lambda pid: player_label(public, pid))
    if st.button("Vote", type="primary"):
        act(code, lambda g, on, now: logic.vote(g, token, suspect, now))


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

    st.caption(f"Room {code} · you are {me['name']}")
    player_status(code, token)

    flash = st.session_state.pop("flash", None)
    if flash:
        st.error(flash)

    host_controls(code, token, public, me)

    if phase == "LOBBY":
        st.info("Keep this page open. The host starts the game.")
    elif phase == "ABORTED":
        st.error(public["abort_reason"])
    elif phase == "RESULT":
        show_result(public)
    else:
        show_card(me)
        if phase == "REVEAL":
            st.info("Read your card. The investigation starts in a moment.")
        if phase == "INVESTIGATION":
            investigation_actions(code, token, public, me)
        if phase in ("INVESTIGATION", "DISCUSSION"):
            answer_forms(code, token, public, me)
        if phase == "DISCUSSION":
            st.info("Talk to each other. Who is lying?")
        if phase == "VOTE":
            vote_form(code, token, public, me)

    st.divider()
    player_log(code)


# ---------------------------------------------------------------- entry point

def main():
    st.set_page_config(page_title="Murder at NOVA", page_icon="🔎")
    code = st.query_params.get("room", "").strip().upper()
    token = st.query_params.get("t", "")
    view = st.query_params.get("view", "")
    if not code:
        home_screen()
    elif view == "board":
        board_screen(code)
    elif token:
        player_screen(code, token)
    else:
        join_screen(code)


main()
