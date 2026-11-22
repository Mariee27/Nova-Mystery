// End-to-end check in a real browser (Chromium via Playwright), run by CI against a running app:
//   node tests/e2e/browser_check.cjs http://localhost:8501
// The pytest suite drives app.py with a stand-in for Streamlit; it cannot see layout or the
// browser. This script plays a demo game on a phone-sized screen and checks what only a real
// browser shows: one paper card per private clue, the stamp on every file, tapping a pin,
// the vote without a preselection, the result, and no error anywhere.
const { chromium } = require('playwright');

(async () => {

const base = process.argv[2] || 'http://localhost:8501';
const failures = [];
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) failures.push(what); };

const browser = await chromium.launch();
const errors = [];
const page = await browser.newPage({ viewport: { width: 390, height: 1400 } });
page.on('pageerror', (e) => errors.push(e.message));
const settle = (ms = 2500) => page.waitForTimeout(ms);
const click = async (name) => { await page.getByRole('button', { name, exact: true }).click(); await settle(); };
const text = () => page.locator('body').innerText();
const goStep = async (params) => {
  const url = new URL(page.url());
  for (const [key, value] of Object.entries(params)) url.searchParams.set(key, value);
  await page.goto(url.toString()); await settle(3500);
};

try {
  await page.goto(`${base}/?demo=1`); await settle(7000);
  check(!(await text()).includes('Which case?') && (await text()).includes('the same culprit every time'),
        'a demo plays the fixed demo case without a choice');
  check(!(await text()).includes('Keep this page open'), 'the host is not told to wait for the host');
  await click('Start game');
  await click('Open your file'); await settle(3000);
  const stamp = await page.locator('.dstamp').innerText();
  check(['MURDERER', 'INNOCENT'].includes(stamp.trim().toUpperCase()), `the opened file is stamped ${stamp.trim()}`);
  const tinted = await page.locator('.unseal.guilty').count() === 1;
  check(tinted === (stamp.trim().toUpperCase() === 'MURDERER'), 'only the murderer\'s own file is tinted red');

  await click('End phase (host)');
  check(await page.locator('.act').count() >= 2, 'the round starts with the action cards');
  await goStep({ step: 'share' });
  check(await page.locator('.paper.clue').count() === 2, 'Share a clue shows exactly two paper cards');
  const cards = await page.locator('.paper.clue').allInnerTexts();
  check(cards.every((c) => /PRIVATE CLUE [12]/i.test(c) && c.split('\n').filter(Boolean).length >= 2),
        'each card holds its heading and its text');

  await goStep({ step: 'search' });
  const pin = page.locator('a.pin2.open').first();
  const place = await pin.locator('.pn').innerText();
  await pin.click(); await settle(4000);
  check((await page.locator('.pin2.sel .pn').allInnerTexts()).includes(place), `tapping ${place} selects it`);
  check(await page.getByRole('button', { name: new RegExp(`^Search ${place}$`, 'i') }).count() === 1,
        `the button to search ${place} appears`);
  await click(`Search ${place}`); await settle(3000);
  const tiles = page.locator('.grid .tile');
  if (await tiles.count() > 0) {          // the jigsaw: its picture loads, and no piece is stretched
    const shape = await tiles.evaluateAll((all) => {
      const grid = all[0].parentElement, cols = getComputedStyle(grid).gridTemplateColumns.split(' ').length;
      const rows = all.length / cols, box = all[0].getBoundingClientRect();
      return { cols, rows, ratio: box.width / box.height, image: getComputedStyle(all[0]).backgroundImage.length };
    });
    check(shape.image > 100, 'the jigsaw shows its picture');
    check(Math.abs(shape.ratio - shape.rows / shape.cols) < 0.05, `the pieces keep the picture's shape (${shape.cols} × ${shape.rows})`);
  } else if (await page.locator('img.motif').count() > 0) {   // rub to reveal: the picture under the cover
    const width = await page.locator('img.motif').evaluate((img) => img.complete ? img.naturalWidth : 0);
    check(width > 0, 'the picture under the cover loads');
  } else if (await page.locator('.olist .ev').count() > 0) {   // order the evening: four entries to tap
    const entries = page.locator('.olist .ev');
    check(await entries.count() === 4, 'the diary shows four entries');
    for (let i = 0; i < 4; i++) { await entries.nth(i).click(); await page.waitForTimeout(150); }
    check(await page.locator('.olist .ev.on').count() === 4 && !(await page.locator('.mg .go').isDisabled()),
          'tapping numbers every entry and the order can be checked');
  }

  for (let i = 0; i < 6 && !(await text()).includes('Who did it?'); i++) await click('End phase (host)');
  check((await text()).includes('Who did it?'), 'the vote opens');
  await click('Vote');
  check((await text()).includes('Choose who did it.'), 'nothing is chosen in advance');
  await page.locator('a.pick').first().click(); await settle(4000);
  await click('Vote');
  check((await text()).includes('Your accusation is filed'), 'a chosen suspect can be voted for');
  await click('End phase (host)'); await settle(4000);
  check(await page.locator('.culprit').count() === 1, 'the result names the culprit');

  const code = new URL(page.url()).searchParams.get('room');
  const board = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  board.on('pageerror', (e) => errors.push(e.message));
  await board.goto(`${base}/?room=${code}&view=board`); await board.waitForTimeout(6000);
  check(await board.locator('.plan2').count() === 1, 'the board shows the campus map');
  const exceptions = await page.locator('[data-testid="stException"]').count()
    + await board.locator('[data-testid="stException"]').count();
  check(exceptions === 0, 'no Streamlit error on any screen');
  check(errors.length === 0, `no browser error${errors.length ? ': ' + errors[0] : ''}`);
} catch (problem) {
  check(false, `the script ran through (${problem.message.split('\n')[0]})`);
} finally {
  await browser.close();
}
if (failures.length) { console.log(`\n${failures.length} check(s) failed`); process.exit(1); }
console.log('\nall browser checks passed');
})();
