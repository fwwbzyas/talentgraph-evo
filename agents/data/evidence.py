from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from itertools import combinations
import re
from typing import Any, Iterable

from agents.data.normalization import clean_text, extract_skills
from agents.data.source_policy import RECRUITMENT_SOURCE_SET
from contracts import CleanedDataItem, CommunitySignal


class EvidenceIntelligenceService:
    """Cross-source evidence analysis. Community sources never become job facts."""

    def copy_clusters(self, jobs: Iterable[CleanedDataItem]) -> list[dict[str, Any]]:
        candidates = list(jobs)
        by_id = {job.source_id: job for job in candidates}
        parent = {job.source_id: job.source_id for job in candidates}

        def find(source_id: str) -> str:
            while parent[source_id] != source_id:
                parent[source_id] = parent[parent[source_id]]
                source_id = parent[source_id]
            return source_id

        def union(left: str, right: str) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        exact: dict[str, list[str]] = defaultdict(list)
        fingerprint_index: dict[str, list[str]] = defaultdict(list)
        fingerprints: dict[str, set[str]] = {}
        for job in candidates:
            template = self._template(job.raw_content or job.content)
            if len(template) < 80:
                continue
            exact[sha256(template.encode("utf-8")).hexdigest()[:20]].append(job.source_id)
            fingerprints[job.source_id] = self._segment_fingerprints(job.raw_content or job.content)
            for fingerprint in fingerprints[job.source_id]:
                fingerprint_index[fingerprint].append(job.source_id)

        for members in exact.values():
            for source_id in members[1:]:
                union(members[0], source_id)

        pair_support: Counter[tuple[str, str]] = Counter()
        for members in fingerprint_index.values():
            unique = sorted(set(members))
            # Boilerplate segments can occur in thousands of JDs. Exact full-
            # text copies are handled above; keep fuzzy pair expansion bounded.
            if 1 < len(unique) <= 24:
                pair_support.update(combinations(unique, 2))
        for (left, right), shared in pair_support.items():
            union_size = len(fingerprints.get(left, set()) | fingerprints.get(right, set()))
            similarity = shared / max(1, union_size)
            if shared >= 2 and similarity >= 0.28:
                union(left, right)

        grouped: dict[str, list[CleanedDataItem]] = defaultdict(list)
        for source_id, job in by_id.items():
            if source_id in fingerprints:
                grouped[find(source_id)].append(job)
        clusters = []
        for root, members in grouped.items():
            source_ids = sorted({job.source_id for job in members})
            if len(source_ids) < 2:
                continue
            companies = sorted({job.company for job in members if job.company})
            platforms = Counter(job.source_platform or "unknown" for job in members)
            score_ids = source_ids
            if len(score_ids) > 120:
                stride = max(1, len(score_ids) // 120)
                score_ids = score_ids[::stride][:120]
            shared_scores = [
                len(fingerprints[left] & fingerprints[right])
                / max(1, len(fingerprints[left] | fingerprints[right]))
                for left, right in combinations(score_ids, 2)
                if left in fingerprints and right in fingerprints
            ]
            clusters.append({
                "cluster_id": f"copy_{sha256(root.encode('utf-8')).hexdigest()[:20]}",
                "record_count": len(source_ids),
                "independent_company_count": len(companies),
                "source_ids": source_ids,
                "companies": companies[:20],
                "platforms": dict(platforms),
                "evidence_weight": round(min(1.0, max(1, len(companies)) / len(source_ids)), 3),
                "similarity": round(max(shared_scores or [1.0]), 3),
                "reason": "正文分段指纹高度一致，图谱统计按独立企业折算证据权重",
                "sample": (members[0].raw_content or members[0].content)[:360],
            })
        return sorted(clusters, key=lambda item: item["record_count"], reverse=True)

    def technology_trends(
        self,
        jobs: Iterable[CleanedDataItem],
        signals: Iterable[CommunitySignal],
    ) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        recruitment: dict[str, list[CleanedDataItem]] = defaultdict(list)
        auxiliary: dict[str, list[CommunitySignal]] = defaultdict(list)
        for job in jobs:
            if getattr(job, "source_platform", None) not in RECRUITMENT_SOURCE_SET:
                continue
            for skill in set(getattr(job, "skill_tags", []) or []):
                recruitment[skill].append(job)
        for signal in signals:
            skills = extract_skills(
                f"{signal.title} {signal.content} {' '.join(signal.tags)}",
                signal.tags,
            )
            for skill in set(skills):
                auxiliary[skill].append(signal)

        output = []
        for technology in sorted(set(recruitment) | set(auxiliary)):
            job_items = recruitment.get(technology, [])
            signal_items = auxiliary.get(technology, [])
            if not signal_items:
                continue
            recent = sum(
                _moment(item) >= now - timedelta(days=30)
                for item in signal_items
            )
            previous = sum(
                now - timedelta(days=60) <= _moment(item) < now - timedelta(days=30)
                for item in signal_items
            )
            growth = round((recent - previous) / max(1, previous), 3)
            companies = {getattr(item, "company", None) for item in job_items}
            companies.discard(None)
            platforms = Counter(item.source_platform for item in signal_items)
            can_publish = bool(job_items)
            output.append({
                "technology": technology,
                "domain": _dominant_domain(job_items, signal_items),
                "auxiliary_evidence_count": len(signal_items),
                "recruitment_evidence_count": len(job_items),
                "company_count": len(companies),
                "auxiliary_platforms": dict(platforms),
                "community_growth_rate": growth,
                "status": "招聘验证" if len(job_items) >= 3 else "前沿观察" if not job_items else "交叉验证中",
                "evidence_role": "auxiliary_plus_recruitment" if can_publish else "auxiliary_only",
                "can_publish_ability": can_publish,
                "search_term_recommended": recent > 0 and len(job_items) < 3,
                "evidence": [
                    {
                        "signal_id": item.signal_id,
                        "platform": item.source_platform,
                        "url": item.source_url,
                        "title": item.title,
                    }
                    for item in sorted(signal_items, key=_moment, reverse=True)[:6]
                ],
            })
        return sorted(
            output,
            key=lambda item: (
                item["status"] == "招聘验证",
                item["auxiliary_evidence_count"],
                item["community_growth_rate"],
            ),
            reverse=True,
        )

    def job_cross_source_assessment(
        self,
        job: CleanedDataItem,
        jobs: Iterable[CleanedDataItem],
    ) -> dict[str, Any]:
        peers = [
            item for item in jobs
            if item.source_id != job.source_id
            and item.source_platform != job.source_platform
            and item.domain == job.domain
            and _skill_similarity(item.skill_tags, job.skill_tags) >= 0.45
        ]
        return {
            "verified_platforms": sorted({job.source_platform, *(item.source_platform for item in peers)}),
            "independent_companies": len({item.company for item in [job, *peers] if item.company}),
            "peer_source_ids": [item.source_id for item in peers[:12]],
            "cross_source_confidence": round(min(1.0, 0.55 + len(peers) * 0.08), 3),
        }

    @staticmethod
    def _template(content: str) -> str:
        value = clean_text(content).casefold()
        value = re.sub(r"https?://\S+|[\w.+-]+@[\w.-]+", " ", value)
        value = re.sub(r"\d+(?:\.\d+)?", "#", value)
        value = re.sub(r"\s+", "", value)
        return value

    @classmethod
    def _segment_fingerprints(cls, content: str) -> set[str]:
        value = clean_text(content).casefold()
        segments = [
            cls._template(segment)
            for segment in re.split(r"[\n。；;！？!?]+", value)
        ]
        segments = [segment for segment in segments if len(segment) >= 28]
        if len(segments) < 2:
            template = cls._template(value)
            segments.extend(
                template[index:index + 96]
                for index in range(0, max(1, len(template) - 48), 48)
                if len(template[index:index + 96]) >= 48
            )
        return {
            sha256(segment.encode("utf-8")).hexdigest()[:16]
            for segment in segments[:36]
        }


def _moment(item: Any) -> datetime:
    value = getattr(item, "published_at", None) or getattr(item, "collected_at", None) or datetime.now(UTC)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _dominant_domain(jobs: list[Any], signals: list[Any]) -> str:
    values = [getattr(item, "domain", None) for item in [*jobs, *signals]]
    values = [value for value in values if value]
    return Counter(values).most_common(1)[0][0] if values else "人工智能"


def _skill_similarity(left: list[str], right: list[str]) -> float:
    left_set, right_set = set(left), set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0
