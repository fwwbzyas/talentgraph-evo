import { useEffect, useRef } from "react";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import ceramicSurfaceUrl from "./assets/talentgraph-ceramic-surface-v2.png";

const STATION_ANCHORS = [
  new THREE.Vector3(-8.2, 0, -0.7),
  new THREE.Vector3(-2.7, 0, 0.65),
  new THREE.Vector3(3.2, 0, 0.32),
  new THREE.Vector3(8.3, 0, -0.2),
];
const STATION_DEPTHS = [2.65, 2.95, 2.95, 2.8];

const ROUTE_POINTS = [
  new THREE.Vector3(-11.1, 0.2, 1.8),
  new THREE.Vector3(-8.2, 0.2, 1.35),
  new THREE.Vector3(-5.45, 0.2, 1.92),
  new THREE.Vector3(-2.7, 0.2, 1.42),
  new THREE.Vector3(0.15, 0.2, 1.93),
  new THREE.Vector3(3.2, 0.2, 1.38),
  new THREE.Vector3(5.9, 0.2, 1.86),
  new THREE.Vector3(8.3, 0.2, 1.4),
  new THREE.Vector3(11.25, 0.2, 2.05),
];

const ROUTE_COLORS = [0xff8d7c, 0x67dbe6, 0x735ce0, 0x3d8eea, 0x62d7df];
const STAGE_PROGRESS = [0, 1 / 3, 2 / 3, 1];

const CAMERA_POINTS = [
  new THREE.Vector3(-10.7, 6.8, 9.9),
  new THREE.Vector3(-4.55, 5.35, 7.8),
  new THREE.Vector3(1.85, 5.45, 7.7),
  new THREE.Vector3(10.1, 5.8, 8.75),
];

const FOCUS_POINTS = [
  new THREE.Vector3(-10.5, 0.72, -0.55),
  new THREE.Vector3(-3.85, 0.88, 0.65),
  new THREE.Vector3(2.05, 1.48, 0.32),
  new THREE.Vector3(8.55, 0.82, -0.1),
];

const LABEL_ANCHOR_POINTS = [
  [[-0.74, 1.72, 0.06], [-1.48, 1.16, 0.46], [0.08, 0.3, 1.22]],
  [[0.62, 1.92, 0.68], [0.62, 1.3, 0.68], [-0.72, 0.26, 1.06]],
  [[0, 2.08, 0.08], [1.26, 1.78, 0.48], [-0.92, 0.48, 1.18]],
  [[0.48, 2.04, -0.06], [-0.05, 1.42, 0.42], [2.72, 1.72, -0.18]],
];

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

function smoothstep(value) {
  const progress = clamp01(value);
  return progress * progress * (3 - 2 * progress);
}

function standardMaterial(color, options = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.46, metalness: 0.03, ...options });
}

function roundedMesh(width, height, depth, radius, material, segments = 2) {
  return new THREE.Mesh(new RoundedBoxGeometry(width, height, depth, segments, radius), material);
}

function createPalette(surfaceTexture) {
  return {
    white: standardMaterial(0xffffff, { roughness: 0.4 }),
    ceramic: standardMaterial(0xf1f7fb, { roughness: 0.6 }),
    ceramicDark: standardMaterial(0xd9e7f0, { roughness: 0.66 }),
    surface: standardMaterial(0xffffff, { map: surfaceTexture, roughness: 0.6, metalness: 0.01 }),
    cyan: standardMaterial(0x72e0e5, { emissive: 0x1d808d, emissiveIntensity: 0.28, roughness: 0.32 }),
    blue: standardMaterial(0x438de8, { emissive: 0x1c5fb4, emissiveIntensity: 0.24, roughness: 0.32 }),
    violet: new THREE.MeshPhysicalMaterial({
      color: 0x7358d9,
      emissive: 0x3b218d,
      emissiveIntensity: 0.34,
      roughness: 0.25,
      metalness: 0.05,
      clearcoat: 0.42,
      clearcoatRoughness: 0.2,
    }),
    coral: standardMaterial(0xff9483, { emissive: 0xa14338, emissiveIntensity: 0.18, roughness: 0.38 }),
    dark: standardMaterial(0x284c69, { roughness: 0.5 }),
    glowCyan: new THREE.MeshBasicMaterial({ color: 0x57d7df, transparent: true, opacity: 0.58, depthWrite: false }),
    glowViolet: new THREE.MeshBasicMaterial({ color: 0x735ce0, transparent: true, opacity: 0.46, depthWrite: false }),
    glass: new THREE.MeshPhysicalMaterial({
      color: 0xb8efff,
      transparent: true,
      opacity: 0.3,
      roughness: 0.12,
      metalness: 0.02,
      transmission: 0.08,
      thickness: 0.45,
      clearcoat: 0.72,
      clearcoatRoughness: 0.16,
      depthWrite: false,
    }),
  };
}

function createSurfaceTexture(renderer, onLoad) {
  const texture = new THREE.TextureLoader().load(ceramicSurfaceUrl, () => {
    onLoad?.();
  });
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(2.5, 2.5);
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  return texture;
}

function makePlatform(width, depth, palette, square = false) {
  const group = new THREE.Group();
  const platformMesh = (nextWidth, height, nextDepth, radius, material, segments = 3) => (
    square
      ? new THREE.Mesh(new THREE.BoxGeometry(nextWidth, height, nextDepth, 1, 1, 1), material)
      : roundedMesh(nextWidth, height, nextDepth, radius, material, segments)
  );
  const lower = platformMesh(width + 0.38, 0.22, depth + 0.38, 0.24, palette.ceramicDark);
  lower.position.y = -0.34;
  lower.castShadow = true;
  lower.receiveShadow = true;
  group.add(lower);
  const upper = platformMesh(width + 0.14, 0.15, depth + 0.14, 0.2, palette.white);
  upper.position.y = -0.15;
  upper.castShadow = true;
  upper.receiveShadow = true;
  group.add(upper);
  const inset = platformMesh(width, 0.055, depth, 0.17, palette.surface);
  inset.position.y = -0.035;
  inset.receiveShadow = true;
  group.add(inset);
  group.add(makeRectRail(width * 0.86, depth * 0.82, 0.035, palette.ceramicDark, 0.016));
  const channel = roundedMesh(width * 0.62, 0.02, 0.065, 0.022, palette.glowCyan, 1);
  channel.position.set(0, 0.02, depth * 0.36);
  channel.renderOrder = 3;
  group.add(channel);
  const socket = roundedMesh(0.34, 0.09, 0.18, 0.045, palette.dark, 2);
  socket.position.set(0, 0.025, depth / 2 + 0.035);
  group.add(socket);
  const socketLight = roundedMesh(0.18, 0.012, 0.04, 0.012, palette.glowCyan, 1);
  socketLight.position.set(0, 0.08, depth / 2 + 0.132);
  socketLight.renderOrder = 4;
  group.add(socketLight);
  return group;
}

function makeRectRail(width, depth, y, material, thickness = 0.025) {
  const rail = new THREE.Group();
  const horizontal = new RoundedBoxGeometry(width, thickness, thickness, 1, thickness * 0.35);
  const vertical = new RoundedBoxGeometry(thickness, thickness, depth, 1, thickness * 0.35);
  rail.add(makeInstancedMesh(horizontal, material, [
    { position: [0, y, -depth / 2] }, { position: [0, y, depth / 2] },
  ], false));
  rail.add(makeInstancedMesh(vertical, material, [
    { position: [-width / 2, y, 0] }, { position: [width / 2, y, 0] },
  ], false));
  return rail;
}

function makeRoundPlatform(radius, palette) {
  const group = new THREE.Group();
  const tiers = [
    { radius: radius + 0.24, height: 0.18, y: -0.34, material: palette.ceramicDark },
    { radius: radius + 0.08, height: 0.14, y: -0.18, material: palette.white },
    { radius: radius - 0.08, height: 0.08, y: -0.07, material: palette.surface },
  ];
  tiers.forEach((tier) => {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(tier.radius, tier.radius, tier.height, 40), tier.material);
    mesh.position.y = tier.y;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    group.add(mesh);
  });
  [0.58, 0.78, 0.93].forEach((ratio, index) => {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius * ratio, index === 1 ? 0.025 : 0.014, 5, 52),
      index === 1 ? palette.glowCyan : palette.ceramicDark,
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.005 + index * 0.008;
    ring.renderOrder = 3;
    group.add(ring);
  });
  const tickGeometry = new RoundedBoxGeometry(0.13, 0.026, 0.035, 1, 0.01);
  const ticks = Array.from({ length: 16 }, (_, index) => {
    const angle = (index / 16) * Math.PI * 2;
    return {
      position: [Math.cos(angle) * radius * 0.87, 0.035, Math.sin(angle) * radius * 0.87],
      rotation: [0, -angle, 0],
    };
  });
  group.add(makeInstancedMesh(tickGeometry, palette.blue, ticks, false));
  return group;
}

function makeStairs(width, depth, count, palette) {
  const group = new THREE.Group();
  const geometry = new RoundedBoxGeometry(width, 0.11, depth / count, 1, 0.025);
  const transforms = Array.from({ length: count }, (_, index) => ({
    position: [0, -0.24 + index * 0.075, -depth / 2 + (index + 0.5) * (depth / count)],
    scale: [1 - index * 0.035, 1 + index * 0.28, 1],
  }));
  group.add(makeInstancedMesh(geometry, palette.ceramic, transforms));
  return group;
}

function makeInstancedMesh(geometry, material, transforms, castShadow = true) {
  const mesh = new THREE.InstancedMesh(geometry, material, transforms.length);
  const dummy = new THREE.Object3D();
  transforms.forEach((transform, index) => {
    dummy.position.set(...transform.position);
    dummy.rotation.set(...(transform.rotation || [0, 0, 0]));
    dummy.scale.set(...(transform.scale || [1, 1, 1]));
    dummy.updateMatrix();
    mesh.setMatrixAt(index, dummy.matrix);
  });
  mesh.instanceMatrix.needsUpdate = true;
  mesh.castShadow = castShadow;
  mesh.receiveShadow = true;
  return mesh;
}

function makeIntake(palette) {
  const group = makePlatform(3.75, 2.55, palette, true);
  const panelGeometry = new RoundedBoxGeometry(0.66, 1.62, 0.16, 3, 0.075);
  const glassGeometry = new RoundedBoxGeometry(0.52, 1.42, 0.045, 2, 0.045);
  const panelTransforms = Array.from({ length: 5 }, (_, index) => ({
    position: [-0.96 + index * 0.48, 0.92 + Math.abs(index - 2) * 0.025, -0.32 + Math.abs(index - 2) * 0.08],
    rotation: [0, -0.1 + index * 0.05, 0],
  }));
  group.add(makeInstancedMesh(panelGeometry, palette.white, panelTransforms));
  group.add(makeInstancedMesh(glassGeometry, palette.glass, panelTransforms.map((item) => ({
    position: [item.position[0], item.position[1], item.position[2] + 0.102], rotation: item.rotation,
  })), false));

  const dataLineGeometry = new RoundedBoxGeometry(0.3, 0.025, 0.018, 1, 0.008);
  const dataLines = [];
  panelTransforms.forEach((panel, panelIndex) => {
    for (let row = 0; row < 4; row += 1) {
      dataLines.push({
        position: [panel.position[0], 0.58 + row * 0.24, panel.position[2] + 0.137],
        rotation: panel.rotation,
        scale: [0.68 + ((panelIndex + row) % 3) * 0.15, 1, 1],
      });
    }
  });
  group.add(makeInstancedMesh(dataLineGeometry, palette.blue, dataLines, false));

  const baseGlowGeometry = new RoundedBoxGeometry(0.48, 0.025, 0.06, 1, 0.015);
  const baseGlow = makeInstancedMesh(baseGlowGeometry, palette.glowCyan, panelTransforms.map((item) => ({
    position: [item.position[0], 0.12, item.position[2] + 0.08], rotation: item.rotation,
  })), false);
  baseGlow.renderOrder = 4;
  group.add(baseGlow);

  const sourceGeometry = new RoundedBoxGeometry(0.34, 1.28, 0.42, 3, 0.075);
  group.add(makeInstancedMesh(sourceGeometry, palette.ceramicDark, [
    { position: [-1.62, 0.72, 0.12] }, { position: [-1.25, 0.62, 0.24], scale: [0.86, 0.84, 0.9] },
  ]));
  const sourceLightGeometry = new RoundedBoxGeometry(0.08, 0.82, 0.025, 1, 0.012);
  group.add(makeInstancedMesh(sourceLightGeometry, palette.coral, [
    { position: [-1.62, 0.75, 0.345] }, { position: [-1.25, 0.64, 0.475], scale: [1, 0.78, 1] },
  ], false));

  const stairs = makeStairs(0.72, 0.68, 4, palette);
  stairs.position.set(1.28, 0, 1.55);
  stairs.rotation.y = Math.PI;
  group.add(stairs);
  group.userData.motion = { portal: baseGlow };
  return group;
}

function makeCapabilityCube(palette) {
  const group = makePlatform(3.2, 2.85, palette, true);

  const voxelGeometry = new RoundedBoxGeometry(0.48, 0.48, 0.48, 2, 0.065);
  const inactive = [];
  const active = [];
  const focus = [];
  for (let y = -1; y <= 1; y += 1) {
    for (let x = -1; x <= 1; x += 1) {
      for (let z = -1; z <= 1; z += 1) {
        const transform = { position: [x * 0.54, 1.06 + y * 0.54, 0.1 + z * 0.54] };
        const isFocus = x === 1 && y === 0 && z === 1;
        const isActive = (x === -1 && y === 0 && z === 0) || (x === 1 && y === 1 && z === 1) || (x === 0 && y === -1 && z === 1) || (x === 1 && y === 0 && z === -1);
        (isFocus ? focus : isActive ? active : inactive).push(transform);
      }
    }
  }
  group.add(makeInstancedMesh(voxelGeometry, palette.surface, inactive));
  group.add(makeInstancedMesh(voxelGeometry, palette.cyan, active));
  const focusVoxel = makeInstancedMesh(voxelGeometry, palette.violet, focus);
  group.add(focusVoxel);

  const liftGeometry = new RoundedBoxGeometry(0.065, 0.55, 0.065, 1, 0.018);
  group.add(makeInstancedMesh(liftGeometry, palette.glowCyan, [
    { position: [-0.86, 0.38, -0.65] }, { position: [0.86, 0.38, -0.65] },
    { position: [-0.86, 0.38, 0.85] }, { position: [0.86, 0.38, 0.85] },
  ], false));
  const innerRail = makeRectRail(2.22, 2.08, 0.09, palette.glowCyan, 0.032);
  innerRail.position.z = 0.1;
  group.add(innerRail);
  const outerRail = makeRectRail(2.55, 2.38, 0.055, palette.glowViolet, 0.018);
  outerRail.position.z = 0.1;
  group.add(outerRail);
  const stairs = makeStairs(0.78, 0.64, 4, palette);
  stairs.position.set(1.05, 0, 1.62);
  stairs.rotation.y = Math.PI;
  group.add(stairs);
  group.userData.motion = {};
  return group;
}

function makeGraph(palette) {
  const group = makeRoundPlatform(2.05, palette);
  const lattice = [];
  [-1, 0, 1].forEach((x) => {
    [-1, 0, 1].forEach((y) => {
      [-1, 0, 1].forEach((z) => {
        if ([x, y, z].filter((value) => Math.abs(value) === 1).length >= 2) lattice.push({ x, y, z });
      });
    });
  });
  const nodes = lattice.map(({ x, y, z }) => new THREE.Vector3(x * 0.94, 1.48 + y * 0.68, 0.08 + z * 0.74));
  const edgePositions = [];
  lattice.forEach((node, index) => {
    lattice.slice(index + 1).forEach((other, offset) => {
      const distance = Math.abs(node.x - other.x) + Math.abs(node.y - other.y) + Math.abs(node.z - other.z);
      if (distance === 1) {
        const start = nodes[index];
        const end = nodes[index + offset + 1];
        edgePositions.push(start.x, start.y, start.z, end.x, end.y, end.z);
      }
    });
    if (index % 4 === 0) {
      const point = nodes[index];
      edgePositions.push(point.x, point.y, point.z, 0, 1.48, 0.08);
    }
  });
  const edgeGeometry = new THREE.BufferGeometry();
  edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(edgePositions, 3));
  const edges = new THREE.LineSegments(edgeGeometry, new THREE.LineBasicMaterial({ color: 0x78aef2, transparent: true, opacity: 0.58 }));
  group.add(edges);

  const nodeGeometry = new THREE.SphereGeometry(0.08, 10, 7);
  const regularNodes = [];
  const activeNodes = [];
  nodes.forEach((node, index) => (index % 5 === 0 ? activeNodes : regularNodes).push({
    position: node.toArray(), scale: index % 3 === 0 ? [1.25, 1.25, 1.25] : [1, 1, 1],
  }));
  group.add(makeInstancedMesh(nodeGeometry, palette.blue, regularNodes, false));
  group.add(makeInstancedMesh(nodeGeometry, palette.cyan, activeNodes, false));

  const pedestal = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 0.94, 0.34, 32), palette.ceramic);
  pedestal.position.set(0, 0.16, 0.08);
  pedestal.castShadow = true;
  group.add(pedestal);
  const pedestalRing = new THREE.Mesh(new THREE.TorusGeometry(0.72, 0.04, 6, 42), palette.glowViolet);
  pedestalRing.rotation.x = Math.PI / 2;
  pedestalRing.position.set(0, 0.36, 0.08);
  group.add(pedestalRing);

  const rotatingCore = new THREE.Group();
  [1.04, 0.76].forEach((size, index) => {
    const shell = roundedMesh(size, size, size, 0.12, palette.glass, 3);
    shell.rotation.set(index * 0.08, 0.22 + index * 0.4, index * 0.1);
    shell.renderOrder = 3 + index;
    rotatingCore.add(shell);
  });
  const core = roundedMesh(0.42, 0.72, 0.42, 0.08, palette.violet, 3);
  core.rotation.set(0.08, 0.42, 0.04);
  core.castShadow = true;
  rotatingCore.add(core);
  rotatingCore.position.set(0, 1.33, 0.08);
  group.add(rotatingCore);

  const pylonGeometry = new THREE.CylinderGeometry(0.11, 0.16, 0.82, 8);
  const pylonTransforms = [[-1.48, 0.48, -0.85], [1.48, 0.48, -0.85], [-1.48, 0.48, 0.98], [1.48, 0.48, 0.98]]
    .map((position) => ({ position }));
  group.add(makeInstancedMesh(pylonGeometry, palette.ceramicDark, pylonTransforms));
  const capGeometry = new THREE.SphereGeometry(0.1, 10, 7);
  group.add(makeInstancedMesh(capGeometry, palette.glowCyan, pylonTransforms.map((item) => ({
    position: [item.position[0], 0.92, item.position[2]],
  })), false));

  const stairs = makeStairs(0.86, 0.7, 4, palette);
  stairs.position.set(0.95, 0, 2.16);
  stairs.rotation.y = Math.PI;
  group.add(stairs);
  group.userData.motion = { core: rotatingCore };
  return group;
}

function makeLimb(start, end, radius, material) {
  const direction = end.clone().sub(start);
  const limb = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.88, radius, 1, 10), material);
  limb.position.copy(start).add(end).multiplyScalar(0.5);
  limb.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.clone().normalize());
  limb.scale.y = direction.length();
  limb.castShadow = true;
  return limb;
}

function makeCandidate(palette) {
  const candidate = new THREE.Group();
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.19, 18, 12), palette.white);
  head.position.y = 1.62;
  head.castShadow = true;
  candidate.add(head);

  const hair = new THREE.Mesh(
    new THREE.SphereGeometry(0.194, 18, 7, 0, Math.PI * 2, 0, Math.PI * 0.43),
    palette.dark,
  );
  hair.position.y = 1.625;
  hair.castShadow = true;
  candidate.add(hair);

  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.068, 0.078, 0.14, 10), palette.ceramic);
  neck.position.y = 1.4;
  neck.castShadow = true;
  candidate.add(neck);

  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.18, 0.56, 10), palette.white);
  torso.position.y = 1.12;
  torso.castShadow = true;
  candidate.add(torso);
  const chestMark = roundedMesh(0.13, 0.28, 0.026, 0.035, palette.blue, 2);
  chestMark.position.set(0, 1.12, 0.232);
  chestMark.castShadow = false;
  candidate.add(chestMark);

  const hips = roundedMesh(0.39, 0.15, 0.25, 0.07, palette.dark, 2);
  hips.position.y = 0.8;
  hips.castShadow = true;
  candidate.add(hips);

  [-1, 1].forEach((side) => {
    const shoulder = new THREE.Vector3(side * 0.24, 1.31, 0);
    const elbow = new THREE.Vector3(side * 0.34, 1.04, 0.015);
    const wrist = new THREE.Vector3(side * 0.3, 0.8, 0.045);
    candidate.add(makeLimb(shoulder, elbow, 0.072, palette.ceramic));
    candidate.add(makeLimb(elbow, wrist, 0.064, palette.white));
    const elbowJoint = new THREE.Mesh(new THREE.SphereGeometry(0.071, 10, 7), palette.ceramic);
    elbowJoint.position.copy(elbow);
    elbowJoint.castShadow = true;
    candidate.add(elbowJoint);
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.068, 10, 7), palette.white);
    hand.position.copy(wrist);
    hand.castShadow = true;
    candidate.add(hand);

    const hip = new THREE.Vector3(side * 0.12, 0.76, 0);
    const knee = new THREE.Vector3(side * 0.14, 0.48, 0.01);
    const ankle = new THREE.Vector3(side * 0.15, 0.23, 0.035);
    candidate.add(makeLimb(hip, knee, 0.082, palette.dark));
    candidate.add(makeLimb(knee, ankle, 0.073, palette.ceramicDark));
    const kneeJoint = new THREE.Mesh(new THREE.SphereGeometry(0.076, 10, 7), palette.dark);
    kneeJoint.position.copy(knee);
    kneeJoint.castShadow = true;
    candidate.add(kneeJoint);
    const foot = roundedMesh(0.2, 0.1, 0.34, 0.045, palette.dark, 2);
    foot.position.set(side * 0.15, 0.14, 0.095);
    foot.castShadow = true;
    candidate.add(foot);
  });
  return candidate;
}

function makeProfileCard(palette) {
  const card = new THREE.Group();
  const housing = roundedMesh(1.22, 1.58, 0.14, 0.12, palette.white, 3);
  housing.castShadow = true;
  card.add(housing);
  const face = roundedMesh(1.08, 1.42, 0.035, 0.09, palette.glass, 3);
  face.position.z = 0.09;
  face.renderOrder = 3;
  card.add(face);
  const avatarHead = new THREE.Mesh(new THREE.CircleGeometry(0.13, 24), palette.blue);
  avatarHead.position.set(-0.3, 0.36, 0.12);
  avatarHead.renderOrder = 4;
  card.add(avatarHead);
  const avatarBody = roundedMesh(0.36, 0.24, 0.02, 0.09, palette.blue, 2);
  avatarBody.position.set(-0.3, 0.12, 0.12);
  avatarBody.renderOrder = 4;
  card.add(avatarBody);
  const lineGeometry = new RoundedBoxGeometry(0.48, 0.032, 0.018, 1, 0.01);
  card.add(makeInstancedMesh(lineGeometry, palette.ceramicDark, [
    { position: [0.2, 0.42, 0.12] }, { position: [0.2, 0.25, 0.12], scale: [0.8, 1, 1] },
    { position: [0, -0.15, 0.12], scale: [1.45, 1, 1] }, { position: [0, -0.34, 0.12], scale: [1.2, 1, 1] },
    { position: [0, -0.53, 0.12], scale: [0.95, 1, 1] },
  ], false));
  const sideLight = roundedMesh(0.035, 1.18, 0.025, 0.012, palette.glowCyan, 1);
  sideLight.position.set(-0.5, 0, 0.13);
  sideLight.renderOrder = 4;
  card.add(sideLight);
  return card;
}

function makeOutcomeRack(palette) {
  const rack = makePlatform(2.08, 1.72, palette);
  const backGeometry = new RoundedBoxGeometry(0.5, 1.48, 0.26, 3, 0.07);
  const backs = [-0.56, 0, 0.56].map((x, index) => ({
    position: [x, 0.78 + index * 0.05, -0.22 - Math.abs(index - 1) * 0.04],
  }));
  rack.add(makeInstancedMesh(backGeometry, palette.white, backs));
  const backFaceGeometry = new RoundedBoxGeometry(0.39, 1.3, 0.025, 2, 0.045);
  rack.add(makeInstancedMesh(backFaceGeometry, palette.glass, backs.map((item) => ({
    position: [item.position[0], item.position[1], item.position[2] + 0.15],
  })), false));
  const slotGeometry = new RoundedBoxGeometry(0.32, 0.19, 0.035, 1, 0.025);
  const slots = [];
  [-0.56, 0, 0.56].forEach((x) => {
    for (let row = 0; row < 4; row += 1) slots.push({ position: [x, 0.35 + row * 0.29, -0.05] });
  });
  rack.add(makeInstancedMesh(slotGeometry, palette.blue, slots, false));
  const rackGlow = roundedMesh(1.58, 0.025, 0.055, 0.016, palette.glowCyan, 1);
  rackGlow.position.set(0, 0.08, 0.54);
  rackGlow.renderOrder = 4;
  rack.add(rackGlow);
  return rack;
}

function makeMatch(palette) {
  const group = makeRoundPlatform(1.78, palette);
  const candidate = makeCandidate(palette);
  candidate.scale.setScalar(0.72);
  candidate.position.set(-0.58, 0.02, 0.28);
  group.add(candidate);
  const profile = makeProfileCard(palette);
  profile.position.set(0.48, 1.12, -0.12);
  profile.rotation.y = -0.08;
  group.add(profile);

  const bridgeCurve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(-0.42, 1.0, 0.22),
    new THREE.Vector3(0, 1.42, 0.46),
    new THREE.Vector3(0.25, 1.14, 0.08),
  );
  const bridge = new THREE.Mesh(new THREE.TubeGeometry(bridgeCurve, 30, 0.028, 6, false), palette.glowCyan);
  bridge.renderOrder = 4;
  group.add(bridge);

  const stairs = makeStairs(0.82, 0.72, 4, palette);
  stairs.position.set(-0.8, 0, 1.82);
  stairs.rotation.y = Math.PI;
  group.add(stairs);
  const tokenGeometry = new RoundedBoxGeometry(0.28, 0.08, 0.18, 1, 0.03);
  group.add(makeInstancedMesh(tokenGeometry, palette.coral, [
    { position: [1.05, 0.18, 1.02], rotation: [0, -0.16, 0] },
    { position: [1.35, 0.24, 0.83], rotation: [0, -0.12, 0] },
  ], false));

  const outcomeRack = makeOutcomeRack(palette);
  outcomeRack.scale.setScalar(0.82);
  outcomeRack.position.set(2.72, 0, -0.32);
  group.add(outcomeRack);
  const outcomeCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(1.15, 0.16, 0.26), new THREE.Vector3(1.72, 0.15, 0.55), new THREE.Vector3(2.2, 0.12, 0.18),
  ], false, "catmullrom", 0.2);
  const outcomeLine = new THREE.Mesh(new THREE.TubeGeometry(outcomeCurve, 26, 0.038, 6, false), palette.glowCyan);
  outcomeLine.renderOrder = 4;
  group.add(outcomeLine);
  group.userData.motion = { portal: outcomeLine };
  return group;
}

function makeRoute(scene) {
  const routeCurve = new THREE.CatmullRomCurve3(ROUTE_POINTS, false, "catmullrom", 0.22);
  const routeSamples = routeCurve.getPoints(220);
  [-0.095, 0.095].forEach((offset) => {
    const railCurve = new THREE.CatmullRomCurve3(
      ROUTE_POINTS.map((point) => new THREE.Vector3(point.x, point.y - 0.025, point.z + offset)),
      false,
      "catmullrom",
      0.22,
    );
    scene.add(new THREE.Mesh(
      new THREE.TubeGeometry(railCurve, 110, 0.026, 5, false),
      new THREE.MeshStandardMaterial({ color: 0xa7bfd1, roughness: 0.54, metalness: 0.06, transparent: true, opacity: 0.78 }),
    ));
  });
  const routeSegmentStops = [0, 1 / 8, 3 / 8, 5 / 8, 7 / 8, 1];
  routeSegmentStops.slice(0, -1).forEach((start, index) => {
    const end = routeSegmentStops[index + 1];
    const segmentCurve = new THREE.Curve();
    segmentCurve.getPoint = (segmentProgress, target = new THREE.Vector3()) => (
      routeCurve.getPoint(start + (end - start) * segmentProgress, target)
    );
    const material = new THREE.MeshBasicMaterial({ color: ROUTE_COLORS[index], transparent: true, opacity: 0.42 });
    scene.add(new THREE.Mesh(new THREE.TubeGeometry(segmentCurve, 38, 0.05, 6, false), material));
  });

  STATION_ANCHORS.forEach((anchor, index) => {
    const start = ROUTE_POINTS[index * 2 + 1];
    const end = new THREE.Vector3(anchor.x, 0.2, anchor.z + STATION_DEPTHS[index] / 2 + 0.04);
    const control = start.clone().lerp(end, 0.5);
    control.y += 0.2;
    const branch = new THREE.QuadraticBezierCurve3(start, control, end);
    const branchMesh = new THREE.Mesh(
      new THREE.TubeGeometry(branch, 22, 0.035, 5, false),
      new THREE.MeshBasicMaterial({ color: ROUTE_COLORS[index + 1], transparent: true, opacity: 0.72 }),
    );
    scene.add(branchMesh);
    const junction = new THREE.Mesh(
      new THREE.CylinderGeometry(0.105, 0.105, 0.055, 18),
      new THREE.MeshStandardMaterial({ color: ROUTE_COLORS[index + 1], emissive: ROUTE_COLORS[index + 1], emissiveIntensity: 0.24, roughness: 0.35 }),
    );
    junction.position.copy(start);
    junction.position.y -= 0.015;
    scene.add(junction);
  });

  const colors = [];
  routeSamples.forEach((_, index) => {
    const progress = index / (routeSamples.length - 1);
    const colorIndex = Math.min(ROUTE_COLORS.length - 1, Math.floor(progress * ROUTE_COLORS.length));
    const color = new THREE.Color(ROUTE_COLORS[colorIndex]);
    colors.push(color.r, color.g, color.b);
  });
  const activeGeometry = new THREE.BufferGeometry().setFromPoints(routeSamples);
  activeGeometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  activeGeometry.setDrawRange(0, 6);
  const activeRoute = new THREE.Line(activeGeometry, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 1 }));
  activeRoute.renderOrder = 5;
  scene.add(activeRoute);

  const particleCount = 42;
  const particlePositions = new Float32Array(particleCount * 3);
  const particleGeometry = new THREE.BufferGeometry();
  const positionAttribute = new THREE.BufferAttribute(particlePositions, 3);
  positionAttribute.setUsage(THREE.DynamicDrawUsage);
  particleGeometry.setAttribute("position", positionAttribute);
  const particles = new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({ color: 0xc9ffff, size: 0.12, sizeAttenuation: true, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false }),
  );
  particles.renderOrder = 6;
  scene.add(particles);
  return { routeCurve, routeSamples, activeRoute, particles, particlePositions, positionAttribute };
}

function makeIslandShape(widthAdjustment = 0) {
  const centerCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-11.8, 0, -0.55),
    ...STATION_ANCHORS.map((anchor) => new THREE.Vector3(anchor.x, 0, anchor.z)),
    new THREE.Vector3(11.8, 0, -0.25),
  ], false, "catmullrom", 0.2);
  const left = [];
  const right = [];
  const point = new THREE.Vector3();
  for (let index = 0; index <= 72; index += 1) {
    const progress = index / 72;
    centerCurve.getPoint(progress, point);
    const width = 1.68 + widthAdjustment + STATION_ANCHORS.reduce((sum, anchor) => {
      const delta = point.x - anchor.x;
      return sum + Math.exp(-(delta * delta) / 2.8) * 0.55;
    }, 0);
    left.push(new THREE.Vector2(point.x, point.z + width));
    right.push(new THREE.Vector2(point.x, point.z - width));
  }
  const shape = new THREE.Shape();
  shape.moveTo(left[0].x, left[0].y);
  left.slice(1).forEach((item) => shape.lineTo(item.x, item.y));
  right.reverse().forEach((item) => shape.lineTo(item.x, item.y));
  shape.closePath();
  return shape;
}

function makeStoryIsland(scene, palette) {
  const baseGeometry = new THREE.ExtrudeGeometry(makeIslandShape(0.16), {
    depth: 0.2,
    bevelEnabled: true,
    bevelSegments: 2,
    bevelSize: 0.12,
    bevelThickness: 0.055,
    curveSegments: 2,
  });
  baseGeometry.rotateX(Math.PI / 2);
  const base = new THREE.Mesh(baseGeometry, palette.ceramicDark);
  base.position.y = -0.24;
  base.receiveShadow = true;
  scene.add(base);

  const topGeometry = new THREE.ShapeGeometry(makeIslandShape(-0.06), 12);
  topGeometry.rotateX(Math.PI / 2);
  const top = new THREE.Mesh(topGeometry, palette.surface);
  top.position.y = -0.205;
  top.receiveShadow = true;
  scene.add(top);
}

function makeLandscapeDetails(scene, palette) {
  const treePositions = [
    [-6.1, -1.25], [-5.55, 1.25], [-0.15, -1.35], [0.45, 1.48],
    [5.7, -1.42], [6.05, 1.32], [10.55, -1.08], [11.05, 1.05],
  ];
  const trunkGeometry = new THREE.CylinderGeometry(0.035, 0.055, 0.32, 7);
  scene.add(makeInstancedMesh(trunkGeometry, palette.dark, treePositions.map(([x, z]) => ({
    position: [x, -0.02, z],
  })), false));
  const crownGeometry = new THREE.ConeGeometry(0.19, 0.46, 7);
  const crowns = [];
  treePositions.forEach(([x, z], index) => {
    crowns.push({ position: [x, 0.2, z], rotation: [0, index * 0.35, 0] });
    crowns.push({ position: [x, 0.41, z], rotation: [0, index * 0.35 + 0.2, 0], scale: [0.72, 0.72, 0.72] });
  });
  scene.add(makeInstancedMesh(crownGeometry, palette.ceramicDark, crowns, false));
}

function makeGroundDetails(scene, palette) {
  const groundMaterial = new THREE.MeshBasicMaterial({ color: 0xf7fbfe, toneMapped: false, fog: false });
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(58, 34), groundMaterial);
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.47;
  scene.add(ground);
  const shadowGround = new THREE.Mesh(new THREE.PlaneGeometry(58, 34), new THREE.ShadowMaterial({ color: 0x7895aa, opacity: 0.1 }));
  shadowGround.rotation.x = -Math.PI / 2;
  shadowGround.position.y = -0.465;
  shadowGround.receiveShadow = true;
  scene.add(shadowGround);
  makeStoryIsland(scene, palette);
  makeLandscapeDetails(scene, palette);

  const dotCount = 138;
  const positions = new Float32Array(dotCount * 3);
  for (let index = 0; index < dotCount; index += 1) {
    positions[index * 3] = -12.5 + (index * 3.91) % 25;
    positions[index * 3 + 1] = -0.345;
    positions[index * 3 + 2] = -5.7 + (index * 1.73) % 11.4;
  }
  const dotGeometry = new THREE.BufferGeometry();
  dotGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  scene.add(new THREE.Points(dotGeometry, new THREE.PointsMaterial({ color: 0x7bdbe2, size: 0.03, transparent: true, opacity: 0.3, depthWrite: false })));
}

function disposeScene(scene, extraTextures) {
  const geometries = new Set();
  const materials = new Set();
  const textures = new Set(extraTextures);
  scene.traverse((object) => {
    if (object.geometry) geometries.add(object.geometry);
    const objectMaterials = Array.isArray(object.material) ? object.material : object.material ? [object.material] : [];
    objectMaterials.forEach((material) => {
      materials.add(material);
      if (material.map) textures.add(material.map);
    });
  });
  geometries.forEach((geometry) => geometry.dispose());
  materials.forEach((material) => material.dispose());
  textures.forEach((texture) => texture.dispose());
}

export default function HomeStoryScene({ progress = 0, reducedMotion = false, active = true, stage = 0, labels = [], overlayOpacity = 1, reveal = 1 }) {
  const mountRef = useRef(null);
  const labelRefs = useRef([]);
  const progressRef = useRef(progress);
  const activeRef = useRef(active);
  const stageRef = useRef(stage);
  const revealRef = useRef(reveal);
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
    stageRef.current = stage;
    controllerRef.current?.wake();
  }, [stage]);

  useEffect(() => {
    revealRef.current = reveal;
    controllerRef.current?.wake();
  }, [reveal]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf7fbfe);
    scene.fog = new THREE.Fog(0xf7fbfe, 39, 68);
    const camera = new THREE.PerspectiveCamera(33, 1, 0.1, 80);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.06;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    mount.appendChild(renderer.domElement);

    let wake = () => {};
    const surfaceTexture = createSurfaceTexture(renderer, () => wake());
    const palette = createPalette(surfaceTexture);
    scene.add(new THREE.HemisphereLight(0xffffff, 0xd7e8f4, 1.52));
    const keyLight = new THREE.DirectionalLight(0xfffcf6, 2.05);
    keyLight.position.set(-8, 13, 10);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    keyLight.shadow.camera.near = 1;
    keyLight.shadow.camera.far = 42;
    keyLight.shadow.camera.left = -18;
    keyLight.shadow.camera.right = 18;
    keyLight.shadow.camera.top = 12;
    keyLight.shadow.camera.bottom = -12;
    keyLight.shadow.bias = -0.0002;
    keyLight.shadow.normalBias = 0.025;
    keyLight.shadow.radius = 2.2;
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xb7e8f5, 0.72);
    fillLight.position.set(8, 5, 4);
    scene.add(fillLight);
    const rimLight = new THREE.PointLight(0x77dbe5, 0.68, 20, 2);
    rimLight.position.set(2.5, 4.5, 2.5);
    scene.add(rimLight);

    makeGroundDetails(scene, palette);
    const stations = [
      makeIntake(palette),
      makeCapabilityCube(palette),
      makeGraph(palette),
      makeMatch(palette),
    ];
    stations.forEach((station, index) => {
      station.position.copy(STATION_ANCHORS[index]);
      station.scale.setScalar(1.06);
      station.userData.baseScale = 1.06;
      scene.add(station);
    });
    const labelAnchors = stations.map((station, stationIndex) => LABEL_ANCHOR_POINTS[stationIndex].map((position) => {
      const anchor = new THREE.Object3D();
      anchor.position.set(...position);
      station.add(anchor);
      return anchor;
    }));
    const route = makeRoute(scene);
    const cameraCurve = new THREE.CatmullRomCurve3(CAMERA_POINTS, false, "catmullrom", 0.24);
    const focusCurve = new THREE.CatmullRomCurve3(FOCUS_POINTS, false, "catmullrom", 0.24);
    const desiredPosition = new THREE.Vector3();
    const desiredTarget = new THREE.Vector3();
    const currentTarget = FOCUS_POINTS[0].clone();
    const routePoint = new THREE.Vector3();
    const labelWorldPoint = new THREE.Vector3();
    const labelScreenPoint = new THREE.Vector3();

    let inViewport = true;
    let pageVisible = document.visibilityState === "visible";
    let frameId = 0;
    let running = false;
    let viewportWidth = 1;
    let viewportHeight = 1;
    const startedAt = performance.now();

    const resize = () => {
      const { width, height } = mount.getBoundingClientRect();
      if (!width || !height) return;
      viewportWidth = width;
      viewportHeight = height;
      const isMobile = width <= 720;
      camera.aspect = width / height;
      camera.fov = isMobile ? 42 : width <= 1100 ? 37 : 33;
      camera.updateProjectionMatrix();
      keyLight.shadow.mapSize.set(isMobile ? 512 : 1024, isMobile ? 512 : 1024);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, isMobile || reducedMotion ? 1 : 1.5));
      renderer.setSize(width, height, false);
      wake();
    };

    const renderFrame = () => {
      if (!activeRef.current || !inViewport || !pageVisible) {
        running = false;
        return;
      }
      const elapsed = reducedMotion ? 0 : (performance.now() - startedAt) / 1000;
      const storyProgress = clamp01(progressRef.current);
      const entrance = reducedMotion ? 1 : smoothstep(revealRef.current);
      cameraCurve.getPoint(storyProgress, desiredPosition);
      focusCurve.getPoint(storyProgress, desiredTarget);
      desiredPosition.y += (1 - entrance) * 1.35;
      desiredPosition.z += (1 - entrance) * 2.4;
      if (mount.clientWidth <= 720) {
        desiredPosition.y += 1.45;
        desiredPosition.z += 3.2;
        desiredTarget.y += 0.25;
      }
      if (reducedMotion) {
        camera.position.copy(desiredPosition);
        currentTarget.copy(desiredTarget);
      } else {
        camera.position.lerp(desiredPosition, 0.075);
        currentTarget.lerp(desiredTarget, 0.09);
      }
      camera.lookAt(currentTarget);

      stations.forEach((station, index) => {
        const focus = smoothstep(1 - Math.abs(storyProgress - STAGE_PROGRESS[index]) * 3.1);
        const scale = station.userData.baseScale * (0.66 + focus * 0.36) * (0.78 + entrance * 0.22);
        station.scale.setScalar(scale);
        station.position.y = reducedMotion ? 0 : Math.sin(elapsed * 0.58 + index * 1.3) * (0.018 + focus * 0.02) - (1 - entrance) * 0.72;
        station.rotation.y = reducedMotion ? 0 : Math.sin(elapsed * 0.22 + index) * 0.018;
        const motion = station.userData.motion;
        if (motion?.core) {
          motion.core.rotation.y += reducedMotion ? 0 : 0.0035 * (0.35 + focus);
        }
        if (motion?.orbit) {
          motion.orbit.rotation.z += reducedMotion ? 0 : 0.0028 * (0.4 + focus);
          if (motion.orbit.material?.opacity !== undefined) motion.orbit.material.opacity = 0.38 + focus * 0.34;
        }
        if (motion?.portal) {
          motion.portal.scale.setScalar(0.98 + focus * 0.05 + Math.sin(elapsed * 1.4) * 0.012);
        }
      });

      const visibleRoute = 0.08 + storyProgress * 0.92;
      route.activeRoute.geometry.setDrawRange(0, Math.max(6, Math.ceil(route.routeSamples.length * visibleRoute)));
      for (let index = 0; index < route.particlePositions.length / 3; index += 1) {
        const phase = (index / 42 + elapsed * 0.045) % 1;
        const offset = index * 3;
        if (phase <= visibleRoute) {
          route.routeCurve.getPointAt(phase, routePoint);
          route.particlePositions[offset] = routePoint.x;
          route.particlePositions[offset + 1] = routePoint.y + 0.08 + Math.sin(elapsed * 1.9 + index) * 0.02;
          route.particlePositions[offset + 2] = routePoint.z;
        } else {
          route.particlePositions[offset] = 0;
          route.particlePositions[offset + 1] = -20;
          route.particlePositions[offset + 2] = 0;
        }
      }
      route.positionAttribute.needsUpdate = true;
      scene.updateMatrixWorld(true);
      const activeStage = Math.min(labelAnchors.length - 1, Math.max(0, stageRef.current));
      labelAnchors[activeStage].forEach((anchor, index) => {
        const element = labelRefs.current[index];
        if (!element) return;
        anchor.getWorldPosition(labelWorldPoint);
        labelScreenPoint.copy(labelWorldPoint).project(camera);
        const isVisible = labelScreenPoint.z > -1 && labelScreenPoint.z < 1
          && labelScreenPoint.x > -1.08 && labelScreenPoint.x < 1.08
          && labelScreenPoint.y > -1.08 && labelScreenPoint.y < 1.08;
        const x = (labelScreenPoint.x * 0.5 + 0.5) * viewportWidth;
        const y = (-labelScreenPoint.y * 0.5 + 0.5) * viewportHeight;
        element.style.opacity = isVisible ? "1" : "0";
        element.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, calc(-100% - 14px))`;
      });
      renderer.render(scene, camera);
      if (reducedMotion) {
        running = false;
        return;
      }
      frameId = requestAnimationFrame(renderFrame);
    };

    wake = () => {
      if (running || !activeRef.current || !inViewport || !pageVisible) return;
      running = true;
      frameId = requestAnimationFrame(renderFrame);
    };
    controllerRef.current = { wake };
    camera.position.copy(CAMERA_POINTS[0]);
    currentTarget.copy(FOCUS_POINTS[0]);
    camera.lookAt(currentTarget);

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(mount);
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      inViewport = entry.isIntersecting;
      if (inViewport) wake();
    }, { rootMargin: "120px" });
    intersectionObserver.observe(mount);
    const onVisibilityChange = () => {
      pageVisible = document.visibilityState === "visible";
      if (pageVisible) wake();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    resize();
    wake();

    return () => {
      cancelAnimationFrame(frameId);
      running = false;
      controllerRef.current = null;
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibilityChange);
      disposeScene(scene, [surfaceTexture]);
      renderer.dispose();
      mount.replaceChildren();
    };
  }, [reducedMotion]);

  return <>
    <div className="home-story-canvas" ref={mountRef} style={{ opacity: Math.min(1, overlayOpacity * 4) }} aria-hidden="true" />
    <div className={`cinematic-model-tags is-world-bound is-stage-${stage}`} style={{ opacity: overlayOpacity }} aria-hidden="true">
      {labels.map((label, index) => <span key={label} ref={(element) => { labelRefs.current[index] = element; }}><i />{label}</span>)}
    </div>
  </>;
}
