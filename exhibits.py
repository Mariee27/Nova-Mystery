"""The pictures of the evidence mini-games, drawn as SVG from the case's own words.

Pure functions: text in, SVG text out. Every word is escaped, so a text written by the AI
can never become markup. Nothing here knows the solution of a case.

- camera_still: the jigsaw picture. The campus illustration of the place (assets/minigames/
  puzzles, or the middle of a print from scratchcards) with the overlay of a security camera: REC, camera number, place, time, caption.
- document: the picture under the scratch-off coating. A handwritten note, a printout, a
  phone screen or a photo print of the campus with a caption on it.
"""

import functools
import html
import pathlib
import re

ASSETS = pathlib.Path(__file__).resolve().parent / "assets" / "minigames"

# Which campus illustration the night camera of each place shows: a jigsaw picture
# (puzzles/, 300 × 300), or the middle of a photo print (scratchcards/, 400 × 500).
STILL_PICTURE = {"Hovione Atrium": "atrium", "Library": "library", "Main Deck": "deck",
                 "Auditorium": "auditorium", "Canteen": "canteen", "Garage": "garage"}
STILL_FROM_PRINT = {"Beach": "beach", "Santander Hall": "stairs", "Horizon Hall": "facade"}
STILL_DEFAULT = "facade"
PHOTO_PICTURE = {"Hovione Atrium": "skylight", "Library": "library-night", "Main Deck": "facade",
                 "Beach": "beach"}
PHOTO_DEFAULT = "stairs"

STYLES = ("note", "printout", "phone", "photo")
LINE_LIMIT = 30          # characters per line of a document: what fits 400 px at these fonts
TITLE_LIMIT = 28
MAX_LINES = 5

HAND = "'Bradley Hand','Segoe Print','Comic Sans MS',cursive"
MONO = "'Courier New',Courier,monospace"
SANS = "Helvetica,Arial,sans-serif"


def e(text):
    return html.escape(str(text), quote=True)


@functools.lru_cache(maxsize=None)
def _asset(name):
    return (ASSETS / name).read_text(encoding="utf-8")


def _inner(svg):
    """The drawing inside an SVG file, without its outer <svg> element."""
    start = svg.index(">", svg.index("<svg")) + 1
    return svg[start:svg.rindex("</svg>")]


# ---------------------------------------------------------------- the jigsaw

def still_picture(location):
    return STILL_PICTURE.get(location) or STILL_FROM_PRINT.get(location, STILL_DEFAULT)


def _still_base(location):
    name = still_picture(location)
    if name in STILL_PICTURE.values():
        return _asset(f"puzzles/{name}.svg")
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300" width="300" height="300">'
            '<svg width="300" height="300" viewBox="0 50 400 400" preserveAspectRatio="xMidYMid slice">'
            + _inner(_asset(f"scratchcards/{name}.svg")) + '</svg></svg>')


def camera_still(location, camera, clock, caption):
    """A security-camera still of the place, 300 × 300."""
    base = _still_base(location)
    overlay = (
        '<defs><pattern id="cm-scan" width="4" height="4" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="1" fill="#000" opacity=".18"/></pattern></defs>'
        '<rect width="300" height="300" fill="url(#cm-scan)"/>'
        '<rect width="300" height="24" fill="#05080d" opacity=".72"/>'
        '<circle cx="14" cy="12" r="4.5" fill="#ff3b3b"/>'
        f'<text x="23" y="16.5" font-family="{MONO}" font-size="11" font-weight="bold" fill="#ff6b6b">REC</text>'
        f'<text x="58" y="16.5" font-family="{MONO}" font-size="11" fill="#e8edf3">CAM {int(camera):02d}</text>'
        f'<text x="292" y="16.5" font-family="{MONO}" font-size="11" fill="#e8edf3" text-anchor="end">'
        f'{e(location.upper())}</text>'
        '<rect y="276" width="300" height="24" fill="#05080d" opacity=".72"/>'
        f'<text x="8" y="292" font-family="{MONO}" font-size="10.5" fill="#f2d79a">{e(caption.upper())}</text>'
        f'<text x="292" y="292" font-family="{MONO}" font-size="11" fill="#e8edf3" text-anchor="end">{e(clock)}</text>'
        '<g stroke="#e8edf3" stroke-width="2" fill="none" opacity=".8">'
        '<path d="M10 34 v-6 h6 M290 34 v-6 h-6 M10 266 v6 h6 M290 266 v6 h-6"/></g>'
    )
    return base[:base.rindex("</svg>")] + overlay + "</svg>"


# ---------------------------------------------------------------- the scratch card

def document(style, title, lines, location):
    """The picture under the coating, 400 × 500."""
    lines = [str(line) for line in lines][:MAX_LINES]
    draw = {"note": _note, "printout": _printout, "phone": _phone, "photo": _photo}[style]
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500" width="400" height="500">'
            + draw(str(title or ""), lines, location) + "</svg>")


def _note(title, lines, location):
    ruled = "".join(f'<line x1="30" x2="370" y1="{y}" y2="{y}" stroke="#9db4d8" stroke-width="1" opacity=".6"/>'
                    for y in range(118, 470, 46))
    text = "".join(
        f'<text x="{48 + (i % 2) * 6}" y="{110 + i * 46}" font-family="{HAND}" font-size="27" fill="#1f2a44"'
        f' transform="rotate(-1.5 200 {110 + i * 46})">{e(line)}</text>' for i, line in enumerate(lines))
    head = (f'<text x="48" y="66" font-family="{HAND}" font-size="30" font-weight="bold" fill="#1f2a44">{e(title)}</text>'
            if title else "")
    return ('<rect width="400" height="500" fill="#2a2420"/>'
            '<g transform="rotate(-2 200 250)"><rect x="18" y="20" width="364" height="460" fill="#f6eedb"/>'
            '<line x1="62" x2="62" y1="20" y2="480" stroke="#d98a8a" stroke-width="1.5" opacity=".7"/>'
            f'{ruled}{head}{text}'
            '<circle cx="320" cy="420" r="38" fill="none" stroke="#8a5a34" stroke-width="5" opacity=".22"/>'
            '<rect x="160" y="8" width="80" height="26" fill="#e8dcb0" opacity=".85" transform="rotate(4 200 21)"/></g>')


def _printout(title, lines, location):
    body = "".join(f'<text x="80" y="{150 + i * 40}" font-family="{MONO}" font-size="17" fill="#1b1b1b">{e(line)}</text>'
                   for i, line in enumerate(lines))
    bars = "".join(f'<rect x="{96 + i * 7}" y="408" width="{2 + (i * 7) % 4}" height="44" fill="#1b1b1b"/>'
                   for i in range(30))
    return ('<rect width="400" height="500" fill="#20242c"/>'
            f'<path d="M62 10 H338 V480 {_zigzag(338, 62, 480)} Z" fill="#fbfaf6"/>'
            f'<text x="200" y="52" font-family="{MONO}" font-size="15" font-weight="bold" fill="#1b1b1b" text-anchor="middle">'
            f'{e(title.upper() or "NOVA SBE")}</text>'
            f'<text x="200" y="76" font-family="{MONO}" font-size="12" fill="#555" text-anchor="middle">'
            f'{e(location.upper())}</text>'
            '<line x1="80" x2="320" y1="96" y2="96" stroke="#1b1b1b" stroke-dasharray="5 4"/>'
            f'{body}'
            '<line x1="80" x2="320" y1="384" y2="384" stroke="#1b1b1b" stroke-dasharray="5 4"/>'
            f'{bars}')


def _zigzag(x_from, x_to, y, step=12, depth=10):
    """The torn bottom edge of a receipt, from right to left."""
    points, x, down = [], x_from, True
    while x - step > x_to:
        x -= step
        points.append(f"L{x} {y + depth if down else y}")
        down = not down
    points.append(f"L{x_to} {y}")
    return " ".join(points)


def _phone(title, lines, location):
    bubbles = []
    y = 132
    for i, line in enumerate(lines):
        width = min(300, 28 + len(line) * 9.6)
        x = 54 if i % 2 == 0 else 346 - width
        fill, ink = ("#2b3550", "#eef2f8") if i % 2 == 0 else ("#2f6fd6", "#ffffff")
        bubbles.append(f'<rect x="{x:.0f}" y="{y}" width="{width:.0f}" height="40" rx="18" fill="{fill}"/>'
                       f'<text x="{x + 14:.0f}" y="{y + 26}" font-family="{SANS}" font-size="16" fill="{ink}">{e(line)}</text>')
        y += 56
    return ('<rect width="400" height="500" fill="#16120f"/>'
            '<rect x="34" y="14" width="332" height="472" rx="38" fill="#0b0e14" stroke="#3a3f4a" stroke-width="3"/>'
            '<rect x="156" y="26" width="88" height="18" rx="9" fill="#000"/>'
            '<rect x="46" y="56" width="308" height="52" fill="#141a24"/>'
            '<circle cx="78" cy="82" r="16" fill="#4a5a78"/>'
            f'<text x="104" y="80" font-family="{SANS}" font-size="16" font-weight="bold" fill="#eef2f8">{e(title or "Unknown")}</text>'
            f'<text x="104" y="98" font-family="{SANS}" font-size="11" fill="#8f9bb0">last seen tonight</text>'
            + "".join(bubbles) +
            '<rect x="46" y="430" width="308" height="40" rx="20" fill="#141a24"/>'
            f'<text x="66" y="455" font-family="{SANS}" font-size="13" fill="#5c6678">Message</text>')


def _photo(title, lines, location):
    picture = _asset(f"scratchcards/{PHOTO_PICTURE.get(location, PHOTO_DEFAULT)}.svg")
    caption = "".join(f'<text x="44" y="{438 + i * 30}" font-family="{HAND}" font-size="24" fill="#1f2a44">{e(line)}</text>'
                      for i, line in enumerate(lines[:2]))
    stamp = (f'<text x="360" y="396" font-family="{MONO}" font-size="16" font-weight="bold" fill="#ff8a2a"'
             f' text-anchor="end" opacity=".9">{e(title)}</text>' if title else "")
    return ('<rect width="400" height="500" fill="#24201c"/>'
            '<g transform="rotate(1.5 200 250)"><rect x="14" y="10" width="372" height="480" fill="#f7f5ef"/>'
            '<svg x="30" y="26" width="340" height="380" viewBox="0 0 400 500" preserveAspectRatio="xMidYMid slice">'
            + _inner(picture) + '</svg>' + stamp + caption + '</g>')


def fits(text, limit=LINE_LIMIT):
    """True if a line fits a document (and holds no control characters)."""
    return isinstance(text, str) and 0 < len(text) <= limit and not re.search(r"[\x00-\x1f]", text)
