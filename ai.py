"""Writes a new story for a case with an AI model, through OpenRouter.

This is the only file that talks to an AI service. It only writes words: who did
it, where, and which clue points to whom is still decided by generator.py, and
logic.validate_story checks every story before it is used. If anything goes wrong,
write_story raises AIError and the game simply plays case #001.

Why OpenRouter and not Requesty (the course's standard): Requesty rejected every
request from our account, also for its free models, with "reached its limit of
concurrent requests" – that limit is the account balance times 5, so 0 without
credit. OpenRouter's free models (ids ending in ":free") work without buying
credit: 20 requests per minute and 50 per day, and we need one per room.
OpenRouter speaks the OpenAI format, so we use the `openai` library with its address.

Settings (environment variables or .streamlit/secrets.toml, never in git):
  OPENROUTER_API_KEY   the key from openrouter.ai        (without it: no AI cases)
  OPENROUTER_MODEL     optional, a free model id         (default: DEFAULT_MODEL)
"""

import json
import logging
import random
import re
import string

import content
import logic
import minigames

BASE_URL = "https://openrouter.ai/api/v1"
# Free models are often busy ("rate-limited upstream"). OpenRouter then tries the next
# model of this list by itself, inside the same request. The first one is the fastest
# we measured (about 10 s); the others are slower but sometimes free when it is busy.
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free"
FALLBACK_MODELS = ["google/gemma-4-31b-it:free", "nvidia/nemotron-3-ultra-550b-a55b:free"]
TIMEOUT_SECONDS = 60        # per request; the lobby usually takes longer than this anyway
MAX_REQUESTS = 2            # the first try, plus one round to repair what the checks found
LOG = logging.getLogger("nova.ai")
REVISIONS = 1               # after a failed test reading, the author may revise the case once
REVIEW_SEED = 2027          # the sample case a test player reads (any fixed seed will do)
REVIEW_PLAYERS = [1, 2, 3, 4, 5]
DEFAULT_ICON = "📍"


class AIError(Exception):
    """The AI could not deliver a usable story. The message is shown to the host.

    retry: True if the AI answered but the case failed the checks; then a fresh case may well
    pass (app.write_ai_case tries once more). False if the service itself failed (no key, limit,
    busy, timeout): asking again at once would only fail again and use the quota."""

    def __init__(self, message, retry=True):
        super().__init__(message)
        self.retry = retry


SYSTEM_PROMPT = """You are the author of NOVA MYSTERY, a party murder-mystery game that 4 to 6 students
play together in one room: they question each other face to face, share clues from their phones and
accuse one of them at the end. You write the texts of one new case: a psychological thriller,
dark, creepy and believable, never gory and never supernatural.
The game itself decides later who is guilty and builds the evidence from your texts. So every
suspect needs a believable motive and must look equally suspicious: no single text may give anyone
away, and every suspicious detail needs an innocent explanation in that suspect's secret.
Answer with ONE valid JSON object and nothing else: no explanation, no markdown."""

# The rules of the game are fixed, so the prompt explains exactly which texts we need.
# Limits are listed once, in words, because models copy "[60]"-style hints into their text.
# We ask for spares (7 suspects, 6 locations) and keep the first good ones.
# Each request gets a random theme and a random first letter for the victim, otherwise the
# model writes nearly the same case every time ("Midnight ...", "Dr. Elias ...").
THEMES = [
    "the night of the annual gala dinner", "exam week, the library full until late",
    "a sudden power cut across campus", "the night before graduation", "a storm over the Tagus",
    "an alumni reunion party", "the opening of a new research centre", "a student theatre premiere",
    "a charity run that ended late", "a hackathon that went on all night",
    "a visiting delegation from abroad", "the last night of the summer festival",
]
VICTIM_LETTERS = [ch for ch in string.ascii_uppercase if ch not in "QXYZ"]


def pick_places(rng=random):
    """The 5 places of a new case: real places of the NOVA campus, so the map can show them."""
    return rng.sample(list(content.PLACES), logic.NUMBER_OF_LOCATIONS)


def user_prompt(rng=random, places=None):
    theme = rng.choice(THEMES)
    letter = rng.choice(VICTIM_LETTERS)
    places = places or pick_places(rng)
    return (USER_PROMPT.replace("<THEME>", theme).replace("<LETTER>", letter)
            .replace("<PLACES>", ", ".join(places)))


USER_PROMPT = f"""Write a brand-new case. Facts every case shares:
- At night on the NOVA SBE campus in Carcavelos, by the sea west of Lisbon, Portugal.
- The victim died at {content.MURDER_TIME} at one of the 5 places below. The body was then moved to a
  different, locked place (the "found_place") and found there at {content.FOUND_TIME}.
- Every suspect had a motive against the victim and hides a harmless but embarrassing secret
  that has nothing to do with the crime. Nothing may hint at who did it.

This case happens during <THEME>: build the victim, the suspects and the mood around it.
The 5 places of this case are fixed, real buildings and spots of the NOVA SBE campus in Carcavelos:
<PLACES>. Use exactly these names, each once.
The victim's last name starts with the letter <LETTER>.

Style: English, short clear sentences that players understand at once, no long biographies.
The mood is a psychological thriller: unsettling discoveries, tense relationships, messages that
should not exist, lights left on where nobody should be. Creepy, never gory, never supernatural.
A good case lets players suspect two or three people, argue about alibis, and in the end say:
"Now everything makes sense, we could have figured that out." Invent every name:
no real NOVA staff, students or famous people. Be original: avoid the obvious choices
(no title starting with "Midnight", no "Night Porter", no "Rooftop Garden").

Rules (the game checks them, a case that breaks one is thrown away):
1. Exactly 7 suspects with different names, and exactly the 5 places above.
2. Role names start with "The" and describe a person on campus, max 40 characters.
   No role name may contain a place name or another role name.
3. A rumor starts with the exact role name followed by " was seen " and describes something that
   looks suspicious tonight, but is really explained by that suspect's secret (for example, someone
   lies about where they were because of a secret meeting). It names no other suspect and no location.
   Max 140 characters.
4. A trace is a small object that suspect could lose, with one detail ("a brass key on a red thread").
   It names no person and no location. Max 80 characters.
5. Neutral clues and "You noticed ..." observations point at nobody: no role name, no place name,
   and never the words "was seen", "belongs to", "hurrying" or "no entry".
6. Never use the words "murderer" or "killer" in traces, rumors, secrets or clues.
7. The 6 intro lines are short like a film trailer, max 50 characters each. Line 4 is
   "<victim_short> is dead." and line 5 is exactly "4 to 6 suspects.". No role or location names.
8. Never say how many suspects there are anywhere else.
9. The mini-games are things the victim left behind tonight, in the mood of this case. Their texts
   name no suspect, no role and no other person, and never use "murder", "kill", "culprit" or "guilty".
   Every mini-game "story" contains the exact placeholder {{location}} (the game puts the place there)
   and may use {{victim}} for the victim's short name. Exhibit names max 40 characters, stories max 260.
Other maximum lengths: case_title 60, victim 40, victim_short 20, found_place 60, briefing 600,
flavor 200, neutral_clue 160, dossier 160, intro 240, secret 160, ending title 40, ending text 300.

The JSON shape (replace every description with your text):
{{
  "case_title": "short catchy title",
  "victim": "invented full name with title, e.g. Prof. or Dr.",
  "victim_short": "what people call the victim, usually the last name",
  "found_place": "place in lowercase that continues 'The body was found in ...'",
  "briefing": "3 to 5 sentences: who was found where and when, no accident, the body was moved",
  "intro_lines": ["line 1: Carcavelos or a place nearby", "line 2: a time", "line 3: a detail of the night",
                  "line 4", "4 to 6 suspects.", "line 6: a hook"],
  "locations": [
    {{"name": "one of the 5 places, written exactly as above",
      "flavor": "one atmospheric sentence about it tonight",
      "neutral_clue": "one harmless observation there"}}
  ],
  "suspects": [
    {{"role": "The ...", "dossier": "one public sentence about this person",
      "intro": "starts with 'You are <role>.' then one believable motive against the victim, in second person",
      "trace": "small object with one detail", "secret": "starts with 'You', the embarrassing secret that explains the rumor",
      "rumor": "<role> was seen ..."}}
  ],
  "neutral_private_clues": ["You noticed ...", "... 8 in total"],
  "endings": {{
    "truth": {{"title": "...", "text": "the group named the right suspect and the right place"}},
    "incomplete": {{"title": "...", "text": "right suspect, but the place was wrong or unknown"}},
    "wrong": {{"title": "...", "text": "an innocent suspect was accused"}},
    "escaped": {{"title": "...", "text": "the group could not agree, the case goes cold"}}
  }},
  "minigames": {{
    "code": {{"exhibit": "a locked object of the victim with a 4-digit keypad",
              "story": "1 or 2 sentences: the object in the {{location}}; end with a note taped to it, like 'A note is taped inside:'"}},
    "cipher": {{"exhibit": "the victim's coded note",
                "story": "where it was found in the {{location}}; say the letters are shifted along the alphabet",
                "message": "the note the victim wrote: 3 to 6 words, CAPITAL LETTERS and spaces only, max 40 characters"}},
    "scratch": {{"exhibit": "what was found under dust", "story": "where in the {{location}}, covered in dust; rub it clean",
                 "style": "one of: note, printout, phone, photo",
                 "title": "note: a heading or empty; printout: its header; phone: the contact's name; photo: a date stamp",
                 "lines": ["2 to 5 short lines that appear on it, max 30 characters each (photo: 1 or 2 lines of caption)"]}},
    "puzzle": {{"exhibit": "the torn camera still", "story": "a still of the night camera in the {{location}}, torn into {{pieces}} pieces",
                "caption": "what the camera printed on the still, max 26 characters, e.g. 'Motion detected'"}},
    "order": {{"exhibit": "the victim's last evening", "story": "a torn page about {{victim}}'s evening, found in the {{location}}",
               "events": [["21:15", "an entry of the victim's evening, max 60 characters"], ["22:05", "..."],
                          ["22:40", "..."], ["23:10", "..."]]}}
  }}
}}

The 4 "events" are in time order, at least 10 minutes apart, written as 24-hour times, and none is
later than {content.MURDER_TIME}.

Before you answer, check every rule above once more, especially rules 1, 3, 5 and 9."""


def settings(getter):
    """Read the AI settings. getter(name) returns a value or None. None means: no AI."""
    key = (getter("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return None
    model = (getter("OPENROUTER_MODEL") or "").strip() or DEFAULT_MODEL
    return {"key": key, "model": model}


def _client(api_key):
    from openai import OpenAI  # imported here so the rest of the game works without it

    return OpenAI(api_key=api_key, base_url=BASE_URL, timeout=TIMEOUT_SECONDS, max_retries=1)


def _reason(problem):
    """A short, friendly reason for the host, from the error the AI library raised."""
    name = type(problem).__name__
    message = str(problem).lower()
    if "RateLimit" in name:
        # The service answers 429 for different limits; its message says which one.
        if "upstream" in message:
            return "the free AI models are busy right now"
        if "day" in message or "daily" in message:
            return "the daily AI limit is reached"
        return "the AI service has too many requests right now"
    if "Timeout" in name:
        return "the AI did not answer in time"
    if "Authentication" in name or "PermissionDenied" in name:
        return "the AI key was not accepted"
    if "NotFound" in name:
        return "the AI model is not available"
    return "the AI service did not answer"


def write_story(api_key, model=DEFAULT_MODEL, client=None):
    """Ask the AI for a new story. Returns a story dict, or raises AIError.

    Free models often make a small slip (an intro line too long, five suspects
    instead of six). Then the model gets the list of problems from
    logic.validate_story and one chance to repair its answer. Whatever comes back
    last is returned; logic.ai_case_ready checks it again before it is played.

    client is only passed in by the tests (a fake that never goes online).
    """
    client = client or _client(api_key)
    places = pick_places()
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt(places=places)}]
    story, text, problems = None, None, []
    for _ in range(MAX_REQUESTS):
        text = _ask(client, model, messages)
        story, problems = _read(text, places)
        if not problems:
            break
        messages += [
            {"role": "assistant", "content": text or ""},
            {"role": "user", "content": "Your answer has these problems:\n- " + "\n- ".join(problems[:10])
             + "\nFix them and answer again with the complete JSON object only."},
        ]
    if story is None:
        raise AIError("the AI answer was not readable")
    if problems:
        return story   # still has problems: ai_case_ready will refuse it and case #001 is played

    # A test player reads a sample case built from the story, without knowing the solution.
    # Its findings go back to the author for one revision. The test player is a free model
    # too and often misreads a case, so its verdict improves a case but never throws one away:
    # the code checks (logic.validate_story, and balance building a fair case for every number
    # of players) decide. Only a story from which no fair case can be built is refused.
    for revision in range(REVISIONS + 1):
        verdict = review_story(client, model, story)
        if not verdict["available"] or verdict["ok"]:
            return story   # the test reading passed, or could not be done: the checks suffice
        if revision == REVISIONS:
            if verdict.get("kind") == "balance":
                raise AIError("no fair case could be built from the AI's texts")
            LOG.warning("AI case played although the test reading found: %s", "; ".join(verdict["problems"][:8]))
            return story
        messages += [
            {"role": "assistant", "content": text or ""},
            {"role": "user", "content": REVISION_REQUEST.replace("<FINDINGS>", "\n- ".join(verdict["problems"][:8]))},
        ]
        text = _ask(client, model, messages)
        story, problems = _read(text, places)
        if story is None or problems:
            raise AIError("the revised AI case broke the rules")
    return story


def _read(text, places):
    """(story or None, problems) for an answer of the author."""
    try:
        story = parse_story(text, places)
    except AIError:
        return None, ["The answer was not one valid JSON object of the requested shape."]
    return story, logic.validate_story(story)


# ---------------------------------------------------------------- the test reading
#
# The structure of every case (one culprit, three independent pieces of evidence, red
# herrings that can be cleared, the revelation in round 2) is guaranteed by code: see
# balance.py. What code cannot judge are the texts: a trace that gives someone away, a rumor
# that sounds like a confession, a motive nobody believes, a sentence nobody understands.
# So a second request plays the case like a player: it reads a sample case round by round,
# WITHOUT the solution, and says whom it suspects when. The verdict comes from code
# (judge), from what the test player answered, never from a score alone.

REVIEW_SYSTEM_PROMPT = """You test-play murder-mystery cases for a party game before real players get them.
You are a sharp but ordinary player: you only know what the players can know, never the solution.
Read the case file round by round and say honestly what you would think at each point.
Answer with ONE valid JSON object and nothing else: no explanation, no markdown."""

REVIEW_QUESTION = """Read this case file as a player. Then answer with this JSON object:
{
  "after_round_1": {"top_suspect": "<exact role name>", "confidence": <1 to 5>,
                    "plausible_suspects": ["<exact role names you would still consider>"]},
  "after_all_rounds": {"culprit": "<exact role name>", "confidence": <1 to 5>,
                       "key_reasoning": "<one sentence: which clues, combined, show it>"},
  "needs_unreasonable_leap": <true if the solution needs a guess or knowledge players cannot have>,
  "red_herrings_have_innocent_explanations": <true if every suspicious detail about an innocent-looking
                                              person is explained by what they admit>,
  "clarity": <1 to 5: are the texts easy to understand at a glance>,
  "suspense": <1 to 5: is it eerie and exciting>,
  "problems": ["<short, concrete problems with the TEXTS, e.g. a clue that gives someone away at once,
                a rumor that sounds like a confession, a confusing sentence; at most 5>"]
}
Confidence: 1 = pure guess, 3 = likely, 5 = certain.

CASE FILE
"""

REVISION_REQUEST = """A test player read a case built from your texts, without knowing the solution, and found:
- <FINDINGS>
Revise your texts so that the case is suspenseful but fair: several suspects look guilty at first,
every suspicious detail of an innocent person is explained by their secret, nothing gives anyone
away on its own, and every sentence is easy to understand. Keep every rule of the first request.
Answer again with the complete JSON object only."""


def player_file(story, case):
    """What the players of a sample case can know, round by round. Never the solution: no
    culprit, no true locations, and every suspect's secret is listed (in a game the culprit
    has none, which would give them away here)."""
    import logic as rules

    lines = [f"Title: {story['case_title']}", f"Briefing: {story['briefing']}", "",
             "Suspects (role - public dossier - where they say they were at 23:30):"]
    for c in case["characters"]:
        lines.append(f"- {c['role']} - {story['roles'][c['role']]['dossier']} - \"{c['alibi']}\"")
    lines += ["", "Private cards (each suspect holds their own two and may share them at the table):"]
    for c in case["characters"]:
        lines.append(f"- {c['role']}: " + " | ".join(clue["text"] for clue in c["clues"]))
    lines += ["", "What each suspect admits when pressed hard:"]
    for c in case["characters"]:
        lines.append(f"- {c['role']}: {story['roles'][c['role']]['secret']}")
    for number in range(1, rules.ROUNDS + 1):
        opened = [clue for clue in case["location_clues"] if case["locked"].get(clue["location"], 1) == number]
        lines += ["", f"Round {number}: places that can be searched from now on:"]
        lines += [f"- {clue['location']}: {clue['text']}" for clue in opened] or ["- (none)"]
    return "\n".join(lines)


def review_story(client, model, story):
    """{"available": bool, "ok": bool, "problems": [str], "answer": dict | None}"""
    import balance
    import logic as rules

    try:
        # Every player count must give a balanced case; the test player reads the 5-player one.
        for count in range(rules.MIN_PLAYERS, rules.MAX_PLAYERS + 1):
            balance.build_balanced_case(list(range(1, count + 1)), REVIEW_SEED, story)
        case = balance.build_balanced_case(REVIEW_PLAYERS, REVIEW_SEED, story)
    except rules.Rejected as problem:
        return {"available": True, "ok": False, "problems": [str(problem)], "answer": None, "kind": "balance"}
    messages = [{"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": REVIEW_QUESTION + player_file(story, case)}]
    try:
        answer = _json_object(_ask(client, model, messages, temperature=0.2))
    except AIError:
        return {"available": False, "ok": False, "problems": [], "answer": None}
    culprit_role = next(c["role"] for c in case["characters"] if c["pid"] == case["murderer"])
    problems = judge(answer, culprit_role, [c["role"] for c in case["characters"]])
    if problems is None:
        return {"available": False, "ok": False, "problems": [], "answer": answer}
    return {"available": True, "ok": not problems, "problems": problems, "answer": answer, "kind": "reader"}


def judge(answer, culprit_role, roles):
    """What the test player's answer says about the case. [] means: medium and fair.
    None means the answer cannot be used (then only the code checks count).
    The findings never name the culprit: they go back to the author."""
    def role(value):
        value = str(value or "").strip().casefold()
        return next((r for r in roles if r.casefold() == value), None)

    def number(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5 else None

    try:
        start, end = answer["after_round_1"], answer["after_all_rounds"]
        top, sure_start = role(start["top_suspect"]), number(start["confidence"])
        named, sure_end = role(end["culprit"]), number(end["confidence"])
        plausible = {role(r) for r in start.get("plausible_suspects", [])} - {None}
        leap = answer["needs_unreasonable_leap"]
        explained = answer["red_herrings_have_innocent_explanations"]
        clarity, suspense = number(answer["clarity"]), number(answer["suspense"])
    except (KeyError, TypeError, AttributeError):
        return None
    if None in (sure_start, sure_end, clarity, suspense) or not isinstance(leap, bool) or not isinstance(explained, bool):
        return None
    problems = []
    if named != culprit_role:
        problems.append("too hard: even with all evidence the test player accused the wrong person")
    elif sure_end < 3:
        problems.append("too hard: with all evidence the test player was still unsure")
    if top == culprit_role and sure_start >= 4:
        problems.append("too easy: the test player was already sure after round 1")
    if len(plausible) < 2:
        problems.append("too easy: only one person looked suspicious at the start")
    if leap:
        problems.append("too hard: solving the case needs a guess or knowledge players cannot have")
    if not explained:
        problems.append("unfair: a suspicious detail about an innocent person has no innocent explanation in their secret")
    if clarity < 3:
        problems.append("unclear: some texts are hard to understand")
    if suspense < 3:
        problems.append("dull: the case is not eerie or exciting enough")
    if problems:
        notes = answer.get("problems") if isinstance(answer.get("problems"), list) else []
        problems += [str(note)[:200] for note in notes[:5] if str(note).strip()]
    return problems


def _json_object(text):
    if not isinstance(text, str):
        raise AIError("the AI answer was empty")
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start:end + 1]) if 0 <= start < end else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise AIError("the AI answer was not readable")
    return data


def _ask(client, model, messages, temperature=1.0):
    """One request. Returns the answer text, or raises AIError.
    temperature 1.0 (the author): a little randomness, every room gets a different case;
    lower for the test reading, which should judge steadily."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            # OpenRouter only: try these models if the first one is busy, and do not let
            # "thinking" models think for minutes (we need the case while people join).
            extra_body={"models": [model] + [m for m in FALLBACK_MODELS if m != model],
                        "reasoning": {"enabled": False}},
        )
        return response.choices[0].message.content
    except Exception as problem:   # any network or service error: play case #001
        raise AIError(_reason(problem), retry=False) from problem


def parse_story(text, places=None):
    """Turn the AI's answer (JSON text) into a story dict like content.DEFAULT_STORY.

    places: the 5 campus places the AI was asked to write about. Without them (tests),
    the places are taken from the answer itself."""
    if not isinstance(text, str):
        raise AIError("the AI answer was empty")
    # Models sometimes wrap the JSON in ```json ... ``` or add a sentence: keep the {...} part.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise AIError("the AI answer was not readable")
    try:
        data = json.loads(text[start:end + 1])
        story = _tidy(_to_story(data, places))
    except (ValueError, TypeError, KeyError, AttributeError) as problem:
        raise AIError("the AI answer was not readable") from problem
    return story


LENGTH_HINT = re.compile(r"\s*\[\d+(?: each)?\]")   # "[60]" from our request, copied by mistake


def _clean(value):
    """One line, no double spaces, and no length hints like "[60]" copied from the request."""
    return " ".join(LENGTH_HINT.sub("", str(value)).split())


PLAIN_LOCATION_CLUE = "Nothing unusual here tonight."
# Phrases the demo suspects read as evidence (logic.EVIDENCE_PHRASES), with milder words.
MILDER_PHRASES = (("hurrying", "rushing"), ("belongs to", "is owned by"),
                  ("no entry by", "no sign of"), ("was seen", "was noticed"))


def _tidy(story):
    """Fix small slips that need no new case, so one weak sentence does not cost the story.

    A neutral clue must point at nobody. One that names a suspect or a place, or uses a
    phrase the demo suspects read as evidence, is dropped (private clues: we ask for 8
    and need 6) or replaced by a plain sentence (one clue per location is needed).
    """
    names = [name.casefold() for name in list(story["locations"]) + list(story["roles"])]

    def points_at_somebody(text):
        low = text.casefold()
        return any(name in low for name in names) or any(p in low for p in logic.EVIDENCE_PHRASES)

    def neutral(text):
        """Take every suspect and every place out of a neutral clue."""
        for role in story["roles"]:
            text = re.sub(re.escape(role), "someone", text, flags=re.IGNORECASE)
        for location in story["locations"]:
            text = re.sub(r"(the )?" + re.escape(location), "a nearby building", text, flags=re.IGNORECASE)
        for phrase, milder in MILDER_PHRASES:
            text = re.sub(phrase, milder, text, flags=re.IGNORECASE)
        return text

    clues = [neutral(clue) for clue in story["neutral_private_clues"]]
    good = [clue for clue in clues if not points_at_somebody(clue)]
    story["neutral_private_clues"] = good if len(good) >= logic.MAX_PLAYERS else clues
    for location, clue in story["neutral_location_clues"].items():
        clue = neutral(clue)
        story["neutral_location_clues"][location] = (PLAIN_LOCATION_CLUE if points_at_somebody(clue)
                                                     else clue)
    # A trace becomes "Found at the <place>: <trace>. Whose could it be?" and stands in the dossiers – it may name nobody.
    for texts in story["roles"].values():
        texts["trace"] = neutral(texts["trace"])

    # A rumor may only point at its own suspect: other suspects become "someone", and the
    # phrases the demo suspects read as hard evidence are replaced by milder words.
    for role, texts in story["roles"].items():
        rumor = texts["rumor"]
        head, rest = rumor[:len(role)], rumor[len(role):]
        for other in story["roles"]:
            if other != role:
                rest = re.sub(re.escape(other), "someone", rest, flags=re.IGNORECASE)
        for phrase, milder in MILDER_PHRASES[:3]:   # "was seen" itself stays in a rumor
            rest = re.sub(phrase, milder, rest, flags=re.IGNORECASE)
        texts["rumor"] = head + rest

    # "the murderer"/"the killer" in a text that becomes a clue would give the solution away:
    # it becomes "someone". Endings and the briefing may name the crime (never a clue).
    story["neutral_private_clues"] = [_no_verdict(c) for c in story["neutral_private_clues"]]
    for location, clue in story["neutral_location_clues"].items():
        story["neutral_location_clues"][location] = _no_verdict(clue)
    for role, texts in story["roles"].items():
        texts["trace"] = _no_verdict(texts["trace"])
        texts["rumor"] = texts["rumor"][:len(role)] + _no_verdict(texts["rumor"][len(role):])

    _shorten_all(story)

    # The intro is only decoration: if its lines do not fit, use a standard one for this victim.
    lines = story["intro_lines"]
    if (len(lines) != logic.NUMBER_OF_INTRO_LINES
            or any(len(line) > logic.STORY_LIMITS["intro_line"] or points_at_somebody(line)
                   for line in lines)):
        story["intro_lines"] = standard_intro(story["victim"])
    return story


VERDICT_WORDS = re.compile(r"\b(?:(?:the|a|an)\s+)?(?:murderer|killer)\w*", re.IGNORECASE)


def _no_verdict(text):
    """'the killer left a glove' -> 'someone left a glove' (capitalised at the start)."""
    def someone(match):
        return "Someone" if match.group(0)[:1].isupper() and match.start() == 0 else "someone"
    return VERDICT_WORDS.sub(someone, text)


SENTENCE_END = re.compile(r"[.!?…][\"”’)]?(?=\s|$)")
# Words a cut phrase must not end on ("a silver pen with the" -> "a silver pen").
LOOSE_ENDS = {"a", "an", "the", "of", "with", "and", "or", "in", "on", "at", "to", "from", "for",
              "by", "that", "which", "its", "his", "her", "their", "under", "near", "into"}


def _shorten(text, limit, phrase=False):
    """Make a text that is too long fit its limit instead of refusing the whole case.

    A text is cut after its last full sentence that fits (if that keeps at least half);
    otherwise at a word, with "…". phrase=True (a trace, used inside a sentence: "... and
    loses <trace>."): cut at a word, without "…" and without a dangling "the"/"with"."""
    if len(text) <= limit:
        return text
    if not phrase:
        ends = [m.end() for m in SENTENCE_END.finditer(text[:limit])]
        if ends and ends[-1] >= limit // 2:
            return text[:ends[-1]].strip()
        limit -= 1                                       # room for the "…"
    words = text[:limit + 1].split(" ")[:-1] or [text[:limit]]   # whole words only
    while len(words) > 1 and words[-1].lower().strip(",;:–-") in LOOSE_ENDS:
        words.pop()
    cut = " ".join(words).rstrip(" ,;:–-")[:limit]
    return cut if phrase else cut + "…"


def _shorten_all(story):
    """Apply _shorten to every text with a length limit except the names (a name that is
    cut could clash with another one). Runs last, after the other fixes."""
    limits = logic.STORY_LIMITS
    for key in ("case_title", "found_place", "briefing"):
        story[key] = _shorten(story[key], limits[key])
    for location in story["locations"]:
        story["location_flavor"][location] = _shorten(story["location_flavor"][location], limits["flavor"])
        story["neutral_location_clues"][location] = _shorten(story["neutral_location_clues"][location],
                                                             limits["neutral_clue"])
    story["neutral_private_clues"] = [_shorten(c, limits["neutral_clue"]) for c in story["neutral_private_clues"]]
    for texts in story["roles"].values():
        for field in ("dossier", "intro", "secret", "rumor"):
            texts[field] = _shorten(texts[field], limits[field])
        texts["trace"] = _shorten(texts["trace"], limits["trace"], phrase=True)
    for ending in story["endings"].values():
        ending["title"] = _shorten(ending["title"], limits["ending_title"])
        ending["text"] = _shorten(ending["text"], limits["ending_text"])


def standard_intro(victim):
    return ["Carcavelos, Portugal.", "23:47.", "NOVA University.", f"{victim} is dead.",
            "4 to 6 suspects.", "One of them is lying."]


def _rumor(role, text):
    """Bring a rumor into the fixed form '<role> was seen ...'.

    Models often write 'Rumor has it the night chef was seen ...' or 'Seen ...'. The
    clues and the demo suspects need the exact form, so the code fixes it, not the AI.
    """
    text = _clean(text)
    seen = text.lower().find("was seen ")
    if seen != -1:
        return f"{role} was seen {text[seen + len('was seen '):]}"
    if text.lower().startswith("seen "):
        return f"{role} was seen {text[len('seen '):]}"
    return text   # no 'was seen' at all: validate_story will refuse it


def _place_name(value):
    """'the physics lab' -> 'Physics lab': the clue sentences add 'the' themselves."""
    name = _clean(value)
    if name.lower().startswith("the "):
        name = name[4:]
    return name[:1].upper() + name[1:]


def _first_unique(items, name_of, count):
    """The first `count` items whose names are all different (we asked for spares)."""
    seen, kept = set(), []
    for item in items:
        name = name_of(item).casefold()
        if name and name not in seen:
            seen.add(name)
            kept.append(item)
    return kept[:count]


GENERIC_ENDINGS = {   # used when the AI forgot the endings: they fit every case
    "truth": {"title": "The Truth Revealed",
              "text": "You named the right person and the right place. Every piece fits. Case closed."},
    "incomplete": {"title": "The Incomplete Case",
                   "text": "You caught the right person, but not where it happened. Half the truth."},
    "wrong": {"title": "The Wrong Accusation",
              "text": "An innocent is led away, and the real culprit lets out a slow breath."},
    "escaped": {"title": "The Case Goes Cold",
                "text": "The room could not agree. The file is closed, and the culprit walks free."},
}


def _endings(data):
    endings = data.get("endings") if isinstance(data.get("endings"), dict) else {}
    result = {}
    for key in logic.ENDING_KEYS:
        ending = endings.get(key) if isinstance(endings.get(key), dict) else {}
        title, text = _clean(ending.get("title", "")), _clean(ending.get("text", ""))
        result[key] = {"title": title, "text": text} if title and text else dict(GENERIC_ENDINGS[key])
    return result


def _place_key(name):
    return _clean(name).casefold().removeprefix("the ")


def _campus_name(name):
    """The official spelling of a campus place ('the library' -> 'Library'), else the name tidied."""
    known = {_place_key(place): place for place in content.PLACES}
    return known.get(_place_key(name), _place_name(name))


def _match_places(entries, places):
    """The AI's texts for each place, in the order of `places`. A place is found by its name;
    an entry with an unknown name fills the next free place (models sometimes shorten names)."""
    entries = [entry for entry in entries if isinstance(entry, dict)]
    if places is None:   # no places given: take them from the answer
        places = [_campus_name(e["name"]) for e in
                  _first_unique(entries, lambda e: _campus_name(e["name"]), logic.NUMBER_OF_LOCATIONS)]
    wanted = {_place_key(place) for place in places}
    by_name = {_place_key(e.get("name", "")): e for e in entries}
    leftovers = [e for e in entries if _place_key(e.get("name", "")) not in wanted]
    matched = []
    for place in places:
        entry = by_name.get(_place_key(place)) or (leftovers.pop(0) if leftovers else None)
        if entry is None:
            raise KeyError(place)
        matched.append(entry)
    return list(places), matched


def _to_story(data, places=None):
    names, locations = _match_places(data["locations"], places)
    suspects = _first_unique(data["suspects"], lambda s: _clean(s["role"]), logic.NUMBER_OF_ROLES)
    story = {
        "source": "ai",
        "case_number": "AI",   # replaced by the room code in logic.ai_case_ready
        "case_title": _clean(data["case_title"]),
        "victim": _clean(data["victim"]),
        "victim_short": _clean(data["victim_short"]),
        "found_place": _clean(data["found_place"]),
        "briefing": _clean(data["briefing"]),
        "intro_lines": [_clean(line) for line in data["intro_lines"]],
        "locations": names,
        "location_flavor": {name: _clean(loc["flavor"]) for name, loc in zip(names, locations)},
        "location_icons": {name: content.PLACES.get(name, {}).get("icon", DEFAULT_ICON) for name in names},
        "neutral_location_clues": {name: _clean(loc["neutral_clue"])
                                   for name, loc in zip(names, locations)},
        "roles": {
            _clean(s["role"]): {
                "dossier": _clean(s["dossier"]),
                "intro": _clean(s["intro"]),
                "trace": _clean(s["trace"]),
                "secret": _clean(s["secret"]),
                "rumor": _rumor(_clean(s["role"]), s["rumor"]),
            }
            for s in suspects
        },
        "neutral_private_clues": [_clean(c) for c in data["neutral_private_clues"]],
        "endings": _endings(data),
    }
    # The words of the five mini-games: only pieces that pass the checks are kept, a missing
    # piece is filled in by the game (content.MINIGAME_FALLBACK). A weak piece never costs the case.
    story["minigames"] = minigames.clean_content(data.get("minigames"), story)
    return story
