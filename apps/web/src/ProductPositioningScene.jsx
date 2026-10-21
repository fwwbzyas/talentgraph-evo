import { useEffect, useRef } from "react";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import ceramicSurfaceUrl from "./assets/talentgraph-ceramic-surface-v2.png";

const LABELS = [
  { key: "core", position: [0, 0.5, 2.62] },
  { key: "market", position: [0, 0.42, 1.62] },
  { key: "enterprise", position: [0.45, 2.38, -0.32] },
  { key: "growth", position: [0.15, 0.38, 1.68] },
];

const INPUT_POINTS = [[
  new THREE.Vector3(-6.55, 0.2, 0.58),
  new THREE.Vector3(-5.15, 0.21, 0.62),
  new THREE.Vector3(-3.15, 0.23, 0.4),
  new THREE.Vector3(-1.12, 0.25, 0.02),
]];

const OUTPUT_POINTS = [
  [new THREE.Vector3(1.0, 0.22, -0.2), new THREE.Vector3(2.8, 0.2, -1.1), new THREE.Vector3(4.45, 0.18, -1.78), new THREE.Vector3(5.15, 0.18, -1.9)],
  [new THREE.Vector3(0.95, 0.22, 0.7), new THREE.Vector3(2.45, 0.2, 1.85), new THREE.Vector3(3.9, 0.18, 2.7), new THREE.Vector3(4.55, 0.18, 2.85)],
];

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

function smoothstep(value) {
  const next = clamp01(value);
  return next * next * (3 - 2 * next);
}

function standardMaterial(color, options = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.48, metalness: 0.025, ...options });
}

function roundedMesh(width, height, depth, radius, material, segments = 2) {
  return new THREE.Mesh(new RoundedBoxGeometry(width, height, depth, segments, radius), material);
}

function createPalette(texture) {
  return {
    white: standardMaterial(0xffffff, { roughness: 0.38 }),
    surface: standardMaterial(0xffffff, { map: texture, roughness: 0.58 }),
    ceramic: standardMaterial(0xeef5fa, { roughness: 0.62 }),
    ceramicDark: standardMaterial(0xd8e6f0, { roughness: 0.68 }),
    ink: standardMaterial(0x294d6c, { roughness: 0.52 }),
    blue: standardMaterial(0x3f87e6, { emissive: 0x154d99, emissiveIntensity: 0.2, roughness: 0.34 }),
    cyan: standardMaterial(0x67dce3, { emissive: 0x167b83, emissiveIntensity: 0.25, roughness: 0.32 }),
    violet: new THREE.MeshPhysicalMaterial({
      color: 0x7157dc,
      emissive: 0x3e2394,
      emissiveIntensity: 0.38,
      roughness: 0.22,
      metalness: 0.04,
      clearcoat: 0.54,
      clearcoatRoughness: 0.16,
      transmission: 0.04,
    }),
    coral: standardMaterial(0xff9484, { emissive: 0x8f332b, emissiveIntensity: 0.15, roughness: 0.4 }),
    glass: new THREE.MeshPhysicalMaterial({
      color: 0xd7f6ff,
      transparent: true,
      opacity: 0.42,
      roughness: 0.15,
      transmission: 0.05,
      clearcoat: 0.56,
      clearcoatRoughness: 0.2,
      depthWrite: false,
    }),
    glowBlue: new THREE.MeshBasicMaterial({ color: 0x4a91ef, transparent: true, opacity: 0.72, depthWrite: false }),
    glowCyan: new THREE.MeshBasicMaterial({ color: 0x63dfe5, transparent: true, opacity: 0.72, depthWrite: false }),
    glowViolet: new THREE.MeshBasicMaterial({ color: 0x755de1, transparent: true, opacity: 0.72, depthWrite: false }),
  };
}

function makeInstanced(geometry, material, transforms, shadows = true) {
  const mesh = new THREE.InstancedMesh(geometry, material, transforms.length);
  const dummy = new THREE.Object3D();
  transforms.forEach((transform, index) => {
    dummy.position.set(...(transform.position || [0, 0, 0]));
    dummy.rotation.set(...(transform.rotation || [0, 0, 0]));
    dummy.scale.set(...(transform.scale || [1, 1, 1]));
    dummy.updateMatrix();
    mesh.setMatrixAt(index, dummy.matrix);
  });
  mesh.instanceMatrix.needsUpdate = true;
  mesh.castShadow = shadows;
  mesh.receiveShadow = shadows;
  return mesh;
}

function makeRectPlatform(width, depth, palette) {
  const group = new THREE.Group();
  const lower = new THREE.Mesh(new THREE.BoxGeometry(width + 0.32, 0.22, depth + 0.32, 1, 1, 1), palette.ceramicDark);
  lower.position.y = -0.25;
  lower.castShadow = true;
  lower.receiveShadow = true;
  group.add(lower);
  const upper = new THREE.Mesh(new THREE.BoxGeometry(width, 0.14, depth, 1, 1, 1), palette.surface);
  upper.position.y = -0.08;
  upper.castShadow = true;
  upper.receiveShadow = true;
  group.add(upper);
  return group;
}

function makeRoundPlatform(radius, palette) {
  const group = new THREE.Group();
  [
    [radius + 0.28, 0.2, -0.31, palette.ceramicDark],
    [radius + 0.1, 0.14, -0.13, palette.white],
    [radius - 0.06, 0.08, -0.02, palette.surface],
  ].forEach(([tierRadius, height, y, material]) => {
    const tier = new THREE.Mesh(new THREE.CylinderGeometry(tierRadius, tierRadius, height, 48), material);
    tier.position.y = y;
    tier.castShadow = true;
    tier.receiveShadow = true;
    group.add(tier);
  });
  return group;
}

function makePerson(palette, tone = "blue") {
  const group = new THREE.Group();
  const clothing = palette[tone] || palette.blue;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.14, 16, 12), palette.white);
  head.position.y = 1.16;
  head.castShadow = true;
  group.add(head);
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.055, 0.1, 10), palette.white);
  neck.position.y = 1.01;
  group.add(neck);
  const torso = roundedMesh(0.39, 0.46, 0.24, 0.09, clothing, 2);
  torso.position.y = 0.78;
  torso.castShadow = true;
  group.add(torso);
  const shoulder = new THREE.Mesh(new THREE.CapsuleGeometry(0.075, 0.37, 3, 8), clothing);
  shoulder.rotation.z = Math.PI / 2;
  shoulder.position.y = 0.91;
  group.add(shoulder);
  const limbGeometry = new THREE.CapsuleGeometry(0.055, 0.32, 3, 7);
  const limbs = [
    { position: [-0.24, 0.7, 0], rotation: [0, 0, 0.18] },
    { position: [0.24, 0.7, 0], rotation: [0, 0, -0.18] },
  ];
  group.add(makeInstanced(limbGeometry, palette.white, limbs, true));
  const legGeometry = new THREE.CapsuleGeometry(0.065, 0.35, 3, 7);
  group.add(makeInstanced(legGeometry, palette.ink, [
    { position: [-0.1, 0.3, 0] }, { position: [0.1, 0.3, 0] },
  ], true));
  const shoeGeometry = new RoundedBoxGeometry(0.15, 0.08, 0.24, 2, 0.04);
  group.add(makeInstanced(shoeGeometry, palette.ink, [
    { position: [-0.1, 0.04, 0.05] }, { position: [0.1, 0.04, 0.05] },
  ], true));
  return group;
}

function makePanel(width, height, palette, accent = "blue") {
  const group = new THREE.Group();
  const panel = roundedMesh(width, height, 0.14, 0.13, palette.white, 3);
  panel.castShadow = true;
  group.add(panel);
  const screen = roundedMesh(width * 0.88, height * 0.78, 0.02, 0.08, palette.glass, 2);
  screen.position.z = 0.082;
  group.add(screen);
  const lineGeometry = new RoundedBoxGeometry(width * 0.48, 0.035, 0.018, 1, 0.012);
  group.add(makeInstanced(lineGeometry, palette[accent], [
    { position: [-width * 0.12, height * 0.18, 0.105], scale: [1, 1, 1] },
    { position: [-width * 0.12, 0, 0.105], scale: [0.78, 1, 1] },
    { position: [-width * 0.12, -height * 0.18, 0.105], scale: [0.55, 1, 1] },
  ], false));
  return group;
}

function makeSourceWordmark(text, color, width = 0.62) {
  const canvas = document.createElement("canvas");
  canvas.width = 384;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "rgba(255,255,255,.96)";
  context.beginPath();
  context.roundRect(4, 4, 376, 120, 24);
  context.fill();
  context.fillStyle = color;
  context.font = "700 42px 'Microsoft YaHei', sans-serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(text, 192, 65);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, width / 3), material);
  mesh.renderOrder = 6;
  return mesh;
}

function makeSourceTexture(texture, width = 0.66) {
  const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false });
  const ratio = texture.image?.width && texture.image?.height ? texture.image.width / texture.image.height : 3;
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, Math.min(width / ratio, 0.22)), material);
  mesh.renderOrder = 6;
  return mesh;
}

function makeCore(palette) {
  const group = new THREE.Group();
  group.add(makeRoundPlatform(2.5, palette));
  [1.35, 1.8, 2.22].forEach((radius, index) => {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, index === 1 ? 0.035 : 0.022, 6, 64),
      index === 1 ? palette.glowCyan : palette.glowViolet,
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.12 + index * 0.04;
    ring.renderOrder = 3;
    group.add(ring);
  });
  const crystal = new THREE.Mesh(new THREE.IcosahedronGeometry(0.95, 1), palette.violet);
  crystal.position.y = 1.0;
  crystal.rotation.set(0.08, 0.42, 0.04);
  crystal.castShadow = true;
  group.add(crystal);
  const shell = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.02, 1)),
    new THREE.LineBasicMaterial({ color: 0xe9e4ff, transparent: true, opacity: 0.75 }),
  );
  shell.position.copy(crystal.position);
  shell.rotation.copy(crystal.rotation);
  group.add(shell);
  const nodePositions = [
    [-1.45, 0.8, 0.1], [-1.1, 1.48, -0.52], [-0.5, 1.82, 0.3], [0.2, 1.7, -0.68],
    [0.85, 1.45, 0.48], [1.42, 0.86, -0.12], [0.82, 0.48, 0.72], [-0.55, 0.48, 0.78],
  ];
  const edgePositions = [];
  nodePositions.forEach((position, index) => {
    const next = nodePositions[(index + 1) % nodePositions.length];
    edgePositions.push(...position, ...next, ...position, 0, 1.0, 0);
  });
  const edgeGeometry = new THREE.BufferGeometry();
  edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(edgePositions, 3));
  group.add(new THREE.LineSegments(edgeGeometry, new THREE.LineBasicMaterial({ color: 0x7b73e6, transparent: true, opacity: 0.62 })));
  const nodeGeometry = new THREE.SphereGeometry(0.105, 12, 8);
  group.add(makeInstanced(nodeGeometry, palette.white, nodePositions.map((position) => ({ position })), false));
  group.userData.motion = { crystal, shell, rings: group.children.filter((item) => item.geometry?.type === "TorusGeometry") };
  return group;
}

function makeMarketScene(palette) {
  const group = new THREE.Group();
  group.add(makeRoundPlatform(1.78, palette));
  [0.58, 1.02, 1.45].forEach((radius, index) => {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(radius, 0.014, 4, 48), index === 1 ? palette.glowCyan : palette.ceramicDark);
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.08 + index * 0.012;
    group.add(ring);
  });
  const collector = roundedMesh(0.54, 1.35, 0.54, 0.13, palette.glass, 3);
  collector.position.y = 0.75;
  collector.castShadow = true;
  group.add(collector);
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.065, 1.12, 12), palette.ink);
  mast.position.y = 0.78;
  group.add(mast);
  const radar = new THREE.Mesh(new THREE.RingGeometry(0.12, 1.3, 36, 1, 0, Math.PI * 0.24), palette.glowBlue);
  radar.rotation.x = -Math.PI / 2;
  radar.position.y = 0.12;
  group.add(radar);
  const sources = [
    ["招聘岗位", "#16b9aa", -0.72, "cyan"],
    ["岗位版本", "#2c74df", -0.24, "blue"],
    ["企业 ATS", "#7058d9", 0.24, "violet"],
    ["公开岗位", "#3186b8", 0.72, "blue"],
  ];
  const sourceRack = roundedMesh(2.25, 1.05, 0.18, 0.16, palette.ceramicDark, 3);
  sourceRack.position.set(0, 0.72, -0.81);
  sourceRack.castShadow = true;
  group.add(sourceRack);
  sources.forEach(([text, color, x, accent], index) => {
    const terminal = makePanel(0.5, 0.76, palette, accent);
    terminal.position.set(x, 0.76, -0.69);
    terminal.rotation.y = -x * 0.06;
    const wordmark = makeSourceWordmark(text, color, 0.56);
    wordmark.position.set(0, 0.03, 0.09);
    terminal.add(wordmark);
    group.add(terminal);
    const port = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.13, 12), index < 2 ? palette.cyan : palette.blue);
    port.position.set(x * 0.25, 0.12, 0.5);
    group.add(port);
  });
  [
    [palette.sourceLogos?.boss, -0.58, 1.22, 0.72],
    [palette.sourceLogos?.zhaopin, 0.58, 1.22, 0.76],
  ].forEach(([sourceTexture, x, z, width]) => {
    const badge = new THREE.Group();
    const slab = roundedMesh(width + 0.2, 0.5, 0.17, 0.1, palette.white, 3);
    slab.castShadow = true;
    badge.add(slab);
    const face = sourceTexture ? makeSourceTexture(sourceTexture, width) : makeSourceWordmark("招聘来源", "#2d76c9", width);
    face.position.z = 0.093;
    badge.add(face);
    badge.position.set(x, 0.45, z);
    badge.rotation.x = -0.1;
    badge.rotation.y = -x * 0.11;
    group.add(badge);
  });
  const signalGeometry = new THREE.DodecahedronGeometry(0.1, 0);
  group.add(makeInstanced(signalGeometry, palette.cyan, [
    { position: [-1.42, 0.2, 0.35] }, { position: [-0.75, 0.18, 1.22] },
    { position: [0.62, 0.2, 1.36] }, { position: [1.35, 0.2, 0.42] },
  ], false));
  group.userData.motion = { radar };
  return group;
}

function makeSeatedPerson(palette, tone = "blue") {
  const group = new THREE.Group();
  const clothing = palette[tone] || palette.blue;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.13, 14, 10), palette.white);
  head.position.set(0, 0.96, -0.02);
  head.castShadow = true;
  group.add(head);
  const torso = roundedMesh(0.34, 0.4, 0.23, 0.08, clothing, 2);
  torso.position.set(0, 0.69, 0.02);
  torso.rotation.x = -0.08;
  torso.castShadow = true;
  group.add(torso);
  const armGeometry = new THREE.CapsuleGeometry(0.045, 0.3, 3, 7);
  group.add(makeInstanced(armGeometry, palette.white, [
    { position: [-0.19, 0.62, -0.13], rotation: [0.62, 0, 0.18] },
    { position: [0.19, 0.62, -0.13], rotation: [0.62, 0, -0.18] },
  ], true));
  const legGeometry = new THREE.CapsuleGeometry(0.055, 0.34, 3, 7);
  group.add(makeInstanced(legGeometry, palette.ink, [
    { position: [-0.09, 0.3, 0.02], rotation: [1.05, 0, 0] },
    { position: [0.09, 0.3, 0.02], rotation: [1.05, 0, 0] },
  ], true));
  return group;
}

function makeEnterpriseScene(palette) {
  const group = new THREE.Group();
  group.add(makeRectPlatform(4.1, 2.65, palette));
  [-1.15, 0, 1.15].forEach((x, index) => {
    const panel = makePanel(0.94, 1.2, palette, index === 1 ? "cyan" : "blue");
    panel.position.set(x, 1.05, -0.78);
    panel.rotation.y = -x * 0.08;
    group.add(panel);
  });
  const deskGeometry = new RoundedBoxGeometry(1.08, 0.14, 0.52, 3, 0.11);
  group.add(makeInstanced(deskGeometry, palette.white, [-1.12, 0, 1.12].map((x) => ({ position: [x, 0.54, 0.15], rotation: [0, -x * 0.07, 0] })), true));
  const chairSeat = new RoundedBoxGeometry(0.44, 0.1, 0.42, 2, 0.08);
  const chairBack = new RoundedBoxGeometry(0.44, 0.5, 0.1, 2, 0.08);
  group.add(makeInstanced(chairSeat, palette.ceramicDark, [-1.12, 0, 1.12].map((x) => ({ position: [x, 0.26, 0.76] })), true));
  group.add(makeInstanced(chairBack, palette.ceramicDark, [-1.12, 0, 1.12].map((x) => ({ position: [x, 0.55, 0.97] })), true));
  [-1.12, 0, 1.12].forEach((x, index) => {
    const person = makeSeatedPerson(palette, ["blue", "cyan", "violet"][index]);
    person.scale.setScalar(0.82);
    person.position.set(x, 0.03, 0.7);
    person.rotation.y = -x * 0.06;
    group.add(person);
  });
  return group;
}

function makeGrowthScene(palette) {
  const group = new THREE.Group();
  group.add(makeRectPlatform(3.7, 2.55, palette));
  const graphPanel = makePanel(1.55, 1.42, palette, "violet");
  graphPanel.position.set(-0.72, 1.05, -0.72);
  group.add(graphPanel);
  const gapPanel = makePanel(1.08, 1.08, palette, "cyan");
  gapPanel.position.set(0.74, 0.9, -0.75);
  group.add(gapPanel);
  const person = makePerson(palette, "blue");
  person.scale.setScalar(0.8);
  person.position.set(-1.28, 0.02, 0.6);
  person.rotation.y = 0.35;
  group.add(person);
  const stepGeometry = new RoundedBoxGeometry(0.48, 0.2, 0.48, 2, 0.07);
  const steps = Array.from({ length: 5 }, (_, index) => ({
    position: [0.2 + index * 0.45, 0.12 + index * 0.19, 0.72 - index * 0.12],
  }));
  group.add(makeInstanced(stepGeometry, palette.white, steps, true));
  const goal = new THREE.Mesh(new THREE.OctahedronGeometry(0.18, 0), palette.violet);
  goal.position.set(2.02, 1.28, 0.24);
  group.add(goal);
  group.userData.motion = { goal };
  return group;
}

function makeRail(curve, scene, palette, colorMaterial) {
  const geometries = [];
  [-0.105, 0.105].forEach((offset) => {
    const points = curve.points.map((point) => new THREE.Vector3(point.x, point.y - 0.035, point.z + offset));
    const railCurve = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0.24);
    const rail = new THREE.Mesh(new THREE.TubeGeometry(railCurve, 72, 0.026, 5, false), palette.ceramicDark);
    rail.receiveShadow = true;
    scene.add(rail);
    geometries.push(rail.geometry);
  });
  const live = new THREE.Mesh(new THREE.TubeGeometry(curve, 80, 0.046, 6, false), colorMaterial);
  live.renderOrder = 4;
  scene.add(live);
  geometries.push(live.geometry);
  return geometries;
}

function makeRoutes(scene, palette) {
  const curves = [];
  const tracks = [];
  INPUT_POINTS.forEach((points, index) => {
    const curve = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0.24);
    curves.push(curve);
    tracks.push({ kind: "input", geometries: makeRail(curve, scene, palette, index % 2 ? palette.glowBlue : palette.glowCyan) });
  });
  OUTPUT_POINTS.forEach((points, index) => {
    const curve = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0.24);
    curves.push(curve);
    tracks.push({ kind: "output", index, geometries: makeRail(curve, scene, palette, [palette.glowBlue, palette.glowCyan][index]) });
  });
  const count = 49;
  const positions = new Float32Array(count * 3);
  const geometry = new THREE.BufferGeometry();
  const attribute = new THREE.BufferAttribute(positions, 3);
  attribute.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute("position", attribute);
  const particles = new THREE.Points(geometry, new THREE.PointsMaterial({
    color: 0xeaffff,
    size: 0.11,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.9,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  }));
  particles.renderOrder = 6;
  scene.add(particles);
  return { curves, tracks, positions, attribute };
}

function makeGround(scene, palette) {
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(34, 22), new THREE.MeshBasicMaterial({ color: 0xf8fbfe, toneMapped: false }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.5;
  scene.add(ground);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(34, 22), new THREE.ShadowMaterial({ color: 0x6a8ba3, opacity: 0.09 }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = -0.49;
  shadow.receiveShadow = true;
  scene.add(shadow);
  const dotCount = 110;
  const positions = new Float32Array(dotCount * 3);
  for (let index = 0; index < dotCount; index += 1) {
    positions[index * 3] = -12 + ((index * 3.37) % 24);
    positions[index * 3 + 1] = -0.42;
    positions[index * 3 + 2] = -7 + ((index * 1.91) % 14);
  }
  const dotGeometry = new THREE.BufferGeometry();
  dotGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  scene.add(new THREE.Points(dotGeometry, new THREE.PointsMaterial({ color: 0x69d6de, size: 0.026, opacity: 0.28, transparent: true, depthWrite: false })));
}

function disposeScene(scene, texture) {
  const geometries = new Set();
  const materials = new Set();
  scene.traverse((object) => {
    if (object.geometry) geometries.add(object.geometry);
    const next = Array.isArray(object.material) ? object.material : object.material ? [object.material] : [];
    next.forEach((material) => materials.add(material));
  });
  geometries.forEach((geometry) => geometry.dispose());
  materials.forEach((material) => material.dispose());
  texture.dispose();
}

export default function ProductPositioningScene({ progress = 0, active = true, reducedMotion = false, assetMetrics = [] }) {
  const mountRef = useRef(null);
  const labelRefs = useRef([]);
  const progressRef = useRef(progress);
  const activeRef = useRef(active);
  const controllerRef = useRef(null);

  useEffect(() => {
    progressRef.current = progress;
    controllerRef.current?.wake();
  }, [progress]);

  useEffect(() => {
    activeRef.current = active;
    controllerRef.current?.wake();
  }, [active]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fbfe);
    scene.fog = new THREE.Fog(0xf8fbfe, 24, 46);
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 60);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.04;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    mount.appendChild(renderer.domElement);

    const loader = new THREE.TextureLoader();
    const texture = loader.load(ceramicSurfaceUrl, () => controllerRef.current?.wake());
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(2.2, 2.2);
    texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    const palette = createPalette(texture);
    const bossLogoTexture = loader.load("https://static.zhipin.com/v2/web/geek/images/footer-logo.png", () => controllerRef.current?.wake());
    const zhaopinLogoTexture = loader.load("https://fecdn2.zhaopin.cn/landing_zhaopin_com/assets/register-logo.020d1145690fc48e96c917cb4239779c.png", () => controllerRef.current?.wake());
    [bossLogoTexture, zhaopinLogoTexture].forEach((sourceTexture) => { sourceTexture.colorSpace = THREE.SRGBColorSpace; });
    palette.sourceLogos = { boss: bossLogoTexture, zhaopin: zhaopinLogoTexture };
    makeGround(scene, palette);

    scene.add(new THREE.HemisphereLight(0xffffff, 0xd6e8f4, 1.28));
    const key = new THREE.DirectionalLight(0xfffdf8, 2.0);
    key.position.set(-8, 13, 10);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.near = 1;
    key.shadow.camera.far = 42;
    key.shadow.camera.left = -15;
    key.shadow.camera.right = 15;
    key.shadow.camera.top = 11;
    key.shadow.camera.bottom = -11;
    key.shadow.normalBias = 0.025;
    key.shadow.bias = -0.0002;
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xb9e9f5, 0.68);
    fill.position.set(9, 5, 7);
    scene.add(fill);

    const core = makeCore(palette);
    const market = makeMarketScene(palette);
    market.position.set(-6.55, 0, 0.75);
    const enterprise = makeEnterpriseScene(palette);
    enterprise.position.set(6.1, 0, -1.9);
    enterprise.scale.setScalar(0.88);
    const growth = makeGrowthScene(palette);
    growth.position.set(5.35, 0, 2.85);
    growth.scale.setScalar(0.82);
    const groups = [core, market, enterprise, growth];
    groups.forEach((group) => scene.add(group));
    const routes = makeRoutes(scene, palette);
    const anchors = LABELS.map(({ position }, index) => {
      const anchor = new THREE.Object3D();
      anchor.position.set(...position);
      groups[index].add(anchor);
      return anchor;
    });

    const cameraCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, 12.2, 19.2),
      new THREE.Vector3(-0.4, 9.7, 16.6),
      new THREE.Vector3(0.1, 8.5, 15.0),
    ], false, "catmullrom", 0.22);
    const focusCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, 0.6, -0.4),
      new THREE.Vector3(0, 0.7, 0),
      new THREE.Vector3(0, 0.72, 0.1),
    ], false, "catmullrom", 0.22);
    const desiredPosition = new THREE.Vector3();
    const desiredTarget = new THREE.Vector3();
    const currentTarget = new THREE.Vector3(0, 0.6, 0);
    const particlePoint = new THREE.Vector3();
    const worldPoint = new THREE.Vector3();
    const screenPoint = new THREE.Vector3();
    const delays = [0.02, 0.02, 0.5, 0.68];

    let width = 1;
    let height = 1;
    let inViewport = true;
    let pageVisible = document.visibilityState === "visible";
    let frameId = 0;
    let running = false;
    const startedAt = performance.now();

    const resize = () => {
      const bounds = mount.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return;
      width = bounds.width;
      height = bounds.height;
      const mobile = width <= 720;
      camera.aspect = width / height;
      camera.fov = mobile ? 46 : width <= 1100 ? 39 : 34;
      camera.updateProjectionMatrix();
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, mobile || reducedMotion ? 1 : 1.45));
      renderer.setSize(width, height, false);
      key.shadow.mapSize.set(mobile ? 512 : 1024, mobile ? 512 : 1024);
      controllerRef.current?.wake();
    };

    const renderFrame = () => {
      if (!activeRef.current || !inViewport || !pageVisible) {
        running = false;
        return;
      }
      const elapsed = reducedMotion ? 0 : (performance.now() - startedAt) / 1000;
      const nextProgress = clamp01(progressRef.current);
      const eased = smoothstep(nextProgress);
      cameraCurve.getPoint(eased, desiredPosition);
      focusCurve.getPoint(eased, desiredTarget);
      if (width <= 720) {
        desiredPosition.y += 2.2;
        desiredPosition.z += 4.6;
        desiredTarget.z += 0.7;
      }
      if (reducedMotion) {
        camera.position.copy(desiredPosition);
        currentTarget.copy(desiredTarget);
      } else {
        camera.position.lerp(desiredPosition, 0.075);
        currentTarget.lerp(desiredTarget, 0.09);
      }
      camera.lookAt(currentTarget);

      groups.forEach((group, index) => {
        const reveal = index === 0 || index === 1
          ? 0.72 + smoothstep((nextProgress - delays[index]) / 0.25) * 0.28
          : smoothstep((nextProgress - delays[index]) / 0.22);
        const baseScale = index === 0 ? 1 : index === 2 ? 0.88 : index === 3 ? 0.82 : 1;
        group.scale.setScalar(baseScale * (0.72 + reveal * 0.28));
        group.position.y = -(1 - reveal) * (index === 0 ? 0.48 : 1.45 + index * 0.12) + (reducedMotion ? 0 : Math.sin(elapsed * 0.55 + index) * 0.018);
      });
      core.userData.motion.crystal.rotation.y += reducedMotion ? 0 : 0.0036;
      core.userData.motion.shell.rotation.y += reducedMotion ? 0 : 0.0036;
      core.userData.motion.rings.forEach((ring, index) => {
        ring.rotation.z += reducedMotion ? 0 : (index % 2 ? -1 : 1) * 0.0018;
      });
      market.userData.motion.radar.rotation.z = reducedMotion ? 0 : elapsed * 0.34;
      growth.userData.motion.goal.rotation.y += reducedMotion ? 0 : 0.006;

      const inputRouteReveal = smoothstep((nextProgress - 0.08) / 0.3);
      const enterpriseRouteReveal = smoothstep((nextProgress - 0.46) / 0.25);
      const growthRouteReveal = smoothstep((nextProgress - 0.64) / 0.25);
      routes.tracks.forEach((track) => {
        const reveal = track.kind === "input" ? inputRouteReveal : track.index === 0 ? enterpriseRouteReveal : growthRouteReveal;
        track.geometries.forEach((geometry) => {
          const total = geometry.index?.count || geometry.attributes.position.count;
          geometry.setDrawRange(0, Math.max(0, Math.floor(total * reveal / 6) * 6));
        });
      });
      const routeReveals = [inputRouteReveal, enterpriseRouteReveal, growthRouteReveal];
      for (let index = 0; index < routes.positions.length / 3; index += 1) {
        const curveIndex = index % routes.curves.length;
        const phase = (index / 7 + elapsed * 0.065) % 1;
        const offset = index * 3;
        if (phase <= routeReveals[curveIndex]) {
          routes.curves[curveIndex].getPointAt(phase, particlePoint);
          routes.positions[offset] = particlePoint.x;
          routes.positions[offset + 1] = particlePoint.y + 0.08;
          routes.positions[offset + 2] = particlePoint.z;
        } else {
          routes.positions[offset] = 0;
          routes.positions[offset + 1] = -20;
          routes.positions[offset + 2] = 0;
        }
      }
      routes.attribute.needsUpdate = true;
      scene.updateMatrixWorld(true);
      anchors.forEach((anchor, index) => {
        const element = labelRefs.current[index];
        if (!element) return;
        anchor.getWorldPosition(worldPoint);
        screenPoint.copy(worldPoint).project(camera);
        const visible = screenPoint.z > -1 && screenPoint.z < 1 && screenPoint.x > -1.05 && screenPoint.x < 1.05 && screenPoint.y > -1.05 && screenPoint.y < 1.05;
        const x = (screenPoint.x * 0.5 + 0.5) * width;
        const y = (-screenPoint.y * 0.5 + 0.5) * height;
        element.style.opacity = visible ? String(smoothstep((nextProgress - delays[index]) / 0.28)) : "0";
        const attachment = index === 0 || index === 1 || index === 3
          ? "translate(-50%, 6px)"
          : "translate(-50%, -100%)";
        element.style.transform = `translate3d(${x}px, ${y}px, 0) ${attachment}`;
      });
      renderer.render(scene, camera);
      if (reducedMotion) {
        running = false;
        return;
      }
      frameId = requestAnimationFrame(renderFrame);
    };

    const wake = () => {
      if (running || !activeRef.current || !inViewport || !pageVisible) return;
      running = true;
      frameId = requestAnimationFrame(renderFrame);
    };
    controllerRef.current = { wake };
    camera.position.copy(cameraCurve.getPoint(0));
    camera.lookAt(currentTarget);
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(mount);
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      inViewport = entry.isIntersecting;
      if (inViewport) wake();
    }, { rootMargin: "120px" });
    intersectionObserver.observe(mount);
    const onVisibility = () => {
      pageVisible = document.visibilityState === "visible";
      if (pageVisible) wake();
    };
    document.addEventListener("visibilitychange", onVisibility);
    resize();
    wake();

    return () => {
      cancelAnimationFrame(frameId);
      running = false;
      controllerRef.current = null;
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      disposeScene(scene, texture);
      bossLogoTexture.dispose();
      zhaopinLogoTexture.dispose();
      renderer.dispose();
      mount.replaceChildren();
    };
  }, [reducedMotion]);

  return <>
    <div className="positioning-scene-canvas" ref={mountRef} aria-hidden="true" />
    <div className="positioning-scene-labels">
      <div className="positioning-model-label positioning-metric-panel is-core" ref={(element) => { labelRefs.current[0] = element; }}><strong>平台能力资产</strong><div className="positioning-metric-grid"><span><b>{assetMetrics[2]?.[0]}</b><small>图谱展示岗位族</small></span><span><b>{assetMetrics[3]?.[0]}</b><small>有效技能标签</small></span></div></div>
      <div className="positioning-model-label positioning-metric-panel is-market" ref={(element) => { labelRefs.current[1] = element; }}><strong>岗位市场感知</strong><div className="positioning-metric-grid"><span><b>{assetMetrics[0]?.[0]}</b><small>已入库岗位资产</small></span><span><b>{assetMetrics[1]?.[0]}</b><small>当前活跃岗位</small></span></div></div>
      <div className="positioning-model-label is-enterprise" ref={(element) => { labelRefs.current[2] = element; }}><strong>企业人才决策</strong><span>岗位定义 · 人才评估 · 能力盘点</span></div>
      <div className="positioning-model-label is-growth" ref={(element) => { labelRefs.current[3] = element; }}><strong>个人能力成长</strong><span>目标岗位 · 能力差距 · 学习路径</span></div>
    </div>
  </>;
}
