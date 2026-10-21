import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import { Button } from "@heroui/react";
import {
  ArrowLeft,
  ChevronRight,
  ExternalLink,
  Focus,
  LoaderCircle,
} from "lucide-react";

const TYPE_META = {
  domain: { label: "领域", color: "#61d7c0", size: 76 },
  job: { label: "岗位族", color: "#6fb9ff", size: 68 },
  capability: { label: "能力模块", color: "#e0bd6c", size: 60 },
  skill: { label: "技能点", color: "#bc91ef", size: 52 },
  evidence: { label: "JD 证据", color: "#2f6df4", size: 43 },
};

function toNodeData(node, extra = {}) {
  const { parent, ...rest } = node;
  return {
    ...rest,
    parentId: parent || null,
    id: node.id,
    label: node.label,
    nodeType: node.type,
    color: TYPE_META[node.type]?.color || "#90a6aa",
    size: TYPE_META[node.type]?.size || 48,
    ...extra,
  };
}

function toElements(payload, activeDomain = "all") {
  const scopedRootLabel = activeDomain && activeDomain !== "all" ? activeDomain : "岗位能力图谱";
  const parent = payload.parent || {
    id: "root:ability-map",
    label: "岗位能力图谱",
    type: "domain",
    evidenceCount: payload.stats?.evidence_nodes || payload.stats?.evidence || 0,
    companyCount: payload.stats?.companies || 0,
    syntheticRoot: true,
  };
  const children = payload.children || [];
  const columnCount = Math.max(1, Math.min(children.length || 1, children.length <= 6 ? children.length || 1 : 5));
  const rowGap = 82;
  const columnGap = 218;
  const chartCenterX = 640;
  const parentY = 70;
  const titleY = 158;
  const childStartY = 242;
  const childStartX = chartCenterX - ((columnCount - 1) * columnGap) / 2;
  const childType = children[0]?.type || "domain";
  const nodes = children.map((node, index) => ({
    position: {
      x: childStartX + (index % columnCount) * columnGap,
      y: childStartY + Math.floor(index / columnCount) * rowGap,
    },
    data: toNodeData(node),
  }));
  const levelTitle = {
    position: {
      x: chartCenterX,
      y: titleY,
    },
    data: {
      id: `level-title:${parent.id}`,
      label: TYPE_META[childType]?.label || "层级",
      nodeType: "levelTitle",
      color: TYPE_META[childType]?.color || TYPE_META.domain.color,
      titleNode: true,
    },
    selectable: false,
    grabbable: false,
  };
  return [
    {
      position: { x: chartCenterX, y: parentY },
      data: toNodeData(parent, {
        label: parent.syntheticRoot ? scopedRootLabel : parent.label,
        size: (TYPE_META[parent.type]?.size || 48) + 12,
        current: true,
      }),
    },
    ...nodes,
    levelTitle,
  ];
}

function nodeSummary(node) {
  if (!node) return "";
  if (node.type === "evidence") {
    return `${node.company || "企业未公开"} · ${node.city || ""}`;
  }
  return `${node.evidenceCount || 0} 条招聘证据 · ${node.companyCount || 0} 家企业`;
}

export default function HierarchyGraph({
  apiUrl,
  domain = "all",
  query = "",
  onSelect,
  onStats,
}) {
  const graphRef = useRef(null);
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [payload, setPayload] = useState({ children: [], path: [], stats: {} });
  const [parentId, setParentId] = useState(null);
  const [history, setHistory] = useState([]);
  const [hovered, setHovered] = useState(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [connectors, setConnectors] = useState([]);
  const [activeNodeId, setActiveNodeId] = useState("");

  const loadLevel = useCallback(async (nextParent, nextHistory = history) => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (domain !== "all") params.set("domain", domain);
    if (nextParent) params.set("parent_id", nextParent);
    const endpoint = nextParent ? "/api/graph/children" : "/api/graph/overview";
    try {
      const response = await fetch(`${apiUrl}${endpoint}?${params}`);
      if (!response.ok) throw new Error(`图谱接口返回 ${response.status}`);
      let next = await response.json();
      let resolvedParentId = nextParent;
      if (!nextParent && domain !== "all") {
        const domainNode = (next.children || []).find((node) => node.type === "domain" && node.label === domain);
        if (domainNode) {
          const scopedParams = new URLSearchParams({ domain, parent_id: domainNode.id });
          const scopedResponse = await fetch(`${apiUrl}/api/graph/children?${scopedParams}`);
          if (!scopedResponse.ok) throw new Error(`图谱接口返回 ${scopedResponse.status}`);
          next = await scopedResponse.json();
          resolvedParentId = domainNode.id;
        }
      }
      setPayload(next);
      setParentId(resolvedParentId);
      setHistory(nextHistory);
      setSelected(null);
      onSelect?.(null);
      onStats?.({
        ...(next.stats || {}),
        rendered_nodes: (next.children?.length || 0) + (next.parent ? 1 : 0),
        current_level: next.children?.[0]?.type || "domain",
      });
    } catch (reason) {
      setError(reason.message || "图谱层级加载失败");
    } finally {
      setLoading(false);
    }
  }, [apiUrl, domain, history, onSelect, onStats]);

  useEffect(() => {
    setHistory([]);
    loadLevel(null, []);
  }, [domain]); // eslint-disable-line react-hooks/exhaustive-deps

  const elements = useMemo(() => toElements(payload, domain), [payload, domain]);

  useEffect(() => {
    if (!containerRef.current || !elements.length) return undefined;
    cyRef.current?.destroy();
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      autoungrabify: true,
      boxSelectionEnabled: false,
      minZoom: 0.38,
      maxZoom: 2.2,
      pixelRatio: Math.min(window.devicePixelRatio, 1.5),
      layout: {
        name: "preset",
        animate: true,
        animationDuration: 520,
        animationEasing: "ease-out-cubic",
        fit: true,
        padding: window.innerWidth < 700 ? 34 : 46,
      },
      style: [
        {
          selector: "node",
          style: {
            width: 176,
            height: 42,
            shape: "round-rectangle",
            "background-color": "#071315",
            "background-opacity": 1,
            "border-width": 1,
            "border-color": "data(color)",
            "border-opacity": 0.78,
            label: "data(label)",
            color: "#ffffff",
            "font-family": "Microsoft YaHei",
            "font-size": 11,
            "font-weight": "bold",
            "text-wrap": "wrap",
            "text-max-width": 142,
            "text-valign": "center",
            "text-halign": "center",
            "text-margin-y": 0,
            "overlay-opacity": 0,
          },
        },
        {
          selector: "node[current]",
          style: {
            width: 250,
            height: 60,
            "background-color": "data(color)",
            "border-color": "data(color)",
            "border-width": 2,
            color: "#06131d",
            "font-size": 18,
            "text-max-width": 210,
          },
        },
        {
          selector: "node[titleNode]",
          style: {
            width: 126,
            height: 30,
            shape: "round-rectangle",
            "background-color": "rgba(8,19,21,0.86)",
            "border-color": "data(color)",
            "border-width": 1,
            color: "data(color)",
            "font-size": 12,
            "font-weight": 700,
            "text-max-width": 100,
            "text-valign": "center",
            "text-halign": "center",
            "events": "no",
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#62d8c4",
            "line-opacity": 0.72,
            "curve-style": "straight",
            "target-arrow-shape": "none",
          },
        },
        {
          selector: ".muted",
          style: { opacity: 0.12 },
        },
        {
          selector: ".related",
          style: {
            opacity: 1,
            "border-width": 3,
            "line-opacity": 0.92,
          },
        },
        {
          selector: "edge.related",
          style: {
            width: 3,
          },
        },
        {
          selector: ".search-hit",
          style: {
            "border-width": 4,
            "background-opacity": 0.52,
          },
        },
      ],
    });
    const updateConnectors = () => {
      const graphBox = graphRef.current?.getBoundingClientRect();
      const canvasBox = containerRef.current?.getBoundingClientRect();
      const parentNode = cy.nodes("[current]").first();
      const titleNode = cy.nodes("[titleNode]").first();
      const childNodes = cy.nodes().filter((node) => !node.data("current") && !node.data("titleNode"));
      if (!graphBox || !canvasBox || !parentNode.length || !titleNode.length) {
        setConnectors([]);
        return;
      }
      const offsetX = canvasBox.left - graphBox.left;
      const offsetY = canvasBox.top - graphBox.top;
      const point = (node) => {
        const position = node.renderedPosition();
        return {
          id: node.id(),
          x: offsetX + position.x,
          y: offsetY + position.y,
          width: node.renderedWidth(),
          height: node.renderedHeight(),
        };
      };
      const parentPoint = point(parentNode);
      const titlePoint = point(titleNode);
      const childIds = childNodes.map((node) => node.id());
      const nextConnectors = [
        {
          type: "line",
          activeFor: childIds,
          x1: parentPoint.x,
          y1: parentPoint.y + parentPoint.height / 2,
          x2: titlePoint.x,
          y2: titlePoint.y - titlePoint.height / 2,
        },
      ];
      if (childNodes.length) {
        const children = childNodes.map(point);
        const firstRowY = Math.min(...children.map((item) => item.y));
        const firstRow = children
          .filter((item) => Math.abs(item.y - firstRowY) < 12)
          .sort((a, b) => a.x - b.x);
        const columns = firstRow.map((root) => ({
          x: root.x,
          nodes: children
            .filter((item) => Math.abs(item.x - root.x) < 12)
            .sort((a, b) => a.y - b.y),
        }));
        const busPoints = Array.from(new Set([...columns.map((column) => Math.round(column.x)), Math.round(titlePoint.x)]))
          .sort((a, b) => a - b);
        const childTopY = Math.min(...firstRow.map((item) => item.y - item.height / 2));
        const busY = Math.round((titlePoint.y + titlePoint.height / 2 + childTopY) / 2);
        nextConnectors.push(
          {
            type: "line",
            activeFor: childIds,
            x1: titlePoint.x,
            y1: titlePoint.y + titlePoint.height / 2,
            x2: titlePoint.x,
            y2: busY,
          },
          ...busPoints.slice(0, -1).map((x1, index) => {
            const x2 = busPoints[index + 1];
            const segmentCenter = (x1 + x2) / 2;
            return {
              type: "line",
              activeFor: columns
                .filter((column) => {
                  const pathMin = Math.min(titlePoint.x, column.x);
                  const pathMax = Math.max(titlePoint.x, column.x);
                  return segmentCenter >= pathMin && segmentCenter <= pathMax;
                })
                .flatMap((column) => column.nodes.map((item) => item.id)),
              x1,
              y1: busY,
              x2,
              y2: busY,
            };
          }),
          ...firstRow.map((item) => ({
            type: "line",
            activeFor: columns
              .find((column) => Math.abs(column.x - item.x) < 12)
              ?.nodes.map((node) => node.id) || [item.id],
            x1: item.x,
            y1: busY,
            x2: item.x,
            y2: item.y - item.height / 2,
          })),
          ...columns.flatMap((column) => column.nodes.slice(0, -1).map((item, index) => {
            const nextItem = column.nodes[index + 1];
            return {
              type: "line",
              activeFor: column.nodes.slice(index + 1).map((node) => node.id),
              x1: column.x,
              y1: item.y + item.height / 2,
              x2: column.x,
              y2: nextItem.y - nextItem.height / 2,
            };
          })),
          ...columns.flatMap((column) => {
            return column.nodes.slice(1).map((item) => ({
              type: "line",
              guide: true,
              activeFor: [item.id],
              x1: column.x,
              y1: busY,
              x2: column.x,
              y2: item.y - item.height / 2,
            }));
          }),
        );
      }
      setConnectors(nextConnectors);
    };
    let connectorFrame = 0;
    const scheduleConnectors = () => {
      cancelAnimationFrame(connectorFrame);
      connectorFrame = requestAnimationFrame(updateConnectors);
    };
    cy.on("render", scheduleConnectors);
    scheduleConnectors();
    cy.on("mouseover", "node", (event) => {
      const node = event.target;
      if (node.data("titleNode")) return;
      cy.elements().addClass("muted");
      node.removeClass("muted").addClass("related");
      cy.nodes("[current], [titleNode]").removeClass("muted").addClass("related");
      setActiveNodeId(node.id());
      setHovered(node.data());
    });
    cy.on("mouseout", "node", () => {
      cy.elements().removeClass("muted related");
      setActiveNodeId("");
      setHovered(null);
    });
    cy.on("tap", "node", (event) => {
      const data = event.target.data();
      if (data.titleNode) return;
      setSelected(data);
      if (data.syntheticRoot) {
        onSelect?.(data);
        return;
      }
      if (data.nodeType === "evidence") {
        return;
      }
      const nextHistory = data.current
        ? history
        : [...history, { id: parentId, label: payload.parent?.label || "全局" }];
      loadLevel(data.id, nextHistory);
    });
    cy.on("tap", (event) => {
      if (event.target === cy) setSelected(null);
    });
    cyRef.current = cy;
    return () => {
      cancelAnimationFrame(connectorFrame);
      cy.destroy();
      if (cyRef.current === cy) cyRef.current = null;
    };
  }, [elements]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass("search-hit");
    const term = query.trim().toLowerCase();
    if (term.length < 2) return;
    const hit = cy.nodes().filter((node) => String(node.data("label") || "").toLowerCase().includes(term)).first();
    if (hit.length) {
      hit.addClass("search-hit");
      cy.animate({ center: { eles: hit }, zoom: 1.35 }, { duration: 420 });
    }
  }, [query, elements]);

  const back = () => {
    if (!history.length) {
      loadLevel(null, []);
      return;
    }
    const next = [...history];
    const target = next.pop();
    loadLevel(target.id, next);
  };

  const inspect = selected || hovered;
  const levelColor = TYPE_META[payload.children?.[0]?.type]?.color || TYPE_META.domain.color;
  return (
    <section ref={graphRef} className="hierarchy-graph" style={{ "--hierarchy-level-color": levelColor }}>
      <div className="hierarchy-grid" aria-hidden="true" />
      <div className="hierarchy-breadcrumb">
        <Button isIconOnly variant="ghost" onPress={back} isDisabled={!parentId && !history.length} aria-label="返回上一级">
          <ArrowLeft size={16} />
        </Button>
        <Button variant="ghost" onPress={() => loadLevel(null, [])}>全局</Button>
        {(payload.path || []).map((item) => (
          <React.Fragment key={item.id}>
            <ChevronRight size={13} />
            <Button variant="ghost" onPress={() => loadLevel(item.id, history)}>{item.label}</Button>
          </React.Fragment>
        ))}
        <span className="hierarchy-breadcrumb-meta">
          {TYPE_META[payload.children?.[0]?.type]?.label || "证据图谱"}
          <b>{payload.children?.length || 0}</b>
        </span>
      </div>
      <svg className="hierarchy-connectors" aria-hidden="true">
        {connectors.map((line, index) => (
          <line
            key={`${line.x1}-${line.y1}-${line.x2}-${line.y2}-${index}`}
            className={[
              line.guide ? "guide" : "",
              activeNodeId ? (line.activeFor?.includes(activeNodeId) ? "active" : "inactive") : "",
            ].filter(Boolean).join(" ")}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
          />
        ))}
      </svg>
      <div ref={containerRef} className="hierarchy-canvas" />
      {loading && (
        <div className="hierarchy-state">
          <LoaderCircle className="spin" size={22} />
          正在组织证据层级
        </div>
      )}
      {error && <div className="hierarchy-state error">{error}</div>}
      {!loading && !error && !payload.children?.length && (
        <div className="hierarchy-state">当前层级暂无已验证证据</div>
      )}
      {inspect && (
        <aside className="hierarchy-peek">
          <span className={inspect.nodeType === "evidence" ? "hierarchy-peek-evidence" : undefined}>
            {TYPE_META[inspect.nodeType]?.label || "节点"}
          </span>
          <h3>{inspect.label}</h3>
          <p>{inspect.description || nodeSummary(inspect)}</p>
          <div>
            <b>{inspect.evidenceCount || 0}</b><small>招聘证据</small>
            <b>{Math.round((inspect.confidence || inspect.qualityScore / 100 || 0) * 100)}%</b><small>证据置信度</small>
          </div>
          {selected && (
            <Button className="hierarchy-peek-action" variant="primary" onPress={() => onSelect?.(selected)}>
              <Focus size={15} />
              查看完整证据
            </Button>
          )}
          {inspect.sourceUrl && (
            <a className="hierarchy-source-link" href={inspect.sourceUrl} target="_blank" rel="noreferrer">
              原始岗位 <ExternalLink size={13} />
            </a>
          )}
        </aside>
      )}
      <div className="hierarchy-legend">
        {Object.entries(TYPE_META).map(([key, meta]) => (
          <span key={key}><i style={{ borderColor: meta.color, background: `${meta.color}22` }} />{meta.label}</span>
        ))}
      </div>
    </section>
  );
}
