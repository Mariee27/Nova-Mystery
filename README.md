# NOVA MYSTERY

A multiplayer murder mystery for 4 to 6 players (about 20 minutes once it starts, plus two short hot-seat
breaks of about a minute each), built with Python and Streamlit.
One screen (the projector) shows the public board. Every player joins on their own phone, gets a
secret role card, and together the group has to find out who committed the murder before time runs out.
The host plays the handcrafted case #001 "The Last Lecture" or asks an AI for a brand-new case.

**Course:** Introduction to Programming, Nova SBE

**Live app:** <https://nova-mystery.streamlit.app> (Streamlit Community Cloud; see [Deployment](#deployment)).
The app sleeps when nobody used it for a while: the first visit then wakes it up, which takes about a minute.

## Team

| Name | Student number |
|---|---|
| Laura Ann Emke | 78309 |
| Marie-Christin Pelz | 80454 |
| Tassilo Stewanowitsch | 78127 |
| Emilia Vetter | 81228 |

---

## 1. The problem and the idea

Party murder-mystery games usually need printed cards, a game master who knows the solution,
and a long evening. We wanted a version that a group of students can start in a lecture break:
no accounts, no printing, nobody who has to stay out of the game, and a fair case that is
different every time.

## 2. How to play

1. Someone opens the app on a laptop connected to a projector and clicks **Create room**. The board
   shows a 4-letter room code and a QR code.
2. Every player scans the QR code (or enters the code) and picks a name. The first player is the host.
3. The host picks the case (case #001 with a new culprit every game, or a new
   AI-written case) and starts the game. Each phone now shows a private file: a role, an alibi, a secret,
   and two private cards. One player is secretly the murderer: their file carries a big red MURDERER
   stamp (each phone is only seen by its owner).

**The cards.** Every card is true and physically possible, and the kind of card gives nobody away. Every
player, the murderer too, holds one sighting ("At 23:20 you saw … at the …", always of somebody at the
observer's own place) or the witness account, and one more card: an observation, a rumor, or the witness
account. The innocents spend the evening in pairs (three together if needed) who see each other around
23:30; one or two of them are alone. So at the start the murderer is never the only one without an alibi:
a lone innocent looks just as suspicious until the keycard log of their place (a night camera on the
Beach) is found and clears them. The murderer's claimed place has a log too – it shows
they never came.

| Phase | Time | What happens |
|---|---|---|
| Reveal | 30 s | Everybody reads their card. |
| Investigation | 3 rounds, each up to 5 min | Each round every player has exactly **one** action in the app: search a place on the **campus map** or share one of their clues. Interrogations happen **out loud**: the players question each other face to face. A round ends early when everybody has moved or has nothing left to search or share. The murderer may additionally plant one fake clue. |
| Hot seat | after rounds 1 and 2, about 1 min | A short break (the host can switch it off in the lobby). Everybody picks on their phone whom the room should grill (20 s; never yourself, nobody twice). The suspect with the most picks sits in the hot seat for 45 s: the room questions them out loud, their phone shows their own story as a cheat sheet, and everybody else taps 👍 Believe or 👎 Lying. The board shows only counts, never who picked or rated whom. Nobody can search, share or plant during the break. |
| Discussion | 3 min | Players question each other in person and argue (lying is allowed). |
| Vote | 1 min | Everybody taps a suspect (nothing is chosen in advance) and, if they like, the crime scene, then *Vote*. |
| Result | – | The murderer and all cards are revealed. Detectives win only if the murderer got strictly the most votes. |

**The round, step by step.** The phone first shows "Your move." with two big action cards
(a third, "Plant a false clue", only on the murderer's phone). Each card leads to its own screen with a
"Change action" link back: *Search a place* (tap a pin on the campus plan, read the paper card, press
"Search <place>") or *Share a clue* (tap one of your private clues, "Share with everyone").
Afterwards "Move made." shows your move with a LOGGED stamp and who is still choosing.
A solved exhibit first shows "Access granted" until the player taps *Continue*. Opening a place's mini-game
holds that place for 2 minutes: nobody else can open or search it meanwhile (one place per player; the hold
ends with the find, the time or the round), and nobody sees who holds it. Taps on cards, pins and chips are
handled without reloading the page, so the phone never goes blank between two steps. "Your move." shows the
round, and from round 2 on says that a new round has begun.
There is no interrogation in the app: the players sit in one room and question, accuse and
defend their alibis out loud. A player with nothing left to search or share is told so and is
not waited for.

**The campus map.** A simplified plan of NOVA SBE Carcavelos, seen from above the way the campus is usually
shown (the architects' rendering): north to the upper left, the beach to the bottom right. Gallery / Main Deck
(I) is the long main building from left to right, adjoining the Hovione Atrium (A) at its left end; the
academic halls B, C, D and E hang below it as parallel wings; the Library (H) and Horizon Hall (G) stand
just above it and the Grand Auditorium (F) just past its right end. As on the aerial views, the N6-7 runs
along the bottom into the roundabout below the campus and the big road passes its right end; the beach of
Carcavelos and the sea begin beyond that road, in the bottom right corner. The buildings carry the letters
of the official campus map. There is no car park and no canteen on the plan. The drawing is one SVG of
building outlines, roads and grounds; it and the pins use percent of the map (`content.BUILDINGS`,
`GROUNDS`, `ROADS`, `PLACES`), so phone and board draw the same plan. The buildings carry no letters (a
legend would only crowd the phone); every place of a case has its name on its pin. The north arrow follows
the satellite view: north is left and a little up. Every case happens at 5 of 7 places
(Library, Horizon Hall, Auditorium, Main Deck, Hovione Atrium, Santander Hall, Beach). Each place holds exactly one clue. Pins are
red (open), grey with a tick (searched) or dashed with a lock (locked). Two places are locked at the
start – the crime scene and one other – and open in rounds 2 and 3. The board names the round a place
was searched in, never who searched it, so the murderer's planted clue does not stand out.

**The board during the rounds** shows room code, round and a big timer; the campus plan; the detectives
(moved or still choosing, never which action) and the evidence board (newest first).
It never shows private cards, private clues or the solution.
Every rule (one move per round, locked or searched places, only your
own clues, only players of your room) is checked on the server, with a test for the allowed and the
refused case (`tests/test_rounds_and_map.py`).

Phases end early when everybody is done, and the host can skip ahead.

## 3. Features

- **Real-time multiplayer** for 4–6 players on their own phones, plus a public projector board.
- **A new case every game.** The generator draws the murderer, the crime scene, roles, alibis and clues.
  A demo ("Play a demo") always plays the same case with the same culprit, for rehearsing a presentation.
- **A new story for a room, written by AI (optional).** When the host picks it in the lobby, an AI model writes
  a new NOVA-campus story while the players join: victim, five locations, six suspects with motives, secrets
  and rumors, the endings, and the words of the five mini-games. The AI only writes words. Who did it, where,
  and which clue points to whom is still decided by the generator, and every AI story is checked
  (`logic.validate_story`) before it is used. If the AI is not set up, too slow, over its daily limit, or writes
  something that fails the checks, the AI writes one more case on its own (if the AI quota allows it; the
  host sees "The first AI case did not pass the checks …"). If that one fails too, or the AI service itself
  fails (no key, limit, busy, timeout), only the host sees why and can try again or play case #001.
  See section 4 for the setup.
- **Every case has its own opening.** The home page plays a short intro about the game. When the host starts,
  every phone plays the intro of *this* case (six lines written with the story, then the case title) before
  the private files open. The board plays a longer scene that everybody watches together: police tape and
  blue lights, the victim and where the body was found ("But this is not where Vale died."), then the
  suspects as file cards (name, role, public dossier line) landing one by one, all within the 30 seconds of
  "Read your file". Only public facts; who did it stays secret. While the AI is still writing, the lobby says so instead of showing an
  old case file.
- **Every case is checked for fairness** before the game starts (exactly one murderer, at least two strong
  clues against them, no strong clue against innocents, …). See `logic.validate_case`.
- **Hidden information:** each phone only ever receives its own card. The board shows no secrets until the result.
- **A murderer's special move:** one planted fake clue that looks exactly like a real search result.
- **Hot seat between rounds:** the interrogation happens out loud, with a little structure: the phones pick
  the suspect, the board shows them with a clock and a live 👍/👎 meter (see the phase table above).
- **Robust to real life:** the game page asks the phone to keep its screen on (Screen Wake Lock, where the
  browser supports it). A player without a sign of life for 45 seconds is marked offline and never blocks the
  game; the host role moves to another player. If fewer than 3 players are online, the game pauses (the clock
  stands still, every screen says so) and runs on as soon as they are back; only after 3 minutes without
  enough players does it end. Reopening the tab or the same link restores the seat.
- **Timers** on every phase, so the game always ends.
- **Host tools:** choose the case, switch the hot seat on or off, start the game, start the hot seat early, end
  a phase or the break early, add demo suspects (computer players for presentations), remove strangers from
  the lobby.

### Evidence mini-games – play to unlock

In every room created by the app, each place's clue is a **sealed exhibit**. Tap a pin, press
*Search &lt;place&gt;*, and solve that place's puzzle on your phone; solving it is your move for the round.
A case has five places and there are five games, so **every place has a different game**; which place gets
which game changes from game to game. The games are made of things the victim left behind that night, in
the case's own words (see *Mini-games that fit the case* below).

| Game | What you do | Solvable from |
|---|---|---|
| 🔐 Crack the code | Tap a 4-digit code on a keypad | The case timeline: death ≈ 23:30, body found 23:47 (e.g. 17 minutes, then 23 → `1723`) |
| 🕵️ Rub to reveal | Rub the dust (finger or mouse) off a find: a note, a printout, a phone screen or a photo | Just rubbing: 55 % of it |
| 🧩 Reassemble the still | Tap two pieces to swap them (9 or 6 pieces of the night camera's still of the place) | The picture itself; the hints say where its parts are |
| 🧠 Decode the note | Turn a cipher wheel until the victim's shifted-letter note reads | The note is signed with the victim's name |
| 🗂️ Order the evening | Tap four torn diary entries in the order they happened | Their times (24-hour clock) |

- **Checked in Python, never on the phone.** The phone only reports what the player did (digits, rubbed cells,
  swaps, wheel setting, the order tapped). `minigames.verify` checks it against data the phone never gets (the
  code, the cipher key, the right order) or cannot change (the seeded starting order), and `logic.search` refuses to hand out the clue without a
  valid proof. Each place still has exactly one clue, so evidence is awarded exactly once.
- **Hints** on request, one by one (nudge → stronger hint → almost the answer), plus contextual feedback after a
  wrong attempt ("that is just one time from the case file …"). Wrong answers cost nothing but time.
- **Reward:** "🔓 ACCESS GRANTED · NEW EVIDENCE DISCOVERED · Evidence #0N – …", the clue, the case progress and a
  link to the evidence log. It stays until *Continue*, even if the round ends in that very second.
- **Phone first:** one custom Streamlit component (`st.components.v2`, no new package), pointer events for touch and
  mouse, tap targets of at least 48 px, no horizontal scrolling at 320 px. Sound is off by default (🔇/🔊 in the
  puzzle header) and only starts after a tap, as mobile browsers require. Reduced motion is respected.
- **Mini-games that fit the case.** Every case brings the words of its five games (`story["minigames"]`):
  the victim's locked object, the victim's coded note, the find under the dust (style and lines), the caption
  of the camera still, and four entries of the victim's last evening. Case #001 has its own
  (`content.CASE_MINIGAMES`: Vale's grade cabinet, his coded note, his phone, his diary). An AI case writes
  them in the same request as its story, so they cost no extra AI request. Code checks every piece
  (`minigames.clean_content`): it names no suspect and none of "murder", "kill", "culprit", "guilty", every
  line fits its picture, the diary has four entries in time order, at least 10 minutes apart and none after
  23:30. A piece that fails is replaced by a neutral one that fits every case (`content.MINIGAME_FALLBACK`),
  so a weak answer never costs the case. The words decide nothing: the answers (the code, the cipher key,
  the order, the starting order of the pieces) come from code, and the clue a player earns is the same
  whatever a game shows.
- **The pictures are drawn from those words** (`exhibits.py`, SVG, every word escaped): the jigsaw is the
  night camera's still of the place, the campus illustration of the place (`assets/minigames/puzzles/`:
  Hovione Atrium, Library, the Main Deck hall with the KPMG Gallery, Grand Auditorium; for the Beach,
  Santander Hall and Horizon Hall the middle of a campus print: the beach and the fort, a staircase, the
  building corner with its sun fins) with REC, camera number,
  place, time and the case's caption; the scratch card is a handwritten note, a receipt or printout, a phone
  screen with messages, or a photo print of the campus (`assets/minigames/scratchcards/`) with a caption.
- Every puzzle is built from the case seed and the story, so it works for case #001 and AI-written cases, and
  every player in a room gets the same puzzle for the same place. Demo bots skip the puzzles and wait until every
  human has moved, so they never snatch a place from someone who is solving it.

## 4. Run it locally

Requirements: Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run streamlit run app.py
```

Then open <http://localhost:8501>. To try a full game alone, click **Play a demo** (you and four computer
suspects), or open a room in several browser windows (each window is one player).

Without uv:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip
.venv/bin/streamlit run app.py
```

Optional environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | not set | A `postgresql://` address. If set, rooms live in PostgreSQL and survive a restart of the app. |
| `MURDER_DB` | `data/murder.db` | Where the SQLite file is stored when `DATABASE_URL` is not set. |
| `APP_BASE_URL` | the page's own URL | Public address of the app, used for the QR code. Set it when deployed. |
| `OPENROUTER_API_KEY` | not set | Key for AI-written cases. Without it, every game plays case #001. |
| `OPENROUTER_MODEL` | `google/gemma-4-31b-it:free` | Which free OpenRouter model writes the stories. |

All of them can also go into `.streamlit/secrets.toml` (git ignores it). Copy
`.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the values.

### AI-written cases (OpenRouter)

We use [OpenRouter](https://openrouter.ai) and one of its free models (the model id ends in `:free`). Without
buying credit, free models allow 20 requests per minute and 50 per day. A new AI case takes 2 to 5 requests
(writing, perhaps one repair, the test reading, perhaps one revision and a second test reading), so the free
quota is enough for about 10 to 25 AI rooms a day; after that, rooms play case #001.

**How an AI case is made, and why it is medium difficulty.** The AI only writes texts: the victim, six
suspects with a motive, a secret and a rumor the secret explains, traces, places and endings, in the mood of a
psychological thriller. The facts are decided by code (`generator.py`), and for AI stories `balance.py` then
tunes them and checks them; case #001 never passes through it and is built exactly as before
(`tests/test_demo_case_frozen.py`).
- *Solution first:* culprit, scene, false alibi and where everybody really was are fixed before any clue
  exists; every clue is made from these facts, and the solution file (motive, method, timeline, evidence,
  red herrings) is stored with the case. Nobody sees it before the result.
- *Fair:* three independent pieces of evidence (the trace at the scene, the keycard log against the false
  alibi, a witness on somebody's private card); losing any one still leaves two; sharing private cards matters.
- *Not obvious:* after round 1 two or three people look suspicious and the culprit is at most slightly ahead.
  The crime scene opens in round 2, the revelation in the middle that makes earlier clues fall into place.
- *Controlled misdirection:* one or two red herrings, each explained by that person's secret and cleared by a
  sighting from another player. The result screen explains them under "The false trails".
- *Not too hard:* with everything found and shared, the culprit clearly stands out; every timeline and every
  clue is checked for contradictions.
- *Test reading:* a second AI request reads a sample case like a player, without the solution, and says
  whom it suspects after round 1 and at the end. Code judges the answer: the reader must find the culprit at
  the end without being sure after round 1, without a leap of faith, with explainable red herrings and clear
  texts. Otherwise the author gets the findings and revises once. The test player is a free model too and
  often misreads a case, so its verdict improves a case but never throws one away: a case that passed every
  code check is played (the findings go to the server log). Only a story from which no fair case can be
  built for every number of players is refused. If the test reading is unavailable, the code checks decide.

**Why not Requesty, the course's standard?** We tried it first. Requesty rejected every request from our
account, also for its free models, with "Your organization reached its limit of concurrent requests". Its limit
for parallel requests is the account balance times 5, so it is 0 without credit. OpenRouter's free models work
without buying credit, and both speak the same OpenAI format, so only the address, key and model changed.

1. One team member creates a free account at openrouter.ai and creates an API key.
2. Share the key only privately (password manager or direct message), never in a chat, issue or commit.
3. Put it into `.streamlit/secrets.toml` as `OPENROUTER_API_KEY = "..."` and restart the app (on Streamlit
   Cloud: the app's **Settings → Secrets**, see Deployment).
4. In the lobby the host picks "A new case written by the AI". Only then is the AI asked (creating rooms and
   demos never uses the quota). The host's phone shows "The AI is writing your case …" and, a little later,
   "New AI case ready"; *Start game* waits for it. If it fails or takes longer than 6 minutes, the host sees
   why and can *Try again* or switch to case #001. *Write a different AI case* asks for another one. At most
   5 AI cases per hour and 10 per day are written for the whole app (a case takes up to 5 requests, the free
   plan allows 50 a day); raise `MAX_AI_CASES_PER_HOUR` / `_PER_DAY` in `db.py` if you buy credit.
   These limits are rolling windows, not a reset at a fixed time: a new case is allowed if fewer than 5 were
   started in the last 60 minutes and fewer than 10 in the last 24 hours. An automatic second try counts as a
   case of its own. OpenRouter's own limit for free models resets once a day.

If a key ever leaks: revoke it on openrouter.ai immediately, create a new one, and update it locally and on
Streamlit Cloud. Deleting the commit does not remove it from the history.

The free models and limits can change. Pick another model ending in `:free` from openrouter.ai/models and set it
with `OPENROUTER_MODEL`.

### Deployment

The app runs on Streamlit Community Cloud (<https://nova-mystery.streamlit.app>): main file `app.py`. Streamlit
Cloud installs the exact versions from `uv.lock` and runs Python 3.14; the tests run on 3.13 and the app needs
3.11 or newer. In the app's **Settings → Secrets**, add:

```toml
APP_BASE_URL = "https://nova-mystery.streamlit.app"
OPENROUTER_API_KEY = "<the OpenRouter key>"
```

`APP_BASE_URL` makes the QR code point to the right address. Without `OPENROUTER_API_KEY` the app works
the same, but only offers case #001.

**Keep the rooms over a restart.** Streamlit Community Cloud restarts the app after every new commit and
after it slept, and a SQLite file is lost then, with every running game. For a presentation, create a free
PostgreSQL database (for example on neon.tech or supabase.com) and add its address as a secret:

```toml
DATABASE_URL = "postgresql://user:password@host/database?sslmode=require"
```

The tables are created on the first visit. Nothing else changes; the same tests run on both databases.

## 5. Run the tests

```bash
uv run pytest
```

The same tests run automatically on GitHub for every push to `main` and every pull request (see
`.github/workflows/tests.yml`): on SQLite and on PostgreSQL, together with a check of all dependencies for known
vulnerabilities, and a demo game in a real browser (`tests/e2e/browser_check.cjs`).

| File | Tests | What it checks |
|---|---|---|
| `tests/test_rules.py` | 141 | Every rule and every rejected action: wrong phase, wrong player, acting twice, voting for yourself, ties, timers, early end, host handover, the pause when players drop out, planting rules, removing players, names that only look like another one. Rejected calls must leave the game unchanged. |
| `tests/test_ai_cases.py` | 118 | AI stories: reading the answer, the checks, the repair round, busy models, the story on every screen. |
| `tests/test_minigames.py` | 84 | The puzzles: solvable from the story, the phone never gets the answer, wrong/forged/duplicate proofs fail, `search` needs a valid proof and awards each clue once, hints and feedback, bots. |
| `tests/test_case_minigames.py` | 70 | Mini-games that fit the case: five different games for the five places, case #001's own words and the AI's (checked, with fallback), the pictures, the diary order, rubbish from a phone never crashes a check. |
| `tests/test_rounds_and_map.py` | 52 | Rounds, locked places and the campus map: every pin in its building, pins far enough apart to tap, no car park. |
| `tests/test_nova.py` | 44 | Accusation and endings, demo suspects, the HTML building blocks (escaping, the murderer stamp on the own file), the board's crime-scene intro and suspect cards. |
| `tests/test_balanced_ai_cases.py` | 38 | AI cases: medium difficulty, the solution file, the test reading, the host's choice, the AI's status. |
| `tests/test_app_smoke.py` | 28 | Plays whole games through every screen with a stand-in for Streamlit, including escaped user input, invalid room codes, the fixed demo case, a broken database, the hot seat and the AI's automatic second try. |
| `tests/test_case.py` | 21 | Case generator and validator, including 600 random cases that must all be solvable and fair. |
| `tests/test_views.py` | 20 | Who sees what: no token, secret, murderer or private clue in the public view before the result; each phone only sees its own card. |
| `tests/test_hot_seat.py` | 19 | The hot seat: when the break happens, picking, ties, rating, the clock, counts only on the board, bots never search in the break. |
| `tests/test_demo_case_frozen.py` | 19 | Case #001 cannot change by accident (fingerprints of its story and cases). |
| `tests/test_db.py` | 19 | Storage on SQLite and PostgreSQL: transactions, rollback, two players acting at the same moment, heartbeats, room and AI limits, shared reads. |
| `tests/test_clue_design.py` | 10 | The cards: true, physically possible, never giving the murderer away by their kind. |
| `tests/test_playtest_fixes.py` | 9 | Fixes from the first playtest: a place is held while somebody solves it, no late intro over the file, a locked-in hot-seat pick, the new-round banner. |
| `tests/test_minigame_screen.py` | 9 | The puzzles on the phone: seal, hints, reward until *Continue*, limited wrong answers, no instant answers. |

All together: 701 tests.

The appearance in a real browser is checked by `tests/e2e/browser_check.cjs` (in CI, or locally with
`node tests/e2e/browser_check.cjs http://localhost:8501` while the app runs).

## 6. How it is built

```
app.py         screens (Streamlit): board, phone, join form; only shows data and passes clicks on
   │   ├── ui.py, minigame_ui.py   HTML building blocks and the mini-game component
   │
   ├── logic.py      all game rules as pure functions: game in → new game out, or Rejected
   │      ├── generator.py   builds a random case from the texts (balance.py tunes AI cases)
   │      ├── minigames.py   the evidence mini-games and their checks (exhibits.py draws the pictures)
   │      └── content.py     all texts of case #001: roles, locations, clue templates, mini-games
   │
   ├── ai.py         asks an AI (OpenRouter) for a new story, in a background thread
   │
   └── db.py         storage, SQLite or PostgreSQL: one row per room (the game as JSON) + heartbeats
```

| File | Lines | Responsibility |
|---|---|---|
| `logic.py` | ~1500 | Rules, phases, timers, the pause, the hot seat, held places, results, the public and private views, case and story validator |
| `app.py` | ~1350 | All screens, taps without reloading, and the polling loop |
| `ui.py` | ~880 | HTML building blocks: map, cards, board, the board's intro, result |
| `ai.py` | ~670 | The AI request, reading and repairing the answer, the test reading |
| `minigames.py` | ~500 | The five mini-games: what the phone gets, the checks, hints, the case's words |
| `minigame_ui.py` | ~490 | The mini-games on the phone (one custom component) |
| `content.py` | ~330 | Case #001: story texts, the campus map, clue templates, the mini-games' words |
| `balance.py` | ~320 | Medium difficulty for AI cases and the solution file |
| `db.py` | ~260 | Rooms, transactions, heartbeats, room and AI limits |
| `generator.py` | ~210 | Turns a seed into a complete case |
| `exhibits.py` | ~180 | The mini-games' pictures (camera stills and documents) as SVG |

A game is one plain dictionary (see `docs/CONTRACT.md` for its exact shape). Each click runs like this:

1. `app.py` calls `db.apply(code, action)`.
2. `db.apply` opens a write transaction, loads the game, and calls the rule from `logic.py`.
3. The rule either returns a **new** game, which is saved, or raises `Rejected`. Then nothing is saved and
   the message is shown to the player.

Every open screen re-reads the game every 2 seconds. That same call records a heartbeat (who is online)
and advances the timers.

## 7. Why we built it this way

| Decision | Why |
|---|---|
| **Rules as pure functions in `logic.py`**, with no Streamlit and no database code | The rules can be tested quickly without a browser or a database (the whole suite runs in a few seconds). A rejected action can never leave a half-changed game behind. |
| **The whole game stored as one JSON row**, in SQLite or PostgreSQL | A game is small and short-lived. One row per room means every action is a single read-modify-write inside one transaction, which also makes simultaneous clicks safe (one writer at a time). SQLite needs no setup at all; with `DATABASE_URL` the same code uses PostgreSQL, so rooms survive a restart. |
| **Polling every 2 seconds** instead of WebSockets | Streamlit has no push channel for this. Polling is simple, works on every phone, and 2 seconds is fast enough for a talking game. The same poll doubles as the "I am online" heartbeat and drives the timers, so no background process is needed. Only one part of each screen refreshes itself, always at the same place; the rest is redrawn when something changes (two self-refreshing parts at moving places crashed Streamlit in the browser). |
| **A secret token in each player's link** instead of accounts | Joining takes a few seconds with no password and no personal data. The token (22 random characters from `secrets`) is the only way to see a card, so nobody can take over another seat with just a name and room code. |
| **The server builds separate public and private views** | Secrets are filtered on the server, so they never reach a screen where they don't belong. Tests check this for every phase. |
| **A generator plus a validator** instead of hand-written cases | Every game is new, and the validator guarantees that every case is solvable and fair. |
| **All story texts in `content.py`** | The story can be changed or translated without touching any rule. |

## 8. Security

- **No credentials in the repository.** The only key (the optional OpenRouter key) is read from the environment or
  `.streamlit/secrets.toml`, never written in the code. `.env`, `.streamlit/secrets.toml` and the database are in
  `.gitignore`; only `.streamlit/secrets.toml.example` with placeholders is committed.
- **The AI never sees players or their data.** It only gets a fixed request for a new story. It never decides
  who is guilty, and its text is checked (length, no giveaway words, no names inside clues) and shown as plain
  text like everything else.
- **No personal data is stored:** no accounts, passwords or e-mail addresses. Only a chosen name per room. Rooms are deleted after 24 hours.
- **Access control:** every action checks the player's token, the phase, and the role (host only, murderer only).
  Before the result, the board never contains the murderer, secrets or private clues.
- **Input validation:** names are limited to 1–20 characters and need a letter or digit. They are normalised,
  and invisible characters (zero-width spaces, text-direction marks, blank letters) are refused, so a name can
  neither be invisible nor pass for another one: names that only look alike (case, accents, full-width letters,
  Cyrillic or Greek look-alikes) count as taken (`logic.clean_name`, `logic.name_key`). All user and AI text is
  escaped before it is shown, so HTML and Markdown are shown as plain text; case texts in widget labels are
  escaped for Markdown too (`ui.md`), so an AI text can never become a link or load an image.
  Room codes from the URL must be exactly 4 valid letters. SQL always uses placeholders.
- **No error details for players:** Streamlit never shows a player the technical details of an error
  (`showErrorDetails = "none"` in `.streamlit/config.toml`); a database problem shows a short message, and the
  details go to the server log only.
- **Abuse limits:** at most 6 players per room, and the host can remove strangers from the lobby. At most 200 new
  rooms per hour; when that is reached, lobbies nobody was active in for 5 minutes are freed, so a flood of rooms
  blocks new ones for minutes, not an hour. The AI is only asked when a host picks an AI case, and for at most
  5 cases per hour and 10 per day; past that, the host is told why and plays case #001. Both limits work without recognising visitors,
  because behind the host's proxy their addresses are not reliable.
- **Dependencies:** four direct dependencies (`streamlit`, `qrcode[pil]`, `openai` for the OpenRouter calls, and `psycopg` for PostgreSQL). All 50 packages the app needs are pinned to exact versions
  in `uv.lock` and `requirements.txt` and checked against the OSV vulnerability database (no known vulnerabilities at the time of submission;
  the check runs again on every push).

More scenarios, each with the test that proves it, are in [`docs/WHAT_HAPPENS_IF.md`](docs/WHAT_HAPPENS_IF.md).

## 9. Limits

- **Storage on free hosting:** with SQLite, Streamlit Community Cloud loses every room when it restarts the app. Set
  `DATABASE_URL` to a free PostgreSQL database to keep them (see Deployment).
- **One server process:** SQLite and polling are fine for a few rooms at a time, but not for hundreds of games at once.
- **The link is the key:** whoever has a player's link (screenshot, browser history) can see that card. Coming back on another device
  is not possible without the link.
- **2-second delay:** updates appear with up to 2 seconds of delay, and every open screen causes a small amount of server work.
- **Phones that sleep:** the page keeps the screen on where the browser allows it (not on iOS before 16.4). A phone
  that goes dark anyway counts as offline after 45 seconds; with fewer than 3 players online the game pauses.
- **Fixed size:** every case has 6 roles and 5 locations, so the game supports at most 6 players. Without the AI,
  repeat players get to know the texts of case #001.
- **AI quality varies:** a free model sometimes writes a weaker story or one that fails the checks (then the host
  can try again or play case #001). The free plan allows about 50 AI requests a day, enough for about 10 AI
  cases; the app writes at most 10 a day and 5 an hour.
- **English only.**

## 10. How it could change

- **Push updates via WebSockets** (e.g. a FastAPI backend) to remove the polling delay. `logic.py` could be reused unchanged.
- **More content:** more roles, locations and story variants in `content.py`. The validator would keep new cases fair.
- **More players or game modes,** for example several rounds, an accomplice, or adjustable timers.
- **Other languages** by adding translated versions of `content.py` and the screen texts.

## 11. Repository structure

```
app.py                  Streamlit screens
ui.py                   HTML building blocks for the screens
logic.py                game rules, views, case and story validator
generator.py            case generator
balance.py              medium difficulty for AI cases: adjustments, checks, the solution file
content.py              story texts of case #001 and the clue templates
ai.py                   asks an AI (via OpenRouter) for a new story
db.py                   storage: SQLite or PostgreSQL
minigames.py            evidence mini-games: puzzles, hints and the Python-side check
minigame_ui.py          the mini-games on the phone (HTML fragments and one custom component)
exhibits.py             the mini-games' pictures: camera stills and documents, drawn as SVG
assets/minigames/       the campus illustrations: puzzles/ (camera stills), scratchcards/ (photo prints)
docs/CONTRACT.md        exact function signatures and data shapes
docs/WHAT_HAPPENS_IF.md answers for edge cases, each linked to a test
tests/                  pytest suite (701 tests); tests/e2e/ the browser check
.github/workflows/      automatic tests and dependency check on GitHub
pyproject.toml, uv.lock pinned dependencies (uv)
requirements.txt        the same pinned dependencies for pip (Streamlit Cloud uses uv.lock)
```
