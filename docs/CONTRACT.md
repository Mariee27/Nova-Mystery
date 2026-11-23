# Interface contract – NOVA MYSTERY

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
DURATIONS = {"REVEAL": 60, "INVESTIGATION": 300, "DISCUSSION": 180, "VOTE": 60}
ROUNDS = 3            # INVESTIGATION has 3 rounds; DURATIONS["INVESTIGATION"] is the length of one round
LOCKED_PLACES = 2     # locked at the start: the crime scene and one other place
OFFLINE_AFTER = 45     # seconds; online means now - last_seen <= 45
MIN_PLAYERS = 4; MAX_PLAYERS = 6; MIN_ONLINE = 3
PAUSE_LIMIT = 180      # seconds a paused game waits for players before it ends
STAND_IN_AFTER = 15    # seconds without a sign of life: the computer plays that seat
HOLD_SECONDS = 120     # a place stays reserved this long while somebody solves its mini-game
HOT_SEAT_PICK_SECONDS = 20; HOT_SEAT_SECONDS = 45; HOT_SEAT_VERDICTS = ("believe", "lie")
MAX_WRONG_TRIES = 6    # wrong puzzle answers per player, place and round
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
 "acted": [pid, ...],          # players who used their one action in the current round
 "round": 1..3,                # only during the investigation; log entries of a round carry it too
 "searched": [location, ...],
 "planted": False,
 "log": [entry, ...], "next_log_id": 1,
 "votes": {"1": 3},            # keys are str(pid of voter), values are target pid
 "scene_votes": {"1": "Library"},  # str(pid of voter) -> accused crime scene (optional per voter)
 "result": None | result, "abort_reason": None | str,
 "minigames": bool,            # see "Evidence mini-games"
 # only when needed:
 "demo": True,                 # a "Play a demo" room (logic.as_demo)
 "stand_ins": [pid, ...],      # human seats the computer plays right now (update_stand_ins)
 "paused": {"since": now, "left": seconds},   # while fewer than MIN_ONLINE players are online
 "holds": {location: {"pid": pid, "until": now + HOLD_SECONDS}},   # places reserved for a mini-game
 "hot_seat": {"open": bool, "picks": {"1": pid}, "seat": pid | None,
              "ratings": {"1": "believe"|"lie"}, "history": [{"pid", "after_round", "believe", "lie"}]},
 "wrong_tries": {"pid|location|round": int}
}
```
A player dict may also carry `"bot": True` (a demo suspect, see *Demo suspects* below).

Log entry: `{"id": int, "kind": "search"|"share"|"system", "by": pid|None, "text": str, ...}`
plus, depending on kind: `location`, `clue_id`, `implicates`, `clue_kind`, `planted` (bool, on search/share entries).

Result: `{"winner": "detectives"|"murderer", "ending": "truth"|"incomplete"|"wrong"|"escaped",
"murderer": pid, "murder_location": str, "tally": {"3": 2, ...}, "scene_tally": {"Library": 2, ...},
"votes": {...}, "scene_votes": {...}, "secrets_kept": [pid, ...]}` (`tally` and `scene_tally` only list entries
with at least one vote; `votes` and `scene_votes` are every single ballot). AI cases add `"red_herrings"` (see *Stories*).
`hall_of_fame(game)` (None before RESULT) gives the awards: each `{"key", "title", "pids": [pid, ...], "detail"}` (ties share it); keys: `detective` (named the culprit and
the scene, else just the culprit), `hunter` (most exhibits found), `witness` (most clues shared), `oracle` (most threads
to the culprit), `liar` (the murderer: master liar if they got away, caught red-handed if not). A title nobody earned
is left out, and so are hunter, witness and oracle when more than two players tie for them.

## Case dict (built by `generator.build_case(pids, seed, story=None)`)
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
Location clues also carry `"location": str`. Clue ids are unique within a case. A "confirms" clue also carries
`"seen": pid, "at": location` and, on a private card, `"time": "HH:MM"` (who was seen where and when; never sent to a
phone: `private_view` gives only `id`, `text`, `shared`).

How `build_case` decides the night: the innocents are at the places other than the crime scene and the false alibi,
in pairs (three together if needed) and one or two alone. Every player holds two cards in random order: a sighting
(`confirms`, of somebody at the observer's own place, inside 23:15–23:45 for pairs; the murderer and the first lone
innocent saw each other between 22:55 and 23:10 at that innocent's place, each at a time of its own) or the witness account (`scene`, "hurrying toward the
scene" at 23:25, held by an innocent), plus an observation (`neutral`), a rumor (`suspicious`) or the witness account.
The rumor is held by the murderer or by an innocent; if the murderer holds it, an innocent holds one too and no note is
found at a place. Place clues: the trace at the scene (`scene`, without its owner: the dossiers say who carries what), the log of the false alibi's place showing that nobody was there (no name: compare the alibis)
(`alibi_broken`), the log of each lone innocent's place showing them there 23:10–23:50 (`confirms`), a note with a
rumor (`suspicious`) and neutral observations. Open-air places (`content.OPEN_AIR`: Beach, Main Deck) have a night
camera instead of a keycard log. Locked: the crime scene and the first lone innocent's place.

`generator.build_case(pids: list[int], seed: int, story: dict | None = None) -> case` is deterministic for the same arguments. Without a story it uses case #001 (`content.DEFAULT_STORY`).
`generator.build_valid_case(pids, seed, story=None) -> case` tries seed, seed+1, ... (max 5) until `validate_case` passes, else raises `logic.Rejected`.

`logic.validate_case(case, pids, story=None) -> list[str]` returns a list of problems; an empty list means valid. Checks:
1. `case["murderer"]` is in `pids`, and there is exactly one character per pid.
2. At least 2 clues (location or private) have `implicates == murderer` and kind in STRONG_KINDS; at least 1 of them is a location clue.
3. No clue has an innocent as `implicates` with a strong kind. At most 1 clue with kind "suspicious" per innocent.
4. Every clue's `implicates` is None or in `pids`; every location clue's `location` is one of the story's `locations`; every character role is one of the story's `roles` (without a story: case #001).
5. No clue text contains "murderer" or "killer" (case-insensitive); every clue text has 1..200 characters.
6. Exactly 5 location clues, one per location; exactly 2 private clues per character.
7. If the case has `"locked"`: exactly `LOCKED_PLACES` places, the crime scene among them, each opening in a round from 2 to `ROUNDS`; at least one strong place clue against the murderer is open in round 1.
8. Clue ids are unique.

## `logic` functions
```
new_token() -> str                                  # secrets.token_urlsafe(16), 22 characters
new_game(code, now, minigames=False) -> game
as_demo(game) -> game                               # marks a "Play a demo" room (game["demo"] = True)
online_ids(presence: dict[int, float], now) -> set[int]
clean_name(name) -> str; name_key(name) -> str      # see join
join(game, name, token, now) -> game                # new pid = game["next_pid"]; first player becomes host
kick(game, token, target_pid, now) -> game          # host only, only in LOBBY
start(game, token, online, now, seed=None, fixed_case=False, use_ai=True, hot_seat=False) -> game
                                                    # host only; use_ai=False plays case #001;
                                                    # hot_seat=True adds the hot seat between rounds
ai_status(game, token) -> "writing" | "ready" | "failed" | None   # host only, None for everybody else
wrong_tries(game, pid, location) -> int            # wrong puzzle answers of this player at this place in this round
note_wrong_try(game, token, location, now) -> game # counts one; app refuses answers after MAX_WRONG_TRIES (6)
max_minutes() -> int                               # the longest a started game can take (20)
end_phase(game, token, online, now) -> game         # host only, only in REVEAL/INVESTIGATION/DISCUSSION/VOTE
tick(game, online, now) -> game                     # host handover, pause/abort, timers, early end
current_round(game) -> int                          # 0 before, 1..ROUNDS during, ROUNDS+1 after the investigation
locked_until(game, location) -> int | None          # the round a locked place opens in, None if open
search(game, token, location, now, proof=None) -> game
open_place(game, token, location, now) -> game      # reserve a place while solving its mini-game
place_holder(game, location, now) -> pid | None     # who holds the place right now
busy_places(game, now) -> list[str]                 # places somebody holds (without saying who)
my_hold(game, token, now) -> str | None             # the place this player holds
share(game, token, clue_id, now) -> game
has_move(game, pid) -> bool                         # an open unsearched place or an own unshared clue
plant(game, token, target_pid, location, now) -> game
plant_locations(game) -> list[str]                  # where the murderer may plant right now
vote(game, token, target_pid, now, scene=None) -> game
hot_seat_open(game) -> bool                         # True during the break between two rounds
hot_seat_candidates(game) -> list[int]              # players who have not been in the hot seat yet
pick_hot_seat(game, token, target_pid, now) -> game
start_hot_seat(game, token, now) -> game            # host only, needs at least one pick
rate_hot_seat(game, token, verdict, now) -> game    # verdict in HOT_SEAT_VERDICTS
hot_seat_tie(game, tied: list[int]) -> pid          # seeded chance, the same for the same game
hot_seat_view(game) -> dict | None                  # public part, None outside the break
my_hot_seat(game, token) -> {"pick", "rating"} | None
bot_ids(game) -> list[int]                          # pids of the demo suspects
with_bots(game, online) -> set[int]                 # online plus all bots and stand-ins
stand_in_ids(game) -> list[int]; robot_ids(game) -> list[int]   # stand-ins; bots + stand-ins
update_stand_ins(game, presence, now) -> game       # stand-ins for seats without a sign of life
add_bot(game, token, now) -> game                   # host only, only in LOBBY
bot_moves(game, now) -> game                        # the moves of all bots that are due now (threads included)
pin_thread(game, token, entry_id, target_pid, now) -> game   # INVESTIGATION/DISCUSSION; one thread per player and note
unpin_thread(game, token, entry_id, now) -> game
cut_thread(game, token, entry_id, target_pid, now) -> game   # the murderer, DISCUSSION, once
can_cut(game, pid) -> bool
thread_view(game) -> [{"entry", "pid", "count", "at"}]     # public: counts per connection, never who
cut_view(game) -> None | {"entry", "pid", "at"}            # public: what the murderer cut, never by whom
my_threads(game, token) -> None | {"threads": {entry id: pid}, "can_cut": bool}   # one player's own
hall_of_fame(game) -> None | [award, ...]                  # after the game
public_view(game, online) -> dict
private_view(game, token) -> dict | None
last_move(game, pid) -> dict | None                 # the player's own move in the current round
```
Locations are always the locations of the game's story (`story_of(game)["locations"]`); for case #001 these are `content.LOCATIONS`.

### Behaviour
- **join**: only in LOBBY (else Rejected). Name via `clean_name`: NFKC-normalised, tabs and line breaks become
  spaces, other control characters are dropped, runs of spaces become one; invisible characters (Unicode
  format, private-use, unassigned, line/paragraph separators, blank letters such as U+2800, U+3164) and
  more than 2 combining marks in a row are refused; it needs a letter or digit; 1..20 characters. Unique in the
  room by `name_key` (ignoring case, accents, width and Cyrillic/Greek look-alike letters). A 7th player is rejected. Token must not already be used in the room.
- **kick**: only in LOBBY; only the host; the target must be another player of the room. The player is removed from `players`.
- **start**: only the host; only in LOBBY; the number of *online* players must be 4..6. Offline lobby players are removed from `players`. Picks the story (see *Stories* below), stores it in `game["story"]` and builds the case with it (seed=None → random seed). Phase becomes REVEAL, `phase_started = now`, `deadline = now + 60` (about 20 s to watch the suspects on the board, then 40 s to read the file).
- **start** with `hot_seat=True` stores `game["hot_seat"]` (see *Hot seat* below). The app shows the host a checkbox for it, on by default.
- **end_phase**: moves to the next step immediately (same as a timer running out): the next round, the hot seat break, or the next phase.
- **tick** (in this order):
  0. In LOBBY: an AI case that has been writing for more than `AI_WRITING_TIMEOUT` fails ("the AI took too long").
  1. Host handover (any phase except RESULT/ABORTED): if the host is not in `online` or is played by a stand-in, and another human who is there is online, the first of them in join order becomes host (never a bot or stand-in). The old host does not get the role back.
  2. Pause: in REVEAL, INVESTIGATION, DISCUSSION, VOTE, if fewer than 3 players are online, the game pauses: `paused = {"since": now, "left": seconds left}`, `deadline = None`, no timer and no early end. When enough players are back, `deadline = now + left` and the pause ends. Only after `PAUSE_LIMIT` seconds of pause → phase ABORTED, `abort_reason` set.
  3. Timer: if `now >= deadline` → next step. The new step starts at `now` (deadline = now + its duration). One step per call. During the hot seat break only the hot seat clock counts.
  4. Early end: INVESTIGATION ends as soon as every online player is in `acted` or has no move left (`has_move`); VOTE ends as soon as every online player has voted.
  - Order of phases: REVEAL → INVESTIGATION → DISCUSSION → VOTE → RESULT.
  - When VOTE ends, `result` is computed.
- **Interrogations happen out loud.** The players question each other face to face; there is no question or answer action and no question/answer log entry. The hot seat (below) only organises who is questioned and collects ratings.
- **Actions** `search`, `share`: only in INVESTIGATION and not during the hot seat break, only by a player of the game, once per player and round (the pid is then in `acted`).
  - `search`: location must be one of the story's locations, open (`locked_until` is None) and not in `searched`, else Rejected and the action is **not** used up. A place another human holds is refused for humans ("Somebody else is searching this place right now."). With mini-games, a human needs a valid `proof` (see *Evidence mini-games*). Otherwise the location clue is appended to the log (kind "search"), the location to `searched`, and the place's hold is removed.
  - `open_place`: same checks as `search` for phase, move, place and holder. Holds the place for this player for `HOLD_SECONDS`; a player holds at most one place (an older hold of theirs is dropped). A hold ends when the place is searched, its time runs out, or the round ends. Who holds a place is never public (`busy_places` lists only places).
  - `share`: `clue_id` must be one of the player's own private clues and not shared before.
- **plant**: only in INVESTIGATION; only the murderer; only once per game (`planted`); target must be another player (an innocent); location must be in `plant_locations(game)`: not yet in `searched`, and not a location whose real clue implicates the murderer with a strong kind. Does **not** use up the normal action. The location is appended to `searched` (its real clue is covered up). Appends a log entry kind "search" with `planted: True`, `implicates: target`, `clue_kind: "suspicious"`; its text uses `content.TEMPLATES["herring"]` with the target's rumor, exactly like a real red herring.
- **plant** is also refused during the hot seat break, and only targets open places.
- **vote**: only in VOTE; target must be another player of the game (not self); one vote per player. `scene` (optional) is where the voter thinks the murder happened; it must be one of the story's locations, else Rejected. It is stored in `scene_votes`.
- **Result**: detectives win only if the murderer has strictly more votes than every other player. A tie at the top or zero votes → the murderer wins. `ending`:
  `truth` (detectives win and the crime scene has strictly the most scene votes), `incomplete` (detectives win, scene wrong, tied or not given),
  `wrong` (one innocent has strictly the most votes), `escaped` (no votes or a tie at the top). The screens show the matching text from the story's `endings`.
  `secrets_kept` lists the innocents for whom no log entry has `implicates == pid` and `clue_kind == "suspicious"`.
- Any call with an unknown token → Rejected.

### Hot seat (between rounds)
Only with `start(..., hot_seat=True)`. After every investigation round except the last one, and only while
`hot_seat_candidates` is not empty, comes a break: the phase stays INVESTIGATION, `round` stays the finished
round, nobody can search, share or plant. The break uses `deadline` as its clock, so a pause stops it too.
1. **Picking** (`HOT_SEAT_PICK_SECONDS`): `pick_hot_seat` names a candidate other than oneself; one pick per
   player, locked in. The seat starts when every online player who can pick has picked, when the time is up, or
   when the host calls `start_hot_seat` (needs at least one pick). Most picks win; a tie is decided by
   `hot_seat_tie` (seeded with the room code and the number of earlier hot seats). No pick at all → the next
   round starts right away.
2. **Seat** (`HOT_SEAT_SECONDS`): the room questions the suspect out loud. Every other player may
   `rate_hot_seat` "believe" or "lie" and change their mind until the time is up; the suspect cannot rate.
3. The counts go into `history` (`{"pid", "after_round", "believe", "lie"}`) and the next round starts.
   Nobody sits there twice.
- `hot_seat_view(game)` → `{"after_round", "seat", "until", "picked", "believe", "lie", "candidates", "history"}`
  or None outside the break. Only counts: never who picked or rated whom. `my_hot_seat` gives one player their own pick and rating.

### Demo suspects (bots)
For presentations with fewer than 4 people. A bot is an ordinary player with `"bot": True` that plays
through the same functions as everybody else and only uses its own card and the public log.
- **add_bot**: only in LOBBY; only the host. Joins `"<first name> (demo)"` with the first unused name from
  `content.DEMO_NAMES` and a fresh token. A full room → Rejected.
- **with_bots**: bots send no heartbeats, so the app adds them to `online` before `tick` and `public_view`.
- **bot_moves**: does nothing without bots or outside INVESTIGATION and VOTE. Bot number *i* (in join order)
  moves once `now - phase_started >= 6 + 4·i` seconds.
  - INVESTIGATION: with mini-games, bots wait until every human has moved. A bot searches an open, free place
    it does not hold against anybody (a guilty bot skips places with its own strong traces) and leaves the last
    open place to a waiting human; otherwise it shares a clue. Bots search without a proof.
  - Hot seat break: a bot picks the candidate it suspects most and rates them "lie", everybody else "believe".
  - VOTE: a bot votes for the player the readable evidence points at most and names a scene if the evidence gives one.
- Bots are never host (see `tick`) and look like everybody else in `public_view`.

### Stand-ins (players who dropped out)
- `update_stand_ins(game, presence, now)`: in REVEAL, INVESTIGATION, DISCUSSION and VOTE every human seat whose last
  sign of life is more than `STAND_IN_AFTER` seconds ago (or missing) is in `game["stand_ins"]`; everybody else is
  not. Outside these phases the list is empty. Returns the same game if nothing changes. The app calls it before
  `tick` on every poll, with the heartbeat times.
- A stand-in counts as online (`with_bots`) and is moved by `bot_moves` exactly like a demo suspect, with the same
  knowledge (own card, public log). Like bots it searches without a proof. "Waiting for humans" (mini-games,
  the last open place) only counts players who are there, not stand-ins.
- `public_view` players and `private_view` carry `"stand_in": bool`. As soon as the player's phone is back, the
  stand-in ends and the player plays again (with mini-games, puzzles again).

### Red threads
- `game["threads"] = {str(pid): {str(entry id): {"pid": suspect, "at": time}}}`: a player connects a note (a search
  or share entry) to another player. Free (not the move of the round), in INVESTIGATION (also in the hot seat break)
  and DISCUSSION; pinning the same note again moves the thread, `unpin_thread` takes it down. Refused: an unknown note,
  oneself, an unknown suspect, a connection that was cut, another phase.
- `cut_thread`: only the murderer, only in DISCUSSION, once per game (`game["cut"] = {"entry", "pid", "at"}`), only a
  connection that has a thread. Removes every thread on it; that connection cannot be pinned again.
- Like the hot seat, the threads live next to the views, not in them (the views keep their fields): public
  `thread_view` (counts per connection, never who) and `cut_view` (what was cut, never by whom); private
  `my_threads` (the player's own threads and `can_cut`). The app adds them to its screens' data.
- Demo suspects and stand-ins pin one thread at a time (`BOT_THREAD_DELAY`, `BOT_THREAD_GAP`) from the notes that point
  at somebody the way they read them; a guilty one cuts the thickest thread against itself in the discussion.

### Views
- `public_view(game, online)` → `{"code","phase","deadline","demo","paused_since","players":[{"pid","name","role","online","stand_in","is_host","acted","voted"}],"log":[...],"searched":[...],"result":None|result,"abort_reason", "characters": None | [...]}`. `paused_since` is None unless the game is paused.
  `role` is None in LOBBY and the player's role name from REVEAL on. **Roles are public** (clues talk about roles, so everybody must know who plays whom); who the murderer is stays secret.
  Before RESULT: log entries contain **no** `implicates`, `clue_kind`, `planted` keys; `result` is None; `characters` is None; and nowhere in the view is there a token, the murderer, a secret, an intro, an alibi or a private clue. In RESULT: full log, result, and `characters` (the case's characters with names).
- `private_view(game, token)` → None for an unknown token. Otherwise `{"pid","name","is_host","phase","acted","voted","stand_in","role","intro","alibi","secret","is_murderer","clues":[{"id","text","shared"}],"can_plant","plant_locations","last_move","puzzles"}`. Before the game starts, the case fields are None / empty. `plant_locations` is empty unless `can_plant`; `can_plant` is False when there is no location left to plant at. It never contains another player's card or token.

## `db` functions (SQLite or PostgreSQL)
```
connect(target) -> connection              # a file path (SQLite) or a postgresql:// address; creates tables if needed
shared(target) -> connection               # this thread's reused connection (made once); forget(target) drops it
snapshot(conn, code, now, key="") -> (game, presence)   # one read per room and second for all screens;
                                           # every write through apply() drops the room's snapshot
create_room(conn, now) -> code             # 4 letters from "ABCDEFGHJKLMNPQRSTUVWXYZ", unused
                                           # at 200 rooms in the last hour, lobbies without activity for
                                           # IDLE_ROOM_SECONDS are deleted first; logic.Rejected if still 200
load(conn, code) -> game | None
apply(conn, code, fn) -> game              # runs game = fn(game) inside ONE write transaction and saves it.
                                           # If fn raises logic.Rejected: rollback, nothing saved, exception re-raised.
                                           # Unknown code → logic.Rejected.
heartbeat(conn, code, pid, now) -> None
presence(conn, code) -> dict[int, float]   # pid -> last_seen
raw_state(conn, code) -> str | None        # the stored JSON text, for "unchanged" checks
claim_ai_case(conn, now) -> bool           # True and counted while fewer than 5 AI cases this hour and 10 today
```

## Stories (case texts, optionally written by an AI)

A *story* is a dict with exactly the keys of `content.DEFAULT_STORY` (case #001):
`source` ("fixed" or "ai"), `case_number`, `case_title`, `victim`, `victim_short`, `found_place`,
`briefing`, `intro_lines` (exactly 6 short lines, the 4th is shown in red), `locations` (list of 5 names), `location_flavor`, `location_icons`,
`neutral_location_clues` (dicts keyed by location), `roles` (dict of 6 role names →
`{"dossier","intro","trace","secret","rumor"}`), `neutral_private_clues` (list, at least 6),
`endings` (`truth`, `incomplete`, `wrong`, `escaped` → `{"title","text"}`).
The clue templates and the times (23:30, 23:47) are the same for every story.

```
logic.validate_story(story) -> list[str]        # empty = usable
logic.ai_case_writing(game, now) -> game         # LOBBY only: game["ai_case"] = {"status": "writing", ...}
logic.ai_case_ready(game, story, now) -> game    # checks the story; "ready" or "failed". Outside LOBBY: unchanged.
logic.ai_case_failed(game, reason, now) -> game  # "failed" with a short reason. Outside LOBBY: unchanged.
logic.story_of(game) -> story                    # game["story"]; before the start the AI story if ready; else case #001
logic.public_story(story) -> dict                # no intro, secret, trace or rumor; roles only as "dossiers"
logic.story_view(game) -> dict                   # public_story(story_of(game)) + "pending" (AI still writing in the lobby)
logic.host_note(game, token) -> str | None       # a note about the AI case, only for the host
ai.write_story(api_key, model, client=None) -> story   # raises ai.AIError; the only module that calls an AI service
ai.review_story(client, model, story) -> {"available", "ok", "problems", "answer", "kind"}   # the test reading;
    # kind "balance": no fair case can be built (refused), "reader": the test player's findings (advice only)
ai.judge(answer, culprit_role, roles) -> list[str] | None   # [] = passed, None = unusable answer
ai.player_file(story, case) -> str               # what players can know, round by round; never the solution
balance.build_balanced_case(pids, seed, story) -> case   # AI stories only; raises logic.Rejected
balance.problems(case) -> list[str]              # "inconsistent:", "unfair:", "too easy:", "too hard:", "too complex:"
balance.analyze(case) -> dict                    # the numbers behind the checks
```

- `start` builds case #001 with `generator.build_valid_case`. An AI story is built with
  `balance.build_balanced_case`: `generator.build_case`, then `balance.adjust` (crime scene opens in round 2,
  the other locked place in round 3), then `validate_case` and `balance.problems`; the next seed is tried, up to
  40. The case gets `"balance"` (analyze) and `"solution"` (culprit, culprit_role, motive, method, scene,
  false_alibi, timeline, evidence, red_herrings). Neither is in any view before RESULT; the result of an AI case
  has `"red_herrings"`: [{"points_at", "explained_by", "cleared_by"}], lone innocents without an alibi included.
- Suspicion model (`balance.suspicion`): trace at the scene 3, log against the alibi 2, witness 2 (1 while the
  scene is still locked), note or rumor 1, no alibi 1 (nobody saw them at their place 23:15–23:45 and no log of
  their place has been found). Medium: culprit's lead after round 1 <= 2, never the only one without an alibi
  after round 1, the culprit's card kinds held by an innocent too, with all evidence lead >= 3, at least 3
  independent strong sources incl. a place and a private card, every innocent cleared in the end.
- `ai_case_ready` accepts a story only if a balanced case can be built for 4, 5 and 6 players. In the lobby,
  `tick` gives up on an AI case after `AI_WRITING_TIMEOUT` (6 min) of writing ("the AI took too long").

- `start` plays the AI story only if `game["ai_case"]["status"] == "ready"`, `fixed_case` is False and `use_ai` is True.
  Otherwise it plays case #001. If an AI case was expected (writing or failed), `game["story_note"]`
  explains why, and only the host sees it via `host_note`. Without `game["ai_case"]` nothing changes.
- `validate_story` checks: 5 unique locations and 6 unique roles, no name inside another name, every text
  present and within its length limit, no "murderer"/"killer" in texts that become clues (traces, rumors, neutral clues), intro lines that name no suspect and no location, every rumor starts with "<role> was seen " and names
  nobody else, traces and neutral clues name nobody and use none of the phrases the demo suspects read as
  evidence. `ai_case_ready` also builds a valid case with the story for 4, 5 and 6 players.
- `public_view` and `private_view` are unchanged. The screens get the story from `story_view`.

`ai.parse_story` tidies an AI answer before the checks: it keeps the first 6 suspects and 5 locations with
different names (the request asks for 7 and 6), removes a leading "the" from place names, brings rumors into
the form "<role> was seen ...", takes suspects and places out of neutral clues and traces, replaces intro
lines that do not fit by a standard intro, and fills in generic endings if some are missing. Every request
gets a random theme and a random first letter for the victim, so rooms get different cases.

## Rounds, locked places and the campus map

- The investigation has `ROUNDS` rounds. A round ends at its deadline, or early as soon as every online
  player has made one move or has no move left (`logic.has_move`: no open unsearched place and no own
  unshared clue). The host's `end_phase` also ends a round. After the last round comes
  DISCUSSION. Each new round clears `acted` and `holds` and sets a new deadline. With the hot seat
  switched on, the break comes between the rounds (see *Hot seat*).
- The case has `"locked": {location: round}`: two places, the crime scene always one of them, opening in
  rounds 2 and 3. The place of the false alibi is never locked, so a strong clue is open from round 1.
- Every place holds exactly one clue. `search`: refused outside INVESTIGATION, for a second move in the
  same round, for an unknown place, for a place that is still locked, and for a place that was already
  searched (or where the murderer planted a clue). `plant` only targets unlocked, unsearched places.
- `logic.map_view(game) -> {"round", "rounds", "places": [{"name", "state", "opens_in", "found", "found_in"}]}`;
  state is `open`, `done` or `locked`; `found_in` is the round of the search. Never who searched.
- `private_view(...)["last_move"]`: the player's own search or share of the current round
  (for "Move made."), or None.

## Evidence mini-games

- `logic.new_game(code, now, minigames=False)` / `db.create_room(conn, now, minigames=False)`: rooms made by
  the app pass `minigames=True`; the game stores it as `game["minigames"]`.
- With mini-games on, every place's clue is sealed: `search(game, token, location, now, proof)` is refused
  ("The evidence is still sealed. Solve the puzzle first.") unless `minigames.verify(game, location, proof)`
  is True. Demo bots search without a proof. Every other rule of `search` is unchanged, so each place's
  evidence is still awarded exactly once.
- `minigames.spec(game, location)` -> `{"id": "MG-0N-kind", "kind": code|scratch|puzzle|cipher|order, "variant",
  "location", "evidence_id" (the clue id), "evidence_no", "icon", "name", "exhibit", "verb", "story",
  "hints": [3 texts], ...kind-specific data}`. It never contains the answer: no code, no cipher key, no order.
  `private_view(...)["puzzles"]` maps every place to its spec during INVESTIGATION (else `{}`).
  The five places of a case get the five kinds (`minigames.assignment`), so no kind comes twice.
  Puzzle and scratch specs have `"image"` (SVG from `exhibits.camera_still` / `exhibits.document`); scratch
  has `"cover"`; order has `"items"`: `[{"letter", "when", "text"}]` in the shuffled order shown.
- `story["minigames"]` (optional): `{kind: piece}` with `exhibit` and `story` (containing `{location}`; may use
  `{victim}`; the puzzle's may use `{pieces}`), plus cipher `message`, scratch `style` (note|printout|phone|photo),
  `title`, `lines`, puzzle `caption`, order `events` (4 × `["HH:MM", text]`). `minigames.clean_content(raw, story)`
  keeps the pieces that pass the checks; `minigames.piece(game, kind)` falls back to `content.MINIGAME_FALLBACK`.
- Proofs: code `{"code": "2160"}` (the lock of the place: `minigames._lock`, a new code every game); scratch `{"cells": [cell indices]}` (at least 55 % of 10 × 14);
  puzzle `{"swaps": [[a, b], ...]}` replayed on the seeded starting order; cipher `{"shift": n}`;
  order `{"order": [positions on screen, earliest entry first]}`.
- `content.BUILDINGS` (letter of the official campus map -> `name`, `shape`: outline as [(x, y), ...] and
  `tag`: where the letter sits, all in percent), `content.GROUNDS` ((css class, outline): lawn,
  open land, sand, sea), `content.ROADS` ((name, line, angle of the name)) and `content.PLACES` (7 places,
  no car park and no canteen, with pin centre `x`, `y`
  in percent, icon and letter) describe the plan. `ui.campus_map` draws them as one SVG with the pins as
  HTML on top. Every story's
  locations must be places of `content.PLACES`.
- On the phone every tap is a link: `?step=search|share|plant` plus the selection
  (`place`, `clue`, `blame`). An unknown step (for example an old `question` link) opens "Your move.". `app.handle_move_links` copies them into
  `session_state["move"]` and removes them from the address; only the buttons call `logic`.
