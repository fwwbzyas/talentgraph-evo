"""
数据质量评分模块

对应功能技术说明 工程4: 多源数据清洗流水线
  - 质量评分 0-100: 加权综合 = w1·完整度 + w2·原创度 + w3·新鲜度 + w4·信息量

评分维度:
  1. 完整度 (0-30): 必填字段是否齐全
  2. 原创度 (0-30): 与模板 JD 的差异度
  3. 新鲜度 (0-20): 基于发布时间的衰减权重
  4. 信息量 (0-20): 描述文本的信息密度
"""

import re
import math
from datetime import datetime, timedelta
from typing import Optional

from contracts.data_schema import (
    RawJobDescription,
    CleanedJobDescription,
    SkillItem,
    QualityLevel,
    CleaningTrace,
    Source,
)


class QualityScorer:
    """
    JD 质量评分器

    输入: RawJobDescription
    输出: 质量评分 0-100 + 质量等级
    """

    def __init__(
        self,
        weight_completeness: float = 0.30,
        weight_originality: float = 0.30,
        weight_freshness: float = 0.20,
        weight_informativeness: float = 0.20,
    ):
        self.w_completeness = weight_completeness
        self.w_originality = weight_originality
        self.w_freshness = weight_freshness
        self.w_info = weight_informativeness

        # 常见 JD 模板短语（出现这些说明模板化程度高）
        self._template_phrases = [
            "我们是一家", "公司致力于", "扁平化管理", "零食下午茶",
            "五险一金", "定期团建", "氛围轻松", "弹性工作",
            "薪资面议", "待遇从优", "工资面谈",
        ]

        # AI 生成文本的典型特征词
        self._ai_indicator_words = [
            "在当今", "随着", "综上所述", "值得注意的是",
            "不可或缺", "至关重要", "此外", "并且",
        ]

    # ── 维度1: 完整度 ──────────────────────

    def _score_completeness(self, jd: RawJobDescription) -> float:
        """
        评估 JD 字段完整度。

        关键字段: title, company, description(长度), salary, location,
                  experience, education, publish_date
        """
        score = 0.0

        # title 非空
        if jd.title and len(jd.title) >= 2:
            score += 5
        # company 非空
        if jd.company and len(jd.company) >= 2:
            score += 4
        # description 长度足够（≥100 字）
        if len(jd.description) >= 200:
            score += 10
        elif len(jd.description) >= 100:
            score += 6
        elif len(jd.description) >= 50:
            score += 3
        # salary
        if jd.salary_range:
            score += 4
        # location
        if jd.location:
            score += 3
        # experience
        if jd.experience:
            score += 2
        # education
        if jd.education:
            score += 2

        return score  # 满分 30

    # ── 维度2: 原创度 ──────────────────────

    def _score_originality(self, jd: RawJobDescription) -> float:
        """
        检测 JD 是否高度模板化（抄袭检测的简化版）。

        统计模板化短语命中率，命中越多说明原创度越低。
        """
        desc = jd.description
        desc_lower = desc.lower()
        hit_count = sum(1 for phrase in self._template_phrases
                       if phrase in desc_lower)

        # 模板短语密度 = 命中数 / 文本总长(每100字)
        text_len_in_hundreds = max(len(desc) / 100.0, 1.0)
        density = hit_count / text_len_in_hundreds

        # 密度 0 → 满分 30; 密度 2+ → 接近 0
        score = max(0, 30 - density * 15)
        return round(score, 1)

    # ── 维度3: 新鲜度 ──────────────────────

    def _score_freshness(self, jd: RawJobDescription) -> float:
        """
        基于发布时间计算新鲜度权重（指数衰减）。

        计算公式: score = 20 × e^(-λ × days_since_publish)
        其中 λ = ln(2) / half_life_days

        默认半衰期 30 天（即 30 天前的 JD 新鲜度折半）。
        """
        half_life = 30  # 天
        decay_rate = math.log(2) / half_life

        # 尝试解析发布日期
        days_ago = self._parse_days_ago(jd.publish_date)
        if days_ago is None:
            return 10.0  # 无法解析时给中位分

        score = 20 * math.exp(-decay_rate * days_ago)
        return round(score, 1)

    @staticmethod
    def _parse_days_ago(date_str: Optional[str]) -> Optional[int]:
        """解析中文日期字符串为距今多少天"""
        if not date_str:
            return None
        now = datetime.now()
        patterns = [
            (r"(\d+)天前", lambda m: int(m.group(1))),
            (r"(\d+)小时前", lambda m: 0),
            (r"(\d+)分钟前", lambda m: 0),
            (r"昨天", lambda m: 1),
            (r"前天", lambda m: 2),
            (r"(\d{4})-(\d{2})-(\d{2})", lambda m: (now - datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)))).days),
        ]
        for pattern, fn in patterns:
            m = re.search(pattern, date_str)
            if m:
                return fn(m)
        return None

    # ── 维度4: 信息量 ──────────────────────

    def _score_informativeness(self, jd: RawJobDescription) -> float:
        """
        评估 JD 描述的信息密度。

        指标:
          - 文本长度
          - 技能关键词密度
          - 结构化程度（是否有列表/编号）
        """
        desc = jd.description
        score = 0.0

        # 文本长度
        text_len = len(desc)
        if text_len >= 500:
            score += 8
        elif text_len >= 200:
            score += 5
        elif text_len >= 100:
            score += 3

        # 技能关键词密度（技术栈词汇）
        tech_keywords = [
            "python", "java", "javascript", "react", "vue", "spring",
            "docker", "kubernetes", "mysql", "redis", "mongodb",
            "机器学习", "深度学习", "nlp", "cv", "大数据", "hadoop",
            "spark", "flink", "tensorflow", "pytorch", "linux",
            "git", "ci/cd", "微服务", "分布式", "高并发",
        ]
        hit_tech = sum(1 for kw in tech_keywords if kw in desc.lower())
        if hit_tech >= 10:
            score += 6
        elif hit_tech >= 5:
            score += 4
        elif hit_tech >= 2:
            score += 2

        # 列表/编号（结构化程度）
        has_list = bool(re.search(r"[\d一二三四五六七八九十][\.、．)]", desc))
        has_bullet = bool(re.search(r"[•·\-●◆▶▸▪✓✅⭐]", desc))
        if has_list or has_bullet:
            score += 4
        if has_list and has_bullet:
            score += 2

        return score  # 满分 20

    # ── AI 生成检测 ──────────────────────

    def _detect_ai_generated(self, text: str) -> float:
        """
        AI 生成内容检测（统计特征方法）。

        原理:
          - AI 生成文本倾向使用更多连接词和"教科书式"表达
          - 句长分布更均匀（人类写作句长方差更大）
          - Perplexity burst: AI 文本的困惑度更平滑

        Returns:
            AI 生成概率 [0, 1]
        """
        score = 0.0

        # 1. AI 特征词密度
        text_lower = text.lower()
        ai_word_hits = sum(1 for w in self._ai_indicator_words if w in text_lower)
        text_len_hundreds = max(len(text) / 100.0, 1.0)
        ai_word_density = ai_word_hits / text_len_hundreds
        score += min(ai_word_density * 0.15, 0.4)

        # 2. 句长方差（以句号/换行分割）
        sentences = re.split(r"[。！？\n]+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
        if len(sentences) >= 3:
            lengths = [len(s) for s in sentences]
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            cv = math.sqrt(variance) / max(avg_len, 1)  # 变异系数
            # CV 在 0.2-0.4 之间可疑（AI 文本较均匀）
            # CV > 0.8 更可能是人类写的
            if cv < 0.4:
                score += 0.3
            elif cv < 0.6:
                score += 0.1

        # 3. 特殊字符比例（过低可能为清洗后的 AI 文本）
        special_chars = len(re.findall(r"[^\w\s一-鿿]", text))
        special_ratio = special_chars / max(len(text), 1)
        if special_ratio < 0.01:
            score += 0.1

        return min(score, 1.0)

    # ── 综合评分 ─────────────────────────

    def score(self, jd: RawJobDescription) -> CleanedJobDescription:
        """
        对一条原始 JD 进行综合质量评分，返回清洗后的数据结构。
        """
        # 计算各维度
        completeness = self._score_completeness(jd)
        originality = self._score_originality(jd)
        freshness_weight = self._score_freshness(jd) / 20.0  # 归一化到 [0,1]
        informativeness = self._score_informativeness(jd)

        quality_score = round(
            completeness + originality + informativeness +
            (freshness_weight * 20.0 * self.w_freshness / 0.20),  # scale back
            1
        )
        quality_score = min(max(quality_score, 0), 100)

        # 质量等级
        if quality_score >= 80:
            level = QualityLevel.HIGH
        elif quality_score >= 50:
            level = QualityLevel.MEDIUM
        else:
            level = QualityLevel.LOW

        # AI 生成检测
        ai_score = self._detect_ai_generated(jd.description)

        # 清洗追溯
        trace = CleaningTrace(
            dedup_passed=True,
            plagiarism_score=round(1 - originality / 30.0, 2),
            ai_generated_score=round(ai_score, 2),
            freshness_weight=round(freshness_weight, 2),
        )

        raw_id = (
            jd.source_url
            if hasattr(jd, "source_url") and jd.source_url
            else str(hash(jd.description))
        )

        return CleanedJobDescription(
            raw_id=raw_id,
            source=jd.source,
            title=jd.title,
            company=jd.company,
            description_clean=jd.description,
            quality_score=quality_score,
            quality_level=level,
            freshness_weight=freshness_weight,
            cleaning_trace=trace,
        )

    def score_batch(self, jds: list[RawJobDescription]) -> list[CleanedJobDescription]:
        """批量评分"""
        return [self.score(jd) for jd in jds]
