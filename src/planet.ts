// Footer planet: the Touchstone star texture from touchstoneai.org on a slowly turning sphere that
// sits half off the left edge, lit from the right, with a soft warm halo and a field of faint stars.
import * as THREE from 'three';

export function planet(canvas: HTMLCanvasElement, texUrl: string) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#000');
  const camera = new THREE.PerspectiveCamera(12, 1, 0.1, 400);
  camera.position.set(0, 0, 52);

  const tex = new THREE.TextureLoader().load(texUrl);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  const R = 7.2;
  const ball = new THREE.Mesh(new THREE.SphereGeometry(R, 96, 64),
    new THREE.MeshStandardMaterial({ map: tex, roughness: 1, metalness: 0, color: '#9a8f84' }));
  ball.rotation.z = 0.25;
  scene.add(ball);
  const sun = new THREE.DirectionalLight('#fff1dc', 2.6);
  sun.position.set(10, 2, 1.5);
  scene.add(sun, new THREE.AmbientLight('#3a3450', 0.5));

  // Atmosphere: a soft halo outside the limb, fading outward from the planet's edge.
  const halo = new THREE.Mesh(new THREE.SphereGeometry(R * 1.12, 96, 64), new THREE.ShaderMaterial({
    transparent: true, side: THREE.BackSide, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { c: { value: new THREE.Color('#c99868') } },
    vertexShader: 'varying vec3 n; varying vec3 v; void main(){ n = normalize(normalMatrix * normal); vec4 p = modelViewMatrix * vec4(position,1.); v = normalize(-p.xyz); gl_Position = projectionMatrix * p; }',
    fragmentShader: 'uniform vec3 c; varying vec3 n; varying vec3 v; void main(){ float d = abs(dot(n, v)); float f = smoothstep(0.0, 0.46, d); gl_FragColor = vec4(c, pow(f, 2.5) * .45); }',
  }));
  scene.add(halo);

  const N = 420, pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) pos.set([(Math.random() - 0.5) * 120, (Math.random() - 0.5) * 30, -30 - Math.random() * 30], i * 3);
  const sg = new THREE.BufferGeometry();
  sg.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  scene.add(new THREE.Points(sg, new THREE.PointsMaterial({ color: '#ffffff', size: 0.1, transparent: true, opacity: 0.8 })));

  const resize = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    // Put the sphere's centre just past the left edge of the view.
    const halfW = Math.tan((camera.fov * Math.PI) / 360) * camera.position.z * camera.aspect;
    ball.position.x = halo.position.x = -halfW + R * 0.2;
  };
  addEventListener('resize', resize);
  resize();

  let visible = false;
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(canvas);
  const tick = () => {
    requestAnimationFrame(tick);
    if (!visible) return;
    ball.rotation.y += 0.0012;
    renderer.render(scene, camera);
  };
  tick();
}
