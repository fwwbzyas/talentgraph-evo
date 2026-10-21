import React, { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import { LoaderCircle } from "lucide-react";

const DOMAIN_COLORS = {
  人工智能: "#58c5e8",
  大数据: "#69cf8b",
  智能系统: "#ef7f72",
  物联网: "#b893e6",
};

const LENS_TYPES = {
  integrated: new Set(["core_skill", "requires_skill", "job_similarity", "skill_cooccurrence", "talent_mobility_inference"]),
  job_skill: new Set(["core_skill", "requires_skill"]),
  similarity: new Set(["job_similarity"]),
  combination: new Set(["skill_cooccurrence"]),
  mobility: new Set(["talent_mobility_inference"]),
};

const EDGE_META = {
  core_skill: { color: "#f1c96c", label: "核心技能" },
  requires_skill: { color: "#638da0", label: "岗位技能" },
  job_similarity: { color: "#54c7ec", label: "岗位相似" },
  skill_cooccurrence: { color: "#79d991", label: "技能组合" },
  talent_mobility_inference: { color: "#d8a4ff", label: "跨岗迁移" },
};

const RELATION_LIMITS = {
  core_skill: Number.POSITIVE_INFINITY,
  requires_skill: 140,
  job_similarity: 70,
  skill_cooccurrence: 55,
  talent_mobility_inference: 55,
};
const EMPTY_RELATION_TYPES = [];

const EVOLUTION_STATE_META = {
  retained: { color: "#58b9ff", label: "持续技能" },
  strengthened: { color: "#61e6c2", label: "增强技能" },
  added: { color: "#7ef7d2", label: "新增技能" },
  declining: { color: "#f1be67", label: "减弱技能" },
  retired: { color: "#c27bd9", label: "退出技能" },
};

function evolutionElements(profile) {
  if (!profile?.frames?.length) return [];
  const skills = [...new Set(profile.frames.flatMap((frame) => frame.skills.map((skill) => skill.name)))];
  const roleId = "evolution-role";
  return [
    {
      data: {
        id: roleId,
        label: profile.frames[0].title,
        title: profile.frames[0].title,
        family: profile.family,
        nodeType: "family",
        color: profile.demoType === "legacy" ? "#77a9ff" : "#69e2c6",
        size: 86,
        jobCount: profile.actualEvidenceCount,
        category: profile.category,
        demoType: profile.demoType,
        skills,
      },
      position: { x: 0, y: 0 },
    },
    ...skills.map((name, index) => {
      const ring = index < 10 ? 0 : 1;
      const ringIndex = ring ? index - 10 : index;
      const ringCount = ring ? Math.max(1, skills.length - 10) : Math.min(10, skills.length);
      const angle = ringIndex / ringCount * Math.PI * 2 - Math.PI / 2;
      const radius = ring ? 320 : 190;
      return {
        data: {
          id: `evolution-skill:${encodeURIComponent(name)}`,
          label: name,
          title: name,
          name,
          nodeType: "skill",
          color: EVOLUTION_STATE_META.retained.color,
          stateColor: EVOLUTION_STATE_META.retained.color,
          state: "retained",
          size: 28,
        },
        position: { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius },
      };
    }),
    ...skills.map((name) => ({
      data: {
        id: `evolution-edge:${encodeURIComponent(name)}`,
        source: roleId,
        target: `evolution-skill:${encodeURIComponent(name)}`,
        relationType: "evolution_skill",
        edgeColor: EVOLUTION_STATE_META.retained.color,
        edgeLabel: EVOLUTION_STATE_META.retained.label,
        edgeWidth: 1.4,
        state: "retained",
      },
    })),
  ];
}

function graphElements(payload, lens, relationTypes) {
  const allowed = relationTypes?.length ? new Set(relationTypes) : LENS_TYPES[lens] || LENS_TYPES.job_skill;
  const candidateEdges = (payload?.edges || [])
    .filter((edge) => allowed.has(edge.relationType))
    .sort((left, right) => Number(right.weight || 0) - Number(left.weight || 0));
  let edges;
  if (lens === "job_skill") {
    edges = candidateEdges.filter((edge) => ["core_skill", "requires_skill"].includes(edge.relationType));
  } else if (lens === "integrated") {
    edges = Object.entries(RELATION_LIMITS).flatMap(([relationType, limit]) => candidateEdges
      .filter((edge) => edge.relationType === relationType)
      .slice(0, limit));
  } else {
    edges = candidateEdges.slice(0, lens === "combination" ? 120 : lens === "similarity" ? 180 : 140);
  }
  edges = [...new Map(edges.map((edge) => [edge.id, edge])).values()];
  const nodeIds = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
  const nodes = (payload?.nodes || []).filter((node) => nodeIds.has(node.id));
  const domains = [...new Set(nodes.map((node) => node.domain).filter(Boolean))];
  const domainEdges = nodes
    .filter((node) => node.type === "family" && node.domain)
    .map((node) => ({
      data: {
        id: `domain-membership:${node.domain}:${node.id}`,
        source: `domain:${node.domain}`,
        target: node.id,
        relationType: "domain_membership",
        edgeColor: DOMAIN_COLORS[node.domain] || "#74cdb9",
        edgeWidth: 1,
      },
    }));
  return [
    ...domains.map((domain) => ({
      data: {
        id: `domain:${domain}`,
        label: domain,
        nodeType: "domain",
        color: DOMAIN_COLORS[domain] || "#74cdb9",
        size: 66,
      },
    })),
    ...nodes.map((node) => ({
      data: {
        ...node,
        id: node.id,
        label: node.label,
        nodeType: node.type,
        color: node.type === "skill" ? "#a9bbc0" : DOMAIN_COLORS[node.domain] || "#74cdb9",
        size: node.type === "family"
          ? Math.min(82, 40 + Math.sqrt(Number(node.jobCount || 1)) * 1.25)
          : Math.min(34, 20 + Math.sqrt(Number(node.supportCount || node.jobCount || 1)) * 0.35),
      },
    })),
    ...edges.map((edge) => ({
      data: {
        ...edge,
        id: edge.id,
        edgeColor: EDGE_META[edge.relationType]?.color || "#64818a",
        edgeLabel: EDGE_META[edge.relationType]?.label || edge.label,
        edgeWidth: Math.max(0.7, Math.min(2.2, 0.7 + Number(edge.weight || 0) * 1.5)),
      },
    })),
    ...domainEdges,
  ];
}

export default function RelationGraph({ payload, lens = "job_skill", relationTypes = EMPTY_RELATION_TYPES, query = "", onSelect, onStats, periodLabel, evolutionMode = false, evolutionProfile = null, evolutionPosition = 0, compact = false }) {
  const mountRef = useRef(null);
  const cyRef = useRef(null);
  const [hover, setHover] = useState(null);
  const elements = useMemo(() => evolutionMode ? evolutionElements(evolutionProfile) : graphElements(payload, lens, relationTypes), [evolutionMode, evolutionProfile, payload, lens, relationTypes]);
  const evolutionFrameIndex = Math.max(0, Math.min(Math.round(Number(evolutionPosition || 0)), Math.max(0, (evolutionProfile?.frames?.length || 1) - 1)));
  const evolutionFrame = evolutionProfile?.frames?.[evolutionFrameIndex] || null;

  useEffect(() => {
    if (!mountRef.current || !elements.length) return undefined;
    cyRef.current?.destroy();
    const cy = cytoscape({
      container: mountRef.current,
      elements,
      minZoom: 0.45,
      maxZoom: 2.4,
      pixelRatio: Math.min(window.devicePixelRatio, 2),
      boxSelectionEnabled: false,
      layout: evolutionMode ? {
        name: "preset",
        fit: true,
        padding: 94,
      } : {
        name: "cose",
        animate: true,
        animationDuration: 900,
        animationEasing: "ease-out-cubic",
        fit: true,
        padding: compact ? 22 : 54,
        nodeRepulsion: (node) => node.data("nodeType") === "family" ? (compact ? 6200 : 11800) : (compact ? 3600 : 7200),
        idealEdgeLength: (edge) => ["core_skill", "requires_skill"].includes(edge.data("relationType")) ? (compact ? 60 : 92) : (compact ? 96 : 150),
        edgeElasticity: (edge) => ["core_skill", "requires_skill"].includes(edge.data("relationType")) ? (compact ? 72 : 110) : (compact ? 30 : 42),
        gravity: 0.18,
        numIter: compact ? 700 : 1100,
        randomize: true,
      },
      style: [
        { selector: "node", style: {
          "background-color": "data(color)",
          "background-opacity": 0.92, "border-width": 2, "border-color": "data(color)",
          "border-opacity": 0.55, label: "data(label)", color: "#dce9f2",
          "font-family": "Microsoft YaHei", "font-size": 11, "font-weight": 700,
          "text-wrap": "wrap", "text-max-width": 112, "text-valign": "bottom",
          "text-margin-y": 9, "overlay-opacity": 0,
        } },
        { selector: "node[size]", style: { width: "data(size)", height: "data(size)" } },
        { selector: "node[nodeType = 'family']", style: {
          shape: "ellipse", "font-size": 12, color: "#ffffff", "text-max-width": 78,
          "text-valign": "center", "text-margin-y": 0,
          "text-background-color": "#07131d", "text-background-opacity": 0.15,
          "text-background-padding": 2, "text-background-shape": "roundrectangle",
        } },
        { selector: "node[nodeType = 'skill']", style: {
          shape: "roundrectangle", width: 78, height: 23, "background-color": "#112a37",
          "background-opacity": 0.96, "border-color": "data(color)", "border-width": 1,
          "border-opacity": 0.45, "font-size": 9, "font-weight": 600, color: "#b9ced8",
          "text-valign": "center", "text-margin-y": 0, "text-max-width": 70,
        } },
        { selector: "node[nodeType = 'domain']", style: {
          shape: "ellipse", "background-color": "#071821", "background-opacity": 0.96,
          "border-width": 2, "border-color": "data(color)", "border-opacity": 0.8,
          label: "data(label)", color: "#e7f3f5", "font-size": 11, "font-weight": 700,
          "text-valign": "center", "text-halign": "center", "text-margin-x": 0, "text-margin-y": 0,
        } },
        { selector: "edge", style: {
          width: "data(edgeWidth)", "line-color": "data(edgeColor)", "line-opacity": 0.3,
          "curve-style": "unbundled-bezier", "control-point-distances": 28, "control-point-weights": 0.5,
          "target-arrow-shape": "none", "overlay-opacity": 0,
        } },
        { selector: "edge[relationType = 'core_skill']", style: { "line-opacity": 0.44 } },
        { selector: "edge[relationType = 'requires_skill']", style: { "line-opacity": 0.2 } },
        { selector: "edge[relationType = 'job_similarity']", style: { "line-opacity": 0.2, "line-style": "dotted" } },
        { selector: "edge[relationType = 'skill_cooccurrence']", style: { "line-opacity": 0.18 } },
        { selector: "edge[relationType = 'talent_mobility_inference']", style: { "line-opacity": 0.18, "line-style": "dashed" } },
        { selector: "edge[relationType = 'domain_membership']", style: {
          width: 1, "line-opacity": 0.16, "curve-style": "straight", "line-style": "dashed",
        } },
        { selector: ".dimmed", style: { opacity: 0.035 } },
        { selector: ".focused", style: { opacity: 1, "border-width": 3, "border-opacity": 0.95, "line-opacity": 0.9 } },
        { selector: "edge.focused", style: {
          label: "data(edgeLabel)", color: "#d8e8ef", "font-size": 8,
          "text-background-color": "#07131d", "text-background-opacity": 0.9,
          "text-background-padding": 3, "text-rotation": "autorotate",
        } },
        { selector: ".locked", style: { "border-width": 5, "border-color": "#ffffff", "border-opacity": 0.95, "z-index": 999 } },
        { selector: "node[nodeType = 'skill'].overview-label-hidden", style: {
          width: 9, height: 9, shape: "ellipse", "background-color": "data(color)",
          "background-opacity": 0.82, "border-width": 1, "border-opacity": 0.72, "text-opacity": 0,
        } },
        { selector: "node[nodeType = 'skill'].overview-label-hidden.focused", style: {
          width: 78, height: 23, shape: "roundrectangle", "background-color": "#112a37",
          "text-opacity": 1,
        } },
        { selector: ".search-hit", style: { "border-width": 5, "border-color": "#ffffff", "border-opacity": 1 } },
        { selector: "node[id = 'evolution-role']", style: {
          shape: "ellipse", width: 72, height: 72, "font-size": 11, color: "#f7ffff",
          "text-valign": "center", "text-margin-y": 0, "text-max-width": 64,
          "background-opacity": 0.96, "border-width": 3, "border-opacity": 0.92,
          "shadow-blur": 28, "shadow-color": "data(color)", "shadow-opacity": 0.46,
        } },
        { selector: "node[nodeType = 'skill'][state]", style: {
          shape: "roundrectangle", width: 96, height: 30,
          "background-color": "data(stateColor)", "border-color": "data(stateColor)",
          "background-opacity": 0.13, "border-width": 1.5, "border-opacity": 0.88,
          color: "#eaf7fa", "font-size": 10, "font-weight": 700,
          "text-valign": "center", "text-margin-y": 0, "text-max-width": 88,
          "text-background-opacity": 0, "shadow-blur": 16,
          "shadow-color": "data(stateColor)", "shadow-opacity": 0.38,
          "transition-property": "opacity background-color border-color width height",
          "transition-duration": "420ms", "transition-timing-function": "ease-out",
        } },
        { selector: "edge[relationType = 'evolution_skill']", style: {
          "line-color": "data(edgeColor)", "line-opacity": 0.76, width: "data(edgeWidth)",
          "curve-style": "bezier", label: "data(edgeLabel)", color: "#d9ecef", "font-size": 8,
          "text-background-color": "#07131d", "text-background-opacity": 0.78,
          "text-background-padding": 3, "text-rotation": "autorotate",
          "transition-property": "opacity line-color width", "transition-duration": "420ms",
        } },
        { selector: ".evolution-added", style: { "border-width": 2.5, "shadow-opacity": 0.72 } },
        { selector: ".evolution-strengthened", style: { "border-width": 2, "shadow-opacity": 0.58 } },
        { selector: ".evolution-declining", style: { opacity: 0.68 } },
        { selector: "edge.evolution-declining", style: { "line-style": "dashed" } },
        { selector: ".evolution-retired", style: { opacity: 0.24 } },
        { selector: "edge.evolution-retired", style: { "line-style": "dotted" } },
        { selector: ".evolution-hidden", style: { opacity: 0, "text-opacity": 0 } },
      ],
    });

    cy.one("layoutstop", () => {
      if (evolutionMode) {
        cy.fit(cy.elements().not(".evolution-hidden"), 108);
        return;
      }
      const visibleNodes = cy.nodes();
      if (compact) {
        cy.fit(visibleNodes, 22);
        return;
      }
      const box = visibleNodes.boundingBox({ includeLabels: false, includeOverlays: false });
      const centerX = box.x1 + box.w / 2;
      const centerY = box.y1 + box.h / 2;
      visibleNodes.positions((node) => ({
        x: centerX + (node.position("x") - centerX) * 2.25,
        y: centerY + (node.position("y") - centerY) * 0.9,
      }));
      cy.fit(visibleNodes, 72);
    });

    let lockedNode = null;
    const focusNode = (node, locked = false) => {
      const neighborhood = node.closedNeighborhood();
      cy.elements().addClass("dimmed").removeClass("focused");
      neighborhood.removeClass("dimmed").addClass("focused");
      if (locked) {
        cy.nodes().removeClass("locked");
        node.addClass("locked");
      }
    };
    const restoreFocus = () => {
      cy.elements().removeClass("dimmed focused");
      if (lockedNode?.length) focusNode(lockedNode, true);
    };
    cy.on("mouseover", "node", (event) => {
      const node = event.target;
      if (node.data("nodeType") === "domain") return;
      focusNode(node);
      const relations = node.connectedEdges().map((edge) => edge.data("edgeLabel"));
      setHover({ ...node.data(), relationLabels: [...new Set(relations)] });
    });
    cy.on("mouseout", "node", () => { restoreFocus(); setHover(null); });
    cy.on("tap", "node", (event) => {
      if (event.target.data("nodeType") === "domain") return;
      lockedNode = event.target;
      focusNode(lockedNode, true);
      onSelect?.(event.target.data());
    });
    cy.on("tap", "edge", (event) => {
      const edge = event.target;
      onSelect?.({
        id: edge.id(), title: edge.data("edgeLabel"), label: edge.data("edgeLabel"),
        nodeType: "relation", category: "关系证据", description: edge.data("method"),
        confidence: edge.data("confidence"), evidenceCount: edge.data("evidenceIds")?.length || 0,
        sharedSkills: edge.data("sharedSkills") || [], skills: edge.data("sharedSkills") || [], period: payload?.period,
      });
    });
    cy.on("tap", (event) => { if (event.target === cy) { lockedNode = null; cy.elements().removeClass("dimmed focused locked"); onSelect?.(null); } });
    const updateZoomLabels = () => {
      const hideSkillLabels = !compact && !evolutionMode && cy.zoom() < 0.92;
      cy.nodes("[nodeType = 'skill']").toggleClass("overview-label-hidden", hideSkillLabels);
    };
    cy.on("zoom", updateZoomLabels);
    updateZoomLabels();
    cyRef.current = cy;
    onStats?.({
      ...(payload?.stats || {}),
      rendered_nodes: cy.nodes().filter((node) => node.data("nodeType") !== "domain").length,
      rendered_edges: cy.edges().length,
    });
    return () => { cy.destroy(); if (cyRef.current === cy) cyRef.current = null; };
  }, [compact, elements, evolutionMode, lens, onSelect, onStats, payload?.period, payload?.stats]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !evolutionMode || !evolutionFrame) return;
    const currentSkills = new Map(evolutionFrame.skills.map((skill) => [skill.name, skill]));
    cy.batch(() => {
      const role = cy.$id("evolution-role");
      role.data("label", evolutionFrame.title);
      role.data("title", evolutionFrame.title);
      role.data("period", evolutionFrame.period);
      role.data("skills", evolutionFrame.skills.filter((skill) => skill.state !== "retired").map((skill) => skill.name));
      cy.nodes("[nodeType = 'skill']").forEach((node) => {
        const skill = currentSkills.get(node.data("name"));
        const state = skill?.state || "hidden";
        const meta = EVOLUTION_STATE_META[state] || EVOLUTION_STATE_META.retained;
        node.removeClass("evolution-hidden evolution-retained evolution-strengthened evolution-added evolution-declining evolution-retired");
        if (!skill) node.addClass("evolution-hidden");
        else {
          node.addClass(`evolution-${state}`);
          node.data("state", state);
          node.data("stateColor", meta.color);
          node.data("evidenceType", skill.evidenceType);
        }
        const edge = cy.$id(`evolution-edge:${encodeURIComponent(node.data("name"))}`);
        edge.removeClass("evolution-hidden evolution-retained evolution-strengthened evolution-added evolution-declining evolution-retired");
        if (!skill) edge.addClass("evolution-hidden");
        else {
          edge.addClass(`evolution-${state}`);
          edge.data("state", state);
          edge.data("edgeColor", meta.color);
          edge.data("edgeLabel", meta.label);
          edge.data("edgeWidth", Math.max(0.9, 1 + Number(skill.weight || 0) * 1.5));
        }
      });
    });
    const visible = cy.$id("evolution-role").union(cy.nodes("[nodeType = 'skill']").filter((node) => currentSkills.has(node.data("name"))));
    const skillNodes = visible.filter("[nodeType = 'skill']");
    skillNodes.forEach((node, index) => {
      const ring = index < 8 ? 0 : 1;
      const ringIndex = ring ? index - 8 : index;
      const ringCount = ring ? Math.max(1, skillNodes.length - 8) : Math.min(8, skillNodes.length);
      const angle = ringIndex / ringCount * Math.PI * 2 - Math.PI / 2 + evolutionFrameIndex * 0.035;
      const radius = ring ? 315 : 188;
      node.animate({ position: { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius } }, { duration: 520, easing: "ease-out-cubic" });
    });
    cy.$id("evolution-role").animate({ position: { x: 0, y: 0 } }, { duration: 420, easing: "ease-out-cubic" });
    cy.animate({ fit: { eles: visible, padding: 112 } }, { duration: 500, easing: "ease-out-cubic" });
    onStats?.({
      ...(payload?.stats || {}),
      rendered_nodes: visible.length,
      rendered_edges: evolutionFrame.skills.length,
      visible_relation_edges: evolutionFrame.skills.length,
    });
  }, [evolutionFrame, evolutionFrameIndex, evolutionMode, onStats, payload?.stats]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass("search-hit");
    const term = query.trim().toLowerCase();
    if (evolutionMode || term.length < 2) return;
    const hit = cy.nodes().filter((node) => String(node.data("label") || "").toLowerCase().includes(term)).first();
    if (hit.length) {
      hit.addClass("search-hit");
      cy.animate({ center: { eles: hit }, zoom: 1.35 }, { duration: 420 });
    }
  }, [query, elements, evolutionMode]);

  if (!payload) return <div className="relation-graph-state"><LoaderCircle className="spin" size={22} />正在构建岗位关系网络</div>;
  if (evolutionMode && !evolutionProfile) return <div className="relation-graph-state">二维岗位演进仅支持两个精选岗位，请从搜索历史中选择演示岗位</div>;
  if (!elements.length) return <div className="relation-graph-state">当前时间与筛选条件下没有足够关系证据</div>;
  return (
    <section className={`relation-graph-stage${compact ? " is-compact" : ""}`}>
      <div className="relation-graph-grid" aria-hidden="true" />
      <div ref={mountRef} className="relation-graph-canvas" />
      <div className="relation-time-stamp"><span>{evolutionMode ? "二维岗位技能演进" : "市场关系快照"}</span><strong>{evolutionMode ? evolutionFrame?.period : periodLabel || "当前市场"}</strong><small>{evolutionMode ? `${evolutionFrame?.skills.length || 0} 个可见技能 · ${evolutionProfile?.demoLabel}` : `${payload?.nodes?.length || 0} 节点 · ${elements.filter((item) => item.data?.relationType && item.data.relationType !== "domain_membership").length} 条当前关系 / ${payload?.edges?.length || 0} 条证据关系`}</small></div>
      {evolutionMode && evolutionFrame && <aside className="relation-evolution-hud">
        <header><span>{evolutionProfile.demoType === "legacy" ? "既有岗位 AI 转型研究" : "新兴岗位形成研究"}</span><strong>{evolutionFrame.title}</strong><small>{evolutionFrame.period} · {evolutionProfile.demoLabel}</small></header>
        <div>
          <p className="added"><b>新增技能</b><span>{evolutionFrame.addedSkills.join(" · ") || "本月结构稳定"}</span></p>
          <p className="declining"><b>减弱技能</b><span>{evolutionFrame.decliningSkills.join(" · ") || "暂无明显减弱"}</span></p>
          <p className="retired"><b>退出技能</b><span>{evolutionFrame.retiredSkills.join(" · ") || "暂无退出"}</span></p>
        </div>
        <footer>实线技能来自真实 JD；补齐月份的技能变化为研究性模拟，不作为现实预测。</footer>
      </aside>}
      {hover && <aside className="relation-hover"><span>{hover.nodeType === "family" ? "岗位" : "技能"}</span><strong>{hover.label}</strong><small>{hover.nodeType === "family" ? `${hover.jobCount || 0} 条岗位证据` : `${hover.supportCount || hover.jobCount || 0} 条技能证据`}</small><p>{hover.relationLabels?.join(" · ")}</p></aside>}
      <div className="relation-graph-legend" aria-label="图谱图例">
        {evolutionMode ? <>
          <span><i className="job" />当前岗位</span>
          {Object.entries(EVOLUTION_STATE_META).map(([key, meta]) => <span key={key}><i className="edge" style={{ "--edge-color": meta.color }} />{meta.label}</span>)}
        </> : <>
          <span><i className="job" />岗位</span><span><i className="skill" />技能</span>
          {Object.entries(EDGE_META).map(([key, meta]) => <span key={key}><i className="edge" style={{ "--edge-color": meta.color }} />{meta.label}</span>)}
        </>}
      </div>
    </section>
  );
}
