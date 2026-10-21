# 100条真实JD时间渐进性测试套件

本目录用于验证项目能否捕捉岗位在12个月内的渐进变化。它从仓库数据库快照中确定性抽取100条去重后的真实计算机类JD作为基线，生成2025-09至2026-08共12个月的隔离测试观测。

## 安全边界

- 不修改、删除或回写任何现有真实岗位。
- 生成数据全部带有 `synthetic_temporal_test=true` 和 `production_write_forbidden=true`。
- 测试只写入临时SQLite数据库。
- 模拟趋势不得用于真实市场结论，也不得冒充正式人工金标结果。
- 正式赛题JD解析准确率仍需使用独立、双人标注并仲裁冻结的100条以上真实JD金标集。

## 目录

```text
temporal_progression_test/
├─ data/
│  ├─ baseline_100.jsonl
│  ├─ temporal_raw_12_months.jsonl.gz
│  ├─ ground_truth.jsonl
│  └─ manifest.json
├─ reports/
│  ├─ latest.json
│  └─ latest.md
├─ tests/
│  └─ test_temporal_progression.py
├─ generate_dataset.py
├─ run_validation.py
├─ TEST_PROCESS.md
└─ README.md
```

## 快速执行

在仓库根目录运行：

```powershell
python .\temporal_progression_test\run_validation.py
python -m pytest -q .\temporal_progression_test\tests\test_temporal_progression.py -o addopts=
```

如需从当前仓库快照重新生成：

```powershell
python .\temporal_progression_test\generate_dataset.py `
  --source .\data\talentgraph-db.zip `
  --output .\temporal_progression_test\data
```

固定种子为 `20260905`。压缩JSONL使用固定gzip时间戳，因此同一输入数据库与同一代码应得到相同的数据文件哈希。

## 数据设计

- 四领域各25条：人工智能、大数据、智能系统、物联网。
- 仅从 `zhaopin`、`boss`、`51job`、`liepin` 的真实来源记录抽样。
- 排除已有模拟来源、模拟标记、下线岗位、短文本、技能过少、缺失来源证据和重复记录。
- 公司、岗位ID、来源URL、手机号、邮箱和正文链接均脱敏或伪名化。
- 场景包括稳定对照、技能渐进增长、技能迁移、薪资渐进、经验门槛变化、上下线/恢复和多字段复合变化。

详细步骤与验收规则见 [TEST_PROCESS.md](TEST_PROCESS.md)。
