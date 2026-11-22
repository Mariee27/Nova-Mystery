"""Rules of NOVA MYSTERY.

Everything in this file is a pure function: it gets a game (a plain dict),
returns a NEW game, and never changes the one it was given. If an action is
not allowed it raises Rejected, and nothing has changed.

No Streamlit and no database code belongs in here.
"""

import copy
import random
import secrets
import unicodedata

import balance
import content
import generator
import minigames

PHASES = ["LOBBY", "REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE", "RESULT", "ABORTED"]
DURATIONS = {"REVEAL": 30, "INVESTIGATION": 300, "DISCUSSION": 180, "VOTE": 60}
# The investigation has ROUNDS rounds. Each round lasts at most DURATIONS["INVESTIGATION"]
# seconds and ends early when every online player has made their one move or has no move
# left (nothing to search, nothing to share). Interrogations happen out loud, not in the app.
ROUNDS = 3
HOT_SEAT_SECONDS = 45   # how long one suspect is grilled out loud in the discussion
LOCKED_PLACES = 2      # places that are locked at the start (the crime scene is always one)
NEXT_PHASE = {
    "REVEAL": "INVESTIGATION",
    "INVESTIGATION": "DISCUSSION",
    "DISCUSSION": "VOTE",
    "VOTE": "RESULT",
}
OFFLINE_AFTER = 45     # seconds without a sign from a phone: then the player counts as offline
MIN_PLAYERS = 4
MAX_PLAYERS = 6
MIN_ONLINE = 3
PAUSE_LIMIT = 180      # seconds a game waits, paused, for players to come back before it ends
MAX_TEXT = 140
MAX_NAME = 20
MAX_CLUE_TEXT = 200
STRONG_KINDS = {"scene", "alibi_broken"}
FORBIDDEN_WORDS = ("murderer", "killer")
DEMO_SEED = 2026
# Keys that would give the solution away. They are removed from the public log
# until the game is over.
HIDDEN_LOG_KEYS = ("implicates", "clue_kind", "planted")


def max_minutes():
    """The longest a game can take once it has started: the card, every round, discussion, vote."""
    seconds = sum(DURATIONS.values()) + DURATIONS["INVESTIGATION"] * (ROUNDS - 1)
    return -(-seconds // 60)


class Rejected(Exception):
    """An action that the rules do not allow. The game stays unchanged."""


# ---------------------------------------------------------------- helpers

def new_token():
    """A random secret that identifies one player (22 characters)."""
    return secrets.token_urlsafe(16)


def online_ids(presence, now):
    """presence maps pid -> time of last sign of life. Online means <= 20 s ago."""
    return {pid for pid, last_seen in presence.items() if now - last_seen <= OFFLINE_AFTER}


def clean_text(text, max_length):
    """Remove control characters, trim, and check the length (1..max_length)."""
    if not isinstance(text, str):
        raise Rejected("Text is missing.")
    cleaned = "".join(ch for ch in text if ord(ch) >= 32 and ord(ch) != 127).strip()
    if len(cleaned) < 1:
        raise Rejected("Text must not be empty.")
    if len(cleaned) > max_length:
        raise Rejected(f"Text must have at most {max_length} characters.")
    return cleaned


def _player_by_token(game, token):
    for player in game["players"]:
        if token and player["token"] == token:
            return player
    raise Rejected("Unknown player.")


def _player_ids(game):
    return [player["pid"] for player in game["players"]]


def _character(game, pid):
    for character in game["case"]["characters"]:
        if character["pid"] == pid:
            return character
    raise Rejected("Unknown character.")


def _add_log(game, kind, by, text, **extra):
    entry = {"id": game["next_log_id"], "kind": kind, "by": by, "text": text}
    if game["phase"] == "INVESTIGATION":
        entry["round"] = game.get("round", 1)   # the board shows when it happened
    entry.update(extra)
    game["log"].append(entry)
    game["next_log_id"] += 1
    return entry


def _require_phase(game, *phases):
    if game["phase"] not in phases:
        raise Rejected(f"Not possible in phase {game['phase']}.")


# ---------------------------------------------------------------- lobby

def new_game(code, now, minigames=False):
    """minigames=True seals every place's clue behind a puzzle (see minigames.py)."""
    return {
        "code": code,
        "phase": "LOBBY",
        "phase_started": now,
        "deadline": None,
        "host": None,
        "next_pid": 1,
        "players": [],
        "case": None,
        "acted": [],
        "searched": [],
        "planted": False,
        "log": [],
        "next_log_id": 1,
        "votes": {},
        "scene_votes": {},   # str(pid of voter) -> location where they think Vale died
        "result": None,
        "abort_reason": None,
        "minigames": bool(minigames),
    }


def as_demo(game):
    """A demo room ("Play a demo"): it always plays case #001 the same way (see app.case_choice)."""
    game = copy.deepcopy(game)
    game["demo"] = True
    return game


# Names are what players recognise each other by, so a name must look like itself and like
# nobody else's: no invisible characters, no text-direction tricks, no look-alike letters.
BLANK_LETTERS = {"\u115f", "\u1160", "\u3164", "\uffa0", "\u2800"}   # fillers and the braille blank
INVISIBLE_CATEGORIES = {"Cf", "Cs", "Co", "Cn", "Zl", "Zp"}    # format (zero-width, direction
                                                                 # marks), private use, unassigned
MAX_MARKS = 2                       # combining accents on one letter ("Zalgo" text has dozens)
# Cyrillic and Greek letters that look exactly like Latin ones, for name_key. Capitals are
# mapped before the name is lower-cased (a Greek capital N is lower-case v-shaped).
CAPITAL_LOOK_ALIKES = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "Ё": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
    "Т": "T", "У": "Y", "Х": "X", "І": "I", "Ї": "I", "Ј": "J", "Ѕ": "S", "Ԛ": "Q", "Ԝ": "W",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
})
LOOK_ALIKES = str.maketrans({
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c",
    "т": "t", "у": "y", "х": "x", "і": "i", "ї": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ԛ": "q", "ԝ": "w",
    "ɡ": "g", "ɑ": "a", "ı": "i", "ℓ": "l",
    "α": "a", "β": "b", "ε": "e", "η": "n", "ι": "i", "κ": "k", "μ": "u", "ν": "v", "ο": "o", "ρ": "p",
    "τ": "t", "υ": "u", "χ": "x", "ω": "w",
})


def clean_name(name):
    """A player's name: normalised, single spaces, 1..MAX_NAME visible characters."""
    if not isinstance(name, str):
        raise Rejected("Text is missing.")
    name = unicodedata.normalize("NFKC", name)
    # Old-style control characters: tabs and line breaks become spaces, the rest is dropped.
    name = "".join(" " if ch in "\t\n\r\v\f" else ch for ch in name
                   if unicodedata.category(ch) != "Cc" or ch in "\t\n\r\v\f")
    if any(unicodedata.category(ch) in INVISIBLE_CATEGORIES or ch in BLANK_LETTERS for ch in name):
        raise Rejected("Names cannot contain invisible or special characters.")
    name = " ".join(name.split())            # every kind of space becomes one plain space
    marks = 0
    for ch in name:
        marks = marks + 1 if unicodedata.category(ch).startswith("M") else 0
        if marks > MAX_MARKS:
            raise Rejected("Names cannot contain invisible or special characters.")
    if not any(unicodedata.category(ch)[0] in "LN" for ch in name):
        raise Rejected("A name needs at least one letter or digit.")
    if len(name) > MAX_NAME:
        raise Rejected(f"Text must have at most {MAX_NAME} characters.")
    return name


def name_key(name):
    """Two names with the same key look alike on a screen: same letters regardless of case,
    accents, width, and Cyrillic or Greek look-alike letters."""
    name = unicodedata.normalize("NFKC", name).translate(CAPITAL_LOOK_ALIKES)
    folded = unicodedata.normalize("NFKD", name.casefold())
    letters = "".join(ch for ch in folded if not unicodedata.category(ch).startswith("M"))
    return " ".join(letters.translate(LOOK_ALIKES).split())


def join(game, name, token, now):
    _require_phase(game, "LOBBY")
    name = clean_name(name)
    if len(game["players"]) >= MAX_PLAYERS:
        raise Rejected(f"The room is full ({MAX_PLAYERS} players).")
    if any(name_key(p["name"]) == name_key(name) for p in game["players"]):
        raise Rejected("This name is already taken in this room.")
    if not token or any(p["token"] == token for p in game["players"]):
        raise Rejected("Invalid token.")
    game = copy.deepcopy(game)
    pid = game["next_pid"]
    game["players"].append({"pid": pid, "name": name, "token": token, "joined_at": now})
    game["next_pid"] = pid + 1
    if game["host"] is None:
        game["host"] = pid
    return game


def kick(game, token, target_pid, now):
    """The host removes a player from the lobby (for strangers who guessed the code)."""
    _require_phase(game, "LOBBY")
    player = _player_by_token(game, token)
    if player["pid"] != game["host"]:
        raise Rejected("Only the host can remove players.")
    if target_pid == player["pid"]:
        raise Rejected("You cannot remove yourself.")
    if target_pid not in _player_ids(game):
        raise Rejected("Unknown player.")
    game = copy.deepcopy(game)
    game["players"] = [p for p in game["players"] if p["pid"] != target_pid]
    return game


def start(game, token, online, now, seed=None, fixed_case=False, use_ai=True):
    """Start the game. The story is the AI-written one if it is ready, otherwise case #001.

    fixed_case=True always plays case #001 with its fixed seed (rehearsal mode).
    use_ai=False plays case #001 even if an AI case is ready (the host chose it). If an AI
    case was expected but cannot be used, the host gets a short note (see host_note).
    """
    _require_phase(game, "LOBBY")
    player = _player_by_token(game, token)
    if player["pid"] != game["host"]:
        raise Rejected("Only the host can start the game.")
    present = [p for p in game["players"] if p["pid"] in online]
    if not MIN_PLAYERS <= len(present) <= MAX_PLAYERS:
        raise Rejected(f"The game needs {MIN_PLAYERS} to {MAX_PLAYERS} players online.")
    if seed is None:
        seed = secrets.randbits(32)
    game = copy.deepcopy(game)
    game["players"] = copy.deepcopy(present)  # players who are offline in the lobby are dropped
    story, note = _story_for_start(game, fixed_case or not use_ai)
    try:
        if story is content.DEFAULT_STORY:
            # Case #001 is handcrafted and is built exactly as it always was.
            game["case"] = generator.build_valid_case(_player_ids(game), seed, story)
        else:
            # An AI story: tuned to medium difficulty, checked, and with its solution written down.
            game["case"] = balance.build_balanced_case(_player_ids(game), seed, story)
    except Rejected:
        if story is content.DEFAULT_STORY:
            raise
        # The AI story passed the checks but no fair case came out of it: play case #001.
        story = content.DEFAULT_STORY
        note = "The AI case could not be used, so you are playing case #001."
        game["case"] = generator.build_valid_case(_player_ids(game), seed, story)
    game["story"] = story
    if note:
        game["story_note"] = note
    _enter_phase(game, "REVEAL", now)
    return game


def _story_for_start(game, fixed_case):
    """(story, note for the host) at the start of a game."""
    ai = game.get("ai_case")
    if fixed_case or ai is None:   # demo switch, or the AI was never asked
        return content.DEFAULT_STORY, None
    if ai["status"] == "ready":
        return ai["story"], None
    if ai["status"] == "writing":
        return content.DEFAULT_STORY, "The AI case was not finished yet, so you are playing case #001."
    return content.DEFAULT_STORY, f"No AI case ({ai['reason']}), so you are playing case #001."


# ---------------------------------------------------------------- phases

def _enter_phase(game, phase, now):
    """Change the phase of an already copied game."""
    game["phase"] = phase
    game["phase_started"] = now
    game["deadline"] = now + DURATIONS[phase] if phase in DURATIONS else None
    if phase == "INVESTIGATION":
        game["round"] = 1
        game["acted"] = []
    if phase == "DISCUSSION":
        game["hot_seat"] = new_hot_seat()
    if phase == "RESULT":
        game["result"] = _compute_result(game)


def _advance(game, now):
    """End the current step of an already copied game: the next investigation round,
    or after the last round (and in every other phase) the next phase."""
    game.pop("paused", None)        # a new step starts with a running clock (tick pauses again if needed)
    if game["phase"] == "INVESTIGATION" and game.get("round", 1) < ROUNDS:
        game["round"] = game.get("round", 1) + 1
        game["acted"] = []                  # everybody gets a new move
        game["phase_started"] = now
        game["deadline"] = now + DURATIONS["INVESTIGATION"]
        return
    _enter_phase(game, NEXT_PHASE[game["phase"]], now)


def current_round(game):
    """1..ROUNDS during the investigation; 0 before it, ROUNDS + 1 after it."""
    if game["phase"] in ("LOBBY", "REVEAL"):
        return 0
    if game["phase"] == "INVESTIGATION":
        return game.get("round", 1)
    return ROUNDS + 1


def locked_until(game, location):
    """The round in which a place opens, or None if it is open now."""
    if game["case"] is None:
        return None
    opens = game["case"].get("locked", {}).get(location)
    if opens is None or current_round(game) >= opens:
        return None
    return opens


def has_move(game, pid):
    """Whether the player could still make a move this round: an open place nobody has
    searched yet, or one of their own clues that is not public yet."""
    if any(locked_until(game, loc) is None and loc not in game["searched"]
           for loc in story_of(game)["locations"]):
        return True
    public = {e.get("clue_id") for e in game["log"]}
    return any(c["id"] not in public for c in _character(game, pid)["clues"])


def _name(game, pid):
    for player in game["players"]:
        if player["pid"] == pid:
            return player["name"]
    return "Someone"


def end_phase(game, token, online, now):
    _require_phase(game, *NEXT_PHASE)
    player = _player_by_token(game, token)
    if player["pid"] != game["host"]:
        raise Rejected("Only the host can end a phase.")
    game = copy.deepcopy(game)
    _advance(game, now)
    return game


def tick(game, online, now):
    """Called every time a screen asks for the current state.

    Order: host handover, abort, timer, early end. At most one phase change per call.
    """
    ai = game.get("ai_case")
    if (game["phase"] == "LOBBY" and ai and ai["status"] == "writing"
            and now - ai.get("since", now) > AI_WRITING_TIMEOUT):
        # The writing thread is gone (a server restart) or the AI hangs: stop waiting.
        return ai_case_failed(game, "the AI took too long", now)
    if game["phase"] in ("RESULT", "ABORTED"):
        return game
    pids = _player_ids(game)
    online_players = [pid for pid in pids if pid in online]
    new = None  # copy only if something really changes

    # 1. Host handover: the first online human in join order takes over (never a demo bot).
    bots = set(bot_ids(game))
    online_humans = [pid for pid in online_players if pid not in bots]
    if game["host"] not in online and online_humans:
        new = copy.deepcopy(game)
        new["host"] = online_humans[0]

    if game["phase"] in NEXT_PHASE:
        # 2. Fewer than 3 players online: the game pauses (the clock stops) and waits for them.
        # Phones drop out when a screen locks or a tab is in the background; they come back.
        # Only after PAUSE_LIMIT seconds without enough players does the game end.
        paused = game.get("paused")
        if len(online_players) < MIN_ONLINE:
            if paused is None:
                new = new or copy.deepcopy(game)
                new["paused"] = {"since": now, "left": max(0.0, (game["deadline"] or now) - now)}
                new["deadline"] = None
                return new
            if now - paused["since"] >= PAUSE_LIMIT:
                new = new or copy.deepcopy(game)
                new.pop("paused", None)
                new["phase"] = "ABORTED"
                new["phase_started"] = now
                new["deadline"] = None
                new["abort_reason"] = (
                    f"Fewer than {MIN_ONLINE} players were online for {PAUSE_LIMIT // 60} minutes. "
                    "Please create a new room."
                )
                return new
            return new or game                  # still waiting: no timer, no early end
        if paused is not None:                  # enough players again: the clock runs on
            new = new or copy.deepcopy(game)
            new["deadline"] = now + paused["left"]
            new.pop("paused")
            return new
        # 3. Timer, 4. early end.
        # A player with nothing left to search or share is not waited for.
        everyone_acted = game["phase"] == "INVESTIGATION" and all(
            pid in game["acted"] or not has_move(game, pid) for pid in online_players)
        everyone_voted = all(str(pid) in game["votes"] for pid in online_players)
        if (
            now >= game["deadline"]
            or (game["phase"] == "INVESTIGATION" and everyone_acted)
            or (game["phase"] == "VOTE" and everyone_voted)
        ):
            new = new or copy.deepcopy(game)
            _advance(new, now)
            return new
        # 5. The hot seat in the discussion: start it when everybody has picked, end it on time.
        if game["phase"] == "DISCUSSION":
            changed = _hot_seat_tick(new or game, online_players, now)
            if changed is not None:
                return changed
    return new or game


# ---------------------------------------------------------------- actions

def _begin_action(game, token):
    """Checks shared by search and share. Returns the acting player."""
    _require_phase(game, "INVESTIGATION")
    player = _player_by_token(game, token)
    if player["pid"] in game["acted"]:
        raise Rejected("You have already used your action in this round.")
    return player


def search(game, token, location, now, proof=None):
    """Search a place and find its one clue.

    Not allowed: outside the investigation, a second move in the same round, an unknown
    place, a place that is still locked, or a place that has already been searched.
    In a room with mini-games, a human player must also send a `proof` that solves the
    place's puzzle (checked by minigames.verify); demo bots search without one.
    """
    player = _begin_action(game, token)
    if location not in story_of(game)["locations"]:
        raise Rejected("Unknown location.")
    opens = locked_until(game, location)
    if opens is not None:
        raise Rejected(f"This place is locked. It opens in round {opens}.")
    if location in game["searched"]:
        raise Rejected("This place has already been searched. Pick another one.")
    if minigames.enabled(game) and not player.get("bot") and not minigames.verify(game, location, proof):
        raise Rejected("The evidence is still sealed. Solve the puzzle first.")
    clue = next(c for c in game["case"]["location_clues"] if c["location"] == location)
    game = copy.deepcopy(game)
    game["searched"].append(location)
    game["acted"].append(player["pid"])
    _add_log(game, "search", player["pid"], clue["text"], location=location,
             clue_id=clue["id"], implicates=clue["implicates"], clue_kind=clue["kind"],
             planted=False)
    return game


EVIDENCE_KINDS = ("search", "share")   # log entries that are public evidence


def share(game, token, clue_id, now):
    player = _begin_action(game, token)
    clue = next((c for c in _character(game, player["pid"])["clues"] if c["id"] == clue_id), None)
    if clue is None:
        raise Rejected("This is not one of your clues.")
    if any(e.get("clue_id") == clue_id for e in game["log"]):
        raise Rejected("This clue is already public.")
    game = copy.deepcopy(game)
    game["acted"].append(player["pid"])
    _add_log(game, "share", player["pid"], clue["text"], clue_id=clue_id,
             implicates=clue["implicates"], clue_kind=clue["kind"], planted=False)
    return game


MAX_WRONG_TRIES = 6   # wrong puzzle answers per player, place and round: no guessing all 10 000 codes


def wrong_tries(game, pid, location):
    """How often this player gave a wrong answer to this place's puzzle in this round."""
    return game.get("wrong_tries", {}).get(f"{pid}|{location}|{game.get('round')}", 0)


def note_wrong_try(game, token, location, now):
    """Count one wrong puzzle answer. Kept in the game, so a new browser tab does not reset it."""
    _require_phase(game, "INVESTIGATION")
    player = _player_by_token(game, token)
    game = copy.deepcopy(game)
    tries = game.setdefault("wrong_tries", {})
    key = f"{player['pid']}|{location}|{game.get('round')}"
    tries[key] = tries.get(key, 0) + 1
    return game


def plant_locations(game):
    """Locations where the murderer may plant a clue.

    Only locations nobody has searched yet (the planted clue takes the place of
    the real one, so a location never shows two results), and never a location
    whose real clue points strongly to the murderer (the case stays solvable).
    """
    if game["case"] is None:
        return []
    murderer = game["case"]["murderer"]
    return [
        clue["location"] for clue in game["case"]["location_clues"]
        if clue["location"] not in game["searched"]
        and locked_until(game, clue["location"]) is None
        and not (clue["implicates"] == murderer and clue["kind"] in STRONG_KINDS)
    ]


def plant(game, token, target_pid, location, now):
    """The murderer's extra move: one fake clue per game. Looks like a search result."""
    _require_phase(game, "INVESTIGATION")
    player = _player_by_token(game, token)
    if player["pid"] != game["case"]["murderer"]:
        raise Rejected("This action is not available to you.")
    if game["planted"]:
        raise Rejected("You have already planted a clue in this game.")
    if target_pid == player["pid"] or target_pid not in _player_ids(game):
        raise Rejected("Pick another player.")
    if location not in story_of(game)["locations"]:
        raise Rejected("Unknown location.")
    if location not in plant_locations(game):
        raise Rejected("You cannot plant a clue there. Pick another location.")
    # Same wording as a real red herring, so the fake clue does not stand out.
    role = _character(game, target_pid)["role"]
    text = content.TEMPLATES["herring"].format(
        location=location, rumor=story_of(game)["roles"][role]["rumor"])
    game = copy.deepcopy(game)
    game["planted"] = True
    # The location now counts as searched: its real clue is covered up.
    game["searched"].append(location)
    # "by" stays empty so that the log does not show who planted the clue.
    _add_log(game, "search", None, text, location=location, clue_id=None,
             implicates=target_pid, clue_kind="suspicious", planted=True)
    return game


def vote(game, token, target_pid, now, scene=None):
    """The final accusation: who did it, and (optionally) where Vale really died."""
    _require_phase(game, "VOTE")
    player = _player_by_token(game, token)
    if str(player["pid"]) in game["votes"]:
        raise Rejected("You have already voted.")
    if target_pid == player["pid"]:
        raise Rejected("You cannot vote for yourself.")
    if target_pid not in _player_ids(game):
        raise Rejected("Unknown player.")
    if scene is not None and scene not in story_of(game)["locations"]:
        raise Rejected("Unknown location.")
    game = copy.deepcopy(game)
    game["votes"][str(player["pid"])] = target_pid
    if scene is not None:
        game.setdefault("scene_votes", {})[str(player["pid"])] = scene
    return game


def _clear_winner(tally):
    """The key with strictly the most votes, or None on a tie or without votes."""
    if not tally:
        return None
    best = max(tally.values())
    leaders = [key for key, count in tally.items() if count == best]
    return leaders[0] if len(leaders) == 1 else None


def _compute_result(game):
    murderer = game["case"]["murderer"]
    tally = {}   # only players who received at least one vote appear here
    for target in game["votes"].values():
        tally[str(target)] = tally.get(str(target), 0) + 1
    scene_tally = {}
    for scene in game.get("scene_votes", {}).values():
        scene_tally[scene] = scene_tally.get(scene, 0) + 1
    accused = _clear_winner(tally)
    # Detectives only win with a clear majority against the murderer. A tie is not enough.
    winner = "detectives" if accused == str(murderer) else "murderer"
    if winner == "detectives":
        solved_scene = _clear_winner(scene_tally) == game["case"]["murder_location"]
        ending = "truth" if solved_scene else "incomplete"
    else:
        ending = "wrong" if accused is not None else "escaped"
    exposed = {e.get("implicates") for e in game["log"] if e.get("clue_kind") == "suspicious"}
    secrets_kept = [pid for pid in _player_ids(game) if pid != murderer and pid not in exposed]
    result = {
        "winner": winner,
        "ending": ending,
        "murderer": murderer,
        "murder_location": game["case"]["murder_location"],
        "tally": tally,
        "scene_tally": scene_tally,
        # Every single ballot, so the room can see afterwards who voted for whom.
        # The result only becomes public in RESULT (see public_view), so the ballots
        # stay secret while people are still voting.
        "votes": dict(game["votes"]),                     # str(voter pid) -> accused pid
        "scene_votes": dict(game.get("scene_votes", {})),  # str(voter pid) -> location
        "secrets_kept": secrets_kept,
    }
    if "solution" in game["case"]:
        # AI cases only: why the red herrings pointed where they did, and what cleared them.
        result["red_herrings"] = [
            {key: h[key] for key in ("points_at", "explained_by", "cleared_by")}
            for h in game["case"]["solution"]["red_herrings"]]
    return result


# ---------------------------------------------------------------- hot seat (discussion)
#
# Everybody sits in one room, so the interrogation happens out loud. The phones only pick
# who is grilled next and rate the answers. Flow:
#   1. Every player picks a suspect (not themselves, not someone who already sat there).
#   2. When everybody online has picked (or the host starts it), the suspect with the most
#      picks sits in the hot seat for HOT_SEAT_SECONDS. Ties: chance decides (hot_seat_tie).
#   3. The others rate on their phone: "believe" or "lie". The board shows only the counts.
#   4. When the time is up the counts go into the history and the next pick starts.

HOT_SEAT_VERDICTS = ("believe", "lie")


def new_hot_seat():
    return {"picks": {}, "seat": None, "until": None, "ratings": {}, "history": []}


def _hot(game):
    """The hot seat of a game (older saved games may not have one yet)."""
    return game.get("hot_seat") or new_hot_seat()


def hot_seat_candidates(game):
    """Who can still be put in the hot seat: everybody who has not sat there yet."""
    grilled = {entry["pid"] for entry in _hot(game)["history"]}
    return [pid for pid in _player_ids(game) if pid not in grilled]


def _can_pick(game, pid):
    """A player can pick if there is somebody other than themselves left to grill."""
    return any(other != pid for other in hot_seat_candidates(game))


def pick_hot_seat(game, token, target_pid, now):
    """A player picks who should sit in the hot seat next."""
    _require_phase(game, "DISCUSSION")
    player = _player_by_token(game, token)
    hot = _hot(game)
    if hot["seat"] is not None:
        raise Rejected("Somebody is already in the hot seat.")
    if target_pid == player["pid"]:
        raise Rejected("You cannot put yourself in the hot seat.")
    if target_pid not in hot_seat_candidates(game):
        raise Rejected("Pick somebody who has not been in the hot seat yet.")
    game = copy.deepcopy(game)
    game["hot_seat"] = hot = copy.deepcopy(hot)
    hot["picks"][str(player["pid"])] = target_pid
    return game


def _start_hot_seat(game, now):
    """Seat the suspect with the most picks (an already copied game with at least one pick)."""
    hot = game["hot_seat"]
    counts = {}
    for target in hot["picks"].values():
        counts[target] = counts.get(target, 0) + 1
    most = max(counts.values())
    hot["seat"] = hot_seat_tie(game, [pid for pid, n in counts.items() if n == most])
    hot["until"] = now + HOT_SEAT_SECONDS
    hot["picks"] = {}
    hot["ratings"] = {}


def hot_seat_tie(game, tied):
    """Chance decides between suspects with the same number of picks.
    The dice are seeded with the room code and the number of earlier hot seats: different in
    every room and every time, but the same game state always gives the same answer
    (so a test can check it, and two screens never disagree)."""
    tied = sorted(tied)
    if len(tied) == 1:
        return tied[0]
    dice = random.Random(f"{game['code']}-{len(game['hot_seat']['history'])}")
    return dice.choice(tied)


def start_hot_seat(game, token, now):
    """The host starts the hot seat now, with the picks made so far."""
    _require_phase(game, "DISCUSSION")
    player = _player_by_token(game, token)
    if player["pid"] != game["host"]:
        raise Rejected("Only the host can start the hot seat.")
    hot = _hot(game)
    if hot["seat"] is not None:
        raise Rejected("Somebody is already in the hot seat.")
    if not hot["picks"]:
        raise Rejected("Nobody has picked a suspect yet.")
    game = copy.deepcopy(game)
    game["hot_seat"] = copy.deepcopy(hot)
    _start_hot_seat(game, now)
    return game


def rate_hot_seat(game, token, verdict, now):
    """A player rates the answers of the suspect in the hot seat: "believe" or "lie".
    A player may change their mind until the time is up."""
    _require_phase(game, "DISCUSSION")
    player = _player_by_token(game, token)
    hot = _hot(game)
    if hot["seat"] is None:
        raise Rejected("Nobody is in the hot seat.")
    if hot["seat"] == player["pid"]:
        raise Rejected("You cannot rate yourself.")
    if verdict not in HOT_SEAT_VERDICTS:
        raise Rejected("Choose believe or lie.")
    game = copy.deepcopy(game)
    game["hot_seat"] = hot = copy.deepcopy(hot)
    hot["ratings"][str(player["pid"])] = verdict
    return game


def _rating_counts(hot):
    votes = list(hot["ratings"].values())
    return votes.count("believe"), votes.count("lie")


def _hot_seat_tick(game, online_players, now):
    """End the hot seat on time, or start it when every online player who can pick has picked.
    Returns a changed copy, or None if nothing happens."""
    hot = _hot(game)
    if hot["seat"] is not None:
        if now < hot["until"]:
            return None
        game = copy.deepcopy(game)
        hot = game["hot_seat"]
        believe, lie = _rating_counts(hot)
        hot["history"].append({"pid": hot["seat"], "believe": believe, "lie": lie})
        hot.update(seat=None, until=None, ratings={})
        return game
    pickers = [pid for pid in online_players if _can_pick(game, pid)]
    if pickers and all(str(pid) in hot["picks"] for pid in pickers):
        game = copy.deepcopy(game)
        game["hot_seat"] = copy.deepcopy(hot)
        _start_hot_seat(game, now)
        return game
    return None


def hot_seat_view(game):
    """The public part of the hot seat (board and every phone), or None outside the discussion:
    who sits there, until when, and only COUNTS of the picks and ratings.
    Who picked or rated whom stays private (see my_hot_seat)."""
    if game["phase"] != "DISCUSSION":
        return None
    hot = _hot(game)
    picks = {}
    for target in hot["picks"].values():
        picks[target] = picks.get(target, 0) + 1
    believe, lie = _rating_counts(hot)
    return {
        "seat": hot["seat"],
        "until": hot["until"],
        "picks": picks,
        "picked": len(hot["picks"]),
        "believe": believe,
        "lie": lie,
        "candidates": hot_seat_candidates(game),
        "history": copy.deepcopy(hot["history"]),
    }


def my_hot_seat(game, token):
    """One player's own pick and rating, or None for an unknown token / outside the discussion."""
    player = next((p for p in game["players"] if token and p["token"] == token), None)
    if player is None or game["phase"] != "DISCUSSION":
        return None
    hot = _hot(game)
    return {"pick": hot["picks"].get(str(player["pid"])),
            "rating": hot["ratings"].get(str(player["pid"]))}


# ---------------------------------------------------------------- demo suspects (bots)
#
# For presentations with fewer than 4 people. A bot is an ordinary player with
# "bot": True. It is always online, never becomes host, and plays by the same rules
# through the same functions as everybody else. It only "knows" what a player in
# its seat would know: its own card and the public log. It never reads the solution.

BOT_FIRST_MOVE = 6    # seconds after a phase starts before the first bot moves
BOT_STEP = 4          # every further bot waits this much longer, so moves arrive one by one


def bot_ids(game):
    return [p["pid"] for p in game["players"] if p.get("bot")]


def with_bots(game, online):
    """Bots have no screen that sends heartbeats, so they always count as online."""
    return set(online) | set(bot_ids(game))


def add_bot(game, token, now):
    """The host adds one demo suspect to the lobby."""
    _require_phase(game, "LOBBY")
    player = _player_by_token(game, token)
    if player["pid"] != game["host"]:
        raise Rejected("Only the host can add demo suspects.")
    taken = {name_key(p["name"]) for p in game["players"]}
    name = next((f"{first} (demo)" for first in content.DEMO_NAMES
                 if name_key(f"{first} (demo)") not in taken), None)
    if name is None or len(game["players"]) >= MAX_PLAYERS:
        raise Rejected(f"The room is full ({MAX_PLAYERS} players).")
    game = join(game, name, new_token(), now)
    game["players"][-1]["bot"] = True   # join returned a fresh copy, so this is safe
    return game


def _bot_reading(game, pid):
    """Texts a bot may use: the public evidence and its own private clues."""
    texts = [e["text"] for e in game["log"] if e["kind"] in EVIDENCE_KINDS]
    texts += [c["text"] for c in _character(game, pid)["clues"]]
    return texts


def _bot_suspect(game, pid):
    """Whom the bot accuses: the role that the evidence it can read points at most."""
    scores = {other: 0 for other in _player_ids(game) if other != pid}
    role_of = {c["pid"]: c["role"] for c in game["case"]["characters"]}
    for text in _bot_reading(game, pid):
        if any(word in text for word in ("belongs to", "no entry by", "hurrying")):
            weight = 3          # physical evidence, a broken alibi, a witness
        elif "was seen" in text:
            weight = 1          # a rumor
        else:
            continue
        for other in scores:
            if role_of[other] in text:
                scores[other] += weight
    best = max(scores.values())
    return min(other for other, score in scores.items() if score == best)


def _bot_scene(game, pid):
    for text in _bot_reading(game, pid):
        if "belongs to" in text or "hurrying" in text:
            for location in story_of(game)["locations"]:
                if location in text:
                    return location
    return None


def _bot_investigate(game, bot, index, now):
    pid = bot["pid"]
    # With mini-games a human needs 30 to 90 seconds to open a place. Demo bots wait until
    # every human has made their move, so they never snatch a place from someone solving it.
    if minigames.enabled(game) and any(not p.get("bot") and p["pid"] not in game["acted"]
                                       for p in game["players"]):
        return game
    places = [loc for loc in story_of(game)["locations"] if locked_until(game, loc) is None]
    free = [loc for loc in places if loc not in game["searched"]]
    if pid == game["case"]["murderer"]:
        # A guilty bot does not search where its own traces are.
        mine = {c["location"] for c in game["case"]["location_clues"]
                if c["implicates"] == pid and c["kind"] in STRONG_KINDS}
        free = [loc for loc in free if loc not in mine]
    # Places are scarce (one clue each): a bot leaves the last open place to a human
    # player who has not moved yet.
    humans_waiting = any(not p.get("bot") and p["pid"] not in game["acted"] for p in game["players"])
    if humans_waiting and len(free) <= 1:
        free = []
    if free:
        return search(game, bot["token"], free[index % len(free)], now)
    public = {e.get("clue_id") for e in game["log"]}
    clue = next((c for c in _character(game, pid)["clues"] if c["id"] not in public), None)
    if clue is not None:
        return share(game, bot["token"], clue["id"], now)
    # Nothing it would rather do: a guilty bot searches its own place after all, so the round
    # can still end early. Places it leaves to a waiting human stay theirs.
    rest = [loc for loc in places if loc not in game["searched"]]
    if rest and not humans_waiting:
        return search(game, bot["token"], rest[index % len(rest)], now)
    return game       # nothing left at all: the round does not wait for it (has_move)


def _bot_hot_seat(game, bot, now):
    """A bot picks the suspect it trusts least, and calls them a liar in the hot seat."""
    pid = bot["pid"]
    hot = _hot(game)
    suspect = _bot_suspect(game, pid)
    if hot["seat"] is None and str(pid) not in hot["picks"] and _can_pick(game, pid):
        options = [other for other in hot_seat_candidates(game) if other != pid]
        target = suspect if suspect in options else options[0]
        return pick_hot_seat(game, bot["token"], target, now)
    if hot["seat"] is not None and hot["seat"] != pid and str(pid) not in hot["ratings"]:
        return rate_hot_seat(game, bot["token"], "lie" if hot["seat"] == suspect else "believe", now)
    return game


def bot_moves(game, now):
    """Let every bot make the moves that are due. Returns the same game if nothing happens."""
    bots = [p for p in game["players"] if p.get("bot")]
    if not bots or game["phase"] not in ("INVESTIGATION", "DISCUSSION", "VOTE"):
        return game
    elapsed = now - game["phase_started"]
    for index, bot in enumerate(bots):
        pid = bot["pid"]
        due = elapsed >= BOT_FIRST_MOVE + BOT_STEP * index
        if game["phase"] == "INVESTIGATION" and due and pid not in game["acted"]:
            game = _bot_investigate(game, bot, index, now)
        if game["phase"] == "DISCUSSION" and due:
            game = _bot_hot_seat(game, bot, now)
        if game["phase"] == "VOTE" and due and str(pid) not in game["votes"]:
            game = vote(game, bot["token"], _bot_suspect(game, pid), now,
                        scene=_bot_scene(game, pid))
    return game


# ---------------------------------------------------------------- views

def public_view(game, online):
    """What everybody may see (board and all phones). No secrets before RESULT."""
    finished = game["phase"] == "RESULT"
    log = []
    for entry in game["log"]:
        entry = dict(entry)
        if not finished:
            for key in HIDDEN_LOG_KEYS:
                entry.pop(key, None)
            if entry["kind"] == "search":
                # A planted clue has no searcher. Hide the searcher of every
                # search result so that a planted clue does not stand out.
                entry["by"] = None
        log.append(entry)
    characters = None
    if finished:
        characters = []
        for character in game["case"]["characters"]:
            character = copy.deepcopy(character)
            character["name"] = _name(game, character["pid"])
            characters.append(character)
    # Roles are public once the game runs: clues talk about roles, so everybody
    # must know who plays whom. Who the murderer is stays secret.
    role_of = {}
    if game["case"] is not None:
        role_of = {c["pid"]: c["role"] for c in game["case"]["characters"]}
    return {
        "code": game["code"],
        "phase": game["phase"],
        "deadline": game["deadline"],
        "demo": bool(game.get("demo")),
        # While too few players are online: when the pause began (the game ends PAUSE_LIMIT later).
        "paused_since": (game.get("paused") or {}).get("since"),
        "players": [
            {
                "pid": p["pid"],
                "name": p["name"],
                "role": role_of.get(p["pid"]),
                "online": p["pid"] in online,
                "is_host": p["pid"] == game["host"],
                "acted": p["pid"] in game["acted"],
                "voted": str(p["pid"]) in game["votes"],
            }
            for p in game["players"]
        ],
        "log": log,
        "searched": list(game["searched"]),
        "result": copy.deepcopy(game["result"]) if finished else None,
        "abort_reason": game["abort_reason"],
        "characters": characters,
    }


def private_view(game, token):
    """What ONE player may see: only their own card. None for an unknown token."""
    player = next((p for p in game["players"] if token and p["token"] == token), None)
    if player is None:
        return None
    pid = player["pid"]
    view = {
        "pid": pid,
        "name": player["name"],
        "is_host": pid == game["host"],
        "phase": game["phase"],
        "acted": pid in game["acted"],
        "voted": str(pid) in game["votes"],
        "role": None,
        "intro": None,
        "alibi": None,
        "secret": None,
        "is_murderer": False,
        "clues": [],
        "can_plant": False,
        "plant_locations": [],
        "last_move": None,
        "puzzles": {},
    }
    if game["case"] is None:
        return view
    character = _character(game, pid)
    public_clue_ids = {e.get("clue_id") for e in game["log"]}
    is_murderer = pid == game["case"]["murderer"]
    can_plant = (is_murderer and not game["planted"] and game["phase"] == "INVESTIGATION"
                 and bool(plant_locations(game)))
    view.update({
        "role": character["role"],
        "intro": character["intro"],
        "alibi": character["alibi"],
        "secret": character["secret"],
        "is_murderer": is_murderer,
        "clues": [
            {"id": c["id"], "text": c["text"], "shared": c["id"] in public_clue_ids}
            for c in character["clues"]
        ],
        "can_plant": can_plant,
        "plant_locations": plant_locations(game) if can_plant else [],
        "last_move": last_move(game, pid),
        # The sealed exhibits of this case (mini-games). Never contains an answer.
        "puzzles": ({p["location"]: p for p in minigames.specs(game)}
                    if game["phase"] == "INVESTIGATION" else {}),
    })
    return view


def last_move(game, pid):
    """The player's own move in the current round (for the 'Move made.' screen), or None.
    Only this player's own entry: who searched stays hidden from everybody else."""
    if game["phase"] != "INVESTIGATION":
        return None
    for entry in reversed(game["log"]):
        if (entry["by"] == pid and entry["kind"] in ("search", "share")
                and entry.get("round") == game.get("round")):
            return {key: entry[key] for key in ("id", "kind", "text", "location", "target", "evidence")
                    if key in entry}
    return None


# ---------------------------------------------------------------- case validator

def validate_case(case, pids, story=None):
    """Returns a list of problems. An empty list means the case is fair and solvable."""
    story = story or content.DEFAULT_STORY
    problems = []
    murderer = case.get("murderer")
    characters = case.get("characters", [])
    location_clues = case.get("location_clues", [])

    # 1. one murderer who is a player, one character per player
    if murderer not in pids:
        problems.append("The murderer is not a player of this game.")
    if sorted(c["pid"] for c in characters) != sorted(pids):
        problems.append("There must be exactly one character per player.")

    all_clues = list(location_clues)
    for character in characters:
        all_clues.extend(character["clues"])

    # 2. the murderer can be found
    strong = [c for c in all_clues if c["implicates"] == murderer and c["kind"] in STRONG_KINDS]
    strong_at_locations = [c for c in strong if c in location_clues]
    if len(strong) < 2:
        problems.append("Fewer than 2 strong clues point to the murderer.")
    if len(strong_at_locations) < 1:
        problems.append("No location clue points strongly to the murderer.")

    # 3. innocents are never strongly accused, and at most one red herring each
    for pid in pids:
        if pid == murderer:
            continue
        against = [c for c in all_clues if c["implicates"] == pid]
        if any(c["kind"] in STRONG_KINDS for c in against):
            problems.append(f"A strong clue points to innocent player {pid}.")
        if sum(1 for c in against if c["kind"] == "suspicious") > 1:
            problems.append(f"More than one suspicious clue points to innocent player {pid}.")

    # 4. every reference exists
    for clue in all_clues:
        if clue["implicates"] is not None and clue["implicates"] not in pids:
            problems.append(f"Clue {clue['id']} points to an unknown player.")
    for clue in location_clues:
        if clue.get("location") not in story["locations"]:
            problems.append(f"Clue {clue['id']} has an unknown location.")
    for character in characters:
        if character["role"] not in story["roles"]:
            problems.append(f"Unknown role {character['role']}.")

    # 5. texts: no giveaway words, sensible length
    for clue in all_clues:
        text = clue["text"]
        if any(word in text.lower() for word in FORBIDDEN_WORDS):
            problems.append(f"Clue {clue['id']} gives the solution away.")
        if not 1 <= len(text) <= MAX_CLUE_TEXT:
            problems.append(f"Clue {clue['id']} must have 1 to {MAX_CLUE_TEXT} characters.")

    # 6. counts
    if sorted(c.get("location", "") for c in location_clues) != sorted(story["locations"]):
        problems.append("There must be exactly one clue per location.")
    for character in characters:
        if len(character["clues"]) != 2:
            problems.append(f"Player {character['pid']} must have exactly 2 private clues.")
    # 7. rounds: locked places (cases built before the rounds have none)
    locked = case.get("locked") or {}
    if locked:
        if case.get("murder_location") not in locked:
            problems.append("The crime scene must be locked at the start.")
        if len(locked) != LOCKED_PLACES:
            problems.append(f"Exactly {LOCKED_PLACES} places must be locked at the start.")
        for location, opens in locked.items():
            if location not in story["locations"] or not 2 <= opens <= ROUNDS:
                problems.append(f"{location} must open in a round from 2 to {ROUNDS}.")
        if not any(c["implicates"] == murderer and c["kind"] in STRONG_KINDS
                   and c["location"] not in locked for c in location_clues):
            problems.append("No strong clue against the murderer is open in round 1.")

    ids = [c["id"] for c in all_clues]
    if len(ids) != len(set(ids)):
        problems.append("Clue ids must be unique.")
    return problems


# ---------------------------------------------------------------- the story of a game
#
# Every game has a story: the texts of its case (victim, locations, roles, ...).
# It is case #001 from content.py, or a new one written by an AI while the lobby
# fills (see ai.py and app.py). The AI only writes words: who did it, where, and
# which clue points to whom is still decided by generator.py and checked by
# validate_case. A story from the AI is checked by validate_story first.
#
# Lifecycle of an AI case, stored in game["ai_case"] (only in the lobby):
#   {"status": "writing"}  ->  {"status": "ready", "story": {...}}
#                          ->  {"status": "failed", "reason": "..."}

STORY_LIMITS = {   # the longest allowed text per field, in characters
    # Generous where a longer text only means more reading. Tight where a text becomes
    # part of a clue: every clue must stay within MAX_CLUE_TEXT (checked by validate_case).
    "case_title": 80, "victim": 60, "victim_short": 30, "found_place": 80, "briefing": 900,
    "location": 30, "flavor": 300, "neutral_clue": 200, "role": 40, "dossier": 240,
    "intro": 360, "trace": 90, "secret": 240, "rumor": 140, "ending_title": 60,
    "ending_text": 450, "intro_line": 60,
}
NUMBER_OF_INTRO_LINES = len(content.INTRO_LINES)   # 6, the 4th one is shown in red
ENDING_KEYS = ("truth", "incomplete", "wrong", "escaped")
# The demo suspects (bots) read these phrases as evidence, so ordinary texts must not use them.
EVIDENCE_PHRASES = ("belongs to", "no entry by", "hurrying", "was seen")
NUMBER_OF_LOCATIONS = len(content.LOCATIONS)   # 5
NUMBER_OF_ROLES = len(content.ROLES)           # 6
FIXED_CASE_NOTE = "Case #001 will be played."


def story_of(game):
    """The story of this game. Before the start: the one that would be played now."""
    if game.get("story"):
        return game["story"]
    ai = game.get("ai_case")
    if game["case"] is None and ai is not None and ai["status"] == "ready":
        return ai["story"]
    return content.DEFAULT_STORY


def public_story(story):
    """The parts of a story everybody may see. No secrets, rumors, traces or private intros."""
    return {
        "source": story["source"],
        "case_number": story["case_number"],
        "case_title": story["case_title"],
        "victim": story["victim"],
        "victim_short": story["victim_short"],
        "found_place": story["found_place"],
        "briefing": story["briefing"],
        "intro_lines": list(story["intro_lines"]),
        "locations": list(story["locations"]),
        "location_flavor": dict(story["location_flavor"]),
        "location_icons": dict(story["location_icons"]),
        "dossiers": {role: texts["dossier"] for role, texts in story["roles"].items()},
        "endings": copy.deepcopy(story["endings"]),
    }


def story_view(game):
    """The public story of this game, for the board and every phone.

    "pending" is True while an AI is still writing the case in the lobby: the screens
    then say so instead of showing case #001, which will probably not be played.
    """
    view = public_story(story_of(game))
    ai = game.get("ai_case")
    view["pending"] = (game["case"] is None and ai is not None and ai["status"] == "writing")
    return view


def map_view(game):
    """The campus map for every screen: for each place of this case, whether it is open,
    searched or still locked, and in which round it was searched. Only public facts:
    what was searched is in the log anyway, and locks are shown openly. Never who
    searched, so that the murderer's planted clue does not stand out."""
    places = []
    for location in story_of(game)["locations"]:
        opens = locked_until(game, location)
        found = [e for e in game["log"] if e["kind"] == "search" and e.get("location") == location]
        if opens is not None:
            state = "locked"
        elif found or location in game["searched"]:
            state = "done"
        else:
            state = "open"
        places.append({"name": location, "state": state, "opens_in": opens,
                       "found": [e["id"] for e in found],
                       "found_in": found[0].get("round") if found else None})
    return {"round": current_round(game), "rounds": ROUNDS, "places": places}


def host_note(game, token):
    """A short note about the AI case, for the host only. None for everybody else."""
    player = next((p for p in game["players"] if token and p["token"] == token), None)
    if player is None or player["pid"] != game["host"]:
        return None
    if game["phase"] != "LOBBY":
        return game.get("story_note")
    ai = game.get("ai_case")
    if ai is None:
        return None
    if ai["status"] == "writing":
        return "The AI is writing a new case for this room …"
    if ai["status"] == "ready":
        return f"New AI case ready: “{ai['story']['case_title']}”."
    return f"No AI case ({ai['reason']}). {FIXED_CASE_NOTE}"


def ai_case_writing(game, now):
    """Mark that an AI is writing a new case for this lobby."""
    _require_phase(game, "LOBBY")
    game = copy.deepcopy(game)
    game["ai_case"] = {"status": "writing", "since": now}
    return game


def ai_case_ready(game, story, now):
    """Store a story the AI wrote, but only if it passes every check."""
    if game["phase"] != "LOBBY":
        return game   # too late: the game has already started with another case
    problems = validate_story(story)
    if not problems:
        story = copy.deepcopy(story)
        story["source"] = "ai"
        story["case_number"] = game["code"]
        # Every player count must give a fair, balanced case with this story.
        for count in range(MIN_PLAYERS, MAX_PLAYERS + 1):
            try:
                balance.build_balanced_case(list(range(1, count + 1)), count, story)
            except Rejected as problem:
                problems.append(str(problem))
                break
    game = copy.deepcopy(game)
    if problems:
        game["ai_case"] = {"status": "failed", "reason": "the AI case did not pass the checks",
                           "problems": problems[:5]}
    else:
        game["ai_case"] = {"status": "ready", "story": story}
    return game


AI_WRITING_TIMEOUT = 6 * 60   # seconds; then the lobby stops waiting (e.g. the server restarted)


def ai_status(game, token):
    """"writing", "ready", "failed" or None (never asked), for the host only; None for others."""
    player = next((p for p in game["players"] if token and p["token"] == token), None)
    if player is None or player["pid"] != game["host"] or game.get("ai_case") is None:
        return None
    return game["ai_case"]["status"]


def ai_case_failed(game, reason, now):
    """The AI could not write a case (no key, no answer, limit reached ...)."""
    if game["phase"] != "LOBBY":
        return game
    game = copy.deepcopy(game)
    game["ai_case"] = {"status": "failed", "reason": str(reason)}
    return game


def validate_story(story):
    """Returns a list of problems. An empty list means the story can be used for a case."""
    if not isinstance(story, dict):
        return ["The story is missing."]
    problems = []

    def check_text(value, limit_key, what, becomes_a_clue=False):
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{what} is missing.")
            return ""
        if len(value) > STORY_LIMITS[limit_key]:
            problems.append(f"{what} is longer than {STORY_LIMITS[limit_key]} characters.")
        if any(ord(ch) < 32 for ch in value):
            problems.append(f"{what} contains control characters.")
        # "murderer"/"killer" only matter in texts that become clues: a clue must never
        # call someone the murderer. In a briefing or an ending the word gives nothing away.
        if becomes_a_clue and any(word in value.lower() for word in FORBIDDEN_WORDS):
            problems.append(f"{what} gives the solution away.")
        return value

    for key in ("case_title", "victim", "victim_short", "found_place", "briefing"):
        check_text(story.get(key), key, key)

    locations = story.get("locations")
    roles = story.get("roles")
    if not isinstance(locations, list) or len(locations) != NUMBER_OF_LOCATIONS:
        problems.append(f"There must be exactly {NUMBER_OF_LOCATIONS} locations.")
        locations = []
    if not isinstance(roles, dict) or len(roles) != NUMBER_OF_ROLES:
        problems.append(f"There must be exactly {NUMBER_OF_ROLES} roles.")
        roles = {}
    locations = [check_text(loc, "location", "A location name") for loc in locations]
    role_names = [check_text(role, "role", "A role name") for role in roles]

    # No name may be part of another one: clues and bots find people and places by name.
    names = [name for name in locations + role_names if name]
    for a in names:
        for b in names:
            if a is not b and a.casefold() in b.casefold():
                problems.append(f"The name '{a}' is part of the name '{b}'.")

    def mentions_a_name(value):
        return any(name.casefold() in value.casefold() for name in names)

    def uses_evidence_words(value):
        return any(phrase in value.lower() for phrase in EVIDENCE_PHRASES)

    for key in ("location_flavor", "location_icons", "neutral_location_clues"):
        if not isinstance(story.get(key), dict):
            problems.append(f"{key} is missing.")
    flavor = story.get("location_flavor") or {}
    icons = story.get("location_icons") or {}
    neutral_at = story.get("neutral_location_clues") or {}
    for location in locations:
        if location and location not in content.PLACES:
            problems.append(f"{location} is not a place on the campus map.")
        check_text(flavor.get(location), "flavor", f"The description of {location}")
        icon = icons.get(location)
        if not isinstance(icon, str) or not 1 <= len(icon) <= 4:
            problems.append(f"The icon of {location} must be one emoji.")
        clue = check_text(neutral_at.get(location), "neutral_clue", f"The neutral clue at {location}",
                          becomes_a_clue=True)
        if mentions_a_name(clue) or uses_evidence_words(clue):
            problems.append(f"The neutral clue at {location} must not point at anybody.")

    for role, texts in roles.items():
        if not isinstance(texts, dict):
            problems.append(f"The texts of {role} are missing.")
            continue
        for field in ("dossier", "intro", "secret"):
            check_text(texts.get(field), field, f"The {field} of {role}")
        trace = check_text(texts.get("trace"), "trace", f"The trace of {role}", becomes_a_clue=True)
        if mentions_a_name(trace) or uses_evidence_words(trace):
            problems.append(f"The trace of {role} must not name anybody or any place.")
        rumor = check_text(texts.get("rumor"), "rumor", f"The rumor about {role}", becomes_a_clue=True)
        if rumor and not rumor.startswith(f"{role} was seen "):
            problems.append(f"The rumor about {role} must start with '{role} was seen'.")
        others = [name for name in role_names if name and name != role]
        if any(name.casefold() in rumor.casefold() for name in others) or any(
                phrase in rumor.lower() for phrase in EVIDENCE_PHRASES[:3]):
            problems.append(f"The rumor about {role} must only point at {role}.")

    intro = story.get("intro_lines")
    if not isinstance(intro, list) or len(intro) != NUMBER_OF_INTRO_LINES:
        problems.append(f"There must be exactly {NUMBER_OF_INTRO_LINES} intro lines.")
        intro = []
    for line in intro:
        line = check_text(line, "intro_line", "An intro line")
        if mentions_a_name(line):   # the intro must not hint at a suspect or a place
            problems.append("An intro line must not name a suspect or a location.")

    private = story.get("neutral_private_clues")
    if not isinstance(private, list) or len(private) < MAX_PLAYERS:
        problems.append(f"There must be at least {MAX_PLAYERS} neutral private clues.")
        private = []
    for clue in private:
        clue = check_text(clue, "neutral_clue", "A neutral private clue", becomes_a_clue=True)
        if mentions_a_name(clue) or uses_evidence_words(clue):
            problems.append("A neutral private clue must not point at anybody.")

    endings = story.get("endings")
    if not isinstance(endings, dict) or set(endings) != set(ENDING_KEYS):
        problems.append("There must be exactly the four endings " + ", ".join(ENDING_KEYS) + ".")
    else:
        for key in ENDING_KEYS:
            ending = endings[key] if isinstance(endings[key], dict) else {}
            check_text(ending.get("title"), "ending_title", f"The title of the ending '{key}'")
            check_text(ending.get("text"), "ending_text", f"The text of the ending '{key}'")
    return problems
