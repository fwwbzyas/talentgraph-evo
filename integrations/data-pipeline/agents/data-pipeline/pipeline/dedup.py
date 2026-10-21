"""
数据去重模块 — 基于 datasketch 库的 MinHash LSH 去重

对应功能技术说明 工程4: 多源数据清洗流水线
  - MinHash + LSH 近似去重（datasketch 工业级标准方案）
  - 招聘 JD 场景：同一岗位重复发布、跨站采集的去重

核心原理:
  MinHash 将文本指纹压缩为固定长度的签名，LSH 对签名做分桶索引。
  新文本只需在相关桶内查找候选，无需 O(n²) 全量比对。

依赖: pip install datasketch
"""

import re

from datasketch import MinHash, MinHashLSH

from contracts.data_schema import RawJobDescription


def tokenize_jd(text: str, ngram: int = 3) -> list[str]:
    """
    JD 文本分词：字符 n-gram + 空格分词。

    中文字符间没有天然分隔，字符级 n-gram 对中文去重最稳定。
    同时保留英文单词分词作为补充特征。
    """
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    tokens = []
    for i in range(len(text) - ngram + 1):
        tokens.append(text[i:i + ngram])
    tokens.extend(text.split())
    return tokens


class DedupAgent:
    """
    MinHash LSH 去重器。

    用法:
        agent = DedupAgent(threshold=0.85)
        unique = agent.deduplicate(raw_jds)
    """

    def __init__(self, threshold: float = 0.85, num_perm: int = 128):
        self.threshold = threshold
        self.num_perm = num_perm

    def deduplicate(self, items: list[RawJobDescription]) -> list[RawJobDescription]:
        """
        批量去重，保留原始顺序，移除后续重复项。

        流程:
          对每条 JD → 分词 → 计算 MinHash 签名 → LSH 查询候选 →
          精确 Jaccard 比对 → 重复则跳过，否则加入结果。
        """
        if not items:
            return []

        # LSH 查询边界略低于目标阈值（概率方法补偿）
        lsh = MinHashLSH(threshold=max(0, self.threshold - 0.05),
                         num_perm=self.num_perm)
        # 缓存签名对象，用于 LSH 查询命中的精确比对
        sig_cache: dict[str, MinHash] = {}

        unique: list[RawJobDescription] = []
        dup_count = 0

        for idx, item in enumerate(items):
            tokens = tokenize_jd(item.description)
            m = MinHash(num_perm=self.num_perm)
            for t in tokens:
                m.update(t.encode("utf-8"))

            # 在 LSH 索引中查找相似候选
            candidates = lsh.query(m)
            is_dup = False

            for cand_key in candidates:
                cand_m = sig_cache.get(cand_key)
                if cand_m is not None and m.jaccard(cand_m) >= self.threshold:
                    is_dup = True
                    break

            if is_dup:
                dup_count += 1
                continue

            # 加入索引并保留
            key = str(idx)
            lsh.insert(key, m)
            sig_cache[key] = m
            unique.append(item)

        if dup_count:
            print(f"  [去重] {len(items)} → {len(unique)} (移除 {dup_count} 条)")
        return unique
