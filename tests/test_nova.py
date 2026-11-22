"""Features of NOVA MYSTERY: the scene accusation and its endings, the demo
suspects (bots), and the HTML building blocks."""
import re

import content
import logic
import ui
from conftest import (
    assert_rejected_unchanged, innocent_pids, make_lobby, make_started,
    murderer_pid, started_in, token_of,
)


# ---------------------------------------------------------------- accusation and endings

def vote_all(game, target_of, scene_of=lambda pid: None):
    for p in game["players"]:
        game = logic.vote(game, p["token"], target_of(p["pid"]), 0, scene=scene_of(p["pid"]))
    return game


def finish(game):
    return logic.end_phase(game, token_of(game, game["host"]), {1, 2, 3, 4, 5}, 0)


def accuse_murderer(game):
    m = murderer_pid(game)
    return lambda pid: m if pid != m else innocent_pids(game)[0]


def test_right_suspect_and_right_scene_is_the_truth():
    g = started_in("VOTE")
    scene = g["case"]["murder_location"]
    r = finish(vote_all(g, accuse_murderer(g), lambda pid: scene))["result"]
    assert r["winner"] == "detectives" and r["ending"] == "truth"
    assert r["scene_tally"] == {scene: 5}


def test_right_suspect_wrong_scene_is_incomplete():
    g = started_in("VOTE")
    wrong = next(loc for loc in content.LOCATIONS if loc != g["case"]["murder_location"])
    r = finish(vote_all(g, accuse_murderer(g), lambda pid: wrong))["result"]
    assert r["winner"] == "detectives" and r["ending"] == "incomplete"


def test_right_suspect_but_no_scene_is_incomplete():
    g = started_in("VOTE")
    r = finish(vote_all(g, accuse_murderer(g)))["result"]
    assert r["ending"] == "incomplete" and r["scene_tally"] == {}


def test_scene_tie_is_not_the_truth():
    g = started_in("VOTE")
    scene = g["case"]["murder_location"]
    other = next(loc for loc in content.LOCATIONS if loc != scene)
    places = {1: scene, 2: scene, 3: other, 4: other}
    r = finish(vote_all(g, accuse_murderer(g), places.get))["result"]
    assert r["ending"] == "incomplete"


def test_innocent_with_most_votes_is_the_wrong_accusation():
    g = started_in("VOTE")
    victim = innocent_pids(g)[0]
    r = finish(vote_all(g, lambda pid: victim if pid != victim else innocent_pids(g)[1]))["result"]
    assert r["winner"] == "murderer" and r["ending"] == "wrong"


def test_no_votes_means_the_case_goes_cold():
    r = finish(started_in("VOTE"))["result"]
    assert r["winner"] == "murderer" and r["ending"] == "escaped"


def test_unknown_scene_is_rejected():
    g = started_in("VOTE")
    assert_rejected_unchanged(lambda x: logic.vote(x, "t1", 2, 0, scene="Mars"), g)


def test_scene_is_secret_until_the_result():
    g = started_in("VOTE")
    g = logic.vote(g, "t1", 2, 0, scene=content.LOCATIONS[0])
    view = logic.public_view(g, {1, 2, 3, 4, 5})
    assert "scene_votes" not in view and view["result"] is None


def test_old_games_without_scene_votes_still_finish():
    g = started_in("VOTE")
    del g["scene_votes"]
    assert finish(g)["result"]["scene_tally"] == {}


# ---------------------------------------------------------------- demo suspects

def demo_lobby(humans=1, bots=4):
    g = make_lobby(humans)
    for _ in range(bots):
        g = logic.add_bot(g, "t1", 0)
    return g


def test_host_adds_demo_suspects_with_unique_names():
    g = demo_lobby(1, 5)
    bots = [p for p in g["players"] if p.get("bot")]
    assert len(bots) == 5 and len(g["players"]) == logic.MAX_PLAYERS
    assert len({p["name"] for p in bots}) == 5
    assert all(p["name"].endswith("(demo)") for p in bots)
    assert g["host"] == 1


def test_only_the_host_adds_demo_suspects():
    assert_rejected_unchanged(lambda x: logic.add_bot(x, "t2", 0), make_lobby(2))


def test_no_demo_suspects_in_a_full_room_or_after_the_start():
    assert_rejected_unchanged(lambda x: logic.add_bot(x, "t1", 0), demo_lobby(1, 5))
    assert_rejected_unchanged(lambda x: logic.add_bot(x, "t1", 0), make_started(4))


def test_bots_count_as_online_and_never_become_host():
    g = demo_lobby(1, 3)
    assert logic.with_bots(g, set()) == {2, 3, 4}
    g = logic.start(g, "t1", logic.with_bots(g, {1}), 0, seed=1)
    # The only human leaves: the game goes on, but no bot takes the host role.
    later = logic.tick(g, logic.with_bots(g, set()), 1)
    assert later["host"] == 1 and later["phase"] == "REVEAL"


def test_bots_wait_before_they_move():
    g = logic.start(demo_lobby(1, 4), "t1", {1, 2, 3, 4, 5}, 0, seed=1)
    g = logic.end_phase(g, "t1", {1, 2, 3, 4, 5}, 0)
    assert logic.bot_moves(g, logic.BOT_FIRST_MOVE - 1) is g        # nothing due yet
    g = logic.bot_moves(g, logic.BOT_FIRST_MOVE)
    assert len(g["acted"]) == 1                                       # one bot at a time
    g = logic.bot_moves(g, logic.BOT_FIRST_MOVE + 3 * logic.BOT_STEP)
    assert sorted(g["acted"]) == [2, 3, 4, 5]


def test_bot_moves_do_nothing_without_bots_or_outside_play():
    g = started_in("INVESTIGATION")
    assert logic.bot_moves(g, 1000) is g
    lobby = demo_lobby(1, 4)
    assert logic.bot_moves(lobby, 1000) is lobby


def test_a_guilty_bot_does_not_search_its_own_traces():
    for seed in range(40):
        g = logic.start(demo_lobby(1, 4), "t1", {1, 2, 3, 4, 5}, 0, seed=seed)
        m = g["case"]["murderer"]
        if m == 1:
            continue
        g = logic.end_phase(g, "t1", {1, 2, 3, 4, 5}, 0)
        g = logic.bot_moves(g, 1000)
        searched_by_m = [e for e in g["log"] if e["kind"] == "search" and e["by"] == m]
        for entry in searched_by_m:
            assert not (entry["implicates"] == m and entry["clue_kind"] in logic.STRONG_KINDS)


def test_bots_vote_by_the_evidence_they_can_read():
    g = logic.start(demo_lobby(1, 4), "t1", {1, 2, 3, 4, 5}, 0, seed=1)
    g = logic.end_phase(g, "t1", {1, 2, 3, 4, 5}, 0)
    # The crime scene is locked at first: the host ends rounds until it opens.
    while g["round"] < g["case"]["locked"][g["case"]["murder_location"]]:
        g = logic.end_phase(g, "t1", {1, 2, 3, 4, 5}, 0)
    # The human searches the crime scene: the trace there names the culprit's role.
    g = logic.search(g, "t1", g["case"]["murder_location"], 0)
    while g["phase"] != "VOTE":
        g = logic.end_phase(g, "t1", {1, 2, 3, 4, 5}, 0)
    g = logic.bot_moves(g, g["phase_started"] + 1000)
    m = g["case"]["murderer"]
    for voter, target in g["votes"].items():
        if int(voter) != m:
            assert target == m
            assert g["scene_votes"][voter] == g["case"]["murder_location"]


def test_a_demo_game_with_one_human_plays_to_the_end_by_itself():
    g = demo_lobby(1, 3)
    g = logic.start(g, "t1", logic.with_bots(g, {1}), 0, seed=logic.DEMO_SEED)
    now = 0
    for _ in range(1200):           # only timers and bots, the human does nothing (all rounds)
        if g["phase"] == "RESULT":
            break
        now += 2
        g = logic.bot_moves(logic.tick(g, logic.with_bots(g, {1}), now), now)
    assert g["phase"] == "RESULT"
    assert len(g["votes"]) == 3     # every bot voted
    assert g["result"]["ending"] in content.ENDINGS


def test_bots_do_not_show_up_in_the_public_view_as_special():
    g = logic.start(demo_lobby(1, 4), "t1", {1, 2, 3, 4, 5}, 0, seed=1)
    view = logic.public_view(g, logic.with_bots(g, {1}))
    assert all("bot" not in p for p in view["players"])
    assert all(p["online"] for p in view["players"])


# ---------------------------------------------------------------- HTML building blocks

EVIL = '<script>alert(1)</script> $x$ "q"'


def test_h_escapes_html_quotes_and_math():
    out = ui.h(EVIL)
    assert "<script>" not in out and "$" not in out and '"' not in out


def test_log_cards_escape_player_text():
    shared = {"id": 2, "kind": "share", "by": 1, "text": EVIL}
    html = ui.log_entry(shared, lambda pid: EVIL)
    assert "<script>" not in html and "Witness statement" in html


def test_question_and_answer_entries_of_old_games_still_show_as_plain_notes():
    """Rooms saved before interrogations moved off the app may still hold such entries."""
    old = [{"id": 1, "kind": "question", "by": 1, "target": 2, "text": EVIL, "answered": False},
           {"id": 2, "kind": "answer", "by": 2, "text": EVIL, "question_id": 1}]
    for entry in old:
        assert "<script>" not in ui.log_entry(entry, lambda pid: EVIL)
    assert "<script>" not in ui.evidence_wall(old, lambda pid: EVIL)


def test_no_card_leaks_a_forgery_before_the_result():
    hidden = {"id": 1, "kind": "search", "by": None, "text": "A note.", "location": content.LOCATIONS[0]}
    html = ui.log_entry(hidden, str)
    assert "planted" not in html.lower() and "Forged" not in html and "Unverified" in html
    revealed = dict(hidden, planted=True, clue_kind="suspicious", implicates=2)
    assert "planted by the murderer" in ui.log_entry(revealed, str)


def test_evidence_wall_pins_every_kind_escaped_with_a_fixed_tilt():
    log = [{"id": 1, "kind": "search", "by": None, "text": EVIL, "location": content.LOCATIONS[0]},
           {"id": 2, "kind": "share", "by": 1, "text": EVIL},
           {"id": 3, "kind": "system", "by": None, "text": EVIL}]
    html = ui.evidence_wall(log, lambda pid: EVIL)
    assert "<script>" not in html and "$" not in html
    for css in ("pin photo", "pin typed", "pin slip"):
        assert css in html
    assert content.LOCATION_ICONS[content.LOCATIONS[0]] in html     # the polaroid shows the place
    assert html.count(" new") == 1 and 'pin slip new"' in html      # only the newest drops in
    assert html == ui.evidence_wall(log, lambda pid: EVIL)          # same tilt on every refresh
    assert f"--tilt:{ui.tilt(3)}deg" in html


def test_evidence_wall_hides_forgeries_and_handles_an_empty_log():
    hidden = {"id": 1, "kind": "search", "by": None, "text": "A note.", "location": content.LOCATIONS[0]}
    html = ui.evidence_wall([hidden], str)
    assert "Forged" not in html and "Unverified" in html
    assert "Nothing has been pinned up yet" in ui.evidence_wall([], str)


def test_suspect_cards_and_dossier_escape_names():
    players = [{"pid": 1, "name": EVIL, "role": None, "online": True, "is_host": True,
                "acted": False, "voted": False}]
    assert "<script>" not in ui.suspects(players, "LOBBY")
    me = {"is_murderer": False, "intro": EVIL, "alibi": EVIL, "secret": EVIL, "role": EVIL,
          "clues": [{"id": "a", "text": EVIL, "shared": False}]}
    assert "<script>" not in ui.dossier(me)


def test_html_blocks_have_no_blank_lines():
    """A blank line would end the HTML block and let Markdown change the rest."""
    for block in (ui.intro(), ui.sealed_file(), ui.banner("a", "b"), ui.timer(5, 30),
                  ui.campus_map([content.LOCATIONS[0]])):
        assert "\n\n" not in block


def test_timer_marks_the_last_ten_seconds():
    assert "low" in ui.timer(10, 90) and "low" not in ui.timer(11, 90)
    assert "width:0.0%" in ui.timer(0, 0)


def test_big_board_timer_reads_minutes_and_turns_red_at_ten_seconds():
    assert ">1:30<" in ui.big_timer(90, 90) and ">0:28<" in ui.big_timer(28, 30)
    assert "low" in ui.big_timer(10, 90) and "low" not in ui.big_timer(11, 90)
    assert ">0:00<" in ui.big_timer(-3, 30) and "width:0.0%" in ui.big_timer(0, 0)
    assert 'role="timer"' in ui.big_timer(5, 30) and "\n\n" not in ui.big_timer(5, 30)


def test_intro_lines_all_appear_within_the_first_two_seconds():
    """The whole intro lasts about 4 s: the lines first, then the title (timings in style.css)."""
    delays = [float(part.split("s")[0]) for part in ui.intro().split("animation-delay:")[1:]]
    assert len(delays) == len(content.HOME_INTRO_LINES)   # the home intro is about the game, not case #001
    assert max(delays) <= 2.0


def test_streamlit_toolbar_is_hidden_for_the_audience():
    import pathlib
    import tomllib
    config = tomllib.loads((pathlib.Path(ui.__file__).parent / ".streamlit" / "config.toml").read_text())
    assert config["client"]["toolbarMode"] == "viewer"
def test_phone_suspect_list_is_compact_and_escapes_names():
    role = next(iter(content.ROLES))
    players = [
        {"pid": 1, "name": EVIL, "role": role, "online": True, "is_host": True,
         "acted": False, "voted": True},
        {"pid": 2, "name": "Ben", "role": None, "online": False, "is_host": False,
         "acted": False, "voted": False},
    ]
    html = ui.suspect_list(players, "VOTE", me_pid=1)
    assert "<script>" not in html and "\n\n" not in html
    assert html.count('role="listitem"') == 2              # one short row per player
    assert "you · host · voted" in html                     # my own row is marked
    assert 'aria-label="online"' in html and 'aria-label="offline"' in html
    assert "awaiting file" in html                          # no role before the reveal
    assert ui.h(content.ROLES[role]["dossier"]) not in html   # no long dossier text on the phone
    assert ui.suspect_list([], "LOBBY") == '<div class="muted">Nobody has joined yet.</div>'


def test_sealed_envelope_shows_only_the_name_escaped():
    html = ui.envelope(EVIL)
    assert "<script>" not in html and "\n\n" not in html
    assert "CONFIDENTIAL – for &lt;script&gt;" in html and 'class="seal"' in html


def test_opened_file_plays_once_and_tints_the_murderers_file():
    me = {"is_murderer": False, "intro": "i", "alibi": "a", "secret": "s", "role": EVIL,
          "clues": [{"id": "a", "text": EVIL, "shared": False}]}
    first, later = ui.opened_file(me, animate=True), ui.opened_file(me, animate=False)
    assert "unseal play" in first and "env-back" in first      # the opening animation
    assert "play" not in later and "env-back" not in later      # afterwards just the file
    assert "<script>" not in first and 'class="dossier"' in later
    assert "unseal guilty" in ui.opened_file(dict(me, is_murderer=True), animate=False)
    assert "guilty" not in later


def test_board_intro_shows_where_the_body_was_found_and_escapes_it():
    story = dict(ui._story(None), victim=EVIL, found_place=EVIL)
    html = ui.case_intro(story, scene=True)
    assert 'class="intro case short long"' in html and 'class="scene"' in html
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "CRIME SCENE – DO NOT CROSS" in html
    assert "\n\n" not in html
    # Without scene (the phones) the intro stays the short one.
    plain = ui.case_intro(story)
    assert 'class="scene"' not in plain and 'class="intro case short"' in plain


def test_board_intro_never_names_the_real_crime_scene():
    html = ui.crime_scene(ui._story(None))
    # Only where the body was FOUND (public); where the victim died is decided per game
    # and lives in game["case"], which the story never sees.
    assert content.FOUND_PLACE.replace("'", "&#x27;") in html


def test_board_intro_cards_show_every_player_with_role_and_dossier():
    players = [{"pid": 1, "name": EVIL, "role": "The IT Technician"},
               {"pid": 2, "name": "Ana", "role": "The Security Guard"}]
    html = ui.case_intro(ui._story(None), suspects=2, scene=True, players=players)
    assert 'class="lineup"' in html and html.count('class="lu"') == 2
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "#2" in html and "The Security Guard" in html
    assert "Runs the campus servers" in html            # the public dossier line of the IT Technician
    assert ui.lineup([]) == ""                          # no players known: no empty lineup


def test_board_intro_is_over_before_the_reveal_phase_ends():
    """At the next phase the board redraws: the intro must be finished by then, even with 6 players."""
    players = [{"pid": i, "name": f"P{i}", "role": ""} for i in range(1, 7)]
    html = ui.lineup(players)
    landed = [float(x) for x in re.findall(r"--in:([0-9.]+)s", html)]
    assert len(landed) == 6 and landed == sorted(landed)       # one after another
    assert max(landed) <= ui.SUSPECTS_LAST_IN < ui.SUSPECTS_UNTIL   # time to read them all
    assert ui.SUSPECTS_UNTIL < ui.BOARD_INTRO_END < logic.DURATIONS["REVEAL"]
    assert "introOut .8s ease 28s" in ui.page_style()   # style.css uses the same end time


def test_board_intro_capitalises_a_lowercase_found_place_of_an_ai_case():
    story = dict(ui._story(None), found_place="the locked rector's office")
    assert "📍 The locked rector&#x27;s office" in ui.crime_scene(story)


def test_vote_table_shows_every_ballot_escaped():
    result = {"murderer": 2, "murder_location": content.LOCATIONS[0],
              "votes": {"1": 2, "2": 1}, "scene_votes": {"1": content.LOCATIONS[0]}}
    players = [{"pid": 1}, {"pid": 2}, {"pid": 3}]
    html = ui.vote_table(result, players, lambda pid: f"{EVIL}{pid}")
    assert "<script>" not in html and "$" not in html
    assert html.count('style="--i:') == 3                  # one card per player
    assert html.count("✓") == 2                             # player 1: right culprit and right scene
    assert "Did not vote" in html                           # player 3 abstained
    assert "ballot killer" in html and "The killer&#x27;s ballot" in html   # player 2 is the culprit
    assert "1 of 2 ballots named the killer" in html


def test_ballots_come_wrong_first_right_next_and_the_killers_ballot_last():
    scene = content.LOCATIONS[0]
    result = {"murderer": 3, "murder_location": scene,
              "votes": {"1": 3, "2": 1, "3": 2, "4": 3}, "scene_votes": {"1": scene, "4": content.LOCATIONS[1]}}
    players = [{"pid": 1}, {"pid": 2}, {"pid": 3}, {"pid": 4}, {"pid": 5}]
    names = {1: "Ana", 2: "Ben", 3: "Caro", 4: "Dev", 5: "Eli"}
    html = ui.vote_table(result, players, lambda pid: names[pid])
    order = re.findall(r'style="--i:\d+"><span class="who"><span class="face">.</span>(\w+)', html)
    assert order == ["Ben", "Eli", "Ana", "Dev", "Caro"]     # wrong/none, right, killer last
    assert "🕵️ Sharpest detective" in html                   # Ana: right person and right place
    assert "🔎 Good instinct" in html                         # Dev: right person, wrong place
    assert "🤡 Fooled" in html and "🙈 Too scared to vote" in html
    assert "🎭 Master liar" in html                           # only 2 of 4 named Caro: not more than half


def test_the_killer_is_a_master_liar_when_few_ballots_name_them():
    assert ui.ballot_award(1, None, 3, "X", True, caught=False) == "🎭 Master liar"
    assert ui.ballot_award(1, None, 3, "X", True, caught=True) == "🚨 Caught"


def test_widget_labels_with_case_texts_show_markdown_as_plain_text():
    """Streamlit reads labels as Markdown; an AI role name must not become a link or an image."""
    assert ui.md("![x](https://example.com/p.png)") == "\\!\\[x\\]\\(https\\://example\\.com/p\\.png\\)"
    assert ui.md("The <b>Dean</b> **x**") == "The \\<b\\>Dean\\</b\\> \\*\\*x\\*\\*"
    for place in content.PLACES:
        assert ui.md(place) == place                       # plain names stay as they are


def test_waiting_room_greets_you_counts_who_is_here_and_escapes_names():
    me = {"pid": 2, "name": EVIL}
    players = [{"pid": 1, "name": "Ana", "online": True}, {"pid": 2, "name": EVIL, "online": True},
               {"pid": 3, "name": "Ben", "online": False}]               # Ben has left: not counted
    html = ui.waiting_room(me, "ABCD", players, is_host=False)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "Checked in" in html and "Room ABCD" in html
    assert "Waiting for the host to start" in html
    assert f"2 of {logic.MIN_PLAYERS}–{logic.MAX_PLAYERS} here · {logic.MIN_PLAYERS - 2} more needed" in html
    assert html.count('class="wr-p') == 2 and html.count('class="wr-p me"') == 1 and "Ben" not in html


def test_waiting_room_for_the_host_and_a_full_room():
    players = [{"pid": i, "name": f"P{i}", "online": True} for i in range(1, logic.MIN_PLAYERS + 1)]
    html = ui.waiting_room({"pid": 1, "name": "P1"}, "ABCD", players, is_host=True)
    assert "You are the host" in html and "Waiting for the host" not in html
    assert f"{logic.MIN_PLAYERS} suspects here · ready to start" in html
    tips = {ui.waiting_room({"pid": 1, "name": "P1"}, "ABCD", players, True, tip=t) for t in range(3)}
    assert len(tips) == 3                                 # the tip changes as people join
def test_round_banner_says_when_a_new_round_has_begun():
    assert "Round 1 of 3" in ui.round_banner(1, 3) and "new move" not in ui.round_banner(1, 3)
    second = ui.round_banner(2, 3)
    assert "Round 2 of 3" in second and "everybody gets a new move" in second and "round-banner new" in second
    assert ui.round_banner(0, 3) == ""
