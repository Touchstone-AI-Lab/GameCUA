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
const realtime = (g: Game) => g.timing === 'real-time';

/* Game sheet */
const sheet = $('#sheet');
function openSheet(slug: string) {
  const g = bySlug[slug], b = best(slug);
  const shots = Array.from({ length: g.shots }, (_, i) => `<img loading="lazy" src="${img(`shot/${slug}/${String(i).padStart(2, '0')}.webp`)}" alt="">`).join('');
  sheet.innerHTML = `
    <button class="sheet-close">Close</button>
    <div class="sheet-hero" style="background-image:url(${img(`hero/${slug}.webp`)})">
      ${g.logo ? `<img class="glogo" src="${img(`logo/${slug}.webp`)}" alt="${g.name}">` : `<h3>${g.name}</h3>`}
    </div>
    <div class="sheet-body">
      <div>
        <p class="lead">A ${g.timing} ${g.genre} game with ${g.milestones} milestones. The furthest any agent got is
          <b>${b.score.toFixed(1)}</b>, by ${b.model} in ${b.mode} execution.</p>
        <h4>What happened in that run</h4><p>${g.case}</p>
      </div>
      <div>
        <h4>The game</h4><p>${g.intro}</p>
        <h4>What the agent may press</h4><p>${g.controls}</p>
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
const frame = $('#screen-frame'), voice = $('#voice'), dots = $('#step-dots'), title = $('#watch-title');
const watchSec = $('#watch');
let cur = bySlug['peak'], step = -1;
const dot = h('i', 'cursor-dot');
function loadGame(g: Game) {
  cur = g; step = -1;
  frame.innerHTML = '';
  g.replay.forEach((_, i) => frame.appendChild(Object.assign(new Image(), { src: img(`replay/${g.slug}/${String(i).padStart(2, '0')}.webp`), alt: '' })));
  frame.appendChild(dot);
  dots.innerHTML = g.replay.map(() => '<i></i>').join('');
  title.innerHTML = `${g.best.agent} plays <em>${g.name}</em>`;
  document.querySelectorAll('#watch-picker button').forEach(b => b.classList.toggle('on', (b as HTMLElement).dataset.slug === g.slug));
  onScroll();
}
function show(i: number) {
  if (i === step) return;
  step = i;
  const s = cur.replay[i];
  frame.querySelectorAll('img').forEach((im, j) => im.classList.toggle('on', j === i));
  dots.querySelectorAll('i').forEach((d, j) => d.classList.toggle('on', j <= i));
  const a = s.action;
  if (a.x != null && a.y != null) Object.assign(dot.style, { left: `${a.x * 100}%`, top: `${a.y * 100}%`, opacity: '1' });
  else dot.style.opacity = '0';
  voice.innerHTML = `<p class="who">decision ${i + 1} of the 8 shown, ${cur.best.mode} execution</p>
    <p class="see">${s.observation}</p><p class="think">${s.hypothesis}</p><p class="do">${say(a)}</p>`;
}
function onScroll() {
  const r = watchSec.getBoundingClientRect();
  const t = Math.min(0.999, Math.max(0, -r.top / (r.height - innerHeight)));
  show(Math.floor(t * cur.replay.length));
}
addEventListener('scroll', onScroll, { passive: true });
const picker = $('#watch-picker');
for (const g of data.games) {
  const b = h('button', g.logo ? '' : 'txt', g.logo ? `<img src="${img(`logo/${g.slug}.webp`)}" alt="${g.name}">` : g.name);
  b.dataset.slug = g.slug;
  b.addEventListener('click', () => loadGame(g));
  picker.appendChild(b);
}
loadGame(cur);

/* Game index with a poster that follows the cursor */
const index = $('#game-index'), cp = $('#cursor-poster'), cpImg = cp.querySelector('img')!;
for (const g of data.games) {
  const b = best(g.slug);
  const li = h('li', realtime(g) ? '' : 'turn', `<span class="gname">${g.name}</span><span class="gfact">${g.genre}, best ${b.score.toFixed(1)}</span>`);
  li.addEventListener('mouseenter', () => { cpImg.src = img(`poster/${g.slug}.webp`); cp.classList.add('on'); });
  li.addEventListener('mouseleave', () => cp.classList.remove('on'));
  li.addEventListener('click', () => openSheet(g.slug));
  index.appendChild(li);
}
index.insertAdjacentElement('afterend', h('p', 'games-key', 'Solid names run in real time. <span>Outlined</span> names wait for a move, so they are played only live. Click any game to see its runs.'));
let px = 0, py = 0, tx = 0, ty = 0;
addEventListener('pointermove', e => { tx = e.clientX; ty = e.clientY; });
(function follow() {
  px += (tx - px) * 0.18; py += (ty - py) * 0.18;
  cp.style.left = `${px}px`; cp.style.top = `${py}px`;
  requestAnimationFrame(follow);
})();

/* Scores */
const setBars = bars($('#bars-gl') as HTMLCanvasElement, $('#bar-tip'));
const note = $('#mode-note'), avg = $('#averages');
const notes: Record<Mode, string> = {
  live: 'Live: the game keeps running while the agent thinks. Each bar is the percentage of a game’s milestones reached in the best of that agent’s trials.',
  frozen: 'Frozen: the game is paused during inference, so only the eleven real-time games have a second run. Turn-based games stay flat.',
};
function renderAvg(mode: Mode) {
  const col = (key: string, label: string) => {
    const rows = data.models.map((m, i) => ({ m, i, v: data.scores[m][mode][key] })).sort((a, b) => (b.v ?? -1) - (a.v ?? -1));
    return `<div class="avg-col"><h3>${label}</h3>${rows.map(r => `<div class="avg-row"><span>${r.m}</span>
      <span class="track"><span class="fill" style="width:${(r.v ?? 0) / 60 * 100}%;background:${MODEL_COLORS[r.i]}"></span></span>
      <span class="num">${r.v == null ? '–' : r.v.toFixed(1)}</span></div>`).join('')}</div>`;
  };
  avg.innerHTML = col('avg-rt', 'Average over the 11 real-time games') + (mode === 'live' ? col('avg-tb', 'Average over the 4 turn-based games') : '');
}
function setMode(mode: Mode) {
  document.querySelectorAll('#mode-switch button').forEach(b => b.classList.toggle('on', (b as HTMLElement).dataset.mode === mode));
  note.textContent = notes[mode];
  $('#best-rt').textContent = Math.max(...data.models.map(m => data.scores[m][mode]['avg-rt'] ?? 0)).toFixed(1);
  setBars(mode);
  renderAvg(mode);
}
document.querySelectorAll('#mode-switch button').forEach(b => b.addEventListener('click', () => setMode((b as HTMLElement).dataset.mode as Mode)));
setMode('live');

timeDemo($('#time-demo'));

/* Failures */
const FAIL = [
  { k: 'plan', n: 29, label: 'Planning', color: '#80a99c', head: 'Abandoning the right idea',
    text: 'Opus 5.5 in Baba Is You proposes WALL IS YOU at decision 375, then returns to the rock-sealed rule text for the last 70 minutes of its budget.' },
  { k: 'vis', n: 18, label: 'Visual perception', color: '#829fb3', head: 'A door read as stairs',
    text: 'Grok 4.7 in The Binding of Isaac calls the treasure-room door “glowing stairs” and the chest a metal gate.' },
  { k: 'know', n: 15, label: 'Game knowledge', color: '#be9e78', head: 'Climbing the lobby',
    text: 'DeepSeek-Flash in PEAK climbs a parapet inside the airport terminal and turns away from the boarding gate that starts the expedition.' },
  { k: 'act', n: 13, label: 'Action execution', color: '#aaa762', head: 'Building in mid-air',
    text: 'Opus 5.5 in Oxygen Not Included clicks above the walkable floor, so the generator blueprints are queued in mid-air or rejected.' },
  { k: 'rt', n: 13, label: 'Real-time latency', color: '#bd8d7a', head: 'The bend arrives first',
    text: 'Opus 5.5 in art of rally sees the car before a left bend. Its input lands 8.6 seconds of game time later, with the car already off the road.' },
];
const band = $('#fail-band'), fig = $('#fail-figure');
function pick(i: number) {
  const f = FAIL[i];
  band.querySelectorAll('.fail-seg').forEach((s, j) => s.classList.toggle('on', j === i));
  fig.querySelector('img')!.src = img(`err/${f.k}.webp`);
  fig.querySelector('figcaption')!.innerHTML = `<b>${f.head}</b>${f.text}`;
}
FAIL.forEach((f, i) => {
  const s = h('div', 'fail-seg', `<span class="pct">${Math.round(f.n / 88 * 100)}%</span><span class="lab">${f.label}<br>${f.n} of 88</span>`);
  s.style.flexGrow = String(f.n);
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
$('#authors').innerHTML = data.authors.map(a => `<span title="${a.inst}">${a.name}${a.equal ? '<sup>*</sup>' : ''}${a.corr ? '<sup>†</sup>' : ''}</span>`).join('<i>/</i>')
  + '<p class="authors-note"><sup>*</sup> equal contribution &nbsp; <sup>†</sup> corresponding author. Hover a name for the affiliation.</p>';
