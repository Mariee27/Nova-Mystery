"""public_view / private_view (Done-when 17, 18)."""
import json

import pytest

import content
import logic
from conftest import (
    LOC, SECURE_TOKENS, advance_to, character, innocent_pids, innocent_token,
    last_log_id, make_lobby, make_started, murderer_pid, murderer_token,
    online_all, own_clue_ids, pids_of, plant_spot, started_in, token_of, cast_votes,
)

PUBLIC_KEYS = {"code", "phase", "deadline", "players", "log", "searched",
               "result", "abort_reason", "characters"}
PUBLIC_PLAYER_KEYS = {"pid", "name", "role", "online", "is_host", "acted", "voted"}
PRIVATE_KEYS = {"pid", "name", "is_host", "phase", "acted", "voted", "role", "intro",
                "alibi", "secret", "is_murderer", "clues", "can_plant", "plant_locations",
                "open_questions", "last_move"}
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
    g = logic.question(g, innocent_token(g, 3), inn[0], "Where were you?", 8)
    view = logic.public_view(g, online_all(g))
    kinds = {e["kind"] for e in view["log"]}
    assert {"search", "share", "question"} <= kinds
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
    assert v["open_questions"] == []


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


def test_dw17_private_view_shared_flag_and_open_questions():
    g = started_in("INVESTIGATION")
    cid = own_clue_ids(g, 2)[0]
    g = logic.share(g, "t2", cid, 5)
    v = logic.private_view(g, "t2")
    assert [c["shared"] for c in v["clues"] if c["id"] == cid] == [True]
    assert v["acted"]
    g = logic.question(g, "t1", 3, "Where were you?", 6)
    qid = last_log_id(g)
    assert [e["id"] for e in logic.private_view(g, "t3")["open_questions"]] == [qid]
    assert logic.private_view(g, "t4")["open_questions"] == []
    g = logic.answer(g, "t3", qid, "In the library.", 7)
    assert logic.private_view(g, "t3")["open_questions"] == []


def test_dw17_private_view_murderer_can_plant_in_investigation():
    g = started_in("INVESTIGATION")
    assert logic.private_view(g, murderer_token(g))["can_plant"]


# ---------------------------------------------------------------- DW18
def _question_entry(g):
    return [e for e in g["log"] if e["kind"] == "question"][-1]


def test_dw18_html_in_question_stored_and_shown_literally():
    g = started_in("INVESTIGATION")
    g = logic.question(g, "t1", 2, "<b>x</b>", 5)
    assert "<b>x</b>" in _question_entry(g)["text"]
    view = logic.public_view(g, online_all(g))
    shown = [e for e in view["log"] if e["kind"] == "question"][-1]
    assert "<b>x</b>" in shown["text"]
    assert "&lt;" not in shown["text"]


def test_dw18_control_characters_removed_from_question():
    g = started_in("INVESTIGATION")
    g = logic.question(g, "t1", 2, "Hel\x00lo\nwor\x07ld", 5)
    text = _question_entry(g)["text"]
    assert "Helloworld" in text
    assert not any(ord(ch) < 32 for ch in text)
    view = logic.public_view(g, online_all(g))
    assert "\x00" not in json.dumps(view, ensure_ascii=False)


def test_dw18_text_of_only_control_characters_is_rejected():
    from conftest import assert_rejected_unchanged
    g = started_in("INVESTIGATION")
    assert_rejected_unchanged(lambda x: logic.question(x, "t1", 2, "\x00\n", 5), g)


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
