from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
import hashlib
import math
import re
from statistics import median
from typing import Any, Iterable

from contracts import CleanedDataItem, CommunitySignal
from agents.data.source_policy import RECRUITMENT_SOURCE_SET
from agents.data.normalization import extract_skills, is_valid_skill
from agents.job_graph.service import CAPABILITY_LABELS, SKILL_CATALOG


FAMILY_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "人工智能": (
        (r"agent|智能体", "AI Agent 工程师"), (r"大模型|llm|rag", "大模型应用工程师"),
        (r"视觉|cv|图像|多模态", "计算机视觉与多模态工程师"), (r"nlp|自然语言", "NLP 工程师"),
        (r"机器学习|深度学习", "机器学习工程师"), (r"算法", "AI 算法工程师"),
        (r"平台|工程化|推理", "AI 平台工程师"),
    ),
    "大数据": (
        (r"flink|实时|流式", "实时计算工程师"), (r"数仓|数据仓库|湖仓", "数据仓库与湖仓工程师"),
        (r"治理|质量|血缘", "数据治理工程师"), (r"平台", "数据平台工程师"),
        (r"bi|商业智能|分析", "数据分析与 BI 工程师"), (r"大数据|数据开发|数据工程", "大数据开发工程师"),
    ),
    "智能系统": (
        (r"机器人", "机器人软件工程师"), (r"自动驾驶|感知|控制", "智能系统算法工程师"),
        (r"云原生|kubernetes|容器", "云原生工程师"), (r"devops|sre|运维|可靠性", "智能运维工程师"),
        (r"测试|质量", "测试开发工程师"), (r"边缘智能", "边缘智能工程师"),
        (r"智能系统", "智能系统工程师"),
    ),
    "物联网": (
        (r"嵌入式|单片机|mcu", "嵌入式工程师"), (r"固件|驱动", "固件与驱动工程师"),
        (r"网关|边缘计算", "边缘网关工程师"), (r"平台|设备接入", "物联网平台工程师"),
        (r"iot|物联网", "物联网工程师"), (r"硬件|电路", "智能硬件工程师"),
    ),
}

CITY_COORDS: dict[str, tuple[float, float]] = {
    "北京": (116.41, 39.90), "上海": (121.47, 31.23), "天津": (117.20, 39.12),
    "重庆": (106.55, 29.56), "深圳": (114.06, 22.54), "广州": (113.26, 23.13),
    "杭州": (120.15, 30.27), "南京": (118.80, 32.06), "苏州": (120.58, 31.30),
    "成都": (104.07, 30.57), "武汉": (114.31, 30.59), "西安": (108.94, 34.34),
    "长沙": (112.94, 28.23), "合肥": (117.23, 31.82), "郑州": (113.63, 34.75),
    "济南": (117.12, 36.65), "青岛": (120.38, 36.07), "厦门": (118.09, 24.48),
    "福州": (119.30, 26.08), "宁波": (121.55, 29.87), "无锡": (120.31, 31.49),
    "东莞": (113.75, 23.02), "佛山": (113.12, 23.02), "珠海": (113.58, 22.27),
    "中山": (113.39, 22.52), "惠州": (114.42, 23.11), "常州": (119.97, 31.81),
    "南通": (120.89, 31.98), "徐州": (117.29, 34.21), "扬州": (119.41, 32.39),
    "温州": (120.70, 28.00), "嘉兴": (120.76, 30.75), "绍兴": (120.58, 30.03),
    "湖州": (120.09, 30.89), "金华": (119.65, 29.08), "台州": (121.42, 28.66),
    "沈阳": (123.43, 41.80), "大连": (121.61, 38.91), "长春": (125.32, 43.82),
    "哈尔滨": (126.53, 45.80), "石家庄": (114.51, 38.04), "唐山": (118.18, 39.63),
    "保定": (115.46, 38.87), "太原": (112.55, 37.87), "烟台": (121.45, 37.46),
    "潍坊": (119.16, 36.71), "威海": (122.12, 37.51), "淄博": (118.05, 36.81),
    "临沂": (118.36, 35.10), "南昌": (115.86, 28.68), "南宁": (108.32, 22.82),
    "贵阳": (106.63, 26.65), "昆明": (102.71, 25.04), "海口": (110.20, 20.04),
    "兰州": (103.83, 36.06), "银川": (106.23, 38.49), "西宁": (101.78, 36.62),
    "乌鲁木齐": (87.62, 43.83), "呼和浩特": (111.75, 40.84), "拉萨": (91.14, 29.65),
    "芜湖": (118.38, 31.33), "洛阳": (112.45, 34.62), "绵阳": (104.68, 31.47),
    "泉州": (118.68, 24.87), "赣州": (114.93, 25.83), "桂林": (110.29, 25.27),
}


class KnowledgeGraphService:
    """Build a navigable evidence graph exclusively from persisted recruitment jobs."""

    def build(
        self,
        jobs: Iterable[CleanedDataItem],
        *,
        domain: str | None = None,
        source_platform: str | None = None,
        max_jobs_per_domain: int = 18,
        max_skills_per_job: int = 10,
        max_evidence: int = 360,
    ) -> dict[str, Any]:
        source_jobs = [
            job for job in jobs
            if job.job_status == "active"
            and job.source_platform in RECRUITMENT_SOURCE_SET
            and (domain is None or job.domain == domain)
            and (source_platform is None or job.source_platform == source_platform)
        ]
        families: dict[tuple[str, str], list[CleanedDataItem]] = defaultdict(list)
        for job in source_jobs:
            families[(job.domain, self._family(job))].append(job)

        selected: dict[tuple[str, str], list[CleanedDataItem]] = {}
        for domain_name in sorted({key[0] for key in families}):
            ranked = sorted(
                ((key, value) for key, value in families.items() if key[0] == domain_name),
                key=lambda item: (-len(item[1]), item[0][1]),
            )[:max_jobs_per_domain]
            selected.update(ranked)

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        evidence_budget = max_evidence
        for domain_name in sorted({key[0] for key in selected}):
            domain_jobs = [job for key, values in selected.items() if key[0] == domain_name for job in values]
            domain_id = f"domain:{self._slug(domain_name)}"
            nodes.append(self._node(
                domain_id, domain_name, "domain", None, domain_jobs,
                f"来自 BOSS直聘与智联招聘的{domain_name}岗位集合。",
            ))
            for (family_domain, family_name), family_jobs in selected.items():
                if family_domain != domain_name:
                    continue
                family_id = f"job:{self._slug(domain_name)}:{self._slug(family_name)}"
                skill_counts = Counter(skill for job in family_jobs for skill in job.skill_tags if is_valid_skill(skill))
                responsibility_counts = Counter(
                    responsibility for job in family_jobs for responsibility in job.responsibilities if responsibility
                )
                job_node = self._node(
                    family_id, family_name, "job", domain_id, family_jobs,
                    self._summary(responsibility_counts, family_name),
                )
                job_node["responsibilities"] = [item for item, _ in responsibility_counts.most_common(8)]
                job_node["sampleTitles"] = [item for item, _ in Counter(job.title for job in family_jobs).most_common(6)]
                nodes.append(job_node)
                edges.append(self._edge(domain_id, family_id, "contains", len(family_jobs)))

                category_skills: dict[str, list[tuple[str, int]]] = defaultdict(list)
                for skill, count in skill_counts.most_common(max_skills_per_job):
                    category_skills[self._skill_category(skill)].append((skill, count))
                for category, skills in sorted(category_skills.items()):
                    capability_id = f"cap:{self._slug(family_id)}:{self._slug(category)}"
                    supporting = [job for job in family_jobs if any(skill in job.skill_tags for skill, _ in skills)]
                    nodes.append(self._node(
                        capability_id, CAPABILITY_LABELS.get(category, category), "capability", family_id,
                        supporting, f"由 {len(skills)} 项真实岗位技能要求归纳形成。",
                    ))
                    edges.append(self._edge(family_id, capability_id, "requires", len(supporting)))
                    for skill, count in skills:
                        skill_id = f"skill:{self._slug(family_id)}:{self._slug(skill)}"
                        skill_jobs = [job for job in family_jobs if skill in job.skill_tags]
                        skill_node = self._node(
                            skill_id, skill, "skill", capability_id, skill_jobs,
                            f"在 {count} 条{family_name}招聘要求中出现。",
                        )
                        skill_node["coverage"] = round(count / max(1, len(family_jobs)) * 100, 1)
                        nodes.append(skill_node)
                        edges.append(self._edge(capability_id, skill_id, "includes", count))
                        for evidence_job in sorted(skill_jobs, key=self._evidence_rank, reverse=True)[:2]:
                            if evidence_budget <= 0:
                                break
                            evidence_budget -= 1
                            evidence_id = f"evidence:{self._slug(evidence_job.source_id)}:{self._slug(skill)}"
                            nodes.append({
                                "id": evidence_id, "label": evidence_job.company or evidence_job.title,
                                "type": "evidence", "parent": skill_id,
                                "description": self._snippet(evidence_job, skill), "evidenceCount": 1,
                                "growth": 0, "confidence": round(evidence_job.quality_score / 100, 2),
                                "sourceId": evidence_job.source_id, "sourcePlatform": evidence_job.source_platform,
                                "sourceUrl": evidence_job.source_url, "company": evidence_job.company,
                                "jobTitle": evidence_job.title, "city": evidence_job.city,
                                "publishedAt": (evidence_job.published_at or evidence_job.collected_at).isoformat(),
                                "qualityScore": evidence_job.quality_score,
                            })
                            edges.append(self._edge(skill_id, evidence_id, "supported_by", 1))

        type_counts = Counter(node["type"] for node in nodes)
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_policy": "recruitment_primary_live_only",
            "filters": {"domain": domain, "source_platform": source_platform},
            "stats": {
                "source_jobs": len(source_jobs), "rendered_nodes": len(nodes), "rendered_edges": len(edges),
                "domains": type_counts["domain"], "job_families": type_counts["job"],
                "skills": type_counts["skill"], "evidence": type_counts["evidence"],
                "sources": dict(Counter(job.source_platform for job in source_jobs)),
                "companies": len({job.company for job in source_jobs if job.company}),
            },
            "nodes": nodes,
            "edges": edges,
        }

    def build_city_map(
        self,
        jobs: Iterable[CleanedDataItem],
        *,
        domain: str | None = None,
        source_platform: str | None = None,
        max_cities: int = 60,
    ) -> dict[str, Any]:
        """Aggregate persisted recruitment evidence into city clusters and similarity flows."""
        source_jobs = [
            job for job in jobs
            if job.job_status == "active"
            and job.source_platform in RECRUITMENT_SOURCE_SET
            and (domain is None or job.domain == domain)
            and (source_platform is None or job.source_platform == source_platform)
        ]
        grouped: dict[str, list[CleanedDataItem]] = defaultdict(list)
        for job in source_jobs:
            city = (job.city or "").strip().removesuffix("市")
            if city in CITY_COORDS:
                grouped[city].append(job)
        ranked_cities = sorted(grouped, key=lambda name: len(grouped[name]), reverse=True)[:max_cities]
        city_nodes: list[dict[str, Any]] = []
        skill_sets: dict[str, set[str]] = {}
        domain_vectors: dict[str, Counter[str]] = {}
        all_periods = sorted({
            self._career_period(job)
            for city in ranked_cities
            for job in grouped[city]
        })
        visible_periods = all_periods[-21:]

        for city in ranked_cities:
            city_jobs = grouped[city]
            domains = Counter(job.domain for job in city_jobs)
            families = Counter(self._family(job) for job in city_jobs)
            skills = Counter(
                skill
                for job in city_jobs
                for skill in job.skill_tags
                if self._is_graph_skill(skill)
            )
            periods = Counter(self._career_period(job) for job in city_jobs)
            salaries = [
                (job.salary_min_k + job.salary_max_k) / 2
                for job in city_jobs
                if job.salary_min_k is not None and job.salary_max_k is not None
                and 4 <= (job.salary_min_k + job.salary_max_k) / 2 <= 120
            ]
            ranked_jobs = sorted(city_jobs, key=self._evidence_rank, reverse=True)[:6]
            dominant_domain = domains.most_common(1)[0][0]
            skill_sets[city] = {name for name, _ in skills.most_common(20)}
            domain_vectors[city] = domains
            city_nodes.append({
                "id": f"city:{self._slug(city)}",
                "name": city,
                "coord": CITY_COORDS[city],
                "jobCount": len(city_jobs),
                "companyCount": len({job.company for job in city_jobs if job.company}),
                "dominantDomain": dominant_domain,
                "domainDistribution": [
                    {"name": name, "value": count, "rate": round(count / len(city_jobs) * 100, 1)}
                    for name, count in domains.most_common()
                ],
                "topFamilies": [
                    {"name": name, "count": count}
                    for name, count in families.most_common(8)
                ],
                "topSkills": [
                    {"name": name, "count": count, "coverage": round(count / len(city_jobs) * 100, 1)}
                    for name, count in skills.most_common(12)
                ],
                "timeline": [
                    {"period": period, "count": periods.get(period, 0)}
                    for period in visible_periods
                ],
                "averageSalaryK": round(median(salaries), 1) if salaries else None,
                "qualityScore": round(sum(job.quality_score for job in city_jobs) / len(city_jobs), 1),
                "sourceDistribution": dict(Counter(job.source_platform for job in city_jobs)),
                "topJobs": [
                    {
                        "id": job.source_id, "title": job.title, "company": job.company or "企业未公开",
                        "domain": job.domain, "family": self._family(job), "salary": self._salary_label(job),
                        "skills": job.skill_tags[:6], "qualityScore": round(job.quality_score, 1),
                        "sourcePlatform": job.source_platform, "sourceUrl": job.source_url,
                    }
                    for job in ranked_jobs
                ],
            })

        links: list[dict[str, Any]] = []
        linked_pairs: set[tuple[str, str]] = set()
        for city in ranked_cities[:32]:
            candidates: list[tuple[float, str, list[str]]] = []
            left_skills = skill_sets[city]
            for other in ranked_cities[:32]:
                if other == city:
                    continue
                right_skills = skill_sets[other]
                union = left_skills | right_skills
                overlap = sorted(left_skills & right_skills)
                if not union or len(overlap) < 2:
                    continue
                similarity = len(overlap) / len(union)
                left_domains, right_domains = domain_vectors[city], domain_vectors[other]
                shared_domain = sum(min(left_domains[key], right_domains[key]) for key in set(left_domains) | set(right_domains))
                domain_score = shared_domain / max(1, min(sum(left_domains.values()), sum(right_domains.values())))
                score = similarity * 0.72 + domain_score * 0.28
                candidates.append((score, other, overlap[:5]))
            for score, other, overlap in sorted(candidates, reverse=True)[:3]:
                pair = tuple(sorted((city, other)))
                if pair in linked_pairs or score < 0.28:
                    continue
                linked_pairs.add(pair)
                links.append({
                    "source": city, "target": other, "similarity": round(score, 3),
                    "sharedSkills": overlap, "type": "skill_similarity",
                })

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_policy": "recruitment_primary_live_only",
            "layout": "china_city_talent_map",
            "filters": {"domain": domain, "source_platform": source_platform},
            "stats": {
                "source_jobs": len(source_jobs),
                "mapped_jobs": sum(len(grouped[city]) for city in ranked_cities),
                "cities": len(city_nodes),
                "companies": len({job.company for job in source_jobs if job.company}),
                "links": len(links),
                "domains": dict(Counter(job.domain for job in source_jobs)),
            },
            "periods": [{"id": item, "label": self._period_label(item)} for item in visible_periods],
            "cities": city_nodes,
            "links": links,
        }

    def build_relation_network(
        self,
        jobs: Iterable[CleanedDataItem],
        *,
        domain: str | None = None,
        source_platform: str | None = None,
        period: str | None = None,
        emerging_jobs: Iterable[Any] | None = None,
    ) -> dict[str, Any]:
        """Build cross-cutting, evidence-backed graph edges from recruitment JDs.

        Co-occurrence is intentionally kept separate from prerequisite dependency:
        the available JD data can prove the former but not causal ordering.
        """
        all_source_jobs = [
            job for job in jobs
            if job.job_status == "active"
            and job.source_platform in RECRUITMENT_SOURCE_SET
            and (domain is None or job.domain == domain)
            and (source_platform is None or job.source_platform == source_platform)
        ]
        periods = sorted({self._career_period(job) for job in all_source_jobs})
        source_jobs = [
            job for job in all_source_jobs
            if period is None or self._career_period(job) == period
        ]
        families: dict[tuple[str, str], list[CleanedDataItem]] = defaultdict(list)
        for job in source_jobs:
            families[(job.domain, self._family(job))].append(job)
        ranked_families = sorted(families.items(), key=lambda item: len(item[1]), reverse=True)[:72]
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        family_skills: dict[str, set[str]] = {}
        for (family_domain, family_name), items in ranked_families:
            family_id = f"family:{self._slug(family_domain)}:{self._slug(family_name)}"
            skills = {skill for item in items for skill in item.skill_tags if self._is_graph_skill(skill)}
            family_skills[family_id] = skills
            skill_counts = Counter(
                skill for item in items for skill in item.skill_tags if self._is_graph_skill(skill)
            )
            top_skills = skill_counts.most_common(10)
            nodes.append({
                "id": family_id, "label": family_name, "title": family_name,
                "type": "family", "nodeType": "family", "domain": family_domain,
                "category": family_domain, "jobCount": len(items),
                "companyCount": len({item.company for item in items if item.company}),
                "skills": [name for name, _ in top_skills],
                "skillEvidence": [
                    {"name": name, "count": count, "coverage": round(count / len(items) * 100, 1)}
                    for name, count in top_skills
                ],
                "description": self._summary(Counter(value for item in items for value in item.responsibilities if value), family_name),
                "evidenceCount": len(items), "qualityScore": round(sum(item.quality_score for item in items) / len(items), 1),
                "period": period or (periods[-1] if periods else None),
                "evidenceIds": [item.source_id for item in items[:80]],
            })

        for left_index, ((left_domain, left_name), left_items) in enumerate(ranked_families):
            left_id = f"family:{self._slug(left_domain)}:{self._slug(left_name)}"
            left_skills = family_skills[left_id]
            for (right_domain, right_name), right_items in ranked_families[left_index + 1:]:
                right_id = f"family:{self._slug(right_domain)}:{self._slug(right_name)}"
                right_skills = family_skills[right_id]
                shared = sorted(left_skills & right_skills)
                union = left_skills | right_skills
                score = len(shared) / len(union) if union else 0
                if len(shared) < 2 or score < 0.16:
                    continue
                evidence_ids = [item.source_id for item in (left_items + right_items) if set(item.skill_tags) & set(shared)][:12]
                relation_type = "job_similarity" if left_domain == right_domain else "talent_mobility_inference"
                edges.append({
                    "id": f"{relation_type}:{left_id}:{right_id}", "source": left_id, "target": right_id,
                    "relationType": relation_type, "label": "岗位相似" if relation_type == "job_similarity" else "能力可迁移（推断）",
                    "weight": round(score, 3), "confidence": round(min(0.92, 0.45 + score), 3),
                    "sharedSkills": shared[:8], "evidenceIds": evidence_ids,
                    "method": "skill_jaccard_overlap", "timeWindow": "current_active_jobs",
                })

        skill_jobs: dict[str, list[CleanedDataItem]] = defaultdict(list)
        pair_jobs: dict[tuple[str, str], list[CleanedDataItem]] = defaultdict(list)
        for job in source_jobs:
            skills = sorted({skill for skill in job.skill_tags if self._is_graph_skill(skill)})[:16]
            for skill in skills:
                skill_jobs[skill].append(job)
            for index, left in enumerate(skills):
                for right in skills[index + 1:]:
                    pair_jobs[(left, right)].append(job)
        for skill, items in sorted(skill_jobs.items(), key=lambda item: len(item[1]), reverse=True)[:60]:
            domains = Counter(item.domain for item in items)
            nodes.append({
                "id": f"skill:{self._slug(skill)}", "label": skill, "title": skill,
                "type": "skill", "nodeType": "skill", "domain": domains.most_common(1)[0][0],
                "category": domains.most_common(1)[0][0], "supportCount": len(items),
                "jobCount": len(items), "coverage": round(len(items) / max(1, len(source_jobs)) * 100, 1),
                "evidenceCount": len(items), "period": period or (periods[-1] if periods else None),
                "description": f"{len(items)} 条招聘岗位提及该技能，占当前时间切片 {round(len(items) / max(1, len(source_jobs)) * 100, 1)}%。",
                "evidenceIds": [item.source_id for item in items[:80]],
            })
        visible_skill_ids = {node["id"] for node in nodes if node["type"] == "skill"}
        for (family_domain, family_name), items in ranked_families:
            family_id = f"family:{self._slug(family_domain)}:{self._slug(family_name)}"
            counts = Counter(skill for item in items for skill in item.skill_tags if self._is_graph_skill(skill))
            for skill, count in counts.most_common(8):
                skill_id = f"skill:{self._slug(skill)}"
                if skill_id not in visible_skill_ids:
                    continue
                coverage = count / max(1, len(items))
                edges.append({
                    "id": f"requires_skill:{family_id}:{skill_id}", "source": family_id, "target": skill_id,
                    "relationType": "core_skill" if coverage >= 0.4 else "requires_skill",
                    "label": "核心技能" if coverage >= 0.4 else "岗位技能", "weight": round(coverage, 3),
                    "confidence": round(min(0.98, 0.55 + coverage / 2), 3),
                    "evidenceIds": [item.source_id for item in items if skill in item.skill_tags][:12],
                    "method": "same_family_skill_coverage", "timeWindow": period or "current_active_jobs",
                })
        for (left, right), items in sorted(pair_jobs.items(), key=lambda item: len(item[1]), reverse=True)[:90]:
            if len(items) < 3:
                continue
            support = len(items) / max(1, min(len(skill_jobs[left]), len(skill_jobs[right])))
            edges.append({
                "id": f"skill_cooccurrence:{self._slug(left)}:{self._slug(right)}", "source": f"skill:{self._slug(left)}", "target": f"skill:{self._slug(right)}",
                "relationType": "skill_cooccurrence", "label": "技能共现", "weight": round(support, 3),
                "confidence": round(min(0.95, 0.45 + support / 2), 3), "evidenceIds": [item.source_id for item in items[:12]],
                "method": "same_jd_skill_cooccurrence", "timeWindow": "current_active_jobs",
            })

        city_company_jobs: dict[tuple[str, str], list[CleanedDataItem]] = defaultdict(list)
        for job in source_jobs:
            if job.city and job.company:
                city_company_jobs[(job.city, job.company)].append(job)
        for (city, company), items in sorted(city_company_jobs.items(), key=lambda item: len(item[1]), reverse=True)[:60]:
            city_id, company_id = f"city:{self._slug(city)}", f"company:{self._slug(company)}"
            nodes.extend(({"id": city_id, "label": city, "type": "city"}, {"id": company_id, "label": company, "type": "company"}))
            edges.append({"id": f"recruits_in:{city_id}:{company_id}", "source": company_id, "target": city_id, "relationType": "recruits_in", "label": "在此招聘", "weight": len(items), "confidence": 0.95, "evidenceIds": [item.source_id for item in items[:12]], "method": "jd_company_city", "timeWindow": "published_or_collected_at"})

        for candidate in emerging_jobs or []:
            if not candidate.source_family:
                continue
            candidate_id = f"emerging:{candidate.candidate_id}"
            source_match = next((node for node in nodes if node["type"] == "family" and node["label"] == candidate.source_family), None)
            if not source_match:
                continue
            nodes.append({"id": candidate_id, "label": candidate.name, "type": "emerging_job", "evidenceIds": [item.get("source_id") for item in candidate.evidence if item.get("source_id")]})
            edges.append({"id": f"emerges_from:{source_match['id']}:{candidate_id}", "source": source_match["id"], "target": candidate_id, "relationType": "emerges_from", "label": "从岗位族分化", "weight": candidate.confidence, "confidence": candidate.confidence, "newSkills": candidate.required_skills[:8], "evidenceIds": [item.get("source_id") for item in candidate.evidence if item.get("source_id")][:12], "method": "emerging_job_family_lineage", "timeWindow": "candidate_trend_series"})

        deduped_nodes = {node["id"]: node for node in nodes}
        return {
            "generated_at": datetime.now(UTC).isoformat(), "data_policy": "recruitment_primary_with_inference_labels",
            "dependency_policy": "No prerequisite edges are emitted without an explicit skill ontology; co-occurrence is non-causal.",
            "period": period,
            "periods": [{"id": item, "label": self._period_label(item)} for item in periods],
            "nodes": list(deduped_nodes.values()), "edges": edges,
            "stats": {"source_jobs": len(source_jobs), "nodes": len(deduped_nodes), "edges": len(edges), "job_skill_relations": sum(edge["relationType"] in {"core_skill", "requires_skill"} for edge in edges), "job_relations": sum(edge["relationType"] in {"job_similarity", "talent_mobility_inference"} for edge in edges), "skill_cooccurrences": sum(edge["relationType"] == "skill_cooccurrence" for edge in edges), "lineages": sum(edge["relationType"] == "emerges_from" for edge in edges)},
        }

    def build_hierarchy_level(
        self,
        jobs: Iterable[CleanedDataItem],
        *,
        parent_id: str | None = None,
        domain: str | None = None,
        source_platform: str | None = None,
    ) -> dict[str, Any]:
        graph = self.build(
            jobs,
            domain=domain,
            source_platform=source_platform,
            max_jobs_per_domain=40,
            max_skills_per_job=20,
            max_evidence=1000,
        )
        nodes_by_id = {node["id"]: node for node in graph["nodes"]}
        if parent_id is None:
            children = [node for node in graph["nodes"] if node["type"] == "domain"]
            path = []
        else:
            if parent_id not in nodes_by_id:
                return {}
            children = [node for node in graph["nodes"] if node.get("parent") == parent_id]
            path = []
            cursor = nodes_by_id[parent_id]
            while cursor:
                path.append({
                    "id": cursor["id"],
                    "label": cursor["label"],
                    "type": cursor["type"],
                })
                cursor = nodes_by_id.get(cursor.get("parent"))
            path.reverse()
        child_ids = {node["id"] for node in children}
        edges = [
            edge for edge in graph["edges"]
            if edge["target"] in child_ids or (parent_id and edge["source"] == parent_id)
        ]
        return {
            "generated_at": graph["generated_at"],
            "data_policy": graph["data_policy"],
            "parent": nodes_by_id.get(parent_id) if parent_id else None,
            "path": path,
            "children": children,
            "edges": edges,
            "stats": graph["stats"],
        }

    def build_city_drilldown(
        self,
        jobs: Iterable[CleanedDataItem],
        *,
        city: str,
        domain: str | None = None,
        family: str | None = None,
        skill: str | None = None,
        source_platform: str | None = None,
    ) -> dict[str, Any]:
        """Return one lightweight, decision-oriented level of the city evidence graph."""
        city_name = city.strip().removesuffix("市")
        city_jobs = [
            job for job in jobs
            if job.job_status == "active"
            and job.source_platform in RECRUITMENT_SOURCE_SET
            and (job.city or "").strip().removesuffix("市") == city_name
            and (source_platform is None or job.source_platform == source_platform)
        ]
        if not city_jobs:
            return {}

        scoped_jobs = city_jobs
        path = [{"type": "city", "name": city_name}]
        level = "domain"
        if domain:
            scoped_jobs = [job for job in scoped_jobs if job.domain == domain]
            path.append({"type": "domain", "name": domain})
            level = "family"
        if family:
            scoped_jobs = [job for job in scoped_jobs if self._family(job) == family]
            path.append({"type": "family", "name": family})
            level = "skill"
        if skill:
            scoped_jobs = [job for job in scoped_jobs if skill in job.skill_tags]
            path.append({"type": "skill", "name": skill})
            level = "evidence"
        if not scoped_jobs:
            return {}

        def midpoint(job: CleanedDataItem) -> float | None:
            if job.salary_min_k is None or job.salary_max_k is None:
                return None
            value = (job.salary_min_k + job.salary_max_k) / 2
            return value if 4 <= value <= 120 else None

        def summary(items: list[CleanedDataItem]) -> dict[str, Any]:
            salaries = [value for item in items if (value := midpoint(item)) is not None]
            periods = Counter(self._career_period(item) for item in items)
            ordered_periods = sorted(periods)
            current = periods[ordered_periods[-1]] if ordered_periods else 0
            previous = periods[ordered_periods[-2]] if len(ordered_periods) > 1 else 0
            delta = round((current - previous) / previous * 100, 1) if previous else None
            return {
                "jobCount": len(items),
                "companyCount": len({item.company for item in items if item.company}),
                "medianSalaryK": round(median(salaries), 1) if salaries else None,
                "qualityScore": round(sum(item.quality_score for item in items) / len(items), 1),
                "sourceDistribution": dict(Counter(item.source_platform for item in items)),
                "latestBatch": current,
                "previousBatch": previous,
                "batchDelta": delta,
                "topResponsibilities": [
                    name for name, _ in Counter(
                        value for item in items for value in item.responsibilities if value
                    ).most_common(6)
                ],
                "topRequirements": [
                    name for name, _ in Counter(
                        value for item in items for value in item.requirements if value
                    ).most_common(6)
                ],
            }

        children: list[dict[str, Any]] = []
        if level == "domain":
            grouped = defaultdict(list)
            for job in scoped_jobs:
                grouped[job.domain].append(job)
            for name, items in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
                node = summary(items)
                node.update({
                    "id": f"domain:{self._slug(name)}", "name": name, "type": "domain",
                    "share": round(len(items) / len(scoped_jobs) * 100, 1),
                    "topSkills": [
                        value for value, _ in Counter(
                            skill_name for item in items for skill_name in item.skill_tags
                            if self._is_graph_skill(skill_name)
                        ).most_common(5)
                    ],
                })
                children.append(node)
        elif level == "family":
            grouped = defaultdict(list)
            for job in scoped_jobs:
                grouped[self._family(job)].append(job)
            for name, items in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[:18]:
                node = summary(items)
                node.update({
                    "id": f"family:{self._slug(name)}", "name": name, "type": "family",
                    "share": round(len(items) / len(scoped_jobs) * 100, 1),
                    "topSkills": [
                        value for value, _ in Counter(
                            skill_name for item in items for skill_name in item.skill_tags
                            if self._is_graph_skill(skill_name)
                        ).most_common(6)
                    ],
                })
                children.append(node)
        elif level == "skill":
            counts = Counter(
                skill_name for item in scoped_jobs for skill_name in item.skill_tags
                if self._is_graph_skill(skill_name)
            )
            for name, count in counts.most_common(24):
                items = [item for item in scoped_jobs if name in item.skill_tags]
                node = summary(items)
                node.update({
                    "id": f"skill:{self._slug(name)}", "name": name, "type": "skill",
                    "category": self._skill_category(name), "jobCount": count,
                    "share": round(count / len(scoped_jobs) * 100, 1),
                })
                children.append(node)
        else:
            for job in sorted(scoped_jobs, key=self._evidence_rank, reverse=True)[:36]:
                children.append({
                    "id": job.source_id, "name": job.title, "type": "evidence",
                    "title": job.title, "company": job.company or "企业未公开",
                    "city": city_name, "salary": self._salary_label(job),
                    "experience": self._experience_label(job), "education": job.education or "不限",
                    "qualityScore": round(job.quality_score, 1), "sourcePlatform": job.source_platform,
                    "sourceUrl": job.source_url, "publishedAt": (
                        job.published_at or job.collected_at
                    ).isoformat(),
                    "skills": job.skill_tags[:10],
                    "responsibilities": job.responsibilities[:5],
                    "requirements": job.requirements[:5],
                    "snippet": self._snippet(job, skill or ""),
                })

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_policy": "recruitment_primary_live_only",
            "level": level,
            "path": path,
            "focus": path[-1],
            "summary": summary(scoped_jobs),
            "children": children,
        }

    def build_career_galaxy(
        self,
        jobs: Iterable[CleanedDataItem],
        *,
        domain: str | None = None,
        source_platform: str | None = None,
        max_nodes: int = 1400,
        community_signals: Iterable[CommunitySignal] | None = None,
        deep_relations: bool = False,
    ) -> dict[str, Any]:
        """Build a multi-scale temporal galaxy from persisted recruitment evidence."""
        source_jobs = [
            job for job in jobs
            if job.job_status == "active"
            and job.source_platform in RECRUITMENT_SOURCE_SET
            and (domain is None or job.domain == domain)
            and (source_platform is None or job.source_platform == source_platform)
        ]
        sampling_buckets: dict[tuple[str, str], list[CleanedDataItem]] = defaultdict(list)
        for job in source_jobs:
            sampling_buckets[(self._career_period(job), job.domain)].append(job)
        quota = max(1, max_nodes // max(1, len(sampling_buckets)))
        ranked: list[CleanedDataItem] = []
        selected_ids: set[str] = set()
        for bucket_jobs in sampling_buckets.values():
            for job in sorted(bucket_jobs, key=self._evidence_rank, reverse=True)[:quota]:
                ranked.append(job)
                selected_ids.add(job.source_id)
        if len(ranked) < max_nodes:
            remainder = sorted(
                (job for job in source_jobs if job.source_id not in selected_ids),
                key=self._evidence_rank, reverse=True,
            )
            ranked.extend(remainder[:max_nodes - len(ranked)])
        actual_periods = sorted({self._career_period(job) for job in ranked})
        periods = self._monthly_axis(actual_periods[-1], months=12) if actual_periods else []
        actual_period_set = set(actual_periods)
        period_index = {period: index for index, period in enumerate(periods)}
        period_gap = 34
        job_nodes: list[dict[str, Any]] = []
        raw_grouped: dict[tuple[str, str, str], list[CleanedDataItem]] = defaultdict(list)
        for job in ranked:
            raw_grouped[(self._career_period(job), job.domain, self._family(job))].append(job)
        retained_families: dict[tuple[str, str], set[str]] = defaultdict(set)
        for (period, domain_name, family_name), family_jobs in sorted(raw_grouped.items(), key=lambda item: len(item[1]), reverse=True):
            bucket = retained_families[(period, domain_name)]
            if len(bucket) < 18:
                bucket.add(family_name)
        grouped: dict[tuple[str, str, str], list[CleanedDataItem]] = defaultdict(list)
        family_by_job: dict[str, str] = {}
        for (period, domain_name, family_name), family_jobs in raw_grouped.items():
            display_family = family_name if family_name in retained_families[(period, domain_name)] else f"{domain_name}其他技术岗位"
            grouped[(period, domain_name, display_family)].extend(family_jobs)
            for job in family_jobs:
                family_by_job[job.source_id] = display_family

        family_angles: dict[tuple[str, str], float] = {}
        family_radii: dict[tuple[str, str], float] = {}
        domain_centers = {"人工智能": 0.15, "大数据": math.pi / 2, "智能系统": math.pi, "物联网": math.pi * 1.5}
        domain_families: dict[str, list[str]] = defaultdict(list)
        for _, domain_name, family_name in grouped:
            if family_name not in domain_families[domain_name]:
                domain_families[domain_name].append(family_name)
        for domain_name, family_names in domain_families.items():
            ordered = sorted(family_names)
            for index, family_name in enumerate(ordered):
                offset = (index - (len(ordered) - 1) / 2) * min(0.14, 0.72 / max(1, len(ordered)))
                family_angles[(domain_name, family_name)] = domain_centers.get(domain_name, 0) + offset
                family_radii[(domain_name, family_name)] = 5.5 + index % 3 * 3.2

        for job in ranked:
            period = self._career_period(job)
            ring_type = self._career_ring(job)
            seed = int(hashlib.sha1(job.source_id.encode("utf-8")).hexdigest()[:12], 16)
            radius = {"inner": 15, "middle": 27, "outer": 39}[ring_type]
            family_name = family_by_job[job.source_id]
            base_angle = family_angles[(job.domain, family_name)]
            angle = base_angle + ((seed % 10000) / 10000 - 0.5) * 0.7
            jitter = ((seed // 10000) % 1000) / 1000 * 4 - 2
            salary = self._salary_label(job)
            description = (job.raw_content or job.content or "").strip()[:900]
            family_id = f"family:{self._slug(job.domain)}:{self._slug(family_name)}:{period}"
            job_nodes.append({
                "id": job.source_id,
                "nodeType": "job",
                "name": job.title,
                "title": job.title,
                "category": job.domain,
                "domain": job.domain,
                "ringType": ring_type,
                "period": period,
                "periodIndex": period_index[period],
                "x": round((radius + jitter) * math.cos(angle), 3),
                "y": round((radius + jitter) * math.sin(angle), 3),
                "z": -period_index[period] * period_gap,
                "company": job.company or "企业未公开",
                "location": "·".join(part for part in (job.city, job.district) if part) or "地点未公开",
                "salary": salary,
                "experience": self._experience_label(job),
                "education": job.education or "不限",
                "skills": job.skill_tags[:14],
                "responsibilities": job.responsibilities[:8],
                "requirements": job.requirements[:8],
                "description": description,
                "sourcePlatform": job.source_platform,
                "sourceUrl": job.source_url,
                "qualityScore": round(job.quality_score, 1),
                "publishedAt": (job.published_at or job.collected_at).isoformat(),
                "collectedAt": job.collected_at.isoformat(),
                "family": family_name,
                "familyId": family_id,
            })

        family_nodes: list[dict[str, Any]] = []
        skill_nodes: list[dict[str, Any]] = []
        for (period, domain_name, family_name), family_jobs in sorted(grouped.items()):
            angle = family_angles[(domain_name, family_name)]
            hub_radius = family_radii[(domain_name, family_name)]
            family_id = f"family:{self._slug(domain_name)}:{self._slug(family_name)}:{period}"
            skill_counts = Counter(skill for item in family_jobs for skill in item.skill_tags if self._is_graph_skill(skill))
            top_skills = skill_counts.most_common(14 if deep_relations else 8)
            responsibilities = Counter(item for job in family_jobs for item in job.responsibilities if item)
            family_node = {
                "id": family_id, "nodeType": "family", "name": family_name, "title": family_name,
                "category": domain_name, "domain": domain_name, "period": period,
                "periodIndex": period_index[period], "x": round(math.cos(angle) * hub_radius, 3),
                "y": round(math.sin(angle) * hub_radius, 3), "z": -period_index[period] * period_gap,
                "ringType": "hub", "family": family_name, "jobCount": len(family_jobs),
                "companyCount": len({job.company for job in family_jobs if job.company}),
                "cities": [name for name, _ in Counter(job.city for job in family_jobs if job.city).most_common(5)],
                "skills": [name for name, _ in top_skills],
                "skillEvidence": [{"name": name, "count": count, "coverage": round(count / len(family_jobs) * 100, 1)} for name, count in top_skills],
                "responsibilities": [name for name, _ in responsibilities.most_common(5)],
                "qualityScore": round(sum(job.quality_score for job in family_jobs) / len(family_jobs), 1),
                "description": self._summary(responsibilities, family_name),
                "evidenceIds": [job.source_id for job in family_jobs[:100]],
                "evidenceStatus": "verified_recruitment",
                "firstSeenAt": min(job.published_at or job.collected_at for job in family_jobs).isoformat(),
                "lastSeenAt": max(job.published_at or job.collected_at for job in family_jobs).isoformat(),
                "isSimulated": False,
            }
            family_nodes.append(family_node)
            for skill_index, (skill, count) in enumerate(top_skills[:12 if deep_relations else 6]):
                skill_angle = angle + (skill_index - 2.5) * 0.09
                skill_id = f"skill:{self._slug(domain_name)}:{self._slug(family_name)}:{self._slug(skill)}:{period}"
                skill_nodes.append({
                    "id": skill_id, "nodeType": "skill", "name": skill, "title": skill,
                    "category": domain_name, "domain": domain_name, "period": period,
                    "periodIndex": period_index[period], "x": round(math.cos(skill_angle) * (47 + skill_index % 2 * 3), 3),
                    "y": round(math.sin(skill_angle) * (47 + skill_index % 2 * 3), 3),
                    "z": -period_index[period] * period_gap, "ringType": "skill", "family": family_name,
                    "familyId": family_id, "supportCount": count,
                    "coverage": round(count / len(family_jobs) * 100, 1), "jobCount": len(family_jobs),
                    "description": f"{count} 条真实岗位要求提及该技能，占当前岗位族 {round(count / len(family_jobs) * 100, 1)}%。",
                    "evidenceIds": [job.source_id for job in family_jobs if skill in job.skill_tags][:100],
                    "evidenceStatus": "verified_recruitment",
                    "canPublishAbility": True,
                    "isSimulated": False,
                })

        # When the live dataset does not yet span a year, derive deterministic monthly
        # snapshots for visual evolution only. These nodes never become formal evidence.
        latest_templates: dict[tuple[str, str], dict[str, Any]] = {}
        for node in family_nodes:
            if actual_periods and node["period"] != actual_periods[-1]:
                continue
            key = (node["category"], node["family"])
            if key not in latest_templates or node["periodIndex"] > latest_templates[key]["periodIndex"]:
                latest_templates[key] = node
        skills_by_template: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for node in skill_nodes:
            template = latest_templates.get((node["category"], node["family"]))
            if template and node["period"] == template["period"]:
                skills_by_template[(node["category"], node["family"])].append(node)
        existing_family_keys = {(node["period"], node["category"], node["family"]) for node in family_nodes}
        for (domain_name, family_name), template in latest_templates.items():
            family_seed = int(hashlib.sha1(f"{domain_name}:{family_name}".encode("utf-8")).hexdigest()[:8], 16)
            introduction_index = 3 + family_seed % 7 if family_seed % 10 == 0 else 0
            yearly_direction = ((family_seed % 2001) / 2000 - 0.5) * 0.72
            for target_period in periods:
                target_index = period_index[target_period]
                if target_index < introduction_index or (target_period, domain_name, family_name) in existing_family_keys:
                    continue
                progress = target_index / max(1, len(periods) - 1)
                wave = math.sin((target_index + family_seed % 7) * 0.72) * 0.035
                factor = max(0.34, 1 - yearly_direction * (1 - progress) + wave)
                projected_jobs = max(1, round(template["jobCount"] * factor))
                family_id = f"family:{self._slug(domain_name)}:{self._slug(family_name)}:{target_period}"
                projected_family = {
                    **template,
                    "id": family_id,
                    "period": target_period,
                    "periodIndex": target_index,
                    "z": -target_index * period_gap,
                    "jobCount": projected_jobs,
                    "companyCount": max(1, round(template["companyCount"] * factor)),
                    "evidenceIds": [],
                    "evidenceStatus": "simulated_historical_projection",
                    "description": f"基于当前真实岗位结构反向推演的 {self._period_label(target_period)} 月度展示快照，不作为正式招聘证据。",
                    "isSimulated": True,
                    "simulationBasisPeriod": template["period"],
                }
                projected_skill_evidence = []
                projected_skills = []
                for skill_index, skill_template in enumerate(skills_by_template[(domain_name, family_name)]):
                    skill_seed = int(hashlib.sha1(f"{family_name}:{skill_template['title']}".encode("utf-8")).hexdigest()[:8], 16)
                    skill_introduction = introduction_index if skill_index < 2 else min(9, introduction_index + 1 + skill_seed % 7)
                    if target_index < skill_introduction:
                        continue
                    coverage_shift = (((skill_seed % 1001) / 1000) - 0.5) * 28 * (1 - progress)
                    coverage = round(max(5, min(98, skill_template["coverage"] - coverage_shift)), 1)
                    support = max(1, round(projected_jobs * coverage / 100))
                    skill_id = f"skill:{self._slug(domain_name)}:{self._slug(family_name)}:{self._slug(skill_template['title'])}:{target_period}"
                    skill_nodes.append({
                        **skill_template,
                        "id": skill_id,
                        "period": target_period,
                        "periodIndex": target_index,
                        "z": -target_index * period_gap,
                        "familyId": family_id,
                        "supportCount": support,
                        "jobCount": projected_jobs,
                        "coverage": coverage,
                        "description": f"{self._period_label(target_period)} 推演覆盖率 {coverage}%，仅用于月度演化展示。",
                        "evidenceIds": [],
                        "evidenceStatus": "simulated_historical_projection",
                        "canPublishAbility": False,
                        "isSimulated": True,
                        "simulationBasisPeriod": template["period"],
                    })
                    projected_skills.append(skill_template["title"])
                    projected_skill_evidence.append({"name": skill_template["title"], "count": support, "coverage": coverage})
                projected_family["skills"] = projected_skills
                projected_family["skillEvidence"] = projected_skill_evidence
                family_nodes.append(projected_family)

        signal_nodes: list[dict[str, Any]] = []
        skill_targets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for node in skill_nodes:
            skill_targets[node["title"]].append(node)
        for signal_index, signal in enumerate(sorted(
            community_signals or [],
            key=lambda item: item.published_at or item.collected_at,
            reverse=True,
        )):
            signal_skills = extract_skills(
                f"{signal.title} {signal.content} {' '.join(signal.tags)}",
                signal.tags,
            )
            target = next((
                sorted(skill_targets[skill], key=lambda item: item["periodIndex"], reverse=True)[0]
                for skill in signal_skills if skill in skill_targets
            ), None)
            if target is None or len(signal_nodes) >= 80:
                continue
            angle = signal_index * 2.399963
            signal_nodes.append({
                "id": f"signal:{self._slug(signal.signal_id)}",
                "nodeType": "signal",
                "name": signal.title,
                "title": signal.title,
                "category": target["category"],
                "domain": target["domain"],
                "period": target["period"],
                "periodIndex": target["periodIndex"],
                "x": round(target["x"] + math.cos(angle) * 8, 3),
                "y": round(target["y"] + math.sin(angle) * 8, 3),
                "z": target["z"],
                "ringType": "signal",
                "family": target["family"],
                "familyId": target["familyId"],
                "targetSkillId": target["id"],
                "skills": signal_skills[:8],
                "description": signal.content[:420],
                "sourcePlatform": signal.source_platform,
                "sourceUrl": signal.source_url,
                "qualityScore": signal.quality_score,
                "evidenceRole": "auxiliary_only",
                "canPublishAbility": False,
                "publishedAt": (signal.published_at or signal.collected_at).isoformat(),
            })
        nodes = family_nodes + job_nodes + skill_nodes + signal_nodes
        links: list[dict[str, Any]] = []
        linked: set[tuple[str, str, str]] = set()

        def add_link(source: str, target: str, relation: str, weight: float, **metadata: Any) -> None:
            if source == target:
                return
            pair = tuple(sorted((source, target))) + (relation,)
            if pair in linked:
                return
            linked.add(pair)
            links.append({"source": source, "target": target, "type": relation, "weight": round(weight, 2), **metadata})

        for node in job_nodes:
            add_link(node["familyId"], node["id"], "family_member", 0.35)
        temporal_skills: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for node in skill_nodes:
            temporal_skills[(node["category"], node["family"], node["title"])].append(node)
        for temporal_nodes in temporal_skills.values():
            ordered = sorted(temporal_nodes, key=lambda item: item["periodIndex"])
            for index, node in enumerate(ordered):
                previous = ordered[index - 1] if index else None
                change_marker = int(hashlib.sha1(f"{node['category']}:{node['family']}:{node['title']}:{node['period']}".encode("utf-8")).hexdigest()[:8], 16) % 3 == 0
                if previous is None and node["periodIndex"] > 0:
                    change_state = "added"
                    node["evolutionState"] = "emerging"
                elif previous and change_marker and node["coverage"] >= previous["coverage"] + 0.8:
                    change_state = "strengthened"
                    node["evolutionState"] = "emerging"
                elif previous and change_marker and node["coverage"] <= previous["coverage"] - 0.8:
                    change_state = "weakened"
                    node["evolutionState"] = "declining"
                else:
                    change_state = "stable"
                    node["evolutionState"] = "stable"
                add_link(
                    node["familyId"], node["id"], "requires_skill", max(0.25, node["coverage"] / 100),
                    changeState=change_state,
                    coverageDelta=round(node["coverage"] - previous["coverage"], 1) if previous else None,
                    simulated=bool(node.get("isSimulated")),
                )
        for node in signal_nodes:
            add_link(
                node["targetSkillId"],
                node["id"],
                "auxiliary_signal",
                0.18,
                visualStyle="dashed",
                evidenceRole="auxiliary_only",
            )
        temporal_families: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for node in family_nodes:
            temporal_families[(node["category"], node["family"])].append(node)
        for temporal_nodes in temporal_families.values():
            ordered = sorted(temporal_nodes, key=lambda item: item["periodIndex"])
            for index, node in enumerate(ordered):
                previous_node = ordered[index - 1] if index > 0 else None
                if node["periodIndex"] < len(periods) - 1 and index == len(ordered) - 1:
                    node["evolutionState"] = "exited"
                elif previous_node and node["jobCount"] < previous_node["jobCount"]:
                    node["evolutionState"] = "declining"
                elif previous_node and node["jobCount"] > previous_node["jobCount"]:
                    node["evolutionState"] = "emerging"
                elif index == 0 and node["periodIndex"] > 0:
                    node["evolutionState"] = "emerging"
                else:
                    node["evolutionState"] = "stable"
            for left, right in zip(ordered, ordered[1:]):
                left_skills = {item["name"]: item["coverage"] for item in left["skillEvidence"]}
                right_skills = {item["name"]: item["coverage"] for item in right["skillEvidence"]}
                added = sorted(set(right_skills) - set(left_skills))[:5]
                removed = sorted(set(left_skills) - set(right_skills))[:5]
                rising = sorted(
                    ({"name": name, "delta": round(right_skills[name] - left_skills[name], 1)} for name in set(left_skills) & set(right_skills)),
                    key=lambda item: item["delta"], reverse=True,
                )[:4]
                add_link(left["id"], right["id"], "evolution", 0.95, addedSkills=added, removedSkills=removed,
                         risingSkills=[item for item in rising if item["delta"] > 0],
                         jobDelta=right["jobCount"] - left["jobCount"])

        # Keep lateral relations sparse: they appear only when a selected time slice is inspected.
        fusion_candidates = []
        families_by_period: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for node in family_nodes:
            families_by_period[node["period"]].append(node)
        for period, period_families in families_by_period.items():
            for left_index, left in enumerate(period_families):
                left_skills = {item["name"] for item in left["skillEvidence"]}
                for right in period_families[left_index + 1:]:
                    right_skills = {item["name"] for item in right["skillEvidence"]}
                    shared = sorted(left_skills & right_skills)
                    union = left_skills | right_skills
                    similarity = len(shared) / max(1, len(union))
                    if len(shared) < 2 or similarity < 0.16:
                        continue
                    if left["category"] != right["category"]:
                        relation = "talent_mobility"
                    elif len(shared) >= 3 and similarity >= 0.42:
                        relation = "possible_fusion"
                    else:
                        relation = "job_similarity"
                    fusion_candidates.append((similarity, left, right, relation, shared, period))
        for similarity, left, right, relation, shared, period in sorted(fusion_candidates, reverse=True, key=lambda item: item[0])[:80]:
            add_link(left["id"], right["id"], relation, similarity, sharedSkills=shared[:8], period=period,
                     confidence=round(min(0.92, 0.48 + similarity), 2), inferred=True)
            if relation == "possible_fusion":
                left["fusionCandidate"] = True
                right["fusionCandidate"] = True

        skill_node_ids = {
            (node["period"], node["category"], node["family"], node["title"]): node["id"]
            for node in skill_nodes
        }
        if deep_relations:
            # The wormhole overview keeps every relation sparse and explainable:
            # job -> skill is direct JD evidence, while job <-> job is a bounded
            # similarity inference. The regular temporal view does not pay this
            # payload or rendering cost.
            for node in job_nodes:
                for skill in node.get("skills", [])[:8]:
                    skill_id = skill_node_ids.get((node["period"], node["category"], node["family"], skill))
                    if skill_id:
                        add_link(
                            node["id"], skill_id, "job_requires_skill", 1.0,
                            skill=skill, evidenceIds=[node["id"]], inferred=False,
                        )

            job_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
            for node in job_nodes:
                job_groups[(node["period"], node["category"], node["family"])].append(node)
            for group_nodes in job_groups.values():
                postings: dict[str, list[dict[str, Any]]] = defaultdict(list)
                skill_sets: dict[str, set[str]] = {}
                for node in group_nodes:
                    node_skills = {
                        skill for skill in node.get("skills", [])[:12]
                        if self._is_graph_skill(skill)
                    }
                    skill_sets[node["id"]] = node_skills
                    for skill in node_skills:
                        postings[skill].append(node)
                for node in group_nodes:
                    own_skills = skill_sets[node["id"]]
                    if len(own_skills) < 2:
                        continue
                    candidates: dict[str, dict[str, Any]] = {}
                    for skill in sorted(own_skills, key=lambda value: len(postings[value])):
                        for candidate in postings[skill][:80]:
                            if candidate["id"] != node["id"]:
                                candidates[candidate["id"]] = candidate
                        if len(candidates) >= 120:
                            break
                    scored = []
                    for candidate in candidates.values():
                        shared = sorted(own_skills & skill_sets[candidate["id"]])
                        if len(shared) < 2:
                            continue
                        union = own_skills | skill_sets[candidate["id"]]
                        similarity = len(shared) / max(1, len(union))
                        if similarity >= 0.24:
                            scored.append((similarity, candidate, shared))
                    for similarity, candidate, shared in sorted(
                        scored, key=lambda item: (-item[0], item[1]["id"]),
                    )[:2]:
                        add_link(
                            node["id"], candidate["id"], "job_similarity", similarity,
                            sharedSkills=shared[:8], confidence=round(similarity, 3),
                            evidenceIds=[node["id"], candidate["id"]], inferred=True,
                            relationScope="job_instance",
                        )

            shared_skill_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
            for node in skill_nodes:
                shared_skill_groups[(node["period"], node["title"])].append(node)
            for (period, skill), matching_nodes in shared_skill_groups.items():
                actual_nodes = [node for node in matching_nodes if not node.get("isSimulated")]
                candidates = actual_nodes or matching_nodes
                if len(candidates) < 2:
                    continue
                anchor = max(candidates, key=lambda item: (item.get("supportCount", 0), item["id"]))
                for other in candidates:
                    if other["id"] != anchor["id"]:
                        add_link(
                            anchor["id"], other["id"], "shared_skill", 0.72,
                            skill=skill, period=period, inferred=False,
                        )

        for (period, domain_name, family_name), family_jobs in grouped.items():
            pairs = Counter()
            for job in family_jobs:
                skills = sorted({skill for skill in job.skill_tags if self._is_graph_skill(skill)})[:12]
                for left_index, left in enumerate(skills):
                    for right in skills[left_index + 1:]:
                        pairs[(left, right)] += 1
            for (left, right), support in pairs.most_common(4):
                left_id = skill_node_ids.get((period, domain_name, family_name, left))
                right_id = skill_node_ids.get((period, domain_name, family_name, right))
                if left_id and right_id and support >= 2:
                    add_link(left_id, right_id, "skill_cooccurrence", support / max(1, len(family_jobs)),
                             supportCount=support, period=period, inferred=False)

        period_counts = Counter(node["period"] for node in job_nodes)
        layers = [
            {
                "id": period,
                "label": self._period_label(period),
                "index": period_index[period],
                "z": -period_index[period] * period_gap,
                "jobCount": period_counts[period] or sum(node["jobCount"] for node in family_nodes if node["period"] == period),
                "familyCount": sum(node["period"] == period for node in family_nodes),
                "skillCount": sum(node["period"] == period for node in skill_nodes),
                "isSimulated": period not in actual_period_set,
                "dataLabel": "真实招聘数据" if period in actual_period_set else "历史推演快照",
            }
            for period in periods
        ]
        if deep_relations:
            compact_fields = {
                "family": {
                    "id", "nodeType", "name", "title", "category", "domain", "period", "periodIndex",
                    "x", "y", "z", "ringType", "family", "jobCount", "companyCount", "cities", "skills",
                    "skillEvidence", "qualityScore", "evidenceStatus", "isSimulated", "evolutionState",
                    "fusionCandidate", "firstSeenAt", "lastSeenAt",
                },
                "job": {
                    "id", "nodeType", "name", "title", "category", "domain", "ringType", "period",
                    "periodIndex", "x", "y", "z", "company", "location", "salary", "experience",
                    "education", "skills", "sourcePlatform", "sourceUrl", "qualityScore", "publishedAt",
                    "family", "familyId",
                },
                "skill": {
                    "id", "nodeType", "name", "title", "category", "domain", "period", "periodIndex",
                    "x", "y", "z", "ringType", "family", "familyId", "supportCount", "coverage",
                    "jobCount", "evidenceStatus", "canPublishAbility", "isSimulated", "evolutionState",
                },
                "signal": {
                    "id", "nodeType", "name", "title", "category", "domain", "period", "periodIndex",
                    "x", "y", "z", "ringType", "family", "familyId", "targetSkillId", "skills",
                    "sourcePlatform", "sourceUrl", "qualityScore", "evidenceRole", "canPublishAbility",
                    "publishedAt",
                },
            }
            nodes = [
                {key: value for key, value in node.items() if key in compact_fields.get(node["nodeType"], set())}
                for node in nodes
            ]
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_policy": "live_recruitment_current_plus_simulated_monthly_history",
            "simulation_notice": "历史月份为基于当前真实招聘结构生成的确定性展示推演，不进入正式证据图谱。",
            "layout": "career_galaxy_wormhole",
            "filters": {"domain": domain, "source_platform": source_platform},
            "stats": {
                "source_jobs": len(source_jobs),
                "rendered_nodes": len(nodes),
                "rendered_edges": len(links),
                "periods": len(layers),
                "sources": dict(Counter(job.source_platform for job in ranked)),
                "companies": len({job.company for job in ranked if job.company}),
                "domains": dict(Counter(job.domain for job in ranked)),
                "job_nodes": len(job_nodes), "family_nodes": len(family_nodes), "skill_nodes": len(skill_nodes),
                "auxiliary_signal_nodes": len(signal_nodes),
                "fusion_candidates": sum(link["type"] == "possible_fusion" for link in links),
                "exit_risks": sum(node.get("evolutionState") in {"declining", "exited"} for node in family_nodes),
                "simulated_months": sum(layer["isSimulated"] for layer in layers),
                "job_skill_edges": sum(link["type"] == "job_requires_skill" for link in links),
                "job_similarity_edges": sum(
                    link["type"] == "job_similarity" and link.get("relationScope") == "job_instance"
                    for link in links
                ),
                "shared_skill_edges": sum(link["type"] == "shared_skill" for link in links),
            },
            "layers": layers,
            "nodes": nodes,
            "links": links,
        }

    @staticmethod
    def _career_period(job: CleanedDataItem) -> str:
        moment = job.published_at or job.collected_at
        return moment.astimezone(UTC).strftime("%Y-%m")

    @staticmethod
    def _monthly_axis(latest_period: str, *, months: int) -> list[str]:
        latest = datetime.strptime(latest_period, "%Y-%m")
        latest_index = latest.year * 12 + latest.month - 1
        result = []
        for offset in range(months - 1, -1, -1):
            month_index = latest_index - offset
            result.append(f"{month_index // 12:04d}-{month_index % 12 + 1:02d}")
        return result

    @staticmethod
    def _period_label(period: str) -> str:
        moment = datetime.strptime(period, "%Y-%m")
        return moment.strftime("%Y.%m")

    @staticmethod
    def _is_graph_skill(skill: str) -> bool:
        return is_valid_skill(skill)

    @staticmethod
    def _career_ring(job: CleanedDataItem) -> str:
        minimum = job.experience_min_years
        title = job.title.casefold()
        if minimum is not None and minimum >= 3:
            return "inner"
        if re.search(r"专家|架构|资深|高级|leader|负责人", title):
            return "inner"
        if minimum is not None and minimum >= 1:
            return "middle"
        if re.search(r"中级", title):
            return "middle"
        return "outer"

    @staticmethod
    def _salary_label(job: CleanedDataItem) -> str:
        if job.salary_min_k is None and job.salary_max_k is None:
            return "薪资面议"
        low = job.salary_min_k or 0
        high = job.salary_max_k or low
        suffix = f"·{job.salary_months}薪" if job.salary_months != 12 else ""
        return f"{low}-{high}K{suffix}"

    @staticmethod
    def _experience_label(job: CleanedDataItem) -> str:
        low, high = job.experience_min_years, job.experience_max_years
        if low is None and high is None:
            return "经验不限"
        if high is None:
            return f"{low or 0}年以上"
        return f"{low or 0}-{high}年"

    def _family(self, job: CleanedDataItem) -> str:
        title = re.sub(r"[（(].*?[）)]", "", job.title).strip()
        lowered = title.casefold()
        for pattern, label in FAMILY_RULES.get(job.domain, ()):
            if re.search(pattern, lowered, re.IGNORECASE):
                return label
        cleaned = re.sub(r"(高级|资深|初级|中级|专家|实习|应届|急聘|双休|五险一金|[0-9]+k)", "", title, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_/·")
        return cleaned[:30] or f"{job.domain}工程师"

    def _skill_category(self, skill: str) -> str:
        if skill in SKILL_CATALOG:
            return SKILL_CATALOG[skill][0]
        lowered = skill.casefold()
        rules = (
            ("ai", r"llm|rag|agent|模型|算法|pytorch|tensorflow|向量|lang"),
            ("big_data", r"flink|spark|hadoop|hive|数仓|湖仓"),
            ("iot", r"mqtt|嵌入式|rtos|单片机|固件|边缘"),
            ("cloud_native", r"docker|kubernetes|k8s|云原生|容器"),
            ("database", r"sql|mysql|redis|数据库|clickhouse|mongodb"),
            ("testing", r"测试|pytest|selenium|质量"),
            ("language", r"python|java|go|c\+\+|javascript|typescript"),
        )
        return next((category for category, pattern in rules if re.search(pattern, lowered)), "engineering")

    def _node(self, node_id: str, label: str, node_type: str, parent: str | None, jobs: list[CleanedDataItem], description: str) -> dict[str, Any]:
        moments = [job.published_at or job.collected_at for job in jobs]
        return {
            "id": node_id, "label": label, "type": node_type, "parent": parent, "description": description,
            "evidenceCount": len(jobs), "growth": self._growth(jobs),
            "confidence": round(sum(job.quality_score for job in jobs) / max(1, len(jobs)) / 100, 2),
            "sources": dict(Counter(job.source_platform for job in jobs)),
            "companies": len({job.company for job in jobs if job.company}),
            "cities": [item for item, _ in Counter(job.city for job in jobs if job.city).most_common(6)],
            "evidenceIds": [job.source_id for job in jobs[:100]],
            "firstSeenAt": min(moments).isoformat() if moments else None,
            "lastSeenAt": max(moments).isoformat() if moments else None,
            "evidenceStatus": "verified_recruitment" if jobs else "insufficient",
            "reviewStatus": "published" if jobs else "blocked",
        }

    @staticmethod
    def _edge(source: str, target: str, relation: str, weight: int) -> dict[str, Any]:
        return {"id": f"{source}->{target}", "source": source, "target": target, "relation": relation, "weight": weight}

    @staticmethod
    def _summary(responsibilities: Counter[str], family_name: str) -> str:
        top = [item.rstrip("。；") for item, _ in responsibilities.most_common(2)]
        return "；".join(top)[:220] if top else f"从真实招聘数据归并形成的{family_name}岗位族。"

    @staticmethod
    def _growth(jobs: list[CleanedDataItem]) -> float:
        now = datetime.now(UTC)
        recent = previous = 0
        for job in jobs:
            moment = job.published_at or job.collected_at
            if moment >= now - timedelta(days=30):
                recent += 1
            elif moment >= now - timedelta(days=60):
                previous += 1
        return round((recent - previous) / max(1, previous) * 100, 1)

    @staticmethod
    def _evidence_rank(job: CleanedDataItem) -> tuple[float, datetime]:
        return job.quality_score, job.published_at or job.collected_at

    @staticmethod
    def _snippet(job: CleanedDataItem, skill: str) -> str:
        for segment in job.evidence_segments:
            text = str(segment.get("text") or segment.get("snippet") or "")
            if skill.casefold() in text.casefold():
                return text[:420]
        content = job.raw_content or job.content
        index = content.casefold().find(skill.casefold())
        start = max(0, index - 90) if index >= 0 else 0
        return content[start:start + 420].strip()

    @staticmethod
    def _slug(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value).strip("-").casefold()
        return cleaned[:90]
