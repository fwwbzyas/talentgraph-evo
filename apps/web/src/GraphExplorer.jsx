import React, { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import { Crosshair, Maximize2, Minus, Plus, Search, X } from "lucide-react";
import { publicJobSamples } from "./demoData";

const palette = {
  job: { color: "#fff", background: "#172033", border: "#172033" },
  category: { color: "#314032", background: "#e7f4e9", border: "#79a981" },
  skill: { color: "#4b3513", background: "#fff1cf", border: "#d1a149" },
  tool: { color: "#5b2945", background: "#f8e5f0", border: "#bb78a0" },
  responsibility: { color: "#3c355e", background: "#ece9ff", border: "#8a7ec1" },
  scenario: { color: "#12324a", background: "#dff2ff", border: "#5aa7cf" },
  evidence: { color: "#4f5967", background: "#f2f4f7", border: "#9aa4b2" },
};

const toolNames = new Set(["Spring Boot", "Spring Cloud", "MySQL", "Redis", "Kafka", "RabbitMQ", "Docker", "Kubernetes", "Prometheus", "ELK", "Terraform", "Pytest", "Selenium", "Appium", "LangChain", "PyTorch"]);

function buildFallbackElements() {
  const focus = publicJobSamples[3];
  const categories = {
    "语言与基础": ["Java", "JVM", "多线程", "数据结构"],
    "服务架构": ["Spring Boot", "Spring Cloud", "微服务", "高并发"],
    "数据基础设施": ["MySQL", "Redis", "Kafka", "SQL优化"],
    "交付与稳定性": ["Docker", "Kubernetes", "可观测性", "故障治理"],
  };
  const nodes = [{ data: { id: "job_java", label: "Java 后端工程师", type: "job", detail: "企业岗位能力模型", confidence: 0.96, evidenceCount: 42 } }];
  const edges = [];
  Object.entries(categories).forEach(([category, skills], cIndex) => {
    const categoryId = `cat_${cIndex}`;
    nodes.push({ data: { id: categoryId, label: category, type: "category", detail: `能力域 · ${skills.length} 个技能`, confidence: 0.92, evidenceCount: 18 + cIndex * 3 } });
    edges.push({ data: { id: `e_job_${cIndex}`, source: "job_java", target: categoryId, label: "包含" } });
    skills.forEach((skill, sIndex) => {
      const skillId = `skill_${cIndex}_${sIndex}`;
      const type = toolNames.has(skill) ? "tool" : "skill";
      nodes.push({ data: { id: skillId, label: skill, type, detail: sIndex < 2 ? "核心要求" : "进阶要求", confidence: 0.78 + sIndex * 0.05, evidenceCount: 7 + cIndex + sIndex, level: sIndex < 2 ? "advanced" : "intermediate" } });
      edges.push({ data: { id: `e_${categoryId}_${sIndex}`, source: categoryId, target: skillId, label: "要求" } });
      if (sIndex < 2) {
        const evId = `ev_${cIndex}_${sIndex}`;
        nodes.push({ data: { id: evId, label: `证据 ${cIndex * 2 + sIndex + 1}`, type: "evidence", detail: `${focus.company}等公开岗位样本中出现“${skill}”要求`, confidence: 0.9, evidenceCount: 1, sourceUrl: focus.sourceUrl } });
        edges.push({ data: { id: `e_ev_${cIndex}_${sIndex}`, source: skillId, target: evId, label: "证据支持" } });
      }
    });
  });
  focus.responsibilities.forEach((item, index) => {
    const id = `resp_${index}`;
    nodes.push({ data: { id, label: item.slice(0, 10), type: "responsibility", detail: item, confidence: 0.89, evidenceCount: 4 } });
    edges.push({ data: { id: `e_resp_${index}`, source: "job_java", target: id, label: "承担" } });
  });
  return [...nodes, ...edges];
}

function normalizeGraph(graph) {
  if (!graph?.graph_nodes?.length) return buildFallbackElements();
  const nodes = graph.graph_nodes.map((node) => ({
    data: {
      ...node,
      id: node.id,
      label: node.label,
      type: node.type === "capability_domain" ? "category" : node.type,
      confidence: node.confidence ?? node.score ?? 0.84,
      evidenceCount: node.evidence_count ?? 1,
      detail: node.detail ?? node.description ?? `${node.label} · ${node.type}`,
    },
  }));
  const edges = graph.graph_edges.map((edge, index) => ({ data: { id: `api_edge_${index}`, ...edge } }));
  return [...nodes, ...edges];
}

export default function GraphExplorer({ graph }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState("");
  const [layout, setLayout] = useState("cose");
  const [visibleTypes, setVisibleTypes] = useState(() => new Set(Object.keys(palette)));
  const elements = useMemo(() => normalizeGraph(graph), [graph]);

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      minZoom: 0.32,
      maxZoom: 2.4,
      wheelSensitivity: 0.18,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-wrap": "wrap",
            "text-max-width": 92,
            "text-valign": "center",
            "text-halign": "center",
            "font-size": 11,
            "font-family": "Aptos, Microsoft YaHei, sans-serif",
            width: 62,
            height: 62,
            "border-width": 1.5,
            "overlay-opacity": 0,
            "transition-property": "opacity, border-width, width, height",
            "transition-duration": "180ms",
          },
        },
        ...Object.entries(palette).map(([type, colors]) => ({ selector: `node[type = "${type}"]`, style: { color: colors.color, "background-color": colors.background, "border-color": colors.border } })),
        { selector: 'node[type = "job"]', style: { width: 146, height: 146, "font-size": 15, "font-weight": 700, "text-max-width": 96, "border-width": 7, "border-color": "#d9e2ea" } },
        { selector: 'node[type = "category"]', style: { width: 96, height: 96, "font-size": 12, "font-weight": 600 } },
        { selector: 'node[type = "responsibility"]', style: { shape: "round-rectangle", width: 112, height: 52, "text-max-width": 92, "font-size": 9 } },
        { selector: 'node[type = "evidence"]', style: { width: 42, height: 42, "font-size": 8 } },
        { selector: "edge", style: { width: 1.65, "curve-style": "bezier", "line-color": "#b9c6d1", "target-arrow-color": "#b9c6d1", "target-arrow-shape": "triangle", "arrow-scale": 0.78, label: "data(label)", "font-size": 7, color: "#748190", "text-background-color": "#f8fafc", "text-background-opacity": 0.82, "text-background-padding": 2 } },
        { selector: ".dim", style: { opacity: 0.09 } },
        { selector: ".focus", style: { "border-width": 4, "border-color": "#ff7a45", width: 66, height: 66, "z-index": 999 } },
        { selector: "edge.focus", style: { opacity: 1, width: 2.8, "line-color": "#ff9c76", "target-arrow-color": "#ff9c76", "z-index": 998 } },
        { selector: ".hidden", style: { display: "none" } },
      ],
      layout: { name: "cose", animate: false, padding: 76, nodeRepulsion: 5200, idealEdgeLength: 58, gravity: 1.05, componentSpacing: 42 },
    });
    cy.fit(undefined, 76);
    cy.zoom(Math.min(cy.zoom() * 1.2, 1.35));
    cy.center(cy.$('node[type="job"]'));
    cy.on("tap", "node", (event) => {
      const node = event.target;
      cy.elements().addClass("dim").removeClass("focus");
      node.closedNeighborhood().removeClass("dim").addClass("focus");
      setSelected(node.data());
    });
    cy.on("tap", (event) => {
      if (event.target === cy) {
        cy.elements().removeClass("dim focus");
        setSelected(null);
      }
    });
    cyRef.current = cy;
    return () => { cy.stop(); cy.destroy(); };
  }, [elements]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().forEach((node) => node.toggleClass("hidden", !visibleTypes.has(node.data("type"))));
  }, [visibleTypes]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const term = query.trim().toLowerCase();
    cy.elements().removeClass("dim focus");
    if (!term) return;
    const hits = cy.nodes().filter((node) => String(node.data("label")).toLowerCase().includes(term));
    cy.elements().addClass("dim");
    hits.union(hits.closedNeighborhood()).removeClass("dim");
    hits.addClass("focus");
    if (hits.length) cy.animate({ fit: { eles: hits.union(hits.closedNeighborhood()), padding: 90 }, duration: 350 });
  }, [query]);

  const switchLayout = (next) => {
    setLayout(next);
    cyRef.current?.layout(next === "breadthfirst" ? { name: next, directed: true, roots: cyRef.current.$('node[type="job"]'), padding: 58, spacingFactor: 1.16, animate: false } : { name: "cose", animate: false, padding: 76, nodeRepulsion: 5200, idealEdgeLength: 58, gravity: 1.05, componentSpacing: 42 }).run();
  };

  const toggleType = (type) => setVisibleTypes((current) => {
    const next = new Set(current);
    if (next.has(type)) next.delete(type); else next.add(type);
    return next;
  });

  return (
    <section className="graph-explorer">
      <div className="graph-commandbar">
        <label className="graph-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索技能、工具或证据" /></label>
        <div className="segmented" aria-label="图谱布局">
          <button className={layout === "cose" ? "active" : ""} onClick={() => switchLayout("cose")}>关系网络</button>
          <button className={layout === "breadthfirst" ? "active" : ""} onClick={() => switchLayout("breadthfirst")}>能力分层</button>
        </div>
        <div className="icon-actions">
          <button title="缩小" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.82)}><Minus size={16} /></button>
          <button title="放大" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.2)}><Plus size={16} /></button>
          <button title="适应画布" onClick={() => cyRef.current?.fit(undefined, 48)}><Maximize2 size={16} /></button>
          <button title="定位岗位" onClick={() => cyRef.current?.animate({ center: { eles: cyRef.current.$('node[type="job"]') }, zoom: 1.05, duration: 350 })}><Crosshair size={16} /></button>
        </div>
      </div>
      <div className="graph-legend">
        {Object.entries(palette).map(([type, colors]) => (
          <button key={type} className={visibleTypes.has(type) ? "active" : ""} onClick={() => toggleType(type)}>
            <i style={{ background: colors.background, borderColor: colors.border }} />{({ job: "岗位", category: "能力域", skill: "技能", tool: "工具", responsibility: "职责", scenario: "业务场景", evidence: "证据" })[type]}
          </button>
        ))}
      </div>
      <div className="graph-surface" ref={containerRef} />
      <aside className={`graph-inspector ${selected ? "open" : ""}`}>
        {selected && <>
          <button className="inspector-close" title="关闭" onClick={() => { setSelected(null); cyRef.current?.elements().removeClass("dim focus"); }}><X size={17} /></button>
          <span className="eyebrow">{selected.type}</span>
          <h3>{selected.label}</h3>
          <p>{selected.detail}</p>
          <dl>
            <div><dt>置信度</dt><dd>{Math.round((selected.confidence || 0.84) * 100)}%</dd></div>
            <div><dt>证据数量</dt><dd>{selected.evidenceCount || 1}</dd></div>
            <div><dt>要求等级</dt><dd>{selected.level || "核心"}</dd></div>
          </dl>
          <div className="confidence-track"><span style={{ width: `${Math.round((selected.confidence || 0.84) * 100)}%` }} /></div>
          {selected.sourceUrl && <a href={selected.sourceUrl} target="_blank" rel="noreferrer">查看公开来源</a>}
          <small>点击其他节点继续沿证据链探索</small>
        </>}
      </aside>
    </section>
  );
}
