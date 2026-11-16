# "What happens if …" – Answer sheet for the Q&A

Each answer describes what the app actually does. The test that proves it is given in brackets
(`tests/test_rules.py`, `test_views.py`, `test_db.py`, `test_case.py`; number = Done-when line of the spec).

## Failures

**… a player goes offline (phone off, no internet)?**
Every open phone checks in every 2 seconds. If nothing arrives for 20 seconds, the player is shown as "offline" in everyone's list. The game continues. Their action counts as "no action", their vote as an abstention. Nobody has to wait for them: the round ends as soon as all online players are done, at the latest when the timer runs out. (DW 12, 13)

**… they come back?**
They open the same link in the same browser and are back in their seat, with the same card, in any phase. The link contains their secret token (22 random characters). (Smoke test, DW 17)

**… they try from a different device?**
It doesn't work without the link. This is intentional: if you could get back in with name and room code, anyone could take over someone else's seat and read their card.

**… the host goes offline?**
After 20 seconds, the next online player in join order automatically becomes host. If the old host comes back, the new host stays host. (DW 14)

**… too many players drop out?**
If fewer than 3 players are online during the game, the game ends with a message on all screens. With 3 it continues. (DW 15)

**… the murderer goes offline?**
The game continues normally. They can be voted for and are revealed at the end.

**… the app restarts?**
Locally everything is kept, because the game state is stored in an SQLite file (DW 21). On free hosting the file can be lost on a restart. Then you need a new room. We decided this on purpose: a game lasts 5 minutes.

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

**… a question is never answered?**
At the end of the discussion the log states that no answer came. (DW 8)

**… nobody does anything?**
The timers advance the phases: 30 s cards, 90 s investigation, 60 s discussion, 30 s vote. (DW 6)

## Security

**… someone wants to see another player's card?**
The server sends each phone only its own card. Before the reveal, the board and the public log contain neither the murderer nor secrets nor private clues. (DW 17)

**… someone types HTML or formatting into a question?**
It appears as plain text, nothing is executed. At most 140 characters. (DW 18)

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
No. Murderer, crime scene, roles and clues are drawn anew for every game. With the demo switch you always get the same case, for rehearsing. (DW 2)

**Where is the data stored?**
In an SQLite file on the server: one row per room with the game state, plus a table with the players' heartbeats. There are no accounts, no passwords and no email addresses.

**What do the tests cover?**
All rules and rejections, the timers, the failure rules, the case checker, visibility (who sees what) and storage. The interface is played through with a mock. We check the look in the browser by hand.
