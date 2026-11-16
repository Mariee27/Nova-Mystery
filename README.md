# Murder at NOVA

A five-minute multiplayer murder mystery for 4 to 6 players, built with Python and Streamlit.
One screen (the projector) shows the public board. Every player joins on their own phone, gets a
secret role card, and together the group has to find out who murdered Dr. Marta Quintela before time runs out.

**Course:** Introduction to Programming, Nova SBE

**Live app:** _add the Streamlit Community Cloud link here_

## Team

| Name | Student number |
|---|---|
| Emilia Vetter | 81228 |
| Laura Ann Emke | 78309 |
| Tassilo Stewanowitsch | 78127 |
| Marie-Christin Pelz | 80454 |

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
3. The host starts the game. Each phone now shows a private card: a role, an alibi, a secret, and two
   private clues. One player is secretly the murderer.

| Phase | Time | What happens |
|---|---|---|
| Reveal | 30 s | Everybody reads their card. |
| Investigation | 90 s | Each player has exactly **one** action: search a location, ask someone a public question, or make one of their clues public. The murderer may additionally plant one fake clue. |
| Discussion | 60 s | Players talk and answer open questions (lying is allowed). |
| Vote | 30 s | Everybody votes for a suspect. |
| Result | – | The murderer and all cards are revealed. Detectives win only if the murderer got strictly the most votes. |

Phases end early when everybody is done, and the host can skip ahead.

## 3. Features

- **Real-time multiplayer** for 4–6 players on their own phones, plus a public projector board.
- **A new case every game.** The generator draws the murderer, the crime scene, roles, alibis and clues.
  A demo switch gives a fixed case for rehearsing.
- **Every case is checked for fairness** before the game starts (exactly one murderer, at least two strong
  clues against them, no strong clue against innocents, …). See `logic.validate_case`.
- **Hidden information:** each phone only ever receives its own card. The board shows no secrets until the result.
- **A murderer's special move:** one planted fake clue that looks exactly like a real search result.
- **Robust to real life:** players who lose connection are marked offline and never block the game, the host
  role moves to another player, and the game stops cleanly if fewer than 3 players are left. Reloading the
  page or coming back later via the same link restores the seat.
- **Timers** on every phase, so the game always ends.
- **Host tools:** start the game, end a phase early, remove strangers from the lobby.

## 4. Run it locally

Requirements: Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run streamlit run app.py
```

Then open <http://localhost:8501>. To try a full game alone, open the room in several browser windows
(each window is one player).

Without uv:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip
.venv/bin/streamlit run app.py
```

Optional environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `MURDER_DB` | `data/murder.db` | Where the SQLite file is stored. |
| `APP_BASE_URL` | the page's own URL | Public address of the app, used for the QR code. Set it when deployed. |

### Deployment

The app runs on Streamlit Community Cloud: main file `app.py`, dependencies from `requirements.txt`.
Set `APP_BASE_URL` to the public URL in the app's secrets so the QR code points to the right address.

## 5. Run the tests

```bash
uv run pytest
```

The same tests run automatically on GitHub for every push to `main` (see `.github/workflows/tests.yml`),
together with a check of all dependencies for known vulnerabilities.

| File | Tests | What it checks |
|---|---|---|
| `tests/test_rules.py` | 124 | Every rule and every rejected action: wrong phase, wrong player, acting twice, voting for yourself, ties, timers, early end, host handover, abort, planting rules, removing players. Rejected calls must leave the game unchanged. |
| `tests/test_case.py` | 21 | Case generator and validator, including 600 random cases that must all be solvable and fair. |
| `tests/test_views.py` | 19 | Who sees what: no token, secret, murderer or private clue in the public view before the result; each phone only sees its own card. |
| `tests/test_db.py` | 13 | Storage: transactions, rollback on rejection, two players acting at the same moment, heartbeats, room codes, room limit. |
| `tests/test_app_smoke.py` | 2 | Plays a whole game through every screen with a stand-in for Streamlit, including escaped user input and invalid room codes. |

The appearance in a real browser is checked by hand.

## 6. How it is built

```
app.py         screens (Streamlit): board, phone, join form; only shows data and passes clicks on
   │
   ├── logic.py      all game rules as pure functions: game in → new game out, or Rejected
   │      └── generator.py   builds a random case from the texts
   │             └── content.py   all texts: roles, locations, clue templates
   │
   └── db.py         SQLite storage: one row per room (the game as JSON) + heartbeats
```

| File | Lines | Responsibility |
|---|---|---|
| `logic.py` | ~570 | Rules, phases, timers, results, the public and private views, case validator |
| `app.py` | ~500 | All screens and the polling loop |
| `generator.py` | ~140 | Turns a seed into a complete case |
| `db.py` | ~110 | Rooms, transactions, heartbeats |
| `content.py` | ~80 | Story texts |

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
| **The whole game stored as one JSON row** in SQLite | A game is small and short-lived. One row per room means every action is a single read-modify-write inside one transaction, which also makes simultaneous clicks safe (`BEGIN IMMEDIATE`). No server or database setup is needed. |
| **Polling every 2 seconds** instead of WebSockets | Streamlit has no push channel for this. Polling is simple, works on every phone, and 2 seconds is fast enough for a talking game. The same poll doubles as the "I am online" heartbeat and drives the timers, so no background process is needed. |
| **A secret token in each player's link** instead of accounts | Joining takes a few seconds with no password and no personal data. The token (22 random characters from `secrets`) is the only way to see a card, so nobody can take over another seat with just a name and room code. |
| **The server builds separate public and private views** | Secrets are filtered on the server, so they never reach a screen where they don't belong. Tests check this for every phase. |
| **A generator plus a validator** instead of hand-written cases | Every game is new, and the validator guarantees that every case is solvable and fair. |
| **All story texts in `content.py`** | The story can be changed or translated without touching any rule. |

## 8. Security

- **No credentials in the repository.** The app needs no API keys. `.env`, `.streamlit/secrets.toml` and the
  database are in `.gitignore`.
- **No personal data is stored:** no accounts, passwords or e-mail addresses. Only a chosen name per room. Rooms are deleted after 24 hours.
- **Access control:** every action checks the player's token, the phase, and the role (host only, murderer only, target of the question only).
  Before the result, the board never contains the murderer, secrets or private clues.
- **Input validation:** names are limited to 1–20 characters and must be unique, questions and answers to 1–140 characters,
  and control characters are removed. All user text is escaped before it is shown, so HTML and Markdown are shown as plain text.
  Room codes from the URL must be exactly 4 valid letters. SQL always uses placeholders.
- **Abuse limits:** at most 6 players per room, the host can remove strangers from the lobby, and at most 200 new rooms can be created per hour.
- **Dependencies:** only two direct dependencies (`streamlit`, `qrcode[pil]`). All 42 packages are pinned to exact versions
  in `uv.lock` and `requirements.txt` and checked against the OSV vulnerability database (no known vulnerabilities at the time of submission;
  the check runs again on every push).

More scenarios, each with the test that proves it, are in [`docs/WHAT_HAPPENS_IF.md`](docs/WHAT_HAPPENS_IF.md).

## 9. Limits

- **Storage on free hosting:** Streamlit Community Cloud can restart the app and lose the SQLite file. A running game is then lost
  and a new room is needed. We accepted this because a game lasts only about five minutes.
- **One server process:** SQLite and polling are fine for a few rooms at a time, but not for hundreds of games at once.
- **The link is the key:** whoever has a player's link (screenshot, browser history) can see that card. Coming back on another device
  is not possible without the link.
- **2-second delay:** updates appear with up to 2 seconds of delay, and every open screen causes a small amount of server work.
- **Fixed content:** 6 roles and 5 locations, so the game supports at most 6 players, and repeat players get to know the texts.
- **English only.**

## 10. How it could change

- **Persistent database** (e.g. PostgreSQL) so games survive restarts. Only `db.py` would change, since the rest never touches storage.
- **Push updates via WebSockets** (e.g. a FastAPI backend) to remove the polling delay. `logic.py` could be reused unchanged.
- **More content:** more roles, locations and story variants in `content.py`. The validator would keep new cases fair.
- **More players or game modes,** for example several rounds, an accomplice, or adjustable timers.
- **Other languages** by adding translated versions of `content.py` and the screen texts.

## 11. Repository structure

```
app.py                  Streamlit screens
logic.py                game rules, views, case validator
generator.py            case generator
content.py              story texts
db.py                   SQLite storage
docs/CONTRACT.md        exact function signatures and data shapes
docs/WHAT_HAPPENS_IF.md answers for edge cases, each linked to a test
tests/                  pytest suite (179 tests)
.github/workflows/      automatic tests and dependency check on GitHub
pyproject.toml, uv.lock pinned dependencies (uv)
requirements.txt        the same pinned dependencies for pip / Streamlit Cloud
```
