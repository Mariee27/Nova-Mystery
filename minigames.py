"""Evidence mini-games: every place's clue is sealed behind a short puzzle.

Pure functions, like logic.py: no Streamlit, no database. logic.search asks verify()
before it hands out a clue, so evidence can never be unlocked by changing what the
phone shows – the proof is checked here, in Python, against data the phone never gets
(the code, the cipher key) or cannot change (the starting order of the puzzle pieces).

Four kinds, spread over the five places of a case:
  code     🔐  a keypad lock; the 4-digit code follows from the case timeline
  scratch  🕵️  rub a blank page to raise the writing pressed into it
  puzzle   🧩  a torn camera still: tap two pieces to swap them
  cipher   🧠  a note in shifted letters: turn the cipher wheel until it reads

Everything is built from the case seed, the story and the fixed times of the night
(content.MURDER_TIME, content.FOUND_TIME), so it works for case #001 and for every
AI-written case, and every player of a room gets the same puzzle for the same place.
"""

import math
import random
import re

import content

KINDS = ("code", "scratch", "puzzle", "cipher")

KIND_INFO = {
    "code": {"icon": "🔐", "name": "Crack the code", "exhibit": "The locked cash box",
             "verb": "Enter the 4-digit code."},
    "scratch": {"icon": "🕵️", "name": "Rub to reveal", "exhibit": "The pressed-in note",
                "verb": "Rub the page with your finger."},
    "puzzle": {"icon": "🧩", "name": "Reconstruct the still", "exhibit": "The torn camera still",
               "verb": "Tap two pieces to swap them."},
    "cipher": {"icon": "🧠", "name": "Decode the note", "exhibit": "The shifted-letter note",
               "verb": "Turn the wheel until the note makes sense."},
}

SCRATCH_COLS, SCRATCH_ROWS = 10, 14     # the page is checked in this grid of cells
SCRATCH_NEEDED = 0.55                   # share of the cells that must be rubbed
MAX_SWAPS = 400
# Faster than a person can solve it: an answer that comes sooner is ignored (seconds after the
# puzzle opened). A puzzle that runs in the browser can always be faked by someone with the
# browser's developer tools; this, and the limit on wrong answers, makes it slow and pointless.
MIN_SECONDS = {"code": 3, "cipher": 3, "scratch": 4, "puzzle": 4}
MAX_PROOF_ITEMS = SCRATCH_COLS * SCRATCH_ROWS


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
    """location -> (kind, variant). The order of kinds starts at a seeded offset."""
    locations = _story(game)["locations"]
    offset = game["case"]["seed"] % len(KINDS)
    return {loc: (KINDS[(i + offset) % len(KINDS)], i // len(KINDS)) for i, loc in enumerate(locations)}


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
    place = _letters(location, 18)
    sig = _signature(game)
    if variant % 2 == 0:
        return f"THE {place} KEY IS UNDER THE MAT {sig}"
    return f"LEAVE THE {place} DOOR OPEN AFTER ELEVEN {sig}"


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
    base = {
        "id": f"MG-{number:02d}-{kind}", "kind": kind, "variant": variant, "location": location,
        "evidence_id": clue["id"], "evidence_no": number,
        "icon": info["icon"], "name": info["name"], "exhibit": info["exhibit"], "verb": info["verb"],
    }
    if kind == "code":
        if variant % 2 == 0:
            riddle = (f"The minutes between {victim}'s last breath and the discovery of the body – "
                      "then the hour it all ended.")
        else:
            riddle = (f"The hour the body of {victim} was found – then the minutes between "
                      "the last breath and the discovery.")
        base.update(
            story=f"A steel cash box under a desk in the {location}. Its keypad wants four digits. "
                  "A note is taped inside the drawer:",
            riddle=riddle,
            facts=[["Time of death", f"≈ {content.MURDER_TIME}"], ["Body found", content.FOUND_TIME]],
            hints=_code_hints(variant))
    elif kind == "scratch":
        base.update(
            story=f"A blank notepad page from the {location}. Whoever wrote on the sheet above pressed hard. "
                  "Rub it like a pencil to raise the writing.",
            cols=SCRATCH_COLS, rows=SCRATCH_ROWS, needed=SCRATCH_NEEDED,
            lines=[f"{victim} –", f"{location}", f"{content.MURDER_TIME} ?", "don't tell anyone"],
            hints=["Rub with your finger over the whole page, not just one spot.",
                   "The writing is spread across the page – work from edge to edge.",
                   f"Rub a little more than half of the page ({int(SCRATCH_NEEDED * 100)} %) and it opens."])
    elif kind == "puzzle":
        cols, rows = _puzzle_grid(variant)
        rng = _rng(game, location, "still")
        base.update(
            story=f"A security still from the camera in the {location}, torn into {cols * rows} pieces "
                  "and left in a bin. Put it back together.",
            cols=cols, rows=rows, start=_puzzle_start(game, location, variant),
            image=camera_still(location, number, rng.randint(20, 29), rng.randint(10, 59)),
            hints=["The camera writes its number top-left and the time bottom-left.",
                   "The name of the place runs across the top row; the floor lines meet in the middle.",
                   "PIECE"])   # replaced on the phone by a concrete move (see first_misplaced)
    else:
        sig = _signature(game)
        key = _cipher_key(game, location)
        cipher = shift_text(_cipher_plain(game, location, variant), key)
        base.update(
            story=f"A folded note slipped under the door of the {location}. The letters are shifted – "
                  "every letter replaced by one a fixed number of steps further along the alphabet.",
            cipher=cipher, signature_length=len(sig),
            hints=["Notes like this are signed at the end. Whose name would it be?",
                   f"The last word is {sig}. Turn the wheel until the last word reads {sig}.",
                   f"The first letter of the signature, {cipher.split()[-1][0]}, has to become {sig[0]}: "
                   f"turn the wheel to {key}."])
    return base


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


# ---------------------------------------------------------------- the camera still (SVG)

def camera_still(location, number, minute, second):
    """A stylised security-camera frame of a place, 300 × 300. Every piece looks different."""
    from html import escape
    place = escape(location.upper())
    icon = content.PLACES.get(location, {}).get("icon", "📷")
    lines = "".join(f'<line x1="150" y1="165" x2="{x}" y2="300" stroke="#1f6f7a" stroke-width="1.4"/>'
                    for x in range(-150, 451, 60))
    rows = "".join(f'<line x1="0" y1="{y}" x2="300" y2="{y}" stroke="#1f6f7a" stroke-width="1" opacity=".7"/>'
                   for y in (190, 215, 250, 295))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300" width="300" height="300">'
        '<defs><radialGradient id="g" cx="50%" cy="40%" r="75%"><stop offset="0" stop-color="#20384a"/>'
        '<stop offset="1" stop-color="#05080d"/></radialGradient></defs>'
        '<rect width="300" height="300" fill="url(#g)"/>'
        f'{lines}{rows}'
        '<rect x="30" y="70" width="70" height="95" fill="#0b1520" stroke="#3b82a0" stroke-width="2"/>'
        '<rect x="200" y="60" width="72" height="50" fill="#132433" stroke="#3b82a0" stroke-width="2"/>'
        '<line x1="200" y1="85" x2="272" y2="85" stroke="#3b82a0"/><line x1="236" y1="60" x2="236" y2="110" stroke="#3b82a0"/>'
        '<circle cx="85" cy="120" r="4" fill="#d4a853"/>'
        '<rect x="120" y="120" width="70" height="40" rx="3" fill="#1b2a38" stroke="#5aa9bf"/>'
        f'<text x="155" y="105" font-size="44" text-anchor="middle">{icon}</text>'
        '<rect x="0" y="0" width="300" height="34" fill="rgba(0,0,0,.55)"/>'
        f'<text x="10" y="22" font-family="monospace" font-size="15" fill="#e2e8f0">CAM {number:02d}</text>'
        f'<text x="290" y="22" font-family="monospace" font-size="13" fill="#f5f1e8" text-anchor="end">{place}</text>'
        '<circle cx="96" cy="17" r="5" fill="#ef4444"/><text x="106" y="22" font-family="monospace" font-size="13" fill="#ef4444">REC</text>'
        '<rect x="0" y="266" width="300" height="34" fill="rgba(0,0,0,.6)"/>'
        f'<text x="10" y="289" font-family="monospace" font-size="15" fill="#d4a853">23:{minute:02d}:{second:02d}</text>'
        '<text x="290" y="289" font-family="monospace" font-size="12" fill="#94a3b8" text-anchor="end">NOVA SECURITY</text>'
        '<path d="M8 44 v-8 h8 M292 44 v-8 h-8 M8 256 v8 h8 M292 256 v8 h-8" stroke="#e2e8f0" fill="none" stroke-width="2"/>'
        '</svg>')
