"""public_view / private_view (Done-when 17, 18)."""
import json

import pytest

import content
import logic
import ui
from conftest import (
    LOC, SECURE_TOKENS, advance_to, character, innocent_pids, innocent_token,
    make_lobby, make_started, murderer_pid, murderer_token,
    online_all, own_clue_ids, pids_of, plant_spot, started_in, token_of, cast_votes,
)

PUBLIC_KEYS = {"code", "phase", "deadline", "players", "log", "searched",
               "result", "abort_reason", "characters"}
PUBLIC_PLAYER_KEYS = {"pid", "name", "role", "online", "is_host", "acted", "voted"}
PRIVATE_KEYS = {"pid", "name", "is_host", "phase", "acted", "voted", "role", "intro",
                "alibi", "secret", "is_murderer", "clues", "can_plant", "plant_locations",
                "last_move", "puzzles"}
# "role" is intentionally NOT forbidden: roles are public from REVEAL on.
FORBIDDEN_KEYS = {"token", "murderer", "is_murderer", "secret", "intro", "alibi",
                  "clues", "implicates", "clue_kind", "planted", "case",
                  "true_location", "alibi_location", "murder_location",
                  "murder_time", "location_clues", "secrets_kept", "tally", "winner"}
LOG_FORBIDDEN = {"implicates", "clue_kind", "planted"}


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def has_text(obj, text):
    return json.dumps(text, ensure_ascii=False)[1:-1] in dump(obj)


def all_keys(obj):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= all_keys(v)
    return keys


def private_texts(game):
    """Every secret / intro / alibi / private and location clue text of the case."""
    case = game["case"]
    texts = []
    for c in case["characters"]:
        for field in ("secret", "intro", "alibi"):
            if c.get(field):
                texts.append(c[field])
        texts += [cl["text"] for cl in c["clues"]]
    texts += [cl["text"] for cl in case["location_clues"]]
    return texts


def secure_game(phase):
    if phase == "LOBBY":
        return make_lobby(5, SECURE_TOKENS)
    return advance_to(make_started(5, 1, SECURE_TOKENS), phase)


# ---------------------------------------------------------------- DW17 public
@pytest.mark.parametrize("phase", ["LOBBY", "REVEAL", "INVESTIGATION", "DISCUSSION", "VOTE"])
def test_dw17_public_view_leaks_nothing_in_every_phase(phase):
    g = secure_game(phase)
    view = logic.public_view(g, online_all(g))
    text = dump(view)
    assert set(view) == PUBLIC_KEYS
    assert view["phase"] == phase
    assert view["result"] is None
    assert view["characters"] is None
    for p in view["players"]:
        assert set(p) == PUBLIC_PLAYER_KEYS
    assert not (all_keys(view) & FORBIDDEN_KEYS)
    for tok in SECURE_TOKENS:
        assert tok not in text
    assert "murderer" not in text.lower()
    if g["case"]:
        for t in private_texts(g):
            assert not has_text(view, t), "leaked: %r" % t


def test_dw17_public_view_role_none_in_lobby_and_character_role_in_reveal():
    g = make_lobby(5, SECURE_TOKENS)
    view = logic.public_view(g, online_all(g))
    assert [p["role"] for p in view["players"]] == [None] * 5
    g = make_started(5, 1, SECURE_TOKENS)
    assert g["phase"] == "REVEAL"
    view = logic.public_view(g, online_all(g))
    for p in view["players"]:
        assert p["role"] == character(g, p["pid"])["role"]
        assert p["role"] in content.ROLES


def test_dw17_public_log_has_no_hidden_keys_also_after_plant():
    g = started_in("INVESTIGATION", tokens=SECURE_TOKENS)
    m = murderer_pid(g)
    inn = innocent_pids(g)
    g = logic.plant(g, murderer_token(g), inn[0], plant_spot(g), 5)
    free = next(loc for loc in LOC if loc not in g["searched"])
    g = logic.search(g, innocent_token(g, 1), free, 6)
    g = logic.share(g, innocent_token(g, 2), own_clue_ids(g, inn[2])[0], 7)
    view = logic.public_view(g, online_all(g))
    kinds = {e["kind"] for e in view["log"]}
    assert {"search", "share"} <= kinds
    assert len(view["log"]) == len(g["log"])
    for e in view["log"]:
        assert not (set(e) & LOG_FORBIDDEN)
    assert not (all_keys(view) & FORBIDDEN_KEYS)
    for tok in SECURE_TOKENS:
        assert tok not in dump(view)
    assert "murderer" not in dump(view).lower()
    assert m is not None


def test_dw17_public_view_result_phase_has_result_and_characters():
    g = started_in("INVESTIGATION", tokens=SECURE_TOKENS)
    inn = innocent_pids(g)
    g = logic.plant(g, murderer_token(g), inn[0], plant_spot(g), 5)
    g = advance_to(g, "RESULT")
    view = logic.public_view(g, online_all(g))
    assert view["phase"] == "RESULT"
    assert view["result"] is not None
    assert view["result"]["murderer"] == murderer_pid(g)
    assert view["characters"] is not None
    assert len(view["characters"]) == 5
    assert sorted(c["pid"] for c in view["characters"]) == pids_of(g)
    for c in view["characters"]:
        assert c["role"] in content.ROLES
    assert any(e.get("planted") is True for e in view["log"])
    for tok in SECURE_TOKENS:
        assert tok not in dump(view)


def test_dw17_public_view_players_flags():
    g = started_in("INVESTIGATION")
    g = logic.search(g, "t1", LOC[0], 5)
    view = logic.public_view(g, {1, 2, 3})
    by = {p["pid"]: p for p in view["players"]}
    assert [by[i]["online"] for i in range(1, 6)] == [True, True, True, False, False]
    assert by[1]["is_host"] is True
    assert all(by[i]["is_host"] is False for i in range(2, 6))
    assert by[1]["acted"] is True
    assert all(by[i]["acted"] is False for i in range(2, 6))
    assert all(by[i]["voted"] is False for i in range(1, 6))
    assert view["searched"] == [LOC[0]]


def test_dw17_public_view_does_not_mutate_game():
    g = started_in("INVESTIGATION")
    before = json.dumps(g, sort_keys=True)
    logic.public_view(g, online_all(g))
    assert json.dumps(g, sort_keys=True) == before


# ---------------------------------------------------------------- DW17 private
def test_dw17_private_view_wrong_token_is_none():
    for g in (make_lobby(4), started_in("INVESTIGATION")):
        assert logic.private_view(g, "nope") is None
        assert logic.private_view(g, "") is None


def test_dw17_private_view_before_start_has_no_case_fields():
    g = make_lobby(4)
    v = logic.private_view(g, "t1")
    assert set(v) == PRIVATE_KEYS
    assert v["pid"] == 1 and v["name"] == "P1" and v["is_host"] is True
    assert v["phase"] == "LOBBY"
    assert v["role"] is None and v["intro"] is None
    assert v["alibi"] is None and v["secret"] is None
    assert not v["is_murderer"]
    assert v["clues"] == []
    assert not v["can_plant"]


def test_dw17_private_view_own_card_matches_case():
    g = started_in("INVESTIGATION")
    m = murderer_pid(g)
    for pid in pids_of(g):
        v = logic.private_view(g, token_of(g, pid))
        ch = character(g, pid)
        assert set(v) == PRIVATE_KEYS
        assert v["pid"] == pid
        assert v["role"] == ch["role"]
        assert v["intro"] == ch["intro"]
        assert v["alibi"] == ch["alibi"]
        assert v["secret"] == ch["secret"]
        assert v["is_murderer"] == (pid == m)
        assert [c["id"] for c in v["clues"]] == [c["id"] for c in ch["clues"]]
        assert [c["text"] for c in v["clues"]] == [c["text"] for c in ch["clues"]]
        assert all(c["shared"] is False for c in v["clues"])
        if pid != m:
            assert not v["can_plant"]
    assert logic.private_view(g, token_of(g, m))["secret"] is None


def test_dw17_private_view_contains_no_other_players_card_or_token():
    g = started_in("INVESTIGATION", tokens=SECURE_TOKENS)
    for a in pids_of(g):
        va = logic.private_view(g, token_of(g, a))
        own_texts = {c["text"] for c in va["clues"]}
        for b in pids_of(g):
            if a == b:
                continue
            assert token_of(g, b) not in dump(va)
            cb = character(g, b)
            if cb["secret"]:
                assert not has_text(va, cb["secret"])
            for cl in cb["clues"]:
                if cl["text"] not in own_texts:
                    assert not has_text(va, cl["text"])
        assert "token" not in all_keys(va)


def test_dw17_private_view_shared_flag():
    g = started_in("INVESTIGATION")
    cid = own_clue_ids(g, 2)[0]
    g = logic.share(g, "t2", cid, 5)
    v = logic.private_view(g, "t2")
    assert [c["shared"] for c in v["clues"] if c["id"] == cid] == [True]
    assert v["acted"]
    assert [c["shared"] for c in logic.private_view(g, "t3")["clues"]] == [False, False]


def test_dw17_private_view_murderer_can_plant_in_investigation():
    g = started_in("INVESTIGATION")
    assert logic.private_view(g, murderer_token(g))["can_plant"]


# ---------------------------------------------------------------- DW18
def _joined(name):
    return logic.join(logic.new_game("ABCD", 0), name, "ta", 0)["players"][-1]["name"]


def test_dw18_html_in_a_name_stored_and_shown_literally():
    """Players type only their name now (interrogations happen out loud)."""
    assert _joined("<b>x</b>") == "<b>x</b>"
    g = logic.join(logic.new_game("ABCD", 0), "<b>x</b>", "ta", 0)
    shown = logic.public_view(g, {1})["players"][0]["name"]
    assert shown == "<b>x</b>" and "&lt;" not in shown


def test_dw18_control_characters_removed_from_a_name():
    name = _joined("Hel\x00lo\nwor\x07ld")
    assert name == "Hello world" and not any(ord(ch) < 32 for ch in name)   # a line break becomes a space


def test_dw18_text_of_only_control_characters_is_rejected():
    from conftest import assert_rejected_unchanged
    assert_rejected_unchanged(lambda x: logic.join(x, "\x00\n", "tb", 0), logic.new_game("ABCD", 0))


def test_ballots_are_secret_while_voting_and_public_in_the_result():
    g = started_in("INVESTIGATION", tokens=SECURE_TOKENS)
    g = advance_to(g, "VOTE")
    murderer = murderer_pid(g)
    voter, other = innocent_pids(g)[0], innocent_pids(g)[1]
    g = cast_votes(g, {voter: murderer, other: voter})
    during = logic.public_view(g, online_all(g))
    assert during["result"] is None                          # nobody sees a ballot while voting
    assert '"votes"' not in dump(during)                       # no ballot hides anywhere in the view
    g = advance_to(g, "RESULT")
    result = logic.public_view(g, online_all(g))["result"]
    assert result["votes"][str(voter)] == murderer           # afterwards every ballot is shown
    assert result["votes"][str(other)] == voter
    assert set(result["votes"]) == {str(voter), str(other)}  # players who did not vote are not invented


def test_the_case_file_holds_the_public_facts_and_never_the_crime_scene():
    story = logic.public_story(content.DEFAULT_STORY)
    html_text = ui.case_file(story)
    for fact in (story["case_title"], story["victim"], content.FOUND_TIME, content.MURDER_TIME,
                 "Vale&#x27;s locked research office", *story["locations"]):
        assert fact in html_text
    assert "Unknown" in html_text                              # the crime scene is the puzzle


def test_the_case_file_escapes_ai_texts():
    story = dict(logic.public_story(content.DEFAULT_STORY), victim="<b>Eve</b>", case_title="A & B",
                 found_place="the <i>boathouse</i>")
    html_text = ui.case_file(story)
    assert "<b>Eve</b>" not in html_text and "&lt;b&gt;Eve&lt;/b&gt;" in html_text
    assert "A &amp; B" in html_text and "The &lt;i&gt;boathouse" in html_text


def test_the_case_file_has_its_own_style_not_the_start_pages_paper_file():
    # .casefile is the light paper file on the start page and in the lobby; the dark case file
    # on the phones once borrowed that name, and its dark background hid the start page's text.
    assert 'class="casefile' in ui.teaser() and 'class="casefile' in ui.sealed_file()
    assert 'class="casefile' not in ui.case_file(logic.public_story(content.DEFAULT_STORY))
