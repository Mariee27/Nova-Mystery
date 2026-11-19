"""The evidence mini-games on the phone: HTML fragments and one Streamlit component.

Fragments (puzzle head, hints, reward card) are pure functions like ui.py: all text goes
through ui.h() and the strings contain no blank lines.

COMPONENT_CSS / COMPONENT_JS are one st.components.v2 component that draws all four games.
It runs in the page (no iframe), touch first: pointer events for rubbing and the wheel,
big tap targets (at least 48 px), no dragging needed. It only ever reports what the player
did (the code typed, the cells rubbed, the swaps made, the wheel setting); app.py checks
that in Python with minigames.verify before logic.search hands out the evidence.

Sound is off by default. The player can switch it on in the puzzle header (remembered in
this browser); the first tap after that unlocks Web Audio, as iOS and Android require.
"""

from ui import h

PROGRESS_LABEL = "Evidence unlocked"
RENDERERS = {}   # app.mg_renderer: one registered component per name and server process


def sealed_line(spec):
    """One line for the place card: what seals this place."""
    return (f'<div class="mg-seal"><span class="mg-seal-i" aria-hidden="true">{h(spec["icon"])}</span>'
            f'<span><b>Sealed exhibit #{spec["evidence_no"]:02d}</b> · {h(spec["name"])}</span></div>')


def progress(done, total):
    share = 0 if not total else done / total
    return (f'<div class="mg-progress" role="img" aria-label="{done} of {total} pieces of evidence unlocked">'
            f'<div class="mg-progress-t"><span>{PROGRESS_LABEL}</span><b>{done} / {total}</b></div>'
            f'<div class="mg-bar"><i style="width:{share * 100:.0f}%"></i></div></div>')


def puzzle_head(spec, done, total):
    return (f'<div class="mg-head fade-up"><div class="mg-kick">Sealed exhibit #{spec["evidence_no"]:02d} · '
            f'{h(spec["location"])}</div><div class="mg-title"><span aria-hidden="true">{h(spec["icon"])}</span> '
            f'{h(spec["name"])}</div><div class="mg-verb">{h(spec["verb"])} Solving it uses your move '
            f'for this round.</div>{progress(done, total)}</div>')


def hints(texts):
    if not texts:
        return ""
    items = "".join(f'<li><b>Hint {i}</b> {h(t)}</li>' for i, t in enumerate(texts, start=1))
    return f'<ol class="mg-hints" aria-live="polite">{items}</ol>'


def reward(spec, text, exhibit_id, done, total, celebrate):
    """'ACCESS GRANTED': the evidence that a solved puzzle unlocked."""
    css = " celebrate" if celebrate else ""
    return (f'<div class="mg-reward{css}" role="status"><div class="mg-burst" aria-hidden="true"></div>'
            '<div class="mg-lock" aria-hidden="true"><span class="sh"></span><span class="bd"></span></div>'
            '<div class="mg-granted">🔓 Access granted</div><div class="mg-new">New evidence discovered</div>'
            f'<div class="mg-ev">Evidence #{spec["evidence_no"]:02d} — {h(spec["exhibit"])}</div>'
            f'<div class="mg-place">{h(spec["location"])} · Exhibit {h(exhibit_id)} on the board</div>'
            f'<div class="mg-text">{h(text)}</div>{progress(done, total)}'
            '<a class="mg-inspect" href="#evidence-log" target="_self">Inspect it in the evidence log ↓</a></div>')


# ---------------------------------------------------------------- the component

COMPONENT_CSS = r"""
:host{display:block}
.mg{--bg:#0B111B;--panel:#141C2B;--line:rgba(212,168,83,.35);--gold:#D4A853;--red:#E5484D;--ok:#3FD49B;
  --ivory:#F5F1E8;--muted:#A7B0BF;--mono:'Courier Prime','Courier New',ui-monospace,monospace;
  --sans:Inter,system-ui,-apple-system,sans-serif;--hand:Caveat,'Bradley Hand','Segoe Print',cursive;
  font-family:var(--sans);color:var(--ivory);background:linear-gradient(180deg,#121a28,#0b111b);
  border:1px solid var(--line);border-radius:14px;padding:14px;box-sizing:border-box;width:100%;
  box-shadow:0 18px 50px rgba(0,0,0,.45),inset 0 0 40px rgba(212,168,83,.04);-webkit-tap-highlight-color:transparent;
  user-select:none;-webkit-user-select:none;overflow:hidden}
.mg *{box-sizing:border-box}
.top{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.top .k{font-family:var(--mono);font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);flex:1}
button{font:inherit;color:inherit;cursor:pointer;-webkit-appearance:none;appearance:none;touch-action:manipulation}
button:focus-visible{outline:3px solid var(--gold);outline-offset:2px}
.snd{min-width:48px;min-height:44px;border-radius:10px;border:1px solid rgba(167,176,191,.35);background:rgba(255,255,255,.04);font-size:18px}
.snd[aria-pressed=true]{border-color:var(--gold)}
.story{font-size:15px;line-height:1.45;color:#E6E1D6;margin:0 0 10px}
.status{min-height:22px;margin-top:10px;font-family:var(--mono);font-size:14px;letter-spacing:.06em;text-align:center;color:var(--muted)}
.status.bad{color:#FF8A8D}.status.good{color:var(--ok)}
.go{width:100%;min-height:56px;margin-top:12px;border-radius:12px;border:1px solid #f0c674;font-family:var(--mono);
  font-size:16px;letter-spacing:.16em;text-transform:uppercase;background:linear-gradient(180deg,#c42222,#9f1d1d);color:#fff;
  box-shadow:0 8px 26px rgba(185,28,28,.35)}
.go:disabled{opacity:.5;box-shadow:none}
.shake{animation:shake .45s}
@keyframes shake{20%,60%{transform:translateX(-7px)}40%,80%{transform:translateX(7px)}}
/* ---- code lock ---- */
.note{background:#F3EAD6;color:#1d1a16;border-radius:4px;padding:10px 12px;font-family:var(--hand);font-size:22px;line-height:1.15;
  transform:rotate(-1deg);box-shadow:0 6px 18px rgba(0,0,0,.4);margin:0 4px 10px}
.facts{display:flex;gap:8px;margin-bottom:12px}
.facts div{flex:1;border:1px dashed rgba(167,176,191,.4);border-radius:8px;padding:6px 8px;font-size:12px;color:var(--muted)}
.facts b{display:block;font-family:var(--mono);font-size:18px;color:var(--ivory);letter-spacing:.06em}
.lockface{background:#05080D;border:1px solid #2a3446;border-radius:12px;padding:10px 12px 12px;display:flex;flex-direction:column;align-items:stretch;gap:8px}
.slots{display:flex;gap:8px;justify-content:center}
.slots span{flex:1;max-width:58px;height:58px;border-radius:8px;background:#0F1724;border:1px solid #33415a;display:grid;place-items:center;
  font-family:var(--mono);font-size:30px;color:#7DF9C9;text-shadow:0 0 12px rgba(125,249,201,.6)}
.slots span.cur{border-color:var(--gold);box-shadow:0 0 0 2px rgba(212,168,83,.25)}
.led{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-align:center;color:var(--muted)}
.led i{display:inline-block;width:12px;height:12px;border-radius:50%;background:#7a2222;margin-left:6px;vertical-align:-1px}
.led.bad{color:#FF8A8D}.led.bad i{background:var(--red);box-shadow:0 0 12px var(--red)}
.led.wait i{background:var(--gold);animation:blink .6s infinite}
@keyframes blink{50%{opacity:.3}}
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}
.pad button{min-height:60px;border-radius:14px;border:1px solid #2f3b52;background:linear-gradient(180deg,#1b2537,#131b29);
  font-family:var(--mono);font-size:26px;box-shadow:0 3px 0 #0a0f18}
.pad button:active{transform:translateY(2px);box-shadow:none;background:#222e44}
.pad .fn{font-size:18px;color:var(--muted)}
.pad .ok{color:#0b111b;background:linear-gradient(180deg,#e7c27a,#c99a3d);border-color:#f0c674;font-size:16px;letter-spacing:.1em}
.pad button:disabled{opacity:.45}
/* ---- rub to reveal ---- */
.paper{position:relative;width:100%;border-radius:6px;overflow:hidden;background:#232327;box-shadow:0 10px 30px rgba(0,0,0,.5)}
.under{position:absolute;inset:0;padding:22px 18px;background:
  repeating-linear-gradient(115deg,rgba(255,255,255,.03) 0 2px,transparent 2px 5px),radial-gradient(circle at 30% 30%,#3a3a40,#1d1d21);}
.under p{margin:0 0 6px;font-family:var(--hand);font-size:clamp(26px,8vw,36px);line-height:1.15;color:rgba(255,255,255,.88);
  text-shadow:0 1px 0 rgba(0,0,0,.6);transform:rotate(-2deg)}
.under p:nth-child(2){padding-left:18px}.under p:nth-child(4){font-size:clamp(20px,6vw,26px);color:rgba(255,255,255,.65)}
canvas{position:absolute;inset:0;width:100%;height:100%;touch-action:none;cursor:crosshair;transition:opacity .9s}
canvas.gone{opacity:0}
.meter{height:10px;border-radius:5px;background:rgba(255,255,255,.08);margin-top:12px;overflow:hidden}
.meter i{display:block;height:100%;width:0;background:linear-gradient(90deg,#8a6d2f,var(--gold));transition:width .2s}
/* ---- puzzle ---- */
.grid{display:grid;gap:4px;padding:4px;background:#05080D;border-radius:10px;border:1px solid #2a3446;transition:gap .5s,padding .5s}
.tile{position:relative;aspect-ratio:1/1;border-radius:6px;border:2px solid rgba(255,255,255,.12);background-repeat:no-repeat;
  min-height:48px;transition:transform .18s,border-color .2s,box-shadow .2s}
.tile .n{position:absolute;left:4px;top:3px;font-family:var(--mono);font-size:11px;color:#fff;background:rgba(0,0,0,.55);
  border-radius:4px;padding:0 4px}
.tile.in::after{content:"✓";position:absolute;right:4px;bottom:3px;width:20px;height:20px;border-radius:50%;background:rgba(0,0,0,.6);
  color:var(--ok);font-size:13px;display:grid;place-items:center}
.tile.in{border-color:rgba(63,212,155,.55);border-style:solid}
.tile.sel{transform:scale(.92);border-color:var(--gold);box-shadow:0 0 0 3px rgba(212,168,83,.45),0 0 24px rgba(212,168,83,.4)}
.tile.pop{animation:pop .25s}
@keyframes pop{50%{transform:scale(1.06)}}
.grid.done{gap:0;padding:0;border-color:var(--gold);box-shadow:0 0 30px rgba(212,168,83,.35)}
.grid.done .tile{border-radius:0;border-color:transparent}.grid.done .tile .n,.grid.done .tile::after{display:none}
.count{font-family:var(--mono);font-size:13px;color:var(--muted);text-align:center;margin-top:8px}
/* ---- cipher ---- */
.ct{font-family:var(--mono);font-size:clamp(17px,5vw,22px);letter-spacing:.12em;line-height:1.5;text-align:center;word-spacing:.35em;
  background:#05080D;border:1px solid #2a3446;border-radius:10px;padding:10px;color:#FFB3B5}
.pt{font-family:var(--mono);font-size:clamp(17px,5vw,22px);letter-spacing:.12em;line-height:1.5;text-align:center;word-spacing:.35em;
  padding:8px 10px;min-height:44px;color:#7DF9C9;text-shadow:0 0 10px rgba(125,249,201,.35)}
.lbl{font-family:var(--mono);font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);text-align:center;margin-top:8px}
.wheelrow{display:flex;align-items:center;justify-content:center;gap:10px;margin-top:6px}
.turn{min-width:56px;min-height:56px;border-radius:50%;border:1px solid #2f3b52;background:#1b2537;font-size:22px}
.wheel{width:min(62vw,230px);aspect-ratio:1/1;touch-action:none;cursor:grab}
.wheel text{font-family:var(--mono);font-size:11px;text-anchor:middle;dominant-baseline:central}
.wheel .outer text{fill:#7DF9C9}.wheel .inner text{fill:#FFB3B5}
.wheel .inner{transition:transform .25s}
.setting{font-family:var(--mono);text-align:center;font-size:13px;color:var(--muted)}
.setting b{font-size:22px;color:var(--ivory)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

COMPONENT_JS = r"""
const SND = window.__novaSound || (window.__novaSound = {
  ctx: null,
  on() { try { return localStorage.getItem('nova-sound') === 'on'; } catch (e) { return false; } },
  set(v) { try { localStorage.setItem('nova-sound', v ? 'on' : 'off'); } catch (e) {} },
  unlock() {
    if (!this.on()) return;
    const C = window.AudioContext || window.webkitAudioContext;
    if (!C) return;
    if (!this.ctx) this.ctx = new C();
    if (this.ctx.state === 'suspended') this.ctx.resume();
  },
  tone(freq, dur, type, vol, delay) {
    if (!this.on() || !this.ctx || this.ctx.state !== 'running') return;
    const t = this.ctx.currentTime + (delay || 0), o = this.ctx.createOscillator(), g = this.ctx.createGain();
    o.type = type || 'sine'; o.frequency.value = freq;
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol || 0.08, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(this.ctx.destination); o.start(t); o.stop(t + dur + 0.05);
  },
  tap() { this.tone(520, 0.05, 'square', 0.025); },
  bad() { this.tone(160, 0.25, 'sawtooth', 0.05); this.tone(120, 0.3, 'sawtooth', 0.04, 0.12); },
  good() { [523, 659, 784, 1047].forEach((f, i) => this.tone(f, 0.5, 'triangle', 0.06, i * 0.09)); },
});
function buzz(ms) { try { navigator.vibrate && navigator.vibrate(ms); } catch (e) {} }
function el(tag, cls, text, parent) {
  const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text;
  if (parent) parent.appendChild(e); return e;
}

function header(root, data) {
  const top = el('div', 'top', null, root);
  el('div', 'k', 'Exhibit #' + String(data.evidence_no).padStart(2, '0') + ' · ' + data.exhibit, top);
  const snd = el('button', 'snd', SND.on() ? '🔊' : '🔇', top);
  snd.type = 'button'; snd.setAttribute('aria-label', 'Sound effects'); snd.setAttribute('aria-pressed', SND.on());
  snd.onclick = () => { SND.set(!SND.on()); SND.unlock(); snd.textContent = SND.on() ? '🔊' : '🔇';
    snd.setAttribute('aria-pressed', SND.on()); SND.tap(); };
  el('p', 'story', data.story, root);
}

const BUILD = {
  code(root, data) {
    el('div', 'note', '“' + data.riddle + '”', root);
    const facts = el('div', 'facts', null, root);
    data.facts.forEach(([k, v]) => { const d = el('div', null, k, facts); el('b', null, v, d); });
    const face = el('div', 'lockface', null, root);
    const led = el('div', 'led', null, face); led.innerHTML = 'LOCKED<i></i>';
    const slots = el('div', 'slots', null, face); slots.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < 4; i++) el('span', null, '', slots);
    const pad = el('div', 'pad', null, root);
    const status = el('div', 'status', 'Enter four digits', root); status.setAttribute('aria-live', 'polite');
    let code = '';
    const draw = () => { [...slots.children].forEach((s, i) => { s.textContent = code[i] || ''; s.className = i === code.length ? 'cur' : ''; });
      okb.disabled = code.length !== 4 || root.__busy; };
    const press = (k) => {
      if (root.__busy) return; SND.unlock(); SND.tap(); buzz(8);
      if (k === 'del') code = code.slice(0, -1);
      else if (k === 'ok') { if (code.length === 4) { root.__busy = true; led.className = 'led wait'; led.innerHTML = 'VERIFYING<i></i>';
        status.textContent = 'Checking the code…'; status.className = 'status'; draw(); root.__send('submit', { code }); } return; }
      else if (code.length < 4) code += k;
      draw();
    };
    ['1','2','3','4','5','6','7','8','9','del','0','ok'].forEach(k => {
      const b = el('button', k === 'ok' ? 'ok' : k === 'del' ? 'fn' : '', k === 'del' ? '⌫' : k === 'ok' ? 'OPEN' : k, pad);
      b.type = 'button'; b.setAttribute('aria-label', k === 'del' ? 'Delete digit' : k === 'ok' ? 'Open the lock' : 'Digit ' + k);
      b.onclick = () => press(k);
    });
    const okb = pad.lastChild;
    root.__code = { reset() { code = ''; draw(); }, led, status, face };
    draw();
  },

  scratch(root, data) {
    const paper = el('div', 'paper', null, root);
    const under = el('div', 'under', null, paper); under.setAttribute('aria-hidden', 'true');
    data.lines.forEach(t => el('p', null, t, under));
    const canvas = el('canvas', null, null, paper);
    canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', 'A blank page. Rub it with your finger or the mouse.');
    const meter = el('div', 'meter', null, root); const fill = el('i', null, null, meter);
    const status = el('div', 'status', 'Rub the page · 0 %', root); status.setAttribute('aria-live', 'polite');
    const cols = data.cols, rows = data.rows, total = cols * rows, cells = new Set();
    let done = false, ctx, w = 0, hgt = 0, last = null, brush = 30;
    let started = false;
    function size() {
      const width = Math.round(paper.getBoundingClientRect().width);
      if (width < 50) { requestAnimationFrame(size); return; }      // not laid out yet
      if (width === w && ctx) return;
      const height = Math.round(Math.min(width * 1.25, (window.innerHeight || 700) * 0.55));
      paper.style.height = height + 'px';
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = width * dpr; canvas.height = height * dpr; w = width; hgt = height;
      ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const g = ctx.createLinearGradient(0, 0, width, height); g.addColorStop(0, '#F1E8D4'); g.addColorStop(1, '#E2D6BC');
      ctx.fillStyle = g; ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = 'rgba(80,110,160,.25)'; ctx.lineWidth = 1;
      for (let y = 40; y < height; y += 28) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke(); }
      ctx.strokeStyle = 'rgba(200,60,60,.35)'; ctx.beginPath(); ctx.moveTo(36, 0); ctx.lineTo(36, height); ctx.stroke();
      ctx.fillStyle = 'rgba(60,50,40,.35)'; ctx.font = '600 15px Courier Prime, monospace'; ctx.textAlign = 'center';
      ctx.fillText('RUB THE PAGE', width / 2, height / 2);
      brush = Math.max(26, width / 9);
      cells.clear();
    }
    function mark(x, y) {
      const r = brush / 2;
      for (let cy = Math.floor((y - r) / hgt * rows); cy <= Math.floor((y + r) / hgt * rows); cy++)
        for (let cx = Math.floor((x - r) / w * cols); cx <= Math.floor((x + r) / w * cols); cx++)
          if (cx >= 0 && cy >= 0 && cx < cols && cy < rows) cells.add(cy * cols + cx);
    }
    function rub(x, y) {
      ctx.globalCompositeOperation = 'destination-out'; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.lineWidth = brush;
      ctx.beginPath(); ctx.moveTo(last ? last.x : x, last ? last.y : y); ctx.lineTo(x, y); ctx.stroke();
      if (last) { const steps = Math.ceil(Math.hypot(x - last.x, y - last.y) / (brush / 3));
        for (let i = 1; i <= steps; i++) mark(last.x + (x - last.x) * i / steps, last.y + (y - last.y) * i / steps); }
      else mark(x, y);
      last = { x, y };
      const share = cells.size / total; fill.style.width = Math.min(100, share / data.needed * 100) + '%';
      status.textContent = 'Rub the page · ' + Math.round(share * 100) + ' %';
      if (!done && share >= data.needed) finish();
    }
    function finish() {
      done = true; canvas.classList.add('gone'); status.textContent = 'The writing shows through…'; status.className = 'status good';
      SND.good(); buzz([20, 40, 20]);
      setTimeout(() => root.__send('submit', { cells: [...cells] }), 650);
    }
    // pointer position in canvas units, whatever size the page shows the canvas at
    const pos = (e) => { const r = canvas.getBoundingClientRect();
      return { x: (e.clientX - r.left) * (w / (r.width || w)), y: (e.clientY - r.top) * (hgt / (r.height || hgt)) }; };
    canvas.addEventListener('pointerdown', e => { if (done || !ctx) return; started = true; SND.unlock(); canvas.setPointerCapture(e.pointerId); last = null; const p = pos(e); rub(p.x, p.y); });
    canvas.addEventListener('pointermove', e => { if (done || !(e.buttons || e.pointerType === 'touch')) return; if (!last) return; const p = pos(e); rub(p.x, p.y); });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(t => canvas.addEventListener(t, () => { last = null; }));
    requestAnimationFrame(size);
    // the phone turned or the column changed width: redraw the page, unless rubbing has started
    if (window.ResizeObserver) new ResizeObserver(() => { if (!started) size(); }).observe(paper);
    root.__scratch = { again() { done = false; started = false; w = 0; canvas.classList.remove('gone'); size(); status.className = 'status'; } };
  },

  puzzle(root, data) {
    const n = data.cols * data.rows;
    const grid = el('div', 'grid', null, root);
    grid.style.gridTemplateColumns = 'repeat(' + data.cols + ',1fr)';
    grid.setAttribute('role', 'group'); grid.setAttribute('aria-label', 'Torn camera still, ' + n + ' pieces');
    const count = el('div', 'count', null, root); count.setAttribute('aria-live', 'polite');
    const status = el('div', 'status', 'Tap a piece, then the slot it belongs in', root);
    const src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(data.image)));
    let order = data.start.slice(), swaps = [], sel = null, solved = false;
    (data.state.swaps || []).forEach(([a, b]) => { [order[a], order[b]] = [order[b], order[a]]; swaps.push([a, b]); });
    const tiles = [];
    for (let s = 0; s < n; s++) {
      const t = el('button', 'tile', null, grid); t.type = 'button'; el('span', 'n', String(s + 1), t);
      t.style.backgroundImage = 'url("' + src + '")';
      t.style.backgroundSize = (data.cols * 100) + '% ' + (data.rows * 100) + '%';
      t.onclick = () => tap(s); tiles.push(t);
    }
    function paint() {
      let inplace = 0;
      tiles.forEach((t, s) => {
        const p = order[s], c = p % data.cols, r = Math.floor(p / data.cols);
        t.style.backgroundPosition = (data.cols > 1 ? c / (data.cols - 1) * 100 : 0) + '% ' + (data.rows > 1 ? r / (data.rows - 1) * 100 : 0) + '%';
        const ok = p === s; if (ok) inplace++;
        t.classList.toggle('in', ok); t.classList.toggle('sel', sel === s);
        t.setAttribute('aria-pressed', sel === s);
        t.setAttribute('aria-label', 'Slot ' + (s + 1) + (ok ? ', piece in place' : ', piece out of place') + (sel === s ? ', selected' : ''));
      });
      count.textContent = inplace + ' of ' + n + ' pieces in place';
      return inplace;
    }
    function tap(s) {
      if (solved || root.__busy) return; SND.unlock(); SND.tap(); buzz(6);
      if (sel === null) { sel = s; paint(); status.textContent = 'Now tap the slot to swap with'; return; }
      if (sel === s) { sel = null; paint(); status.textContent = 'Tap a piece, then the slot it belongs in'; return; }
      const a = sel; [order[a], order[s]] = [order[s], order[a]]; swaps.push([a, s]); sel = null;
      tiles[a].classList.add('pop'); tiles[s].classList.add('pop'); setTimeout(() => { tiles[a].classList.remove('pop'); tiles[s].classList.remove('pop'); }, 260);
      status.textContent = 'Tap a piece, then the slot it belongs in';
      if (paint() === n) { solved = true; grid.classList.add('done'); status.textContent = 'The picture is whole again…'; status.className = 'status good';
        SND.good(); buzz([20, 40, 20]); setTimeout(() => root.__send('submit', { swaps }), 700); }
      else root.__send('progress', swaps.slice());
    }
    paint();
  },

  cipher(root, data) {
    el('div', 'lbl', 'The note', root);
    const ct = el('div', 'ct', data.cipher, root);
    el('div', 'lbl', 'Read through the wheel', root);
    const pt = el('div', 'pt', null, root); pt.setAttribute('aria-live', 'polite');
    const row = el('div', 'wheelrow', null, root);
    const left = el('button', 'turn', '◀', row); left.type = 'button'; left.setAttribute('aria-label', 'Turn the wheel back');
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', '-110 -110 220 220'); svg.setAttribute('class', 'wheel');
    svg.setAttribute('role', 'slider'); svg.setAttribute('tabindex', '0'); svg.setAttribute('aria-label', 'Cipher wheel setting');
    svg.setAttribute('aria-valuemin', '0'); svg.setAttribute('aria-valuemax', '25');
    row.appendChild(svg);
    const right = el('button', 'turn', '▶', row); right.type = 'button'; right.setAttribute('aria-label', 'Turn the wheel forward');
    const ring = (r, fill, stroke) => { const c = document.createElementNS(NS, 'circle'); c.setAttribute('r', r); c.setAttribute('fill', fill); c.setAttribute('stroke', stroke); svg.appendChild(c); };
    ring(106, '#0F1724', '#33415a'); ring(80, '#1a1216', '#5a3340'); ring(54, '#0B111B', '#2a3446');
    const outer = document.createElementNS(NS, 'g'); outer.setAttribute('class', 'outer'); svg.appendChild(outer);
    const inner = document.createElementNS(NS, 'g'); inner.setAttribute('class', 'inner'); svg.appendChild(inner);
    const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', step = 360 / 26;
    for (let i = 0; i < 26; i++) {
      const a = (i * step - 90) * Math.PI / 180;
      const t1 = document.createElementNS(NS, 'text'); t1.setAttribute('x', Math.cos(a) * 93); t1.setAttribute('y', Math.sin(a) * 93); t1.textContent = A[i]; outer.appendChild(t1);
      const t2 = document.createElementNS(NS, 'text'); t2.setAttribute('x', Math.cos(a) * 67); t2.setAttribute('y', Math.sin(a) * 67); t2.textContent = A[i]; inner.appendChild(t2);
    }
    const mid = document.createElementNS(NS, 'text'); mid.setAttribute('y', 0); mid.setAttribute('style', 'font-size:28px;fill:#F5F1E8'); svg.appendChild(mid);
    const setting = el('div', 'setting', null, root);
    const go = el('button', 'go', 'Lock in this setting', root); go.type = 'button';
    const status = el('div', 'status', 'Turn the wheel until the note makes sense', root); status.setAttribute('aria-live', 'polite');
    let shift = 0;
    const decode = (s) => data.cipher.replace(/[A-Z]/g, ch => A[(A.indexOf(ch) - s + 26) % 26]);
    function draw() {
      inner.style.transform = 'rotate(' + (-shift * step) + 'deg)';
      mid.textContent = shift; svg.setAttribute('aria-valuenow', shift);
      setting.innerHTML = 'Setting <b></b>'; setting.querySelector('b').textContent = shift;
      pt.textContent = decode(shift); go.disabled = !!root.__busy;
    }
    const turn = (d) => { if (root.__busy) return; SND.unlock(); SND.tap(); buzz(5); shift = (shift + d + 26) % 26; draw(); };
    left.onclick = () => turn(-1); right.onclick = () => turn(1);
    svg.addEventListener('keydown', e => { if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { turn(1); e.preventDefault(); }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { turn(-1); e.preventDefault(); } });
    let drag = null;
    const angle = (e) => { const r = svg.getBoundingClientRect(); return Math.atan2(e.clientY - (r.top + r.height / 2), e.clientX - (r.left + r.width / 2)) * 180 / Math.PI; };
    svg.addEventListener('pointerdown', e => { SND.unlock(); svg.setPointerCapture(e.pointerId); drag = angle(e); });
    svg.addEventListener('pointermove', e => { if (drag === null) return; let d = angle(e) - drag; if (d > 180) d -= 360; if (d < -180) d += 360;
      if (Math.abs(d) >= step) { const k = Math.trunc(d / step); turn(-k); drag += k * step; } });
    ['pointerup', 'pointercancel'].forEach(t => svg.addEventListener(t, () => { drag = null; }));
    go.onclick = () => { if (root.__busy) return; SND.unlock(); SND.tap(); root.__busy = true; draw(); status.textContent = 'Checking…'; status.className = 'status'; root.__send('submit', { shift }); };
    root.__cipher = { draw };
    draw();
  },
};

function update(root, data) {
  const st = data.state || {};
  if (root.__seq === st.seq) return;
  const first = root.__seq === undefined;
  root.__seq = st.seq;
  if (first) return;
  // Python has answered a submission that did not unlock the evidence.
  root.__busy = false;
  const status = root.querySelector('.status');
  if (status && st.note) { status.textContent = st.note; status.className = 'status bad'; }
  const target = root.querySelector('.lockface, .wheel, .grid, .paper') || root;
  target.classList.remove('shake'); void target.offsetWidth; target.classList.add('shake');
  SND.bad(); buzz([60, 40, 60]);
  if (root.__code) { root.__code.led.className = 'led bad'; root.__code.led.innerHTML = 'ACCESS DENIED<i></i>'; root.__code.reset(); }
  if (root.__cipher) root.__cipher.draw();
  if (root.__scratch) root.__scratch.again();
}

export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  if (!data || !data.kind) return;
  let root = parentElement.querySelector('.mg');
  if (!root || root.dataset.id !== data.id) {
    if (root) root.remove();
    root = el('div', 'mg mg-' + data.kind);
    root.dataset.id = data.id;
    parentElement.appendChild(root);
    root.__send = (event, value) => setTriggerValue(event, value);
    header(root, data);
    BUILD[data.kind](root, data);
  }
  root.__send = (event, value) => setTriggerValue(event, value);
  update(root, data);
}
"""

CHIME_JS = r"""
export default function (component) {
  const { data } = component;
  const s = window.__novaSound;
  window.__novaChimed = window.__novaChimed || {};
  if (!data || window.__novaChimed[data.id]) return;
  window.__novaChimed[data.id] = true;
  if (s && s.good) s.good();
}
"""
