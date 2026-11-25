// Live vs frozen, as a toy: a car on a three-lane road. The agent looks, thinks for its median latency
// (scaled 4x faster), then steers. In live mode the road keeps moving while it thinks; in frozen mode it waits.
import { data } from './data';

type Rock = { lane: number; y: number; hit?: number };

export function timeDemo(root: HTMLElement) {
  const cv = document.createElement('canvas');
  const ctl = document.createElement('div');
  const read = document.createElement('p');
  ctl.className = 'time-controls';
  read.className = 'time-read';
  root.append(cv, ctl, read);
  const W = 900, H = 600, LANES = 3, LW = 150, X0 = (W - LANES * LW) / 2, SPEED = 260, CAR_Y = H - 110, SCALE = 0.25;
  const ctx = cv.getContext('2d')!;
  const fit = () => { const r = devicePixelRatio || 1; cv.width = W * r; cv.height = H * r; ctx.setTransform(r, 0, 0, r, 0, 0); };
  fit();

  const agents = Object.entries(data.latency).sort((a, b) => a[1] - b[1]);
  let live = true, agent = agents.find(a => a[0] === 'GPT-6-Astra') ?? agents[0];
  let rocks: Rock[] = [], lane = 1, carX = 1, gameT = 0, wallT = 0, crashes = 0, spawn = 0, scroll = 0;
  let phase: 'think' | 'act' = 'think', left = 0, seen: Rock[] = [], target = 1;
  const reset = () => { rocks = []; lane = target = 1; carX = 1; gameT = wallT = crashes = spawn = 0; phase = 'think'; left = agent[1] * SCALE; seen = []; };

  const btn = (text: string, on: () => boolean, go: () => void) => {
    const b = document.createElement('button');
    b.textContent = text;
    b.addEventListener('click', () => { go(); reset(); sync(); });
    ctl.appendChild(b);
    return () => b.classList.toggle('on', on());
  };
  const syncs = [btn('Live', () => live, () => (live = true)), btn('Frozen', () => !live, () => (live = false)),
    ...agents.map(a => btn(`${a[0]} ${a[1]} s`, () => agent === a, () => (agent = a)))];
  const sync = () => syncs.forEach(s => s());
  sync();
  reset();

  // Choose the lane whose nearest rock ahead, in the remembered picture, is farthest away.
  const decide = (view: Rock[]) => {
    let bestLane = lane, bestD = -1;
    for (let l = 0; l < LANES; l++) {
      if (Math.abs(l - lane) > 1) continue;
      const ahead = view.filter(r => r.lane === l && r.y < CAR_Y + 30).map(r => CAR_Y - r.y);
      const d = ahead.length ? Math.min(...ahead.filter(x => x > -30), 9999) : 9999;
      if (d > bestD + (l === lane ? -1 : 40)) { bestD = d; bestLane = l; }
    }
    return bestLane;
  };

  const step = (dt: number) => {
    wallT += dt;
    const worldRuns = live || phase === 'act';
    if (phase === 'think') {
      left -= dt;
      if (left <= 0) { target = decide(seen); phase = 'act'; left = 0.35; }
    } else {
      left -= dt;
      if (left <= 0) { lane = target; phase = 'think'; left = agent[1] * SCALE; seen = rocks.map(r => ({ ...r })); }
    }
    if (!worldRuns) return;
    gameT += dt;
    scroll = (scroll + SPEED * dt) % 80;
    carX += (target - carX) * Math.min(1, dt * 9);
    spawn -= dt;
    if (spawn <= 0) {
      rocks.push({ lane: Math.floor(Math.random() * LANES), y: -60 });
      if (Math.random() < 0.35) rocks.push({ lane: Math.floor(Math.random() * LANES), y: -260 });
      spawn = 0.9 + Math.random() * 0.5;
    }
    for (const r of rocks) {
      r.y += SPEED * dt;
      if (!r.hit && Math.abs(r.y - CAR_Y) < 46 && Math.abs(r.lane - carX) < 0.45) { r.hit = 1; crashes++; }
    }
    rocks = rocks.filter(r => r.y < H + 80);
  };

  const rock = (r: Rock, ghost = false) => {
    const x = X0 + r.lane * LW + LW / 2;
    ctx.beginPath();
    ctx.ellipse(x, r.y, 44, 30, 0, 0, Math.PI * 2);
    if (ghost) { ctx.setLineDash([8, 7]); ctx.strokeStyle = '#d9714f'; ctx.lineWidth = 3; ctx.stroke(); ctx.setLineDash([]); }
    else { ctx.fillStyle = r.hit ? '#c8372d' : '#f2ede0'; ctx.fill(); }
  };

  const draw = () => {
    ctx.fillStyle = '#1d2e27';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#2b4038';
    ctx.fillRect(X0 - 14, 0, 14, H);
    ctx.fillRect(X0 + LANES * LW, 0, 14, H);
    ctx.fillStyle = '#d9a63a';
    for (let l = 1; l < LANES; l++)
      for (let y = -80 + scroll; y < H; y += 80) ctx.fillRect(X0 + l * LW - 3, y, 6, 40);
    rocks.forEach(r => rock(r));
    if (phase === 'think' && live) seen.forEach(r => rock(r, true));
    const cx = X0 + carX * LW + LW / 2;
    ctx.fillStyle = '#d9714f';
    ctx.beginPath();
    ctx.roundRect(cx - 30, CAR_Y - 46, 60, 92, 14);
    ctx.fill();
    ctx.fillStyle = '#1d2e27';
    ctx.fillRect(cx - 20, CAR_Y - 28, 40, 22);
    if (phase === 'think' && !live) {
      ctx.fillStyle = 'rgba(242,237,224,0.18)';
      ctx.fillRect(0, 0, W, H);
    }
    ctx.fillStyle = '#f2ede0';
    ctx.font = '700 30px "Bricolage Grotesque Variable", sans-serif';
    ctx.fillText(phase === 'think' ? (live ? 'thinking, road still moving' : 'thinking, game paused') : 'steering', 28, 52);
    read.textContent = `${agent[0]} in ${live ? 'live' : 'frozen'} execution: ${crashes} ${crashes === 1 ? 'crash' : 'crashes'}, ` +
      `${gameT.toFixed(1)} s of game time in ${wallT.toFixed(1)} s on the wall clock.`;
  };

  let last = 0, visible = false;
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(cv);
  const loop = (t: number) => {
    requestAnimationFrame(loop);
    const dt = Math.min(0.05, (t - last) / 1000);
    last = t;
    if (!visible) return;
    step(dt);
    draw();
  };
  requestAnimationFrame(loop);
}
