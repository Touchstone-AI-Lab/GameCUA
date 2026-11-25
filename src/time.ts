// Live vs frozen, as a toy: the same agent drives two identical three-lane roads at once. It looks, thinks for
// its median latency (scaled 4x faster), then steers. On the live road the world keeps moving while it thinks;
// on the frozen road the world waits. Both roads get the same rocks in game time.
import { data } from './data';

type Rock = { lane: number; y: number; hit?: boolean };
const LANES = 3, LW = 120, RW = LANES * LW, H = 600, TOP = 76, BOT = 84, CAR_Y = H - 110, SPEED = 260, SCALE = 0.25, ACT = 0.35;

/** Seeded generator, so both roads see the same rocks at the same game time. */
function rng(seed: number) {
  return () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}

class Road {
  rocks: Rock[] = []; lane = 1; carX = 1; target = 1; gameT = 0; crashes = 0; spawn = 0.4; scroll = 0;
  phase: 'think' | 'act' = 'think'; left = 0; seen: Rock[] = []; rnd = rng(7);
  constructor(public live: boolean, public latency: number) { this.left = latency * SCALE; }

  // Choose the adjacent lane whose nearest rock ahead, in the remembered picture, is farthest away.
  decide() {
    let best = this.lane, bestD = -1;
    for (let l = Math.max(0, this.lane - 1); l <= Math.min(LANES - 1, this.lane + 1); l++) {
      const ahead = this.seen.filter(r => r.lane === l && r.y < CAR_Y + 40).map(r => CAR_Y - r.y);
      const d = ahead.length ? Math.min(...ahead) : 9999;
      if (d > bestD + (l === this.lane ? -1 : 30)) { bestD = d; best = l; }
    }
    return best;
  }

  step(dt: number) {
    this.left -= dt;
    if (this.left <= 0) {
      if (this.phase === 'think') { this.target = this.decide(); this.phase = 'act'; this.left = ACT; }
      else { this.lane = this.target; this.phase = 'think'; this.left = this.latency * SCALE; this.seen = this.rocks.map(r => ({ ...r })); }
    }
    if (!this.live && this.phase === 'think') return;
    this.gameT += dt;
    this.scroll = (this.scroll + SPEED * dt) % 80;
    this.carX += (this.target - this.carX) * Math.min(1, dt * 9);
    this.spawn -= dt;
    if (this.spawn <= 0) {
      this.rocks.push({ lane: Math.floor(this.rnd() * LANES), y: -50 });
      if (this.rnd() < 0.35) this.rocks.push({ lane: Math.floor(this.rnd() * LANES), y: -230 });
      this.spawn = 0.85 + this.rnd() * 0.5;
    }
    for (const r of this.rocks) {
      r.y += SPEED * dt;
      if (!r.hit && Math.abs(r.y - CAR_Y) < 44 && Math.abs(r.lane - this.carX) < 0.45) { r.hit = true; this.crashes++; }
    }
    this.rocks = this.rocks.filter(r => r.y < H + 80);
  }
}

export function timeDemo(root: HTMLElement) {
  const pickRow = document.createElement('div');
  pickRow.className = 'time-pick';
  const cv = document.createElement('canvas');
  root.append(pickRow, cv);
  const GAP = 40, W = RW * 2 + GAP;
  const ctx = cv.getContext('2d')!;
  const r = Math.min(2, devicePixelRatio || 1);
  cv.width = W * r; cv.height = (H + TOP + BOT) * r;
  ctx.setTransform(r, 0, 0, r, 0, 0);

  const agents = Object.entries(data.latency).sort((a, b) => a[1] - b[1]);
  let agent = agents.find(a => a[0] === 'GPT-6-Astra') ?? agents[0];
  let roads: Road[] = [];
  const reset = () => { roads = [new Road(true, agent[1]), new Road(false, agent[1])]; };
  const buttons = agents.map(a => {
    const b = document.createElement('button');
    b.innerHTML = `${a[0]} <small>${a[1]} s</small>`;
    b.addEventListener('click', () => { agent = a; reset(); buttons.forEach((x, i) => x.classList.toggle('on', agents[i] === agent)); });
    pickRow.appendChild(b);
    return b;
  });
  buttons[agents.indexOf(agent)].classList.add('on');
  reset();

  const rock = (x0: number, rk: Rock, ghost = false) => {
    const x = x0 + rk.lane * LW + LW / 2;
    ctx.beginPath();
    ctx.ellipse(x, rk.y, 36, 26, 0, 0, Math.PI * 2);
    if (ghost) { ctx.setLineDash([7, 6]); ctx.strokeStyle = '#d9714f'; ctx.lineWidth = 3; ctx.stroke(); ctx.setLineDash([]); }
    else { ctx.fillStyle = rk.hit ? '#c8372d' : '#f2ede0'; ctx.fill(); }
  };

  const drawRoad = (x0: number, rd: Road) => {
    ctx.save();
    ctx.translate(0, TOP);
    ctx.beginPath();
    ctx.rect(x0, 0, RW, H);
    ctx.clip();
    ctx.fillStyle = '#1d2e27';
    ctx.fillRect(x0, 0, RW, H);
    ctx.fillStyle = '#d9a63a';
    for (let l = 1; l < LANES; l++)
      for (let y = -80 + rd.scroll; y < H; y += 80) ctx.fillRect(x0 + l * LW - 3, y, 6, 40);
    rd.rocks.forEach(rk => rock(x0, rk));
    if (rd.live && rd.phase === 'think') rd.seen.forEach(rk => rock(x0, rk, true));
    const cx = x0 + rd.carX * LW + LW / 2;
    ctx.fillStyle = '#d9714f';
    ctx.fillRect(cx - 26, CAR_Y - 40, 52, 80);
    ctx.fillStyle = '#1d2e27';
    ctx.fillRect(cx - 17, CAR_Y - 24, 34, 18);
    if (!rd.live && rd.phase === 'think') { ctx.fillStyle = 'rgba(242,237,224,0.22)'; ctx.fillRect(x0, 0, RW, H); }
    ctx.restore();
    const font = (w: number, px: number) => `${w} ${px}px "Bricolage Grotesque Variable", sans-serif`;
    ctx.fillStyle = '#1d2e27';
    ctx.font = font(800, 44);
    ctx.fillText(rd.live ? 'Live' : 'Frozen', x0, 40);
    ctx.font = font(600, 17);
    ctx.fillText(rd.phase === 'act' ? 'steering' : rd.live ? 'thinking while the road moves' : 'thinking, game paused', x0, 64);
    ctx.font = font(800, 52);
    const n = String(rd.crashes);
    ctx.fillText(n, x0, TOP + H + 56);
    const nw = ctx.measureText(n).width;
    ctx.font = font(600, 17);
    ctx.fillText(`${rd.crashes === 1 ? 'crash' : 'crashes'} in ${rd.gameT.toFixed(0)} s of game time`, x0 + nw + 12, TOP + H + 54);
  };

  let last = 0, visible = false;
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(cv);
  const loop = (t: number) => {
    requestAnimationFrame(loop);
    const dt = Math.min(0.05, (t - last) / 1000);
    last = t;
    if (!visible) return;
    roads.forEach(rd => rd.step(dt));
    ctx.clearRect(0, 0, W, H + TOP + BOT);
    drawRoad(0, roads[0]);
    drawRoad(RW + GAP, roads[1]);
  };
  requestAnimationFrame(loop);
}
