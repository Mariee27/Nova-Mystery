"""Evidence mini-games: every place's clue is sealed behind a short puzzle.

Pure functions, like logic.py: no Streamlit, no database. logic.search asks verify()
before it hands out a clue, so evidence can never be unlocked by changing what the
phone shows – the proof is checked here, in Python, against data the phone never gets
(the code, the cipher key) or cannot change (the starting order of the puzzle pieces).

The kinds, one per place of a case:
  code     🔐  a keypad lock; the 4-digit code follows from the case timeline
  scratch  🕵️  rub the dust off a find of this case: a note, a printout, a phone, a photo
  puzzle   🧩  a torn still of the night camera at the place: tap two pieces to swap them
  cipher   🧠  the victim's note in shifted letters: turn the cipher wheel until it reads
  order    🗂️  the victim's last evening, torn apart: tap the entries in the right order

Five kinds for the five places of a case, so no game comes twice. The words of each game
come from the case (story["minigames"]; see "what a puzzle shows" below).

Everything is built from the case seed, the story and the fixed times of the night
(content.MURDER_TIME, content.FOUND_TIME), so it works for case #001 and for every
AI-written case, and every player of a room gets the same puzzle for the same place.
"""

import math
import random
import re

import content
import exhibits

KINDS = ("code", "scratch", "puzzle", "cipher", "order")   # five kinds for the five places of a case

KIND_INFO = {
    "code": {"icon": "🔐", "name": "Crack the code", "exhibit": "The locked cash box",
             "verb": "Enter the 4-digit code."},
    "scratch": {"icon": "🕵️", "name": "Rub to reveal", "exhibit": "The dusty find",
                "verb": "Rub the dust away with your finger."},
    "puzzle": {"icon": "🧩", "name": "Reassemble the still", "exhibit": "The torn camera still",
               "verb": "Tap two pieces to swap them."},
    "cipher": {"icon": "🧠", "name": "Decode the note", "exhibit": "The shifted-letter note",
               "verb": "Turn the wheel until the note makes sense."},
    "order": {"icon": "🗂️", "name": "Order the evening", "exhibit": "The torn diary page",
              "verb": "Tap the entries in the order they happened."},
}

SCRATCH_COLS, SCRATCH_ROWS = 10, 14     # the page is checked in this grid of cells
SCRATCH_NEEDED = 0.55                   # share of the cells that must be rubbed
MAX_SWAPS = 400
# Faster than a person can solve it: an answer that comes sooner is ignored (seconds after the
# puzzle opened). A puzzle that runs in the browser can always be faked by someone with the
# browser's developer tools; this, and the limit on wrong answers, makes it slow and pointless.
MIN_SECONDS = {"code": 3, "cipher": 3, "scratch": 4, "puzzle": 4, "order": 4}
MAX_PROOF_ITEMS = SCRATCH_COLS * SCRATCH_ROWS


# ---------------------------------------------------------------- what a puzzle shows: the case's own words
#
# Every case brings one piece of words per kind (story["minigames"], see content.CASE_MINIGAMES):
# the locked object, the victim's note, the document under the dust, the camera caption, the
# entries of the victim's evening. An AI case writes its own; clean_content keeps only the
# pieces that pass the checks below, and every missing piece comes from content.MINIGAME_FALLBACK.
# The words never decide anything: the answers come from code, and no piece may name a suspect,
# so a puzzle can never point at anybody.

PUZZLE_HINT_MOVE = "PIECE"   # the third puzzle hint: replaced on the phone by a concrete move
ORDER_EVENTS = 4
EVENT_LIMIT = 60             # characters of one diary entry
STORY_LIMIT = 260            # characters of a puzzle's story
EXHIBIT_LIMIT = 40
CAPTION_LIMIT = 26
FORBIDDEN = ("murder", "kill", "killer", "culprit", "guilty")
LATEST_EVENT = content.MURDER_TIME   # the diary ends with the victim's last breath

# How the jigsaw picture of each place is laid out (the camera bars run along the top and bottom).
STILL_HINTS = {
    "atrium": ["The camera bar with REC is the top row; the blue glass roof fills the top under it.",
               "The window and the name plate sit in the centre; the stone floor and the people are at the bottom."],
    "library": ["The camera bar runs along the top; the library's name is on the white façade below it, left.",
                "The lit glass entrance is in the middle of the bottom half; the time is in the bottom-right corner."],
    "auditorium": ["The camera bar runs along the top; the screen with NOVA SBE is at the top centre.",
                   "The stage is in the middle; the red rows of seats and the time fill the bottom."],
    "deck": ["The camera bar and the white steel roof beams are at the top; the glass wall with its lattice is on the right.",
             "The white gallery with KPMG Gallery is in the centre; tables, chairs and the blue booths fill the bottom."],
    "beach": ["The camera bar runs along the top; the sunset sky and the sun are in the top half, the fort on the right.",
              "The sea and the sand cross the middle; the terrace railing is at the bottom."],
    "stairs": ["The camera bar runs along the top; the tall window is top right, the gallery with a figure top left.",
               "The white stairs climb from the bottom right; the FLOOR 1 sign is on the left wall."],
    "facade": ["The camera bar runs along the top; the white sun fins stand on the left, the sky is top right.",
               "The nova lettering runs up the white corner in the middle; the sun and the sea are bottom right."],
}


def _fill(text, location, victim):
    return str(text).replace("{location}", location).replace("{victim}", victim)


def _plain(value, limit):
    """One line of text within `limit` characters, or None."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text or len(text) > limit or re.search(r"[\x00-\x1f<>]", text):
        return None
    return text


def _names_nobody(text, story):
    low = text.casefold()
    roles = [role.casefold() for role in story.get("roles", {})]
    return not any(word in low for word in FORBIDDEN) and not any(role in low for role in roles)


def _clock(value):
    """'HH:MM' -> minutes after midnight, or None."""
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", str(value).strip())
    return int(match.group(1)) * 60 + int(match.group(2)) if match else None


def clean_piece(kind, raw, story):
    """The piece of words for one kind if it passes every check, else None."""
    if not isinstance(raw, dict):
        return None
    probe = {"location": "Main Deck", "victim": story.get("victim_short", "X")[:20]}
    piece = {}
    for key, limit in (("exhibit", EXHIBIT_LIMIT), ("story", STORY_LIMIT)):
        text = _plain(raw.get(key), limit)
        if text is None or "{location}" not in text and key == "story" or not _names_nobody(text, story):
            return None
        piece[key] = text
    if kind == "cipher":
        message = _plain(raw.get("message"), 40)
        letters = _letters(_fill(message or "", probe["location"], probe["victim"]), 60)
        if not message or not _names_nobody(message, story) or not 12 <= len(letters) <= 40 or len(letters.split()) < 3:
            return None
        piece["message"] = message
    elif kind == "scratch":
        style = raw.get("style")
        title = _plain(raw.get("title") or "-", exhibits.TITLE_LIMIT)
        lines = raw.get("lines")
        if style not in exhibits.STYLES or title is None or not isinstance(lines, list):
            return None
        lines = [_plain(line, exhibits.LINE_LIMIT) for line in lines[:exhibits.MAX_LINES]]
        wanted = 1 if style == "photo" else 2
        if len(lines) < wanted or None in lines or not all(_names_nobody(t, story) for t in lines + [title]):
            return None
        if any(len(_fill(t, "", probe["victim"])) > exhibits.LINE_LIMIT for t in lines):
            return None
        piece.update(style=style, title="" if title == "-" else title, lines=lines)
    elif kind == "puzzle":
        caption = _plain(raw.get("caption"), CAPTION_LIMIT)
        if caption is None or not _names_nobody(caption, story):
            return None
        piece["caption"] = caption
    elif kind == "order":
        events = raw.get("events")
        if not isinstance(events, list) or len(events) != ORDER_EVENTS:
            return None
        cleaned, times = [], []
        for event in events:
            if not isinstance(event, (list, tuple)) or len(event) != 2:
                return None
            minutes, text = _clock(event[0]), _plain(event[1], EVENT_LIMIT)
            if minutes is None or text is None or not _names_nobody(text, story):
                return None
            cleaned.append([str(event[0]).strip(), text])
            times.append(minutes)
        if (times != sorted(times) or len(set(times)) != len(times) or times[0] < 18 * 60
                or times[-1] > _clock(LATEST_EVENT) or min(b - a for a, b in zip(times, times[1:])) < 10):
            return None
        piece["events"] = cleaned
    return piece


def clean_content(raw, story):
    """The pieces of an AI case that pass the checks (a dict kind -> piece, maybe empty)."""
    raw = raw if isinstance(raw, dict) else {}
    pieces = {kind: clean_piece(kind, raw.get(kind), story) for kind in KINDS}
    return {kind: piece for kind, piece in pieces.items() if piece is not None}


def piece(game, kind):
    """The words of one kind for this game: the case's own, else the fallback."""
    story = _story(game)
    own = (story.get("minigames") or {}).get(kind)
    return own if own else content.MINIGAME_FALLBACK[kind]


def _minutes(clock):
    hours, minutes = clock.split(":")
    return int(hours), int(minutes)


def _letters(text, limit=24):
    """Upper-case A–Z and single spaces only (for the cipher)."""
    cleaned = re.sub(r"[^A-Z ]", "", str(text).upper().replace("-", " "))
    return re.sub(r" +", " ", cleaned).strip()[:limit].strip()


def _rng(game, location, salt):
    return random.Random(f"{game['case']['seed']}|{location}|{salt}")


def _story(game):
    import logic   # logic imports this module; import here to avoid a cycle
    return logic.story_of(game)


def enabled(game):
    return bool(game.get("minigames")) and game.get("case") is not None


def assignment(game):
    """location -> (kind, variant). Every place of a case gets a different kind (a case has five
    places and there are five kinds); which place gets which starts at a seeded offset. The
    variant (0 or 1: the code's order, the jigsaw's grid) changes from game to game."""
    locations = _story(game)["locations"]
    seed = game["case"]["seed"]
    offset = seed % len(KINDS)
    return {loc: (KINDS[(i + offset) % len(KINDS)], (seed // len(KINDS) + i) % 2) for i, loc in enumerate(locations)}


# ---------------------------------------------------------------- the secret parts

def _code_answer(variant):
    death_h, death_m = _minutes(content.MURDER_TIME)
    found_h, found_m = _minutes(content.FOUND_TIME)
    gap = (found_h * 60 + found_m) - (death_h * 60 + death_m)
    if variant % 2 == 0:
        return f"{gap:02d}{death_h:02d}"
    return f"{found_h:02d}{gap:02d}"


def _cipher_key(game, location):
    return _rng(game, location, "cipher").choice([k for k in range(3, 24) if k != 13])


def _signature(game):
    return _letters(_story(game)["victim_short"], 12).replace(" ", "") or "VALE"


def _cipher_plain(game, location, variant):
    """The victim's note, signed with the victim's name."""
    message = _fill(piece(game, "cipher")["message"], location, _story(game)["victim_short"])
    return f"{_letters(message, 40)} {_signature(game)}"


def shift_text(text, shift):
    return "".join(chr((ord(c) - 65 + shift) % 26 + 65) if "A" <= c <= "Z" else c for c in text)


def _puzzle_grid(variant):
    return (3, 3) if variant % 2 == 0 else (3, 2)     # (columns, rows): 9 or 6 pieces


def _puzzle_start(game, location, variant):
    cols, rows = _puzzle_grid(variant)
    n = cols * rows
    rng = _rng(game, location, "puzzle")
    order = list(range(n))
    while sum(1 for i, p in enumerate(order) if i == p) > 1:
        rng.shuffle(order)
    return order       # order[slot] = the piece lying in that slot


def apply_swaps(order, swaps):
    """Replay the player's swaps on the starting order. Raises ValueError on bad input."""
    order = list(order)
    if not isinstance(swaps, list) or len(swaps) > MAX_SWAPS:
        raise ValueError("bad swaps")
    for pair in swaps:
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                or not all(isinstance(i, int) and not isinstance(i, bool) for i in pair)
                or not all(0 <= i < len(order) for i in pair)):
            raise ValueError("bad swap")
        a, b = pair
        order[a], order[b] = order[b], order[a]
    return order


# ---------------------------------------------------------------- what the phone gets

def spec(game, location):
    """Everything the phone needs to draw the puzzle of one place – never the answer.
    None if mini-games are off or the place is not part of this case."""
    if not enabled(game):
        return None
    table = assignment(game)
    if location not in table:
        return None
    kind, variant = table[location]
    story = _story(game)
    number = story["locations"].index(location) + 1
    clue = next(c for c in game["case"]["location_clues"] if c["location"] == location)
    info = KIND_INFO[kind]
    victim = story["victim_short"]
    words = piece(game, kind)
    base = {
        "id": f"MG-{number:02d}-{kind}", "kind": kind, "variant": variant, "location": location,
        "evidence_id": clue["id"], "evidence_no": number,
        "icon": info["icon"], "name": info["name"], "verb": info["verb"],
        "exhibit": _fill(words["exhibit"], location, victim),
    }
    if kind == "code":
        if variant % 2 == 0:
            riddle = (f"The minutes between {victim}'s last breath and the discovery of the body – "
                      "then the hour it all ended.")
        else:
            riddle = (f"The hour the body of {victim} was found – then the minutes between "
                      "the last breath and the discovery.")
        base.update(
            story=_fill(words["story"], location, victim),
            riddle=riddle,
            facts=[["Time of death", f"≈ {content.MURDER_TIME}"], ["Body found", content.FOUND_TIME]],
            hints=_code_hints(variant))
    elif kind == "scratch":
        lines = [_fill(line, location, victim) for line in words["lines"]]
        base.update(
            story=_fill(words["story"], location, victim), cover="RUB AWAY THE DUST",
            cols=SCRATCH_COLS, rows=SCRATCH_ROWS, needed=SCRATCH_NEEDED,
            image=exhibits.document(words["style"], _fill(words["title"], location, victim), lines, location),
            hints=["Rub with your finger over the whole surface, not just one spot.",
                   "What is underneath fills the whole surface – work from edge to edge.",
                   f"Rub a little more than half of it ({int(SCRATCH_NEEDED * 100)} %) and it opens."])
    elif kind == "puzzle":
        cols, rows = _puzzle_grid(variant)
        rng = _rng(game, location, "still")
        clock = f"23:{rng.randint(10, 29):02d}:{rng.randint(10, 59):02d}"
        base.update(
            story=_fill(words["story"], location, victim).replace("{pieces}", str(cols * rows)),
            cols=cols, rows=rows, start=_puzzle_start(game, location, variant),
            image=exhibits.camera_still(location, number, clock, _fill(words["caption"], location, victim)),
            hints=STILL_HINTS[exhibits.still_picture(location)] + [PUZZLE_HINT_MOVE])   # see first_misplaced
    elif kind == "order":
        events = _order_events(game, location)
        start = _order_start(game, location)
        items = [{"letter": LETTERS[i], "when": events[true][0], "text": events[true][1]}
                 for i, true in enumerate(start)]
        answer = _order_answer(start)
        base.update(
            story=_fill(words["story"], location, victim), items=items,
            hints=["Look at the times: the earliest entry comes first.",
                   f"The evening starts with entry {LETTERS[answer[0]]}.",
                   "The right order: " + ", ".join(LETTERS[i] for i in answer) + "."])
    else:
        sig = _signature(game)
        key = _cipher_key(game, location)
        cipher = shift_text(_cipher_plain(game, location, variant), key)
        base.update(
            story=_fill(words["story"], location, victim),
            cipher=cipher, signature_length=len(sig),
            hints=["Notes like this are signed at the end. Whose name would it be?",
                   f"The last word is {sig}. Turn the wheel until the last word reads {sig}.",
                   f"The first letter of the signature, {cipher.split()[-1][0]}, has to become {sig[0]}: "
                   f"turn the wheel to {key}."])
    return base


# ---------------------------------------------------------------- the diary (order)

LETTERS = "ABCDEFGH"
def _order_events(game, location):
    """[(time, text)] in the true order, times as 24-hour clock times."""
    victim = _story(game)["victim_short"]
    return [(clock, _fill(text, location, victim)) for clock, text in piece(game, "order")["events"]]


def _order_start(game, location):
    """start[i] = the true position of the entry shown at position i (never already in order)."""
    rng = _rng(game, location, "order")
    start = list(range(ORDER_EVENTS))
    while start == sorted(start):
        rng.shuffle(start)
    return start


def _order_answer(start):
    """The positions on screen, tapped in the true order."""
    return [start.index(true) for true in range(len(start))]


def _code_hints(variant):
    if variant % 2 == 0:
        return ["Both numbers come from the timeline of the night, shown above the keypad.",
                "Death about 23:30, body found 23:47. The first two digits are the minutes in between.",
                "47 − 30 = 17 minutes. Then the hour of death: 23."]
    return ["Both numbers come from the timeline of the night, shown above the keypad.",
            "Found at 23:47 – the first two digits are that hour. Then the minutes between 23:30 and 23:47.",
            "The hour is 23. Then 47 − 30 = 17."]


def specs(game):
    """The puzzle of every place, in the order of the story's locations."""
    if not enabled(game):
        return []
    return [spec(game, loc) for loc in _story(game)["locations"]]


# ---------------------------------------------------------------- the check

def verify(game, location, proof):
    """True only if `proof` really solves the puzzle of this place."""
    if not enabled(game) or not isinstance(proof, dict):
        return False
    table = assignment(game)
    if location not in table:
        return False
    kind, variant = table[location]
    try:
        if kind == "code":
            return str(proof.get("code", "")) == _code_answer(variant)
        if kind == "scratch":
            cells = proof.get("cells")
            if not isinstance(cells, list) or len(cells) > MAX_PROOF_ITEMS:
                return False
            if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < MAX_PROOF_ITEMS for c in cells):
                return False
            return len(set(cells)) >= math.ceil(SCRATCH_NEEDED * MAX_PROOF_ITEMS)
        if kind == "puzzle":
            order = apply_swaps(_puzzle_start(game, location, variant), proof.get("swaps"))
            return order == list(range(len(order)))
        if kind == "cipher":
            shift = proof.get("shift")
            return isinstance(shift, int) and not isinstance(shift, bool) and shift % 26 == _cipher_key(game, location)
        if kind == "order":
            return proof.get("order") == _order_answer(_order_start(game, location))
    except (ValueError, TypeError, AttributeError):
        return False
    return False


def feedback(game, location, proof):
    """A short, contextual note after a wrong attempt (never the answer itself)."""
    table = assignment(game) if enabled(game) else {}
    if location not in table or not isinstance(proof, dict):
        return "That did not work."
    kind, variant = table[location]
    if kind == "code":
        code = str(proof.get("code", ""))
        if not re.fullmatch(r"\d{4}", code):
            return "The lock wants exactly four digits."
        times = {content.MURDER_TIME.replace(":", ""), content.FOUND_TIME.replace(":", "")}
        if code in times:
            return "ACCESS DENIED – that is just one time from the case file. The note combines two of them."
        answer = _code_answer(variant)
        if code[2:] == answer[2:] or code[:2] == answer[:2]:
            return "ACCESS DENIED – the lock clicked halfway. Half of your code is right."
        return "ACCESS DENIED – read the note again and use the timeline above the keypad."
    if kind == "cipher":
        shift = proof.get("shift")
        if not isinstance(shift, int):
            return "Turn the wheel first."
        word = shift_text(spec(game, location)["cipher"].split()[-1], -shift)
        return f"Still gibberish: with setting {shift % 26} the signature reads “{word}”."
    if kind == "puzzle":
        return "Some pieces are still out of place."
    if kind == "order":
        picked = proof.get("order")
        answer = _order_answer(_order_start(game, location))
        if not isinstance(picked, list) or sorted(picked) != list(range(len(answer))):
            return "Tap every entry once, earliest first."
        right = sum(1 for a, b in zip(picked, answer) if a == b)
        return f"Not quite – {right} of {len(answer)} entries are in the right place. Check the times again."
    return "Keep rubbing – the writing is not readable yet."


def solve(game, location):
    """A valid proof for a place (used by the tests and the demo bots, never sent to a phone)."""
    kind, variant = assignment(game)[location]
    if kind == "code":
        return {"code": _code_answer(variant)}
    if kind == "scratch":
        return {"cells": list(range(MAX_PROOF_ITEMS))}
    if kind == "cipher":
        return {"shift": _cipher_key(game, location)}
    if kind == "order":
        return {"order": _order_answer(_order_start(game, location))}
    start = _puzzle_start(game, location, variant)
    order, swaps = list(start), []
    for slot in range(len(order)):
        if order[slot] != slot:
            other = order.index(slot)
            swaps.append([slot, other])
            order[slot], order[other] = order[other], order[slot]
    return {"swaps": swaps}


def first_misplaced(spec_, swaps):
    """For hint 3 of the puzzle: (slot of a misplaced piece, slot it belongs in), 1-based."""
    try:
        order = apply_swaps(spec_["start"], swaps or [])
    except ValueError:
        order = list(spec_["start"])
    for slot, piece in enumerate(order):
        if piece != slot:
            return slot + 1, piece + 1
    return None
