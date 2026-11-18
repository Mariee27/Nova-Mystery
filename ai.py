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
import random
import re
import string

import content
import logic

BASE_URL = "https://openrouter.ai/api/v1"
# Free models are often busy ("rate-limited upstream"). OpenRouter then tries the next
# model of this list by itself, inside the same request. The first one is the fastest
# we measured (about 10 s); the others are slower but sometimes free when it is busy.
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free"
FALLBACK_MODELS = ["google/gemma-4-31b-it:free", "nvidia/nemotron-3-ultra-550b-a55b:free"]
TIMEOUT_SECONDS = 60        # per request; the lobby usually takes longer than this anyway
MAX_REQUESTS = 2            # the first try, plus one round to repair what the checks found
DEFAULT_ICON = "📍"


class AIError(Exception):
    """The AI could not deliver a usable story. The message is shown to the host."""


SYSTEM_PROMPT = """You are the author of NOVA MYSTERY, a party murder-mystery game that 4 to 6 friends
play in 5 minutes on their phones. You write the texts of one new case. The game itself decides
later who is guilty, so you write every suspect as equally suspicious.
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
- At night on the campus of NOVA University in Lisbon, Portugal.
- The victim died at {content.MURDER_TIME} at one of the 5 places below. The body was then moved to a
  different, locked place (the "found_place") and found there at {content.FOUND_TIME}.
- Every suspect had a motive against the victim and hides a harmless but embarrassing secret
  that has nothing to do with the crime. Nothing may hint at who did it.

This case happens during <THEME>: build the victim, the suspects and the mood around it.
The 5 places of this case are fixed, real buildings and spots of the NOVA SBE campus in Carcavelos:
<PLACES>. Use exactly these names, each once.
The victim's last name starts with the letter <LETTER>.

Style: English, atmospheric, short sentences, a little dark humour is welcome. Invent every name:
no real NOVA staff, students or famous people. Be original: avoid the obvious choices
(no title starting with "Midnight", no "Night Porter", no "Rooftop Garden").

Rules (the game checks them, a case that breaks one is thrown away):
1. Exactly 7 suspects with different names, and exactly the 5 places above.
2. Role names start with "The" and describe a person on campus, max 40 characters.
   No role name may contain a place name or another role name.
3. A rumor starts with the exact role name followed by " was seen " and hints at that suspect's secret.
   It names no other suspect and no location. Max 140 characters.
4. A trace is a small object that suspect could lose, with one detail ("a brass key on a red thread").
   It names no person and no location. Max 80 characters.
5. Neutral clues and "You noticed ..." observations point at nobody: no role name, no place name,
   and never the words "was seen", "belongs to", "hurrying" or "no entry".
6. Never use the words "murderer" or "killer" in traces, rumors, secrets or clues.
7. The 6 intro lines are short like a film trailer, max 50 characters each. Line 4 is
   "<victim_short> is dead." and line 5 is exactly "4 to 6 suspects.". No role or location names.
8. Never say how many suspects there are anywhere else.
Other maximum lengths: case_title 60, victim 40, victim_short 20, found_place 60, briefing 600,
flavor 200, neutral_clue 160, dossier 160, intro 240, secret 160, ending title 40, ending text 300.

The JSON shape (replace every description with your text):
{{
  "case_title": "short catchy title",
  "victim": "invented full name with title, e.g. Prof. or Dr.",
  "victim_short": "what people call the victim, usually the last name",
  "found_place": "place in lowercase that continues 'The body was found in ...'",
  "briefing": "3 to 5 sentences: who was found where and when, no accident, the body was moved",
  "intro_lines": ["line 1: a place in Lisbon", "line 2: a time", "line 3: a detail of the night",
                  "line 4", "4 to 6 suspects.", "line 6: a hook"],
  "locations": [
    {{"name": "one of the 5 places, written exactly as above",
      "flavor": "one atmospheric sentence about it tonight",
      "neutral_clue": "one harmless observation there"}}
  ],
  "suspects": [
    {{"role": "The ...", "dossier": "one public sentence about this person",
      "intro": "starts with 'You are <role>.' then the motive against the victim, in second person",
      "trace": "small object with one detail", "secret": "starts with 'You', the embarrassing secret",
      "rumor": "<role> was seen ..."}}
  ],
  "neutral_private_clues": ["You noticed ...", "... 8 in total"],
  "endings": {{
    "truth": {{"title": "...", "text": "the group named the right suspect and the right place"}},
    "incomplete": {{"title": "...", "text": "right suspect, but the place was wrong or unknown"}},
    "wrong": {{"title": "...", "text": "an innocent suspect was accused"}},
    "escaped": {{"title": "...", "text": "the group could not agree, the case goes cold"}}
  }}
}}

Before you answer, check every rule above once more, especially rules 1, 3 and 5."""


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
    story = None
    for _ in range(MAX_REQUESTS):
        text = _ask(client, model, messages)
        try:
            story = parse_story(text, places)
            problems = logic.validate_story(story)
        except AIError:
            problems = ["The answer was not one valid JSON object of the requested shape."]
        if not problems:
            return story
        messages += [
            {"role": "assistant", "content": text or ""},
            {"role": "user", "content": "Your answer has these problems:\n- " + "\n- ".join(problems[:10])
             + "\nFix them and answer again with the complete JSON object only."},
        ]
    if story is None:
        raise AIError("the AI answer was not readable")
    return story   # still has problems: ai_case_ready will refuse it and case #001 is played


def _ask(client, model, messages):
    """One request. Returns the answer text, or raises AIError."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=1.0,   # a little randomness: every room gets a different case
            # OpenRouter only: try these models if the first one is busy, and do not let
            # "thinking" models think for minutes (we need the case while people join).
            extra_body={"models": [model] + [m for m in FALLBACK_MODELS if m != model],
                        "reasoning": {"enabled": False}},
        )
        return response.choices[0].message.content
    except Exception as problem:   # any network or service error: play case #001
        raise AIError(_reason(problem)) from problem


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
    # A trace becomes "Found at the <place>: <trace>. It belongs to <role>." – it may name nobody.
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

    # The intro is only decoration: if its lines do not fit, use a standard one for this victim.
    lines = story["intro_lines"]
    if (len(lines) != logic.NUMBER_OF_INTRO_LINES
            or any(len(line) > logic.STORY_LIMITS["intro_line"] or points_at_somebody(line)
                   for line in lines)):
        story["intro_lines"] = standard_intro(story["victim"])
    return story


def standard_intro(victim):
    return ["Lisbon, Portugal.", "23:47.", "NOVA University.", f"{victim} is dead.",
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
    return {
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
