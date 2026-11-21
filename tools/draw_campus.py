"""Run: python tools/draw_campus.py

Draws assets/minigames/puzzles/campus.svg from the campus map (content.BUILDINGS, GROUNDS,
ROADS): the same plan, seen at dusk from a camera on the beach side, looking across the campus."""
import math, sys
ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import content

W = H = 300
CAM = (64.0 * 1.25, 135.0)             # south of the campus, beyond the beach road
TARGET = (50.0 * 1.25, 30.0)
CAM_H = 55.0                          # how high the camera hangs (map units)
F = 200.0                             # focal length in pixels
HORIZON = 34.0                        # where the horizon lies on the picture
dx, dy = TARGET[0] - CAM[0], TARGET[1] - CAM[1]
n = math.hypot(dx, dy); DIR = (dx / n, dy / n)

def project(x, y, z=0.0):
    X, Y = x * 1.25, y
    vx, vy = X - CAM[0], Y - CAM[1]
    depth = vx * DIR[0] + vy * DIR[1]
    lateral = DIR[0] * vy - DIR[1] * vx          # positive = to the right on screen
    return (W / 2 + F * lateral / depth, HORIZON + F * (CAM_H - z) / depth), depth

def pts(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)

HEIGHT = {"A": 5.0, "I": 4.2, "B": 3.4, "C": 3.4, "D": 3.4, "E": 3.4, "H": 4.0, "G": 3.6, "F": 5.4}
out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300" width="300" height="300">',
       '<!-- The NOVA SBE campus at dusk, drawn by tools/draw_campus.py from the campus map (content.BUILDINGS): the long Gallery '
       'with the Hovione Atrium at its far end, the academic halls B to E as parallel wings toward the '
       'viewer, Library and Horizon Hall behind it, the Grand Auditorium at its near end; the road, the '
       'roundabout and Carcavelos beach in front. Generated, do not edit by hand. -->',
       '<defs><linearGradient id="cs-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#18213f"/>'
       '<stop offset=".6" stop-color="#5d4a78"/><stop offset="1" stop-color="#e3925a"/></linearGradient>'
       '<linearGradient id="cs-land" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a4a3a"/>'
       '<stop offset="1" stop-color="#1d2a1f"/></linearGradient></defs>',
       f'<rect width="300" height="{HORIZON + 1:.0f}" fill="url(#cs-sky)"/>',
       f'<rect y="{HORIZON:.0f}" width="300" height="{300 - HORIZON:.0f}" fill="url(#cs-land)"/>',
       f'<path d="M0 {HORIZON:.0f} Q60 {HORIZON - 6:.0f} 120 {HORIZON - 3:.0f} T300 {HORIZON - 5:.0f} V{HORIZON:.0f} H0 Z" fill="#26324a"/>',
       ''.join(f'<circle cx="{x}" cy="{y * (HORIZON - 6) / 30:.1f}" r="1.1" fill="#f6efd8"/>' for x, y in ((40, 22), (120, 12), (250, 26), (190, 8)) if HORIZON > 12)]
COLORS = {"lawn": "#355a35", "open": "#4d5a40", "sand": "#d8b98a", "sea": "#2f4f7a"}
for kind, shape in content.GROUNDS:
    out.append(f'<polygon points="{pts(project(x, y)[0] for x, y in shape)}" fill="{COLORS[kind]}"/>')
# paths and courtyards between the wings
for name, line, _ in content.ROADS:
    width = 2.2 if name else 1.6
    out.append(f'<polyline points="{pts(project(x, y)[0] for x, y in line)}" fill="none" stroke="#6b6f78" '
               f'stroke-width="{width * 2.2:.1f}" stroke-linejoin="round"/>')
out.append(f'<polygon points="{pts(project(x, y)[0] for x, y in [(100, 66), (100, 70), (80, 100), (77, 100)])}" fill="#f3efe6" opacity=".7"/>')

def building(letter, shape):
    h = HEIGHT[letter]
    base = [project(x, y)[0] for x, y in shape]
    top = [project(x, y, h)[0] for x, y in shape]
    parts = []
    k = len(shape)
    walls = []
    for i in range(k):
        j = (i + 1) % k
        (ax, ay), (bx, by) = shape[i], shape[j]
        # outward normal of the edge (shape is clockwise on screen coords: y down)
        nx, ny = (by - ay), -(bx - ax)
        mx, my = (ax + bx) / 2 * 1.25, (ay + by) / 2
        facing = nx * 1.25 * (CAM[0] - mx) + ny * (CAM[1] - my)
        if facing <= 0:
            continue
        depth = project((ax + bx) / 2, (ay + by) / 2)[1]
        light = 0.5 + 0.5 * max(0.0, (nx * 0.6 + ny * 0.8) / math.hypot(nx, ny))
        shade = int(196 + 50 * light)
        quad = [base[i], base[j], top[j], top[i]]
        band = [project(ax + (bx - ax) * t, ay + (by - ay) * t, h * zz)[0]
                for t, zz in ((0.06, 0.45), (0.94, 0.45), (0.94, 0.72), (0.06, 0.72))]
        walls.append((depth, f'<polygon points="{pts(quad)}" fill="rgb({shade},{shade},{shade + 4})" stroke="#9aa3b0" stroke-width=".4"/>'
                             f'<polygon points="{pts(band)}" fill="#ffcf7a" opacity=".85"/>'))
    for _, svg in sorted(walls, reverse=True):
        parts.append(svg)
    parts.append(f'<polygon points="{pts(top)}" fill="#eef0f3" stroke="#c3c9d2" stroke-width=".5"/>')
    if letter == "I":   # the solar panels on the Gallery's roof
        (a, b, c, d) = shape
        def lerp(p, q, t): return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
        for t0 in (0.1, 0.4, 0.7):
            strip = [lerp(a, b, t0), lerp(a, b, t0 + 0.22), lerp(d, c, t0 + 0.22), lerp(d, c, t0)]
            strip = [lerp(p, q, s) for (p, q), s in zip([(strip[0], strip[3]), (strip[1], strip[2]), (strip[2], strip[1]), (strip[3], strip[0])], (0.25, 0.25, 0.25, 0.25))]
            parts.append(f'<polygon points="{pts(project(x, y, h + .05)[0] for x, y in strip)}" fill="#3d5f9a"/>')
    return parts

import random
def inside(px, py, poly):
    hit = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit
def near_building(px, py):
    return any(inside(px + ex, py + ey, b["shape"]) for b in content.BUILDINGS.values()
               for ex, ey in ((0, 0), (2, 0), (-2, 0), (0, 2), (0, -2)))
rng = random.Random(7)
water = [shape for kind, shape in content.GROUNDS if kind in ("sand", "sea")]
items = []
for _ in range(260):
    x, y = rng.uniform(-30, 105), rng.uniform(-40, 86)
    if near_building(x, y) or any(inside(x, y, w) for w in water) or (70 < x < 96 and y > 0 and abs(x - (93 - y * 0.2)) < 4):
        continue
    (sx, sy), d = project(x, y)
    if d <= 5 or not (-10 < sx < 310 and -10 < sy < 310):
        continue
    (tx, ty), _ = project(x, y, 2.2)
    r = max(0.8, 150 / d)
    tone = rng.choice(["#1e3524", "#24402a", "#2b4a2f"])
    items.append((d, f'<ellipse cx="{tx:.1f}" cy="{ty:.1f}" rx="{r:.1f}" ry="{r * .8:.1f}" fill="{tone}"/>'))
for letter, b in content.BUILDINGS.items():
    cx, cy = sum(p[0] for p in b["shape"]) / 4, sum(p[1] for p in b["shape"]) / 4
    items.append((project(cx, cy)[1], "".join(building(letter, b["shape"]))))
for _, svg in sorted(items, key=lambda it: -it[0]):
    out.append(svg)
# lamps along the road and a person on the promenade
for x, y in [(80, 80), (86, 66), (60, 88), (40, 88.5)]:
    (sx, sy), d = project(x, y, 0)
    (tx, ty), _ = project(x, y, 3)
    r = max(1.2, 160 / d)
    out.append(f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="#141820" stroke-width="{r / 2:.1f}"/>'
               f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{r:.1f}" fill="#ffe2a0"/>'
               f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{r * 3:.1f}" fill="#ffe2a0" opacity=".18"/>')
out.append('<rect width="300" height="300" fill="none" stroke="#0d1a2e" stroke-width="6"/></svg>')
open(ROOT / "assets" / "minigames" / "puzzles" / "campus.svg", "w", encoding="utf-8").write("\n".join(out))
