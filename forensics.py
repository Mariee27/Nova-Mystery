"""Voice Forensics: real signal analysis of a recording, and the fictional tension score.

Pure functions only: samples in, plain dictionaries out. No Streamlit, no files.
Only NumPy is used (it already comes with Streamlit), so nothing new has to be installed
on Streamlit Community Cloud.

What is MEASURED here (from the samples themselves):
  waveform envelope, RMS energy per frame, level spread, silences and pauses,
  the average spectrum (centroid, roll-off, dominant frequency, flatness, bands),
  and onsets of tonal events inside a frequency band (used for the bell clue).

What needs a TRANSCRIPT (typed by a person, never recognised from the audio):
  the approximate speech rate. This module does no speech recognition.

What is FICTION (a game mechanic, clearly labelled everywhere it is shown):
  the tension score. Voice analysis cannot reliably detect deception, guilt or
  nervousness, and nothing in this file claims to.
"""

import io
import math
import re
import wave

import numpy as np

DISCLAIMER = ("Experimental gameplay simulation. Voice analysis cannot reliably determine "
              "deception, guilt, or nervousness.")

# ---------------------------------------------------------------- limits

MAX_UPLOAD_BYTES = 5 * 1024 * 1024     # 5 MB
MAX_SECONDS = 60.0
MIN_SECONDS = 0.5
MIN_RATE, MAX_RATE = 4000, 96000

# ---------------------------------------------------------------- analysis settings

FRAME_SECONDS = 0.030      # 30 ms analysis frames ...
HOP_SECONDS = 0.010        # ... every 10 ms
MIN_PAUSE_SECONDS = 0.25   # a silence inside speech shorter than this is a normal gap between words
MIN_CONTRAST_DB = 10.0     # speech must be this much louder than the background to find pauses
SILENT_PEAK = 10 ** (-70 / 20)   # a recording whose loudest sample is below -70 dBFS is silent
ENVELOPE_POINTS = 720      # points of the drawn waveform
SPECTRUM_POINTS = 96       # log-spaced points of the drawn spectrum
MAX_SPECTRUM_FRAMES = 600  # the average spectrum uses at most this many frames (speed)
REFERENCE_WPM = 150.0      # a common conversational speech rate, for the deviation term

BANDS = (("Low", 0, 300), ("Voice", 300, 3400), ("High", 3400, None))


class AudioError(ValueError):
    """The file cannot be analysed. The message is shown to the player."""


# ---------------------------------------------------------------- decoding

def decode_wav(data):
    """WAV bytes -> (mono float samples in [-1, 1], sample rate).

    Only uncompressed PCM WAV (8, 16, 24 or 32 bit). Everything is checked before use:
    size, format, sample rate and duration. Raises AudioError with a readable reason.
    """
    if not data:
        raise AudioError("The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise AudioError(f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            count = wav.getnframes()
            if not MIN_RATE <= rate <= MAX_RATE:
                raise AudioError(f"Unsupported sample rate ({rate} Hz).")
            if count / rate > MAX_SECONDS + 0.01:
                raise AudioError(f"The recording is longer than {int(MAX_SECONDS)} seconds.")
            raw = wav.readframes(count)
    except AudioError:
        raise
    except (wave.Error, EOFError, ValueError, OSError) as problem:
        raise AudioError(f"This is not a readable PCM WAV file ({problem}).") from None
    if channels < 1 or width not in (1, 2, 3, 4):
        raise AudioError("Unsupported WAV layout.")
    usable = len(raw) - len(raw) % (width * channels)
    raw = raw[:usable]
    if not raw:
        raise AudioError("The file contains no audio samples.")
    if width == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        ints = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        ints = np.where(ints & 0x800000, ints - 0x1000000, ints)
        samples = ints.astype(np.float64) / 8388608.0
    else:
        samples = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, rate


def encode_wav(samples, rate):
    """Mono float samples -> 16-bit PCM WAV bytes (for the bundled recordings and tests)."""
    clipped = np.clip(np.asarray(samples, dtype=np.float64), -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2").tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(rate))
        wav.writeframes(pcm)
    return buffer.getvalue()


# ---------------------------------------------------------------- small helpers

def to_db(value):
    return 20.0 * np.log10(np.maximum(value, 1e-10))


def frame_rms(samples, rate):
    """RMS energy of every 30 ms frame, every 10 ms. Uses a running sum, so it is fast."""
    frame = max(1, int(round(FRAME_SECONDS * rate)))
    hop = max(1, int(round(HOP_SECONDS * rate)))
    if len(samples) < frame:
        return np.array([math.sqrt(float(np.mean(samples ** 2)))]) if len(samples) else np.zeros(0), hop
    squares = np.concatenate([[0.0], np.cumsum(samples ** 2)])
    starts = np.arange(0, len(samples) - frame + 1, hop)
    energy = (squares[starts + frame] - squares[starts]) / frame
    return np.sqrt(np.maximum(energy, 0.0)), hop


def envelope(samples, points=ENVELOPE_POINTS):
    """Min and max of the samples in `points` equal buckets: the drawn waveform."""
    n = len(samples)
    if n == 0:
        return [], []
    points = max(1, min(points, n))
    edges = np.linspace(0, n, points + 1).astype(int)
    lows, highs = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        chunk = samples[a:max(b, a + 1)]
        lows.append(round(float(chunk.min()), 4))
        highs.append(round(float(chunk.max()), 4))
    return lows, highs


def runs(mask):
    """[(start, end)] of the True runs of a boolean array (end exclusive)."""
    if len(mask) == 0:
        return []
    padded = np.concatenate([[False], mask, [False]]).astype(np.int8)
    change = np.flatnonzero(np.diff(padded))
    return list(zip(change[0::2].tolist(), change[1::2].tolist()))


def count_words(transcript):
    return len(re.findall(r"[A-Za-z0-9À-ÿ]+(?:['’-][A-Za-z0-9À-ÿ]+)*", transcript or ""))


def _clip01(value):
    return max(0.0, min(1.0, float(value)))


# ---------------------------------------------------------------- the analysis

def analyze(samples, rate, transcript=None):
    """Measure a recording. Returns one plain dictionary; nothing in it is invented.

    Every metric that cannot be measured reliably is None, and `notes` says why.
    `ok` is False only when the recording is unusable as a whole (empty, too short, silent).
    """
    samples = np.asarray(samples, dtype=np.float64)
    duration = len(samples) / rate if rate else 0.0
    result = {
        "ok": False, "reason": None, "notes": [],
        "rate": int(rate), "duration": round(duration, 3), "samples": int(len(samples)),
        "peak_dbfs": None, "rms_dbfs": None,
        "envelope": {"low": [], "high": []},
        "frames": {"hop": HOP_SECONDS, "db": []},
        "threshold_db": None, "noise_floor_db": None, "speech_level_db": None, "contrast_db": None,
        "speech_start": None, "speech_end": None, "speech_span": None,
        "pauses": None, "pause_count": None, "pause_total": None, "pause_ratio": None,
        "longest_pause": None, "pauses_per_minute": None,
        "level_spread_db": None, "level_range_db": None,
        "spectrum": None,
        "words": None, "speech_rate_wpm": None, "articulation_wpm": None,
    }
    if len(samples) == 0 or rate <= 0:
        result["reason"] = "The recording contains no samples."
        return result
    if not np.all(np.isfinite(samples)):
        result["reason"] = "The recording contains invalid sample values."
        return result
    lows, highs = envelope(samples)
    result["envelope"] = {"low": lows, "high": highs}
    peak = float(np.max(np.abs(samples)))
    result["peak_dbfs"] = round(float(to_db(peak)), 1)
    result["rms_dbfs"] = round(float(to_db(math.sqrt(float(np.mean(samples ** 2))))), 1)
    if duration < MIN_SECONDS:
        result["reason"] = f"The recording is shorter than {MIN_SECONDS} s – too short to analyse."
        return result
    if peak < SILENT_PEAK:
        result["reason"] = "The recording is silent: no signal above -70 dBFS."
        return result

    rms, hop = frame_rms(samples, rate)
    hop_s = hop / rate
    levels = to_db(rms)
    result["frames"] = {"hop": hop_s, "db": [round(float(v), 1) for v in np.maximum(levels, -100.0)]}
    floor = float(np.percentile(levels, 10))
    loud = float(np.percentile(levels, 95))
    contrast = loud - floor
    result["noise_floor_db"] = round(floor, 1)
    result["speech_level_db"] = round(loud, 1)
    result["contrast_db"] = round(contrast, 1)
    result["ok"] = True

    if contrast < MIN_CONTRAST_DB:
        result["notes"].append(
            f"Speech and background differ by only {contrast:.1f} dB (at least {MIN_CONTRAST_DB:.0f} dB "
            "are needed), so silences and pauses cannot be told apart reliably. Pause metrics, "
            "speech rate and the tension score are unavailable.")
        result["spectrum"] = spectrum(samples, rate, None, hop)
        return result

    threshold = floor + 0.35 * contrast
    result["threshold_db"] = round(threshold, 1)
    voiced = levels >= threshold
    voiced_runs = runs(voiced)
    first, last = voiced_runs[0][0], voiced_runs[-1][1]
    start_s, end_s = first * hop_s, (last - 1) * hop_s + FRAME_SECONDS
    span = max(0.0, min(duration, end_s) - start_s)
    result["speech_start"] = round(start_s, 3)
    result["speech_end"] = round(min(duration, end_s), 3)
    result["speech_span"] = round(span, 3)

    pauses = []
    for a, b in runs(~voiced[first:last]):
        a, b = a + first, b + first
        # frame a starts at a*hop; the gap between speech is from the end of frame a-1 to the start of frame b
        gap_start = (a - 1) * hop_s + FRAME_SECONDS
        gap_end = b * hop_s
        length = gap_end - gap_start
        if length >= MIN_PAUSE_SECONDS:
            pauses.append({"start": round(gap_start, 3), "end": round(gap_end, 3), "length": round(length, 3)})
    pause_total = sum(p["length"] for p in pauses)
    result["pauses"] = pauses
    result["pause_count"] = len(pauses)
    result["pause_total"] = round(pause_total, 3)
    result["pause_ratio"] = round(pause_total / span, 4) if span > 0 else None
    result["longest_pause"] = round(max((p["length"] for p in pauses), default=0.0), 3)
    result["pauses_per_minute"] = round(len(pauses) / (span / 60.0), 2) if span > 0 else None

    # Level spread over the speech frames, measured on a 200 ms smoothed level so that the normal
    # rise and fall inside one syllable does not count, only louder and quieter stretches.
    voiced_levels = levels[voiced]
    if len(voiced_levels) >= 20:
        width = max(1, int(round(0.2 / hop_s)))
        smooth = np.convolve(rms ** 2, np.ones(width) / width, mode="same")
        smooth_db = to_db(np.sqrt(smooth))[voiced]
        result["level_spread_db"] = round(float(np.std(smooth_db)), 2)
        result["level_range_db"] = round(float(np.percentile(smooth_db, 95) - np.percentile(smooth_db, 5)), 2)
    else:
        result["notes"].append("Too little speech to measure the level spread.")

    result["spectrum"] = spectrum(samples, rate, voiced, hop)

    words = count_words(transcript)
    if transcript and words:
        result["words"] = words
        speaking = span - pause_total
        if span >= 1.0 and speaking > 0.3:
            result["speech_rate_wpm"] = round(words / (span / 60.0), 1)
            result["articulation_wpm"] = round(words / (speaking / 60.0), 1)
        else:
            result["notes"].append("Too little speech for a speech-rate estimate.")
    else:
        result["notes"].append("No transcript: speech rate is unavailable (this tool does not "
                               "recognise words from audio).")
    return result


def spectrum(samples, rate, voiced, hop):
    """The average power spectrum of the speech frames (all frames if voiced is None)."""
    frame = 1 << int(math.ceil(math.log2(max(16, FRAME_SECONDS * rate))))
    if len(samples) < frame:
        return None
    starts = np.arange(0, len(samples) - frame + 1, hop)
    if voiced is not None:
        keep = np.zeros(len(starts), dtype=bool)
        keep[:min(len(voiced), len(starts))] = voiced[:len(starts)]
        if keep.sum() >= 5:
            starts = starts[keep]
    if len(starts) > MAX_SPECTRUM_FRAMES:
        starts = starts[np.linspace(0, len(starts) - 1, MAX_SPECTRUM_FRAMES).astype(int)]
    window = np.hanning(frame)
    frames = np.stack([samples[s:s + frame] for s in starts]) * window
    power = np.mean(np.abs(np.fft.rfft(frames, axis=1)) ** 2, axis=0)
    freqs = np.fft.rfftfreq(frame, 1.0 / rate)
    total = float(power.sum())
    if total <= 0:
        return None
    use = freqs >= 60
    centroid = float(np.sum(freqs * power) / total)
    rolloff = float(freqs[min(len(freqs) - 1, int(np.searchsorted(np.cumsum(power), 0.85 * total)))])
    dominant = float(freqs[use][int(np.argmax(power[use]))]) if use.any() else None
    p = power[use] + 1e-20
    flatness = float(np.exp(np.mean(np.log(p))) / np.mean(p))
    bands = []
    for name, lo, hi in BANDS:
        hi_value = rate / 2 if hi is None else hi
        part = power[(freqs >= lo) & (freqs < hi_value)].sum()
        bands.append({"name": name, "low": lo, "high": int(hi_value), "share": round(float(part / total), 4)})
    # log-spaced points for the chart
    edges = np.geomspace(60, rate / 2, SPECTRUM_POINTS + 1)
    curve_f, curve_db = [], []
    peak_power = float(power.max())
    for a, b in zip(edges[:-1], edges[1:]):
        mask = (freqs >= a) & (freqs < b)
        if mask.any():
            curve_f.append(round(float(math.sqrt(a * b)), 1))
            curve_db.append(round(float(10 * np.log10(power[mask].mean() / peak_power + 1e-12)), 1))
    return {
        "centroid_hz": round(centroid, 1), "rolloff_hz": round(rolloff, 1),
        "dominant_hz": round(dominant, 1) if dominant is not None else None,
        "flatness": round(flatness, 4), "bands": bands,
        "curve": {"hz": curve_f, "db": curve_db},
    }


# ---------------------------------------------------------------- tonal events (audio evidence)

def band_onsets(samples, rate, start, end, low_hz, high_hz, rise_db=10.0, min_gap=0.45,
                tonal_db=12.0, headroom_db=20.0):
    """Find the onsets of ringing, tonal events inside one frequency band (start..end seconds).

    Used to count the strikes of a bell behind a voice. For every 32 ms frame it measures the
    strongest frequency peak inside the band. An onset is a sharp rise of that peak
    (at least `rise_db` above the last 80 ms) that is tonal (at least `tonal_db` above the
    median of the band, so noise such as consonants does not count) and loud (within
    `headroom_db` of the loudest peak in the segment). Every number comes from the samples.
    """
    samples = np.asarray(samples, dtype=np.float64)
    a = max(0, int(start * rate))
    b = min(len(samples), int(end * rate))
    frame = 1 << int(math.ceil(math.log2(max(16, 0.032 * rate))))
    hop = max(1, int(0.01 * rate))
    empty = {"times": [], "db": [], "onsets": [], "count": 0, "dominant_hz": None,
             "band": (low_hz, high_hz)}
    if b - a < frame * 2 or high_hz <= low_hz:
        return empty
    segment = samples[a:b]
    starts = np.arange(0, len(segment) - frame + 1, hop)
    window = np.hanning(frame)
    spec = np.abs(np.fft.rfft(np.stack([segment[s:s + frame] for s in starts]) * window, axis=1)) ** 2
    freqs = np.fft.rfftfreq(frame, 1.0 / rate)
    mask = (freqs >= low_hz) & (freqs <= high_hz)
    if mask.sum() < 3:
        return empty
    inside = spec[:, mask] + 1e-20
    peak = 10 * np.log10(inside.max(axis=1))
    tonality = peak - 10 * np.log10(np.median(inside, axis=1))
    times = (starts + frame / 2) / rate + a / rate
    loudest = float(peak.max())
    lookback = max(1, int(0.08 * rate / hop))
    gap = max(1, int(min_gap * rate / hop))
    onsets = []
    last = -gap
    for i in range(lookback, len(peak)):
        if i - last < gap:
            continue
        if (peak[i] - peak[i - lookback:i].min() >= rise_db and tonality[i] >= tonal_db
                and peak[i] >= loudest - headroom_db):
            onsets.append(round(float(times[i]), 3))
            last = i
    band_power = inside.mean(axis=0)
    dominant = float(freqs[mask][int(np.argmax(band_power))])
    step = max(1, len(peak) // 400)
    return {
        "times": [round(float(t), 3) for t in times[::step]],
        "db": [round(float(v - loudest), 1) for v in peak[::step]],
        "onsets": onsets, "count": len(onsets),
        "dominant_hz": round(dominant, 1), "band": (low_hz, high_hz),
    }


def band_pass(samples, rate, low_hz, high_hz, edge_hz=150.0):
    """Keep only low_hz..high_hz (FFT filter with soft edges), so a person can listen to the
    isolated band. Normalised to a peak of 0.9; silence stays silence."""
    samples = np.asarray(samples, dtype=np.float64)
    if len(samples) == 0:
        return samples
    spec = np.fft.rfft(samples)
    freqs = np.fft.rfftfreq(len(samples), 1.0 / rate)
    gain = np.clip((freqs - (low_hz - edge_hz)) / edge_hz, 0, 1) * np.clip(((high_hz + edge_hz) - freqs) / edge_hz, 0, 1)
    out = np.fft.irfft(spec * gain, n=len(samples))
    peak = float(np.max(np.abs(out)))
    return out * (0.9 / peak) if peak > 1e-9 else out


# ---------------------------------------------------------------- the fictional score

# (key, label, weight, how the raw value is normalised to 0..1, unit)
SCORE_TERMS = (
    ("level_spread_db", "Volume variation", 0.35, (3.0, 9.0), "dB"),
    ("pause_ratio", "Share of time in pauses", 0.30, (0.05, 0.35), ""),
    ("pauses_per_minute", "Pause frequency", 0.15, (6.0, 30.0), "/min"),
    ("rate_deviation", "Speech-rate deviation", 0.20, (0.10, 0.50), ""),
)

LABELS = ((25, "Low fictional tension"), (50, "Moderate fictional tension"),
          (75, "Elevated fictional tension"), (101, "High fictional tension"))


def tension_label(score):
    for limit, label in LABELS:
        if score < limit:
            return label
    return LABELS[-1][1]


def tension_score(analysis):
    """The fictional Nervousness Score (0–100). Deterministic and fully transparent.

    Each term is a measured value mapped linearly from [low, high] to [0, 1]; the score is the
    weighted sum. Speech-rate deviation (|rate − 150 wpm| / 150) is used only with a transcript;
    without one, the other weights are scaled up so they still add to 1.

    Returns {"available": False, "reason": ...} instead of a number when the recording does
    not allow one – no score is ever invented.
    """
    if not analysis.get("ok"):
        return {"available": False, "reason": analysis.get("reason") or "The recording cannot be analysed.",
                "disclaimer": DISCLAIMER}
    if analysis.get("pauses") is None or analysis.get("level_spread_db") is None:
        return {"available": False,
                "reason": "Pauses or volume variation could not be measured reliably, so no score is given.",
                "disclaimer": DISCLAIMER}
    if (analysis.get("speech_span") or 0) < 1.0:
        return {"available": False, "reason": "Less than one second of speech – not enough for a score.",
                "disclaimer": DISCLAIMER}
    values = dict(analysis)
    rate = analysis.get("articulation_wpm")
    values["rate_deviation"] = abs(rate - REFERENCE_WPM) / REFERENCE_WPM if rate else None
    present = [t for t in SCORE_TERMS if values.get(t[0]) is not None]
    weight_sum = sum(t[2] for t in present)
    terms, total = [], 0.0
    for key, label, weight, (low, high), unit in SCORE_TERMS:
        raw = values.get(key)
        if raw is None:
            terms.append({"key": key, "label": label, "raw": None, "unit": unit, "normalized": None,
                          "weight": 0.0, "points": 0.0, "range": (low, high)})
            continue
        normalized = _clip01((raw - low) / (high - low))
        used = weight / weight_sum
        points = 100.0 * used * normalized
        total += points
        terms.append({"key": key, "label": label, "raw": round(float(raw), 3), "unit": unit,
                      "normalized": round(normalized, 3), "weight": round(used, 3),
                      "points": round(points, 1), "range": (low, high)})
    score = int(round(total))
    return {"available": True, "score": score, "label": tension_label(score), "terms": terms,
            "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------- comparison

COMPARE_METRICS = (
    ("duration", "Duration", "s", 1),
    ("speech_rate_wpm", "Speech rate", "wpm", 0),
    ("articulation_wpm", "Articulation rate", "wpm", 0),
    ("pause_count", "Pauses", "", 0),
    ("pauses_per_minute", "Pause frequency", "/min", 1),
    ("pause_total", "Time in pauses", "s", 2),
    ("longest_pause", "Longest pause", "s", 2),
    ("level_spread_db", "Volume variation", "dB", 1),
    ("rms_dbfs", "Average level", "dBFS", 1),
    ("centroid_hz", "Spectral centroid", "Hz", 0),
)


def metric(analysis, key):
    if key == "centroid_hz":
        spec = analysis.get("spectrum")
        return spec.get("centroid_hz") if spec else None
    return analysis.get(key)


def compare(a, b):
    """Side-by-side measured differences between two analyses (B relative to A).

    Only reports what changed in the signal. It does not interpret a change as a lie.
    """
    rows = []
    for key, label, unit, digits in COMPARE_METRICS:
        va, vb = metric(a, key), metric(b, key)
        row = {"key": key, "label": label, "unit": unit, "digits": digits, "a": va, "b": vb,
               "delta": None, "relative": None}
        if va is not None and vb is not None:
            row["delta"] = round(vb - va, 3)
            if abs(va) > 1e-9:
                row["relative"] = round((vb - va) / abs(va), 3)
        rows.append(row)
    return rows


def biggest_changes(rows, limit=3):
    """The measured characteristics that changed most (by relative change)."""
    usable = [r for r in rows if r["relative"] is not None and r["key"] not in ("duration", "rms_dbfs")]
    usable.sort(key=lambda r: abs(r["relative"]), reverse=True)
    return [r for r in usable[:limit] if abs(r["relative"]) >= 0.1]
