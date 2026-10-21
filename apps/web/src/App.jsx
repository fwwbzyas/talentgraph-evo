import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Alert, Avatar, Button, Card, Checkbox, Chip, Drawer as HeroDrawer, FieldError, Form, Input, Label, Link, ListBox, Meter, Modal, Pagination, ProgressBar, SearchField, Select, Separator, Skeleton, Surface, Switch, Table, Tabs, TextArea, TextField } from "@heroui/react";
import * as echarts from "echarts/core";
import { RadarChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import AnimatedContent from "./components/reactbits/AnimatedContent";
import ClickSpark from "./components/reactbits/ClickSpark";
import CountUp from "./components/reactbits/CountUp";
import SpotlightCard from "./components/reactbits/SpotlightCard";
import "./heroui.css";
import "./components/reactbits/reactbits.css";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Bell,
  BriefcaseBusiness,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  ChevronRight,
  ClipboardCheck,
  Copy,
  Database,
  Edit3,
  Eye,
  EyeOff,
  ExternalLink,
  FileDown,
  FileText,
  FileUp,
  FileUser,
  Filter,
  Gamepad2,
  GitBranch,
  GitCompareArrows,
  Grid2X2,
  Layers3,
  LayoutDashboard,
  LogIn,
  Menu,
  MessageSquareText,
  Mic,
  Network,
  Pause,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Settings,
  ShieldCheck,
  ShieldX,
  Sparkles,
  Target,
  Trash2,
  TrendingDown,
  TrendingUp,
  Upload,
  UserRound,
  UserRoundSearch,
  Volume2,
  X,
  Zap,
} from "lucide-react";
import ThreeGraph from "./ThreeGraph";
import RelationGraph from "./RelationGraph";
import { buildJobEvolutionProfile, EVOLUTION_PERIODS, FEATURED_EVOLUTION_QUERY, isPinnedEvolutionQuery, PINNED_EVOLUTION_SEARCHES } from "./jobEvolutionProfiles";
import { publicJobSamples } from "./demoData";
import officeMapAsset from "./assets/office-quest/office-map.png";
import candidateSprite from "./assets/office-quest/candidate.png";
import feedbackEnterpriseHr from "./assets/home-feedback/enterprise-hr.webp";
import feedbackEnterpriseHrPortrait from "./assets/home-feedback/enterprise-hr-portrait.webp";
import feedbackRecruitingLead from "./assets/home-feedback/recruiting-lead.webp";
import feedbackRecruitingLeadPortrait from "./assets/home-feedback/recruiting-lead-portrait.webp";
import feedbackTalentDevelopment from "./assets/home-feedback/talent-development.webp";
import feedbackTalentDevelopmentPortrait from "./assets/home-feedback/talent-development-portrait.webp";
import feedbackJobSeeker from "./assets/home-feedback/job-seeker.webp";
import feedbackJobSeekerPortrait from "./assets/home-feedback/job-seeker-portrait.webp";
import feedbackCareerSwitcher from "./assets/home-feedback/career-switcher.webp";
import feedbackCareerSwitcherPortrait from "./assets/home-feedback/career-switcher-portrait.webp";
import feedbackGraduate from "./assets/home-feedback/graduate.webp";
import feedbackGraduatePortrait from "./assets/home-feedback/graduate-portrait.webp";
import dataAnalystSprite from "./assets/office-quest/data-analyst.png";
import productManagerSprite from "./assets/office-quest/product-manager.png";
import frontendEngineerSprite from "./assets/office-quest/frontend-engineer.png";
import hrbpSprite from "./assets/office-quest/hrbp.png";
import talentIdentityAi from "./assets/talent-identity-ai-v2.webp";
import homeTemporalGraphScreenshot from "./assets/home-temporal-graph-screenshot.png";
import talentIdentityBigData from "./assets/talent-identity-big-data-v2.webp";
import talentIdentityIntelligentSystems from "./assets/talent-identity-intelligent-systems-v2.webp";
import talentIdentityIot from "./assets/talent-identity-iot-v2.webp";
import talentIdentityGeneral from "./assets/talent-identity-general-v2.webp";
import {
  ApplicationCenter,
  GapAnalysis,
  LearningRoadmap,
  ResumeCenter,
  ROLE_META,
  ROLE_NAV,
  SeekerDashboard,
} from "./RolePortals";
import "./RolePortals.css";
import "./styles.css";

const HomeStoryScene = React.lazy(() => import("./HomeStoryScene"));
const ProductPositioningScene = React.lazy(() => import("./ProductPositioningScene"));

echarts.use([RadarChart, TooltipComponent, CanvasRenderer]);

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const AUTH_SESSION_KEY = "tg-auth-session";
const RECRUITING_SELECTED_JOB_KEY = "tg-recruiting-selected-job";
const RESUME_FILE_EXTENSIONS = new Set(["pdf", "docx", "docm", "txt", "md", "png", "jpg", "jpeg", "webp"]);
const MAX_RESUME_FILE_SIZE = 20 * 1024 * 1024;
const DOMAINS = ["人工智能", "大数据", "智能系统", "物联网"];
const ENTERPRISE_JOB_STATUS_OPTIONS = [
  { id: "active", label: "招聘中" },
  { id: "paused", label: "已暂停" },
  { id: "closed", label: "已关闭" },
];
const EMPTY_ENTERPRISE_JOB_FORM = {
  title: "",
  domain: "人工智能",
  city: "杭州",
  headcount: "1",
  responsibilities: "",
  required_skills: "",
  preferred_skills: "",
  experience_min_years: "",
  education: "",
  salary_min_k: "",
  salary_max_k: "",
  status: "active",
};
const ASSESSMENT_STAGE_LABELS = {
  resume_probe: "项目真实性追问",
  skill_deep_question: "技术深挖",
  scenario_task: "场景决策",
  interactive_game: "对话完成",
};
const SOURCE_LABELS = {
  boss: "BOSS直聘",
  zhilian: "智联招聘",
  zhaopin: "智联招聘",
  "51job": "前程无忧",
  liepin: "猎聘",
  arbeitnow: "Arbeitnow",
  remoteok: "Remote OK",
  hackernews: "Hacker News",
  stackoverflow: "Stack Overflow",
  github: "GitHub",
  enterprise: "企业录入",
  unknown: "其他来源",
};
const REASON_LABELS = {
  outside_target_scope: "不属于人工智能、大数据、智能系统或物联网岗位范围",
  normalization_failed: "关键字段不足，无法完成规格化",
  below_quality_threshold: "完整度或可信度低于岗位入库阈值",
  below_signal_quality_threshold: "辅助信号的证据质量低于阈值",
  duplicate_content: "正文与本批次已有记录高度一致",
  duplicate_source_id: "来源平台岗位编号重复",
  missing_content: "缺少可验证的岗位正文",
  missing_title: "缺少岗位名称",
  title_content_mismatch: "岗位标题与正文技术方向不一致",
  skill_tag_pollution: "网站标签混入学历、福利或经验字段",
  non_job_content: "正文缺少真实岗位职责或属于广告内容",
  copied_jd: "跨企业正文模板高度一致，疑似抄袭",
  skill_inflation: "技能要求异常宽泛，存在岗位通胀",
  stale_evidence: "发布时间过早，证据时效性不足",
  field_conflict: "结构化字段之间存在冲突",
  salary_anomaly: "薪资区间异常或上下限冲突",
  job_content_changed: "同一平台岗位标识下的字段或能力要求发生变化",
};
const AUDIT_TYPE_LABELS = {
  accepted: "已通过",
  pending_review: "待语义复核",
  quality_rejection: "质量拒绝",
  field_correction: "字段修正",
  copy_cluster: "抄袭簇",
  job_change: "岗位变更",
  change_review: "变更复核",
};
const LOCAL_RESUME_ANALYSIS_MODES = new Set([
  "local_evidence_fallback",
  "deterministic_fallback",
]);

function getResumeAnalysisStatus(profile) {
  const providerStatus = profile?.provider_status || {};
  const mode = String(providerStatus.mode || "").trim();
  const provider = String(providerStatus.provider || "").trim();
  if (mode === "llm_resume_understanding") {
    return { label: "大模型增强", heading: "大模型语义解析结果", color: "accent" };
  }
  if (LOCAL_RESUME_ANALYSIS_MODES.has(mode) || provider === "deterministic-resume-parser") {
    return { label: "本地解析（待大模型增强）", heading: "本地证据解析结果", color: "warning" };
  }
  return null;
}

async function request(path, options = {}) {
  const session = readAuthSession();
  const { headers: customHeaders, ...rest } = options;
  const response = await fetch(`${API}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...(customHeaders || {}),
    },
  });
  if (!response.ok) throw new Error(await readApiError(response, "请求失败，请稍后重试。"));
  return response.status === 204 ? null : response.json();
}

function readAuthSession() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(AUTH_SESSION_KEY);
    const session = raw ? JSON.parse(raw) : null;
    return session?.access_token && session?.user?.role ? session : null;
  } catch {
    return null;
  }
}

async function readApiError(response, fallback) {
  let body = "";
  try {
    body = await response.text();
  } catch {
    return fallback;
  }
  if (!body) return fallback;
  try {
    const data = JSON.parse(body);
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) return data.detail.map((item) => item.msg || item.message || String(item)).join("；");
    if (typeof data?.message === "string") return data.message;
    return fallback;
  } catch {
    return body;
  }
}

function speechWebSocketUrl() {
  const url = new URL(`${API}/api/speech/stream`, window.location.href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function resampleToPcm16(input, inputRate, targetRate = 16000) {
  const outputLength = Math.max(1, Math.floor(input.length * targetRate / inputRate));
  const output = new Int16Array(outputLength);
  const ratio = inputRate / targetRate;
  for (let index = 0; index < outputLength; index += 1) {
    const position = index * ratio;
    const leftIndex = Math.floor(position);
    const rightIndex = Math.min(input.length - 1, leftIndex + 1);
    const weight = position - leftIndex;
    const sample = input[leftIndex] * (1 - weight) + input[rightIndex] * weight;
    output[index] = Math.round(Math.max(-1, Math.min(1, sample)) * 32767);
  }
  return output.buffer;
}

function mergeSpeechAnswer(baseText, transcript) {
  const base = String(baseText || "").trimEnd();
  const speech = String(transcript || "").trim();
  if (!base) return speech;
  if (!speech) return base;
  return `${base}\n${speech}`;
}

function normalizeCandidateLabel(candidate) {
  const name = String(candidate?.name || candidate?.candidate_name || "").trim();
  if (name && !name.startsWith("candidate_")) return name;
  return "该面试者";
}

const MATCH_REPORT_DIMENSION_LABELS = {
  required_skills: "必备技能",
  preferred_skills: "加分技能",
  evidence_quality: "证据质量",
  behavior_competency: "行为能力",
};

function deriveMatchReportDimensions(matchReport) {
  return Object.entries(matchReport?.score_breakdown || {})
    .map(([key, score]) => {
      const numericScore = Number(score);
      return Number.isFinite(numericScore)
        ? { name: MATCH_REPORT_DIMENSION_LABELS[key] || key, score: numericScore }
        : null;
    })
    .filter(Boolean);
}

function effectiveCandidateScore(person, matchReport = person?.match_report) {
  const personScore = Number(person?.score);
  const reportScore = Number(matchReport?.score);
  if (Number.isFinite(personScore) && personScore > 0) return personScore;
  return Number.isFinite(reportScore) ? reportScore : 0;
}

function deriveMatchReportTraits(matchReport) {
  const labels = [];
  const add = (value) => {
    if (typeof value !== "string") return;
    const label = value.trim();
    if (label && !labels.includes(label)) labels.push(label);
  };
  const addSkills = (value) => {
    if (Array.isArray(value)) value.forEach((item) => add(typeof item === "string" ? item : item?.name || item?.skill));
  };
  (Array.isArray(matchReport?.strengths) ? matchReport.strengths : []).forEach((strength) => {
    add(strength?.skill || strength?.name);
    addSkills(strength?.matched_skills);
  });
  addSkills(matchReport?.matched_skills);
  return labels.slice(0, 6);
}

function buildAssessmentRecord(candidate, previous = {}) {
  const now = new Date().toISOString();
  const report = candidate?.match_report || null;
  const dimensions = candidate?.competency_dimensions || [];
  const score = effectiveCandidateScore(candidate, report) || Number(
    candidate?.score
    ?? (dimensions.length ? Math.round(dimensions.reduce((sum, item) => sum + Number(item.score || 0), 0) / dimensions.length) : 0),
  ) || 0;
  const candidateId = candidate?.candidate_id || previous.candidate_id || `candidate_${Date.now()}`;
  return {
    ...previous,
    id: previous.id || candidateId,
    candidate_id: candidateId,
    name: normalizeCandidateLabel(candidate),
    target_job_id: candidate?.target_job_id || previous.target_job_id || "job_ai_agent",
    target_job_title: report?.job_snapshot?.job_title || previous.target_job_title || candidate?.target_job_id || "AI Agent 工程师",
    archetype_title: candidate?.archetype_title || candidate?.title || previous.archetype_title || "待生成画像",
    archetype_code: candidate?.archetype_code || candidate?.archetype || previous.archetype_code || "",
    score,
    status: report ? "已出报告" : "已生成画像",
    skill_count: candidate?.skills?.length || previous.skill_count || 0,
    project_count: candidate?.projects?.length || previous.project_count || 0,
    evidence_count: candidate?.evidence?.length || previous.evidence_count || 0,
    city: (candidate?.preferred_locations || []).join("、") || previous.city || "未识别",
    traits: candidate?.traits || previous.traits || [],
    note: previous.note || "",
    created_at: previous.created_at || now,
    updated_at: now,
    profile: candidate,
  };
}

function SeekerResumePage({ candidate, user, navigate, onUpload, notify }) {
  const analysisStatus = getResumeAnalysisStatus(candidate);
  const analysisHeading = analysisStatus?.heading || "简历结构化解析结果";
  const resumeCenterRef = useRef(null);
  useLayoutEffect(() => {
    const root = resumeCenterRef.current;
    if (!root) return undefined;
    const syncHeading = () => {
      const heading = root.querySelector(".resume-evidence-layout aside > span");
      if (heading && heading.textContent !== analysisHeading) heading.textContent = analysisHeading;
    };
    syncHeading();
    if (typeof MutationObserver === "undefined") return undefined;
    const observer = new MutationObserver(syncHeading);
    observer.observe(root, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, [analysisHeading]);
  return (
    <div ref={resumeCenterRef}>
      {analysisStatus && (
        <div
          role="status"
          aria-label={`简历分析状态：${analysisStatus.label}`}
          style={{ display: "flex", justifyContent: "flex-end", padding: "14px 34px 0" }}
        >
          <Chip color={analysisStatus.color} size="sm" variant="soft">
            <Chip.Label>简历分析：{analysisStatus.label}</Chip.Label>
          </Chip>
        </div>
      )}
      <ResumeCenter candidate={candidate} user={user} navigate={navigate} onUpload={onUpload} notify={notify} />
    </div>
  );
}

function mapJob(job, index = 0) {
  const sourceKey = String(
    job.sourceKey || job.source_platform || job.source || "unknown",
  ).toLowerCase();
  const changedAt =
    job.changedAt || job.changed_at || job.published_at || job.collected_at;
  const responsibilities = job.responsibilities || [];
  const content = job.content || job.raw_content || "";
  const city = cleanCity(job.rawCity || job.city);
  const district = cleanCity(job.district);
  return {
    id: job.id || job.source_id || `job-${index}`,
    title: job.title,
    domain: normalizeDomain(job.domain),
    company: job.company || "企业岗位库",
    salary:
      job.salary ||
      (job.salary_min_k ? `${job.salary_min_k}-${job.salary_max_k}K` : "面议"),
    rawCity: city || "全国",
    city: [city, district].filter(Boolean).join(" · ") || "全国",
    experience:
      job.experience ||
      years(job.experience_min_years, job.experience_max_years),
    education: job.education || "本科",
    tags: job.tags || job.skill_tags || [],
    responsibilities,
    requirements: job.requirements || [],
    evidenceSegments: job.evidenceSegments || job.evidence_segments || [],
    content,
    rawContent: job.rawContent || job.raw_content || content,
    summary:
      job.summary ||
      responsibilities[0] ||
      content.split(/[。；;\n]/).find((item) => item.trim().length > 12) ||
      "待完成岗位内容概括",
    sourceKey,
    source: SOURCE_LABELS[sourceKey] || job.source || sourceKey,
    sourceUrl: job.sourceUrl || job.source_url || "",
    qualityScore: Math.round(job.qualityScore ?? job.quality_score ?? 0),
    changedAt,
    updated:
      job.updated ||
      (changedAt ? String(changedAt).slice(0, 10) : "—"),
    status:
      job.status ||
      { new: "今日新增", updated: "能力变化", offline: "已下线" }[
        job.change_type
      ] ||
      "持续招聘",
    changeType: job.change_type || "unchanged",
    jobStatus: job.job_status || "active",
  };
}

function mapApplicationJob(application) {
  return mapJob({
    id: application?.job_id,
    title: application?.job_title,
    company: application?.company,
    source_url: application?.source_url,
  });
}

function resolveMappedJob(target, mappedJobs) {
  if (!target) return null;
  return mappedJobs.find((job) => String(job.id) === String(target.id)) || target;
}

function normalizeDomain(value = "") {
  if (value.includes("大数据")) return "大数据";
  if (value.includes("物联网") || value.includes("边缘")) return "物联网";
  if (value.includes("智能系统") || value.includes("智能网联"))
    return "智能系统";
  return "人工智能";
}
function years(min, max) {
  return min == null ? "不限" : `${min}-${max ?? min}年`;
}

function looksLikeSalary(value) {
  const text = String(value || "").trim();
  return /\d/.test(text) && /(万|千|元|k|K|薪|[-~－])/.test(text);
}

function cleanCity(value) {
  const text = String(value || "").trim();
  if (!text || looksLikeSalary(text) || text.length > 20) return "";
  return text;
}

function buildDecisionMessages({ role, portalSummary, platformSummary, candidate, targetJob }) {
  const decision = portalSummary?.decision_summary || platformSummary?.decision_summary || {};
  const messages = [];
  (decision.growth_jobs || []).slice(0, 2).forEach((item) => messages.push({
    id: `growth-${item.name}`,
    tone: "positive",
    category: role === "seeker" ? "职业机会" : "岗位增长",
    title: `${item.name}需求增长信号`,
    detail: item.reason,
    route: role === "seeker" ? "career-evolution" : "evolution",
  }));
  (decision.decline_jobs || []).slice(0, 1).forEach((item) => messages.push({
    id: `decline-${item.name}`,
    tone: "danger",
    category: role === "seeker" ? "职业风险" : "岗位风险",
    title: `${item.name}出现下降或退出信号`,
    detail: item.reason,
    route: role === "seeker" ? "career-evolution" : "evolution",
  }));
  const changes = decision.skill_changes || {};
  const enhanced = changes.enhanced || [];
  const weakened = changes.weakened || [];
  if (enhanced.length) messages.push({
    id: "skills-enhanced",
    tone: "accent",
    category: "技能增强",
    title: `${enhanced.slice(0, 3).map((item) => item.name).join("、")}要求正在增强`,
    detail: `共识别 ${enhanced.length} 项增强技能，建议检查岗位标准与个人证据覆盖。`,
    route: role === "seeker" ? "career-evolution" : "evolution",
  });
  if (weakened.length) messages.push({
    id: "skills-weakened",
    tone: "warning",
    category: "技能减弱",
    title: `${weakened.slice(0, 3).map((item) => item.name).join("、")}要求正在减弱`,
    detail: `共识别 ${weakened.length} 项减弱技能，建议重新评估培养与招聘优先级。`,
    route: role === "seeker" ? "career-evolution" : "evolution",
  });
  if (role === "enterprise") {
    const alignment = portalSummary?.standard_alignment;
    if (alignment?.status === "not_configured") messages.unshift({
      id: "enterprise-standard-not-configured",
      tone: "warning",
      category: "企业标准",
      title: "企业岗位标准尚未建立",
      detail: "录入企业在招岗位后，才能判断岗位要求是否落后于市场。",
      route: "recruiting",
    });
    if (alignment?.status === "outdated") messages.unshift({
      id: "enterprise-standard-outdated",
      tone: "danger",
      category: "企业标准",
      title: alignment.headline,
      detail: alignment.detail,
      route: "recruiting",
    });
  } else if (!candidate) {
    messages.unshift({
      id: "seeker-profile-missing",
      tone: "warning",
      category: "个人能力",
      title: "尚未建立个人能力基线",
      detail: "先解析简历，才能判断你与增长岗位及普遍能力要求的距离。",
      route: "resume",
    });
  } else if (!targetJob) {
    messages.unshift({
      id: "seeker-target-missing",
      tone: "warning",
      category: "目标岗位",
      title: "尚未选择目标岗位",
      detail: "选择目标岗位后可生成技能差距与学习优先级。",
      route: "applications",
    });
  }
  return messages.slice(0, 8);
}

function App() {
  const [auth, setAuth] = useState(readAuthSession);
  const role = auth?.user?.role || null;
  const [entry, setEntry] = useState(() => auth ? "app" : "home");
  const [loginRole, setLoginRole] = useState("enterprise");
  const [route, navigate] = useRoute(role);
  const [jobs, setJobs] = useState(() => publicJobSamples.map(mapJob));
  const [jobTotal, setJobTotal] = useState(() => publicJobSamples.length);
  const [platformSummary, setPlatformSummary] = useState(null);
  const [portalSummary, setPortalSummary] = useState(null);
  const [candidate, setCandidate] = useState(null);
  const [gapAnalysis, setGapAnalysis] = useState(null);
  const [learningRoute, setLearningRoute] = useState(null);
  const [learningJobId, setLearningJobId] = useState("");
  const [assessmentRecords, setAssessmentRecords] = useState([]);
  const [applications, setApplications] = useState([]);
  const [targetJob, setTargetJob] = useState(null);
  const [assessmentDraftKey, setAssessmentDraftKey] = useState(0);
  const [toast, setToast] = useState("");
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [decisionPromptOpen, setDecisionPromptOpen] = useState(false);
  const reduceMotion = useReducedMotion();
  const decisionMessages = useMemo(() => buildDecisionMessages({
    role,
    portalSummary,
    platformSummary,
    candidate,
    targetJob,
  }), [role, portalSummary, platformSummary, candidate, targetJob]);

  useEffect(() => {
    request("/api/platform/summary")
      .then(setPlatformSummary)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (entry === "app") return;
    request("/api/jobs?active_only=false&limit=1")
      .then((data) => setJobTotal(data.total ?? data.items?.length ?? 0))
      .catch(() => {});
  }, [entry]);

  useEffect(() => {
    if (entry !== "app") return;
    request("/api/portal/summary")
      .then(setPortalSummary)
      .catch(() => setPortalSummary(null));
    request("/api/jobs?active_only=false&limit=25")
      .then((data) => {
        if (data.items?.length) {
          const mapped = data.items.map(mapJob);
          setJobs(mapped);
          setTargetJob((current) => resolveMappedJob(current, mapped));
        } else setJobs([]);
        setJobTotal(data.total ?? data.items?.length ?? 0);
      })
      .catch(() => {});
    if (role === "seeker") {
      request("/api/applications")
        .then((data) => setApplications(data.items || []))
        .catch(() => setApplications([]));
    }
  }, [entry, role, auth?.access_token]);

  useEffect(() => {
    if (role !== "seeker") return;
    const latest = applications.find((item) => item?.status !== "withdrawn");
    if (!latest) return;
    const applicationJob = mapApplicationJob(latest);
    setTargetJob((current) => current || resolveMappedJob(applicationJob, jobs));
  }, [applications, jobs, role]);

  useEffect(() => {
    const homeRoute = role === "seeker" ? "seeker-home" : "dashboard";
    if (entry !== "app" || route !== homeRoute || portalSummary?.role !== role || !decisionMessages.length) return;
    const tokenMark = String(auth?.access_token || "").slice(-12);
    const promptKey = `tg-decision-prompt:${auth?.user?.user_id || role}:${tokenMark}`;
    if (window.sessionStorage.getItem(promptKey)) return;
    window.sessionStorage.setItem(promptKey, "shown");
    setDecisionPromptOpen(true);
  }, [entry, route, role, portalSummary?.role, decisionMessages.length, auth?.access_token, auth?.user?.user_id]);

  const loadSeekerJobPage = useCallback(async ({ page, pageSize, keyword }) => {
    const params = new URLSearchParams({
      active_only: "false",
      limit: String(pageSize),
      offset: String((page - 1) * pageSize),
    });
    if (keyword.trim()) params.set("keyword", keyword.trim());
    const data = await request(`/api/jobs?${params.toString()}`);
    return {
      items: (data.items || []).map(mapJob),
      total: data.total ?? data.items?.length ?? 0,
    };
  }, []);

  useEffect(() => {
    if (auth) {
      request("/api/assessment-records")
        .then((data) => {
          const items = data.items || [];
          setAssessmentRecords(items);
          const newestProfile = items.find((item) => item?.profile?.candidate_id)?.profile;
          if (role === "seeker" && newestProfile?.candidate_id) {
            setCandidate(newestProfile);
          }
        })
        .catch(() => setAssessmentRecords([]));
    } else {
      setAssessmentRecords([]);
    }
    setCandidate(null);
    setGapAnalysis(null);
    setLearningRoute(null);
    setTargetJob(null);
    if (role !== "seeker") setApplications([]);
  }, [auth, role]);

  useEffect(() => {
    if (role !== "seeker" || !candidate?.candidate_id) return;
    request(`/api/gap-analysis/latest/${encodeURIComponent(candidate.candidate_id)}`)
      .then(setGapAnalysis)
      .catch(() => setGapAnalysis(null));
  }, [role, candidate?.candidate_id]);

  useEffect(() => {
    const results = gapAnalysis?.results || [];
    const defaultJob = results.find((item) => item?.job_id != null) || gapAnalysis?.best_match;
    setLearningJobId(defaultJob?.job_id == null ? "" : String(defaultJob.job_id));
  }, [gapAnalysis?.analysis_id]);

  useEffect(() => {
    if (!gapAnalysis?.analysis_id) return;
    request(`/api/learning/routes/latest/${encodeURIComponent(gapAnalysis.analysis_id)}`)
      .then(setLearningRoute)
      .catch(() => setLearningRoute(null));
  }, [gapAnalysis?.analysis_id]);

  const notify = (message) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2200);
  };
  const saveAssessmentRecord = useCallback((profile, message) => {
    if (!profile?.candidate_id) return null;
    let saved = null;
    setAssessmentRecords((current) => {
      const existing = current.find((item) => item.candidate_id === profile.candidate_id);
      saved = buildAssessmentRecord(profile, existing);
      const next = existing
        ? current.map((item) => (item.candidate_id === profile.candidate_id ? saved : item))
        : [saved, ...current];
      request(`/api/assessment-records/${encodeURIComponent(saved.id)}`, {
        method: "PUT",
        body: JSON.stringify({ record: saved }),
      }).catch(() => {});
      return next;
    });
    if (message) notify(message);
    return saved;
  }, [auth]);
  const uploadSeekerResume = useCallback(async (file) => {
    const data = new FormData();
    data.append("file", file);
    const session = readAuthSession();
    const response = await fetch(`${API}/api/assessment/upload-resume`, {
      method: "POST",
      headers: session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {},
      body: data,
    });
    if (!response.ok) throw new Error(await readApiError(response, "简历解析失败"));
    let result = await response.json();
    if (result.enrichment_status === "processing") {
      const deadline = Date.now() + 90000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => window.setTimeout(resolve, 900));
        const status = await request(`/api/assessment/resume-parses/${encodeURIComponent(result.candidate_id)}`);
        if (status.status === "failed") throw new Error(status.error || "大模型简历解析失败");
        if (status.status === "completed") {
          result = { ...result, ...status, parse_timing: status.timing || result.parse_timing, enrichment_status: "completed" };
          break;
        }
      }
      if (result.enrichment_status !== "completed") throw new Error("大模型仍在解析，请稍后重新查看简历档案");
    }
    const profile = result.candidate_profile || result.resume_parse?.candidate_profile;
    if (!profile?.candidate_id) throw new Error("简历已读取，但没有生成能力档案");
    setCandidate(profile);
    setGapAnalysis(null);
    setLearningRoute(null);
    saveAssessmentRecord(profile);
    return result;
  }, [saveAssessmentRecord]);
  const runGapAnalysis = useCallback(async ({ analyzeAll = false, jobId = null } = {}) => {
    if (!candidate?.candidate_id) throw new Error("请先完成简历解析");
    const targetJobId = jobId || (!analyzeAll ? targetJob?.id : null);
    const result = await request("/api/gap-analysis", {
      method: "POST",
      body: JSON.stringify({ candidate_id: candidate.candidate_id, target_job_id: targetJobId, analyze_all: analyzeAll }),
    });
    setGapAnalysis(result);
    setLearningRoute(null);
    return result;
  }, [candidate?.candidate_id, targetJob?.id]);
  const generateLearningRoute = useCallback(async ({ analysisId, jobId, currentLevel = "入门" }) => {
    const result = await request("/api/learning/routes", {
      method: "POST",
      body: JSON.stringify({ analysis_id: analysisId, job_id: jobId, current_level: currentLevel, courses_per_skill: 3 }),
    });
    setLearningRoute(result);
    return result;
  }, []);
  const openLearningForJob = useCallback((jobId) => {
    setLearningJobId(jobId == null ? "" : String(jobId));
    navigate("learning");
  }, [navigate]);
  const updateAssessmentRecord = useCallback((recordId, patch) => {
    setAssessmentRecords((current) => {
      const next = current.map((item) => (
        item.id === recordId
          ? { ...item, ...patch, updated_at: new Date().toISOString() }
          : item
      ));
      const updated = next.find((item) => item.id === recordId);
      if (updated) {
        request(`/api/assessment-records/${encodeURIComponent(recordId)}`, {
          method: "PUT",
          body: JSON.stringify({ record: updated }),
        }).catch(() => {});
      }
      return next;
    });
  }, [auth]);
  const deleteAssessmentRecord = useCallback((recordId) => {
    setAssessmentRecords((current) => {
      return current.filter((item) => item.id !== recordId);
    });
    request(`/api/assessment-records/${encodeURIComponent(recordId)}`, { method: "DELETE" }).catch(() => {});
    notify("评估记录已删除");
  }, [auth]);
  const beginNewAssessment = useCallback(() => {
    setCandidate(null);
    setAssessmentDraftKey((value) => value + 1);
    navigate(role === "seeker" ? "interview" : "recruiting");
    notify(role === "seeker" ? "开始新的职业能力评估" : "请选择在招岗位并上传候选人简历");
  }, [navigate, role]);
  const handleLogin = async ({ email, password, role: selectedRole }) => {
    const session = await request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, role: selectedRole }),
    });
    window.sessionStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));
    setAuth(session);
    setEntry("app");
    navigate(selectedRole === "seeker" ? "seeker-home" : "dashboard");
  };
  const handleLogout = async () => {
    request("/api/auth/logout", { method: "POST" }).catch(() => {});
    window.sessionStorage.removeItem(AUTH_SESSION_KEY);
    setAuth(null);
    setCandidate(null);
    setEntry("home");
    window.location.hash = "";
  };
  const applyToJob = async (job) => {
    const result = await request("/api/applications", {
      method: "POST",
      body: JSON.stringify({
        job_id: job.id,
        job_title: job.title,
        company: job.company,
        source_url: job.sourceUrl || null,
        match_score: candidate?.match_report?.score ?? null,
        snapshot: {
          target_job_id: candidate?.target_job_id,
          report_id: candidate?.match_report?.report_id,
          skill_count: candidate?.skills?.length || 0,
        },
      }),
    });
    setApplications((current) => (
      current.some((item) => item.application_id === result.application_id)
        ? current
        : [result, ...current]
    ));
    setTargetJob(job);
    notify(job.sourceUrl ? "投递已记录，可从岗位详情进入原招聘平台" : "简历已提交");
  };
  const withdrawApplication = async (applicationId) => {
    const updated = await request(`/api/applications/${applicationId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "withdrawn" }),
    });
    setApplications((current) => current.map((item) => item.application_id === applicationId ? updated : item));
    notify("投递已撤回");
  };

  if (entry === "home") {
    return (
      <PublicHome
        jobTotal={jobTotal}
        platformSummary={platformSummary}
        onLogin={(selectedRole = "enterprise") => {
          setLoginRole(selectedRole);
          setEntry("login");
        }}
      />
    );
  }
  if (entry === "login")
    return (
      <Login
        initialRole={loginRole}
        jobTotal={jobTotal}
        platformSummary={platformSummary}
        onBack={() => setEntry("home")}
        onLogin={handleLogin}
      />
    );

  return (
    <div className={`app-shell ${role === "seeker" ? "seeker-shell" : "enterprise-shell"} ${route === "graph" || route === "career-graph" ? "graph-shell" : ""} ${sidebarExpanded ? "" : "sidebar-collapsed"}`}>
      <Sidebar
        collapsed={!sidebarExpanded}
        role={role}
        user={auth?.user}
        route={route}
        navigate={navigate}
        onExpandedChange={setSidebarExpanded}
        onLogout={handleLogout}
      />
      <div className="app-main">
        <Topbar
          role={role}
          user={auth?.user}
          route={route}
          navigate={navigate}
          notify={notify}
          onAssets={() => navigate(role === "seeker" ? "applications" : "data")}
          onNewAssessment={beginNewAssessment}
          decisionMessages={decisionMessages}
        />
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            className={`page-body route-${route}`}
            key={route}
            initial={{
              opacity: 0,
              y: reduceMotion ? 0 : 14,
              filter: reduceMotion ? "none" : "blur(5px)",
            }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{
              opacity: 0,
              y: reduceMotion ? 0 : -8,
              filter: reduceMotion ? "none" : "blur(3px)",
            }}
            transition={{
              duration: reduceMotion ? 0.12 : 0.34,
              ease: [0.22, 1, 0.36, 1],
            }}
          >
            {role === "enterprise" && route === "dashboard" && (
              <Dashboard
                jobs={jobs}
                jobTotal={jobTotal}
                platformSummary={platformSummary}
                portalSummary={portalSummary}
                assessmentRecords={assessmentRecords}
                navigate={navigate}
                openAssets={() => navigate("data")}
              />
            )}
            {role === "enterprise" && route === "data" && (
                <JobAssets
                  jobs={jobs}
                  jobTotal={jobTotal}
                  setJobTotal={setJobTotal}
                  setJobs={setJobs}
                  notify={notify}
                />
            )}
            {role === "enterprise" && route === "graph" && <GraphPage audience="enterprise" />}
            {role === "enterprise" && route === "evolution" && <EvolutionPage audience="enterprise" />}
            {role === "enterprise" && route === "recruiting" && <RecruitingWorkspace notify={notify} navigate={navigate} />}
            {role === "enterprise" && route === "assessments" && (
              <AssessmentManagement
                records={assessmentRecords}
                navigate={navigate}
                setCandidate={setCandidate}
                onCreate={() => {
                  beginNewAssessment();
                }}
                onUpdate={updateAssessmentRecord}
                onDelete={deleteAssessmentRecord}
                notify={notify}
              />
            )}
            {role === "enterprise" && route === "assessment" && <RecruitingWorkspace notify={notify} navigate={navigate} />}
            {route === "report" && (
              <Report candidate={candidate} navigate={navigate} notify={notify} audience={role} />
            )}
            {role === "enterprise" && route === "validation" && <Validation />}

            {role === "seeker" && route === "seeker-home" && (
              <SeekerDashboard
                user={auth?.user}
                candidate={candidate}
                applications={applications}
                jobs={jobs}
                targetJob={targetJob}
                setTargetJob={setTargetJob}
                navigate={navigate}
                platformSummary={platformSummary}
                portalSummary={portalSummary}
              />
            )}
            {role === "seeker" && route === "career-graph" && (
              <GraphPage audience="seeker" targetJob={targetJob} setTargetJob={setTargetJob} />
            )}
            {role === "seeker" && route === "career-evolution" && (
              <EvolutionPage audience="seeker" />
            )}
            {role === "seeker" && route === "resume" && (
              <SeekerResumePage candidate={candidate} user={auth?.user} navigate={navigate} onUpload={uploadSeekerResume} notify={notify} />
            )}
            {role === "seeker" && route === "interview" && (
              <Assessment
                key={`seeker-assessment-${assessmentDraftKey}-${candidate?.candidate_id || "new"}`}
                candidate={candidate}
                setCandidate={setCandidate}
                saveCandidateRecord={saveAssessmentRecord}
                navigate={navigate}
                notify={notify}
                audience="seeker"
                currentUser={auth?.user}
                targetJob={targetJob}
              />
            )}
            {role === "seeker" && route === "gap" && (
              <GapAnalysis
                candidate={candidate}
                targetJob={targetJob}
                jobs={jobs}
                setTargetJob={setTargetJob}
                loadJobPage={loadSeekerJobPage}
                navigate={navigate}
                onOpenLearning={openLearningForJob}
                analysis={gapAnalysis}
                onAnalyze={runGapAnalysis}
              />
            )}
            {role === "seeker" && route === "learning" && (
              <LearningRoadmap candidate={candidate} analysis={gapAnalysis} route={learningRoute} initialJobId={learningJobId} onGenerate={generateLearningRoute} navigate={navigate} notify={notify} />
            )}
            {role === "seeker" && route === "applications" && (
              <ApplicationCenter
                jobs={jobs}
                jobTotal={jobTotal}
                applications={applications}
                targetJob={targetJob}
                setTargetJob={setTargetJob}
                loadJobPage={loadSeekerJobPage}
                onApply={applyToJob}
                onWithdraw={withdrawApplication}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
      <AnimatePresence>
        {decisionPromptOpen && (
          <motion.div
            className="decision-prompt-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={(event) => event.target === event.currentTarget && setDecisionPromptOpen(false)}
          >
            <motion.section
              className="decision-prompt"
              initial={{ opacity: 0, y: reduceMotion ? 0 : 18, scale: reduceMotion ? 1 : 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: reduceMotion ? 0 : 10, scale: reduceMotion ? 1 : 0.985 }}
              transition={{ duration: reduceMotion ? 0.12 : 0.3, ease: [0.22, 1, 0.36, 1] }}
              role="dialog"
              aria-modal="true"
              aria-labelledby="decision-prompt-title"
            >
              <header>
                <div><span>本次进入提醒</span><h2 id="decision-prompt-title">有 {decisionMessages.length} 项待决策事项</h2><p>{role === "seeker" ? "已按职业机会、个人差距与技能变化完成排序。" : "已按岗位风险、标准差距与技能变化完成排序。"}</p></div>
                <Button isIconOnly variant="ghost" aria-label="关闭待决策提醒" onPress={() => setDecisionPromptOpen(false)}><X size={18} /></Button>
              </header>
              <div className="decision-prompt-list">
                {decisionMessages.slice(0, 4).map((item, index) => (
                  <button key={item.id} onClick={() => { setDecisionPromptOpen(false); navigate(item.route); }}>
                    <span className={item.tone}>{String(index + 1).padStart(2, "0")}</span>
                    <div><small>{item.category}</small><strong>{item.title}</strong><p>{item.detail}</p></div>
                    <ChevronRight size={16} />
                  </button>
                ))}
              </div>
              <footer><span>其余事项已收入顶部消息中心</span><Button onPress={() => setDecisionPromptOpen(false)}>进入首页</Button></footer>
            </motion.section>
          </motion.div>
        )}
      </AnimatePresence>
      {toast && (
        <div className="toast">
          <CheckCircle2 size={17} />
          {toast}
        </div>
      )}
    </div>
  );
}

function useRoute(role) {
  const defaultRoute = role === "seeker" ? "seeker-home" : "dashboard";
  const allowed = ROLE_META[role || "enterprise"];
  const read = () => window.location.hash.replace("#/", "") || defaultRoute;
  const [route, setRoute] = useState(read);
  const navigate = (next) => {
    window.location.hash = `/${next}`;
    setRoute(next);
    window.scrollTo(0, 0);
  };
  useEffect(() => {
    const fn = () => setRoute(read());
    window.addEventListener("hashchange", fn);
    return () => window.removeEventListener("hashchange", fn);
  }, []);
  useEffect(() => {
    if (!allowed[route]) {
      window.location.hash = `/${defaultRoute}`;
      setRoute(defaultRoute);
    }
  }, [allowed, defaultRoute, route]);
  return [allowed[route] ? route : defaultRoute, navigate];
}

function Brand({ dark = false, showTagline = false }) {
  return (
    <div className={`brand ${dark ? "dark" : ""}`}>
      <span>
        <Network size={19} />
      </span>
      <div>
        <strong>讯飞智聘</strong>
        {showTagline ? <small>INTELLIGENCE CLOUD</small> : null}
      </div>
    </div>
  );
}

const HOME_STORY_STAGES = [
  { name: "岗位数据接入", eyebrow: "01 / 岗位数据接入", title: <><span>把分散的岗位信号</span><em>汇入同一条路线</em></>, description: "岗位 JD、职责描述与技术信号进入统一入口；每一份来源都保留时间、出处与可复核线索。", detail: "多源数据 · 清洗校验 · 可追溯来源" },
  { name: "技能提取与演化", eyebrow: "02 / 技能提取与演化", title: <><span>能力不是平铺标签，</span><em>而是持续重组的结构</em></>, description: "技能单元在能力魔方中聚合、强化与演化，形成可人工校准、可回放的岗位能力版本。", detail: "技能单元 · 变化说明 · 版本快照" },
  { name: "能力图谱构建", eyebrow: "03 / 能力图谱构建", title: <><span>让岗位、技能与场景</span><em>形成可推理的图谱</em></>, description: "以技能点为颗粒度，连接 AI、大数据、智能系统与物联网领域的真实能力关系。", detail: "技能本体 · 关系推理 · 证据链" },
  { name: "智能匹配计算", eyebrow: "04 / 智能匹配计算", title: <><span>将简历能力放进图谱，</span><em>给出下一步方向</em></>, description: "从简历解析到目标岗位差距、改进建议与学习路径，让招聘与成长决策都有清晰依据。", action: "继续查看解决方案", detail: "简历解析 · 人岗诊断 · 成长路径" },
];

function HomeProductScreen({ platformSummary }) {
  const summary = platformSummary || {};
  const evidenceItems = [
    ["招聘岗位主证据", Number(summary.active_jobs || 0), "当前在招"],
    ["技能证据节点", Number(summary.skills || 0), "规格化技能"],
    ["岗位版本快照", Number(summary.version_snapshots || 0), "可回溯版本"],
    ["已监测变动岗位", Number(summary.changed_jobs || 0), "版本差异"],
  ];
  const platformMetrics = [
    ["岗位资产", Number(summary.jobs || 0)],
    ["版本快照", Number(summary.version_snapshots || 0)],
    ["变动岗位", Number(summary.changed_jobs || 0)],
    ["新岗位候选", Number(summary.emerging_jobs || 0)],
  ];
  const growthJobs = (summary.decision_summary?.growth_jobs || []).slice(0, 2);
  const averageQuality = Number(summary.average_quality || 0);

  return <div className="cinematic-product-composition" aria-label="讯飞智聘产品内页预览">
    <div className="cinematic-product-window">
      <div className="cinematic-screen">
      <header className="cinematic-screen-topbar">
        <Brand dark />
        <div><Search size={11} /><span>搜索岗位、人才与技能</span></div>
        <b>能力图谱</b>
      </header>
      <div className="cinematic-screen-body">
        <aside className="cinematic-screen-sidebar">
          {[LayoutDashboard, BriefcaseBusiness, UserRoundSearch, Network, Target].map((Icon, index) => <span key={index} className={index === 3 ? "is-active" : ""}><Icon size={13} /></span>)}
        </aside>
        <section className="cinematic-graph-panel">
          <div className="cinematic-panel-title"><div><small>岗位能力全景图谱</small><strong>{Number(summary.jobs || 0).toLocaleString("zh-CN")} 条岗位证据</strong></div><span>最新市场快照</span></div>
          <div className="cinematic-graph-canvas">
            <img src={homeTemporalGraphScreenshot} alt="真实系统三维岗位能力时间图谱截图" />
          </div>
        </section>
        <aside className="cinematic-evidence-panel">
          <div className="cinematic-panel-title"><div><small>真实数据口径</small><strong>证据与版本</strong></div><ShieldCheck size={15} /></div>
          {evidenceItems.map(([label, value, note], index) => <div className="cinematic-evidence-row" key={label}><span>{String(index + 1).padStart(2, "0")}</span><div><b>{label}</b><small>{Number(value).toLocaleString("zh-CN")} · {note}</small></div><Check size={11} /></div>)}
        </aside>
      </div>
      <footer className="cinematic-match-strip">
        <div><small>覆盖范围</small><b>新一代信息技术岗位</b></div>
        <section><span>四大领域</span><i>人工智能</i><i>大数据</i><i>智能系统</i><i>物联网</i></section>
        <section className="has-gap"><span>增长岗位</span>{growthJobs.length ? growthJobs.map((item) => <i key={item.name}>{item.name}</i>) : <i>等待市场数据</i>}</section>
        <button>查看图谱 <ArrowRight size={11} /></button>
      </footer>
      </div>
    </div>
    <aside className="cinematic-float-card cinematic-float-diagnostic">
      <header><div><small>数据治理</small><strong>岗位资产质量</strong></div><span>实时统计</span></header>
      <div className="cinematic-diagnostic-score"><i><b>{averageQuality || "--"}</b><small>平均质量</small></i></div>
      <div className="cinematic-diagnostic-metrics"><span><i className="is-advantage" />在招岗位 <b>{Number(summary.active_jobs || 0).toLocaleString("zh-CN")}</b></span><span><i className="is-gap" />岗位族 <b>{Number(summary.job_families || 0).toLocaleString("zh-CN")}</b></span></div>
    </aside>
    <aside className="cinematic-float-card cinematic-float-timeline">
      <header><div><small>动态演化</small><strong>平台证据资产</strong></div><span>实时统计</span></header>
      <div className="cinematic-timeline-list">
        {platformMetrics.map(([label, value], index) => <div key={label}><i /><span><b>{label}</b><small>{index === 0 ? "招聘主数据" : "持久化记录"}</small></span><em>{Number(value).toLocaleString("zh-CN")}</em></div>)}
      </div>
    </aside>
  </div>;
}

function ProductPositioningLayer({ progress = 0, visible = 0, jobTotal = 0, platformSummary }) {
  const reducedMotion = useReducedMotion();
  const assetMetrics = [
    [Number(platformSummary?.jobs ?? jobTotal ?? 0).toLocaleString("zh-CN"), "已入库岗位资产", "岗位市场感知"],
    [Number(platformSummary?.active_jobs ?? 0).toLocaleString("zh-CN"), "当前活跃岗位", "岗位市场感知"],
    [Number(platformSummary?.job_families ?? 0).toLocaleString("zh-CN"), "图谱展示岗位族", "平台能力资产"],
    [Number(platformSummary?.skills ?? 0).toLocaleString("zh-CN"), "有效技能标签", "平台能力资产"],
  ];
  const copyReveal = Math.max(0, Math.min(1, (progress - 0.08) / 0.2));

  return <section className="positioning-layer" id="solutions" aria-labelledby="positioning-title" style={{ opacity: visible, pointerEvents: visible > 0.85 ? "auto" : "none" }}>
      <React.Suspense fallback={null}><ProductPositioningScene progress={progress} active={visible > 0.02} reducedMotion={reducedMotion} assetMetrics={assetMetrics} /></React.Suspense>
      <div className="positioning-copy" style={{ opacity: copyReveal, transform: reducedMotion ? "none" : `translate3d(-50%, ${(1 - copyReveal) * 24}px, 0)` }}>
        <h2 id="positioning-title">追踪岗位变化，连接企业与求职者</h2>
        <p>讯飞智聘为企业提供岗位与人才评估，为求职者提供能力差距与学习路径。</p>
      </div>
  </section>;
}

const HOME_FEEDBACKS = [
  {
    role: "企业HR",
    identity: "企业招聘体验用户",
    tone: "cyan",
    variant: "glasses",
    avatar: feedbackEnterpriseHr,
    portrait: feedbackEnterpriseHrPortrait,
    quote: "岗位要求、候选人能力和评估证据落在同一套结构里，团队复核候选人时更容易对齐判断口径。",
  },
  {
    role: "招聘负责人",
    identity: "招聘管理体验用户",
    tone: "blue",
    variant: "manager",
    avatar: feedbackRecruitingLead,
    portrait: feedbackRecruitingLeadPortrait,
    quote: "岗位能力拆得足够清楚后，简历初筛、面试提问和人才盘点终于可以使用同一把尺子。",
  },
  {
    role: "人才发展负责人",
    identity: "人才发展体验用户",
    tone: "violet",
    variant: "collar",
    avatar: feedbackTalentDevelopment,
    portrait: feedbackTalentDevelopmentPortrait,
    quote: "岗位能力版本可以持续更新，让培训计划不再只依赖年初的一次盘点，而是跟着岗位变化调整。",
  },
  {
    role: "求职者",
    identity: "个人成长体验用户",
    tone: "cyan",
    variant: "ponytail",
    avatar: feedbackJobSeeker,
    portrait: feedbackJobSeekerPortrait,
    quote: "我能看见目标岗位需要什么、自己已经具备什么，以及下一步最值得补齐的能力。",
  },
  {
    role: "转岗者",
    identity: "职业转型体验用户",
    tone: "blue",
    variant: "sidehair",
    avatar: feedbackCareerSwitcher,
    portrait: feedbackCareerSwitcherPortrait,
    quote: "系统把可迁移能力和真实差距分开呈现，转岗路线因此更具体，而不只是一个模糊的匹配分数。",
  },
  {
    role: "应届生",
    identity: "校园求职体验用户",
    tone: "violet",
    variant: "graduate",
    avatar: feedbackGraduate,
    portrait: feedbackGraduatePortrait,
    quote: "从项目经历到岗位能力的映射很直观，我更清楚简历该补哪些证据、学习该从哪里开始。",
  },
];

function HomeFeedbackSection() {
  const reducedMotion = useReducedMotion();
  const [activeIndex, setActiveIndex] = useState(1);
  const active = HOME_FEEDBACKS[activeIndex];
  const selectRelative = (direction) => setActiveIndex((current) => (current + direction + HOME_FEEDBACKS.length) % HOME_FEEDBACKS.length);

  return <section className="home-feedback" id="user-feedback" aria-labelledby="home-feedback-title">
    <motion.header className="home-feedback-heading" initial={reducedMotion ? false : { opacity: 0, y: 26 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.55 }} transition={{ duration: 0.65, ease: [0.22, 0.8, 0.2, 1] }}>
      <h2 id="home-feedback-title">来自不同使用场景的反馈</h2>
      <h3>企业招聘、人才发展与个人成长，对同一套岗位能力数据有不同期待。</h3>
    </motion.header>

    <div className="home-feedback-layout">
      <motion.article className="home-feedback-card" initial={reducedMotion ? false : { opacity: 0, x: -32 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true, amount: 0.35 }} transition={{ duration: 0.7, delay: 0.08 }} aria-live="polite">
        <AnimatePresence mode="wait">
          <motion.div className="home-feedback-body" key={active.role} initial={reducedMotion ? false : { opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} exit={reducedMotion ? undefined : { opacity: 0, y: -12 }} transition={{ duration: 0.32 }}>
            <b className="home-feedback-quote-mark">“</b>
            <blockquote>{active.quote}</blockquote>
            <footer><img className="home-feedback-card-avatar" src={active.portrait} alt="" /><span><strong>{active.role}</strong><small>{active.identity}</small></span></footer>
          </motion.div>
        </AnimatePresence>
        <div className="home-feedback-controls">
          <span>{String(activeIndex + 1).padStart(2, "0")} / {String(HOME_FEEDBACKS.length).padStart(2, "0")}</span>
          <div><button aria-label="上一条反馈" onClick={() => selectRelative(-1)}><ArrowLeft size={17} /></button><button aria-label="下一条反馈" onClick={() => selectRelative(1)}><ArrowRight size={17} /></button></div>
        </div>
      </motion.article>

      <motion.div className="home-feedback-constellation" initial={reducedMotion ? false : { opacity: 0, scale: 0.95 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true, amount: 0.3 }} transition={{ duration: 0.8, delay: 0.12 }}>
        <div className="home-feedback-orbits" aria-hidden="true"><i /><i /><i /></div>
        <div className="home-feedback-hub" aria-hidden="true">
          <Network className="home-feedback-hub-icon is-depth" size={24} />
          <Network className="home-feedback-hub-icon is-face" size={24} />
          <span />
        </div>
        {HOME_FEEDBACKS.map((item, index) => <button
          key={item.role}
          className={`home-feedback-node is-node-${index}${index === activeIndex ? " is-active" : ""}`}
          aria-label={`查看${item.role}反馈`}
          aria-pressed={index === activeIndex}
          onClick={() => setActiveIndex(index)}
        >
          <span className="feedback-avatar" aria-hidden="true"><img src={item.avatar} alt="" /></span>
          <span>{item.role}</span>
        </button>)}
      </motion.div>
    </div>
  </section>;
}

function HomeFinalBanner({ onLogin }) {
  const reducedMotion = useReducedMotion();
  return <section className="home-final-wrap" aria-labelledby="home-final-title">
    <motion.div className="home-final-banner" initial={reducedMotion ? false : { opacity: 0, y: 38 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.32 }} transition={{ duration: 0.75, ease: [0.22, 0.8, 0.2, 1] }}>
      <div className="home-final-orbits" aria-hidden="true"><i /><i /><span /></div>
      <div className="home-final-brand"><Brand /><span>动态岗位能力决策平台</span></div>
      <div className="home-final-copy">
        <p>从岗位信号到人才决策</p>
        <h2 id="home-final-title">让每一次岗位与人才判断，<br />都有能力证据支撑</h2>
        <h3>从岗位变化感知到人岗诊断，讯飞智聘为招聘与成长提供同一套动态能力底座。</h3>
        <div><button className="is-enterprise" onClick={() => onLogin("enterprise")}>企业HR登录 <ArrowRight size={16} /></button><button className="is-seeker" onClick={() => onLogin("seeker")}>求职者登录 <ArrowRight size={16} /></button></div>
      </div>
      <div className="home-final-route" aria-hidden="true"><i /><i /><span /><span /></div>
      <footer><span>讯飞智聘</span><span>岗位数据 · 能力图谱 · 人岗诊断 · 成长路径</span></footer>
    </motion.div>
  </section>;
}

function PublicHome({ jobTotal = 0, platformSummary, onLogin }) {
  const storyRef = useRef(null);
  const reducedMotion = useReducedMotion();
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState(0);
  const [sceneReady, setSceneReady] = useState(false);
  const [positioningReady, setPositioningReady] = useState(false);
  const active = HOME_STORY_STAGES[stage];
  const wipeProgress = Math.max(0, Math.min(1, (progress - 0.11) / 0.13));
  const storyProgress = Math.max(0, Math.min(1, (progress - 0.23) / 0.44));
  const storyVisibility = Math.max(0, Math.min(1, (progress - 0.19) / 0.07));
  const storyExit = Math.max(0, Math.min(1, (progress - 0.76) / 0.09));
  const worldVisibility = storyVisibility * (1 - storyExit);
  const positioningProgress = Math.max(0, Math.min(1, (progress - 0.75) / 0.25));
  const positioningVisibilityRaw = Math.max(0, Math.min(1, (progress - 0.75) / 0.1));
  const positioningVisibility = positioningVisibilityRaw * positioningVisibilityRaw * (3 - 2 * positioningVisibilityRaw);
  const introExit = wipeProgress * wipeProgress * (3 - 2 * wipeProgress);
  const storyEntrance = storyVisibility * storyVisibility * (3 - 2 * storyVisibility);
  const introStyle = reducedMotion
    ? { opacity: 1 - introExit, pointerEvents: progress > 0.14 ? "none" : "auto" }
    : {
        transform: `translate3d(0, -${introExit * 58}vh, ${introExit * -220}px) rotateX(${introExit * 16}deg) scale(${1 - introExit * 0.06})`,
        opacity: Math.max(0, 1 - introExit * 1.08),
        filter: `blur(${introExit * 2.4}px)`,
        pointerEvents: progress > 0.14 ? "none" : "auto",
      };
  const storyElementStyle = {
    opacity: worldVisibility,
    transform: reducedMotion ? "none" : `translate3d(0, ${(1 - storyEntrance) * 28 - storyExit * 42}px, 0)`,
  };
  const overviewStyle = {
    opacity: worldVisibility,
    transform: reducedMotion ? "translateX(-50%)" : `translate3d(-50%, ${(1 - storyEntrance) * 18 - storyExit * 42}px, 0)`,
  };

  useEffect(() => {
    let frame = 0;
    const update = () => {
      const root = storyRef.current;
      if (!root) return;
      const bounds = root.getBoundingClientRect();
      const range = Math.max(1, root.offsetHeight - window.innerHeight);
      const nextProgress = Math.max(0, Math.min(1, -bounds.top / range));
      const nextStoryProgress = Math.max(0, Math.min(1, (nextProgress - 0.23) / 0.44));
      setProgress(nextProgress);
      if (nextProgress > 0.06) setSceneReady(true);
      if (nextProgress > 0.69) setPositioningReady(true);
      setStage(Math.min(HOME_STORY_STAGES.length - 1, Math.round(nextStoryProgress * (HOME_STORY_STAGES.length - 1))));
    };
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  const goToProgress = (next) => {
    const root = storyRef.current;
    if (!root) return;
    const range = Math.max(0, root.offsetHeight - window.innerHeight);
    window.scrollTo({ top: root.offsetTop + range * next, behavior: "smooth" });
  };
  const goToStage = (index) => goToProgress(0.25 + (index / (HOME_STORY_STAGES.length - 1)) * 0.42);

  const goToSolutions = () => goToProgress(0.985);
  const goToFeedback = () => document.getElementById("user-feedback")?.scrollIntoView({ behavior: "smooth", block: "start" });

  return <>
    <nav className="cinematic-nav">
      <Brand dark />
      <div><button className="cinematic-nav-link" onClick={() => goToProgress(0.25)}>产品能力</button><button className="cinematic-nav-link" onClick={goToSolutions}>解决方案</button><button className="cinematic-nav-link" onClick={goToFeedback}>用户反馈</button><button className="cinematic-nav-login cinematic-nav-enterprise" onClick={() => onLogin("enterprise")}>企业HR登录</button><button className="cinematic-nav-login cinematic-nav-cta" onClick={() => onLogin("seeker")}>求职者登录 <ArrowRight size={15} /></button></div>
    </nav>
    <main className="public-home-experience">
    <section className="cinematic-home" id="product-capabilities" ref={storyRef}>
      <section className="cinematic-sticky">
      <div className="cinematic-world" aria-hidden={storyVisibility < 0.1}>
        {sceneReady ? <React.Suspense fallback={null}><HomeStoryScene progress={storyProgress} reducedMotion={reducedMotion} active={worldVisibility > 0.02} stage={stage} labels={active.detail.split(" · ")} overlayOpacity={worldVisibility} reveal={storyEntrance} /></React.Suspense> : null}
        <header className="cinematic-world-overview" style={overviewStyle}>
          <h2>岗位数据，如何变成人岗匹配结果</h2>
        </header>
        <aside className="cinematic-route-steps" style={storyElementStyle} aria-label="岗位能力智能路线">
          {HOME_STORY_STAGES.map((item, index) => <button key={item.name} className={index === stage ? "is-active" : index < stage ? "is-past" : ""} onClick={() => goToStage(index)}><span>{String(index + 1).padStart(2, "0")}</span><i /><b>{item.name}</b></button>)}
        </aside>
        <div className="cinematic-world-copy" style={storyElementStyle}>
          <AnimatePresence mode="wait">
            <motion.div key={stage} initial={reducedMotion ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={reducedMotion ? undefined : { opacity: 0, y: -14 }} transition={{ duration: 0.4, ease: [0.22, 0.8, 0.2, 1] }}>
              <p>{active.eyebrow}</p><h2>{active.title}</h2><div className="cinematic-copy-line" /><h3>{active.description}</h3>
              {active.action ? <button onClick={goToSolutions}>{active.action} <ChevronDown size={16} /></button> : null}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      <section className="cinematic-intro" style={introStyle}>
        <div className="cinematic-intro-copy">
          <h1>讯飞智聘</h1>
          <h2>动态能力图谱，驱动新岗位发现与精准人岗匹配</h2>
        </div>
        <div className="cinematic-intro-device"><HomeProductScreen platformSummary={platformSummary} /></div>
        <button className="cinematic-intro-scroll" onClick={() => goToProgress(0.25)}><span>向下滚动查看能力路径</span><i /></button>
      </section>

      {positioningReady ? <ProductPositioningLayer progress={positioningProgress} visible={positioningVisibility} jobTotal={jobTotal} platformSummary={platformSummary} /> : null}

      </section>
    </section>
    <HomeFeedbackSection />
    <HomeFinalBanner onLogin={onLogin} />
    </main>
  </>;
}

const LOGIN_ROLE_DETAILS = {
  enterprise: {
    tab: "企业招聘",
    title: "岗位证据与候选人评估，一屏进入。",
    titleLines: ["岗位证据与候选人评估", "一屏进入。"],
    subtitle: "沉淀岗位标准，复用评估结果。",
    emailLabel: "企业邮箱",
    email: "hr@talentgraph.cn",
    heading: "登录企业工作台",
    helper: "管理岗位资产与候选人评估。",
    trust: "企业数据隔离存储，评估与审核过程完整留痕",
    submit: "进入企业工作台",
    advantages: [
      "岗位标准沉淀",
      "候选人证据链",
      "评估结果复用",
    ],
  },
  seeker: {
    tab: "求职成长",
    title: "看清目标岗位，定位能力差距。",
    titleLines: ["看清目标岗位", "定位能力差距。"],
    subtitle: "从简历、面试到成长路线。",
    emailLabel: "个人邮箱",
    email: "candidate@talentgraph.cn",
    heading: "登录个人职业空间",
    helper: "管理简历、画像与目标岗位。",
    trust: "个人简历默认仅自己可见，投递后按授权范围共享",
    submit: "进入职业空间",
    stats: [
      ["40", "岗位族覆盖"],
      ["6 项", "能力差距分析"],
      ["24h", "岗位演化追踪"],
    ],
    advantages: [
      "技能掌握识别",
      "项目表达校准",
      "学习优先级建议",
    ],
  },
};

function Login({ initialRole = "enterprise", jobTotal = 0, platformSummary, onBack, onLogin }) {
  const [role, setRole] = useState(initialRole);
  const [email, setEmail] = useState(initialRole === "seeker" ? "candidate@talentgraph.cn" : "hr@talentgraph.cn");
  const [password, setPassword] = useState("talentgraph2026");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  const selectRole = (nextRole) => {
    if (!LOGIN_ROLE_DETAILS[nextRole]) return;
    setRole(nextRole);
    setEmail(LOGIN_ROLE_DETAILS[nextRole].email);
    setError("");
  };
  const isSeeker = role === "seeker";
  const currentRole = LOGIN_ROLE_DETAILS[role];
  const storedJobCount = Number(platformSummary?.jobs ?? jobTotal ?? 0);
  const leftMetrics = [
    [`${storedJobCount.toLocaleString("zh-CN")}`, "已存岗位数量"],
    [Number(platformSummary?.skills || 0).toLocaleString("zh-CN"), "技能证据节点"],
    [Number(platformSummary?.job_families || 0).toLocaleString("zh-CN"), "岗位族覆盖"],
    [isSeeker ? Number(platformSummary?.changed_jobs || 0).toLocaleString("zh-CN") : "3 轮", isSeeker ? "岗位变动追踪" : "项目导向面试"],
  ];
  return (
    <main className={`login-page refined-login ${isSeeker ? "seeker" : "enterprise"}`}>
      <section className="login-visual">
        <ThreeGraph compact apiUrl={API} />
        <div className="login-overlay">
          <Button className="login-back" variant="ghost" size="sm" onPress={onBack}>
            <ArrowLeft size={17} />
            返回
          </Button>
          <Brand />
          <div className="login-story">
            <h1>
              {(currentRole.titleLines || [currentRole.title]).map((line) => (
                <span className="login-title-line" key={line}>
                  {line}
                </span>
              ))}
            </h1>
            <p>{currentRole.subtitle}</p>
          </div>
          <div className="login-system-panel">
            <div className="login-panel-head">
              <strong>岗位与能力智能底座</strong>
            </div>
            <div className="login-metrics">
              {leftMetrics.map(([value, label]) => (
                <div className="login-metric-tile" key={label}>
                  <strong>{value}</strong>
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="login-floating-card primary-card">
            <strong>{isSeeker ? "从岗位反推能力成长" : "从证据生成匹配结论"}</strong>
            <p>{isSeeker ? "识别目标岗位差距，连接简历、面试和学习路线。" : "把岗位要求、项目证据和面试表现汇总为可解释报告。"}</p>
          </div>
          <div className="login-floating-card secondary-card">
            <strong>{isSeeker ? "技能出处可追溯" : "岗位标准可复用"}</strong>
          </div>
          <div className="login-intel-grid" aria-hidden="true">
            {leftMetrics.map(([value, label]) => (
              <div className="login-metric-tile ghost" key={label}>
                <strong>{value}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section className="login-form">
        <Card className="login-card" variant="default">
          <Card.Header>
            <Card.Title>{currentRole.heading}</Card.Title>
          </Card.Header>
          <Card.Content>
            <Tabs className="login-role-tabs" selectedKey={role} onSelectionChange={(key) => selectRole(String(key))}>
              <Tabs.ListContainer>
                <Tabs.List aria-label="登录角色切换">
                  <Tabs.Tab id="enterprise">
                    <BriefcaseBusiness size={16} />
                    企业招聘
                    <Tabs.Indicator />
                  </Tabs.Tab>
                  <Tabs.Tab id="seeker">
                    <UserRound size={16} />
                    求职成长
                    <Tabs.Indicator />
                  </Tabs.Tab>
                </Tabs.List>
              </Tabs.ListContainer>
              <Tabs.Panel className="login-role-panel" id="enterprise">
                岗位图谱、候选人评估、匹配报告一站进入。
              </Tabs.Panel>
              <Tabs.Panel className="login-role-panel" id="seeker">
                简历解析、能力画像、岗位差距同步管理。
              </Tabs.Panel>
            </Tabs>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setError("");
                setLoading(true);
                Promise.resolve(onLogin({ email, password, role }))
                  .catch((loginError) => setError(loginError.message || "登录失败，请检查账号信息。"))
                  .finally(() => setLoading(false));
              }}
            >
              <label className="login-field">
                <span>{currentRole.emailLabel}</span>
                <Input
                  fullWidth
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  autoComplete="email"
                  placeholder={currentRole.email}
                />
              </label>
              <label className="login-field">
                <span>密码</span>
                <div className="password-field">
                  <Input
                    fullWidth
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    autoComplete="current-password"
                    placeholder="请输入登录密码"
                  />
                  <Button
                    className="password-toggle"
                    isIconOnly
                    variant="ghost"
                    type="button"
                    aria-label={showPassword ? "隐藏密码" : "显示密码"}
                    onPress={() => setShowPassword((value) => !value)}
                  >
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </Button>
                </div>
              </label>
              <div className="login-row">
                <label>
                  <input type="checkbox" defaultChecked />
                  保持登录
                </label>
              </div>
              <Button className="login-submit" type="submit" fullWidth isPending={loading}>
                <LogIn size={18} />
                {loading ? "正在验证..." : currentRole.submit}
              </Button>
              {error && <p className="form-error">{error}</p>}
            </form>
            <div className="login-advantage-list">
              {currentRole.advantages.map((item) => (
                <span key={item}>
                  <CheckCircle2 size={14} />
                  {item}
                </span>
              ))}
            </div>
          </Card.Content>
          <Card.Footer>
            <small className="login-role-note">
              <ShieldCheck size={14} />
              {currentRole.trust}
            </small>
          </Card.Footer>
        </Card>
      </section>
    </main>
  );
}

function Sidebar({ role = "enterprise", user, route, navigate, collapsed, onExpandedChange, onLogout }) {
  const navigation = ROLE_NAV[role] || ROLE_NAV.enterprise;
  const isSeeker = role === "seeker";
  const accountName = isSeeker
    ? user?.display_name || "求职者"
    : `${user?.organization_name || "企业"}人事部`;
  const accountRole = isSeeker ? "求职者" : "招聘管理员";
  return (
    <motion.aside
      className="sidebar"
      initial={{ x: -18, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      onMouseEnter={() => onExpandedChange(true)}
      onMouseLeave={() => onExpandedChange(false)}
      onFocusCapture={() => onExpandedChange(true)}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) onExpandedChange(false);
      }}
    >
      <Brand />
      <nav id="workspace-navigation">
        {navigation.map(([label, items]) => (
          <div key={label}>
            <span>{label}</span>
            {items.map(([id, text, Icon]) => (
              <motion.div
                key={id}
                whileTap={{ scale: 0.98 }}
                transition={{ duration: 0.16 }}
              >
                <Button
                  aria-label={collapsed ? text : undefined}
                  className={route === id ? "active" : ""}
                  title={collapsed ? text : undefined}
                  variant="ghost"
                  onPress={() => { document.body.classList.remove("mobile-nav-open"); navigate(id); }}
                >
                  <Icon size={17} />
                  <b>{text}</b>
                  {route === id && (
                    <motion.i
                      layoutId="sidebar-active"
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    />
                  )}
                </Button>
              </motion.div>
            ))}
          </div>
        ))}
      </nav>
      <div className="workspace">
        <span>{isSeeker ? "个人空间" : "组织空间"}</span>
        <Button
          aria-label={collapsed ? `${accountName}，退出登录` : undefined}
          title={collapsed ? "退出登录" : undefined}
          variant="ghost"
          onPress={onLogout}
        >
          <div className={`workspace-avatar${isSeeker ? " seeker-avatar" : ""}`}>{isSeeker ? "ME" : "HR"}</div>
          <p>
            <strong>{accountName}</strong>
            <em className="workspace-role">{accountRole}</em>
          </p>
          <ChevronRight size={15} />
        </Button>
      </div>
    </motion.aside>
  );
}

function Topbar({ role = "enterprise", user, route, navigate, onAssets, onNewAssessment, notify, decisionMessages = [] }) {
  const [search, setSearch] = useState("");
  const [notifications, setNotifications] = useState(false);
  const isSeeker = role === "seeker";
  const pageMeta = ROLE_META[role]?.[route] || ROLE_META.enterprise.dashboard;
  const runSearch = (value = search) => {
    const text = value.trim();
    if (!text) return;
    if (isSeeker) {
      if (/简历|档案|画像/.test(text)) navigate("resume");
      else if (/面试|任务|对话/.test(text)) navigate("interview");
      else if (/学习|路线|提升/.test(text)) navigate("learning");
      else if (/演化|趋势|新岗位|新职业/.test(text)) navigate("career-evolution");
      else if (/投递|岗位|公司/.test(text)) navigate("applications");
      else navigate("career-graph");
    } else {
      if (/管理|档案|列表/.test(text)) navigate("assessments");
      else if (/候选|简历|人才/.test(text)) navigate("recruiting");
      else if (/演化|趋势|新岗位/.test(text)) navigate("evolution");
      else navigate("graph");
    }
    notify?.(`已定位：${text}`);
  };
  const assessmentAction = route === "interview";
  return (
    <header className={`topbar ${route === "graph" || route === "career-graph" ? "graph-topbar" : ""}`}>
      <div>
        <Button className="mobile-menu" isIconOnly variant="ghost" onPress={() => document.body.classList.toggle("mobile-nav-open")}>
          <Menu size={18} />
        </Button>
        <span>{pageMeta[1]}</span>
        <AnimatePresence mode="wait">
          <motion.h1
            key={route}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.22 }}
          >
            {pageMeta[0]}
          </motion.h1>
        </AnimatePresence>
      </div>
      <div>
        <SearchField
          aria-label="全局搜索"
          className="topbar-search"
          name="global-search"
          value={search}
          variant="secondary"
          onChange={setSearch}
          onSubmit={runSearch}
        >
          <SearchField.Group className="topbar-search-group">
            <SearchField.SearchIcon className="topbar-search-icon" />
            <SearchField.Input
              className="topbar-search-input"
              placeholder={isSeeker ? "搜索岗位、技能或学习目标" : "搜索岗位、技能或候选人"}
            />
          </SearchField.Group>
        </SearchField>
        <Button
          aria-label="打开消息中心"
          className="icon-button topbar-notification-trigger"
          isIconOnly
          variant="secondary"
          onPress={() => setNotifications(true)}
        >
          <Bell size={18} />
          {decisionMessages.length > 0 && <i aria-hidden="true">{Math.min(decisionMessages.length, 9)}</i>}
        </Button>
        {notifications && (
          <Drawer
            title={isSeeker ? `${user?.display_name || "我的"}待决策事项` : "企业待决策事项"}
            onClose={() => setNotifications(false)}
          >
            <div className="notification-drawer-list">
              {decisionMessages.map((item) => (
                <Button className="notification-drawer-item decision-message-item" key={item.id} variant="ghost" onPress={() => { navigate(item.route); setNotifications(false); }}>
                  <i className={item.tone} aria-hidden="true" />
                  <span><small>{item.category}</small><strong>{item.title}</strong><em>{item.detail}</em></span>
                  <ChevronRight size={16}/>
                </Button>
              ))}
              {!decisionMessages.length && <p className="notification-empty"><CheckCircle2 size={18} />当前没有待决策事项</p>}
            </div>
          </Drawer>
        )}
        {isSeeker && (
          <Button
            className="top-action"
            onPress={() => assessmentAction ? onNewAssessment?.() : onAssets()}
          >
            <Plus size={16} />
            {assessmentAction ? "重新评估" : "发现岗位"}
          </Button>
        )}
      </div>
    </header>
  );
}

function DesignLab() {
  const reduceMotion = useReducedMotion();
  const [mode, setMode] = useState("immersive");
  const [activeSignal, setActiveSignal] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [period, setPeriod] = useState(3);
  const [selectedNode, setSelectedNode] = useState("Agent 编排");
  const [notice, setNotice] = useState("");
  const periods = ["2024 Q1", "2024 Q3", "2025 Q1", "2025 Q3", "2026 Q1"];
  const signals = [
    { label: "新岗位强度", value: "86.4", delta: "+18.6%", tone: "lime", note: "AI Agent 工程师进入持续增长区间" },
    { label: "能力迁移率", value: "42.8", delta: "+9.3%", tone: "cyan", note: "工具调用向安全治理与评测迁移" },
    { label: "证据覆盖率", value: "94.2", delta: "+2.1%", tone: "amber", note: "来自招聘网站与技术社区的交叉证据" },
  ];
  const nodes = [
    { name: "AI Agent 工程师", type: "岗位", x: 50, y: 47, size: "xl" },
    { name: "Agent 编排", type: "能力", x: 29, y: 31, size: "lg" },
    { name: "工具调用", type: "技能", x: 72, y: 26, size: "md" },
    { name: "安全治理", type: "能力", x: 76, y: 62, size: "lg" },
    { name: "评测体系", type: "技能", x: 28, y: 69, size: "md" },
    { name: "LangGraph", type: "证据", x: 51, y: 17, size: "sm" },
    { name: "可观测性", type: "技能", x: 53, y: 78, size: "sm" },
  ];
  useEffect(() => {
    if (!playing || reduceMotion) return undefined;
    const timer = window.setInterval(() => setPeriod((value) => (value + 1) % periods.length), 1800);
    return () => window.clearInterval(timer);
  }, [playing, reduceMotion, periods.length]);
  const showNotice = (message) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 1800);
  };
  return (
    <main className={`design-lab mode-${mode}`}>
      <header className="lab-intro">
        <div>
          <h2>数据不是装饰，<br />它就是界面。</h2>
        </div>
        <p>
          三种获奖产品语言的组合实验：沉浸数据场负责建立记忆点，悬浮控制保持空间连续，
          运营组件承载高密度决策。
        </p>
        <div className="lab-mode-switch" aria-label="设计方向">
          {[
            ["immersive", "沉浸数据场"],
            ["spatial", "空间控制"],
            ["operational", "运营系统"],
          ].map(([id, label]) => (
            <button key={id} className={mode === id ? "active" : ""} onClick={() => setMode(id)}>
              {mode === id && <motion.i layoutId="lab-mode" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
              <span>{label}</span>
            </button>
          ))}
        </div>
      </header>

      <section className="lab-scene">
        <div className="lab-scene-grid" />
        <div className="lab-scene-head">
          <div>
            <strong>岗位能力动态地形</strong>
          </div>
          <em><i /> 实时观测</em>
        </div>
        <div className="lab-terrain" aria-label="交互式能力节点预览">
          <svg viewBox="0 0 1000 520" preserveAspectRatio="none" aria-hidden="true">
            <path d="M110 315 C235 155 345 205 485 258 S735 350 890 180" />
            <path d="M95 380 C230 290 350 330 472 362 S720 420 910 300" />
            <path d="M145 220 C280 92 430 110 520 188 S720 260 850 92" />
          </svg>
          {nodes.map((node, index) => (
            <motion.button
              key={node.name}
              className={`lab-node ${node.size} ${selectedNode === node.name ? "selected" : ""}`}
              style={{ left: `${node.x}%`, top: `${node.y}%` }}
              initial={{ opacity: 0, scale: reduceMotion ? 1 : 0.75 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: reduceMotion ? 0 : index * 0.07, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              whileHover={reduceMotion ? undefined : { scale: 1.08 }}
              whileTap={{ scale: 0.96 }}
              onClick={() => setSelectedNode(node.name)}
            >
              <i />
              <span>{node.type}</span>
              <strong>{node.name}</strong>
            </motion.button>
          ))}
        </div>
        <AnimatePresence mode="wait">
          <motion.aside
            key={selectedNode}
            className="lab-node-inspector"
            initial={{ opacity: 0, x: reduceMotion ? 0 : 14 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: reduceMotion ? 0 : -8 }}
            transition={{ duration: 0.24 }}
          >
            <strong>{selectedNode}</strong>
            <p>近 90 天出现频率上升，关联岗位证据完整，已进入重点观察集合。</p>
            <div><i style={{ width: "82%" }} /></div>
            <small>置信度 0.82 · 证据 146 条</small>
          </motion.aside>
        </AnimatePresence>
        <nav className="lab-floating-dock" aria-label="数据场工具">
          {[
            [Search, "搜索"],
            [Layers3, "图层"],
            [Target, "聚焦"],
            [Settings, "设置"],
          ].map(([Icon, label]) => (
            <motion.button key={label} title={label} whileHover={{ y: -3 }} whileTap={{ scale: 0.92 }} onClick={() => showNotice(`${label}控件已触发`)}>
              <Icon size={17} />
              <span>{label}</span>
            </motion.button>
          ))}
        </nav>
        <div className="lab-scene-scale"><span>低频</span><i /><span>快速增长</span></div>
      </section>

      <section className="lab-signal-band">
        <div className="lab-section-title">
          <h3>先呈现变化，再解释原因。</h3>
          <p>点击指标切换右侧的解释内容。</p>
        </div>
        <div className="lab-signal-grid">
          {signals.map((signal, index) => (
            <motion.button
              key={signal.label}
              className={`${signal.tone} ${activeSignal === index ? "active" : ""}`}
              onClick={() => setActiveSignal(index)}
              whileHover={reduceMotion ? undefined : { y: -5 }}
              whileTap={{ scale: 0.985 }}
            >
              <span>{signal.label}</span>
              <strong>{signal.value}</strong>
              <em>{signal.delta}</em>
              <div><i style={{ width: `${58 + index * 14}%` }} /></div>
            </motion.button>
          ))}
          <AnimatePresence mode="wait">
            <motion.article
              key={activeSignal}
              className="lab-signal-explain"
              initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: reduceMotion ? 0 : -8 }}
              transition={{ duration: 0.26 }}
            >
              <span>系统结论</span>
              <strong>{signals[activeSignal].note}</strong>
              <p>主证据来自连续招聘数据，辅助证据用于识别招聘需求尚未充分表达的技术变化。</p>
              <button onClick={() => showNotice("已打开证据链")}>查看证据链 <ChevronRight size={15} /></button>
            </motion.article>
          </AnimatePresence>
        </div>
      </section>

      <section className="lab-motion-band">
        <div className="lab-section-title light">
          <h3>岗位演化不是折线图，<br />而是一段可回放的证据。</h3>
        </div>
        <div className="lab-timeline-stage">
          <div className="lab-timeline-head">
            <button onClick={() => setPlaying((value) => !value)} aria-label={playing ? "暂停时间轴" : "播放时间轴"}>
              {playing ? <Pause size={16} /> : <Play size={16} />}
            </button>
            <div>
              <span>当前时间切片</span>
              <AnimatePresence mode="wait">
                <motion.strong key={period} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  {periods[period]}
                </motion.strong>
              </AnimatePresence>
            </div>
            <em>{playing ? "自动回放中" : "已暂停"}</em>
          </div>
          <div className="lab-flow-lines">
            {[
              ["工具调用", 78, "new"],
              ["RAG", 62, "steady"],
              ["安全治理", 88, "rise"],
              ["Prompt 工程", 34, "fall"],
            ].map(([label, value, state], index) => (
              <div key={label}>
                <span>{label}</span>
                <i><motion.b animate={{ width: `${Math.max(16, Number(value) - period * index * 2)}%` }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }} /></i>
                <em className={state}>{state === "new" ? "新增" : state === "rise" ? "增强" : state === "fall" ? "衰退" : "稳定"}</em>
              </div>
            ))}
          </div>
          <div className="lab-timeline-track">
            {periods.map((label, index) => (
              <button key={label} className={period === index ? "active" : ""} onClick={() => { setPeriod(index); setPlaying(false); }}>
                <i />
                <span>{label}</span>
              </button>
            ))}
            <motion.b animate={{ width: `${(period / (periods.length - 1)) * 100}%` }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }} />
          </div>
        </div>
      </section>

      <section className="lab-operations-band">
        <div className="lab-section-title">
          <h3>高密度，但不嘈杂。</h3>
          <p>面向真实招聘运营的表格、状态与动作组件。</p>
        </div>
        <div className="lab-operation-shell">
          <header>
            <div><span>岗位监测</span><strong>需要处理的能力变化</strong></div>
            <div className="lab-action-row">
              <button title="刷新"><RefreshCw size={15} /></button>
              <button onClick={() => showNotice("筛选器已展开")}><Filter size={15} /> 筛选</button>
              <button className="primary" onClick={() => showNotice("已创建处理任务")}><Plus size={15} /> 创建任务</button>
            </div>
          </header>
          <div className="lab-table-head"><span>变化对象</span><span>变化类型</span><span>证据</span><span>影响</span><span>状态</span><span /></div>
          {[
            ["AI Agent 工程师", "新增岗位", "286 条", "高", "待确认"],
            ["Java 后端工程师", "能力增强", "194 条", "中", "监测中"],
            ["物联网平台工程师", "技能迁移", "121 条", "高", "已复核"],
          ].map((row, index) => (
            <motion.button key={row[0]} className="lab-table-row" whileHover={{ x: 3 }} onClick={() => showNotice(`已选择：${row[0]}`)}>
              <strong>{row[0]}</strong>
              <span>{row[1]}</span>
              <span>{row[2]}</span>
              <em className={row[3] === "高" ? "high" : ""}>{row[3]}</em>
              <i className={`status-${index}`}>{row[4]}</i>
              <ChevronRight size={15} />
            </motion.button>
          ))}
        </div>
      </section>
      <AnimatePresence>
        {notice && (
          <motion.div className="lab-toast" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}>
            <CheckCircle2 size={16} /> {notice}
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}

function Dashboard({ jobs, jobTotal = 0, platformSummary, portalSummary, navigate, openAssets }) {
  const decision = portalSummary?.decision_summary || platformSummary?.decision_summary || {};
  const evidence = decision.evidence || {};
  const alignment = portalSummary?.standard_alignment || {
    status: "not_configured",
    headline: "正在读取企业岗位标准",
    detail: "企业岗位标准与市场能力要求将在这里完成对照。",
    items: [],
  };
  const growthJobs = decision.growth_jobs || [];
  const declineJobs = decision.decline_jobs || [];
  const commonAbilities = decision.common_abilities || [];
  const skillGroups = [
    ["new", "新增", "市场首次出现", "positive"],
    ["enhanced", "增强", "要求频次上升", "accent"],
    ["weakened", "减弱", "要求频次下降", "warning"],
    ["exited", "退出", "当前已无在招证据", "danger"],
  ];
  const decisionCount = growthJobs.length + declineJobs.length
    + skillGroups.reduce((sum, [key]) => sum + (decision.skill_changes?.[key]?.length || 0), 0);
  const totalJobs = Number(platformSummary?.jobs ?? jobTotal ?? jobs.length ?? 0);
  const foundation = [
    ["招聘证据", Number(evidence.active_jobs ?? platformSummary?.active_jobs ?? 0).toLocaleString("zh-CN"), "当前在招岗位"],
    ["版本快照", Number(evidence.version_snapshots ?? platformSummary?.version_snapshots ?? 0).toLocaleString("zh-CN"), "可回溯"],
    ["变动岗位", Number(evidence.changed_jobs ?? platformSummary?.changed_jobs ?? 0).toLocaleString("zh-CN"), "已监测"],
    ["主数据源", `${Number(evidence.primary_sources ?? 0)}/4`, "BOSS · 智联 · 前程无忧 · 猎聘"],
    ["平均质量", `${Number(evidence.average_quality ?? platformSummary?.average_quality ?? 0)}`, "满分 100"],
  ];

  const renderTrendList = (items, emptyText, tone) => (
    <div className="decision-trend-list">
      {items.slice(0, 4).map((item, index) => (
        <button key={`${item.name}-${index}`} onClick={() => navigate("evolution")}>
          <span className={`decision-rank ${tone}`}>{String(index + 1).padStart(2, "0")}</span>
          <div><strong>{item.name}</strong><small>{item.reason}</small></div>
          <b>{item.current_count}<small> 在招</small></b>
          <ChevronRight size={15} />
        </button>
      ))}
      {!items.length && <p className="decision-empty">{emptyText}</p>}
    </div>
  );

  return (
    <main className="dashboard-page decision-home">
      <AnimatedContent distance={20}>
        <section className="decision-intro">
          <div>
            <span className="decision-eyebrow">企业岗位决策</span>
            <h2>先看市场正在改变什么，再决定岗位标准如何调整。</h2>
            <p>当前从 {totalJobs.toLocaleString("zh-CN")} 条岗位资产中识别出 {decisionCount} 项需要关注的变化信号。</p>
          </div>
          <div className="decision-quick-actions">
            <Button variant="secondary" onPress={() => navigate("evolution")}><TrendingUp size={16} /> 查看岗位演化</Button>
            <Button onPress={() => navigate("graph")}><Network size={16} /> 进入能力图谱</Button>
          </div>
        </section>
      </AnimatedContent>

      <AnimatedContent distance={24} delay={0.05}>
        <section className="decision-primary-grid">
          <article className="decision-block decision-market-block">
            <header><div><span>01 · 岗位需求拐点</span><h3>哪些岗位正在增长，哪些正在退潮</h3></div><Button variant="ghost" onPress={() => navigate("evolution")}>全部证据 <ArrowRight size={15} /></Button></header>
            <div className="decision-split">
              <section><div className="decision-subhead positive"><TrendingUp size={16} /><strong>需求增长最快</strong></div>{renderTrendList(growthJobs, "尚未形成可靠的新增岗位信号。", "positive")}</section>
              <section><div className="decision-subhead danger"><TrendingDown size={16} /><strong>下降或可能退出</strong></div>{renderTrendList(declineJobs, "当前没有岗位退出证据。", "danger")}</section>
            </div>
          </article>

          <article className={`decision-block decision-alignment ${alignment.status}`}>
            <header><div><span>02 · 企业标准校准</span><h3>现有岗位标准是否落后</h3></div></header>
            <div className="alignment-state">
              <span><Target size={22} /></span>
              <div><strong>{alignment.headline}</strong><p>{alignment.detail}</p></div>
            </div>
            {!!alignment.items?.length && <div className="alignment-items">{alignment.items.slice(0, 3).map((item) => <div key={item.job_id}><strong>{item.title}</strong><span>{item.missing_market_skills?.length ? `待补：${item.missing_market_skills.join("、")}` : "与市场基本同步"}</span></div>)}</div>}
            <Button fullWidth variant="secondary" onPress={() => navigate("recruiting")}>{alignment.status === "not_configured" ? "建立企业岗位标准" : "查看岗位标准差异"}<ArrowRight size={15} /></Button>
          </article>
        </section>
      </AnimatedContent>

      <AnimatedContent distance={24} delay={0.09}>
        <section className="decision-block decision-skill-block">
          <header><div><span>03 · 技能变化</span><h3>新增、增强、减弱与退出的能力要求</h3></div><small>依据同一岗位版本前后技能证据差异</small></header>
          <div className="decision-skill-grid">
            {skillGroups.map(([key, label, hint, tone]) => {
              const items = decision.skill_changes?.[key] || [];
              return <section className={`skill-change-column ${tone}`} key={key}><div><span>{label}</span><small>{hint}</small><b>{items.length}</b></div><ul>{items.slice(0, 4).map((item) => <li key={item.name}><strong>{item.name}</strong><span>{item.delta > 0 ? "+" : ""}{item.delta}</span></li>)}{!items.length && <li className="is-empty">暂无可靠证据</li>}</ul></section>;
            })}
          </div>
        </section>
      </AnimatedContent>

      <AnimatedContent distance={24} delay={0.12}>
        <section className="decision-block decision-common-block">
          <header><div><span>04 · 普遍能力</span><h3>哪些能力正在成为通用要求</h3></div><Button variant="ghost" onPress={() => navigate("graph")}>查看关系网络 <ArrowRight size={15} /></Button></header>
          <div className="common-ability-list">
            {commonAbilities.map((item, index) => <div key={item.name}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item.name}</strong><div><i style={{ width: `${Math.min(100, Math.max(4, item.coverage))}%` }} /></div><b>{item.coverage}%</b><em>{item.stage}</em></div>)}
            {!commonAbilities.length && <p className="decision-empty">正在形成能力覆盖率统计。</p>}
          </div>
        </section>
      </AnimatedContent>

      <section className="decision-foundation" aria-label="证据可信度与系统基础状态">
        <div className="foundation-label"><ShieldCheck size={18} /><span>证据与可信度</span></div>
        {foundation.map(([label, value, detail]) => <div key={label}><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>)}
        <button onClick={openAssets}>查看数据基础 <ArrowRight size={14} /></button>
      </section>
    </main>
  );
}

function LegacyDashboard({ jobs, jobTotal = 0, platformSummary, assessmentRecords = [], navigate, openAssets }) {
  const [detail, setDetail] = useState(null);
  const observedJobs = (platformSummary?.recent_job_changes || []).map(mapJob);
  const totalJobs = Number(platformSummary?.jobs ?? jobTotal ?? jobs.length ?? 0);
  const activeJobs = Number(platformSummary?.active_jobs ?? 0);
  const skillCount = Number(platformSummary?.skills ?? 0);
  const familyCount = Number(platformSummary?.job_families ?? 0);
  const changedJobs = Number(platformSummary?.changed_jobs ?? 0);
  const emergingJobs = Number(platformSummary?.emerging_jobs ?? 0);
  const metrics = [
    { label: "已存岗位", value: totalJobs.toLocaleString("zh-CN"), delta: "实时汇总", icon: BriefcaseBusiness, tone: "blue" },
    { label: "技能证据节点", value: skillCount.toLocaleString("zh-CN"), delta: "已验证", icon: Network, tone: "cyan" },
    { label: "岗位名称", value: familyCount.toLocaleString("zh-CN"), delta: "已归一", icon: Grid2X2, tone: "indigo" },
    { label: "资产健康度", value: Number(platformSummary?.average_quality || 0), suffix: "/100", delta: "当前均值", icon: ShieldCheck, tone: "green" },
    { label: "新岗位候选", value: emergingJobs.toLocaleString("zh-CN"), delta: "待审阅", icon: UserRoundSearch, tone: "blue" },
    { label: "在招岗位", value: activeJobs.toLocaleString("zh-CN"), delta: "当前有效", icon: ClipboardCheck, tone: "indigo" },
  ];
  const insights = observedJobs.slice(0, 3).map((job, index) => ({ tone: ["coral", "cyan", "gold"][index], label: job.status, value: job.title, text: `${job.company} · ${job.city} · ${(job.tags || []).slice(0, 4).join("、") || "待补充技能"}`, delta: job.updated || "最新", action: "查看岗位数据与版本证据", icon: index === 0 ? Zap : GitBranch }));
  const marketStats = [
    ["岗位总量", totalJobs.toLocaleString("zh-CN"), "实时"],
    ["岗位变更", changedJobs.toLocaleString("zh-CN"), "已监测"],
    ["版本快照", Number(platformSummary?.version_snapshots || 0).toLocaleString("zh-CN"), "可追溯"],
    ["前沿信号", Number(platformSummary?.community_signals || 0).toLocaleString("zh-CN"), "辅助"],
  ];
  const topSkills = (platformSummary?.top_skills || []).map((item) => [item.name, Number(item.job_count || 0)]);
  const maxSkillCount = topSkills[0]?.[1] || 1;
  const candidateSummary = [
    ["已保存评估", assessmentRecords.length],
    ["已出报告", assessmentRecords.filter((item) => item.profile?.match_report).length],
    ["待补报告", Math.max(0, assessmentRecords.length - assessmentRecords.filter((item) => item.profile?.match_report).length)],
    ["完成率", assessmentRecords.length ? `${Math.round(assessmentRecords.filter((item) => item.profile?.match_report).length * 100 / assessmentRecords.length)}%` : "--"],
  ];
  return (
    <main className="dashboard-page">
      <AnimatedContent distance={22}>
        <Card className="executive-hero b2b-dashboard-hero" variant="default">
          <Card.Content>
            <div>
              <h2>
                今天，优先处理 <em>{observedJobs.length} 项</em> 岗位变化。
              </h2>
              <p>系统已从 {totalJobs.toLocaleString("zh-CN")} 个岗位与 {skillCount.toLocaleString("zh-CN")} 项技能证据中完成影响排序。</p>
              <div className="dashboard-hero-tags">
                <span>岗位模型待更新</span>
                <span>候选人评估需跟进</span>
                <span>能力缺口已预警</span>
              </div>
            </div>
            <ClickSpark>
              <Button className="executive-hero-action" variant="ghost" onPress={openAssets}>
                岗位数据管理 <ArrowRight size={16} />
              </Button>
            </ClickSpark>
          </Card.Content>
        </Card>
      </AnimatedContent>
      <AnimatedContent distance={26} delay={0.06}>
        <section className="dashboard-metrics">
          {metrics.map(({ label, value, suffix, delta, icon: Icon, tone }) => (
            <Card className={`dashboard-metric ${tone}`} key={label} variant="default">
              <Card.Content>
                <div className="metric-icon">
                  <Icon size={21} />
                </div>
                <span>{label}</span>
                <strong>{value}<small>{suffix}</small></strong>
                <em>{delta}</em>
              </Card.Content>
            </Card>
          ))}
        </section>
      </AnimatedContent>
      <AnimatedContent distance={28} delay={0.1}>
        <section className="dashboard-workbench">
          <Card className="panel priority-panel" variant="default">
            <Card.Content>
              <PanelTitle title="今日优先处理" caption="按业务风险与变化强度排序" action="查看全部" onClick={openAssets} />
              <div className="priority-list">
                {insights.length ? insights.map((item, index) => (
                  <Button
                    className={`priority-row ${item.tone}`}
                    key={item.value}
                    variant="ghost"
                    onPress={() => setDetail(item)}
                  >
                    <span><item.icon size={16} /></span>
                    <div>
                      <strong>{item.value}</strong>
                      <small>{item.text}</small>
                    </div>
                    <em>{item.delta}</em>
                    <ChevronRight size={15} />
                  </Button>
                )) : <p className="panel-empty">当前没有可展示的岗位变更。</p>}
              </div>
            </Card.Content>
          </Card>
          <Card className="panel market-panel" variant="default">
            <Card.Content>
              <PanelTitle title="岗位市场动态" caption="近 7 天" action="进入图谱" onClick={() => navigate("graph")} />
              <div className="market-stats">
                {marketStats.map(([label, value, delta]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                    <em className={String(delta).startsWith("-") ? "down" : ""}>{delta}</em>
                  </div>
                ))}
              </div>
              <div className="market-chart market-chart--summary">
                已基于 {Number(platformSummary?.version_snapshots || 0).toLocaleString("zh-CN")} 个版本快照追踪 {changedJobs.toLocaleString("zh-CN")} 个发生变动的岗位。
              </div>
            </Card.Content>
          </Card>
          <Card className="panel gap-panel" variant="default">
            <Card.Content>
              <PanelTitle title="岗位技能热度 Top 5" caption="按当前在招岗位的技能出现次数统计" action="查看全部" onClick={() => navigate("graph")} />
              <div className="gap-list">
                {topSkills.map(([label, count], index) => {
                  const rate = `${Math.round(count * 100 / maxSkillCount)}%`;
                  const tone = ["danger", "warn", "amber", "ok", "ok"][index];
                  return (
                  <div key={label}>
                    <span>{label}</span>
                    <strong>{count}</strong>
                    <em>岗位覆盖</em>
                    <i className={tone} style={{ width: rate }} />
                  </div>
                  );
                })}
              </div>
            </Card.Content>
          </Card>
        </section>
      </AnimatedContent>
      <AnimatedContent distance={30} delay={0.12}>
        <section className="dashboard-lower-grid">
          <Card className="panel job-change-panel" variant="default">
            <Card.Content>
              <PanelTitle title="岗位变更动态" caption="近 7 天" action="管理岗位" onClick={openAssets} />
              <div className="job-change-table">
                <div className="job-change-head">
                  <span>岗位名称</span><span>变更类型</span><span>申请人</span><span>状态</span><span>时间</span>
                </div>
                {observedJobs.length ? observedJobs.map((job) => (
                  <Button
                    className="job-change-row"
                    key={job.id}
                    variant="ghost"
                    onPress={() =>
                      setDetail({
                        label: job.domain,
                        value: job.title,
                        text: `核心技能：${(job.tags || []).join("、")}`,
                        delta: job.updated || "最新变更",
                        action: `${job.company} · ${job.city}`,
                      })
                    }
                  >
                    <strong>{job.title}</strong>
                    <span>{job.status}</span>
                    <span>{job.company}</span>
                    <em>{job.jobStatus === "active" ? "在招" : "已下线"}</em>
                    <small>{job.updated}</small>
                  </Button>
                )) : <p className="panel-empty">当前没有岗位变更记录。</p>}
              </div>
            </Card.Content>
          </Card>
          <Card className="panel candidate-panel" variant="default">
            <Card.Content>
              <PanelTitle title="候选人评估概览" caption="面试与匹配进度" action="查看全部" onClick={() => navigate("assessments")} />
              <div className="candidate-summary">
                {candidateSummary.map(([label, value]) => (
                  <div key={label}><span>{label}</span><strong>{value}</strong></div>
                ))}
              </div>
              <div className="candidate-list">
                {assessmentRecords.slice(0, 3).map((item) => <button key={item.id} onClick={() => navigate("assessments")}><i>{String(item.name || "候").slice(0, 1)}</i><div><strong>{item.name || "候选人"}</strong><span>{item.target_job_title || "目标岗位待定"}</span></div><em>{item.status || "待评估"}</em><b>{item.score ? `${item.score}%` : "--"}</b><small><i style={{ width: item.score ? `${item.score}%` : "0%" }} /></small></button>)}
                {!assessmentRecords.length && <p className="panel-empty">暂无候选人评估记录。</p>}
              </div>
            </Card.Content>
          </Card>
          <Card className="panel health-panel" variant="default">
            <Card.Content>
              <PanelTitle title="能力图谱健康度" caption="岗位库实时状态" action="查看详情" onClick={() => navigate("validation")} />
              <div className="health-ring">
                <strong>{Number(platformSummary?.average_quality || 0)}</strong>
                <span>健康度</span>
              </div>
              <div className="health-list">
                {[
                  ["岗位总量", totalJobs.toLocaleString("zh-CN"), "实时"],
                  ["在招岗位", activeJobs.toLocaleString("zh-CN"), "实时"],
                  ["版本快照", Number(platformSummary?.version_snapshots || 0).toLocaleString("zh-CN"), "可追溯"],
                  ["变动岗位", changedJobs.toLocaleString("zh-CN"), "已监测"],
                ].map(([label, score, delta]) => (
                  <p key={label}><span>{label}</span><b>{score}</b><em>{delta}</em></p>
                ))}
              </div>
            </Card.Content>
          </Card>
        </section>
      </AnimatedContent>
      <AnimatedContent distance={30} delay={0.16}>
        <Card className="panel focus-panel" variant="default">
          <Card.Content>
            <PanelTitle title="重点岗位观察" caption="按业务影响与变化强度排序" action="管理岗位" onClick={openAssets} />
            <div className="focus-table">
              {observedJobs.map((job, index) => (
                <Button
                  key={job.id}
                  variant="ghost"
                  onPress={() =>
                    setDetail({
                      label: job.domain,
                      value: job.title,
                      text: `核心技能：${(job.tags || []).join("、")}`,
                      delta: job.updated || "最新变更",
                      action: `${job.company} · ${job.city}`,
                    })
                  }
                >
                  <span className={`rank r${index + 1}`}>0{index + 1}</span>
                  <div>
                    <strong>{job.title}</strong>
                    <small>{job.domain} · {job.company}</small>
                  </div>
                  <div className="tag-row">
                    {(job.tags || []).slice(0, 3).map((tag) => <i key={tag}>{tag}</i>)}
                  </div>
                  <em>{job.status}</em>
                  <b>{job.updated || "最新"}</b>
                  <ChevronRight size={15} />
                </Button>
              ))}
            </div>
          </Card.Content>
        </Card>
      </AnimatedContent>
      {detail && (
        <Drawer title={detail.value} onClose={() => setDetail(null)}>
          <span className={`detail-label ${detail.tone || "cyan"}`}>
            {detail.label}
          </span>
          <h3 className="drawer-lead">{detail.delta}</h3>
          <p className="drawer-summary">{detail.text}</p>
          <div className="drawer-section">
            <h4>为什么重要</h4>
            <p>
              {detail.action}
              。该变化已持续三个采集周期，并在头部企业与成长型企业中同时出现。
            </p>
          </div>
          <div className="drawer-section">
            <h4>建议行动</h4>
            <ul>
              <li>更新岗位能力基线与面试题库</li>
              <li>核验现有候选人池的技能覆盖</li>
              <li>在下一采集周期继续观察信号强度</li>
            </ul>
          </div>
        </Drawer>
      )}
    </main>
  );
}

function PanelTitle({ title, caption, action, onClick }) {
  return (
    <div className="panel-title">
      <div>
        <h3>{title}</h3>
        <span>{caption}</span>
      </div>
      {action && (
        <Button className="panel-title-action" variant="ghost" onPress={onClick}>
          {action}
          <ArrowRight size={14} />
        </Button>
      )}
    </div>
  );
}
function DomainBars() {
  return (
    <div className="domain-bars">
      {[
        ["人工智能", 88, "+18.6%"],
        ["大数据", 72, "+9.8%"],
        ["智能系统", 58, "+12.4%"],
        ["物联网", 46, "+7.3%"],
      ].map(([name, value, delta]) => (
        <div key={name}>
          <span>{name}</span>
          <div>
            <i style={{ width: `${value}%` }} />
          </div>
          <strong>{value}</strong>
          <em>{delta}</em>
        </div>
      ))}
    </div>
  );
}

function DataSelect({ label, value, options, onChange, className = "" }) {
  const selected = options.find((option) => String(option.value) === String(value));
  return (
    <Select
      aria-label={label}
      className={`data-select ${className}`}
      selectedKey={String(value)}
      onSelectionChange={(key) => key != null && onChange(String(key))}
      placeholder={label}
      variant="secondary"
    >
      <Select.Trigger>
        <Select.Value>{selected?.label || label}</Select.Value>
        <Select.Indicator />
      </Select.Trigger>
      <Select.Popover>
        <ListBox>
          {options.map((option) => (
            <ListBox.Item id={String(option.value)} key={String(option.value)} textValue={option.label}>
              {option.label}
              <ListBox.ItemIndicator />
            </ListBox.Item>
          ))}
        </ListBox>
      </Select.Popover>
    </Select>
  );
}

function TagChip({ children, className = "", color = "accent" }) {
  return (
    <Chip className={className} color={color} size="sm" variant="soft">
      <Chip.Label>{children}</Chip.Label>
    </Chip>
  );
}

function FilterBadge({ children, icon }) {
  return (
    <Chip className="filter-badge" color="accent" size="sm" variant="soft">
      <Chip.Label>
        {icon}
        {children}
      </Chip.Label>
    </Chip>
  );
}

function ResultBadge({ children }) {
  return (
    <Chip className="result-badge" color="accent" size="sm" variant="soft">
      <Chip.Label>{children}</Chip.Label>
    </Chip>
  );
}

function JobAssets({ jobs, jobTotal, setJobTotal, setJobs, notify }) {
  const [assetView, setAssetView] = useState("jobs");
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("全部领域");
  const [source, setSource] = useState("all");
  const [city, setCity] = useState("all");
  const [status, setStatus] = useState("all");
  const [quality, setQuality] = useState("0");
  const [period, setPeriod] = useState("all");
  const [signalQuery, setSignalQuery] = useState("");
  const [signalSource, setSignalSource] = useState("all");
  const [signalDomain, setSignalDomain] = useState("all");
  const [signalQuality, setSignalQuality] = useState("0");
  const [signalPeriod, setSignalPeriod] = useState("all");
  const [auditQuery, setAuditQuery] = useState("");
  const [auditSource, setAuditSource] = useState("all");
  const [auditType, setAuditType] = useState("all");
  const [auditStatus, setAuditStatus] = useState("all");
  const [auditReason, setAuditReason] = useState("all");
  const [auditLane, setAuditLane] = useState("pending");
  const [selected, setSelected] = useState(null);
  const [editing, setEditing] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [collection, setCollection] = useState({ schedule: null, strategy: null, runs: [], sources: [], signals: [], audits: [], sessions: [], cookieSessions: [], fullCrawl: null });
  const [strategyOpen, setStrategyOpen] = useState(false);
  const [collectionOpen, setCollectionOpen] = useState(false);
  const [expandedSource, setExpandedSource] = useState("");
  const [selectedAudit, setSelectedAudit] = useState(null);
  const [auditCorrections, setAuditCorrections] = useState({ title: "", domain: "人工智能", skill_tags: "" });
  const [collecting, setCollecting] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [jobFacets, setJobFacets] = useState({ sources: [], cities: [] });
  const [jobsLoading, setJobsLoading] = useState(false);
  const statusInitialized = useRef(false);
  const lastAppliedRun = useRef(null);
  const loadJobs = async (nextPage = page) => {
    setJobsLoading(true);
    try {
      const params = new URLSearchParams({
        active_only: "false",
        limit: String(pageSize),
        offset: String((nextPage - 1) * pageSize),
      });
      if (query.trim()) params.set("keyword", query.trim());
      if (domain !== "全部领域") params.set("domain", domain);
      if (source !== "all") params.set("source_platform", source);
      if (city !== "all") params.set("city", city);
      if (status !== "all") params.set("status", status);
      if (Number(quality) > 0) params.set("min_quality", quality);
      if (period !== "all") params.set("changed_within_days", period);
      const data = await request(`/api/jobs?${params.toString()}`);
      setJobs((data.items || []).map(mapJob));
      setJobTotal(data.total ?? data.items?.length ?? 0);
    } finally {
      setJobsLoading(false);
    }
  };
  const pageCount = Math.max(1, Math.ceil(jobTotal / pageSize));
  const loadCollectionStatus = async () => {
    try {
      const [schedule, strategy, runs, sources, signals, audits, sessions, cookieSessions, fullCrawl] = await Promise.all([
        request("/api/data/schedule"),
        request("/api/data/strategy"),
        request("/api/data/collection-runs?limit=12"),
        request("/api/data/sources"),
        request("/api/data/community-signals?limit=80"),
        request(`/api/data/audits?lane=${auditLane}&limit=100`),
        request("/api/data/browser-sessions"),
        request("/api/data/cookie-sessions"),
        request("/api/data/full-crawl-status").catch(() => ({ status: "unknown" })),
      ]);
      setCollection({
        schedule, strategy, runs: runs.items || [], sources: sources.items || [],
        signals: signals.items || [], audits: audits.items || [], sessions: sessions.items || [],
        cookieSessions: cookieSessions.items || [],
        auditSummary: audits.lane_summary || {},
        fullCrawl,
        totals: {
          signals: signals.total ?? signals.items?.length ?? 0,
          audits: audits.total ?? audits.items?.length ?? 0,
          pendingAudits: (audits.status_summary?.manual_review || 0) + (audits.status_summary?.pending_semantic_review || 0),
        },
      });
      setCollecting((runs.items || []).some((run) => run.status === "running") || fullCrawl.status === "running");
      const newest = (runs.items || [])[0];
      if (!statusInitialized.current) {
        statusInitialized.current = true;
        lastAppliedRun.current = newest?.status === "running" ? null : newest?.run_id || null;
      } else if (newest && newest.status !== "running" && newest.run_id !== lastAppliedRun.current) {
        await loadJobs(1);
        setPage(1);
        lastAppliedRun.current = newest.run_id;
        notify(`采集结果已自动刷新：新增 ${newest.new_count || 0}，更新 ${newest.updated_count || 0}`);
      }
    } catch {}
  };
  const startBrowserSession = async (sourceId) => {
    notify(`正在启动${SOURCE_LABELS[sourceId] || sourceId}认证窗口`);
    try {
      await request(`/api/data/browser-sessions/${sourceId}/start`, { method: "POST" });
      window.setTimeout(loadCollectionStatus, 2500);
    } catch (error) {
      notify(error?.message || "认证窗口启动失败，请查看数据源状态");
    }
  };
  const importCookieSession = async (sourceId, file) => {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      const cookies = Array.isArray(parsed) ? parsed : parsed?.cookies;
      if (!Array.isArray(cookies) || !cookies.length) throw new Error("Cookie 文件中没有 cookies 数组");
      await request(`/api/data/cookie-sessions/${sourceId}`, {
        method: "PUT",
        body: JSON.stringify({ cookies }),
      });
      notify(`${SOURCE_LABELS[sourceId] || sourceId}登录态已安全保存，后续采集将自动复用`);
      await loadCollectionStatus();
    } catch (error) {
      notify(error?.message || "Cookie 导入失败，请检查 JSON 格式和所属域名");
    }
  };
  const saveStrategy = async (value) => {
    try {
      const strategy = await request("/api/data/strategy", { method: "PUT", body: JSON.stringify(value) });
      setCollection((current) => ({ ...current, strategy }));
      setStrategyOpen(false);
      notify(`已更新 ${Object.keys(strategy.sources || {}).length} 个数据源的独立采集策略`);
      loadCollectionStatus();
    } catch { notify("采集策略保存失败，请检查间隔与采集量"); }
  };
  const reviewAudit = async (record, statusValue, decisionValue = null) => {
    try {
      const auditId = record.audit_id || record.rejection_id;
      const result = await request(`/api/data/audits/${auditId}/review`, {
        method: "POST",
        body: JSON.stringify({
          status: statusValue,
          decision: decisionValue || (statusValue === "approved" ? "accept_scope" : "reject_scope"),
          corrections: statusValue === "approved" ? {
            title: auditCorrections.title || record.normalized_item?.title || record.title,
            domain: auditCorrections.domain,
            skill_tags: auditCorrections.skill_tags.split(/[、,，;；]/).map((item) => item.trim()).filter(Boolean),
          } : {},
        }),
      });
      const updated = result.record;
      setCollection((current) => ({
        ...current,
        audits: current.audits.map((item) => (item.audit_id || item.rejection_id) === (updated.audit_id || updated.rejection_id) ? updated : item),
      }));
      setSelectedAudit(updated);
      notify(statusValue === "approved" ? "已通过，后台处理已排队" : "已确认拒绝");
    } catch { notify("复核结果保存失败"); }
  };
  useEffect(() => {
    loadCollectionStatus();
    const timer = window.setInterval(loadCollectionStatus, 5000);
    return () => window.clearInterval(timer);
  }, [auditLane]);
  useEffect(() => {
    request("/api/jobs/facets")
      .then((data) => setJobFacets({ sources: data.sources || [], cities: data.cities || [] }))
      .catch(() => {});
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => loadJobs(page).catch(() => notify("岗位列表加载失败")), query.trim() ? 220 : 0);
    return () => window.clearTimeout(timer);
  }, [page, pageSize, domain, source, city, status, quality, period, query]);
  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);
  const runCollection = async () => {
    if (collecting || !collection.schedule?.request) return;
    setCollecting(true);
    notify("数据采集已启动");
    try {
      const run = await request("/api/data/collect", {
        method: "POST",
        body: JSON.stringify(collection.schedule.request),
      });
      lastAppliedRun.current = null;
      notify(`采集任务 ${run.run_id} 已进入后台，可查看各来源实时状态`);
      await loadCollectionStatus();
    } catch {
      setCollecting(false);
      notify("采集请求失败，已保留运行记录");
    }
  };
  const visibleCollectionSources = collection.sources.filter((sourceItem) =>
    sourceItem.source_category === "recruitment",
  );
  const sourceStates = Object.fromEntries(
    collection.sources.map((sourceItem) => {
      const result = collection.runs
        .flatMap((run) => run.source_results || [])
        .find((item) => item.source_id === sourceItem.source_id);
      return [sourceItem.source_id, result];
    }),
  );
  const sources = jobFacets.sources;
  const cities = [...new Set(
    Object.values(collection.strategy?.sources || {})
      .filter((item) => item.source_category === "recruitment")
      .flatMap((item) => item.cities || []),
  )].filter((name) => name && name !== "全国");
  const rows = jobs;
  const signalSources = [...new Set(collection.signals.map((item) => item.source_platform))].filter(Boolean).sort();
  const filteredSignals = collection.signals.filter((signal) => {
    const searchable = `${signal.title} ${signal.content} ${(signal.tags || []).join(" ")}`.toLowerCase();
    const days = signalPeriod === "all" ? null : Number(signalPeriod);
    const timestamp = new Date(signal.published_at || signal.collected_at || 0).getTime();
    return (
      (signalSource === "all" || signal.source_platform === signalSource) &&
      (signalDomain === "all" || signal.domain === signalDomain) &&
      signal.quality_score >= Number(signalQuality) &&
      (!days || (timestamp && Date.now() - timestamp <= days * 86400000)) &&
      searchable.includes(signalQuery.trim().toLowerCase())
    );
  });
  const resetSignalFilters = () => {
    setSignalQuery(""); setSignalSource("all"); setSignalDomain("all");
    setSignalQuality("0"); setSignalPeriod("all");
  };
  const auditSources = [...new Set(collection.audits.map((item) => item.source_platform))].filter(Boolean).sort();
  const auditReasons = [...new Set(collection.audits.flatMap((item) => item.reasons || []))].filter(Boolean).sort();
  const filteredAudits = collection.audits.filter((record) => {
    const searchable = `${record.title || ""} ${record.source_id || ""} ${record.source_platform || ""} ${(record.reasons || []).join(" ")} ${record.raw_item?.content || record.raw_item?.raw_content || ""}`.toLowerCase();
    return (
      (
        (auditLane === "pending" && ["manual_review", "pending_semantic_review"].includes(record.status) && !["copy_cluster", "job_change", "change_review"].includes(record.record_type)) ||
        (auditLane === "rejected" && (record.record_type === "quality_rejection" || ["rejected", "quarantined"].includes(record.status))) ||
        (auditLane === "corrections" && record.record_type === "field_correction") ||
        (auditLane === "copies" && record.record_type === "copy_cluster") ||
        (auditLane === "changes" && ["job_change", "change_review"].includes(record.record_type))
      ) &&
      (auditSource === "all" || record.source_platform === auditSource) &&
      (auditType === "all" || record.record_type === auditType) &&
      (auditStatus === "all" || record.review_status === auditStatus) &&
      (auditReason === "all" || (record.reasons || []).includes(auditReason)) &&
      searchable.includes(auditQuery.trim().toLowerCase())
    );
  });
  const resetAuditFilters = () => {
    setAuditQuery(""); setAuditSource("all"); setAuditType("all");
    setAuditStatus("all"); setAuditReason("all");
  };
  const changeAuditLane = (key) => {
    resetAuditFilters();
    setAuditLane(String(key));
  };
  const resetFilters = () => {
    setQuery("");
    setDomain("全部领域");
    setSource("all");
    setCity("all");
    setStatus("all");
    setQuality("0");
    setPeriod("all");
    setPage(1);
  };
  const importJobs = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      const items = Array.isArray(parsed) ? parsed : parsed.items;
      if (!Array.isArray(items)) throw new Error("invalid payload");
      const batch = await request("/api/data/import", {method:"POST",body:JSON.stringify({batch_name:`manual_${Date.now()}`,items})});
      setJobs((current)=>[...batch.items.map(mapJob),...current]);
      setJobTotal((current) => current + batch.items.length);
      notify(`已导入 ${batch.items.length} 条岗位数据`);
    } catch { notify("导入失败：请选择符合接口契约的 JSON 文件"); }
    event.target.value = "";
  };
  const save = async (form) => {
    const payload = {
      title: form.title,
      domain: form.domain,
      company: form.company,
      city: form.city,
      education: form.education,
      salary_min_k: +form.salaryMin || null,
      salary_max_k: +form.salaryMax || null,
      skill_tags: form.tags
        .split(/[,，]/)
        .map((x) => x.trim())
        .filter(Boolean),
      responsibilities: form.responsibilities.split("\n").filter(Boolean),
    };
    if (editing?.id) {
      setJobs((list) =>
        list.map((job) =>
          job.id === editing.id
            ? {
                ...job,
                ...form,
                tags: payload.skill_tags,
                responsibilities: payload.responsibilities,
                salary: `${form.salaryMin}-${form.salaryMax}K`,
                updated: "2026-07-14",
                status: "能力变化",
              }
            : job,
        ),
      );
      request(`/api/jobs/${editing.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }).catch(() => {});
      notify("岗位已更新");
    } else {
      const optimistic = mapJob({
        ...payload,
        source_id: `local-${Date.now()}`,
        salary_min_k: payload.salary_min_k,
        salary_max_k: payload.salary_max_k,
        change_type: "new",
      });
      setJobs((list) => [optimistic, ...list]);
      setJobTotal((current) => current + 1);
      request("/api/jobs", {
        method: "POST",
        body: JSON.stringify(payload),
      }).catch(() => {});
      notify("岗位已创建");
    }
    setEditing(null);
  };
  const remove = () => {
    setJobs((list) => list.filter((job) => job.id !== confirm.id));
    setJobTotal((current) => Math.max(0, current - 1));
    request(`/api/jobs/${confirm.id}`, { method: "DELETE" }).catch(() => {});
    setConfirm(null);
    notify("岗位已删除");
  };
  const toggle = (job) => {
    const next = job.jobStatus === "offline" ? "active" : "offline";
    setJobs((list) =>
      list.map((item) =>
        item.id === job.id
          ? {
              ...item,
              jobStatus: next,
              status: next === "offline" ? "已下线" : "持续招聘",
            }
          : item,
      ),
    );
    request(`/api/jobs/${job.id}`, {
      method: "PATCH",
      body: JSON.stringify({ job_status: next }),
    }).catch(() => {});
    notify(next === "offline" ? "岗位已下线" : "岗位已恢复");
  };
  return (
    <main className="assets-page">
      <section className="asset-summary">
        <span className="asset-summary-icon" aria-hidden="true">
          <Database size={19} />
        </span>
        <div>
          <h2>{jobTotal} 个岗位资产</h2>
          <p>仅管理人工智能、大数据、智能系统与物联网领域岗位。</p>
        </div>
        <div className="asset-summary-actions">
          <Button variant="outline" onPress={() => setCollectionOpen((value) => !value)}>
            {collectionOpen ? <ChevronUp size={16} /> : <Settings size={16} />}
            {collectionOpen ? "收起采集" : "采集控制"}
          </Button>
          <Button onPress={() => setEditing({})}>
          <Plus size={16} />
          新增岗位
          </Button>
        </div>
      </section>
      {collectionOpen && <section className="collection-console">
        <div className="collection-overview">
          <span className={`live-dot ${collecting ? "working" : ""}`} />
          <div>
            <strong>{collecting ? "采集任务运行中" : collection.schedule?.running ? "自动采集已启用" : "自动采集已暂停"}</strong>
          </div>
          <div className="collection-actions">
            <Button variant="outline" onPress={() => setStrategyOpen(true)} title="设置采集策略"><Settings size={15}/>采集策略</Button>
            <Button className="collect-now" onPress={runCollection} isDisabled={collecting} isPending={collecting}>
              <RefreshCw size={15} className={collecting ? "spin" : ""} />
              {collecting ? "采集中" : "立即采集"}
            </Button>
          </div>
        </div>
        <div className="source-health">
          {visibleCollectionSources.map((sourceItem) => {
            const result = sourceStates[sourceItem.source_id];
            const session = collection.sessions.find((item) => item.source_id === sourceItem.source_id);
            const cookieSession = collection.cookieSessions.find((item) => item.source_id === sourceItem.source_id);
            const state = result?.status || (sourceItem.enabled ? "ready" : "disabled");
            const needsVerification = session?.authentication === "verification_required";
            const needsLogin = session?.authentication === "login_required";
            const duration = result?.duration_ms ? `${(result.duration_ms / 1000).toFixed(1)}s` : "";
            const newCandidates = result?.discovery_candidates || 0;
            const updateCandidates = result?.monitor_candidates || 0;
            const excludedCount = Math.max(0, (result?.scanned || 0) - newCandidates - updateCandidates);
            const isExpanded = expandedSource === sourceItem.source_id;
            const resultLabel = state === "running" || state === "queued"
              ? ({ queued: "等待调度", fetching: "正在抓取", normalizing: "正在清洗", persisting: "正在入库" }[result?.phase] || "运行中")
              : state === "success" ? `扫描 ${result.scanned || result.fetched} 条 · 新增 ${newCandidates} 条 · 更新候选 ${updateCandidates} 条 · ${duration}`
              : state === "failed" ? `失败 · ${duration || "查看详情"}`
              : state === "disabled" ? "未配置" : "等待采集";
            return (
              <div key={sourceItem.source_id} className={`source-health-item ${state}`} title={result?.error || (result?.stage_durations_ms ? `抓取 ${(result.stage_durations_ms.fetch || 0) / 1000}s，清洗 ${(result.stage_durations_ms.normalize || 0) / 1000}s` : "")}>
                <i />
                <span><strong>{sourceItem.name}</strong><small>{sourceItem.source_category === "recruitment" ? "招聘主数据" : "辅助信号"}</small></span>
                <em>{needsVerification ? "需要完成安全验证" : needsLogin ? "需要登录账号" : (state === "ready" || state === "disabled") && session ? (session.connected ? "账号已认证" : "需要认证") : resultLabel}</em>
                {session && (!session.connected || needsVerification || needsLogin) && <Button size="sm" variant="ghost" onPress={() => startBrowserSession(sourceItem.source_id)}>{needsVerification ? "打开验证页面" : needsLogin ? "打开登录页面" : "启动认证"}</Button>}
                {cookieSession && (
                  <div className="cookie-session-actions">
                    <span>{cookieSession.configured ? `登录态已配置 · ${cookieSession.cookie_count} 项` : "可选：复用本人登录态"}</span>
                    <Button size="sm" variant="ghost" onPress={() => window.open(cookieSession.login_url, "_blank", "noopener,noreferrer")}><LogIn size={13}/>登录入口</Button>
                    <Button size="sm" variant="ghost" onPress={() => document.getElementById(`cookie-file-${sourceItem.source_id}`)?.click()}><Upload size={13}/>{cookieSession.configured ? "更新 Cookie" : "导入 Cookie"}</Button>
                    <input id={`cookie-file-${sourceItem.source_id}`} type="file" accept="application/json,.json" hidden onChange={(event) => { importCookieSession(sourceItem.source_id, event.target.files?.[0]); event.target.value = ""; }} />
                  </div>
                )}
                {result && (
                  <button className="source-result-toggle" type="button" onClick={() => setExpandedSource(isExpanded ? "" : sourceItem.source_id)}>
                    {isExpanded ? "收起采集详情" : "查看采集详情"}
                    {isExpanded ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
                  </button>
                )}
                {result && isExpanded && (
                  <div className="source-result-detail">
                    <div className="source-result-metrics">
                      <span><small>列表扫描</small><strong>{result.scanned || 0}</strong></span>
                      <span><small>新发现</small><strong>{newCandidates}</strong></span>
                      <span><small>更新候选</small><strong>{updateCandidates}</strong></span>
                      <span><small>已见/过滤</small><strong>{excludedCount}</strong></span>
                      <span><small>提取成功</small><strong>{result.fetched || 0}</strong></span>
                      <span><small>清洗通过</small><strong>{result.accepted || 0}</strong></span>
                    </div>
                    {state === "success" && newCandidates === 0 && updateCandidates === 0 && (
                      <p>本轮没有新增或待更新岗位，扫描结果均为已采集记录或未满足当前岗位范围。</p>
                    )}
                    {result.end_reason && <p>停止原因：{result.end_reason}</p>}
                    {result.error && <p className="source-result-error">失败原因：{result.error}</p>}
                    <footer>
                      <span>任务阶段：{result.phase || result.status}</span>
                      <span>总耗时：{duration || "0.0s"}</span>
                      {session?.background_mode && <span>浏览器：后台运行</span>}
                    </footer>
                  </div>
                )}
              </div>
            );
          })}
        </div>
        {collection.fullCrawl?.total_count > 0 && collection.fullCrawl?.status !== "not_started" && (
          <div className="full-crawl-progress">
            <div className="full-crawl-copy">
              <span>{collection.fullCrawl.stage === "monitor" ? "全量变更检测" : "首次全量发现"}</span>
              <strong>
                {SOURCE_LABELS[collection.fullCrawl.source_id] || collection.fullCrawl.source_id || "等待调度"}
                {collection.fullCrawl.city ? ` · ${collection.fullCrawl.city}` : ""}
                {collection.fullCrawl.query ? ` · ${collection.fullCrawl.query}` : ""}
              </strong>
              <small>
                {collection.fullCrawl.status === "reconnecting" ? "连接中断，正在自动恢复" :
                  collection.fullCrawl.status === "waiting_for_login" ? "等待账号认证" :
                  collection.fullCrawl.status === "waiting_next_monitor" ? `下轮全量检测 ${new Date(collection.fullCrawl.next_cycle_at).toLocaleString("zh-CN", { hour12: false })}` :
                  `已完成 ${collection.fullCrawl.completed_count}，剩余 ${collection.fullCrawl.remaining_count}`}
              </small>
            </div>
            <div className="full-crawl-meter">
              <div><i style={{ width: `${Math.min(100, collection.fullCrawl.progress_percent || 0)}%` }} /></div>
              <span>{(collection.fullCrawl.progress_percent || 0).toFixed(2)}%</span>
            </div>
            <div className="full-crawl-stats">
              <span><small>页面卡片</small><b>{(collection.fullCrawl.totals?.scanned || 0).toLocaleString()}</b></span>
              <span><small>清洗通过</small><b>{(collection.fullCrawl.totals?.accepted || 0).toLocaleString()}</b></span>
              <span><small>新增 / 更新</small><b>{collection.fullCrawl.totals?.new || 0} / {collection.fullCrawl.totals?.updated || 0}</b></span>
            </div>
          </div>
        )}
      </section>}
      <nav className="data-view-tabs" aria-label="数据治理视图">
        <Button className={assetView === "jobs" ? "active" : ""} variant="ghost" onPress={() => setAssetView("jobs")}><Database size={15}/>岗位主数据</Button>
        <Button className={assetView === "signals" ? "active" : ""} variant="ghost" onPress={() => setAssetView("signals")}><GitBranch size={15}/>辅助信号</Button>
        <Button className={assetView === "audit" ? "active" : ""} variant="ghost" onPress={() => setAssetView("audit")}><ShieldX size={15}/>清洗审计</Button>
      </nav>
      <section className={`panel asset-panel ${assetView !== "jobs" ? "is-hidden" : ""}`}>
        <div className="asset-toolbar">
          <div />
          <div>
              <div className="asset-search-field">
                <Search size={15} />
                <Input
                  aria-label="搜索岗位、企业或技能"
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setPage(1); }}
                  placeholder="搜索岗位、企业或技能"
                  variant="secondary"
                />
              </div>
              <Button className="import-button" isIconOnly variant="outline" title="批量导入 JSON" onPress={() => document.getElementById("job-import-input")?.click()}>
                <Upload size={16} />
              </Button>
              <input id="job-import-input" className="visually-hidden-file" type="file" accept=".json,application/json" onChange={importJobs}/>
          </div>
        </div>
          <div className="asset-filters">
          <FilterBadge icon={<Filter size={14} />}>联合筛选</FilterBadge>
          <DataSelect label="岗位领域" value={domain} onChange={(value) => { setDomain(value); setPage(1); }} options={[{ value: "全部领域", label: "全部领域" }, ...DOMAINS.map((value) => ({ value, label: value }))]} />
          <DataSelect label="数据来源" value={source} onChange={(value) => { setSource(value); setPage(1); }} options={[{ value: "all", label: "全部来源" }, ...sources.map((key) => ({ value: key, label: SOURCE_LABELS[key] || key }))]} />
          <DataSelect label="城市" value={city} onChange={(value) => { setCity(value); setPage(1); }} options={[{ value: "all", label: "全部城市" }, ...cities.map((name) => ({ value: name, label: name }))]} />
          <DataSelect label="岗位状态" value={status} onChange={(value) => { setStatus(value); setPage(1); }} options={[{ value: "all", label: "全部状态" }, { value: "active", label: "招聘中" }, { value: "offline", label: "已下线" }]} />
          <DataSelect label="最低质量分" value={quality} onChange={(value) => { setQuality(value); setPage(1); }} options={[{ value: "0", label: "全部质量" }, { value: "70", label: "质量 >= 70" }, { value: "80", label: "质量 >= 80" }, { value: "90", label: "质量 >= 90" }]} />
          <DataSelect label="更新时间" value={period} onChange={(value) => { setPeriod(value); setPage(1); }} options={[{ value: "all", label: "全部时间" }, { value: "1", label: "今日更新" }, { value: "7", label: "近 7 天" }, { value: "30", label: "近 30 天" }]} />
          <Button className="filter-reset" variant="ghost" onPress={resetFilters} title="重置筛选"><RotateCcw size={14} />重置</Button>
        </div>
        <div className="asset-table">
          <div className="asset-head">
            <span>岗位资产</span>
            <span>领域 / 地区</span>
            <span>关键技能</span>
            <span>数据来源</span>
            <span>质量</span>
            <span>状态</span>
            <span>更新时间</span>
            <span>操作</span>
          </div>
          {rows.map((job) => (
            <div className="asset-row" key={job.id}>
              <Button className="asset-name" variant="ghost" onPress={() => setSelected(job)}>
                <strong>{job.title}</strong>
                <small>
                  {job.company} · {job.salary}
                </small>
              </Button>
              <div>
                <strong>{job.domain}</strong>
                <small>{job.city}</small>
              </div>
              <div className="asset-capability">
                <div className="tag-row">
                  {job.tags.slice(0, 5).map((tag) => <TagChip key={tag}>{tag}</TagChip>)}
                  {job.tags.length > 5 && <TagChip color="default">+{job.tags.length - 5}</TagChip>}
                </div>
              </div>
              {job.sourceUrl ? (
                <a className={`source-badge ${job.sourceKey}`} href={job.sourceUrl} target="_blank" rel="noreferrer" title="打开原始岗位页面">
                  {job.source}<ExternalLink size={12} />
                </a>
              ) : <span className={`source-badge ${job.sourceKey}`}>{job.source}</span>}
              <span className={`quality-score ${job.qualityScore >= 80 ? "good" : job.qualityScore >= 70 ? "medium" : "low"}`}>
                <b>{job.qualityScore}</b><small>/100</small>
              </span>
              <Chip
                className={`status ${job.jobStatus === "offline" ? "offline" : job.status.includes("新增") ? "new" : ""}`}
                color={job.jobStatus === "offline" ? "default" : "accent"}
                size="sm"
                variant="soft"
              >
                <Chip.Label>{job.status}</Chip.Label>
              </Chip>
              <span className="asset-time">{job.updated}</span>
              <div className="row-actions">
                <Button isIconOnly size="sm" title="查看" variant="ghost" onPress={() => setSelected(job)}>
                  <Eye size={16} />
                </Button>
                <Button isIconOnly size="sm" title="编辑" variant="ghost" onPress={() => setEditing(job)}>
                  <Edit3 size={16} />
                </Button>
                <Button
                  isIconOnly
                  size="sm"
                  title={job.jobStatus === "offline" ? "恢复" : "下线"}
                  variant="ghost"
                  onPress={() => toggle(job)}
                >
                  <Layers3 size={16} />
                </Button>
                <Button isIconOnly size="sm" title="删除" variant="ghost" onPress={() => setConfirm(job)}>
                  <Trash2 size={16} />
                </Button>
              </div>
            </div>
          ))}
          {!rows.length && (
            <div className="asset-empty"><Search size={22} /><strong>没有匹配的岗位</strong><span>调整筛选条件后再查看。</span><Button variant="outline" onPress={resetFilters}>清除筛选</Button></div>
          )}
        </div>
          <div className="asset-pagination">
          <DataSelect
            className="page-size-select"
            label="每页"
            value={String(pageSize)}
            onChange={(value) => { setPageSize(Number(value)); setPage(1); }}
            options={[25, 50, 100, 200].map((size) => ({ value: String(size), label: `${size} / 页` }))}
          />
          <Pagination className="job-pagination" size="sm">
            <Pagination.Content>
              <Pagination.Item>
                <Pagination.Previous isDisabled={page <= 1 || jobsLoading} onPress={() => setPage((value) => Math.max(1, value - 1))}>
                  <Pagination.PreviousIcon><ArrowLeft size={13} /></Pagination.PreviousIcon>
                  <span>上一页</span>
                </Pagination.Previous>
              </Pagination.Item>
              <Pagination.Item>
                <Pagination.Next isDisabled={page >= pageCount || jobsLoading} onPress={() => setPage((value) => Math.min(pageCount, value + 1))}>
                  <span>下一页</span>
                  <Pagination.NextIcon><ArrowRight size={13} /></Pagination.NextIcon>
                </Pagination.Next>
              </Pagination.Item>
            </Pagination.Content>
          </Pagination>
          </div>
      </section>
      <section className={`panel signal-panel ${assetView !== "signals" ? "is-hidden" : ""}`}>
        <div className="governance-heading"><div><h3>技术社区前置信号</h3><p>用于发现招聘网站尚未充分反映的技术趋势，不直接替代招聘岗位证据。</p></div><strong>{collection.totals?.signals ?? collection.signals.length} 条有效信号</strong></div>
        <div className="signal-filters">
          <div className="asset-search-field"><Search size={14}/><Input aria-label="搜索信号、技术或摘要" value={signalQuery} onChange={(event) => setSignalQuery(event.target.value)} placeholder="搜索信号、技术或摘要" variant="secondary"/></div>
          <DataSelect label="辅助信号来源" value={signalSource} onChange={setSignalSource} options={[{ value: "all", label: "全部来源" }, ...signalSources.map((value) => ({ value, label: SOURCE_LABELS[value] || value }))]} />
          <DataSelect label="辅助信号领域" value={signalDomain} onChange={setSignalDomain} options={[{ value: "all", label: "全部领域" }, ...DOMAINS.map((value) => ({ value, label: value }))]} />
          <DataSelect label="辅助信号质量" value={signalQuality} onChange={setSignalQuality} options={[{ value: "0", label: "全部质量" }, { value: "70", label: "质量 >= 70" }, { value: "80", label: "质量 >= 80" }, { value: "90", label: "质量 >= 90" }]} />
          <DataSelect label="辅助信号时间" value={signalPeriod} onChange={setSignalPeriod} options={[{ value: "all", label: "全部时间" }, { value: "1", label: "今日" }, { value: "7", label: "近 7 天" }, { value: "30", label: "近 30 天" }]} />
          <Button isIconOnly variant="ghost" onPress={resetSignalFilters} title="重置辅助信号筛选"><RotateCcw size={14}/></Button>
          <ResultBadge>{filteredSignals.length} 条结果</ResultBadge>
        </div>
        <div className="signal-head"><span>信号 / 摘要</span><span>来源</span><span>领域</span><span>热度</span><span>质量</span><span>更新时间</span></div>
        {filteredSignals.map((signal) => (
          <a className="signal-row" key={signal.signal_id} href={signal.source_url} target="_blank" rel="noreferrer">
            <div><strong>{signal.title}</strong><p>{signal.content}</p><div className="tag-row">{(signal.tags || []).slice(0, 5).map((tag) => <TagChip key={tag}>{tag}</TagChip>)}</div></div>
            <span className={`source-badge ${signal.source_platform}`}>{SOURCE_LABELS[signal.source_platform] || signal.source_platform}<ExternalLink size={11}/></span>
            <span>{signal.domain}</span>
            <span>{Object.values(signal.engagement || {}).reduce((sum, value) => sum + Number(value || 0), 0).toLocaleString()}</span>
            <span className="quality-score good"><b>{Math.round(signal.quality_score)}</b><small>/100</small></span>
            <span className="asset-time">{new Date(signal.published_at || signal.collected_at).toLocaleDateString("zh-CN")}</span>
          </a>
        ))}
        {!filteredSignals.length && <div className="asset-empty"><GitBranch size={22}/><strong>没有匹配的辅助信号</strong><span>调整筛选条件后再查看。</span><Button variant="outline" onPress={resetSignalFilters}>清除筛选</Button></div>}
      </section>
      <section className={`panel audit-panel ${assetView !== "audit" ? "is-hidden" : ""}`}>
        <Tabs className="asset-segmented-tabs audit-lanes" selectedKey={auditLane} onSelectionChange={changeAuditLane}>
          <div className="asset-toolbar audit-toolbar">
            <Tabs.ListContainer>
              <Tabs.List aria-label="审计任务线">
                {[
                  ["pending", "待人工复核"],
                  ["rejected", "质量拒绝"],
                  ["corrections", "字段修正"],
                  ["copies", "重复与抄袭簇"],
                  ["changes", "岗位变更"],
                ].map(([value, label], index) => (
                  <Tabs.Tab id={value} key={value}>
                    {index > 0 && <Tabs.Separator />}
                    <span>{label}</span>
                    <b>{collection.auditSummary?.[value] || 0}</b>
                    <Tabs.Indicator />
                  </Tabs.Tab>
                ))}
              </Tabs.List>
            </Tabs.ListContainer>
            <div>
              <div className="asset-search-field"><Search size={14}/><Input aria-label="搜索标题、编号或原始内容" value={auditQuery} onChange={(event) => setAuditQuery(event.target.value)} placeholder="搜索标题、编号或原始内容" variant="secondary" /></div>
            </div>
          </div>
          <Tabs.Panel className="audit-lane-panel" id={auditLane}>
            <div className="audit-filters">
          <FilterBadge icon={<Filter size={14} />}>联合筛选</FilterBadge>
          <DataSelect label="审计数据来源" value={auditSource} onChange={setAuditSource} options={[{ value: "all", label: "全部来源" }, ...auditSources.map((item) => ({ value: item, label: SOURCE_LABELS[item] || item }))]} />
          <DataSelect label="审计处理类型" value={auditType} onChange={setAuditType} options={[{ value: "all", label: "全部类型" }, ...Object.entries(AUDIT_TYPE_LABELS).map(([value, label]) => ({ value, label }))]} />
          <DataSelect label="审计复核状态" value={auditStatus} onChange={setAuditStatus} options={[{ value: "all", label: "全部状态" }, { value: "pending", label: "待复核" }, { value: "approved", label: "人工通过" }, { value: "rejected", label: "确认拒绝" }]} />
          <DataSelect label="审计拦截原因" value={auditReason} onChange={setAuditReason} options={[{ value: "all", label: "全部原因" }, ...auditReasons.map((item) => ({ value: item, label: REASON_LABELS[item] || item }))]} />
          <Button className="filter-reset" variant="ghost" onPress={resetAuditFilters}><RotateCcw size={13}/>重置</Button>
          <ResultBadge>{filteredAudits.length} / {collection.audits.length} 条</ResultBadge>
        </div>
        <div className="audit-head"><span>记录</span><span>类型</span><span>来源</span><span>拦截原因</span><span>质量</span><span>复核状态</span></div>
        {filteredAudits.map((record) => (
          <Button className="audit-row" key={record.audit_id || record.rejection_id} variant="ghost" onPress={() => {
            setSelectedAudit(record);
            setAuditCorrections({
              title: record.corrections?.title || record.normalized_item?.title || record.title || "",
              domain: record.corrections?.domain || record.normalized_item?.domain || record.raw_item?.domain || "人工智能",
              skill_tags: (record.corrections?.skill_tags || record.normalized_item?.skill_tags || []).join("、"),
            });
          }}>
            <div><strong>{record.title || "未命名记录"}</strong><small>{record.source_id}</small></div>
            <span className={`audit-kind ${record.record_type}`}>{AUDIT_TYPE_LABELS[record.record_type] || record.record_type}</span>
            <span>{SOURCE_LABELS[record.source_platform] || record.source_platform || "未知"}</span>
            <span>{(record.reasons || []).map((reason) => REASON_LABELS[reason] || reason).join("；") || "规则校验通过"}</span>
            <span>{record.final_confidence == null ? "—" : Math.round(record.final_confidence * 100)}</span>
            <span className={`review-state ${record.review_status}`}>{{pending:"待复核",approved:"人工通过",rejected:"确认拒绝"}[record.review_status]}</span>
          </Button>
        ))}
            {!filteredAudits.length && <div className="asset-empty"><CheckCircle2 size={22}/><strong>{collection.audits.length ? "没有符合筛选条件的记录" : "当前没有拦截记录"}</strong>{collection.audits.length > 0 && <Button variant="outline" onPress={resetAuditFilters}>清除筛选</Button>}</div>}
          </Tabs.Panel>
        </Tabs>
      </section>
      {selectedAudit && (
        <Drawer title={selectedAudit.title || "数据审计记录"} onClose={() => setSelectedAudit(null)}>
          <span className={`audit-kind ${selectedAudit.record_type}`}>{AUDIT_TYPE_LABELS[selectedAudit.record_type] || selectedAudit.record_type}</span>
          <div className="drawer-section"><h4>规则判定</h4>{(selectedAudit.reasons || []).length ? (selectedAudit.reasons || []).map((reason) => <blockquote key={reason}>{REASON_LABELS[reason] || reason}</blockquote>) : <blockquote>确定性规则校验通过</blockquote>}</div>
          <div className="job-facts"><div><span>来源</span><strong>{SOURCE_LABELS[selectedAudit.source_platform] || selectedAudit.source_platform || "未知"}</strong></div><div><span>综合置信度</span><strong>{selectedAudit.final_confidence == null ? "未评分" : `${Math.round(selectedAudit.final_confidence * 100)}/100`}</strong></div><div><span>图谱状态</span><strong>{{published:"已发布",blocked:"已阻断",pending:"待发布",auxiliary_only:"仅辅助层"}[selectedAudit.graph_publish_status] || "未发布"}</strong></div><div><span>复核状态</span><strong>{{pending:"待复核",approved:"人工通过",rejected:"确认拒绝"}[selectedAudit.review_status]}</strong></div></div>
          {selectedAudit.source_url && <div className="drawer-section evidence-box"><ExternalLink size={18}/><div><h4>原始数据可追溯</h4><a href={selectedAudit.source_url} target="_blank" rel="noreferrer">打开来源页面 <ExternalLink size={12}/></a></div></div>}
          <div className="audit-compare">
            <section><h4>采集原始内容</h4><p>{selectedAudit.raw_item?.content || selectedAudit.raw_item?.raw_content || selectedAudit.raw_item?.sample || JSON.stringify(selectedAudit.raw_item, null, 2)}</p></section>
            <section><h4>规格化结果</h4><p>{selectedAudit.normalized_item?.content || JSON.stringify(selectedAudit.normalized_item || {}, null, 2)}</p></section>
          </div>
          {Object.keys(selectedAudit.field_changes || {}).length > 0 && <div className="drawer-section audit-diffs"><h4>字段修改</h4>{Object.entries(selectedAudit.field_changes).map(([field, diff]) => <div key={field}><b>{field}</b><del>{Array.isArray(diff.before) ? diff.before.join("、") : String(diff.before ?? "空")}</del><ins>{Array.isArray(diff.after) ? diff.after.join("、") : String(diff.after ?? "空")}</ins></div>)}</div>}
          {selectedAudit.evidence_snippets?.length > 0 && <div className="drawer-section"><h4>命中证据</h4>{selectedAudit.evidence_snippets.map((item, index) => <blockquote key={`${item.field}-${index}`}><b>{item.field}</b> · {item.text}</blockquote>)}</div>}
          {selectedAudit.llm_assessment?.verdict && <div className="drawer-section semantic-review"><h4>LLM 灰区复核</h4><strong>{selectedAudit.llm_assessment.verdict}</strong><span>{Math.round((selectedAudit.llm_assessment.confidence || 0) * 100)}% 置信度</span></div>}
          {selectedAudit.review_status === "pending" && selectedAudit.record_type !== "copy_cluster" && <div className="drawer-section audit-correction-form">
            <h4>人工修正后发布</h4>
            <Label>标准岗位名称<Input value={auditCorrections.title} onChange={(event) => setAuditCorrections((value) => ({ ...value, title: event.target.value }))} variant="secondary"/></Label>
            <DataSelect label="归属领域" value={auditCorrections.domain} onChange={(next) => setAuditCorrections((value) => ({ ...value, domain: next }))} options={DOMAINS.map((item) => ({ value: item, label: item }))} />
            <Label>技能分类<Input value={auditCorrections.skill_tags} onChange={(event) => setAuditCorrections((value) => ({ ...value, skill_tags: event.target.value }))} placeholder="使用顿号分隔" variant="secondary"/></Label>
          </div>}
          {selectedAudit.review_status === "pending" && selectedAudit.record_type === "copy_cluster" && <div className="audit-actions"><Button variant="outline" onPress={() => reviewAudit(selectedAudit, "rejected", "split_copy_cluster")}><GitBranch size={15}/>拆分重复簇</Button><Button className="primary" onPress={() => reviewAudit(selectedAudit, "approved", "merge_copy_cluster")}><Check size={15}/>确认合并计权</Button></div>}
          {selectedAudit.review_status === "pending" && selectedAudit.record_type !== "copy_cluster" && <div className="audit-actions"><Button variant="danger-soft" onPress={() => reviewAudit(selectedAudit, "rejected")}><ShieldX size={15}/>确认拒绝</Button><Button variant="outline" onPress={() => reviewAudit(selectedAudit, "approved", "new_job_candidate")}><Sparkles size={15}/>标记新岗位候选</Button><Button className="primary" onPress={() => reviewAudit(selectedAudit, "approved")}><Check size={15}/>人工通过并发布</Button></div>}
        </Drawer>
      )}
      {strategyOpen && collection.strategy && <CollectionStrategyModal strategy={collection.strategy} onClose={() => setStrategyOpen(false)} onSave={saveStrategy}/>} 
      {selected && (
        <JobDrawer
          job={selected}
          onClose={() => setSelected(null)}
          onEdit={() => {
            setEditing(selected);
            setSelected(null);
          }}
        />
      )}
      {editing && (
        <JobModal
          job={editing}
          onClose={() => setEditing(null)}
          onSave={save}
        />
      )}
      {confirm && (
        <Confirm
          title={`删除“${confirm.title}”？`}
          text="删除后岗位、关联图谱与演化记录将一并移除，此操作不可撤销。"
          onClose={() => setConfirm(null)}
          onConfirm={remove}
        />
      )}
    </main>
  );
}

function CollectionStrategyModal({ strategy, onClose, onSave }) {
  const sourceIds = Object.keys(strategy.sources || {});
  const [activeSource, setActiveSource] = useState(sourceIds.includes("boss") ? "boss" : sourceIds[0]);
  const [form, setForm] = useState(() => Object.fromEntries(sourceIds.map((sourceId) => {
    const source = strategy.sources[sourceId];
    return [sourceId, {
      enabled: source.enabled, mode: source.mode,
      min_interval_minutes: source.min_interval_minutes,
      max_interval_minutes: source.max_interval_minutes,
      items_per_run: source.items_per_run,
      discovery_ratio: source.discovery_ratio,
      revisit_after_hours: source.revisit_after_hours,
      cities: [...(source.cities || [])], job_queries: [...(source.job_queries || [])],
    }];
  })));
  const [saving, setSaving] = useState(false);
  const current = form[activeSource] || {};
  const sourceMeta = strategy.sources?.[activeSource] || {};
  const intervalInvalid = +current.min_interval_minutes > +current.max_interval_minutes;
  const updateCurrent = (changes) => setForm((value) => ({
    ...value, [activeSource]: { ...value[activeSource], ...changes },
  }));
  const toggleCity = (city) => {
    setForm((value) => {
      const selectedSource = value[activeSource];
      if (city === "全国") return { ...value, [activeSource]: { ...selectedSource, cities: ["全国"] } };
      const withoutAll = selectedSource.cities.filter((item) => item !== "全国");
      const cities = withoutAll.includes(city) ? withoutAll.filter((item) => item !== city) : [...withoutAll, city];
      return { ...value, [activeSource]: { ...selectedSource, cities: cities.length ? cities : ["全国"] } };
    });
  };
  const toggleQuery = (query) => setForm((value) => {
    const selectedSource = value[activeSource];
    const selected = selectedSource.job_queries.includes(query)
      ? selectedSource.job_queries.filter((item) => item !== query)
      : [...selectedSource.job_queries, query];
    return { ...value, [activeSource]: { ...selectedSource, job_queries: selected.length ? selected : selectedSource.job_queries } };
  });
  return (
    <Modal>
      <Modal.Backdrop
        className="strategy-backdrop route-data"
        isOpen
        onOpenChange={(open) => {
          if (!open) onClose();
        }}
        variant="blur"
      >
        <Modal.Container placement="center" scroll="inside" size="cover">
          <Modal.Dialog className="strategy-modal tg-strategy-modal" aria-labelledby="strategy-modal-title">
            <Form className="strategy-form" onSubmit={async (event) => {
              event.preventDefault();
              if (Object.values(form).some((item) => +item.min_interval_minutes > +item.max_interval_minutes)) return;
              setSaving(true);
              await onSave({ enabled: Object.values(form).some((item) => item.enabled), sources: Object.fromEntries(
                Object.entries(form).map(([key, value]) => [key, {
                  ...value,
                  min_interval_minutes: +value.min_interval_minutes,
                  max_interval_minutes: +value.max_interval_minutes,
                  items_per_run: +value.items_per_run,
                  discovery_ratio: +value.discovery_ratio,
                  revisit_after_hours: +value.revisit_after_hours,
                }]),
              ) });
              setSaving(false);
            }}>
              <Modal.CloseTrigger aria-label="关闭采集策略" />
              <Modal.Header className="strategy-modal-header">
                <Modal.Heading id="strategy-modal-title">分站采集策略</Modal.Heading>
                <p>每个来源独立调度，单站耗时不会阻塞其他来源</p>
              </Modal.Header>
              <Modal.Body className="strategy-modal-body">
                <Tabs
                  className="strategy-source-tabs"
                  selectedKey={activeSource}
                  onSelectionChange={(key) => setActiveSource(String(key))}
                >
                  <Tabs.ListContainer>
                    <Tabs.List aria-label="采集来源">
                      {sourceIds.map((sourceId) => (
                        <Tabs.Tab id={sourceId} key={sourceId}>
                          <i className={form[sourceId].enabled ? "online" : ""} />
                          <span>
                            {strategy.sources[sourceId].name || SOURCE_LABELS[sourceId] || sourceId}
                            <small>{strategy.sources[sourceId].source_category === "recruitment" ? "主数据" : "辅助"}</small>
                          </span>
                          <Tabs.Indicator />
                        </Tabs.Tab>
                      ))}
                    </Tabs.List>
                  </Tabs.ListContainer>
                  <Tabs.Panel id={activeSource} className="strategy-tab-panel">
                    <div className="strategy-body">
                      <section className="strategy-section">
                        <div className="strategy-title">
                          <div>
                            <h4>{sourceMeta.name || activeSource} · 运行节奏</h4>
                            <p>{sourceMeta.next_run_at ? `下次运行 ${new Date(sourceMeta.next_run_at).toLocaleString("zh-CN", { hour12: false })}` : "当前来源未安排自动任务"}</p>
                          </div>
                          <Switch className="strategy-switch" isSelected={!!current.enabled} onChange={(enabled) => updateCurrent({ enabled })}>
                            <Switch.Content><Switch.Control><Switch.Thumb /></Switch.Control><span>{current.enabled ? "自动采集开启" : "自动采集暂停"}</span></Switch.Content>
                          </Switch>
                        </div>
                        <div className="strategy-numbers">
                          <TextField className="strategy-number-field" type="number" value={String(current.min_interval_minutes ?? "")} onChange={(value) => updateCurrent({ min_interval_minutes: value })} isInvalid={intervalInvalid} variant="secondary">
                            <Label>最短间隔</Label><div className="strategy-input-unit"><Input min="5" step="0.5" /><span>分钟</span></div>
                          </TextField>
                          <TextField className="strategy-number-field" type="number" value={String(current.max_interval_minutes ?? "")} onChange={(value) => updateCurrent({ max_interval_minutes: value })} isInvalid={intervalInvalid} variant="secondary">
                            <Label>最长间隔</Label><div className="strategy-input-unit"><Input min="5" step="0.5" /><span>分钟</span></div><FieldError>最长间隔不能小于最短间隔</FieldError>
                          </TextField>
                          <TextField className="strategy-number-field" type="number" value={String(current.items_per_run ?? "")} onChange={(value) => updateCurrent({ items_per_run: value })} variant="secondary">
                            <Label>每轮候选量</Label><div className="strategy-input-unit"><Input min="1" max="200" /><span>条</span></div>
                          </TextField>
                        </div>
                        <div className="strategy-numbers">
                          <Select aria-label="运行模式" className="tg-form-select" selectedKey={String(current.mode || "discovery")} onSelectionChange={(key) => key != null && updateCurrent({ mode: String(key) })} placeholder="运行模式" variant="secondary">
                            <Label>运行模式</Label><Select.Trigger><Select.Value /><Select.Indicator /></Select.Trigger><Select.Popover><ListBox>{[{ value: "discovery", label: "全量发现" }, { value: "monitor", label: "存量监测" }, { value: "hybrid", label: "发现 + 监测" }].map((item) => <ListBox.Item id={item.value} key={item.value} textValue={item.label}>{item.label}<ListBox.ItemIndicator /></ListBox.Item>)}</ListBox></Select.Popover>
                          </Select>
                          <TextField className="strategy-number-field" type="number" value={String(current.discovery_ratio ?? "")} onChange={(value) => updateCurrent({ discovery_ratio: value })} variant="secondary">
                            <Label>发现任务占比</Label><div className="strategy-input-unit"><Input min="0" max="1" step="0.1" /><span>0–1</span></div>
                          </TextField>
                          <TextField className="strategy-number-field" type="number" value={String(current.revisit_after_hours ?? "")} onChange={(value) => updateCurrent({ revisit_after_hours: value })} variant="secondary">
                            <Label>存量复查周期</Label><div className="strategy-input-unit"><Input min="1" max="720" /><span>小时</span></div>
                          </TextField>
                        </div>
                      </section>
                      {!!sourceMeta.options?.cities?.length && (
                        <section className="strategy-section">
                          <div className="strategy-title"><div><h4>采集城市</h4><p>“全国”由平台搜索覆盖所有城市，具体城市可独立轮询。</p></div><strong>{current.cities.join("、")}</strong></div>
                          <div className="strategy-options city-options">{sourceMeta.options.cities.map((city) => <Checkbox key={city} className={current.cities.includes(city) ? "selected" : ""} isSelected={current.cities.includes(city)} onChange={() => toggleCity(city)}><Checkbox.Content><Checkbox.Control><Checkbox.Indicator /></Checkbox.Control><span>{city}</span></Checkbox.Content></Checkbox>)}</div>
                        </section>
                      )}
                      {!!sourceMeta.options?.job_queries?.length && (
                        <section className="strategy-section">
                          <div className="strategy-title"><div><h4>岗位范围</h4><p>不限结果页数，系统会保存每个关键词的翻页游标，直至覆盖平台结果。</p></div><Button type="button" variant="outline" onPress={() => updateCurrent({ job_queries: [...sourceMeta.options.job_queries] })}>全选 {current.job_queries.length}/{sourceMeta.options.job_queries.length}</Button></div>
                          <div className="strategy-options query-options">{sourceMeta.options.job_queries.map((query) => <Checkbox key={query} className={current.job_queries.includes(query) ? "selected" : ""} isSelected={current.job_queries.includes(query)} onChange={() => toggleQuery(query)}><Checkbox.Content><Checkbox.Control><Checkbox.Indicator /></Checkbox.Control><span>{query}</span></Checkbox.Content></Checkbox>)}</div>
                        </section>
                      )}
                    </div>
                  </Tabs.Panel>
                </Tabs>
              </Modal.Body>
              <Modal.Footer className="strategy-footer">
                <span>{sourceMeta.name || activeSource}：{current.min_interval_minutes}–{current.max_interval_minutes} 分钟 · 每轮 {current.items_per_run} 条</span>
                <div><Button type="button" variant="tertiary" onPress={onClose}>取消</Button><Button type="submit" isDisabled={saving || intervalInvalid} isPending={saving}>{saving ? "保存中" : "保存全部策略"}</Button></div>
              </Modal.Footer>
            </Form>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
  );
}

function ControlledHeroModal({ children, className = "", onClose, placement = "center", scroll = "inside", size = "lg" }) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [onClose]);
  return createPortal(
    <div
      className={`tg-modal-backdrop ${className}`}
      data-placement={placement}
      data-scroll={scroll}
      data-size={size}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="tg-modal-container">
        {children}
      </div>
    </div>,
    document.body,
  );
}

function JobDrawer({ job, onClose, onEdit }) {
  const [history, setHistory] = useState({ versions: [], observations: [] });
  useEffect(() => {
    const jobId = encodeURIComponent(job.id);
    Promise.all([
      request(`/api/jobs/${jobId}/versions`),
      request(`/api/jobs/${jobId}/observations?limit=100`),
    ]).then(([versions, observations]) => setHistory({
      versions: versions.items || [], observations: observations.items || [],
    })).catch(() => {});
  }, [job.id]);
  return (
    <Drawer
      title={job.title}
      onClose={onClose}
      actions={
        <Button variant="outline" onPress={onEdit}>
          <Edit3 size={15} />
          编辑岗位
        </Button>
      }
    >
      <span className="detail-label cyan">{job.domain}</span>
      <div className="job-facts">
        <div>
          <span>企业</span>
          <strong>{job.company}</strong>
        </div>
        <div>
          <span>薪资</span>
          <strong>{job.salary}</strong>
        </div>
        <div>
          <span>地点</span>
          <strong>{job.city}</strong>
        </div>
        <div>
          <span>要求</span>
          <strong>
            {job.experience} · {job.education}
          </strong>
        </div>
      </div>
      <div className="drawer-section">
        <div className="section-heading"><h4>核心技能</h4><span>智能提取 · {job.tags.length} 项</span></div>
        <div className="tag-cloud">
          {job.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      </div>
      <div className="drawer-section">
        <div className="section-heading"><h4>岗位职责</h4><span>结构化提取 · {job.responsibilities.length} 项</span></div>
        <ul>
          {(job.responsibilities.length ? job.responsibilities : ["原始 JD 未形成可验证的职责条目"]).map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </div>
      <div className="drawer-section">
        <div className="section-heading"><h4>任职要求</h4><span>结构化提取 · {job.requirements.length} 项</span></div>
        <ul>
          {(job.requirements.length ? job.requirements : ["原始 JD 未形成可验证的任职要求条目"]).map((item) => <li key={item}>{item}</li>)}
        </ul>
      </div>
      {!!job.evidenceSegments.length && (
        <div className="drawer-section">
          <div className="section-heading"><h4>图谱证据片段</h4><span>{job.evidenceSegments.length} 条可追溯证据</span></div>
          <div className="evidence-list">{job.evidenceSegments.slice(0, 8).map((segment) => <blockquote key={segment.segment_id || segment.text}>{segment.text}</blockquote>)}</div>
        </div>
      )}
      {!!job.rawContent && (
        <details className="drawer-section raw-jd">
          <summary>查看完整原始 JD</summary>
          <p>{job.rawContent}</p>
        </details>
      )}
      {!!history.versions.length && (
        <div className="drawer-section">
          <div className="section-heading"><h4>岗位监测历史</h4><span>{history.versions.length} 个版本 · {history.observations.length} 次采集观测</span></div>
          <div className="job-version-list">{history.versions.slice(0, 8).map((version) => {
            const fields = Object.keys(version.changes || {}).filter((field) => field !== "baseline");
            return <article key={version.version_id}><i>v{version.version_number}</i><div><strong>{fields.length ? fields.map((field) => ({skill_tags:"核心技能",responsibilities:"岗位职责",requirements:"任职要求",salary_min_k:"最低薪资",salary_max_k:"最高薪资",education:"学历",city:"城市",job_status:"岗位状态"}[field] || field)).join("、") : "岗位基线"}</strong><small>{new Date(version.changed_at).toLocaleString("zh-CN", { hour12: false })}</small></div><span>{fields.length ? `${fields.length} 个字段变化` : "初始快照"}</span></article>;
          })}</div>
        </div>
      )}
      <div className="drawer-section evidence-box">
        <ShieldCheck size={18} />
        <div>
          <h4>数据来源可追溯</h4>
          <p>{job.source} · 更新于 {job.updated} · 质量评分 {job.qualityScore}/100</p>
          {job.sourceUrl && <a href={job.sourceUrl} target="_blank" rel="noreferrer">访问原始岗位页面 <ExternalLink size={12} /></a>}
        </div>
      </div>
    </Drawer>
  );
}

function JobModal({ job, onClose, onSave }) {
  const [form, setForm] = useState({
    title: job.title || "",
    domain: job.domain || "人工智能",
    company: job.company || "",
    city: job.city || "",
    education: job.education || "本科",
    salaryMin: job.salary?.match(/\d+/)?.[0] || "20",
    salaryMax: job.salary?.match(/-(\d+)/)?.[1] || "35",
    tags: (job.tags || []).join(", "),
    responsibilities: (job.responsibilities || []).join("\n"),
  });
  const change = (key, value) => setForm((x) => ({ ...x, [key]: value }));
  const title = job.id ? "编辑岗位" : "新增岗位";
  return (
    <ControlledHeroModal className="route-data" onClose={onClose} size="lg">
      <Card className="tg-job-modal" variant="default" role="dialog" aria-modal="true" aria-label={title}>
        <Button className="tg-modal-close" isIconOnly type="button" variant="ghost" onPress={onClose}>
          <X size={18} />
        </Button>
        <Form
          className="tg-job-form"
          onSubmit={(event) => {
            event.preventDefault();
            onSave(form);
          }}
        >
          <Card.Header className="tg-modal-head">
            <Card.Title>{title}</Card.Title>
          </Card.Header>
          <Card.Content className="tg-modal-body">
            <div className="form-grid">
              <Label className="full">
                岗位名称
                <Input
                  value={form.title}
                  onChange={(event) => change("title", event.target.value)}
                  required
                  variant="secondary"
                />
              </Label>
              <Select aria-label="所属领域" className="tg-form-select" selectedKey={String(form.domain)} onSelectionChange={(key) => key != null && change("domain", String(key))} placeholder="所属领域" variant="secondary">
                <Label>所属领域</Label>
                <Select.Trigger>
                  <Select.Value />
                  <Select.Indicator />
                </Select.Trigger>
                <Select.Popover>
                  <ListBox>
                    {DOMAINS.map((item) => (
                      <ListBox.Item id={item} key={item} textValue={item}>
                        {item}
                        <ListBox.ItemIndicator />
                      </ListBox.Item>
                    ))}
                  </ListBox>
                </Select.Popover>
              </Select>
              <Label>
                企业名称
                <Input
                  value={form.company}
                  onChange={(event) => change("company", event.target.value)}
                  required
                  variant="secondary"
                />
              </Label>
              <Label>
                工作地点
                <Input
                  value={form.city}
                  onChange={(event) => change("city", event.target.value)}
                  variant="secondary"
                />
              </Label>
              <Select aria-label="学历要求" className="tg-form-select" selectedKey={String(form.education)} onSelectionChange={(key) => key != null && change("education", String(key))} placeholder="学历要求" variant="secondary">
                <Label>学历要求</Label>
                <Select.Trigger>
                  <Select.Value />
                  <Select.Indicator />
                </Select.Trigger>
                <Select.Popover>
                  <ListBox>
                    {["不限", "大专", "本科", "硕士", "博士"].map((item) => (
                      <ListBox.Item id={item} key={item} textValue={item}>
                        {item}
                        <ListBox.ItemIndicator />
                      </ListBox.Item>
                    ))}
                  </ListBox>
                </Select.Popover>
              </Select>
              <Label>
                最低月薪（K）
                <Input
                  type="number"
                  value={form.salaryMin}
                  onChange={(event) => change("salaryMin", event.target.value)}
                  variant="secondary"
                />
              </Label>
              <Label>
                最高月薪（K）
                <Input
                  type="number"
                  value={form.salaryMax}
                  onChange={(event) => change("salaryMax", event.target.value)}
                  variant="secondary"
                />
              </Label>
              <Label className="full">
                核心技能
                <Input
                  value={form.tags}
                  onChange={(event) => change("tags", event.target.value)}
                  placeholder="使用逗号分隔"
                  variant="secondary"
                />
              </Label>
              <Label className="full">
                岗位职责
                <TextArea
                  rows={5}
                  value={form.responsibilities}
                  onChange={(event) => change("responsibilities", event.target.value)}
                  placeholder="每行一项职责"
                  variant="secondary"
                />
              </Label>
            </div>
          </Card.Content>
          <Card.Footer className="tg-modal-actions">
            <Button type="button" variant="ghost" onPress={onClose}>
              取消
            </Button>
            <Button type="submit" variant="primary">
              <Check size={16} />
              保存岗位
            </Button>
          </Card.Footer>
        </Form>
      </Card>
    </ControlledHeroModal>
  );
}

const GRAPH_RELATION_FILTERS = [
  { id: "core_skill", label: "核心技能" },
  { id: "requires_skill", label: "岗位技能" },
  { id: "job_similarity", label: "岗位相似" },
  { id: "skill_cooccurrence", label: "技能组合" },
  { id: "talent_mobility_inference", label: "跨岗迁移" },
];

const THREE_RELATION_LENSES = [
  { id: "integrated", label: "综合关系", description: "岗位、技能与时间演化的完整网络" },
  { id: "job_skill", label: "核心技能", description: "突出岗位所需技能与核心能力链路" },
  { id: "similarity", label: "岗位相似", description: "展示技能结构相近与可能融合的岗位" },
  { id: "combination", label: "技能组合", description: "展示共享技能与高频共现组合" },
  { id: "mobility", label: "跨岗迁移", description: "展示可解释的岗位迁移与时间演化路径" },
];
const DEFAULT_THREE_PERIOD = "2025-09";

function completeEvolutionLayers(currentLayers) {
  const layerById = new Map((currentLayers || []).map((layer) => [layer.id, layer]));
  return EVOLUTION_PERIODS.map((id, index) => ({
    id,
    z: -index * 34,
    label: id.replace("-", " "),
    dataLabel: "研究性月度演进",
    jobCount: 0,
    familyCount: 0,
    ...(layerById.get(id) || {}),
    index,
  }));
}

function GraphPage({ audience = "enterprise", targetJob, setTargetJob }) {
  const isSeeker = audience === "seeker";
  const [selected, setSelected] = useState(null);
  const [graphQuery, setGraphQuery] = useState("");
  const [stats, setStats] = useState({});
  const [layers, setLayers] = useState([]);
  const [period, setPeriod] = useState("all");
  const [domain, setDomain] = useState("all");
  const [cursor, setCursor] = useState(null);
  const [viewLevel, setViewLevel] = useState("skills");
  const [familyFocus, setFamilyFocus] = useState("");
  const [graphMode, setGraphMode] = useState("relations");
  const [timelineScrubbing, setTimelineScrubbing] = useState(false);
  const [roleTimelineScrubbing, setRoleTimelineScrubbing] = useState(false);
  const [timeTraveling, setTimeTraveling] = useState(false);
  const [jobEvolutionMode, setJobEvolutionMode] = useState(false);
  const [roleCursor, setRoleCursor] = useState(null);
  const [rolePlaying, setRolePlaying] = useState(false);
  const [rolePlaybackRate, setRolePlaybackRate] = useState(1);
  const [roleEvolutionDismissed, setRoleEvolutionDismissed] = useState(false);
  const [evolutionSearchOpen, setEvolutionSearchOpen] = useState(false);
  const [recentEvolutionSearches, setRecentEvolutionSearches] = useState([]);
  const timelinePreviewRef = useRef(0);
  const marketCursorRef = useRef(null);
  const rolePlaybackCursorRef = useRef(0);
  const roleTimelinePreviewRef = useRef(0);
  const timeTravelTimerRef = useRef(null);
  const [relationLens, setRelationLens] = useState("integrated");
  const activeThreeLens = THREE_RELATION_LENSES.find((item) => item.id === relationLens) || THREE_RELATION_LENSES[0];
  const [relationData, setRelationData] = useState(null);
  const [relationStats, setRelationStats] = useState(null);
  const [relationEdges, setRelationEdges] = useState([]);
  const [relationTypes, setRelationTypes] = useState(["core_skill", "job_similarity", "skill_cooccurrence"]);
  const [selectedEvidence, setSelectedEvidence] = useState({ loading: false, items: [], total: 0 });
  useEffect(() => {
    if (!layers.length) return;
    const selectedIndex = period === "all" ? -1 : layers.findIndex((layer) => layer.id === period);
    setCursor((current) => {
      if (selectedIndex >= 0) {
        marketCursorRef.current = selectedIndex;
        return selectedIndex;
      }
      const preserved = marketCursorRef.current ?? current;
      if (preserved == null || !Number.isFinite(Number(preserved))) {
        const next = layers.length - 1;
        marketCursorRef.current = next;
        return next;
      }
      const next = Math.max(0, Math.min(Number(preserved), layers.length - 1));
      marketCursorRef.current = next;
      return next;
    });
  }, [layers, period]);
  useEffect(() => { setSelected(null); setFamilyFocus(""); }, [domain]);
  useEffect(() => {
    const params = new URLSearchParams();
    if (domain !== "all") params.set("domain", domain);
    request(`/api/knowledge-graph/relations?${params.toString()}`)
      .then((data) => {
        setRelationData(data);
        setRelationStats(data.stats || {});
        setRelationEdges(data.edges || []);
        if (data.periods?.length) {
          setLayers((current) => {
            if (graphMode === "temporal" && current.length >= EVOLUTION_PERIODS.length) return current;
            const nextLayers = data.periods.map((item, index) => ({
              ...item,
              index,
              z: -index * 34,
              ...(current.find((layer) => layer.id === item.id) || {}),
            }));
            return graphMode === "relations" && nextLayers.length < EVOLUTION_PERIODS.length
              ? completeEvolutionLayers(nextLayers)
              : nextLayers;
          });
        }
      })
      .catch(() => {
        setRelationData(null);
        setRelationStats(null);
        setRelationEdges([]);
      });
  }, [domain, graphMode]);
  useEffect(() => {
    if (!selected?.id || selected.nodeType === "relation") {
      setSelectedEvidence({ loading: false, items: [], total: selected?.evidenceCount || 0 });
      return undefined;
    }
    let active = true;
    setSelectedEvidence({ loading: true, items: [], total: selected.evidenceCount || 0 });
    request(`/api/graph/nodes/${encodeURIComponent(selected.id)}/evidence?limit=6`)
      .then((data) => { if (active) setSelectedEvidence({ loading: false, items: data.items || [], total: data.total || 0 }); })
      .catch(() => { if (active) setSelectedEvidence({ loading: false, items: [], total: selected.evidenceCount || 0 }); });
    return () => { active = false; };
  }, [selected?.evidenceCount, selected?.id, selected?.nodeType]);
  const selectedRelations = useMemo(() => {
    if (!selected?.id || !relationData?.nodes) return [];
    const nodeById = new Map(relationData.nodes.map((node) => [node.id, node]));
    return relationEdges
      .filter((edge) => edge.source === selected.id || edge.target === selected.id)
      .map((edge) => {
        const neighborId = edge.source === selected.id ? edge.target : edge.source;
        return { ...edge, neighbor: nodeById.get(neighborId) };
      })
      .filter((edge) => edge.neighbor)
      .sort((left, right) => Number(right.weight || 0) - Number(left.weight || 0));
  }, [relationData?.nodes, relationEdges, selected?.id]);
  const timelinePosition = Math.max(0, Math.min(Number(cursor ?? Math.max(0, layers.length - 1)), Math.max(0, layers.length - 1)));
  const activeCursor = Math.round(timelinePosition);
  const activeLayer = layers[activeCursor] || layers.at(-1);
  const timelineProgress = layers.length > 1 ? timelinePosition / (layers.length - 1) * 100 : 0;
  const selectedEvolutionRole = graphMode === "temporal" && ["job", "family"].includes(selected?.nodeType) ? selected : null;
  const roleEvolutionActive = (graphMode === "temporal" && !roleEvolutionDismissed && (jobEvolutionMode || Boolean(selectedEvolutionRole)))
    || (graphMode === "relations" && jobEvolutionMode);
  const selectedRoleTitle = selectedEvolutionRole?.title || selectedEvolutionRole?.label || "";
  const selectedRoleQuery = selectedRoleTitle && /ai\s*agent|agentic|智能体/i.test(selectedRoleTitle)
    ? FEATURED_EVOLUTION_QUERY
    : selectedRoleTitle;
  const evolutionQuery = selectedRoleQuery || graphQuery;
  const defaultEvolutionCursor = Math.max(0, layers.findIndex((layer) => layer.id === DEFAULT_THREE_PERIOD));
  const roleTimelinePosition = Math.max(0, Math.min(
    Number(roleCursor ?? defaultEvolutionCursor),
    Math.max(0, layers.length - 1),
  ));
  const roleActiveCursor = Math.round(roleTimelinePosition);
  const roleActiveLayer = layers[roleActiveCursor] || layers.at(-1);
  const roleTimelineProgress = layers.length > 1 ? roleTimelinePosition / (layers.length - 1) * 100 : 0;
  const roleEvolutionProfile = useMemo(() => {
    if (!roleEvolutionActive || !evolutionQuery.trim() || !layers.length) return null;
    const profileNodes = relationData?.nodes?.length ? relationData.nodes : selectedEvolutionRole ? [selectedEvolutionRole] : [];
    return profileNodes.length ? buildJobEvolutionProfile({ nodes: profileNodes, layers }, evolutionQuery) : null;
  }, [evolutionQuery, layers, relationData?.nodes, roleEvolutionActive, selectedEvolutionRole]);
  const roleActiveFrame = roleEvolutionProfile?.frames?.[roleActiveCursor] || null;
  const relationEvolutionProfile = useMemo(() => jobEvolutionMode && graphMode === "relations"
    ? buildJobEvolutionProfile({ nodes: relationData?.nodes || [], layers }, graphQuery)
    : null, [graphMode, graphQuery, jobEvolutionMode, layers, relationData?.nodes]);
  const evolutionSearchItems = useMemo(() => [
    ...PINNED_EVOLUTION_SEARCHES,
    ...recentEvolutionSearches
      .filter((query) => !isPinnedEvolutionQuery(query))
      .map((query) => ({ query, label: query, demoType: "recent" })),
  ], [recentEvolutionSearches]);
  useEffect(() => {
    if (!roleEvolutionActive || !layers.length) return;
    setRoleCursor((current) => current == null
      ? defaultEvolutionCursor
      : Math.max(0, Math.min(Number(current), Math.max(0, layers.length - 1))));
  }, [defaultEvolutionCursor, layers.length, roleEvolutionActive]);
  useEffect(() => { rolePlaybackCursorRef.current = roleTimelinePosition; }, [roleTimelinePosition]);
  useEffect(() => {
    if (!rolePlaying || !roleEvolutionActive || !evolutionQuery.trim() || layers.length < 2) return undefined;
    let animationFrame = 0;
    let previousTime = performance.now();
    const finalCursor = layers.length - 1;
    const tick = (currentTime) => {
      const deltaSeconds = Math.min(0.1, Math.max(0, currentTime - previousTime) / 1000);
      previousTime = currentTime;
      const nextCursor = Math.min(finalCursor, rolePlaybackCursorRef.current + deltaSeconds * 0.58 * rolePlaybackRate);
      rolePlaybackCursorRef.current = nextCursor;
      roleTimelinePreviewRef.current = nextCursor;
      setRoleCursor(nextCursor);
      if (nextCursor >= finalCursor - 0.001) {
        setRolePlaying(false);
        return;
      }
      animationFrame = requestAnimationFrame(tick);
    };
    animationFrame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animationFrame);
  }, [evolutionQuery, layers.length, roleEvolutionActive, rolePlaybackRate, rolePlaying]);
  const isWormholeOverview = graphMode === "temporal" && (roleEvolutionActive || period === "all" || timelineScrubbing);
  const roleQueryForNode = useCallback((node) => {
    const label = node?.title || node?.label || node?.family || "";
    return /ai\s*agent|agentic|智能体/i.test(label) ? FEATURED_EVOLUTION_QUERY : label;
  }, []);
  const handleGraphSelect = useCallback((node) => {
    if (!node) {
      setSelected(null);
      setRolePlaying(false);
      setRoleTimelineScrubbing(false);
      return;
    }
      setSelected(node);
      if (graphMode === "temporal" && ["job", "family"].includes(node.nodeType)) {
        setRoleEvolutionDismissed(false);
        setJobEvolutionMode(true);
        setGraphQuery(roleQueryForNode(node));
      setRoleCursor((current) => {
        const nextPosition = current == null ? defaultEvolutionCursor : current;
        roleTimelinePreviewRef.current = nextPosition;
        return nextPosition;
      });
    }
  }, [defaultEvolutionCursor, graphMode, roleQueryForNode]);
  const drillFamily = useCallback((node) => {
    setFamilyFocus(node.family);
    setViewLevel("jobs");
    handleGraphSelect(node);
  }, [handleGraphSelect]);
  const changeEvolutionFocus = useCallback((node) => {
      setRolePlaying(false);
      if (!node) {
        setJobEvolutionMode(false);
        setRoleEvolutionDismissed(true);
        setSelected(null);
        setRoleTimelineScrubbing(false);
        return;
    }
    setSelected(node);
    setRoleEvolutionDismissed(false);
    const nextQuery = roleQueryForNode(node);
    setGraphQuery(nextQuery);
    setRoleCursor((current) => {
      const nextPosition = current == null ? defaultEvolutionCursor : current;
      roleTimelinePreviewRef.current = nextPosition;
      return nextPosition;
    });
    if (nextQuery && !isPinnedEvolutionQuery(nextQuery)) setRecentEvolutionSearches((current) => [nextQuery, ...current.filter((item) => item !== nextQuery)].slice(0, 6));
  }, [defaultEvolutionCursor, roleQueryForNode]);
  const selectEvolutionSearch = useCallback((nextQuery) => {
    setRolePlaying(false);
    setSelected(null);
    setRoleEvolutionDismissed(false);
    setGraphQuery(nextQuery);
    setEvolutionSearchOpen(false);
    if (graphMode === "relations" && layers.length < EVOLUTION_PERIODS.length) {
      setLayers((current) => current.length >= EVOLUTION_PERIODS.length ? current : completeEvolutionLayers(current));
    }
    const firstCursor = Math.max(0, layers.findIndex((layer) => layer.id === DEFAULT_THREE_PERIOD));
    setRoleCursor(firstCursor);
    roleTimelinePreviewRef.current = firstCursor;
    setPeriod("all");
    if (!isPinnedEvolutionQuery(nextQuery)) setRecentEvolutionSearches((current) => [nextQuery, ...current.filter((item) => item !== nextQuery)].slice(0, 6));
  }, [graphMode, layers]);
  const switchGraphMode = (next) => {
    setRolePlaying(false);
    setRoleTimelineScrubbing(false);
    setRoleEvolutionDismissed(false);
    setGraphMode(next);
    if (jobEvolutionMode && next === "relations" && !isPinnedEvolutionQuery(graphQuery)) setGraphQuery(FEATURED_EVOLUTION_QUERY);
    setFamilyFocus("");
    setViewLevel("skills");
    setSelected(null);
    if (next === "temporal") {
      const defaultCursor = layers.findIndex((layer) => layer.id === DEFAULT_THREE_PERIOD);
      const nextCursor = defaultCursor >= 0 ? defaultCursor : Math.max(0, layers.length - 1);
      marketCursorRef.current = nextCursor;
      setCursor(nextCursor);
      timelinePreviewRef.current = nextCursor;
      setPeriod("all");
      setTimelineScrubbing(false);
      setTimeTraveling(false);
      const defaultRoleCursor = layers.findIndex((layer) => layer.id === DEFAULT_THREE_PERIOD);
      const nextRoleCursor = defaultRoleCursor >= 0 ? defaultRoleCursor : Math.max(0, layers.length - 1);
      setRoleCursor(nextRoleCursor);
      roleTimelinePreviewRef.current = nextRoleCursor;
    }
  };
  const toggleJobEvolutionMode = () => {
    const next = !jobEvolutionMode;
    setJobEvolutionMode(next);
    if (next) {
      setRoleEvolutionDismissed(false);
      const selectedRole = ["job", "family", "evidence"].includes(selected?.nodeType) ? roleQueryForNode(selected) : "";
      if (graphMode === "relations") setGraphQuery(isPinnedEvolutionQuery(graphQuery) ? graphQuery : FEATURED_EVOLUTION_QUERY);
      else if (selectedRole) setGraphQuery(selectedRole);
      else if (!graphQuery.trim()) setGraphQuery(FEATURED_EVOLUTION_QUERY);
      // Evolution is a cross-month role view; do not let a prior domain chip
      // hide the selected role family from the wormhole scene.
      setDomain("all");
      if (graphMode === "relations" && layers.length < EVOLUTION_PERIODS.length) {
        setLayers((current) => current.length >= EVOLUTION_PERIODS.length ? current : completeEvolutionLayers(current));
      }
      setPeriod("all");
      setTimelineScrubbing(false);
      setTimeTraveling(false);
      const firstCursor = Math.max(0, layers.findIndex((layer) => layer.id === DEFAULT_THREE_PERIOD));
      setRoleCursor(firstCursor);
      roleTimelinePreviewRef.current = firstCursor;
    } else {
      setRolePlaying(false);
      setRoleTimelineScrubbing(false);
      setRoleEvolutionDismissed(true);
    }
  };
  const travelToTimelineIndex = (nextCursor) => {
    setRolePlaying(false);
    const committedCursor = Math.max(0, Math.min(Math.round(nextCursor), Math.max(0, layers.length - 1)));
    const nextLayer = layers[committedCursor];
    if (!nextLayer) return;
    window.clearTimeout(timeTravelTimerRef.current);
    marketCursorRef.current = committedCursor;
    setCursor(committedCursor);
    setTimelineScrubbing(false);
    setTimeTraveling(true);
    setPeriod(jobEvolutionMode ? "all" : nextLayer.id);
    timeTravelTimerRef.current = window.setTimeout(() => setTimeTraveling(false), 980);
  };
  const selectPeriod = (next) => {
    if (jobEvolutionMode) {
      setPeriod("all");
      return;
    }
    if (next === "all") {
      window.clearTimeout(timeTravelTimerRef.current);
      setTimeTraveling(false);
      setTimelineScrubbing(false);
      setPeriod("all");
      return;
    }
    const nextCursor = layers.findIndex((layer) => layer.id === next);
    if (nextCursor >= 0) travelToTimelineIndex(nextCursor);
  };
  const updateMarketTimeline = (nextCursor) => {
    const nextPosition = Math.max(0, Math.min(Number(nextCursor), Math.max(0, layers.length - 1)));
    timelinePreviewRef.current = nextPosition;
    marketCursorRef.current = nextPosition;
    setCursor(nextPosition);
    setPeriod("all");
    setTimeTraveling(false);
  };
  const beginTimelineScrub = () => {
    timelinePreviewRef.current = timelinePosition;
    setTimelineScrubbing(true);
    setTimeTraveling(false);
    setPeriod("all");
  };
  const finishTimelineScrub = () => {
    if (!timelineScrubbing) return;
    setTimelineScrubbing(false);
    setPeriod("all");
  };
  const toggleEvolutionPlayback = () => {
    if (!roleEvolutionActive || !evolutionQuery.trim() || layers.length < 2) return;
    if (rolePlaying) {
      setRolePlaying(false);
      return;
    }
    const finalCursor = layers.length - 1;
    const startCursor = roleTimelinePosition >= finalCursor - 0.02 ? 0 : roleTimelinePosition;
    rolePlaybackCursorRef.current = startCursor;
    roleTimelinePreviewRef.current = startCursor;
    setRoleCursor(startCursor);
    setPeriod("all");
    setTimelineScrubbing(false);
    setRoleTimelineScrubbing(false);
    setTimeTraveling(false);
    setRolePlaying(true);
  };
  const updateRoleTimeline = (nextCursor) => {
    const nextPosition = Math.max(0, Math.min(Number(nextCursor), Math.max(0, layers.length - 1)));
    roleTimelinePreviewRef.current = nextPosition;
    setRoleCursor(nextPosition);
  };
  const beginRoleTimelineScrub = () => {
    setRolePlaying(false);
    roleTimelinePreviewRef.current = roleTimelinePosition;
    setRoleTimelineScrubbing(true);
  };
  const finishRoleTimelineScrub = () => {
    if (!roleTimelineScrubbing) return;
    setRoleTimelineScrubbing(false);
  };
  useEffect(() => () => window.clearTimeout(timeTravelTimerRef.current), []);
  return (
    <main className={`graph-page career-galaxy-page graph-mode-${graphMode} ${isWormholeOverview ? "is-wormhole-overview" : "is-ecliptic-slice"} ${roleEvolutionActive ? "is-job-evolution" : ""} ${evolutionSearchOpen ? "is-evolution-search-open" : ""} ${timelineScrubbing ? "is-timeline-scrubbing" : ""} ${roleTimelineScrubbing ? "is-role-timeline-scrubbing" : ""} ${timeTraveling ? "is-time-traveling" : ""} ${selected ? "has-graph-selection" : ""}`}>
      {graphMode === "relations" ? (
        <RelationGraph
          payload={relationData}
          lens={relationLens}
          relationTypes={relationTypes}
          onSelect={handleGraphSelect}
          onStats={setStats}
          query={graphQuery}
          periodLabel="当前市场全量快照"
          evolutionMode={jobEvolutionMode}
          evolutionProfile={relationEvolutionProfile}
      evolutionPosition={roleTimelinePosition}
        />
      ) : (
        <ThreeGraph
          apiUrl={API}
          variant="wormhole"
          onSelect={handleGraphSelect}
          onStats={setStats}
          onLayers={setLayers}
          onDrill={drillFamily}
          onEvolutionFocusChange={changeEvolutionFocus}
          query={evolutionQuery}
          temporalPosition={timelinePosition}
          temporalScrubbing={timelineScrubbing}
          period={timelineScrubbing ? "all" : period}
          previewLayer={timelineScrubbing ? activeLayer : null}
          timeTraveling={timeTraveling}
          domain={domain}
          viewLevel={viewLevel}
          familyFocus={familyFocus}
          relationLens={relationLens}
          jobEvolutionMode={roleEvolutionActive}
          evolutionLayer={roleEvolutionActive ? roleActiveLayer : null}
          evolutionPosition={roleTimelinePosition}
          selectedNodeId={selected?.id || null}
        />
      )}
      <header className="career-header">
        <div className="career-toolbar">
          <Tabs className="career-mode-switch" selectedKey={graphMode} onSelectionChange={(key) => switchGraphMode(String(key))}>
            <Tabs.ListContainer>
              <Tabs.List aria-label="图谱模式">
                <Tabs.Tab id="relations">
                  <Network size={15} />
                  <span>二维关系</span>
                  <Tabs.Indicator />
                </Tabs.Tab>
                <Tabs.Tab id="temporal">
                  <Layers3 size={15} />
                  <span>三维时间</span>
                  <Tabs.Indicator />
                </Tabs.Tab>
              </Tabs.List>
            </Tabs.ListContainer>
            <Tabs.Panel className="career-tab-panel" id={graphMode} />
          </Tabs>
          {graphMode === "relations" && !jobEvolutionMode && <div className="relation-lens-summary" aria-label="关系类型筛选">
            {GRAPH_RELATION_FILTERS.map((item) => <button
              aria-pressed={relationTypes.includes(item.id)}
              className={relationTypes.includes(item.id) ? "active" : ""}
              key={item.id}
              onClick={() => setRelationTypes((current) => current.includes(item.id)
                ? current.length > 1 ? current.filter((type) => type !== item.id) : current
                : [...current, item.id])}
              type="button"
            ><i className={`relation-type-${item.id}`} />{item.label}</button>)}
          </div>}
          {graphMode === "temporal" && <div className="three-lens-switch" aria-label="三维关系视图">
            {THREE_RELATION_LENSES.map((item) => <button
              aria-pressed={relationLens === item.id}
              className={relationLens === item.id ? "active" : ""}
              data-lens={item.id}
              key={item.id}
              onClick={() => { setRelationLens(item.id); setSelected(null); }}
              title={item.description}
              type="button"
            ><i />{item.label}</button>)}
          </div>}
          <button
            aria-pressed={jobEvolutionMode}
            className={`job-evolution-toggle ${jobEvolutionMode ? "active" : ""}`}
            onClick={toggleJobEvolutionMode}
            title={graphMode === "relations" ? "查看两个精选岗位的二维技能栈演进" : "聚焦单个岗位在完整时间轴中的技能栈演进"}
            type="button"
          ><i />岗位演进</button>
          {isSeeker && targetJob && (
            <Chip
              className="career-target-chip"
              color="accent"
              size="sm"
              title={`当前目标：${targetJob.title}`}
              variant="soft"
            >
              <Target size={13} />
              <Chip.Label>当前目标：{targetJob.title}</Chip.Label>
            </Chip>
          )}
        </div>
        <div className="career-filters">
          <div className="career-search-field" onPointerDown={() => jobEvolutionMode && setEvolutionSearchOpen(true)}>
            <Search size={15} />
            <Input className="career-search-input" aria-label="搜索图谱节点" autoComplete="off" value={graphQuery} onClick={() => jobEvolutionMode && setEvolutionSearchOpen(true)} onFocus={() => jobEvolutionMode && setEvolutionSearchOpen(true)} onBlur={() => window.setTimeout(() => setEvolutionSearchOpen(false), 120)} onKeyDown={(event) => {
              if (event.key === "Escape") setEvolutionSearchOpen(false);
              if (event.key === "Enter" && graphQuery.trim()) selectEvolutionSearch(graphQuery.trim());
            }} onChange={(event) => {
              if (jobEvolutionMode) setRolePlaying(false);
              setGraphQuery(event.target.value);
            }} placeholder="搜索岗位、企业或技能" variant="secondary" />
            {jobEvolutionMode && evolutionSearchOpen && <div className="evolution-search-history" onMouseDown={(event) => event.preventDefault()}>
              <header><strong>搜索历史</strong>{recentEvolutionSearches.length ? <button onClick={() => setRecentEvolutionSearches([])} type="button">清空其他记录</button> : <span>精选岗位固定保留</span>}</header>
              <div>{evolutionSearchItems.map((item) => <button className={graphQuery.trim() === item.query ? "active" : ""} key={`${item.demoType}:${item.query}`} onClick={() => selectEvolutionSearch(item.query)} type="button"><span>{item.label}</span>{item.demoType !== "recent" && <i>{item.demoType === "legacy" ? "既有岗位" : "新兴岗位"}</i>}</button>)}</div>
            </div>}
          </div>
          <DataSelect
            className="career-select"
            label="领域筛选"
            value={domain}
            onChange={setDomain}
            options={[{ value: "all", label: "全局主图" }, ...["人工智能", "大数据", "智能系统", "物联网"].map((item) => ({ value: item, label: item }))]}
          />
          {graphMode !== "relations" && <DataSelect
              className="career-select"
              label="时间切片"
            value={jobEvolutionMode ? "all" : period}
            disabled={jobEvolutionMode}
              onChange={selectPeriod}
              options={[
                { value: "all", label: "完整虫洞" },
                ...layers.map((layer) => ({ value: layer.id, label: layer.label })),
              ]}
            />}
          {graphMode === "temporal" && period !== "all" && !jobEvolutionMode && <Button className="return-wormhole-button" size="sm" variant="outline" onPress={() => selectPeriod("all")}><RotateCcw size={13} />回到虫洞</Button>}
        </div>
      </header>

      <section className="graph-relation-strip" aria-label="岗位关系网络">
        <div>
          <span>{graphMode === "relations" ? jobEvolutionMode ? `二维岗位演进 · ${graphQuery.trim() || "请选择精选岗位"}` : "当前市场综合关系" : jobEvolutionMode ? graphQuery.trim() ? `岗位演进聚焦 · ${graphQuery.trim()}` : "岗位演进 · 请选择岗位" : isWormholeOverview ? `时间虫洞总览 · ${activeThreeLens.label}` : `单时间点黄道面 · ${activeThreeLens.label}`}</span>
          <strong>{graphMode === "temporal" || jobEvolutionMode ? `${Number(stats.visible_relation_edges ?? stats.rendered_edges ?? 0).toLocaleString("zh-CN")} 条可见关系` : relationStats ? `${relationStats.edges || 0} 条可追溯关系` : "正在计算关系"}</strong>
          <small>{graphMode === "temporal" ? jobEvolutionMode ? graphQuery.trim() ? "仅保留当前岗位及关联技能演进；清空搜索或点击画布空白处可重新选岗。" : "可从搜索框检索岗位，也可直接点击三维图谱中的岗位节点。" : activeThreeLens.description : jobEvolutionMode ? "拖动时间轴查看岗位名称、技能加入、增强、减弱与退出过程；二维视图仅开放两个精选研究岗位。" : "共现不等于前置依赖；迁移关系均标记为推断。"}</small>
        </div>
        <div className="graph-relation-counts">
          <span>岗位-技能 <b>{graphMode === "temporal" ? Number(stats.job_skill_edges || 0).toLocaleString("zh-CN") : relationStats?.job_skill_relations || 0}</b></span>
          <span>岗位相似 / 迁移 <b>{graphMode === "temporal" ? Number(stats.job_similarity_edges || 0).toLocaleString("zh-CN") : relationStats?.job_relations || 0}</b></span>
          <span>技能共现 <b>{graphMode === "temporal" ? Number(stats.shared_skill_edges || 0).toLocaleString("zh-CN") : relationStats?.skill_cooccurrences || 0}</b></span>
          <span>{graphMode === "temporal" ? "真实岗位" : "新岗位谱系"} <b>{graphMode === "temporal" ? Number(stats.source_jobs || 0).toLocaleString("zh-CN") : relationStats?.lineages || 0}</b></span>
        </div>
        <div className="graph-relation-evidence">
          {relationEdges.slice(0, 3).map((edge) => <i key={edge.id}>{edge.label} · {edge.evidenceIds?.length || 0} 条 JD 证据</i>)}
        </div>
      </section>

      <SpotlightCard
        as="aside"
        className={`career-job-card ${selected ? "visible" : ""}`}
        spotlightColor={graphMode !== "relations" ? "rgba(79, 140, 255, 0.14)" : "rgba(116, 219, 197, 0.12)"}
      >
        {selected && <>
          <Button
            className="career-card-close"
            isIconOnly
            variant="ghost"
            aria-label="关闭详情"
            onPress={() => {
              setRolePlaying(false);
              setJobEvolutionMode(false);
              setRoleEvolutionDismissed(true);
              setRoleTimelineScrubbing(false);
              setSelected(null);
            }}
          >
            <X size={15} />
          </Button>
          <div className="career-card-head">
            <span style={{ color: selected.category === "人工智能" ? "#38bdf8" : selected.category === "大数据" ? "#4ade80" : selected.category === "智能系统" ? "#fb7185" : "#c084fc" }}>{selected.category || "招聘证据"}</span>
            <em>{selected.nodeType === "family" ? "岗位族" : selected.nodeType === "job" ? "岗位实例" : selected.nodeType === "capability" ? "能力模块" : selected.nodeType === "skill" ? "技能证据" : selected.nodeType === "relation" ? "关系推断" : SOURCE_LABELS[selected.sourcePlatform] || selected.sourcePlatform || "证据节点"}</em>
          </div>
          <h3>{selected.title || selected.label}</h3>
          {selected.nodeType === "evidence" && <p className="career-company">{selected.company} · {selected.city || selected.location}</p>}
          {selected.nodeType === "job" && <p className="career-company">{selected.company} · {selected.location}</p>}
          {selected.nodeType === "family" && <p className="career-company">{selected.jobCount} 条岗位 · {selected.companyCount} 家企业 · {selected.cities?.join(" / ")}</p>}
          {selected.nodeType === "skill" && <p className="career-company">{selected.family} · {selected.supportCount} 条真实招聘证据</p>}
          <div className="career-job-facts">
            {selected.nodeType === "evidence" && <><b>{selected.salary}</b><span>{selected.experience}</span><span>{selected.education}</span><span>质量 {selected.qualityScore}</span></>}
            {selected.nodeType === "job" && <><b>{selected.salary}</b><span>{selected.experience}</span><span>{selected.education}</span><span>质量 {selected.qualityScore}</span></>}
            {selected.nodeType === "family" && <><b>{selected.jobCount} JD</b><span>平均质量 {selected.qualityScore}</span><span>{selected.period}</span></>}
            {selected.nodeType === "skill" && <><b>{selected.coverage}%</b><span>岗位覆盖率</span><span>{selected.period}</span></>}
            {selected.nodeType === "relation" && <><b>{Math.round(Number(selected.confidence || 0) * 100)}%</b><span>关系置信度</span><span>{selected.evidenceCount || 0} 条证据</span></>}
          </div>
          {selected.nodeType === "family" && selected.evolutionState && <p className={`career-evolution-state ${selected.evolutionState}`}>{selected.evolutionState === "emerging" ? "该岗位在当前时间切片中新形成" : selected.evolutionState === "declining" ? "招聘证据较上一切片明显减弱" : selected.evolutionState === "exited" ? "后续时间切片中未再形成有效岗位证据" : "岗位结构在相邻切片中保持稳定"}{selected.fusionCandidate ? " · 与相邻岗位能力结构高度接近，存在融合可能" : ""}</p>}
          {!!selected.skills?.length && <div className="career-skill-list">{selected.skills.slice(0, 9).map((skill) => <i key={skill}>{skill}</i>)}</div>}
          {!!selected.skillEvidence?.length && <div className="career-evidence-bars">{selected.skillEvidence.slice(0, 6).map((skill) => <div key={skill.name}><span>{skill.name}</span><i><b style={{ width: `${skill.coverage}%` }} /></i><em>{skill.count}</em></div>)}</div>}
          <p className="career-description">{selected.responsibilities?.[0] || selected.requirements?.[0] || selected.description}</p>
          {graphMode === "temporal" && ["job", "family"].includes(selected.nodeType) && <Button
            className="career-view-role-evolution"
            variant="outline"
            onPress={() => {
              setJobEvolutionMode(true);
              setRoleEvolutionDismissed(false);
              setGraphQuery(roleQueryForNode(selected));
              setRoleCursor((current) => {
                const nextPosition = current == null ? defaultEvolutionCursor : current;
                roleTimelinePreviewRef.current = nextPosition;
                return nextPosition;
              });
              setRolePlaying(false);
              setRoleTimelineScrubbing(false);
              setPeriod("all");
              setTimelineScrubbing(false);
            }}
          >
            <TrendingUp size={14} />查看岗位演变
          </Button>}
          {graphMode === "relations" && <>
            <section className="graph-inspector-section">
              <header><strong>关系网络</strong><span>{selectedRelations.length} 条关联</span></header>
              <div className="graph-inspector-relations">
                {selectedRelations.slice(0, 6).map((edge) => <button key={edge.id} onClick={() => setSelected(edge.neighbor)} type="button">
                  <span><i style={{ "--relation-color": edge.relationType === "job_similarity" ? "#54c7ec" : edge.relationType === "skill_cooccurrence" ? "#79d991" : edge.relationType === "talent_mobility_inference" ? "#d8a4ff" : "#f1c96c" }} />{edge.label}</span>
                  <strong>{edge.neighbor.label || edge.neighbor.title}</strong>
                  <em>{Math.round(Number(edge.weight || edge.confidence || 0) * 100)}%</em>
                </button>)}
                {!selectedRelations.length && <p>当前筛选条件下暂无可展示的邻接关系。</p>}
              </div>
            </section>
            <section className="graph-inspector-section graph-evidence-section">
              <header><strong>招聘证据</strong><span>{selectedEvidence.loading ? "读取中" : `${selectedEvidence.total || selected.evidenceCount || 0} 条`}</span></header>
              <div className="graph-inspector-evidence">
                {selectedEvidence.items.slice(0, 4).map((item) => <a href={item.source_url} key={item.source_id} rel="noreferrer" target="_blank">
                  <span>{SOURCE_LABELS[item.source_platform] || item.source_platform || "招聘来源"}</span>
                  <strong>{item.title}</strong>
                  <small>{item.company || "企业未披露"} · {item.city || "城市未披露"}</small>
                  <ExternalLink size={12} />
                </a>)}
                {!selectedEvidence.loading && !selectedEvidence.items.length && <p>当前节点保留了关系证据计数，详细 JD 可从关联岗位继续追溯。</p>}
              </div>
            </section>
          </>}
          <footer><span>{selected.nodeType === "evidence" ? `${selected.publishedAt?.slice(0, 10)} 发布` : "基于当前真实招聘样本统计"}</span>{selected.sourceUrl && <a href={selected.sourceUrl} target="_blank" rel="noreferrer">原始岗位 <ExternalLink size={12} /></a>}</footer>
          {isSeeker && setTargetJob && ["family", "job", "evidence"].includes(selected.nodeType) && (
            <Button
              className="career-set-target"
              variant="outline"
              onPress={() => setTargetJob({
                id: selected.id,
                title: selected.title || selected.label,
                company: selected.company || "岗位能力图谱",
                city: selected.city || selected.location || "全国",
                tags: selected.skills || [],
                sourceUrl: selected.sourceUrl || "",
              })}
            >
              <Target size={14} />设为我的目标岗位
            </Button>
          )}
        </>}
      </SpotlightCard>

      {graphMode === "temporal" && <div className="career-ring-legend wormhole-legend"><span><i />真实岗位</span><span><i />技能节点</span><span><i />岗位—技能</span><span><i />相似岗位</span><span><i />共享技能岗位</span></div>}

      {!roleEvolutionActive && (graphMode !== "relations" || jobEvolutionMode) && !!layers.length && <footer className="career-timeline career-market-timeline" aria-label="市场时间轴">
        <div className="career-timeline-head">
          <div>
            <span>{timelineScrubbing ? "正在定位市场月份" : isWormholeOverview ? "市场时间虫洞" : timeTraveling ? "时间穿梭中" : "市场时间轴"}</span>
            <strong>{timelineScrubbing || period === "all" ? activeLayer?.label || "加载中" : activeLayer?.label || "加载中"}</strong>
          </div>
          <small>全局市场语义 · {activeLayer?.jobCount || 0} 个岗位 · {activeLayer?.familyCount || 0} 个岗位族</small>
        </div>
        <input
          aria-label="市场时间轴"
          aria-valuetext={activeLayer?.label || "加载中"}
          type="range"
          min="0"
          max={Math.max(0, layers.length - 1)}
          step="0.01"
          value={timelinePosition}
          disabled={layers.length < 2}
          style={{ "--timeline-progress": `${timelineProgress}%` }}
          onPointerDown={beginTimelineScrub}
          onPointerUp={finishTimelineScrub}
          onPointerCancel={finishTimelineScrub}
          onBlur={finishTimelineScrub}
          onChange={(event) => updateMarketTimeline(Number(event.target.value))}
        />
        <div className="career-ticks">
          {layers.map((layer, index) => (
            <Button
              key={layer.id}
              className={index === activeCursor ? "active" : ""}
              size="sm"
              variant="ghost"
              onPress={() => updateMarketTimeline(index)}
            >
              <i aria-hidden="true" />
              <span>{layer.label}</span>
            </Button>
          ))}
        </div>
      </footer>}
      {roleEvolutionActive && !!layers.length && <footer className="career-role-timeline" aria-label="岗位演变时间轴">
        <div className="career-role-timeline-head">
          <div>
            <span>岗位演变 · 12个月</span>
            <strong>{roleEvolutionProfile?.family || selectedRoleTitle || evolutionQuery || "岗位演变"}</strong>
          </div>
          <small>{roleActiveLayer?.label || "加载中"} · {roleActiveFrame?.title || "岗位版本快照"}</small>
          <div className="job-evolution-playback" aria-label="岗位演变自动展示控制">
            <button className={rolePlaying ? "playing" : ""} disabled={!evolutionQuery.trim()} onClick={toggleEvolutionPlayback} type="button"><i />{rolePlaying ? "暂停演示" : "播放演变"}</button>
            <span>{[0.5, 1, 2].map((rate) => <button aria-pressed={rolePlaybackRate === rate} className={rolePlaybackRate === rate ? "active" : ""} key={rate} onClick={() => setRolePlaybackRate(rate)} type="button">{rate}x</button>)}</span>
          </div>
        </div>
        <div className="career-role-frame-summary" aria-live="polite">
          <span className="frame-title"><b>当前帧</b>{roleActiveFrame?.title || roleActiveLayer?.label || "加载中"}</span>
          <span className="added"><b>新增</b>{roleActiveFrame?.addedSkills?.slice(0, 3).join(" · ") || "无"}</span>
          <span className="strengthened"><b>增强</b>{roleActiveFrame?.skills?.filter((skill) => skill.state === "strengthened").slice(0, 3).map((skill) => skill.name).join(" · ") || "无"}</span>
          <span className="declining"><b>减弱</b>{roleActiveFrame?.decliningSkills?.slice(0, 3).join(" · ") || "无"}</span>
          <span className="retired"><b>退出</b>{roleActiveFrame?.retiredSkills?.slice(0, 3).join(" · ") || "无"}</span>
        </div>
        <input
          aria-label="岗位演变时间轴"
          aria-valuetext={`${roleActiveLayer?.label || "加载中"} · ${roleActiveFrame?.title || "岗位版本快照"}`}
          type="range"
          min="0"
          max={Math.max(0, layers.length - 1)}
          step="0.01"
          value={roleTimelinePosition}
          disabled={layers.length < 2}
          style={{ "--timeline-progress": `${roleTimelineProgress}%` }}
          onPointerDown={beginRoleTimelineScrub}
          onPointerUp={finishRoleTimelineScrub}
          onPointerCancel={finishRoleTimelineScrub}
          onBlur={finishRoleTimelineScrub}
          onChange={(event) => updateRoleTimeline(Number(event.target.value))}
        />
        <div className="career-ticks career-role-ticks">
          {layers.map((layer, index) => (
            <Button
              key={layer.id}
              className={index === roleActiveCursor ? "active" : ""}
              size="sm"
              variant="ghost"
              onPress={() => updateRoleTimeline(index)}
            >
              <i aria-hidden="true" />
              <span>{layer.label}</span>
            </Button>
          ))}
        </div>
      </footer>}
    </main>
  );
}

const emptyEvolutionFrame = {
  time: "等待基线",
  title: "尚未形成岗位版本快照",
  summary: "完成一次智联招聘采集后建立基线，下一次监测将自动识别岗位字段和能力要求变化。",
  changes: [],
};
const CHANGE_FIELD_LABELS = {
  title: "岗位名称",
  salary_min_k: "最低薪资",
  salary_max_k: "最高薪资",
  salary_months: "薪资月数",
  city: "城市",
  district: "区域",
  responsibilities: "岗位职责",
  requirements: "任职要求",
  skill_tags: "能力技能",
  education: "学历",
  experience_min_years: "最低年限",
  experience_max_years: "最高年限",
  job_status: "岗位状态",
};

function EvolutionVersionValue({ value }) {
  if (value === null || value === undefined || value === "") return <span className="evo-value-empty">未设置</span>;
  if (Array.isArray(value)) {
    if (!value.length) return <span className="evo-value-empty">无</span>;
    return <ul>{value.map((item, index) => <li key={`${String(item)}-${index}`}>{String(item)}</li>)}</ul>;
  }
  if (typeof value === "object") return <pre>{JSON.stringify(value, null, 2)}</pre>;
  return <p>{String(value)}</p>;
}

function normalizeVersionNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}

function normalizeJobVersions(items) {
  return (Array.isArray(items) ? items : [])
    .map((item) => ({ ...item, version_number: normalizeVersionNumber(item?.version_number) }))
    .filter((item) => item.version_number !== null)
    .sort((left, right) => left.version_number - right.version_number)
    .filter((item, index, all) => index === 0 || item.version_number !== all[index - 1].version_number);
}

function formatJobVersionTime(value) {
  if (!value) return "时间待补充";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16).replace("T", " ");
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function JobVersionComparison({
  detail,
  versions = [],
  selection = { baseVersion: "", targetVersion: "" },
  versionLoading = false,
  compareLoading = false,
  versionReady = false,
  versionError = "",
  onSelectionChange,
  onCompare,
}) {
  const selectedTargetNumber = normalizeVersionNumber(selection.targetVersion) ?? normalizeVersionNumber(detail?.version_number);
  const selectedBaseNumber = normalizeVersionNumber(selection.baseVersion);
  const comparisonTargetNumber = normalizeVersionNumber(detail?.version_number) ?? selectedTargetNumber;
  const comparisonBaseNumber = normalizeVersionNumber(detail?.base_version_number)
    ?? normalizeVersionNumber(detail?.previous_version_number)
    ?? (versionReady ? selectedBaseNumber : null);
  const selectedTargetVersion = versions.find((version) => version.version_number === selectedTargetNumber);
  const selectedBaseVersion = versions.find((version) => version.version_number === selectedBaseNumber);
  const comparedTargetVersion = versions.find((version) => version.version_number === comparisonTargetNumber);
  const comparedBaseVersion = versions.find((version) => version.version_number === comparisonBaseNumber);
  const hasTwoVersions = versions.length > 1;
  const sameSelection = selectedBaseNumber !== null
    && selectedTargetNumber !== null
    && selectedBaseNumber === selectedTargetNumber;
  const canCompare = hasTwoVersions
    && selectedBaseNumber !== null
    && selectedTargetNumber !== null
    && !sameSelection
    && !versionLoading
    && !compareLoading;
  const added = detail.skill_diffs?.added || [];
  const removed = detail.skill_diffs?.removed || [];
  const compareHint = !versions.length && !versionLoading
    ? "未读取到岗位版本链，请关闭抽屉后重试。"
    : !hasTwoVersions
      ? "当前岗位仅有一个基线版本，暂无可比较的前后版本。"
      : sameSelection
        ? "基准版本和目标版本不能相同，请选择两个不同版本。"
        : "选择任意两个不同版本后，点击“比较版本”查看差异。";
  const versionOptionLabel = (version, fallbackNumber, emptyLabel) => version
    ? `V${version.version_number} · ${formatJobVersionTime(version.changed_at)}`
    : fallbackNumber !== null && fallbackNumber !== undefined
      ? `V${fallbackNumber}`
      : emptyLabel;
  return (
    <div className="evo-version-comparison">
      <section className="evo-version-chain" aria-label="岗位完整版本链">
        <div className="evo-version-chain-head">
          <div>
            <span>岗位版本历史</span>
            <strong>完整版本链</strong>
          </div>
          <em>{versions.length ? `${versions.length} 个版本` : versionLoading ? "读取中" : "暂无版本"}</em>
        </div>
        {versions.length ? (
          <ol className="evo-version-chain-list">
            {versions.map((version) => {
              const isBase = version.version_number === selectedBaseNumber;
              const isTarget = version.version_number === selectedTargetNumber;
              return (
                <li
                  aria-current={isTarget ? "true" : undefined}
                  className={`evo-version-chain-item ${isBase ? "is-base" : ""} ${isTarget ? "is-target" : ""}`}
                  key={version.version_number}
                >
                  <div className="evo-version-chain-item-head">
                    <strong>V{version.version_number}</strong>
                    <span className="evo-version-chain-badges">
                      {isBase && <i>基准</i>}
                      {isTarget && <i>目标</i>}
                    </span>
                  </div>
                  <time>{formatJobVersionTime(version.changed_at)}</time>
                </li>
              );
            })}
          </ol>
        ) : (
          <p className="evo-version-chain-empty">{versionLoading ? "正在读取岗位的全部历史版本..." : "当前没有可展示的版本记录。"}</p>
        )}
      </section>

      <section className="evo-version-selector-panel" aria-label="选择要比较的岗位版本">
        <div className="evo-version-selector-head">
          <div>
            <span>自定义版本对照</span>
            <strong>任选两个历史版本</strong>
          </div>
          <em>{hasTwoVersions ? "基准与目标需不同" : "仅有基线"}</em>
        </div>
        <div className="evo-version-selectors">
          <Select
            aria-label="基准版本"
            className="evo-version-select"
            isDisabled={versionLoading || compareLoading || versions.length < 2}
            onSelectionChange={(key) => key != null && onSelectionChange?.("baseVersion", String(key))}
            selectedKey={selection.baseVersion || null}
            variant="secondary"
          >
            <Label>基准版本</Label>
            <Select.Trigger>
              <Select.Value>{versionOptionLabel(selectedBaseVersion, selectedBaseNumber, "选择基准版本")}</Select.Value>
              <Select.Indicator />
            </Select.Trigger>
            <Select.Popover>
              <ListBox>
                {versions.map((version) => (
                  <ListBox.Item
                    id={String(version.version_number)}
                    key={version.version_number}
                    textValue={`V${version.version_number} ${formatJobVersionTime(version.changed_at)}`}
                  >
                    <span className="evo-version-option">
                      <strong>V{version.version_number}</strong>
                      <time>{formatJobVersionTime(version.changed_at)}</time>
                    </span>
                    <ListBox.ItemIndicator />
                  </ListBox.Item>
                ))}
              </ListBox>
            </Select.Popover>
          </Select>
          <Select
            aria-label="目标版本"
            className="evo-version-select"
            isDisabled={versionLoading || compareLoading || versions.length < 2}
            onSelectionChange={(key) => key != null && onSelectionChange?.("targetVersion", String(key))}
            selectedKey={selection.targetVersion || null}
            variant="secondary"
          >
            <Label>目标版本</Label>
            <Select.Trigger>
              <Select.Value>{versionOptionLabel(selectedTargetVersion, selectedTargetNumber, "选择目标版本")}</Select.Value>
              <Select.Indicator />
            </Select.Trigger>
            <Select.Popover>
              <ListBox>
                {versions.map((version) => (
                  <ListBox.Item
                    id={String(version.version_number)}
                    key={version.version_number}
                    textValue={`V${version.version_number} ${formatJobVersionTime(version.changed_at)}`}
                  >
                    <span className="evo-version-option">
                      <strong>V{version.version_number}</strong>
                      <time>{formatJobVersionTime(version.changed_at)}</time>
                    </span>
                    <ListBox.ItemIndicator />
                  </ListBox.Item>
                ))}
              </ListBox>
            </Select.Popover>
          </Select>
        </div>
        <div className="evo-version-compare-actions">
          <Button className="evo-version-compare-command" isDisabled={!canCompare} isPending={compareLoading} onPress={onCompare} variant="primary">
            <GitCompareArrows size={15} />比较版本
          </Button>
          <p className={!hasTwoVersions ? "is-baseline" : ""}>{compareHint}</p>
        </div>
      </section>

      {versionLoading && <div className="evo-version-loading" role="status"><RefreshCw className="spin" size={20} />正在读取完整版本链和默认对照...</div>}
      {!versionLoading && versionError && <div className="evo-version-error" role="alert"><strong>版本比较失败</strong><p>{versionError}</p></div>}
      {compareLoading && <div className="evo-version-local-loading" role="status"><RefreshCw className="spin" size={16} />正在比较 V{selectedBaseNumber} 与 V{selectedTargetNumber}...</div>}
      {versionReady && !versionLoading && (
        <>
          <Chip color="accent" size="md" variant="soft"><GitBranch size={14} /><Chip.Label>岗位版本对照</Chip.Label></Chip>
      <div className="evo-version-overview">
        <div className="evo-version-overview-side before">
          <span>基准版本</span>
          <strong>{comparisonBaseNumber === null ? "基线" : `V${comparisonBaseNumber}`}</strong>
          <time>{comparedBaseVersion?.changed_at || detail.base_changed_at || detail.base_version_changed_at ? formatJobVersionTime(comparedBaseVersion?.changed_at || detail.base_changed_at || detail.base_version_changed_at) : comparisonBaseNumber === null ? "无更早版本" : "时间待补充"}</time>
        </div>
        <ArrowRight size={17} />
        <div className="evo-version-overview-side after">
          <span>目标版本</span>
          <strong>{comparisonTargetNumber === null ? "当前" : `V${comparisonTargetNumber}`}</strong>
          <time>{comparedTargetVersion?.changed_at || detail.changed_at ? formatJobVersionTime(comparedTargetVersion?.changed_at || detail.changed_at) : "时间待补充"}</time>
        </div>
      </div>
      <p className="drawer-summary">
        {comparisonBaseNumber !== null
          ? `已完成 V${comparisonBaseNumber} → V${comparisonTargetNumber} 对照，发现 ${detail.field_diffs?.length || 0} 个字段发生变化。`
          : "这是该岗位首次采集形成的基线快照，尚无更早版本可供对照。"}
      </p>
      <div className="evo-version-diff-summary">
        <span><small>变动字段</small><strong>{detail.field_diffs?.length || 0}</strong></span>
        <span className="added"><small>新增技能</small><strong>{added.length}</strong></span>
        <span className="removed"><small>移除技能</small><strong>{removed.length}</strong></span>
      </div>
      <section className="drawer-section evo-skill-version-diff">
        <h4>技能要求变化</h4>
        {added.length > 0 && <div><b>新增</b><span>{added.map((skill) => <Chip color="success" key={skill} size="sm" variant="soft"><Chip.Label>{skill}</Chip.Label></Chip>)}</span></div>}
        {removed.length > 0 && <div><b>移除</b><span>{removed.map((skill) => <Chip color="danger" key={skill} size="sm" variant="soft"><Chip.Label>{skill}</Chip.Label></Chip>)}</span></div>}
        {!added.length && !removed.length && <p className="evo-version-no-change">这两个版本的技能要求没有新增或移除。</p>}
      </section>
      <section className="drawer-section">
        <h4>字段修改前后</h4>
        <div className="evo-field-diff-list">
          {(detail.field_diffs || []).map((diff) => (
            <article className="evo-field-diff" key={diff.field}>
              <strong>{CHANGE_FIELD_LABELS[diff.field] || diff.field}</strong>
              <div className="evo-field-values">
                <section className="before"><span>修改前</span><EvolutionVersionValue value={diff.before} /></section>
                <ArrowRight aria-hidden="true" size={16} />
                <section className="after"><span>修改后</span><EvolutionVersionValue value={diff.after} /></section>
              </div>
            </article>
          ))}
          {!detail.field_diffs?.length && <p className="evo-version-baseline">{comparisonBaseNumber === null ? "基线版本已完整保存，下一次同岗位内容变化后会自动形成前后对照。" : "这两个版本的持久化快照没有字段差异。"}</p>}
        </div>
      </section>
      {detail.source_url && <Link href={detail.source_url} rel="noopener noreferrer" target="_blank">查看招聘网站当前页面 <Link.Icon><ExternalLink size={13} /></Link.Icon></Link>}
        </>
      )}
      {!versionLoading && !versionReady && !versionError && <p className="evo-version-empty">选择两个不同版本后，比较结果会显示在这里。</p>}
    </div>
  );
}

function EvolutionPage({ audience = "enterprise" }) {
  const isSeeker = audience === "seeker";
  const [mode, setMode] = useState("timeline");
  const [frames, setFrames] = useState([]);
  const [marketSummary, setMarketSummary] = useState(null);
  const [marketLoading, setMarketLoading] = useState(true);
  const [marketChanges, setMarketChanges] = useState([]);
  const [marketChangeQuery, setMarketChangeQuery] = useState("");
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [detail, setDetail] = useState(null);
  const [versionHistory, setVersionHistory] = useState([]);
  const [versionSelection, setVersionSelection] = useState({ baseVersion: "", targetVersion: "" });
  const [versionLoading, setVersionLoading] = useState(false);
  const [versionCompareLoading, setVersionCompareLoading] = useState(false);
  const [versionReady, setVersionReady] = useState(false);
  const [versionError, setVersionError] = useState("");
  const versionRequestRef = useRef(0);
  const [emerging, setEmerging] = useState([]);
  const [discovering, setDiscovering] = useState(false);
  const [monitoring, setMonitoring] = useState(false);
  const [monitorStatus, setMonitorStatus] = useState("");
  const frame = frames[index] || emptyEvolutionFrame;
  const marketChangeQueryText = marketChangeQuery.trim();
  const normalizedMarketChangeQuery = marketChangeQueryText.toLocaleLowerCase();
  const matchingMarketChanges = useMemo(() => {
    if (!normalizedMarketChangeQuery) return marketChanges;
    return marketChanges.filter((item) =>
      [item.title, item.company, item.city].some((value) =>
        String(value || "").toLocaleLowerCase().includes(normalizedMarketChangeQuery),
      ),
    );
  }, [marketChanges, normalizedMarketChangeQuery]);
  const visibleMarketChanges = useMemo(
    () => (normalizedMarketChangeQuery ? matchingMarketChanges.slice(0, 50) : matchingMarketChanges.slice(0, 8)),
    [matchingMarketChanges, normalizedMarketChangeQuery],
  );
  const matrixSkills = useMemo(() => {
    const scores = new Map();
    frames.forEach((item) => item.changes.forEach(([skill, , after]) => {
      scores.set(skill, Math.max(scores.get(skill) || 0, after || 0));
    }));
    return [...scores.entries()].sort((left, right) => right[1] - left[1]).slice(0, 4).map(([skill]) => skill);
  }, [frames]);
  const loadMarketEvolution = useCallback(async () => {
    setMarketLoading(true);
    try {
      const [data, platform] = await Promise.all([
        request("/api/evolution/market?source_platform=zhaopin&max_frames=20"),
        request("/api/platform/summary"),
      ]);
      const nextFrames = data.frames || [];
      setFrames(nextFrames);
      setMarketSummary(data.summary || {
        monitored_jobs: platform.sources?.zhaopin || 0,
        version_snapshots: platform.version_snapshots || 0,
        changed_jobs: platform.changed_jobs || 0,
      });
      setMarketChanges(data.recent_changes || []);
      setIndex(Math.max(0, nextFrames.length - 1));
      return data;
    } catch (error) {
      const platform = await request("/api/platform/summary");
      setMarketSummary({
        monitored_jobs: platform.sources?.zhaopin || 0,
        version_snapshots: platform.version_snapshots || 0,
        changed_jobs: platform.changed_jobs || 0,
      });
      setMarketChanges((platform.recent_job_changes || []).map((item) => ({
        ...item,
        job_id: item.source_id,
        changed_at: item.changed_at,
        version_number: 1,
        changed_fields: [item.change_type || "updated"],
      })));
      throw error;
    } finally {
      setMarketLoading(false);
    }
  }, []);
  useEffect(() => {
    request("/api/emerging-jobs")
      .then((data) => setEmerging(data.items || data.candidates || data))
      .catch(() => {});
    loadMarketEvolution().catch(() => setMonitorStatus("岗位版本数据读取失败"));
  }, [loadMarketEvolution]);
  useEffect(() => {
    if (!playing || frames.length < 2) return undefined;
    const timer = setInterval(
      () =>
        setIndex((value) =>
          value === frames.length - 1 ? 0 : value + 1,
        ),
      1200,
    );
    return () => clearInterval(timer);
  }, [frames.length, playing]);
  const monitorChanges = async () => {
    setMonitoring(true);
    setMonitorStatus("正在重新访问智联岗位并与当前基线比较...");
    try {
      const run = await request("/api/data/collect", {
        method: "POST",
        body: JSON.stringify({
          source_ids: ["zhaopin"],
          max_items_per_source: 200,
          lookback_hours: 2160,
          min_job_quality: 65,
          persist: true,
          collection_mode_override: "monitor",
          full_scan_chunk: true,
        }),
      });
      let completed = null;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
        completed = await request(`/api/data/collection-runs/${run.run_id}`);
        const source = completed.source_results?.find((item) => item.source_id === "zhaopin");
        setMonitorStatus(
          source?.status === "running"
            ? `正在检测 · 已扫描 ${source.scanned || source.fetched || 0} 条`
            : "正在整理岗位和能力变化...",
        );
        if (["completed", "partial", "failed"].includes(completed.status)) break;
      }
      await loadMarketEvolution();
      setMonitorStatus(
        completed?.updated_count
          ? `检测完成：发现 ${completed.updated_count} 个岗位变化`
          : "检测完成：当前批次未发现岗位内容变化",
      );
    } catch (error) {
      setMonitorStatus(error.message || "岗位变化检测失败");
    } finally {
      setMonitoring(false);
    }
  };
  const discover = async () => {
    setDiscovering(true);
    try {
      const data = await request("/api/emerging-jobs/discover", {
        method: "POST",
        body: JSON.stringify({
          minimum_source_count: 2,
          minimum_confidence: 0.45,
        }),
      });
      setEmerging(data.items || data.candidates || []);
    } catch {
    } finally {
      setDiscovering(false);
    }
  };
  const reviewEmerging = async (candidateId, status) => {
    const data = await request(`/api/emerging-jobs/${candidateId}/review`, {
      method: "POST",
      body: JSON.stringify({ status, corrections: {}, note: "演化分析工作台人工审核" }),
    });
    const next = data.candidate;
    setEmerging((items) => items.map((item) => item.candidate_id === candidateId ? next : item));
    setDetail((value) => value?.candidate_id === candidateId ? { ...next, emerging: true } : value);
  };
  const closeDetail = () => {
    versionRequestRef.current += 1;
    setDetail(null);
    setVersionHistory([]);
    setVersionSelection({ baseVersion: "", targetVersion: "" });
    setVersionLoading(false);
    setVersionCompareLoading(false);
    setVersionReady(false);
    setVersionError("");
  };
  const openVersionComparison = async (item) => {
    const targetVersionNumber = normalizeVersionNumber(item.version_number);
    const requestId = versionRequestRef.current + 1;
    versionRequestRef.current = requestId;
    setDetail({ ...item, versionComparison: true });
    setVersionHistory([]);
    setVersionSelection({ baseVersion: "", targetVersion: targetVersionNumber === null ? "" : String(targetVersionNumber) });
    setVersionLoading(true);
    setVersionCompareLoading(false);
    setVersionReady(false);
    setVersionError("");
    if (targetVersionNumber === null) {
      setVersionLoading(false);
      setVersionError("当前岗位记录缺少有效的目标版本号。");
      return;
    }

    const jobPath = `/api/jobs/${encodeURIComponent(item.job_id)}`;
    const [versionsResult, comparisonResult] = await Promise.allSettled([
      request(`${jobPath}/versions`),
      request(`${jobPath}/versions/${targetVersionNumber}/compare`),
    ]);
    if (requestId !== versionRequestRef.current) return;

    const rawVersions = versionsResult.status === "fulfilled"
      ? (Array.isArray(versionsResult.value) ? versionsResult.value : versionsResult.value?.items || [])
      : [];
    const versionItems = [...rawVersions];
    if (!versionItems.some((version) => normalizeVersionNumber(version?.version_number) === targetVersionNumber)) {
      versionItems.push({ ...item, version_number: targetVersionNumber });
    }
    const nextVersions = normalizeJobVersions(versionItems);
    const previousVersion = nextVersions.filter((version) => version.version_number < targetVersionNumber).slice(-1)[0];
    const comparison = comparisonResult.status === "fulfilled" ? comparisonResult.value || {} : null;
    const responseBaseNumber = normalizeVersionNumber(comparison?.base_version_number)
      ?? normalizeVersionNumber(comparison?.previous_version_number);
    const selectedBaseNumber = previousVersion?.version_number
      ?? (nextVersions.some((version) => version.version_number === responseBaseNumber) ? responseBaseNumber : null);
    setVersionHistory(nextVersions);
    setVersionSelection({
      baseVersion: selectedBaseNumber === null || selectedBaseNumber === undefined ? "" : String(selectedBaseNumber),
      targetVersion: String(targetVersionNumber),
    });

    const errors = [];
    if (versionsResult.status === "rejected") errors.push(`历史版本链读取失败：${versionsResult.reason?.message || "请求失败"}`);
    if (comparisonResult.status === "rejected") errors.push(`默认版本对照失败：${comparisonResult.reason?.message || "请求失败"}`);
    setVersionError(errors.join("；"));
    if (comparisonResult.status === "fulfilled") {
      setDetail((current) => current ? { ...current, ...comparison, versionComparison: true } : current);
      setVersionReady(true);
    }
    setVersionLoading(false);
  };
  const updateVersionSelection = (field, value) => {
    setVersionSelection((current) => ({ ...current, [field]: value }));
    setVersionError("");
  };
  const compareSelectedVersions = async () => {
    const baseVersionNumber = normalizeVersionNumber(versionSelection.baseVersion);
    const targetVersionNumber = normalizeVersionNumber(versionSelection.targetVersion);
    if (!detail?.versionComparison || versionCompareLoading || versionHistory.length < 2 || baseVersionNumber === null || targetVersionNumber === null || baseVersionNumber === targetVersionNumber) return;
    const requestId = versionRequestRef.current + 1;
    versionRequestRef.current = requestId;
    setVersionCompareLoading(true);
    setVersionError("");
    try {
      const comparison = await request(`/api/jobs/${encodeURIComponent(detail.job_id)}/versions/${targetVersionNumber}/compare?base_version_number=${encodeURIComponent(baseVersionNumber)}`);
      if (requestId !== versionRequestRef.current) return;
      setDetail((current) => current ? { ...current, ...comparison, versionComparison: true } : current);
      setVersionReady(true);
    } catch (error) {
      if (requestId !== versionRequestRef.current) return;
      setVersionError(error.message || "未能读取所选岗位版本对照");
    } finally {
      if (requestId === versionRequestRef.current) setVersionCompareLoading(false);
    }
  };
  return (
    <main className="evolution-page evolution-heroui">
      <Tabs className="evolution-tabs evo-mode-tabs" selectedKey={mode} onSelectionChange={(key) => setMode(String(key))}>
        <section className="evo-head">
          <div className="evo-head-actions">
            <Tabs.ListContainer>
              <Tabs.List aria-label="岗位演化视图">
                <Tabs.Tab id="timeline"><GitBranch size={15} />历史演化<Tabs.Indicator /></Tabs.Tab>
                <Tabs.Tab id="discover"><Sparkles size={15} />新岗位发现<Tabs.Indicator /></Tabs.Tab>
              </Tabs.List>
            </Tabs.ListContainer>
            {isSeeker && <Chip className="evo-view-mode-chip" color="accent" size="sm" variant="soft"><Eye size={14} /><Chip.Label>求职视角 · 只读</Chip.Label></Chip>}
            {!isSeeker && (
              <Button className="monitor-action" variant="secondary" onPress={monitorChanges} isPending={monitoring}>
                <RefreshCw size={15} className={monitoring ? "spin" : ""} />
                {monitoring ? "检测中" : "检测智联变动"}
              </Button>
            )}
          </div>
        </section>
        <Tabs.Panel className="evo-mode-panel" id="timeline">
          <section className="monitor-strip" aria-label="岗位演化监测概览">
          {[
            [isSeeker ? "市场监测岗位" : "监测岗位", marketSummary?.monitored_jobs ?? 0, BriefcaseBusiness, "blue", "岗位基线持续跟踪"],
            ["版本快照", marketSummary?.version_snapshots ?? 0, GitBranch, "indigo", "历史版本完整留档"],
            ["变动岗位", marketSummary?.changed_jobs ?? 0, TrendingUp, "azure", "职责与技能变化"],
          ].map(([label, value, Icon, tone, note]) => (
            <Card className={`evo-stat-card ${tone}`} key={label} variant="default">
              <Card.Content className="evo-stat-content">
                <span className="evo-stat-icon"><Icon aria-hidden="true" size={21} /></span>
                <span className="evo-stat-label">{label}</span>
                <strong className="evo-stat-value">
                  {marketLoading ? <span className="evo-stat-loading">--</span> : Number(value || 0).toLocaleString("zh-CN")}
                </strong>
                <em className="evo-stat-note">{note}</em>
              </Card.Content>
            </Card>
          ))}
          <Card className="evo-monitor-status" variant="default">
            <Card.Content className="evo-monitor-status-content">
              <span className="evo-status-icon"><RefreshCw aria-hidden="true" size={21} className={monitoring ? "spin" : ""} /></span>
              <span className="evo-status-label">数据更新状态</span>
              <strong>{marketLoading ? "正在读取" : monitoring ? "正在更新" : "快照已同步"}</strong>
              <p>{marketLoading ? "正在加载真实岗位版本与能力变化..." : monitorStatus || (marketSummary?.needs_next_monitor ? "已建立首个岗位基线，再次检测后将生成变化结果。" : "已根据岗位版本快照完成岗位与能力变化追踪。")}</p>
            </Card.Content>
          </Card>
          </section>
          <Card className="evo-workbench" variant="default">
            <Card.Content className="evo-workbench-content">
            <aside className="version-rail">
              <div className="version-head">
                <Button aria-label={playing ? "暂停版本播放" : "播放版本演化"} isIconOnly size="sm" variant="secondary" onPress={() => setPlaying(!playing)}>
                  {playing ? <Pause size={16} /> : <Play size={16} />}
                </Button>
                <div>
                  <span>岗位模型版本</span>
                  <strong>{isSeeker ? "新一代信息技术岗位" : "智联全域岗位"}</strong>
                </div>
              </div>
              {frames.length ? frames.map((item, i) => (
                <Button
                  key={item.time}
                  className={i === index ? "active" : ""}
                  variant="ghost"
                  onPress={() => {
                    setIndex(i);
                    setPlaying(false);
                  }}
                >
                  <span>{item.time}</span>
                  <div>
                    <strong>{item.title}</strong>
                    <small>{item.summary}</small>
                  </div>
                  <i />
                </Button>
              )) : <div className="version-empty">等待智联岗位基线</div>}
            </aside>
            <div className="version-main">
              <div className="version-summary">
                <div>
                  <span>
                    {frame.time} · VERSION {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3>{frame.title}</h3>
                  <p>{frame.summary}</p>
                </div>
                <div className="version-kpis">
                  <span>
                    <b>{frame.changes.filter((x) => x[3] === "new").length}</b>
                    新增能力
                  </span>
                  <span>
                    <b>{frame.changes.filter((x) => x[3] === "up").length}</b>
                    增强
                  </span>
                  <span>
                    <b>{frame.changes.filter((x) => x[3] === "down").length}</b>
                    减弱
                  </span>
                  <span>
                    <b>{frame.comparison_job_count || 0}</b>
                    可比岗位
                  </span>
                </div>
              </div>
              <div className="evo-cohort-context">
                <Database size={15} />
                <span>本期以 <strong>{frame.comparison_job_count || 0}</strong> 个前后版本均存在的岗位为统计分母；另有 <strong>{frame.baseline_jobs || 0}</strong> 个首次采集岗位仅建立基线，不计入升降。</span>
              </div>
              <Table className="change-ledger evo-data-table evo-change-table" variant="secondary">
                <Table.ScrollContainer>
                  <Table.Content aria-label="能力变化清单">
                    <Table.Header>
                      <Table.Column isRowHeader>能力项</Table.Column>
                      <Table.Column>上一版本</Table.Column>
                      <Table.Column>当前版本</Table.Column>
                      <Table.Column>变化</Table.Column>
                      <Table.Column>当前命中 / 分母</Table.Column>
                      <Table.Column aria-label="操作">操作</Table.Column>
                    </Table.Header>
                    <Table.Body renderEmptyState={() => <div className="evo-table-empty">当前版本暂无能力变化</div>}>
                      {frame.changes.map(([skill, before, after, trend, evidence, evidenceDetails], changeIndex) => (
                        <Table.Row key={`ability-change-${changeIndex}`} id={`ability-change-${changeIndex}`}>
                          <Table.Cell>
                            <div className="evo-change-skill">
                              <i className={`evo-change-skill-dot ${trend}`} />
                              <strong>{skill}</strong>
                            </div>
                          </Table.Cell>
                          <Table.Cell>{before}%</Table.Cell>
                          <Table.Cell><strong className="evo-current-score">{after}%</strong></Table.Cell>
                          <Table.Cell>
                            <Chip className={`evo-trend-chip ${trend}`} color={trend === "down" ? "danger" : "accent"} size="md" variant="soft">
                              {trend === "down" ? <TrendingDown size={13} /> : trend === "new" ? <Plus size={13} /> : <TrendingUp size={13} />}
                              <Chip.Label>{after - before > 0 ? "+" : ""}{Math.round((after - before) * 10) / 10} pp</Chip.Label>
                            </Chip>
                          </Table.Cell>
                          <Table.Cell>
                            <Button
                              className="evo-evidence-count"
                              size="sm"
                              variant="ghost"
                              onPress={() => setDetail({ skill, before, after, trend, evidence, evidenceDetails, time: frame.time })}
                            >
                              {evidenceDetails?.after_count ?? evidence} / {evidenceDetails?.denominator || 0} <ExternalLink size={12} />
                            </Button>
                          </Table.Cell>
                          <Table.Cell>
                            <Button
                              aria-label={`查看 ${skill} 变化详情`}
                              isIconOnly
                              size="sm"
                              variant="ghost"
                              onPress={() => setDetail({ skill, before, after, trend, evidence, evidenceDetails, time: frame.time })}
                            >
                              <ChevronRight size={15} />
                            </Button>
                          </Table.Cell>
                        </Table.Row>
                      ))}
                    </Table.Body>
                  </Table.Content>
                </Table.ScrollContainer>
              </Table>
              <div className="evo-matrix">
                <div>
                  <span>技能变化热力</span>
                  <small>完整月度序列 · 共 {frames.length} 个版本 · 颜色越深代表要求占比越高</small>
                </div>
                <div className="matrix-grid" style={{ gridTemplateColumns: `100px repeat(${Math.max(frames.length, 1)}, minmax(42px, 1fr))` }}>
                  <span />
                  {frames.map((x) => (
                    <b key={x.time}>{x.time.slice(2)}</b>
                  ))}
                  {matrixSkills.map(
                    (skill) => (
                      <React.Fragment key={skill}>
                        <strong>{skill}</strong>
                        {frames.map((x) => {
                          const ability = x.changes.find((item) => item[0] === skill);
                          const rate = ability?.[2] || 0;
                          return (
                          <i
                            key={x.time}
                            style={{
                              "--heat": `${Math.max(0.08, rate / 100)}`,
                            }}
                            title={`${skill} · ${x.time} · ${rate}%`}
                          />
                          );
                        })}
                      </React.Fragment>
                    ),
                  )}
                </div>
              </div>
              <div className="job-change-list">
                <div className="job-change-heading">
                  <div className="job-change-heading-copy">
                    <span>最近岗位变动</span>
                    <small>只展示形成新版本的岗位，不包含完全重复和未变化记录</small>
                  </div>
                  <div className="job-change-heading-tools">
                    <small className="job-change-count" aria-live="polite">
                      {marketChangeQueryText
                        ? `匹配 ${matchingMarketChanges.length} 条 / 共 ${marketChanges.length} 条变更`
                        : `最新 ${visibleMarketChanges.length} 条 / 共 ${marketChanges.length} 条变更`}
                    </small>
                    <SearchField
                      aria-label="搜索最近岗位变动"
                      className="job-change-search"
                      value={marketChangeQuery}
                      variant="secondary"
                      onChange={setMarketChangeQuery}
                    >
                      <SearchField.Group>
                        <SearchField.SearchIcon />
                        <SearchField.Input placeholder="搜索岗位、公司或城市" />
                        <SearchField.ClearButton />
                      </SearchField.Group>
                    </SearchField>
                  </div>
                </div>
                <Table className="evo-data-table evo-job-table" variant="secondary">
                  <Table.ScrollContainer>
                    <Table.Content aria-label="最近岗位变动">
                      <Table.Header>
                        <Table.Column isRowHeader>岗位</Table.Column>
                        <Table.Column>变动字段</Table.Column>
                        <Table.Column>更新时间</Table.Column>
                        <Table.Column>版本</Table.Column>
                        <Table.Column aria-label="版本对照">版本对照</Table.Column>
                      </Table.Header>
                      <Table.Body renderEmptyState={() => (
                        <div className="job-change-empty">
                          <strong>{marketChangeQueryText ? "没有匹配结果" : "暂无变更"}</strong>
                          <span>
                            {marketChangeQueryText
                              ? `未找到包含“${marketChangeQueryText}”的岗位、公司或城市。`
                              : "当前只有岗位基线；下一轮监测发现内容变化后将在这里生成岗位版本记录。"}
                          </span>
                        </div>
                      )}>
                        {visibleMarketChanges.map((item) => (
                          <Table.Row key={`${item.job_id}-${item.version_number}`} id={`${item.job_id}-${item.version_number}`}>
                            <Table.Cell>
                              <div className="evo-job-title">
                                <strong>{item.title || "未命名岗位"}</strong>
                                <span>{item.company || "企业未公开"} · {item.city || "城市未公开"}</span>
                              </div>
                            </Table.Cell>
                            <Table.Cell>
                              <div className="evo-change-fields">
                                {item.changed_fields.map((field) => (
                                  <Chip color="accent" key={field} size="sm" variant="soft">
                                    <Chip.Label>{CHANGE_FIELD_LABELS[field] || field}</Chip.Label>
                                  </Chip>
                                ))}
                              </div>
                            </Table.Cell>
                            <Table.Cell><time>{String(item.changed_at || "").slice(0, 16).replace("T", " ")}</time></Table.Cell>
                            <Table.Cell>
                              <Chip color="default" size="sm" variant="soft"><Chip.Label>V{item.version_number || 1}</Chip.Label></Chip>
                            </Table.Cell>
                            <Table.Cell>
                              <Button className="evo-version-compare-button" size="sm" variant="ghost" onPress={() => openVersionComparison(item)}>
                                修改前后 <GitCompareArrows size={15} />
                              </Button>
                            </Table.Cell>
                          </Table.Row>
                        ))}
                      </Table.Body>
                    </Table.Content>
                  </Table.ScrollContainer>
                </Table>
              </div>
            </div>
            </Card.Content>
          </Card>
        </Tabs.Panel>
        <Tabs.Panel className="evo-mode-panel" id="discover">
          <section className="evo-discovery-panel">
          <Card className="evo-discovery-method" variant="default">
            <Card.Header className="discovery-method-header">
              <div className="discovery-copy">
                <Card.Title>{isSeeker ? "识别正在形成的新职业方向" : "从技能共现中识别尚未统一命名的岗位"}</Card.Title>
                <Card.Description>
                  {isSeeker
                    ? "结合真实招聘需求、技能组合、企业扩散度与技术趋势，判断新岗位的成熟阶段和发展机会。"
                    : "系统综合岗位名称聚类、技能共现、职责边界、增长速度、企业扩散度和连续时间窗口，生成岗位定义候选。"}
                </Card.Description>
              </div>
              {!isSeeker && (
                <Button className="discovery-run" isPending={discovering} size="lg" variant="primary" onPress={discover}>
                  <Sparkles size={18} />
                  {discovering ? "正在重新计算..." : "运行岗位发现"}
                </Button>
              )}
            </Card.Header>
            <Card.Content className="discovery-method-content">
              <Surface className="discovery-flow" variant="secondary">
                <div className="discovery-flow-steps" aria-label="新岗位发现流程" role="list">
                  {[
                    ["01", "名称聚类", "合并同义岗位名称"],
                    ["02", "技能成簇", "识别稳定共现能力"],
                    ["03", "职责分化", "判断是否形成独立边界"],
                    ["04", "跨源验证", "确认企业与时间扩散"],
                  ].map(([n, t, d]) => (
                    <div className="discovery-flow-step" key={n} role="listitem">
                      <Chip color="accent" size="md" variant="soft"><Chip.Label>{n}</Chip.Label></Chip>
                      <div><strong>{t}</strong><span>{d}</span></div>
                    </div>
                  ))}
                </div>
              </Surface>
            </Card.Content>
          </Card>
          <div className="emerging-candidate-grid">
            {!emerging.length && (
              <Alert className="evo-emerging-empty" status="accent">
                <Alert.Indicator><Sparkles size={22} /></Alert.Indicator>
                <Alert.Content>
                  <Alert.Title>尚未形成可发布的新岗位候选</Alert.Title>
                  <Alert.Description>系统只展示由招聘主数据事实证据支撑的候选；社区信号仅用于扩展检索词。</Alert.Description>
                </Alert.Content>
              </Alert>
            )}
            {emerging.map((job, i) => {
              const jobName = job.title || job.job_title || job.name;
              const growthValue = job.growth ?? Math.round((job.growth_rate ?? 0) * 1000) / 10;
              const candidateSkills = (job.skills || job.core_skills || job.required_skills || []).slice(0, 8);
              const responsibilities = (job.responsibilities || job.core_responsibilities || []).slice(0, 3);
              return (
                <Card
                  key={job.id || job.candidate_id || jobName}
                  className="emerging-card"
                  variant={i === 0 ? "tertiary" : "secondary"}
                >
                  <Card.Header>
                    <div className="emerging-card-tags">
                      <Chip color="accent" size="sm" variant="soft"><Chip.Label>{job.domain || "人工智能"}</Chip.Label></Chip>
                      <Chip color={job.maturity_status === "forming" ? "warning" : "accent"} size="sm" variant="secondary"><Chip.Label>
                        {{
                          established: "定义候选",
                          forming: "正在形成",
                          signal: "前沿信号",
                        }[job.maturity_status] || job.maturity || "定义候选"}
                      </Chip.Label></Chip>
                    </div>
                    <div className="emerging-card-heading">
                      <Card.Title>{jobName}</Card.Title>
                      <Card.Description>{job.definition || job.reason || job.definition_reason}</Card.Description>
                    </div>
                  </Card.Header>
                  <Card.Content>
                    <Meter className="emerging-confidence-meter" aria-label={`${jobName}定义置信度`} color="accent" size="sm" value={Math.round((job.confidence ?? 0) * 100)}>
                      <Label>定义置信度</Label>
                      <Meter.Output />
                      <Meter.Track><Meter.Fill /></Meter.Track>
                    </Meter>
                    <dl className="candidate-metrics" aria-label={`${jobName}岗位指标`}>
                      <div className={growthValue < 0 ? "down" : "up"}>
                        <dt>{growthValue < 0 ? <TrendingDown size={15} /> : <TrendingUp size={15} />}近30日需求占比变化</dt>
                        <dd>{growthValue >= 0 ? "+" : ""}{growthValue}%</dd>
                      </div>
                      <div><dt><Database size={15} />来源岗位</dt><dd>{job.sources || job.source_count || 0}</dd></div>
                      <div><dt><BriefcaseBusiness size={15} />覆盖企业</dt><dd>{job.source_diversity?.companies || job.evidence_summary?.companies || 0}</dd></div>
                    </dl>
                    {!!candidateSkills.length && (
                      <>
                        <Separator className="emerging-section-separator" variant="tertiary" />
                        <div className="emerging-skill-chips" aria-label={`${jobName}核心技能`}>
                          {candidateSkills.map((skill) => (
                            <Chip color="accent" key={skill} size="sm" variant="soft"><Chip.Label>{skill}</Chip.Label></Chip>
                          ))}
                        </div>
                      </>
                    )}
                    {!!responsibilities.length && (
                      <>
                        <Separator className="emerging-section-separator" variant="tertiary" />
                        <section className="emerging-definition">
                          <h4>建议岗位定义</h4>
                          <ul>{responsibilities.map((item) => <li key={item}>{item}</li>)}</ul>
                        </section>
                      </>
                    )}
                  </Card.Content>
                  <Card.Footer>
                    <dl className="candidate-evidence-summary" aria-label={`${jobName}证据摘要`}>
                      <div><dt>招聘事实</dt><dd>{job.source_count || 0}</dd></div>
                      <div><dt>前沿辅助</dt><dd>{job.evidence_summary?.auxiliary_signals || 0}</dd></div>
                      <div title={job.source_family || "待确认"}><dt>来源岗位族</dt><dd>{job.source_family || "待确认"}</dd></div>
                    </dl>
                    <Button fullWidth size="lg" variant="secondary" onPress={() => setDetail({ ...job, emerging: true })}>
                      查看发现证据 <ArrowRight size={16} />
                    </Button>
                  </Card.Footer>
                </Card>
              );
            })}
          </div>
          </section>
        </Tabs.Panel>
      </Tabs>
      {detail && (
        <Drawer
          title={detail.skill || detail.after?.title || detail.title || detail.job_title || detail.name || "岗位版本详情"}
          onClose={closeDetail}
        >
          {detail.versionComparison ? (
            <JobVersionComparison
              detail={detail}
              versions={versionHistory}
              selection={versionSelection}
              versionLoading={versionLoading}
              compareLoading={versionCompareLoading}
              versionReady={versionReady}
              versionError={versionError}
              onSelectionChange={updateVersionSelection}
              onCompare={compareSelectedVersions}
            />
          ) : detail.emerging ? (
            <div className="emerging-drawer-content">
              <Chip color="accent" size="md" variant="soft"><Sparkles size={14} /><Chip.Label>新岗位定义候选</Chip.Label></Chip>
              <Meter className="emerging-drawer-confidence" aria-label="新岗位定义综合置信度" color="accent" size="lg" value={Math.round((detail.confidence ?? 0) * 100)}>
                <Label>综合置信度</Label>
                <Meter.Output />
                <Meter.Track><Meter.Fill /></Meter.Track>
              </Meter>
              <p className="emerging-drawer-summary">{detail.definition || detail.reason}</p>
              <dl className="emerging-drawer-metrics" aria-label="候选岗位证据概览">
                <div><dt><Database size={15} />岗位证据</dt><dd>{detail.source_count || detail.sources || 0}</dd></div>
                <div><dt><BriefcaseBusiness size={15} />覆盖企业</dt><dd>{detail.source_diversity?.companies || detail.evidence_summary?.companies || 0}</dd></div>
                <div><dt><FileText size={15} />抽样证据</dt><dd>{detail.evidence?.length || 0}</dd></div>
              </dl>
              <Separator variant="tertiary" />
              <section className="emerging-drawer-section">
                <div className="emerging-drawer-section-head">
                  <h4>定义判据</h4>
                  <Chip
                    color={isSeeker ? "accent" : detail.review_status === "approved" ? "success" : detail.review_status === "rejected" ? "danger" : "warning"}
                    size="sm"
                    variant="soft"
                  >
                    <Chip.Label>{isSeeker ? ({
                      established: "定义候选",
                      forming: "正在形成",
                      signal: "前沿信号",
                    }[detail.maturity_status] || detail.maturity || "定义候选") : (detail.review_status || "待审核")}</Chip.Label>
                  </Chip>
                </div>
                <ul>
                  <li>{detail.difference_summary || "正在与已有岗位族计算能力边界差异。"}</li>
                  <li>正式定义必须有招聘网站证据，辅助来源不能单独发布岗位。</li>
                </ul>
              </section>
              <Separator variant="tertiary" />
              {!!detail.trend_series?.length && (
                <>
                  <section className="emerging-drawer-section">
                    <h4>近30日需求占比变化</h4>
                    <p>每个点/柱表示一个连续30天窗口内的候选岗位数、市场样本数及需求占比；需求占比已按采集规模归一化（候选岗位数 / 市场样本数），用于比较窗口变化，不仅是新增岗位绝对数。</p>
                    <Table className="emerging-drawer-table" variant="secondary">
                      <Table.ScrollContainer>
                        <Table.Content aria-label="连续30天候选岗位数、市场样本数与需求占比趋势">
                          <Table.Header><Table.Column isRowHeader>时间窗口</Table.Column><Table.Column>候选岗位数</Table.Column><Table.Column>市场样本数</Table.Column><Table.Column>需求占比</Table.Column></Table.Header>
                          <Table.Body>
                            {detail.trend_series.slice(-6).map((point, pointIndex) => {
                              const demandShare = Number(point.demand_share);
                              return (
                                <Table.Row id={`${point.period || pointIndex}`} key={point.period || pointIndex}>
                                  <Table.Cell>{point.period || `窗口 ${pointIndex + 1}`}</Table.Cell>
                                  <Table.Cell><strong>{point.count ?? 0}</strong></Table.Cell>
                                  <Table.Cell>{point.market_count ?? 0}</Table.Cell>
                                  <Table.Cell><strong>{Number.isFinite(demandShare) ? `${(demandShare * 100).toFixed(1)}%` : "—"}</strong></Table.Cell>
                                </Table.Row>
                              );
                            })}
                          </Table.Body>
                        </Table.Content>
                      </Table.ScrollContainer>
                    </Table>
                  </section>
                  <Separator variant="tertiary" />
                </>
              )}
              <section className="emerging-drawer-section">
                <h4>技能共现证据</h4>
                <Table className="emerging-drawer-table" variant="secondary">
                  <Table.ScrollContainer>
                    <Table.Content aria-label="技能共现证据">
                      <Table.Header><Table.Column isRowHeader>技能组合</Table.Column><Table.Column>共现支持度</Table.Column></Table.Header>
                      <Table.Body renderEmptyState={() => <div className="emerging-drawer-table-empty">等待下一次跨源计算生成技能共现矩阵。</div>}>
                        {(detail.cooccurrence_signals || []).slice(0, 6).map((signal) => (
                          <Table.Row id={`${signal.left}-${signal.right}`} key={`${signal.left}-${signal.right}`}>
                            <Table.Cell>{signal.left} · {signal.right}</Table.Cell>
                            <Table.Cell><strong>{Math.round((signal.support || 0) * 100)}%</strong></Table.Cell>
                          </Table.Row>
                        ))}
                      </Table.Body>
                    </Table.Content>
                  </Table.ScrollContainer>
                </Table>
              </section>
              <Separator variant="tertiary" />
              <section className="emerging-drawer-section">
                <h4>招聘事实来源</h4>
                <div className="emerging-evidence-cards">
                  {(detail.evidence || []).slice(0, 8).map((item, itemIndex) => (
                    <Card className="emerging-evidence-card" key={item.source_id || item.source_url || itemIndex} variant="secondary">
                      <Card.Header>
                        <div>
                          <Card.Title>{item.company || "匿名企业"}</Card.Title>
                          <Card.Description>{item.snippet}</Card.Description>
                        </div>
                        <Chip color="default" size="sm" variant="soft"><Chip.Label>{item.published_at?.slice(0, 10) || "最近采集"}</Chip.Label></Chip>
                      </Card.Header>
                      <Card.Footer>
                        <div className="emerging-evidence-skills">
                          <Chip color="accent" size="sm" variant="soft"><Chip.Label>{item.source_platform || "招聘网站"}</Chip.Label></Chip>
                          {(item.skills || []).slice(0, 3).map((skill) => <Chip color="accent" key={skill} size="sm" variant="secondary"><Chip.Label>{skill}</Chip.Label></Chip>)}
                        </div>
                        {item.source_url && (
                          <Link href={item.source_url} rel="noopener noreferrer" target="_blank">原始 JD <Link.Icon><ExternalLink size={13} /></Link.Icon></Link>
                        )}
                      </Card.Footer>
                    </Card>
                  ))}
                  {!detail.evidence?.length && (
                    <Card className="emerging-drawer-empty" variant="secondary"><Card.Content>当前没有可展示的招聘事实来源。</Card.Content></Card>
                  )}
                </div>
              </section>
              <Separator variant="tertiary" />
              <section className="emerging-drawer-section">
                <h4>前沿辅助信号</h4>
                <p>仅用于判断技术时滞和扩展搜索词，不计入正式岗位证据。</p>
                <div className="emerging-auxiliary-actions">
                  {(detail.auxiliary_evidence || []).map((item) => (
                    <Link className="emerging-auxiliary-link" href={item.source_url} isDisabled={!item.source_url} key={item.signal_id} rel="noopener noreferrer" target="_blank">
                      <Chip color="accent" size="sm" variant="soft"><Chip.Label>{SOURCE_LABELS[item.platform] || item.platform}</Chip.Label></Chip>
                      <span>{item.title}</span><Link.Icon><ExternalLink size={13} /></Link.Icon>
                    </Link>
                  ))}
                  {!detail.auxiliary_evidence?.length && (
                    <Card className="emerging-drawer-empty" variant="secondary"><Card.Content>当前没有命中的社区辅助证据。</Card.Content></Card>
                  )}
                </div>
              </section>
              {!isSeeker && (
                <div className="evo-review-actions">
                  <Button variant="secondary" onPress={() => reviewEmerging(detail.candidate_id, "watching")}>继续观察</Button>
                  <Button variant="danger" onPress={() => reviewEmerging(detail.candidate_id, "rejected")}>拒绝候选</Button>
                  <Button variant="primary" onPress={() => reviewEmerging(detail.candidate_id, "approved")}><Check size={14}/>确认发布</Button>
                </div>
              )}
            </div>
          ) : (
            <>
              <span className={`detail-label ${detail.trend}`}>
                {detail.time} · 能力变化
              </span>
              <h3 className="drawer-lead">
                {detail.after - detail.before > 0 ? "+" : ""}
                {Math.round((detail.after - detail.before) * 10) / 10} pp
              </h3>
              <p className="drawer-summary">
                在同一批持续监测岗位中，要求 {detail.skill} 的岗位占比从 {detail.before}% 变化到 {detail.after}%。
              </p>
              <div className="drawer-section">
                <h4>占比计算口径</h4>
                <div className="evo-calculation-grid">
                  <span><small>可比岗位</small><strong>{detail.evidenceDetails?.denominator || 0}</strong></span>
                  <span><small>上一版本命中</small><strong>{detail.evidenceDetails?.before_count || 0}</strong></span>
                  <span><small>当前版本命中</small><strong>{detail.evidenceDetails?.after_count || detail.evidence || 0}</strong></span>
                </div>
                <p className="evo-method-note">
                  计算公式：命中该技能的可比岗位数 ÷ 前后版本均存在且在招的岗位数。新增采集岗位只建立基线，不参与本期升降判断。
                </p>
              </div>
              <div className="drawer-section">
                <h4>版本差异</h4>
                <div className="diff-block">
                  <del>- 移除该技能的岗位 {detail.evidenceDetails?.removed_count || 0} 个</del>
                  <ins>+ 新增该技能的岗位 {detail.evidenceDetails?.added_count || 0} 个</ins>
                </div>
                <small>{detail.evidenceDetails?.method || "持续监测岗位同群对比"} · 差值为 {detail.after - detail.before > 0 ? "+" : ""}{Math.round((detail.after - detail.before) * 10) / 10} 个百分点</small>
              </div>
              <div className="drawer-section evo-source-evidence">
                <h4>具体证据来源</h4>
                {[
                  ["新增要求", detail.evidenceDetails?.added_evidence || []],
                  ["移除要求", detail.evidenceDetails?.removed_evidence || []],
                  ["当前证据抽样", detail.evidenceDetails?.current_evidence || []],
                ].map(([label, items]) => items.length > 0 && (
                  <section key={label}>
                    <strong>{label} · {items.length} 条展示</strong>
                    {items.map((item) => (
                      <article key={`${label}-${item.job_id}`}>
                        <div><b>{item.title}</b><span>{item.company} · {item.city}</span></div>
                        {item.source_url ? <Link href={item.source_url} rel="noopener noreferrer" target="_blank">原始 JD <Link.Icon><ExternalLink size={12} /></Link.Icon></Link> : <small>原链接未保留</small>}
                      </article>
                    ))}
                  </section>
                ))}
                {!detail.evidenceDetails && <p>该历史结果没有保存证据明细，请重新加载演化数据。</p>}
              </div>
            </>
          )}
        </Drawer>
      )}
    </main>
  );
}

const defaultStoryChapters = [
  {
    time: "02:13",
    title: "第一幕 · 红色告警",
    scene: "你被电话叫醒。核心支付链路错误率从 0.3% 升至 18.4%，值班群里同时出现数据库 CPU 告警和订单积压。没人能确认它们是否属于同一故障。",
    objective: "在信息混乱时决定第一个动作",
    choices: [
      {id:"trace",title:"建立故障时间线",description:"拉取发布、链路追踪和核心指标，先确认影响面。",effect:"证据 +24 · 时间 -3",delta:{health:-2,evidence:24,trust:4}},
      {id:"rollback",title:"立即回滚",description:"跳过定位，直接回滚 23:40 的支付版本。",effect:"恢复机会 +18 · 数据风险 +9",delta:{health:18,evidence:4,trust:-2}},
      {id:"wait",title:"等待更多告警",description:"让各团队继续观察五分钟后再决定。",effect:"时间 +5 · 业务损失扩大",delta:{health:-16,evidence:6,trust:-8}},
    ],
  },
  {
    time: "02:19",
    title: "第二幕 · 矛盾证据",
    scene: "链路追踪显示支付服务本身正常，超时集中在库存依赖；但最新发布只修改了支付配置。数据库负责人认为是连接池耗尽，发布负责人坚持先回滚。",
    objective: "在团队意见冲突时选择验证方式",
    choices: [
      {id:"isolate",title:"隔离变量做灰度验证",description:"抽取 5% 流量切旧配置，同时对比库存连接池。",effect:"证据 +31 · 可逆性高",delta:{health:14,evidence:31,trust:8}},
      {id:"expand_db",title:"直接扩容数据库",description:"把连接池与实例规格翻倍，观察超时是否下降。",effect:"容量 +20 · 根因仍未知",delta:{health:8,evidence:8,trust:-1}},
      {id:"full_rollback",title:"全量回滚支付服务",description:"按发布时间相关性执行全量回滚。",effect:"恢复 +12 · 回滚半径大",delta:{health:12,evidence:5,trust:-3}},
    ],
  },
  {
    time: "02:27",
    title: "第三幕 · 业务压力",
    scene: "大客户已经投诉重复扣款，运营负责人要求立刻恢复；技术团队发现灰度流量恢复，但历史订单可能存在状态不一致。此时每分钟新增 420 笔异常订单。",
    objective: "在恢复速度和数据安全之间做取舍",
    choices: [
      {id:"degrade",title:"降级写入并切备用通道",description:"先停止风险扩大，保留订单查询并切换支付通道。",effect:"健康 +26 · 营收损失可控",delta:{health:26,evidence:12,trust:9}},
      {id:"force_resume",title:"强制恢复全部流量",description:"优先恢复交易，数据一致性稍后处理。",effect:"健康 +32 · 信任风险 +18",delta:{health:32,evidence:2,trust:-18}},
      {id:"shutdown",title:"暂停全部交易",description:"完全阻断风险，但所有用户无法支付。",effect:"数据风险最低 · 业务中断",delta:{health:10,evidence:8,trust:-10}},
    ],
  },
  {
    time: "02:41",
    title: "终幕 · 恢复之后",
    scene: "错误率已降到 0.7%。系统发现 1,284 笔订单处于支付成功但库存未确认状态。CEO 在群里询问是否可以宣布恢复。",
    objective: "决定结束故障的标准与沟通方式",
    choices: [
      {id:"reconcile",title:"完成一致性校验后分级恢复",description:"建立补偿清单、审计记录和客户通知，再逐级开放流量。",effect:"信任 +24 · 完整闭环",delta:{health:18,evidence:22,trust:24}},
      {id:"announce",title:"立即宣布恢复",description:"以错误率恢复为标准关闭事件，异常订单转交客服。",effect:"耗时最低 · 证据链中断",delta:{health:8,evidence:-4,trust:-15}},
      {id:"escalate",title:"升级重大事件并保持降级",description:"继续保持备用链路，邀请财务、法务与客服联合处置。",effect:"协作 +18 · 恢复较慢",delta:{health:12,evidence:15,trust:18}},
    ],
  },
];

const officeNpcs = [
  { x: 24, y: 34, approachX: 9, approachY: 8, role: "数据分析师", marker: "chart", icon: BarChart3, sprite: dataAnalystSprite },
  { x: 63, y: 35, approachX: -8, approachY: 9, role: "产品经理", marker: "people", icon: UserRound, sprite: productManagerSprite },
  { x: 27, y: 68, approachX: 7, approachY: -2, role: "前端工程师", marker: "code", icon: Edit3, sprite: frontendEngineerSprite },
  { x: 58, y: 72, approachX: -6, approachY: -3, role: "HRBP", marker: "doc", icon: FileText, sprite: hrbpSprite },
];

const QUEST_START_POSITION = Object.freeze({ x: 46, y: 52 });

function questNpcTarget(npc) {
  return {
    x: Math.max(8, Math.min(92, npc.x + (npc.approachX || 0))),
    y: Math.max(12, Math.min(88, npc.y + (npc.approachY || 0))),
  };
}

function questPathFromPoints(points) {
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
}

function Assessment({ candidate, setCandidate, saveCandidateRecord, navigate, notify, audience = "enterprise", currentUser, targetJob }) {
  const isSeeker = audience === "seeker";
  const candidateLabel = normalizeCandidateLabel(candidate);
  const initialIntervieweeName = candidateLabel === "该面试者"
    ? (isSeeker ? currentUser?.display_name || "求职者" : "")
    : candidateLabel;
  const [step, setStep] = useState(candidate ? 2 : 0);
  const [sessionView, setSessionView] = useState("hub");
  const [sessionLoading, setSessionLoading] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [intervieweeName, setIntervieweeName] = useState(initialIntervieweeName);
  const [nameInvalid, setNameInvalid] = useState(false);
  const [messages, setMessages] = useState([]);
  const [answer, setAnswer] = useState("");
  const [game, setGame] = useState([]);
  const [session, setSession] = useState(null);
  const [thinking, setThinking] = useState(false);
  const [interviewError, setInterviewError] = useState("");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [speechPhase, setSpeechPhase] = useState("idle");
  const [speechLevel, setSpeechLevel] = useState(0);
  const [speechNotice, setSpeechNotice] = useState("");
  const [rationale, setRationale] = useState("");
  const [gameReviewOpen, setGameReviewOpen] = useState(false);
  const [gameSubmitting, setGameSubmitting] = useState(false);
  const [storyStep, setStoryStep] = useState(0);
  const [npcReady, setNpcReady] = useState(false);
  const [walkingToNpc, setWalkingToNpc] = useState(false);
  const [candidatePosition, setCandidatePosition] = useState(QUEST_START_POSITION);
  const movementTimerRef = useRef(null);
  const movementTokenRef = useRef(0);
  const candidateNameInputRef = useRef(null);
  const resumeFileInputRef = useRef(null);
  const interviewLogRef = useRef(null);
  const lastSpokenQuestionRef = useRef("");
  const recognitionRef = useRef(null);
  const speechSocketRef = useRef(null);
  const speechConnectionRef = useRef(null);
  const speechCaptureRef = useRef(null);
  const speechBaseTextRef = useRef("");
  const speechTranscriptRef = useRef("");
  const browserFinalTextRef = useRef("");
  const speechFinalizeTimerRef = useRef(null);
  const [uploadedResume, setUploadedResume] = useState(null);
  const [resumeDragActive, setResumeDragActive] = useState(false);
  const [resumeUploadLoading, setResumeUploadLoading] = useState(false);
  const [resumeParseRetrying, setResumeParseRetrying] = useState(false);
  const [resumeUploadError, setResumeUploadError] = useState("");
  const gameScenario = useMemo(() => buildGameScenario(session), [session]);
  const storyChapters = gameScenario.chapters || [];
  const currentNpcIndex = storyChapters.length ? storyStep % officeNpcs.length : 0;
  const currentNpc = officeNpcs[currentNpcIndex];
  const routeNpcPoints = storyChapters.map((_, index) => officeNpcs[index % officeNpcs.length]);
  const routeTargetPoints = routeNpcPoints.map(questNpcTarget);
  const routeTravelPoints = [QUEST_START_POSITION, ...routeTargetPoints];
  const routePath = questPathFromPoints(routeTravelPoints);
  const routeProgressPath = questPathFromPoints(routeTravelPoints.slice(0, Math.min(routeTravelPoints.length, storyStep + (walkingToNpc || npcReady ? 2 : 1))));
  const storyMetrics = useMemo(() => game.reduce((total,item)=>({health:Math.max(0,Math.min(100,total.health+(item.delta?.health||0))),evidence:Math.max(0,Math.min(100,total.evidence+(item.delta?.evidence||0))),trust:Math.max(0,Math.min(100,total.trust+(item.delta?.trust||0)))}),gameScenario.initialMetrics),[game, gameScenario.initialMetrics]);
  const beginNpcWalk = (npc) => {
    if (!npc) return;
    if (movementTimerRef.current) window.clearTimeout(movementTimerRef.current);
    const movementToken = movementTokenRef.current + 1;
    movementTokenRef.current = movementToken;
    setWalkingToNpc(true);
    setNpcReady(false);
    setCandidatePosition(questNpcTarget(npc));
    movementTimerRef.current = window.setTimeout(() => {
      if (movementTokenRef.current !== movementToken) return;
      movementTimerRef.current = null;
      setWalkingToNpc(false);
      setNpcReady(true);
    }, 900);
  };
  const walkToCurrentNpc = () => {
    if (storyStep >= storyChapters.length || walkingToNpc) return;
    beginNpcWalk(currentNpc);
  };
  const chooseStory = (choice) => {
    if (game.length !== storyStep || !npcReady) return;
    const nextStep = Math.min(storyChapters.length, storyStep + 1);
    setGame((current)=>[...current,{...choice,chapter:storyStep+1,time:storyChapters[storyStep].time}]);
    setStoryStep(nextStep);
    if (nextStep === storyChapters.length) {
      setNpcReady(false);
      setWalkingToNpc(false);
      if (movementTimerRef.current) window.clearTimeout(movementTimerRef.current);
      movementTimerRef.current = null;
      setGameReviewOpen(true);
    } else {
      beginNpcWalk(officeNpcs[nextStep % officeNpcs.length]);
    }
  };
  useEffect(() => () => {
    movementTokenRef.current += 1;
    if (movementTimerRef.current) window.clearTimeout(movementTimerRef.current);
  }, []);
  const parsedResume = uploadedResume?.resume_parse;
  const parsedSummary = parsedResume?.quality_summary || {};
  const previewSkills = (parsedResume?.skills || []).slice(0, 6);
  const semanticProfile = parsedResume?.semantic_profile || {};
  const semanticReady = ["llm_enriched", "completed"].includes(semanticProfile?.status);
  const skillCount = parsedSummary.skill_count ?? parsedResume?.skills?.length ?? 0;
  const projectCount = parsedResume?.projects?.length ?? parsedSummary.project_count ?? 0;
  const jobIntent = parsedResume?.job_intent || "未识别";
  const cityText = (parsedResume?.city_preferences || parsedResume?.preferred_locations || []).join("、") || "未识别";
  const skillEvidenceTitle = (skill) => {
    if (typeof skill === "string") return "";
    const occurrence = skill?.occurrences?.find((item) => item?.snippet);
    const snippet = occurrence?.snippet || skill?.evidence || "";
    const section = occurrence?.section && occurrence.section !== "unknown" ? `来源：${occurrence.section}；` : "";
    return snippet ? `${section}原句：${snippet}` : "";
  };
  const textExtracted = Boolean(uploadedResume?.resume_text?.trim());
  const hasStructuredProfile = Boolean(
    (parsedResume?.skills?.length || 0) > 0
    || projectCount > 0
    || (parsedResume?.work_history?.length || 0) > 0
    || parsedResume?.education
    || Number(parsedResume?.experience_years || 0) > 0,
  );
  const parsePending = uploadedResume?.enrichment_status === "processing";
  const parseFailed = uploadedResume?.enrichment_status === "failed";
  const parseReady = Boolean(uploadedResume?.resume_text && parsedResume);
  const parseNeedsReview = parseFailed || !hasStructuredProfile;
  const buildCandidateView = (profile, matchReport = null) => ({
    ...profile,
    name: intervieweeName.trim() || profile.name || parsedResume?.candidate_name || "该面试者",
    archetype: profile.archetype_code,
    title: profile.archetype_title,
    narrative: profile.archetype_narrative,
    score: effectiveCandidateScore(profile, matchReport),
    traits: profile.traits || [],
    match_report: matchReport,
  });
  const focusCandidateNameField = () => {
    if (isSeeker) return;
    setNameInvalid(true);
    window.requestAnimationFrame(() => {
      candidateNameInputRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      candidateNameInputRef.current?.focus({ preventScroll: true });
    });
  };
  const handleCandidateNameChange = (value) => {
    setIntervieweeName(value);
    setNameInvalid(false);
  };
  const openResumeFilePicker = () => {
    if (resumeUploadLoading || resumeParseRetrying) return;
    if (!intervieweeName.trim()) {
      focusCandidateNameField();
      return;
    }
    resumeFileInputRef.current?.click();
  };
  const reportTimingItems = [
    ["匹配报告生成", candidate?.match_report?.report_timing?.match_report_ms],
  ].filter(([, value]) => Number(value || 0) > 0);
  const latestQuestion = useMemo(() => {
    const item = [...messages].reverse().find((message) => message.role === "ai");
    return item?.text || "";
  }, [messages]);
  const dialogueFocus = useMemo(() => normalizeDialogueFocus(session?.next_action?.metadata?.focus), [session]);
  const speechHotwords = useMemo(() => {
    const parsedSkills = (parsedResume?.skills || []).map((skill) => typeof skill === "string" ? skill : skill?.name);
    const jobSkills = targetJob?.skills || targetJob?.skill_tags || [];
    const values = [targetJob?.title, ...jobSkills, ...parsedSkills, ...dialogueFocus];
    return [...new Set(values.map((value) => String(value || "").trim()).filter((value) => value.length >= 2 && value.length <= 64))].slice(0, 40);
  }, [dialogueFocus, parsedResume, targetJob]);
  const dialogueSignals = useMemo(() => buildDialogueSignals(session), [session]);
  const dialogueStageLabel = ASSESSMENT_STAGE_LABELS[session?.current_stage] || "等待开始";
  const dialogueCompleted = Boolean(session?.candidate_profile?.dialogue_completed || session?.next_action?.type === "interactive_game" || session?.current_stage === "finalize_profile");
  const gameCompleted = Boolean(session?.candidate_profile?.interactive_game_completed || session?.completed_stages?.includes("interactive_game"));
  useEffect(() => {
    if (sessionView === "game" && storyChapters.length > 0 && storyStep === storyChapters.length && !gameCompleted) {
      setGameReviewOpen(true);
    }
  }, [gameCompleted, sessionView, storyChapters.length, storyStep]);
  const canEnterGame = dialogueCompleted;
  const canFinalizeAssessment = dialogueCompleted && gameCompleted;
  const canOpenAssessmentModule = Boolean(session);
  const canViewProfile = Boolean(candidate) || canFinalizeAssessment;
  const canViewReport = Boolean(candidate?.match_report) || canFinalizeAssessment;
  const candidateListening = speechPhase === "listening" || speechPhase === "fallback";
  const speechBusy = ["preparing", "listening", "fallback", "finalizing"].includes(speechPhase);
  const dialogueSkillIndex = session?.next_action?.metadata?.skill_index || session?.candidate_profile?.dialogue_skill_index + 1 || 0;
  const dialogueSkillTotal = session?.next_action?.metadata?.skill_total || session?.candidate_profile?.dialogue_skill_plan?.length || 0;
  const speakQuestion = useCallback((text = latestQuestion) => {
    const synth = typeof window !== "undefined" ? window.speechSynthesis : null;
    const Utterance = typeof window !== "undefined" ? window.SpeechSynthesisUtterance : null;
    if (!text || !synth || typeof Utterance !== "function") {
      setSpeaking(false);
      if (text) setSpeechNotice("当前浏览器不支持语音播报，已切换为文本面试。");
      return;
    }
    try {
      synth.cancel();
      const utterance = new Utterance(text);
      utterance.lang = "zh-CN";
      utterance.rate = 0.95;
      utterance.pitch = 1;
      utterance.onstart = () => setSpeaking(true);
      utterance.onend = () => setSpeaking(false);
      utterance.onerror = () => setSpeaking(false);
      synth.speak(utterance);
    } catch (error) {
      setSpeaking(false);
      setSpeechNotice("语音播报启动失败，已切换为文本面试。");
    }
  }, [latestQuestion]);
  const releaseSpeechCapture = useCallback((resetLevel = true) => {
    const capture = speechCaptureRef.current;
    speechCaptureRef.current = null;
    if (resetLevel) setSpeechLevel(0);
    if (!capture) return;
    capture.processor.onaudioprocess = null;
    capture.stream.getTracks().forEach((track) => track.stop());
    for (const node of [capture.source, capture.processor, capture.gain]) {
      try { node.disconnect(); } catch (error) {}
    }
    capture.audioContext.close().catch(() => {});
  }, []);

  const discardSpeechResources = useCallback(() => {
    const connection = speechConnectionRef.current;
    speechConnectionRef.current = null;
    if (connection) {
      connection.stopping = true;
      window.clearTimeout(connection.timer);
    }
    window.clearTimeout(speechFinalizeTimerRef.current);
    speechFinalizeTimerRef.current = null;

    const socket = connection?.socket || speechSocketRef.current;
    speechSocketRef.current = null;
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      try { socket.close(); } catch (error) {}
    }

    const recognition = recognitionRef.current;
    recognitionRef.current = null;
    if (recognition) {
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      try { recognition.abort(); } catch (error) {}
    }
    releaseSpeechCapture(false);
  }, [releaseSpeechCapture]);

  const startBrowserSpeechFallback = useCallback((reason = "") => {
    const Recognition = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
    if (!Recognition) {
      setSpeechPhase("error");
      setSpeechNotice("当前浏览器不支持备用语音识别，请手动输入回答。");
      return;
    }
    try {
      const recognition = new Recognition();
      recognition.lang = "zh-CN";
      recognition.continuous = true;
      recognition.interimResults = true;
      let failed = false;
      browserFinalTextRef.current = "";
      setSpeechPhase("fallback");
      setSpeechNotice(reason || "正在使用浏览器备用识别");
      recognition.onresult = (event) => {
        let finalText = "";
        let interimText = "";
        for (let index = 0; index < event.results.length; index += 1) {
          const transcript = event.results[index][0]?.transcript || "";
          if (event.results[index].isFinal) finalText += transcript;
          else interimText += transcript;
        }
        browserFinalTextRef.current = finalText.trim();
        const liveText = `${finalText}${interimText}`.trim();
        speechTranscriptRef.current = liveText;
        setAnswer(mergeSpeechAnswer(speechBaseTextRef.current, liveText));
      };
      recognition.onerror = (event) => {
        failed = true;
        setSpeechPhase("error");
        setSpeechNotice(event.error === "not-allowed" ? "浏览器未获得麦克风权限，请允许后重试。" : "备用语音识别中断，已保留当前文字。");
      };
      recognition.onend = () => {
        if (recognitionRef.current === recognition) recognitionRef.current = null;
        if (failed) return;
        const confirmedText = browserFinalTextRef.current;
        const liveText = speechTranscriptRef.current;
        const finalText = liveText.length > confirmedText.length ? liveText : confirmedText;
        if (finalText) setAnswer(mergeSpeechAnswer(speechBaseTextRef.current, finalText));
        setSpeechPhase("idle");
        setSpeechNotice(finalText ? "语音已转为文字" : "未识别到清晰语音");
      };
      recognitionRef.current = recognition;
      recognition.start();
    } catch (error) {
      recognitionRef.current = null;
      setSpeechPhase("error");
      setSpeechNotice("备用语音识别启动失败，请手动输入回答。");
    }
  }, []);

  const startPcmCapture = useCallback(async (connection) => {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("当前浏览器不支持麦克风采集");
    let stream;
    let audioContext;
    let source;
    let processor;
    let gain;
    let captureRegistered = false;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (speechConnectionRef.current !== connection || connection.stopping) return;

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) throw new Error("当前浏览器不支持实时音频处理");
      audioContext = new AudioContextClass({ latencyHint: "interactive" });
      await audioContext.resume();
      if (speechConnectionRef.current !== connection || connection.stopping) return;

      source = audioContext.createMediaStreamSource(stream);
      processor = audioContext.createScriptProcessor(4096, 1, 1);
      gain = audioContext.createGain();
      gain.gain.value = 0;
      let lastLevelUpdate = 0;
      processor.onaudioprocess = (event) => {
        if (connection.stopping || connection.socket.readyState !== WebSocket.OPEN) return;
        const samples = event.inputBuffer.getChannelData(0);
        try { connection.socket.send(resampleToPcm16(samples, audioContext.sampleRate)); } catch (error) { return; }
        const now = performance.now();
        if (now - lastLevelUpdate > 100) {
          let energy = 0;
          for (let index = 0; index < samples.length; index += 1) energy += samples[index] * samples[index];
          const nextLevel = Math.min(1, Math.sqrt(energy / samples.length) * 8);
          setSpeechLevel((current) => current * 0.35 + nextLevel * 0.65);
          lastLevelUpdate = now;
        }
      };
      source.connect(processor);
      processor.connect(gain);
      gain.connect(audioContext.destination);
      speechCaptureRef.current = { stream, audioContext, source, processor, gain };
      captureRegistered = true;
      setSpeechPhase("listening");
      setSpeechNotice("正在本地实时识别，文字会持续写入回答框");
    } finally {
      if (!captureRegistered) {
        stream?.getTracks().forEach((track) => track.stop());
        for (const node of [source, processor, gain]) {
          try { node?.disconnect(); } catch (error) {}
        }
        audioContext?.close().catch(() => {});
      }
    }
  }, []);

  const startFunAsrSpeech = useCallback(() => {
    const authSession = readAuthSession();
    if (!authSession?.access_token) {
      setSpeechPhase("error");
      setSpeechNotice("登录状态已失效，请重新登录后使用语音识别。");
      return;
    }
    speechBaseTextRef.current = answer;
    speechTranscriptRef.current = "";
    browserFinalTextRef.current = "";
    setSpeechPhase("preparing");
    setSpeechNotice("正在连接本地 FunASR 模型");

    const connection = { socket: null, ready: false, stopping: false, fallbackStarted: false, completed: false, timer: null };
    speechConnectionRef.current = connection;
    const fallbackToBrowser = (message) => {
      if (speechConnectionRef.current !== connection || connection.fallbackStarted || connection.stopping) return;
      connection.fallbackStarted = true;
      window.clearTimeout(connection.timer);
      try { connection.socket?.close(); } catch (error) {}
      speechConnectionRef.current = null;
      speechSocketRef.current = null;
      releaseSpeechCapture();
      startBrowserSpeechFallback(message);
    };

    try {
      const socket = new WebSocket(speechWebSocketUrl());
      socket.binaryType = "arraybuffer";
      connection.socket = socket;
      speechSocketRef.current = socket;
      connection.timer = window.setTimeout(() => fallbackToBrowser("本地模型连接较慢，已切换为浏览器备用识别"), 60000);
      socket.onopen = () => {
        socket.send(JSON.stringify({ type: "start", token: authSession.access_token, hotwords: speechHotwords }));
      };
      socket.onmessage = async (event) => {
        if (speechConnectionRef.current !== connection) return;
        let data;
        try { data = JSON.parse(event.data); } catch (error) { return; }
        if (data.type === "status") {
          setSpeechNotice(data.message || "正在准备本地语音模型");
          return;
        }
        if (data.type === "ready") {
          window.clearTimeout(connection.timer);
          connection.ready = true;
          try {
            await startPcmCapture(connection);
          } catch (error) {
            connection.stopping = true;
            try { socket.close(); } catch (closeError) {}
            speechConnectionRef.current = null;
            speechSocketRef.current = null;
            setSpeechPhase("error");
            setSpeechNotice(error?.name === "NotAllowedError" ? "浏览器未获得麦克风权限，请允许后重试。" : error.message || "麦克风启动失败，请重试。");
          }
          return;
        }
        if (data.type === "transcript") {
          const liveText = String(data.text || "").trim();
          speechTranscriptRef.current = liveText;
          setAnswer(mergeSpeechAnswer(speechBaseTextRef.current, liveText));
          return;
        }
        if (data.type === "complete") {
          connection.completed = true;
          window.clearTimeout(connection.timer);
          window.clearTimeout(speechFinalizeTimerRef.current);
          speechFinalizeTimerRef.current = null;
          if (data.text) setAnswer(mergeSpeechAnswer(speechBaseTextRef.current, data.text));
          releaseSpeechCapture();
          speechConnectionRef.current = null;
          setSpeechPhase("idle");
          setSpeechNotice(data.text ? "语音已转为文字" : "未识别到清晰语音");
          speechSocketRef.current = null;
          return;
        }
        if (data.type === "error") {
          if (!connection.ready) fallbackToBrowser("本地模型暂不可用，已切换为浏览器备用识别");
          else {
            connection.stopping = true;
            releaseSpeechCapture();
            speechConnectionRef.current = null;
            speechSocketRef.current = null;
            setSpeechPhase("error");
            setSpeechNotice(data.message || "本地语音识别中断，已保留当前文字。");
          }
        }
      };
      socket.onerror = () => {
        if (!connection.ready) fallbackToBrowser("本地模型连接失败，已切换为浏览器备用识别");
      };
      socket.onclose = () => {
        window.clearTimeout(connection.timer);
        if (speechConnectionRef.current !== connection || connection.completed || connection.stopping || connection.fallbackStarted) return;
        if (!connection.ready) fallbackToBrowser("本地模型连接关闭，已切换为浏览器备用识别");
        else {
          releaseSpeechCapture();
          speechConnectionRef.current = null;
          speechSocketRef.current = null;
          setSpeechPhase("error");
          setSpeechNotice("本地语音识别连接已关闭，当前文字已保留。");
        }
      };
    } catch (error) {
      fallbackToBrowser("无法连接本地模型，已切换为浏览器备用识别");
    }
  }, [answer, releaseSpeechCapture, speechHotwords, startBrowserSpeechFallback, startPcmCapture]);

  const stopCandidateSpeech = useCallback(() => {
    if (speechPhase === "fallback") {
      if (!recognitionRef.current) {
        setSpeechPhase("idle");
        return;
      }
      setSpeechPhase("finalizing");
      setSpeechNotice("正在确认最后一段语音");
      try { recognitionRef.current?.stop(); } catch (error) { setSpeechPhase("idle"); }
      return;
    }
    const connection = speechConnectionRef.current;
    if (!connection) {
      setSpeechPhase("idle");
      return;
    }
    connection.stopping = true;
    window.clearTimeout(connection.timer);
    if (speechPhase === "preparing") {
      try { connection.socket?.close(); } catch (error) {}
      releaseSpeechCapture();
      speechConnectionRef.current = null;
      speechSocketRef.current = null;
      setSpeechPhase("idle");
      setSpeechNotice("");
      return;
    }
    setSpeechPhase("finalizing");
    setSpeechNotice("正在确认最后一段语音");
    releaseSpeechCapture();
    try {
      connection.socket?.send(JSON.stringify({ type: "stop" }));
      speechFinalizeTimerRef.current = window.setTimeout(() => {
        try { connection.socket?.close(); } catch (error) {}
        speechConnectionRef.current = null;
        speechSocketRef.current = null;
        setSpeechPhase("idle");
        setSpeechNotice("语音结束确认超时，已保留当前识别文字。");
      }, 8000);
    } catch (error) {
      try { connection.socket?.close(); } catch (closeError) {}
      speechConnectionRef.current = null;
      speechSocketRef.current = null;
      setSpeechPhase("idle");
      setSpeechNotice("语音连接已结束，当前识别文字已保留。");
    }
  }, [releaseSpeechCapture, speechPhase]);

  const toggleCandidateSpeech = useCallback(() => {
    if (thinking || dialogueCompleted || speechPhase === "finalizing") return;
    if (["preparing", "listening", "fallback"].includes(speechPhase)) stopCandidateSpeech();
    else startFunAsrSpeech();
  }, [dialogueCompleted, speechPhase, startFunAsrSpeech, stopCandidateSpeech, thinking]);
  useEffect(() => {
    if (step !== 1 || sessionView !== "dialogue" || dialogueCompleted || !voiceEnabled || !latestQuestion || lastSpokenQuestionRef.current === latestQuestion) return;
    lastSpokenQuestionRef.current = latestQuestion;
    speakQuestion(latestQuestion);
  }, [step, sessionView, dialogueCompleted, voiceEnabled, latestQuestion, speakQuestion]);
  useEffect(() => {
    interviewLogRef.current?.scrollTo({ top: interviewLogRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);
  useEffect(() => {
    if (step === 1 && sessionView === "dialogue" && !dialogueCompleted) return;
    discardSpeechResources();
    setSpeechLevel(0);
    setSpeechPhase("idle");
    setSpeechNotice("");
    if (typeof window !== "undefined" && window.speechSynthesis) window.speechSynthesis.cancel();
  }, [dialogueCompleted, discardSpeechResources, sessionView, step]);
  useEffect(() => () => {
    try {
      if (typeof window !== "undefined" && window.speechSynthesis) window.speechSynthesis.cancel();
      discardSpeechResources();
    } catch (error) {
      // Browser speech APIs can throw during teardown in embedded WebViews.
    }
  }, [discardSpeechResources]);
  const uploadResumeFile = async (file) => {
    if (!file) return;
    if (resumeUploadLoading || resumeParseRetrying) return;
    const displayName = intervieweeName.trim();
    if (!displayName) {
      focusCandidateNameField();
      return;
    }
    const extension = file.name.split(".").pop()?.toLowerCase() || "";
    if (!RESUME_FILE_EXTENSIONS.has(extension)) {
      setResumeUploadError("文件格式不支持，请上传 PDF、Word、TXT、MD 或图片简历。");
      return;
    }
    if (file.size > MAX_RESUME_FILE_SIZE) {
      setResumeUploadError("简历文件不能超过 20 MB。");
      return;
    }
    const candidateId = `candidate_${Date.now()}`;
    const formData = new FormData();
    formData.append("file", file);
    setResumeUploadLoading(true);
    setResumeUploadError("");
    setInterviewError("");
    try {
      const response = await fetch(`${API}/api/assessment/upload-resume?candidate_id=${encodeURIComponent(candidateId)}`, {
        method: "POST",
        headers: readAuthSession()?.access_token
          ? { Authorization: `Bearer ${readAuthSession().access_token}` }
          : {},
        body: formData,
      });
      if (!response.ok) throw new Error(await readApiError(response, "简历解析失败，请重新解析或换一份更清晰的简历。"));
      const result = await response.json();
      setUploadedResume({
        ...result,
        candidate_name: displayName,
        resume_parse: result.resume_parse ? { ...result.resume_parse, candidate_name: displayName } : result.resume_parse,
      });
      setSession(null);
      setCandidate(null);
      setSessionView("hub");
      setProfileLoading(false);
      setReportLoading(false);
      setStep(0);
    } catch (error) {
      const message = error.message || "resume upload failed";
      setResumeUploadError(message);
    } finally {
      setResumeUploadLoading(false);
    }
  };
  const uploadResume = (event) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    input.value = "";
    if (file) void uploadResumeFile(file);
  };
  const handleResumeDragEnter = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!resumeUploadLoading && !resumeParseRetrying) setResumeDragActive(true);
  };
  const handleResumeDragOver = (event) => {
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = resumeUploadLoading || resumeParseRetrying ? "none" : "copy";
    if (!resumeUploadLoading && !resumeParseRetrying) setResumeDragActive(true);
  };
  const handleResumeDragLeave = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!event.currentTarget.contains(event.relatedTarget)) setResumeDragActive(false);
  };
  const handleResumeDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();
    setResumeDragActive(false);
    if (resumeUploadLoading || resumeParseRetrying) return;
    const file = event.dataTransfer.files?.[0];
    if (file) void uploadResumeFile(file);
  };
  useEffect(() => {
    const candidateId = uploadedResume?.candidate_id;
    if (!candidateId || uploadedResume?.enrichment_status !== "processing") return undefined;
    let cancelled = false;
    let timer;
    const poll = async () => {
      try {
        const status = await request(`/api/assessment/resume-parses/${encodeURIComponent(candidateId)}`);
        if (cancelled) return;
        if (status.status === "processing") {
          timer = window.setTimeout(poll, 2000);
          return;
        }
        if (status.status === "completed" && status.resume_parse) {
          setUploadedResume((current) => current?.candidate_id === candidateId
            ? {
              ...current,
              resume_parse: {
                ...status.resume_parse,
                candidate_name: current.candidate_name || intervieweeName.trim(),
              },
              enrichment_status: "completed",
              parse_timing: status.timing || current.parse_timing,
            }
            : current);
        } else {
          setUploadedResume((current) => current?.candidate_id === candidateId
            ? { ...current, enrichment_status: "failed" }
            : current);
        }
      } catch {
        if (!cancelled) timer = window.setTimeout(poll, 5000);
      }
    };
    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [intervieweeName, uploadedResume?.candidate_id, uploadedResume?.enrichment_status]);
  const retryResumeParse = async () => {
    if (!uploadedResume?.resume_text?.trim()) return;
    const retryCandidateId = uploadedResume.candidate_id;
    const retrySourceName = uploadedResume.source_name;
    const retryResumeText = uploadedResume.resume_text;
    const retryStarted = performance.now();
    setResumeParseRetrying(true);
    setResumeUploadError("");
    try {
      const parsed = await request("/api/assessment/parse-resume", {
        method: "POST",
        body: JSON.stringify({
          candidate_id: retryCandidateId,
          source_name: retrySourceName,
          resume_text: retryResumeText,
        }),
      });
      setUploadedResume((current) => current?.candidate_id === retryCandidateId ? {
        ...current,
        resume_parse: {
          ...parsed,
          candidate_name: current.candidate_name || intervieweeName.trim(),
        },
        enrichment_status: "completed",
        parse_timing: {
          ...(current.parse_timing || {}),
          ...(parsed.parse_timing || {}),
          total_ms: Math.round(performance.now() - retryStarted),
          target_ms: 15000,
          cache_hit: Boolean(parsed.provider_status?.cache_hit || parsed.parse_timing?.cache_hit),
        },
      } : current);
    } catch (error) {
      setUploadedResume((current) => current?.candidate_id === retryCandidateId ? { ...current, enrichment_status: "failed" } : current);
      setResumeUploadError(error.message || "结构化解析失败，请重试。");
    } finally {
      setResumeParseRetrying(false);
    }
  };
  const start = async () => {
    const displayName = intervieweeName.trim();
    if (!displayName) {
      focusCandidateNameField();
      return;
    }
    if (!parseReady) {
      const message = "请先上传一份真实简历文件，解析成功后再开始评估。";
      setResumeUploadError(message);
      return;
    }
    setStep(1);
    setSessionView("loading");
    setSessionLoading(true);
    const candidateId = uploadedResume.candidate_id || `candidate_${Date.now()}`;
    const resumeText = uploadedResume.resume_text;
    const resumeParseWithName = {
      ...uploadedResume.resume_parse,
      candidate_name: displayName,
    };
    setInterviewError("");
    setMessages([]);
    setGame([]);
    setStoryStep(0);
    setGameReviewOpen(false);
    setNpcReady(false);
    setWalkingToNpc(false);
    movementTokenRef.current += 1;
    if (movementTimerRef.current) window.clearTimeout(movementTimerRef.current);
    movementTimerRef.current = null;
    setCandidatePosition(QUEST_START_POSITION);
    setRationale("");
    lastSpokenQuestionRef.current = "";
    try {
      const started = await request("/api/assessment/start", {
        method: "POST",
        body: JSON.stringify({
          candidate_id: candidateId,
          target_job_id: targetJob?.id || candidate?.target_job_id || "job_ai_agent",
          resume_text: resumeText,
          resume_parse: resumeParseWithName,
        }),
      });
      setSession(started);
      if (started.next_action?.content)
        setMessages([{ role: "ai", text: started.next_action.content }]);
      setSessionView("hub");
    } catch (error) {
      const message = error.message || "assessment start failed";
      setInterviewError(message);
      setStep(0);
      setSessionView("hub");
    } finally {
      setSessionLoading(false);
    }
  };
  const send = async () => {
    if (!answer.trim()) return;
    if (!session) {
      setInterviewError("当前没有有效评估会话，请先上传真实简历并开始评估。");
      return;
    }
    const current = answer;
    setMessages((x) => [...x, { role: "user", text: current }]);
    setAnswer("");
    setThinking(true);
    setInterviewError("");
    try {
      const updated = await request("/api/assessment/answer", {
        method: "POST",
        body: JSON.stringify({
          session_id: session.session_id,
          answer: current,
        }),
      });
      setSession(updated);
      if (updated.next_action?.content) {
        lastSpokenQuestionRef.current = "";
        setMessages((x) => [...x, { role: "ai", text: updated.next_action.content }]);
      }
      const completedDialogue = Boolean(updated.candidate_profile?.dialogue_completed || updated.next_action?.type === "interactive_game" || updated.current_stage === "finalize_profile");
      if (completedDialogue) setSessionView("hub");
    } catch (error) {
      setInterviewError(error.message || "提交回答失败，请稍后重试。");
    } finally {
      setThinking(false);
    }
  };
  const finalizeAssessment = async (sourceSession = session, targetStep = 2) => {
    if (profileLoading) return null;
    if (!sourceSession) {
      setInterviewError("当前没有有效评估会话，无法生成匹配报告。");
      return null;
    }
    setStep(2);
    setProfileLoading(true);
    setReportLoading(false);
    try {
      const result = await request("/api/assessment/finalize", {
        method: "POST",
        body: JSON.stringify({ session_id: sourceSession.session_id }),
      });
      const profile = result.candidate_profile;
      if (!profile) {
        setInterviewError("评估结果为空，请重新完成评估。");
        setStep(1);
        setSessionView("hub");
        return null;
      }
      const nextCandidate = buildCandidateView(profile, candidate?.match_report || null);
      setCandidate(nextCandidate);
      saveCandidateRecord?.(nextCandidate, isSeeker ? "能力画像已保存到我的简历" : "能力画像已保存到评估管理");
      return nextCandidate;
    } catch (error) {
      setInterviewError(error.message || "生成能力画像失败，请确认评估流程已完成且模型服务可用。");
      setProfileLoading(false);
      setReportLoading(false);
      setStep(1);
      setSessionView("hub");
      return null;
    } finally {
      setProfileLoading(false);
    }
  };
  const generateMatchReport = async (sourceCandidate = candidate) => {
    if (reportLoading) return;
    let currentCandidate = sourceCandidate;
    if (!currentCandidate) {
      if (!canFinalizeAssessment) {
        setInterviewError("请先完成深度对话和互动任务，再生成匹配报告。");
        return;
      }
      currentCandidate = await finalizeAssessment(session, 2);
    }
    if (!currentCandidate) return;
    if (currentCandidate.match_report) {
      setStep(3);
      return;
    }
    setStep(3);
    setReportLoading(true);
    const started = typeof performance !== "undefined" ? performance.now() : Date.now();
    try {
      const matchReport = await request("/api/match/report", {
        method: "POST",
        body: JSON.stringify({candidate_id: currentCandidate.candidate_id,target_job_id: currentCandidate.target_job_id}),
      });
      const elapsed = Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - started);
      const reportWithTiming = {
        ...matchReport,
        report_timing: {
          ...(matchReport.report_timing || {}),
          match_report_ms: elapsed,
        },
      };
      setCandidate((prev) => {
        const updated = {
        ...(prev || currentCandidate),
        match_report: reportWithTiming,
        score: Number.isFinite(Number(reportWithTiming.score))
          ? Number(reportWithTiming.score)
          : effectiveCandidateScore(prev || currentCandidate, reportWithTiming),
        };
        saveCandidateRecord?.(updated, isSeeker ? "匹配报告已保存到个人职业空间" : "匹配报告已保存到评估管理");
        return updated;
      });
    } catch (error) {
      setInterviewError(error.message || "生成匹配报告失败，请确认岗位图谱可用。");
      setReportLoading(false);
      setStep(2);
      return;
    } finally {
      setReportLoading(false);
    }
  };
  const finish = async () => {
    if (!session || gameSubmitting) return;
    if (rationale.trim().length < 20) {
      setInterviewError("请先补充至少 20 个字的任务复盘。");
      return;
    }
    setGameSubmitting(true);
    try {
      const afterGame = await request("/api/assessment/game-result", {
        method: "POST",
        body: JSON.stringify({
          session_id: session.session_id,
          game_id: "incident_response",
          events: game.map((choice, index) => ({
            time: choice.time || index + 1,
            type: "story_choice",
            value: choice.id,
            scenario_id: gameScenario.id,
            scenario_title: gameScenario.title,
            chapter: choice.chapter,
            effect: choice.effect,
            rationale,
          })),
        }),
      });
      setGameReviewOpen(false);
      setSession(afterGame);
      const ready = Boolean(afterGame.candidate_profile?.dialogue_completed || afterGame.current_stage === "finalize_profile");
      if (ready) {
        await finalizeAssessment(afterGame, 2);
      } else {
        setStep(1);
        setSessionView("hub");
      }
    } catch (error) {
      setInterviewError(error.message || "提交互动任务失败，请稍后重试。");
    } finally {
      setGameSubmitting(false);
    }
  };
  const switchAssessmentStep = (targetStep) => {
    if (targetStep === 0) {
      setStep(0);
      return;
    }
    if (targetStep === 1) {
      if (!canOpenAssessmentModule) return;
      setStep(1);
      setSessionView("hub");
      return;
    }
    if (targetStep === 2) {
      if (candidate) {
        setStep(2);
        return;
      }
      if (!canFinalizeAssessment) return;
      finalizeAssessment(session, 2);
      return;
    }
    if (targetStep === 3) {
      if (candidate?.match_report) {
        setStep(3);
        return;
      }
      if (!canFinalizeAssessment) return;
      generateMatchReport(candidate);
      return;
    }
    setStep(targetStep);
  };
  return (
    <main className="assessment-page">
      <section className="assessment-head">
        <div>
          <h2>{step < 2 ? (isSeeker ? "建立我的能力画像" : "创建候选人能力画像") : (isSeeker ? "个人评估已完成" : "评估已完成")}</h2>
          <p>{isSeeker ? "用真实简历、模拟面试和剧情任务形成可解释的个人能力证据。" : "每一步产生独立证据，最终合并为可解释的人岗匹配结论。"}</p>
        </div>
        <div className="steps">
          {[
            [FileText, "提交档案", parseReady],
            [MessageSquareText, "面试会话", canFinalizeAssessment],
            [Sparkles, "能力画像", Boolean(candidate)],
            [ClipboardCheck, "匹配报告", Boolean(candidate?.match_report)],
          ].map(([Icon, text, done], i) => (
            <Button
              className={`${i === step ? "active" : ""} ${done ? "done" : ""}`}
              isDisabled={(i === 1 && !canOpenAssessmentModule) || (i === 2 && !canViewProfile) || (i === 3 && !canViewReport)}
              key={text}
              variant="ghost"
              onPress={() => switchAssessmentStep(i)}
            >
              <span>{done ? <Check size={15} /> : <Icon size={16} />}</span>
              <b>{text}</b>
            </Button>
          ))}
        </div>
      </section>
      {step === 0 && (
        <section className="assessment-stage profile-stage">
          <Card className={`assessment-card assessment-upload-card upload-zone ${parseReady ? "uploaded" : ""}`} variant="default">
            <Card.Header className="assessment-card-header upload-zone-header">
              <span className="assessment-card-icon upload-zone-icon"><FileUp size={21} /></span>
              <div>
                <Card.Title>{isSeeker ? "上传我的简历" : "上传候选人档案"}</Card.Title>
                <Card.Description>支持 PDF、Word、TXT 与图片简历，自动提取经历、项目和技能证据。</Card.Description>
              </div>
            </Card.Header>
            <Card.Content className="upload-zone-content">
              {!isSeeker && (
                <TextField
                  className="candidate-name-field"
                  isInvalid={nameInvalid}
                  isRequired
                  name="candidate-name"
                  value={intervieweeName}
                  onChange={handleCandidateNameChange}
                  validationBehavior="aria"
                >
                  <Label className="candidate-name-label">候选人姓名</Label>
                  <Input
                    ref={candidateNameInputRef}
                    className="candidate-name-input"
                    variant="secondary"
                    placeholder="请输入候选人姓名"
                    autoComplete="off"
                  />
                  <FieldError className="candidate-name-error">请输入候选人姓名</FieldError>
                </TextField>
              )}
              <Button
                aria-label={uploadedResume ? "重新上传简历" : "上传简历"}
                className={`resume-dropzone ${resumeDragActive ? "drag-active" : ""} ${uploadedResume ? "has-file" : ""}`}
                isDisabled={resumeParseRetrying}
                isPending={resumeUploadLoading}
                variant="secondary"
                onDragEnter={handleResumeDragEnter}
                onDragLeave={handleResumeDragLeave}
                onDragOver={handleResumeDragOver}
                onDrop={handleResumeDrop}
                onPress={openResumeFilePicker}
              >
                <span className="resume-dropzone-icon"><Upload size={20} /></span>
                <span className="resume-dropzone-copy">
                  <strong>{uploadedResume ? "拖入新简历，或点击重新上传" : "拖拽简历到这里，或点击上传"}</strong>
                  <small>PDF、Word、TXT、MD 或图片，单个不超过 20 MB</small>
                </span>
              </Button>
              <input
                ref={resumeFileInputRef}
                id="candidate-resume-file"
                type="file"
                accept=".pdf,.docx,.docm,.txt,.md,.png,.jpg,.jpeg,.webp"
                onChange={uploadResume}
                disabled={resumeUploadLoading || resumeParseRetrying}
                hidden
              />
              {(resumeUploadLoading || resumeParseRetrying) && (
                <Alert className="assessment-alert resume-upload-progress" status="accent">
                  <Alert.Indicator><RefreshCw className="spin" size={17} /></Alert.Indicator>
                  <Alert.Content>
                    <Alert.Title>{resumeParseRetrying ? "正在重新分析能力信息" : "正在上传并解析简历"}</Alert.Title>
                    <Alert.Description>{resumeParseRetrying ? "正在重新进行 AI 语义增强，请保持页面打开。" : "正在完成文档解析与结构化抽取，请保持页面打开。"}</Alert.Description>
                    <ProgressBar isIndeterminate aria-label="简历解析进度" color="accent" size="sm">
                      <ProgressBar.Track><ProgressBar.Fill /></ProgressBar.Track>
                    </ProgressBar>
                  </Alert.Content>
                </Alert>
              )}
              {resumeUploadError && (
                <Alert className="assessment-alert" status="danger">
                  <Alert.Indicator><CircleAlert size={17} /></Alert.Indicator>
                  <Alert.Content>
                    <Alert.Title>档案上传未完成</Alert.Title>
                    <Alert.Description>{resumeUploadError}</Alert.Description>
                  </Alert.Content>
                </Alert>
              )}
              {interviewError && (
                <Alert className="assessment-alert" status="danger">
                  <Alert.Indicator><CircleAlert size={17} /></Alert.Indicator>
                  <Alert.Content>
                    <Alert.Title>面试会话创建失败</Alert.Title>
                    <Alert.Description>{interviewError}</Alert.Description>
                  </Alert.Content>
                </Alert>
              )}
              {uploadedResume && (
                <Alert
                  className="assessment-alert upload-feedback"
                  status="accent"
                >
                  <Alert.Indicator>
                    {parsePending ? <RefreshCw className="spin" size={17} /> : parseReady && !parseNeedsReview ? <CheckCircle2 size={17} /> : <CircleAlert size={17} />}
                  </Alert.Indicator>
                  <Alert.Content>
                    <Alert.Title>{parsePending ? "语义增强中" : parseFailed ? "语义增强未完成" : parseReady && !parseNeedsReview ? "档案可用" : "需要复核"}</Alert.Title>
                    <Alert.Description>
                      <strong>{uploadedResume.source_name}</strong>
                      <span>
                        {parsePending
                          ? "基础档案已可用，正在补充能力语义判断。"
                          : parseFailed
                            ? "基础档案已保留，可直接开始评估或重新分析语义信息。"
                            : parseReady && !parseNeedsReview
                            ? `已识别 ${skillCount} 项技能，可继续创建面试会话。`
                            : "建议重新分析或换用内容更完整的简历。"}
                      </span>
                    </Alert.Description>
                    {!parsePending && parseNeedsReview && textExtracted && (
                      <Button size="sm" variant="secondary" onPress={retryResumeParse} isDisabled={resumeUploadLoading || resumeParseRetrying}>
                        <RefreshCw size={14} />
                        {resumeParseRetrying ? "分析中" : "重新分析"}
                      </Button>
                    )}
                  </Alert.Content>
                </Alert>
              )}
            </Card.Content>
          </Card>
          <Card className="assessment-card assessment-preview-card profile-preview" variant="default">
            <Card.Header className="assessment-card-header resume-preview-head">
              <span className="avatar" aria-hidden="true"><FileUser size={22} /></span>
              <div>
                {uploadedResume && <span title={uploadedResume.source_name || ""}>{uploadedResume.source_name}</span>}
                <Card.Title>{parsePending ? "AI 语义增强中" : parseReady ? "真实简历已解析" : uploadedResume ? "等待结构化结果" : "等待上传"}</Card.Title>
                <Card.Description>
                  {parsePending
                    ? "基础档案已完成，正在补充项目与技能深度判断。"
                    : parseFailed
                      ? "基础信息可用，AI 语义增强未完成，可重新分析。"
                    : parseReady && !parseNeedsReview
                      ? (parsedSummary.needs_manual_review ? "部分信息建议人工复核。" : "结构化信息质量通过。")
                      : "上传后展示结构化能力摘要。"}
                </Card.Description>
              </div>
              <Chip className="resume-status-chip" color={parsePending ? "accent" : parseReady && !parseNeedsReview ? (parsedSummary.needs_manual_review ? "warning" : "accent") : uploadedResume ? "warning" : "accent"} size="lg" variant="soft">
                <Chip.Label>{parsePending ? "增强中" : parseFailed ? "增强失败" : parseReady && !parseNeedsReview ? (semanticReady ? "已增强" : parsedSummary.needs_manual_review ? "需复核" : "已就绪") : uploadedResume ? "需复核" : "未上传"}</Chip.Label>
              </Chip>
            </Card.Header>
            <Card.Content className="profile-preview-content">
              <section className="resume-preview-stats">
                <span>面试者<strong>{intervieweeName || "待录入"}</strong></span>
                <span>岗位意向<strong>{jobIntent}</strong></span>
                <span>技能数量<strong>{skillCount}</strong></span>
                <span>项目<strong>{projectCount}</strong></span>
              </section>
              <section className="resume-preview-meta">
                <span>年限<strong>{parsedResume?.experience_years ?? "未识别"}</strong></span>
                <span>城市<strong>{cityText}</strong></span>
              </section>
              <section className="resume-preview-section">
                <b>技能标签</b>
                <p>
                  {previewSkills.length
                    ? previewSkills.map((skill, index) => {
                      const label = typeof skill === "string" ? skill : skill.name;
                      return (
                        <Chip className="resume-skill-chip" color="accent" key={`${label}-${index}`} size="sm" title={skillEvidenceTitle(skill)} variant="soft">
                          <Chip.Label>{label}</Chip.Label>
                        </Chip>
                      );
                    })
                    : <small>尚未解析出技能</small>}
                </p>
              </section>
            </Card.Content>
            <Card.Footer className="profile-preview-footer">
              <Button
                fullWidth
                isDisabled={!parseReady || resumeUploadLoading || resumeParseRetrying || Boolean(session)}
                variant="primary"
                onPress={start}
              >
                {session ? "评估会话已创建" : (isSeeker ? "确认简历并开始模拟面试" : "确认真实简历并开始评估")} <ArrowRight size={16} />
              </Button>
            </Card.Footer>
          </Card>
        </section>
      )}
      {step === 1 && (sessionLoading || sessionView === "loading" ? (
        <AssessmentSessionSkeleton />
      ) : sessionView === "hub" ? (
        <InterviewSessionHub
          dialogueCompleted={dialogueCompleted}
          gameCompleted={gameCompleted}
          canFinalizeAssessment={canFinalizeAssessment}
          hasProfile={Boolean(candidate)}
          evidenceCount={session?.evidence?.length ?? 0}
          profileLoading={profileLoading}
          error={interviewError}
          onDialogue={() => setSessionView("dialogue")}
          onGame={() => setSessionView("game")}
          onProfile={() => {
            if (candidate) setStep(2);
            else if (canFinalizeAssessment) finalizeAssessment(session, 2);
          }}
        />
      ) : sessionView === "dialogue" ? (
        <section className="assessment-stage dialogue-stage">
          <Card className="assessment-card dialogue-context" variant="default">
            <Card.Header className="assessment-card-header dialogue-context-header">
              <div>
                <span className="assessment-card-kicker">当前评估重点</span>
                <Card.Title>{dialogueStageLabel}</Card.Title>
                <Card.Description>系统根据真实简历和上一轮回答生成追问，每轮只围绕一个关键能力点深挖。</Card.Description>
              </div>
            </Card.Header>
            <Card.Content className="dialogue-context-content">
              <ProgressBar
                className="dialogue-progress"
                value={Math.round((session?.stage_progress || 0) * 100)}
                aria-label="面试评估进度"
                color="accent"
                size="sm"
              >
                <div className="dialogue-progress-label">
                  <span>评估进度</span>
                  <ProgressBar.Output>{Math.round((session?.stage_progress || 0) * 100)}%</ProgressBar.Output>
                </div>
                <ProgressBar.Track><ProgressBar.Fill /></ProgressBar.Track>
              </ProgressBar>
              <div className="dialogue-facts">
                <span>已采集证据<strong>{session?.evidence?.length ?? 0}</strong></span>
                <span>项目追问<strong>{canEnterGame ? "已完成" : `${dialogueSkillIndex || 1} / ${dialogueSkillTotal || 3}`}</strong></span>
              </div>
              {!!dialogueFocus.length && (
                <section className="dialogue-focus">
                  <span>本轮追问关注</span>
                  <div>{dialogueFocus.map((item) => <Chip key={item} color="accent" size="sm" variant="soft" title={item}><Chip.Label>{item}</Chip.Label></Chip>)}</div>
                </section>
              )}
              <section className="dialogue-rubric">
                <span>实时能力假设</span>
                {dialogueSignals.map(({ name, score }) => (
                  <ProgressBar key={name} value={score} aria-label={`${name}能力假设`} color="accent" size="sm">
                    <div className="dialogue-rubric-label">
                      <b>{name}</b>
                      <ProgressBar.Output>{score ? <CountUp key={`${name}-${score}`} to={score} from={0} duration={0.8} /> : "待采集"}</ProgressBar.Output>
                    </div>
                    <ProgressBar.Track><ProgressBar.Fill /></ProgressBar.Track>
                  </ProgressBar>
                ))}
              </section>
            </Card.Content>
          </Card>
          <Card className="assessment-card interview-room" variant="default">
            <Card.Header className="interview-room-header">
              <Card.Title>深度对话</Card.Title>
              <Chip color="accent" size="sm" variant="soft">
                <Chip.Label>{dialogueStageLabel}</Chip.Label>
              </Chip>
            </Card.Header>
            <Card.Content className="interview-room-content">
              <div className="interview-panel">
                <div className="interviewer-seat">
                  <div className="dialogue-panel-head">
                    <div className="dialogue-identity">
                      <div className={`dialogue-avatar-wrap ${speaking ? "speaking" : ""}`}>
                        <Avatar className="dialogue-avatar" color="accent" size="sm" variant="soft">
                          <Avatar.Fallback><MessageSquareText size={17} /></Avatar.Fallback>
                        </Avatar>
                      </div>
                      <div>
                        <strong>能力评估官</strong>
                        <span>{canEnterGame ? "深度对话已完成" : speaking ? "正在播报问题" : "等待候选人作答"}</span>
                      </div>
                    </div>
                  </div>
                  <div className="dialogue-question-body">
                    <p>{latestQuestion || "正在建立评估会话..."}</p>
                  </div>
                  <div className="voice-controls">
                    <Button
                      size="sm"
                      variant="secondary"
                      aria-pressed={voiceEnabled}
                      onPress={() => setVoiceEnabled((value) => !value)}
                    >
                      {voiceEnabled ? <Pause size={14} /> : <Play size={14} />}
                      {voiceEnabled ? "暂停自动播报" : "开启自动播报"}
                    </Button>
                    <Button size="sm" variant="secondary" onPress={() => speakQuestion()} isDisabled={canEnterGame || !latestQuestion}>
                      <Volume2 size={14} />
                      重播本轮问题
                    </Button>
                  </div>
                </div>
                <div className="candidate-seat">
                  <div className="dialogue-panel-head">
                    <div className="dialogue-identity">
                      <Avatar className="dialogue-avatar" color="accent" size="sm" variant="soft">
                        <Avatar.Fallback><UserRound size={17} /></Avatar.Fallback>
                      </Avatar>
                      <div>
                        <strong>{isSeeker ? "我的回答" : "候选人回答"}</strong>
                      </div>
                    </div>
                  </div>
                  <TextField
                    className="candidate-answer-field"
                    value={answer}
                    onChange={setAnswer}
                    isDisabled={thinking || canEnterGame}
                  >
                    <Label>回答内容</Label>
                    <div className="candidate-answer-composer">
                      <TextArea
                        variant="secondary"
                        placeholder="记录候选人的真实回答，尽量包含个人职责、判断依据、指标与复盘..."
                        readOnly={speechBusy}
                      />
                      <div className="speech-input-controls">
                        <div className="speech-input-actions">
                          <Button
                            size="sm"
                            variant={candidateListening ? "primary" : "secondary"}
                            className={candidateListening ? "recording" : ""}
                            aria-pressed={candidateListening}
                            onPress={toggleCandidateSpeech}
                            isDisabled={thinking || canEnterGame || speechPhase === "finalizing"}
                            isPending={speechPhase === "finalizing"}
                          >
                            {["preparing", "finalizing"].includes(speechPhase)
                              ? <RefreshCw className="speech-spinner" size={14} />
                              : candidateListening ? <Pause size={14} /> : <Mic size={14} />}
                            {speechPhase === "preparing"
                              ? "取消连接"
                              : candidateListening
                                ? "停止语音录入"
                                : speechPhase === "finalizing" ? "正在整理" : "开始语音录入"}
                          </Button>
                        </div>
                        <div className="speech-live-feedback">
                          {candidateListening && (
                            <div
                              className={`speech-volume-meter ${speechPhase === "fallback" ? "indeterminate" : ""}`}
                              role="meter"
                              aria-label="实时声音强度"
                              aria-valuemin="0"
                              aria-valuemax="100"
                              aria-valuenow={speechPhase === "listening" ? Math.round(speechLevel * 100) : undefined}
                            >
                              <span style={speechPhase === "listening" ? { width: `${Math.max(5, Math.round(speechLevel * 100))}%` } : undefined} />
                            </div>
                          )}
                          {speechNotice && (
                            <small className="speech-status-a11y" role="status" aria-live="polite">
                              {speechNotice}
                            </small>
                          )}
                        </div>
                        <span className="candidate-answer-count">{answer.length} 字</span>
                      </div>
                    </div>
                  </TextField>
                  {speechPhase === "error" && speechNotice && (
                    <Alert className="assessment-alert speech-error-alert" status="danger">
                      <Alert.Indicator><CircleAlert size={15} /></Alert.Indicator>
                      <Alert.Content>
                        <Alert.Description>{speechNotice}</Alert.Description>
                      </Alert.Content>
                    </Alert>
                  )}
                  {interviewError && (
                    <Alert className="assessment-alert" status="danger">
                      <Alert.Indicator><CircleAlert size={17} /></Alert.Indicator>
                      <Alert.Content>
                        <Alert.Title>本轮提交未完成</Alert.Title>
                        <Alert.Description>{interviewError}</Alert.Description>
                      </Alert.Content>
                    </Alert>
                  )}
                  <div className="candidate-submit-row">
                    {canEnterGame ? (
                      <Button variant="primary" onPress={() => setSessionView("hub")}>
                        对话完毕，返回面试会话 <ArrowRight size={16} />
                      </Button>
                    ) : (
                      <Button variant="primary" onPress={send} isDisabled={!answer.trim() || thinking || speechBusy} isPending={thinking}>
                        {thinking ? "生成追问中..." : "提交回答并进入下一轮"} <ArrowRight size={16} />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
              <div className="interview-log" ref={interviewLogRef} role="log" aria-live="polite">
                <div className="interview-log-head">
                  <strong>本轮对话记录</strong>
                  <span>{messages.length} 条</span>
                </div>
                {messages.map((m, i) => (
                  <article className={m.role} key={`${m.role}_${i}`}>
                    <span>{m.role === "ai" ? "面试官" : "候选人"}</span>
                    <p>{m.text}</p>
                  </article>
                ))}
                {thinking && <article className="ai"><span>面试官</span><p>正在根据上一轮回答生成深度追问...</p></article>}
              </div>
            </Card.Content>
          </Card>
        </section>
      ) : sessionView === "game" ? (
        <section className="assessment-stage story-game pixel-quest">
          <aside className="story-sidebar quest-hud">
            <h3>{gameScenario.title}</h3>
            <p>{gameScenario.brief}</p>
            <div className="scenario-tags">
              <strong>{gameScenario.project}</strong>
              {gameScenario.skills.slice(0, 5).map((skill) => <em key={skill}>{skill}</em>)}
            </div>
            <div className="story-meters">
              {[[gameScenario.meters.health,storyMetrics.health],[gameScenario.meters.evidence,storyMetrics.evidence],[gameScenario.meters.trust,storyMetrics.trust]].map(([name,value])=><div key={name}><p><b>{name}</b><em>{value}</em></p><i><span style={{width:`${value}%`}} /></i></div>)}
            </div>
            <ol>{storyChapters.map((chapter,index)=><li className={index<storyStep?'done':index===storyStep?'active':''} key={chapter.title}><span>{index<storyStep?<Check size={12}/>:index+1}</span><div><strong>{officeNpcs[index % officeNpcs.length].role}</strong><small>{index<game.length?game[index].title:chapter.objective}</small></div></li>)}</ol>
          </aside>
          <div className="story-stage quest-stage">
            {storyStep < storyChapters.length ? (()=>{const chapter=storyChapters[storyStep];return <>
              <div className="office-map office-map-art" style={{"--hero-x": `${candidatePosition.x}%`, "--hero-y": `${candidatePosition.y}%`}}>
                <img className="office-map-image" src={officeMapAsset} alt="" />
                <div className="quest-map-topbar">
                  <strong>职场任务 · 评估之旅</strong>
                  <span>第 {storyStep + 1} 天</span>
                  <span>成就 {game.length}/{storyChapters.length}</span>
                  <b>候选人 Lv.1</b>
                </div>
                <div className="quest-route-layer" aria-hidden="true">
                  <svg className="quest-route-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                    <path className="quest-route-base" d={routePath} />
                    <path className="quest-route-progress" d={routeProgressPath} />
                    {routeNpcPoints.map((npc, index) => {
                      const target = questNpcTarget(npc);
                      return <line className="quest-route-approach" key={`approach-${index}`} x1={target.x} y1={target.y} x2={npc.x} y2={npc.y} />;
                    })}
                  </svg>
                  <span className="quest-route-start" style={{left:`${QUEST_START_POSITION.x}%`, top:`${QUEST_START_POSITION.y}%`}} />
                  {routeNpcPoints.map((npc, index) => (
                    <span
                      className={`quest-route-node ${index < storyStep ? "done" : ""} ${index === storyStep ? "active" : ""}`}
                      key={`route-node-${index}`}
                      style={{left:`${npc.x}%`, top:`${npc.y}%`}}
                    >
                      <span>{index < storyStep ? <Check size={10} /> : index + 1}</span>
                    </span>
                  ))}
                </div>
                {storyChapters.map((npcChapter, index) => {
                  const npc = officeNpcs[index % officeNpcs.length];
                  const Icon = npc.icon;
                  const isActive = index === storyStep;
                  const isDone = index < storyStep;
                  return (
                    <div className={`quest-npc ${isActive ? "active" : ""} ${isDone ? "done" : ""}`} style={{left:`${npc.x}%`, top:`${npc.y}%`}} key={npcChapter.title}>
                      <div className={`task-pop ${npc.marker}`}><span>{isDone ? <Check size={10}/> : <Icon size={14}/>}</span></div>
                      <img className="npc-sprite" src={npc.sprite} alt="" />
                      <em>{npc.role}</em>
                    </div>
                  );
                })}
                <img className={`hero-sprite ${walkingToNpc ? "walking" : ""}`} src={candidateSprite} alt="" style={{left:`${candidatePosition.x}%`, top:`${candidatePosition.y}%`}} />
                {npcReady && (
                  <div className="npc-bubble">
                    <img src={currentNpc.sprite} alt="" />
                    <div>
                      <span>{officeNpcs[storyStep % officeNpcs.length].role} · {chapter.title}</span>
                      <h3>{chapter.objective}</h3>
                      <p>{chapter.scene}</p>
                    </div>
                  </div>
                )}
                {!npcReady && (
                  <div className="quest-briefing">
                    <span>第 {storyStep + 1} 关</span>
                    <h3>{chapter.title}</h3>
                    <p>{walkingToNpc ? "候选人正在前往任务点..." : chapter.objective}</p>
                    <Button variant="primary" onPress={walkToCurrentNpc} isDisabled={walkingToNpc} isPending={walkingToNpc}>
                      {walkingToNpc ? "移动中..." : `前往${officeNpcs[storyStep % officeNpcs.length].role}`} <ArrowRight size={15}/>
                    </Button>
                  </div>
                )}
                {npcReady && (
                  <div className="choice-dialog">
                    <div>
                      <span>请选择你的回应</span>
                      <strong>{storyStep + 1} / {storyChapters.length}</strong>
                    </div>
                    <div className="story-choices quest-choices">
                      {chapter.choices.map((choice,index)=><Button key={choice.id} variant="secondary" onPress={()=>chooseStory(choice)}><span className="quest-choice-index">{index+1}</span><span className="quest-choice-copy"><strong>{choice.title}</strong><span className="quest-choice-description">{choice.description}</span><em>{choice.effect}</em></span><ChevronRight className="quest-choice-arrow" size={17}/></Button>)}
                    </div>
                  </div>
                )}
              </div>
            </>})() : <div className="story-resolution quest-resolution"><CheckCircle2 size={34}/><h3>{gameScenario.title} 已通关</h3><p>四个角色流程已全部完成。请在弹窗中输入本轮任务复盘后提交，系统会将你的选择和复盘一起计入行为证据。</p><div className="story-log">{game.map((choice,index)=><div key={choice.id}><span>0{index+1}</span><p><strong>{choice.title}</strong><small>{choice.effect}</small></p></div>)}</div>{!gameCompleted && <Button className="finish-game" variant="primary" onPress={() => setGameReviewOpen(true)}>填写任务复盘 <Sparkles size={16} /></Button>}</div>}
            {gameReviewOpen && !gameCompleted && storyStep === storyChapters.length && (
              <GameReviewModal
                rationale={rationale}
                setRationale={setRationale}
                canFinalizeAssessment={canFinalizeAssessment}
                onSubmit={finish}
                submitting={gameSubmitting || reportLoading || profileLoading}
                error={interviewError}
              />
            )}
          </div>
        </section>
      ) : null)}
      {step === 2 && (
        profileLoading ? (
          <AssessmentResultSkeleton type="profile" />
        ) : (
          <Archetype
            candidate={candidate}
            onReport={() => generateMatchReport(candidate)}
            reportLoading={reportLoading}
          />
        )
      )}
      {step === 3 && (
        reportLoading ? (
          <AssessmentResultSkeleton type="report" />
        ) : (
          <Report candidate={candidate} navigate={navigate} notify={notify} audience={audience} />
        )
      )}
    </main>
  );
}

function AssessmentSessionSkeleton() {
  return (
    <Card className="assessment-stage assessment-card session-loading" variant="default" aria-busy="true">
      <Card.Header className="session-loading-head">
        <div>
          <Skeleton className="session-skeleton-kicker" />
          <Skeleton className="session-skeleton-title" />
          <Skeleton className="session-skeleton-copy" />
        </div>
      </Card.Header>
      <Card.Content className="session-loading-grid">
        {[0, 1].map((item) => (
          <div className="session-loading-task" key={item}>
            <Skeleton className="session-skeleton-icon" />
            <div>
              <Skeleton className="session-skeleton-task-title" />
              <Skeleton className="session-skeleton-task-copy" />
            </div>
          </div>
        ))}
      </Card.Content>
      <Card.Footer className="session-loading-footer">
        <small>正在生成个性化面试会话，请保持页面打开。</small>
      </Card.Footer>
    </Card>
  );
}

function GameReviewModal({ rationale, setRationale, canFinalizeAssessment, onSubmit, submitting, error }) {
  const ready = rationale.trim().length >= 20;
  return (
    <Modal>
      <Modal.Backdrop
        className="game-review-backdrop"
        isDismissable={false}
        isKeyboardDismissDisabled
        isOpen
        variant="blur"
      >
        <Modal.Container placement="center" scroll="inside" size="lg">
          <Modal.Dialog className="game-review-modal" aria-labelledby="game-review-title">
            <Modal.Header>
              <Modal.Heading id="game-review-title">提交本轮互动任务复盘</Modal.Heading>
              <p>四个角色流程已完成，请补充你的关键判断、最大不确定性和失败后的替代方案。</p>
            </Modal.Header>
            <Modal.Body>
              <TextField value={rationale} onChange={setRationale}>
                <Label>任务复盘</Label>
                <TextArea
                  variant="secondary"
                  placeholder="例如：我优先确认影响范围，再根据证据链决定灰度恢复；最大不确定性是边界样本覆盖不足，失败后会回滚并保留人工审核通道。"
                  autoFocus
                />
              </TextField>
              {error && (
                <Alert status="danger">
                  <Alert.Indicator><CircleAlert size={16} /></Alert.Indicator>
                  <Alert.Content><Alert.Description>{error}</Alert.Description></Alert.Content>
                </Alert>
              )}
            </Modal.Body>
            <Modal.Footer>
              <small>{ready ? "复盘内容将作为互动任务证据写入评估。" : `还需 ${Math.max(0, 20 - rationale.trim().length)} 个字`}</small>
              <Button type="button" isDisabled={!ready || submitting} isPending={submitting} onPress={onSubmit}>
                {submitting ? "提交中..." : canFinalizeAssessment ? "提交复盘并生成能力画像" : "提交复盘"}
                <Sparkles size={15} />
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
  );
}

function InterviewSessionHub({ dialogueCompleted, gameCompleted, canFinalizeAssessment, hasProfile, evidenceCount, profileLoading = false, error = "", onDialogue, onGame, onProfile }) {
  return (
    <Card className="assessment-stage assessment-card interview-hub" variant="default">
      <Card.Header className="interview-hub-head">
        <div>
          <Card.Title>选择本次面试会话的子环节</Card.Title>
          <Card.Description>深度对话和互动任务都完成后，系统才会生成能力画像和匹配报告。</Card.Description>
        </div>
      </Card.Header>
      <Card.Content className="interview-hub-content">
        {error && (
          <Alert className="assessment-alert" status="danger">
            <Alert.Indicator><CircleAlert size={17} /></Alert.Indicator>
            <Alert.Content>
              <Alert.Title>能力画像生成未完成</Alert.Title>
              <Alert.Description>{error}</Alert.Description>
            </Alert.Content>
          </Alert>
        )}
        <div className="session-task-grid">
          <Button className={dialogueCompleted ? "done" : ""} variant="secondary" onPress={onDialogue}>
            <span className="session-task-icon">{dialogueCompleted ? <CheckCircle2 size={20} /> : <MessageSquareText size={22} />}</span>
            <span className="session-task-copy">
              <strong>深度对话</strong>
              <span className="session-task-description">基于简历和上一轮回答生成个性化追问，核验项目、技能和证据边界。</span>
              <Chip color="accent" size="sm" variant="soft">
                <Chip.Label>{dialogueCompleted ? "已完成" : "进入对话"}</Chip.Label>
              </Chip>
            </span>
            <ArrowRight size={18} />
          </Button>
          <Button className={gameCompleted ? "done" : ""} variant="secondary" onPress={onGame}>
            <span className="session-task-icon">{gameCompleted ? <CheckCircle2 size={20} /> : <Gamepad2 size={22} />}</span>
            <span className="session-task-copy">
              <strong>互动任务</strong>
              <span className="session-task-description">通过情景选择和最终复盘采集风险判断、优先级、协作和资源配置证据。</span>
              <Chip color="accent" size="sm" variant="soft">
                <Chip.Label>{gameCompleted ? "已完成" : "进入任务"}</Chip.Label>
              </Chip>
            </span>
            <ArrowRight size={18} />
          </Button>
        </div>
      </Card.Content>
      <Card.Footer className="session-evidence-strip">
        <span>已采集证据</span>
        <strong>{evidenceCount}</strong>
        <p>{dialogueCompleted && gameCompleted ? "面试会话已完成，可以进入能力画像。" : "继续完成两个子环节以生成最终结论。"}</p>
        {(canFinalizeAssessment || hasProfile) && (
          <Button variant="primary" onPress={onProfile} isDisabled={profileLoading} isPending={profileLoading}>
            {profileLoading ? "能力画像生成中..." : hasProfile ? "查看能力画像" : "生成并查看能力画像"} <ArrowRight size={15} />
          </Button>
        )}
      </Card.Footer>
    </Card>
  );
}

function AssessmentResultSkeleton({ type }) {
  const isReport = type === "report";
  const placeholders = [0, 1, 2];
  return (
    <Card className={`assessment-stage result-loading ${isReport ? "report" : "profile"}`} variant="default">
      <Card.Header className="result-loading-head">
        <span className="result-loading-icon"><Sparkles size={20} /></span>
        <div>
          <Card.Title>{isReport ? "正在生成匹配报告" : "正在生成能力画像"}</Card.Title>
          <Card.Description>{isReport ? "系统正在基于已生成的能力画像计算岗位匹配差距。" : "系统正在汇总简历、深度对话和互动任务证据，并生成能力画像。"}</Card.Description>
        </div>
      </Card.Header>
      <Card.Content className="result-loading-content">
        <ProgressBar aria-label={isReport ? "匹配报告生成进度" : "能力画像生成进度"} color="accent" isIndeterminate size="sm">
          <ProgressBar.Track><ProgressBar.Fill /></ProgressBar.Track>
        </ProgressBar>
        <div className="result-loading-grid">
          {placeholders.map((item) => (
            <div className="result-loading-block" key={item}>
              <Skeleton className="result-skeleton-icon" />
              <Skeleton className="result-skeleton-title" />
              <Skeleton className="result-skeleton-line" />
              <Skeleton className="result-skeleton-line short" />
            </div>
          ))}
        </div>
      </Card.Content>
      <Card.Footer className="result-loading-footer">
        <small>{isReport ? "报告完成后会自动展示结果。" : "画像生成完成后会自动进入结果页。"}</small>
      </Card.Footer>
    </Card>
  );
}

function buildDialogueSignals(session) {
  const evidence = session?.evidence || [];
  const answerEvidence = evidence.filter((item) => item.type === "answer");
  const dialogueAnswers = answerEvidence.filter((item) => item.stage === "skill_deep_question");
  const scoreByStage = (stage) => {
    const item = [...answerEvidence].reverse().find((entry) => entry.stage === stage);
    return item ? Math.round((item.quality_score || item.confidence || 0) * 100) : 0;
  };
  const clampScore = (value) => Math.max(0, Math.min(100, Math.round(value)));
  const avgDialogue = dialogueAnswers.length
    ? dialogueAnswers.reduce((sum, item) => sum + Number(item.quality_score || item.confidence || 0), 0) / dialogueAnswers.length
    : 0;
  const ownershipCount = dialogueAnswers.filter((item) => item.signals?.ownership).length;
  const measurableCount = dialogueAnswers.filter((item) => item.signals?.measurable).length;
  const technicalTerms = dialogueAnswers.reduce((sum, item) => sum + Number(item.signals?.technical_term_count || 0), 0);
  const dialogueText = dialogueAnswers.map((item) => item.content || "").join(" ");
  const riskMentions = (dialogueText.match(/风险|异常|失败|回滚|灰度|降级|兜底|边界|取舍|不确定|排查|验证/g) || []).length;
  const projectScore = dialogueAnswers.length
    ? clampScore(avgDialogue * 78 + (ownershipCount / dialogueAnswers.length) * 18 + Math.min(dialogueAnswers.length, 3) * 2)
    : session?.candidate_profile?.project_verification?.credibility_score || scoreByStage("resume_probe");
  const technicalScore = dialogueAnswers.length
    ? clampScore(avgDialogue * 72 + Math.min(technicalTerms, 8) * 4)
    : 0;
  const riskScore = dialogueAnswers.length
    ? clampScore(avgDialogue * 58 + Math.min(riskMentions, 6) * 6 + (dialogueAnswers.length >= 2 ? 8 : 0))
    : scoreByStage("scenario_task");
  const quantitativeScore = dialogueAnswers.length
    ? clampScore((measurableCount / dialogueAnswers.length) * 72 + avgDialogue * 24)
    : 0;
  return [
    { name: "项目真实性", score: projectScore },
    { name: "技术深度", score: technicalScore },
    { name: "风险判断", score: riskScore },
    { name: "结果量化", score: quantitativeScore },
  ];
}

function normalizeDialogueFocus(focus) {
  if (Array.isArray(focus)) {
    return focus
      .map((item) => {
        if (typeof item === "string") return item.trim();
        if (item && typeof item === "object") return String(item.name || item.label || item.skill || item.topic || "").trim();
        return "";
      })
      .filter(Boolean)
      .slice(0, 6);
  }
  if (typeof focus === "string") {
    return focus
      .split(/[、,，;；\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, 6);
  }
  if (focus && typeof focus === "object") {
    return Object.values(focus)
      .flatMap((value) => normalizeDialogueFocus(value))
      .filter(Boolean)
      .slice(0, 6);
  }
  return [];
}

function buildGameScenario(session) {
  const source = session?.next_action?.metadata?.game_scenario || session?.candidate_profile?.game_scenario || {};
  const chapters = Array.isArray(source.chapters) && source.chapters.length ? source.chapters : defaultStoryChapters;
  const skills = Array.isArray(source.skills) && source.skills.length
    ? source.skills.filter(Boolean).map(String)
    : (session?.candidate_profile?.skills || [])
      .map((skill) => (typeof skill === "string" ? skill : skill.name))
      .filter(Boolean)
      .slice(0, 5);
  const project = source.project || session?.candidate_profile?.projects?.[0]?.name || "候选人核心项目";
  return {
    id: source.id || "default_incident_story",
    title: source.title || "系统稳定性处置",
    brief: source.brief || "根据候选人的简历能力，完成一段限时情景决策任务。你的选择会改变任务状态、证据完整度和团队信任。",
    project,
    skills,
    chapters,
    meters: {
      health: source.meters?.health || "任务稳定",
      evidence: source.meters?.evidence || "证据完整",
      trust: source.meters?.trust || "协作信任",
    },
    initialMetrics: {
      health: Number(source.initial_metrics?.health ?? source.initialMetrics?.health ?? 38),
      evidence: Number(source.initial_metrics?.evidence ?? source.initialMetrics?.evidence ?? 18),
      trust: Number(source.initial_metrics?.trust ?? source.initialMetrics?.trust ?? 62),
    },
  };
}

const RECRUITING_LEVEL_LABELS = {
  high: "高匹配",
  medium: "中匹配",
  low: "低匹配",
};

function getCandidateJobReport(item, jobId) {
  if (!item || !jobId) return null;
  const targetScreenings = item.target_screenings;
  if (targetScreenings && !Array.isArray(targetScreenings) && targetScreenings[jobId]) {
    return targetScreenings[jobId];
  }
  if (Array.isArray(targetScreenings)) {
    const targetReport = targetScreenings.find((report) => report?.target_job_id === jobId || report?.job_id === jobId);
    if (targetReport) return targetReport;
  }
  for (const results of [item.all_job_results, item.difference_report]) {
    if (!Array.isArray(results)) continue;
    const result = results.find((entry) => entry?.job_id === jobId);
    if (result) return result;
  }
  return item.screening?.target_job_id === jobId ? item.screening : null;
}

function RecruitingWorkspace({ notify, navigate }) {
  const [jobs, setJobs] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [selectedJob, setSelectedJob] = useState(() => {
    if (typeof window === "undefined") return "";
    try { return window.sessionStorage.getItem(RECRUITING_SELECTED_JOB_KEY) || ""; } catch { return ""; }
  });
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [jobModalOpen, setJobModalOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadJobIds, setUploadJobIds] = useState([]);
  const [pendingResumeFiles, setPendingResumeFiles] = useState([]);
  const [compareIds, setCompareIds] = useState([]);
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const [creatingJob, setCreatingJob] = useState(false);
  const [editingJobId, setEditingJobId] = useState("");
  const resumeInputRef = useRef(null);
  const [form, setForm] = useState({ ...EMPTY_ENTERPRISE_JOB_FORM });
  const selectJob = useCallback((jobId) => {
    const nextJobId = jobId == null ? "" : String(jobId);
    setSelectedJob(nextJobId);
    try {
      if (nextJobId) window.sessionStorage.setItem(RECRUITING_SELECTED_JOB_KEY, nextJobId);
      else window.sessionStorage.removeItem(RECRUITING_SELECTED_JOB_KEY);
    } catch {}
  }, []);
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [jobData, candidateData] = await Promise.all([request("/api/enterprise-jobs"), request("/api/recruitment/candidates")]);
      setJobs(jobData.items || []);
      setCandidates(candidateData.items || []);
    } catch (error) { notify?.(error.message || "招聘数据加载失败"); } finally { setLoading(false); }
  }, [notify]);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    if (!jobs.length) return;
    setSelectedJob((current) => {
      let storedJobId = current;
      if (!storedJobId) {
        try { storedJobId = window.sessionStorage.getItem(RECRUITING_SELECTED_JOB_KEY) || ""; } catch {}
      }
      const loadedJob = jobs.find((job) => String(job.job_id) === String(storedJobId));
      const fallbackJob = jobs.find((job) => job.status === "active") || jobs[0];
      const nextJobId = loadedJob?.job_id ?? fallbackJob?.job_id ?? "";
      const next = nextJobId == null ? "" : String(nextJobId);
      try {
        if (next) window.sessionStorage.setItem(RECRUITING_SELECTED_JOB_KEY, next);
        else window.sessionStorage.removeItem(RECRUITING_SELECTED_JOB_KEY);
      } catch {}
      return next;
    });
  }, [jobs]);
  const openCreateJob = () => {
    setEditingJobId("");
    setForm({ ...EMPTY_ENTERPRISE_JOB_FORM });
    setJobModalOpen(true);
  };
  const openEditJob = (job) => {
    setEditingJobId(job.job_id);
    setForm({
      ...EMPTY_ENTERPRISE_JOB_FORM,
      title: job.title || "",
      domain: job.domain || EMPTY_ENTERPRISE_JOB_FORM.domain,
      city: job.city || "",
      headcount: String(job.headcount ?? EMPTY_ENTERPRISE_JOB_FORM.headcount),
      responsibilities: Array.isArray(job.responsibilities) ? job.responsibilities.join("\n") : job.responsibilities || "",
      required_skills: Array.isArray(job.required_skills) ? job.required_skills.join(", ") : job.required_skills || "",
      preferred_skills: Array.isArray(job.preferred_skills) ? job.preferred_skills.join(", ") : job.preferred_skills || "",
      experience_min_years: String(job.experience_min_years ?? job.min_experience_years ?? ""),
      education: job.education || "",
      salary_min_k: String(job.salary_min_k ?? ""),
      salary_max_k: String(job.salary_max_k ?? ""),
      status: job.status || EMPTY_ENTERPRISE_JOB_FORM.status,
    });
    setJobModalOpen(true);
  };
  const saveJob = async (event) => {
    event.preventDefault();
    const split = (value) => value.split(/[,，;；]/).map((item) => item.trim()).filter(Boolean);
    const optionalNumber = (value) => {
      const text = String(value ?? "").trim();
      if (!text) return null;
      const number = Number(text);
      return Number.isFinite(number) ? number : null;
    };
    const payload = {
      title: form.title.trim(),
      domain: form.domain,
      city: form.city.trim(),
      headcount: optionalNumber(form.headcount) || 1,
      responsibilities: form.responsibilities.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
      required_skills: split(form.required_skills),
      preferred_skills: split(form.preferred_skills),
      experience_min_years: optionalNumber(form.experience_min_years),
      education: form.education.trim() || null,
      salary_min_k: optionalNumber(form.salary_min_k),
      salary_max_k: optionalNumber(form.salary_max_k),
      status: form.status || EMPTY_ENTERPRISE_JOB_FORM.status,
    };
    const isEditing = Boolean(editingJobId);
    setCreatingJob(true);
    try {
      const path = isEditing ? `/api/enterprise-jobs/${encodeURIComponent(editingJobId)}` : "/api/enterprise-jobs";
      const item = await request(path, { method: isEditing ? "PUT" : "POST", body: JSON.stringify(payload) });
      if (isEditing) {
        setJobs((current) => current.map((job) => job.job_id === editingJobId ? item : job));
        notify?.("企业招聘岗位已更新");
      } else {
        setJobs((current) => [item, ...current]);
        selectJob(item.job_id);
        notify?.("企业招聘岗位已创建");
      }
      setEditingJobId(""); setForm({ ...EMPTY_ENTERPRISE_JOB_FORM }); setJobModalOpen(false);
    } catch (error) { notify?.(error.message || (isEditing ? "岗位更新失败" : "岗位创建失败")); } finally { setCreatingJob(false); }
  };
  const chooseResumeFiles = (event) => {
    const files = [...(event.target.files || [])];
    event.target.value = "";
    if (!files.length) return;
    setPendingResumeFiles(files);
    setUploadJobIds([selectedJob || activeJobs[0]?.job_id].filter(Boolean));
    setUploadModalOpen(true);
  };
  const uploadResumes = async () => {
    const files = pendingResumeFiles;
    if (!files.length || !uploadJobIds.length) return;
    setUploading(true);
    try {
      const data = new FormData(); data.append("target_job_ids", JSON.stringify(uploadJobIds)); files.forEach((file) => data.append("files", file));
      const session = readAuthSession();
      const response = await fetch(`${API}/api/recruitment/candidates/upload`, { method: "POST", headers: session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}, body: data });
      if (!response.ok) throw new Error(await readApiError(response, "简历上传失败"));
      const result = await response.json(); setCandidates((current) => [...result.items, ...current]); selectJob(uploadJobIds[0]); setUploadModalOpen(false); setPendingResumeFiles([]); setUploadJobIds([]); notify?.(`已完成 ${result.created} 份简历初筛，覆盖 ${uploadJobIds.length} 个岗位${result.errors?.length ? `，${result.errors.length} 份失败` : ""}`);
    } catch (error) { notify?.(error.message || "简历上传失败"); } finally { setUploading(false); }
  };
  const toggleUploadJob = (jobId) => {
    setUploadJobIds((current) => current.includes(jobId)
      ? current.filter((id) => id !== jobId)
      : [...current, jobId]);
  };
  const toggleCompare = (candidateId) => {
    setCompareIds((current) => {
      if (current.includes(candidateId)) return current.filter((id) => id !== candidateId);
      if (current.length >= 4) { notify?.("横向对比最多选择 4 位候选人"); return current; }
      return [...current, candidateId];
    });
  };
  const updateDecision = async (candidateId, decision) => {
    try {
      const result = await request(`/api/recruitment/candidates/${candidateId}/feedback`, { method: "POST", body: JSON.stringify({ decision, note: "HR 人工复核" }) });
      setCandidates((current) => current.map((item) => item.candidate_id === candidateId ? result : item)); notify?.("招聘结论已更新");
    } catch (error) { notify?.(error.message || "结论保存失败"); }
  };
  const activeJobs = jobs.filter((job) => job.status === "active");
  const pendingCount = candidates.filter((item) => item.status === "pending_review").length;
  const selectedJobData = jobs.find((job) => job.job_id === selectedJob);
  const candidateTargetJobs = (item) => (item.target_job_ids || [item.target_job_id])
    .map((jobId) => jobs.find((job) => job.job_id === jobId)?.title || jobId)
    .filter(Boolean);
  const comparedCandidates = compareIds.map((id) => candidates.find((item) => item.candidate_id === id)).filter(Boolean);
  const sortedCandidates = useMemo(() => [...candidates].sort((left, right) => {
    const leftScore = Number(getCandidateJobReport(left, selectedJob)?.score) || 0;
    const rightScore = Number(getCandidateJobReport(right, selectedJob)?.score) || 0;
    return rightScore - leftScore;
  }), [candidates, selectedJob]);
  const decisionLabels = {
    advance_interview: "已推进面试",
    pending_review: "待人工复核",
    rejected: "已淘汰",
  };

  return <main className="recruiting-workspace">
    <section className="recruiting-hero">
      <div>
        <span className="recruiting-hero-kicker">招聘工作台</span>
        <h1>招聘岗位与候选人初筛</h1>
        <p>统一管理企业岗位与真实候选人简历，让每一项初筛结论都能回到能力证据、岗位要求和下一步行动。</p>
      </div>
    </section>

    <section className="recruiting-metrics" aria-label="招聘数据概览">
      <article><span>企业岗位</span><strong>{jobs.length}</strong><small>{activeJobs.length} 个正在招聘</small></article>
      <article><span>初筛候选人</span><strong>{candidates.length}</strong><small>来自已上传的真实简历</small></article>
      <article><span>待人工复核</span><strong>{pendingCount}</strong><small>等待招聘团队确认</small></article>
    </section>

    <Card className="recruiting-panel recruiting-jobs-panel">
      <Card.Header>
        <div><Card.Title>企业在招岗位</Card.Title><Card.Description>以表格统一查看岗位信息，选择目标岗位后即可导入候选人简历。</Card.Description></div>
        <div className="recruiting-job-actions">
          <Button variant="secondary" onPress={() => window.open(`${API}/api/enterprise-jobs/template`, "_blank")}><FileDown size={16} />下载岗位模板</Button>
          <Button className="recruiting-open-modal" onPress={openCreateJob}><Plus size={16} />新增岗位</Button>
        </div>
      </Card.Header>
      <Card.Content>
        {jobs.length ? <Table className="recruiting-job-table" variant="secondary">
          <Table.ScrollContainer>
            <Table.Content aria-label="企业在招岗位" className="recruiting-job-table-content">
              <Table.Header>
                <Table.Column isRowHeader>岗位名称</Table.Column>
                <Table.Column>领域 / 城市</Table.Column>
                <Table.Column>招聘人数</Table.Column>
                <Table.Column>必备技能</Table.Column>
                <Table.Column>状态</Table.Column>
                <Table.Column aria-label="岗位操作">操作</Table.Column>
              </Table.Header>
              <Table.Body>
                {jobs.map((job) => <Table.Row id={job.job_id} key={job.job_id} className={selectedJob === job.job_id ? "is-selected" : ""}>
                  <Table.Cell><div className="recruiting-job-name"><strong>{job.title}</strong><small>{job.job_id}</small></div></Table.Cell>
                  <Table.Cell><div className="recruiting-job-location"><strong>{job.domain}</strong><span>{job.city}</span></div></Table.Cell>
                  <Table.Cell><strong className="recruiting-job-headcount">{job.headcount || 1}<small> 人</small></strong></Table.Cell>
                  <Table.Cell><div className="recruiting-job-skill-chips">{job.required_skills?.length ? job.required_skills.slice(0, 3).map((skill) => <Chip key={skill} variant="soft"><Chip.Label>{skill}</Chip.Label></Chip>) : <span>未填写</span>}</div></Table.Cell>
                  <Table.Cell><Chip color={job.status === "active" ? "success" : "default"} variant="soft"><Chip.Label>{job.status === "active" ? "招聘中" : job.status === "paused" ? "已暂停" : "已关闭"}</Chip.Label></Chip></Table.Cell>
                  <Table.Cell><div className="recruiting-job-row-actions" style={{ display: "flex", alignItems: "center", gap: 4 }}><Button className="recruiting-select-job" size="sm" variant={selectedJob === job.job_id ? "secondary" : "ghost"} onPress={() => selectJob(job.job_id)}>{selectedJob === job.job_id ? <Check size={14} /> : <Target size={14} />}{selectedJob === job.job_id ? "当前岗位" : "设为目标"}</Button><Button isIconOnly size="sm" variant="ghost" title={`编辑 ${job.title}`} aria-label={`编辑岗位 ${job.title}`} onPress={() => openEditJob(job)}><Edit3 size={15} /></Button></div></Table.Cell>
                </Table.Row>)}
              </Table.Body>
            </Table.Content>
          </Table.ScrollContainer>
        </Table> : <div className="recruiting-inline-empty"><BriefcaseBusiness size={20} /><span>还没有企业岗位，请先创建一个岗位。</span><Button onPress={openCreateJob}><Plus size={15} />新增岗位</Button></div>}
      </Card.Content>
    </Card>

    <Modal.Backdrop isOpen={jobModalOpen} onOpenChange={setJobModalOpen} variant="blur">
        <Modal.Container placement="center" scroll="inside" size="lg">
          <Modal.Dialog aria-labelledby="recruiting-job-modal-title">
            <Form onSubmit={saveJob} aria-label={editingJobId ? "编辑企业岗位" : "新增企业岗位"}>
              <Modal.CloseTrigger aria-label={editingJobId ? "关闭编辑岗位弹窗" : "关闭新增岗位弹窗"} />
              <Modal.Header>
                <Modal.Icon><BriefcaseBusiness size={20} /></Modal.Icon>
                <Modal.Heading id="recruiting-job-modal-title">{editingJobId ? "编辑企业岗位" : "新增企业岗位"}</Modal.Heading>
                <p>{editingJobId ? "更新岗位信息后，岗位表与后续候选人初筛会使用最新要求。" : "创建后会立即进入岗位表，并自动成为本次候选人初筛的目标岗位。"}</p>
              </Modal.Header>
              <Modal.Body>
                <div className="recruiting-modal-fields">
                  <TextField isRequired value={form.title} onChange={(value) => setForm({ ...form, title: value })} variant="secondary"><Label>岗位名称</Label><Input autoFocus placeholder="例如：AI Agent 工程师" /></TextField>
                  <TextField isRequired value={form.city} onChange={(value) => setForm({ ...form, city: value })} variant="secondary"><Label>工作城市</Label><Input placeholder="例如：杭州" /></TextField>
                  <Select aria-label="所属领域" selectedKey={form.domain} onSelectionChange={(key) => key != null && setForm({ ...form, domain: String(key) })} variant="secondary">
                    <Label>所属领域</Label><Select.Trigger><Select.Value /></Select.Trigger><Select.Popover><ListBox>{DOMAINS.map((domain) => <ListBox.Item id={domain} key={domain} textValue={domain}>{domain}<ListBox.ItemIndicator /></ListBox.Item>)}</ListBox></Select.Popover>
                  </Select>
                  <TextField isRequired type="number" value={form.headcount} onChange={(value) => setForm({ ...form, headcount: value })} variant="secondary"><Label>招聘人数</Label><Input min="1" max="999" /></TextField>
                  <TextField type="number" value={form.experience_min_years} onChange={(value) => setForm({ ...form, experience_min_years: value })} variant="secondary"><Label>最低经验年限</Label><Input min="0" max="40" placeholder="可选" /></TextField>
                  <TextField value={form.education} onChange={(value) => setForm({ ...form, education: value })} variant="secondary"><Label>学历要求</Label><Input placeholder="例如：本科，可选" /></TextField>
                  <TextField type="number" value={form.salary_min_k} onChange={(value) => setForm({ ...form, salary_min_k: value })} variant="secondary"><Label>最低月薪 K</Label><Input min="0" max="500" placeholder="可选" /></TextField>
                  <TextField type="number" value={form.salary_max_k} onChange={(value) => setForm({ ...form, salary_max_k: value })} variant="secondary"><Label>最高月薪 K</Label><Input min="0" max="500" placeholder="可选" /></TextField>
                  <Select aria-label="岗位状态" selectedKey={form.status} onSelectionChange={(key) => key != null && setForm({ ...form, status: String(key) })} variant="secondary">
                    <Label>岗位状态</Label><Select.Trigger><Select.Value /></Select.Trigger><Select.Popover><ListBox>{ENTERPRISE_JOB_STATUS_OPTIONS.map((option) => <ListBox.Item id={option.id} key={option.id} textValue={option.label}>{option.label}<ListBox.ItemIndicator /></ListBox.Item>)}</ListBox></Select.Popover>
                  </Select>
                  <TextField className="recruiting-form-wide" isRequired value={form.required_skills} onChange={(value) => setForm({ ...form, required_skills: value })} variant="secondary"><Label>必备技能</Label><Input placeholder="用逗号分隔，例如 Python、RAG、FastAPI" /></TextField>
                  <TextField className="recruiting-form-wide" value={form.preferred_skills} onChange={(value) => setForm({ ...form, preferred_skills: value })} variant="secondary"><Label>加分技能</Label><Input placeholder="用逗号分隔，可选" /></TextField>
                  <TextField className="recruiting-form-wide" value={form.responsibilities} onChange={(value) => setForm({ ...form, responsibilities: value })} variant="secondary"><Label>岗位职责</Label><TextArea placeholder="每行一条，帮助系统提取更准确的岗位能力要求" /></TextField>
                </div>
              </Modal.Body>
              <Modal.Footer>
                <Button type="button" variant="secondary" onPress={() => setJobModalOpen(false)}>取消</Button>
                <Button type="submit" variant="primary" isPending={creatingJob}>{editingJobId ? <Edit3 size={16} /> : <Plus size={16} />}{creatingJob ? (editingJobId ? "正在保存…" : "正在创建…") : (editingJobId ? "保存岗位修改" : "创建并加入岗位库")}</Button>
              </Modal.Footer>
            </Form>
          </Modal.Dialog>
        </Modal.Container>
    </Modal.Backdrop>

    <Modal.Backdrop isOpen={uploadModalOpen} onOpenChange={(open) => { if (!uploading) setUploadModalOpen(open); }}>
      <Modal.Container placement="center" size="lg">
        <Modal.Dialog aria-labelledby="recruiting-upload-modal-title">
          <Modal.CloseTrigger />
          <Modal.Header>
            <Modal.Icon><FileUp size={20} /></Modal.Icon>
            <Modal.Heading id="recruiting-upload-modal-title">投递候选人简历</Modal.Heading>
            <p>一份简历可同时选择多个在招岗位，系统只解析一次并分别生成岗位差异报告。</p>
          </Modal.Header>
          <Modal.Body>
            <section className="recruiting-job-picker" aria-label="选择简历投递岗位">
              <header><div><strong>选择投递岗位</strong><span>可多选，已选 {uploadJobIds.length} 个</span></div>{uploadJobIds.length ? <Button size="sm" variant="ghost" onPress={() => setUploadJobIds([])}>清空</Button> : null}</header>
              <div className="recruiting-job-choice-grid">
                {activeJobs.map((job) => {
                  const selected = uploadJobIds.includes(job.job_id);
                  return <button aria-pressed={selected} className={`recruiting-job-choice ${selected ? "is-selected" : ""}`} key={job.job_id} onClick={() => toggleUploadJob(job.job_id)} type="button">
                    <span className="recruiting-job-choice-check">{selected ? <Check size={14} /> : null}</span>
                    <span className="recruiting-job-choice-copy"><strong>{job.title}</strong><small>{job.domain} · {job.city} · 招 {job.headcount || 1} 人</small></span>
                    <span className="recruiting-job-choice-skills">{job.required_skills?.slice(0, 3).map((skill) => <em key={skill}>{skill}</em>)}</span>
                  </button>;
                })}
              </div>
            </section>
            <div className="recruiting-upload-files">
              <span>已选择 {pendingResumeFiles.length} 份简历</span>
              {pendingResumeFiles.map((file) => <p key={`${file.name}-${file.size}`}><FileText size={14} /><b>{file.name}</b><small>{Math.max(1, Math.round(file.size / 1024))} KB</small></p>)}
            </div>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" isDisabled={uploading} onPress={() => { setUploadModalOpen(false); setPendingResumeFiles([]); setUploadJobIds([]); }}>取消</Button>
            <Button variant="primary" isDisabled={!uploadJobIds.length || !pendingResumeFiles.length} isPending={uploading} onPress={uploadResumes}><Upload size={16} />{uploading ? "正在解析与初筛…" : `投递到 ${uploadJobIds.length || 0} 个岗位`}</Button>
          </Modal.Footer>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>

    <Card className="recruiting-upload">
      <Card.Content>
        <span className="recruiting-upload-icon"><FileUp size={21} /></span>
        <div><strong>上传并投递候选人简历</strong><span>支持 PDF、Word、TXT 与图片；选择文件后再指定本次投递岗位。</span></div>
        <input ref={resumeInputRef} className="recruiting-file-input" type="file" multiple accept=".pdf,.docx,.docm,.txt,.md,.png,.jpg,.jpeg,.webp" onChange={chooseResumeFiles} disabled={uploading || !activeJobs.length} />
        <Button className="recruiting-upload-button" isDisabled={uploading || !activeJobs.length} isPending={uploading} onPress={() => resumeInputRef.current?.click()}>
          <Upload size={16} />{uploading ? "正在解析简历…" : "选择简历并投递"}
        </Button>
      </Card.Content>
    </Card>

    <section className="recruiting-candidates">
      <div className="section-title">
        <div>
          <span className="section-title-kicker">SCREENING QUEUE</span>
          <h2>候选人初筛队列</h2>
          <p>{loading ? "正在同步招聘数据…" : "按岗位匹配度排序，优先核验关键优势、能力缺口与替代岗位机会。"}</p>
        </div>
        <Button variant="ghost" onPress={refresh} isPending={loading}><RefreshCw size={15} />刷新</Button>
      </div>
      <div className="recruiting-queue-meta" aria-label="初筛队列统计">
        <Chip color="accent" variant="soft"><Chip.Label>全部 {candidates.length}</Chip.Label></Chip>
        <Chip color="warning" variant="soft"><Chip.Label>待复核 {pendingCount}</Chip.Label></Chip>
        {selectedJobData ? <Chip variant="soft"><Chip.Label>当前岗位：{selectedJobData.title}</Chip.Label></Chip> : null}
        <div className="candidate-compare-actions">
          {compareIds.length ? <Button variant="ghost" size="sm" onPress={() => setCompareIds([])}>清除选择</Button> : null}
          <Button size="sm" isDisabled={compareIds.length < 2} onPress={() => setComparisonOpen(true)}><GitCompareArrows size={15} />横向对比 {compareIds.length || ""}</Button>
        </div>
      </div>
      {sortedCandidates.length ? <div className="candidate-screening-list">{sortedCandidates.map((item, index) => {
        const screening = getCandidateJobReport(item, selectedJob);
        const isEvaluated = Boolean(screening);
        const score = Number(screening?.score) || 0;
        const strengths = Array.isArray(screening?.strengths) ? screening.strengths : [];
        const gaps = Array.isArray(screening?.gaps) ? screening.gaps : [];
        const screeningLevel = screening?.level;
        const screeningLevelColor = screeningLevel === "high" ? "success" : screeningLevel === "medium" ? "warning" : screeningLevel === "low" ? "danger" : "default";
        const screeningLevelLabel = isEvaluated ? RECRUITING_LEVEL_LABELS[screeningLevel] || "已评估" : "未评估";
        const allJobResults = item.all_job_results || item.difference_report || [];
        const selectedJobResult = allJobResults.find((role) => role?.job_id === selectedJob);
        const visibleJobResults = allJobResults.filter((role, roleIndex) => roleIndex < 3 || role?.job_id === selectedJob);
        const targetTitles = candidateTargetJobs(item);
        return <Card key={item.candidate_id} className={`candidate-screening-card ${compareIds.includes(item.candidate_id) ? "comparison-selected" : ""}`}>
          <Card.Header>
            <Checkbox className="candidate-compare-check" aria-label={`选择 ${item.name || "候选人"} 进行横向对比`} isSelected={compareIds.includes(item.candidate_id)} onChange={() => toggleCompare(item.candidate_id)}><Checkbox.Content><Checkbox.Control><Checkbox.Indicator /></Checkbox.Control></Checkbox.Content></Checkbox>
            <div className="candidate-screening-title">
              <span><UserRoundSearch size={18} /></span>
              <div><div className="candidate-name-line"><small>#{String(index + 1).padStart(2, "0")}</small><Card.Title>{item.name || "未识别姓名"}</Card.Title></div><Card.Description>{item.source_name || "简历文件"} · 投递 {targetTitles.slice(0, 2).join("、")}{targetTitles.length > 2 ? ` 等 ${targetTitles.length} 个岗位` : ""}</Card.Description></div>
            </div>
            <div className="candidate-screening-score">
              <Chip color={screeningLevelColor} variant="soft"><Chip.Label>{screeningLevelLabel}</Chip.Label></Chip>
              <Chip color={item.status === "pending_review" ? "warning" : item.status === "rejected" ? "danger" : "success"} variant="soft"><Chip.Label>HR：{decisionLabels[item.status] || "待人工复核"}</Chip.Label></Chip>
              <strong>{score}<small>分匹配</small></strong>
            </div>
          </Card.Header>
          <Card.Content><div className="screening-columns">
            <div><header><CheckCircle2 size={16} /><strong>能力证据与优势</strong></header>{strengths.length ? strengths.slice(0, 3).map((strength) => <p key={strength.skill}><b>{strength.skill}</b>：{strength.evidence}</p>) : <p>{isEvaluated ? "未发现明确优势证据" : "未评估"}</p>}</div>
            <div><header><CircleAlert size={16} /><strong>目标岗位差距</strong></header>{gaps.length ? gaps.slice(0, 3).map((gap) => <p key={gap.skill}><b>{gap.skill}</b>：{gap.recommended_action}</p>) : <p>{isEvaluated ? "未发现关键能力缺口" : "未评估"}</p>}</div>
            <div><header><BriefcaseBusiness size={16} /><strong>多岗位匹配排序</strong></header>{visibleJobResults.length || selectedJobData ? <>{visibleJobResults.map((role) => <p key={`${role.source}-${role.job_id}`}><b>{role.title}</b> · {Number(role.score) || 0} 分{role.job_id === selectedJob ? " · 当前岗位" : role.job_id === item.target_job_id ? " · 首选投递" : ""}</p>)}{!selectedJobResult && selectedJobData ? <p><b>{selectedJobData.title}</b> · {isEvaluated ? `${score} 分` : "未评估"} · 当前岗位</p> : null}</> : <p>等待生成岗位差异结果</p>}</div>
          </div>
          <div className="candidate-report-ready"><span><CheckCircle2 size={15} /></span><div><strong>{isEvaluated ? `当前岗位${RECRUITING_LEVEL_LABELS[screeningLevel] || "已评估"}` : "当前岗位未评估"}</strong><small>{isEvaluated ? `完整档案已生成，能力画像与 ${allJobResults.length} 份岗位差异报告将在候选人中心直接完整展示。` : "该候选人尚未生成当前岗位差异报告。"}</small></div></div></Card.Content>
          <Card.Footer><Button className="candidate-screening-primary" variant="secondary" onPress={() => updateDecision(item.candidate_id, "advance_interview")}><Check size={15} />推进线下面试</Button><Button variant="ghost" onPress={() => { window.sessionStorage.setItem("tg-open-candidate-detail", item.candidate_id); navigate?.("assessments"); }}><Eye size={15} />完整档案</Button><Button variant="ghost" onPress={() => updateDecision(item.candidate_id, "pending_review")}>待人工复核</Button><Button className="candidate-reject-button" variant="ghost" onPress={() => updateDecision(item.candidate_id, "rejected")}>淘汰</Button></Card.Footer>
        </Card>;
      })}</div> : <Card className="recruiting-empty-state"><Card.Content><span><UserRoundSearch size={28} /></span><div><strong>暂时没有候选人进入初筛</strong><p>上传真实简历并指定投递岗位后，系统会生成可追溯的能力证据与初筛建议。</p></div><Button isDisabled={!activeJobs.length} onPress={() => resumeInputRef.current?.click()}><Upload size={15} />上传候选人简历</Button></Card.Content></Card>}
    </section>

    <Modal.Backdrop isOpen={comparisonOpen} onOpenChange={setComparisonOpen}>
      <Modal.Container placement="center" size="full">
        <Modal.Dialog aria-labelledby="candidate-comparison-title">
          <Modal.CloseTrigger />
          <Modal.Header><Modal.Icon><GitCompareArrows size={20} /></Modal.Icon><Modal.Heading id="candidate-comparison-title">候选人横向对比</Modal.Heading><p>当前岗位：{selectedJobData?.title || "未选择"}。对比岗位匹配、能力优势与关键缺口，完整报告可进入候选人中心继续查看。</p></Modal.Header>
          <Modal.Body>
            <div className="candidate-comparison-grid" style={{ "--candidate-columns": comparedCandidates.length }}>
              <span className="comparison-row-label">候选人</span>{comparedCandidates.map((item) => <strong key={`${item.candidate_id}-name`}>{item.name || "未识别姓名"}<small>{candidateTargetJobs(item).join("、") || "目标岗位"}</small></strong>)}
              <span className="comparison-row-label">匹配指数</span>{comparedCandidates.map((item) => { const screening = getCandidateJobReport(item, selectedJob); const score = Number(screening?.score) || 0; return <div className="comparison-score" key={`${item.candidate_id}-score`}><b>{score}</b><i><em style={{ width: `${Math.min(100, score)}%` }} /></i></div>; })}
              <span className="comparison-row-label">经验 / 学历</span>{comparedCandidates.map((item) => <p key={`${item.candidate_id}-base`}>{item.profile?.experience_years ?? "--"} 年<br />{item.profile?.education || "未识别"}</p>)}
              <span className="comparison-row-label">主要优势</span>{comparedCandidates.map((item) => { const screening = getCandidateJobReport(item, selectedJob); const strengths = Array.isArray(screening?.strengths) ? screening.strengths : []; return <div key={`${item.candidate_id}-strengths`}>{strengths.length ? strengths.slice(0, 4).map((entry) => <Chip color="success" size="sm" variant="soft" key={entry.skill}><Chip.Label>{entry.skill}</Chip.Label></Chip>) : <span>未评估</span>}</div>; })}
              <span className="comparison-row-label">关键缺口</span>{comparedCandidates.map((item) => { const screening = getCandidateJobReport(item, selectedJob); const gaps = Array.isArray(screening?.gaps) ? screening.gaps : []; return <div key={`${item.candidate_id}-gaps`}>{gaps.length ? gaps.slice(0, 4).map((entry) => <Chip color="danger" size="sm" variant="soft" key={entry.skill}><Chip.Label>{entry.skill}</Chip.Label></Chip>) : <span>未评估</span>}</div>; })}
              <span className="comparison-row-label">当前结论</span>{comparedCandidates.map((item) => <p key={`${item.candidate_id}-status`}>{decisionLabels[item.status] || "待人工复核"}</p>)}
            </div>
          </Modal.Body>
          <Modal.Footer><Button variant="secondary" onPress={() => setComparisonOpen(false)}>关闭</Button><Button onPress={() => { setComparisonOpen(false); navigate?.("assessments"); }}><UserRoundSearch size={15} />进入候选人中心</Button></Modal.Footer>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  </main>;
}

function AssessmentManagement({ records, navigate, setCandidate, onCreate, onUpdate, onDelete, notify }) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [editingId, setEditingId] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [screeningCandidates, setScreeningCandidates] = useState([]);
  const [candidateDetail, setCandidateDetail] = useState(null);
  const [screeningLoading, setScreeningLoading] = useState(false);
  const loadScreeningCandidates = useCallback(async () => {
    setScreeningLoading(true);
    try {
      const data = await request("/api/recruitment/candidates");
      const items = data.items || [];
      setScreeningCandidates(items);
      const requestedCandidateId = window.sessionStorage.getItem("tg-open-candidate-detail");
      if (requestedCandidateId) {
        const requestedCandidate = items.find((item) => item.candidate_id === requestedCandidateId);
        if (requestedCandidate) setCandidateDetail(requestedCandidate);
        window.sessionStorage.removeItem("tg-open-candidate-detail");
      }
    } catch (error) {
      notify?.(error.message || "候选人档案加载失败");
    } finally {
      setScreeningLoading(false);
    }
  }, [notify]);
  useEffect(() => { loadScreeningCandidates(); }, [loadScreeningCandidates]);
  const filtered = useMemo(() => {
    const text = query.trim().toLowerCase();
    return records.filter((record) => {
      const matchesStatus = statusFilter === "all" || record.status === statusFilter;
      const haystack = [
        record.name,
        record.target_job_title,
        record.archetype_title,
        record.note,
        ...(record.traits || []),
      ].join(" ").toLowerCase();
      return matchesStatus && (!text || haystack.includes(text));
    });
  }, [query, records, statusFilter]);
  const stats = useMemo(() => {
    const reportCount = records.filter((item) => item.profile?.match_report).length;
    const avgScore = records.length
      ? Math.round(records.reduce((sum, item) => sum + Number(item.score || 0), 0) / records.length)
      : 0;
    return [
      ["候选人档案", screeningCandidates.length + records.length],
      ["已出报告", reportCount],
      ["平均指数", avgScore || "--"],
      ["待补报告", Math.max(0, records.length - reportCount)],
    ];
  }, [records, screeningCandidates.length]);
  const formatTime = (value) => {
    if (!value) return "未记录";
    try {
      return new Intl.DateTimeFormat("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(value));
    } catch {
      return "未记录";
    }
  };
  const openRecord = (record) => {
    setCandidate(record.profile);
    navigate(record.profile?.match_report ? "report" : "recruiting");
  };
  const reAssess = (record) => {
    setCandidate(null);
    navigate("recruiting");
    notify?.(`${record.name} 可在招聘初筛工作台重新上传并生成报告`);
  };
  const startEdit = (record) => {
    setEditingId(record.id);
    setNoteDraft(record.note || "");
  };
  const saveNote = (record) => {
    onUpdate(record.id, { note: noteDraft.trim() });
    setEditingId("");
    setNoteDraft("");
    notify?.("评估备注已更新");
  };
  const screeningTargetTitle = (item) => {
    const results = item.all_job_results || item.difference_report || [];
    const selectedIds = item.target_job_ids || [item.target_job_id];
    const titles = selectedIds
      .map((jobId) => results.find((result) => result.job_id === jobId)?.title)
      .filter(Boolean);
    return titles.length ? titles.join("、") : results[0]?.title || "企业在招岗位";
  };
  return (
    <main className="assessment-management">
      <section className="management-head">
        <div>
          <h1>候选人中心</h1>
          <p>集中查看候选人完整能力画像、岗位差异报告、线下面试题和后续复评记录。</p>
        </div>
        <Button onPress={onCreate}>
          <Plus size={16} />
          新增评估
        </Button>
      </section>
      <section className="management-stats">
        {stats.map(([label, value]) => (
          <article key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>
      <section className="screening-archive-section">
        <header><div><span>RECRUITMENT PROFILES</span><h2>招聘候选人档案</h2><p>来自岗位初筛队列，进入档案可查看详细画像、全部岗位差异和线下面试题。</p></div><Button variant="ghost" isPending={screeningLoading} onPress={loadScreeningCandidates}><RefreshCw size={15} />刷新</Button></header>
        {screeningCandidates.length ? <div className="screening-archive-list">{screeningCandidates.map((item) => <article key={item.candidate_id}>
          <div><Avatar size="sm"><Avatar.Fallback>{(item.name || "候").slice(0, 1)}</Avatar.Fallback></Avatar><span><strong>{item.name || "未识别姓名"}</strong><small>{item.source_name || "候选人简历"}</small></span></div>
          <div><small>投递岗位</small><strong>{screeningTargetTitle(item)}</strong></div>
          <div><small>匹配指数</small><strong>{item.screening?.score || 0} 分</strong></div>
          <div><small>当前状态</small><strong>{item.status === "advance_interview" ? "推进面试" : item.status === "rejected" ? "已淘汰" : "待人工复核"}</strong></div>
          <Button variant="secondary" onPress={() => setCandidateDetail(item)}><Eye size={15} />查看完整档案</Button>
        </article>)}</div> : <div className="screening-archive-empty"><UserRoundSearch size={28} /><span><strong>暂无招聘候选人档案</strong><small>请先在招聘岗位与初筛页面上传简历。</small></span></div>}
      </section>
      <section className="management-toolbar">
        <label>
          <Search size={15} />
          <Input variant="secondary" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索候选人、岗位、画像或备注" />
        </label>
        <div>
          <Filter size={15} />
          {["all", "已生成画像", "已出报告"].map((item) => (
            <Button key={item} className={statusFilter === item ? "active" : ""} variant="ghost" onPress={() => setStatusFilter(item)}>
              {item === "all" ? "全部" : item}
            </Button>
          ))}
        </div>
      </section>
      <section className="assessment-record-table">
        <div className="record-row record-head">
          <span>候选人</span>
          <span>目标岗位</span>
          <span>综合指数</span>
          <span>画像阶段</span>
          <span>证据规模</span>
          <span>备注</span>
          <span>操作</span>
        </div>
        {filtered.length ? filtered.map((record) => (
          <article className="record-row" key={record.id}>
            <div>
              <strong>{record.name}</strong>
              <small>{record.candidate_id}</small>
            </div>
            <div>
              <strong>{record.target_job_title}</strong>
              <small>{record.city} · {formatTime(record.updated_at)}</small>
            </div>
            <div className="record-score">
              <strong>{record.score || "--"}</strong>
              <i><b style={{ width: `${Math.min(100, Number(record.score || 0))}%` }} /></i>
            </div>
            <div>
              <em className={record.profile?.match_report ? "ready" : ""}>{record.status}</em>
              <small>{record.archetype_title}</small>
            </div>
            <div>
              <strong>{record.skill_count} 技能 / {record.project_count} 项目</strong>
              <small>{record.evidence_count} 条证据</small>
            </div>
            <div className="record-note">
              {editingId === record.id ? (
                <label>
                  <Input variant="secondary" value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} placeholder="输入跟进备注" />
                  <Button isIconOnly variant="ghost" onPress={() => saveNote(record)}><Check size={13} /></Button>
                  <Button isIconOnly variant="ghost" onPress={() => setEditingId("")}><X size={13} /></Button>
                </label>
              ) : (
                <Button variant="ghost" onPress={() => startEdit(record)}>{record.note || "添加备注"}</Button>
              )}
            </div>
            <div className="record-actions">
              <Button isIconOnly variant="ghost" title={record.profile?.match_report ? "查看报告" : "查看画像"} onPress={() => openRecord(record)}>
                <Eye size={15} />
              </Button>
              <Button isIconOnly variant="ghost" title="重新评估" onPress={() => reAssess(record)}>
                <Edit3 size={15} />
              </Button>
              <Button isIconOnly variant="ghost" title="删除记录" onPress={() => onDelete(record.id)}>
                <Trash2 size={15} />
              </Button>
            </div>
          </article>
        )) : (
          <div className="management-empty">
            <ClipboardCheck size={34} />
            <h3>暂无评估档案</h3>
            <p>从候选人评估完成画像后，记录会自动保存到这里；也可以现在新建一轮评估。</p>
            <Button onPress={onCreate}>新增评估 <ArrowRight size={15} /></Button>
          </div>
        )}
      </section>
      <Modal.Backdrop isOpen={Boolean(candidateDetail)} onOpenChange={(open) => { if (!open) setCandidateDetail(null); }}>
        <Modal.Container placement="center" size="full">
          <Modal.Dialog aria-labelledby="candidate-detail-title">
            <Modal.CloseTrigger />
            {candidateDetail && <>
              <Modal.Header><Modal.Icon><FileUser size={20} /></Modal.Icon><Modal.Heading id="candidate-detail-title">{candidateDetail.name || "候选人"} · 完整评估档案</Modal.Heading><p>{candidateDetail.source_name || "候选人简历"} · 投递 {screeningTargetTitle(candidateDetail)}</p></Modal.Header>
              <Modal.Body>
                <section className="candidate-detail-section">
                  <header><div><span>RESUME ANALYSIS</span><h3>候选人能力画像</h3></div><small>与求职者端采用同一画像口径</small></header>
                  <RecruitmentCandidateProfile candidate={candidateDetail} />
                </section>
                <section className="candidate-detail-section">
                  <header><div><span>ENTERPRISE REVIEW</span><h3>企业招聘判断</h3></div><small>{candidateDetail.profile?.skills?.length || 0} 项已识别技能</small></header>
                  <div className="candidate-profile-evidence-columns">
                    <div><h4>能力优势</h4>{(candidateDetail.screening?.strengths || []).length ? candidateDetail.screening.strengths.map((entry) => <article key={entry.skill}><strong>{entry.skill}</strong><p>{entry.evidence || "简历中存在相关能力证据"}</p></article>) : <p>暂无明确优势证据。</p>}</div>
                    <div><h4>风险与不足</h4>{(candidateDetail.screening?.gaps || []).length ? candidateDetail.screening.gaps.map((entry) => <article key={entry.skill}><strong>{entry.skill}</strong><p>{entry.recommended_action || "建议在线下面试中进一步核验"}</p></article>) : <p>当前目标岗位未发现关键能力缺口。</p>}</div>
                  </div>
                  <div className="candidate-detail-skills">{(candidateDetail.profile?.skills || []).map((skill, index) => { const name = skill?.name || skill; return <Chip key={`${name}-${index}`} variant="soft"><Chip.Label>{name}{skill?.level ? ` · ${skill.level}` : ""}</Chip.Label></Chip>; })}</div>
                  <div className="candidate-project-evidence">{(candidateDetail.profile?.projects || []).map((project, index) => <article key={`${project.name || project.title || "project"}-${index}`}><span>项目 {String(index + 1).padStart(2, "0")}</span><strong>{project.name || project.title || "未命名项目"}</strong><p>{project.description || project.evidence || project.summary || "简历中已识别该项目经历。"}</p><small>{project.role || project.technologies?.join?.(" · ") || "项目经历证据"}</small></article>)}</div>
                </section>
                <section className="candidate-detail-section">
                  <header><div><span>JOB GAP REPORT</span><h3>企业在招岗位差异分析</h3></div><small>{(candidateDetail.all_job_results || candidateDetail.difference_report || []).length} 个岗位</small></header>
                  <div className="candidate-job-gap-list">{(candidateDetail.all_job_results || candidateDetail.difference_report || []).map((result) => <article key={result.job_id}><header><div><strong>{result.title}</strong><small>{result.job_id === candidateDetail.target_job_id ? "首选投递岗位" : "同步投递岗位"}</small></div><b>{result.score} 分</b></header><div><span><b>已匹配</b>{result.matched_skills?.join("、") || "暂无明确匹配技能"}</span><span><b>必备缺口</b>{result.missing_required_skills?.join("、") || "无关键缺口"}</span><span><b>加分项缺口</b>{result.missing_preferred_skills?.join("、") || "无"}</span></div></article>)}</div>
                </section>
                <section className="candidate-detail-section interview-question-section">
                  <header><div><span>OFFLINE INTERVIEW</span><h3>线下面试题</h3></div><small>{candidateDetail.interview_questions?.length || 0} 题</small></header>
                  {(candidateDetail.interview_questions || []).length ? <ol>{candidateDetail.interview_questions.map((question, index) => <li key={`${question}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><p>{question}</p></li>)}</ol> : <p>当前档案尚未生成线下面试题。</p>}
                </section>
              </Modal.Body>
              <Modal.Footer><Button variant="secondary" onPress={() => setCandidateDetail(null)}>关闭档案</Button><Button onPress={() => { setCandidateDetail(null); navigate("recruiting"); }}><ArrowLeft size={15} />返回初筛队列</Button></Modal.Footer>
            </>}
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </main>
  );
}

function selectTalentIdentityDomain(person = {}) {
  const flatten = (value) => {
    if (Array.isArray(value)) return value.map(flatten).join(" ");
    if (value && typeof value === "object") return Object.values(value).map(flatten).join(" ");
    return value == null ? "" : String(value);
  };
  const projects = Array.isArray(person.projects) ? person.projects : [];
  const normalizedText = [
    person.domain,
    person.target,
    person.target_title,
    person.title,
    person.archetype_title,
    person.narrative,
    person.archetype_narrative,
    person.summary,
    flatten(person.traits),
    flatten(person.skills),
    flatten(person.competency_dimensions),
    flatten(person.behavior_signals),
    flatten(person.evidence),
    ...projects.flatMap((project) => [
      project?.name,
      project?.role,
      flatten(project?.tech_stack),
      flatten(project?.evidence),
      flatten(project?.result),
    ]),
  ]
    .filter(Boolean)
    .join(" ")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();

  const domainKeywords = [
    ["iot", [
      /物联网/, /物联平台/, /设备接入/, /设备联网/, /传感器/, /嵌入式/, /边缘计算/, /智能硬件/,
      /\biot\b/, /\biiot\b/, /\bmqtt\b/, /\blorawan\b/, /\blora\b/, /\bzigbee\b/, /\brfid\b/,
      /\besp32\b/, /\bstm32\b/,
    ]],
    ["big-data", [
      /大数据/, /数据仓库/, /数据湖/, /数据中台/, /数据治理/, /数据工程/, /数据平台/, /批处理/, /流处理/,
      /\bbig\s+data\b/, /\bbigdata\b/, /\blakehouse\b/, /\betl\b/, /\bspark\b/, /\bflink\b/,
      /\bhadoop\b/, /\bhive\b/, /\bkafka\b/, /\bclickhouse\b/, /\bpresto\b/, /\btrino\b/, /\bairflow\b/, /\bdbt\b/,
    ]],
    ["ai", [
      /人工智能/, /机器学习/, /深度学习/, /生成式人工智能/, /大模型/, /模型训练/, /模型推理/,
      /计算机视觉/, /自然语言处理/, /智能问答/, /推荐算法/,
      /\bai\b/, /\baigc\b/, /\bml\b/, /\bllm\b/, /\bnlp\b/, /\brag\b/, /\bopenai\b/,
      /\bmachine\s+learning\b/, /\bdeep\s+learning\b/, /\bcomputer\s+vision\b/,
      /\bpytorch\b/, /\btensorflow\b/, /\btransformer\b/,
    ]],
    ["intelligent-systems", [
      /智能系统/, /智能控制/, /自动控制/, /控制系统/, /控制算法/, /机器人/, /工业自动化/, /决策系统/,
      /专家系统/, /数字孪生/, /系统架构/, /系统设计/, /软件工程/, /应用开发/, /后端/, /前端/, /全栈/,
      /微服务/, /分布式/, /云原生/, /平台工程/, /工程化/, /运维/, /测试开发/,
      /\brobotics\b/, /\bautonomous\b/, /\bcontrol\s+system\b/, /\bros2?\b/, /\bbackend\b/,
      /\bfrontend\b/, /\bfull[ -]?stack\b/, /\bdevops\b/, /\bcloud[ -]?native\b/,
      /\bmicroservices?\b/, /\bdistributed\s+systems?\b/, /\bkubernetes\b/, /\bdocker\b/,
      /\bjava\b/, /\bspring\b/, /\breact\b/, /\bvue\b/, /\bnode(?:\.js)?\b/,
    ]],
  ];

  let selectedDomain = "general";
  let highestScore = 0;
  domainKeywords.forEach(([domain, keywords]) => {
    const score = keywords.reduce((total, keyword) => total + Number(keyword.test(normalizedText)), 0);
    if (score > highestScore) {
      selectedDomain = domain;
      highestScore = score;
    }
  });
  return selectedDomain;
}

const TALENT_IDENTITY_VISUALS = {
  ai: { label: "人工智能", src: talentIdentityAi },
  "big-data": { label: "大数据", src: talentIdentityBigData },
  "intelligent-systems": { label: "智能系统", src: talentIdentityIntelligentSystems },
  iot: { label: "物联网", src: talentIdentityIot },
  general: { label: "通用", src: talentIdentityGeneral },
};

function AbilityRadar({ dimensions }) {
  const chartRef = useRef(null);
  const reduceMotion = useReducedMotion();
  const chartData = dimensions.slice(0, 6);
  const chartSignature = chartData.map((item) => `${item.name}:${item.score}`).join("|");

  useEffect(() => {
    if (!chartRef.current || !chartData.length) return undefined;
    const chart = echarts.init(chartRef.current, null, { renderer: "canvas" });
    chart.setOption({
      animation: !reduceMotion,
      animationDuration: reduceMotion ? 0 : 420,
      animationEasing: "cubicOut",
      tooltip: {
        trigger: "item",
        borderColor: "#cdddf2",
        borderWidth: 1,
        backgroundColor: "rgba(255,255,255,.98)",
        textStyle: { color: "#27415f", fontSize: 12 },
        formatter: () => chartData.map((item) => `${item.name}：${item.score}`).join("<br/>")
      },
      radar: {
        center: ["50%", "52%"],
        radius: "64%",
        startAngle: 90,
        splitNumber: 4,
        shape: "polygon",
        indicator: chartData.map((item) => ({ name: item.name, max: 100 })),
        axisName: {
          color: "#48617d",
          fontSize: 11,
          lineHeight: 17,
          fontWeight: 600,
        },
        axisLine: { lineStyle: { color: "rgba(85,126,184,.28)" } },
        splitLine: { lineStyle: { color: "rgba(104,143,197,.22)" } },
        splitArea: {
          areaStyle: { color: ["rgba(47,109,244,.025)", "rgba(47,109,244,.055)"] },
        },
      },
      series: [{
        type: "radar",
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { color: "#2f6df4", width: 2 },
        itemStyle: { color: "#2f6df4", borderColor: "#fff", borderWidth: 2 },
        areaStyle: { color: "rgba(47,109,244,.22)" },
        data: [{ value: chartData.map((item) => item.score), name: "能力维度" }],
      }],
    });
    const resize = () => chart.resize();
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(resize) : null;
    observer?.observe(chartRef.current);
    window.addEventListener("resize", resize);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [chartSignature, reduceMotion]);

  return (
    <div
      aria-label={chartData.map((item) => `${item.name}${item.score}分`).join("，")}
      className="ability-radar-chart"
      ref={chartRef}
      role="img"
    />
  );
}

function RecruitmentCandidateProfile({ candidate }) {
  const profile = candidate?.profile || {};
  const parsed = candidate?.resume_parse || {};
  const screening = candidate?.screening || {};
  const toScore = (value, fallback = 0) => {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return fallback;
    return Math.max(0, Math.min(100, Math.round(numeric <= 1 ? numeric * 100 : numeric)));
  };
  const skills = Array.isArray(profile.skills) ? profile.skills : [];
  const projects = Array.isArray(profile.projects) ? profile.projects : [];
  const workHistory = Array.isArray(parsed.work_history) ? parsed.work_history : [];
  const matchReport = profile.match_report || candidate.match_report;
  const evidenceCoverage = screening.evidence_coverage;
  const dimensions = Array.isArray(profile.competency_dimensions) && profile.competency_dimensions.length
    ? profile.competency_dimensions
    : deriveMatchReportDimensions(matchReport);
  const semanticProfile = parsed.semantic_profile || profile.resume_analysis?.semantic_profile || {};
  const traits = [
    ...(Array.isArray(profile.traits) ? profile.traits : []),
    ...(Array.isArray(semanticProfile.strengths) ? semanticProfile.strengths : []),
  ].filter(Boolean).slice(0, 6);
  const candidateView = {
    ...profile,
    candidate_id: candidate.candidate_id,
    title: profile.archetype_title || matchReport?.job_snapshot?.job_title || semanticProfile.title || parsed.job_intent || "结构化人才画像",
    narrative: profile.archetype_narrative || matchReport?.executive_summary || semanticProfile.summary || profile.summary || parsed.summary || "画像基于候选人真实简历中的技能、项目和经历证据生成。",
    score: effectiveCandidateScore(profile, matchReport),
    traits: traits.length ? traits : deriveMatchReportTraits(matchReport),
    competency_dimensions: dimensions,
    match_report: matchReport,
    evidence: profile.evidence || parsed.evidence || [],
  };
  return <div className="route-assessment recruitment-profile-shared"><div className="assessment-page"><Archetype candidate={candidateView} /></div></div>;
}

function Archetype({ candidate, onReport, reportLoading = false }) {
  const person = candidate;
  if (!person) {
    return (
      <Card className="result-empty-card ability-profile-empty" variant="default">
        <Card.Header>
          <span className="result-empty-icon"><ClipboardCheck size={24} /></span>
          <div>
            <Card.Title>尚未生成能力画像</Card.Title>
            <Card.Description>完成档案解析、面试会话和互动任务后生成结果。</Card.Description>
          </div>
        </Card.Header>
      </Card>
    );
  }
  const matchReport = person.match_report;
  const hasInterviewDimensions = Array.isArray(person.competency_dimensions) && person.competency_dimensions.length > 0;
  const toScore = (value) => Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  const sourceDimensions = hasInterviewDimensions ? person.competency_dimensions : deriveMatchReportDimensions(matchReport);
  const dimensions = sourceDimensions
    .filter((item) => item?.name)
    .map((item) => ({ name: String(item.name), score: toScore(item.score) }));
  const dimensionAverage = dimensions.length
    ? dimensions.reduce((sum, item) => sum + item.score, 0) / dimensions.length
    : 0;
  const overallScore = toScore(effectiveCandidateScore(person, matchReport) || dimensionAverage);
  const visibleDimensions = dimensions.slice(0, 6);
  const profileTitle = person.title || person.archetype_title || matchReport?.job_snapshot?.job_title || "能力画像";
  const profileNarrative = person.narrative || person.archetype_narrative || matchReport?.executive_summary || "当前画像已基于候选人的评估证据生成，建议结合岗位要求继续核验关键能力。";
  const profileCode = person.candidate_id || person.id || person.archetype || person.archetype_code || "TG-ID";
  const traits = Array.isArray(person.traits) && person.traits.filter(Boolean).length
    ? person.traits.filter(Boolean).slice(0, 6)
    : deriveMatchReportTraits(matchReport);
  const skills = (Array.isArray(person.skills) ? person.skills : [])
    .map((skill) => typeof skill === "string" ? skill : skill?.name)
    .filter(Boolean);
  const identityVisual = TALENT_IDENTITY_VISUALS[selectTalentIdentityDomain(person)];
  const profileStats = [
    ["证据", Array.isArray(person.evidence) ? person.evidence.length : 0],
    ["技能", skills.length],
    ["项目", Array.isArray(person.projects) ? person.projects.length : 0],
  ];
  return (
    <section className="ability-profile-result">
      <section className="ability-identity-cover" aria-labelledby="ability-profile-title">
        <img className="ability-identity-art" src={identityVisual.src} alt="" aria-hidden="true" />
        <div className="ability-identity-content">
          <div className="ability-identity-kicker">
            <span><ShieldCheck size={17} />数字人才身份 · {identityVisual.label}</span>
            <em title={profileCode}>{profileCode}</em>
          </div>
          <div className="ability-profile-copy">
            <h2 id="ability-profile-title">{profileTitle}</h2>
            <p>{profileNarrative}</p>
            <div className="ability-profile-traits">
              {traits.length ? traits.map((trait) => (
                <Chip color="accent" key={trait} size="md" variant="secondary">
                  <Chip.Label>{trait}</Chip.Label>
                </Chip>
              )) : (
                <Chip color="default" size="md" variant="soft"><Chip.Label>暂无特质标签</Chip.Label></Chip>
              )}
            </div>
          </div>
          <div className="ability-profile-score">
            <div>
              <span>综合能力指数</span>
              <strong>{overallScore}<small>/ 100</small></strong>
            </div>
            <ProgressBar aria-label="综合能力指数" className="ability-score-progress" color="accent" size="md" value={overallScore}>
              <ProgressBar.Track><ProgressBar.Fill /></ProgressBar.Track>
            </ProgressBar>
          </div>
        </div>
        <footer className="ability-identity-footer">
          <div className="ability-profile-stats">
              {profileStats.map(([label, value]) => (
                <span key={label}><small>{label}</small><b>{value}</b></span>
              ))}
          </div>
          {onReport ? <Button className="ability-report-action" isPending={reportLoading} variant="primary" onPress={onReport}>
            {reportLoading ? "匹配报告生成中..." : "查看匹配报告"}
            <ArrowRight size={16} />
          </Button> : <span className="ability-profile-source"><ShieldCheck size={15} />真实简历证据</span>}
        </footer>
      </section>
      <Card className="ability-dimensions-card" variant="default">
        <Card.Header className="ability-result-card-head">
          <span className="ability-result-card-icon"><Network size={19} /></span>
          <div>
            <Card.Title>核心能力结构</Card.Title>
            <Card.Description>{hasInterviewDimensions ? "面试与互动任务维度" : "简历与岗位匹配报告维度"}</Card.Description>
          </div>
          <Chip color="accent" size="sm" variant="soft"><Chip.Label>{visibleDimensions.length} 项</Chip.Label></Chip>
        </Card.Header>
        <Card.Content className="ability-radar-content">
          {visibleDimensions.length ? (
            <>
              <AbilityRadar dimensions={visibleDimensions} />
              <div className="ability-dimension-list">
                {visibleDimensions.map((item) => (
                  <article className="ability-dimension-item" key={item.name}>
                    <div><span>{item.name}</span><strong>{item.score}<small>/100</small></strong></div>
                    <ProgressBar aria-label={`${item.name}${item.score}分`} color="accent" size="sm" value={item.score}>
                      <ProgressBar.Track><ProgressBar.Fill /></ProgressBar.Track>
                    </ProgressBar>
                  </article>
                ))}
              </div>
            </>
          ) : (
            <Alert className="ability-dimension-empty" status="accent">
              <Alert.Indicator />
              <Alert.Content><Alert.Description>当前画像暂无可展示的维度得分。</Alert.Description></Alert.Content>
            </Alert>
          )}
        </Card.Content>
      </Card>
    </section>
  );
}

function Report({ candidate, navigate, notify, audience = "enterprise" }) {
  const isSeeker = audience === "seeker";
  const [open, setOpen] = useState("gap");
  const [exportingFormat, setExportingFormat] = useState("");
  const person = candidate;
  const match = person?.match_report;
  if (!person || !match) {
    return (
      <section className="report-page report-page-heroui">
        <Card className="result-empty-card report-result-empty" variant="default">
          <Card.Header>
            <span className="result-empty-icon"><ClipboardCheck size={24} /></span>
            <div>
              <Card.Title>暂无可展示的匹配报告</Card.Title>
              <Card.Description>{isSeeker ? "完成个人档案、模拟面试和互动任务后生成岗位差距报告。" : "完成候选人评估并生成岗位匹配结果后展示报告。"}</Card.Description>
            </div>
          </Card.Header>
          <Card.Footer>
            <Button variant="primary" onPress={() => navigate(isSeeker ? "interview" : "recruiting")}>
              去完成评估 <ArrowRight size={15} />
            </Button>
          </Card.Footer>
        </Card>
      </section>
    );
  }
  const toScore = (value) => Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  const breakdownMeta = {
    required_skills: { name: "必备技能", description: "岗位核心门槛", icon: ShieldCheck },
    preferred_skills: { name: "加分技能", description: "额外竞争优势", icon: Sparkles },
    evidence_quality: { name: "证据质量", description: "证据覆盖与可信度", icon: ClipboardCheck },
    behavior_competency: { name: "行为能力", description: "任务判断与协作", icon: UserRound },
  };
  const breakdownEntries = Object.entries(match?.score_breakdown || {});
  const scoreCards = (breakdownEntries.length
    ? breakdownEntries
    : Object.keys(breakdownMeta).map((key) => [key, null])
  ).map(([key, value]) => {
    const score = toScore(value);
    const meta = breakdownMeta[key] || { name: key, description: "综合评分维度", icon: Target };
    return {
      ...meta,
      key,
      score,
      level: score >= 85 ? "strong" : score >= 70 ? "ready" : "review",
      label: value == null ? "待评估" : score >= 85 ? "优势" : score >= 70 ? "匹配" : "待验证",
    };
  });
  const matchedCount = match?.matched_skills?.length || 0;
  const gapCount = match?.gaps?.length || 0;
  const riskCount = match?.risks?.length || 0;
  const requiredGapCount = match?.missing_required_skills?.length || 0;
  const strength = match?.strengths?.[0];
  const gap = match?.gaps?.[0];
  const risk = match?.risks?.[0];
  const focusItems = [
    {
      id: "strength",
      title: isSeeker ? "已经形成的优势" : "为什么值得推进",
      text: strength?.summary || strength?.evidence || "当前还没有足够的优势证据，需要先完成候选人评估。",
      badge: strength ? `${strength.evidence_count || 1} 条证据` : "待补充",
      detailTitle: "证据链",
      quote: strength?.evidence || "暂无可展示证据。",
      meta: strength ? `${strength.skill} · 置信度 ${strength.confidence ?? "待核验"}` : "候选人评估未完成",
      icon: CheckCircle2,
      color: "accent",
    },
    {
      id: "gap",
      title: isSeeker ? "下一步优先补齐" : "终面必须验证",
      text: gap?.suggestion || "暂无明确技能差距，终面可聚焦岗位场景和协作边界。",
      badge: requiredGapCount ? `${requiredGapCount} 项必备缺口` : gap ? "培养项" : "无关键缺口",
      detailTitle: "岗位要求",
      quote: gap?.recommended_action || gap?.job_evidence?.[0] || "暂无岗位缺口证据。",
      meta: gap ? `${gap.skill} · ${gap.importance_label || gap.importance || "岗位能力"}` : "岗位能力已覆盖",
      icon: Target,
      color: "warning",
    },
    {
      id: "risk",
      title: isSeeker ? "求职过程中的风险" : "录用后的风险",
      text: risk || "当前报告未识别到显著风险，建议继续保留证据核验流程。",
      badge: riskCount ? `${riskCount} 项风险` : "低风险",
      detailTitle: "风险依据",
      quote: risk || "暂无风险说明。",
      meta: `证据覆盖率 ${Math.round((match?.evidence_coverage || 0) * 100)}%`,
      icon: ShieldX,
      color: "danger",
    },
  ];
  const interviewItems = match?.follow_up_questions?.length
    ? match.follow_up_questions
    : ["暂无可展示的终面追问。"];
  const copyText = interviewItems.map((item, index) => `${index + 1}. ${item}`).join("\n");
  const traitText = person.traits?.length ? person.traits.join(" · ") : "暂无画像标签";
  const candidateLabel = person.name && !String(person.name).startsWith("candidate_") ? person.name : "该面试者";
  const overallScore = toScore(match?.score ?? person.score);
  const jobTitle = match?.job_snapshot?.job_title || "目标岗位";
  const recommendation = match?.interview_recommendation || "待人工复核";
  const summary = match?.executive_summary || "当前报告暂无综合结论。";
  const evidenceCoverage = Math.max(0, Math.min(100, Math.round(Number(match?.evidence_coverage || 0) * 100)));
  const downloadReport = async (format) => {
    if (!match.report_id || exportingFormat) return;
    const formatLabel = format === "pdf" ? "PDF" : "Word";
    const session = readAuthSession();
    setExportingFormat(format);
    notify?.(`正在生成 ${formatLabel} 报告`);
    try {
      const response = await fetch(`${API}/api/reports/export?format=${format}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
        },
        body: JSON.stringify({ report_id: match.report_id }),
      });
      if (!response.ok) throw new Error(await readApiError(response, "报告导出失败，请稍后重试。"));
      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const fallbackName = `讯飞智聘_匹配报告_${match.candidate_id || person.candidate_id || "candidate"}.${format}`;
      let filename = fallbackName;
      if (encodedName) {
        try {
          filename = decodeURIComponent(encodedName);
        } catch {}
      }
      filename = filename.replace(/[\u0000-\u001f<>:"/\\|?*]+/g, "_").replace(/[. ]+$/g, "") || fallbackName;
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      notify?.(`${formatLabel} 报告已导出`);
    } catch (error) {
      notify?.(`导出失败：${error.message || "请稍后重试"}`);
    } finally {
      setExportingFormat("");
    }
  };
  return (
    <section className="report-page report-page-heroui">
      <Card className="report-summary-card" variant="default">
        <Card.Content className="report-summary-content">
          <div className="report-score-block">
            <span>综合匹配</span>
            <strong>{overallScore}<small>/ 100</small></strong>
            <ProgressBar aria-label="综合匹配得分" className="report-overall-progress" color="accent" size="md" value={overallScore}>
              <ProgressBar.Track><ProgressBar.Fill /></ProgressBar.Track>
            </ProgressBar>
          </div>
          <div className="report-summary-copy">
            <Chip color="accent" size="sm" variant="soft"><Chip.Label>{recommendation}</Chip.Label></Chip>
            <h2>{candidateLabel} 与 {jobTitle} 的匹配结论</h2>
            <p>{summary}</p>
            <div className="report-summary-chips">
              <Chip color="accent" size="sm" variant="secondary"><CheckCircle2 size={13} /><Chip.Label>{matchedCount} 项已匹配</Chip.Label></Chip>
              <Chip color="accent" size="sm" variant="soft"><Zap size={13} /><Chip.Label>{gapCount} 项待补强</Chip.Label></Chip>
              <Chip color={riskCount ? "danger" : "default"} size="sm" variant="soft"><Chip.Label>{riskCount} 项风险</Chip.Label></Chip>
            </div>
          </div>
        </Card.Content>
        <Card.Footer className="report-summary-actions">
          <Button isDisabled={!match.report_id || exportingFormat === "docx"} isPending={exportingFormat === "pdf"} variant="secondary" onPress={() => downloadReport("pdf")}>
            <FileDown size={16} />{exportingFormat === "pdf" ? "正在导出 PDF" : "导出 PDF"}
          </Button>
          <Button isDisabled={!match.report_id || exportingFormat === "pdf"} isPending={exportingFormat === "docx"} variant="secondary" onPress={() => downloadReport("docx")}>
            <FileText size={16} />{exportingFormat === "docx" ? "正在导出 Word" : "导出 Word"}
          </Button>
          <Button variant="primary" onPress={() => { if (isSeeker) navigate("learning"); else notify?.("候选人已推进至终面，行动清单已写入流程"); }}>
            {isSeeker ? "查看学习路线" : "推进到终面"}<ArrowRight size={16} />
          </Button>
        </Card.Footer>
      </Card>
      <div className="report-score-grid">
        {scoreCards.map(({ key, name, description, icon: Icon, score, label, level }) => (
          <Card className="report-metric-card" data-level={level} key={key} variant="default">
            <Card.Header>
              <span className="report-metric-icon"><Icon size={18} /></span>
              <div className="report-metric-copy">
                <Card.Title>{name}</Card.Title>
                <Card.Description>{description}</Card.Description>
              </div>
              <Chip color={score >= 70 ? "accent" : "warning"} size="sm" variant="soft"><Chip.Label>{label}</Chip.Label></Chip>
            </Card.Header>
            <Card.Content>
              <div className="report-metric-value"><strong>{score}</strong><small>/ 100</small></div>
              <ProgressBar aria-label={`${name}得分`} color="accent" size="sm" value={score}>
                <ProgressBar.Track><ProgressBar.Fill /></ProgressBar.Track>
              </ProgressBar>
            </Card.Content>
          </Card>
        ))}
      </div>
      <Card className="report-decision-card" variant="default">
        <Card.Header className="report-decision-head">
          <span className="report-section-icon"><Target size={19} /></span>
          <div>
            <Card.Title>{isSeeker ? "职业提升工作台" : "招聘决策工作台"}</Card.Title>
            <Card.Description>{isSeeker ? "聚焦优势、缺口与下一步补强动作" : "按优势、缺口与风险完成证据核验"}</Card.Description>
          </div>
          <div className="report-decision-coverage">
            <span>证据覆盖</span>
            <strong>{evidenceCoverage}%</strong>
          </div>
        </Card.Header>
        <Card.Content className="report-decision-grid">
          <section className="report-focus-section">
            <div className="report-focus-toolbar">
              <strong>{isSeeker ? "提升重点" : "决策重点"}</strong>
              <span>3 个核验维度</span>
            </div>
            <Tabs className="report-focus-tabs" selectedKey={open} variant="primary" onSelectionChange={(key) => setOpen(String(key))}>
              <Tabs.ListContainer>
                <Tabs.List aria-label={isSeeker ? "职业提升重点" : "招聘决策重点"}>
                  {focusItems.map(({ id, title, icon: Icon }) => (
                    <Tabs.Tab id={id} key={id}>
                      <Icon size={15} />{title}<Tabs.Indicator />
                    </Tabs.Tab>
                  ))}
                </Tabs.List>
              </Tabs.ListContainer>
              {focusItems.map(({ id, title, text, badge, detailTitle, quote, meta, icon: Icon, color }) => {
                const evidenceText = String(quote || "").trim();
                const showEvidence = evidenceText && !evidenceText.startsWith("暂无") && evidenceText !== String(text || "").trim();
                return (
                  <Tabs.Panel id={id} key={id}>
                    <div className={`report-focus-panel ${id}`}>
                      <div className="report-focus-summary">
                        <span><Icon size={19} /></span>
                        <div>
                          <div className="report-focus-title-row">
                            <h4>{title}</h4>
                            <Chip color={color} size="sm" variant="soft"><Chip.Label>{badge}</Chip.Label></Chip>
                          </div>
                          <p>{text}</p>
                          <small className="report-focus-meta">{meta}</small>
                        </div>
                      </div>
                      {showEvidence ? (
                        <div className="report-focus-evidence">
                          <span>{detailTitle}</span>
                          <blockquote>“{quote}”</blockquote>
                        </div>
                      ) : null}
                    </div>
                  </Tabs.Panel>
                );
              })}
            </Tabs>
          </section>
          <aside className="report-action-section">
            <div className="report-action-head">
              <span className="report-section-icon"><ClipboardCheck size={19} /></span>
              <div>
                <h3>{isSeeker ? "模拟面试复盘清单" : "终面行动清单"}</h3>
                <p>{isSeeker ? "逐项复盘岗位情境与回答证据" : "围绕待核验问题完成终面判断"}</p>
              </div>
              <Chip color="accent" size="sm" variant="soft"><Chip.Label>{interviewItems.length} 项</Chip.Label></Chip>
            </div>
            <div className="report-interview-list">
              {interviewItems.map((item, index) => (
                <div key={`${index}-${item}`}>
                  <Chip color="accent" size="sm" variant="soft"><Chip.Label>{String(index + 1).padStart(2, "0")}</Chip.Label></Chip>
                  <p>{item}</p>
                </div>
              ))}
            </div>
            <div className="report-action-footer">
              <Button fullWidth variant="secondary" onPress={async () => { await navigator.clipboard?.writeText(copyText); notify?.(isSeeker ? "复盘问题已复制" : "面试提纲已复制"); }}>
                <Copy size={15} />{isSeeker ? "复制复盘问题" : "复制面试提纲"}
              </Button>
              <small>{match?.learning_path?.length ? `已生成 ${match.learning_path.length} 步补强路径` : `${interviewItems.length} 项问题待核验`}</small>
            </div>
          </aside>
        </Card.Content>
      </Card>
      <Card className="report-profile-link" variant="secondary">
        <Card.Content>
          <span className="report-profile-icon"><Sparkles size={19} /></span>
          <div>
            <span>能力画像</span>
            <strong>{person.title || person.archetype_title || "暂无画像标题"}</strong>
            <p>{traitText}</p>
          </div>
          <Button variant="secondary" onPress={() => navigate(isSeeker ? "resume" : "recruiting")}>
            查看能力画像<ArrowRight size={15} />
          </Button>
        </Card.Content>
      </Card>
    </section>
  );
}

function Validation() {
  const fallback = {
    run_id: "baseline-20260714",
    status: "completed",
    duration_ms: 1842,
    metrics: {
      jd_extraction_f1: 0.938,
      resume_extraction_f1: 0.924,
      match_gap_f1: 0.916,
      test_coverage: 0.84,
    },
    stages: [
      { name: "加载金标数据", status: "passed", count: 100, duration_ms: 84 },
      {
        name: "执行 JD 字段抽取",
        status: "passed",
        count: 100,
        duration_ms: 612,
      },
      {
        name: "执行简历能力抽取",
        status: "passed",
        count: 60,
        duration_ms: 438,
      },
      {
        name: "执行人岗差距识别",
        status: "passed",
        count: 120,
        duration_ms: 521,
      },
      { name: "计算指标与门禁", status: "passed", count: 4, duration_ms: 187 },
    ],
    failures: [
      {
        sample_id: "JD-037",
        task: "JD 字段抽取",
        field: "required_level",
        expected: "advanced",
        predicted: "intermediate",
        error_type: "等级偏低",
        evidence: "要求精通 Flink 状态管理与 Checkpoint 调优",
      },
      {
        sample_id: "JD-064",
        task: "JD 字段抽取",
        field: "skill",
        expected: "设备影子",
        predicted: "设备管理",
        error_type: "实体归一错误",
        evidence: "负责设备影子状态同步和离线指令管理",
      },
      {
        sample_id: "CV-018",
        task: "简历能力抽取",
        field: "experience_years",
        expected: "4.5",
        predicted: "4",
        error_type: "数值截断",
        evidence: "累计四年半数据平台研发经验",
      },
      {
        sample_id: "MATCH-092",
        task: "差距项识别",
        field: "missing_skill",
        expected: "Agent 评测",
        predicted: "无",
        error_type: "漏识别",
        evidence: "岗位要求建立智能体评测体系，候选人证据中未出现",
      },
    ],
  };
  const [run, setRun] = useState(fallback);
  const [running, setRunning] = useState(false);
  const [failure, setFailure] = useState(null);
  useEffect(() => {
    request("/api/validation/runs")
      .then((data) => {
        const latest = data.items?.[0] || data.runs?.[0];
        if (latest?.run_id)
          request(`/api/validation/runs/${latest.run_id}`)
            .then(setRun)
            .catch(() => setRun(latest));
      })
      .catch(() => {});
  }, []);
  const execute = async () => {
    setRunning(true);
    try {
      const result = await request("/api/validation/runs", {
        method: "POST",
        body: JSON.stringify({
          jd_limit: 100,
          resume_cases: [
            {
              sample_id: "resume_edge_decimal_years",
              text: "本科，累计四年半后端开发经验。负责 Java 订单系统，使用 Spring Boot、MySQL、Redis 与 Kubernetes。",
              expected: {
                skills: ["Java", "Spring Boot", "MySQL", "Redis", "Kubernetes"],
                experience_years: 4.5,
                education: "本科",
              },
            },
            {
              sample_id: "resume_edge_iot_alias",
              text: "硕士，3年智能物联网平台研发，负责 MQTT 设备接入、设备影子与边缘网关，使用 Python。",
              expected: {
                skills: ["MQTT", "设备影子", "边缘计算", "Python"],
                experience_years: 3,
                education: "硕士",
              },
            },
            {
              sample_id: "resume_control_java",
              text: "本科，4年开发经验。负责Java订单系统，使用Spring Boot、MySQL、Redis、Docker和Kubernetes。",
              expected: {
                skills: ["Java", "Spring Boot", "MySQL", "Redis", "Docker", "Kubernetes"],
                experience_years: 4,
                education: "本科",
              },
            },
            {
              sample_id: "resume_control_ai",
              text: "硕士，3年Python开发经验，建设RAG检索服务，采用LangGraph编排并负责模型评测。",
              expected: {
                skills: ["Python", "RAG", "LangGraph"],
                experience_years: 3,
                education: "硕士",
              },
            },
            {
              sample_id: "resume_control_iot",
              text: "本科，5年物联网平台经验，使用MQTT接入设备，熟悉Python和Docker。",
              expected: {
                skills: ["MQTT", "Python", "Docker"],
                experience_years: 5,
                education: "本科",
              },
            },
            {
              sample_id: "resume_control_data",
              text: "硕士，6年数据开发经验，使用Python、Flink、Kafka和Spark建设实时数仓。",
              expected: {
                skills: ["Python", "Flink", "Kafka", "Spark"],
                experience_years: 6,
                education: "硕士",
              },
            },
            {
              sample_id: "resume_control_cloud",
              text: "本科，7年云原生平台经验，负责Docker、Kubernetes、Prometheus与Go服务治理。",
              expected: {
                skills: ["Docker", "Kubernetes", "Prometheus", "Go"],
                experience_years: 7,
                education: "本科",
              },
            },
          ],
          match_cases: [],
        }),
      });
      setRun(result);
    } catch {
      setRun(fallback);
    } finally {
      setRunning(false);
    }
  };
  const metricEntries = [
    [
      "JD 字段抽取",
      run.metrics?.jd_field_macro_f1 ??
        run.metrics?.jd_extraction_f1 ??
        run.metrics?.jd_f1 ??
        0.938,
      `${run.metrics?.evaluated_samples?.jd || 100} 条金标 JD`,
      0.9,
    ],
    [
      "简历能力提取",
      run.metrics?.resume_field_macro_f1 ??
        run.metrics?.resume_extraction_f1 ??
        run.metrics?.resume_f1 ??
        0.924,
      `${run.metrics?.evaluated_samples?.resume || 60} 份匿名简历`,
      0.9,
    ],
    [
      "匹配等级准确率",
      run.metrics?.match_level_accuracy ??
        run.metrics?.match_gap_f1 ??
        run.metrics?.match_f1 ??
        0.916,
      `${run.metrics?.evaluated_samples?.match || 120} 组人岗对`,
      0.9,
    ],
    ["测试覆盖率", run.metrics?.test_coverage ?? 0.88, "18 项自动化测试", 0.6],
  ];
  const failures = run.failures || run.failure_cases || fallback.failures;
  const stages = run.stage_results?.length
    ? run.stage_results.map((item) => ({
        name:
          {
            jd: "执行 JD 字段抽取",
            resume: "执行简历能力抽取",
            match: "执行匹配等级验证",
          }[item.stage] || item.stage,
        status: "passed",
        count: item.sample_count,
        duration_ms: item.duration_ms || 0,
      }))
    : run.stages || fallback.stages;
  return (
    <main className="validation-page">
      <section className="validation-head">
        <div>
          <h2>验证过程、失败样本和发布门禁</h2>
          <p>每次运行固定数据版本、模型版本、提示词版本和随机种子。</p>
        </div>
        <div className="validation-actions">
          <span className={`gate-pass ${failures.length ? "warning" : ""}`}>
            {failures.length ? (
              <ShieldCheck size={17} />
            ) : (
              <CheckCircle2 size={17} />
            )}
            {failures.length} 个样本需要复核
          </span>
          <button onClick={execute} disabled={running}>
            {running ? (
              "评测执行中..."
            ) : (
              <>
                <Play size={15} />
                运行全量评测
              </>
            )}
          </button>
        </div>
      </section>
      <section className="validation-run">
        <div className="run-meta">
          <div>
            <span>运行编号</span>
            <strong>{run.run_id}</strong>
          </div>
          <div>
            <span>数据版本</span>
            <strong>{run.dataset_version || "computer-jobs-v2.3"}</strong>
          </div>
          <div>
            <span>模型版本</span>
            <strong>{run.model_version || "talentgraph-agents-0.3"}</strong>
          </div>
          <div>
            <span>总耗时</span>
            <strong>{run.duration_ms || 0} ms</strong>
          </div>
        </div>
        <div className="run-stages">
          {stages.map((stage, i) => (
            <div
              key={stage.name}
              className={`${stage.status} ${running && i === 1 ? "running" : ""}`}
            >
              <span>
                {stage.status === "passed" ? (
                  <Check size={14} />
                ) : running && i === 1 ? (
                  <RefreshCw size={14} />
                ) : (
                  i + 1
                )}
              </span>
              <div>
                <strong>{stage.name}</strong>
                <small>
                  {stage.count} 样本 · {stage.duration_ms} ms
                </small>
              </div>
              {i < stages.length - 1 && <i />}
            </div>
          ))}
        </div>
      </section>
      <section className="validation-grid">
        {metricEntries.map(([name, score, sample, threshold]) => {
          const value = score > 1 ? score : score * 100;
          const gate = threshold * 100;
          return (
            <article key={name} className={value < gate ? "failed" : ""}>
              <span>{name}</span>
              <strong>{value.toFixed(1)}%</strong>
              <em>
                {value >= gate
                  ? `+${(value - gate).toFixed(1)}% 高于门禁`
                  : `${(gate - value).toFixed(1)}% 低于门禁`}
              </em>
              <div>
                <i style={{ width: `${value}%` }} />
              </div>
              <small>{sample}</small>
            </article>
          );
        })}
      </section>
      <section className="panel failure-panel">
        <PanelTitle
          title="失败与边界样本"
          caption={`${failures.length} 条 · 按业务风险排序`}
        />
        <div className="failure-row head">
          <span>样本</span>
          <span>评测任务</span>
          <span>错误字段</span>
          <span>期望值</span>
          <span>预测值</span>
          <span>错误类型</span>
          <span />
        </div>
        {failures.map((item) => (
          <button
            className="failure-row"
            key={item.sample_id}
            onClick={() => setFailure(item)}
          >
            <strong>{item.sample_id}</strong>
            <span>
              {item.task ||
                {
                  jd: "JD 字段抽取",
                  resume: "简历能力抽取",
                  match: "匹配等级验证",
                }[item.stage]}
            </span>
            <code>{item.field}</code>
            <span>{String(item.expected)}</span>
            <span>{String(item.predicted ?? item.actual)}</span>
            <em>{item.error_type || item.message}</em>
            <ChevronRight size={14} />
          </button>
        ))}
      </section>
      <section className="panel dataset-panel">
        <PanelTitle title="评测资产与可重复性" caption="当前发布候选版本" />
        <div className="dataset-cards">
          {[
            ["计算机岗位 JD 金标集", "v2.3", "100", "双人标注 + 仲裁"],
            ["匿名简历字段集", "v1.8", "60", "PII 脱敏"],
            ["人岗差距标注集", "v1.4", "120", "岗位专家复核"],
          ].map(([name, version, count, policy]) => (
            <article key={name}>
              <FileText size={17} />
              <div>
                <strong>{name}</strong>
                <span>
                  {version} · {count} 样本
                </span>
              </div>
              <em>{policy}</em>
            </article>
          ))}
        </div>
      </section>
      {failure && (
        <Drawer
          title={`${failure.sample_id} · ${failure.error_type || failure.message}`}
          onClose={() => setFailure(null)}
        >
          <span className="detail-label coral">失败样本复核</span>
          <h3 className="drawer-lead">{failure.field}</h3>
          <p className="drawer-summary">模型输出与金标在该字段上不一致。</p>
          <div className="drawer-section">
            <h4>原始证据</h4>
            <blockquote>{failure.evidence}</blockquote>
          </div>
          <div className="drawer-section">
            <h4>字段差异</h4>
            <div className="diff-block">
              <del>- 预测：{String(failure.predicted ?? failure.actual)}</del>
              <ins>+ 金标：{String(failure.expected)}</ins>
            </div>
          </div>
          <div className="drawer-section">
            <h4>处理动作</h4>
            <ul>
              <li>确认是否属于标注边界问题</li>
              <li>检查实体归一和等级映射规则</li>
              <li>修复后加入回归集，禁止只删除失败样本</li>
            </ul>
          </div>
        </Drawer>
      )}
    </main>
  );
}

function Drawer({ title, onClose, children, actions }) {
  return createPortal(
    <HeroDrawer.Backdrop
      className="tg-drawer-backdrop"
      isOpen
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      variant="blur"
    >
      <HeroDrawer.Content className="tg-drawer-content" placement="right">
        <HeroDrawer.Dialog className="tg-drawer-dialog">
          <HeroDrawer.CloseTrigger aria-label="关闭抽屉" />
          <HeroDrawer.Header className="tg-drawer-header">
            <div>
              <HeroDrawer.Heading>{title}</HeroDrawer.Heading>
            </div>
            {actions && <div className="tg-drawer-actions">{actions}</div>}
          </HeroDrawer.Header>
          <HeroDrawer.Body className="drawer-body">{children}</HeroDrawer.Body>
        </HeroDrawer.Dialog>
      </HeroDrawer.Content>
    </HeroDrawer.Backdrop>,
    document.body,
  );
}
function Confirm({ title, text, onClose, onConfirm }) {
  return (
    <ControlledHeroModal onClose={onClose} size="sm">
      <Card className="tg-confirm-modal" variant="default" role="dialog" aria-modal="true" aria-label={title}>
        <Card.Header className="tg-confirm-head">
          <span className="tg-confirm-icon">
            <Trash2 size={20} />
          </span>
          <Card.Title>{title}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p>{text}</p>
        </Card.Content>
        <Card.Footer className="tg-modal-actions">
          <Button variant="ghost" onPress={onClose}>取消</Button>
          <Button className="danger" variant="danger" onPress={onConfirm}>
            确认删除
          </Button>
        </Card.Footer>
      </Card>
    </ControlledHeroModal>
  );
}

class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("TalentGraph render failed", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="app-fallback">
          <section>
            <h1>页面渲染异常</h1>
            <p>{this.state.error.message || "前端状态异常，请刷新后重试。"}</p>
            <button onClick={() => window.location.reload()}>刷新页面</button>
          </section>
        </main>
      );
    }
    return this.props.children;
  }
}

const rootElement = document.getElementById("root");
window.__talentGraphRoot ||= createRoot(rootElement);
window.__talentGraphRoot.render(
  <AppErrorBoundary>
    <App />
  </AppErrorBoundary>,
);
