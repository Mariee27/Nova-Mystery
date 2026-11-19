"""The audio archive of Case #001 "The Last Lecture": bundled demo recordings.

The recordings are SYNTHETIC SAMPLES, made here from code (no voice actor, no text-to-speech
service, no files to download): voiced syllables with a pitch contour and vowel formants, real
pauses, a quiet room tone, and in one recording a struck bell behind the voice. They are labelled
as synthetic wherever they are shown. The transcripts are the written statements the syllables
stand for; the analyser never "hears" words.

Every recording is built from a fixed seed, so it is identical on every run and every machine,
and so is every measurement made from it.

The one piece of real audio evidence (the bell in the guard's radio check-in) only uses facts
that are already canonical in case #001 (content.py): the university bell rings eleven times at
23:00, the Main Deck holds tonight's patrol log, and the Security Guard's secret is that three
patrols in the log never happened. It exposes a false log entry – never who the murderer is,
which the generator decides anew in every game.
"""

import math

import numpy as np

import content
import forensics

RATE = 16000
SYNTHETIC_NOTE = "Synthetic sample, generated for the demo – not a real person's voice."

# Vowel formants (F1, F2, F3) in Hz, roughly like spoken English vowels.
VOWELS = ((730, 1090, 2440), (530, 1840, 2480), (270, 2290, 3010), (570, 840, 2410),
          (300, 870, 2240), (660, 1720, 2410), (490, 1350, 1690), (440, 1020, 2240))

# Script marks: "|" is a short pause, "||" a long one, "^" makes the next word louder, "_" quieter.
SHORT_PAUSE, LONG_PAUSE = "|", "||"


def _syllables(word):
    groups = len([g for g in "".join(c if c in "aeiouy" else " " for c in word.lower()).split() if g])
    if word.lower().endswith("e") and groups > 1 and not word.lower().endswith(("le", "ee")):
        groups -= 1
    return max(1, groups)


def _resonance(freq, formants, bandwidth=(90, 110, 170)):
    gain = 0.0
    for f, bw in zip(formants, bandwidth):
        gain += 1.0 / (1.0 + ((freq - f) / bw) ** 2)
    return gain


def synth_voice(script, f0=120.0, syllable=0.17, word_gap=0.06, short_pause=0.45, long_pause=0.95,
                loudness_jitter_db=1.5, pitch_wobble=0.04, level_db=-14.0, lead=0.4, tail=0.5,
                min_seconds=0.0, seed=1, rate=RATE):
    """A speech-like signal for a script. Returns (samples, word count).

    Each word becomes one or more voiced syllables (harmonics shaped by vowel formants, below
    3.4 kHz like a telephone voice) with a short consonant burst before it.
    """
    rng = np.random.default_rng(seed)
    pieces = [np.zeros(int(lead * rate))]
    words = 0
    tokens = script.split()
    phrase_pos = 0
    for token in tokens:
        if token == SHORT_PAUSE or token == LONG_PAUSE:
            length = short_pause if token == SHORT_PAUSE else long_pause
            pieces.append(np.zeros(int(length * rng.uniform(0.9, 1.1) * rate)))
            phrase_pos = 0
            continue
        boost = 0.0
        while token[:1] in "^_":
            boost += 6.0 if token[0] == "^" else -6.0
            token = token[1:]
        clean = "".join(c for c in token if c.isalnum() or c in "'-")
        if not clean:
            continue
        words += 1
        word_db = level_db + boost + rng.normal(0, loudness_jitter_db) - 0.6 * phrase_pos
        phrase_pos += 1
        for part in clean.split("-"):
            for _ in range(_syllables(part)):
                pieces.append(_syllable(rng, f0 * (1 - 0.015 * phrase_pos), syllable, word_db,
                                        pitch_wobble, rate))
        pieces.append(np.zeros(int(word_gap * rng.uniform(0.7, 1.3) * rate)))
    pieces.append(np.zeros(int(tail * rate)))
    out = np.concatenate(pieces)
    if min_seconds and len(out) < int(min_seconds * rate):
        out = np.concatenate([out, np.zeros(int(min_seconds * rate) - len(out))])
    return out, words


def _syllable(rng, f0, mean_length, level_db, wobble, rate):
    length = mean_length * rng.uniform(0.8, 1.25)
    n = int(length * rate)
    t = np.arange(n) / rate
    contour = f0 * (1 + wobble * np.sin(2 * math.pi * rng.uniform(2, 4) * t + rng.uniform(0, 6.28))
                    - 0.06 * t / max(length, 1e-3))
    phase = 2 * math.pi * np.cumsum(contour) / rate
    formants = VOWELS[rng.integers(len(VOWELS))]
    voice = np.zeros(n)
    k = 1
    while k * f0 < 3400:
        amp = _resonance(k * f0, formants) / k ** 0.9
        voice += amp * np.sin(k * phase)
        k += 1
    attack, release = int(0.02 * rate), int(0.05 * rate)
    shape = np.ones(n)
    shape[:attack] = np.linspace(0, 1, attack)
    shape[-release:] = np.minimum(shape[-release:], np.linspace(1, 0, release))
    voice *= shape
    voice /= max(1e-9, np.sqrt(np.mean(voice ** 2)))
    # a short consonant: smoothed noise (little energy above 3 kHz)
    burst = rng.normal(0, 1, int(0.03 * rate))
    burst = np.convolve(burst, np.ones(5) / 5, mode="same") * np.hanning(len(burst)) * 0.35
    out = np.concatenate([burst, voice])
    return out * 10 ** (level_db / 20)


def room_tone(n, level_db=-58.0, seed=7, rate=RATE):
    """Quiet, low background noise (a room or a radio channel)."""
    rng = np.random.default_rng(seed)
    noise = np.convolve(rng.normal(0, 1, n), np.ones(9) / 9, mode="same")
    noise /= max(1e-9, np.sqrt(np.mean(noise ** 2)))
    return noise * 10 ** (level_db / 20)


BELL_PARTIALS = ((1.0, 1.0), (2.76, 0.55), (3.92, 0.85), (5.40, 0.45))   # (ratio, amplitude)
BELL_BASE_HZ = 1010.0


def bell(n, strikes, level_db=-24.0, base=BELL_BASE_HZ, decay=0.55, rate=RATE):
    """A struck bell: inharmonic partials that ring and fade, once per strike time (seconds)."""
    out = np.zeros(n)
    ring = int(min(2.5, 6 * decay) * rate)
    t = np.arange(ring) / rate
    tone = np.zeros(ring)
    for ratio, amp in BELL_PARTIALS:
        tone += amp * np.sin(2 * math.pi * base * ratio * t) * np.exp(-t * ratio ** 0.5 / decay)
    tone *= np.minimum(1.0, t / 0.002)
    tone /= np.max(np.abs(tone))
    for when in strikes:
        a = int(when * rate)
        b = min(n, a + ring)
        if a < n:
            out[a:b] += tone[:b - a]
    return out * 10 ** (level_db / 20)


# ---------------------------------------------------------------- the archive

GUARD = "The Security Guard"
LIBRARIAN = "The Night Librarian"
TECHNICIAN = "The IT Technician"

BELL_STRIKES = [1.2 + 1.25 * i for i in range(11)]   # eleven strikes: the 23:00 bell

RECORDINGS = {
    "guard_routine": {
        "title": "Intake interview – routine questions",
        "suspect": GUARD,
        "context": "Recorded at 08:10 the next morning. The detective asks for name, shift and duties.",
        "logged": "Interview room 2, 08:10",
        "script": "I work the night shift in the academic halls. | I start at nine and I finish at five. "
                  "I walk the main deck every hour | and I write each round in the patrol log.",
        "voice": {"f0": 112, "syllable": 0.165, "loudness_jitter_db": 1.0, "short_pause": 0.38, "seed": 11},
    },
    "guard_night": {
        "title": "Interrogation – the night of the murder",
        "suspect": GUARD,
        "context": "Same session, twelve minutes later. The detective asks about 23:00 to 23:47.",
        "logged": "Interview room 2, 08:22",
        "script": "I was on patrol. || The whole time. | I found him at twenty-three forty-seven. || "
                  "^The ^door ^was ^locked. | I did not | _touch _anything. || I checked the log | "
                  "every round is in the log.",
        "voice": {"f0": 118, "syllable": 0.2, "loudness_jitter_db": 4.5, "short_pause": 0.55,
                  "long_pause": 1.25, "seed": 12},
    },
    "guard_radio": {
        "title": "Radio check-in – logged as 23:30",
        "suspect": GUARD,
        "context": "From the radio archive of the Main Deck. The patrol log lists this check-in at 23:30.",
        "logged": "Main Deck radio channel, entry 23:30",
        "script": "Main deck. | Patrol round complete. | Twenty-three thirty. || All quiet. | "
                  "Nothing to report. | Main deck out.",
        "voice": {"f0": 110, "syllable": 0.18, "loudness_jitter_db": 1.2, "short_pause": 0.6,
                  "long_pause": 1.1, "seed": 13, "lead": 0.6, "min_seconds": 15.5},
        "bell": BELL_STRIKES,
    },
    "librarian_statement": {
        "title": "Statement – the reading room",
        "suspect": LIBRARIAN,
        "context": "Recorded at 09:05. The librarian describes the evening in the Library.",
        "logged": "Library office, 09:05",
        "script": "I closed the archive at ten. | After that I sorted returns at the counter. | "
                  "The radiator was knocking all night. | I did not see Professor Vale after nine.",
        "voice": {"f0": 205, "syllable": 0.15, "loudness_jitter_db": 1.4, "short_pause": 0.42, "seed": 21},
    },
    "technician_statement": {
        "title": "Statement – the server room",
        "suspect": TECHNICIAN,
        "context": "Recorded at 09:40. The technician talks about the cameras on the Main Deck.",
        "logged": "Horizon Hall, 09:40",
        "script": "Two cameras were black. | That happens. || Old cables. | I was in the server room "
                  "| ^all ^night. | The backup finished at ten. || I can show you the logs.",
        "voice": {"f0": 135, "syllable": 0.14, "loudness_jitter_db": 3.0, "short_pause": 0.5,
                  "long_pause": 1.0, "seed": 31},
    },
}

DEFAULT_PAIR = ("guard_routine", "guard_night")

# The one recording that holds a background sound worth inspecting, and where.
CLUE = {
    "recording": "guard_radio",
    "segment": (0.9, 15.0),          # seconds: the stretch the lab highlights
    "band": (3600.0, 5800.0),        # Hz: where the bell rings and the voice is quiet
    "title": "Bell strikes behind the voice",
    "hint": "A thin metallic ringing sits under the voice, high above the speech band. "
            "Count its strikes – then find the piece of evidence it belongs to.",
    "expected_strikes": 11,
    "answer": "bell",
    "conclusion": (
        "The patrol log lists this check-in at 23:30. But the bell behind the voice strikes eleven "
        "times – the university bell that rings eleven times at 23:00. The 23:30 entry was spoken "
        "about half an hour early. At least one patrol in tonight's log never happened as written, "
        "so the log cannot be used as an alibi. This exposes a false log entry – on its own it does "
        "not show who killed Vale."),
    "notebook": ("Radio check-in 'logged 23:30' carries eleven bell strikes (the 23:00 bell). "
                 "The patrol log is unreliable: at least one round was recorded in advance."),
}

# The evidence the player can connect the sound to. All of them are canonical case #001 texts.
EVIDENCE = {
    "bell": {"label": "Witness note: the university bell",
             "text": "You noticed the university bell rang eleven times at 23:00, a little late as always.",
             "feedback": None},
    "elevator": {"label": "Witness note: the elevator",
                 "text": "You noticed the main elevator was out of order, so everyone had to take the stairs.",
                 "feedback": "An elevator makes a hum and a chime once – not eleven evenly spaced metallic strikes."},
    "heating": {"label": "Witness note: the heating",
                "text": "You noticed the heating in the east wing clicked off at 23:10 to save energy.",
                "feedback": "A heating relay clicks once and does not ring. The sound repeats eleven times."},
    "deck": {"label": "Main Deck: the guard's booth",
             "text": content.LOCATION_FLAVOR["Main Deck"],
             "feedback": "The booth is where the log is kept – but which evidence tells you what time "
                         "the bell says it is?"},
}

assert "eleven times at 23:00" in EVIDENCE["bell"]["text"]
assert EVIDENCE["bell"]["text"] in content.NEUTRAL_PRIVATE_CLUES
assert EVIDENCE["elevator"]["text"] in content.NEUTRAL_PRIVATE_CLUES
assert EVIDENCE["heating"]["text"] in content.NEUTRAL_PRIVATE_CLUES


def transcript(recording_id):
    script = RECORDINGS[recording_id]["script"]
    return " ".join(w.lstrip("^_") for w in script.split() if w not in (SHORT_PAUSE, LONG_PAUSE))


def render(recording_id):
    """The samples of one bundled recording (deterministic). Returns (samples, rate)."""
    spec = RECORDINGS[recording_id]
    voice, _ = synth_voice(spec["script"], **spec["voice"])
    n = len(voice)
    mix = voice + room_tone(n, seed=spec["voice"]["seed"] + 100)
    if spec.get("bell"):
        mix = mix + bell(n, spec["bell"])
    peak = np.max(np.abs(mix))
    if peak > 0.95:
        mix = mix * (0.95 / peak)
    return mix, RATE


def wav_bytes(recording_id):
    samples, rate = render(recording_id)
    return forensics.encode_wav(samples, rate)
