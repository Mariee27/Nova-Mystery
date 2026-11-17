"""Builds a murder case from the text templates in content.py.

The code decides the facts (who did it, where, which clue points to whom).
The templates only supply the wording. The same seed and the same story always
give the same case. The story is case #001 (content.DEFAULT_STORY) unless an
AI-written story is passed in; both have the same shape.
"""

import random

import content

MAX_ATTEMPTS = 5


def build_case(pids, seed, story=None):
    """pids: player ids in join order. Returns a case dict (see docs/CONTRACT.md)."""
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

    other_locations = [loc for loc in locations if loc != murder_location]
    rng.shuffle(other_locations)
    fake_alibi_location = other_locations[0]   # where the murderer claims to have been
    innocent_locations = other_locations[1:]   # where the innocents really were

    true_location = {murderer: murder_location}
    for index, pid in enumerate(innocents):
        true_location[pid] = innocent_locations[index % len(innocent_locations)]

    # Two innocents get a red herring at a location. One more is known to the murderer.
    herring_targets = rng.sample(innocents, 2)
    free_innocents = [pid for pid in innocents if pid not in herring_targets]
    rumor_target = rng.choice(free_innocents)

    # --- location clues: exactly one per location
    clue_at = {
        murder_location: {
            "text": templates["scene"].format(
                location=murder_location,
                trace=roles_text[role_of[murderer]]["trace"],
                role=role_of[murderer]),
            "implicates": murderer, "kind": "scene",
        },
        fake_alibi_location: {
            "text": templates["alibi_broken"].format(
                location=fake_alibi_location, role=role_of[murderer]),
            "implicates": murderer, "kind": "alibi_broken",
        },
    }
    for location, target in zip(innocent_locations, herring_targets):
        clue_at[location] = {
            "text": templates["herring"].format(
                location=location, rumor=roles_text[role_of[target]]["rumor"]),
            "implicates": target, "kind": "suspicious",
        }
    for location in locations:
        if location not in clue_at:
            clue_at[location] = {
                "text": story["neutral_location_clues"][location],
                "implicates": None, "kind": "neutral",
            }
    location_clues = []
    for number, location in enumerate(locations, start=1):
        clue = {"id": f"L{number}", "location": location}
        clue.update(clue_at[location])
        location_clues.append(clue)

    # --- private clues: exactly two per player
    neutral_pool = rng.sample(list(story["neutral_private_clues"]), len(pids))
    witness = rng.choice(innocents)
    private = {}
    for index, pid in enumerate(innocents):
        seen = innocents[(index + 1) % len(innocents)]   # each innocent confirms the next one
        confirms = {
            "text": templates["confirms"].format(role=role_of[seen], location=true_location[seen]),
            "implicates": None, "kind": "confirms",
        }
        if pid == witness:
            first = {
                "text": templates["witness"].format(
                    role=role_of[murderer], location=murder_location),
                "implicates": murderer, "kind": "scene",
            }
            private[pid] = [first, confirms]
        else:
            private[pid] = [confirms,
                            {"text": neutral_pool[index], "implicates": None, "kind": "neutral"}]
    private[murderer] = [
        {
            "text": templates["knows_secret"].format(
                rumor=roles_text[role_of[rumor_target]]["rumor"]),
            "implicates": rumor_target, "kind": "suspicious",
        },
        {"text": neutral_pool[-1], "implicates": None, "kind": "neutral"},
    ]

    characters = []
    for pid in pids:
        role = role_of[pid]
        claimed = fake_alibi_location if pid == murderer else true_location[pid]
        clues = []
        for letter, clue in zip("ab", private[pid]):
            clue = dict(clue)
            clue["id"] = f"P{pid}{letter}"
            clues.append(clue)
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

    return {
        "seed": seed,
        "murderer": murderer,
        "murder_location": murder_location,
        "murder_time": content.MURDER_TIME,
        "characters": characters,
        "location_clues": location_clues,
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
