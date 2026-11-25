// Scores: a 3D field of 15 games x 6 agents. Bar height is the milestone score; the Live/Frozen switch
// animates every bar to the other mode. Pointing at a bar dims the other games and prints that game's six scores.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { data, type Mode } from './data';

export const MODEL_COLORS = ['#d9714f', '#d9a63a', '#80a99c', '#8fa7c4', '#c98fa5', '#e9e2cf'];

export function bars(canvas: HTMLCanvasElement) {
  const wrap = canvas.parentElement!;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  const night = new THREE.Color('#121b17');
  const scene = new THREE.Scene();
  scene.background = night;
  scene.fog = new THREE.Fog(night, 30, 60);
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 200);
  camera.position.set(-7, 13, 25);

  scene.add(new THREE.HemisphereLight('#fff6e0', '#20302a', 1.4));
  const sun = new THREE.DirectionalLight('#ffffff', 2.2);
  sun.position.set(-10, 22, 12);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -20, right: 20, top: 20, bottom: -20 });
  scene.add(sun);

  const G = data.games, M = data.models, GX = 1.45, MZ = 2.1, UNIT = 0.1;
  const ox = ((G.length - 1) * GX) / 2, oz = ((M.length - 1) * MZ) / 2;
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.ShadowMaterial({ opacity: 0.45 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  const box = new THREE.BoxGeometry(1, 1, 1);
  box.translate(0, 0.5, 0);
  const meshes: THREE.Mesh[] = [];
  M.forEach((m, mi) => G.forEach((g, gi) => {
    const mat = new THREE.MeshStandardMaterial({ color: MODEL_COLORS[mi], roughness: 0.55, metalness: 0.05 });
    const b = new THREE.Mesh(box, mat);
    b.scale.set(0.9, 0.01, 1.05);
    b.position.set(gi * GX - ox, 0, mi * MZ - oz);
    b.castShadow = b.receiveShadow = true;
    b.userData = { model: m, game: g, h: 0.01, target: 0.01, mi };
    scene.add(b);
    meshes.push(b);
  }));

  // Name labels are HTML so they stay crisp; they are projected each frame.
  const labels: { el: HTMLElement; p: THREE.Vector3 }[] = [];
  const label = (text: string, p: THREE.Vector3, cls = '') => {
    const el = document.createElement('div');
    el.className = `bar-label ${cls}`;
    el.textContent = text;
    wrap.appendChild(el);
    labels.push({ el, p });
    return el;
  };
  const gameLabels = G.map((g, gi) => label(g.name.replace('The Binding of Isaac', 'Isaac').replace('Hollow Knight: ', '').replace('Oxygen Not Included', 'ONI').replace('Untitled Goose Game', 'Goose').replace('Civilization VI', 'Civ VI'),
    new THREE.Vector3(gi * GX - ox, 0, oz + 1.6), 'game'));
  M.forEach((m, mi) => label(m, new THREE.Vector3(-ox - 1.1, 0, mi * MZ - oz), 'model'));
  labels.forEach((l, i) => { if (i >= G.length) l.el.style.color = MODEL_COLORS[i - G.length]; });
  const vals = M.map(() => { const p = new THREE.Vector3(); const el = label('', p, 'val'); el.style.opacity = '0'; return { el, p }; });

  const controls = new OrbitControls(camera, canvas);
  controls.target.set(0, 1.2, 1);
  controls.enableZoom = false;
  controls.enableDamping = true;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.35;
  controls.minPolarAngle = 0.5;
  controls.maxPolarAngle = 1.35;
  controls.minAzimuthAngle = -0.75;
  controls.maxAzimuthAngle = 0.35;
  let dir = 1;

  const resize = () => {
    const w = wrap.clientWidth, h = wrap.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.fov = w < 900 ? 52 : 34;
    camera.updateProjectionMatrix();
  };
  addEventListener('resize', resize);
  resize();

  const ray = new THREE.Raycaster();
  const ptr = new THREE.Vector2(9, 9);
  let mx = 0, my = 0, mode: Mode = 'live';
  canvas.addEventListener('pointermove', e => {
    const r = canvas.getBoundingClientRect();
    mx = e.clientX - r.left; my = e.clientY - r.top;
    ptr.set((mx / r.width) * 2 - 1, -(my / r.height) * 2 + 1);
  });
  canvas.addEventListener('pointerleave', () => ptr.set(9, 9));

  const set = (m: Mode) => {
    mode = m;
    for (const b of meshes) {
      const s = data.scores[b.userData.model][m][b.userData.game.slug];
      b.userData.target = s == null ? 0.01 : Math.max(0.03, s * UNIT);
      b.userData.none = s == null;
      (b.material as THREE.MeshStandardMaterial).opacity = 1;
    }
  };

  let visible = false;
  new IntersectionObserver(([e]) => {
    if (e.isIntersecting && !visible) set(mode);
    visible = e.isIntersecting;
  }, { threshold: 0.25 }).observe(canvas);
  for (const b of meshes) b.userData.target = 0.01;

  const v = new THREE.Vector3();
  const base = meshes.map(b => (b.material as THREE.MeshStandardMaterial).color.clone());
  let col = -1;
  const tick = () => {
    requestAnimationFrame(tick);
    if (!visible) return;
    // Sweep back and forth inside the allowed azimuth range.
    const az = controls.getAzimuthalAngle();
    if (az > 0.3) dir = -1; else if (az < -0.7) dir = 1;
    controls.autoRotateSpeed = 0.35 * dir;
    controls.update();
    for (const b of meshes) {
      const u = b.userData;
      u.h += (u.target - u.h) * (0.05 + (u.mi + (u.game.slug.length % 5)) * 0.004);
      b.scale.y = u.h;
    }
    ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(meshes)[0]?.object as THREE.Mesh | undefined;
    const c = hit ? G.indexOf(hit.userData.game) : -1;
    if (c !== col) {
      col = c;
      meshes.forEach((b, k) => (b.material as THREE.MeshStandardMaterial).color.copy(base[k]).multiplyScalar(c < 0 || G.indexOf(b.userData.game) === c ? 1 : 0.35));
      gameLabels.forEach((el, k) => { el.classList.toggle('on', k === c); el.style.opacity = c < 0 || k === c ? '1' : '0.35'; });
    }
    vals.forEach((l, mi) => {
      l.el.style.opacity = col < 0 ? '0' : '1';
      if (col < 0) return;
      const b = meshes[mi * G.length + col], s = data.scores[M[mi]][mode][G[col].slug];
      l.el.textContent = s == null ? '–' : s.toFixed(1);
      l.p.set(b.position.x, b.userData.h + 0.45, b.position.z);
    });
    const w = canvas.clientWidth, h = canvas.clientHeight;
    for (const l of labels) {
      v.copy(l.p).project(camera);
      l.el.style.transform = `translate(${(v.x + 1) * w / 2}px, ${(1 - v.y) * h / 2}px) translate(${l.el.classList.contains('model') ? '-100%' : '-50%'}, -50%)`;
    }
    renderer.render(scene, camera);
  };
  tick();
  return set;
}
