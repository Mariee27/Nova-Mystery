VICTIM = "Dr. Marta Quintela"
LOCATIONS = ["Library", "Grand Auditorium", "Mon Café & Açaí", "Rooftop Terrace", "Beach Access"]

LOCATION_FLAVOR = {
    "Library": "Reading lamps hum over case studies, and the silence is thick enough to cut with a highlighter.",
    "Grand Auditorium": "Velvet seats wait in the dark, and the stage still smells of last week's keynote and espresso.",
    "Mon Café & Açaí": "Espresso machines hiss, the açaí bowls are sold out, and everyone is pretending not to talk about the exam.",
    "Rooftop Terrace": "City lights shimmer over the river, and the wind carries the faint sound of a distant student party.",
    "Beach Access": "Sand, sea breeze and a weathered wooden boardwalk, where the only sounds are waves and a bicycle bell.",
}

ROLES = {
    "The TA": {
        "intro": "You are The TA. Dr. Quintela rejected your grading proposal three times this week.",
        "trace": "a red grading pen with a chewed cap",
        "secret": "You changed one grade in exchange for concert tickets.",
        "rumor": "The TA was seen slipping an envelope into the exam office mailbox.",
    },
    "The Professor": {
        "intro": "You are The Professor. Dr. Quintela chairs the committee that decides whether your exam questions survive another year.",
        "trace": "a fountain pen with a cracked gold nib",
        "secret": "You still have not read the group projects you were supposed to grade.",
        "rumor": "The Professor was seen hiding a stack of unread group projects under a coat.",
    },
    "The Librarian": {
        "intro": "You are The Librarian. Dr. Quintela has returned your overdue-fines memo unopened four times.",
        "trace": "a library card with a faded photo",
        "secret": "You have been reading the upcoming exam questions on the staff computer for weeks.",
        "rumor": "The Librarian was spotted at the staff computer long after closing time.",
    },
    "The Barista": {
        "intro": "You are The Barista. Dr. Quintela orders a flat white every evening and never once tips.",
        "trace": "a napkin with a half-drawn latte heart",
        "secret": "You have been selling extra coffee on the side and keeping the cash for yourself.",
        "rumor": "The Barista was seen counting a thick roll of cash that never reached the till.",
    },
    "The Exchange Student": {
        "intro": "You are The Exchange Student. Dr. Quintela still calls you by the wrong name at every committee meeting.",
        "trace": "a battered Lisbon metro ticket",
        "secret": "You have been pretending to follow the lectures and copying your friend's notes.",
        "rumor": "The Exchange Student was seen photocopying a stranger's lecture notes in a hurry.",
    },
    "The Students' Union President": {
        "intro": "You are The Students' Union President. Dr. Quintela has blocked the party budget you promised the whole campus.",
        "trace": "a gold lanyard with a broken clasp",
        "secret": "You have been padding the party budget with receipts from a karaoke bar.",
        "rumor": "The Students' Union President was seen shredding a suspicious stack of karaoke receipts.",
    },
}

NEUTRAL_LOCATION_CLUES = {
    "Library": "A cold cup of tea sits on a reading table, its milk skin untouched by any sip.",
    "Grand Auditorium": "A dropped microphone lies under row nine, its cable neatly coiled as if it were never used.",
    "Mon Café & Açaí": "A receipt for two sparkling waters and a granola bowl is stuck under the sugar dispenser.",
    "Rooftop Terrace": "Three chairs face the skyline, and one of them has a warm blanket folded over its back.",
    "Beach Access": "A sandcastle with a flag made from a candy wrapper stands at the gate, slightly lopsided.",
}

NEUTRAL_PRIVATE_CLUES = [
    "You noticed the campus fountain was switched off for the evening, which nobody seemed to mind.",
    "You noticed a delivery of sparkling water had gone to the wrong building and was being sorted by the porter.",
    "You noticed the sunset over the river was early and orange, and everyone stopped to take a photo.",
    "You noticed a group of students practising a dance routine in the courtyard, with laughter and no music.",
    "You noticed the elevator in the main building was out of order, so everyone took the stairs.",
    "You noticed a bicycle with a bell shaped like a duck was propped against the railing near the gate.",
    "You noticed a coffee ring covered the date of the next committee meeting on the notice board.",
    "You noticed the corridor lights flickered at 21:00 and then settled, as if nothing had happened.",
    "You noticed a stray umbrella in a corridor, dripping quietly onto a folded exam timetable.",
    "You noticed a chalk drawing of a swan on the pavement, half washed away by the evening rain.",
]

TEMPLATES = {
    "alibi": "I was at the {location} around 21:30.",
    "scene": "Found at the {location}: {trace}. It belongs to {role}.",
    "alibi_broken": "The door log of the {location} shows no entry by {role} between 21:15 and 21:45.",
    "witness": "At 21:25 you saw {role} hurrying toward the {location}.",
    "confirms": "At 21:30 you saw {role} at the {location}.",
    "knows_secret": "You heard a rumor: {rumor}",
    "herring": "A note found at the {location}: {rumor}",
    "plant": "A crumpled note at the {location} says {role} argued with the victim at 21:20.",
}
