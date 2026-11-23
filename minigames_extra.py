"""Two more evidence mini-games: Spot the difference and Find the object.

They plug into minigames.py (KINDS, spec, verify, feedback, solve) and into the one mini-game
component of minigame_ui.py (CSS and JS below), and reuse everything else: the seal on a place,
launching, the Python-side check, hints, wrong-answer limits and the reward.

  spot  👁️  two stills of a NOVA SBE place, one of them changed in four spots: tap the changes
  find  🔎  a still of a NOVA SBE place: tap the one object the note asks for

Each game has five predefined variants, drawn on the campus illustrations of assets/minigames/
puzzles (exhibits._asset). Which variant a place shows is drawn from the case seed and the place,
so it is random per game, the same for every player, and stable across reruns and reloads.
The phone gets the pictures and the spots (it highlights a find at once, like the jigsaw shows a
piece in place); the server checks the player's taps before the clue is handed out.
"""

import math
import random

import exhibits

KINDS = ("spot", "find")

KIND_INFO = {
    "spot": {"icon": "👁️", "name": "Spot the difference", "exhibit": "Two prints of one photo",
             "verb": "Tap every change in the copy."},
    "find": {"icon": "🔎", "name": "Find the object", "exhibit": "The photo of the scene",
             "verb": "Tap the object the note asks for."},
}
MIN_SECONDS = {"spot": 5, "find": 3}
SPARE_TAPS = 12        # taps that miss, before the copy has to be searched again from the start
VARIANTS = 5


def _rng(game, location, kind):
    return random.Random(f"{game['case']['seed']}|{location}|{kind}-variant")


# The picture that shows the place itself. A place with its own picture always shows it;
# the others show a random one (a photo taken somewhere else and left there).
PICTURE_OF = {"Hovione Atrium": "atrium", "Library": "library", "Main Deck": "deck", "Canteen": "canteen",
              "Garage": "garage", "Auditorium": "auditorium"}


def variant_of(game, location, kind):
    """Which of the five variants this place shows in this game."""
    looks = SPOT if kind == "spot" else FIND
    own = [i for i, look in enumerate(looks) if look["scene"] == PICTURE_OF.get(location)]
    if own:
        return own[0]
    return _rng(game, location, kind).randrange(VARIANTS)


def _photo_of(look, location, victim):
    """Where the photo comes from: the place itself, or a photo the victim took elsewhere."""
    if look["scene"] == PICTURE_OF.get(location):
        return f"a photo of this room, the {location}"
    return f"a photo {victim} took of {look['title']} that evening, left in the {location}"


def _scene(name):
    return exhibits._asset(f"puzzles/{name}.svg")


def _with(svg, overlay):
    return svg[:svg.rindex("</svg>")] + overlay + "</svg>"


def _where(x, y):
    """Where a spot of a 300 x 300 picture is, in words."""
    across = "left" if x < 100 else "right" if x > 200 else ""
    down = "top" if y < 100 else "bottom" if y > 200 else ""
    if across and down:
        return f"at the {down} {across}"
    if across:
        return f"on the {across}"
    return f"at the {down}" if down else "in the middle"


# ---------------------------------------------------------------- spot the difference
# Every change: (SVG drawn over the copy, x, y, radius of the spot that counts, what it is).

SPOT = [
    {"scene": "atrium", "title": "the Hovione Atrium", "changes": [
        ('<rect x="152" y="153" width="25" height="27" fill="#ffd88a"/>', 164, 166, 15, "a lit window pane"),
        ('<rect x="234" y="256" width="12" height="12" rx="3" fill="#b03030"/>', 240, 262, 13, "a red bag"),
        ('<g fill="#b03030"><circle cx="186" cy="244" r="5"/><path d="M180 274 q0 -24 6 -24 q6 0 6 24 z"/></g>',
         186, 258, 16, "a red jacket"),
        ('<rect x="14" y="132" width="12" height="16" fill="#5a6a80"/>', 20, 140, 13, "a dark window"),
    ]},
    {"scene": "library", "title": "the library", "changes": [
        ('<rect x="130" y="128" width="30" height="16" fill="#2b3550"/>', 145, 136, 15, "a dark window"),
        ('<circle cx="253.2" cy="204" r="5.5" fill="#6b7280"/>', 253, 204, 14, "a lamp that is off"),
        ('<g fill="#111"><ellipse cx="200" cy="244" rx="8" ry="5"/><circle cx="193" cy="238" r="4"/>'
         '<path d="M190 236 l2 -5 l2 4 z M194 235 l2 -5 l2 4 z"/></g>', 198, 241, 14, "a black cat"),
        ('<rect x="119" y="180" width="18" height="28" fill="#ffd98f"/>', 128, 194, 15, "nobody in the door"),
    ]},
    {"scene": "deck", "title": "the Main Deck", "changes": [
        ('<rect x="84" y="56" width="32" height="7" fill="#c0392b"/>', 100, 60, 14, "a red banner top"),
        ('<polygon points="208,214 256,226 256,262 208,248" fill="#2f9e5b"/>'
         '<polygon points="208,214 214,210 262,222 256,226" fill="#4cc27f"/>', 232, 236, 20, "a green booth"),
        ('<g><rect x="105" y="246" width="9" height="9" rx="1" fill="#ffffff"/>'
         '<path d="M114 248 q4 2 0 5" stroke="#ffffff" stroke-width="1.5" fill="none"/></g>', 110, 250, 13,
         "a cup on the table"),
        ('<rect x="134" y="134" width="32" height="10" fill="#f4f5f6"/>', 150, 139, 15, "a missing word"),
    ]},
    {"scene": "canteen", "title": "the canteen", "changes": [
        ('<rect x="203" y="131" width="78" height="13" fill="#1d2330"/><text x="242" y="141" '
         'font-family="Helvetica, Arial, sans-serif" font-size="9" font-weight="bold" letter-spacing="2" '
         'fill="#f2d79a" text-anchor="middle">MENU · 13:00</text>', 242, 137, 17, "another time on the menu"),
        ('<rect x="248" y="258" width="18" height="22" fill="#9b3b2f"/>', 257, 268, 14, "a red flower pot"),
        ('<circle cx="150" cy="263" r="4.5" fill="#c0392b"/>', 150, 263, 13, "an apple on the table"),
        ('<ellipse cx="240" cy="28" rx="11" ry="4" fill="#6b6b6b"/>', 240, 27, 15, "a lamp that is off"),
    ]},
    {"scene": "garage", "title": "the garage", "changes": [
        ('<rect x="132" y="104" width="36" height="12" rx="1" fill="#b8322b"/><text x="150" y="113.5" '
         'font-family="Helvetica, Arial, sans-serif" font-size="8" font-weight="bold" fill="#fff2f0" '
         'text-anchor="middle">EXIT</text>', 150, 110, 15, "a red exit sign"),
        ('<rect x="170" y="186" width="56" height="26" rx="8" fill="#e0b43a"/>'
         '<rect x="178" y="178" width="38" height="14" rx="5" fill="#c99d2a"/>'
         '<rect x="182" y="181" width="14" height="9" fill="#9ec3e8"/><rect x="199" y="181" width="13" height="9" '
         'fill="#9ec3e8"/><circle cx="182" cy="213" r="6" fill="#16181d"/><circle cx="214" cy="213" r="6" '
         'fill="#16181d"/>', 198, 196, 22, "a yellow car"),
        ('<rect x="78" y="242" width="12" height="6" fill="#f4f4f2"/>', 84, 245, 13, "a missing stripe"),
        ('<polygon points="232,224 238,240 226,240" fill="#ff7a1a"/><rect x="224" y="240" width="16" height="3" '
         'fill="#ff7a1a"/>', 232, 234, 13, "a traffic cone"),
    ]},
]


def _spot_spec(game, location, victim):
    look = SPOT[variant_of(game, location, "spot")]
    base = _scene(look["scene"])
    copy = _with(base, "".join(change[0] for change in look["changes"]))
    changes = look["changes"]
    return {
        "story": f"Two prints of {_photo_of(look, location, victim)}. Somebody changed "
                 f"one of them in {len(changes)} places. Tap every change in the copy.",
        "left": base, "right": copy, "spots": [[x, y, r] for _, x, y, r, _ in changes],
        "spare": SPARE_TAPS,
        "hints": ["Compare the two pictures part by part: first the top, then the middle, then the bottom.",
                  f"One change is {_where(changes[0][1], changes[0][2])}: {changes[0][4]}.",
                  "The changes: " + "; ".join(f"{what} ({_where(x, y)})" for _, x, y, _, what in changes) + "."],
    }


def _spot_found(look, taps):
    """How many changes these taps found."""
    return sum(1 for _, x, y, r, _ in look["changes"]
               if any(math.hypot(tx - x, ty - y) <= r for tx, ty in taps))


def _taps(value, limit):
    """A list of [x, y] taps inside the picture, or None."""
    if not isinstance(value, list) or not 0 < len(value) <= limit:
        return None
    taps = []
    for tap in value:
        if (not isinstance(tap, (list, tuple)) or len(tap) != 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 300 for v in tap)):
            return None
        taps.append((float(tap[0]), float(tap[1])))
    return taps


# ---------------------------------------------------------------- find the object

def _object(name, x, y, turn=0):
    """A small object drawn at (x, y): about 14 px in a 300 px picture."""
    shapes = {
        "keycard": '<rect x="-7" y="-4.5" width="14" height="9" rx="1.5" fill="#2f6fd6"/>'
                   '<rect x="-7" y="-1.5" width="14" height="2" fill="#ffffff"/>',
        "phone": '<rect x="-3.5" y="-6" width="7" height="12" rx="1.5" fill="#111"/>'
                 '<rect x="-2.5" y="-4.5" width="5" height="8" fill="#3a7bd5"/>',
        "glasses": '<g fill="none" stroke="#1b1b1b" stroke-width="1.6"><circle cx="-3.5" cy="0" r="3"/>'
                   '<circle cx="3.5" cy="0" r="3"/><path d="M-0.5 0 h1"/></g>',
        "key": '<g fill="none" stroke="#c9a227" stroke-width="2"><circle cx="-4" cy="0" r="3"/>'
               '<path d="M-1 0 h8 M5 0 v3"/></g>',
        "cup": '<rect x="-4" y="-4" width="8" height="8" rx="1" fill="#ffffff"/>'
               '<path d="M4 -2 q4 2 0 5" stroke="#ffffff" stroke-width="1.5" fill="none"/>',
        "notebook": '<rect x="-6" y="-4.5" width="12" height="9" rx="1" fill="#8e2f2f"/>'
                    '<path d="M-3 -4.5 v9" stroke="#e6dcc6" stroke-width="1"/>',
        "usb stick": '<rect x="-6" y="-2" width="9" height="4" rx="1" fill="#3d3d3d"/>'
                     '<rect x="3" y="-1.5" width="3" height="3" fill="#bdbdbd"/>',
    }
    return f'<g transform="translate({x} {y}) rotate({turn})">{shapes[name]}</g>'


NAMES = {"keycard": "a keycard", "phone": "a phone", "glasses": "a pair of glasses", "key": "a brass key",
         "cup": "a coffee cup", "notebook": "a red notebook", "usb stick": "a USB stick"}
FIND_RADIUS = 14

FIND = [
    {"scene": "auditorium", "title": "the Grand Auditorium", "target": "keycard", "near": "the third row of seats",
     "objects": [("keycard", 96, 231, -12), ("phone", 210, 203, 8), ("glasses", 60, 262, 0),
                 ("notebook", 240, 282, 10), ("cup", 236, 150, 0)]},
    {"scene": "atrium", "title": "the Hovione Atrium", "target": "key", "near": "the person on the right",
     "objects": [("key", 214, 280, 20), ("usb stick", 70, 286, -10), ("cup", 130, 252, 0),
                 ("phone", 98, 266, 14), ("glasses", 262, 292, 0)]},
    {"scene": "library", "title": "the library", "target": "phone", "near": "the lamp on the right",
     "objects": [("phone", 238, 262, -20), ("notebook", 60, 278, 8), ("cup", 152, 230, 0),
                 ("keycard", 110, 290, 15), ("key", 186, 286, 0)]},
    {"scene": "canteen", "title": "the canteen", "target": "glasses", "near": "the front table",
     "objects": [("glasses", 140, 262, 0), ("keycard", 60, 232, 8), ("phone", 160, 232, 0),
                 ("cup", 100, 202, 0), ("usb stick", 276, 286, 30)]},
    {"scene": "garage", "title": "the garage", "target": "usb stick", "near": "the barrier",
     "objects": [("usb stick", 52, 262, -25), ("keycard", 204, 238, 10), ("key", 150, 276, 0),
                 ("glasses", 266, 280, 0), ("cup", 110, 230, 0)]},
]


def _find_spec(game, location, victim):
    look = FIND[variant_of(game, location, "find")]
    target = next(item for item in look["objects"] if item[0] == look["target"])
    picture = _with(_scene(look["scene"]), "".join(_object(*item) for item in look["objects"]))
    thing = look["target"].replace("usb", "USB")
    wanted = f"{victim}'s {thing}"
    return {
        "story": f"{_photo_of(look, location, victim)[0].upper()}{_photo_of(look, location, victim)[1:]}. "
                 f"On the back: “Where did {victim} leave "
                 f"the {thing}?” Find it in the picture.",
        "ask": f"Find {wanted}",
        "image": picture, "target": [target[1], target[2], FIND_RADIUS],
        "objects": [[NAMES[name], x, y] for name, x, y, _ in look["objects"]],
        "hints": ["It is small: look at the floor, the tables and the seats.",
                  f"It is {_where(target[1], target[2])}.",
                  f"It lies near {look['near']}."],
    }


# ---------------------------------------------------------------- the interface for minigames.py

def spec(game, location, kind, variant, number, evidence_id, victim):
    """Everything the phone needs to draw the game (the same keys as every other mini-game)."""
    info = KIND_INFO[kind]
    data = {
        "id": f"MG-{number:02d}-{kind}", "kind": kind, "variant": variant, "location": location,
        "evidence_id": evidence_id, "evidence_no": number,
        "icon": info["icon"], "name": info["name"], "verb": info["verb"], "exhibit": info["exhibit"],
    }
    data.update(_spot_spec(game, location, victim) if kind == "spot" else _find_spec(game, location, victim))
    return data


def verify(game, location, kind, proof):
    """True only if the taps really solve the game of this place."""
    try:
        if kind == "spot":
            look = SPOT[variant_of(game, location, "spot")]
            taps = _taps(proof.get("taps"), len(look["changes"]) + SPARE_TAPS)
            return taps is not None and _spot_found(look, taps) == len(look["changes"])
        look = FIND[variant_of(game, location, "find")]
        taps = _taps([proof.get("tap")], 1)
        target = next(item for item in look["objects"] if item[0] == look["target"])
        return taps is not None and math.hypot(taps[0][0] - target[1], taps[0][1] - target[2]) <= FIND_RADIUS
    except (AttributeError, TypeError, ValueError):
        return False


def feedback(game, location, kind, proof):
    """A short note after a wrong answer (never the answer itself)."""
    if kind == "spot":
        look = SPOT[variant_of(game, location, "spot")]
        taps = _taps(proof.get("taps") if isinstance(proof, dict) else None, len(look["changes"]) + SPARE_TAPS)
        if taps is None:
            return "Tap the changes in the copy."
        return f"{_spot_found(look, taps)} of {len(look['changes'])} changes found. Keep looking."
    return "That is not it. Read the note again and look closely."


def solve(game, location, kind):
    """A valid proof (for the tests and the demo bots, never sent to a phone)."""
    if kind == "spot":
        return {"taps": [[x, y] for _, x, y, _, _ in SPOT[variant_of(game, location, "spot")]["changes"]]}
    look = FIND[variant_of(game, location, "find")]
    target = next(item for item in look["objects"] if item[0] == look["target"])
    return {"tap": [target[1], target[2]]}


# ---------------------------------------------------------------- on the phone (added to minigame_ui)

CSS = r"""
/* ---- spot the difference, find the object ---- */
.pic{position:relative;border-radius:8px;overflow:hidden;border:1px solid #2a3446;margin-bottom:10px;touch-action:manipulation;cursor:crosshair}
.pic img{display:block;width:100%;height:auto;-webkit-user-drag:none;user-select:none}
.pic .lbl2{position:absolute;left:6px;top:6px;font-family:var(--mono);font-size:11px;letter-spacing:.08em;background:rgba(0,0,0,.65);
  padding:2px 6px;border-radius:4px;color:var(--ivory);pointer-events:none}
.mk{position:absolute;border-radius:50%;transform:translate(-50%,-50%);pointer-events:none}
.mk.ok{border:3px solid var(--ok);box-shadow:0 0 12px rgba(63,212,155,.7)}
.mk.no{width:22px;height:22px;border:2px solid var(--red);animation:mkout .8s forwards}
@keyframes mkout{to{opacity:0;transform:translate(-50%,-50%) scale(1.6)}}
.ask{font-family:var(--hand);font-size:24px;color:#1d1a16;background:#F3EAD6;border-radius:4px;padding:6px 12px;margin:0 4px 10px;
  transform:rotate(-1deg);box-shadow:0 6px 18px rgba(0,0,0,.4)}
"""

JS = r"""
function picture(root, svg, label) {
  const box = el('div', 'pic', null, root);
  const img = el('img', null, null, box); img.alt = ''; img.draggable = false;
  img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)));
  if (label) el('span', 'lbl2', label, box);
  box.__at = (e) => { const r = img.getBoundingClientRect();
    return [Math.round((e.clientX - r.left) / r.width * 300), Math.round((e.clientY - r.top) / r.height * 300)]; };
  box.__mark = (x, y, r, cls) => { const m = el('span', 'mk ' + cls, null, box);
    m.style.left = (x / 3) + '%'; m.style.top = (y / 3) + '%';
    if (r) { m.style.width = (r * 2 / 3) + '%'; m.style.height = (r * 2 / 3) + '%'; }
    if (cls === 'no') setTimeout(() => m.remove(), 900); return m; };
  return box;
}

BUILD.spot = function (root, data) {
  const pics = [picture(root, data.left, 'ORIGINAL'), picture(root, data.right, 'COPY')];
  const status = el('div', 'status', null, root); status.setAttribute('aria-live', 'polite');
  const go = el('button', 'go', 'Open the evidence', root); go.type = 'button';
  const n = data.spots.length, found = new Set(); let taps = [], marks = [];
  function paint(note, cls) {
    status.textContent = note || (found.size === n ? 'All changes found!' : found.size + ' of ' + n + ' changes found');
    status.className = 'status' + (cls ? ' ' + cls : found.size === n ? ' good' : '');
    go.style.display = found.size === n ? 'block' : 'none';
  }
  pics.forEach(box => box.addEventListener('pointerdown', (e) => {
    if (root.__busy || found.size === n) return;
    SND.unlock(); const [x, y] = box.__at(e); taps.push([x, y]);
    const hit = data.spots.findIndex((s, i) => !found.has(i) && (x - s[0]) ** 2 + (y - s[1]) ** 2 <= s[2] ** 2);
    if (hit >= 0) {
      found.add(hit); const s = data.spots[hit];
      pics.forEach(b => marks.push(b.__mark(s[0], s[1], s[2], 'ok'))); SND.tap(); buzz(12);
      if (found.size === n) { SND.good(); buzz([20, 40, 20]); }
      paint();
    } else {
      box.__mark(x, y, 0, 'no'); buzz(6);
      if (taps.length > n + data.spare) {
        found.clear(); taps = []; marks.forEach(m => m.remove()); marks = [];
        paint('Too many guesses – look again from the start.', 'bad'); return;
      }
      paint();
    }
  }));
  go.onclick = () => { if (root.__busy || found.size !== n) return; SND.unlock(); SND.tap(); root.__busy = true;
    status.textContent = 'Checking…'; status.className = 'status'; root.__send('submit', { taps: taps.slice() }); };
  paint();
};

BUILD.find = function (root, data) {
  el('div', 'ask', data.ask, root);
  const box = picture(root, data.image, null);
  const status = el('div', 'status', 'Tap the object in the picture', root); status.setAttribute('aria-live', 'polite');
  const go = el('button', 'go', 'Take it', root); go.type = 'button'; go.style.display = 'none';
  let tap = null, ring = null;
  box.addEventListener('pointerdown', (e) => {
    if (root.__busy) return;
    SND.unlock(); const [x, y] = box.__at(e); const t = data.target;
    if ((x - t[0]) ** 2 + (y - t[1]) ** 2 <= t[2] ** 2) {
      tap = [x, y]; if (ring) ring.remove(); ring = box.__mark(t[0], t[1], t[2] + 4, 'ok');
      status.textContent = 'Found it!'; status.className = 'status good'; go.style.display = 'block';
      SND.good(); buzz([20, 40, 20]);
    } else {
      box.__mark(x, y, 0, 'no'); buzz(6);
      const near = data.objects.find(o => (x - o[1]) ** 2 + (y - o[2]) ** 2 <= 14 * 14);
      status.textContent = near ? 'That is ' + near[0] + ' – not what the note asks for.' : 'Nothing there. Look closer.';
      status.className = 'status bad';
    }
  });
  go.onclick = () => { if (root.__busy || !tap) return; SND.unlock(); SND.tap(); root.__busy = true;
    status.textContent = 'Checking…'; status.className = 'status'; root.__send('submit', { tap: tap }); };
};
"""
