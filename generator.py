"""Builds a murder case from the text templates in content.py.

The code decides the facts (who did it, where, which clue points to whom).
The templates only supply the wording. The same seed and the same story always
give the same case. The story is case #001 (content.DEFAULT_STORY) unless an
AI-written story is passed in; both have the same shape.
"""

import random

import content

MAX_ATTEMPTS = 5


# When the people were seen. Sightings inside the window give an alibi for the murder (23:30).
WINDOW_TIMES = ["23:15", "23:20", "23:25", "23:35", "23:40"]
EARLY_TIME = "23:05"   # the murderer passes the lone suspect's place, before the keycard window


def _place_text(templates, kind, location):
    """Buildings have keycard readers, open-air places a night camera."""
    return templates[f"{kind}_open_air" if location in content.OPEN_AIR else kind]


def build_case(pids, seed, story=None):
    """pids: player ids in join order. Returns a case dict (see docs/CONTRACT.md).

    The night, as the code decides it:
    - The innocents spend the evening at their places, in pairs (three together if needed)
      who see each other inside the keycard window; one or two of them are alone there.
    - The murderer claims a place they never entered (the keycard log or camera shows it),
      passes the place of a lone innocent at 23:05 (they see each other), is seen hurrying
      toward the crime scene at 23:25, kills at 23:30, loses their trace there and moves
      the body.
    Every card is true and physically possible: a sighting is always of somebody at the
    observer's own place. Every player, the murderer too, holds one sighting and one more
    card (an observation, a witness account or a rumor), so the kind of card gives nobody away.
    A lone innocent has no witness at first, just like the murderer: the log or camera of
    their place, found by searching, clears them.
    """
    story = story or content.DEFAULT_STORY
    rng = random.Random(seed)
    templates = content.TEMPLATES
    roles_text = story["roles"]
    locations = list(story["locations"])

    # Who is who, who did it, and where.
    roles = rng.sample(list(roles_text), len(pids))
    role_of = dict(zip(pids, roles))
    murderer = rng.choice(pids)
    innocents = [pid for pid in pids if pid != murderer]
    murder_location = rng.choice(locations)

    others = [loc for loc in locations if loc != murder_location]
    rng.shuffle(others)
    fake_alibi_location = others[0]            # where the murderer claims to have been
    spots = others[1:]                         # where the innocents really were (3 places)

    # Groups: a pair, then a pair or a lone innocent, then whoever is left alone.
    order = list(innocents)
    rng.shuffle(order)
    size = {3: [2, 1], 4: [2, 1, 1], 5: [2, 2, 1]}[len(order)]
    groups, start = [], 0
    for count in size:
        groups.append(order[start:start + count])
        start += count
    true_location = {murderer: murder_location}
    for group, place in zip(groups, spots):
        for pid in group:
            true_location[pid] = place
    lone = [group[0] for group in groups if len(group) == 1]
    paired = [pid for group in groups if len(group) > 1 for pid in group]
    early = lone[0]                             # the murderer passes their place at 23:05
    early_place = true_location[early]

    def sighting(observer, seen, place, time):
        """A true sighting: `observer` saw `seen` at `place` (where the observer was) at `time`."""
        return {"text": templates["confirms"].format(time=time, role=role_of[seen], location=place),
                "implicates": None, "kind": "confirms", "seen": seen, "at": place, "time": time}

    witness_card = {"text": templates["witness"].format(role=role_of[murderer], location=murder_location),
                    "implicates": murderer, "kind": "scene"}

    # --- first card: a sighting for everybody (or the witness account for a second lone innocent)
    first = {}
    for group in groups:
        if len(group) > 1:
            for index, pid in enumerate(group):
                partner = group[(index + 1) % len(group)]
                first[pid] = sighting(pid, partner, true_location[pid], rng.choice(WINDOW_TIMES))
    first[early] = sighting(early, murderer, early_place, EARLY_TIME)
    first[murderer] = sighting(murderer, early, early_place, EARLY_TIME)
    witness = None
    for pid in lone[1:]:
        first[pid] = dict(witness_card)
        witness = pid

    # --- second card: the witness account (if still free), one rumor, the rest observations
    second = {}
    if witness is None:
        witness = rng.choice(paired)
        second[witness] = dict(witness_card)
    # The lone innocent whose place is locked longest is the main red herring: no witness,
    # and a rumor about them, until the log or camera of their place clears them.
    suspect = early
    rumor_holder = murderer if rng.random() < 0.5 else rng.choice([p for p in innocents if p not in second and p != suspect])
    rumors = []   # (holder, target)
    if rumor_holder == murderer:
        # The murderer's rumor must not be the only rumor card: an innocent holds one too,
        # and then no note is found at a place (two red herrings either way).
        # ... someone whose other card is a sighting too, so both rumor holders look alike.
        other_holder = rng.choice([p for p in innocents if p not in second and p != suspect
                                   and first[p]["kind"] == "confirms"])
        rumors.append((murderer, rng.choice([p for p in innocents if p != suspect])))
        rumors.append((other_holder, suspect))
        herring_target = None
    else:
        rumors.append((rumor_holder, rng.choice([p for p in innocents if p not in (rumor_holder, suspect)])))
        herring_target = suspect
    for holder, target in rumors:
        second[holder] = {"text": templates["knows_secret"].format(rumor=roles_text[role_of[target]]["rumor"]),
                          "implicates": target, "kind": "suspicious"}
    neutral_pool = rng.sample(list(story["neutral_private_clues"]), len(pids))
    for index, pid in enumerate(pids):
        second.setdefault(pid, {"text": neutral_pool[index], "implicates": None, "kind": "neutral"})

    # --- location clues: exactly one per location
    clue_at = {
        murder_location: {
            "text": templates["scene"].format(location=murder_location, trace=roles_text[role_of[murderer]]["trace"],
                                              role=role_of[murderer]),
            "implicates": murderer, "kind": "scene",
        },
        fake_alibi_location: {
            "text": _place_text(templates, "alibi_broken", fake_alibi_location).format(
                location=fake_alibi_location, role=role_of[murderer]),
            "implicates": murderer, "kind": "alibi_broken",
        },
    }
    for pid in lone:   # the log or camera of a lone innocent's place clears them
        place = true_location[pid]
        clue_at[place] = {"text": _place_text(templates, "present", place).format(location=place, role=role_of[pid]),
                          "implicates": None, "kind": "confirms", "seen": pid, "at": place}
    free = [loc for loc in spots if loc not in clue_at]
    if free and herring_target is not None:
        clue_at[free[0]] = {
            "text": templates["herring"].format(location=free[0], rumor=roles_text[role_of[herring_target]]["rumor"]),
            "implicates": herring_target, "kind": "suspicious",
        }
    for location in locations:
        if location not in clue_at:
            clue_at[location] = {"text": story["neutral_location_clues"][location], "implicates": None, "kind": "neutral"}
    location_clues = []
    for number, location in enumerate(locations, start=1):
        clue = {"id": f"L{number}", "location": location}
        clue.update(clue_at[location])
        location_clues.append(clue)

    characters = []
    for pid in pids:
        role = role_of[pid]
        claimed = fake_alibi_location if pid == murderer else true_location[pid]
        clues = []
        for letter, clue in zip("ab", (first[pid], second[pid])):
            clue = dict(clue)
            clue["id"] = f"P{pid}{letter}"
            clues.append(clue)
        rng.shuffle(clues)      # which card comes first gives nothing away either
        characters.append({
            "pid": pid,
            "role": role,
            "intro": roles_text[role]["intro"],
            "alibi_location": claimed,
            "alibi": templates["alibi"].format(location=claimed),
            "true_location": true_location[pid],
            "secret": None if pid == murderer else roles_text[role]["secret"],
            "clues": clues,
        })

    # --- rounds: two places start locked. The crime scene is always one of them; the other
    # is the place of the lone innocent who is the main red herring, so their alibi only comes
    # out later. The false alibi's place is open from round 1.
    locked_place = true_location[suspect]
    first_round, second_round = rng.sample([2, 3], 2)
    locked = {murder_location: first_round, locked_place: second_round}

    return {
        "seed": seed,
        "murderer": murderer,
        "murder_location": murder_location,
        "murder_time": content.MURDER_TIME,
        "characters": characters,
        "location_clues": location_clues,
        "locked": locked,
    }


def build_valid_case(pids, seed, story=None):
    """Build a case and check it. Try the next seed if the validator complains."""
    import logic  # imported here because logic also imports this module

    problems = []
    for attempt in range(MAX_ATTEMPTS):
        case = build_case(pids, seed + attempt, story)
        problems = logic.validate_case(case, pids, story)
        if not problems:
            return case
    raise logic.Rejected("Could not build a valid case: " + "; ".join(problems))
