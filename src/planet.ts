// Footer planet: the Touchstone star texture from touchstoneai.org on a slowly turning sphere that rises
// from the bottom right edge, lit from the upper left, with a soft gold halo.
import * as THREE from 'three';

export function planet(canvas: HTMLCanvasElement, texUrl: string) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#121b17');
  const camera = new THREE.PerspectiveCamera(12, 1, 0.1, 400);
  camera.position.set(0, 0, 52);

  const tex = new THREE.TextureLoader().load(texUrl);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  const R = 9;
  const ball = new THREE.Mesh(new THREE.SphereGeometry(R, 96, 64),
    new THREE.MeshStandardMaterial({ map: tex, roughness: 1, metalness: 0, color: '#7d746a' }));
  ball.rotation.z = 0.25;
  scene.add(ball);
  const sun = new THREE.DirectionalLight('#fff1dc', 2.6);
  sun.position.set(-6, 8, 4);
  scene.add(sun, new THREE.AmbientLight('#2c3a33', 0.6));

  // Atmosphere: a soft halo outside the limb, fading outward from the planet's edge.
  const halo = new THREE.Mesh(new THREE.SphereGeometry(R * 1.12, 96, 64), new THREE.ShaderMaterial({
    transparent: true, side: THREE.BackSide, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { c: { value: new THREE.Color('#d9a63a') } },
    vertexShader: 'varying vec3 n; varying vec3 v; void main(){ n = normalize(normalMatrix * normal); vec4 p = modelViewMatrix * vec4(position,1.); v = normalize(-p.xyz); gl_Position = projectionMatrix * p; }',
    fragmentShader: 'uniform vec3 c; varying vec3 n; varying vec3 v; void main(){ float d = abs(dot(n, v)); float f = smoothstep(0.0, 0.46, d); gl_FragColor = vec4(c, pow(f, 2.5) * .45); }',
  }));
  scene.add(halo);

  const resize = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    // Put the sphere's centre below the bottom edge, right of centre, so only its cap shows.
    const halfH = Math.tan((camera.fov * Math.PI) / 360) * camera.position.z, halfW = halfH * camera.aspect;
    ball.position.set(halfW * 0.42, -halfH - R * 0.5, 0);
    halo.position.copy(ball.position);
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
