// Page wiring: hero ring, scroll-driven replay, game index and sheet, score field, time demo, failures, paper.
import '@fontsource-variable/bricolage-grotesque/wdth.css';
import '@fontsource-variable/fraunces/wght-italic.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/600.css';
import './style.css';
import { data, img, best, say, type Game, type Mode } from './data';
import { hero } from './hero';
import { bars, MODEL_COLORS } from './bars';
import { timeDemo } from './time';

const $ = <T extends HTMLElement = HTMLElement>(s: string) => document.querySelector(s) as T;
const h = (tag: string, cls = '', html = '') => Object.assign(document.createElement(tag), { className: cls, innerHTML: html });
const bySlug = Object.fromEntries(data.games.map(g => [g.slug, g])) as Record<string, Game>;
const pad = (i: number) => String(i).padStart(2, '0');

/* Navigation hides while scrolling down and returns on the way up. */
const nav = $('.nav');
let lastY = 0;
addEventListener('scroll', () => {
  nav.classList.toggle('away', scrollY > lastY && scrollY > 200);
  lastY = scrollY;
}, { passive: true });

/* Game sheet */
const sheet = $('#sheet');
function openSheet(slug: string) {
  const g = bySlug[slug], b = best(slug);
  const shots = Array.from({ length: g.shots - 2 }, (_, i) => `<img loading="lazy" src="${img(`shot/${slug}/${pad(i + 2)}.webp`)}" alt="">`).join('');
  sheet.innerHTML = `
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
    <div class="sheet-strip">${shots}</div>`;
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
addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });

hero($('#hero-gl') as HTMLCanvasElement, openSheet);

/* Watch: the scroll position inside the tall section picks one of eight recorded decisions. */
const frame = $('#screen-frame'), voice = $('#voice'), line = $('#timeline'), title = $('#watch-title');
const watchSec = $('#watch');
let cur = bySlug['peak'], step = -1;
const dot = h('i', 'cursor-dot');
function loadGame(g: Game) {
  cur = g; step = -1;
  frame.innerHTML = '';
  g.replay.forEach((_, i) => frame.appendChild(Object.assign(new Image(), { src: img(`replay/${g.slug}/${pad(i)}.webp`), alt: '' })));
  frame.appendChild(dot);
  const d = g.replay.map(s => s.decision), lo = d[0], span = Math.max(1, d[d.length - 1] - lo);
  line.innerHTML = d.map(n => `<span style="left:${((n - lo) / span) * 100}%">${n}</span>`).join('');
  title.innerHTML = `<b>${g.best.agent}</b> playing ${g.name}, ${g.best.mode} execution`;
  document.querySelectorAll('#watch-picker button').forEach(b => b.classList.toggle('on', (b as HTMLElement).dataset.slug === g.slug));
  onScroll();
}
function show(i: number) {
  if (i === step) return;
  step = i;
  const s = cur.replay[i], a = s.action;
  frame.querySelectorAll('img').forEach((im, j) => im.classList.toggle('on', j === i));
  line.querySelectorAll('span').forEach((d, j) => d.classList.toggle('on', j === i));
  if (a.x != null && a.y != null) Object.assign(dot.style, { left: `${a.x * 100}%`, top: `${a.y * 100}%`, opacity: '1' });
  else dot.style.opacity = '0';
  voice.innerHTML = `<p class="do">${say(a)}</p><p class="see">${s.observation}</p><p class="think">${s.hypothesis}</p>`;
}
function onScroll() {
  const r = watchSec.getBoundingClientRect();
  const t = Math.min(0.999, Math.max(0, -r.top / (r.height - innerHeight)));
  show(Math.floor(t * cur.replay.length));
}
addEventListener('scroll', onScroll, { passive: true });
const picker = $('#watch-picker');
for (const g of data.games) {
  const b = h('button', '', g.name);
  b.dataset.slug = g.slug;
  b.addEventListener('click', () => loadGame(g));
  picker.appendChild(b);
}
loadGame(cur);

/* Game index with a poster that follows the cursor */
const index = $('#game-index'), cp = $('#cursor-poster'), cpImg = cp.querySelector('img')!;
for (const g of data.games) {
  const li = h('li', g.timing === 'real-time' ? '' : 'turn',
    `<span class="gname">${g.name}</span><span class="ggenre">${g.genre}</span><span class="gscore">${best(g.slug).score.toFixed(1)}</span>`);
  li.addEventListener('mouseenter', () => { cpImg.src = img(`poster/${g.slug}.webp`); cp.classList.add('on'); });
  li.addEventListener('mouseleave', () => cp.classList.remove('on'));
  li.addEventListener('click', () => openSheet(g.slug));
  index.appendChild(li);
}
index.insertAdjacentElement('afterend', h('p', 'games-key',
  'The number is the best score any agent reached, out of 100. Solid names run in real time; <span>outlined</span> names wait for each move. Click a game to open its runs.'));
let px = 0, py = 0, tx = 0, ty = 0;
addEventListener('pointermove', e => { tx = e.clientX; ty = e.clientY; });
(function follow() {
  px += (tx - px) * 0.18; py += (ty - py) * 0.18;
  cp.style.left = `${px}px`; cp.style.top = `${py}px`;
  requestAnimationFrame(follow);
})();

/* Scores: 3D field plus a leaderboard of the three averages. */
const setBars = bars($('#bars-gl') as HTMLCanvasElement);
const note = $('#mode-note'), board = $('#board');
const notes: Record<Mode, string> = {
  live: 'The game keeps running while the agent thinks. Each bar is the share of a game’s milestones reached in that agent’s best trial. Point at a bar to compare a game across agents.',
  frozen: 'The game is paused while the agent thinks. Only the eleven real-time games have a frozen run, so the four turn-based games lie flat.',
};
const COLS: [Mode, string, string][] = [['live', 'avg-rt', 'Real-time, live'], ['frozen', 'avg-rt', 'Real-time, frozen'], ['live', 'avg-tb', 'Turn-based']];
const order = [...data.models].sort((a, b) => (data.scores[b].frozen['avg-rt'] ?? 0) - (data.scores[a].frozen['avg-rt'] ?? 0));
function renderBoard(mode: Mode) {
  const top = COLS.map(([m, k]) => Math.max(...data.models.map(x => data.scores[x][m][k] ?? 0)));
  board.innerHTML = `<span></span>${COLS.map(([m, k, l]) => `<span class="hd ${m === mode || k === 'avg-tb' && mode === 'live' ? 'on' : ''}">${l}</span>`).join('')}` +
    order.map(x => `<span class="who"><i style="background:${MODEL_COLORS[data.models.indexOf(x)]}"></i>${x}</span>` +
      COLS.map(([m, k], c) => {
        const v = data.scores[x][m][k] ?? 0;
        const on = m === mode || (k === 'avg-tb' && mode === 'live');
        return `<span class="v ${on ? (v === top[c] ? 'top' : 'on') : ''}">${v.toFixed(1)}</span>`;
      }).join('')).join('');
}
function setMode(mode: Mode) {
  document.querySelectorAll('#mode-switch button').forEach(b => b.classList.toggle('on', (b as HTMLElement).dataset.mode === mode));
  note.textContent = notes[mode];
  $('#best-rt').textContent = Math.max(...data.models.map(m => data.scores[m][mode]['avg-rt'] ?? 0)).toFixed(1);
  setBars(mode);
  renderBoard(mode);
}
document.querySelectorAll('#mode-switch button').forEach(b => b.addEventListener('click', () => setMode((b as HTMLElement).dataset.mode as Mode)));
setMode('live');

timeDemo($('#time-demo'));

/* Failures: band widths follow the event counts. */
const FAIL = [
  { k: 'plan', n: 29, label: 'Planning', color: '#d9714f', head: 'Abandoning the right idea',
    text: 'Opus 5.5 in Baba Is You proposes WALL IS YOU at decision 375, then keeps returning to the rock-sealed rule text for the last 70 minutes of its budget.' },
  { k: 'vis', n: 18, label: 'Visual perception', color: '#188e86', head: 'A door read as stairs',
    text: 'Grok 4.7 in The Binding of Isaac calls the treasure-room door “glowing stairs” and the chest a metal gate.' },
  { k: 'know', n: 15, label: 'Game knowledge', color: '#b8862a', head: 'Climbing the lobby',
    text: 'DeepSeek-Flash in PEAK climbs a parapet inside the airport terminal and turns away from the boarding gate that starts the expedition.' },
  { k: 'act', n: 13, label: 'Action execution', color: '#1d2e27', head: 'Building in mid-air',
    text: 'Opus 5.5 in Oxygen Not Included clicks above the walkable floor, so its generator blueprints are queued in mid-air or rejected.' },
  { k: 'rt', n: 13, label: 'Real-time latency', color: '#c8372d', head: 'The bend arrives first',
    text: 'Opus 5.5 in art of rally sees the car before a left bend. Its input lands 8.6 seconds of game time later, with the car already off the road.' },
];
const band = $('#fail-band'), fig = $('#fail-figure');
function pick(i: number) {
  const f = FAIL[i];
  band.querySelectorAll('.fail-seg').forEach((s, j) => s.classList.toggle('on', j === i));
  fig.querySelector('img')!.src = img(`err/${f.k}.webp`);
  fig.querySelector('figcaption')!.innerHTML = `<b>${f.head}</b><span>${f.text}</span>`;
}
FAIL.forEach((f, i) => {
  const s = h('div', 'fail-seg', `<span class="pct">${Math.round(f.n / 88 * 100)}%</span><span class="lab">${f.label}<small>${f.n} of 88 failures</small></span>`);
  s.style.flex = `${f.n} 1 0`;
  s.style.background = f.color;
  s.addEventListener('click', () => pick(i));
  band.appendChild(s);
});
pick(0);

/* Paper */
$('#abstract').textContent = data.abstract;
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
  setTimeout(() => ((e.target as HTMLElement).textContent = 'Copy BibTeX'), 1600);
});
const person = (a: (typeof data.authors)[number]) =>
  `<div class="au"><b>${a.name}${a.corr ? '<sup>†</sup>' : ''}</b><span>${a.inst}</span></div>`;
$('#authors').innerHTML =
  `<p class="au-label">Equal contribution</p><div class="au-lead">${data.authors.filter(a => a.equal).map(person).join('')}</div>` +
  `<div class="au-rest">${data.authors.filter(a => !a.equal).map(person).join('')}</div>` +
  '<p class="authors-note"><sup>†</sup> Corresponding author</p>';
