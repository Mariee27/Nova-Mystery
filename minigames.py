"""Evidence mini-games: every place's clue is sealed behind a short puzzle.

Pure functions, like logic.py: no Streamlit, no database. logic.search asks verify()
before it hands out a clue, so evidence can never be unlocked by changing what the
phone shows – the proof is checked here, in Python, against data the phone never gets
(the code, the cipher key) or cannot change (the starting order of the puzzle pieces).

Four kinds, spread over the five places of a case:
  code     🔐  a keypad lock; the 4-digit code follows from the case timeline
  scratch  🕵️  rub the coating off a photo print of a NOVA SBE place
  puzzle   🧩  a torn photo of a NOVA SBE place: tap two pieces to swap them
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
    "scratch": {"icon": "🕵️", "name": "Rub to reveal", "exhibit": "The covered photo print",
                "verb": "Rub the coating away with your finger."},
    "puzzle": {"icon": "🧩", "name": "Reassemble the photo", "exhibit": "The torn photo",
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
# stored choice (rehearsal mode, games from before) every place shows the first motif.
# Pictures are SVG files; a <text data-slot="..."> element in one would get this case's words
# (fill, escaped). The NOVA SBE pictures need none: they show the campus, not the case.

ASSETS = pathlib.Path(__file__).resolve().parent / "assets" / "minigames"
PUZZLE_HINT_MOVE = "PIECE"   # the third puzzle hint: replaced on the phone by a concrete move

# Pictures of real places on the NOVA SBE campus, drawn as flat illustrations. The puzzle and the
# scratch card only show a picture; the clue a player earns never depends on which one it is.
MOTIFS = {
    "puzzle": [
        {"id": "atrium", "file": "puzzles/atrium.svg", "name": "Reassemble the photo",
         "exhibit": "The torn photo of the Hovione Atrium",
         "story": "A photo of the Hovione Atrium, found torn into {pieces} pieces in the {location}. "
                  "Someone kept it for a reason. Put it back together.",
         "hints": ["The blue glass roof fills the top row; its white grid lines run toward the middle.",
                   "The window and the name plate sit in the centre; the stone floor and the people are at the bottom."],
         "slots": {}},
        {"id": "library", "file": "puzzles/library.svg", "name": "Reassemble the photo",
         "exhibit": "The torn photo of the library",
         "story": "A photo of the Teresa e Alexandre Soares dos Santos Library, found torn into {pieces} pieces "
                  "in the {location}. Put it back together.",
         "hints": ["The library's name runs across the white façade at the top left; the side of the building is on the right.",
                   "The lit glass entrance is in the middle of the bottom half; the steps and lamps are below it."],
         "slots": {}},
        {"id": "campus", "file": "puzzles/campus.svg", "name": "Reassemble the photo",
         "exhibit": "The torn photo of the campus",
         "story": "A photo of the NOVA SBE campus at sunset, found torn into {pieces} pieces in the {location}. "
                  "Put it back together.",
         "hints": ["The sunset sky is in the top row; the sea and the sun sit just above the long white building.",
                   "The school's name runs across the middle; the lawns, paths and trees are at the bottom."],
         "slots": {}},
        {"id": "deck", "file": "puzzles/deck.svg", "name": "Reassemble the photo",
         "exhibit": "The torn photo of the Main Deck",
         "story": "A photo of the Main Deck at night, found torn into {pieces} pieces in the {location}. "
                  "Put it back together.",
         "hints": ["The moon is at the top centre; the white wings close in from the left and the right.",
                   "The wooden deck widens toward the bottom, where its name plate and a bench are."],
         "slots": {}},
        {"id": "auditorium", "file": "puzzles/auditorium.svg", "name": "Reassemble the photo",
         "exhibit": "The torn photo of the Grand Auditorium",
         "story": "A photo of the empty Grand Auditorium, found torn into {pieces} pieces in the {location}. "
                  "Put it back together.",
         "hints": ["The screen with the NOVA name is at the top centre, between the wooden walls.",
                   "The stage and the lectern are in the middle; the red rows of seats fan out across the bottom."],
         "slots": {}},
    ],
    "scratch": [
        {"id": "skylight", "file": "scratchcards/skylight.svg", "name": "Rub to reveal",
         "exhibit": "The print of the atrium roof", "verb": "Rub the coating away with your finger.",
         "cover": "RUB TO REVEAL",
         "story": "A photo print found face down in the {location}, covered in grey coating. Rub it clean to see "
                  "where it was taken.",
         "slots": {}},
        {"id": "library-night", "file": "scratchcards/library-night.svg", "name": "Rub to reveal",
         "exhibit": "The print of the library at night", "verb": "Rub the coating away with your finger.",
         "cover": "RUB TO REVEAL",
         "story": "A photo print found face down in the {location}, covered in grey coating. Rub it clean to see "
                  "where it was taken.",
         "slots": {}},
        {"id": "facade", "file": "scratchcards/facade.svg", "name": "Rub to reveal",
         "exhibit": "The print of the building's corner", "verb": "Rub the coating away with your finger.",
         "cover": "RUB TO REVEAL",
         "story": "A photo print found face down in the {location}, covered in grey coating. Rub it clean to see "
                  "where it was taken.",
         "slots": {}},
        {"id": "stairs", "file": "scratchcards/stairs.svg", "name": "Rub to reveal",
         "exhibit": "The print of the staircase", "verb": "Rub the coating away with your finger.",
         "cover": "RUB TO REVEAL",
         "story": "A photo print found face down in the {location}, covered in grey coating. Rub it clean to see "
                  "where it was taken.",
         "slots": {}},
        {"id": "beach", "file": "scratchcards/beach.svg", "name": "Rub to reveal",
         "exhibit": "The print of Carcavelos beach", "verb": "Rub the coating away with your finger.",
         "cover": "RUB TO REVEAL",
         "story": "A photo print found face down in the {location}, covered in grey coating. Rub it clean to see "
                  "where it was taken.",
         "slots": {}},
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
