"""The Voice Forensics Lab screen, driven through app.py with the Streamlit stand-in of
test_app_smoke.py: every section, the scan, comparison, the audio clue, uploads, the notebook,
the guided demo, and the way in from the home page and from a game."""

import numpy as np
import pytest

import forensics
import lab
import lab_ui
import recordings
from test_app_smoke import Browser, FakeStreamlit, game_db  # noqa: F401  (fixture)


class Upload:
    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getvalue(self):
        return self._data


class LabStreamlit(FakeStreamlit):
    """Adds the widgets the lab uses. Iframes are recorded so the tests can look inside."""

    def __init__(self):
        super().__init__()
        self.iframes = []
        self.downloads = {}
        st = self

        class V1:
            @staticmethod
            def html(document, height=None, scrolling=False):
                st.iframes.append(document)

        self.components = type("Components", (), {"v1": V1})

    def radio(self, label, options, key=None, **kwargs):
        if key and key in self.session_state:
            return self.session_state[key]
        return self.values.get(label, options[0])

    def selectbox(self, label, options, format_func=str, key=None, **kwargs):
        options = list(options)
        self.shown.extend(str(format_func(o)) for o in options)
        if label in self.values:
            if key:
                self.session_state[key] = self.values[label]
            return self.values[label]
        if key and key in self.session_state:
            return self.session_state[key]
        return options[0]

    def file_uploader(self, label, **kwargs):
        return self.values.get(label)

    def text_area(self, label, **kwargs):
        return self.values.get(label, "")

    def download_button(self, label, data=None, file_name=None, **kwargs):
        self.downloads[file_name] = data
        self.shown.append(label)
        return False

    def container(self, **kwargs):
        from test_app_smoke import Block
        return Block()


class LabBrowser(Browser):
    def __init__(self, **params):
        super().__init__(**params)
        fresh = LabStreamlit()
        fresh.query_params.update(self.st.query_params)
        self.st = fresh

    def run(self, press=(), **values):
        self.st.iframes = []
        return super().run(press=press, **values)


@pytest.fixture(autouse=True)
def fast_scan(monkeypatch):
    monkeypatch.setattr(lab, "SCAN_PACING", 0)


def open_lab(**params):
    browser = LabBrowser(lab="1", **params)
    return browser, browser.run()


SCAN = "◎  INITIATE FORENSIC SCAN"


# ---------------------------------------------------------------- way in and out

def test_home_page_opens_the_lab(game_db):
    home = LabBrowser()
    assert "Voice Forensics Lab" in home.run()
    home.run(press=["🎧 Voice Forensics Lab"])
    assert home.st.query_params.get("lab") == "1"
    assert "Evidence locker" in "\n".join(home.st.shown)


def test_back_button_leaves_the_lab(game_db):
    browser, page = open_lab()
    assert "VOICE" in page and forensics.DISCLAIMER in page
    browser.run(press=["◂ Back to NOVA MYSTERY"])
    assert "lab" not in browser.st.query_params


def test_phone_links_to_the_lab_during_a_case_001_investigation(game_db):
    import db
    import logic
    host = LabBrowser()
    host.run(press=["Play a demo"])
    code = host.st.query_params["room"]
    host.run(press=["Start game"], **{"Use the fixed demo case": True})
    conn = db.connect(game_db)
    try:
        while db.load(conn, code)["phase"] == "REVEAL":
            host.run(press=["End phase (host)"])
        assert db.load(conn, code)["phase"] == "INVESTIGATION"
        assert db.load(conn, code)["story"]["source"] == "fixed"
    finally:
        conn.close()
    page = host.run()
    assert "audio archive" in page and 'href="?lab=1"' in page and 'target="_blank"' in page
    assert logic   # the game itself is untouched by the link


# ---------------------------------------------------------------- analyze and scan

def test_nothing_is_measured_before_the_scan(game_db):
    browser, page = open_lab()
    assert "Forensic readout" not in page
    assert '"revealed":false' in browser.st.iframes[0]
    assert "Interrogation" in page


def test_scan_reveals_waveform_score_and_report(game_db):
    browser, _ = open_lab()
    page = browser.run(press=[SCAN])
    assert "Forensic readout" in page and "Forensic audio report" in page
    assert "fictional tension" in page.lower() and "Fictional game mechanic" in page
    assert '"revealed":true' in browser.st.iframes[0]
    assert recordings.DEFAULT_PAIR[1] in browser.st.session_state["lab_scanned"]
    assert any(name.endswith(".md") for name in browser.st.downloads)
    # the score in the page is the deterministic one
    analysis = lab.analysis_of(recordings.DEFAULT_PAIR[1])
    score = forensics.tension_score(analysis)
    assert f"{score['score']}<small>/100" in page


def test_each_recording_can_be_loaded_and_scanned(game_db):
    browser, _ = open_lab()
    for rid in recordings.RECORDINGS:
        browser.run(press=[] if browser.st.session_state["lab_sel"] == rid else ["Load recording"])
        browser.st.session_state["lab_sel"] = rid
        page = browser.run(press=[SCAN])
        assert "Forensic readout" in page, rid
    assert set(browser.st.session_state["lab_scanned"]) == set(recordings.RECORDINGS)


def test_the_radio_check_in_flags_the_anomaly_after_the_scan(game_db):
    browser, _ = open_lab()
    browser.st.session_state["lab_sel"] = recordings.CLUE["recording"]
    page = browser.run(press=[SCAN])
    assert "background anomaly" in page
    browser.run(press=["Inspect the background sound ▸"])
    assert browser.st.session_state["lab_mode"] == "Audio evidence"


def test_saving_a_report_to_the_notebook(game_db):
    browser, _ = open_lab()
    browser.run(press=[SCAN])
    browser.run(press=["✎ Save to detective notebook"])
    notes = browser.st.session_state["lab_notebook"]
    assert len(notes) == 1 and notes[0]["kind"] == "report"
    browser.run(press=["✎ Save to detective notebook", "✓ Saved in the notebook"])
    assert len(browser.st.session_state["lab_notebook"]) == 1     # the button is now disabled


# ---------------------------------------------------------------- uploads

def test_upload_with_transcript_is_analysed(game_db):
    t = np.arange(int(0.4 * 16000)) / 16000
    word = 0.4 * np.sin(2 * np.pi * 180 * t)
    gap = np.zeros(int(0.5 * 16000))
    x = np.concatenate([gap, word, gap, word, gap, word, gap])
    x = x + np.random.default_rng(0).normal(0, 1e-4, len(x))
    data = forensics.encode_wav(x, 16000)
    browser, _ = open_lab()
    browser.run(press=["Load into the lab"], **{"WAV file": Upload("<b>my</b> tape.wav", data),
                                                "Transcript (optional – needed for speech rate)": "one two three"})
    s = browser.st.session_state
    assert s["lab_sel"] == lab.UPLOAD and s["lab_upload"]["transcript"] == "one two three"
    assert "<b>" not in s["lab_upload"]["name"]
    page = browser.run(press=[SCAN])
    assert "Forensic readout" in page
    assert lab.analysis_of(lab.UPLOAD)["pause_count"] == 2


def test_invalid_upload_shows_an_error_and_loads_nothing(game_db):
    browser, _ = open_lab()
    page = browser.run(press=["Load into the lab"], **{"WAV file": Upload("x.wav", b"RIFF garbage")})
    assert "not a readable PCM WAV" in page
    assert browser.st.session_state["lab_upload"] is None


def test_silent_upload_is_scanned_without_a_score(game_db):
    browser, _ = open_lab()
    browser.run(press=["Load into the lab"], **{"WAV file": Upload("quiet.wav", forensics.encode_wav(np.zeros(32000), 16000))})
    page = browser.run(press=[SCAN])
    assert "Signal unusable" in page and "silent" in page
    assert "/100" not in page


# ---------------------------------------------------------------- comparison

def test_comparison_shows_both_decks_and_the_differences(game_db):
    browser, _ = open_lab()
    browser.st.session_state["lab_mode"] = "Compare"
    page = browser.run()
    assert "Suspect voice comparison" in page and "Largest measured changes" in page
    assert '"mode":"compare"' in browser.st.iframes[0]
    assert "none of this shows that anyone lied" in page
    browser.run(press=["✎ Save comparison to notebook"])
    assert browser.st.session_state["lab_notebook"][-1]["kind"] == "compare"


def test_comparing_a_recording_with_itself_is_refused(game_db):
    browser, _ = open_lab()
    browser.st.session_state["lab_mode"] = "Compare"
    rid = recordings.DEFAULT_PAIR[0]
    page = browser.run(**{"Recording A": rid, "Recording B": rid})
    assert "two different recordings" in page and not browser.st.iframes


# ---------------------------------------------------------------- the audio clue

def test_isolating_and_connecting_the_bell(game_db):
    browser, _ = open_lab()
    browser.st.session_state["lab_mode"] = "Audio evidence"
    page = browser.run()
    assert "Bell strikes behind the voice" in page and "Connect the sound" not in page
    page = browser.run(press=["◎ Isolate the 3.6–5.8 kHz band"])
    assert '<div class="n">11</div>' in page
    assert "Connect the sound to the investigation" in page


def test_a_wrong_card_explains_and_logs_nothing():
    class S(dict):
        pass
    lab.st = type("St", (), {"session_state": S()})
    lab.state()
    assert lab.connect("elevator") is False
    assert lab.st.session_state["lab_wrong"] == "elevator" and lab.st.session_state["lab_notebook"] == []
    assert lab.connect("nonsense") is False
    assert lab.connect("bell") is True and lab.connect("bell") is True
    notes = lab.st.session_state["lab_notebook"]
    assert len(notes) == 1 and notes[0]["kind"] == "clue"     # connecting twice logs once


def test_the_connected_clue_appears_in_the_notebook(game_db):
    browser, _ = open_lab()
    browser.st.session_state.update({"lab_mode": "Audio evidence", "lab_isolated": True})
    browser.run(press=["Connect this evidence"])     # the first card is the bell
    assert browser.st.session_state["lab_connected"] == "bell"
    page = browser.run()
    assert "The 23:30 check-in was spoken at 23:00" in page
    browser.st.session_state["lab_mode"] = "Notebook"
    page = browser.run()
    assert "Audio evidence" in page and "detective-notebook.md" in browser.st.downloads
    browser.run(press=["Clear the notebook"])
    assert browser.st.session_state["lab_notebook"] == []


# ---------------------------------------------------------------- guided demo

def test_guided_demo_walks_all_steps(game_db):
    browser = LabBrowser(lab="demo")
    page = browser.run()
    assert "Guided demo · step 1 of 9" in page
    for _ in range(len(lab.DEMO_STEPS) - 1):
        page = browser.run(press=["Next step ▸"])
    s = browser.st.session_state
    assert s["lab_demo"] == len(lab.DEMO_STEPS) - 1
    assert recordings.DEFAULT_PAIR[1] in s["lab_scanned"]            # the scan ran
    assert s["lab_connected"] == "bell"                               # the clue is connected
    assert any(e["kind"] == "clue" for e in s["lab_notebook"])
    browser.run(press=["Finish demo ✓"])
    assert browser.st.session_state["lab_demo"] is None
    assert 60 <= sum(step["seconds"] for step in lab.DEMO_STEPS) <= 90


def test_demo_can_go_back_and_exit(game_db):
    browser = LabBrowser(lab="demo")
    browser.run()
    browser.run(press=["Next step ▸"])
    browser.run(press=["◂ Previous"])
    assert browser.st.session_state["lab_demo"] == 0
    browser.run(press=["Exit demo"])
    assert browser.st.session_state["lab_demo"] is None
    browser.run()                                                    # the demo does not restart
    assert browser.st.session_state["lab_demo"] is None


# ---------------------------------------------------------------- HTML safety

def test_lab_html_escapes_user_text():
    meta = {"title": "<script>x</script>", "suspect": "<img src=x>", "context": "$1", "logged": "a",
            "transcript": "<b>hi</b>", "source_note": "n", "synthetic": False}
    analysis = forensics.analyze(np.zeros(100), 16000)
    for html in (lab_ui.tape_card(meta), lab_ui.context_card(meta),
                 lab_ui.report(meta, dict(analysis, duration=1.0), {"available": False, "reason": "r"})):
        assert "<script>" not in html and "<img" not in html and "<b>hi" not in html
        assert "\n\n" not in html


def test_iframe_document_cannot_be_closed_by_data():
    meta = {"title": "</script><script>alert(1)</script>", "suspect": "s", "synthetic": True}
    analysis = {"duration": 1.0, "envelope": {"low": [0], "high": [0]}, "pauses": []}
    doc = lab_ui.player_document("x", meta, analysis, b"RIFF", revealed=True)
    assert "</script><script>alert" not in doc
