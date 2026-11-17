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

LOCATIONS = ["Research Laboratory", "Main Library", "Server Room", "Underground Archive", "Security Office"]

LOCATION_FLAVOR = {
    "Research Laboratory": "Centrifuges tick as they cool down. A whiteboard still shows Vale's handwriting, half wiped away.",
    "Main Library": "Green reading lamps glow over empty desks. Somewhere between the shelves, a radiator knocks like a slow heartbeat.",
    "Server Room": "Cold air, blinking lights and the hum of forty machines. One rack door is open that should be locked.",
    "Underground Archive": "Concrete stairs lead down to rows of grey boxes. The air smells of dust, paper and old secrets.",
    "Security Office": "Twelve camera screens, two of them black. A cold coffee sits next to tonight's patrol log.",
}

LOCATION_ICONS = {
    "Research Laboratory": "🧪",
    "Main Library": "📚",
    "Server Room": "🖥️",
    "Underground Archive": "🗄️",
    "Security Office": "📹",
}

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
        "dossier": "Keeps the Main Library and the Underground Archive open after midnight.",
        "intro": "You are The Night Librarian. Vale wanted the archive closed and your night shifts cut. "
                 "Without them you cannot pay your rent.",
        "trace": "a brass archive key on a red thread",
        "secret": "Every night you let a homeless student sleep in the reading room after closing.",
        "rumor": "The Night Librarian was seen carrying a blanket and a pillow into the reading room after closing.",
    },
    "The Security Guard": {
        "dossier": "Night guard of the research building. Found the body at 23:47 and raised the alarm.",
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
    "Research Laboratory": "A rack of test tubes stands in perfect order. The fridge log shows nothing unusual tonight.",
    "Main Library": "A returned book about Lisbon trams lies on the counter. Its due date was three weeks ago.",
    "Server Room": "A backup job finished at 22:00 as planned. The status lights are all green.",
    "Underground Archive": "Dust lies evenly on the boxes of row C. Nobody has touched them for months.",
    "Security Office": "The lost-and-found box holds two umbrellas, one glove and a forgotten student card.",
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
2. **Investigate:** take **one** action: search a location, interrogate someone (you may confront them with evidence), or share a clue.
3. **Discuss:** answer questions and argue. Everybody may lie.
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
