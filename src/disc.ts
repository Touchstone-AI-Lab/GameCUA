// Hero: fifteen game discs, printed with each game's poster, orbit a disc drive on a tilted ring. Every few
// seconds, or on click, one disc flies onto the drive's spindle and spins up while the previous one returns
// to its slot. Drag turns the ring. Returns load(slug) so other parts of the page can load a disc.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { data, img } from './data';

const R = 3.55, DR = 0.7, TOP = 0.42;

/** Poster cropped into a disc with a clear hub, a silver ring and a faint sheen. */
function discTexture(src: string) {
  const S = 512, cv = document.createElement('canvas');
  cv.width = cv.height = S;
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  const im = new Image();
  im.onload = () => {
    const c = cv.getContext('2d')!, h = S / 2;
    c.save();
    c.beginPath(); c.arc(h, h, h - 2, 0, Math.PI * 2); c.moveTo(h + S * 0.07, h); c.arc(h, h, S * 0.07, 0, Math.PI * 2, true); c.clip('evenodd');
    const k = S / Math.min(im.width, im.height);
    c.drawImage(im, h - (im.width * k) / 2, h - (im.height * k) / 2.6, im.width * k, im.height * k);
    c.fillStyle = 'rgba(214,224,240,0.82)';
    c.beginPath(); c.arc(h, h, S * 0.17, 0, 7); c.fill();
    c.strokeStyle = 'rgba(120,135,160,0.7)'; c.lineWidth = 2;
    c.beginPath(); c.arc(h, h, S * 0.12, 0, 7); c.stroke();
    const sheen = c.createConicGradient(0.6, h, h);
    [[0, .0], [.12, .22], [.25, 0], [.5, 0], [.62, .18], [.75, 0], [1, 0]].forEach(([p, a]) => sheen.addColorStop(p, `rgba(255,255,255,${a})`));
    c.fillStyle = sheen; c.fillRect(0, 0, S, S);
    c.restore();
    c.strokeStyle = 'rgba(230,238,250,0.85)'; c.lineWidth = 4;
    c.beginPath(); c.arc(h, h, h - 3, 0, 7); c.stroke();
    tex.needsUpdate = true;
  };
  im.src = src;
  return tex;
}

export function discs(canvas: HTMLCanvasElement, onLoad: (slug: string) => void) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0, 0);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  scene.add(new THREE.HemisphereLight('#dce8ff', '#0c1524', 1.3));
  const key = new THREE.DirectionalLight('#ffffff', 2.4);
  key.position.set(-4, 8, 6);
  scene.add(key);
  const rim = new THREE.DirectionalLight('#8cb8ff', 1.6);
  rim.position.set(5, 2, -6);
  scene.add(rim);

  // Drive: a dark rounded slab, a glowing pedestal on top, a slot and a status light on the front.
  const drive = new THREE.Group();
  const body = new THREE.Mesh(new RoundedBoxGeometry(3.7, 0.72, 2.5, 5, 0.16),
    new THREE.MeshStandardMaterial({ color: '#1a2840', roughness: 0.38, metalness: 0.65 }));
  body.position.y = -0.36;
  const ped = new THREE.Mesh(new THREE.CylinderGeometry(0.86, 0.9, 0.1, 72),
    new THREE.MeshStandardMaterial({ color: '#33435c', roughness: 0.3, metalness: 0.85 }));
  ped.position.y = 0.05;
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.9, 0.014, 10, 96), new THREE.MeshBasicMaterial({ color: '#8cb8ff' }));
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.1;
  const spindle = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.2, 24), new THREE.MeshStandardMaterial({ color: '#c9d6ea', metalness: 0.9, roughness: 0.2 }));
  spindle.position.y = 0.2;
  const slot = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.05, 0.02), new THREE.MeshBasicMaterial({ color: '#05080e' }));
  slot.position.set(0, -0.26, 1.251);
  const led = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.035, 0.02), new THREE.MeshBasicMaterial({ color: '#8cb8ff' }));
  led.position.set(1.4, -0.5, 1.251);
  drive.add(body, ped, ring, spindle, slot, led);
  scene.add(drive);

  // A soft blue pool of light under the drive.
  const gc = document.createElement('canvas');
  gc.width = gc.height = 256;
  const g2 = gc.getContext('2d')!, gr = g2.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, 'rgba(90,150,255,0.55)'); gr.addColorStop(0.45, 'rgba(70,120,220,0.18)'); gr.addColorStop(1, 'rgba(60,100,200,0)');
  g2.fillStyle = gr; g2.fillRect(0, 0, 256, 256);
  const glow = new THREE.Mesh(new THREE.PlaneGeometry(9, 6), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(gc), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  glow.rotation.x = -Math.PI / 2;
  glow.position.y = -0.64;
  scene.add(glow);

  // Orbit: a thin line with a few small beads, tilted like the disc ring.
  const tilt = new THREE.Euler(0.3, 0, -0.1);
  const tq = new THREE.Quaternion().setFromEuler(tilt);
  const orbit = new THREE.Group();
  orbit.quaternion.copy(tq);
  orbit.position.y = 0.5;
  const pts = Array.from({ length: 129 }, (_, i) => new THREE.Vector3(Math.sin(i / 128 * Math.PI * 2) * R, 0, Math.cos(i / 128 * Math.PI * 2) * R));
  orbit.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: '#6f9bd8', transparent: true, opacity: 0.35 })));
  scene.add(orbit);
  const beads = [0.31, 1.9, 3.3, 4.6, 5.7].map((a, i) => {
    const b = new THREE.Mesh(new THREE.SphereGeometry(0.06, 16, 12), new THREE.MeshBasicMaterial({ color: i % 2 ? '#e2c377' : '#9fe6f2' }));
    b.userData.a = a;
    orbit.add(b);
    return b;
  });

  // Discs: the poster prints on both faces.
  const games = data.games;
  const circle = new THREE.CircleGeometry(DR, 64);
  const list = games.map((g, i) => {
    const m = new THREE.Mesh(circle, new THREE.MeshBasicMaterial({ map: discTexture(img(`poster/${g.slug}.webp`)), transparent: true, alphaTest: 0.5, side: THREE.DoubleSide }));
    m.userData.i = i;
    scene.add(m);
    return { g, m, a: (i / games.length) * Math.PI * 2, hover: 0 };
  });
  const hits = list.map(d => d.m);

  let ang = 0, vel = 0.0022, cur = -1, prev = -1, t = 1, spin = 0, spinV = 0, idle = 0, dragging = false, lastX = 0, moved = 0;
  const flat = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0));
  const seat = new THREE.Vector3(0, TOP - 0.2, 0);
  const tmpQ = new THREE.Quaternion(), qa = new THREE.Quaternion(), qb = new THREE.Quaternion();
  const pa = new THREE.Vector3(), pb = new THREE.Vector3(), out = new THREE.Vector3(), cv3 = new THREE.Vector3(), m4 = new THREE.Matrix4();
  const ease = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

  const ringPose = (d: (typeof list)[number], p: THREE.Vector3, q: THREE.Quaternion) => {
    const a = d.a + ang, r = R + d.hover * 0.5;
    p.set(Math.sin(a) * r, d.hover * 0.3, Math.cos(a) * r).applyQuaternion(tq);
    p.y += 0.5;
    // Lean each disc toward the camera so the printed side reads all around the ring.
    out.set(Math.sin(a), 0, Math.cos(a)).applyQuaternion(tq);
    cv3.copy(camera.position).sub(p).normalize();
    if (out.dot(cv3) < 0) out.negate();
    out.multiplyScalar(0.4).add(cv3.multiplyScalar(0.6)).add(p);
    m4.lookAt(out, p, THREE.Object3D.DEFAULT_UP);
    q.setFromRotationMatrix(m4);
  };
  const seatPose = (p: THREE.Vector3, q: THREE.Quaternion) => {
    p.copy(seat);
    q.copy(flat).multiply(tmpQ.setFromAxisAngle(new THREE.Vector3(0, 0, 1), spin));
  };

  const load = (i: number) => {
    if (i === cur) return;
    prev = cur; cur = i; t = 0; spinV = 0;
    led.material.color.set('#e2c377');
  };
  const loadSlug = (slug: string) => { idle = 0; load(games.findIndex(g => g.slug === slug)); };

  const resize = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const far = w / h < 1 ? 17.5 : 15;
    camera.position.set(0, 5.4, far);
    camera.lookAt(0, 0.2, 0);
    camera.updateProjectionMatrix();
  };
  addEventListener('resize', resize);
  resize();

  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2(9, 9);
  let hovered = -1;
  canvas.addEventListener('pointerdown', e => { dragging = true; lastX = e.clientX; moved = 0; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', e => {
    const r = canvas.getBoundingClientRect();
    ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    if (!dragging) return;
    const dx = e.clientX - lastX;
    lastX = e.clientX; moved += Math.abs(dx);
    ang += dx * 0.005; vel = dx * 0.0008;
  });
  canvas.addEventListener('pointerup', () => {
    if (moved < 6 && hovered >= 0) loadSlug(games[hovered].slug);
    dragging = false;
  });
  canvas.addEventListener('pointercancel', () => { dragging = false; });
  canvas.addEventListener('pointerleave', () => ptr.set(9, 9));

  let visible = true, last = performance.now();
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(canvas);
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;

  const tick = (now: number) => {
    requestAnimationFrame(tick);
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (!visible) return;
    if (!dragging) { vel += (0.0022 - vel) * 0.03; if (!still) ang += vel; }
    idle += dt;
    if (idle > 6.5 && t >= 1 && !still) { idle = 0; load((cur + 1) % games.length); }
    if (t < 1) {
      t = Math.min(1, t + dt / 1.25);
      if (t >= 1) { led.material.color.set('#8cb8ff'); onLoad(games[cur].slug); }
    }
    spinV += ((t >= 1 ? 7 : 1.5) - spinV) * 0.04;
    spin += spinV * dt;
    beads.forEach(b => { const a = b.userData.a + ang * 0.6; b.position.set(Math.sin(a) * R, 0, Math.cos(a) * R); });

    ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(hits)[0];
    hovered = hit && !dragging ? hit.object.userData.i : -1;
    canvas.style.cursor = hovered >= 0 && hovered !== cur ? 'pointer' : dragging ? 'grabbing' : 'grab';

    const e = ease(t);
    list.forEach((d, i) => {
      d.hover += ((i === hovered && i !== cur ? 1 : 0) - d.hover) * 0.15;
      if (i === cur) {
        ringPose(d, pa, qa); seatPose(pb, qb);
        d.m.position.lerpVectors(pa, pb, e); d.m.position.y += Math.sin(Math.PI * e) * 1.6;
        d.m.quaternion.slerpQuaternions(qa, qb, e);
      } else if (i === prev && t < 1) {
        seatPose(pa, qa); ringPose(d, pb, qb);
        d.m.position.lerpVectors(pa, pb, e); d.m.position.y += Math.sin(Math.PI * e) * 1.2;
        d.m.quaternion.slerpQuaternions(qa, qb, e);
      } else {
        ringPose(d, d.m.position, d.m.quaternion);
      }
      d.m.scale.setScalar(1 + d.hover * 0.12);
    });
    renderer.render(scene, camera);
  };
  requestAnimationFrame(tick);
  load(games.findIndex(g => g.slug === 'peak'));
  return loadSlug;
}
