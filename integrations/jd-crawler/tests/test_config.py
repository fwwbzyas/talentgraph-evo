"""矩阵配置:默认 12 城市 × 24 关键词,JSON 覆盖加载。"""

import json

import pytest

from jd_crawler.config import (
    CITIES, KEYWORD_GROUPS, MatrixConfig, flatten_keywords, keyword_category,
    load_matrix_config,
)


def test_default_matrix_is_12x24x2():
    cfg = MatrixConfig()
    assert len(cfg.cities) == 12
    assert len(cfg.keywords) == 24
    assert cfg.sites == ["51job", "liepin"]
    assert cfg.combo_count() == 2 * 12 * 24
    # 指定城市全部在列
    for c in ["北京", "上海", "广州", "深圳", "杭州", "南京",
              "苏州", "成都", "武汉", "西安", "合肥", "长沙"]:
        assert c in CITIES


def test_keyword_groups_cover_24_and_categories():
    kws = flatten_keywords()
    assert len(kws) == 24
    assert keyword_category("算法工程师") == "人工智能"
    assert keyword_category("Flink 工程师") == "大数据"
    assert keyword_category("固件工程师") == "物联网"
    assert keyword_category("不存在的词") == ""
    # 每组数量符合需求 8/7/4/5
    sizes = sorted(len(v) for v in KEYWORD_GROUPS.values())
    assert sizes == [4, 5, 7, 8]


def test_load_matrix_config_override(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({
        "cities": ["北京", "上海"],
        "keyword_groups": {"人工智能": ["算法工程师", "RAG 工程师"]},
        "keywords": ["额外岗位"],
        "sites": ["liepin"],
        "pages": 3,
    }, ensure_ascii=False), encoding="utf-8")
    cfg = load_matrix_config(p)
    assert cfg.cities == ["北京", "上海"]
    assert cfg.keywords == ["算法工程师", "RAG 工程师", "额外岗位"]
    assert cfg.sites == ["liepin"]
    assert cfg.pages == 3
    assert cfg.combo_count() == 1 * 2 * 3


def test_load_matrix_config_rejects_unknown_site(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"sites": ["boss"]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_matrix_config(p)
