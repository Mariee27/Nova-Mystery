"""Voice Forensics: the signal analysis, the fictional score, and the bundled recordings."""

import io
import wave

import numpy as np
import pytest

import content
import forensics
import recordings

RATE = 16000


def tone_bursts(bursts, gap, burst=0.3, rate=RATE, level=0.5, lead=0.3):
    """`bursts` 220 Hz tone bursts separated by `gap` seconds of silence."""
    t = np.arange(int(burst * rate)) / rate
    tone = level * np.sin(2 * np.pi * 220 * t)
    parts = [np.zeros(int(lead * rate))]
    for i in range(bursts):
        parts.append(tone)
        if i < bursts - 1:
            parts.append(np.zeros(int(gap * rate)))
    parts.append(np.zeros(int(lead * rate)))
    noise = np.random.default_rng(0).normal(0, 1e-4, sum(len(p) for p in parts))
    return np.concatenate(parts) + noise


# ---------------------------------------------------------------- decoding and limits

def test_wav_roundtrip_keeps_the_samples():
    x = tone_bursts(3, 0.5)
    y, rate = forensics.decode_wav(forensics.encode_wav(x, RATE))
    assert rate == RATE and len(y) == len(x)
    assert np.max(np.abs(x - y)) < 1e-4


@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_every_pcm_width_and_stereo_decode(width):
    x = 0.5 * np.sin(2 * np.pi * 440 * np.arange(RATE) / RATE)
    scale = 2 ** (8 * width - 1) - 1
    ints = np.round(x * scale).astype(np.int64)
    stereo = np.repeat(ints, 2)
    if width == 1:
        raw = (stereo + 128).astype(np.uint8).tobytes()
    else:
        raw = b"".join(int(v).to_bytes(width, "little", signed=True) for v in stereo)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(width)
        w.setframerate(RATE)
        w.writeframes(raw)
    y, rate = forensics.decode_wav(buffer.getvalue())
    assert rate == RATE and len(y) == RATE
    assert np.max(np.abs(x - y)) < 0.02


@pytest.mark.parametrize("data, words", [
    (b"", "empty"),
    (b"not a wav file at all" * 10, "not a readable"),
    (b"x" * (forensics.MAX_UPLOAD_BYTES + 1), "larger than"),
])
def test_invalid_files_are_rejected_with_a_reason(data, words):
    with pytest.raises(forensics.AudioError, match=words):
        forensics.decode_wav(data)


def test_too_long_and_odd_rates_are_rejected():
    long = forensics.encode_wav(np.zeros(int(4000 * 61)), 4000)
    with pytest.raises(forensics.AudioError, match="longer than"):
        forensics.decode_wav(long)
    with pytest.raises(forensics.AudioError, match="sample rate"):
        forensics.decode_wav(forensics.encode_wav(np.zeros(1000), 2000))


def test_header_without_samples_is_rejected():
    with pytest.raises(forensics.AudioError, match="no audio"):
        forensics.decode_wav(forensics.encode_wav(np.zeros(0), RATE))


# ---------------------------------------------------------------- empty, silent, short

def test_silent_recording_gives_no_measurements_and_no_score():
    a = forensics.analyze(np.zeros(RATE * 3), RATE, "hello there")
    assert a["ok"] is False and "silent" in a["reason"]
    assert a["pauses"] is None and a["speech_rate_wpm"] is None
    score = forensics.tension_score(a)
    assert score["available"] is False and "score" not in score


def test_empty_and_too_short_recordings():
    assert forensics.analyze(np.zeros(0), RATE)["ok"] is False
    short = forensics.analyze(np.ones(int(0.2 * RATE)) * 0.3, RATE)
    assert short["ok"] is False and "too short" in short["reason"]
    assert forensics.tension_score(short)["available"] is False


def test_no_contrast_means_pauses_and_score_unavailable():
    noise = np.random.default_rng(1).normal(0, 0.2, RATE * 3)
    a = forensics.analyze(noise, RATE, "some words here")
    assert a["ok"] is True
    assert a["pauses"] is None and a["speech_rate_wpm"] is None
    assert any("cannot be told apart" in n for n in a["notes"])
    assert forensics.tension_score(a)["available"] is False


def test_nan_samples_are_refused():
    x = tone_bursts(2, 0.5)
    x[100] = np.nan
    assert forensics.analyze(x, RATE)["ok"] is False


# ---------------------------------------------------------------- pauses and levels

def test_pauses_are_found_where_the_silences_are():
    a = forensics.analyze(tone_bursts(4, 0.6), RATE)
    assert a["ok"] and a["pause_count"] == 3
    for p in a["pauses"]:
        assert p["length"] == pytest.approx(0.6, abs=0.05)
    assert a["pauses"][0]["start"] == pytest.approx(0.6, abs=0.05)   # lead 0.3 + burst 0.3
    assert a["speech_start"] == pytest.approx(0.3, abs=0.03)


def test_short_gaps_are_not_pauses():
    a = forensics.analyze(tone_bursts(5, 0.1), RATE)
    assert a["pause_count"] == 0 and a["pause_total"] == 0


def test_more_and_longer_pauses_raise_pause_metrics():
    few = forensics.analyze(tone_bursts(4, 0.3), RATE)
    many = forensics.analyze(tone_bursts(4, 1.2), RATE)
    assert many["pause_ratio"] > few["pause_ratio"]
    assert many["longest_pause"] > few["longest_pause"]


def test_volume_variation_follows_the_level_changes():
    steady = tone_bursts(6, 0.4)
    uneven = steady.copy()
    half = len(uneven) // 2
    uneven[:half] *= 0.1   # first half 20 dB quieter
    s = forensics.analyze(steady, RATE)["level_spread_db"]
    u = forensics.analyze(uneven, RATE)["level_spread_db"]
    assert u > s + 5


def test_rms_and_peak_levels_are_correct():
    x = 0.5 * np.sin(2 * np.pi * 1000 * np.arange(RATE * 2) / RATE)
    a = forensics.analyze(x, RATE)
    assert a["peak_dbfs"] == pytest.approx(-6.0, abs=0.1)
    assert a["rms_dbfs"] == pytest.approx(-9.0, abs=0.1)


# ---------------------------------------------------------------- spectrum

def test_spectrum_finds_the_tone():
    x = tone_bursts(4, 0.4)
    spec = forensics.analyze(x, RATE)["spectrum"]
    assert spec["dominant_hz"] == pytest.approx(220, abs=20)
    assert spec["centroid_hz"] < 600
    assert sum(b["share"] for b in spec["bands"]) == pytest.approx(1.0, abs=0.01)
    assert len(spec["curve"]["hz"]) == len(spec["curve"]["db"]) > 20


def test_bright_sound_has_a_higher_centroid():
    t = np.arange(RATE * 2) / RATE
    low = forensics.analyze(0.4 * np.sin(2 * np.pi * 200 * t), RATE)["spectrum"]["centroid_hz"]
    high = forensics.analyze(0.4 * np.sin(2 * np.pi * 3000 * t), RATE)["spectrum"]["centroid_hz"]
    assert high > low * 5


# ---------------------------------------------------------------- speech rate

def test_speech_rate_needs_a_transcript():
    x = tone_bursts(6, 0.4)
    assert forensics.analyze(x, RATE)["speech_rate_wpm"] is None
    a = forensics.analyze(x, RATE, "one two three four five six")
    assert a["words"] == 6
    expected = 6 / (a["speech_span"] / 60)
    assert a["speech_rate_wpm"] == pytest.approx(expected, rel=0.01)
    assert a["articulation_wpm"] > a["speech_rate_wpm"]


def test_word_count():
    assert forensics.count_words("I was on patrol. Twenty-three forty-seven, didn't I?") == 8
    assert forensics.count_words("") == 0 and forensics.count_words(None) == 0


# ---------------------------------------------------------------- the fictional score

def test_score_is_deterministic_bounded_and_labelled():
    x = tone_bursts(6, 0.7)
    first = forensics.tension_score(forensics.analyze(x, RATE, "a b c d e f"))
    second = forensics.tension_score(forensics.analyze(x.copy(), RATE, "a b c d e f"))
    assert first == second
    assert 0 <= first["score"] <= 100
    assert first["label"].endswith("fictional tension")
    assert first["disclaimer"] == forensics.DISCLAIMER
    assert sum(t["points"] for t in first["terms"]) == pytest.approx(first["score"], abs=0.6)


def test_weights_are_renormalised_without_a_transcript():
    s = forensics.tension_score(forensics.analyze(tone_bursts(6, 0.7), RATE))
    used = [t for t in s["terms"] if t["raw"] is not None]
    assert all(t["key"] != "rate_deviation" for t in used)
    assert sum(t["weight"] for t in used) == pytest.approx(1.0, abs=0.01)


def test_labels_cover_the_range():
    assert forensics.tension_label(0) == "Low fictional tension"
    assert forensics.tension_label(30) == "Moderate fictional tension"
    assert forensics.tension_label(60) == "Elevated fictional tension"
    assert forensics.tension_label(100) == "High fictional tension"


def test_more_pauses_more_fictional_tension():
    calm = forensics.tension_score(forensics.analyze(tone_bursts(8, 0.3, burst=1.5), RATE))
    tense = forensics.tension_score(forensics.analyze(tone_bursts(8, 0.8, burst=1.5), RATE))
    assert tense["score"] > calm["score"]


def test_the_disclaimer_never_claims_lie_detection():
    text = forensics.DISCLAIMER.lower()
    assert "cannot reliably determine deception" in text


# ---------------------------------------------------------------- comparison

def test_compare_reports_measured_differences():
    a = forensics.analyze(tone_bursts(6, 0.3), RATE, "a b c d e f")
    b = forensics.analyze(tone_bursts(6, 1.0), RATE, "a b c d e f")
    rows = {r["key"]: r for r in forensics.compare(a, b)}
    assert rows["pause_total"]["delta"] > 0
    assert rows["speech_rate_wpm"]["delta"] < 0
    changes = forensics.biggest_changes(list(rows.values()))
    assert changes and all(abs(c["relative"]) >= 0.1 for c in changes)


def test_compare_handles_missing_values():
    a = forensics.analyze(tone_bursts(4, 0.5), RATE)               # no transcript
    b = forensics.analyze(tone_bursts(4, 0.5), RATE, "a b c d")
    row = next(r for r in forensics.compare(a, b) if r["key"] == "speech_rate_wpm")
    assert row["a"] is None and row["delta"] is None


# ---------------------------------------------------------------- tonal onsets and band-pass

def test_band_onsets_count_bell_strikes_and_ignore_noise():
    n = RATE * 8
    strikes = [0.5 + i for i in range(7)]
    x = recordings.bell(n, strikes, level_db=-12) + np.random.default_rng(3).normal(0, 0.001, n)
    found = forensics.band_onsets(x, RATE, 0, 8, 3600, 5800)
    assert found["count"] == 7
    for got, want in zip(found["onsets"], strikes):
        assert got == pytest.approx(want, abs=0.05)
    noise = np.random.default_rng(4).normal(0, 0.1, n)
    assert forensics.band_onsets(noise, RATE, 0, 8, 3600, 5800)["count"] == 0


def test_band_onsets_with_too_little_audio():
    assert forensics.band_onsets(np.zeros(100), RATE, 0, 1, 3600, 5800)["count"] == 0


def test_band_pass_removes_the_voice_band():
    t = np.arange(RATE) / RATE
    x = np.sin(2 * np.pi * 300 * t) + 0.2 * np.sin(2 * np.pi * 4500 * t)
    y = forensics.band_pass(x, RATE, 3600, 5800)
    spec = np.abs(np.fft.rfft(y))
    freqs = np.fft.rfftfreq(len(y), 1 / RATE)
    assert spec[np.argmin(abs(freqs - 4500))] > 100 * spec[np.argmin(abs(freqs - 300))]
    assert np.allclose(forensics.band_pass(np.zeros(500), RATE, 3600, 5800), 0)


# ---------------------------------------------------------------- the bundled recordings

def test_bundled_recordings_are_deterministic():
    for rid in recordings.RECORDINGS:
        assert recordings.wav_bytes(rid) == recordings.wav_bytes(rid)


def test_every_bundled_recording_is_analysable():
    for rid in recordings.RECORDINGS:
        samples, rate = forensics.decode_wav(recordings.wav_bytes(rid))
        a = forensics.analyze(samples, rate, recordings.transcript(rid))
        assert a["ok"], rid
        assert a["pause_count"] >= 1 and a["speech_rate_wpm"] > 0
        assert forensics.tension_score(a)["available"]
        assert a["duration"] <= forensics.MAX_SECONDS


def test_the_night_recording_measures_more_tension_than_the_routine_one():
    a_id, b_id = recordings.DEFAULT_PAIR
    scores = []
    for rid in (a_id, b_id):
        samples, rate = forensics.decode_wav(recordings.wav_bytes(rid))
        scores.append(forensics.tension_score(forensics.analyze(samples, rate, recordings.transcript(rid)))["score"])
    assert scores[1] > scores[0]


def test_the_bell_in_the_radio_check_in_strikes_eleven_times():
    clue = recordings.CLUE
    samples, rate = forensics.decode_wav(recordings.wav_bytes(clue["recording"]))
    found = forensics.band_onsets(samples, rate, *clue["segment"], *clue["band"])
    assert found["count"] == clue["expected_strikes"] == 11


def test_the_other_recordings_have_no_bell():
    clue = recordings.CLUE
    for rid in recordings.RECORDINGS:
        if rid == clue["recording"]:
            continue
        samples, rate = forensics.decode_wav(recordings.wav_bytes(rid))
        assert forensics.band_onsets(samples, rate, 0, len(samples) / rate, *clue["band"])["count"] < 6


def test_the_clue_only_uses_canonical_case_facts():
    """The bell clue must not contradict case #001: it uses the canonical bell, the guard's
    canonical secret (false patrols), and never names a murderer (the generator picks one per game)."""
    assert recordings.EVIDENCE[recordings.CLUE["answer"]]["text"] in content.NEUTRAL_PRIVATE_CLUES
    assert "patrols in tonight's log never happened" in content.ROLES[recordings.GUARD]["secret"]
    assert recordings.CLUE["recording"] in recordings.RECORDINGS
    assert "not show who killed" in recordings.CLUE["conclusion"]
    for rec in recordings.RECORDINGS.values():
        assert rec["suspect"] in content.ROLES
    for text in [recordings.CLUE["conclusion"], recordings.CLUE["notebook"]]:
        assert "murderer" not in text.lower()


def test_transcripts_have_no_script_marks():
    for rid in recordings.RECORDINGS:
        text = recordings.transcript(rid)
        assert "|" not in text and "^" not in text and "_" not in text
