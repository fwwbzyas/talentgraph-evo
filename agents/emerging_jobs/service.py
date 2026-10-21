from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha1
import json
import re

from agents.llm import OpenAICompatibleClient
from contracts import (
    CleanedDataBatch,
    CleanedDataItem,
    CommunitySignal,
    EmergingJobCandidate,
    EmergingJobDiscoveryRequest,
    JobGraph,
)


EMERGING_SKILLS = {
    "LangGraph", "多 Agent 协作", "工具调用", "RAG", "向量数据库", "边缘计算",
    "时序数据库", "数字孪生", "流批一体", "实时湖仓", "模型评测", "可观测性",
}
EMERGING_TITLE_TERMS = (
    "agent", "智能体", "大模型", "rag", "数字孪生", "边缘智能",
    "边缘计算", "实时湖仓", "流批一体", "具身智能", "多模态",
)
TREND_INTERVAL_DAYS = 30
TREND_INTERVAL_COUNT = 6


class EmergingJobAgent:
    """Discovers job definitions from observed title/skill co-occurrence, recency and source support."""

    def __init__(self, llm: OpenAICompatibleClient | None = None) -> None:
        self.llm = llm or OpenAICompatibleClient()

    def discover(
        self,
        batches: list[CleanedDataBatch],
        graphs: list[JobGraph],
        request: EmergingJobDiscoveryRequest,
        persisted_jobs: list[CleanedDataItem] | None = None,
        community_signals: list[CommunitySignal] | None = None,
    ) -> list[EmergingJobCandidate]:
        items_by_id: dict[str, CleanedDataItem] = {}
        for batch in batches:
            for item in batch.items:
                if item.source_type == "jd":
                    items_by_id[item.source_id] = item
        for item in persisted_jobs or []:
            if item.source_type == "jd":
                items_by_id[item.source_id] = item

        market_items = list(items_by_id.values())

        groups: dict[str, list[CleanedDataItem]] = defaultdict(list)
        for item in items_by_id.values():
            groups[self._normalize_title(item.title)].append(item)

        graph_skills = {graph.job_title: [skill.name for skill in graph.skills] for graph in graphs}
        candidates: list[EmergingJobCandidate] = []
        now = self._now()
        for normalized_title, items in groups.items():
            skills = Counter(skill for item in items for skill in item.skill_tags)
            if items[0].title in graph_skills:
                skills.update(graph_skills[items[0].title])
            required_skills = [name for name, _ in skills.most_common(8)]
            bonus_skills = [name for name, _ in skills.most_common(14)[8:14]]
            emerging_count = sum(skill in EMERGING_SKILLS for skill in required_skills)
            trend_series = self._trend_series(items, market_items, now)
            previous = trend_series[-2]["demand_share"]
            recent = trend_series[-1]["demand_share"]
            growth_rate = self._growth_rate(recent, previous)
            source_count = len(items)
            company_count = len({item.company for item in items if item.company})
            cooccurrence_density = min(1.0, len(required_skills) / 6)
            support = min(1.0, source_count / 12)
            diversity = min(1.0, company_count / 6)
            novelty = min(1.0, emerging_count / 3)
            growth_signal = min(1.0, max(0.0, growth_rate + 0.25))
            confidence = round(0.28 * support + 0.22 * diversity + 0.22 * cooccurrence_density + 0.18 * novelty + 0.10 * growth_signal, 3)

            title_is_emerging = any(
                term in normalized_title.casefold()
                for term in EMERGING_TITLE_TERMS
            )
            is_candidate = title_is_emerging
            if not is_candidate or source_count < request.minimum_source_count or confidence < request.minimum_confidence:
                continue
            title = Counter(item.title for item in items).most_common(1)[0][0]
            responsibilities = Counter(responsibility for item in items for responsibility in item.responsibilities)
            ordered_items = sorted(items, key=self._published_at, reverse=True)
            evidence = [
                {
                    "source_id": item.source_id,
                    "company": item.company,
                    "source_url": item.source_url,
                    "source_platform": item.source_platform,
                    "published_at": self._published_at(item).isoformat(),
                    "skills": item.skill_tags[:8],
                    "snippet": item.content[:220],
                }
                for item in ordered_items[:12]
            ]
            pairs = Counter()
            for item in items:
                tags = sorted(set(item.skill_tags))[:10]
                for left_index, left in enumerate(tags):
                    for right in tags[left_index + 1 :]:
                        pairs[(left, right)] += 1
            cooccurrence = [
                {"left": left, "right": right, "count": count, "support": round(count / max(source_count, 1), 3)}
                for (left, right), count in pairs.most_common(10)
            ]
            source_diversity = {
                "companies": company_count,
                "platforms": dict(Counter(item.source_platform or "unknown" for item in items)),
                "cities": dict(Counter(item.city or "unknown" for item in items)),
            }
            skill_set = set(required_skills)
            auxiliary_evidence = []
            for signal in community_signals or []:
                signal_text = f"{signal.title} {signal.content} {' '.join(signal.tags)}".casefold()
                matched = sorted(skill for skill in skill_set if skill.casefold() in signal_text)
                if not matched:
                    continue
                auxiliary_evidence.append({
                    "signal_id": signal.signal_id,
                    "platform": signal.source_platform,
                    "source_url": signal.source_url,
                    "title": signal.title,
                    "matched_skills": matched,
                    "evidence_role": "auxiliary_only",
                })
            auxiliary_evidence = auxiliary_evidence[:10]
            source_family = self._closest_family(title, required_skills, graphs)
            difference_summary = (
                f"相较于 {source_family or '现有岗位族'}，该候选更集中要求"
                f" {', '.join(required_skills[:4]) or '复合技术能力'}。"
            )
            application_scenarios = self._application_scenarios(items, required_skills)
            fallback_definition = f"{title} 是围绕 {', '.join(required_skills[:4]) or '复合技术能力'} 形成的岗位候选，承担跨系统设计、交付与治理职责。"
            synthesis_fallback = {"definition": fallback_definition, "responsibilities": [name for name, _ in responsibilities.most_common(5)], "risk_notes": []}
            synthesis_data = synthesis_fallback
            synthesis_status = {
                **self.llm.status(),
                "mode": "deterministic_evidence",
                "ok": True,
                "fallback": True,
                "reason": "remote_definition_budget",
            }
            candidates.append(
                EmergingJobCandidate(
                    candidate_id=f"emerging_{sha1(normalized_title.encode('utf-8')).hexdigest()[:10]}",
                    name=title,
                    domain=self._domain(items),
                    core_responsibilities=[str(name) for name in synthesis_data.get("responsibilities", []) if name][:6] or [name for name, _ in responsibilities.most_common(5)],
                    required_skills=required_skills,
                    bonus_skills=bonus_skills,
                    application_scenarios=application_scenarios,
                    source_family=source_family,
                    difference_summary=difference_summary,
                    auxiliary_evidence=auxiliary_evidence,
                    evidence=evidence,
                    confidence=confidence,
                    maturity_status=self._maturity(source_count, company_count, growth_rate),
                    source_count=source_count,
                    growth_rate=growth_rate,
                    definition=str(synthesis_data.get("definition", fallback_definition)),
                    trend_series=trend_series,
                    source_diversity=source_diversity,
                    cooccurrence_signals=cooccurrence,
                    evidence_summary={
                        "sampled": len(evidence),
                        "total": source_count,
                        "companies": company_count,
                        "cities": len({item.city for item in items if item.city}),
                        "auxiliary_signals": len(auxiliary_evidence),
                        "risk_notes": synthesis_data.get("risk_notes", []),
                    },
                    provider_status=synthesis_status,
                )
            )
        ranked = sorted(
            candidates,
            key=lambda item: (item.confidence, item.growth_rate, item.source_count),
            reverse=True,
        )
        if not self.llm.configured:
            return ranked

        def synthesize(candidate: EmergingJobCandidate) -> EmergingJobCandidate:
            fallback = {
                "definition": candidate.definition,
                "responsibilities": candidate.core_responsibilities,
                "risk_notes": candidate.evidence_summary.get("risk_notes", []),
            }
            result = self.llm.generate_json(
                system_prompt=(
                    "你是新岗位定义 Agent。只输出 JSON 对象 definition、responsibilities、risk_notes。"
                    "只能依据输入证据定义岗位，必须区分岗位已形成、正在形成和弱信号，"
                    "不得把单一企业命名当成新职业。"
                ),
                user_prompt=json.dumps(
                    {
                        "title": candidate.name,
                        "skills": candidate.required_skills,
                        "sources": candidate.evidence,
                        "cooccurrence": candidate.cooccurrence_signals,
                        "trend": candidate.trend_series,
                    },
                    ensure_ascii=False,
                ),
                fallback=fallback,
            )
            data = result.data
            definition = data.get("definition", candidate.definition)
            if isinstance(definition, dict):
                definition = (
                    definition.get("summary")
                    or definition.get("definition")
                    or candidate.definition
                )
            responsibilities = []
            for item in data.get("responsibilities", candidate.core_responsibilities):
                if isinstance(item, dict):
                    item = item.get("responsibility") or item.get("text")
                if item:
                    responsibilities.append(str(item))
            return candidate.model_copy(update={
                "definition": str(definition),
                "core_responsibilities": responsibilities[:6] or candidate.core_responsibilities,
                "evidence_summary": {
                    **candidate.evidence_summary,
                    "risk_notes": data.get("risk_notes", []),
                },
                "provider_status": result.provider_status,
            })

        remote_count = min(3, len(ranked))
        with ThreadPoolExecutor(max_workers=remote_count or 1) as executor:
            enriched = list(executor.map(synthesize, ranked[:remote_count]))
        return enriched + ranked[remote_count:]

    def _normalize_title(self, title: str) -> str:
        lowered = title.strip().casefold()
        canonical_rules = (
            (("agent", "智能体", "agentic"), "AI Agent"),
            (("rag", "检索增强"), "RAG"),
            (("具身智能",), "具身智能"),
            (("多模态",), "多模态"),
            (("数字孪生",), "数字孪生"),
            (("实时湖仓", "流批一体"), "实时湖仓"),
            (("边缘智能", "边缘计算"), "边缘智能"),
            (("大模型", "大型语言模型", "llm"), "大模型应用"),
        )
        for terms, canonical in canonical_rules:
            if any(term in lowered for term in terms):
                return canonical
        value = re.sub(r"(?:高级|资深|初级|中级|专家|招聘|急聘|工程师)", "", title.strip(), flags=re.IGNORECASE)
        value = re.sub(r"\s+", " ", value).strip(" -_/·")
        value = re.sub(r"(?:ai\s*)?智能体|agentic|ai\s*agent", "AI Agent", value, flags=re.IGNORECASE)
        value = re.sub(r"大型语言模型|large language model|llm", "大模型", value, flags=re.IGNORECASE)
        return value or title.strip()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _trend_series(
        self,
        candidate_items: list[CleanedDataItem],
        market_items: list[CleanedDataItem],
        now: datetime,
    ) -> list[dict[str, int | float | str]]:
        candidate_published_at = [self._published_at(item) for item in candidate_items]
        market_published_at = [
            self._published_at(item)
            for item in market_items
            if item.source_type == "jd"
        ]
        trend_series: list[dict[str, int | float | str]] = []
        for bucket in range(TREND_INTERVAL_COUNT - 1, -1, -1):
            end = now - timedelta(days=bucket * TREND_INTERVAL_DAYS)
            start = end - timedelta(days=TREND_INTERVAL_DAYS)
            count = sum(start <= moment < end for moment in candidate_published_at)
            market_count = sum(start <= moment < end for moment in market_published_at)
            trend_series.append({
                "period": start.date().isoformat(),
                "count": count,
                "market_count": market_count,
                "demand_share": count / market_count if market_count else 0.0,
            })
        return trend_series

    @staticmethod
    def _growth_rate(recent: float, previous: float) -> float:
        if previous == 0:
            return 1.0 if recent > 0 else 0.0
        return round((recent - previous) / previous, 3)

    def _published_at(self, item: CleanedDataItem) -> datetime:
        value = item.published_at or item.collected_at
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    def _domain(self, items: list[CleanedDataItem]) -> str:
        raw = Counter(item.domain for item in items).most_common(1)[0][0]
        if "大数据" in raw:
            return "大数据"
        if "物联网" in raw or "IoT" in raw:
            return "物联网"
        if "智能系统" in raw or "云原生" in raw or "测试" in raw or "后端" in raw:
            return "智能系统"
        return "人工智能"

    def _maturity(self, source_count: int, company_count: int, growth_rate: float) -> str:
        if source_count >= 10 and company_count >= 5:
            return "established"
        if source_count >= 4 and company_count >= 2 and growth_rate >= -0.3:
            return "forming"
        return "signal"

    @staticmethod
    def _closest_family(title: str, skills: list[str], graphs: list[JobGraph]) -> str:
        best_title = ""
        best_score = 0.0
        skill_set = set(skills)
        for graph in graphs:
            graph_skills = {skill.name for skill in graph.skills}
            union = skill_set | graph_skills
            score = len(skill_set & graph_skills) / len(union) if union else 0
            if graph.job_title.casefold() in title.casefold():
                score += 0.35
            if score > best_score:
                best_title, best_score = graph.job_title, score
        if best_title:
            return best_title
        title_text = title.casefold()
        title_families = (
            ("机器学习与智能算法岗位族", ("多模态", "具身智能")),
            ("大模型应用岗位族", ("agent", "智能体", "rag", "大模型", "llm")),
            ("物联网与边缘系统岗位族", ("边缘计算", "数字孪生")),
            ("实时数据平台岗位族", ("实时湖仓", "流批一体")),
        )
        matched_title_family = next(
            (family for family, terms in title_families if any(term in title_text for term in terms)),
            None,
        )
        if matched_title_family:
            return matched_title_family
        text = f"{title} {' '.join(skills)}".casefold()
        fallback_families = (
            ("机器学习与智能算法岗位族", ("多模态", "具身智能", "pytorch", "tensorflow")),
            ("大模型应用岗位族", ("agent", "智能体", "rag", "大模型", "llm")),
            ("物联网与边缘系统岗位族", ("边缘计算", "数字孪生", "mqtt", "嵌入式")),
            ("实时数据平台岗位族", ("实时湖仓", "流批一体", "flink", "kafka")),
        )
        return next(
            (family for family, terms in fallback_families if any(term in text for term in terms)),
            "新一代信息技术复合岗位族",
        )

    @staticmethod
    def _application_scenarios(items: list[CleanedDataItem], skills: list[str]) -> list[str]:
        text = " ".join(item.content for item in items[:20]).casefold()
        rules = (
            ("企业知识服务与智能问答", ("rag", "知识库", "向量数据库")),
            ("智能制造与工业系统", ("工业", "制造", "数字孪生")),
            ("金融风控与数据智能", ("金融", "风控", "银行")),
            ("智能汽车与机器人", ("自动驾驶", "汽车", "机器人", "ros")),
            ("物联网设备与边缘计算", ("物联网", "mqtt", "边缘", "嵌入式")),
            ("数据平台与实时分析", ("flink", "实时计算", "数据平台", "湖仓")),
        )
        values = [label for label, terms in rules if any(term in text for term in terms)]
        if values:
            return values[:5]
        return [f"{skills[0]}相关企业级系统" if skills else "新一代信息技术企业应用"]
