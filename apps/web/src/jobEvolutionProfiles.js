export const FEATURED_EVOLUTION_QUERY = "AI Agent 应用开发工程师";
export const LEGACY_EVOLUTION_QUERY = "Java开发工程师";
export const EVOLUTION_PERIODS = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"];

export const PINNED_EVOLUTION_SEARCHES = [
  { query: FEATURED_EVOLUTION_QUERY, label: `${FEATURED_EVOLUTION_QUERY}（新兴岗位演示数据）`, demoType: "emerging" },
  { query: LEGACY_EVOLUTION_QUERY, label: `${LEGACY_EVOLUTION_QUERY}（既有岗位演示数据）`, demoType: "legacy" },
];

const FEATURED_EVOLUTION_BLUEPRINT = [
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库", "混合检索", "Rerank", "评测体系"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库", "混合检索", "Rerank", "评测体系", "Agent", "工具调用", "结构化输出"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库", "混合检索", "Rerank", "评测体系", "Agent", "工具调用", "结构化输出", "短期记忆", "LangGraph", "状态机"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库", "混合检索", "Rerank", "评测体系", "Agent", "工具调用", "结构化输出", "短期记忆", "LangGraph", "状态机", "MCP", "任务规划", "记忆管理"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库", "混合检索", "Rerank", "评测体系", "Agent", "工具调用", "结构化输出", "短期记忆", "LangGraph", "状态机", "MCP", "任务规划", "记忆管理", "多智能体", "协作编排"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库", "混合检索", "Rerank", "评测体系", "Agent", "工具调用", "结构化输出", "短期记忆", "LangGraph", "状态机", "MCP", "任务规划", "记忆管理", "多智能体", "协作编排", "自动化评测", "可观测性", "Tracing"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库", "混合检索", "Rerank", "评测体系", "Agent", "工具调用", "结构化输出", "短期记忆", "LangGraph", "状态机", "MCP", "任务规划", "记忆管理", "多智能体", "协作编排", "自动化评测", "可观测性", "Tracing", "Human-in-the-loop"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库", "混合检索", "Rerank", "评测体系", "Agent", "工具调用", "结构化输出", "短期记忆", "LangGraph", "状态机", "MCP", "任务规划", "记忆管理", "多智能体", "协作编排", "自动化评测", "可观测性", "Tracing", "Human-in-the-loop", "Guardrails", "红队测试"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库", "混合检索", "Rerank", "评测体系", "Agent", "工具调用", "结构化输出", "短期记忆", "LangGraph", "状态机", "MCP", "任务规划", "记忆管理", "多智能体", "协作编排", "自动化评测", "可观测性", "Tracing", "Human-in-the-loop", "Guardrails", "红队测试", "生产级编排", "权限治理", "模型网关"] },
  { title: "AI Agent 应用开发工程师", skills: ["Python", "LLM", "Prompt Engineering", "LangChain", "RAG", "Embedding", "向量数据库", "混合检索", "Rerank", "评测体系", "Agent", "工具调用", "结构化输出", "短期记忆", "LangGraph", "状态机", "MCP", "任务规划", "记忆管理", "多智能体", "协作编排", "自动化评测", "可观测性", "Tracing", "Human-in-the-loop", "Guardrails", "红队测试", "生产级编排", "权限治理", "模型网关", "Docker", "CI/CD", "成本优化", "弹性伸缩", "Kubernetes", "审计日志", "SLO 与告警"] },
];

const LEGACY_EVOLUTION_BLUEPRINT = [
  { title: "Java开发工程师", skills: ["Java", "Spring Boot", "MySQL", "Redis", "Linux", "Git"] },
  { title: "Java后端开发工程师", skills: ["Java", "Spring Boot", "MySQL", "Redis", "Linux", "微服务", "Kafka"] },
  { title: "Java微服务开发工程师", skills: ["Java", "Spring Boot", "微服务", "Kafka", "Redis", "Docker", "高并发"] },
  { title: "云原生Java工程师", skills: ["Java", "Spring Boot", "微服务", "Kafka", "Docker", "Kubernetes", "CI/CD", "可观测性"] },
  { title: "Java平台工程师", skills: ["Java", "Spring Boot", "微服务", "Kubernetes", "服务治理", "可观测性", "Python", "REST API"] },
  { title: "AI增强型Java工程师", skills: ["Java", "Spring Boot", "微服务", "Kubernetes", "Python", "LLM API", "Prompt Engineering", "REST API"] },
  { title: "智能应用Java工程师", skills: ["Java", "Spring Boot", "Python", "LLM API", "Prompt Engineering", "RAG", "向量数据库", "工具调用"] },
  { title: "Java AI应用工程师", skills: ["Java", "Spring Boot", "Python", "RAG", "向量数据库", "工具调用", "Agent", "评测体系"] },
  { title: "企业智能体集成工程师", skills: ["Java", "Spring Boot", "RAG", "Agent", "工具调用", "MCP", "权限治理", "可观测性"] },
  { title: "AI原生Java工程师", skills: ["Java", "Spring Boot", "Agent", "MCP", "模型网关", "Guardrails", "自动化评测", "Kubernetes"] },
  { title: "智能应用平台工程师", skills: ["Java", "Agent", "MCP", "模型网关", "多智能体", "权限治理", "成本优化", "可观测性"] },
  { title: "企业级智能体平台工程师", skills: ["Java", "Agent", "MCP", "多智能体", "生产级编排", "权限治理", "自动化评测", "弹性伸缩", "可观测性"] },
];

const DOMAIN_EVOLUTION_SUPPLEMENTS = {
  人工智能: ["Python", "LLM", "RAG", "向量数据库", "Agent", "评测体系", "Docker", "可观测性", "Kubernetes"],
  大数据: ["SQL", "Python", "Spark", "Flink", "Kafka", "湖仓一体", "数据治理", "实时计算", "可观测性"],
  智能系统: ["Python", "C++", "ROS2", "控制算法", "边缘推理", "数字孪生", "Docker", "可观测性", "自动化测试"],
  物联网: ["C", "C++", "RTOS", "MQTT", "边缘计算", "设备接入", "OTA", "数字孪生", "安全治理"],
};

const nodeType = (node) => node.nodeType || node.type;
const nodeTitle = (node) => node.title || node.label || "";
const nodeCategory = (node) => node.category || node.domain || "";
const nodeFamily = (node) => node.family || nodeTitle(node);
const nodeText = (node) => `${nodeTitle(node)} ${node.company || ""} ${nodeFamily(node)} ${(node.skills || []).join(" ")}`.toLowerCase();

export function isPinnedEvolutionQuery(query) {
  const term = String(query || "").trim().toLowerCase();
  return PINNED_EVOLUTION_SEARCHES.some((item) => item.query.toLowerCase() === term);
}

function demoDefinition(query) {
  const term = String(query || "").trim();
  if (/ai\s*agent|agentic|智能体/i.test(term)) return { type: "emerging", blueprint: FEATURED_EVOLUTION_BLUEPRINT, anchorPattern: /ai\s*agent|智能体/i };
  if (/java\s*开发工程师|java\s*工程师/i.test(term)) return { type: "legacy", blueprint: LEGACY_EVOLUTION_BLUEPRINT, anchorPattern: /java\s*开发工程师|java\s*工程师/i };
  return null;
}

export function buildJobEvolutionProfile(graph, query) {
  const term = String(query || "").trim().toLowerCase();
  if (!term) return null;
  const definition = demoDefinition(query);
  const graphPeriods = (graph?.layers || []).map((layer) => layer.id).filter((id) => /^202(5|6)-\d{2}$/.test(id)).slice(-12);
  const periods = definition ? EVOLUTION_PERIODS : graphPeriods;
  if (!periods.length || !graph?.nodes?.length) return null;
  const roleNodes = graph.nodes.filter((node) => ["job", "family"].includes(nodeType(node)));
  let anchor = roleNodes.find((node) => nodeText(node).includes(term));
  if (!anchor && definition) anchor = roleNodes
    .filter((node) => definition.anchorPattern.test(`${nodeTitle(node)} ${nodeFamily(node)}`))
    .sort((left, right) => Number(right.jobCount || 0) - Number(left.jobCount || 0))[0];
  if (!anchor) anchor = roleNodes.find((node) => nodeTitle(node).toLowerCase().includes(term));
  if (!anchor) return null;
  const familyKey = nodeFamily(anchor);
  const category = nodeCategory(anchor);
  const familyNodes = graph.nodes.filter((node) => nodeCategory(node) === category && nodeFamily(node) === familyKey);
  const familyJobs = familyNodes.filter((node) => nodeType(node) === "job");
  const familyHubs = familyNodes.filter((node) => nodeType(node) === "family");
  const actualSkills = [...new Set([...(anchor.skills || []), ...familyNodes.flatMap((node) => node.skills || [])].filter(Boolean))];
  const supplements = DOMAIN_EVOLUTION_SUPPLEMENTS[category] || [];
  let skillSeries;
  let titleSeries;
  if (definition) {
    const blueprintSkills = new Set(definition.blueprint.flatMap((frame) => frame.skills));
    const actualCore = definition.type === "emerging"
      ? []
      : actualSkills.filter((skill) => !blueprintSkills.has(skill)).slice(0, definition.type === "legacy" ? 2 : 3);
    skillSeries = periods.map((_, index) => [...new Set([...definition.blueprint[Math.min(index, definition.blueprint.length - 1)].skills, ...actualCore])]);
    titleSeries = periods.map((_, index) => definition.blueprint[Math.min(index, definition.blueprint.length - 1)].title);
  } else {
    const pool = [...new Set([...actualSkills, ...supplements])].slice(0, 16);
    const initialCount = Math.min(pool.length, Math.max(4, Math.min(7, actualSkills.length || 5)));
    skillSeries = periods.map((_, index) => {
      const growthRange = Math.max(0, pool.length - initialCount);
      const growthCount = periods.length > 1 ? Math.round(index / (periods.length - 1) * growthRange) : growthRange;
      const expanded = pool.slice(0, Math.min(pool.length, initialCount + growthCount));
      const retirementCount = index < 7 ? 0 : Math.min(2, Math.floor((index - 5) / 3));
      return retirementCount ? expanded.filter((__, skillIndex) => skillIndex >= retirementCount || skillIndex < 2) : expanded;
    });
    titleSeries = periods.map((periodId) => familyJobs.find((node) => node.period === periodId && nodeTitle(node))?.title || nodeTitle(anchor) || familyKey);
  }
  const frames = periods.map((periodId, index) => {
    const current = new Set(skillSeries[index]);
    const previous = new Set(skillSeries[Math.max(0, index - 1)]);
    const next = new Set(skillSeries[Math.min(skillSeries.length - 1, index + 1)]);
    const retired = index ? [...previous].filter((skill) => !current.has(skill)) : [];
    const names = [...new Set([...current, ...retired])];
    const skills = names.map((name, skillIndex) => {
      let state = "retained";
      if (retired.includes(name)) state = "retired";
      else if (index > 0 && !previous.has(name)) state = "added";
      else if (!next.has(name)) state = "declining";
      else if (index > 0 && skillIndex >= Math.max(0, current.size - 3)) state = "strengthened";
      const baseWeight = Math.max(0.35, 1 - skillIndex * 0.045);
      return { name, state, weight: state === "retired" ? 0.12 : state === "declining" ? baseWeight * 0.58 : state === "added" ? Math.min(1, baseWeight + 0.08) : baseWeight, evidenceType: actualSkills.includes(name) ? "real_jd" : definition ? "simulated" : "inferred" };
    });
    const periodAnchor = familyHubs.find((node) => node.period === periodId) || familyJobs.find((node) => node.period === periodId);
    return {
      period: periodId,
      title: titleSeries[index],
      anchorId: periodAnchor?.id || null,
      skills,
      addedSkills: skills.filter((skill) => skill.state === "added").map((skill) => skill.name),
      decliningSkills: skills.filter((skill) => skill.state === "declining").map((skill) => skill.name),
      retiredSkills: retired,
    };
  });
  return {
    anchorId: anchor.id,
    anchorTitle: nodeTitle(anchor) || familyKey,
    category,
    family: familyKey,
    featured: definition?.type === "emerging",
    demoFeatured: Boolean(definition),
    demoType: definition?.type || "general",
    demoLabel: definition?.type === "legacy" ? "既有岗位演示数据" : definition?.type === "emerging" ? "新兴岗位演示数据" : "岗位演进推断",
    containsSimulation: frames.some((frame) => frame.skills.some((skill) => skill.evidenceType !== "real_jd")),
    actualEvidenceCount: Number(anchor.jobCount || familyJobs.length || 0),
    frames,
  };
}
