"""The Voice Forensics Lab screen (Streamlit).

Opened with ?lab=1 (free analysis) or ?lab=demo (the guided demo for a presentation).
From a game, the phone links here in a new tab, so the seat in the game stays online.

Like app.py, this file only shows things and passes clicks on:
  forensics.py   measures the audio (pure NumPy)
  recordings.py  builds the bundled, synthetic recordings of case #001 and holds the clue
  lab_ui.py      builds the HTML (fragments and the interactive iframe players)

Everything the lab remembers (selected recording, scans, the notebook) lives in the
browser session only. Uploaded files are analysed in memory and never stored or sent anywhere.
There is no microphone recording.
"""

import hashlib
import re
import time

import altair as alt
import pandas as pd

import content
import forensics
import lab_ui
import recordings

st = None   # the streamlit module, handed in by app.py (see lab_screen)

SCAN_PACING = 0.25          # seconds each scan stage stays on screen (presentation pacing only)
UPLOAD = "upload"
MODES = ["Analyze", "Compare", "Audio evidence", "Notebook"]
MODE_LABELS = {"Analyze": "◉  Analyze", "Compare": "⇄  Compare", "Audio evidence": "◆  Audio evidence",
               "Notebook": "✎  Notebook"}

# The guided demo for professors: about 80 seconds. "mode" opens that section; "do" runs on entry.
DEMO_STEPS = [
    {"title": "1 · The Voice Forensics Lab", "seconds": 6, "mode": "Analyze", "do": None,
     "text": "The audio archive of case #001. Every measurement below is real signal processing of the "
             "recording. The tension score is a clearly labelled game mechanic."},
    {"title": "2 · Select a suspect's recording", "seconds": 6, "mode": "Analyze", "do": "select",
     "text": "We load the Security Guard's interrogation about the night of the murder."},
    {"title": "3 · Play the recording", "seconds": 12, "mode": "Analyze", "do": None,
     "text": "Press ▶ Play on the deck. Click anywhere on the waveform to jump. The recording is a "
             "synthetic sample made for the demo."},
    {"title": "4 · Initiate the forensic scan", "seconds": 6, "mode": "Analyze", "do": None,
     "text": "Press INITIATE FORENSIC SCAN. Each stage you see is the actual computation running: "
             "decoding, RMS energy, pause detection, spectrum, score."},
    {"title": "5 · The reveal", "seconds": 12, "mode": "Analyze", "do": "scan",
     "text": "The waveform opens with the detected pauses marked in amber. Below: energy over time with the "
             "pause threshold, the average spectrum and all measured values."},
    {"title": "6 · The fictional Nervousness Score", "seconds": 10, "mode": "Analyze", "do": "scan",
     "text": "A transparent, deterministic mix of volume variation, pauses and speech rate. "
             "It is fiction: voice analysis cannot detect lies."},
    {"title": "7 · Compare two recordings", "seconds": 12, "mode": "Compare", "do": "pair",
     "text": "Routine questions (A) against the night of the murder (B), on one synchronized timeline. "
             "Hover a deck to align both. The table shows what changed – not who lied."},
    {"title": "8 · Discover a real audio clue", "seconds": 10, "mode": "Audio evidence", "do": "isolate",
     "text": "The guard's radio check-in, logged at 23:30. Isolating the 3.6–5.8 kHz band reveals a bell "
             "behind the voice. The lab counts its strikes."},
    {"title": "9 · Connect it to the investigation", "seconds": 8, "mode": "Audio evidence", "do": "connect",
     "text": "Eleven strikes = the 23:00 bell from a witness note. The 23:30 entry was spoken half an hour "
             "early: the patrol log is false. The finding is now in the detective notebook."},
]


# ---------------------------------------------------------------- small helpers

def show(html):
    st.markdown(html, unsafe_allow_html=True)


def state():
    s = st.session_state
    defaults = {"lab_sel": recordings.DEFAULT_PAIR[1], "lab_scanned": [], "lab_upload": None,
                "lab_mode": MODES[0], "lab_isolated": False, "lab_connected": None, "lab_wrong": None,
                "lab_notebook": [], "lab_demo": None}
    for key, value in defaults.items():
        if key not in s:
            s[key] = value if not isinstance(value, list) else list(value)
    return s


def go(mode):
    """Open another section on the next run (a widget's value cannot change after it is drawn)."""
    st.session_state["lab_mode_next"] = mode
    st.rerun()


def iframe(document, height):
    components = getattr(st, "components", None)
    html = getattr(getattr(components, "v1", None), "html", None)
    if callable(html):
        html(document, height=height, scrolling=False)
    else:   # only without a real Streamlit (tests)
        st.markdown("[interactive player]")


class _NoStatus:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def update(self, **kwargs):
        pass

    def write(self, *args):
        pass


def status_box(label):
    box = st.status(label, expanded=True) if hasattr(st, "status") else None
    return box if hasattr(box, "__enter__") else _NoStatus()


# ---------------------------------------------------------------- recordings and analyses

_CACHE = {}   # deterministic results of the bundled recordings, shared by every session


def _cached(key, make):
    if key not in _CACHE:
        _CACHE[key] = make()
    return _CACHE[key]


def bundled_meta(rid):
    spec = recordings.RECORDINGS[rid]
    meta = {"title": spec["title"], "suspect": spec["suspect"], "context": spec["context"],
            "logged": spec["logged"], "transcript": recordings.transcript(rid), "synthetic": True,
            "source_note": recordings.SYNTHETIC_NOTE}
    if spec.get("bell"):
        meta["bell_note"] = ("A bell rings behind the voice. It adds energy inside the pauses, which raises "
                             "the measured volume variation – one more reason the score proves nothing.")
    return meta


def items():
    """Every recording the lab can show: the bundled ones, plus the upload of this session."""
    ids = list(recordings.RECORDINGS)
    if st.session_state.get("lab_upload"):
        ids.append(UPLOAD)
    return ids


def meta_of(rid):
    if rid == UPLOAD:
        up = st.session_state["lab_upload"]
        return {"title": up["name"], "suspect": "Unknown speaker (your upload)", "context": "Uploaded in this session.",
                "logged": "your file", "transcript": up["transcript"] or None, "synthetic": False,
                "source_note": "Your WAV file – analysed in memory, never stored or uploaded anywhere."}
    return bundled_meta(rid)


def wav_of(rid):
    if rid == UPLOAD:
        return st.session_state["lab_upload"]["wav"]
    return _cached(("wav", rid), lambda: recordings.wav_bytes(rid))


def samples_of(rid):
    if rid == UPLOAD:
        up = st.session_state["lab_upload"]
        return forensics.decode_wav(up["wav"])
    return _cached(("samples", rid), lambda: forensics.decode_wav(wav_of(rid)))


def analysis_of(rid):
    if rid == UPLOAD:
        up = st.session_state["lab_upload"]
        key = ("analysis", up["hash"], up["transcript"])
        store = st.session_state.setdefault("lab_upload_cache", {})
        if key not in store:
            store.clear()
            samples, rate = samples_of(rid)
            store[key] = forensics.analyze(samples, rate, up["transcript"] or None)
        return store[key]
    return _cached(("analysis", rid), lambda: forensics.analyze(*samples_of(rid), recordings.transcript(rid)))


def label_of(rid):
    meta = meta_of(rid)
    return f"{meta['suspect']} — {meta['title']}"


def clue_onsets():
    clue = recordings.CLUE
    samples, rate = samples_of(clue["recording"])
    return _cached(("onsets",), lambda: forensics.band_onsets(samples, rate, *clue["segment"], *clue["band"]))


def isolated_wav():
    clue = recordings.CLUE
    samples, rate = samples_of(clue["recording"])
    return _cached(("isolated",), lambda: forensics.encode_wav(forensics.band_pass(samples, rate, *clue["band"]), rate))


# ---------------------------------------------------------------- charts (Altair, ships with Streamlit)

def _style(chart, height):
    return (chart.properties(height=height, background="transparent")
            .configure_view(strokeOpacity=0)
            .configure_axis(labelColor="#94A3B8", titleColor="#94A3B8", gridColor="#1E293B",
                            domainColor="#334155", tickColor="#334155", labelFont="Courier Prime",
                            titleFont="Courier Prime", titleFontWeight="normal")
            .configure_legend(labelColor="#CBD5E1", titleColor="#94A3B8"))


def level_chart(analysis):
    hop = analysis["frames"]["hop"]
    db = analysis["frames"]["db"]
    step = max(1, len(db) // 1500)
    frame = pd.DataFrame({"t": [i * hop for i in range(0, len(db), step)], "level": db[::step]})
    floor = max(-90.0, min(frame["level"].min(), (analysis.get("noise_floor_db") or -80) - 6))
    frame["floor"] = floor
    base = alt.Chart(frame).encode(x=alt.X("t:Q", title="time (s)", scale=alt.Scale(nice=False)))
    area = base.mark_area(color="#22D3EE", opacity=0.28, line={"color": "#22D3EE", "strokeWidth": 1.2}).encode(
        y=alt.Y("level:Q", title="RMS level (dBFS)", scale=alt.Scale(domain=[floor, 0])), y2="floor:Q",
        tooltip=[alt.Tooltip("t:Q", title="time s", format=".2f"), alt.Tooltip("level:Q", title="dBFS", format=".1f")])
    layers = []
    pauses = analysis.get("pauses") or []
    if pauses:
        pf = pd.DataFrame(pauses)
        layers.append(alt.Chart(pf).mark_rect(color="#F5B841", opacity=0.16).encode(
            x="start:Q", x2="end:Q",
            tooltip=[alt.Tooltip("start:Q", format=".2f"), alt.Tooltip("end:Q", format=".2f"),
                     alt.Tooltip("length:Q", title="pause s", format=".2f")]))
    layers.append(area)
    if analysis.get("threshold_db") is not None:
        layers.append(alt.Chart(pd.DataFrame({"y": [analysis["threshold_db"]]})).mark_rule(
            color="#F5B841", strokeDash=[5, 4]).encode(y="y:Q", tooltip=[alt.Tooltip("y:Q", title="pause threshold dBFS")]))
    return _style(alt.layer(*layers).interactive(bind_y=False), 230)


def spectrum_chart(spectrum):
    curve = pd.DataFrame({"hz": spectrum["curve"]["hz"], "db": spectrum["curve"]["db"]})
    low = min(-80.0, float(curve["db"].min()))
    curve["low"] = low
    base = alt.Chart(curve).encode(x=alt.X("hz:Q", title="frequency (Hz, log)", scale=alt.Scale(type="log", nice=False)))
    area = base.mark_area(color="#F5B841", opacity=0.22, line={"color": "#F5B841", "strokeWidth": 1.4}).encode(
        y=alt.Y("db:Q", title="power (dB re peak)", scale=alt.Scale(domain=[low, 2])), y2="low:Q",
        tooltip=[alt.Tooltip("hz:Q", title="Hz", format=".0f"), alt.Tooltip("db:Q", title="dB", format=".1f")])
    rule = alt.Chart(pd.DataFrame({"hz": [spectrum["centroid_hz"]], "label": ["centroid"]})).mark_rule(
        color="#22D3EE", strokeDash=[4, 3]).encode(x="hz:Q", tooltip=["label:N", alt.Tooltip("hz:Q", format=".0f")])
    return _style(alt.layer(area, rule), 230)


def band_chart(found):
    frame = pd.DataFrame({"t": found["times"], "level": found["db"]})
    line = alt.Chart(frame).mark_line(color="#EF4444", strokeWidth=1.3).encode(
        x=alt.X("t:Q", title="time (s)", scale=alt.Scale(nice=False)),
        y=alt.Y("level:Q", title="band peak (dB re max)"),
        tooltip=[alt.Tooltip("t:Q", format=".2f"), alt.Tooltip("level:Q", format=".1f")])
    marks = alt.Chart(pd.DataFrame({"t": found["onsets"], "n": list(range(1, len(found["onsets"]) + 1))})).mark_rule(
        color="#F8FAFC", strokeWidth=1, opacity=0.7).encode(x="t:Q", tooltip=[alt.Tooltip("n:Q", title="strike"),
                                                                                  alt.Tooltip("t:Q", format=".2f")])
    return _style(alt.layer(line, marks), 190)


def chart(figure):
    st.altair_chart(figure, use_container_width=True, theme=None)


# ---------------------------------------------------------------- the screen

def lab_screen(streamlit_module):
    global st
    st = streamlit_module
    s = state()
    if st.query_params.get("lab") == "demo" and not s.get("lab_demo_started"):
        s["lab_demo_started"] = True
        start_demo()
    if "lab_mode_next" in s:
        s["lab_mode"] = s.pop("lab_mode_next")
    show(lab_ui.lab_style())

    left, _, right = st.columns([2, 3, 2])
    with left:
        if st.button("◂ Back to NOVA MYSTERY", key="lab_back"):
            if "lab" in st.query_params:
                del st.query_params["lab"]
            st.rerun()
    with right:
        if s["lab_demo"] is None and st.button("▶ Guided demo (≈80 s)", key="lab_demo_btn",
                                               use_container_width=True):
            start_demo()
            st.rerun()

    show(lab_ui.hero(content.CASE_NUMBER, content.CASE_TITLE, demo=s["lab_demo"] is not None))
    if s["lab_demo"] is not None:
        demo_controls()
    show(lab_ui.disclaimer())

    picked = st.radio("Lab section", MODES, key="lab_mode", horizontal=True,
                      format_func=lambda m: MODE_LABELS[m], label_visibility="collapsed")
    mode = picked if picked in MODES else s["lab_mode"]
    if mode == "Analyze":
        analyze_view()
    elif mode == "Compare":
        compare_view()
    elif mode == "Audio evidence":
        evidence_view()
    else:
        notebook_view()


# ---------------------------------------------------------------- guided demo

def start_demo():
    s = state()
    s["lab_demo"] = 0
    s["lab_mode_next"] = DEMO_STEPS[0]["mode"]


def demo_enter(index):
    s = state()
    step = DEMO_STEPS[index]
    action = step["do"]
    if action == "select":
        s["lab_sel"] = recordings.DEFAULT_PAIR[1]
    elif action == "scan":
        s["lab_sel"] = recordings.DEFAULT_PAIR[1]
        if recordings.DEFAULT_PAIR[1] not in s["lab_scanned"]:
            s["lab_autoscan"] = True
    elif action == "pair":
        s["lab_a"], s["lab_b"] = recordings.DEFAULT_PAIR
    elif action == "isolate":
        s["lab_isolated"] = True
    elif action == "connect":
        s["lab_isolated"] = True
        connect(recordings.CLUE["answer"])
    s["lab_demo"] = index
    s["lab_mode_next"] = step["mode"]


def demo_controls():
    s = state()
    index = s["lab_demo"]
    show(lab_ui.demo_panel(DEMO_STEPS, index))
    a, b, c = st.columns([1, 1, 1])
    last = index == len(DEMO_STEPS) - 1
    with a:
        if st.button("◂ Previous", key="demo_prev", disabled=index == 0, use_container_width=True):
            demo_enter(index - 1)
            st.rerun()
    with b:
        if st.button("Finish demo ✓" if last else "Next step ▸", key="demo_next", type="secondary",
                     use_container_width=True):
            if last:
                s["lab_demo"] = None
            else:
                demo_enter(index + 1)
            st.rerun()
    with c:
        if st.button("Exit demo", key="demo_exit", use_container_width=True):
            s["lab_demo"] = None
            st.rerun()


# ---------------------------------------------------------------- analyze

def analyze_view():
    s = state()
    if s["lab_sel"] not in items():
        s["lab_sel"] = recordings.DEFAULT_PAIR[1]
    show(lab_ui.section("Evidence locker", "Select a recording"))
    ids = items()
    for row in range(0, len(ids), 3):
        columns = st.columns(3)
        for column, rid in zip(columns, ids[row:row + 3]):
            with column:
                analysis = analysis_of(rid)
                show(lab_ui.tape_card(meta_of(rid), selected=rid == s["lab_sel"], scanned=rid in s["lab_scanned"],
                                      duration=analysis["duration"], has_clue=rid == recordings.CLUE["recording"]))
                chosen = rid == s["lab_sel"]
                if st.button("✓ Loaded" if chosen else "Load recording", key=f"lab_pick_{rid}",
                             disabled=chosen, use_container_width=True):
                    s["lab_sel"] = rid
                    st.rerun()
    upload_box()

    rid = s["lab_sel"]
    meta, analysis = meta_of(rid), analysis_of(rid)
    scanned = rid in s["lab_scanned"]
    show(lab_ui.section(meta["title"], f"Deck · {meta['suspect']}"))
    left, right = st.columns([3, 2])
    with right:
        show(lab_ui.context_card(meta))
    with left:
        with st.container(key="vfscan"):
            pressed = st.button("◎  INITIATE FORENSIC SCAN" if not scanned else "↻  Re-run forensic scan",
                                key="lab_scan", type="primary", use_container_width=True)
        if pressed or s.pop("lab_autoscan", False):
            run_scan(rid)
            scanned = True
        if not scanned:
            st.caption("Play the tape first if you like – then scan it. Nothing is analysed until you do.")
    clue = recordings.CLUE["segment"] if scanned and rid == recordings.CLUE["recording"] else None
    iframe(lab_ui.player_document(rid, meta, analysis, wav_of(rid), revealed=scanned, clue=clue),
           lab_ui.player_height("single"))
    if scanned:
        results(rid, meta, analysis)


def upload_box():
    s = state()
    with st.expander("⇪  Analyse your own recording (WAV, up to 5 MB and 60 s)"):
        st.caption("PCM WAV only. The file is analysed in memory for this session and never stored or sent "
                   "anywhere. The lab never records from a microphone.")
        file = st.file_uploader("WAV file", type=["wav"], key="lab_file")
        typed = st.text_area("Transcript (optional – needed for speech rate)", key="lab_transcript",
                             max_chars=2000, placeholder="Type what is said in the recording …")
        if st.button("Load into the lab", key="lab_load", disabled=file is None):
            data = file.getvalue() if file is not None else b""
            try:
                forensics.decode_wav(data)
            except forensics.AudioError as problem:
                st.error(str(problem))
                return
            name = re.sub(r"[^\w .()-]", "", getattr(file, "name", "upload.wav"))[:60] or "upload.wav"
            s["lab_upload"] = {"name": name, "wav": data, "transcript": (typed or "").strip()[:2000],
                               "hash": hashlib.sha256(data).hexdigest()}
            s["lab_scanned"] = [r for r in s["lab_scanned"] if r != UPLOAD]
            s.pop("lab_upload_cache", None)
            s["lab_sel"] = UPLOAD
            st.rerun()


def run_scan(rid):
    """The cinematic scan. Every stage label is shown while that computation actually runs."""
    s = state()
    with status_box("Initializing audio analysis…") as box:
        started = time.perf_counter()
        wav = wav_of(rid)
        box.write(f"› Loaded {len(wav) / 1024:.0f} KB of PCM audio.")
        time.sleep(SCAN_PACING)
        box.update(label="Processing acoustic signal…")
        samples, rate = (forensics.decode_wav(wav) if rid == UPLOAD else samples_of(rid))
        box.write(f"› Decoded {len(samples):,} samples at {rate} Hz.")
        time.sleep(SCAN_PACING)
        box.update(label="Detecting pauses…")
        if rid == UPLOAD:
            s.pop("lab_upload_cache", None)
        analysis = analysis_of(rid)
        if analysis["ok"]:
            box.write(f"› {len(analysis['frames']['db']):,} RMS frames · "
                      f"{analysis['pause_count'] if analysis['pause_count'] is not None else 'no'} pauses found.")
        else:
            box.write(f"› {analysis['reason']}")
        time.sleep(SCAN_PACING)
        box.update(label="Calculating experimental tension index…")
        score = forensics.tension_score(analysis)
        box.write("› " + (f"Fictional index {score['score']}/100." if score["available"] else "No score: " + score["reason"]))
        time.sleep(SCAN_PACING)
        took = time.perf_counter() - started - 4 * SCAN_PACING
        box.update(label=f"Analysis complete. ({max(0.0, took) * 1000:.0f} ms of computation)",
                   state="complete" if analysis["ok"] else "error", expanded=False)
    if rid not in s["lab_scanned"]:
        s["lab_scanned"] = s["lab_scanned"] + [rid]


def results(rid, meta, analysis):
    s = state()
    if not analysis["ok"]:
        show(lab_ui.unusable(analysis["reason"]))
        return
    score = forensics.tension_score(analysis)
    show(lab_ui.section("Forensic readout", "Measured signal"))
    g, m = st.columns([1, 2])
    with g:
        show(lab_ui.gauge(score))
    with m:
        show(lab_ui.metric_grid(analysis))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="vf-kicker">Energy over time · pauses in amber · drag to pan, scroll to zoom</div>',
                    unsafe_allow_html=True)
        chart(level_chart(analysis))
    with c2:
        st.markdown('<div class="vf-kicker">Average spectrum of the speech frames</div>', unsafe_allow_html=True)
        if analysis.get("spectrum"):
            chart(spectrum_chart(analysis["spectrum"]))
            show(lab_ui.bands(analysis["spectrum"]))
        else:
            st.caption("Spectrum unavailable for this recording.")
    show(lab_ui.notes(analysis, [meta["bell_note"]] if meta.get("bell_note") else []))
    with st.expander("How the fictional score is computed"):
        show(lab_ui.score_breakdown(score))
    if rid == recordings.CLUE["recording"]:
        st.warning("◆ The analyst flagged a background anomaly in this recording.")
        if st.button("Inspect the background sound ▸", key="lab_to_clue"):
            go("Audio evidence")

    show(lab_ui.section("Investigation report", "Ready for the notebook"))
    clue_found = rid == recordings.CLUE["recording"] and s["lab_connected"] == recordings.CLUE["answer"]
    show(lab_ui.report(meta, analysis, score, clue_found))
    text = lab_ui.report_text(meta, analysis, score, clue_found,
                              recordings.CLUE["notebook"] if clue_found else None)
    title = f"{meta['suspect']} – {meta['title']}"
    saved = any(e["title"] == title and e["kind"] == "report" for e in s["lab_notebook"])
    a, b = st.columns(2)
    with a:
        if st.button("✓ Saved in the notebook" if saved else "✎ Save to detective notebook", key="lab_save",
                     disabled=saved, use_container_width=True):
            summary = (f"{analysis['pause_count']} pauses, volume variation "
                       f"{lab_ui.fmt(analysis.get('level_spread_db'), 1, 'dB', 'n/a')}, speech rate "
                       f"{lab_ui.fmt(analysis.get('speech_rate_wpm'), 0, 'wpm', 'n/a')}. Fictional index: "
                       + (f"{score['score']}/100." if score["available"] else "unavailable."))
            note(kind="report", title=title, summary=summary, text=text)
            st.rerun()
    with b:
        st.download_button("⤓ Download report (.md)", data=text, file_name=_file_name(meta["title"]),
                           mime="text/markdown", key="lab_dl", use_container_width=True)


def _file_name(title):
    return "forensic-report-" + (re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "recording") + ".md"


def note(kind, title, summary, text):
    s = state()
    s["lab_notebook"] = s["lab_notebook"] + [{"kind": kind, "title": title, "summary": summary, "text": text}]


# ---------------------------------------------------------------- compare

def compare_view():
    s = state()
    ids = items()
    s.setdefault("lab_a", recordings.DEFAULT_PAIR[0])
    s.setdefault("lab_b", recordings.DEFAULT_PAIR[1])
    for key in ("lab_a", "lab_b"):
        if s[key] not in ids:
            s[key] = recordings.DEFAULT_PAIR[0 if key == "lab_a" else 1]
    show(lab_ui.section("Suspect voice comparison", "Two recordings · one timeline"))
    left, right = st.columns(2)
    with left:
        a = st.selectbox("Recording A", ids, format_func=label_of, key="lab_a")
    with right:
        b = st.selectbox("Recording B", ids, format_func=label_of, key="lab_b")
    if a == b:
        st.info("Choose two different recordings to compare.")
        return
    ma, mb = meta_of(a), meta_of(b)
    aa, ab = analysis_of(a), analysis_of(b)
    broken = [(m, x) for m, x in ((ma, aa), (mb, ab)) if not x["ok"]]
    for m, x in broken:
        show(lab_ui.unusable(f"{m['title']}: {x['reason']}"))
    if broken:
        return
    iframe(lab_ui.compare_document((a, ma, aa, wav_of(a)), (b, mb, ab, wav_of(b))), lab_ui.player_height("compare"))
    sa, sb = forensics.tension_score(aa), forensics.tension_score(ab)
    g1, g2, t = st.columns([1, 1, 2])
    with g1:
        show(lab_ui.gauge(sa, "A · fictional tension"))
    with g2:
        show(lab_ui.gauge(sb, "B · fictional tension"))
    rows = forensics.compare(aa, ab)
    changes = forensics.biggest_changes(rows)
    with t:
        show(lab_ui.change_summary(changes))
    show(lab_ui.compare_table(rows, ma["title"], mb["title"]))
    show(lab_ui.disclaimer(compact=True))
    title = f"Comparison: {ma['title']} vs {mb['title']}"
    saved = any(e["title"] == title for e in s["lab_notebook"])
    if st.button("✓ Comparison saved" if saved else "✎ Save comparison to notebook", key="lab_save_cmp", disabled=saved):
        summary = "; ".join(f"{r['label']} {'+' if r['delta'] > 0 else ''}{r['relative'] * 100:.0f}%" for r in changes) \
            or "No characteristic changed by 10% or more."
        lines = [f"# {title}", ""] + [
            f"- {r['label']}: A {lab_ui.fmt(r['a'], r['digits'], r['unit'], 'n/a')} · "
            f"B {lab_ui.fmt(r['b'], r['digits'], r['unit'], 'n/a')}" for r in rows] + ["", f"_{forensics.DISCLAIMER}_"]
        note(kind="compare", title=title, summary=summary + " (measured differences, not evidence of lying)",
             text="\n".join(lines))
        st.rerun()


# ---------------------------------------------------------------- audio evidence

def connect(key):
    """The player links the sound to a piece of evidence. Only the right card logs the clue."""
    s = state()
    if key not in recordings.EVIDENCE:
        return False
    if key != recordings.CLUE["answer"]:
        s["lab_wrong"] = key
        return False
    s["lab_wrong"] = None
    if s["lab_connected"] != key:
        s["lab_connected"] = key
        clue = recordings.CLUE
        note(kind="clue", title="Audio evidence: the 23:30 check-in was spoken at 23:00",
             summary=clue["notebook"], text=f"# Audio evidence\n\n{clue['conclusion']}\n")
    return True


def evidence_view():
    s = state()
    clue = recordings.CLUE
    rid = clue["recording"]
    meta, analysis = meta_of(rid), analysis_of(rid)
    show(lab_ui.section("Background sounds", "Audio evidence · " + meta["suspect"]))
    found = clue_onsets() if s["lab_isolated"] else None
    left, right = st.columns([3, 2])
    with right:
        show(lab_ui.context_card(meta))
    with left:
        show(lab_ui.clue_brief(clue, found))
        if not s["lab_isolated"]:
            if st.button(f"◎ Isolate the {clue['band'][0] / 1000:.1f}–{clue['band'][1] / 1000:.1f} kHz band",
                         key="lab_isolate", type="primary", use_container_width=True):
                s["lab_isolated"] = True
                st.rerun()
    iframe(lab_ui.player_document(rid, meta, analysis, wav_of(rid), revealed=True, clue=clue["segment"],
                                  onsets=found["onsets"] if found else None), lab_ui.player_height("single"))
    if not found:
        st.caption("The highlighted stretch is where the analyst heard something. Use “Loop anomaly” on the deck, "
                   "then isolate the band to measure it.")
        return
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown('<div class="vf-kicker">Strongest tonal peak in the band · white lines = detected strikes</div>',
                    unsafe_allow_html=True)
        chart(band_chart(found))
    with c2:
        st.markdown('<div class="vf-kicker">Listen to the isolated band (voice removed by the filter)</div>',
                    unsafe_allow_html=True)
        st.audio(isolated_wav(), format="audio/wav")
        st.caption(f"{found['count']} strikes, about {found['dominant_hz']:.0f} Hz. A real FFT band-pass of "
                   "the recording – nothing is added.")

    show(lab_ui.section("Connect the sound to the investigation", "Which evidence explains it?"))
    keys = list(recordings.EVIDENCE)
    for row in range(0, len(keys), 2):
        columns = st.columns(2)
        for column, key in zip(columns, keys[row:row + 2]):
            card = recordings.EVIDENCE[key]
            with column:
                show(lab_ui.evidence_card(key, card, chosen=key in (s["lab_connected"], s["lab_wrong"])))
                done = s["lab_connected"] == key
                if st.button("✓ Connected" if done else "Connect this evidence", key=f"lab_link_{key}",
                             disabled=done, use_container_width=True):
                    connect(key)
                    st.rerun()
    if s["lab_wrong"] and not s["lab_connected"]:
        st.warning("That does not fit: " + recordings.EVIDENCE[s["lab_wrong"]]["feedback"])
    if s["lab_connected"]:
        show(lab_ui.conclusion(clue))
        st.success("Logged in the detective notebook.")
        if st.button("Open the notebook ▸", key="lab_to_notes"):
            go("Notebook")


# ---------------------------------------------------------------- notebook

def notebook_view():
    s = state()
    show(lab_ui.section("Detective notebook", "This browser session only"))
    entries = s["lab_notebook"]
    if not entries:
        st.info("Nothing saved yet. Scan a recording and save its report, or connect an audio clue.")
        return
    for number, entry in enumerate(entries, start=1):
        show(lab_ui.notebook_entry(entry, number))
    everything = "\n\n---\n\n".join(e["text"] for e in entries)
    a, b = st.columns(2)
    with a:
        st.download_button("⤓ Download the notebook (.md)", data=everything, file_name="detective-notebook.md",
                           mime="text/markdown", key="lab_dl_notes", use_container_width=True)
    with b:
        if st.button("Clear the notebook", key="lab_clear", use_container_width=True):
            s["lab_notebook"] = []
            st.rerun()
