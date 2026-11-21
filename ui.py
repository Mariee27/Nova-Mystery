"""HTML building blocks for the NOVA MYSTERY screens.

Every function here is pure: it gets plain data and returns an HTML string.
No Streamlit, no database. app.py shows the strings with st.markdown(..., unsafe_allow_html=True).

Safety rule: every piece of text that goes into the HTML passes through h() first,
so names and other text typed by players are always shown as plain text.
The strings never contain blank lines, so Markdown never touches the HTML.

Functions that show story texts take the public story of the game (logic.story_view).
Without one they show case #001.
"""

import html
import pathlib
import re

import content
import logic

STYLE_FILE = pathlib.Path(__file__).with_name("style.css")


def h(text):
    """Escape text for HTML. '$' is escaped too, so Streamlit never reads it as math."""
    return html.escape(str(text), quote=True).replace("$", "&#36;")


def page_style():
    return "<style>" + STYLE_FILE.read_text(encoding="utf-8") + "</style>"


def _story(story):
    return story if story is not None else logic.public_story(content.DEFAULT_STORY)


def initial(name):
    name = str(name).strip()
    return h(name[0].upper()) if name else "?"


# ---------------------------------------------------------------- intro and case file

def brand():
    return ('<div class="brand"><div class="title">NOVA <b>MYSTERY</b></div>'
            f'<div class="tag">{h(content.TAGLINE)}</div></div>')


INTRO_FIRST_LINE = 0.15   # seconds until the first line appears
INTRO_LINE_STEP = 0.3     # seconds between two lines; style.css ends the whole intro at 4 s


def intro():
    """The cinematic opening of the home page, about the game (not one case), about 4 seconds.
    Pure CSS: it plays once and then fades away by itself."""
    final = '<div class="title">NOVA <b>MYSTERY</b></div><div class="tag">Everyone has a secret.</div>'
    return _intro(content.HOME_INTRO_LINES, "", INTRO_FIRST_LINE, INTRO_LINE_STEP, final, red=1)


NUMBER_WORDS = {4: "Four", 5: "Five", 6: "Six"}
SUSPECT_RANGE = re.compile(r"4 to 6 suspects", re.IGNORECASE)


def case_intro(story=None, suspects=None):
    """The shorter intro of one case (about 8 seconds), on the board and every phone at the start.

    suspects: how many play in this room. Then "4 to 6 suspects." becomes e.g. "Five suspects."
    """
    story = _story(story)
    if suspects in NUMBER_WORDS:
        word = NUMBER_WORDS[suspects]
        story = dict(story, intro_lines=[
            SUSPECT_RANGE.sub(lambda m: f"{word if m.start() == 0 else word.lower()} suspects", line)
            for line in story["intro_lines"]])
    final = (f'<div class="no">CASE #{h(story["case_number"])}</div>'
             f'<div class="title case">{h(story["case_title"])}</div>'
             '<div class="tag">Your file is waiting.</div>')
    return _intro(story["intro_lines"], " case short", 0.3, 0.65, final)


def _intro(lines, css, start, step, final, red=3):
    """Lines appear one by one (line number `red`, counted from 0, in red), then the final title."""
    parts = []
    for number, line in enumerate(lines):
        colour = " red" if number == red else ""
        parts.append(f'<div class="line{colour}" style="animation-delay:{start + number * step:.2f}s">{h(line)}</div>')
    return (f'<div class="intro{css}" aria-hidden="true"><div class="glitch"></div>'
            f'<div class="lines">{"".join(parts)}</div><div class="final">{final}</div></div>')


def teaser():
    """The home page: what the game is, before any room or case exists. Only the rules."""
    rows = [
        ("Players", "4 to 6, each on their own phone"),
        ("Board", "One shared screen – laptop or projector"),
        ("Your file", "Role, alibi, secret and two private clues"),
        ("Your move", "One per round: search or share – questions out loud"),
        ("The goal", "Name the culprit – and where it happened"),
        ("Duration", f"{logic.ROUNDS} rounds, 15 to 30 minutes"),
    ]
    brief = ("One of you is the murderer, and only that player knows. Everybody may lie. "
             "Collect evidence, compare alibis, and accuse together before the clock runs out.")
    return _file("Classified", "MURDER MYSTERY", "One of you did it.", rows, brief)


def sealed_file():
    """The lobby: the case stays sealed until the host starts. It looks the same whether
    the AI is still writing, is done, or failed, so the intro at the start is the reveal."""
    rows = [("Opens", "when the host starts"), ("Players", "4 to 6")]
    return _file("Sealed", "MURDER MYSTERY", "The file is sealed.", rows, "One of you did it.")


def _file(stamp, number, name, rows, brief):
    table = "".join(f"<tr><td>{h(k)}</td><td>{h(v)}</td></tr>" for k, v in rows)
    return (f'<div class="casefile fade-up"><div class="stamp">{h(stamp)}</div>'
            f'<div class="no">{h(number)}</div><div class="name">{h(name)}</div>'
            f'<table>{table}</table><div class="brief">{h(brief)}</div></div>')


def case_file(story=None):
    story = _story(story)
    rows = [
        ("Case", f"#{story['case_number']}"),
        ("Location", "NOVA University, Lisbon"),
        ("Victim", story["victim"]),
        ("Found", f"{content.FOUND_TIME}, {story['found_place']}"),
        ("Initial classification", "Suspicious death"),
        ("Suspects", "4 to 6"),
    ]
    if story["source"] == "ai":
        rows.append(("Written by", "AI, new for this room"))
    table = "".join(f"<tr><td>{h(k)}</td><td>{h(v)}</td></tr>" for k, v in rows)
    return ('<div class="casefile fade-up"><div class="stamp">Active investigation</div>'
            f'<div class="no">CASE FILE #{h(story["case_number"])}</div>'
            f'<div class="name">{h(story["case_title"])}</div>'
            f'<table>{table}</table><div class="brief">{h(story["briefing"])}</div></div>')


# ---------------------------------------------------------------- phase and timer

def banner(title, subtitle=""):
    sub = f'<div class="s">{h(subtitle)}</div>' if subtitle else ""
    return f'<div class="banner"><div class="t">{h(title)}</div>{sub}</div>'


def timer(left, total):
    share = 0 if total <= 0 else max(0.0, min(1.0, left / total))
    low = " low" if left <= 10 else ""
    return (f'<div class="timer{low}"><div style="width:{share * 100:.1f}%"></div></div>'
            f'<div class="timer-label{low}">{int(left)} s left</div>')


def big_timer(left, total):
    """The board's countdown as large numbers (m:ss) with a thick bar under them.
    Red and pulsing in the last 10 seconds; style.css stops the pulse for reduced motion."""
    left = max(0, int(left))
    share = 0 if total <= 0 else min(1.0, left / total)
    low = " low" if left <= 10 else ""
    return (f'<div class="bigtimer{low}" role="timer" aria-label="{left} seconds left">'
            f'<div class="num">{left // 60}:{left % 60:02d}</div>'
            f'<div class="timer{low}"><div style="width:{share * 100:.1f}%"></div></div></div>')


# ---------------------------------------------------------------- suspects and map

def suspects(players, phase, guilty_pid=None, story=None):
    """One dossier card per player. Roles are public from REVEAL on (see logic.public_view)."""
    dossiers = _story(story)["dossiers"]
    cards = []
    for player in players:
        role = player.get("role")
        dossier = dossiers.get(role, "") if role else ""
        tags = []
        if player.get("is_host"):
            tags.append("host")
        if phase == "VOTE" and player.get("voted"):
            tags.append("voted")
        dot = '<span class="dot"></span>' if player.get("online") else '<span class="dot off"></span>'
        guilty = " guilty" if guilty_pid is not None and player["pid"] == guilty_pid else ""
        role_html = f'<div class="r">{h(role)}</div>' if role else '<div class="r">awaiting file</div>'
        dossier_html = f'<div class="d">{h(dossier)}</div>' if dossier else ""
        cards.append(
            f'<div class="suspect{guilty}"><div class="tags">{h(" · ".join(tags))}{dot}</div>'
            f'<div class="face">{initial(player["name"])}</div>'
            f'<div class="n">{h(player["name"])}</div>{role_html}{dossier_html}</div>')
    if not cards:
        return '<div class="muted">Nobody has joined yet.</div>'
    return f'<div class="suspects">{"".join(cards)}</div>'


def suspect_list(players, phase, me_pid=None):
    """Compact suspects for the phone: one short row per player (avatar, name, role, online dot).
    The board keeps the big dossier tiles from suspects(). Shows only public data."""
    rows = []
    for player in players:
        tags = []
        if player["pid"] == me_pid:
            tags.append("you")
        if player.get("is_host"):
            tags.append("host")
        if phase == "VOTE" and player.get("voted"):
            tags.append("voted")
        online = "online" if player.get("online") else "offline"
        dot_css = "dot" if player.get("online") else "dot off"
        mine = " me" if player["pid"] == me_pid else ""
        rows.append(
            f'<div class="srow{mine}" role="listitem">'
            f'<span class="face">{initial(player["name"])}</span>'
            f'<span class="who"><span class="n">{h(player["name"])}</span>'
            f'<span class="r">{h(player.get("role") or "awaiting file")}</span></span>'
            f'<span class="tags">{h(" · ".join(tags))}</span>'
            f'<span class="{dot_css}" role="img" aria-label="{online}" title="{online}"></span></div>')
    if not rows:
        return '<div class="muted">Nobody has joined yet.</div>'
    return f'<div class="slist" role="list" aria-label="Suspects">{"".join(rows)}</div>'


# ---------------------------------------------------------------- the campus plan
#
# NOVA SBE, floor 0, seen from above (north to the upper left, the beach to the bottom right). The ground, the roads and the building
# outlines are one SVG whose units are percent of the map (content.BUILDINGS, GROUNDS,
# ROADS); it is stretched to the map's 1.25 : 1 box. The building letters and the pins are
# HTML on top of it at the same percent positions, so text never stretches and, on the
# phone, the pins can be links.

STATE_LABELS = {"open": "Not searched yet", "done": "Searched", "locked": "Locked"}
ICONS = {
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M15.5 15.5L20 20"/>',
    "question": ('<path d="M4 12a8 8 0 1 1 3.2 6.4L4 20l1-3.6A7.9 7.9 0 0 1 4 12z"/>'
                 '<path d="M9.8 9.8a2.3 2.3 0 1 1 3.2 2.1c-.6.3-1 .8-1 1.4v.4"/><path d="M12 16.6v.1"/>'),
    "share": ('<rect x="6" y="3" width="12" height="18" rx="1.5"/><path d="M9 8h6M9 12h6M9 16h4"/>'),
    "plant": '<path d="M5 19l6-6M14 4l6 6-8 8H6v-6z"/>',
    "back": '<path d="M14 6l-6 6 6 6"/>',
}


def icon(name):
    return f'<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def _spot(name, index):
    """Where a place's pin stands (percent of the map) and its letter. A place that is not on
    the campus plan (games from before the plan) gets a spot on a row along the bottom."""
    place = content.PLACES.get(name)
    if place is None:
        return 12 + index * 18, 92, name[:1]
    return place["x"], place["y"], place["letter"]


def _points(points):
    return " ".join(f"{x},{y}" for x, y in points)


def _plan_ground(pinned=()):
    """The drawing under the pins: ground, roads, building outlines, building letters.
    pinned: letters that a pin already shows; their building letter is left out."""
    shapes = [f'<polygon class="g-{css}" points="{_points(points)}"/>' for css, points in content.GROUNDS]
    shapes += [f'<polyline class="road" points="{_points(points)}"/>' for _, points, _ in content.ROADS]
    shapes += [f'<polyline class="path" points="{_points(points)}"/>' for points in content.PATHS]
    shapes += [f'<polygon class="b-{"spine" if label == "I" else "hall"}" points="{_points(item["shape"])}">'
               f'<title>{h(label)} · {h(item["name"])}</title></polygon>'
               for label, item in content.BUILDINGS.items()]
    svg = ('<svg class="ground" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
           f'{"".join(shapes)}</svg>')
    tags = [f'<span class="btag" style="left:{x}%;top:{y}%">{h(label)}</span>'
            for label, item in content.BUILDINGS.items() if label not in pinned for x, y in [item["tag"]]]
    roads = [f'<span class="rname" style="left:{points[1][0]}%;top:{points[1][1]}%;--rot:{angle}deg">'
             f'{h(name)}</span>' for name, points, angle in content.ROADS if name]
    return svg + "".join(tags) + "".join(roads)


def plan_key():
    """The legend under the plan: the letters of the official campus map and their buildings."""
    rows = [f'<span class="k"><b>{h(label)}</b>{h(item["name"])}</span>'
            for label, item in sorted(content.BUILDINGS.items(), key=lambda kv: (kv[0].isdigit(), kv[0]))]
    return f'<div class="plan-key" aria-label="Buildings">{"".join(rows)}</div>'


def campus_map(searched, scene=None, story=None, view=None, links=None, active=True,
               selected=None, board=False):
    """The campus plan with a pin for every place of this case.

    view: logic.map_view(game), the state of every place (open, done, locked).
          Without it, a place is "done" when it is in `searched`, else "open".
    links: {place: url} makes pins tappable (only on the player's own phone).
    active: False greys the plan out (the player has already moved this round).
    selected: the place whose paper card is open on the phone (gets a gold ring).
    board: True adds a second line under each name (opens in round …, just now).
    scene: the crime scene, marked on the result screen.
    """
    story = _story(story)
    if view is None:
        view = {"round": 0, "places": [{"name": place, "state": "done" if place in searched else "open",
                                         "opens_in": None, "found_in": None}
                                        for place in story["locations"]]}
    links = links or {}
    this_round = view.get("round")
    pins = []
    pinned = {_spot(item["name"], index)[2] for index, item in enumerate(view["places"])}
    for index, item in enumerate(view["places"]):
        name, state = item["name"], item["state"]
        x, y, letter = _spot(name, index)
        found_in = item.get("found_in")
        just_now = state == "done" and found_in is not None and found_in == this_round
        face = icon("lock") if state == "locked" else icon("check") if state == "done" else h(letter)
        sub = ""
        if board and state == "locked":
            sub = f"Opens round {item['opens_in']}"
        elif board and state == "done":
            sub = "Just now" if just_now else (f"Round {found_in}" if found_in else "Searched")
        sub_html = f'<span class="ps">{h(sub)}</span>' if sub else ""
        css = (f"pin2 {state}" + (" sel" if name == selected else "") + (" scene" if name == scene else "")
               + (" now" if board and just_now else ""))
        inner = f'<span class="pc">{face}</span><span class="pl"><span class="pn">{h(name)}</span>{sub_html}</span>'
        style = f"left:{x}%;top:{y}%"
        label = f"{name}: {STATE_LABELS.get(state, '')}"
        href = links.get(name)
        if href:
            pins.append(f'<a class="{css}" href="{h(href)}" target="_self" style="{style}" '
                        f'aria-label="{h(label)}">{inner}</a>')
        else:
            pins.append(f'<div class="{css}" style="{style}" aria-label="{h(label)}">{inner}</div>')
    css = "plan2" + ("" if active else " off") + (" board" if board else "")
    return (f'<div class="{css}" role="group" aria-label="Campus map">{_plan_ground(pinned)}{"".join(pins)}'
            f'<div class="compass" aria-label="North is to the upper left">↖ N</div>'
            f'<div class="plan-foot">NOVA SBE Carcavelos · Floor 0</div></div>{plan_key()}')


def place_card(name, item=None, entries=(), story=None):
    """The paper card under the plan on the phone: the selected place and what it holds."""
    if name is None or item is None:
        return ('<div class="paper"><div class="pk">No place selected</div>'
                '<div class="pb">Grey pins were searched already. Dashed pins open later in the game.</div></div>')
    state = item["state"]
    icon_text = _story(story)["location_icons"].get(name, content.PLACES.get(name, {}).get("icon", ""))
    title = f'<div class="pt"><span class="pi">{h(icon_text)}</span>{h(name)}</div>'
    if state == "locked":
        return (f'<div class="paper"><div class="pk">Locked</div>{title}'
                f'<div class="pb">This place opens in round {h(item["opens_in"])}.</div></div>')
    if state == "open":
        return (f'<div class="paper"><div class="pk red">Not searched yet</div>{title}'
                '<div class="pb">Searching uses your move for this round. '
                'Whatever you find goes on the board.</div></div>')
    when = f" · round {item['found_in']}" if item.get("found_in") else ""
    found = "".join(f'<div class="pe"><span class="pk">Exhibit {h(e["id"])}</span>'
                    f'<div class="pb">{h(e["text"])}</div></div>' for e in entries)
    return f'<div class="paper"><div class="pk">Searched{h(when)}</div>{title}{found}</div>'


# ---------------------------------------------------------------- the phone's move, step by step

def action_cards(cards):
    """'Your move.': one big card per action. cards: dicts with href, icon, title, text, info."""
    rows = []
    for card in cards:
        css = "act" + (" off" if not card.get("href") else "") + (" " + card["css"] if card.get("css") else "")
        inner = (f'<span class="ai">{icon(card["icon"])}</span><span class="ab">'
                 f'<span class="at">{h(card["title"])}</span><span class="ad">{h(card["text"])}</span>'
                 f'<span class="ax">{h(card["info"])}</span></span>')
        if card.get("href"):
            rows.append(f'<a class="{css}" href="{h(card["href"])}" target="_self">{inner}</a>')
        else:
            rows.append(f'<div class="{css}" aria-disabled="true">{inner}</div>')
    return f'<div class="acts">{"".join(rows)}</div>'


def back_link(href):
    return f'<a class="back" href="{h(href)}" target="_self">{icon("back")}Change action</a>'


def step_head(title, text=""):
    sub = f'<div class="sh-s">{h(text)}</div>' if text else ""
    return f'<div class="sh"><div class="sh-t">{h(title)}</div>{sub}</div>'


def label(text):
    return f'<div class="lbl">{h(text)}</div>'


def pick_rows(rows):
    """Players to tap, one row each: (href, name, role, selected)."""
    out = []
    for href, name, role, selected in rows:
        css = "pick sel" if selected else "pick"
        out.append(f'<a class="{css}" href="{h(href)}" target="_self" role="radio" '
                   f'aria-checked="{"true" if selected else "false"}">'
                   f'<span class="face">{initial(name)}</span><span class="who"><span class="n">{h(name)}</span>'
                   f'<span class="r">{h(role or "")}</span></span><span class="radio"></span></a>')
    return f'<div class="picks" role="radiogroup">{"".join(out)}</div>'


def chips(items):
    """Public evidence to tap: (href, text, selected). Tapping a selected chip deselects it."""
    if not items:
        return '<div class="muted small">No public evidence yet.</div>'
    out = []
    for href, text, selected in items:
        short = text if len(text) <= 42 else text[:40].rstrip() + "…"
        css = "chip sel" if selected else "chip"
        out.append(f'<a class="{css}" href="{h(href)}" target="_self" title="{h(text)}">{h(short)}</a>')
    return f'<div class="chips">{"".join(out)}</div>'


def clue_cards(items):
    """The player's own private clues as paper cards: (href or None, number, text, selected)."""
    out = []
    for href, number, text, selected in items:
        css = "paper clue" + (" sel" if selected else "") + (" used" if href is None else "")
        kicker = f"Private clue {number}" + (" · already shared" if href is None else "")
        inner = f'<div class="pk">{h(kicker)}</div><div class="pq">{h(text)}</div>'
        if href:
            out.append(f'<a class="{css}" href="{h(href)}" target="_self">{inner}</a>')
        else:
            out.append(f'<div class="{css}">{inner}</div>')
    # The wrapping <div> matters: st.markdown would otherwise put the bare <a> cards into a <p>,
    # and the browser splits an <a> holding <div>s there into several empty or half cards.
    return f'<div class="clues">{"".join(out)}</div>'


def move_made(kicker, title, text):
    """'Move made.': the paper card of the move with a LOGGED stamp."""
    title_html = f'<div class="pt">{h(title)}</div>' if title else ""
    return (f'<div class="paper made fade-up"><div class="logged">Logged</div>'
            f'<div class="pk red">{h(kicker)}</div>{title_html}<div class="pb">{h(text)}</div></div>')


def waiting_list(players, me_pid):
    """Who has moved this round and who is still choosing. Public: never which action."""
    online = [p for p in players if p.get("online")]
    waiting = sum(1 for p in online if not p.get("acted"))
    rows = []
    for player in players:
        if not player.get("online"):
            state, css = "offline", "off"
        elif player.get("acted"):
            state, css = "done", "done"
        else:
            state, css = "choosing…", "wait"
        you = " (you)" if player["pid"] == me_pid else ""
        rows.append(f'<div class="wl-row"><span class="wd {css}"></span>'
                    f'<span class="wn">{h(player["name"])}{you}</span><span class="ws">{h(state)}</span></div>')
    head = f"Waiting for {waiting} player{'s' if waiting != 1 else ''}" if waiting else "Everybody has moved"
    return f'<div class="box wl"><div class="lbl">{h(head)}</div>{"".join(rows)}</div>'


# ---------------------------------------------------------------- the board during the rounds

def board_head(code, round_no, rounds, left):
    """Room code, 'Round X of 3' and the big timer (the logo stands above it, ui.brand)."""
    left = max(0, int(left or 0))
    low = " low" if left <= 10 else ""
    rnd = (f'<div class="hbox"><div class="hk">Investigation</div><div class="hv">Round {h(round_no)} of {h(rounds)}</div></div>'
           if round_no else "")
    return (f'<div class="bhead"><div class="bh-boxes">'
            f'<div class="hbox"><div class="hk">Room</div><div class="hv">{h(code)}</div></div>{rnd}'
            f'<div class="hbox clock{low}" role="timer" aria-label="{left} seconds left">'
            f'{left // 60}:{left % 60:02d}</div></div></div>')


def detectives(players):
    """The board's player list: name, role and whether they have moved (never which action)."""
    online = [p for p in players if p.get("online")]
    moved = sum(1 for p in online if p.get("acted"))
    rows = []
    for player in players:
        if not player.get("online"):
            state, css = "Offline", "off"
        elif player.get("acted"):
            state, css = "Moved", "done"
        else:
            state, css = "Choosing…", "wait"
        rows.append(f'<div class="dt-row"><span class="face">{initial(player["name"])}</span>'
                    f'<span class="dn">{h(player["name"])}</span><span class="dr">{h(player.get("role") or "")}</span>'
                    f'<span class="ds {css}">{h(state)}</span></div>')
    return (f'<div class="box dt"><div class="lbl">Detectives<span>{moved} of {len(online)} moved</span></div>'
            f'{"".join(rows)}</div>')


def evidence_board(log, name_of, story=None):
    """All public evidence, newest first: search results (no finder) and shared clues."""
    icons = _story(story)["location_icons"]
    cards = []
    for entry in reversed(log):
        tag = f'R{entry["round"]}' if entry.get("round") else ""
        if entry["kind"] == "search":
            place = entry.get("location", "")
            title = f'{icons.get(place, "")} {place}'.strip()
        elif entry["kind"] == "share":
            title = f"Shared by {name_of(entry['by'])}"
        else:
            continue
        cards.append(f'<div class="eb"><span class="eb-r">{h(tag)}</span><div class="eb-c">'
                     f'<div class="eb-t">Exhibit {h(entry["id"])} · {h(title)}</div>'
                     f'<div class="eb-b">{h(entry["text"])}</div></div></div>')
    if not cards:
        cards.append('<div class="muted small">Nothing has been found yet.</div>')
    return f'<div class="lbl">Evidence board</div><div class="ebs">{"".join(cards)}</div>'


# ---------------------------------------------------------------- evidence feed

RELIABILITY = {   # shown only after the case is closed (clue_kind is hidden before)
    "scene": ("Key evidence", "st-gold"),
    "alibi_broken": ("Key evidence", "st-gold"),
    "suspicious": ("Red herring", "st-grey"),
    "confirms": ("Verified", "st-grey"),
    "neutral": ("Irrelevant", "st-mute"),
}


def _stamp(entry):
    if entry.get("planted"):
        return '<div class="stamp st-red">Forged</div>'
    if "clue_kind" in entry:
        label, css = RELIABILITY.get(entry["clue_kind"], ("", ""))
        return f'<div class="stamp {css}">{h(label)}</div>' if label else ""
    if entry["kind"] == "search":
        return '<div class="stamp st-grey">Unverified</div>'
    return ""


def log_entry(entry, name_of, entries_by_id, story=None):
    """One entry of the public log as a card. name_of(pid) -> display name."""
    kind = entry["kind"]
    text = h(entry["text"])
    if kind == "search":
        icon = h(_story(story)["location_icons"].get(entry.get("location"), ""))
        note = ""
        if entry.get("planted"):
            note = '<div class="h" style="color:#B91C1C;margin-top:.4rem">Forged evidence: planted by the murderer</div>'
        return (f'<div class="ev exhibit">{_stamp(entry)}'
                f'<div class="h">Exhibit {entry["id"]} · {icon} {h(entry.get("location", ""))}</div>'
                f'<div class="b">{text}</div>{note}</div>')
    if kind == "share":
        return (f'<div class="ev statement">{_stamp(entry)}'
                f'<div class="h">Exhibit {entry["id"]} · Witness statement · {h(name_of(entry["by"]))}</div>'
                f'<div class="b">{text}</div></div>')
    return f'<div class="ev note">— {text}</div>'


# ---------------------------------------------------------------- evidence wall (board)

# Small tilts in degrees. The id picks one, so a note keeps its angle on every refresh.
TILTS = (-3, 2, -1.5, 3, -2.5, 1.5, -1, 2.5)


def tilt(entry_id):
    return TILTS[int(entry_id) % len(TILTS)]


def pinned_note(entry, name_of, newest=False, story=None):
    """One log entry as a note pinned to the cork board. name_of(pid) -> display name."""
    kind = entry["kind"]
    text = h(entry["text"])
    number = h(entry["id"])
    if kind == "search":       # an exhibit: a polaroid photo of the place
        icon = h(_story(story)["location_icons"].get(entry.get("location"), ""))
        css = "photo"
        body = (f'<div class="shot">{icon}</div>'
                f'<div class="cap">Exhibit {number} · {h(entry.get("location", ""))}</div>'
                f'<div class="b">{text}</div>')
    elif kind == "share":      # a witness statement: typed paper
        css = "typed"
        body = (f'<div class="cap">Exhibit {number} · Witness statement</div>'
                f'<div class="b">{text}</div><div class="sig">– {h(name_of(entry["by"]))}</div>')
    else:                      # a message from the game itself
        css = "slip"
        body = f'<div class="b">{text}</div>'
    new = " new" if newest else ""
    return (f'<div class="pin {css}{new}" role="listitem" style="--tilt:{tilt(entry["id"])}deg">'
            f'{_stamp(entry)}{body}</div>')


def evidence_wall(log, name_of, story=None):
    """The whole public log as a cork board. Oldest first, so old notes never move;
    only the newest note gets the class 'new' and drops in."""
    if not log:
        return '<div class="cork empty">Nothing has been pinned up yet.</div>'
    notes = [pinned_note(entry, name_of, newest=(i == len(log) - 1), story=story)
             for i, entry in enumerate(log)]
    return f'<div class="cork" role="list" aria-label="Evidence wall">{"".join(notes)}</div>'


# ---------------------------------------------------------------- private card (phone)

def file_stamp(guilty, slam=False):
    """The rubber stamp on the private card. Only private_view knows is_murderer, so this
    stamp can only ever reach the player's own phone. slam=True plays the stamp landing once."""
    if guilty:
        play = " slam" if slam else ""
        return f'<div class="dstamp murderer{play}" aria-label="Stamp: murderer">MURDERER</div>'
    return '<div class="dstamp innocent" aria-label="Stamp: innocent">INNOCENT</div>'


def dossier(me, slam=False):
    guilty = me["is_murderer"]
    rows = [f'<div class="row">{h(me["intro"])}</div>']
    if guilty:
        rows.append('<div class="row lie"><span class="lbl">The truth</span>'
                    'You did it. Nobody saw you – almost nobody. Do not get caught.</div>')
        rows.append(f'<div class="row lie"><span class="lbl">Your cover story</span>{h(me["alibi"])}</div>')
    else:
        rows.append(f'<div class="row"><span class="lbl">Your alibi</span>{h(me["alibi"])}</div>')
        rows.append(f'<div class="row secret"><span class="lbl">Your secret</span>{h(me["secret"])}</div>')
    slips = []
    for clue in me["clues"]:
        state = "shared" if clue["shared"] else "only you know"
        slips.append(f'<div class="slip"><span class="k">{h(state.upper())}</span>{h(clue["text"])}</div>')
    css = "dossier guilty" if guilty else "dossier"
    return (f'<div class="{css}">{file_stamp(guilty, slam)}<span class="lbl">Personal file</span>'
            f'<div class="role">{h(me["role"])}</div>{"".join(rows)}'
            f'<div class="row"><span class="lbl">What you know</span>{"".join(slips)}</div></div>')


def envelope(name, story=None):
    """The sealed case envelope the phone shows when the REVEAL phase starts.
    No role and no card data in here: only the player's own name and the case number."""
    return ('<div class="envelope" role="img" aria-label="Sealed case file">'
            '<div class="flap"></div><div class="seal">N</div>'
            f'<div class="env-label"><span class="case">Case #{h(_story(story)["case_number"])}</span>'
            f'CONFIDENTIAL – for {h(name)} only</div></div>')


def opened_file(me, animate, slam=False):
    """The opened envelope with the dossier inside. animate=True plays the opening once:
    the flap folds back, the seal breaks, the file slides out (pure CSS, see style.css).
    The murderer's file gets a subtle red tint. slam=True lets the stamp land once."""
    guilty = " guilty" if me["is_murderer"] else ""
    play = " play" if animate else ""
    back = ('<div class="env-back" aria-hidden="true"><div class="flap"></div>'
            '<div class="seal">N</div></div>') if animate else ""
    return f'<div class="unseal{guilty}{play}">{back}<div class="file">{dossier(me, slam)}</div></div>'


# ---------------------------------------------------------------- the reveal

def reveal(result, characters, name_of, story=None):
    endings = _story(story)["endings"]
    ending = endings[result.get("ending", "truth" if result["winner"] == "detectives" else "escaped")]
    won = result["winner"] == "detectives"
    who = "The detectives win" if won else "The murderer got away"
    culprit = next(c for c in characters if c["pid"] == result["murderer"])
    lost = "" if won else " lost"
    return (f'<div class="reveal{lost}"><div class="k">CASE CLOSED</div>'
            f'<div class="t">{h(ending["title"])}</div><div class="w">{h(who)}</div>'
            f'<div class="x">{h(ending["text"])}</div></div>'
            f'<div class="culprit"><div class="suspect guilty" style="padding:0;border:none;background:none">'
            f'<div class="face">{initial(name_of(culprit["pid"]))}</div></div>'
            f'<div class="who"><div class="r">It was</div><div class="n">{h(name_of(culprit["pid"]))}</div>'
            f'<div class="r">{h(culprit["role"])} · {h(result["murder_location"])}, {h(content.MURDER_TIME)}</div></div></div>')


def reconstruction(result, characters, name_of, story=None):
    """What really happened that night, built from the case data."""
    story = _story(story)
    victim = story["victim"]
    culprit = next(c for c in characters if c["pid"] == result["murderer"])
    scene = result["murder_location"]
    who = f'{name_of(culprit["pid"])} ({culprit["role"]})'
    events = [
        ("22:30", f"{victim} is seen alive for the last time, working late.", False),
        ("23:15", "The keycard window opens. The suspects are still on campus.", False),
        ("23:25", f"{who} hurries toward the {scene}.", False),
        (content.MURDER_TIME, f"{victim} dies in the {scene}.", True),
        ("23:40", f"{who} moves the body to {story['found_place']} and locks the door. "
                  f"The cover story: “{culprit['alibi']}”", True),
        (content.FOUND_TIME, ("The night guard finds the body and raises the alarm."
                              if story["source"] == "fixed"
                              else f"The body is found in {story['found_place']}. The alarm is raised."),
         False),
    ]
    items = "".join(
        f'<div class="tl{" red" if red else ""}" style="animation-delay:{i * 0.25:.2f}s">'
        f'<div class="time">{h(time)}</div><div class="what">{h(what)}</div></div>'
        for i, (time, what, red) in enumerate(events))
    return f'<div class="timeline">{items}</div>'


def alibi_table(result, characters, name_of):
    rows = []
    for c in characters:
        true = c["alibi_location"] == c["true_location"]
        verdict = '<span class="ok">TRUE</span>' if true else '<span class="bad">FALSE ALIBI</span>'
        if c["secret"]:
            kept = c["pid"] in result["secrets_kept"]
            secret = f'{h(c["secret"])} <b>{"(kept)" if kept else "(came out)"}</b>'
        else:
            secret = "—"
        rows.append(f'<tr><td><b>{h(name_of(c["pid"]))}</b><br><span class="sec">{h(c["role"])}</span></td>'
                    f'<td>{h(c["alibi_location"])}</td><td>{h(c["true_location"])}<br>{verdict}</td>'
                    f'<td class="sec">{secret}</td></tr>')
    return ('<table class="alibis"><tr><th>Suspect</th><th>Claimed</th><th>Really</th><th>Secret</th></tr>'
            f'{"".join(rows)}</table>')


def ballot_award(accused, place, murderer, scene, is_killer, caught):
    """A small title for each ballot, just for fun. caught: did most ballots name the killer?"""
    if is_killer:
        return "🚨 Caught" if caught else "🎭 Master liar"
    if accused is None:
        return "🙈 Too scared to vote"
    if accused != murderer:
        return "🤡 Fooled"
    if place == scene:
        return "🕵️ Sharpest detective"
    return "🔎 Good instinct"


def ballot_order(player, votes, murderer):
    """Suspense: wrong and missing ballots first, then the right ones, the killer's ballot last."""
    if player["pid"] == murderer:
        return 2
    return 1 if votes.get(str(player["pid"])) == murderer else 0


def vote_table(result, players, name_of):
    """After the game: every ballot as a card that flips in, one after another.
    Green = pointed at the real culprit, red = the culprit's own ballot, grey = wrong.
    --i is the card's number; the CSS uses it to delay each card a little more
    (and the killer's ballot, which comes last, a little longer)."""
    murderer = result["murderer"]
    scene = result["murder_location"]
    votes = result.get("votes", {})
    scene_votes = result.get("scene_votes", {})
    right = sum(1 for accused in votes.values() if accused == murderer)
    caught = right * 2 > len(votes)          # more than half of the ballots named the killer
    ordered = sorted(players, key=lambda p: ballot_order(p, votes, murderer))   # sorted() keeps ties in order
    cards = []
    for i, p in enumerate(ordered):
        voter = str(p["pid"])
        accused = votes.get(voter)
        place = scene_votes.get(voter)
        killer = p["pid"] == murderer
        if accused is None:
            css, tag, target = "ballot none", "Did not vote", '<span class="who">—</span>'
        else:
            css = "ballot right" if accused == murderer else "ballot"
            tag = "✓ Right" if accused == murderer else "✗ Wrong"
            target = (f'<span class="who"><span class="face">{initial(name_of(accused))}</span>'
                      f'{h(name_of(accused))}</span>')
        if killer:
            css += " killer"
            tag = "The killer's ballot"
        where = ""
        if place is not None:
            mark = " ✓" if place == scene else " ✗"
            icon = content.LOCATION_ICONS.get(place, "")
            where = f'<div class="where">{icon} {h(place)}{mark}</div>'
        award = ballot_award(accused, place, murderer, scene, killer, caught)
        cards.append(f'<div class="{css}" style="--i:{i}">'
                     f'<span class="who"><span class="face">{initial(name_of(p["pid"]))}</span>'
                     f'{h(name_of(p["pid"]))}</span><span class="arrow">accuses</span>{target}'
                     f'<span class="tag">{h(tag)}</span>{where}<div class="award">{h(award)}</div></div>')
    summary = f'{right} of {len(votes)} ballots named the killer'
    return (f'<div class="ballots"><div class="sum">{h(summary)}</div>'
            f'<div class="ballot-grid">{"".join(cards)}</div></div>')


def bars(counts, labels, hit=None):
    """Vote bars. counts: key -> votes; labels: list of (key, label) in display order."""
    most = max(counts.values(), default=0) or 1
    rows = []
    for key, label in labels:
        count = counts.get(key, 0)
        css = "bar hit" if key == hit else "bar"
        rows.append(f'<div class="{css}"><div>{h(label)}</div><div class="track">'
                    f'<div class="fill" style="width:{count / most * 100:.0f}%"></div></div>'
                    f'<div class="c">{count}</div></div>')
    return f'<div class="bars">{"".join(rows)}</div>'
