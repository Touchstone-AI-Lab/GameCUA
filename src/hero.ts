// Hero: a tilted ring of the 15 game posters on cream paper. Drag spins it with inertia, scroll turns it,
// hovering lifts a poster out of the ring, clicking opens that game's sheet.
import * as THREE from 'three';
import { data, img } from './data';

export function hero(canvas: HTMLCanvasElement, open: (slug: string) => void) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const paper = new THREE.Color('#f2ede0');
  const scene = new THREE.Scene();
  scene.background = paper;
  scene.fog = new THREE.Fog(paper, 17, 32);
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);

  const ring = new THREE.Group();
  const tilt = new THREE.Group();
  tilt.add(ring);
  tilt.rotation.set(0.2, 0, -0.12);
  scene.add(tilt);

  const games = data.games;
  const R = 5.4, W = 1.6, H = 2.4;
  const loader = new THREE.TextureLoader();
  const cards: THREE.Mesh[] = [];
  const geo = new THREE.PlaneGeometry(W, H, 12, 1);
  // Bend each card slightly so it follows the ring.
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i);
    pos.setZ(i, -(x * x) / (2 * R) * 1.6);
  }
  games.forEach((g, i) => {
    const tex = loader.load(img(`poster/${g.slug}.webp`));
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    const mat = new THREE.MeshBasicMaterial({ map: tex, side: THREE.DoubleSide, fog: true });
    const m = new THREE.Mesh(geo, mat);
    const a = (i / games.length) * Math.PI * 2;
    m.position.set(Math.sin(a) * R, 0, Math.cos(a) * R);
    m.rotation.y = a;
    m.userData = { slug: g.slug, a, lift: 0 };
    ring.add(m);
    cards.push(m);
  });

  // A soft shadow on the paper under the ring.
  const sh = document.createElement('canvas');
  sh.width = sh.height = 256;
  const c = sh.getContext('2d')!;
  const grad = c.createRadialGradient(128, 128, 60, 128, 128, 128);
  grad.addColorStop(0, 'rgba(29,46,39,0.0)');
  grad.addColorStop(0.62, 'rgba(29,46,39,0.16)');
  grad.addColorStop(1, 'rgba(29,46,39,0)');
  c.fillStyle = grad;
  c.fillRect(0, 0, 256, 256);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(R * 2.9, R * 2.9),
    new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sh), transparent: true, depthWrite: false }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = -H / 2 - 0.9;
  tilt.add(shadow);

  let angle = 0, vel = 0.0016, dragging = false, lastX = 0, moved = 0, scrollT = 0;
  const ray = new THREE.Raycaster();
  const ptr = new THREE.Vector2(9, 9);
  let hovered: THREE.Mesh | null = null;

  const resize = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const narrow = w < 900;
    camera.position.set(0, narrow ? 3.4 : 2.6, narrow ? 24 : 17);
    camera.lookAt(narrow ? 0 : -0.4, narrow ? 1.6 : 0.2, 0);
    tilt.position.x = narrow ? 0 : 6.1;
    camera.updateProjectionMatrix();
  };
  addEventListener('resize', resize);
  resize();

  canvas.addEventListener('pointerdown', e => {
    dragging = true; lastX = e.clientX; moved = 0;
    canvas.setPointerCapture(e.pointerId);
    canvas.classList.add('dragging');
  });
  canvas.addEventListener('pointermove', e => {
    const r = canvas.getBoundingClientRect();
    ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    if (!dragging) return;
    const dx = e.clientX - lastX;
    lastX = e.clientX; moved += Math.abs(dx);
    vel = dx * 0.0009;
    angle += dx * 0.0042;
  });
  const up = () => { dragging = false; canvas.classList.remove('dragging'); };
  canvas.addEventListener('pointerup', () => {
    if (moved < 6 && hovered) open(hovered.userData.slug);
    up();
  });
  canvas.addEventListener('pointercancel', up);
  canvas.addEventListener('pointerleave', () => ptr.set(9, 9));
  addEventListener('scroll', () => { scrollT = Math.min(1, scrollY / innerHeight); }, { passive: true });

  let visible = true;
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(canvas);

  const tick = () => {
    requestAnimationFrame(tick);
    if (!visible) return;
    if (!dragging) {
      vel += (0.0016 - vel) * 0.02;
      angle += vel;
    }
    ring.rotation.y = angle + scrollT * 1.4;
    tilt.rotation.x = 0.2 + scrollT * 0.35;
    ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(cards)[0]?.object as THREE.Mesh | undefined;
    hovered = hit && !dragging ? hit : null;
    canvas.style.cursor = hovered ? 'pointer' : dragging ? 'grabbing' : 'grab';
    for (const m of cards) {
      const u = m.userData;
      u.lift += ((m === hovered ? 1 : 0) - u.lift) * 0.12;
      const r = R + u.lift * 0.9;
      m.position.set(Math.sin(u.a) * r, u.lift * 0.35, Math.cos(u.a) * r);
      m.scale.setScalar(1 + u.lift * 0.12);
    }
    renderer.render(scene, camera);
  };
  tick();
}
