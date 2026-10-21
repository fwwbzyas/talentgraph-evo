from __future__ import annotations


def evidence_confidence(source_count: int, quality_score: float) -> float:
    diversity = min(source_count / 5, 1.0)
    quality = min(max(quality_score, 0), 100) / 100
    return round(0.55 * quality + 0.45 * diversity, 2)


def snippet_for_skill(content: str, skill: str) -> str:
    if skill in content:
        idx = content.index(skill)
        return content[max(0, idx - 24) : idx + len(skill) + 32]
    return content[:80]
