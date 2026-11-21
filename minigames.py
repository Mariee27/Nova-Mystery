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

import functools
import html
import math
import pathlib
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


# ---------------------------------------------------------------- motifs: what a puzzle shows
#
# Each kind can show one of several pictures (assets/minigames/...). Only the picture and its
# words change; how a puzzle is solved, checked and rewarded never does. logic.start picks a
# first motif per kind for the game (choose_motifs) and stores it in game["motifs"]; a second
# place of the same kind gets the next motif, so no picture repeats within a game. Without a
# stored choice (rehearsal mode, games from before) every place shows the first motif, the
# picture case #001 always had. Pictures are SVG files with <text data-slot="..."> elements
# that get this case's words (fill), so no picture contradicts the story.

ASSETS = pathlib.Path(__file__).resolve().parent / "assets" / "minigames"
PUZZLE_HINT_MOVE = "PIECE"   # the third puzzle hint: replaced on the phone by a concrete move

MOTIFS = {
    "puzzle": [
        {"id": "camera", "file": "puzzles/camera.svg", "name": "Reconstruct the still",
         "exhibit": "The torn camera still",
         "story": "A security still from the camera in the {location}, torn into {pieces} pieces and left in a bin. "
                  "Put it back together.",
         "hints": ["The camera writes its number top-left and the time bottom-left.",
                   "The name of the place runs across the top row; the floor lines meet in the middle."],
         "slots": {"camera": "CAM {number:02d}", "place": "{PLACE}", "time": "23:{minute:02d}:{second:02d}",
                   "icon": "{icon}"}},
        {"id": "letter", "file": "puzzles/letter.svg", "name": "Piece the letter together",
         "exhibit": "The torn letter",
         "story": "A letter found in the {location}, torn into {pieces} pieces. Somebody did not want it read. "
                  "Put it back together.",
         "hints": ["The letterhead runs across the top row; the place and the hour sit top-right.",
                   "The red wax seal is bottom-left, the signature bottom-right; the lines of writing fill the middle."],
         "slots": {"place": "{location}", "victim": "Dear {victim},"}},
        {"id": "corridor", "file": "puzzles/corridor.svg", "name": "Reconstruct the photo",
         "exhibit": "The torn photo of the corridor",
         "story": "A photo of the dark corridor by the {location}, printed and torn into {pieces} pieces. "
                  "Someone stands at the far end. Put it back together.",
         "hints": ["The sign with the place name and the lamps are in the top row; the floor lines meet in the middle.",
                   "The open door with its light is on the right; the figure stands at the far end, in the centre."],
         "slots": {"place": "{PLACE}"}},
        {"id": "photograph", "file": "puzzles/photograph.svg", "name": "Restore the photograph",
         "exhibit": "The torn group photo",
         "story": "An old photograph pinned up in the {location}, torn into {pieces} pieces. One face is circled in red. "
                  "Put it back together.",
         "hints": ["The red pushpin holds the top-left corner; the arched windows run across the top.",
                   "The red circle is around one face on the right; the caption is written along the bottom."],
         "slots": {"place": "{location}"}},
        {"id": "document", "file": "puzzles/document.svg", "name": "Reassemble the memo",
         "exhibit": "The shredded memo",
         "story": "A confidential memo from the {location}, torn into {pieces} pieces before anyone could read it. "
                  "Put it back together.",
         "hints": ["The paperclip and the heading are top-left; the red CONFIDENTIAL stamp is top-right.",
                   "The black bars are in the middle; the signature and the coffee ring are at the bottom."],
         "slots": {"victim": "RE: {victim}", "place": "LOCATION: {location}"}},
    ],
    "scratch": [
        {"id": "note", "file": "scratchcards/note.svg", "name": "Rub to reveal", "exhibit": "The pressed-in note",
         "verb": "Rub the page with your finger.", "cover": "RUB THE PAGE",
         "story": "A blank notepad page from the {location}. Whoever wrote on the sheet above pressed hard. "
                  "Rub it like a pencil to raise the writing.",
         "slots": {"victim": "{victim} –", "place": "{location}", "time": "{murder_time} ?"}},
        {"id": "fingerprint", "file": "scratchcards/fingerprint.svg", "name": "Dust for prints",
         "exhibit": "The dusted fingerprint", "verb": "Brush the powder with your finger.", "cover": "BRUSH THE POWDER",
         "story": "A glass left on a desk in the {location}. Brush the powder across it to raise the fingerprint.",
         "slots": {"place": "{location}"}},
        {"id": "symbol", "file": "scratchcards/symbol.svg", "name": "Rub away the dust",
         "exhibit": "The carved symbol", "verb": "Rub the dust away with your finger.", "cover": "RUB AWAY THE DUST",
         "story": "Under a desk in the {location}, something was carved into the wood. Rub away the dust to see it.",
         "slots": {"place": "{PLACE}"}},
        {"id": "photo", "file": "scratchcards/photo.svg", "name": "Clean the photograph",
         "exhibit": "The torn photograph", "verb": "Rub the grime away with your finger.", "cover": "RUB IT CLEAN",
         "story": "Half a photograph, stuck face down under grime in the {location}. Rub it clean.",
         "slots": {"victim": "{victim}", "place": "{location}"}},
        {"id": "watch", "file": "scratchcards/watch.svg", "name": "Polish the watch",
         "exhibit": "The stopped pocket watch", "verb": "Rub the tarnish away with your finger.",
         "cover": "RUB AWAY THE TARNISH",
         "story": "A pocket watch under a cloth in the {location}, black with tarnish. Rub it until you can read it.",
         "slots": {"place": "{PLACE}"}},
    ],
}


def choose_motifs(seed):
    """The first motif of each kind for a new game: random, but fixed by the game's seed."""
    rng = random.Random(f"{seed}|motifs")
    return {kind: rng.randrange(len(options)) for kind, options in MOTIFS.items()}


def motif(game, kind, variant):
    """The motif of a place: the game's first motif of this kind, then the next ones for further
    places of the same kind. Without a stored choice: always the first motif."""
    options = MOTIFS[kind]
    chosen = game.get("motifs")
    if not chosen:
        return options[0]
    return options[(chosen.get(kind, 0) + variant) % len(options)]


@functools.lru_cache(maxsize=None)
def _picture(name):
    return (ASSETS / name).read_text(encoding="utf-8")


def picture(name, **words):
    """An SVG asset with its <text data-slot="..."> elements filled (every word escaped)."""
    def fill(match):
        slot = match.group(2)
        return match.group(1) + (html.escape(str(words[slot])) if slot in words else match.group(3)) + match.group(4)
    return re.sub(r'(<text\b[^>]*\bdata-slot="([a-z_]+)"[^>]*>)(.*?)(</text>)', fill, _picture(name), flags=re.S)


def _words(spec_slots, **values):
    return {slot: template.format(**values) for slot, template in spec_slots.items()}


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
        look = motif(game, kind, variant)
        words = _words(look["slots"], location=location, PLACE=location.upper(), victim=victim,
                       murder_time=content.MURDER_TIME)
        base.update(
            motif=look["id"], name=look["name"], exhibit=look["exhibit"], verb=look["verb"], cover=look["cover"],
            story=look["story"].format(location=location),
            cols=SCRATCH_COLS, rows=SCRATCH_ROWS, needed=SCRATCH_NEEDED,
            image=picture(look["file"], **words),
            hints=["Rub with your finger over the whole surface, not just one spot.",
                   "The picture is spread across the whole surface – work from edge to edge.",
                   f"Rub a little more than half of it ({int(SCRATCH_NEEDED * 100)} %) and it opens."])
    elif kind == "puzzle":
        cols, rows = _puzzle_grid(variant)
        rng = _rng(game, location, "still")
        look = motif(game, kind, variant)
        words = _words(look["slots"], location=location, PLACE=location.upper(), victim=victim, number=number,
                       minute=rng.randint(20, 29), second=rng.randint(10, 59),
                       icon=content.PLACES.get(location, {}).get("icon", "📷"))
        base.update(
            motif=look["id"], name=look["name"], exhibit=look["exhibit"],
            story=look["story"].format(location=location, pieces=cols * rows),
            cols=cols, rows=rows, start=_puzzle_start(game, location, variant),
            image=picture(look["file"], **words),
            hints=look["hints"] + [PUZZLE_HINT_MOVE])   # the move: see first_misplaced
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
    """The camera still (the first puzzle motif) of a place, 300 × 300."""
    look = MOTIFS["puzzle"][0]
    return picture(look["file"], **_words(look["slots"], PLACE=location.upper(), number=number, minute=minute,
                                          second=second, icon=content.PLACES.get(location, {}).get("icon", "📷")))
