# "What happens if …" – Answer sheet for the Q&A

Each answer describes what the app actually does. The test that proves it is given in brackets
(`tests/test_rules.py`, `test_views.py`, `test_db.py`, `test_case.py`; number = Done-when line of the spec).

## Failures

**… a player goes offline (phone off, no internet)?**
Every open phone checks in every few seconds. If nothing arrives for 15 seconds, a stand-in takes over that seat: the computer plays it like a demo suspect (it searches or shares, picks and rates in the hot seat, and votes by the evidence the player could read). Board and phones mark the seat "stand-in". Nobody has to wait: the round ends as soon as everybody (stand-ins included) has moved. (`tests/test_stand_ins.py`)

**… they come back?**
They open the same tab, their link, or just the room's QR code in the same browser, and are back in their seat, with the same card, in any phase; the stand-in stops at once. The link contains their secret token (22 random characters); the browser remembers it per room. (Smoke test, DW 17)

**… they try from a different device?**
It doesn't work without the link. This is intentional: if you could get back in with name and room code, anyone could take over someone else's seat and read their card.

**… the host goes offline?**
When the host's seat gets a stand-in (15 seconds) or the host counts as offline (45 seconds), the next player in join order who is there becomes host. If the old host comes back, the new host stays host. (DW 14, `tests/test_stand_ins.py`)

**… too many players drop out?**
Their seats get stand-ins, so the game goes on. (The pause below only applies if fewer than 3 seats are covered, which with stand-ins does not happen in the app.) If fewer than 3 players are online during the game, the game pauses: the clock stands still and every screen says who is missing. As soon as 3 are online again, the clock runs on with the time that was left. Only after 3 minutes without enough players does the game end with a message on all screens. The host can still end a phase while it is paused. (DW 15)

**… a phone's screen turns off?**
The game page asks the phone to keep its screen on (Screen Wake Lock: Chrome, Android, Safari from iOS 16.4). Where a browser does not support it, the lobby asks the players to keep the tab open and the screen on.

**… the murderer goes offline?**
The game continues normally. They can be voted for and are revealed at the end.

**… the app restarts?**
Locally everything is kept, because the game state is stored in an SQLite file (DW 21). On free hosting the file can be lost on a restart. Then you need a new room. We decided this on purpose: a game lasts 15 to 30 minutes.

**… someone reloads the page?**
Nothing is lost. The game state lives on the server, not in the browser.

## Rules

**… someone acts twice or double-clicks?**
The second action is rejected, the game state stays unchanged. (DW 7, 16)

**… two players search the same location at the same time?**
Exactly one wins. The other gets the message "already searched" and may choose another location. Their action is not used up. Technically: every action runs in a write transaction; the second one has to wait and then sees the updated state. (DW 7, 19)

**… someone acts outside the phase (e.g. votes during the discussion)?**
Rejected. (DW 7, 10)

**… someone votes for themselves or votes twice?**
Rejected. (DW 10)

**… the vote ends in a tie?**
The murderer wins. The detectives only win if the murderer has more votes than everyone else. With 0 votes the murderer also wins. (DW 11)

**… someone wants to join after the game has started, or a 7th player arrives?**
Rejected. Watching via the board is always possible. (DW 4)

**… two players want the same name?**
The second one is rejected, regardless of upper/lower case. (DW 4)

**… fewer than 4 players are there?**
The start button is disabled, and a forced start is also rejected by the rules. (DW 4)

**… a non-host wants to start the game or end a phase?**
They don't have the button, and the rules reject it as well. (DW 5)

**… we want to interrogate someone?**
Do it out loud. The players sit in one room and question, accuse and defend their alibis face to face; the app has no question-and-answer function. (`test_dw07_interrogations_are_not_an_action_in_the_app`)

**… nobody does anything?**
The timers advance the phases: 60 s cards (20 s watching the suspects on the board, then 40 s reading), 3 investigation rounds of up to 5 minutes each (a round ends early when everybody has moved or has nothing left to search or share), 3 min discussion, 1 min vote. (DW 6)

## Security

**… someone wants to see another player's card?**
The server sends each phone only its own card. Before the reveal, the board and the public log contain neither the murderer nor secrets nor private clues. (DW 17)

**… someone types HTML or formatting into their name?**
It appears as plain text, nothing is executed. At most 20 characters. (DW 18)

**… someone guesses a link?**
The token has 22 random characters. The room code alone is only enough for watching and, in the lobby, for joining.

**… the murderer's fake clue could stand out?**
It looks like a real search result. Only in the reveal is it marked as fake. In detail:
- It uses exactly the same wording as a real red herring ("A note found at the …"), with the rumor about the blamed player.
- The murderer can only plant at a location nobody has searched yet. That location then counts as searched, so no location ever shows two results.
- During the investigation the player list shows no "acted" marks, so nobody can see that a new result appeared without anyone acting.
- The murderer cannot plant at a location whose real clue points strongly at them, so the case stays solvable.
(DW 9, 17)

**… a stranger guesses the room code and joins the lobby?**
The host can remove any player from the lobby ("Remove a player"). After the start nobody can join anymore.

**… someone puts links or formatting into the room code in the URL?**
Only 4 letters from the room-code alphabet are accepted. Anything else shows "This is not a valid room code" and the text is not shown. Player names are always shown as plain text.

**… someone creates thousands of rooms?**
At most 200 new rooms per hour. After that, "Create room" shows a message until older rooms age out.

**… someone gets hold of a player's link (screenshot, browser history, looking over a shoulder)?**
They can see that player's card and act for them. The link is the only key, which is why there are no accounts. Players should not share or show their link.

## Case and fairness

**Is every case solvable?**
Yes. A checker validates every case before the start: exactly one murderer, at least 2 strong clues against them (at least 1 of them at a location), no strong clue against innocents, at most 1 misleading clue per innocent. Tested over 600 random cases. (DW 1, 3)

**Is it always the same case?**
No. Murderer, crime scene, roles and clues are drawn anew for every game. Only a demo ("Play a demo") always plays the same case with the same culprit, for rehearsing. (DW 2)

**Where is the data stored?**
In an SQLite file on the server: one row per room with the game state, plus a table with the players' heartbeats. There are no accounts, no passwords and no email addresses.

**What do the tests cover?**
All rules and rejections, the timers, the failure rules, the case checker, visibility (who sees what) and storage. The interface is played through with a mock. We check the look in the browser by hand.

## AI-written cases

**Where do the AI cases come from?**
When a room is created, an AI model (a free model via OpenRouter) writes a new story in the background while the players join. The AI only writes words; the generator still decides who did it, where, and which clue points to whom. (`tests/test_ai_cases.py`)

**What if there is no key, the AI is slow, or the daily limit is reached?**
The game plays case #001 "The Last Lecture". Nobody has to wait. Only the host sees a short note with the reason. (`test_when_the_ai_case_is_missing_case_001_is_played_and_only_the_host_is_told`)

**What if the AI writes something unusable, like giving the solution away?**
Every AI story is checked before it can be played: right number of locations and roles, length limits, no "murderer"/"killer", no names hidden in neutral clues, rumors that point at exactly one suspect, and a fair case for 4, 5 and 6 players. A story that fails is not used. (`test_a_broken_story_is_rejected`, `test_an_ai_story_gives_fair_cases_for_many_seeds`)

**Can the AI story leak secrets to the board?**
No. The screens only get the public part of the story (titles, places, public dossiers, endings). Private intros, secrets, traces and rumors only reach a phone through that player's own card or through evidence found in the game. (`test_the_public_story_holds_no_secrets`)

**Can we still rehearse the demo with the same case?**
Yes. A demo ("Play a demo", or the link `?demo=1`) always plays case #001 with the same seed and the same culprit; its host gets no case choice. (`test_a_demo_always_plays_the_same_case_and_offers_no_choice`)

**Does the interface change with the case?**
Yes: the case file, board header, map, suspects' dossiers, the vote question, the endings and the timeline, plus a short intro of the case that plays on the board and every phone at the start. The colours and layout stay the same. The home page shows a general intro, because no case exists before a room is created. (`test_the_case_intro_shows_this_cases_lines_and_title`, `test_while_the_ai_writes_the_lobby_says_so_instead_of_showing_case_001`)

**What if the AI case arrives after the host already started?**
It is ignored; the running game is never changed. (`test_an_ai_case_that_arrives_after_the_start_is_ignored`)

## Rounds and the campus map

**What if I tap a locked place?**
Nothing happens to your move: the paper card under the map says when the place opens, there is no search button, and the server refuses a search there anyway ("This place is locked. It opens in round 3."). (`test_refused_searching_a_locked_place`)

**What if I try to search twice in one round?**
Refused, on the server; after your move the phone shows "Move made." and who is still choosing. Next round you get a new move. (`test_refused_a_second_move_in_the_same_round`, `test_allowed_a_new_move_in_the_next_round`)

**What if two players tap the same place at the same moment?**
Exactly one of them finds the clue; the other is told "This place has already been searched. Pick another one." and keeps their move. (DW 19, `test_refused_searching_a_place_that_was_already_searched`)

**What if I reload the page after tapping a place?**
Nothing is searched: a tap only selects a place. Searching needs the "Search <place>" button, and a second move in the same round would be refused anyway.

**What if I have nothing left to search or share?**
The phone says "Nothing left to search or share." and the round does not wait for you; question the others out loud meanwhile. A player who can still move is waited for, but never longer than the timer. (`test_allowed_the_round_does_not_wait_for_a_player_with_nothing_left_to_do`, `test_refused_ending_a_round_early_while_a_player_can_still_move`)

**What if the timer runs out before I choose?**
Your move for that round is lost; the next round starts and you get a new one. (`test_allowed_a_player_who_misses_the_timer_simply_loses_the_move`)

**What if I press "Share with everyone" without choosing a clue?**
The screen says "Choose a clue to share." and your move is not used up. (`test_the_phone_guides_through_one_move_and_explains_mistakes`)

**Can the map give the solution away?**
No. It shows which places are open, searched or locked – public facts. The crime scene is always one of the two locked places at the start, so that the hunt has a middle; which of the two it is, the map does not say. (`test_the_map_never_gives_the_solution_away`)
