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
DURATIONS = {"REVEAL": 30, "INVESTIGATION": 300, "DISCUSSION": 180, "VOTE": 60}
ROUNDS = 3            # INVESTIGATION has 3 rounds; DURATIONS["INVESTIGATION"] is the length of one round
LOCKED_PLACES = 2     # locked at the start: the crime scene and one other place
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
 "acted": [pid, ...],          # players who used their one action in the current round
 "round": 1..3,                # only during the investigation; log entries of a round carry it too
 "searched": [location, ...],
 "planted": False,
 "log": [entry, ...], "next_log_id": 1,
 "votes": {"1": 3},            # keys are str(pid of voter), values are target pid
 "result": None | result, "abort_reason": None | str
}
```
Log entry: `{"id": int, "kind": "search"|"share"|"system", "by": pid|None, "text": str, ...}`
plus, depending on kind: `location`, `clue_id`, `implicates`, `clue_kind`, `planted` (bool, on search/share entries).

Result: `{"winner": "detectives"|"murderer", "murderer": pid, "murder_location": str,
"tally": {"3": 2, ...}, "secrets_kept": [pid, ...]}` (`tally` only lists players who received at least one vote)

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
Location clues also carry `"location": str`. Clue ids are unique within a case.

`generator.build_case(pids: list[int], seed: int, story: dict | None = None) -> case` is deterministic for the same arguments. Without a story it uses case #001 (`content.DEFAULT_STORY`).
`generator.build_valid_case(pids, seed, story=None) -> case` tries seed, seed+1, ... (max 5) until `validate_case` passes, else raises `logic.Rejected`.

`logic.validate_case(case, pids, story=None) -> list[str]` returns a list of problems; an empty list means valid. Checks:
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
start(game, token, online, now, seed=None, fixed_case=False) -> game  # host only
end_phase(game, token, online, now) -> game         # host only, only in REVEAL/INVESTIGATION/DISCUSSION/VOTE
tick(game, online, now) -> game                     # timers, early end, host handover, abort
search(game, token, location, now) -> game
share(game, token, clue_id, now) -> game
has_move(game, pid) -> bool                         # an open unsearched place or an own unshared clue
plant(game, token, target_pid, location, now) -> game
plant_locations(game) -> list[str]                  # where the murderer may plant right now
vote(game, token, target_pid, now) -> game
public_view(game, online) -> dict
private_view(game, token) -> dict | None
```

### Behaviour
- **join**: only in LOBBY (else Rejected). Name via `clean_name`: NFKC-normalised, tabs and line breaks become
  spaces, other control characters are dropped, runs of spaces become one; invisible characters (Unicode
  format, private-use, unassigned, line/paragraph separators, blank letters such as U+2800, U+3164) and
  more than 2 combining marks in a row are refused; it needs a letter or digit; 1..20 characters. Unique in the
  room by `name_key` (ignoring case, accents, width and Cyrillic/Greek look-alike letters). A 7th player is rejected. Token must not already be used in the room.
- **kick**: only in LOBBY; only the host; the target must be another player of the room. The player is removed from `players`.
- **start**: only the host; only in LOBBY; the number of *online* players must be 4..6. Offline lobby players are removed from `players`. Picks the story (see *Stories* below), stores it in `game["story"]` and builds the case with it (seed=None → random seed). Phase becomes REVEAL, `phase_started = now`, `deadline = now + 30`.
- **end_phase**: moves to the next phase immediately (same as a timer running out).
- **tick** (in this order):
  1. Host handover (any phase except RESULT/ABORTED): if the host is not in `online` and another player is, the first online player in join order becomes host. The old host does not get the role back.
  2. Abort: in REVEAL, INVESTIGATION, DISCUSSION, VOTE, if fewer than 3 players are online → phase ABORTED, `abort_reason` set.
  3. Timer: if `now >= deadline` → next phase. The new phase starts at `now` (deadline = now + its duration). One step per call.
  4. Early end: INVESTIGATION ends as soon as every online player is in `acted` or has no move left (`has_move`); VOTE ends as soon as every online player has voted.
  - Order of phases: REVEAL → INVESTIGATION → DISCUSSION → VOTE → RESULT.
  - When VOTE ends, `result` is computed.
- **Interrogations are not part of the app.** The players question each other out loud, face to face; there is no question or answer action and no question/answer log entry.
- **Actions** `search`, `share`: only in INVESTIGATION, only by a player of the game, only once per player in total (the pid is then in `acted`).
  - `search`: location must be in `content.LOCATIONS`. If already in `searched` → Rejected and the action is **not** used up. Otherwise the location clue is appended to the log (kind "search") and the location to `searched`.
  - `share`: `clue_id` must be one of the player's own private clues and not shared before.
- **plant**: only in INVESTIGATION; only the murderer; only once per game (`planted`); target must be another player (an innocent); location must be in `plant_locations(game)`: not yet in `searched`, and not a location whose real clue implicates the murderer with a strong kind. Does **not** use up the normal action. The location is appended to `searched` (its real clue is covered up). Appends a log entry kind "search" with `planted: True`, `implicates: target`, `clue_kind: "suspicious"`; its text uses `content.TEMPLATES["herring"]` with the target's rumor, exactly like a real red herring.
- **vote**: only in VOTE; target must be another player of the game (not self); one vote per player.
- **Result**: detectives win only if the murderer has strictly more votes than every other player. A tie at the top or zero votes → the murderer wins. `secrets_kept` lists the innocents for whom no log entry has `implicates == pid` and `clue_kind == "suspicious"`.
- Any call with an unknown token → Rejected.

### Views
- `public_view(game, online)` → `{"code","phase","deadline","players":[{"pid","name","role","online","is_host","acted","voted"}],"log":[...],"searched":[...],"result":None|result,"abort_reason", "characters": None | [...]}`.
  `role` is None in LOBBY and the player's role name from REVEAL on. **Roles are public** (clues talk about roles, so everybody must know who plays whom); who the murderer is stays secret.
  Before RESULT: log entries contain **no** `implicates`, `clue_kind`, `planted` keys; `result` is None; `characters` is None; and nowhere in the view is there a token, the murderer, a secret, an intro, an alibi or a private clue. In RESULT: full log, result, and `characters` (the case's characters with names).
- `private_view(game, token)` → None for an unknown token. Otherwise `{"pid","name","is_host","phase","acted","voted","role","intro","alibi","secret","is_murderer","clues":[{"id","text","shared"}],"can_plant","plant_locations","last_move","puzzles"}`. Before the game starts, the case fields are None / empty. `plant_locations` is empty unless `can_plant`; `can_plant` is False when there is no location left to plant at. It never contains another player's card or token.

## `db` functions (SQLite)
```
connect(path) -> sqlite3.Connection        # creates tables if needed
create_room(conn, now) -> code             # 4 letters from "ABCDEFGHJKLMNPQRSTUVWXYZ", unused
                                           # at 200 rooms in the last hour, lobbies without activity for
                                           # IDLE_ROOM_SECONDS are deleted first; logic.Rejected if still 200
claim_ai_case(conn, now) -> bool           # True and counted if fewer than MAX_AI_CASES_PER_HOUR (30) AI
                                           # requests were made in the last hour
load(conn, code) -> game | None
apply(conn, code, fn) -> game              # runs game = fn(game) inside ONE write transaction and saves it.
                                           # If fn raises logic.Rejected: rollback, nothing saved, exception re-raised.
                                           # Unknown code → logic.Rejected.
heartbeat(conn, code, pid, now) -> None
presence(conn, code) -> dict[int, float]   # pid -> last_seen
raw_state(conn, code) -> str | None        # the stored JSON text, for "unchanged" checks
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
ai.review_story(client, model, story) -> {"available", "ok", "problems", "answer"}   # the test reading
ai.judge(answer, culprit_role, roles) -> list[str] | None   # [] = passed, None = unusable answer
ai.player_file(story, case) -> str               # what players can know, round by round; never the solution
balance.build_balanced_case(pids, seed, story) -> case   # AI stories only; raises logic.Rejected
balance.problems(case) -> list[str]              # "inconsistent:", "unfair:", "too easy:", "too hard:", "too complex:"
balance.analyze(case) -> dict                    # the numbers behind the checks
```

- `start` builds case #001 with `generator.build_valid_case`, exactly as before. An AI story is built with
  `balance.build_balanced_case`: `generator.build_case`, then `balance.adjust` (at most 2 innocents with a red
  herring; crime scene opens in round 2, the other locked place in round 3, preferably one without a red
  herring), then `validate_case` and `balance.problems`; the next seed is tried, up to 25. The case gets
  `"balance"` (analyze) and `"solution"` (culprit, culprit_role, motive, method, scene, false_alibi, timeline,
  evidence, red_herrings). Neither is in any view before RESULT; the result of an AI case has
  `"red_herrings"`: [{"points_at", "explained_by", "cleared_by"}].
- Suspicion model (`balance.suspicion`): trace at the scene 3, keycard log against the alibi 2, witness 2
  (1 while the scene is still locked), note or rumor 1. Medium: culprit's lead after round 1 <= 2, with all
  evidence >= 3; at least 3 independent strong sources incl. a place and a private card.

- `start` plays the AI story only if `game["ai_case"]["status"] == "ready"` and `fixed_case` is False.
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
  DISCUSSION. Each new round clears `acted` and sets a new deadline.
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
- `minigames.spec(game, location)` -> `{"id": "MG-0N-kind", "kind": code|scratch|puzzle|cipher, "variant",
  "location", "evidence_id" (the clue id), "evidence_no", "icon", "name", "exhibit", "verb", "story",
  "hints": [3 texts], ...kind-specific data}`. It never contains the answer: no code, no cipher key.
  `private_view(...)["puzzles"]` maps every place to its spec during INVESTIGATION (else `{}`).
- Proofs: code `{"code": "1723"}`; scratch `{"cells": [cell indices]}` (at least 55 % of 10 × 14);
  puzzle `{"swaps": [[a, b], ...]}` replayed on the seeded starting order; cipher `{"shift": n}`.
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
