import * as echarts from "echarts";
import {
  ArrowLeft,
  BarChart3,
  Building2,
  ChevronRight,
  CircleDot,
  ExternalLink,
  Layers3,
  Network,
  Search,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import "./ChinaTalentMap.css";

const DOMAIN_META = {
  人工智能: { color: "#ff7358", short: "AI" },
  大数据: { color: "#58d5c0", short: "DATA" },
  智能系统: { color: "#b9e85f", short: "SYSTEM" },
  物联网: { color: "#e9b95f", short: "IOT" },
};
const SOURCE_LABELS = {
  boss: "BOSS 直聘",
  zhaopin: "智联招聘",
  "51job": "前程无忧",
  liepin: "猎聘",
};
const DEPTH_META = [
  ["全国", "城市产业分布"],
  ["城市", "产业领域结构"],
  ["领域", "岗位族结构"],
  ["岗位族", "技能要求结构"],
  ["技能", "真实招聘证据"],
];

const requestJson = async (url) => {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
};

const formatDelta = (value) => {
  if (value === null || value === undefined) return "暂无对比";
  return `${value > 0 ? "+" : ""}${value}%`;
};

export default function ChinaTalentMap({ apiUrl }) {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);
  const reduceMotion = useReducedMotion();
  const [data, setData] = useState({ cities: [], links: [], periods: [], stats: {} });
  const [drill, setDrill] = useState(null);
  const [mapReady, setMapReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [drillLoading, setDrillLoading] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState("cluster");
  const [domainFilter, setDomainFilter] = useState("all");
  const [source, setSource] = useState("all");
  const [query, setQuery] = useState("");
  const [selectedCity, setSelectedCity] = useState("");
  const [depth, setDepth] = useState(0);
  const [selection, setSelection] = useState({ domain: "", family: "", skill: "" });
  const [activeEvidence, setActiveEvidence] = useState(null);
  const [compact, setCompact] = useState(() => window.innerWidth < 700);

  useEffect(() => {
    const update = () => setCompact(window.innerWidth < 700);
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ max_cities: "60" });
    if (domainFilter !== "all") params.set("domain", domainFilter);
    if (source !== "all") params.set("source_platform", source);
    Promise.all([
      requestJson("/maps/china.json"),
      requestJson(`${apiUrl}/api/knowledge-graph/city-map?${params}`),
    ])
      .then(([geoJson, payload]) => {
        if (!active) return;
        echarts.registerMap("talent-china", geoJson);
        setMapReady(true);
        setData(payload);
        setSelectedCity((current) =>
          payload.cities.some((item) => item.name === current)
            ? current
            : payload.cities[0]?.name || "",
        );
      })
      .catch((reason) => active && setError(reason.message || "地图数据加载失败"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [apiUrl, domainFilter, source]);

  useEffect(() => {
    if (!selectedCity) return undefined;
    let active = true;
    setDrillLoading(true);
    const params = new URLSearchParams({ city: selectedCity });
    if (source !== "all") params.set("source_platform", source);
    if (selection.domain) params.set("domain", selection.domain);
    if (selection.family) params.set("family", selection.family);
    if (selection.skill) params.set("skill", selection.skill);
    requestJson(`${apiUrl}/api/knowledge-graph/city-drilldown?${params}`)
      .then((payload) => {
        if (!active) return;
        setDrill(payload);
        setActiveEvidence(payload.level === "evidence" ? payload.children[0] || null : null);
      })
      .catch((reason) => active && setError(reason.message || "层级数据加载失败"))
      .finally(() => active && setDrillLoading(false));
    return () => {
      active = false;
    };
  }, [apiUrl, selectedCity, selection, source]);

  const selected = useMemo(
    () => data.cities.find((item) => item.name === selectedCity) || data.cities[0],
    [data.cities, selectedCity],
  );
  const filteredCities = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return data.cities;
    return data.cities.filter(
      (item) =>
        item.name.toLowerCase().includes(keyword) ||
        item.topFamilies.some((family) => family.name.toLowerCase().includes(keyword)) ||
        item.topSkills.some((skill) => skill.name.toLowerCase().includes(keyword)),
    );
  }, [data.cities, query]);

  const enterCity = (cityName) => {
    setSelectedCity(cityName);
    setSelection({ domain: "", family: "", skill: "" });
    setDepth(1);
  };

  const enterChild = (item) => {
    if (depth === 1) {
      setSelection({ domain: item.name, family: "", skill: "" });
      setDepth(2);
    } else if (depth === 2) {
      setSelection((current) => ({ ...current, family: item.name, skill: "" }));
      setDepth(3);
    } else if (depth === 3) {
      setSelection((current) => ({ ...current, skill: item.name }));
      setDepth(4);
    } else if (depth === 4) {
      setActiveEvidence(item);
    }
  };

  const goDepth = (target) => {
    if (target === 0) setSelection({ domain: "", family: "", skill: "" });
    if (target === 1) setSelection({ domain: "", family: "", skill: "" });
    if (target === 2) setSelection((current) => ({ domain: current.domain, family: "", skill: "" }));
    if (target === 3) setSelection((current) => ({ ...current, skill: "" }));
    setDepth(target);
  };

  useEffect(() => {
    if (!chartRef.current || !mapReady || !data.cities.length) return undefined;
    const chart = chartInstance.current || echarts.init(chartRef.current, null, { renderer: "canvas" });
    chartInstance.current = chart;
    const cityByName = new Map(data.cities.map((item) => [item.name, item]));
    const visibleNames = new Set(filteredCities.map((item) => item.name));

    if (depth === 0) {
      const maxValue = Math.max(1, ...filteredCities.map((city) => city.jobCount));
      const points = filteredCities.map((city) => ({
        name: city.name,
        value: [...city.coord, city.jobCount],
        itemStyle: { color: DOMAIN_META[city.dominantDomain]?.color || "#58d5c0" },
        symbolSize: Math.max(9, Math.min(42, 9 + Math.sqrt(city.jobCount / maxValue) * 30)),
        label: {
          show:
            city.name === selectedCity ||
            (!compact && city.jobCount >= (data.cities[7]?.jobCount || Infinity)),
        },
      }));
      const links = data.links
        .filter((item) => visibleNames.has(item.source) && visibleNames.has(item.target))
        .map((item) => ({
          coords: [cityByName.get(item.source)?.coord, cityByName.get(item.target)?.coord],
          value: item.similarity,
        }))
        .filter((item) => item.coords.every(Boolean));
      chart.setOption({
        animation: !reduceMotion,
        tooltip: {
          trigger: "item",
          confine: true,
          padding: 0,
          borderWidth: 0,
          backgroundColor: "transparent",
          formatter: (params) => {
            const city = cityByName.get(params.name);
            if (!city) return "";
            return `<div class="talent-map-tooltip"><span>${city.dominantDomain}</span><strong>${city.name}</strong><p>${city.jobCount.toLocaleString()} 个岗位 · ${city.companyCount.toLocaleString()} 家企业</p><small>点击进入产业结构</small></div>`;
          },
        },
        geo: {
          map: "talent-china",
          roam: true,
          zoom: 1.14,
          center: [104.8, 35.5],
          scaleLimit: { min: 0.9, max: 7 },
          layoutCenter: ["50%", "49%"],
          layoutSize: "112%",
          itemStyle: { areaColor: "#101b19", borderColor: "#34504b", borderWidth: 0.75 },
          emphasis: {
            itemStyle: { areaColor: "#1d302d", borderColor: "#78d9c6" },
            label: { show: false },
          },
          label: { show: false },
        },
        series: [
          ...(mode === "heat"
            ? [{
                type: "heatmap", coordinateSystem: "geo", data: points.map((item) => item.value),
                pointSize: 19, blurSize: 30, minOpacity: 0.2, maxOpacity: 0.8, silent: true,
              }]
            : [{
                type: "lines", coordinateSystem: "geo", data: links, zlevel: 2, silent: true,
                effect: {
                  show: mode === "flow" && !reduceMotion, period: 4.8, trailLength: 0.22,
                  symbolSize: 2.8, color: "#d9f17c",
                },
                lineStyle: {
                  color: mode === "flow" ? "#72d9c5" : "#597972",
                  width: mode === "flow" ? 1.25 : 0.8, opacity: mode === "flow" ? 0.58 : 0.3,
                  curveness: 0.18,
                },
              }]),
          {
            type: "effectScatter", coordinateSystem: "geo", data: points, zlevel: 4,
            rippleEffect: { scale: 2.2, brushType: "stroke", period: 4.2 },
            showEffectOn: reduceMotion ? "emphasis" : "render",
            itemStyle: {
              shadowBlur: 18, shadowColor: "rgba(84,221,194,.35)",
              borderColor: "rgba(233,249,241,.7)", borderWidth: 0.6,
            },
            label: {
              show: false, position: "right", distance: 7, color: "#dfeae5",
              fontSize: 10, fontWeight: 600, formatter: "{b}",
            },
            emphasis: { scale: 1.35, label: { show: true, color: "#fff" } },
          },
        ],
      }, true);
    } else if (drill) {
      const children = drill.children.slice(0, depth === 4 ? 20 : 18);
      const maxCount = Math.max(1, ...children.map((item) => item.jobCount || 1));
      const rootName = drill.focus?.name || selectedCity;
      const graphNodes = [
        {
          id: "focus", name: rootName, value: drill.summary.jobCount,
          symbolSize: compact ? 62 : 86, category: 0, draggable: false,
          itemStyle: { color: "#ecf5ef", borderColor: "#58d5c0", borderWidth: 3 },
          label: { color: "#10201c", fontSize: compact ? 12 : 15, fontWeight: 700 },
        },
        ...children.map((item, index) => ({
          id: item.id, name: item.name, value: item.jobCount || 1, raw: item,
          category: index % 4 + 1,
          symbolSize: Math.max(24, Math.min(60, 23 + Math.sqrt((item.jobCount || 1) / maxCount) * 34)),
          itemStyle: {
            color: item.type === "domain"
              ? DOMAIN_META[item.name]?.color
              : ["#ff7659", "#57d3be", "#b9e95f", "#e8b85f"][index % 4],
            shadowBlur: 16,
            shadowColor: "rgba(0,0,0,.24)",
          },
          label: {
            show: !compact || index < 7, color: "#e8f2ed", fontSize: 10,
            formatter: item.type === "evidence"
              ? `${item.name.slice(0, 12)}${item.name.length > 12 ? "…" : ""}`
              : item.name,
          },
        })),
      ];
      chart.setOption({
        animation: !reduceMotion,
        tooltip: {
          trigger: "item", confine: true, padding: 0, borderWidth: 0, backgroundColor: "transparent",
          formatter: ({ data: item }) => item.raw
            ? `<div class="talent-map-tooltip"><span>${DEPTH_META[depth][0]}</span><strong>${item.raw.name}</strong><p>${(item.raw.jobCount || 1).toLocaleString()} 条岗位证据</p><small>${depth < 4 ? "点击继续下钻" : "点击查看证据详情"}</small></div>`
            : "",
        },
        series: [{
          type: "graph",
          layout: "force",
          roam: true,
          data: graphNodes,
          links: children.map((item) => ({ source: "focus", target: item.id })),
          categories: [{ name: "focus" }, { name: "a" }, { name: "b" }, { name: "c" }, { name: "d" }],
          force: {
            repulsion: compact ? 220 : 430,
            gravity: 0.12,
            edgeLength: compact ? [75, 105] : [105, 165],
            layoutAnimation: !reduceMotion,
          },
          lineStyle: { color: "#46645d", width: 1, opacity: 0.52 },
          emphasis: {
            focus: "adjacency",
            scale: 1.22,
            lineStyle: { color: "#d9ee75", width: 1.8, opacity: 0.9 },
          },
        }],
      }, true);
    }

    const select = (params) => {
      if (depth === 0 && params.seriesType === "effectScatter" && cityByName.has(params.name)) {
        enterCity(params.name);
      } else if (depth > 0 && params.data?.raw) {
        enterChild(params.data.raw);
      }
    };
    chart.off("click");
    chart.on("click", select);
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [compact, data, depth, drill, filteredCities, mapReady, mode, reduceMotion, selectedCity]);

  useEffect(
    () => () => {
      chartInstance.current?.dispose();
      chartInstance.current = null;
    },
    [],
  );

  const focusSummary = depth === 0 ? {
    jobCount: selected?.jobCount,
    companyCount: selected?.companyCount,
    medianSalaryK: selected?.averageSalaryK,
    qualityScore: selected?.qualityScore,
  } : drill?.summary;
  const currentChildren = depth === 0 ? selected?.domainDistribution || [] : drill?.children || [];

  return (
    <main className="talent-atlas">
      <header className="atlas-header">
        <div>
          <span>NATIONAL TALENT INTELLIGENCE · EVIDENCE GRAPH</span>
          <h2>中国数字人才决策图谱</h2>
          <p>从地域需求进入岗位结构，逐层追溯到技能与真实招聘证据。</p>
        </div>
        <div className="atlas-header-actions">
          <label>
            <Search size={15} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索城市、岗位族或技能" />
          </label>
          <select value={domainFilter} onChange={(event) => { setDomainFilter(event.target.value); goDepth(0); }} aria-label="领域筛选">
            <option value="all">全部领域</option>
            {Object.keys(DOMAIN_META).map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={source} onChange={(event) => setSource(event.target.value)} aria-label="数据来源">
            <option value="all">全部招聘来源</option>
            {Object.entries(SOURCE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </div>
      </header>

      <nav className="atlas-depth-nav" aria-label="知识图谱层级">
        {DEPTH_META.map(([name, caption], index) => (
          <button
            key={name}
            className={`${index === depth ? "active" : ""} ${index < depth ? "done" : ""}`}
            disabled={index > depth}
            onClick={() => index <= depth && goDepth(index)}
          >
            <i>{String(index + 1).padStart(2, "0")}</i>
            <span><strong>{name}</strong><small>{caption}</small></span>
            {index < DEPTH_META.length - 1 && <ChevronRight size={13} />}
          </button>
        ))}
      </nav>

      <section className="atlas-stage">
        <aside className="atlas-context">
          <header>
            <span>{depth === 0 ? "城市需求强度" : "当前探索路径"}</span>
            <strong>{depth === 0 ? `${data.stats.cities || 0} 城` : `${depth}/4`}</strong>
          </header>
          {depth === 0 ? (
            <div className="atlas-city-list">
              {filteredCities.slice(0, 10).map((city, index) => (
                <button key={city.name} className={city.name === selectedCity ? "active" : ""} onClick={() => enterCity(city.name)}>
                  <i>{String(index + 1).padStart(2, "0")}</i>
                  <span><strong>{city.name}</strong><small>{city.dominantDomain}</small></span>
                  <b>{city.jobCount.toLocaleString()}</b>
                </button>
              ))}
            </div>
          ) : (
            <>
              <button className="atlas-back" onClick={() => goDepth(depth - 1)}>
                <ArrowLeft size={15} /> 返回上一层
              </button>
              <ol className="atlas-path">
                <li><i><CircleDot size={12} /></i><span><small>城市</small><strong>{selectedCity}</strong></span></li>
                {selection.domain && <li><i /><span><small>领域</small><strong>{selection.domain}</strong></span></li>}
                {selection.family && <li><i /><span><small>岗位族</small><strong>{selection.family}</strong></span></li>}
                {selection.skill && <li><i /><span><small>技能</small><strong>{selection.skill}</strong></span></li>}
              </ol>
              <div className="atlas-level-guide">
                <Layers3 size={17} />
                <span>
                  <strong>{DEPTH_META[depth][1]}</strong>
                  <small>{depth < 4 ? "点击图中节点进入下一层" : "点击证据节点查看完整招聘信息"}</small>
                </span>
              </div>
            </>
          )}
        </aside>

        <div className="atlas-map-shell">
          {depth === 0 && (
            <div className="atlas-mode-switch" aria-label="地图模式">
              {[
                ["cluster", Network, "产业集群"],
                ["heat", TrendingUp, "岗位热度"],
                ["flow", Sparkles, "技能流向"],
              ].map(([value, Icon, label]) => (
                <button key={value} className={mode === value ? "active" : ""} onClick={() => setMode(value)} title={label}>
                  <Icon size={16} /><span>{label}</span>
                </button>
              ))}
            </div>
          )}
          {depth > 0 && (
            <div className="atlas-focus-label">
              <span>{DEPTH_META[depth][0]}层</span>
              <strong>{drill?.focus?.name || selectedCity}</strong>
              <small>{drillLoading ? "正在计算关系…" : `${drill?.children?.length || 0} 个下级节点`}</small>
            </div>
          )}
          <div className="atlas-map" ref={chartRef} />
          {(loading || error || drillLoading) && (
            <div className={`atlas-loading ${error ? "error" : ""}`}>
              <i /><span>{error || (drillLoading ? "正在计算下一层证据关系…" : "正在构建城市人才图谱…")}</span>
            </div>
          )}
          {depth === 0 && (
            <div className="atlas-legend">
              {Object.entries(DOMAIN_META).map(([name, meta]) => (
                <span key={name}><i style={{ background: meta.color }} />{name}</span>
              ))}
            </div>
          )}
          <div className="atlas-map-note">
            <Target size={13} />
            {depth === 0 ? "点击城市节点进入产业领域层" : depth < 4 ? "节点大小代表岗位证据量" : "节点代表可回溯的真实 JD"}
          </div>
        </div>

        <aside className="atlas-inspector">
          <AnimatePresence mode="wait">
            <motion.div
              key={`${depth}-${drill?.focus?.name || selectedCity}`}
              initial={{ opacity: 0, x: reduceMotion ? 0 : 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: reduceMotion ? 0 : -8 }}
            >
              <header>
                <span>{DEPTH_META[depth][1]} · DECISION VIEW</span>
                <h3>{depth === 0 ? selectedCity : drill?.focus?.name}</h3>
                <p>
                  {(focusSummary?.jobCount || 0).toLocaleString()} 条岗位证据，
                  覆盖 {(focusSummary?.companyCount || 0).toLocaleString()} 家招聘企业
                </p>
              </header>
              <div className="atlas-kpis">
                <div><span>薪资中位数</span><strong>{focusSummary?.medianSalaryK ? `${focusSummary.medianSalaryK}K` : "—"}</strong></div>
                <div><span>证据质量</span><strong>{focusSummary?.qualityScore || "—"}</strong></div>
                {depth > 0 && (
                  <div className="wide">
                    <span>最新采集批次变化</span>
                    <strong className={(focusSummary?.batchDelta || 0) >= 0 ? "positive" : "negative"}>
                      {formatDelta(focusSummary?.batchDelta)}
                    </strong>
                  </div>
                )}
              </div>

              {depth < 4 ? (
                <section className="atlas-child-ledger">
                  <div><span>{depth === 0 ? "领域结构" : "下级节点"}</span><small>岗位量 / 占比</small></div>
                  {currentChildren.slice(0, 8).map((item, index) => {
                    const name = item.name;
                    const count = item.jobCount ?? item.value;
                    const share = item.share ?? item.rate;
                    return (
                      <button key={name} onClick={() => depth === 0 ? enterCity(selectedCity) : enterChild(item)}>
                        <i style={{ background: DOMAIN_META[name]?.color || ["#ff7659", "#58d5c0", "#b9e85f", "#e9b95f"][index % 4] }} />
                        <span><strong>{name}</strong><small>{item.topSkills?.slice(0, 3).join(" · ") || `${share}% 岗位占比`}</small></span>
                        <b>{Number(count || 0).toLocaleString()}</b>
                        <em>{share}%</em>
                        <ChevronRight size={13} />
                      </button>
                    );
                  })}
                </section>
              ) : (
                <section className="atlas-evidence-list">
                  <div><span>真实招聘证据</span><small>{drill?.children?.length || 0} 条</small></div>
                  {(drill?.children || []).slice(0, 10).map((job) => (
                    <button key={job.id} className={activeEvidence?.id === job.id ? "active" : ""} onClick={() => setActiveEvidence(job)}>
                      <i><Building2 size={13} /></i>
                      <span><strong>{job.title}</strong><small>{job.company} · {job.salary}</small></span>
                      <ChevronRight size={13} />
                    </button>
                  ))}
                </section>
              )}

              {depth > 0 && depth < 4 && (
                <section className="atlas-decisions">
                  <div><span>企业决策提示</span><small>基于当前层证据</small></div>
                  {(drill?.summary?.topResponsibilities || []).slice(0, 3).map((item, index) => (
                    <p key={item}><i>{index + 1}</i><span>{item}</span></p>
                  ))}
                </section>
              )}

              {depth === 4 && activeEvidence && (
                <section className="atlas-evidence-detail">
                  <span>{SOURCE_LABELS[activeEvidence.sourcePlatform] || activeEvidence.sourcePlatform || "招聘来源"} · 质量 {activeEvidence.qualityScore}</span>
                  <h4>{activeEvidence.title}</h4>
                  <p>{activeEvidence.snippet}</p>
                  <div>{activeEvidence.skills?.slice(0, 6).map((item) => <i key={item}>{item}</i>)}</div>
                  <a href={activeEvidence.sourceUrl} target="_blank" rel="noreferrer">
                    查看原始岗位 <ExternalLink size={13} />
                  </a>
                </section>
              )}

              {depth === 0 && (
                <button className="atlas-enter" onClick={() => enterCity(selectedCity)}>
                  进入 {selectedCity} 产业结构 <ChevronRight size={15} />
                </button>
              )}
            </motion.div>
          </AnimatePresence>
        </aside>
      </section>

      <footer className="atlas-decision-strip">
        <div><BarChart3 size={16} /><span>当前视角</span><strong>{DEPTH_META[depth][1]}</strong></div>
        <div><Building2 size={16} /><span>岗位证据</span><strong>{(focusSummary?.jobCount || 0).toLocaleString()}</strong></div>
        <div><Network size={16} /><span>下级节点</span><strong>{currentChildren.length}</strong></div>
        <button onClick={() => goDepth(0)}>返回全国总览 <ChevronRight size={14} /></button>
      </footer>
    </main>
  );
}
