import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { ChevronLeft, ChevronRight, Maximize2, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { buildJobEvolutionProfile } from "./jobEvolutionProfiles";

const DOMAIN_META = {
  人工智能: { color: 0x54c7ec, css: "#54c7ec" },
  大数据: { color: 0x79d991, css: "#79d991" },
  智能系统: { color: 0xff8a7a, css: "#ff8a7a" },
  物联网: { color: 0xd8a4ff, css: "#d8a4ff" },
};
const WORMHOLE_BLUE = 0x4f8cff;
const WORMHOLE_LIGHT_BLUE = 0x8bb8ff;
const WORMHOLE_MUTED_BLUE = 0x42658f;
const OVERVIEW_DENSE_PERIOD_NODE_LIMIT = 900;
const ECLIPTIC_OUTER_RADIUS = 49;
const ECLIPTIC_FAMILY_LIMIT = 44.5;
const GALACTIC_ARM_INNER_RADIUS = 50.5;
const GALACTIC_ARM_OUTER_RADIUS = 70;
const RING_SCALE = { inner: 1.18, middle: 0.88, outer: 0.62 };
const EVOLUTION_META = {
  emerging: { color: 0x55d993, label: "新形成" },
  declining: { color: 0xf0b45f, label: "减弱风险" },
  exited: { color: 0xef6f68, label: "已退出后续切片" },
  stable: { color: null, label: "结构稳定" },
};
const RELATION_LENS_TYPES = {
  job_skill: new Set(["requires_skill", "job_requires_skill", "family_member", "evolution"]),
  similarity: new Set(["job_similarity", "possible_fusion", "evolution"]),
  combination: new Set(["shared_skill", "skill_cooccurrence", "evolution"]),
  mobility: new Set(["talent_mobility", "evolution"]),
  integrated: new Set(["requires_skill", "job_requires_skill", "job_similarity", "shared_skill", "possible_fusion", "skill_cooccurrence", "talent_mobility", "evolution"]),
};

const RELATION_LABELS = {
  requires_skill: "核心技能",
  job_requires_skill: "核心技能",
  job_similarity: "岗位相似",
  shared_skill: "共享技能",
  skill_cooccurrence: "技能组合",
  talent_mobility: "跨岗迁移",
  possible_fusion: "可能融合",
  evolution: "时间演化",
  family_member: "岗位归属",
};

function glowTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 96;
  const context = canvas.getContext("2d");
  const gradient = context.createRadialGradient(48, 48, 0, 48, 48, 48);
  gradient.addColorStop(0, "rgba(255,255,255,1)");
  gradient.addColorStop(0.16, "rgba(255,255,255,.78)");
  gradient.addColorStop(0.48, "rgba(255,255,255,.14)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 96, 96);
  return new THREE.CanvasTexture(canvas);
}

function labelSprite(text, color = "#dbe9eb", scale = 1) {
  const canvas = document.createElement("canvas");
  canvas.width = 768;
  canvas.height = 112;
  const context = canvas.getContext("2d");
  context.font = "600 34px 'Microsoft YaHei', sans-serif";
  context.textAlign = "center";
  context.shadowColor = "rgba(0,0,0,.95)";
  context.shadowBlur = 9;
  context.fillStyle = color;
  context.fillText(text.length > 18 ? `${text.slice(0, 18)}…` : text, 384, 68);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false, opacity: 0.88 }));
  sprite.scale.set(18 * scale, 2.65 * scale, 1);
  sprite.userData.labelTexture = texture;
  return sprite;
}

function edgeLabelSprite(text, color = "#8bb8ff") {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 112;
  const context = canvas.getContext("2d");
  context.fillStyle = "rgba(5, 13, 27, .9)";
  context.strokeStyle = color;
  context.lineWidth = 3;
  context.beginPath();
  context.roundRect(10, 10, 620, 92, 30);
  context.fill();
  context.stroke();
  context.font = "600 28px 'Microsoft YaHei', sans-serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillStyle = "#f7fbff";
  context.fillText(text.length > 22 ? `${text.slice(0, 22)}…` : text, 320, 57);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false, opacity: 0.96 });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(8.8, 1.58, 1);
  sprite.renderOrder = 20;
  sprite.userData.labelTexture = texture;
  return sprite;
}

function seeded(index) {
  const value = Math.sin(index * 9283.73 + 91.17) * 43758.5453;
  return value - Math.floor(value);
}

function nodeText(node) {
  return `${node.title || ""} ${node.company || ""} ${node.family || ""} ${(node.skills || []).join(" ")}`.toLowerCase();
}

function hashUnit(value) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967295;
}

function buildDensityPlanes(nodes, layers, compact) {
  const clearNodeLimit = compact ? 100 : 140;
  const subplaneSpacing = compact ? 4.5 : 5.5;
  const periodSpacing = compact ? 24 : 34;
  const nodesByPeriod = new Map();
  nodes.forEach((node) => {
    if (!node.period) return;
    if (!nodesByPeriod.has(node.period)) nodesByPeriod.set(node.period, []);
    nodesByPeriod.get(node.period).push(node);
  });
  const planes = [];
  const periodMap = new Map();
  const nodePlaneMap = new Map();
  let cursorZ = 0;
  layers.forEach((layer) => {
    const periodNodes = nodesByPeriod.get(layer.id) || [];
    const planeCount = Math.max(1, Math.ceil(periodNodes.length / clearNodeLimit));
    const periodPlanes = Array.from({ length: planeCount }, (_, index) => ({
      id: `${layer.id}:density:${index}`,
      period: layer.id,
      label: planeCount > 1 ? `${layer.label} · 职业快轨面 ${index + 1}/${planeCount}` : layer.label,
      z: cursorZ - index * subplaneSpacing,
      index,
      planeCount,
      nodeCount: 0,
      isDensityPlane: planeCount > 1,
    }));
    [...periodNodes]
      .sort((left, right) => `${left.nodeType}:${left.id}`.localeCompare(`${right.nodeType}:${right.id}`))
      .forEach((node, nodeIndex) => {
      const planeIndex = planeCount === 1 ? 0 : nodeIndex % planeCount;
      nodePlaneMap.set(node.id, planeIndex);
      periodPlanes[planeIndex].nodeCount += 1;
    });
    const centerZ = periodPlanes.reduce((sum, plane) => sum + plane.z, 0) / planeCount;
    const meta = { ...layer, planeCount, planes: periodPlanes, centerZ, nodeCount: periodNodes.length, clearNodeLimit };
    periodMap.set(layer.id, meta);
    planes.push(...periodPlanes);
    cursorZ = periodPlanes.at(-1).z - periodSpacing;
  });
  return { planes, periodMap, nodePlaneMap, clearNodeLimit };
}

function relationColor(link, dimmed = false) {
  if (dimmed) return new THREE.Color(0x182336);
  if (link.changeState === "added" || link.changeState === "strengthened") return new THREE.Color(0x55d993);
  if (link.changeState === "weakened") return new THREE.Color(0xf0b45f);
  return new THREE.Color(link.type === "evolution" ? WORMHOLE_BLUE : ["requires_skill", "job_requires_skill"].includes(link.type) ? 0xf1c96c : link.type === "job_similarity" ? 0x54c7ec : link.type === "shared_skill" ? 0x79d991 : link.type === "possible_fusion" ? 0xe090ff : link.type === "talent_mobility" ? 0xb99aff : link.type === "skill_cooccurrence" ? 0x79d991 : link.type === "auxiliary_signal" ? 0xf4c76f : WORMHOLE_MUTED_BLUE);
}

function buildScenePositions(nodes, clusterMode, densityLayout) {
  const nodeZ = (node) => {
    const periodMeta = densityLayout.periodMap.get(node.period);
    if (!periodMeta) return node.z;
    const planeIndex = densityLayout.nodePlaneMap.get(node.id) || 0;
    return periodMeta.planes[planeIndex]?.z ?? periodMeta.centerZ;
  };
  const positions = new Map(nodes.map((node) => [node.id, new THREE.Vector3(node.x, node.y, nodeZ(node))]));
  const familyNodes = nodes.filter((node) => node.nodeType === "family");
  const domainOrder = Object.keys(DOMAIN_META);
  const periods = [...new Set(familyNodes.map((node) => node.period))].sort();
  const familyRanks = new Map();
  const categoryMaxRank = new Map();
  domainOrder.forEach((category) => {
    const totals = new Map();
    familyNodes.filter((node) => node.category === category).forEach((node) => {
      totals.set(node.family, Math.max(totals.get(node.family) || 0, node.jobCount || 0));
    });
    [...totals.entries()]
      .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
      .forEach(([family], index, entries) => {
        familyRanks.set(`${category}:${family}`, index);
        categoryMaxRank.set(category, entries.length - 1);
      });
  });

  familyNodes.forEach((family) => {
    const rank = familyRanks.get(`${family.category}:${family.family}`) || 0;
    const periodIndex = Math.max(0, periods.indexOf(family.period));
    if (clusterMode) {
      const lane = rank % 4;
      const radius = 8.5 + lane * 7.2;
      const angle = rank * 2.399963 + periodIndex * 0.055;
      positions.set(family.id, new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius, nodeZ(family)));
      return;
    }
    const domainIndex = Math.max(0, domainOrder.indexOf(family.category));
    const lane = Math.floor(rank / 7);
    const slot = rank % 7;
    const centerAngle = domainIndex * Math.PI / 2 + Math.PI / 4;
    let angle = centerAngle + (slot - 3) * 0.12 + lane * 0.035;
    const naturalRadius = 15 + lane * 8.5 + (slot % 2) * 1.8;
    let radius = naturalRadius;
    if (naturalRadius > ECLIPTIC_FAMILY_LIMIT) {
      const firstOverflowRank = 28;
      const overflowIndex = Math.max(0, rank - firstOverflowRank);
      const overflowCount = Math.max(1, (categoryMaxRank.get(family.category) || rank) - firstOverflowRank + 1);
      const progress = Math.sqrt((overflowIndex + 1) / overflowCount);
      const direction = domainIndex % 2 ? -1 : 1;
      radius = GALACTIC_ARM_INNER_RADIUS + progress * (GALACTIC_ARM_OUTER_RADIUS - GALACTIC_ARM_INNER_RADIUS);
      angle = centerAngle + direction * (0.1 + progress * 1.55) + (slot - 3) * 0.014 + periodIndex * 0.004;
    }
    positions.set(family.id, new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius, nodeZ(family)));
  });

  const jobsByFamily = new Map();
  nodes.filter((node) => node.nodeType === "job").forEach((node) => {
    if (!jobsByFamily.has(node.familyId)) jobsByFamily.set(node.familyId, []);
    jobsByFamily.get(node.familyId).push(node);
  });
  jobsByFamily.forEach((jobs, familyId) => {
    const center = positions.get(familyId);
    if (!center) return;
    jobs.sort((left, right) => left.id.localeCompare(right.id));
    jobs.forEach((job, index) => {
      const angle = index * 2.399963 + hashUnit(job.id) * 0.4;
      const levelOffset = job.ringType === "inner" ? 0 : job.ringType === "middle" ? 1.2 : 2.4;
      const radius = Math.min(clusterMode ? 8.5 : 6.8, 2.3 + Math.sqrt(index) * 0.68 + levelOffset);
      positions.set(job.id, new THREE.Vector3(center.x + Math.cos(angle) * radius, center.y + Math.sin(angle) * radius, nodeZ(job)));
    });
  });

  const skillsByFamily = new Map();
  nodes.filter((node) => node.nodeType === "skill").forEach((node) => {
    if (!skillsByFamily.has(node.familyId)) skillsByFamily.set(node.familyId, []);
    skillsByFamily.get(node.familyId).push(node);
  });
  skillsByFamily.forEach((skills, familyId) => {
    const center = positions.get(familyId);
    if (!center) return;
    skills.forEach((skill) => {
      const angle = hashUnit(`${skill.category}:${skill.family}:${skill.title}`) * Math.PI * 2;
      positions.set(skill.id, new THREE.Vector3(center.x + Math.cos(angle) * 4.2, center.y + Math.sin(angle) * 4.2, nodeZ(skill) + 0.3));
    });
  });
  return positions;
}

export default function ThreeGraph({
  compact = false,
  variant = "temporal",
  onSelect,
  onStats,
  onLayers,
  onDrill,
  onEvolutionFocusChange,
  query = "",
  period = "all",
  temporalPosition = 0,
  temporalScrubbing = false,
  domain = "all",
  viewLevel = "overview",
  familyFocus = "",
  relationLens = "job_skill",
  jobEvolutionMode = false,
  evolutionLayer = null,
  evolutionPosition = 0,
  selectedNodeId = null,
  previewLayer = null,
  timeTraveling = false,
  apiUrl = "http://localhost:8000",
}) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const hoverRef = useRef(null);
  const periodTransitionRef = useRef(null);
  const cameraSeedRef = useRef(null);
  const requestedPeriodRef = useRef(period);
  const timeTravelingRef = useRef(timeTraveling);
  const jobEvolutionModeRef = useRef(jobEvolutionMode);
  const evolutionFocusActiveRef = useRef(false);
  const evolutionProfileRef = useRef(null);
  const evolutionPositionRef = useRef(evolutionPosition);
  const temporalPositionRef = useRef(Number(temporalPosition) || 0);
  const temporalScrubbingRef = useRef(Boolean(temporalScrubbing));
  const [graph, setGraph] = useState({ nodes: [], links: [], layers: [], stats: {} });
  const [hover, setHover] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [renderPeriod, setRenderPeriod] = useState(period);
  const [periodTransitioning, setPeriodTransitioning] = useState(false);
  const [densityPlaneFilter, setDensityPlaneFilter] = useState("0");
  const wormholeMode = variant === "wormhole";
  const clusterMode = domain !== "all";

  const evolutionProfile = useMemo(() => buildJobEvolutionProfile(graph, query), [graph, query]);
  const evolutionFrameIndex = Math.max(0, Math.min(
    Math.round(Number(evolutionPosition || 0)),
    Math.max(0, (evolutionProfile?.frames.length || 1) - 1),
  ));
  const evolutionFrame = evolutionProfile?.frames[evolutionFrameIndex] || null;

  useEffect(() => {
    timeTravelingRef.current = timeTraveling;
  }, [timeTraveling]);

  useEffect(() => {
    jobEvolutionModeRef.current = jobEvolutionMode;
    evolutionFocusActiveRef.current = Boolean(jobEvolutionMode && evolutionProfile);
    evolutionProfileRef.current = evolutionProfile;
    evolutionPositionRef.current = Number(evolutionPosition || 0);
    sceneRef.current?.setEvolutionState?.(jobEvolutionMode, evolutionProfile, Number(evolutionPosition || 0));
  }, [evolutionPosition, evolutionProfile, jobEvolutionMode]);

  useEffect(() => {
    const nextPosition = Number(temporalPosition);
    temporalPositionRef.current = Number.isFinite(nextPosition) ? nextPosition : 0;
    temporalScrubbingRef.current = Boolean(temporalScrubbing);
    sceneRef.current?.setTemporalState?.(temporalPositionRef.current, temporalScrubbingRef.current);
  }, [temporalPosition, temporalScrubbing]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const endpoint = wormholeMode ? "/api/graph/wormhole" : "/api/graph/temporal";
    const maxNodes = compact ? 420 : wormholeMode ? 12000 : 1800;
    fetch(`${apiUrl}${endpoint}?max_nodes=${maxNodes}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`星系接口返回 ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        setGraph(payload);
        onLayers?.(payload.layers || []);
        setError("");
      })
      .catch((reason) => {
        if (reason.name !== "AbortError") setError(reason.message || "图谱加载失败");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [apiUrl, compact, onLayers, wormholeMode]);

  const rawSceneNodePool = useMemo(() => graph.nodes.filter((node) => {
    if (domain !== "all" && node.category !== domain) return false;
    if (familyFocus && node.family !== familyFocus) return false;
    if (wormholeMode) return ["family", "job", "skill", "signal"].includes(node.nodeType);
    if (viewLevel === "overview") return node.nodeType === "family";
    if (viewLevel === "jobs") return node.nodeType === "family" || node.nodeType === "job";
    return node.nodeType === "family" || node.nodeType === "skill" || node.nodeType === "signal";
  }), [domain, familyFocus, graph.nodes, viewLevel, wormholeMode]);

  const sceneNodePool = useMemo(() => {
    if (wormholeMode) return rawSceneNodePool;
    if (familyFocus || viewLevel === "jobs") return rawSceneNodePool;
    const periodLimit = renderPeriod === "all" ? 18 : 42;
    const periods = renderPeriod === "all"
      ? [...new Set(rawSceneNodePool.map((node) => node.period).filter(Boolean))]
      : [renderPeriod];
    const keptFamilies = new Set();
    periods.forEach((itemPeriod) => {
      rawSceneNodePool
        .filter((node) => node.nodeType === "family" && node.period === itemPeriod)
        .sort((left, right) => Number(right.jobCount || 0) - Number(left.jobCount || 0))
        .slice(0, periodLimit)
        .forEach((node) => keptFamilies.add(node.id));
    });
    if (viewLevel === "overview") {
      return rawSceneNodePool.filter((node) => keptFamilies.has(node.id));
    }
    const familyNames = new Set(rawSceneNodePool.filter((node) => keptFamilies.has(node.id)).map((node) => `${node.period}:${node.family || node.title}`));
    const keptSkills = new Set();
    familyNames.forEach((familyKey) => {
      const [itemPeriod, ...familyParts] = familyKey.split(":");
      const familyName = familyParts.join(":");
      rawSceneNodePool
        .filter((node) => node.nodeType === "skill" && node.period === itemPeriod && node.family === familyName)
        .sort((left, right) => Number(right.supportCount || right.coverage || 0) - Number(left.supportCount || left.coverage || 0))
        .slice(0, 5)
        .forEach((node) => keptSkills.add(node.id));
    });
    return rawSceneNodePool.filter((node) => keptFamilies.has(node.id) || keptSkills.has(node.id));
  }, [familyFocus, rawSceneNodePool, renderPeriod, viewLevel, wormholeMode]);

  const denseOverviewPeriods = useMemo(() => {
    if (!wormholeMode || renderPeriod !== "all") return new Set();
    const counts = new Map();
    sceneNodePool.forEach((node) => {
      if (node.period) counts.set(node.period, (counts.get(node.period) || 0) + 1);
    });
    return new Set(
      [...counts.entries()]
        .filter(([, count]) => count > (compact ? 600 : OVERVIEW_DENSE_PERIOD_NODE_LIMIT))
        .map(([periodId]) => periodId),
    );
  }, [compact, renderPeriod, sceneNodePool, wormholeMode]);

  const densityLayout = useMemo(() => buildDensityPlanes(sceneNodePool, graph.layers, compact), [compact, graph.layers, sceneNodePool]);
  const activePeriodMeta = renderPeriod === "all" ? null : densityLayout.periodMap.get(renderPeriod);
  const flatMode = renderPeriod !== "all";
  const displayPlanes = useMemo(() => densityLayout.planes.filter((plane) => {
    if (renderPeriod === "all") return true;
    if (plane.period !== renderPeriod) return false;
    return plane.index === Number(densityPlaneFilter);
  }), [densityLayout.planes, densityPlaneFilter, renderPeriod]);
  const visibleNodes = useMemo(() => sceneNodePool.filter((node) => {
    if (renderPeriod === "all") return true;
    if (node.period !== renderPeriod) return false;
    return densityLayout.nodePlaneMap.get(node.id) === Number(densityPlaneFilter);
  }).filter((node) => !(denseOverviewPeriods.has(node.period) && node.nodeType === "skill")), [denseOverviewPeriods, densityLayout.nodePlaneMap, densityPlaneFilter, renderPeriod, sceneNodePool]);
  const visibleLayers = useMemo(() => graph.layers.filter((layer) => renderPeriod === "all" || layer.id === renderPeriod), [graph.layers, renderPeriod]);
  const scenePositions = useMemo(() => buildScenePositions(sceneNodePool, clusterMode, densityLayout), [clusterMode, densityLayout, sceneNodePool]);

  useEffect(() => setDensityPlaneFilter("0"), [domain, familyFocus, renderPeriod]);

  useEffect(() => {
    const ids = new Set(visibleNodes.map((node) => node.id));
    const periodsById = new Map(visibleNodes.map((node) => [node.id, node.period]));
    const lensTypes = RELATION_LENS_TYPES[relationLens] || RELATION_LENS_TYPES.integrated;
    // Dense overview periods intentionally suppress their line geometry for
    // performance, but their relations still exist between the currently
    // visible nodes. Keep the semantic count separate from the GPU draw count
    // so the header does not incorrectly report zero relations.
    const visibleRelationLinks = graph.links.filter((link) =>
      ids.has(link.source) && ids.has(link.target) && lensTypes.has(link.type));
    const renderedRelationLinks = visibleRelationLinks.filter((link) =>
      !denseOverviewPeriods.has(periodsById.get(link.source))
      && !denseOverviewPeriods.has(periodsById.get(link.target)));
    const focusedEvolutionEdges = jobEvolutionMode && evolutionFrame
      ? evolutionFrame.skills.filter((skill) => skill.weight > 0.08).length
      : null;
    onStats?.({
      ...(graph.stats || {}),
      rendered_nodes: focusedEvolutionEdges == null ? visibleNodes.length : focusedEvolutionEdges + 1,
      visible_relation_edges: focusedEvolutionEdges == null ? visibleRelationLinks.length : focusedEvolutionEdges,
      rendered_edges: focusedEvolutionEdges == null ? renderedRelationLinks.length : focusedEvolutionEdges,
      density_suppressed_edges: visibleRelationLinks.length - renderedRelationLinks.length,
      companies: new Set(visibleNodes.map((node) => node.company).filter(Boolean)).size || graph.stats?.companies || 0,
      periods: visibleLayers.length,
      rendered_planes: displayPlanes.length,
    });
  }, [denseOverviewPeriods, displayPlanes.length, evolutionFrame, graph.links, graph.stats, jobEvolutionMode, onStats, relationLens, visibleLayers, visibleNodes]);

  const focusNode = useCallback((node) => {
    const context = sceneRef.current;
    if (!context || !node) return;
    const position = context.positions.get(node.id) || new THREE.Vector3(node.x || 0, node.y || 0, node.z || 0);
    context.desiredTarget.copy(position);
    context.desiredCamera.set(
      flatMode ? position.x + 0.01 : position.x + 13,
      flatMode ? position.y + 0.01 : position.y + 11,
      position.z - (flatMode ? 34 : 20),
    );
    onSelect?.(node);
  }, [flatMode, onSelect]);

  useEffect(() => {
    const term = query.trim().toLowerCase();
    if (jobEvolutionMode || term.length < 2) return;
    const node = visibleNodes.find((item) => nodeText(item).includes(term));
    if (node) focusNode(node);
  }, [focusNode, jobEvolutionMode, query, visibleNodes]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !visibleNodes.length || !displayPlanes.length) return undefined;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060b0d);
    scene.fog = new THREE.FogExp2(0x060b0d, compact ? 0.0036 : 0.0024);
    const camera = new THREE.PerspectiveCamera(52, 1, 0.1, 800);
    const middleZ = displayPlanes.reduce((sum, plane) => sum + plane.z, 0) / displayPlanes.length;
    const cameraSeed = cameraSeedRef.current;
    camera.position.copy(cameraSeed?.position || new THREE.Vector3(flatMode ? 0.01 : 68, flatMode ? 0.01 : 42, middleZ - (flatMode ? 108 : 58)));
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, compact ? 1 : 1.35));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.enableRotate = !flatMode;
    controls.enablePan = true;
    controls.enableZoom = true;
    controls.screenSpacePanning = true;
    controls.zoomToCursor = true;
    controls.mouseButtons.LEFT = flatMode ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE;
    controls.mouseButtons.MIDDLE = THREE.MOUSE.DOLLY;
    controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
    controls.touches.ONE = flatMode ? THREE.TOUCH.PAN : THREE.TOUCH.ROTATE;
    controls.touches.TWO = THREE.TOUCH.DOLLY_PAN;
    controls.autoRotate = compact && !flatMode;
    controls.autoRotateSpeed = 0.16;
    controls.minDistance = 10;
    controls.maxDistance = 250;
    controls.target.copy(cameraSeed?.target || new THREE.Vector3(0, 0, middleZ));
    let controlsInteracting = false;

    scene.add(new THREE.AmbientLight(0xb9d9dc, 0.8));
    const keyLight = new THREE.PointLight(0xbbeeff, 16, 180);
    keyLight.position.set(0, 0, middleZ + 12);
    scene.add(keyLight);

    const dustCount = compact ? 500 : 1100;
    const dustPositions = new Float32Array(dustCount * 3);
    for (let index = 0; index < dustCount; index += 1) {
      dustPositions[index * 3] = (seeded(index * 3) - 0.5) * 220;
      dustPositions[index * 3 + 1] = (seeded(index * 3 + 1) - 0.5) * 150;
      dustPositions[index * 3 + 2] = middleZ + (seeded(index * 3 + 2) - 0.5) * 260;
    }
    const dustGeometry = new THREE.BufferGeometry();
    dustGeometry.setAttribute("position", new THREE.BufferAttribute(dustPositions, 3));
    const dust = new THREE.Points(dustGeometry, new THREE.PointsMaterial({ color: 0x7fa0a4, size: 0.18, transparent: true, opacity: 0.32, depthWrite: false }));
    scene.add(dust);

    const glow = glowTexture();
    const minZ = Math.min(...displayPlanes.map((plane) => plane.z)) - 18;
    const maxZ = Math.max(...displayPlanes.map((plane) => plane.z)) + 18;
    const helixCount = compact ? 360 : 720;
    const helixPositions = new Float32Array(helixCount * 3);
    for (let index = 0; index < helixCount; index += 1) {
      const t = index / Math.max(1, helixCount - 1);
      const angle = t * Math.max(3, displayPlanes.length * 0.9) * Math.PI * 2;
      const radius = 2.35 + Math.sin(t * Math.PI * 6) * 0.35;
      helixPositions[index * 3] = Math.cos(angle) * radius;
      helixPositions[index * 3 + 1] = Math.sin(angle) * radius;
      helixPositions[index * 3 + 2] = maxZ + t * (minZ - maxZ);
    }
    const helixGeometry = new THREE.BufferGeometry();
    helixGeometry.setAttribute("position", new THREE.BufferAttribute(helixPositions, 3));
    const helix = new THREE.Points(helixGeometry, new THREE.PointsMaterial({ color: WORMHOLE_LIGHT_BLUE, size: 0.72, map: glow, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.78 }));
    helix.visible = renderPeriod === "all";
    scene.add(helix);

    const ringPositions = [];
    const ringColors = [];
    const planeLabelSprites = [];
    displayPlanes.forEach((layer) => {
      [15, 27, 39, 49].forEach((radius, ringIndex) => {
        const ringColor = new THREE.Color(ringIndex === 3 ? WORMHOLE_MUTED_BLUE : layer.isDensityPlane ? 0x416fae : WORMHOLE_BLUE);
        const segmentCount = 96;
        for (let segment = 0; segment < segmentCount; segment += 1) {
          const angle0 = segment / segmentCount * Math.PI * 2;
          const angle1 = (segment + 1) / segmentCount * Math.PI * 2;
          ringPositions.push(Math.cos(angle0) * radius, Math.sin(angle0) * radius, layer.z, Math.cos(angle1) * radius, Math.sin(angle1) * radius, layer.z);
          ringColors.push(ringColor.r, ringColor.g, ringColor.b, ringColor.r, ringColor.g, ringColor.b);
        }
      });
      const radialCount = clusterMode ? 12 : 4;
      const radialColor = new THREE.Color(WORMHOLE_MUTED_BLUE);
      for (let index = 0; index < radialCount; index += 1) {
        const angle = index * Math.PI * 2 / radialCount + 0.15;
        ringPositions.push(Math.cos(angle) * 11, Math.sin(angle) * 11, layer.z, Math.cos(angle) * 51, Math.sin(angle) * 51, layer.z);
        ringColors.push(radialColor.r, radialColor.g, radialColor.b, radialColor.r, radialColor.g, radialColor.b);
      }
      const shouldLabel = !layer.isDensityPlane || displayPlanes.length <= 12 || layer.index === 0 || layer.index === layer.planeCount - 1 || layer.index % 5 === 0;
      if (shouldLabel) {
        const label = labelSprite(layer.label, layer.isDensityPlane ? "#8faed3" : "#c5d7d8", layer.isDensityPlane ? 0.62 : 0.9);
        label.position.set(0, 5.7, layer.z + 0.5);
        scene.add(label);
        planeLabelSprites.push(label);
      }
    });
    let ringMesh = null;
    if (ringPositions.length) {
      const ringGeometry = new THREE.BufferGeometry();
      ringGeometry.setAttribute("position", new THREE.Float32BufferAttribute(ringPositions, 3));
      ringGeometry.setAttribute("color", new THREE.Float32BufferAttribute(ringColors, 3));
      ringMesh = new THREE.LineSegments(ringGeometry, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: clusterMode ? 0.2 : 0.24, depthWrite: false, blending: THREE.AdditiveBlending }));
      scene.add(ringMesh);
    }

    const galacticArmGroups = new Map();
    if (!clusterMode) {
      visibleNodes.filter((node) => node.nodeType === "family").forEach((node) => {
        const position = scenePositions.get(node.id);
        if (!position) return;
        const radius = Math.hypot(position.x, position.y);
        if (radius <= ECLIPTIC_OUTER_RADIUS + 1) return;
        const key = `${position.z.toFixed(2)}:${node.category}`;
        if (!galacticArmGroups.has(key)) galacticArmGroups.set(key, { category: node.category, positions: [] });
        galacticArmGroups.get(key).positions.push(position.clone());
      });
    }
    const armPositions = [];
    const armColors = [];
    const armNodePositions = [];
    const armNodeColors = [];
    let galacticArmMesh = null;
    let galacticArmAnchors = null;
    galacticArmGroups.forEach(({ category, positions }) => {
      positions.sort((left, right) => Math.hypot(left.x, left.y) - Math.hypot(right.x, right.y));
      const first = positions[0];
      const firstAngle = Math.atan2(first.y, first.x);
      const points = [new THREE.Vector3(Math.cos(firstAngle) * (ECLIPTIC_OUTER_RADIUS - 0.2), Math.sin(firstAngle) * (ECLIPTIC_OUTER_RADIUS - 0.2), first.z), ...positions];
      if (points.length === 2) points.splice(1, 0, points[0].clone().lerp(points[1], 0.48));
      const curvePoints = new THREE.CatmullRomCurve3(points, false, "centripetal", 0.45).getPoints(Math.max(12, positions.length * 5));
      const color = new THREE.Color(DOMAIN_META[category]?.color || WORMHOLE_LIGHT_BLUE).lerp(new THREE.Color(WORMHOLE_LIGHT_BLUE), 0.26);
      for (let index = 1; index < curvePoints.length; index += 1) {
        armPositions.push(...curvePoints[index - 1].toArray(), ...curvePoints[index].toArray());
        armColors.push(color.r, color.g, color.b, color.r, color.g, color.b);
      }
      positions.forEach((position) => {
        armNodePositions.push(...position.toArray());
        armNodeColors.push(color.r, color.g, color.b);
      });
    });
    if (armPositions.length) {
      const armGeometry = new THREE.BufferGeometry();
      armGeometry.setAttribute("position", new THREE.Float32BufferAttribute(armPositions, 3));
      armGeometry.setAttribute("color", new THREE.Float32BufferAttribute(armColors, 3));
      galacticArmMesh = new THREE.LineSegments(
        armGeometry,
        new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.3, depthWrite: false, blending: THREE.AdditiveBlending }),
      );
      scene.add(galacticArmMesh);
      const anchorGeometry = new THREE.BufferGeometry();
      anchorGeometry.setAttribute("position", new THREE.Float32BufferAttribute(armNodePositions, 3));
      anchorGeometry.setAttribute("color", new THREE.Float32BufferAttribute(armNodeColors, 3));
      galacticArmAnchors = new THREE.Points(
        anchorGeometry,
        new THREE.PointsMaterial({ vertexColors: true, size: 0.75, map: glow, transparent: true, opacity: 0.46, depthWrite: false, blending: THREE.AdditiveBlending }),
      );
      scene.add(galacticArmAnchors);
    }

    const nodeById = new Map(visibleNodes.map((node) => [node.id, node]));
    const labelBuckets = new Map();
    const frontPeriod = renderPeriod === "all" ? visibleLayers.at(-1)?.id : renderPeriod;
    visibleNodes.filter((node) => node.nodeType === "family" && node.period === frontPeriod).forEach((node) => {
      const key = clusterMode ? node.category : `${node.period}:${node.category}`;
      if (!labelBuckets.has(key)) labelBuckets.set(key, []);
      labelBuckets.get(key).push(node);
    });
    const familyLabelIds = new Set();
    labelBuckets.forEach((nodes) => nodes
      .sort((left, right) => right.jobCount - left.jobCount || left.title.localeCompare(right.title))
      .slice(0, clusterMode ? 8 : 2)
      .forEach((node) => familyLabelIds.add(node.id)));
    const interactive = [];
    const objectNode = new Map();
    const nodeMeshes = new Map();
    const nodeLabelSprites = [];
    const megaCoronas = [];
    const familyGeometry = new THREE.IcosahedronGeometry(0.78, 2);
    const skillGeometry = new THREE.OctahedronGeometry(0.48, 1);
    visibleNodes.filter((node) => node.nodeType !== "job" && !(wormholeMode && node.nodeType === "skill")).forEach((node) => {
      const isSignal = node.nodeType === "signal";
      const meta = isSignal ? { color: 0xf4c76f, css: "#f4c76f" } : DOMAIN_META[node.category] || DOMAIN_META.人工智能;
      const evolutionMeta = EVOLUTION_META[node.evolutionState] || EVOLUTION_META.stable;
      const geometry = node.nodeType === "family" ? familyGeometry : skillGeometry;
      const material = new THREE.MeshStandardMaterial({
        color: meta.color,
        emissive: evolutionMeta.color || meta.color,
        emissiveIntensity: node.nodeType === "family" ? (evolutionMeta.color ? 0.82 : 0.58) : isSignal ? 0.52 : 0.24,
        roughness: 0.32,
        metalness: 0.18,
        flatShading: true,
        transparent: true,
        opacity: node.nodeType === "family" ? 0.98 : isSignal ? 0.7 : 0.82,
        wireframe: isSignal,
      });
      const mesh = new THREE.Mesh(geometry, material);
      const position = scenePositions.get(node.id) || new THREE.Vector3(node.x, node.y, node.z);
      mesh.position.copy(position);
      const isMega = node.nodeType === "family" && node.jobCount >= 8;
      const scale = node.nodeType === "family"
        ? Math.min(isMega ? 2.35 : 1.8, 1.05 + Math.sqrt(node.jobCount || 1) * 0.085)
        : isSignal ? 0.72 : 0.9 + Math.min(0.65, (node.coverage || 0) / 100);
      mesh.scale.setScalar(scale);
      mesh.userData = { node, baseScale: scale, isMega };
      scene.add(mesh);
      interactive.push(mesh);
      objectNode.set(mesh.uuid, node);
      nodeMeshes.set(node.id, mesh);
      if (isMega || evolutionMeta.color || node.fusionCandidate) {
        const corona = new THREE.Mesh(
          familyGeometry,
          new THREE.MeshBasicMaterial({ color: node.fusionCandidate ? 0xe090ff : evolutionMeta.color || meta.color, wireframe: true, transparent: true, opacity: evolutionMeta.color || node.fusionCandidate ? 0.3 : 0.16, depthWrite: false }),
        );
        corona.position.copy(position);
        corona.scale.setScalar(scale * 1.42);
        corona.userData = { nodeId: node.id, pulseOffset: hashUnit(node.id) * Math.PI * 2, baseScale: scale * 1.42 };
        scene.add(corona);
        megaCoronas.push(corona);
      }
      if ((node.nodeType === "family" && familyLabelIds.has(node.id)) || familyFocus || visibleNodes.length < 28) {
        const label = labelSprite(node.title, meta.css, node.nodeType === "family" ? 0.78 : 0.6);
        label.position.set(position.x, position.y + scale + 1.05, position.z);
        label.userData.nodeId = node.id;
        nodeLabelSprites.push(label);
        scene.add(label);
      }
    });

    const jobGroups = Object.keys(DOMAIN_META).map((category) => [category, visibleNodes.filter((node) => node.nodeType === "job" && node.category === category)]).filter(([, nodes]) => nodes.length);
    const jobGeometry = new THREE.SphereGeometry(compact ? 0.32 : 0.38, 7, 6);
    const jobInstances = [];
    jobGroups.forEach(([category, nodes]) => {
      const material = wormholeMode
        ? new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.88 })
        : new THREE.MeshStandardMaterial({ color: DOMAIN_META[category].color, emissive: DOMAIN_META[category].color, emissiveIntensity: 0.3, roughness: 0.45 });
      const mesh = new THREE.InstancedMesh(jobGeometry, material, nodes.length);
      const matrix = new THREE.Matrix4();
      const baseColors = [];
      nodes.forEach((node, index) => {
        const scale = RING_SCALE[node.ringType] || 0.8;
        const position = scenePositions.get(node.id) || new THREE.Vector3(node.x, node.y, node.z);
        matrix.compose(position, new THREE.Quaternion(), new THREE.Vector3(scale, scale, scale));
        mesh.setMatrixAt(index, matrix);
        if (wormholeMode) {
          const color = new THREE.Color(DOMAIN_META[category].color);
          mesh.setColorAt(index, color);
          baseColors.push(color);
        }
      });
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      mesh.userData.nodes = nodes;
      mesh.userData.baseColors = baseColors;
      scene.add(mesh);
      interactive.push(mesh);
      jobInstances.push(mesh);
    });

    const skillInstances = [];
    if (wormholeMode) {
      const skillGroups = Object.keys(DOMAIN_META)
        .map((category) => [category, visibleNodes.filter((node) => node.nodeType === "skill" && node.category === category)])
        .filter(([, nodes]) => nodes.length);
      skillGroups.forEach(([category, nodes]) => {
        const material = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.88 });
        const mesh = new THREE.InstancedMesh(skillGeometry, material, nodes.length);
        const halo = new THREE.InstancedMesh(skillGeometry, new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.14, blending: THREE.AdditiveBlending, depthWrite: false }), nodes.length);
        const matrix = new THREE.Matrix4();
        const haloMatrix = new THREE.Matrix4();
        const baseColors = [];
        nodes.forEach((node, index) => {
          const position = scenePositions.get(node.id) || new THREE.Vector3(node.x, node.y, node.z);
          const scale = 0.72 + Math.min(0.52, Number(node.coverage || 0) / 150);
          matrix.compose(position, new THREE.Quaternion(), new THREE.Vector3(scale, scale, scale));
          haloMatrix.compose(position, new THREE.Quaternion(), new THREE.Vector3(scale * 1.72, scale * 1.72, scale * 1.72));
          mesh.setMatrixAt(index, matrix);
          halo.setMatrixAt(index, haloMatrix);
          const color = new THREE.Color(DOMAIN_META[category].color).lerp(new THREE.Color(0x9de6c0), 0.22);
          mesh.setColorAt(index, color);
          halo.setColorAt(index, color);
          baseColors.push(color);
        });
        mesh.instanceMatrix.needsUpdate = true;
        halo.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        if (halo.instanceColor) halo.instanceColor.needsUpdate = true;
        mesh.userData.nodes = nodes;
        mesh.userData.baseColors = baseColors;
        mesh.userData.instanceKind = "skill";
        mesh.userData.halo = halo;
        halo.userData.nodes = nodes;
        halo.userData.baseColors = baseColors;
        scene.add(mesh);
        scene.add(halo);
        interactive.push(mesh);
        skillInstances.push(mesh);
      });
    }

    const lensRelations = RELATION_LENS_TYPES[relationLens] || RELATION_LENS_TYPES.integrated;
    const relationLinkRecord = (link) => {
      const source = nodeById.get(link.source);
      const target = nodeById.get(link.target);
      if (!source || !target) return null;
      return {
        ...link,
        sourceNode: source,
        targetNode: target,
        sourcePosition: scenePositions.get(source.id) || new THREE.Vector3(source.x, source.y, source.z),
        targetPosition: scenePositions.get(target.id) || new THREE.Vector3(target.x, target.y, target.z),
      };
    };
    const visibleLinks = graph.links.filter((link) => {
      if (!nodeById.has(link.source) || !nodeById.has(link.target) || !lensRelations.has(link.type)) return false;
      const source = nodeById.get(link.source);
      const target = nodeById.get(link.target);
      return !(denseOverviewPeriods.has(source?.period) || denseOverviewPeriods.has(target?.period));
    });
    // The base mesh stays sparse, while click focus can recover relations that
    // were omitted only because an overview period exceeded the density cap.
    const selectionLinkRecords = graph.links
      .filter((link) => nodeById.has(link.source) && nodeById.has(link.target) && lensRelations.has(link.type))
      .map(relationLinkRecord)
      .filter(Boolean);
    const baseLinkOpacity = wormholeMode ? relationLens === "integrated" ? 0.085 : 0.17 : viewLevel === "overview" ? 0.42 : 0.22;
    const linkPositions = [];
    const linkColors = [];
    const linkRecords = [];
    visibleLinks.forEach((link) => {
      const record = relationLinkRecord(link);
      if (!record) return;
      const { sourcePosition, targetPosition } = record;
      linkPositions.push(sourcePosition.x, sourcePosition.y, sourcePosition.z, targetPosition.x, targetPosition.y, targetPosition.z);
      const color = relationColor(link);
      linkColors.push(color.r, color.g, color.b, color.r, color.g, color.b);
      linkRecords.push(record);
    });
    let linkMesh = null;
    if (linkPositions.length) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(linkPositions, 3));
      geometry.setAttribute("color", new THREE.Float32BufferAttribute(linkColors, 3));
      linkMesh = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: baseLinkOpacity, depthWrite: false, blending: THREE.AdditiveBlending }));
      scene.add(linkMesh);
    }

    // Keep the dense relation network in one immutable draw call. Hover paths use
    // a small preallocated overlay so pointer movement never rewrites 10k+ edges.
    const highlightCapacity = compact ? 240 : 1200;
    const highlightSegments = 4;
    const highlightPositions = new Float32Array(highlightCapacity * highlightSegments * 6);
    const highlightColors = new Float32Array(highlightCapacity * highlightSegments * 6);
    const highlightGeometry = new THREE.BufferGeometry();
    highlightGeometry.setAttribute("position", new THREE.BufferAttribute(highlightPositions, 3));
    highlightGeometry.setAttribute("color", new THREE.BufferAttribute(highlightColors, 3));
    highlightGeometry.setDrawRange(0, 0);
    const highlightMesh = new THREE.LineSegments(
      highlightGeometry,
      new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending }),
    );
    highlightMesh.frustumCulled = false;
    scene.add(highlightMesh);

    const highlightLabelGroup = new THREE.Group();
    highlightLabelGroup.renderOrder = 20;
    scene.add(highlightLabelGroup);
    const clearHighlightLabels = () => {
      while (highlightLabelGroup.children.length) {
        const label = highlightLabelGroup.children.pop();
        label.userData?.labelTexture?.dispose?.();
        label.material?.dispose?.();
      }
    };

    const focusHalo = new THREE.Sprite(new THREE.SpriteMaterial({
      map: glow,
      color: 0xffffff,
      transparent: true,
      opacity: 0.72,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }));
    focusHalo.visible = false;
    focusHalo.renderOrder = 12;
    scene.add(focusHalo);

    const animatedTypes = new Set(["evolution"]);
    const animationCandidates = linkRecords.filter((link) => animatedTypes.has(link.type));
    const animationStep = Math.max(1, Math.ceil(animationCandidates.length / 160));
    const animatedLinks = animationCandidates.filter((_, index) => index % animationStep === 0).slice(0, 160);
    const particleCount = Math.min(520, animatedLinks.length * 4);
    const particlePositions = new Float32Array(particleCount * 3);
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
    const particles = new THREE.Points(particleGeometry, new THREE.PointsMaterial({ color: WORMHOLE_LIGHT_BLUE, size: 0.58, map: glow, transparent: true, opacity: 0.88, blending: THREE.AdditiveBlending, depthWrite: false }));
    particles.visible = !flatMode && animatedLinks.length > 0;
    scene.add(particles);

    const evolutionGroup = new THREE.Group();
    evolutionGroup.visible = false;
    evolutionGroup.renderOrder = 14;
    scene.add(evolutionGroup);
    const evolutionState = {
      active: false,
      targetMix: 0,
      mix: 0,
      lastAppliedMix: -1,
      targetPosition: Number(evolutionPositionRef.current || 0),
      currentPosition: Number(evolutionPositionRef.current || 0),
      profile: null,
      branches: [],
      core: null,
      coreHalo: null,
      auraParticles: null,
      pulseRing: null,
      followers: [],
      motionEnergy: 0,
      userCameraOverride: false,
      followOffset: new THREE.Vector3(17.5, 11.5, -27.5),
      titleLabel: null,
      titleText: "",
      cameraBackup: null,
    };
    const evolutionColors = {
      retained: new THREE.Color(0x58b9ff),
      strengthened: new THREE.Color(0x61e6c2),
      added: new THREE.Color(0x7ef7d2),
      declining: new THREE.Color(0xf1be67),
      retired: new THREE.Color(0xc27bd9),
    };
    const evolutionPeriodIndex = new Map(visibleLayers.map((layer, index) => [layer.id, index]));
    const evolutionPeriodSpacing = compact ? 24 : 34;
    const evolutionBaseZ = densityLayout.periodMap.get(visibleLayers[0]?.id)?.planes?.[0]?.z || 0;
    const evolutionFrameCenter = (frame) => {
      const anchor = scenePositions.get(frame?.anchorId);
      const logicalIndex = Math.max(0, evolutionPeriodIndex.get(frame?.period) ?? 0);
      return new THREE.Vector3(
        anchor?.x || 0,
        anchor?.y || 0,
        evolutionBaseZ - logicalIndex * evolutionPeriodSpacing,
      );
    };
    const clearEvolutionOverlay = () => {
      while (evolutionGroup.children.length) {
        const child = evolutionGroup.children.pop();
        child.traverse?.((object) => {
          object.userData?.labelTexture?.dispose?.();
          object.geometry?.dispose?.();
          if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose());
          else object.material?.dispose?.();
        });
      }
      evolutionState.branches = [];
      evolutionState.core = null;
      evolutionState.coreHalo = null;
      evolutionState.auraParticles = null;
      evolutionState.pulseRing = null;
      evolutionState.followers = [];
      evolutionState.titleLabel = null;
      evolutionState.titleText = "";
    };
    const rebuildEvolutionOverlay = (profile) => {
      clearEvolutionOverlay();
      evolutionState.profile = profile;
      if (!profile?.frames?.length) return;
      const coreColor = new THREE.Color(DOMAIN_META[profile.category]?.color || WORMHOLE_LIGHT_BLUE).lerp(new THREE.Color(0xffffff), 0.32);
      const core = new THREE.Mesh(
        new THREE.IcosahedronGeometry(1.36, 3),
        new THREE.MeshStandardMaterial({
          color: coreColor,
          emissive: coreColor,
          emissiveIntensity: 1.05,
          roughness: 0.18,
          metalness: 0.32,
          transparent: true,
          opacity: 0,
        }),
      );
      core.renderOrder = 16;
      evolutionGroup.add(core);
      const coreHalo = new THREE.Sprite(new THREE.SpriteMaterial({
        map: glow,
        color: coreColor,
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }));
      coreHalo.scale.setScalar(8.2);
      coreHalo.renderOrder = 15;
      evolutionGroup.add(coreHalo);
      evolutionState.core = core;
      evolutionState.coreHalo = coreHalo;
      const auraCount = compact ? 34 : 68;
      const auraPositions = new Float32Array(auraCount * 3);
      for (let index = 0; index < auraCount; index += 1) {
        const theta = seeded(index + 4200) * Math.PI * 2;
        const radius = 3.8 + seeded(index + 4600) * 8.2;
        auraPositions[index * 3] = Math.cos(theta) * radius;
        auraPositions[index * 3 + 1] = Math.sin(theta) * radius;
        auraPositions[index * 3 + 2] = (seeded(index + 5100) - 0.5) * 7.5;
      }
      const auraGeometry = new THREE.BufferGeometry();
      auraGeometry.setAttribute("position", new THREE.BufferAttribute(auraPositions, 3));
      const auraParticles = new THREE.Points(auraGeometry, new THREE.PointsMaterial({
        color: 0x72f6df,
        size: compact ? 0.34 : 0.46,
        map: glow,
        transparent: true,
        opacity: 0,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }));
      auraParticles.renderOrder = 13;
      evolutionGroup.add(auraParticles);
      const pulseRing = new THREE.Mesh(
        new THREE.RingGeometry(2.05, 2.22, 72),
        new THREE.MeshBasicMaterial({ color: 0x7fffe6, side: THREE.DoubleSide, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending }),
      );
      pulseRing.renderOrder = 15;
      evolutionGroup.add(pulseRing);
      evolutionState.auraParticles = auraParticles;
      evolutionState.pulseRing = pulseRing;
      for (let index = 0; index < 3; index += 1) {
        const follower = new THREE.Sprite(new THREE.SpriteMaterial({
          map: glow,
          color: index === 1 ? 0xb0fff0 : 0x72f6df,
          transparent: true,
          opacity: 0,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        }));
        follower.scale.setScalar(index === 1 ? 1.65 : 1.28);
        follower.renderOrder = 17;
        evolutionGroup.add(follower);
        evolutionState.followers.push(follower);
      }
      const skillNames = [...new Set(profile.frames.flatMap((frame) => frame.skills.map((skill) => skill.name)))].slice(0, 22);
      const segmentCount = compact ? 10 : 16;
      skillNames.forEach((name, index) => {
        const positions = new Float32Array(segmentCount * 3);
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        const material = new THREE.LineBasicMaterial({
          color: evolutionColors.retained,
          transparent: true,
          opacity: 0,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        });
        const line = new THREE.Line(geometry, material);
        line.frustumCulled = false;
        line.renderOrder = 14;
        evolutionGroup.add(line);
        const node = new THREE.Mesh(
          new THREE.OctahedronGeometry(index < 6 ? 0.42 : 0.3, 1),
          new THREE.MeshBasicMaterial({ color: evolutionColors.retained, transparent: true, opacity: 0, depthWrite: false }),
        );
        node.renderOrder = 16;
        evolutionGroup.add(node);
        const halo = new THREE.Sprite(new THREE.SpriteMaterial({
          map: glow,
          color: evolutionColors.retained,
          transparent: true,
          opacity: 0,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        }));
        halo.scale.setScalar(index < 6 ? 2.6 : 1.8);
        halo.renderOrder = 15;
        evolutionGroup.add(halo);
        const label = edgeLabelSprite(name, index < 6 ? "#75ead5" : "#599fbe");
        label.scale.set(index < 6 ? 7.2 : 6.2, index < 6 ? 1.3 : 1.12, 1);
        label.material.opacity = 0;
        label.renderOrder = 18;
        evolutionGroup.add(label);
        evolutionState.branches.push({ name, index, positions, geometry, material, line, node, halo, label });
      });
    };
    const setEvolutionTitle = (title) => {
      if (!title || evolutionState.titleText === title) return;
      if (evolutionState.titleLabel) {
        evolutionGroup.remove(evolutionState.titleLabel);
        evolutionState.titleLabel.userData?.labelTexture?.dispose?.();
        evolutionState.titleLabel.material?.dispose?.();
      }
      const label = edgeLabelSprite(title, "#6ee7cf");
      label.scale.set(13.4, 2.4, 1);
      label.position.set(0, -5.2, 2.6);
      label.material.opacity = 0;
      evolutionGroup.add(label);
      evolutionState.titleLabel = label;
      evolutionState.titleText = title;
    };
    const updateEvolutionOverlay = (position) => {
      const profile = evolutionState.profile;
      if (!profile?.frames?.length) return;
      const clamped = Math.max(0, Math.min(Number(position || 0), profile.frames.length - 1));
      const leftIndex = Math.floor(clamped);
      const rightIndex = Math.min(profile.frames.length - 1, Math.ceil(clamped));
      const fraction = clamped - leftIndex;
      const leftFrame = profile.frames[leftIndex];
      const rightFrame = profile.frames[rightIndex];
      const leftSkills = new Map(leftFrame.skills.map((skill) => [skill.name, skill]));
      const rightSkills = new Map(rightFrame.skills.map((skill) => [skill.name, skill]));
      const leftAnchor = evolutionFrameCenter(leftFrame);
      const rightAnchor = evolutionFrameCenter(rightFrame);
      const center = leftAnchor.clone().lerp(rightAnchor, fraction);
      evolutionGroup.position.copy(center);
      setEvolutionTitle(fraction < 0.5 ? leftFrame.title : rightFrame.title);
      const mix = evolutionState.mix;
      evolutionState.branches.forEach((branch) => {
        const leftSkill = leftSkills.get(branch.name);
        const rightSkill = rightSkills.get(branch.name);
        const leftWeight = Number(leftSkill?.weight || 0);
        const rightWeight = Number(rightSkill?.weight || 0);
        const weight = THREE.MathUtils.lerp(leftWeight, rightWeight, fraction);
        const state = fraction < 0.5 ? leftSkill?.state || rightSkill?.state || "retired" : rightSkill?.state || leftSkill?.state || "retired";
        const color = evolutionColors[state] || evolutionColors.retained;
        const seed = hashUnit(`${profile.family}:${branch.name}`);
        const angle = seed * Math.PI * 2 + branch.index * 0.54 + clamped * 0.075;
        const temporalBreath = 0.94 + Math.sin(clamped * 0.9 + seed * 6.2) * 0.06;
        const radius = (7.2 + (branch.index % 6) * 1.38 + Math.floor(branch.index / 6) * 1.2) * Math.max(0.08, weight) * temporalBreath;
        const vertical = (seed - 0.5) * 7.5 + Math.sin(clamped * 0.72 + branch.index) * 0.48;
        const segments = branch.positions.length / 3;
        for (let segment = 0; segment < segments; segment += 1) {
          const progress = segment / Math.max(1, segments - 1);
          const growth = Math.min(1, Math.max(0, weight * 1.18));
          const grownProgress = Math.min(progress, growth) / Math.max(0.001, growth);
          const eased = grownProgress * grownProgress * (3 - 2 * grownProgress);
          const curl = Math.sin(progress * Math.PI) * (1.1 + seed * 2.1);
          const localAngle = angle + progress * (0.28 + seed * 0.36);
          const radial = radius * eased;
          branch.positions[segment * 3] = Math.cos(localAngle) * radial - Math.sin(localAngle) * curl;
          branch.positions[segment * 3 + 1] = Math.sin(localAngle) * radial + Math.cos(localAngle) * curl;
          branch.positions[segment * 3 + 2] = vertical * eased + Math.sin(progress * Math.PI * 2 + seed * 5) * 0.72;
        }
        branch.geometry.attributes.position.needsUpdate = true;
        branch.geometry.setDrawRange(0, Math.max(2, Math.floor(segments * Math.max(0.06, weight))));
        const endpointIndex = Math.max(0, Math.min(segments - 1, Math.floor((segments - 1) * Math.max(0.08, weight))));
        branch.node.position.fromArray(branch.positions, endpointIndex * 3);
        branch.halo.position.copy(branch.node.position);
        branch.label.position.copy(branch.node.position).add(new THREE.Vector3(0, 0.72, 0));
        branch.material.color.copy(color);
        branch.node.material.color.copy(color);
        branch.halo.material.color.copy(color);
        const stateBoost = state === "added" ? 1 : state === "strengthened" ? 0.88 : state === "declining" ? 0.62 : state === "retired" ? 0.36 : 0.74;
        branch.material.opacity = mix * weight * stateBoost;
        branch.node.material.opacity = mix * Math.min(1, weight * 1.28) * stateBoost;
        branch.halo.material.opacity = mix * Math.min(0.48, weight * 0.42) * stateBoost;
        branch.label.visible = branch.index < 14 && weight > 0.26;
        branch.label.material.opacity = branch.label.visible ? mix * Math.min(0.94, weight + 0.18) : 0;
        branch.node.scale.setScalar(0.64 + weight * (state === "added" ? 0.9 : 0.58));
      });
      if (evolutionState.core) evolutionState.core.material.opacity = mix * 0.98;
      if (evolutionState.coreHalo) evolutionState.coreHalo.material.opacity = mix * 0.52;
      if (evolutionState.titleLabel) evolutionState.titleLabel.material.opacity = mix * 0.96;
      if (evolutionState.active && !controlsInteracting) {
        if (!evolutionState.userCameraOverride) {
          context?.desiredTarget?.copy(center);
          context?.desiredCamera?.copy(center).add(evolutionState.followOffset);
        }
      }
    };
    const applyEvolutionMix = (mix) => {
      if (mix !== 0 && mix !== 1 && Math.abs(evolutionState.lastAppliedMix - mix) < 0.006) return;
      evolutionState.lastAppliedMix = mix;
      const backgroundVisible = mix < 0.97;
      const backgroundDepthWrite = mix < 0.02;
      nodeMeshes.forEach((mesh) => {
        const baseOpacity = mesh.userData.node?.nodeType === "family" ? 0.98 : mesh.userData.node?.nodeType === "signal" ? 0.7 : 0.82;
        mesh.material.opacity = THREE.MathUtils.lerp(baseOpacity, 0.003, mix);
        mesh.material.depthWrite = backgroundDepthWrite;
        mesh.visible = backgroundVisible;
      });
      jobInstances.forEach((mesh) => {
        mesh.material.opacity = THREE.MathUtils.lerp(0.88, 0.004, mix);
        mesh.material.depthWrite = backgroundDepthWrite;
        mesh.visible = backgroundVisible;
      });
      skillInstances.forEach((mesh) => {
        mesh.material.opacity = THREE.MathUtils.lerp(0.88, 0.004, mix);
        mesh.material.depthWrite = backgroundDepthWrite;
        mesh.visible = backgroundVisible;
        if (mesh.userData.halo) {
          mesh.userData.halo.material.opacity = THREE.MathUtils.lerp(0.14, 0, mix);
          mesh.userData.halo.visible = backgroundVisible;
        }
      });
      nodeLabelSprites.forEach((label) => { label.material.opacity = THREE.MathUtils.lerp(0.88, 0, mix); label.visible = backgroundVisible; });
      megaCoronas.forEach((corona) => { corona.material.opacity = THREE.MathUtils.lerp(0.16, 0, mix); corona.visible = backgroundVisible; });
      planeLabelSprites.forEach((label) => { label.material.opacity = THREE.MathUtils.lerp(0.88, 0, mix); label.visible = backgroundVisible; });
      if (ringMesh) { ringMesh.material.opacity = THREE.MathUtils.lerp(clusterMode ? 0.2 : 0.24, 0, mix); ringMesh.visible = backgroundVisible; }
      if (galacticArmMesh) { galacticArmMesh.material.opacity = THREE.MathUtils.lerp(0.3, 0, mix); galacticArmMesh.visible = backgroundVisible; }
      if (galacticArmAnchors) { galacticArmAnchors.material.opacity = THREE.MathUtils.lerp(0.46, 0, mix); galacticArmAnchors.visible = backgroundVisible; }
      if (linkMesh) { linkMesh.material.opacity = THREE.MathUtils.lerp(baseLinkOpacity, 0, mix); linkMesh.visible = backgroundVisible; }
      helix.material.opacity = THREE.MathUtils.lerp(0.78, 0.56, mix);
      particles.material.opacity = THREE.MathUtils.lerp(0.88, 0, mix);
      particles.visible = backgroundVisible && !flatMode && animatedLinks.length > 0;
      evolutionGroup.visible = mix > 0.004;
    };

    const skillOrbitGroups = new Map();
    const skillOrbitOrder = [];
    const removeSkillOrbit = (parentId) => {
      const group = skillOrbitGroups.get(parentId);
      if (!group) return;
      group.userData.interactive.forEach((object) => {
        const index = interactive.indexOf(object);
        if (index >= 0) interactive.splice(index, 1);
        objectNode.delete(object.uuid);
        scenePositions.delete(object.userData.node.id);
      });
      group.traverse((object) => {
        object.userData?.labelTexture?.dispose?.();
        if (object.geometry && object.geometry !== skillGeometry) object.geometry.dispose();
        if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose());
        else object.material?.dispose?.();
      });
      scene.remove(group);
      skillOrbitGroups.delete(parentId);
      const orderIndex = skillOrbitOrder.indexOf(parentId);
      if (orderIndex >= 0) skillOrbitOrder.splice(orderIndex, 1);
    };
    const toggleSkillOrbit = (node) => {
      const skills = [...new Set((node.skills || []).filter(Boolean))].slice(0, 8);
      if (!skills.length || node.nodeType === "skill") return;
      if (skillOrbitGroups.has(node.id)) {
        removeSkillOrbit(node.id);
        return;
      }
      while (skillOrbitOrder.length >= 3) removeSkillOrbit(skillOrbitOrder[0]);
      const origin = scenePositions.get(node.id) || new THREE.Vector3(node.x, node.y, node.z);
      const meta = DOMAIN_META[node.category] || DOMAIN_META.人工智能;
      const group = new THREE.Group();
      group.userData.interactive = [];
      const orbitRadius = node.nodeType === "family" ? 4.6 : 3.2;
      const orbitPoints = new THREE.EllipseCurve(0, 0, orbitRadius, orbitRadius).getPoints(96).map((point) => new THREE.Vector3(point.x + origin.x, point.y + origin.y, origin.z));
      group.add(new THREE.LineLoop(
        new THREE.BufferGeometry().setFromPoints(orbitPoints),
        new THREE.LineBasicMaterial({ color: meta.color, transparent: true, opacity: 0.28, depthWrite: false, blending: THREE.AdditiveBlending }),
      ));
      const spokePositions = [];
      const spokeColors = [];
      skills.forEach((skill, index) => {
        const angle = index / skills.length * Math.PI * 2 - Math.PI / 2;
        const position = new THREE.Vector3(origin.x + Math.cos(angle) * orbitRadius, origin.y + Math.sin(angle) * orbitRadius, origin.z + 0.35);
        const evidence = node.skillEvidence?.find((item) => item.name === skill);
        const childNode = {
          id: `orbit:${node.id}:${skill}`,
          nodeType: "skill",
          title: skill,
          name: skill,
          category: node.category,
          family: node.family,
          parentId: node.id,
          supportCount: evidence?.count || 1,
          coverage: evidence?.coverage || null,
          period: node.period,
          description: node.nodeType === "family" ? `${skill} 是该岗位族的真实招聘技能要求。` : `${skill} 来自该岗位的技能标签。`,
        };
        scenePositions.set(childNode.id, position);
        const isCoreSkill = index < 3;
        const childColor = new THREE.Color(isCoreSkill ? 0xf1c96c : meta.color);
        const child = new THREE.Mesh(
          skillGeometry,
          new THREE.MeshStandardMaterial({ color: childColor, emissive: childColor, emissiveIntensity: isCoreSkill ? 0.9 : 0.42, roughness: 0.24, metalness: 0.2, transparent: true, opacity: 0.94 }),
        );
        child.position.copy(position);
        const childScale = index < 3 ? 0.92 : 0.66;
        child.scale.setScalar(childScale);
        child.userData = { node: childNode, baseScale: childScale };
        group.add(child);
        interactive.push(child);
        group.userData.interactive.push(child);
        objectNode.set(child.uuid, childNode);
        const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: childColor, transparent: true, opacity: isCoreSkill ? 0.38 : 0.22, blending: THREE.AdditiveBlending, depthWrite: false }));
        halo.position.copy(position);
        halo.scale.setScalar(isCoreSkill ? 2.7 : 1.9);
        group.add(halo);
        spokePositions.push(origin.x, origin.y, origin.z, position.x, position.y, position.z);
        spokeColors.push(childColor.r, childColor.g, childColor.b, childColor.r, childColor.g, childColor.b);
        const label = labelSprite(skill, isCoreSkill ? "#f1d98f" : meta.css, 0.48);
        label.position.set(position.x, position.y + 0.86, position.z);
        group.add(label);
      });
      if (spokePositions.length) {
        const spokeGeometry = new THREE.BufferGeometry();
        spokeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(spokePositions, 3));
        spokeGeometry.setAttribute("color", new THREE.Float32BufferAttribute(spokeColors, 3));
        group.add(new THREE.LineSegments(spokeGeometry, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.7, depthWrite: false, blending: THREE.AdditiveBlending })));
      }
      scene.add(group);
      skillOrbitGroups.set(node.id, group);
      skillOrbitOrder.push(node.id);
    };

    const raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 1.2;
    const pointer = new THREE.Vector2(9, 9);
    let hoveredObject = null;
    let raycastPending = false;
    const resolveNode = (hit) => hit?.object?.isInstancedMesh ? hit.object.userData.nodes?.[hit.instanceId] : objectNode.get(hit?.object?.uuid);
    const adjacency = new Map();
    selectionLinkRecords.forEach((link, index) => {
      if (!adjacency.has(link.source)) adjacency.set(link.source, []);
      if (!adjacency.has(link.target)) adjacency.set(link.target, []);
      adjacency.get(link.source).push(index);
      adjacency.get(link.target).push(index);
    });
    const skillNodesByTitle = new Map();
    visibleNodes.filter((node) => node.nodeType === "skill").forEach((node) => {
      if (!skillNodesByTitle.has(node.title)) skillNodesByTitle.set(node.title, []);
      skillNodesByTitle.get(node.title).push(node);
    });
    const otherEnd = (link, id) => link.source === id ? link.target : link.source;
    const buildCrossPlaneLinks = (node) => {
      if (flatMode || !wormholeMode || !["family", "job"].includes(node?.nodeType) || relationLens === "job_skill") return [];
      const sourceSkills = new Set((node.skills || []).filter(Boolean));
      if (sourceSkills.size < 2) return [];
      const candidates = [];
      visibleNodes.forEach((candidate) => {
        if (candidate.id === node.id || candidate.nodeType !== node.nodeType || candidate.period === node.period) return;
        const candidateSkills = new Set((candidate.skills || []).filter(Boolean));
        const sharedSkills = [...sourceSkills].filter((skill) => candidateSkills.has(skill));
        if (sharedSkills.length < 2) return;
        const similarity = sharedSkills.length / Math.max(1, new Set([...sourceSkills, ...candidateSkills]).size);
        if (similarity < 0.12) return;
        const candidatePosition = scenePositions.get(candidate.id) || new THREE.Vector3(candidate.x, candidate.y, candidate.z);
        candidates.push({
          candidate,
          candidatePosition,
          similarity,
          sharedSkills,
          differentCareer: (candidate.family || candidate.title) !== (node.family || node.title),
        });
      });
      const makeLink = (item, type) => {
        const chronological = type === "talent_mobility" && String(item.candidate.period) < String(node.period);
        return {
          id: `focus:${type}:${node.id}:${item.candidate.id}`,
          source: chronological ? item.candidate.id : node.id,
          target: chronological ? node.id : item.candidate.id,
          type,
          weight: item.similarity,
          confidence: item.similarity,
          skill: item.sharedSkills.slice(0, 2).join(" / "),
          sharedSkills: item.sharedSkills.slice(0, 8),
          inferred: true,
          focusOnly: true,
          sourceNode: chronological ? item.candidate : node,
          targetNode: chronological ? node : item.candidate,
          sourcePosition: chronological ? item.candidatePosition : (scenePositions.get(node.id) || new THREE.Vector3(node.x, node.y, node.z)),
          targetPosition: chronological ? (scenePositions.get(node.id) || new THREE.Vector3(node.x, node.y, node.z)) : item.candidatePosition,
        };
      };
      const ranked = candidates.sort((left, right) => right.similarity - left.similarity || left.candidate.id.localeCompare(right.candidate.id));
      if (relationLens === "similarity") return ranked.filter((item) => item.similarity >= 0.24).slice(0, 16).map((item) => makeLink(item, "job_similarity"));
      if (relationLens === "combination") return ranked.slice(0, 20).map((item) => makeLink(item, "shared_skill"));
      if (relationLens === "mobility") return ranked.filter((item) => item.differentCareer && item.similarity >= 0.18).slice(0, 16).map((item) => makeLink(item, "talent_mobility"));
      const similarityLinks = ranked.filter((item) => item.similarity >= 0.24).slice(0, 6).map((item) => makeLink(item, "job_similarity"));
      const combinationLinks = ranked.slice(0, 6).map((item) => makeLink(item, "shared_skill"));
      const mobilityLinks = ranked.filter((item) => item.differentCareer && item.similarity >= 0.18).slice(0, 6).map((item) => makeLink(item, "talent_mobility"));
      return [...similarityLinks, ...combinationLinks, ...mobilityLinks];
    };
    const semanticRelations = (node, includeCrossPlane = false) => {
      const primary = new Set(node ? [node.id] : []);
      const related = new Set(primary);
      const requiredSkills = new Set();
      const similarJobs = new Set();
      const sameSkillJobs = new Set();
      const mobilityJobs = new Set();
      if (!node) return { primary, related, requiredSkills, similarJobs, sameSkillJobs, mobilityJobs, jobCount: 0, skillCount: 0 };
      const direct = (adjacency.get(node.id) || []).map((index) => selectionLinkRecords[index]);
      if (node.nodeType === "job") {
        direct.filter((link) => link.type === "job_requires_skill").forEach((link) => {
          const neighborId = otherEnd(link, node.id);
          requiredSkills.add(neighborId);
          primary.add(neighborId);
          related.add(neighborId);
        });
        direct.filter((link) => link.type === "job_similarity").forEach((link) => {
          const neighborId = otherEnd(link, node.id);
          similarJobs.add(neighborId);
          related.add(neighborId);
        });
        direct.filter((link) => link.type === "possible_fusion").forEach((link) => {
          const neighborId = otherEnd(link, node.id);
          similarJobs.add(neighborId);
          related.add(neighborId);
        });
        direct.filter((link) => link.type === "talent_mobility").forEach((link) => {
          const neighborId = otherEnd(link, node.id);
          mobilityJobs.add(neighborId);
          related.add(neighborId);
        });
        [...requiredSkills].map((id) => nodeById.get(id)).filter(Boolean).forEach((skillNode) => {
          (skillNodesByTitle.get(skillNode.title) || []).forEach((matchingSkill) => {
            related.add(matchingSkill.id);
            (adjacency.get(matchingSkill.id) || []).map((index) => selectionLinkRecords[index])
              .filter((link) => link.type === "job_requires_skill")
              .forEach((link) => {
                const relatedJobId = otherEnd(link, matchingSkill.id);
                if (relatedJobId !== node.id) sameSkillJobs.add(relatedJobId);
                related.add(relatedJobId);
              });
          });
        });
      } else if (node.nodeType === "skill") {
        (skillNodesByTitle.get(node.title) || [node]).forEach((matchingSkill) => {
          requiredSkills.add(matchingSkill.id);
          primary.add(matchingSkill.id);
          related.add(matchingSkill.id);
          (adjacency.get(matchingSkill.id) || []).map((index) => selectionLinkRecords[index])
            .filter((link) => ["job_requires_skill", "requires_skill"].includes(link.type))
            .forEach((link) => {
              const neighborId = otherEnd(link, matchingSkill.id);
              if (nodeById.get(neighborId)?.nodeType === "job") sameSkillJobs.add(neighborId);
              primary.add(neighborId);
              related.add(neighborId);
            });
        });
      } else {
        direct.forEach((link) => {
          const neighborId = otherEnd(link, node.id);
          primary.add(neighborId);
          related.add(neighborId);
        });
      }
      const crossPlaneLinks = includeCrossPlane ? buildCrossPlaneLinks(node) : [];
      crossPlaneLinks.forEach((link) => {
        const neighborId = otherEnd(link, node.id);
        related.add(neighborId);
        if (link.type === "shared_skill") sameSkillJobs.add(neighborId);
        else if (link.type === "talent_mobility") mobilityJobs.add(neighborId);
        else similarJobs.add(neighborId);
      });
      const relatedNodes = [...related].map((id) => nodeById.get(id)).filter(Boolean);
      return {
        primary,
        related,
        requiredSkills,
        similarJobs,
        sameSkillJobs,
        mobilityJobs,
        crossPlaneLinks,
        jobCount: relatedNodes.filter((item) => item.nodeType === "job").length,
        skillCount: relatedNodes.filter((item) => item.nodeType === "skill").length,
      };
    };
    let lockedNodeId = null;
    const instanceMatrix = new THREE.Matrix4();
    const instanceQuaternion = new THREE.Quaternion();
    const updateInstanceVisibility = (mesh, semantic, locked, kind) => {
      mesh.userData.nodes.forEach((item, index) => {
        const visible = !locked || semantic.related.has(item.id);
        const position = scenePositions.get(item.id) || new THREE.Vector3(item.x, item.y, item.z);
        const scale = kind === "job"
          ? (RING_SCALE[item.ringType] || 0.8)
          : 0.72 + Math.min(0.52, Number(item.coverage || 0) / 150);
        const actualScale = visible ? scale : 0.0001;
        instanceMatrix.compose(position, instanceQuaternion, new THREE.Vector3(actualScale, actualScale, actualScale));
        mesh.setMatrixAt(index, instanceMatrix);
        if (mesh.userData.halo) {
          const haloScale = visible ? scale * 1.72 : 0.0001;
          instanceMatrix.compose(position, instanceQuaternion, new THREE.Vector3(haloScale, haloScale, haloScale));
          mesh.userData.halo.setMatrixAt(index, instanceMatrix);
        }
      });
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.userData.halo) mesh.userData.halo.instanceMatrix.needsUpdate = true;
    };
    const relationLabel = (link) => {
      const base = RELATION_LABELS[link.type] || link.label || "关联关系";
      const skillNode = [link.sourceNode, link.targetNode].find((item) => item?.nodeType === "skill");
      if (["job_requires_skill", "requires_skill", "shared_skill"].includes(link.type) && skillNode?.title) return `${base} · ${skillNode.title}`;
      if (link.type === "shared_skill" && link.skill) return `${base} · ${link.skill}`;
      if (link.focusOnly && link.sharedSkills?.length) return `${base} · ${link.sharedSkills.slice(0, 2).join(" / ")}`;
      const confidence = Number(link.confidence || link.weight || 0);
      return confidence > 0 && confidence <= 1 && ["job_similarity", "possible_fusion", "talent_mobility"].includes(link.type)
        ? `${base} · ${Math.round(confidence * 100)}%`
        : base;
    };
    const highlightRelations = (node, locked = false) => {
      const semantic = semanticRelations(node, locked);
      clearHighlightLabels();
      if (linkMesh) {
        linkMesh.material.opacity = node ? (locked ? 0 : 0.006) : baseLinkOpacity;
      }
      const activeLinkIndexes = new Set();
      if (node) {
        semantic.related.forEach((id) => (adjacency.get(id) || []).forEach((index) => {
          const link = selectionLinkRecords[index];
          if (semantic.related.has(link.source) && semantic.related.has(link.target)
            && (["job_requires_skill", "job_similarity", "shared_skill"].includes(link.type)
              || semantic.primary.has(link.source) || semantic.primary.has(link.target))) {
            activeLinkIndexes.add(index);
          }
        }));
      }
      let highlighted = 0;
      let labelCount = 0;
      const labeledTypes = new Set();
      const labeledTexts = new Set();
      const labelRects = [];
      const placeRelationLabel = (label, x, y, z) => {
        const candidates = [
          [0, 0], [0, 2.25], [0, -2.25], [5.1, 0], [-5.1, 0],
          [5.1, 2.25], [-5.1, 2.25], [5.1, -2.25], [-5.1, -2.25],
          [0, 4.5], [0, -4.5], [10.2, 0], [-10.2, 0],
        ];
        const width = 9.2;
        const height = 1.95;
        const overlaps = (rect) => labelRects.some((other) => !(
          rect.right + 0.42 < other.left
          || rect.left - 0.42 > other.right
          || rect.top + 0.34 < other.bottom
          || rect.bottom - 0.34 > other.top
        ));
        let chosen = candidates.at(-1);
        for (const candidate of candidates) {
          const rect = {
            left: x + candidate[0] - width / 2,
            right: x + candidate[0] + width / 2,
            bottom: y + candidate[1] - height / 2,
            top: y + candidate[1] + height / 2,
          };
          if (!overlaps(rect)) {
            chosen = candidate;
            labelRects.push(rect);
            break;
          }
        }
        if (labelRects.length <= labelCount) {
          labelRects.push({
            left: x + chosen[0] - width / 2,
            right: x + chosen[0] + width / 2,
            bottom: y + chosen[1] - height / 2,
            top: y + chosen[1] + height / 2,
          });
        }
        label.position.set(x + chosen[0], y + chosen[1], z + 0.62 + labelCount * 0.025);
      };
      const orderedLinks = [...activeLinkIndexes].map((index) => selectionLinkRecords[index]).concat(semantic.crossPlaneLinks || []).sort((left, right) => {
        const leftDirect = left.source === node?.id || left.target === node?.id ? 1 : 0;
        const rightDirect = right.source === node?.id || right.target === node?.id ? 1 : 0;
        return rightDirect - leftDirect || Number(right.weight || right.confidence || 0) - Number(left.weight || left.confidence || 0);
      });
      for (const link of orderedLinks) {
        if (highlighted >= highlightCapacity) break;
        const color = relationColor(link);
        const source = link.sourcePosition;
        const target = link.targetPosition;
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const xyLength = Math.max(0.001, Math.hypot(dx, dy));
        const arc = Math.min(5, Math.max(0.65, xyLength * 0.09));
        const controlX = (source.x + target.x) * 0.5 - dy / xyLength * arc;
        const controlY = (source.y + target.y) * 0.5 + dx / xyLength * arc;
        const planeDistance = Math.abs(target.z - source.z);
        const controlZ = (source.z + target.z) * 0.5
          + (planeDistance < 1 ? arc * 0.35 : Math.min(13, 2.4 + planeDistance * 0.16));
        for (let segment = 0; segment < highlightSegments; segment += 1) {
          const t0 = segment / highlightSegments;
          const t1 = (segment + 1) / highlightSegments;
          const inverse0 = 1 - t0;
          const inverse1 = 1 - t1;
          const offset = (highlighted * highlightSegments + segment) * 6;
          highlightPositions.set([
            inverse0 * inverse0 * source.x + 2 * inverse0 * t0 * controlX + t0 * t0 * target.x,
            inverse0 * inverse0 * source.y + 2 * inverse0 * t0 * controlY + t0 * t0 * target.y,
            inverse0 * inverse0 * source.z + 2 * inverse0 * t0 * controlZ + t0 * t0 * target.z,
            inverse1 * inverse1 * source.x + 2 * inverse1 * t1 * controlX + t1 * t1 * target.x,
            inverse1 * inverse1 * source.y + 2 * inverse1 * t1 * controlY + t1 * t1 * target.y,
            inverse1 * inverse1 * source.z + 2 * inverse1 * t1 * controlZ + t1 * t1 * target.z,
          ], offset);
          highlightColors.set([color.r, color.g, color.b, color.r, color.g, color.b], offset);
        }
        const isDirect = link.source === node?.id || link.target === node?.id;
        const labelText = relationLabel(link);
        if (labelCount < 6 && !labeledTexts.has(labelText) && (isDirect || !labeledTypes.has(link.type))) {
          const label = edgeLabelSprite(labelText, `#${color.getHexString()}`);
          placeRelationLabel(label, controlX, controlY, controlZ);
          highlightLabelGroup.add(label);
          labeledTypes.add(link.type);
          labeledTexts.add(labelText);
          labelCount += 1;
        }
        highlighted += 1;
      }
      highlightGeometry.setDrawRange(0, highlighted * highlightSegments * 2);
      highlightGeometry.attributes.position.needsUpdate = highlighted > 0;
      highlightGeometry.attributes.color.needsUpdate = highlighted > 0;
      highlightMesh.material.opacity = highlighted ? 0.94 : 0;
      focusHalo.visible = Boolean(node);
      if (node) {
        const position = scenePositions.get(node.id) || new THREE.Vector3(node.x, node.y, node.z);
        focusHalo.position.copy(position);
        focusHalo.scale.setScalar(node.nodeType === "family" ? 7.2 : node.nodeType === "job" ? 4.5 : 4);
      }
      particles.material.opacity = node ? (locked ? 0 : 0.08) : 0.88;
      if (wormholeMode) {
        nodeMeshes.forEach((mesh, id) => {
          const baseOpacity = mesh.userData.node?.nodeType === "family" ? 0.98 : mesh.userData.node?.nodeType === "signal" ? 0.7 : 0.82;
          mesh.visible = !locked || semantic.related.has(id);
          mesh.material.opacity = !node ? baseOpacity : semantic.related.has(id) ? 1 : 0.025;
          if ("emissiveIntensity" in mesh.material) {
            mesh.material.emissiveIntensity = !node ? 0.35 : semantic.primary.has(id) ? 0.95 : semantic.related.has(id) ? 0.58 : 0.01;
          }
        });
        megaCoronas.forEach((corona) => {
          corona.visible = !locked || semantic.related.has(corona.userData.nodeId);
          corona.material.opacity = !node ? 0.16 : semantic.related.has(corona.userData.nodeId) ? 0.3 : 0.01;
        });
        nodeLabelSprites.forEach((label) => {
          const isRelated = semantic.related.has(label.userData.nodeId);
          label.visible = !locked || isRelated;
          label.material.opacity = !node ? 0.88 : isRelated ? 0.96 : 0.025;
        });
        jobInstances.forEach((mesh) => {
          updateInstanceVisibility(mesh, semantic, locked, "job");
          mesh.userData.nodes.forEach((jobNode, index) => {
            const base = mesh.userData.baseColors[index] || new THREE.Color(DOMAIN_META[jobNode.category]?.color || 0x54c7ec);
            const color = !node
              ? base
              : jobNode.id === node.id
                ? new THREE.Color(0xffffff)
                : semantic.similarJobs.has(jobNode.id)
                  ? base.clone().lerp(new THREE.Color(0x8bb8ff), 0.64)
                  : semantic.mobilityJobs.has(jobNode.id)
                    ? base.clone().lerp(new THREE.Color(0xb99aff), 0.66)
                  : semantic.sameSkillJobs.has(jobNode.id)
                    ? base.clone().lerp(new THREE.Color(0x79d991), 0.58)
                    : semantic.primary.has(jobNode.id)
                      ? base.clone().lerp(new THREE.Color(0xbfe7ff), 0.38)
                      : semantic.related.has(jobNode.id)
                        ? base.clone().multiplyScalar(0.92)
                        : base.clone().multiplyScalar(0.025);
            mesh.setColorAt(index, color);
          });
          if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
          mesh.material.opacity = node ? 1 : 0.88;
        });
        skillInstances.forEach((mesh) => {
          updateInstanceVisibility(mesh, semantic, locked, "skill");
          mesh.userData.nodes.forEach((skillNode, index) => {
            const base = mesh.userData.baseColors[index] || new THREE.Color(0x79d991);
            const color = !node
              ? base
              : skillNode.id === node.id
                ? new THREE.Color(0xffffff)
                : semantic.requiredSkills.has(skillNode.id)
                  ? base.clone().lerp(new THREE.Color(0xffd166), 0.52)
                  : semantic.primary.has(skillNode.id)
                    ? base.clone().lerp(new THREE.Color(0xc7ffe1), 0.48)
                    : semantic.related.has(skillNode.id)
                      ? base.clone().multiplyScalar(0.95)
                      : base.clone().multiplyScalar(0.02);
            mesh.setColorAt(index, color);
            mesh.userData.halo?.setColorAt(index, color);
          });
          if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
          if (mesh.userData.halo?.instanceColor) mesh.userData.halo.instanceColor.needsUpdate = true;
          mesh.material.opacity = node ? 1 : 0.88;
          if (mesh.userData.halo) mesh.userData.halo.material.opacity = node ? 0.1 : 0.14;
        });
      }
      return semantic;
    };
    const inspectPointer = (clientX, clientY) => {
      raycastPending = false;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(interactive, false)[0];
      const node = resolveNode(hit);
      const previousNodeId = hoverRef.current?.node?.id || null;
      const nextNodeId = node?.id || null;
      if (previousNodeId === nextNodeId) {
        if (node) setHover((current) => current ? { ...current, x: clientX, y: clientY } : current);
        return;
      }
      if (hoveredObject && !hoveredObject.isInstancedMesh) hoveredObject.scale.setScalar(hoveredObject.userData.baseScale);
      hoveredObject = hit?.object || null;
      if (hoveredObject && !hoveredObject.isInstancedMesh) hoveredObject.scale.setScalar(hoveredObject.userData.baseScale * 1.24);
      renderer.domElement.style.cursor = node ? "pointer" : "grab";
      const semantic = lockedNodeId ? semanticRelations(node) : highlightRelations(node);
      hoverRef.current = node ? {
        node,
        x: clientX,
        y: clientY,
        relationSummary: node.nodeType === "job"
          ? `${semantic.requiredSkills.size} 个所需技能 · ${semantic.similarJobs.size} 个相似岗位 · ${semantic.sameSkillJobs.size} 个同技能岗位`
          : node.nodeType === "skill"
            ? `${semantic.sameSkillJobs.size} 个岗位采用该技能 · 跨 ${semantic.requiredSkills.size} 个时间技能节点`
            : "悬停高亮直接关系",
      } : null;
      setHover(hoverRef.current);
    };
    let lastRaycastAt = 0;
    let pointerDownAt = null;
    let pointerDragged = false;
    const onPointerDown = (event) => {
      pointerDownAt = { x: event.clientX, y: event.clientY };
      pointerDragged = false;
    };
    const onPointerMove = (event) => {
      if (timeTravelingRef.current) return;
      if (pointerDownAt && event.buttons) {
        pointerDragged = pointerDragged || Math.hypot(event.clientX - pointerDownAt.x, event.clientY - pointerDownAt.y) > 5;
        if (pointerDragged) {
          hoverRef.current = null;
          setHover(null);
          return;
        }
      }
      if (evolutionFocusActiveRef.current) {
        if (hoverRef.current) {
          hoverRef.current = null;
          setHover(null);
        }
        return;
      }
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      const now = performance.now();
      if (!raycastPending && now - lastRaycastAt >= 34) {
        raycastPending = true;
        requestAnimationFrame(() => {
          lastRaycastAt = performance.now();
          const hoverX = Math.max(8, Math.min(event.clientX - rect.left, rect.width - 308));
          const hoverY = Math.max(92, Math.min(event.clientY - rect.top, rect.height - 164));
          inspectPointer(hoverX, hoverY);
        });
      }
    };
    const clearLockedFocus = () => {
      lockedNodeId = null;
      while (skillOrbitOrder.length) removeSkillOrbit(skillOrbitOrder[0]);
      highlightRelations(null);
    };
    const onPointerLeave = () => {
      hoverRef.current = null;
      setHover(null);
      if (!lockedNodeId) highlightRelations(null);
    };
    const onClick = () => {
      if (pointerDragged) {
        pointerDragged = false;
        pointerDownAt = null;
        return;
      }
      pointerDownAt = null;
      const node = hoverRef.current?.node;
      if (!node) {
        if (lockedNodeId) {
          clearLockedFocus();
          onSelect?.(null);
        }
        return;
      }
      if (evolutionFocusActiveRef.current) {
        pointerDownAt = null;
        onEvolutionFocusChange?.(null);
        return;
      }
      if (jobEvolutionModeRef.current && ["job", "family"].includes(node.nodeType)) {
        onEvolutionFocusChange?.(node);
        return;
      }
      if (lockedNodeId === node.id) {
        clearLockedFocus();
        onSelect?.(null);
        return;
      }
      while (skillOrbitOrder.length) removeSkillOrbit(skillOrbitOrder[0]);
      if (["integrated", "job_skill", "combination"].includes(relationLens)) toggleSkillOrbit(node);
      lockedNodeId = node.id;
      highlightRelations(node, true);
      focusNode(node);
    };
    const onDoubleClick = () => !jobEvolutionModeRef.current && hoverRef.current?.node?.nodeType === "family" && onDrill?.(hoverRef.current.node);
    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointermove", onPointerMove);
    renderer.domElement.addEventListener("pointerleave", onPointerLeave);
    renderer.domElement.addEventListener("click", onClick);
    renderer.domElement.addEventListener("dblclick", onDoubleClick);

    const temporalPeriods = renderPeriod === "all"
      ? visibleLayers.map((layer) => layer.id).filter((id) => densityLayout.periodMap.has(id))
      : [];
    const clampTemporalPosition = (position) => {
      const next = Number(position);
      return Math.max(0, Math.min(Number.isFinite(next) ? next : 0, Math.max(0, temporalPeriods.length - 1)));
    };
    const temporalState = {
      target: clampTemporalPosition(temporalPositionRef.current),
      current: clampTemporalPosition(temporalPositionRef.current),
      scrubbing: Boolean(temporalScrubbingRef.current),
    };
    const temporalCenterZ = (position) => {
      if (!temporalPeriods.length) return middleZ;
      const clamped = clampTemporalPosition(position);
      const leftIndex = Math.floor(clamped);
      const rightIndex = Math.min(temporalPeriods.length - 1, Math.ceil(clamped));
      const fraction = clamped - leftIndex;
      const leftZ = densityLayout.periodMap.get(temporalPeriods[leftIndex])?.centerZ ?? middleZ;
      const rightZ = densityLayout.periodMap.get(temporalPeriods[rightIndex])?.centerZ ?? leftZ;
      return THREE.MathUtils.lerp(leftZ, rightZ, fraction);
    };

    const context = {
      camera,
      controls,
      renderer,
      positions: scenePositions,
      temporalState,
      desiredCamera: cameraSeed?.desiredPosition || camera.position.clone(),
      desiredTarget: cameraSeed?.desiredTarget || controls.target.clone(),
      reset() {
        this.desiredTarget.set(0, 0, middleZ);
        this.desiredCamera.set(flatMode ? 0.01 : 68, flatMode ? 0.01 : 42, middleZ - (flatMode ? 108 : 58));
      },
      clearSelection() {
        clearLockedFocus();
      },
      setTemporalState(position, scrubbing) {
        this.temporalState.target = clampTemporalPosition(position);
        this.temporalState.scrubbing = Boolean(scrubbing);
      },
      setEvolutionState(active, profile, position) {
        const nextActive = Boolean(active && profile?.frames?.length);
        const profileChanged = Boolean(profile && profile !== evolutionState.profile);
        if (profileChanged) rebuildEvolutionOverlay(profile);
        const nextPosition = Math.max(0, Math.min(
          Number(position || 0),
          Math.max(0, (profile?.frames?.length || 1) - 1),
        ));
        const positionChanged = Math.abs(nextPosition - evolutionState.targetPosition) > 0.001;
        evolutionState.active = nextActive;
        evolutionState.targetMix = nextActive ? 1 : 0;
        evolutionState.targetPosition = nextPosition;
        if (nextActive && (profileChanged || positionChanged)) {
          evolutionState.userCameraOverride = false;
          evolutionState.motionEnergy = Math.max(evolutionState.motionEnergy, profileChanged ? 0.72 : 1);
        }
        if (nextActive && !evolutionState.cameraBackup) {
          evolutionState.cameraBackup = {
            position: this.desiredCamera.clone(),
            target: this.desiredTarget.clone(),
          };
          clearLockedFocus();
          hoverRef.current = null;
          setHover(null);
        }
        if (!nextActive && evolutionState.cameraBackup) {
          this.desiredCamera.copy(evolutionState.cameraBackup.position);
          this.desiredTarget.copy(evolutionState.cameraBackup.target);
          evolutionState.cameraBackup = null;
          evolutionState.userCameraOverride = false;
        }
        updateEvolutionOverlay(evolutionState.currentPosition);
      },
    };
    const syncDesiredView = () => {
      context.desiredCamera.copy(camera.position);
      context.desiredTarget.copy(controls.target);
    };
    const onControlsStart = () => {
      controlsInteracting = true;
      if (evolutionState.active) evolutionState.userCameraOverride = true;
      renderer.domElement.style.cursor = "grabbing";
    };
    const onControlsChange = () => {
      if (controlsInteracting) syncDesiredView();
    };
    const onControlsEnd = () => {
      syncDesiredView();
      if (evolutionState.active) evolutionState.followOffset.copy(camera.position).sub(controls.target);
      controlsInteracting = false;
      renderer.domElement.style.cursor = hoverRef.current?.node ? "pointer" : "grab";
    };
    controls.addEventListener("start", onControlsStart);
    controls.addEventListener("change", onControlsChange);
    controls.addEventListener("end", onControlsEnd);
    cameraSeedRef.current = null;
    sceneRef.current = context;
    context.setEvolutionState(
      jobEvolutionModeRef.current,
      evolutionProfileRef.current,
      evolutionPositionRef.current,
    );
    context.setTemporalState(temporalPositionRef.current, temporalScrubbingRef.current);
    let frame = 0;
    let elapsed = 0;
    const clock = new THREE.Clock();
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    const relationTravelSpeed = 0.22;
    const render = () => {
      frame = requestAnimationFrame(render);
      const delta = Math.min(0.05, clock.getDelta());
      elapsed += delta;
      const travelingNow = timeTravelingRef.current;
      const motionFactor = reducedMotion ? 0.18 : 1;
      const transitionEase = 1 - Math.exp(-(reducedMotion ? 13 : 7.5) * delta);
      const lateEvolutionStart = evolutionState.profile?.frames?.findIndex((item) => item.period >= "2026-06") ?? -1;
      const inLateEvolutionRange = lateEvolutionStart >= 0
        && (evolutionState.targetPosition >= lateEvolutionStart - 0.02 || evolutionState.currentPosition >= lateEvolutionStart - 0.02);
      const timelineResponse = inLateEvolutionRange ? (reducedMotion ? 7 : 5.2) : (reducedMotion ? 15 : 11);
      const timelineEase = 1 - Math.exp(-timelineResponse * delta);
      evolutionState.mix = THREE.MathUtils.lerp(evolutionState.mix, evolutionState.targetMix, transitionEase);
      const previousEvolutionPosition = evolutionState.currentPosition;
      evolutionState.currentPosition = THREE.MathUtils.lerp(evolutionState.currentPosition, evolutionState.targetPosition, timelineEase);
      const timelineVelocity = Math.abs(evolutionState.currentPosition - previousEvolutionPosition);
      evolutionState.motionEnergy = Math.max(
        evolutionState.motionEnergy * Math.exp(-(reducedMotion ? 7 : 3.6) * delta),
        Math.min(1, timelineVelocity * (reducedMotion ? 6 : 24)),
      );
      if (Math.abs(evolutionState.mix - evolutionState.targetMix) < 0.001) evolutionState.mix = evolutionState.targetMix;
      if (Math.abs(evolutionState.currentPosition - evolutionState.targetPosition) < 0.002) evolutionState.currentPosition = evolutionState.targetPosition;
      applyEvolutionMix(evolutionState.mix);
      if (renderPeriod === "all" && !evolutionState.active && temporalPeriods.length > 1) {
        const temporalEase = 1 - Math.exp(-(temporalState.scrubbing ? 16 : 7) * delta);
        temporalState.current = THREE.MathUtils.lerp(temporalState.current, temporalState.target, temporalEase);
        if (Math.abs(temporalState.current - temporalState.target) < 0.001) temporalState.current = temporalState.target;
        const targetZ = temporalCenterZ(temporalState.current);
        const cameraOffsetZ = context.desiredCamera.z - context.desiredTarget.z;
        context.desiredTarget.z = THREE.MathUtils.lerp(context.desiredTarget.z, targetZ, temporalEase);
        context.desiredCamera.z = THREE.MathUtils.lerp(context.desiredCamera.z, targetZ + cameraOffsetZ, temporalEase);
      }
      if (evolutionGroup.visible) {
        updateEvolutionOverlay(evolutionState.currentPosition);
        if (evolutionState.core) {
          evolutionState.core.rotation.x += delta * 0.2 * motionFactor;
          evolutionState.core.rotation.y += delta * 0.34 * motionFactor;
          const corePulse = 1 + Math.sin(elapsed * 2.8) * 0.045;
          evolutionState.core.scale.setScalar(corePulse);
        }
        if (evolutionState.coreHalo) {
          const haloPulse = 1 + Math.sin(elapsed * 2.2 + 0.8) * 0.08;
          evolutionState.coreHalo.scale.setScalar(8.2 * haloPulse);
          evolutionState.coreHalo.material.opacity = evolutionState.mix * (
            0.3 + evolutionState.motionEnergy * 0.25 + Math.max(0, Math.sin(elapsed * 2.1)) * 0.06
          );
        }
        if (evolutionState.auraParticles) {
          const breath = 0.5 + Math.sin(elapsed * 1.45) * 0.5;
          evolutionState.auraParticles.rotation.z += delta * 0.055 * motionFactor;
          evolutionState.auraParticles.rotation.x = Math.sin(elapsed * 0.22) * 0.1;
          evolutionState.auraParticles.material.opacity = evolutionState.mix * (0.09 + breath * 0.08 + evolutionState.motionEnergy * 0.16);
          evolutionState.auraParticles.material.size = (compact ? 0.34 : 0.46) * (0.92 + breath * 0.16 + evolutionState.motionEnergy * 0.12);
        }
        if (evolutionState.pulseRing) {
          const ringPhase = (elapsed * 0.28 + evolutionState.currentPosition * 0.16) % 1;
          evolutionState.pulseRing.scale.setScalar(1 + ringPhase * (1.8 + evolutionState.motionEnergy * 1.2));
          evolutionState.pulseRing.material.opacity = evolutionState.mix * (1 - ringPhase) * (0.035 + evolutionState.motionEnergy * 0.22);
        }
        evolutionState.branches.forEach((branch) => {
          const shimmer = 0.88 + Math.sin(elapsed * 3.2 + branch.index * 0.63) * 0.12;
          branch.halo.scale.setScalar((branch.index < 6 ? 2.6 : 1.8) * shimmer);
          branch.halo.material.opacity *= 0.88 + evolutionState.motionEnergy * 0.12;
        });
        evolutionState.followers.forEach((follower, index) => {
          const branch = evolutionState.branches[(index * 4 + Math.floor(evolutionState.currentPosition)) % Math.max(1, evolutionState.branches.length)];
          if (!branch) return;
          const pointCount = branch.positions.length / 3;
          const progress = (elapsed * (0.18 + index * 0.025) + evolutionState.currentPosition * 0.12 + index * 0.31) % 1;
          const pointIndex = Math.min(pointCount - 1, Math.max(0, Math.floor(progress * (pointCount - 1))));
          follower.position.fromArray(branch.positions, pointIndex * 3);
          const flicker = 0.58 + Math.sin(elapsed * 7.2 + index * 2.1) * 0.18;
          follower.material.opacity = evolutionState.mix * (0.08 + evolutionState.motionEnergy * 0.58) * flicker;
          follower.scale.setScalar((index === 1 ? 1.65 : 1.28) * (0.92 + evolutionState.motionEnergy * 0.28));
        });
      }
      helix.rotation.z += delta * (travelingNow ? 0.52 : 0.07) * motionFactor;
      if (evolutionState.mix > 0.08) helix.material.opacity = 0.5 + evolutionState.motionEnergy * 0.18 + Math.max(0, Math.sin(elapsed * 1.6)) * 0.035;
      const targetFov = evolutionState.mix > 0.08 ? 50 : travelingNow ? 64 : 52;
      if (Math.abs(camera.fov - targetFov) > 0.05) {
        camera.fov = THREE.MathUtils.lerp(camera.fov, targetFov, 1 - Math.exp(-7 * delta));
        camera.updateProjectionMatrix();
      }
      megaCoronas.forEach((corona) => {
        corona.rotation.x += delta * 0.09 * motionFactor;
        corona.rotation.y += delta * 0.12 * motionFactor;
        const pulse = 1 + Math.sin(elapsed * 3 + corona.userData.pulseOffset) * 0.035;
        corona.scale.setScalar(corona.userData.baseScale * pulse);
      });
      if (particles.visible) {
        for (let index = 0; index < particleCount; index += 1) {
          const link = animatedLinks[index % animatedLinks.length];
          const t = (elapsed * relationTravelSpeed * motionFactor + index / Math.max(1, particleCount)) % 1;
          particlePositions[index * 3] = THREE.MathUtils.lerp(link.sourcePosition.x, link.targetPosition.x, t);
          particlePositions[index * 3 + 1] = THREE.MathUtils.lerp(link.sourcePosition.y, link.targetPosition.y, t);
          particlePositions[index * 3 + 2] = THREE.MathUtils.lerp(link.sourcePosition.z, link.targetPosition.z, t);
        }
        particleGeometry.attributes.position.needsUpdate = true;
      }
      const cameraEase = 1 - Math.exp(-4 * delta);
      if (!controlsInteracting) {
        camera.position.lerp(context.desiredCamera, cameraEase);
        controls.target.lerp(context.desiredTarget, cameraEase);
      }
      controls.update();
      renderer.render(scene, camera);
    };
    const resize = () => {
      const width = Math.max(1, mount.clientWidth);
      const height = Math.max(1, mount.clientHeight);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(mount);
    resize();
    render();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("pointerleave", onPointerLeave);
      renderer.domElement.removeEventListener("click", onClick);
      renderer.domElement.removeEventListener("dblclick", onDoubleClick);
      controls.removeEventListener("start", onControlsStart);
      controls.removeEventListener("change", onControlsChange);
      controls.removeEventListener("end", onControlsEnd);
      controls.dispose();
      scene.traverse((object) => {
        object.userData?.labelTexture?.dispose?.();
        object.geometry?.dispose?.();
        if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose());
        else object.material?.dispose?.();
      });
      glow.dispose();
      renderer.dispose();
      mount.replaceChildren();
      sceneRef.current = null;
    };
  }, [clusterMode, compact, denseOverviewPeriods, displayPlanes, domain, familyFocus, flatMode, focusNode, graph.links, onDrill, onEvolutionFocusChange, relationLens, renderPeriod, scenePositions, viewLevel, visibleLayers, visibleNodes, wormholeMode]);

  useEffect(() => {
    if (!selectedNodeId) sceneRef.current?.clearSelection?.();
  }, [selectedNodeId]);

  useEffect(() => {
    requestedPeriodRef.current = period;
    window.clearTimeout(periodTransitionRef.current);
    if (period === renderPeriod) {
      setPeriodTransitioning(false);
      return undefined;
    }
    if (period !== "all" && !graph.layers.some((item) => item.id === period)) return undefined;
    setPeriodTransitioning(true);
    const transitionDelay = timeTraveling ? 520 : 170;
    const context = sceneRef.current;
    const targetLayer = densityLayout.periodMap.get(period);
    if (context && targetLayer && renderPeriod === "all") {
      context.desiredTarget.set(0, 0, targetLayer.centerZ);
      context.desiredCamera.set(targetLayer.planeCount > 1 ? 42 : 4, targetLayer.planeCount > 1 ? 30 : 4, targetLayer.centerZ - (targetLayer.planeCount > 1 ? 74 : 36));
    }
    periodTransitionRef.current = window.setTimeout(() => {
      const context = sceneRef.current;
      const targetLayer = densityLayout.periodMap.get(period);
      const currentLayer = densityLayout.periodMap.get(renderPeriod);
      if (context && targetLayer && currentLayer) {
        const zShift = targetLayer.centerZ - currentLayer.centerZ;
        const shift = new THREE.Vector3(0, 0, zShift);
        cameraSeedRef.current = {
          position: context.camera.position.clone().add(shift),
          target: context.controls.target.clone().add(shift),
          desiredPosition: context.desiredCamera.clone().add(shift),
          desiredTarget: context.desiredTarget.clone().add(shift),
        };
      }
      setRenderPeriod(period);
    }, transitionDelay);
    const finish = window.setTimeout(() => setPeriodTransitioning(false), timeTraveling ? 980 : 560);
    return () => {
      window.clearTimeout(periodTransitionRef.current);
      window.clearTimeout(finish);
    };
  }, [densityLayout.periodMap, graph.layers, period, renderPeriod, timeTraveling]);

  useEffect(() => () => window.clearTimeout(periodTransitionRef.current), []);

  const adjustZoom = (factor) => {
    const context = sceneRef.current;
    if (!context) return;
    const offset = context.desiredCamera.clone().sub(context.desiredTarget).multiplyScalar(factor);
    context.desiredCamera.copy(context.desiredTarget).add(offset);
  };

  return (
    <div className={`three-graph career-canvas ${compact ? "compact" : ""} ${periodTransitioning ? "period-transitioning" : ""} ${timeTraveling ? "time-traveling" : ""} ${jobEvolutionMode ? "is-job-evolution" : ""}`}>
      <div ref={mountRef} className="three-mount" />
      {jobEvolutionMode && evolutionProfile && evolutionFrame && <aside className="job-evolution-hud" aria-live="polite">
        <header>
          <span>{evolutionProfile.demoType === "legacy" ? "既有岗位演进（演示精选）" : evolutionProfile.demoType === "emerging" ? "新岗位演进（演示精选）" : "岗位技能栈演进"}</span>
          <strong>{evolutionFrame.title}</strong>
          <small>{evolutionLayer?.label || evolutionFrame.period} · {evolutionProfile.family}</small>
        </header>
        <div className="job-evolution-changes">
          <p className="added"><b>新兴技能</b><span>{evolutionFrame.addedSkills.length ? evolutionFrame.addedSkills.slice(0, 4).join(" · ") : "本月结构稳定"}</span></p>
          <p className="declining"><b>减弱技能</b><span>{evolutionFrame.decliningSkills.length ? evolutionFrame.decliningSkills.slice(0, 3).join(" · ") : "暂无明显减弱"}</span></p>
          <p className="retired"><b>退出技能</b><span>{evolutionFrame.retiredSkills.length ? evolutionFrame.retiredSkills.slice(0, 3).join(" · ") : "暂无退出"}</span></p>
        </div>
        <div className="job-evolution-legend" aria-label="技能演进图例">
          <span data-state="retained">持续</span><span data-state="strengthened">增强</span><span data-state="added">新增</span><span data-state="declining">减弱</span><span data-state="retired">退出</span>
        </div>
        <footer>{evolutionProfile.containsSimulation ? "真实 JD 技能证据 + 确定性时间推演（演示数据）" : "基于真实 JD 月度证据"}</footer>
      </aside>}
      {jobEvolutionMode && !evolutionProfile && <aside className="job-evolution-picker-hint">
        <span>自由岗位演进</span>
        <strong>搜索或点击任意岗位</strong>
        <small>选定后将聚焦其 2025-09 至 2026-08 技能栈变化</small>
      </aside>}
      {previewLayer && <div className="wormhole-target-preview"><span>目标黄道面</span><strong>{previewLayer.label}</strong><small>{previewLayer.jobCount || 0} 个岗位 · {previewLayer.skillCount || 0} 个技能</small></div>}
      {timeTraveling && <div className="time-travel-indicator" aria-live="polite"><i /><span>{jobEvolutionMode ? "岗位版本演进" : "穿越时间虫洞"}</span><strong>{jobEvolutionMode ? evolutionFrame?.period || "请选择岗位" : previewLayer?.label || graph.layers.find((item) => item.id === period)?.label || period}</strong></div>}
      {activePeriodMeta?.planeCount > 1 && <div className="ecliptic-density-controls" aria-label="职业快轨面可见性筛选">
        <header><strong>{activePeriodMeta.planeCount} 个职业快轨面</strong><small>{activePeriodMeta.nodeCount.toLocaleString("zh-CN")} 节点 · 每个快轨面 {activePeriodMeta.clearNodeLimit} 个以内</small></header>
        <div className="ecliptic-plane-picker">
          <button aria-label="上一个职业快轨面" disabled={Number(densityPlaneFilter) <= 0} onClick={() => setDensityPlaneFilter(String(Math.max(0, Number(densityPlaneFilter) - 1)))} type="button"><ChevronLeft size={14} /></button>
          <label><span>当前职业快轨面</span><select value={densityPlaneFilter} onChange={(event) => setDensityPlaneFilter(event.target.value)}>
            {activePeriodMeta.planes.map((plane) => <option key={plane.id} value={String(plane.index)}>快轨面 {plane.index + 1} · {plane.nodeCount} 节点</option>)}
          </select></label>
          <button aria-label="下一个职业快轨面" disabled={Number(densityPlaneFilter) >= activePeriodMeta.planeCount - 1} onClick={() => setDensityPlaneFilter(String(Math.min(activePeriodMeta.planeCount - 1, Number(densityPlaneFilter) + 1)))} type="button"><ChevronRight size={14} /></button>
        </div>
      </div>}
      {hover && <div className="career-hover-card" style={{ left: hover.x + 16, top: hover.y + 16 }}>
        <span>{hover.node.nodeType === "family" ? "岗位族" : hover.node.nodeType === "skill" ? "能力技能" : hover.node.nodeType === "signal" ? "前沿辅助信号" : "真实岗位"}</span>
        <strong>{hover.node.title}</strong>
        <small>{hover.node.nodeType === "family" ? `${hover.node.jobCount} 条岗位 · ${hover.node.companyCount} 家企业` : hover.node.nodeType === "skill" ? `${hover.node.supportCount} 条证据 · 覆盖 ${hover.node.coverage}%` : hover.node.nodeType === "signal" ? `${hover.node.sourcePlatform} · 仅作前沿观察` : `${hover.node.company} · ${hover.node.salary}`}</small>
        {wormholeMode && <em>{hover.relationSummary}</em>}
      </div>}
      {loading && <div className="career-loading"><i /><span>正在计算真实岗位关系</span></div>}
      {error && <div className="career-loading error"><span>{error}</span></div>}
      {!compact && <div className="career-camera-tools">
        <button title="放大" onClick={() => adjustZoom(0.82)}><ZoomIn size={16} /></button>
        <button title="缩小" onClick={() => adjustZoom(1.2)}><ZoomOut size={16} /></button>
        <button title="重置视角" onClick={() => sceneRef.current?.reset()}><RotateCcw size={16} /></button>
        <button title="全屏" onClick={() => mountRef.current?.parentElement?.requestFullscreen?.()}><Maximize2 size={16} /></button>
      </div>}
    </div>
  );
}
