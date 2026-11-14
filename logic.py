"""Rules of Murder at NOVA.

Everything in this file is a pure function: it gets a game (a plain dict),
returns a NEW game, and never changes the one it was given. If an action is
not allowed it raises Rejected, and nothing has changed.

No Streamlit and no database code belongs in here.
"""

import copy
import secrets

import content
import generator

PHASES = ["LOBBY", "REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE", "RESULT", "ABORTED"]
DURATIONS = {"REVEAL": 30, "INVESTIGATION": 90, "DISCUSSION": 60, "VOTE": 30}
NEXT_PHASE = {
    "REVEAL": "INVESTIGATION",
    "INVESTIGATION": "DISCUSSION",
    "DISCUSSION": "VOTE",
    "VOTE": "RESULT",
}
OFFLINE_AFTER = 20
MIN_PLAYERS = 4
MAX_PLAYERS = 6
MIN_ONLINE = 3
MAX_TEXT = 140
MAX_NAME = 20
MAX_CLUE_TEXT = 200
STRONG_KINDS = {"scene", "alibi_broken"}
FORBIDDEN_WORDS = ("murderer", "killer")
DEMO_SEED = 2026
# Keys that would give the solution away. They are removed from the public log
# until the game is over.
HIDDEN_LOG_KEYS = ("implicates", "clue_kind", "planted")


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
    entry.update(extra)
    game["log"].append(entry)
    game["next_log_id"] += 1
    return entry


def _require_phase(game, *phases):
    if game["phase"] not in phases:
        raise Rejected(f"Not possible in phase {game['phase']}.")


# ---------------------------------------------------------------- lobby

def new_game(code, now):
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
        "result": None,
        "abort_reason": None,
    }


def join(game, name, token, now):
    _require_phase(game, "LOBBY")
    name = clean_text(name, MAX_NAME)
    if len(game["players"]) >= MAX_PLAYERS:
        raise Rejected(f"The room is full ({MAX_PLAYERS} players).")
    if any(p["name"].casefold() == name.casefold() for p in game["players"]):
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


def start(game, token, online, now, seed=None):
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
    game["case"] = generator.build_valid_case(_player_ids(game), seed)
    _enter_phase(game, "REVEAL", now)
    return game


# ---------------------------------------------------------------- phases

def _enter_phase(game, phase, now):
    """Change the phase of an already copied game."""
    if phase == "VOTE":  # we are leaving DISCUSSION: close open questions
        for entry in list(game["log"]):
            if entry["kind"] == "question" and not entry["answered"]:
                entry["answered"] = True
                asked = _name(game, entry["target"])
                _add_log(game, "system", None,
                         f"{asked} gave no answer to question #{entry['id']}.",
                         question_id=entry["id"])
    game["phase"] = phase
    game["phase_started"] = now
    game["deadline"] = now + DURATIONS[phase] if phase in DURATIONS else None
    if phase == "RESULT":
        game["result"] = _compute_result(game)


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
    _enter_phase(game, NEXT_PHASE[game["phase"]], now)
    return game


def tick(game, online, now):
    """Called every time a screen asks for the current state.

    Order: host handover, abort, timer, early end. At most one phase change per call.
    """
    if game["phase"] in ("RESULT", "ABORTED"):
        return game
    pids = _player_ids(game)
    online_players = [pid for pid in pids if pid in online]
    new = None  # copy only if something really changes

    # 1. Host handover: the first online player in join order takes over.
    if game["host"] not in online and online_players:
        new = copy.deepcopy(game)
        new["host"] = online_players[0]

    if game["phase"] in NEXT_PHASE:
        # 2. Abort when fewer than 3 players are left online.
        if len(online_players) < MIN_ONLINE:
            new = new or copy.deepcopy(game)
            new["phase"] = "ABORTED"
            new["phase_started"] = now
            new["deadline"] = None
            new["abort_reason"] = (
                f"Fewer than {MIN_ONLINE} players are online. Please create a new room."
            )
            return new
        # 3. Timer, 4. early end.
        everyone_acted = all(pid in game["acted"] for pid in online_players)
        everyone_voted = all(str(pid) in game["votes"] for pid in online_players)
        if (
            now >= game["deadline"]
            or (game["phase"] == "INVESTIGATION" and everyone_acted)
            or (game["phase"] == "VOTE" and everyone_voted)
        ):
            new = new or copy.deepcopy(game)
            _enter_phase(new, NEXT_PHASE[game["phase"]], now)
    return new or game


# ---------------------------------------------------------------- actions

def _begin_action(game, token):
    """Checks shared by search, question and share. Returns the acting player."""
    _require_phase(game, "INVESTIGATION")
    player = _player_by_token(game, token)
    if player["pid"] in game["acted"]:
        raise Rejected("You have already used your action in this round.")
    return player


def search(game, token, location, now):
    player = _begin_action(game, token)
    if location not in content.LOCATIONS:
        raise Rejected("Unknown location.")
    if location in game["searched"]:
        raise Rejected("This location has already been searched. Pick another one.")
    clue = next(c for c in game["case"]["location_clues"] if c["location"] == location)
    game = copy.deepcopy(game)
    game["searched"].append(location)
    game["acted"].append(player["pid"])
    _add_log(game, "search", player["pid"], clue["text"], location=location,
             clue_id=clue["id"], implicates=clue["implicates"], clue_kind=clue["kind"],
             planted=False)
    return game


def question(game, token, target_pid, text, now):
    player = _begin_action(game, token)
    if target_pid == player["pid"]:
        raise Rejected("You cannot question yourself.")
    if target_pid not in _player_ids(game):
        raise Rejected("Unknown player.")
    text = clean_text(text, MAX_TEXT)
    game = copy.deepcopy(game)
    game["acted"].append(player["pid"])
    _add_log(game, "question", player["pid"], text, target=target_pid, answered=False)
    return game


def answer(game, token, question_id, text, now):
    _require_phase(game, "INVESTIGATION", "DISCUSSION")
    player = _player_by_token(game, token)
    asked = next((e for e in game["log"]
                  if e["kind"] == "question" and e["id"] == question_id), None)
    if asked is None:
        raise Rejected("Unknown question.")
    if asked["target"] != player["pid"]:
        raise Rejected("This question was not asked to you.")
    if asked["answered"]:
        raise Rejected("This question has already been answered.")
    text = clean_text(text, MAX_TEXT)
    game = copy.deepcopy(game)
    next(e for e in game["log"] if e["id"] == question_id)["answered"] = True
    _add_log(game, "answer", player["pid"], text, question_id=question_id)
    return game


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
    if location not in content.LOCATIONS:
        raise Rejected("Unknown location.")
    text = content.TEMPLATES["plant"].format(
        location=location, role=_character(game, target_pid)["role"])
    game = copy.deepcopy(game)
    game["planted"] = True
    # "by" stays empty so that the log does not show who planted the clue.
    _add_log(game, "search", None, text, location=location, clue_id=None,
             implicates=target_pid, clue_kind="suspicious", planted=True)
    return game


def vote(game, token, target_pid, now):
    _require_phase(game, "VOTE")
    player = _player_by_token(game, token)
    if str(player["pid"]) in game["votes"]:
        raise Rejected("You have already voted.")
    if target_pid == player["pid"]:
        raise Rejected("You cannot vote for yourself.")
    if target_pid not in _player_ids(game):
        raise Rejected("Unknown player.")
    game = copy.deepcopy(game)
    game["votes"][str(player["pid"])] = target_pid
    return game


def _compute_result(game):
    murderer = game["case"]["murderer"]
    tally = {}   # only players who received at least one vote appear here
    for target in game["votes"].values():
        tally[str(target)] = tally.get(str(target), 0) + 1
    murderer_votes = tally.get(str(murderer), 0)
    best_other = max([count for pid, count in tally.items() if pid != str(murderer)], default=0)
    # Detectives only win with a clear majority against the murderer. A tie is not enough.
    winner = "detectives" if murderer_votes > best_other else "murderer"
    exposed = {e.get("implicates") for e in game["log"] if e.get("clue_kind") == "suspicious"}
    secrets_kept = [pid for pid in _player_ids(game) if pid != murderer and pid not in exposed]
    return {
        "winner": winner,
        "murderer": murderer,
        "murder_location": game["case"]["murder_location"],
        "tally": tally,
        "secrets_kept": secrets_kept,
    }


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
        "open_questions": [],
    }
    if game["case"] is None:
        return view
    character = _character(game, pid)
    public_clue_ids = {e.get("clue_id") for e in game["log"]}
    is_murderer = pid == game["case"]["murderer"]
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
        "can_plant": is_murderer and not game["planted"] and game["phase"] == "INVESTIGATION",
        "open_questions": [
            {"id": e["id"], "by": e["by"], "text": e["text"]}
            for e in game["log"]
            if e["kind"] == "question" and e["target"] == pid and not e["answered"]
        ],
    })
    return view


# ---------------------------------------------------------------- case validator

def validate_case(case, pids):
    """Returns a list of problems. An empty list means the case is fair and solvable."""
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
        if clue.get("location") not in content.LOCATIONS:
            problems.append(f"Clue {clue['id']} has an unknown location.")
    for character in characters:
        if character["role"] not in content.ROLES:
            problems.append(f"Unknown role {character['role']}.")

    # 5. texts: no giveaway words, sensible length
    for clue in all_clues:
        text = clue["text"]
        if any(word in text.lower() for word in FORBIDDEN_WORDS):
            problems.append(f"Clue {clue['id']} gives the solution away.")
        if not 1 <= len(text) <= MAX_CLUE_TEXT:
            problems.append(f"Clue {clue['id']} must have 1 to {MAX_CLUE_TEXT} characters.")

    # 6. counts
    if sorted(c.get("location", "") for c in location_clues) != sorted(content.LOCATIONS):
        problems.append("There must be exactly one clue per location.")
    for character in characters:
        if len(character["clues"]) != 2:
            problems.append(f"Player {character['pid']} must have exactly 2 private clues.")
    ids = [c["id"] for c in all_clues]
    if len(ids) != len(set(ids)):
        problems.append("Clue ids must be unique.")
    return problems
