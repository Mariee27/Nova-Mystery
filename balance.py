"""Difficulty balancing for AI-written cases. Case #001 never passes through here.

generator.build_case decides the facts of a case (who did it, where, which clue points to
whom). For an AI story, this module then tunes the case to a medium difficulty, checks it,
and writes down the complete hidden solution:

1. Two fixed adjustments (adjust):
   - at most MAX_SUSPECTED_INNOCENTS innocents carry a red herring, so the table has two or
     three plausible suspects and, with four players, somebody is clearly in the clear;
   - the crime scene opens in round 2: the revelation in the middle of the investigation,
     which makes the earlier clues read differently. The other locked place is one without a
     red herring where possible, so the misdirection is visible from round 1.
2. Checks (problems), each tagged "inconsistent", "unfair", "too easy", "too hard" or
   "too complex". A case with any problem is not played; the next seed is tried.
3. The solution file (solution): culprit, motive, method, timeline, evidence, red herrings.

Suspicion is measured with a simple, explainable model (suspicion): every clue that points at
someone adds weight, and clues that only mean something once they are combined with another
one count less while that other piece is still missing. "Medium" means: after round 1 the
culprit is not clearly ahead (START_MARGIN), with all evidence the culprit clearly is
(END_MARGIN), and at no point does a single source decide the case alone.
"""

import copy

import content
import generator

MAX_SUSPECTED_INNOCENTS = 2   # red herrings on innocents (a location note and the culprit's rumor)
SCENE_OPENS = 2               # the crime scene opens in this round: the revelation in the middle
MIN_STRONG_SOURCES = 3        # independent pieces of evidence that identify the culprit
MIN_AFTER_LOSING_ONE = 2      # ... still this many if any one source is never found or shared
MAX_START_MARGIN = 2          # after round 1 the culprit leads by at most this much (not obvious)
MIN_END_MARGIN = 3            # with all evidence the culprit leads by at least this much (solvable)
MAX_ATTEMPTS = 25
STRONG_KINDS = {"scene", "alibi_broken"}   # clue kinds that identify the culprit (see generator)

# How much a clue makes the person it points at look guilty.
WEIGHT = {
    ("place", "scene"): 3,          # their trace at the crime scene
    ("place", "alibi_broken"): 2,   # the keycard log contradicts their alibi (compare alibis!)
    ("player", "scene"): 2,         # a witness saw them heading to the place that is the scene ...
    ("place", "suspicious"): 1,     # a note with a rumor about them
    ("player", "suspicious"): 1,
}
WITNESS_WITHOUT_SCENE = 1           # ... but before the scene is found, that is only a sighting


def _rounds():
    import logic   # logic imports generator, which this module also uses
    return logic.ROUNDS


def opens_in(case, location):
    return case["locked"].get(location, 1)


def sources(case):
    """Every clue with where it comes from and from which round on it can be known.
    Private clues are known from round 1 to their owner and count once shared."""
    out = []
    for clue in case["location_clues"]:
        out.append({"source": f"place:{clue['location']}", "type": "place",
                    "round": opens_in(case, clue["location"]), "clue": clue})
    for character in case["characters"]:
        for clue in character["clues"]:
            out.append({"source": f"player:{character['pid']}", "type": "player", "round": 1, "clue": clue})
    return out


def suspicion(case, until_round):
    """{pid: how guilty they look} with every clue that can be known by that round."""
    scene_known = opens_in(case, case["murder_location"]) <= until_round
    score = {c["pid"]: 0 for c in case["characters"]}
    for item in sources(case):
        clue = item["clue"]
        if item["round"] > until_round or clue.get("implicates") is None:
            continue
        weight = WEIGHT.get((item["type"], clue["kind"]), 0)
        if (item["type"], clue["kind"]) == ("player", "scene") and not scene_known:
            weight = WITNESS_WITHOUT_SCENE
        score[clue["implicates"]] = score.get(clue["implicates"], 0) + weight
    return score


def _margin(score, culprit):
    others = [value for pid, value in score.items() if pid != culprit]
    return score[culprit] - max(others, default=0)


def analyze(case):
    """The numbers the checks are based on (also stored with the case)."""
    culprit = case["murderer"]
    strong = sorted({i["source"] for i in sources(case)
                     if i["clue"].get("implicates") == culprit and i["clue"]["kind"] in STRONG_KINDS})
    start, end = suspicion(case, 1), suspicion(case, _rounds())
    suspected = sorted({i["clue"]["implicates"] for i in sources(case)
                        if i["clue"]["kind"] == "suspicious" and i["clue"].get("implicates") not in (None, culprit)})
    visible_early = sorted({i["clue"]["implicates"] for i in sources(case)
                            if i["clue"]["kind"] == "suspicious" and i["type"] == "place" and i["round"] == 1
                            and i["clue"].get("implicates") not in (None, culprit)})
    return {
        "strong_sources": strong,
        "after_losing_one": max(len(strong) - 1, 0),   # every source counts once
        "strong_in_round_1": sorted({i["source"] for i in sources(case) if i["round"] == 1
                                     and i["clue"].get("implicates") == culprit
                                     and (i["type"], i["clue"]["kind"]) in (("place", "scene"), ("place", "alibi_broken"))}),
        "start_margin": _margin(start, culprit),
        "end_margin": _margin(end, culprit),
        "plausible_suspects_round_1": sorted(pid for pid, value in start.items() if value > 0),
        "suspected_innocents": suspected,
        "red_herrings_visible_in_round_1": visible_early,
        "scene_opens": opens_in(case, case["murder_location"]),
    }


def timeline_problems(case):
    """The facts must fit together: one place per person at 23:30, the culprit at the scene,
    every sighting and every keycard log true to those places."""
    problems = []
    culprit, scene = case["murderer"], case["murder_location"]
    by_pid = {c["pid"]: c for c in case["characters"]}
    place_of = {c["pid"]: c["true_location"] for c in case["characters"]}
    role_of = {c["pid"]: c["role"] for c in case["characters"]}
    if place_of.get(culprit) != scene:
        problems.append("inconsistent: the culprit is not at the crime scene at the time of the murder")
    for pid, character in by_pid.items():
        if pid != culprit and character["true_location"] == scene:
            problems.append(f"inconsistent: innocent player {pid} is at the crime scene")
        if pid != culprit and character["alibi_location"] != character["true_location"]:
            problems.append(f"inconsistent: innocent player {pid} lies about where they were")
    if by_pid[culprit]["alibi_location"] == scene:
        problems.append("inconsistent: the culprit's alibi is the crime scene")
    for item in sources(case):
        clue = item["clue"]
        text = clue["text"]
        if clue["kind"] == "confirms":
            seen = [pid for pid, role in role_of.items() if role in text]
            if len(seen) != 1 or seen[0] == culprit or place_of[seen[0]] not in text:
                problems.append(f"inconsistent: sighting {clue['id']} does not match where that person was")
        if clue["kind"] == "scene" and item["type"] == "player" and scene not in text:
            problems.append(f"inconsistent: witness clue {clue['id']} does not lead to the crime scene")
        if clue["kind"] == "alibi_broken" and clue["location"] != by_pid[culprit]["alibi_location"]:
            problems.append(f"inconsistent: the keycard log {clue['id']} is not at the place of the false alibi")
        if clue["kind"] == "scene" and item["type"] == "place" and clue["location"] != scene:
            problems.append(f"inconsistent: the trace {clue['id']} is not at the crime scene")
    return problems


def problems(case):
    """Everything that keeps a case from being a fair, medium-difficulty game."""
    found = timeline_problems(case)
    m = analyze(case)
    culprit = case["murderer"]
    confirmed = {pid for pid in (c["pid"] for c in case["characters"])
                 for item in sources(case) if item["clue"]["kind"] == "confirms"
                 and next(c for c in case["characters"] if c["pid"] == pid)["role"] in item["clue"]["text"]}
    if len(m["strong_sources"]) < MIN_STRONG_SOURCES:
        found.append(f"unfair: only {len(m['strong_sources'])} independent pieces of evidence identify the culprit")
    if len(m["strong_sources"]) - 1 < MIN_AFTER_LOSING_ONE:
        found.append("unfair: the case hangs on a single clue")
    if not any(s.startswith("player:") for s in m["strong_sources"]):
        found.append("unfair: no private clue helps to find the culprit, so sharing does not matter")
    for pid in m["suspected_innocents"]:
        if pid not in confirmed:
            found.append(f"unfair: the red herring on player {pid} can never be cleared up")
    if culprit in confirmed:
        found.append("inconsistent: somebody confirms the culprit's false alibi")
    if m["scene_opens"] == 1:
        found.append("too easy: the crime scene is open from the start")
    if m["start_margin"] > MAX_START_MARGIN:
        found.append("too easy: the culprit is clearly ahead after round 1")
    if len(m["plausible_suspects_round_1"]) < 2:
        found.append("too easy: only one person looks suspicious at the start")
    if not m["red_herrings_visible_in_round_1"] and len(m["suspected_innocents"]) < 2:
        found.append("too easy: no red herring is in play early")
    if m["end_margin"] < MIN_END_MARGIN:
        found.append("too hard: even with all evidence the culprit is not clearly ahead")
    if m["scene_opens"] >= _rounds():
        found.append("too hard: the crime scene opens only in the last round")
    if len(m["suspected_innocents"]) > MAX_SUSPECTED_INNOCENTS:
        found.append(f"too complex: {len(m['suspected_innocents'])} innocents carry red herrings")
    return found


def adjust(case, story):
    """The two fixed adjustments for medium difficulty (see the module text)."""
    case = copy.deepcopy(case)
    culprit = case["murderer"]
    # 1. At most MAX_SUSPECTED_INNOCENTS innocents with a red herring. The culprit's own rumor
    #    stays (it is their tool to deflect); surplus notes at places become neutral clues.
    suspected = {}
    for item in sources(case):
        clue = item["clue"]
        if clue["kind"] == "suspicious" and clue.get("implicates") not in (None, culprit):
            suspected.setdefault(clue["implicates"], []).append(item)
    surplus = len(suspected) - MAX_SUSPECTED_INNOCENTS
    for pid in sorted(suspected, key=lambda p: (any(i["type"] == "player" for i in suspected[p]), p)):
        if surplus <= 0:
            break
        places = [i for i in suspected[pid] if i["type"] == "place"]
        if len(places) == len(suspected[pid]):
            for item in places:
                clue = item["clue"]
                clue.update(text=story["neutral_location_clues"][clue["location"]], implicates=None, kind="neutral")
            surplus -= 1
    # 2. The crime scene opens in round SCENE_OPENS; the other locked place is one without a
    #    red herring where possible, and opens in the round after it.
    scene = case["murder_location"]
    others = [loc for loc in case["locked"] if loc != scene]
    neutral = [c["location"] for c in case["location_clues"] if c["kind"] == "neutral" and c["location"] != scene]
    second = others[0] if others and others[0] in neutral else (neutral[0] if neutral else (others[0] if others else None))
    case["locked"] = {scene: SCENE_OPENS}
    if second is not None:
        case["locked"][second] = min(SCENE_OPENS + 1, _rounds())
    return case


def solution(case, story):
    """The complete hidden solution, written down once the facts are fixed."""
    by_pid = {c["pid"]: c for c in case["characters"]}
    culprit = by_pid[case["murderer"]]
    scene, fake = case["murder_location"], culprit["alibi_location"]
    trace = story["roles"][culprit["role"]]["trace"]
    witness = next((c for c in case["characters"] for clue in c["clues"]
                    if clue["kind"] == "scene" and clue.get("implicates") == culprit["pid"]), None)
    timeline = [
        {"time": "23:15–23:45", "event": f"{culprit['role']} never uses a keycard at the {fake}, "
                                          f"although they will claim to have been there."},
    ]
    if witness is not None:
        timeline.append({"time": "23:25", "event": f"{witness['role']} sees {culprit['role']} hurrying "
                                                    f"toward the {scene}."})
    timeline.append({"time": content.MURDER_TIME, "event": f"{story['victim']} dies at the {scene}. "
                                                         f"{culprit['role']} is there and loses {trace}."})
    for c in case["characters"]:
        if c["pid"] != culprit["pid"]:
            timeline.append({"time": content.MURDER_TIME, "event": f"{c['role']} is at the {c['true_location']}."})
    timeline.append({"time": content.FOUND_TIME, "event": f"The body is found in {story['found_place']}."})
    herrings = []
    for item in sources(case):
        clue = item["clue"]
        if clue["kind"] == "suspicious" and clue.get("implicates") not in (None, culprit["pid"]):
            target = by_pid[clue["implicates"]]
            herrings.append({"clue": clue["id"], "points_at": target["role"],
                             "explained_by": target["secret"],
                             "cleared_by": f"{target['role']} was seen at the {target['true_location']} at "
                                           f"{content.MURDER_TIME}."})
    return {
        "culprit": culprit["pid"],
        "culprit_role": culprit["role"],
        "motive": culprit["intro"],
        "method": (f"{culprit['role']} met {story['victim_short']} at the {scene} at {content.MURDER_TIME}, "
                   f"moved the body to {story['found_place']} and claimed to have been at the {fake}."),
        "scene": scene,
        "false_alibi": fake,
        "timeline": timeline,
        "evidence": [i["clue"]["id"] for i in sources(case)
                     if i["clue"].get("implicates") == culprit["pid"] and i["clue"]["kind"] in STRONG_KINDS],
        "red_herrings": herrings,
    }


def build_balanced_case(pids, seed, story):
    """A fair, medium-difficulty case for an AI story, with its solution and its numbers.
    Tries the next seed when a case does not pass; raises logic.Rejected if none does."""
    import logic

    last = []
    for attempt in range(MAX_ATTEMPTS):
        case = adjust(generator.build_case(pids, seed + attempt, story), story)
        last = logic.validate_case(case, pids, story) + problems(case)
        if not last:
            case["balance"] = analyze(case)
            case["solution"] = solution(case, story)
            return case
    raise logic.Rejected("Could not build a balanced case: " + "; ".join(last[:3]))
