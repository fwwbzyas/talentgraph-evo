import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import * as echarts from "echarts/core";
import { RadarChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { Button, Card, Chip, ComboBox, Input, Label, ListBox, Pagination, ProgressBar, SearchField, Table, Tabs } from "@heroui/react";
import abilityCourseCover from "./assets/ability-core-prism.webp";
import {
  ArrowRight,
  BookOpenCheck,
  BriefcaseBusiness,
  ChevronRight,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  ExternalLink,
  FileSearch,
  FileText,
  Gamepad2,
  GraduationCap,
  LayoutDashboard,
  Map,
  Network,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Upload,
} from "lucide-react";

echarts.use([RadarChart, TooltipComponent, CanvasRenderer]);

export const ROLE_NAV = {
  enterprise: [
    ["经营决策", [["dashboard", "决策首页", LayoutDashboard]]],
    ["数据中心", [["data", "岗位数据", BriefcaseBusiness]]],
    [
      "岗位智能",
      [
        ["graph", "能力图谱", Network],
        ["evolution", "新岗位与演化", TrendingUp],
      ],
    ],
    [
      "人才决策",
      [
        ["recruiting", "招聘岗位与初筛", FileSearch],
        ["assessments", "候选人中心", ClipboardCheck],
      ],
    ],
  ],
  seeker: [
    ["职业空间", [["seeker-home", "职业首页", LayoutDashboard]]],
    [
      "岗位探索",
      [
        ["career-graph", "岗位能力图谱", Network],
        ["career-evolution", "岗位演化与新岗位", TrendingUp],
      ],
    ],
    [
      "能力成长",
      [
        ["resume", "我的简历", FileText],
        ["applications", "岗位投递", BriefcaseBusiness],
        ["interview", "模拟面试", Gamepad2],
        ["gap", "差距分析", Target],
        ["learning", "学习路线", GraduationCap],
      ],
    ],
  ],
};

export const ROLE_META = {
  enterprise: {
    dashboard: ["决策首页", "今日岗位与人才决策摘要"],
    data: ["岗位数据", "新一代信息技术岗位全生命周期管理"],
    graph: ["岗位能力图谱", "城市、岗位族、技能与招聘证据"],
    evolution: ["新岗位与演化", "识别岗位形成与能力要求变化"],
    assessments: ["候选人中心", "候选人画像、报告与复评记录"],
    assessment: ["候选人初筛", "简历报告、全岗位差距与面试问题"],
    recruiting: ["招聘岗位与初筛", "企业在招岗位、候选人证据链与替代岗位洞察"],
    report: ["企业匹配报告", "招聘结论、能力证据与面试行动"],
    validation: ["验证中心", "数据、模型与业务质量门禁"],
  },
  seeker: {
    "seeker-home": ["职业首页", "目标岗位、能力差距与下一步行动"],
    "career-graph": ["岗位能力图谱", "探索岗位、技能层级和市场证据"],
    "career-evolution": ["岗位演化与新岗位", "查看能力变化、新岗位成熟度与市场证据"],
    resume: ["我的简历", "管理个人档案与能力画像"],
    interview: ["模拟面试", "通过深度对话与剧情任务验证能力"],
    gap: ["差距分析", "对照目标岗位定位技能缺口"],
    learning: ["学习路线", "按能力依赖规划阶段性提升"],
    applications: ["岗位投递", "发现岗位并管理个人投递进度"],
    report: ["个人匹配报告", "优势、差距与职业提升建议"],
  },
};

const statusLabels = {
  submitted: "已投递",
  viewed: "企业已查看",
  interview: "进入面试",
  offer: "已获录用",
  rejected: "暂未匹配",
  withdrawn: "已撤回",
};

const statusColors = {
  submitted: "accent",
  viewed: "accent",
  interview: "warning",
  offer: "success",
  rejected: "danger",
  withdrawn: "default",
};

const APPLICATION_PAGE_SIZE = 24;
const GAP_JOB_PAGE_SIZE = 40;

function EmptyAction({ icon: Icon, title, text, action, onAction }) {
  return (
    <Card className="seeker-empty" variant="default">
      <Card.Content>
        <Icon size={30} />
        <h3>{title}</h3>
        <p>{text}</p>
        <Button onPress={onAction}>{action}<ArrowRight size={15} /></Button>
      </Card.Content>
    </Card>
  );
}

export function SeekerDashboard({
  user,
  candidate,
  applications,
  jobs,
  targetJob,
  setTargetJob,
  navigate,
  platformSummary,
  portalSummary,
}) {
  const decision = portalSummary?.decision_summary || platformSummary?.decision_summary || {};
  const evidence = decision.evidence || {};
  const report = candidate?.match_report;
  const candidateSkills = new Set((candidate?.skills || []).map((skill) => (
    typeof skill === "string" ? skill : skill.name
  )).filter(Boolean));
  const growthJobs = decision.growth_jobs || [];
  const declineJobs = decision.decline_jobs || [];
  const commonAbilities = decision.common_abilities || [];
  const skillGroups = [
    ["new", "新增", "值得提前布局", "positive"],
    ["enhanced", "增强", "需求正在上升", "accent"],
    ["weakened", "减弱", "重要性下降", "warning"],
    ["exited", "退出", "当前不再主流", "danger"],
  ];
  const personalState = !candidate
    ? { tone: "pending", title: "尚未建立个人能力基线", text: "上传简历后，系统才能判断你与目标岗位标准的距离。", action: "分析我的简历", route: "resume" }
    : !targetJob
      ? { tone: "pending", title: "已建立能力画像，尚未选择目标岗位", text: `已识别 ${candidateSkills.size} 项技能，选择目标岗位后可计算差距。`, action: "选择目标岗位", route: "applications" }
      : report
        ? { tone: Number(report.score || 0) >= 75 ? "current" : "outdated", title: `与目标岗位匹配度 ${report.score ?? 0}%`, text: report.gaps?.length ? `优先补齐：${report.gaps.slice(0, 3).map((item) => item.skill).join("、")}` : "核心要求已基本覆盖，继续强化项目证据与进阶能力。", action: "查看完整差距", route: "gap" }
        : { tone: "pending", title: "目标岗位差距尚未计算", text: `当前目标为 ${targetJob.title}，运行分析后可获得技能差距与学习优先级。`, action: "开始差距分析", route: "gap" };
  const foundation = [
    ["目标岗位", targetJob?.title || "待选择", "个人目标"],
    ["个人技能", candidateSkills.size, "简历证据"],
    ["市场岗位", Number(evidence.active_jobs ?? platformSummary?.active_jobs ?? 0).toLocaleString("zh-CN"), "当前在招"],
    ["版本证据", Number(evidence.version_snapshots ?? platformSummary?.version_snapshots ?? 0).toLocaleString("zh-CN"), "可追溯"],
    ["投递记录", applications.length, "个人数据"],
  ];

  const trendList = (items, emptyText, tone) => (
    <div className="career-trend-list">
      {items.slice(0, 4).map((item, index) => <button key={`${item.name}-${index}`} onClick={() => navigate("career-evolution")}><span className={tone}>{String(index + 1).padStart(2, "0")}</span><div><strong>{item.name}</strong><small>{item.reason}</small></div><b>{item.current_count}<small> 在招</small></b><ChevronRight size={15} /></button>)}
      {!items.length && <p className="career-decision-empty">{emptyText}</p>}
    </div>
  );

  return (
    <main className="seeker-page career-decision-home">
      <motion.section className="career-decision-intro" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div><span>个人职业决策</span><h2>{user?.display_name || "你好"}，先判断机会在哪里，再决定下一步补什么。</h2><p>把岗位市场变化、个人能力证据与目标岗位差距放在同一个决策面板中。</p></div>
        <div><Button variant="secondary" onPress={() => navigate("career-evolution")}><TrendingUp size={16} /> 查看岗位演化</Button><Button onPress={() => navigate(candidate ? "gap" : "resume")}><Target size={16} /> {candidate ? "分析岗位差距" : "建立能力画像"}</Button></div>
      </motion.section>

      <section className="career-decision-primary">
        <article className="career-decision-block career-opportunity-block">
          <header><div><span>01 · 职业机会与风险</span><h3>哪些方向正在增长，哪些需要谨慎选择</h3></div><Button variant="ghost" onPress={() => navigate("career-evolution")}>查看证据 <ArrowRight size={15} /></Button></header>
          <div className="career-decision-split">
            <section><div className="career-subhead positive"><TrendingUp size={16} /><strong>增长机会</strong></div>{trendList(growthJobs, "尚未形成可靠的增长岗位信号。", "positive")}</section>
            <section><div className="career-subhead danger"><TrendingDown size={16} /><strong>下降风险</strong></div>{trendList(declineJobs, "当前没有岗位退出证据。", "danger")}</section>
          </div>
        </article>

        <article className={`career-decision-block career-personal-state ${personalState.tone}`}>
          <header><div><span>02 · 个人适配状态</span><h3>我的能力是否落后于目标岗位</h3></div></header>
          <div className="career-state-main"><span><Target size={22} /></span><div><strong>{personalState.title}</strong><p>{personalState.text}</p></div></div>
          {candidateSkills.size > 0 && <div className="career-known-skills">{[...candidateSkills].slice(0, 6).map((skill) => <span key={skill}>{skill}</span>)}</div>}
          <Button fullWidth variant="secondary" onPress={() => navigate(personalState.route)}>{personalState.action}<ArrowRight size={15} /></Button>
        </article>
      </section>

      <section className="career-decision-block career-skill-changes">
        <header><div><span>03 · 市场技能变化</span><h3>哪些能力值得补，哪些正在失去优势</h3></div><small>带“已具备”标记的能力已在你的简历画像中识别</small></header>
        <div className="career-skill-grid">
          {skillGroups.map(([key, label, hint, tone]) => {
            const items = decision.skill_changes?.[key] || [];
            return <section className={tone} key={key}><div><span>{label}</span><small>{hint}</small><b>{items.length}</b></div><ul>{items.slice(0, 4).map((item) => <li key={item.name}><strong>{item.name}</strong>{candidateSkills.has(item.name) ? <em>已具备</em> : <span>{item.delta > 0 ? "+" : ""}{item.delta}</span>}</li>)}{!items.length && <li className="is-empty">暂无可靠证据</li>}</ul></section>;
          })}
        </div>
      </section>

      <section className="career-decision-block career-common-abilities">
        <header><div><span>04 · 普遍能力要求</span><h3>市场普遍要求与我的覆盖情况</h3></div><Button variant="ghost" onPress={() => navigate("career-graph")}>查看岗位关系 <ArrowRight size={15} /></Button></header>
        <div className="career-common-list">{commonAbilities.map((item, index) => { const hasSkill = candidateSkills.has(item.name); return <div key={item.name}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item.name}</strong><div><i style={{ width: `${Math.min(100, Math.max(4, item.coverage))}%` }} /></div><b>{item.coverage}%</b><em className={hasSkill ? "owned" : "missing"}>{hasSkill ? "已具备" : "待补证据"}</em></div>; })}{!commonAbilities.length && <p className="career-decision-empty">正在形成能力覆盖率统计。</p>}</div>
      </section>

      <section className="career-decision-foundation" aria-label="个人与市场数据基础">
        <div><ShieldCheck size={18} /><span>决策依据</span></div>
        {foundation.map(([label, value, detail]) => <div key={label}><span>{label}</span><strong title={String(value)}>{value}</strong><small>{detail}</small></div>)}
      </section>
    </main>
  );
}

function LegacySeekerDashboard({
  user,
  candidate,
  applications,
  jobs,
  targetJob,
  setTargetJob,
  navigate,
}) {
  const report = candidate?.match_report;
  const skills = candidate?.skills || [];
  const nextGap = report?.gaps?.[0];
  const recommended = useMemo(
    () => jobs.slice(0, 4),
    [jobs],
  );
  const dashboardMetrics = [
    {
      key: "target",
      label: "目标岗位",
      value: targetJob?.title || "尚未选择",
      detail: targetJob ? `${targetJob.company} · ${targetJob.city}` : "从岗位图谱或岗位列表中选择",
      icon: Target,
      tone: "blue",
    },
    {
      key: "match",
      label: "当前匹配度",
      value: report?.score != null ? `${report.score}%` : "—",
      detail: report ? `${report.matched_skills?.length || 0} 项技能已覆盖` : "完成评估后生成",
      icon: TrendingUp,
      tone: "green",
    },
    {
      key: "evidence",
      label: "能力证据",
      value: candidate?.evidence?.length || 0,
      detail: `${skills.length} 项技能进入个人画像`,
      icon: ClipboardCheck,
      tone: "amber",
    },
    {
      key: "applications",
      label: "投递进度",
      value: applications.length,
      detail: `${applications.filter((item) => item.status === "interview").length} 个岗位进入面试`,
      icon: Send,
      tone: "coral",
    },
  ];
  return (
    <main className="seeker-page seeker-dashboard">
      <section className="seeker-overview">
        <div className="seeker-overview-copy">
          <Chip className="seeker-overview-kicker" color="accent" size="sm" variant="soft">
            <Sparkles size={13} />
            <Chip.Label>今日职业进展</Chip.Label>
          </Chip>
          <h2>{user?.display_name || "你好"}，从目标岗位倒推下一次成长。</h2>
          <p>岗位图谱、个人证据和市场变化在同一条路径上更新。</p>
        </div>
        <div className="seeker-overview-actions">
          {targetJob && (
            <div className="seeker-overview-target">
              <span>当前目标</span>
              <strong title={targetJob.title}>{targetJob.title}</strong>
            </div>
          )}
          <Button size="lg" onPress={() => navigate(candidate ? "gap" : "interview")}>
            {candidate ? "查看当前差距" : "建立能力画像"} <ArrowRight size={16} />
          </Button>
        </div>
      </section>

      <section className="seeker-pulse" aria-label="职业进展概览">
        {dashboardMetrics.map(({ key, label, value, detail, icon: Icon, tone }) => (
          <Card className={`seeker-stat-card ${key === "target" ? "seeker-stat-card-target" : ""}`} key={key} variant="default">
            <Card.Header className="seeker-stat-header">
              <span className="seeker-stat-icon" data-tone={tone}><Icon size={17} /></span>
              <Card.Description>{label}</Card.Description>
            </Card.Header>
            <Card.Content className="seeker-stat-content">
              <Card.Title className="seeker-stat-value" title={String(value)}>{value}</Card.Title>
              <p>{detail}</p>
            </Card.Content>
          </Card>
        ))}
      </section>

      <section className="seeker-dashboard-grid">
        <Card className="seeker-next" variant="default">
          <Card.Header className="seeker-panel-header">
            <span className="seeker-panel-icon"><Sparkles size={18} /></span>
            <div>
              <Card.Description>行动建议</Card.Description>
              <Card.Title>下一步最值得做什么</Card.Title>
            </div>
          </Card.Header>
          <Card.Content className="next-action-body">
            {candidate ? (
              <>
                <strong>{nextGap?.skill || "补充目标岗位证据"}</strong>
                <p>{nextGap?.suggestion || "选择一个目标岗位，系统会按必备技能、证据强度和面试表现生成优先级。"}</p>
              </>
            ) : (
              <>
                <strong>先建立你的能力基线</strong>
                <p>上传真实简历后，系统会提取技能、项目和可验证证据，并据此生成模拟面试。</p>
              </>
            )}
          </Card.Content>
          <Card.Footer className="seeker-panel-footer">
            <Button variant="secondary" onPress={() => navigate(candidate ? (report ? "learning" : "interview") : "interview")}>
              {candidate ? (report ? "进入学习路线" : "继续模拟面试") : "上传简历并评估"}
              <ChevronRight size={15} />
            </Button>
          </Card.Footer>
        </Card>

        <Card className="seeker-skill-snapshot" variant="default">
          <Card.Header className="seeker-panel-header">
            <span className="seeker-panel-icon seeker-panel-icon-green"><TrendingUp size={18} /></span>
            <div>
              <Card.Description>能力画像</Card.Description>
              <Card.Title>个人能力快照</Card.Title>
            </div>
          </Card.Header>
          <Card.Content className={`seeker-skill-content ${skills.length ? "" : "is-empty"}`}>
            {skills.length ? (
              <div className="seeker-skill-list">
                {skills.slice(0, 8).map((skill, index) => {
                  const name = typeof skill === "string" ? skill : skill.name;
                  const score = candidate?.skill_scores?.[name] || Math.max(52, 88 - index * 5);
                  return (
                    <div className="seeker-skill-row" key={`${name}-${index}`}>
                      <div><span>{name}</span><strong>{score}</strong></div>
                      <ProgressBar aria-label={`${name}能力评分`} color="success" size="sm" value={score}>
                        <ProgressBar.Track><ProgressBar.Fill /></ProgressBar.Track>
                      </ProgressBar>
                    </div>
                  );
                })}
              </div>
            ) : (
              <Button className="skill-placeholder" variant="ghost" onPress={() => navigate("interview")}>
                <Upload size={20} /><span>上传简历后生成能力快照</span>
              </Button>
            )}
          </Card.Content>
        </Card>
      </section>

      <section className="seeker-recommendations">
        <header className="seeker-section-header">
          <div>
            <h3>正在招聘的相关岗位</h3>
            <p>优先展示与你当前目标方向相关的在招岗位</p>
          </div>
          <Button variant="ghost" onPress={() => navigate("applications")}>查看全部 <ArrowRight size={15} /></Button>
        </header>
        <div className="seeker-job-grid">
          {recommended.map((job) => (
            <Card className="seeker-job-card" key={job.id} variant="default">
              <Card.Header className="seeker-job-header">
                <Chip color="accent" size="sm" variant="soft"><Chip.Label>{job.domain}</Chip.Label></Chip>
                <Card.Title title={job.title}>{job.title}</Card.Title>
                <Card.Description>{job.company} · {job.city}</Card.Description>
              </Card.Header>
              <Card.Content className="seeker-job-tags">
                {job.tags.slice(0, 3).map((tag) => (
                  <Chip key={tag} size="sm" variant="tertiary"><Chip.Label>{tag}</Chip.Label></Chip>
                ))}
              </Card.Content>
              <Card.Footer className="seeker-job-footer">
                <Button fullWidth variant="secondary" onPress={() => { setTargetJob(job); navigate("gap"); }}>
                  <Target size={14} /> 设为目标
                </Button>
              </Card.Footer>
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}

function clampResumeScore(value) {
  return Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
}

function buildResumeEvidenceInsights(candidate) {
  const skills = (candidate.skills || []).filter((item) => item && (typeof item === "string" || item.name));
  const projects = (candidate.projects || []).filter(Boolean);
  const analysis = candidate.resume_analysis || {};
  const quality = analysis.quality_summary || {};
  const workHistory = analysis.work_history || [];
  const skillObjects = skills.filter((item) => typeof item === "object");
  const evidencedSkills = skillObjects.filter((item) => String(item.evidence || "").trim() || Number(item.confidence || 0) >= 0.7);
  const averageSkillConfidence = skillObjects.length
    ? skillObjects.reduce((sum, item) => sum + Number(item.confidence || 0.55), 0) / skillObjects.length
    : 0;
  const hasMetrics = Boolean(quality.has_quantified_metrics || projects.some((item) => item.metrics?.length));
  const averageEvidenceConfidence = Number(quality.avg_evidence_confidence || candidate.confidence || 0);
  const completenessChecks = [
    Boolean(candidate.education),
    candidate.experience_years != null,
    skills.length >= 3,
    projects.length > 0,
    workHistory.length > 0,
    Boolean(analysis.job_intent || candidate.preferred_locations?.length),
  ];
  const dimensions = [
    { name: "技能证据", value: clampResumeScore(skillObjects.length ? (evidencedSkills.length / skillObjects.length) * 100 : 0) },
    { name: "项目深度", value: clampResumeScore(projects.length * 22 + (hasMetrics ? 22 : 0) + projects.filter((item) => item.evidence).length * 8) },
    { name: "经历完整", value: clampResumeScore((candidate.experience_years != null ? 45 : 0) + workHistory.length * 18) },
    { name: "量化成果", value: hasMetrics ? 92 : projects.length ? 38 : 15 },
    { name: "档案完整", value: clampResumeScore((completenessChecks.filter(Boolean).length / completenessChecks.length) * 100) },
  ];
  const strengths = [];
  const weaknesses = [];
  if (evidencedSkills.length >= 3) strengths.push(`${evidencedSkills.length} 项技能具备项目或经历证据`);
  if (projects.length >= 2) strengths.push(`识别到 ${projects.length} 段项目经历，可用于面试核验`);
  if (hasMetrics) strengths.push("项目描述包含可量化成果，贡献边界更清晰");
  if (workHistory.length || Number(candidate.experience_years || 0) > 0) strengths.push(`工作经历已形成 ${candidate.experience_years ?? workHistory.length} 年/段经验线索`);
  if (averageEvidenceConfidence >= 0.75) strengths.push(`简历证据平均置信度 ${Math.round(averageEvidenceConfidence * 100)}%`);
  if (!projects.length) weaknesses.push("未识别到完整项目经历，难以判断实际工程深度");
  if (projects.length && !hasMetrics) weaknesses.push("项目缺少性能、效率或业务结果等量化指标");
  if (skills.length && evidencedSkills.length < Math.ceil(skills.length * 0.6)) weaknesses.push("部分技能仅被提及，缺少工作或项目使用证据");
  if (!workHistory.length) weaknesses.push("工作经历的公司、岗位或时间信息不完整");
  if (!candidate.education) weaknesses.push("学历信息未被可靠识别，需要人工确认");
  if (averageEvidenceConfidence && averageEvidenceConfidence < 0.65) weaknesses.push("部分字段证据置信度偏低，建议核对简历原文");
  if (!strengths.length) strengths.push("已完成基础字段结构化，暂未发现证据充分的突出优势");
  if (!weaknesses.length) weaknesses.push("未发现明显材料短板，建议继续验证技术深度与近期实践");
  return { dimensions, strengths: strengths.slice(0, 4), weaknesses: weaknesses.slice(0, 4), averageSkillConfidence };
}

function ResumeEvidenceRadar({ dimensions }) {
  const chartRef = useRef(null);
  useEffect(() => {
    if (!chartRef.current) return undefined;
    const chart = echarts.init(chartRef.current, null, { renderer: "canvas" });
    chart.setOption({
      animationDuration: 700,
      tooltip: { trigger: "item", formatter: ({ value }) => dimensions.map((item, index) => `${item.name}：${value[index]}分`).join("<br/>") },
      radar: {
        radius: "67%",
        center: ["50%", "52%"],
        splitNumber: 4,
        indicator: dimensions.map((item) => ({ name: item.name, max: 100 })),
        axisName: { color: "#425668", fontSize: 11, fontWeight: 650 },
        axisLine: { lineStyle: { color: "rgba(66,86,104,.18)" } },
        splitLine: { lineStyle: { color: "rgba(66,86,104,.14)" } },
        splitArea: { areaStyle: { color: ["rgba(237,246,244,.42)", "rgba(247,250,252,.66)"] } },
      },
      series: [{
        type: "radar",
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { color: "#168f78", width: 2 },
        itemStyle: { color: "#168f78", borderColor: "#fff", borderWidth: 2 },
        areaStyle: { color: "rgba(22,143,120,.2)" },
        data: [{ value: dimensions.map((item) => item.value), name: "简历证据质量" }],
      }],
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [dimensions]);
  return <div className="resume-evidence-radar" ref={chartRef} role="img" aria-label="简历证据质量雷达图" />;
}

function buildGapVisual(result) {
  const breakdown = result?.score_breakdown || {};
  const dimensions = [
    { key: "required_skills", name: "必备技能", value: clampResumeScore(breakdown.required_skills ?? result?.score ?? 0) },
    { key: "preferred_skills", name: "加分技能", value: clampResumeScore(breakdown.preferred_skills ?? result?.score ?? 0) },
    { key: "evidence_quality", name: "证据质量", value: clampResumeScore(breakdown.evidence_quality ?? (result?.evidence_coverage || 0) * 100) },
    { key: "behavior_competency", name: "行为能力", value: clampResumeScore(breakdown.behavior_competency ?? 0) },
  ];
  const matchedSkills = [...new Set(result?.matched_skills || [])];
  const missingSkills = [...new Set([
    ...(result?.missing_required_skills || []),
    ...(result?.gaps || []).map((item) => item.skill).filter(Boolean),
  ])];
  return {
    dimensions,
    requiredCoverage: dimensions[0].value,
    matchedSkills,
    missingSkills,
  };
}

function GapBenchmarkRadar({ dimensions }) {
  const chartRef = useRef(null);
  useEffect(() => {
    if (!chartRef.current) return undefined;
    const chart = echarts.init(chartRef.current, null, { renderer: "canvas" });
    chart.setOption({
      animationDuration: 720,
      animationEasing: "cubicOut",
      tooltip: {
        trigger: "item",
        formatter: ({ name, value }) => `<strong>${name}</strong><br/>${dimensions.map((item, index) => `${item.name}：${value[index]}分`).join("<br/>")}`,
      },
      radar: {
        radius: "68%",
        center: ["50%", "52%"],
        splitNumber: 4,
        indicator: dimensions.map((item) => ({ name: item.name, max: 100 })),
        axisName: { color: "#425668", fontSize: 11, fontWeight: 650 },
        axisLine: { lineStyle: { color: "rgba(74,95,112,.18)" } },
        splitLine: { lineStyle: { color: "rgba(74,95,112,.14)" } },
        splitArea: { areaStyle: { color: ["rgba(239,246,248,.56)", "rgba(250,252,253,.9)"] } },
      },
      series: [{
        type: "radar",
        symbol: "circle",
        data: [
          {
            value: dimensions.map(() => 100),
            name: "岗位完整要求",
            symbolSize: 0,
            lineStyle: { color: "#aab7c0", width: 1, type: "dashed" },
            areaStyle: { color: "rgba(130,148,160,.035)" },
          },
          {
            value: dimensions.map((item) => item.value),
            name: "当前匹配表现",
            symbolSize: 6,
            lineStyle: { color: "#187f6d", width: 2 },
            itemStyle: { color: "#187f6d", borderColor: "#fff", borderWidth: 2 },
            areaStyle: { color: "rgba(24,127,109,.22)" },
          },
        ],
      }],
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [dimensions]);
  return <div className="gap-benchmark-radar" ref={chartRef} role="img" aria-label="候选人与岗位要求对比雷达图" />;
}

export function ResumeCenter({ candidate, user, navigate, onUpload, notify }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const upload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      const result = await onUpload(file);
      const seconds = Number(result?.parse_timing?.total_ms || 0) / 1000;
      notify?.(`简历解析完成${seconds ? `，耗时 ${seconds.toFixed(1)} 秒` : ""}`);
    } catch (error) {
      notify?.(error.message || "简历解析失败");
    } finally {
      setUploading(false);
    }
  };
  const uploader = <input ref={inputRef} hidden type="file" accept=".pdf,.docx,.docm,.txt,.md,.png,.jpg,.jpeg,.webp" onChange={upload} />;
  if (!candidate) {
    return (
      <main className="seeker-page">
        {uploader}
        <EmptyAction
          icon={FileSearch}
          title="还没有个人能力档案"
          text="上传 PDF、Word 或图片简历，系统会提取经历、项目、技能和证据完整度。"
          action="上传并解析简历"
          onAction={() => inputRef.current?.click()}
        />
        {uploading && <p className="resume-center-status">正在读取文档并调用大模型提取经历、项目、技能与证据，请稍候…</p>}
      </main>
    );
  }
  const skills = candidate.skills || [];
  const projects = candidate.projects || [];
  const resumeInsights = buildResumeEvidenceInsights(candidate);
  const profileStats = [
    {
      key: "skills",
      label: "技能",
      value: skills.length,
      detail: "已进入能力画像",
      icon: CheckCircle2,
      tone: "blue",
    },
    {
      key: "projects",
      label: "项目",
      value: projects.length,
      detail: "用于面试证据核验",
      icon: BriefcaseBusiness,
      tone: "violet",
    },
    {
      key: "experience",
      label: "经验",
      value: candidate.experience_years ?? "—",
      detail: "年工作经验",
      icon: Map,
      tone: "amber",
    },
    {
      key: "confidence",
      label: "画像置信度",
      value: `${Math.round((candidate.confidence || 0) * 100)}%`,
      detail: "来自结构化证据",
      icon: Sparkles,
      tone: "cyan",
    },
  ];
  return (
    <main className="seeker-page resume-center">
      {uploader}
      <Card className="resume-identity" variant="default">
        <div className="resume-monogram">{(candidate.name || user?.display_name || "TG").slice(0, 1)}</div>
        <div>
          <h2>{candidate.name || user?.display_name}</h2>
          <p>{candidate.summary || "系统已从简历中提取经历、项目、技能和可追溯证据。"}</p>
        </div>
        <Button variant="outline" isPending={uploading} onPress={() => inputRef.current?.click()}>{uploading ? "正在解析" : "更新简历"} <Upload size={15} /></Button>
      </Card>
      <section className="resume-profile-grid">
        {profileStats.map(({ key, label, value, detail, icon: Icon, tone }) => (
          <Card className="resume-profile-card" data-tone={tone} key={key} variant="default">
            <Card.Header className="resume-profile-card-header">
              <span className="resume-profile-card-icon"><Icon size={16} /></span>
              <div className="resume-profile-card-copy">
                <Card.Description className="resume-profile-card-label">{label}</Card.Description>
                <Card.Title className="resume-profile-card-value" title={String(value)}>{value}</Card.Title>
              </div>
            </Card.Header>
            <Card.Content className="resume-profile-card-content">
              <p>{detail}</p>
            </Card.Content>
          </Card>
        ))}
      </section>
      <section className="resume-analysis-grid">
        <Card className="resume-radar-card" variant="default">
          <Card.Header className="resume-analysis-header">
            <div><span>证据质量诊断</span><Card.Title>简历能力雷达</Card.Title></div>
            <Chip size="sm" variant="soft"><Chip.Label>不等同于最终能力</Chip.Label></Chip>
          </Card.Header>
          <Card.Content className="resume-radar-content">
            <ResumeEvidenceRadar dimensions={resumeInsights.dimensions} />
            <div className="resume-radar-legend">
              {resumeInsights.dimensions.map((item) => <p key={item.name}><span>{item.name}</span><i><b style={{ width: `${item.value}%` }} /></i><strong>{item.value}</strong></p>)}
            </div>
          </Card.Content>
        </Card>
        <Card className="resume-contrast-card" variant="default">
          <Card.Header className="resume-analysis-header">
            <div><span>双向结论</span><Card.Title>优势与改进项</Card.Title></div>
          </Card.Header>
          <Card.Content className="resume-contrast-content">
            <section className="resume-positive-list">
              <header><TrendingUp size={17} /><strong>已形成优势</strong><span>{resumeInsights.strengths.length}</span></header>
              {resumeInsights.strengths.map((item, index) => <article key={item}><i>{String(index + 1).padStart(2, "0")}</i><p>{item}</p></article>)}
            </section>
            <section className="resume-negative-list">
              <header><TrendingDown size={17} /><strong>需要改进</strong><span>{resumeInsights.weaknesses.length}</span></header>
              {resumeInsights.weaknesses.map((item, index) => <article key={item}><i>{String(index + 1).padStart(2, "0")}</i><p>{item}</p></article>)}
            </section>
          </Card.Content>
        </Card>
      </section>
      <section className="resume-evidence-layout">
        <div>
          <header><h3>技能与证据</h3><span>点击目标岗位后用于差距计算</span></header>
          <div className="resume-skill-cloud">
            {skills.map((skill, index) => {
              const name = typeof skill === "string" ? skill : skill.name;
              return <span key={`${name}-${index}`}>{name}<small>{candidate.skill_scores?.[name] || "已识别"}</small></span>;
            })}
          </div>
        </div>
        <aside>
          <span>{candidate.provider_status?.model || "大模型"}语义解析结果</span>
          <h3>{candidate.education || "教育经历待补充"}</h3>
          <p>已识别 {skills.length} 项技能、{projects.length} 段项目经历和 {candidate.evidence?.length || 0} 条证据，可用于后续岗位差距分析。</p>
          <div>{projects.slice(0, 4).map((project, index) => <i key={`${project.name || "项目"}-${index}`}>{project.name || project.title || `项目 ${index + 1}`}</i>)}</div>
        </aside>
      </section>
    </main>
  );
}

export function GapAnalysis({ candidate, targetJob, jobs, setTargetJob, loadJobPage, navigate, onOpenLearning, analysis, onAnalyze }) {
  const selected = targetJob;
  const [analyzing, setAnalyzing] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [viewJobId, setViewJobId] = useState("");
  const [jobOptions, setJobOptions] = useState(jobs);
  const [jobQuery, setJobQuery] = useState("");
  const [jobTotal, setJobTotal] = useState(jobs.length);
  const [jobLoading, setJobLoading] = useState(false);
  const [jobError, setJobError] = useState("");
  const availableJobs = selected && !jobOptions.some((job) => String(job.id) === String(selected.id))
    ? [selected, ...jobOptions]
    : jobOptions;
  const results = analysis?.results || [];
  const sameId = (left, right) => left != null && right != null && String(left) === String(right);
  const activeResult = results.find((item) => sameId(item.job_id, viewJobId))
    || results.find((item) => sameId(item.job_id, selected?.id))
    || analysis?.best_match
    || null;
  const gaps = activeResult?.gaps || [];
  const strengths = activeResult?.strengths || [];
  const gapVisual = useMemo(() => buildGapVisual(activeResult), [activeResult]);

  const analyze = async (mode) => {
    if (!candidate) return navigate("resume");
    if (mode === "target" && !selected?.id) return;
    setAnalyzing(mode);
    setAnalysisError("");
    try {
      const result = await onAnalyze({ analyzeAll: mode === "all", jobId: mode === "target" ? selected.id : null });
      setViewJobId(result?.best_match?.job_id || "");
    } catch (error) {
      setAnalysisError(error.message || "岗位差距分析失败");
    } finally {
      setAnalyzing("");
    }
  };

  useEffect(() => {
    if (!jobs.length) return;
    setJobOptions((current) => {
      const source = jobs.length ? jobs : current;
      if (!selected || source.some((job) => String(job.id) === String(selected.id))) return source;
      return [selected, ...source];
    });
    if (!jobQuery.trim()) setJobTotal((current) => Math.max(current, jobs.length));
  }, [jobs, jobQuery, selected]);

  useEffect(() => {
    if (!loadJobPage) return undefined;
    let active = true;
    const timer = window.setTimeout(() => {
      setJobLoading(true);
      setJobError("");
      loadJobPage({ page: 1, pageSize: GAP_JOB_PAGE_SIZE, keyword: jobQuery })
        .then((data) => {
          if (!active) return;
          const items = data.items || [];
          setJobOptions(selected && !items.some((job) => String(job.id) === String(selected.id))
            ? [selected, ...items]
            : items);
          setJobTotal(data.total ?? items.length);
        })
        .catch(() => {
          if (active) setJobError("岗位搜索失败，请稍后重试");
        })
        .finally(() => {
          if (active) setJobLoading(false);
        });
    }, jobQuery.trim() ? 240 : 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [jobQuery, loadJobPage, selected]);

  const handleJobInputChange = (value) => {
    setJobQuery(value);
    setJobError("");
  };
  const handleJobChange = (key) => {
    if (key == null) return;
    const job = availableJobs.find((item) => String(item.id) === String(key));
    if (job) {
      setTargetJob(job);
      setJobQuery(job.title);
    }
  };

  return (
    <main className="seeker-page gap-page">
      <Card className="gap-target-card" variant="default">
        <Card.Content className="gap-target-content">
          <div className="gap-target-copy">
            <span>当前诊断目标</span>
            <h2>{selected?.title || "选择目标岗位"}</h2>
            <p>{selected?.company || "岗位能力要求将作为个人诊断基线"}</p>
          </div>
          <ComboBox
            allowsEmptyCollection
            fullWidth
            className="gap-job-combobox"
            inputValue={jobQuery}
            menuTrigger="focus"
            selectedKey={selected?.id == null ? null : String(selected.id)}
            onInputChange={handleJobInputChange}
            onSelectionChange={handleJobChange}
          >
            <Label>搜索全部目标岗位</Label>
            <ComboBox.InputGroup>
              <Input placeholder="输入岗位或公司名称" />
              <ComboBox.Trigger />
            </ComboBox.InputGroup>
            <ComboBox.Popover className="gap-job-popover">
              <ListBox
                aria-label="目标岗位搜索结果"
                renderEmptyState={() => (
                  <div className="gap-job-empty">
                    {jobLoading ? "正在搜索全部岗位…" : jobError || (jobQuery.trim() ? "没有匹配的岗位" : "暂无岗位数据")}
                  </div>
                )}
              >
                {availableJobs.map((job) => (
                  <ListBox.Item
                    key={job.id}
                    id={String(job.id)}
                    textValue={`${job.title} ${job.company}`}
                  >
                    <div className="gap-job-option">
                      <strong>{job.title}</strong>
                      <span>{job.company}{job.city ? ` · ${job.city}` : ""}</span>
                    </div>
                    <ListBox.ItemIndicator />
                  </ListBox.Item>
                ))}
              </ListBox>
            </ComboBox.Popover>
            <div className="gap-job-status" aria-live="polite">
              {jobLoading ? "正在搜索全部岗位…" : jobError || (jobQuery.trim() && jobTotal ? `已找到 ${jobTotal.toLocaleString("zh-CN")} 个匹配岗位` : "")}
            </div>
          </ComboBox>
          <div className="gap-analysis-actions">
            <Button isPending={analyzing === "target"} onPress={() => analyze("target")}><Target size={15} />分析当前岗位</Button>
            <Button variant="secondary" isPending={analyzing === "all"} onPress={() => analyze("all")}><Sparkles size={15} />分析全部岗位并推荐 Top 5</Button>
          </div>
          {analysisError && <p className="gap-analysis-error">{analysisError}</p>}
        </Card.Content>
      </Card>

      {!candidate || !activeResult ? (
        <EmptyAction
          icon={Target}
          title="还不能计算岗位差距"
          text="先解析简历，再选择一个目标岗位，或让系统从全部岗位中计算最匹配的前 5 个岗位。"
          action="前往我的简历"
          onAction={() => navigate("resume")}
        />
      ) : (
        <>
          {results.length > 1 && <section className="gap-top-five">
            <header><div><span>全市场分析</span><h3>最匹配岗位 Top 5</h3></div><small>已评估 {analysis?.evaluated_job_count || results.length} 个有效岗位</small></header>
            <div>{results.slice(0, 5).map((item, index) => <button className={sameId(activeResult.job_id, item.job_id) ? "active" : ""} key={item.job_id} onClick={() => setViewJobId(item.job_id)}><i>0{index + 1}</i><span><strong>{item.title}</strong><small>{item.company}{item.city ? ` · ${item.city}` : ""}</small></span><b>{item.score}</b></button>)}</div>
          </section>}
          <Card className="gap-score" variant="default">
            <Card.Content className="gap-score-content">
              <div>
                <span>岗位差距结论 · {activeResult.source_platform || "招聘岗位"}</span>
                <h2>{activeResult.title || selected?.title}</h2>
                <p>{activeResult.executive_summary}</p>
                {activeResult.source_url && <a className="gap-source-link" href={activeResult.source_url} target="_blank" rel="noreferrer">查看原始招聘页面 <ExternalLink size={13} /></a>}
              </div>
              <strong>{activeResult.score}<small>/100</small></strong>
            </Card.Content>
          </Card>
          <section className="gap-visual-grid">
            <Card className="gap-visual-card gap-radar-card" variant="default">
              <Card.Header className="gap-visual-header">
                <div><span>能力结构对照</span><Card.Title>岗位匹配雷达</Card.Title></div>
                <div className="gap-radar-key"><i /><span>当前表现</span><i /><span>岗位完整要求</span></div>
              </Card.Header>
              <Card.Content className="gap-radar-content">
                <GapBenchmarkRadar dimensions={gapVisual.dimensions} />
                <div className="gap-dimension-bars">
                  {gapVisual.dimensions.map((item) => (
                    <article key={item.key}>
                      <header><span>{item.name}</span><strong>{item.value}</strong></header>
                      <div><i style={{ width: `${item.value}%` }} /></div>
                    </article>
                  ))}
                </div>
              </Card.Content>
            </Card>
            <Card className="gap-visual-card gap-coverage-card" variant="default">
              <Card.Header className="gap-visual-header">
                <div><span>技能覆盖情况</span><Card.Title>已覆盖与待补齐</Card.Title></div>
              </Card.Header>
              <Card.Content className="gap-coverage-content">
                <div className="gap-coverage-summary">
                  <div className="gap-coverage-ring" style={{ "--coverage": `${gapVisual.requiredCoverage * 3.6}deg` }}>
                    <strong>{gapVisual.requiredCoverage}<small>%</small></strong>
                    <span>必备技能覆盖</span>
                  </div>
                  <div className="gap-coverage-counts">
                    <p><span>已匹配技能</span><strong>{gapVisual.matchedSkills.length}</strong></p>
                    <p><span>待补齐技能</span><strong>{gapVisual.missingSkills.length}</strong></p>
                    <p><span>证据覆盖率</span><strong>{Math.round((activeResult.evidence_coverage || 0) * 100)}%</strong></p>
                  </div>
                </div>
                <div className="gap-skill-map">
                  <section><header><CheckCircle2 size={15} /><strong>已覆盖</strong></header><div>{gapVisual.matchedSkills.length ? gapVisual.matchedSkills.slice(0, 10).map((skill) => <span key={skill}>{skill}</span>) : <small>暂无可靠匹配证据</small>}</div></section>
                  <section><header><CircleAlert size={15} /><strong>待补齐</strong></header><div>{gapVisual.missingSkills.length ? gapVisual.missingSkills.slice(0, 10).map((skill) => <span key={skill}>{skill}</span>) : <small>未发现明确技能缺口</small>}</div></section>
                </div>
              </Card.Content>
            </Card>
          </section>
          <section className="gap-columns">
            <Card className="gap-panel" variant="default">
              <Card.Header className="gap-panel-header">
                <CheckCircle2 />
                <Card.Title>已经形成优势</Card.Title>
                <Chip size="sm" variant="tertiary"><Chip.Label>{strengths.length} 项</Chip.Label></Chip>
              </Card.Header>
              <Card.Content className="gap-panel-list">
                {strengths.map((item, index) => <article key={`${item.skill}-${index}`}><span>{item.skill}</span><strong>{item.summary || item.evidence}</strong><small>{item.evidence_count || 1} 条个人证据</small></article>)}
              </Card.Content>
            </Card>
            <Card className="gap-panel gap-panel-priority" variant="default">
              <Card.Header className="gap-panel-header">
                <CircleAlert />
                <Card.Title>优先补齐差距</Card.Title>
                <Chip size="sm" variant="tertiary"><Chip.Label>{gaps.length} 项</Chip.Label></Chip>
              </Card.Header>
              <Card.Content className="gap-panel-list">
                {gaps.map((item, index) => <article key={`${item.skill}-${index}`}><span>{item.skill}</span><strong>{item.suggestion || item.recommended_action}</strong><small>{item.importance_label || item.importance || "岗位必备能力"}</small>{item.job_evidence?.[0] && <q>{item.job_evidence[0]}</q>}</article>)}
              </Card.Content>
            </Card>
          </section>
          <Button className="gap-to-learning" onPress={() => onOpenLearning?.(activeResult.job_id)}>按差距生成学习路线 <ArrowRight size={16} /></Button>
        </>
      )}
    </main>
  );
}

function LearningCourseCard({ course, skill }) {
  const [coverFailed, setCoverFailed] = useState(false);
  const showOriginalCover = Boolean(course.cover_url) && !coverFailed;
  const coverUrl = showOriginalCover ? course.cover_url : abilityCourseCover;
  return (
    <a className="learning-course-card" href={course.url} target="_blank" rel="noreferrer">
      <div className={`learning-course-cover${showOriginalCover ? "" : " is-fallback"}`}>
        <img src={coverUrl} alt={`${course.title}课程封面`} loading="lazy" referrerPolicy="no-referrer" onError={() => setCoverFailed(true)} />
        {!showOriginalCover && <span>{String(skill || "课程").slice(0, 8)}</span>}
        <i>{course.source}</i>
      </div>
      <div className="learning-course-copy">
        <b>{course.title}</b>
        <small>{course.instructor || course.source} · {course.duration_text}</small>
        <em>{course.reason}</em>
        <strong>查看课程 <ExternalLink size={12} /></strong>
      </div>
    </a>
  );
}

export function LearningRoadmap({ candidate, analysis, route, initialJobId, onGenerate, navigate, notify }) {
  const [jobId, setJobId] = useState(initialJobId || "");
  const [level, setLevel] = useState("入门");
  const [generating, setGenerating] = useState(false);
  const results = analysis?.results || [];
  const path = route?.steps || [];
  const defaultJobId = initialJobId || analysis?.best_match?.job_id || "";
  const sameId = (left, right) => left != null && right != null && String(left) === String(right);
  const selectedJobId = jobId || defaultJobId;
  const routeMatchesSelection = Boolean(
    path.length
      && route?.analysis_id != null
      && analysis?.analysis_id != null
      && route?.job_id != null
      && selectedJobId
      && sameId(route.analysis_id, analysis.analysis_id)
      && sameId(route.job_id, selectedJobId),
  );
  useEffect(() => {
    setJobId(defaultJobId);
  }, [analysis?.analysis_id, initialJobId, defaultJobId]);
  const generate = async () => {
    setGenerating(true);
    try {
      await onGenerate({ analysisId: analysis.analysis_id, jobId: selectedJobId, currentLevel: level });
      notify?.("学习路线已根据岗位差距生成");
    } catch (error) {
      notify?.(error.message || "学习路线生成失败");
    } finally {
      setGenerating(false);
    }
  };
  if (!candidate || !analysis) {
    return (
      <main className="seeker-page">
        <EmptyAction
          icon={Map}
          title="学习路线等待岗位差距"
          text="学习计划只根据已经确认的目标岗位差距生成，请先完成差距分析。"
          action="完成差距分析"
          onAction={() => navigate("gap")}
        />
      </main>
    );
  }
  const generator = (
    <Card className="learning-generator" variant="default">
      <Card.Content>
        <div><span>路线生成基线</span><h2>{routeMatchesSelection ? "按当前岗位重新生成" : "选择已分析岗位"}</h2><p>系统会按缺失技能排序学习阶段，并从课程知识库检索免费课程。</p></div>
        <select value={selectedJobId} onChange={(event) => setJobId(event.target.value)}>{results.map((item) => <option key={item.job_id} value={item.job_id}>{item.title} · {item.score} 分</option>)}</select>
        <select value={level} onChange={(event) => setLevel(event.target.value)}><option>零基础</option><option>入门</option><option>进阶</option></select>
        <Button isPending={generating} onPress={generate}><BookOpenCheck size={16} />{generating ? "正在检索课程" : routeMatchesSelection ? "按当前岗位重新生成" : "生成学习路线"}</Button>
      </Card.Content>
    </Card>
  );
  if (!routeMatchesSelection) return <main className="seeker-page learning-page">{generator}</main>;
  return (
    <main className="seeker-page learning-page">
      {generator}
      <section className="learning-intro">
        <div><h2>{route.job_title}学习路线</h2><p>课程来自已入库的免费学习资源，每个阶段以可验证产出结束。</p></div>
        <div><strong>{route.total_estimated_hours}</strong><span>预计学习小时</span></div>
      </section>
      <section className="learning-track">
        {path.map((item, index) => (
          <motion.article
            key={`${item.skill}-${index}`}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.08 }}
          >
            <div><span>0{index + 1}</span><i /></div>
            <section>
              <small>{item.phase} · 约 {item.estimated_hours} 小时 · 岗位覆盖率 {item.demand_rate}%</small>
              <h3>{item.skill}</h3>
              <p>{item.why}</p>
              <div className="learning-content-list">{item.learning_content?.map((content) => <span key={content}>{content}</span>)}</div>
              <div className="learning-course-list">{item.courses?.map((course) => <LearningCourseCard key={course.course_id} course={course} skill={item.skill} />)}</div>
              <strong>{item.completion_criteria?.[0] || "完成一个可验证的项目产出"}</strong>
            </section>
          </motion.article>
        ))}
      </section>
      <Button className="learning-retest" onPress={() => navigate("interview")}><BookOpenCheck size={16} />完成学习后重新评估</Button>
    </main>
  );
}

export function ApplicationCenter({
  jobs,
  jobTotal,
  applications,
  targetJob,
  setTargetJob,
  loadJobPage,
  onApply,
  onWithdraw,
}) {
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("discover");
  const [page, setPage] = useState(1);
  const [pageJobs, setPageJobs] = useState(jobs);
  const [total, setTotal] = useState(jobTotal);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const filteredJobs = pageJobs.filter((job) => `${job.title} ${job.company} ${(job.tags || []).join(" ")}`.toLowerCase().includes(normalizedQuery));
  const targetOnPage = targetJob && pageJobs.some((job) => String(job.id) === String(targetJob.id));
  const showTargetSummary = Boolean(targetJob && !targetOnPage && !normalizedQuery && tab === "discover");
  const applicationIds = new Set(applications.map((item) => item.job_id));
  const pageCount = Math.max(1, Math.ceil(total / APPLICATION_PAGE_SIZE));
  const pageItems = useMemo(() => {
    if (pageCount <= 7) return Array.from({ length: pageCount }, (_, index) => index + 1);
    const items = [1];
    if (page > 3) items.push("start-ellipsis");
    for (let value = Math.max(2, page - 1); value <= Math.min(pageCount - 1, page + 1); value += 1) {
      items.push(value);
    }
    if (page < pageCount - 2) items.push("end-ellipsis");
    items.push(pageCount);
    return items;
  }, [page, pageCount]);
  const rangeStart = total ? (page - 1) * APPLICATION_PAGE_SIZE + 1 : 0;
  const rangeEnd = Math.min(page * APPLICATION_PAGE_SIZE, total);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      setJobsLoading(true);
      setLoadError("");
      loadJobPage({ page, pageSize: APPLICATION_PAGE_SIZE, keyword: query })
        .then((data) => {
          if (!active) return;
          setPageJobs(data.items);
          setTotal(data.total);
        })
        .catch(() => {
          if (active) setLoadError("岗位加载失败，请稍后重试");
        })
        .finally(() => {
          if (active) setJobsLoading(false);
        });
    }, normalizedQuery ? 240 : 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [loadJobPage, normalizedQuery, page, query]);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  const changePage = (nextPage) => {
    const clamped = Math.min(pageCount, Math.max(1, nextPage));
    if (clamped === page) return;
    setPage(clamped);
    document.querySelector(".application-toolbar")?.scrollIntoView({ block: "start" });
  };
  const changeQuery = (value) => {
    setJobsLoading(true);
    setQuery(value);
    setPage(1);
  };
  return (
    <main className="seeker-page application-page">
      <Tabs className="application-tabs" selectedKey={tab} onSelectionChange={(key) => setTab(String(key))}>
        <section className="application-toolbar">
          <Tabs.ListContainer>
            <Tabs.List aria-label="岗位与投递视图">
              <Tabs.Tab id="discover">
                <span className="application-tab-label"><BriefcaseBusiness size={15} />发现岗位</span>
                <Tabs.Indicator />
              </Tabs.Tab>
              <Tabs.Tab id="records">
                <span className="application-tab-label">
                  <ClipboardCheck size={15} />投递记录
                  <span className="application-tab-count">{applications.length}</span>
                </span>
                <Tabs.Indicator />
              </Tabs.Tab>
            </Tabs.List>
          </Tabs.ListContainer>
          {tab === "discover" && (
            <SearchField
              fullWidth
              aria-label="搜索岗位、公司或技能"
              className="application-search"
              value={query}
              variant="secondary"
              onChange={changeQuery}
            >
              <SearchField.Group>
                <SearchField.SearchIcon />
                <SearchField.Input placeholder="搜索岗位、公司或技能" />
                <SearchField.ClearButton />
              </SearchField.Group>
            </SearchField>
          )}
        </section>

        {showTargetSummary && (
          <Card className="application-target-summary" variant="default">
            <Card.Content>
              <div>
                <Chip color="accent" size="sm" variant="soft"><Chip.Label>当前目标已同步</Chip.Label></Chip>
                <strong>{targetJob.title}</strong>
                <span>{targetJob.company}{targetJob.city ? ` · ${targetJob.city}` : ""}</span>
              </div>
              <Button variant="outline" onPress={() => changeQuery(targetJob.title)}>
                在岗位列表中定位 <Target size={14} />
              </Button>
            </Card.Content>
          </Card>
        )}

        <Tabs.Panel className="application-tab-panel" id="discover">
          <section
            aria-busy={jobsLoading}
            aria-label="在招岗位"
            className={`application-market ${jobsLoading ? "is-loading" : ""}`}
          >
          {filteredJobs.map((job) => {
            const applied = applicationIds.has(job.id);
            const isTarget = targetJob?.id === job.id;
            return (
              <Card className={`application-job-card ${isTarget ? "targeted" : ""}`} key={job.id} role="article" variant="default">
                <Card.Header className="application-job-header">
                  <div className="application-job-meta">
                    <Chip color="accent" size="sm" variant="soft"><Chip.Label>{job.domain}</Chip.Label></Chip>
                    <span>{job.source}</span>
                  </div>
                  <Card.Title title={job.title}>{job.title}</Card.Title>
                  <Card.Description>{job.company} · {job.city} · {job.salary}</Card.Description>
                </Card.Header>
                <Card.Content className="application-job-tags">
                  {job.tags.slice(0, 5).map((tag) => (
                    <Chip key={tag} size="sm" variant="tertiary"><Chip.Label>{tag}</Chip.Label></Chip>
                  ))}
                </Card.Content>
                <Card.Footer className="application-job-footer">
                  <Button fullWidth variant={isTarget ? "secondary" : "outline"} onPress={() => setTargetJob(job)}>
                    <Target size={14} />{isTarget ? "当前目标" : "设为目标"}
                  </Button>
                  <Button fullWidth isDisabled={applied} onPress={() => onApply(job)}>
                    {applied ? "已投递" : "投递简历"}<Send size={14} />
                  </Button>
                </Card.Footer>
              </Card>
            );
          })}
          {loadError && (
            <p className="application-load-error" role="alert">{loadError}</p>
          )}
          {!jobsLoading && !loadError && !filteredJobs.length && (
            <EmptyAction
              icon={FileSearch}
              title="没有匹配的岗位"
              text="换一个岗位、公司或技能关键词再试。"
              action="清除搜索"
              onAction={() => changeQuery("")}
            />
          )}
          </section>
          {total > 0 && (
            <Pagination aria-label="岗位分页" className="application-pagination" size="sm">
              <Pagination.Summary>
                {loadError || (jobsLoading
                  ? "正在加载岗位..."
                  : `第 ${rangeStart}-${rangeEnd} 条，共 ${total.toLocaleString("zh-CN")} 个岗位`)}
              </Pagination.Summary>
              <Pagination.Content>
                <Pagination.Item>
                  <Pagination.Previous aria-label="上一页" isDisabled={page <= 1 || jobsLoading} onPress={() => changePage(page - 1)}>
                    <Pagination.PreviousIcon />
                    <span className="application-page-nav-label">上一页</span>
                  </Pagination.Previous>
                </Pagination.Item>
                {pageItems.map((item) => item === "start-ellipsis" || item === "end-ellipsis" ? (
                  <Pagination.Item key={item}><Pagination.Ellipsis /></Pagination.Item>
                ) : (
                  <Pagination.Item key={item}>
                    <Pagination.Link isActive={item === page} isDisabled={jobsLoading} onPress={() => changePage(item)}>
                      {item}
                    </Pagination.Link>
                  </Pagination.Item>
                ))}
                <Pagination.Item>
                  <Pagination.Next aria-label="下一页" isDisabled={page >= pageCount || jobsLoading} onPress={() => changePage(page + 1)}>
                    <span className="application-page-nav-label">下一页</span>
                    <Pagination.NextIcon />
                  </Pagination.Next>
                </Pagination.Item>
              </Pagination.Content>
            </Pagination>
          )}
        </Tabs.Panel>

        <Tabs.Panel className="application-tab-panel" id="records">
          <section className="application-records" aria-label="投递记录">
            {applications.length ? (
              <Table className="application-record-table" variant="secondary">
                <Table.ScrollContainer>
                  <Table.Content aria-label="投递记录" className="application-record-table-content">
                    <Table.Header>
                      <Table.Column isRowHeader>岗位</Table.Column>
                      <Table.Column>状态</Table.Column>
                      <Table.Column>投递时间</Table.Column>
                      <Table.Column>投递时匹配度</Table.Column>
                      <Table.Column className="application-record-action-column">操作</Table.Column>
                    </Table.Header>
                    <Table.Body>
                      {applications.map((item) => (
                        <Table.Row id={item.application_id} key={item.application_id}>
                          <Table.Cell>
                            <div className="application-record-job">
                              <strong>{item.job_title}</strong>
                              <span>{item.company}</span>
                            </div>
                          </Table.Cell>
                          <Table.Cell>
                            <Chip color={statusColors[item.status] || "default"} size="sm" variant="soft">
                              <Chip.Label>{statusLabels[item.status] || item.status}</Chip.Label>
                            </Chip>
                          </Table.Cell>
                          <Table.Cell>{String(item.created_at).slice(0, 10)}</Table.Cell>
                          <Table.Cell>
                            <strong className="application-record-score">
                              {item.match_score ?? "—"}{item.match_score != null && "%"}
                            </strong>
                          </Table.Cell>
                          <Table.Cell className="application-record-action-cell">
                            {item.status === "submitted" ? (
                              <Button size="sm" variant="ghost" onPress={() => onWithdraw(item.application_id)}>撤回投递</Button>
                            ) : <span className="application-record-no-action">—</span>}
                          </Table.Cell>
                        </Table.Row>
                      ))}
                    </Table.Body>
                  </Table.Content>
                </Table.ScrollContainer>
              </Table>
            ) : (
              <EmptyAction icon={Send} title="还没有投递记录" text="选择目标岗位并提交个人简历后，进度会统一记录在这里。" action="去发现岗位" onAction={() => setTab("discover")} />
            )}
          </section>
        </Tabs.Panel>
      </Tabs>
    </main>
  );
}
