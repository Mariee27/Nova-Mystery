# Interface contract – Murder at NOVA

This file fixes the function signatures and data shapes. Tests are written against it.
Rules live in `logic.py`, storage in `db.py`, case building in `generator.py`, texts in `content.py`.

## General rules
- A *game* is a plain JSON-serialisable `dict`. All `logic` functions are **pure**: they never
  mutate their input, they return a **new** dict, and they raise `logic.Rejected(message)` when an
  action is not allowed. A rejected call changes nothing.
- `now` is always a number of seconds (float or int). Tests pass small numbers like `0`, `29`, `30`.
- `online` is always a `set[int]` of player ids that count as online.
- Player ids (`pid`) are integers starting at 1, in join order.

## Constants in `logic`
```
PHASES = ["LOBBY","REVEAL","INVESTIGATION","DISCUSSION","VOTE","RESULT","ABORTED"]
DURATIONS = {"REVEAL": 30, "INVESTIGATION": 90, "DISCUSSION": 60, "VOTE": 30}
OFFLINE_AFTER = 20      # seconds; online means now - last_seen <= 20
MIN_PLAYERS = 4; MAX_PLAYERS = 6; MIN_ONLINE = 3
MAX_TEXT = 140; MAX_NAME = 20; MAX_CLUE_TEXT = 200
STRONG_KINDS = {"scene", "alibi_broken"}
DEMO_SEED = 2026
```
`content.LOCATIONS` is a list of exactly 5 location names. `content.ROLES` is a dict with exactly 6 role names as keys.

## Game dict
```
{
 "code": "ABCD", "phase": "LOBBY", "phase_started": 0, "deadline": None,
 "host": None | pid, "next_pid": 1,
 "players": [{"pid": 1, "name": "Anna", "token": "...", "joined_at": 0}],
 "case": None | case,
 "acted": [pid, ...],          # players who used their one action this game
 "searched": [location, ...],
 "planted": False,
 "log": [entry, ...], "next_log_id": 1,
 "votes": {"1": 3},            # keys are str(pid of voter), values are target pid
 "result": None | result, "abort_reason": None | str
}
```
Log entry: `{"id": int, "kind": "search"|"question"|"answer"|"share"|"system", "by": pid|None, "text": str, ...}`
plus, depending on kind: `location`, `target` (pid), `question_id`, `answered` (bool, on questions),
`clue_id`, `implicates`, `clue_kind`, `planted` (bool, on search/share entries).

Result: `{"winner": "detectives"|"murderer", "murderer": pid, "murder_location": str,
"tally": {"3": 2, ...}, "secrets_kept": [pid, ...]}` (`tally` only lists players who received at least one vote)

## Case dict (built by `generator.build_case(pids, seed)`)
```
{
 "seed": int, "murderer": pid, "murder_location": str, "murder_time": "21:30",
 "characters": [{"pid": 1, "role": "The TA", "intro": str, "alibi_location": str, "alibi": str,
                 "true_location": str, "secret": str | None,      # None for the murderer
                 "clues": [clue, clue]}],                          # exactly 2 private clues
 "location_clues": [clue x 5]                                      # exactly one per location
}
```
Clue: `{"id": str, "text": str, "implicates": pid | None, "kind": "scene"|"alibi_broken"|"suspicious"|"confirms"|"neutral"}`.
Location clues also carry `"location": str`. Clue ids are unique within a case.

`generator.build_case(pids: list[int], seed: int) -> case` is deterministic for the same arguments.
`generator.build_valid_case(pids, seed) -> case` tries seed, seed+1, ... (max 5) until `validate_case` passes, else raises `logic.Rejected`.

`logic.validate_case(case, pids) -> list[str]` returns a list of problems; an empty list means valid. Checks:
1. `case["murderer"]` is in `pids`, and there is exactly one character per pid.
2. At least 2 clues (location or private) have `implicates == murderer` and kind in STRONG_KINDS; at least 1 of them is a location clue.
3. No clue has an innocent as `implicates` with a strong kind. At most 1 clue with kind "suspicious" per innocent.
4. Every clue's `implicates` is None or in `pids`; every location clue's `location` is in `content.LOCATIONS`; every character role is in `content.ROLES`.
5. No clue text contains "murderer" or "killer" (case-insensitive); every clue text has 1..200 characters.
6. Exactly 5 location clues, one per location; exactly 2 private clues per character.

## `logic` functions
```
new_token() -> str                                  # secrets.token_urlsafe(16), 22 characters
new_game(code, now) -> game
online_ids(presence: dict[int, float], now) -> set[int]
join(game, name, token, now) -> game                # new pid = game["next_pid"]; first player becomes host
kick(game, token, target_pid, now) -> game          # host only, only in LOBBY
start(game, token, online, now, seed=None) -> game  # host only
end_phase(game, token, online, now) -> game         # host only, only in REVEAL/INVESTIGATION/DISCUSSION/VOTE
tick(game, online, now) -> game                     # timers, early end, host handover, abort
search(game, token, location, now) -> game
question(game, token, target_pid, text, now) -> game
answer(game, token, question_id, text, now) -> game # question_id = log entry id of the question
share(game, token, clue_id, now) -> game
plant(game, token, target_pid, location, now) -> game
plant_locations(game) -> list[str]                  # where the murderer may plant right now
vote(game, token, target_pid, now) -> game
public_view(game, online) -> dict
private_view(game, token) -> dict | None
```

### Behaviour
- **join**: only in LOBBY (else Rejected). Name is stripped; 1..20 characters; unique in the room ignoring case. A 7th player is rejected. Token must not already be used in the room.
- **kick**: only in LOBBY; only the host; the target must be another player of the room. The player is removed from `players`.
- **start**: only the host; only in LOBBY; the number of *online* players must be 4..6. Offline lobby players are removed from `players`. Builds the case (seed=None → random seed). Phase becomes REVEAL, `phase_started = now`, `deadline = now + 30`.
- **end_phase**: moves to the next phase immediately (same as a timer running out).
- **tick** (in this order):
  1. Host handover (any phase except RESULT/ABORTED): if the host is not in `online` and another player is, the first online player in join order becomes host. The old host does not get the role back.
  2. Abort: in REVEAL, INVESTIGATION, DISCUSSION, VOTE, if fewer than 3 players are online → phase ABORTED, `abort_reason` set.
  3. Timer: if `now >= deadline` → next phase. The new phase starts at `now` (deadline = now + its duration). One step per call.
  4. Early end: INVESTIGATION ends as soon as every online player is in `acted`; VOTE ends as soon as every online player has voted.
  - Order of phases: REVEAL → INVESTIGATION → DISCUSSION → VOTE → RESULT.
  - When DISCUSSION ends, every unanswered question gets a system log entry containing "no answer" and is marked answered.
  - When VOTE ends, `result` is computed.
- **Actions** `search`, `question`, `share`: only in INVESTIGATION, only by a player of the game, only once per player in total (the pid is then in `acted`).
  - `search`: location must be in `content.LOCATIONS`. If already in `searched` → Rejected and the action is **not** used up. Otherwise the location clue is appended to the log (kind "search") and the location to `searched`.
  - `question`: target must be another player of the game; text is cleaned (control characters removed, stripped) and must have 1..140 characters. Appends a log entry kind "question" with `answered: False`.
  - `share`: `clue_id` must be one of the player's own private clues and not shared before.
- **answer**: allowed in INVESTIGATION and DISCUSSION; only the target of that question; only once per question; text 1..140 characters. Does not use up the action.
- **plant**: only in INVESTIGATION; only the murderer; only once per game (`planted`); target must be another player (an innocent); location must be in `plant_locations(game)`: not yet in `searched`, and not a location whose real clue implicates the murderer with a strong kind. Does **not** use up the normal action. The location is appended to `searched` (its real clue is covered up). Appends a log entry kind "search" with `planted: True`, `implicates: target`, `clue_kind: "suspicious"`; its text uses `content.TEMPLATES["herring"]` with the target's rumor, exactly like a real red herring.
- **vote**: only in VOTE; target must be another player of the game (not self); one vote per player.
- **Result**: detectives win only if the murderer has strictly more votes than every other player. A tie at the top or zero votes → the murderer wins. `secrets_kept` lists the innocents for whom no log entry has `implicates == pid` and `clue_kind == "suspicious"`.
- Any call with an unknown token → Rejected.

### Views
- `public_view(game, online)` → `{"code","phase","deadline","players":[{"pid","name","role","online","is_host","acted","voted"}],"log":[...],"searched":[...],"result":None|result,"abort_reason", "characters": None | [...]}`.
  `role` is None in LOBBY and the player's role name from REVEAL on. **Roles are public** (clues talk about roles, so everybody must know who plays whom); who the murderer is stays secret.
  Before RESULT: log entries contain **no** `implicates`, `clue_kind`, `planted` keys; `result` is None; `characters` is None; and nowhere in the view is there a token, the murderer, a secret, an intro, an alibi or a private clue. In RESULT: full log, result, and `characters` (the case's characters with names).
- `private_view(game, token)` → None for an unknown token. Otherwise `{"pid","name","is_host","phase","acted","voted","role","intro","alibi","secret","is_murderer","clues":[{"id","text","shared"}],"can_plant","plant_locations","open_questions":[log entries the player still has to answer]}`. Before the game starts, the case fields are None / empty. `plant_locations` is empty unless `can_plant`; `can_plant` is False when there is no location left to plant at. It never contains another player's card or token.

## `db` functions (SQLite)
```
connect(path) -> sqlite3.Connection        # creates tables if needed
create_room(conn, now) -> code             # 4 letters from "ABCDEFGHJKLMNPQRSTUVWXYZ", unused
                                           # logic.Rejected if 200 rooms were created in the last hour
load(conn, code) -> game | None
apply(conn, code, fn) -> game              # runs game = fn(game) inside ONE write transaction and saves it.
                                           # If fn raises logic.Rejected: rollback, nothing saved, exception re-raised.
                                           # Unknown code → logic.Rejected.
heartbeat(conn, code, pid, now) -> None
presence(conn, code) -> dict[int, float]   # pid -> last_seen
raw_state(conn, code) -> str | None        # the stored JSON text, for "unchanged" checks
```
