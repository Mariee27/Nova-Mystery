"""HTML building blocks of the Voice Forensics Lab.

Pure functions: plain data in, an HTML string out (no Streamlit, no audio processing).

Two kinds of output:
  * fragments for st.markdown (hero, gauge, metric cards, report ...). Every text passes
    through ui.h(), and the strings never contain blank lines, like everywhere in ui.py.
  * complete little documents for an iframe (the interactive player and the comparison deck),
    shown with streamlit.components.v1.html. They carry their own CSS and a small script that
    draws the waveform and moves the playhead. Data goes in as JSON, escaped for <script>.
"""

import base64
import json
import math
import pathlib

import forensics
from ui import h

STYLE_FILE = pathlib.Path(__file__).with_name("lab.css")

CYAN, AMBER, RED = "#22D3EE", "#F5B841", "#EF4444"


def lab_style():
    return "<style>" + STYLE_FILE.read_text(encoding="utf-8") + "</style>"


def fmt(value, digits=1, unit="", missing="unavailable"):
    if value is None:
        return missing
    if digits == 0:
        text = f"{value:,.0f}"
    else:
        text = f"{value:,.{digits}f}"
    return f"{text} {unit}".strip()


def clock(seconds):
    seconds = max(0.0, float(seconds or 0))
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


# ---------------------------------------------------------------- header and notices

def hero(case_number, case_title, demo=False):
    chips = [("DSP engine", "online", "ok"), ("Speech recognition", "not used", "off"),
             ("Microphone", "off", "off"), ("Mode", "guided demo" if demo else "free analysis", "ok")]
    chip_html = "".join(f'<span class="vf-chip {cls}"><i></i>{h(k)}: <b>{h(v)}</b></span>'
                        for k, v, cls in chips)
    return ('<div class="vf-hero"><div class="vf-grid"></div><div class="vf-sweep"></div>'
            f'<div class="vf-kicker">Case #{h(case_number)} · {h(case_title)} · Audio archive</div>'
            '<div class="vf-title">VOICE <b>FORENSICS</b></div>'
            '<div class="vf-sub">The experimental lie detector &#8212; real signal analysis, '
            'fictional verdicts.</div>'
            f'<div class="vf-chips">{chip_html}</div>'
            f'{_hero_wave()}</div>')


def _hero_wave():
    """A decorative oscilloscope line (fixed shape, purely visual)."""
    points = []
    for i in range(121):
        x = i * 1000 / 120
        y = 30 + 18 * math.sin(i * 0.42) * math.exp(-((i - 60) / 38) ** 2) + 5 * math.sin(i * 1.7)
        points.append(f"{x:.1f},{y:.1f}")
    return ('<svg class="vf-heroline" viewBox="0 0 1000 60" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline points="{" ".join(points)}"/></svg>')


def disclaimer(compact=False):
    cls = " compact" if compact else ""
    return (f'<div class="vf-disclaimer{cls}" role="note"><span class="vf-warn">!</span>'
            f'<div><b>Fiction notice.</b> {h(forensics.DISCLAIMER)} The score below is a game '
            'mechanic. Timeline contradictions and identifiable sounds are the real evidence.</div></div>')


def section(title, kicker=""):
    k = f'<div class="vf-kicker">{h(kicker)}</div>' if kicker else ""
    return f'<div class="vf-section">{k}<div class="vf-h">{h(title)}</div></div>'


# ---------------------------------------------------------------- recording shelf

def tape_card(meta, selected=False, scanned=False, duration=None, has_clue=False):
    status = "Scanned" if scanned else "Not analysed"
    cls = " selected" if selected else ""
    clue = '<span class="vf-tag red">Anomaly flagged</span>' if has_clue and scanned else ""
    dur = f'<span class="vf-tag">{h(clock(duration))}</span>' if duration else ""
    synthetic = '<span class="vf-tag ghost">Synthetic</span>' if meta.get("synthetic", True) else '<span class="vf-tag ghost">Upload</span>'
    return (f'<div class="vf-tape{cls}"><div class="vf-reel"><i></i><i></i></div>'
            f'<div class="vf-tape-body"><div class="vf-tape-suspect">{h(meta["suspect"])}</div>'
            f'<div class="vf-tape-title">{h(meta["title"])}</div>'
            f'<div class="vf-tape-tags"><span class="vf-tag {"cyan" if scanned else ""}">{h(status)}</span>'
            f'{dur}{synthetic}{clue}</div></div></div>')


def context_card(meta):
    rows = [("Suspect", meta["suspect"]), ("Logged", meta.get("logged", "–")),
            ("Context", meta.get("context", "–")), ("Source", meta.get("source_note", "–"))]
    table = "".join(f"<tr><td>{h(k)}</td><td>{h(v)}</td></tr>" for k, v in rows)
    transcript = meta.get("transcript")
    t_html = (f'<div class="vf-transcript"><span>Transcript (typed, not recognised)</span>'
              f'&#8220;{h(transcript)}&#8221;</div>' if transcript else
              '<div class="vf-transcript muted"><span>Transcript</span>None supplied &#8212; '
              'speech rate will be unavailable.</div>')
    return f'<div class="vf-panel vf-context"><table>{table}</table>{t_html}</div>'


# ---------------------------------------------------------------- the fictional gauge

def gauge(score, title="Experimental tension index"):
    """Semicircle gauge. score: forensics.tension_score(...)."""
    if not score.get("available"):
        return (f'<div class="vf-panel vf-gauge na"><div class="vf-kicker">{h(title)}</div>'
                '<div class="vf-gauge-na">NO SCORE</div>'
                f'<div class="vf-gauge-reason">{h(score.get("reason", ""))}</div>'
                '<div class="vf-fiction">Fictional game mechanic</div></div>')
    value = max(0, min(100, int(score["score"])))
    r = 90
    length = math.pi * r
    offset = length * (1 - value / 100)
    angle = -90 + 180 * value / 100
    level = "low" if value < 25 else "mid" if value < 50 else "elev" if value < 75 else "high"
    ticks = "".join(
        f'<line x1="{100 + 98 * math.cos(math.pi * (1 - t / 100)):.1f}" y1="{105 - 98 * math.sin(math.pi * (1 - t / 100)):.1f}" '
        f'x2="{100 + 108 * math.cos(math.pi * (1 - t / 100)):.1f}" y2="{105 - 108 * math.sin(math.pi * (1 - t / 100)):.1f}"/>'
        for t in range(0, 101, 10))
    return (f'<div class="vf-panel vf-gauge {level}"><div class="vf-kicker">{h(title)}</div>'
            f'<svg viewBox="-10 -10 220 130" role="img" aria-label="Fictional tension {value} of 100, {h(score["label"])}">'
            '<defs><linearGradient id="vfg" x1="0" x2="1"><stop offset="0" stop-color="#22D3EE"/>'
            '<stop offset=".55" stop-color="#F5B841"/><stop offset="1" stop-color="#EF4444"/></linearGradient></defs>'
            f'<g class="ticks">{ticks}</g>'
            f'<path class="track" d="M10,105 A{r},{r} 0 0 1 190,105"/>'
            f'<path class="value" d="M10,105 A{r},{r} 0 0 1 190,105" stroke-dasharray="{length:.1f}" '
            f'style="--len:{length:.1f};--off:{offset:.1f}" stroke-dashoffset="{offset:.1f}"/>'
            f'<g class="needle" style="--angle:{angle:.1f}deg;transform:rotate({angle:.1f}deg)">'
            '<line x1="100" y1="105" x2="100" y2="28"/><circle cx="100" cy="105" r="6"/></g>'
            '</svg>'
            f'<div class="vf-gauge-num">{value}<small>/100</small></div>'
            f'<div class="vf-gauge-label">{h(score["label"])}</div>'
            '<div class="vf-fiction">Fictional game mechanic &#8212; not a lie detector</div></div>')


def score_breakdown(score):
    if not score.get("available"):
        return f'<div class="vf-panel muted">{h(score.get("reason", "No score."))}</div>'
    rows = []
    for term in score["terms"]:
        if term["raw"] is None:
            rows.append(f'<tr class="off"><td>{h(term["label"])}</td><td colspan="4">unavailable &#8212; '
                        'weight moved to the other terms</td></tr>')
            continue
        low, high = term["range"]
        raw = f'{term["raw"]:.3g} {term["unit"]}'.strip()
        rows.append(
            f'<tr><td>{h(term["label"])}</td><td>{h(raw)}</td>'
            f'<td>{h(f"{low:g} → {high:g}")}</td>'
            f'<td><div class="vf-bar"><i style="width:{term["normalized"] * 100:.0f}%"></i></div>'
            f'{term["normalized"]:.2f}</td><td>× {term["weight"]:.2f} = <b>{term["points"]:.1f}</b></td></tr>')
    return ('<div class="vf-panel vf-breakdown"><table><tr><th>Measured term</th><th>Value</th>'
            '<th>Mapped 0&#8594;1 over</th><th>Normalised</th><th>Points</th></tr>'
            f'{"".join(rows)}<tr class="sum"><td colspan="4">Fictional tension index (sum, rounded)</td>'
            f'<td><b>{score["score"]}</b></td></tr></table>'
            '<div class="vf-small">Deterministic: the same recording always gives the same number. '
            'Speech-rate deviation is |articulation rate &#8722; 150 wpm| / 150 and needs a transcript.</div></div>')


# ---------------------------------------------------------------- measurements

def metric_grid(analysis):
    spec = analysis.get("spectrum") or {}
    cells = [
        ("Duration", clock(analysis["duration"]), f'{analysis["rate"]} Hz sample rate'),
        ("Pauses", fmt(analysis.get("pause_count"), 0, missing="n/a"),
         f'longest {fmt(analysis.get("longest_pause"), 2, "s", "n/a")}'),
        ("Time in pauses", fmt(None if analysis.get("pause_ratio") is None else analysis["pause_ratio"] * 100, 0, "%", "n/a"),
         f'{fmt(analysis.get("pause_total"), 2, "s", "n/a")} of {fmt(analysis.get("speech_span"), 1, "s", "n/a")} speech span'),
        ("Volume variation", fmt(analysis.get("level_spread_db"), 1, "dB", "n/a"),
         f'5–95% range {fmt(analysis.get("level_range_db"), 1, "dB", "n/a")}'),
        ("Speech rate", fmt(analysis.get("speech_rate_wpm"), 0, "wpm", "n/a"),
         "approx., from transcript" if analysis.get("speech_rate_wpm") else "needs a transcript"),
        ("Articulation", fmt(analysis.get("articulation_wpm"), 0, "wpm", "n/a"), "words per minute without pauses"),
        ("Peak / RMS", f'{fmt(analysis.get("peak_dbfs"), 1)} / {fmt(analysis.get("rms_dbfs"), 1)}', "dBFS"),
        ("Contrast", fmt(analysis.get("contrast_db"), 1, "dB", "n/a"),
         f'pause threshold {fmt(analysis.get("threshold_db"), 1, "dBFS", "n/a")}'),
        ("Spectral centroid", fmt(spec.get("centroid_hz"), 0, "Hz", "n/a"),
         f'roll-off 85% {fmt(spec.get("rolloff_hz"), 0, "Hz", "n/a")}'),
        ("Dominant frequency", fmt(spec.get("dominant_hz"), 0, "Hz", "n/a"),
         f'flatness {fmt(spec.get("flatness"), 3, "", "n/a")}'),
    ]
    html = "".join(f'<div class="vf-metric" style="animation-delay:{i * 0.06:.2f}s"><div class="k">{h(k)}</div>'
                   f'<div class="v">{h(v)}</div><div class="d">{h(d)}</div></div>'
                   for i, (k, v, d) in enumerate(cells))
    return f'<div class="vf-metrics">{html}</div>'


def bands(spectrum):
    if not spectrum:
        return ""
    parts = "".join(
        f'<div class="vf-band"><div class="k">{h(b["name"])} <span>{b["low"]}–{b["high"]} Hz</span></div>'
        f'<div class="vf-bar"><i style="width:{b["share"] * 100:.1f}%"></i></div>'
        f'<div class="v">{b["share"] * 100:.1f}%</div></div>' for b in spectrum["bands"])
    return f'<div class="vf-panel vf-bands"><div class="vf-kicker">Energy by band</div>{parts}</div>'


def notes(analysis, extra=()):
    items = list(analysis.get("notes") or []) + list(extra)
    if not items:
        return ""
    lis = "".join(f"<li>{h(n)}</li>" for n in items)
    return f'<div class="vf-panel vf-notes"><div class="vf-kicker">Analyst notes</div><ul>{lis}</ul></div>'


def unusable(reason):
    return (f'<div class="vf-panel vf-unusable"><div class="vf-kicker">Analysis aborted</div>'
            f'<div class="vf-h">Signal unusable</div><p>{h(reason)}</p>'
            '<p class="vf-small">No measurement and no score were produced for this file.</p></div>')


# ---------------------------------------------------------------- report

def investigative_notes(meta, analysis, score, clue_found=False):
    lines = []
    if analysis.get("pause_count") is not None:
        lines.append(f"{analysis['pause_count']} pauses of 0.25 s or longer were measured inside the speech.")
    if analysis.get("speech_rate_wpm"):
        lines.append(f"With the supplied transcript the speaker averages about "
                     f"{analysis['speech_rate_wpm']:.0f} words per minute.")
    if meta.get("bell_note"):
        lines.append(meta["bell_note"])
    if clue_found:
        lines.append("Audio evidence linked: the background bell dates this check-in to about 23:00.")
    lines.append("Measured differences in voice are not evidence of lying. Check them against the timeline.")
    return lines


def report(meta, analysis, score, clue_found=False):
    spec = analysis.get("spectrum") or {}
    pauses = analysis.get("pauses") or []
    pause_list = ", ".join(f'{p["start"]:.1f}–{p["end"]:.1f} s' for p in pauses[:8]) or "none"
    if len(pauses) > 8:
        pause_list += f" (+{len(pauses) - 8} more)"
    rows = [
        ("Recording", meta["title"]), ("Suspect", meta["suspect"]),
        ("Duration", f'{analysis["duration"]:.2f} s at {analysis["rate"]} Hz'),
        ("Signal", f'peak {fmt(analysis.get("peak_dbfs"))} dBFS · RMS {fmt(analysis.get("rms_dbfs"))} dBFS · '
                   f'contrast {fmt(analysis.get("contrast_db"), 1, "dB", "n/a")}'),
        ("Detected pauses", f'{fmt(analysis.get("pause_count"), 0, missing="n/a")} · {pause_list}'),
        ("Volume variation", fmt(analysis.get("level_spread_db"), 1, "dB", "n/a")),
        ("Speech rate", fmt(analysis.get("speech_rate_wpm"), 0, "wpm (approx., transcript)", "unavailable")),
        ("Spectrum", f'centroid {fmt(spec.get("centroid_hz"), 0, "Hz", "n/a")} · dominant '
                     f'{fmt(spec.get("dominant_hz"), 0, "Hz", "n/a")} · roll-off {fmt(spec.get("rolloff_hz"), 0, "Hz", "n/a")}'),
        ("Fictional score", f'{score["score"]}/100 – {score["label"]}' if score.get("available")
         else f'unavailable – {score.get("reason", "")}'),
    ]
    table = "".join(f"<tr><td>{h(k)}</td><td>{h(v)}</td></tr>" for k, v in rows)
    lis = "".join(f"<li>{h(n)}</li>" for n in investigative_notes(meta, analysis, score, clue_found))
    stamp = '<div class="vf-stamp">Clue linked</div>' if clue_found else '<div class="vf-stamp grey">Analysed</div>'
    return (f'<div class="vf-report">{stamp}<div class="vf-kicker">Forensic audio report</div>'
            f'<div class="vf-h">{h(meta["title"])}</div><table>{table}</table>'
            f'<div class="vf-kicker">Investigative notes</div><ul>{lis}</ul>'
            f'<div class="vf-small">{h(forensics.DISCLAIMER)}</div></div>')


def report_text(meta, analysis, score, clue_found=False, clue_text=None):
    """The same report as plain Markdown, for the download and the notebook."""
    spec = analysis.get("spectrum") or {}
    pauses = analysis.get("pauses") or []
    lines = [
        f"# Forensic audio report – {meta['title']}",
        "",
        f"- Suspect: {meta['suspect']}",
        f"- Source: {meta.get('source_note', '–')}",
        f"- Duration: {analysis['duration']:.2f} s at {analysis['rate']} Hz",
        f"- Peak / RMS level: {fmt(analysis.get('peak_dbfs'))} / {fmt(analysis.get('rms_dbfs'))} dBFS",
        f"- Speech/background contrast: {fmt(analysis.get('contrast_db'), 1, 'dB', 'unavailable')}",
        f"- Detected pauses (>= {forensics.MIN_PAUSE_SECONDS} s): {fmt(analysis.get('pause_count'), 0, missing='unavailable')}",
    ]
    lines += [f"  - {p['start']:.2f}–{p['end']:.2f} s ({p['length']:.2f} s)" for p in pauses]
    lines += [
        f"- Time in pauses: {fmt(analysis.get('pause_total'), 2, 's', 'unavailable')}",
        f"- Volume variation: {fmt(analysis.get('level_spread_db'), 1, 'dB', 'unavailable')}",
        f"- Speech rate (approx., from transcript): {fmt(analysis.get('speech_rate_wpm'), 0, 'wpm', 'unavailable')}",
        f"- Articulation rate: {fmt(analysis.get('articulation_wpm'), 0, 'wpm', 'unavailable')}",
        f"- Spectral centroid: {fmt(spec.get('centroid_hz'), 0, 'Hz', 'unavailable')}",
        f"- Dominant frequency: {fmt(spec.get('dominant_hz'), 0, 'Hz', 'unavailable')}",
        f"- 85% roll-off: {fmt(spec.get('rolloff_hz'), 0, 'Hz', 'unavailable')}",
        "",
        "## Fictional tension index",
        (f"{score['score']}/100 – {score['label']}" if score.get("available")
         else f"Unavailable: {score.get('reason', '')}"),
        "",
        "## Investigative notes",
    ]
    lines += [f"- {n}" for n in investigative_notes(meta, analysis, score, clue_found)]
    if clue_text:
        lines += ["", "## Audio evidence", clue_text]
    lines += ["", f"_{forensics.DISCLAIMER}_", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- comparison

def compare_table(rows, label_a, label_b):
    out = []
    for row in rows:
        a, b = row["a"], row["b"]
        d = row["digits"]
        delta_html = "–"
        cls = ""
        if row["delta"] is not None:
            rel = row["relative"]
            sign = "+" if row["delta"] > 0 else ""
            delta_html = f'{sign}{row["delta"]:.{d}f} {row["unit"]}'.strip()
            if rel is not None:
                delta_html += f" <small>({sign}{rel * 100:.0f}%)</small>"
                if abs(rel) >= 0.25 and row["key"] not in ("duration", "rms_dbfs"):
                    cls = " hot"
        width_a = width_b = 0
        if a is not None and b is not None and max(abs(a), abs(b)) > 0:
            top = max(abs(a), abs(b))
            width_a, width_b = abs(a) / top * 100, abs(b) / top * 100
        out.append(
            f'<tr class="{cls.strip()}"><td>{h(row["label"])}</td>'
            f'<td><div class="vf-dual a"><i style="width:{width_a:.0f}%"></i></div>{h(fmt(a, d, row["unit"], "n/a"))}</td>'
            f'<td><div class="vf-dual b"><i style="width:{width_b:.0f}%"></i></div>{h(fmt(b, d, row["unit"], "n/a"))}</td>'
            f'<td class="delta">{delta_html}</td></tr>')
    return ('<div class="vf-panel vf-compare-table"><table>'
            f'<tr><th>Measured characteristic</th><th><span class="sw a"></span>A · {h(label_a)}</th>'
            f'<th><span class="sw b"></span>B · {h(label_b)}</th><th>B &#8722; A</th></tr>'
            f'{"".join(out)}</table></div>')


def change_summary(changes):
    if not changes:
        return ('<div class="vf-panel vf-changes"><div class="vf-kicker">Largest measured changes</div>'
                '<p>No characteristic changed by 10% or more.</p></div>')
    items = []
    for r in changes:
        direction = "higher" if r["delta"] > 0 else "lower"
        items.append(f'<li><b>{h(r["label"])}</b> is {abs(r["relative"]) * 100:.0f}% {direction} in B.</li>')
    return ('<div class="vf-panel vf-changes"><div class="vf-kicker">Largest measured changes</div>'
            f'<ul>{"".join(items)}</ul><div class="vf-small">These are differences in the signal. People pause, '
            'slow down or get louder for many reasons &#8212; none of this shows that anyone lied.</div></div>')


# ---------------------------------------------------------------- audio evidence

def clue_brief(clue, isolated=None):
    found = ""
    if isolated is not None:
        found = (f'<div class="vf-found"><div class="n">{isolated["count"]}</div><div>tonal strikes measured in '
                 f'{isolated["band"][0] / 1000:.1f}–{isolated["band"][1] / 1000:.1f} kHz · dominant '
                 f'{fmt(isolated["dominant_hz"], 0, "Hz", "n/a")}<br><small>evenly spaced: '
                 f'{h(_spacing(isolated["onsets"]))}</small></div></div>')
    return (f'<div class="vf-panel vf-clue"><div class="vf-kicker">Anomaly in the background</div>'
            f'<div class="vf-h">{h(clue["title"])}</div><p>{h(clue["hint"])}</p>{found}</div>')


def _spacing(onsets):
    if len(onsets) < 2:
        return "not enough strikes"
    gaps = [b - a for a, b in zip(onsets, onsets[1:])]
    mean = sum(gaps) / len(gaps)
    spread = max(gaps) - min(gaps)
    return f"one every {mean:.2f} s (spread {spread:.2f} s)"


def evidence_card(key, card, chosen=False):
    cls = " chosen" if chosen else ""
    return (f'<div class="vf-evidence{cls}"><div class="vf-kicker">{h(card["label"])}</div>'
            f'<div class="t">&#8220;{h(card["text"])}&#8221;</div></div>')


def conclusion(clue):
    return ('<div class="vf-conclusion"><div class="vf-stamp">Contradiction</div>'
            '<div class="vf-kicker">Audio evidence · connected</div>'
            '<div class="vf-h">The 23:30 check-in was spoken at 23:00</div>'
            f'<p>{h(clue["conclusion"])}</p>'
            '<div class="vf-timeline"><div><b>23:00</b><span>bell strikes eleven times</span></div>'
            '<div class="hot"><b>~23:00</b><span>check-in actually spoken</span></div>'
            '<div><b>23:30</b><span>time written in the patrol log</span></div>'
            '<div><b>23:47</b><span>body found</span></div></div></div>')


# ---------------------------------------------------------------- notebook and demo

def notebook_entry(entry, number):
    kind = entry.get("kind", "report")
    tag = {"report": "Audio report", "clue": "Audio evidence", "compare": "Comparison"}.get(kind, kind)
    return (f'<div class="vf-note {h(kind)}"><div class="vf-note-no">#{number:02d}</div>'
            f'<div><div class="vf-kicker">{h(tag)}</div><div class="vf-note-title">{h(entry["title"])}</div>'
            f'<div class="vf-note-text">{h(entry["summary"])}</div></div></div>')


def demo_panel(steps, index):
    step = steps[index]
    dots = "".join(f'<i class="{"done" if i < index else "now" if i == index else ""}"></i>'
                   for i in range(len(steps)))
    elapsed = sum(s["seconds"] for s in steps[:index])
    total = sum(s["seconds"] for s in steps)
    return (f'<div class="vf-demo"><div class="vf-demo-top"><span class="vf-kicker">Guided demo · step '
            f'{index + 1} of {len(steps)}</span><span class="vf-demo-time">≈ {elapsed} s / {total} s</span></div>'
            f'<div class="vf-demo-dots">{dots}</div><div class="vf-demo-title">{h(step["title"])}</div>'
            f'<div class="vf-demo-text">{h(step["text"])}</div></div>')


# ---------------------------------------------------------------- interactive iframes

def _json(data):
    return json.dumps(data, separators=(",", ":")).replace("</", "<\\/")


def _b64(wav):
    return base64.b64encode(wav).decode("ascii")


def _track(rid, meta, analysis, wav, clue=None, onsets=None):
    return {
        "id": rid, "title": meta["title"], "suspect": meta["suspect"],
        "duration": analysis["duration"], "low": analysis["envelope"]["low"],
        "high": analysis["envelope"]["high"], "pauses": analysis.get("pauses") or [],
        "clue": list(clue) if clue else None, "onsets": onsets or [],
        "src": "data:audio/wav;base64," + _b64(wav),
        "synthetic": meta.get("synthetic", True),
    }


def player_document(rid, meta, analysis, wav, revealed, clue=None, onsets=None):
    """The interactive player: glowing waveform, playhead, click-to-seek, pause and clue markers."""
    data = {"mode": "single", "revealed": bool(revealed),
            "tracks": [_track(rid, meta, analysis, wav, clue, onsets)]}
    return _document(data)


def compare_document(a, b):
    """Two synchronized decks on one shared time axis. a, b: (rid, meta, analysis, wav)."""
    data = {"mode": "compare", "revealed": True, "tracks": [_track(*a), _track(*b)]}
    return _document(data)


def player_height(mode):
    return 330 if mode == "single" else 520


def _document(data):
    return (DOC_HEAD + '<div id="root"></div><script>const DATA=' + _json(data) + ';' + DOC_SCRIPT
            + '</script></body></html>')


DOC_HEAD = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#080D14;--panel:#111B29;--cyan:#22D3EE;--amber:#F5B841;--red:#EF4444;--text:#F8FAFC;--muted:#94A3B8;
--mono:'Courier Prime','JetBrains Mono',ui-monospace,monospace}
*{box-sizing:border-box}html,body{margin:0;background:transparent;color:var(--text);font-family:Inter,system-ui,sans-serif}
.deck{position:relative;background:linear-gradient(180deg,#0d1726,#0a111c);border:1px solid rgba(34,211,238,.25);
border-radius:6px;padding:12px 14px 10px;margin-bottom:12px;box-shadow:0 0 0 1px rgba(34,211,238,.05),0 18px 50px rgba(0,0,0,.45),inset 0 0 60px rgba(34,211,238,.04);overflow:hidden}
.deck.b{border-color:rgba(245,184,65,.3)}
.hdr{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;font-family:var(--mono);font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.hdr .rec{color:var(--red);font-weight:700}.hdr .rec i{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--red);margin-right:6px;box-shadow:0 0 10px var(--red);animation:blink 1.4s infinite}
.hdr .t{color:var(--text);letter-spacing:.06em}.hdr .badge{margin-left:auto;border:1px solid rgba(148,163,184,.35);padding:1px 6px;border-radius:2px;font-size:10px}
.hdr .lab{color:var(--cyan);font-weight:700}.deck.b .hdr .lab{color:var(--amber)}
.scope{position:relative;margin:10px 0 8px;height:190px;border-radius:4px;cursor:crosshair;
background:radial-gradient(ellipse at 50% 50%,rgba(34,211,238,.07),transparent 70%),repeating-linear-gradient(90deg,rgba(148,163,184,.07) 0 1px,transparent 1px 10%),repeating-linear-gradient(0deg,rgba(148,163,184,.06) 0 1px,transparent 1px 25%),#060a11}
.compare .scope{height:150px}
svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.wave{fill:rgba(34,211,238,.38);stroke:none}.played{fill:var(--cyan);filter:url(#glow)}
.deck.b .wave{fill:rgba(245,184,65,.38)}.deck.b .played{fill:var(--amber);filter:url(#glowa)}
.pause rect{fill:rgba(245,184,65,.13);stroke:rgba(245,184,65,.55);stroke-width:1;stroke-dasharray:3 3;vector-effect:non-scaling-stroke}
.pause text,.cluelbl,.tick{font-family:var(--mono);font-size:10px;fill:var(--amber)}
.clue{fill:rgba(239,68,68,.07);stroke:var(--red);stroke-width:1.5;stroke-dasharray:6 4;vector-effect:non-scaling-stroke;animation:pulse 2s infinite}
.cluelbl{fill:var(--red);font-weight:700;letter-spacing:.12em}
.onset{stroke:var(--red);stroke-width:2;vector-effect:non-scaling-stroke}
.head{stroke:#fff;stroke-width:1.5;vector-effect:non-scaling-stroke;filter:drop-shadow(0 0 4px var(--cyan))}
.ghost{stroke:rgba(255,255,255,.45);stroke-width:1;stroke-dasharray:4 3;vector-effect:non-scaling-stroke}
.cursor{stroke:rgba(248,250,252,.6);stroke-width:1;vector-effect:non-scaling-stroke;display:none}
.mid{stroke:rgba(34,211,238,.25);stroke-width:1;vector-effect:non-scaling-stroke}
.sweep{fill:url(#sw);opacity:0}
.revealed .wavegrp{transform-origin:50% 50%;animation:open 1.1s cubic-bezier(.2,.8,.2,1) both}
.revealed .sweep{animation:sweep 1.4s ease-out both}
.revealed .pause{animation:fade .5s ease both}
.locked .wavegrp{opacity:.28;filter:grayscale(1) blur(1.2px)}
.lockmsg{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:var(--mono);letter-spacing:.25em;text-transform:uppercase;font-size:13px;color:var(--cyan);text-shadow:0 0 12px rgba(34,211,238,.6);pointer-events:none}
.lockmsg small{color:var(--muted);letter-spacing:.12em;font-size:10px;margin-top:6px}
.tip{position:absolute;top:4px;padding:2px 6px;font-family:var(--mono);font-size:11px;background:rgba(8,13,20,.9);border:1px solid rgba(34,211,238,.4);border-radius:2px;pointer-events:none;display:none;white-space:nowrap}
.ctl{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-family:var(--mono);font-size:12px}
button{font-family:var(--mono);font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--text);background:rgba(17,27,41,.9);border:1px solid rgba(34,211,238,.45);border-radius:2px;padding:6px 12px;cursor:pointer;transition:all .15s}
button:hover,button:focus-visible{border-color:var(--cyan);color:var(--cyan);box-shadow:0 0 16px rgba(34,211,238,.25);outline:none}
button.play{min-width:92px;background:linear-gradient(180deg,rgba(34,211,238,.25),rgba(34,211,238,.08));border-color:var(--cyan)}
.deck.b button.play{background:linear-gradient(180deg,rgba(245,184,65,.25),rgba(245,184,65,.08));border-color:var(--amber)}
button[aria-pressed=true]{border-color:var(--red);color:var(--red)}
.time{color:var(--cyan);min-width:120px}.deck.b .time{color:var(--amber)}
.legend{margin-left:auto;display:flex;gap:12px;color:var(--muted);font-size:11px;letter-spacing:.08em;text-transform:uppercase}
.legend i{display:inline-block;width:10px;height:10px;margin-right:5px;vertical-align:-1px;border:1px solid}
.lp{background:rgba(245,184,65,.2);border-color:var(--amber)!important}.lc{border-color:var(--red)!important;border-style:dashed!important}.lw{background:var(--cyan);border-color:var(--cyan)!important}
.axis{display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:-4px}
.synch{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin:0 0 8px;display:flex;gap:10px;align-items:center}
.synch b{color:var(--text)}
@keyframes open{from{transform:scaleY(0);opacity:0}to{transform:scaleY(1);opacity:1}}
@keyframes sweep{0%{opacity:1;transform:translateX(-10%)}90%{opacity:1}100%{opacity:0;transform:translateX(100%)}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pulse{50%{stroke-opacity:.35}}
@keyframes blink{50%{opacity:.25}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
@media (max-width:560px){.legend{display:none}.scope{height:150px}}
</style></head><body>"""

DOC_SCRIPT = r"""
(function(){
const NS='http://www.w3.org/2000/svg',W=1000,H=200,root=document.getElementById('root');
const tmax=Math.max.apply(null,DATA.tracks.map(t=>t.duration))||1;
const decks=[];
function el(tag,attrs,parent){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(parent)parent.appendChild(e);return e;}
function fmt(s){s=Math.max(0,s);const m=Math.floor(s/60);return m+':'+(s%60).toFixed(1).padStart(4,'0');}
function wavePath(t,scaleX){const n=t.high.length;let peak=0;for(let i=0;i<n;i++)peak=Math.max(peak,Math.abs(t.high[i]),Math.abs(t.low[i]));
 const g=peak>0?(H*0.46)/peak:0;let up='',dn='';
 for(let i=0;i<n;i++){const x=(i/(Math.max(1,n-1)))*W*scaleX;up+=(i?'L':'M')+x.toFixed(1)+','+(H/2-t.high[i]*g).toFixed(1);}
 for(let i=n-1;i>=0;i--){const x=(i/(Math.max(1,n-1)))*W*scaleX;dn+='L'+x.toFixed(1)+','+(H/2-t.low[i]*g).toFixed(1);}
 return up+dn+'Z';}
if(DATA.mode==='compare'){const s=document.createElement('div');s.className='synch';s.innerHTML='<span>&#9670; Synchronized timeline</span><b>shared axis 0 &#8211; '+fmt(tmax)+'</b><span>hover either deck to align both</span>';root.appendChild(s);root.className='compare';}
DATA.tracks.forEach(function(t,idx){
 const scaleX=DATA.mode==='compare'?t.duration/tmax:1;
 const deck=document.createElement('div');deck.className='deck'+(idx===1?' b':'')+(DATA.revealed?' revealed':' locked');
 const label=DATA.mode==='compare'?(idx===0?'A':'B'):'REC';
 deck.innerHTML='<div class="hdr"><span class="rec"><i></i>'+(DATA.revealed?'Analysed':'Unanalysed')+'</span><span class="lab">'+label+'</span><span class="t"></span><span class="badge"></span></div>';
 deck.querySelector('.t').textContent=t.suspect+' — '+t.title;
 deck.querySelector('.badge').textContent=t.synthetic?'Synthetic sample':'Uploaded file';
 const scope=document.createElement('div');scope.className='scope';scope.setAttribute('role','slider');scope.setAttribute('tabindex','0');
 scope.setAttribute('aria-label','Waveform of '+t.title+'. Click or use arrow keys to seek.');scope.setAttribute('aria-valuemin','0');scope.setAttribute('aria-valuemax',t.duration.toFixed(1));
 deck.appendChild(scope);
 const svg=el('svg',{viewBox:'0 0 '+W+' '+H,preserveAspectRatio:'none'},scope);
 const defs=el('defs',{},svg);
 if(idx===0){
 const f=el('filter',{id:'glow',x:'-5%',y:'-20%',width:'110%',height:'140%'},defs);el('feGaussianBlur',{stdDeviation:'2.2',result:'b'},f);const m=el('feMerge',{},f);el('feMergeNode',{in:'b'},m);el('feMergeNode',{in:'SourceGraphic'},m);
 const fa=el('filter',{id:'glowa',x:'-5%',y:'-20%',width:'110%',height:'140%'},defs);el('feGaussianBlur',{stdDeviation:'2.2',result:'b'},fa);const ma=el('feMerge',{},fa);el('feMergeNode',{in:'b'},ma);el('feMergeNode',{in:'SourceGraphic'},ma);
 const lg=el('linearGradient',{id:'sw',x1:'0',x2:'1'},defs);el('stop',{offset:'0','stop-color':'#22D3EE','stop-opacity':'0'},lg);el('stop',{offset:'.85','stop-color':'#22D3EE','stop-opacity':'.35'},lg);el('stop',{offset:'1','stop-color':'#fff','stop-opacity':'.9'},lg);
 }
 const clip=el('clipPath',{id:'c'+idx},defs);const clipRect=el('rect',{x:0,y:0,width:0,height:H},clip);
 const X=s=>s/tmax*W*(DATA.mode==='compare'?1:tmax/t.duration);
 if(DATA.revealed){
  t.pauses.forEach(function(p,i){const g=el('g',{'class':'pause',style:'animation-delay:'+(0.6+i*0.08)+'s'},svg);
   el('rect',{x:X(p.start),y:6,width:Math.max(1,X(p.end)-X(p.start)),height:H-12},g);
   if(X(p.end)-X(p.start)>34){const tx=el('text',{x:X(p.start)+3,y:H-10},g);tx.textContent=p.length.toFixed(2)+'s';}});
  if(t.clue){el('rect',{'class':'clue',x:X(t.clue[0]),y:2,width:X(t.clue[1])-X(t.clue[0]),height:H-4},svg);
   const cl=el('text',{'class':'cluelbl',x:X(t.clue[0])+6,y:16},svg);cl.textContent='▲ BACKGROUND ANOMALY';}
  t.onsets.forEach(function(o){el('line',{'class':'onset',x1:X(o),x2:X(o),y1:20,y2:34},svg);});
 }
 el('line',{'class':'mid',x1:0,x2:W,y1:H/2,y2:H/2},svg);
 const wg=el('g',{'class':'wavegrp'},svg);const d=wavePath(t,scaleX);
 el('path',{'class':'wave',d:d},wg);el('path',{'class':'played',d:d,'clip-path':'url(#c'+idx+')'},wg);
 el('rect',{'class':'sweep',x:0,y:0,width:W*0.12,height:H},svg);
 const head=el('line',{'class':'head',x1:0,x2:0,y1:0,y2:H},svg);
 const ghost=el('line',{'class':'ghost',x1:-5,x2:-5,y1:0,y2:H},svg);
 const cursor=el('line',{'class':'cursor',x1:0,x2:0,y1:0,y2:H},svg);
 const tip=document.createElement('div');tip.className='tip';scope.appendChild(tip);
 if(!DATA.revealed){const lm=document.createElement('div');lm.className='lockmsg';lm.innerHTML='Signal not analysed<small>play it &#183; then initiate the forensic scan</small>';scope.appendChild(lm);}
 const axis=document.createElement('div');axis.className='axis';
 for(let i=0;i<=5;i++){const sp=document.createElement('span');sp.textContent=fmt((DATA.mode==='compare'?tmax:t.duration)*i/5);axis.appendChild(sp);}
 deck.appendChild(axis);
 const ctl=document.createElement('div');ctl.className='ctl';
 ctl.innerHTML='<button class="play" type="button">&#9654; Play</button><span class="time"></span><button class="rate" type="button" aria-label="Playback speed">1.0&#215;</button>'+(t.clue&&DATA.revealed?'<button class="loop" type="button" aria-pressed="false">&#10227; Loop anomaly</button>':'')+
  '<span class="legend"><span><i class="lw"></i>signal</span>'+(DATA.revealed?'<span><i class="lp"></i>pause</span>':'')+(t.clue&&DATA.revealed?'<span><i class="lc"></i>anomaly</span>':'')+'</span>';
 deck.appendChild(ctl);root.appendChild(deck);
 const audio=new Audio(t.src);audio.preload='auto';
 const play=ctl.querySelector('.play'),time=ctl.querySelector('.time'),rate=ctl.querySelector('.rate'),loop=ctl.querySelector('.loop');
 let looping=false;
 function draw(){const c=audio.currentTime||0;const x=X(c);clipRect.setAttribute('width',x);head.setAttribute('x1',x);head.setAttribute('x2',x);
  time.textContent=fmt(c)+' / '+fmt(t.duration);scope.setAttribute('aria-valuenow',c.toFixed(1));
  if(looping&&t.clue&&c>=t.clue[1]){audio.currentTime=t.clue[0];}
  decks.forEach(function(o){if(o!==api){if(!audio.paused){o.ghost.setAttribute('x1',X(c));o.ghost.setAttribute('x2',X(c));}}});}
 function loopf(){draw();if(!audio.paused)requestAnimationFrame(loopf);}
 play.addEventListener('click',function(){if(audio.paused){decks.forEach(o=>{if(o!==api)o.audio.pause();});audio.play();}else audio.pause();});
 audio.addEventListener('play',function(){play.innerHTML='&#10074;&#10074; Pause';requestAnimationFrame(loopf);});
 audio.addEventListener('pause',function(){play.innerHTML='&#9654; Play';draw();});
 audio.addEventListener('ended',function(){play.innerHTML='&#9654; Play';draw();});
 rate.addEventListener('click',function(){const r=audio.playbackRate===1?0.5:audio.playbackRate===0.5?1.5:1;audio.playbackRate=r;rate.innerHTML=r.toFixed(1)+'&#215;';});
 if(loop)loop.addEventListener('click',function(){looping=!looping;loop.setAttribute('aria-pressed',looping);if(looping){audio.currentTime=t.clue[0];if(audio.paused)audio.play();}});
 function timeAt(ev){const r=scope.getBoundingClientRect();const frac=Math.min(1,Math.max(0,(ev.clientX-r.left)/r.width));return frac*(DATA.mode==='compare'?tmax:t.duration);}
 scope.addEventListener('click',function(ev){const s=timeAt(ev);if(s<=t.duration){audio.currentTime=s;draw();}});
 scope.addEventListener('keydown',function(ev){if(ev.key==='ArrowRight'){audio.currentTime=Math.min(t.duration,audio.currentTime+1);draw();ev.preventDefault();}
  if(ev.key==='ArrowLeft'){audio.currentTime=Math.max(0,audio.currentTime-1);draw();ev.preventDefault();}
  if(ev.key===' '||ev.key==='Enter'){play.click();ev.preventDefault();}});
 scope.addEventListener('mousemove',function(ev){const s=timeAt(ev);decks.forEach(o=>o.hover(s));});
 scope.addEventListener('mouseleave',function(){decks.forEach(o=>o.hover(null));});
 const api={audio:audio,ghost:ghost,hover:function(s){if(s===null){cursor.style.display='none';tip.style.display='none';return;}
  const x=X(s);cursor.style.display='block';cursor.setAttribute('x1',x);cursor.setAttribute('x2',x);
  let label=fmt(s);if(s>t.duration)label+=' · ended';else{const p=t.pauses.find(p=>s>=p.start&&s<=p.end);if(p&&DATA.revealed)label+=' · pause '+p.length.toFixed(2)+'s';}
  tip.textContent=label;tip.style.display='block';const pct=x/W*100;tip.style.left=Math.min(82,pct)+'%';}};
 decks.push(api);draw();
});
})();
"""
