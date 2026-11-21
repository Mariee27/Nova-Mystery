"""All story texts of NOVA MYSTERY – Case #001: The Last Lecture.

Only words live here. Who did it, where, and which clue points to whom is decided
in generator.py.

Case #001 is the fixed case: it is used for the demo, and whenever no AI-written
case is available (see ai.py). All its texts are collected in DEFAULT_STORY at the
bottom of this file; an AI-written case has exactly the same shape.
"""

GAME_TITLE = "NOVA MYSTERY"
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
    "Lisbon, Portugal.",
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
# NOVA SBE Carcavelos seen from above, north up, simplified (see ui.campus_map). It follows
# the official campus map (buildings A–I) and the satellite view: Gallery / Main Deck (I) is
# the long diagonal spine, the academic halls B, C, D and E branch off it to the west as
# parallel wings, the Hovione Atrium (A) sits at its north end by the bus stop, the Library (H)
# and Horizon Hall (G) lie east of it, the Grand Auditorium (F) at its south end towards the sea.
# The N6-7 runs along the west side with the Saba car park beyond it.
#
# Every value is percent of the map area (x of the width, y of the height), the same unit as
# the pins, so phone and board draw the same plan. The map is 1.25 times as wide as it is high.
MAP_RATIO = 1.25

# BUILDINGS: label of the official campus map -> its name, outline (polygon) and where the
# label sits. "3" is the ICA canteen (food service 3 on the official map).
BUILDINGS = {
    "A": {"name": "Hovione Atrium", "tag": (30.5, 9),
          "shape": [(24.0, 7), (38.4, 4.5), (40.8, 16), (27.2, 20)]},
    "I": {"name": "Gallery / Main Deck", "tag": (54.5, 70),
          "shape": [(37.6, 10), (46.4, 7), (59.2, 74), (50.4, 78)]},
    "B": {"name": "Cascais Academic Hall", "tag": (20.5, 30.3),
          "shape": [(40.7, 22), (18.3, 28.8), (18.3, 34.2), (40.7, 27.5)]},
    "C": {"name": "CTT Student Hall", "tag": (22.9, 43.3),
          "shape": [(43.1, 35), (20.7, 41.8), (20.7, 47.2), (43.1, 40.5)]},
    "D": {"name": "Santander Academic Hall", "tag": (25.4, 56.3),
          "shape": [(45.6, 48), (23.2, 54.8), (23.2, 60.2), (45.6, 53.5)]},
    "E": {"name": "Ming C. Hsu Executive Hall", "tag": (27.8, 69.3),
          "shape": [(48.0, 61), (25.6, 67.8), (25.6, 73.2), (48.0, 66.5)]},
    "3": {"name": "ICA Canteen", "tag": (28.6, 33.2),
          "shape": [(27.2, 32), (35.2, 30), (36.0, 35), (28.0, 37)]},
    "H": {"name": "Teresa e Alexandre Soares dos Santos Library", "tag": (54.4, 27.3),
          "shape": [(52.8, 26), (64.0, 23), (65.6, 34), (54.4, 37)]},
    "G": {"name": "Horizon Hall", "tag": (64.0, 59.3),
          "shape": [(62.4, 58), (73.6, 55), (75.2, 66), (64.0, 69)]},
    "F": {"name": "Jerónimo Martins Grand Auditorium", "tag": (49.6, 81.3),
          "shape": [(48.0, 80), (60.8, 78), (62.4, 88), (48.8, 90)]},
}

# The ground around the buildings: (css class, outline). Drawn below the buildings.
GROUNDS = [
    ("lawn", [(16.0, 20), (36.0, 16), (49.6, 79), (18.4, 82)]),      # the green slope around the wings
    ("park", [(65.6, 8), (89.6, 8), (88.8, 46), (68.8, 50)]),       # The Navigator Company Park
    ("lot", [(0.8, 46), (10.4, 44), (9.6, 86), (0.8, 90)]),          # Saba car park
    ("sand", [(64.0, 100), (100, 74), (100, 84), (77.6, 100)]),      # Carcavelos beach
    ("sea", [(77.6, 100), (100, 84), (100, 100)]),
]
# Roads as lines: (name or "", points).
ROADS = [
    ("N6-7", [(15.2, 0), (12.8, 30), (12.0, 55), (13.6, 78), (17.6, 100)]),
    ("", [(15.2, 2.5), (93.6, 2.5)]),
    ("Est. Medrosa", [(93.6, 0), (92.0, 50), (88.0, 78)]),
]

# Every case happens at 5 of these 8 places. x, y: the centre of the place's pin, in
# percent of the map. letter: what the pin shows (the building's letter on the official map).
PLACES = {
    "Library": {"letter": "H", "icon": "📚", "x": 60.8, "y": 28.5},
    "Horizon Hall": {"letter": "G", "icon": "🖥️", "x": 68.8, "y": 62},
    "Auditorium": {"letter": "F", "icon": "🎭", "x": 55.2, "y": 84},
    "Main Deck": {"letter": "I", "icon": "🌉", "x": 49.9, "y": 50},
    "ICA Canteen": {"letter": "3", "icon": "🍽️", "x": 30.4, "y": 33.8},
    "Santander Hall": {"letter": "D", "icon": "🧪", "x": 29.5, "y": 55.5},
    "Beach": {"letter": "≈", "icon": "🌊", "x": 86.4, "y": 87},
    "Parking": {"letter": "P", "icon": "🅿️", "x": 8.8, "y": 66},
}

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
    "alibi_broken": "The keycard log of the {location} shows no entry by {role} between 23:15 and 23:45.",
    "witness": "At 23:25 you saw {role} hurrying toward the {location}.",
    "confirms": "At 23:30 you saw {role} at the {location}.",
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
                "and the one who did it walks out into the Lisbon rain.",
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
}
