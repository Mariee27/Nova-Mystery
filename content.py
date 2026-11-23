"""All story texts of NOVA MYSTERY – Case #001: The Last Lecture.

Only words live here. Who did it, where, and which clue points to whom is decided
in generator.py.

Case #001 is the fixed case: it is used for the demo, and whenever no AI-written
case is available (see ai.py). All its texts are collected in DEFAULT_STORY at the
bottom of this file; an AI-written case has exactly the same shape.
"""

TAGLINE = "Everyone has a secret. Only one knows the truth."
CASE_NUMBER = "001"
CASE_TITLE = "The Last Lecture"
VICTIM = "Professor Adrian Vale"
VICTIM_SHORT = "Vale"                          # used in short sentences: "Where did Vale really die?"
FOUND_PLACE = "Vale's locked research office"  # where the body was found (not where he died)
# The times are the same in every case: the clue templates below rely on them.
MURDER_TIME = "23:30"
FOUND_TIME = "23:47"

# The opening of the home page, before anybody is in a room: about the game, not one case.
HOME_INTRO_LINES = [
    "NOVA University.",
    "Someone is dead.",   # shown in red
]

# The cinematic intro of case #001. It plays on the board and every phone at the start.
# Line 4 (index 3) is shown in red. An AI case brings its own six lines.
INTRO_LINES = [
    "Carcavelos, Portugal.",
    "23:47.",
    "NOVA University.",
    "A professor is dead.",
    "4 to 6 suspects.",
    "One impossible crime.",
]

BRIEFING = (
    "At 23:47 the night guard found Professor Adrian Vale slumped over the desk of his "
    "locked research office. The police called it an accident. The coroner disagrees: "
    "Vale died around 23:30, and he did not die in that office. Someone moved him, "
    "locked the door, and walked away. Four to six people were still on campus that night. "
    "Every one of them had a reason to hate him. Only one of them knows where it really happened."
)

# ---------------------------------------------------------------- the campus map
#
# NOVA SBE Carcavelos from above, simplified (see ui.campus_map), drawn the way the campus is
# usually shown (the architects' rendering): north is to the LEFT, the beach to the right.
# Gallery / Main Deck (I) is the long main building running left to right; the Hovione
# (Entrance) Atrium (A) adjoins its left end. The academic halls B, C, D
# and E hang below it as parallel wings (the teaching areas), the Library (H) and Horizon Hall
# (G, surf house and restaurant) stand just above it, the Grand Auditorium (F) just past its right end
# towards the beach. The N6-7 runs
# along the bottom into the roundabout below the campus, the big road passes its right end;
# the beach begins beyond that road, towards the bottom right. The building letters
# are those of the official campus map; the layout follows the satellite view turned so.
#
# Every value is percent of the map area (x of the width, y of the height), the same unit as
# the pins, so phone and board draw the same plan. The map is 1.25 times as wide as it is high.

# BUILDINGS: letter of the official campus map -> its name and outline (polygon).
BUILDINGS = {
    "A": {"name": "Hovione Atrium", "shape": [(12.8, 30), (26.4, 28.3), (27.2, 47), (13.6, 49)]},
    "I": {"name": "Gallery / Main Deck", "shape": [(26.8, 34.2), (75.0, 28.0), (75.8, 36.0), (27.6, 42.2)]},
    "B": {"name": "Cascais Academic Hall", "shape": [(32.0, 40.6), (37.6, 39.9), (40.0, 70.6), (34.4, 71.3)]},
    "C": {"name": "CTT Student Hall", "shape": [(44.0, 39.1), (49.6, 38.4), (52.0, 71.1), (46.4, 71.8)]},
    "D": {"name": "Santander Academic Hall", "shape": [(56.0, 37.6), (61.6, 36.9), (64.0, 69.6), (58.4, 70.3)]},
    "E": {"name": "Ming C. Hsu Executive Hall", "shape": [(68.0, 36.0), (73.6, 35.3), (76.0, 62.0), (70.4, 62.7)]},
    "H": {"name": "Teresa e Alexandre Soares dos Santos Library", "shape": [(51.2, 16), (61.6, 15), (62.4, 27.2), (52.0, 28.5)]},
    "G": {"name": "Horizon Hall", "shape": [(65.6, 10), (75.2, 9), (76.0, 25.4), (66.4, 26.5)]},
    "F": {"name": "Jerónimo Martins Grand Auditorium", "shape": [(77.6, 24), (87.2, 22), (88.8, 38), (79.2, 41)]},
}

# The ground around the buildings, drawn below them in this order: (css class, outline).
# The aerial views show the campus in its green site; the big road passes close to its right
# end and meets the roundabout below it; beyond the road a strip of open land, then the beach
# of Carcavelos and the sea in the corner towards the bottom right.
GROUNDS = [
    ("lawn", [(9, 5), (60, 2.5), (86, 6), (89, 40), (82, 80), (50, 86), (9, 85)]),     # the green site
    ("open", [(94, 0), (100, 0), (100, 55), (74, 100), (70, 100), (73, 93.5), (79, 86), (90.5, 60), (93, 30)]),
    ("sand", [(100, 55), (100, 68), (83, 100), (74, 100)]),                           # Carcavelos beach
    ("sea", [(100, 68), (100, 100), (83, 100)]),
]
# Roads as lines: (name or "", points, angle of the name in degrees).
ROADS = [
    ("N6-7", [(0, 91), (36, 90.5), (71.6, 90)], 0),
    ("", [(78, 86.4), (90.5, 60), (92.6, 30), (93.4, 0)], 0),
    ("", [(78.2, 90.0), (77.8, 92.0), (76.9, 93.5), (75.6, 94.0), (74.3, 93.5), (73.4, 92.0), (73.0, 90.0),
          (73.4, 88.0), (74.3, 86.5), (75.6, 86.0), (76.9, 86.5), (77.8, 88.0), (78.2, 90.0)], 0),   # roundabout
    ("", [(74.3, 93.5), (72.5, 100)], 0),
]
# Every case happens at 5 of these 7 places. x, y: the centre of the place's pin, in
# percent of the map. letter: what the pin shows (the building's letter on the official map).
PLACES = {
    "Library": {"letter": "H", "icon": "📚", "x": 55.5, "y": 20.5},
    "Horizon Hall": {"letter": "G", "icon": "🖥️", "x": 70.5, "y": 16},
    "Auditorium": {"letter": "F", "icon": "🎭", "x": 84.5, "y": 35},
    "Main Deck": {"letter": "I", "icon": "🌉", "x": 64, "y": 33.5},   # the indoor hall of the Gallery
    "Hovione Atrium": {"letter": "A", "icon": "🏛️", "x": 20, "y": 38.5},
    "Santander Hall": {"letter": "D", "icon": "🧪", "x": 60, "y": 55},
    "Beach": {"letter": "≈", "icon": "🌊", "x": 88, "y": 82, "open_air": True},
    "Canteen": {"letter": "I", "icon": "🍽️", "x": 40, "y": 36.5},    # in the Gallery (I), west of the Main Deck
    "Garage": {"letter": "≡", "icon": "🚗", "x": 17, "y": 79},        # on the green site, bottom left
}

OPEN_AIR = {name for name, place in PLACES.items() if place.get("open_air")}   # no keycard reader there

# Case #001 happens at these five places.
LOCATIONS = ["Santander Hall", "Library", "Horizon Hall", "Auditorium", "Main Deck"]

LOCATION_FLAVOR = {
    "Santander Hall": "Vale's lab on the second floor. Centrifuges tick as they cool down; a whiteboard still shows his handwriting, half wiped away.",
    "Library": "Green reading lamps glow over empty desks. Somewhere between the shelves, a radiator knocks like a slow heartbeat.",
    "Horizon Hall": "The server room in the basement: cold air, blinking lights and the hum of forty machines. One rack door is open that should be locked.",
    "Auditorium": "Rows of red seats in the dark. The stage light is still warm, as if someone switched it off a minute ago.",
    "Main Deck": "The guard's booth on the deck: twelve camera screens, two of them black, and a cold coffee next to tonight's patrol log.",
}

LOCATION_ICONS = {place: PLACES[place]["icon"] for place in LOCATIONS}

# Every role: a public dossier (everybody may read it), and private texts only the player sees.
ROLES = {
    "The Research Assistant": {
        "dossier": "Vale's PhD researcher for three years. Ran every experiment in his last study.",
        "intro": "You are The Research Assistant. You ran Vale's experiments for three years. "
                 "Last week he submitted the paper under his name alone.",
        "trace": "a lab badge on a frayed blue lanyard",
        "secret": "You quietly changed two data points in the study to make the results look cleaner.",
        "rumor": "The Research Assistant was seen deleting rows from the lab spreadsheets at three in the morning.",
    },
    "The Rival Professor": {
        "dossier": "Senior lecturer in the same department. Applied for tenure twice. Vale sat on both committees.",
        "intro": "You are The Rival Professor. Vale sat on the committee that rejected your tenure – twice – "
                 "and smiled while doing it.",
        "trace": "a silver fountain pen with a chipped cap",
        "secret": "Half of your last grant proposal was copied from a former student's thesis.",
        "rumor": "The Rival Professor was seen feeding the pages of an old student thesis into a shredder.",
    },
    "The IT Technician": {
        "dossier": "Runs the campus servers and the camera system. Works nights, rarely seen in daylight.",
        "intro": "You are The IT Technician. Vale reported you for reading faculty mailboxes. "
                 "Your disciplinary hearing is on Monday.",
        "trace": "a USB stick labelled BACKUP-7 in black marker",
        "secret": "On night shifts you switch off two hallway cameras so you can sleep in the server room.",
        "rumor": "The IT Technician was seen pulling a camera cable out of the wall, then plugging it back in.",
    },
    "The Night Librarian": {
        "dossier": "Keeps the Library and its archive open after midnight.",
        "intro": "You are The Night Librarian. Vale wanted the archive closed and your night shifts cut. "
                 "Without them you cannot pay your rent.",
        "trace": "a brass archive key on a red thread",
        "secret": "Every night you let a homeless student sleep in the reading room after closing.",
        "rumor": "The Night Librarian was seen carrying a blanket and a pillow into the reading room after closing.",
    },
    "The Security Guard": {
        "dossier": "Night guard of the academic halls. Found the body at 23:47 and raised the alarm.",
        "intro": "You are The Security Guard. Vale complained that you sleep on duty. "
                 "One more complaint and you lose the job.",
        "trace": "a torch with a cracked lens",
        "secret": "Three patrols in tonight's log never happened: you were on the phone with your sick mother.",
        "rumor": "The Security Guard was seen writing a whole night of patrol times into the logbook at once.",
    },
    "The Students' Union President": {
        "dossier": "Elected head of the students' union. Had a public argument with Vale last Friday.",
        "intro": "You are The Students' Union President. Vale was about to publish proof that "
                 "the votes in your election were counted twice.",
        "trace": "a gold union lanyard with a broken clasp",
        "secret": "You moved union money into your own campaign fund and called it 'event costs'.",
        "rumor": "The Students' Union President was seen shredding union receipts in the print room.",
    },
}

NEUTRAL_LOCATION_CLUES = {
    "Santander Hall": "A rack of test tubes stands in perfect order. The fridge log shows nothing unusual tonight.",
    "Library": "A returned book about Lisbon trams lies on the counter. Its due date was three weeks ago.",
    "Horizon Hall": "A backup job finished at 22:00 as planned. The status lights are all green.",
    "Auditorium": "A forgotten programme from last week's concert lies on seat F12, folded into a paper boat.",
    "Main Deck": "The lost-and-found box holds two umbrellas, one glove and a forgotten student card.",
}

NEUTRAL_PRIVATE_CLUES = [
    "You noticed the rain started at 22:50 and the courtyard lights reflected in every puddle.",
    "You noticed the main elevator was out of order, so everyone had to take the stairs.",
    "You noticed the vending machine on the ground floor ran out of coffee before 23:00.",
    "You noticed a delivery of printer paper blocking the side corridor all evening.",
    "You noticed the university bell rang eleven times at 23:00, a little late as always.",
    "You noticed the heating in the east wing clicked off at 23:10 to save energy.",
    "You noticed a group of students rehearsing a presentation in the lobby until 22:30.",
    "You noticed the cleaning trolley parked outside the lecture hall the whole night.",
    "You noticed the Wi-Fi dropped for a minute at 22:40 and came back on its own.",
    "You noticed a cat sheltering from the rain under the bicycle racks by the entrance.",
]

TEMPLATES = {
    "alibi": "I was at the {location} around 23:30.",
    "scene": "Found at the {location}: {trace}. It belongs to {role}.",
    # Buildings have keycard readers; open-air places (OPEN_AIR) have a night camera instead.
    "alibi_broken": "The keycard log of the {location} shows no entry by {role} between 23:15 and 23:45.",
    "alibi_broken_open_air": "The night camera at the {location} shows no entry by {role} between 23:15 and 23:45: "
                             "nobody came or went.",
    # Somebody who was alone all evening: the log or the camera of their place vouches for them.
    "present": "The keycard log of the {location} shows {role} inside the whole time from 23:10 to 23:50.",
    "present_open_air": "The night camera at the {location} shows {role} there the whole time from 23:10 to 23:50.",
    "witness": "At 23:25 you saw {role} hurrying toward the {location}.",
    # A sighting is always of somebody at the observer's own place, at the time on the card.
    "confirms": "At {time} you saw {role} at the {location}.",
    "knows_secret": "You heard a rumor: {rumor}",
    # Also used for the murderer's planted clue, so that it looks like a real one.
    "herring": "A note found at the {location}: {rumor}",
}

# The four endings. Which one you get depends only on the votes (see logic._compute_result).
ENDINGS = {
    "truth": {
        "title": "The Truth Revealed",
        "text": "You named the right person and the place where Vale really died. "
                "The moved body, the locked door, the false alibi – every piece fits. Case closed.",
    },
    "incomplete": {
        "title": "The Incomplete Case",
        "text": "You caught the right person, but you could not say where it happened. "
                "A good lawyer will call it a lucky guess. The truth is only half told.",
    },
    "wrong": {
        "title": "The Wrong Accusation",
        "text": "An innocent person is led away in handcuffs, still protesting. "
                "Somewhere on campus, the real culprit lets out a slow breath.",
    },
    "escaped": {
        "title": "The Case Goes Cold",
        "text": "The room could not agree. The file is closed as 'inconclusive', "
                "and the one who did it walks out into the Carcavelos rain.",
    },
}

# Short rules, shown on the start page, the join form and in the lobby.
HOW_TO_PLAY = """Each player is one of 4 to 6 suspects. One of you killed the victim – and only that player knows.

1. **Read your card:** your role, your alibi, your secret and two clues only you know.
2. **Investigate – 3 rounds:** each round you take **one** action in the app: search a place on the campus map or share a clue. Some places are locked until a later round. Interrogations happen out loud: question each other face to face, confront each other with the evidence, defend your alibi.
3. **Discuss:** question each other in person and argue. Everybody may lie.
4. **Accuse:** vote for a suspect **and** for the place where the victim really died. Name both correctly for the full truth.
"""

# First names of the demo suspects (bots) used in presentation mode. "(demo)" is added to each.
DEMO_NAMES = ["Sofia", "Tiago", "Inês", "Rui", "Marta", "João"]

# Every text of case #001 in one place. An AI-written case (see ai.py) has exactly
# these keys, and logic.validate_story checks it before it is ever used.
# The clue TEMPLATES above stay the same for every case.
# ---------------------------------------------------------------- the evidence mini-games
#
# What the five mini-games of a case show: one piece per kind, so the five places of a case
# always have five different games. "{location}" becomes the place the puzzle seals and
# "{victim}" the victim's short name. The mechanics, the checks and the answers are code
# (minigames.py); these are only the words. An AI case brings its own (see ai.py); a piece
# it is missing, or that fails the checks (minigames.clean_content), comes from
# MINIGAME_FALLBACK, which fits every case.
#   code     the locked object; the riddle and the code follow from the case timeline
#   cipher   a note in the victim's hand; the game shifts its letters and signs it
#   scratch  the document under the coating: a note, a printout, a phone screen or a photo
#   puzzle   the caption the night camera printed on its still of the place
#   order    four entries from the victim's evening (24-hour times, none after 23:30)
CASE_MINIGAMES = {
    "code": {"exhibit": "Vale's grade cabinet",
             "story": "Vale's steel grade cabinet stands in the {location}. The final grades are inside, "
                      "and its keypad wants four digits. A note is taped to the back:"},
    "cipher": {"exhibit": "Vale's coded note",
               "story": "A folded note in Vale's handwriting, pushed under a door in the {location}. "
                        "He liked to write in shifted letters: every letter replaced by one a fixed number "
                        "of steps further along the alphabet.",
               "message": "NOBODY PASSES WITHOUT ME"},
    "scratch": {"exhibit": "Vale's phone", "style": "phone", "title": "Prof. Vale",
                "story": "Vale's cracked phone, found face down in the {location} under a film of grey dust. "
                         "Rub the screen clean.",
                "lines": ["Are you still on campus?", "The grades go out tomorrow.", "No second chances.",
                          "Don't come to my office."]},
    "puzzle": {"exhibit": "The night camera still",
               "story": "A still from the security camera in the {location}, printed and torn into {pieces} "
                        "pieces. Somebody did not want it seen. Put it back together.",
               "caption": "Motion detected"},
    "order": {"exhibit": "Vale's last evening",
              "story": "A page of Vale's diary, found in the {location}. Someone tore the entries apart. "
                       "Put his evening back in order.",
              "events": [["21:15", "Cancels his office hour by email"],
                         ["22:10", "Prints the final grade list"],
                         ["22:45", "Argues on the phone in the corridor"],
                         ["23:10", "Books the lecture hall for tomorrow"]]},
}

MINIGAME_FALLBACK = {
    "code": {"exhibit": "The locked cash box",
             "story": "A steel cash box under a desk in the {location}. Its keypad wants four digits. "
                      "A note is taped inside the drawer:"},
    "cipher": {"exhibit": "The shifted-letter note",
               "story": "A folded note slipped under a door of the {location}. The letters are shifted: "
                        "every letter replaced by one a fixed number of steps further along the alphabet.",
               "message": "DO NOT TRUST ANYONE TONIGHT"},
    "scratch": {"exhibit": "The pressed-in note", "style": "note", "title": "",
                "story": "A notepad in the {location}, covered in grey dust. Whoever wrote on it pressed hard. "
                         "Rub it clean.",
                "lines": ["{victim} -", "we need to talk.", "Tonight. Alone.", "You know where."]},
    "puzzle": {"exhibit": "The torn camera still",
               "story": "A still from the security camera in the {location}, torn into {pieces} pieces and "
                        "left in a bin. Put it back together.",
               "caption": "Motion detected"},
    "order": {"exhibit": "The victim's last evening",
              "story": "A calendar page found in the {location}, torn into strips. Put {victim}'s evening "
                       "back in order.",
              "events": [["21:00", "{victim} leaves a meeting early"],
                         ["22:05", "{victim} buys coffee from the machine"],
                         ["22:40", "{victim}'s office light goes out"],
                         ["23:15", "{victim} sends a last email"]]},
}


DEFAULT_STORY = {
    "source": "fixed",
    "case_number": CASE_NUMBER,
    "case_title": CASE_TITLE,
    "victim": VICTIM,
    "victim_short": VICTIM_SHORT,
    "found_place": FOUND_PLACE,
    "briefing": BRIEFING,
    "intro_lines": INTRO_LINES,
    "locations": LOCATIONS,
    "location_flavor": LOCATION_FLAVOR,
    "location_icons": LOCATION_ICONS,
    "neutral_location_clues": NEUTRAL_LOCATION_CLUES,
    "roles": ROLES,
    "neutral_private_clues": NEUTRAL_PRIVATE_CLUES,
    "endings": ENDINGS,
    "minigames": CASE_MINIGAMES,
}
