// Page wiring: starfield, disc loader, playground monitor, game cards and sheet, leaderboard and score field,
// time demo, failures, paper.
import '@fontsource-variable/inter';
import '@fontsource/jetbrains-mono/400.css';
import './style.css';
import { data, img, best, say, type Game, type Mode } from './data';
import { stars } from './stars';
import { discs } from './disc';
import { timeDemo } from './time';
import unis from './unis.json';

const $ = <T extends HTMLElement = HTMLElement>(s: string) => document.querySelector(s) as T;
const h = (tag: string, cls = '', html = '') => Object.assign(document.createElement(tag), { className: cls, innerHTML: html });
const bySlug = Object.fromEntries(data.games.map(g => [g.slug, g])) as Record<string, Game>;
const pad = (i: number) => String(i).padStart(2, '0');
const MODEL_COLORS = ['#8cb8ff', '#7ccade', '#e2c377', '#e0736b', '#b9a6f5', '#dfe7f3'];

stars($('#stars') as HTMLCanvasElement);

/* Navigation: the link of the section in view is highlighted. */
const links = [...document.querySelectorAll<HTMLAnchorElement>('#nav-links a')];
const io = new IntersectionObserver(es => es.forEach(e => {
  if (e.isIntersecting) links.forEach(a => a.classList.toggle('on', a.hash === `#${e.target.id}`));
}), { rootMargin: '-45% 0px -50% 0px' });
document.querySelectorAll('main > section').forEach(s => io.observe(s));
const nav = $('.nav');
$('#menu').addEventListener('click', () => nav.classList.toggle('open'));
links.forEach(a => a.addEventListener('click', () => nav.classList.remove('open')));

/* Game sheet */
const sheet = $('#sheet');
function openSheet(slug: string) {
  const g = bySlug[slug], b = best(slug);
  const shots = Array.from({ length: g.shots - 2 }, (_, i) => `<img loading="lazy" src="${img(`shot/${slug}/${pad(i + 2)}.webp`)}" alt="">`).join('');
  sheet.innerHTML = `<div class="sheet-in">
    <button class="sheet-close" aria-label="Close">×</button>
    <div class="sheet-hero" style="background-image:url(${img(`hero/${slug}.webp`)})">
      ${g.logo ? `<img class="glogo" src="${img(`logo/${slug}.webp`)}" alt="${g.name}">` : `<h3>${g.name}</h3>`}
    </div>
    <div class="sheet-body">
      <div>
        <p class="lead">${b.model} got furthest: <b>${b.score.toFixed(1)}</b> of 100 points in ${b.mode} execution.</p>
        <h4>The run</h4><p>${g.case}</p>
      </div>
      <div>
        <h4>The game</h4><p>${g.intro} It is scored on ${g.milestones} milestones, played ${g.timing === 'real-time' ? 'in real time' : 'turn by turn'}.</p>
        <h4>What the agent may press</h4><p class="controls">${g.controls}</p>
      </div>
    </div>
    <div class="sheet-strip">${shots}</div></div>`;
  sheet.scrollTop = 0;
  sheet.classList.add('open');
  sheet.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  sheet.querySelector('.sheet-close')!.addEventListener('click', closeSheet);
}
function closeSheet() {
  sheet.classList.remove('open');
  sheet.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}
sheet.addEventListener('click', e => { if (e.target === sheet) closeSheet(); });
addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });

/* Playground: the monitor scrolls through the eight recorded decisions of a game's best run. */
const strip = $('#mon-strip'), dot = $('#cursor-dot'), steps = $('#pg-steps'), log = $('#pg-log'), playBtn = $('#pg-play');
let cur = bySlug['peak'], step = 0, playing = true, timer = 0, pgVisible = false;
function loadGame(g: Game) {
  cur = g;
  strip.innerHTML = g.replay.map((_, i) => `<img src="${img(`replay/${g.slug}/${pad(i)}.webp`)}" alt="">`).join('');
  steps.innerHTML = g.replay.map(s => `<button>#${s.decision}</button>`).join('');
  steps.querySelectorAll('button').forEach((b, i) => b.addEventListener('click', () => { setPlaying(false); show(i); }));
  $('#mon-title').textContent = `${g.name} — ${g.best.agent}, ${g.best.mode}`;
  document.querySelectorAll<HTMLElement>('#pg-grid .tile').forEach(t => t.classList.toggle('on', t.dataset.slug === g.slug));
  strip.style.transition = 'none';
  show(0);
  void strip.offsetHeight;
  strip.style.transition = '';
}
function show(i: number) {
  step = i;
  const s = cur.replay[i], a = s.action;
  strip.style.transform = `translateY(${-i * 100}%)`;
  steps.querySelectorAll('button').forEach((b, j) => { b.classList.toggle('on', j === i); b.classList.toggle('done', j < i); });
  $('#mon-step').textContent = `decision ${s.decision} · ${i + 1}/${cur.replay.length}`;
  dot.style.opacity = '0';
  if (a.x != null && a.y != null) setTimeout(() => { if (step === i) Object.assign(dot.style, { left: `${a.x! * 100}%`, top: `${a.y! * 100}%`, opacity: '1' }); }, 900);
  log.innerHTML = `<div><h4>Action</h4><p class="do">${say(a)}</p></div><div><h4>Sees</h4><p>${s.observation}</p></div><div><h4>Thinks</h4><p>${s.hypothesis}</p></div>`;
}
function setPlaying(p: boolean) {
  playing = p;
  playBtn.classList.toggle('paused', !p);
  playBtn.setAttribute('aria-label', p ? 'Pause' : 'Play');
}
playBtn.addEventListener('click', () => setPlaying(!playing));
setInterval(() => {
  if (!playing || !pgVisible || document.hidden) return;
  if (++timer < 5) return;
  timer = 0;
  show((step + 1) % cur.replay.length);
}, 1000);
new IntersectionObserver(([e]) => { pgVisible = e.isIntersecting; }, { threshold: 0.3 }).observe($('.monitor'));

const grid = $('#pg-grid');
const short = (n: string) => n.replace('The Binding of Isaac: Rebirth', 'Binding of Isaac').replace('Hollow Knight: Silksong', 'Silksong');
for (const g of data.games) {
  const t = h('button', 'tile', `<img src="${img(`poster/${g.slug}.webp`)}" alt="" loading="lazy">${short(g.name)}`);
  t.dataset.slug = g.slug;
  t.dataset.timing = g.timing;
  t.addEventListener('click', () => { loadGame(g); timer = 0; setPlaying(true); loadDisc(g.slug); });
  grid.appendChild(t);
}
document.querySelectorAll<HTMLElement>('#pg-tabs button').forEach(b => b.addEventListener('click', () => {
  const f = b.dataset.f!;
  document.querySelectorAll('#pg-tabs button').forEach(x => x.classList.toggle('on', x === b));
  let n = 0;
  grid.querySelectorAll<HTMLElement>('.tile').forEach(t => { t.hidden = f !== 'all' && t.dataset.timing !== f; n += t.hidden ? 0 : 1; });
  $('#pg-count').textContent = String(n);
}));
loadGame(cur);

/* Hero disc loader; the pill sends the loaded game to the monitor. */
let heroSlug = 'peak';
const loadDisc = discs($('#disc-gl') as HTMLCanvasElement, slug => { heroSlug = slug; $('#disc-name').textContent = bySlug[slug].name; });
$('#disc-play').addEventListener('click', () => {
  loadGame(bySlug[heroSlug]); timer = 0; setPlaying(true);
  $('#playground').scrollIntoView();
});

/* Game cards */
const gameGrid = $('#game-grid');
for (const g of data.games) {
  const c = h('button', 'card gcard', `<img src="${img(`poster/${g.slug}.webp`)}" alt="" loading="lazy"><div><b>${g.name}</b><em>${best(g.slug).score.toFixed(1)}</em><span>${g.genre}</span><small>${g.timing} · ${g.milestones} milestones</small></div>`);
  c.addEventListener('click', () => openSheet(g.slug));
  gameGrid.appendChild(c);
}

/* Results: a sortable leaderboard of the averages, and the 3D field of every game. */
const board = $('#board');
const COLS: { m: Mode; k: string; l: string }[] = [
  { m: 'live', k: 'avg-rt', l: 'Real-time, live' }, { m: 'frozen', k: 'avg-rt', l: 'Real-time, frozen' }, { m: 'live', k: 'avg-tb', l: 'Turn-based' },
];
const val = (x: string, c: number) => (c === 3 ? data.latency[x] : data.scores[x][COLS[c].m][COLS[c].k]) ?? 0;
let sortCol = 0;
function renderBoard() {
  const rows = [...data.models].sort((a, b) => (sortCol === 3 ? val(a, 3) - val(b, 3) : val(b, sortCol) - val(a, sortCol)));
  const top = [0, 1, 2].map(c => Math.max(...data.models.map(x => val(x, c))));
  board.innerHTML = `<thead><tr><th>Rank</th><th>Agent</th>${[...COLS.map(c => c.l), 'Median latency (s)'].map((l, c) => `<th data-c="${c}" class="${c === sortCol ? 'on' : ''}">${l}</th>`).join('')}</tr></thead><tbody>` +
    rows.map((x, r) => `<tr><td class="rank"><i>${r + 1}</i></td><td class="who"><i style="background:${MODEL_COLORS[data.models.indexOf(x)]}"></i>${x}</td>` +
      [0, 1, 2, 3].map(c => `<td class="${c === sortCol ? 'col-on' : ''} ${c < 3 && val(x, c) === top[c] ? 'top' : ''}">${val(x, c).toFixed(1)}</td>`).join('') + '</tr>').join('') + '</tbody>';
  board.querySelectorAll<HTMLElement>('th[data-c]').forEach(th => th.addEventListener('click', () => { sortCol = +th.dataset.c!; renderBoard(); }));
}
renderBoard();
$('#best-rt').textContent = $('#fact-best').textContent = Math.max(...data.models.map(m => data.scores[m].live['avg-rt'] ?? 0)).toFixed(1);

/* Per-game heatmap: one row per agent, one column per game, each cell printing its score. */
const heat = $('#heat');
const SHORT: Record<string, string> = { 'The Binding of Isaac: Rebirth': 'Isaac', 'The Binding of Isaac': 'Isaac', 'art of rally': 'Rally', 'Hollow Knight: Silksong': 'Silksong', 'Oxygen Not Included': 'ONI',
  'Untitled Goose Game': 'Goose', 'Civilization VI': 'Civ VI', 'Left 4 Dead 2': 'L4D2', 'Stardew Valley': 'Stardew', 'Papers, Please': 'Papers', 'Slay the Spire': 'Spire', 'Baba Is You': 'Baba', "Don't Starve": "Don't Starve" };
const mix = (t: number) => { const a = [24, 37, 57], b = [149, 184, 255]; return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t)).join(',')})`; };
const notes: Record<Mode, string> = {
  live: 'Live: the game keeps running while the agent thinks. Each cell is one agent’s best trial on one game; gold columns are the turn-based games.',
  frozen: 'Frozen: the game is paused while the agent thinks. Only the eleven real-time games have a frozen run.',
};
function setMode(mode: Mode) {
  document.querySelectorAll<HTMLElement>('#mode-switch button').forEach(b => b.classList.toggle('on', b.dataset.mode === mode));
  $('#mode-note').textContent = notes[mode];
  heat.innerHTML = `<thead><tr><th></th>${data.games.map(g => `<th class="${g.timing === 'turn-based' ? 'tb' : ''}" title="${g.name}">${SHORT[g.name] ?? g.name}</th>`).join('')}</tr></thead><tbody>` +
    order.map(x => `<tr><th><i style="background:${MODEL_COLORS[data.models.indexOf(x)]}"></i>${x}</th>${data.games.map(g => {
      const v = data.scores[x][mode][g.slug];
      if (v == null) return '<td class="na">–</td>';
      const t = Math.min(1, v / 60);
      return `<td style="background:${mix(t)};color:${t > 0.55 ? '#0b1423' : '#dce7f7'}">${v.toFixed(0)}</td>`;
    }).join('')}</tr>`).join('') + '</tbody>';
}
const order = [...data.models].sort((a, b) => val(b, 0) - val(a, 0));
document.querySelectorAll<HTMLElement>('#mode-switch button').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode as Mode)));
setMode('live');

timeDemo($('#time-demo'));

/* Failures: band widths follow the event counts; each cause opens one traced case, built from the trial's raw
   screenshots and the agent's own words. */
type Case = {
  k: string; n: number; label: string; color: string; head: string; run: string;
  shots: [string, string][]; record: [string, number][]; reason: string; outcome: string;
};
const FAIL: Case[] = [
  { k: 'plan', n: 29, label: 'Planning', color: '#8cb8ff', head: 'Abandoning the right idea', run: 'Baba Is You · Opus 5.5 · live',
    shots: [['plan', 'decision 346 · 1:49:37 · level 06 “Off Limits”']],
    record: [['Pushing the WALL text left along row y~485 into the BABA text position should form WALL IS YOU vertically … walls next to the flag could move onto it to win.', 375],
      ['The rock L-shape creates an impenetrable barrier between Baba and the left text blocks … Fresh approach needed.', 419]],
    reason: 'The agent found the right idea within minutes: form WALL IS YOU, so the walls next to the flag can touch it. It wrote the idea down again at decisions 383 and 425, and each time went back to routing Baba around the rocks toward rule text sealed behind ROCK IS STOP.',
    outcome: 'No new level after 1:50; 20.5 points.' },
  { k: 'vis', n: 18, label: 'Visual perception', color: '#7ccade', head: 'A door read as stairs', run: 'The Binding of Isaac · Grok 4.7 · frozen',
    shots: [['vis', 'decision 320 · 1:52:16 · Isaac beside the treasure-room door']],
    record: [['Isaac standing directly on glowing stairs at bottom center of Basement I room … metal gate removed.', 14],
      ['Character is already on exit stairs; pressing S again will trigger automatic Basement II floor transition.', 320]],
    reason: 'There are no stairs in this room. The golden object at the bottom wall is the door of a treasure room, and the “metal gate” is a chest ringed by rocks. Believing it already stood on an exit, the agent pressed S in 261 of its 453 actions and tried 73 bomb attacks on the chest.',
    outcome: 'Three hours in the first room; 3.0 points.' },
  { k: 'know', n: 15, label: 'Game knowledge', color: '#e2c377', head: 'Climbing the lobby', run: 'PEAK · DeepSeek-Flash · frozen',
    shots: [['know', 'decision 620 · 1:20:57 · a parapet inside the terminal'], ['know2', 'decision 1109 · 2:35:41 · the boarding gate']],
    record: [['A mantle (W+J+Space) should crest the parapet and put me on the roof ledge above the plane — the exit from this atrium loop.', 620],
      ['The gate entrance may be blocked by stanchion chains; the yellow dotted path could mark the trail route onward.', 1109]],
    reason: 'In PEAK the airport is a lobby: the expedition starts by boarding the flight at the gate kiosk. The agent treated the terminal as the climbing level, scaled its walls, atrium and parked plane for three hours, and turned away from the gate when it finally reached it.',
    outcome: 'The expedition never started; 0.0 points.' },
  { k: 'act', n: 13, label: 'Action execution', color: '#b9a6f5', head: 'Building in mid-air', run: 'Oxygen Not Included · Opus 5.5 · frozen',
    shots: [['act', 'decision 205 · 1:10:09 · generator blueprints placed in mid-air']],
    record: [['The floor of the cave at approximately y=0.44 should have empty tiles between x=0.35 and x=0.55 where no dupes are standing.', 205],
      ['I mis-read pixel vs normalized coordinates: y≈0.37 is mid-air (266 px), while the actual ledge surface is at y≈0.50.', 286]],
    reason: 'The build plan of power, oxygen and an outhouse was sound, but the agent converted pixel positions into normalized coordinates incorrectly, so its clicks landed above the walkable floor at y ≈ 0.51. It placed floating blueprints for about 250 decisions before it found the offset.',
    outcome: 'Little was built before the first autosave; 8.4 points.' },
  { k: 'rt', n: 13, label: 'Real-time latency', color: '#e0736b', head: 'The bend arrives first', run: 'art of rally · Opus 5.5 · live',
    shots: [['rt', 'decision 641 · what the agent saw · 28:52.956'], ['rt2', 'when its input landed · 29:01.594 · +8.6 s']],
    record: [['The car is centred and the pole sits off the right edge, so straight-line throttle is still safe.', 641],
      ['Same failure as before: plain throttle at 9–12 mph keeps pulling right off the gravel.', 642]],
    reason: 'In live mode the car kept coasting for 7 to 9 seconds while the agent deliberated. It planned a straight throttle pulse for the screenshot it had seen, but by the time the pulse arrived the car had reached the left bend and left the road. The cycle repeated across stage 2.',
    outcome: 'Stage 2 not finished within the budget; 8.5 points.' },
];
const band = $('#fail-band'), fcase = $('#fail-case');
function pick(i: number) {
  const f = FAIL[i];
  band.querySelectorAll('.fail-seg').forEach((s, j) => s.classList.toggle('on', j === i));
  fcase.style.setProperty('--c', f.color);
  fcase.classList.toggle('two', f.shots.length > 1);
  fcase.innerHTML = `<div class="fc-shots ${f.shots.length > 1 ? 'two' : ''}">${f.shots.map(([src, cap]) =>
    `<figure class="fc-screen"><div class="mon-bar"><span class="dots"><i></i><i></i><i></i></span><span>${cap}</span></div><img src="${img(`err/${src}.webp`)}" alt=""></figure>`).join('')}</div>
    <div class="fc-text">
      <p class="eyebrow fc-k"><i></i>${f.label} error</p>
      <h3>${f.head}</h3><p class="fc-run">${f.run}</p>
      <div><h4>The agent's own record</h4>
      ${f.record.map(([q, d]) => `<blockquote>“${q}”<small>decision ${d}</small></blockquote>`).join('')}</div>
      <div><h4>Why it failed</h4><p>${f.reason}</p>
      <p class="fc-out">${f.outcome}</p></div>
    </div>`;
}
FAIL.forEach((f, i) => {
  const s = h('button', 'fail-seg', `<span class="pct">${Math.round(f.n / 88 * 100)}%</span><span class="lab">${f.label}<small>${f.n} of 88</small></span>`);
  s.style.flex = `${f.n} 1 0`;
  s.style.setProperty('--c', f.color);
  s.addEventListener('click', () => pick(i));
  band.appendChild(s);
});
pick(0);

/* Paper */
$('#abstract').innerHTML = data.abstract.split(/(?=We introduce |Evaluations across )/).map(p => `<p>${p}</p>`).join('');
const bib = `@article{gamecua2026,
  title   = {GameCUA: Evaluating Computer-Use Agents in Live Game Runtimes},
  author  = {${data.authors.map(a => a.name).join(' and ')}},
  journal = {arXiv preprint},
  year    = {2026}
}`;
$('#bibtex').textContent = bib;
$('#copy-bib').addEventListener('click', async e => {
  await navigator.clipboard.writeText(bib);
  (e.target as HTMLElement).textContent = 'Copied';
  setTimeout(() => ((e.target as HTMLElement).textContent = 'Copy'), 1600);
});
const person = (a: (typeof data.authors)[number]) =>
  `<div class="au"><b>${a.name}${a.corr ? '<sup>†</sup>' : ''}</b><span>${a.inst}</span></div>`;
$('#authors').innerHTML =
  `<p class="au-label">Equal contribution</p><div class="au-lead">${data.authors.filter(a => a.equal).map(person).join('')}</div>` +
  `<div class="au-rest">${data.authors.filter(a => !a.equal).map(person).join('')}</div>` +
  '<p class="authors-note"><sup>†</sup> Corresponding author</p>';

/* Institution logos: one row, duplicated so the scroll loops seamlessly. */
const row = unis.map(u => `<img src="${img(`uni/${u.k}.webp`)}" alt="${u.name}" title="${u.name}" style="height:${Math.round(u.h * 0.8)}px">`).join('');
$('#unis-track').innerHTML = row + row.replace(/alt="[^"]*"/g, 'alt="" aria-hidden="true"');
