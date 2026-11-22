"""Difficulty balancing for AI-written cases.

generator.build_case decides the facts of every case, case #001 included (who did it, where,
who was where with whom, which card and which place tells what). For an AI story this module
then tunes the case to a medium difficulty, checks it, and writes down the complete hidden
solution. Case #001 is built by the generator alone and never passes through adjust().

1. Adjustment (adjust): the crime scene opens in round 2, the revelation in the middle of the
   investigation that makes earlier clues read differently; the other locked place opens in
   round 3.
2. Checks (problems), each tagged "inconsistent", "unfair", "too easy", "too hard" or
   "too complex". A case with any problem is not played; the next seed is tried.
3. The solution file (solution): culprit, motive, method, timeline, evidence, red herrings.

Suspicion is measured with a simple, explainable model (suspicion). Every clue that points at
someone adds weight; clues that only mean something once combined with another one count less
while that piece is still missing; and having no alibi counts too: whoever nobody has seen at
their place between 23:15 and 23:45 looks suspicious until a keycard log or camera clears them.
"Medium" means: after round 1 the culprit is not clearly ahead (START_MARGIN) and is never the
only one without an alibi; with all evidence the culprit clearly is ahead (END_MARGIN); and at
no point does a single source decide the case alone.
"""

import copy

import content
import generator

SCENE_OPENS = 2               # the crime scene opens in this round: the revelation in the middle
MAX_SUSPECTED_INNOCENTS = 2   # innocents a note or a rumor points at
MIN_STRONG_SOURCES = 3        # independent pieces of evidence that identify the culprit
MIN_AFTER_LOSING_ONE = 2      # ... still this many if any one source is never found or shared
MAX_START_MARGIN = 2          # after round 1 the culprit leads by at most this much (not obvious)
MIN_END_MARGIN = 3            # with all evidence the culprit leads by at least this much (solvable)
MAX_ATTEMPTS = 40
STRONG_KINDS = {"scene", "alibi_broken"}   # clue kinds that identify the culprit
WINDOW = ("23:15", "23:45")                # an alibi for the murder means: seen inside this window

# How much a clue makes the person it points at look guilty.
WEIGHT = {
    ("place", "scene"): 3,          # their trace at the crime scene
    ("place", "alibi_broken"): 2,   # the log or camera contradicts their alibi (compare alibis!)
    ("player", "scene"): 2,         # a witness saw them heading to the place that is the scene ...
    ("place", "suspicious"): 1,     # a note with a rumor about them
    ("player", "suspicious"): 1,
}
WITNESS_WITHOUT_SCENE = 1           # ... but before the scene is found, that is only a sighting
NO_ALIBI = 1                        # nobody has seen them at their place around 23:30


def _rounds():
    import logic   # logic imports this module
    return logic.ROUNDS


def opens_in(case, location):
    return case["locked"].get(location, 1)


def sources(case):
    """Every clue with where it comes from and from which round on it can be known.
    Private cards are known from round 1 to their owner and count once shared."""
    out = []
    for clue in case["location_clues"]:
        out.append({"source": f"place:{clue['location']}", "type": "place",
                    "round": opens_in(case, clue["location"]), "clue": clue})
    for character in case["characters"]:
        for clue in character["clues"]:
            out.append({"source": f"player:{character['pid']}", "type": "player", "round": 1,
                        "clue": clue, "holder": character["pid"]})
    return out


def _in_window(time):
    return time is not None and WINDOW[0] <= time <= WINDOW[1]


def alibied(case, until_round):
    """Players somebody vouches for around the murder, with what can be known by that round:
    a sighting inside the window (private card) or a log or camera of their place."""
    covered = set()
    for item in sources(case):
        clue = item["clue"]
        if item["round"] > until_round or clue["kind"] != "confirms" or "seen" not in clue:
            continue
        if item["type"] == "place" or _in_window(clue.get("time")):
            covered.add(clue["seen"])
    return covered


def suspicion(case, until_round):
    """{pid: how guilty they look} with every clue that can be known by that round."""
    scene_known = opens_in(case, case["murder_location"]) <= until_round
    covered = alibied(case, until_round)
    score = {c["pid"]: (0 if c["pid"] in covered else NO_ALIBI) for c in case["characters"]}
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


def _kinds(character):
    return tuple(sorted(clue["kind"] for clue in character["clues"]))


def analyze(case):
    """The numbers the checks are based on (also stored with the case)."""
    culprit = case["murderer"]
    items = sources(case)
    strong = sorted({i["source"] for i in items
                     if i["clue"].get("implicates") == culprit and i["clue"]["kind"] in STRONG_KINDS})
    start, end = suspicion(case, 1), suspicion(case, _rounds())
    pids = [c["pid"] for c in case["characters"]]
    suspected = sorted({i["clue"]["implicates"] for i in items
                        if i["clue"]["kind"] == "suspicious" and i["clue"].get("implicates") not in (None, culprit)})
    return {
        "strong_sources": strong,
        "after_losing_one": max(len(strong) - 1, 0),   # every source counts once
        "start_margin": _margin(start, culprit),
        "end_margin": _margin(end, culprit),
        "plausible_suspects_round_1": sorted(pid for pid, value in start.items() if value > 0),
        "no_alibi_round_1": sorted(pid for pid in pids if pid not in alibied(case, 1)),
        "no_alibi_at_the_end": sorted(pid for pid in pids if pid not in alibied(case, _rounds())),
        "suspected_innocents": suspected,
        "scene_opens": opens_in(case, case["murder_location"]),
    }


def timeline_problems(case):
    """The facts must fit together: one place per person, the culprit at the scene at 23:30,
    every sighting of somebody at the observer's own place at a possible time, every log and
    camera true to those places."""
    problems = []
    culprit, scene = case["murderer"], case["murder_location"]
    by_pid = {c["pid"]: c for c in case["characters"]}
    place_of = {c["pid"]: c["true_location"] for c in case["characters"]}
    if place_of.get(culprit) != scene:
        problems.append("inconsistent: the culprit is not at the crime scene at the time of the murder")
    for pid, character in by_pid.items():
        if pid != culprit and character["true_location"] == scene:
            problems.append(f"inconsistent: innocent player {pid} is at the crime scene")
        if pid != culprit and character["alibi_location"] != character["true_location"]:
            problems.append(f"inconsistent: innocent player {pid} lies about where they were")
    fake = by_pid[culprit]["alibi_location"]
    if fake == scene:
        problems.append("inconsistent: the culprit's alibi is the crime scene")
    if any(place_of[pid] == fake for pid in place_of if pid != culprit):
        problems.append("inconsistent: somebody spent the evening at the place of the false alibi")
    for item in sources(case):
        clue = item["clue"]
        if clue["kind"] == "confirms" and item["type"] == "player":
            observer, seen, at, time = item["holder"], clue.get("seen"), clue.get("at"), clue.get("time")
            for who in (observer, seen):
                if who == culprit:
                    if _in_window(time) or at == scene:
                        problems.append(f"inconsistent: sighting {clue['id']} puts the culprit somewhere "
                                        f"else during the murder")
                elif who not in place_of or place_of[who] != at:
                    problems.append(f"inconsistent: sighting {clue['id']} is not at the place where "
                                    f"both of them were")
        if clue["kind"] == "confirms" and item["type"] == "place":
            if place_of.get(clue.get("seen")) != clue["location"] or clue.get("seen") == culprit:
                problems.append(f"inconsistent: the log {clue['id']} vouches for somebody who was not there")
        if clue["kind"] == "scene" and item["type"] == "player" and scene not in clue["text"]:
            problems.append(f"inconsistent: witness clue {clue['id']} does not lead to the crime scene")
        if clue["kind"] == "scene" and item["type"] == "player" and item["holder"] == culprit:
            problems.append("inconsistent: the culprit is their own witness")
        if clue["kind"] == "alibi_broken" and clue["location"] != fake:
            problems.append(f"inconsistent: the log {clue['id']} is not at the place of the false alibi")
        if clue["kind"] == "scene" and item["type"] == "place" and clue["location"] != scene:
            problems.append(f"inconsistent: the trace {clue['id']} is not at the crime scene")
        if clue["kind"] == "alibi_broken" and clue["location"] in content.OPEN_AIR and "keycard" in clue["text"]:
            problems.append(f"inconsistent: {clue['location']} is open-air and has no keycard log")
    return problems


def problems(case):
    """Everything that keeps a case from being a fair, medium-difficulty game."""
    found = timeline_problems(case)
    m = analyze(case)
    culprit = case["murderer"]
    by_pid = {c["pid"]: c for c in case["characters"]}
    if len(m["strong_sources"]) < MIN_STRONG_SOURCES:
        found.append(f"unfair: only {len(m['strong_sources'])} independent pieces of evidence identify the culprit")
    if m["after_losing_one"] < MIN_AFTER_LOSING_ONE:
        found.append("unfair: the case hangs on a single clue")
    if not any(s.startswith("player:") for s in m["strong_sources"]):
        found.append("unfair: no private card helps to find the culprit, so sharing does not matter")
    for pid in m["suspected_innocents"]:
        if pid in m["no_alibi_at_the_end"]:
            found.append(f"unfair: the red herring on player {pid} can never be cleared up")
    if m["no_alibi_at_the_end"] != [culprit]:
        found.append("unfair: with all evidence, somebody innocent still has no alibi")
    # The cards must not give the culprit away by their kind, and nobody may be the only one
    # without a witness from the start.
    if not any(_kinds(c) == _kinds(by_pid[culprit]) for pid, c in by_pid.items() if pid != culprit):
        found.append("too easy: the culprit's cards are of a kind no innocent holds")
    if m["no_alibi_round_1"] == [culprit]:
        found.append("too easy: after round 1 only the culprit has no alibi")
    if m["scene_opens"] == 1:
        found.append("too easy: the crime scene is open from the start")
    if m["start_margin"] > MAX_START_MARGIN:
        found.append("too easy: the culprit is clearly ahead after round 1")
    if len(m["plausible_suspects_round_1"]) < 2:
        found.append("too easy: only one person looks suspicious at the start")
    if m["end_margin"] < MIN_END_MARGIN:
        found.append("too hard: even with all evidence the culprit is not clearly ahead")
    if m["scene_opens"] >= _rounds():
        found.append("too hard: the crime scene opens only in the last round")
    if len(m["suspected_innocents"]) > MAX_SUSPECTED_INNOCENTS:
        found.append(f"too complex: {len(m['suspected_innocents'])} innocents carry red herrings")
    return found


def adjust(case, story=None):
    """The crime scene opens in round SCENE_OPENS; the other locked place in the round after."""
    case = copy.deepcopy(case)
    scene = case["murder_location"]
    others = [loc for loc in case["locked"] if loc != scene]
    case["locked"] = {scene: SCENE_OPENS}
    for location in others:
        case["locked"][location] = min(SCENE_OPENS + 1, _rounds())
    return case


def solution(case, story):
    """The complete hidden solution, written down once the facts are fixed."""
    by_pid = {c["pid"]: c for c in case["characters"]}
    culprit = by_pid[case["murderer"]]
    scene, fake = case["murder_location"], culprit["alibi_location"]
    trace = story["roles"][culprit["role"]]["trace"]
    items = sources(case)
    witness = next((by_pid[i["holder"]] for i in items if i["type"] == "player"
                    and i["clue"]["kind"] == "scene"), None)
    early = next((i for i in items if i["type"] == "player" and i.get("holder") == culprit["pid"]
                  and i["clue"]["kind"] == "confirms"), None)
    timeline = []
    if early is not None:
        timeline.append({"time": early["clue"]["time"],
                         "event": f"{culprit['role']} passes the {early['clue']['at']} and sees "
                                  f"{by_pid[early['clue']['seen']]['role']} there."})
    timeline.append({"time": "23:15–23:45", "event": f"{culprit['role']} never enters the {fake}, "
                                                    f"although they will claim to have been there."})
    if witness is not None:
        timeline.append({"time": "23:25", "event": f"{witness['role']} sees {culprit['role']} hurrying "
                                                    f"toward the {scene}."})
    timeline.append({"time": content.MURDER_TIME, "event": f"{story['victim']} dies at the {scene}. "
                                                         f"{culprit['role']} is there and loses {trace}."})
    for place in sorted({c["true_location"] for c in case["characters"] if c["pid"] != culprit["pid"]}):
        there = [c["role"] for c in case["characters"] if c["pid"] != culprit["pid"] and c["true_location"] == place]
        timeline.append({"time": content.MURDER_TIME,
                         "event": f"{' and '.join(there)} {'is' if len(there) == 1 else 'are'} at the {place}."})
    timeline.append({"time": content.FOUND_TIME, "event": f"The body is found in {story['found_place']}."})

    def cleared(pid):
        target = by_pid[pid]
        log = next((i["clue"]["text"] for i in items if i["type"] == "place" and i["clue"]["kind"] == "confirms"
                    and i["clue"].get("seen") == pid), None)
        seen = next((i for i in items if i["type"] == "player" and i["clue"]["kind"] == "confirms"
                     and i["clue"].get("seen") == pid and _in_window(i["clue"].get("time"))), None)
        if seen is not None:
            return f"{by_pid[seen['holder']]['role']} saw them at the {target['true_location']} at {seen['clue']['time']}."
        return log or f"They were at the {target['true_location']} at {content.MURDER_TIME}."

    herrings = []
    for item in items:
        clue = item["clue"]
        if clue["kind"] == "suspicious" and clue.get("implicates") not in (None, culprit["pid"]):
            target = by_pid[clue["implicates"]]
            herrings.append({"clue": clue["id"], "points_at": target["role"],
                             "explained_by": target["secret"], "cleared_by": cleared(target["pid"])})
    for pid in analyze(case)["no_alibi_round_1"]:
        if pid != culprit["pid"] and all(h["points_at"] != by_pid[pid]["role"] for h in herrings):
            herrings.append({"clue": None, "points_at": by_pid[pid]["role"],
                             "explained_by": f"They were alone at the {by_pid[pid]['true_location']} all evening, "
                                             f"so at first nobody could confirm their alibi.",
                             "cleared_by": cleared(pid)})
    return {
        "culprit": culprit["pid"],
        "culprit_role": culprit["role"],
        "motive": culprit["intro"],
        "method": (f"{culprit['role']} met {story['victim_short']} at the {scene} at {content.MURDER_TIME}, "
                   f"moved the body to {story['found_place']} and claimed to have been at the {fake}."),
        "scene": scene,
        "false_alibi": fake,
        "timeline": timeline,
        "evidence": [i["clue"]["id"] for i in items
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
