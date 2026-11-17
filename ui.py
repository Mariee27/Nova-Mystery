"""HTML building blocks for the NOVA MYSTERY screens.

Every function here is pure: it gets plain data and returns an HTML string.
No Streamlit, no database. app.py shows the strings with st.markdown(..., unsafe_allow_html=True).

Safety rule: every piece of text that goes into the HTML passes through h() first,
so names, questions and answers typed by players are always shown as plain text.
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


def intro():
    """The cinematic opening of the home page, about the game (not one case).
    Pure CSS: it plays once and then fades away by itself."""
    final = '<div class="title">NOVA <b>MYSTERY</b></div><div class="tag">Everyone has a secret.</div>'
    return _intro(content.HOME_INTRO_LINES, " short", 0.6, 1.15, final, red=1)


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
        ("Your move", "One action: search, interrogate or share"),
        ("The goal", "Name the culprit – and where it happened"),
        ("Duration", "About 5 minutes"),
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


def campus_map(searched, scene=None, story=None):
    story = _story(story)
    tiles = []
    for location in story["locations"]:
        classes = "loc"
        if location in searched:
            classes += " done"
        if scene == location:
            classes += " scene"
        icon = h(story["location_icons"].get(location, ""))
        tiles.append(f'<div class="{classes}"><span class="i">{icon}</span>{h(location)}</div>')
    return f'<div class="map">{"".join(tiles)}</div>'


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
    if kind == "question":
        confront = ""
        evidence = entries_by_id.get(entry.get("evidence"))
        if evidence is not None:
            confront = (f'<div class="confront">Confronted with Exhibit {evidence["id"]}: '
                        f'“{h(evidence["text"])}”</div>')
        return (f'<div class="ev quest"><div class="h">Interrogation #{entry["id"]} · '
                f'{h(name_of(entry["by"]))} → {h(name_of(entry["target"]))}</div>'
                f'{confront}<div class="b">“{text}”</div></div>')
    if kind == "answer":
        return (f'<div class="ev reply"><div class="h">Statement of {h(name_of(entry["by"]))} '
                f'· re #{entry["question_id"]}</div><div class="b">“{text}”</div></div>')
    return f'<div class="ev note">— {text}</div>'


# ---------------------------------------------------------------- private card (phone)

def dossier(me):
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
    return (f'<div class="{css}"><span class="lbl">Personal file</span>'
            f'<div class="role">{h(me["role"])}</div>{"".join(rows)}'
            f'<div class="row"><span class="lbl">What you know</span>{"".join(slips)}</div></div>')


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
