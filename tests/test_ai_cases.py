"""AI-written cases: a new story for every room, with case #001 as the fallback.

These tests never go online. A fake AI client returns a fixed answer, exactly
like the course wiki recommends ("use fake model responses in tests").
"""
import copy
import json

import pytest
from conftest import make_lobby, token_of

import ai
import content
import generator
import logic
import ui

# ---------------------------------------------------------------- a fake AI answer

FAKE_ANSWER = {
    "case_title": "The Silent Regatta",
    "victim": "Dr. Helena Costa",
    "victim_short": "Costa",
    "found_place": "the locked rector's office",
    "briefing": ("At 23:47 a cleaner found Dr. Helena Costa in the locked rector's office. "
                 "It was no accident, and she did not die there. Someone moved her."),
    "intro_lines": ["Lisbon, Portugal.", "23:47.", "Rain over the river.", "Dr. Costa is dead.",
                    "Six suspects.", "Nobody saw anything."],
    "locations": [
        {"name": "Library", "icon": "🌿", "flavor": "Wet leaves glitter under the lamps.",
         "neutral_clue": "A watering can stands full next to the tomatoes."},
        {"name": "Auditorium", "icon": "🏀", "flavor": "Basketballs sleep in a cage by the door.",
         "neutral_clue": "The scoreboard still shows last week's final score."},
        {"name": "Main Deck", "icon": "🖨️", "flavor": "Warm paper and toner hang in the air.",
         "neutral_clue": "A stack of exam covers waits to be stapled."},
        {"name": "Beach", "icon": "🚣", "flavor": "Oars drip onto the wooden floor.",
         "neutral_clue": "A life jacket hangs on its hook, perfectly dry."},
        {"name": "ICA Canteen", "icon": "🏛️", "flavor": "Rain drums on the glass roof.",
         "neutral_clue": "A vending machine hums with a full row of water bottles."},
    ],
    "suspects": [
        {"role": "The Exchange Student", "dossier": "Arrived from Milan in September.",
         "intro": "You are The Exchange Student. Costa failed your thesis proposal twice.",
         "trace": "a train ticket folded into a tiny boat",
         "secret": "You have not been to a single lecture this month.",
         "rumor": "The Exchange Student was seen sleeping on a sofa in the student lounge."},
        {"role": "The Dean", "dossier": "Runs the school and its budget.",
         "intro": "You are The Dean. Costa was about to expose your expense reports.",
         "trace": "a gold cufflink shaped like an anchor",
         "secret": "You booked a family holiday on the school's card.",
         "rumor": "The Dean was seen hiding a travel brochure in a drawer."},
        {"role": "The Chef", "dossier": "Cooks for the campus canteen.",
         "intro": "You are The Chef. Costa wanted the canteen closed and your job gone.",
         "trace": "a wooden spoon with a burnt handle",
         "secret": "You sell the canteen's leftovers to a café in town.",
         "rumor": "The Chef was seen loading boxes of food into a private car."},
        {"role": "The Rower", "dossier": "Captain of the university rowing team.",
         "intro": "You are The Rower. Costa had you dropped from the national squad.",
         "trace": "a cracked stopwatch on a blue cord",
         "secret": "You skipped the doping test by faking an injury.",
         "rumor": "The Rower was seen bandaging a perfectly healthy ankle."},
        {"role": "The Archivist", "dossier": "Keeps the old records of the university.",
         "intro": "You are The Archivist. Costa called your archive a waste of money.",
         "trace": "a pair of white cotton gloves",
         "secret": "You took an old map home and sold it online.",
         "rumor": "The Archivist was seen photographing an old map at night."},
        {"role": "The Tutor", "dossier": "Teaches the first-year statistics labs.",
         "intro": "You are The Tutor. Costa took credit for your teaching award.",
         "trace": "a red pen with chewed cap",
         "secret": "You let your friends copy the lab solutions.",
         "rumor": "The Tutor was seen emailing solution files after midnight."},
    ],
    "neutral_private_clues": [
        "You noticed the rain started just before eleven.",
        "You noticed the lifts were switched off for the night.",
        "You noticed a cat asleep on a warm radiator.",
        "You noticed the coffee machine ran out of milk.",
        "You noticed the bells rang a little late again.",
        "You noticed a delivery van parked by the entrance.",
        "You noticed the heating clicked off at eleven.",
        "You noticed someone had left the radio on in a cleaning cupboard.",
    ],
    "endings": {
        "truth": {"title": "Case Closed", "text": "Right person, right place. The truth is out."},
        "incomplete": {"title": "Half the Truth", "text": "Right person, but where did it happen?"},
        "wrong": {"title": "The Wrong Person", "text": "An innocent is led away."},
        "escaped": {"title": "Cold Case", "text": "Nobody agreed. The file is closed."},
    },
}
FAKE_ROLES = [s["role"] for s in FAKE_ANSWER["suspects"]]
FAKE_LOCATIONS = [loc["name"] for loc in FAKE_ANSWER["locations"]]


def fake_story():
    return ai.parse_story(json.dumps(FAKE_ANSWER))


class FakeClient:
    """Looks like openai.OpenAI() to ai.write_story, but never goes online."""

    def __init__(self, answer=None, error=None):
        self.answer, self.error = answer, error
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        if self.error is not None:
            raise self.error
        message = type("Message", (), {"content": self.answer})
        choice = type("Choice", (), {"message": message})
        return type("Response", (), {"choices": [choice]})


class RateLimitError(Exception):
    """Same name as the error the openai library raises when the daily limit is reached."""


class APITimeoutError(Exception):
    """Same name as the error the openai library raises after a timeout."""


def lobby_with_ai(n=5, status="ready"):
    g = make_lobby(n)
    g = logic.ai_case_writing(g, 0)
    if status == "ready":
        g = logic.ai_case_ready(g, fake_story(), 1)
    elif status == "failed":
        g = logic.ai_case_failed(g, "the daily AI limit is reached", 1)
    return g


def start(g, n=5, **kwargs):
    return logic.start(g, "t1", set(range(1, n + 1)), 0, seed=kwargs.pop("seed", 1), **kwargs)


# ---------------------------------------------------------------- reading the AI answer

def test_case_001_passes_the_story_checks():
    assert logic.validate_story(content.DEFAULT_STORY) == []


def test_a_good_ai_answer_becomes_a_valid_story():
    story = fake_story()
    assert logic.validate_story(story) == []
    assert story["locations"] == FAKE_LOCATIONS
    assert list(story["roles"]) == FAKE_ROLES
    assert set(story) == set(content.DEFAULT_STORY)   # same shape as case #001


@pytest.mark.parametrize("wrap", [
    "```json\n{}\n```",
    "Here is your case:\n{}\nEnjoy!",
])
def test_json_inside_extra_text_is_still_read(wrap):
    story = ai.parse_story(wrap.format(json.dumps(FAKE_ANSWER)))
    assert story["case_title"] == FAKE_ANSWER["case_title"]


@pytest.mark.parametrize("answer", [None, "", "no json here", "{broken", '{"case_title": "x"}'])
def test_an_unreadable_answer_raises_ai_error(answer):
    with pytest.raises(ai.AIError):
        ai.parse_story(answer)


def test_icons_come_from_the_campus_map_not_from_the_ai():
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["locations"][0]["icon"] = "a whole sentence instead of an emoji"
    story = ai.parse_story(json.dumps(answer))
    assert story["location_icons"]["Library"] == content.PLACES["Library"]["icon"]


def test_write_story_uses_the_client_and_never_goes_online():
    story = ai.write_story("fake-key", client=FakeClient(json.dumps(FAKE_ANSWER)))
    assert logic.validate_story(story) == []


@pytest.mark.parametrize("error, reason", [
    (RateLimitError("429 - Rate limit exceeded: free-models-per-day"), "the daily AI limit is reached"),
    (RateLimitError("429"), "too many requests right now"),
    (APITimeoutError("slow"), "the AI did not answer in time"),
    (ConnectionError("offline"), "the AI service did not answer"),
])
def test_service_errors_become_a_short_reason_for_the_host(error, reason):
    with pytest.raises(ai.AIError, match=reason):
        ai.write_story("fake-key", client=FakeClient(error=error))


def test_settings_without_a_key_mean_no_ai():
    assert ai.settings(lambda name: None) is None
    assert ai.settings(lambda name: "   " if name == "OPENROUTER_API_KEY" else None) is None


def test_settings_with_a_key_use_the_default_model_unless_one_is_set():
    only_key = {"OPENROUTER_API_KEY": "k"}
    assert ai.settings(only_key.get) == {"key": "k", "model": ai.DEFAULT_MODEL}
    both = {"OPENROUTER_API_KEY": "k", "OPENROUTER_MODEL": "google/gemma-4-26b-a4b-it:free"}
    assert ai.settings(both.get)["model"] == "google/gemma-4-26b-a4b-it:free"
    assert ai.settings({"REQUESTY_API_KEY": "old"}.get) is None   # the old setting is not used


# ---------------------------------------------------------------- checking a story

def broken(change):
    story = fake_story()
    change(story)
    return story


BROKEN_STORIES = {
    "giveaway_word_in_a_clue": lambda s: s["roles"]["The Dean"].update(
        rumor="The Dean was seen talking to the murderer."),
    "too_few_roles": lambda s: s["roles"].pop("The Tutor"),
    "too_many_locations": lambda s: s["locations"].append("Car Park"),
    "name_inside_name": lambda s: s["roles"].update(
        {"The Auditorium Coach": s["roles"].pop("The Tutor")}),
    "rumor_without_role": lambda s: s["roles"]["The Dean"].update(
        rumor="Somebody was seen hiding a brochure."),
    "rumor_names_another": lambda s: s["roles"]["The Dean"].update(
        rumor="The Dean was seen talking to The Chef."),
    "trace_names_a_place": lambda s: s["roles"]["The Chef"].update(
        trace="a spoon from the Main Deck"),
    "neutral_clue_points": lambda s: s["neutral_location_clues"].update(
        {"Beach": "A jacket that belongs to somebody hangs here."}),
    "too_long": lambda s: s.update(case_title="x" * 81),
    "missing_ending": lambda s: s["endings"].pop("escaped"),
    "too_few_private_clues": lambda s: s.update(neutral_private_clues=["You noticed rain."]),
    "missing_flavor": lambda s: s["location_flavor"].pop("Auditorium"),
    "intro_names_a_place": lambda s: s["intro_lines"].__setitem__(2, "Blood in the Beach."),
    "intro_names_a_suspect": lambda s: s["intro_lines"].__setitem__(5, "The Dean knows more."),
    "too_few_intro_lines": lambda s: s["intro_lines"].pop(),
    "intro_line_too_long": lambda s: s["intro_lines"].__setitem__(0, "x" * 61),
}


@pytest.mark.parametrize("name", list(BROKEN_STORIES))
def test_a_broken_story_is_rejected(name):
    story = broken(BROKEN_STORIES[name])
    assert logic.validate_story(story) != []
    g = logic.ai_case_ready(logic.ai_case_writing(make_lobby(5), 0), story, 1)
    assert g["ai_case"]["status"] == "failed"
    assert g["ai_case"]["reason"] == "the AI case did not pass the checks"


def test_validate_story_survives_rubbish():
    assert logic.validate_story(None) != []
    assert logic.validate_story({"roles": "nope", "locations": 5}) != []


@pytest.mark.parametrize("n", [4, 5, 6])
def test_an_ai_story_gives_fair_cases_for_many_seeds(n):
    story = fake_story()
    pids = list(range(1, n + 1))
    for seed in range(100):
        case = generator.build_case(pids, seed, story)
        assert logic.validate_case(case, pids, story) == []
        assert {c["role"] for c in case["characters"]} <= set(FAKE_ROLES)
        assert case["murder_location"] in FAKE_LOCATIONS


def test_same_seed_and_story_give_the_same_case():
    story = fake_story()
    assert generator.build_case([1, 2, 3, 4], 7, story) == generator.build_case([1, 2, 3, 4], 7, story)


# ---------------------------------------------------------------- the lobby and the start

def test_a_ready_ai_case_is_played():
    g = start(lobby_with_ai())
    assert g["story"]["source"] == "ai"
    assert g["story"]["case_number"] == "ABCD"   # the room code
    assert {c["role"] for c in g["case"]["characters"]} <= set(FAKE_ROLES)
    assert logic.story_view(g)["case_title"] == "The Silent Regatta"
    assert logic.host_note(g, "t1") is None


def test_the_fixed_case_switch_always_plays_case_001():
    g = start(lobby_with_ai(), fixed_case=True)
    assert g["story"] is content.DEFAULT_STORY or g["story"] == content.DEFAULT_STORY
    assert {c["role"] for c in g["case"]["characters"]} <= set(content.ROLES)
    assert logic.host_note(g, "t1") is None


def test_without_ai_nothing_changes_and_there_is_no_note():
    g = start(make_lobby(5))
    assert g["story"] == content.DEFAULT_STORY
    assert "story_note" not in g
    assert logic.host_note(g, "t1") is None


@pytest.mark.parametrize("status, words", [
    ("writing", "not finished yet"),
    ("failed", "the daily AI limit is reached"),
])
def test_when_the_ai_case_is_missing_case_001_is_played_and_only_the_host_is_told(status, words):
    g = start(lobby_with_ai(status=status))
    assert g["story"] == content.DEFAULT_STORY
    assert words in logic.host_note(g, "t1")
    assert "#001" in logic.host_note(g, "t1")
    for pid in range(2, 6):
        assert logic.host_note(g, token_of(g, pid)) is None
    assert logic.host_note(g, "nobody") is None


def test_the_host_sees_how_far_the_ai_is_in_the_lobby():
    assert "writing" in logic.host_note(lobby_with_ai(status="writing"), "t1")
    assert "The Silent Regatta" in logic.host_note(lobby_with_ai(), "t1")
    assert "#001" in logic.host_note(lobby_with_ai(status="failed"), "t1")
    assert logic.host_note(lobby_with_ai(), "t2") is None
    assert logic.host_note(make_lobby(5), "t1") is None


def test_an_ai_case_that_arrives_after_the_start_is_ignored():
    g = start(logic.ai_case_writing(make_lobby(5), 0))
    assert logic.ai_case_ready(g, fake_story(), 9) is g
    assert logic.ai_case_failed(g, "late", 9) is g


def test_the_lobby_already_shows_the_ai_case_file():
    view = logic.story_view(lobby_with_ai())
    assert view["case_title"] == "The Silent Regatta"
    assert logic.story_view(make_lobby(5))["case_title"] == content.CASE_TITLE


def test_old_games_without_a_story_keep_case_001():
    g = start(make_lobby(5))
    del g["story"]
    assert logic.story_of(g) == content.DEFAULT_STORY


# ---------------------------------------------------------------- nothing secret leaks

SECRET_FIELDS = ("intro", "secret", "trace", "rumor")


@pytest.mark.parametrize("phase", ["LOBBY", "REVEAL"])
def test_the_public_story_holds_no_secrets(phase):
    g = lobby_with_ai()
    if phase == "REVEAL":
        g = start(g)
    view = logic.story_view(g)
    text = json.dumps(view, ensure_ascii=False)
    for texts in fake_story()["roles"].values():
        for field in SECRET_FIELDS:
            assert texts[field] not in text, f"leaked {field}"
    for field in SECRET_FIELDS:
        assert field not in view


def test_the_ai_case_texts_reach_the_screens():
    g = start(lobby_with_ai())
    story = logic.story_view(g)
    assert "The Silent Regatta" in ui.case_file(story)
    assert "ICA Canteen" in ui.campus_map([], story=story)
    assert "Library" in ui.campus_map([], story=story)


# ---------------------------------------------------------------- the bots can play it

def test_demo_suspects_play_an_ai_case_to_the_end():
    g = make_lobby(1)
    for _ in range(4):
        g = logic.add_bot(g, "t1", 0)
    g = logic.ai_case_ready(logic.ai_case_writing(g, 0), fake_story(), 1)
    g = logic.start(g, "t1", logic.with_bots(g, {1}), 0, seed=3)
    now = 0
    for _ in range(1200):
        if g["phase"] == "RESULT":
            break
        now += 2
        g = logic.bot_moves(logic.tick(g, logic.with_bots(g, {1}), now), now)
    assert g["phase"] == "RESULT"
    assert len(g["votes"]) == 4
    assert all(scene in FAKE_LOCATIONS for scene in g["scene_votes"].values())
    assert g["result"]["ending"] in logic.ENDING_KEYS


# ---------------------------------------------------------------- the case on the screens

def test_while_the_ai_writes_the_lobby_says_so_instead_of_showing_case_001():
    assert logic.story_view(lobby_with_ai(status="writing"))["pending"] is True
    assert logic.story_view(lobby_with_ai())["pending"] is False
    assert logic.story_view(lobby_with_ai(status="failed"))["pending"] is False
    assert logic.story_view(make_lobby(5))["pending"] is False
    started = start(lobby_with_ai(status="writing"))
    assert logic.story_view(started)["pending"] is False   # case #001 is played now


def test_the_case_intro_shows_this_cases_lines_and_title():
    story = logic.story_view(start(lobby_with_ai()))
    html = ui.case_intro(story)
    assert "Dr. Costa is dead." in html
    assert "The Silent Regatta" in html and "CASE #ABCD" in html
    assert 'class="intro case short"' in html
    assert 'class="line red"' in html                     # the 4th line is red


def test_case_001_has_its_own_intro_and_the_home_intro_is_about_the_game():
    assert "A professor is dead." in ui.case_intro()
    assert "Someone is dead." in ui.intro()
    assert '<div class="line red"' in ui.intro()          # the death line is red
    assert "A professor is dead." not in ui.intro()


def test_intro_lines_are_escaped():
    story = logic.story_view(start(lobby_with_ai()))
    story["intro_lines"] = ["<script>x</script>"] * 6
    assert "<script>" not in ui.case_intro(story)


def test_new_screen_blocks_have_no_blank_lines():
    for block in (ui.teaser(), ui.sealed_file(), ui.case_intro()):
        assert "\n\n" not in block


def test_the_timeline_of_an_ai_case_does_not_mention_the_night_guard():
    g = start(lobby_with_ai())
    g = logic.end_phase(g, "t1", set(range(1, 6)), 0)   # quickly through to the result
    while g["phase"] != "RESULT":
        g = logic.end_phase(g, "t1", set(range(1, 6)), 0)
    view = logic.public_view(g, set(range(1, 6)))
    html = ui.reconstruction(view["result"], view["characters"], str, story=logic.story_view(g))
    assert "night guard" not in html
    assert "the locked rector" in html


# ---------------------------------------------------------------- repair round and busy models

class SequenceClient(FakeClient):
    """Answers with the next text of a list, and remembers what it was asked."""

    def __init__(self, answers):
        super().__init__()
        self.answers, self.calls = list(answers), []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        self.answer = self.answers.pop(0)
        return super().create(**kwargs)


def five_suspects():
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["suspects"].pop()
    return json.dumps(answer)


def test_a_story_with_a_slip_gets_one_repair_round():
    client = SequenceClient([five_suspects(), json.dumps(FAKE_ANSWER)])
    story = ai.write_story("fake-key", client=client)
    assert logic.validate_story(story) == []
    assert len(client.calls) == 2
    repair = client.calls[1]["messages"][-1]["content"]
    assert "exactly 6 roles" in repair            # the model is told what to fix


def test_after_the_repair_round_the_story_is_handed_on_and_refused_by_the_room():
    client = SequenceClient([five_suspects(), five_suspects(), json.dumps(FAKE_ANSWER)])
    story = ai.write_story("fake-key", client=client)
    assert len(client.calls) == ai.MAX_REQUESTS   # never more than two requests per room
    g = logic.ai_case_ready(logic.ai_case_writing(make_lobby(5), 0), story, 1)
    assert g["ai_case"]["status"] == "failed"


def test_unreadable_twice_raises_ai_error():
    with pytest.raises(ai.AIError):
        ai.write_story("fake-key", client=SequenceClient(["no json", "still no json"]))


def test_a_good_first_answer_needs_only_one_request():
    client = SequenceClient([json.dumps(FAKE_ANSWER)])
    ai.write_story("fake-key", client=client)
    assert len(client.calls) == 1


def test_busy_models_have_fallbacks_and_thinking_is_switched_off():
    client = SequenceClient([json.dumps(FAKE_ANSWER)])
    ai.write_story("fake-key", client=client)
    extra = client.calls[0]["extra_body"]
    assert extra["models"][0] == ai.DEFAULT_MODEL
    assert set(ai.FALLBACK_MODELS) <= set(extra["models"])
    assert extra["reasoning"] == {"enabled": False}


def test_a_busy_free_model_gets_its_own_reason():
    error = RateLimitError("429 - x:free is temporarily rate-limited upstream. Please retry shortly")
    with pytest.raises(ai.AIError, match="the free AI models are busy right now"):
        ai.write_story("fake-key", client=FakeClient(error=error))


def test_endings_may_name_the_crime_because_they_come_after_the_reveal():
    story = fake_story()
    story["endings"]["truth"]["text"] = "The murderer is caught at last."
    assert logic.validate_story(story) == []


@pytest.mark.parametrize("written, expected", [
    ("Rumor has it the dean was seen hiding a brochure.", "The Dean was seen hiding a brochure."),
    ("Seen hiding a brochure in a drawer.", "The Dean was seen hiding a brochure in a drawer."),
    ("The Dean was seen hiding a brochure.", "The Dean was seen hiding a brochure."),
])
def test_rumors_are_brought_into_the_fixed_form(written, expected):
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["suspects"][1]["rumor"] = written
    story = ai.parse_story(json.dumps(answer))
    assert story["roles"]["The Dean"]["rumor"] == expected
    assert logic.validate_story(story) == []


def test_a_neutral_clue_that_names_someone_is_made_neutral():
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["neutral_private_clues"][0] = "You noticed The Dean leaving the Beach early."
    answer["locations"][1]["neutral_clue"] = "The Chef left a towel here."
    story = ai.parse_story(json.dumps(answer))
    assert story["neutral_private_clues"][0] == "You noticed someone leaving a nearby building early."
    assert story["neutral_location_clues"]["Auditorium"] == "someone left a towel here."
    assert logic.validate_story(story) == []


def test_every_neutral_clue_naming_someone_is_still_made_neutral():
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["neutral_private_clues"] = ["You noticed The Dean was seen near the Auditorium."] * 8
    story = ai.parse_story(json.dumps(answer))
    assert logic.validate_story(story) == []


def test_length_hints_copied_from_the_request_are_removed():
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["case_title"] = "Midnight Echoes [60]"
    answer["intro_lines"][0] = "Lisbon, Portugal. [60 each]"
    story = ai.parse_story(json.dumps(answer))
    assert story["case_title"] == "Midnight Echoes"
    assert story["intro_lines"][0] == "Lisbon, Portugal."


@pytest.mark.parametrize("change", [
    lambda lines: lines.__setitem__(0, "x" * 61),
    lambda lines: lines.__setitem__(2, "Blood in the Beach."),
    lambda lines: lines.pop(),
])
def test_intro_lines_that_do_not_fit_are_replaced_by_a_standard_intro(change):
    answer = copy.deepcopy(FAKE_ANSWER)
    change(answer["intro_lines"])
    story = ai.parse_story(json.dumps(answer))
    assert story["intro_lines"] == ai.standard_intro("Dr. Helena Costa")
    assert logic.validate_story(story) == []


def test_a_rumor_that_names_another_suspect_points_only_at_its_own_suspect():
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["suspects"][1]["rumor"] = "The Dean was seen hurrying after The Chef with a brochure."
    story = ai.parse_story(json.dumps(answer))
    assert story["roles"]["The Dean"]["rumor"] == "The Dean was seen rushing after someone with a brochure."
    assert logic.validate_story(story) == []


def test_place_names_get_their_official_spelling():
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["locations"][0]["name"] = "the library"
    story = ai.parse_story(json.dumps(answer))
    assert story["locations"][0] == "Library"
    assert "Library" in story["location_flavor"]
    assert logic.validate_story(story) == []


@pytest.mark.parametrize("n, line", [(4, "Four suspects."), (5, "Five suspects."), (6, "Six suspects.")])
def test_the_case_intro_names_the_real_number_of_suspects(n, line):
    html = ui.case_intro(suspects=n)          # case #001: "4 to 6 suspects."
    assert line in html and "4 to 6" not in html


def test_the_number_also_works_inside_a_sentence_and_without_a_count():
    story = logic.story_view(start(lobby_with_ai()))
    story["intro_lines"][4] = "Only 4 to 6 suspects remain."
    assert "Only five suspects remain." in ui.case_intro(story, suspects=5)
    assert "4 to 6 suspects." in ui.case_intro()   # no count known: unchanged


@pytest.mark.parametrize("seed", range(30))
def test_the_murderer_is_always_one_of_the_players_who_are_there_at_the_start(seed):
    # 6 joined while the AI wrote the case, but only 4 are still online when the host starts.
    g = logic.start(lobby_with_ai(6), "t1", {1, 2, 3, 4}, 0, seed=seed)
    players = [p["pid"] for p in g["players"]]
    assert players == [1, 2, 3, 4]
    assert g["case"]["murderer"] in players
    assert len(g["case"]["characters"]) == 4             # unused AI roles are simply left out
    assert {c["role"] for c in g["case"]["characters"]} <= set(FAKE_ROLES)


def test_the_crime_may_be_named_in_texts_that_never_become_clues():
    story = fake_story()
    story["briefing"] = "The killer moved the body and locked the door."
    story["roles"]["The Dean"]["dossier"] = "Hates murder mysteries."
    assert logic.validate_story(story) == []


def test_spare_suspects_and_locations_are_cut_and_duplicates_skipped():
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["suspects"].insert(1, copy.deepcopy(answer["suspects"][0]))   # the same role twice
    answer["suspects"].append({**answer["suspects"][2], "role": "The Spare Suspect"})
    answer["locations"].append({**answer["locations"][0], "name": "Spare Place"})
    story = ai.parse_story(json.dumps(answer))
    assert list(story["roles"]) == FAKE_ROLES
    assert story["locations"] == FAKE_LOCATIONS
    assert logic.validate_story(story) == []


def test_missing_or_broken_endings_are_replaced_by_generic_ones():
    answer = copy.deepcopy(FAKE_ANSWER)
    del answer["endings"]["escaped"]
    answer["endings"]["wrong"] = "just a string"
    story = ai.parse_story(json.dumps(answer))
    assert story["endings"]["escaped"] == ai.GENERIC_ENDINGS["escaped"]
    assert story["endings"]["wrong"] == ai.GENERIC_ENDINGS["wrong"]
    assert story["endings"]["truth"]["title"] == "Case Closed"
    assert logic.validate_story(story) == []


def test_a_trace_that_names_someone_is_made_neutral():
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["suspects"][2]["trace"] = "a spoon from the Main Deck"
    story = ai.parse_story(json.dumps(answer))
    assert story["roles"]["The Chef"]["trace"] == "a spoon from a nearby building"
    assert logic.validate_story(story) == []


def test_the_request_asks_for_spares_and_has_no_bracket_hints():
    prompt = ai.user_prompt()
    assert "Exactly 7 suspects" in prompt and "exactly the 5 places above" in prompt
    assert "[60]" not in prompt and "[40]" not in prompt


def test_every_request_gets_a_theme_and_a_letter_for_the_victim():
    import random
    prompt = ai.user_prompt(random.Random(1))
    assert "<THEME>" not in prompt and "<LETTER>" not in prompt
    assert any(theme in prompt for theme in ai.THEMES)
    themes = {next(t for t in ai.THEMES if t in ai.user_prompt(random.Random(seed))) for seed in range(40)}
    assert len(themes) > 5                                   # rooms really get different themes



# ---------------------------------------------------------------- places on the campus map

def test_the_ai_writes_about_five_given_campus_places():
    import random
    places = ai.pick_places(random.Random(3))
    assert len(places) == 5 and all(place in content.PLACES for place in places)
    prompt = ai.user_prompt(random.Random(3), places=places)
    assert ", ".join(places) in prompt and "<PLACES>" not in prompt


def test_answer_texts_are_matched_to_the_given_places_by_name_or_order():
    places = ["Library", "Auditorium", "Main Deck", "Beach", "ICA Canteen"]
    answer = copy.deepcopy(FAKE_ANSWER)
    answer["locations"].reverse()                       # any order
    answer["locations"][0]["name"] = "Canteen"          # a shortened name
    story = ai.parse_story(json.dumps(answer), places)
    assert story["locations"] == places
    assert logic.validate_story(story) == []


def test_a_place_that_is_not_on_the_campus_map_is_refused():
    story = fake_story()
    story["locations"][0] = "Moon Base"
    assert any("not a place on the campus map" in p for p in logic.validate_story(story))
