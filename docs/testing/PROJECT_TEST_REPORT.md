# 讯飞智聘项目综合测试报告

> 本文记录历史测试或开发结果；本机路径已统一为 `<project-root>`（仓库根目录），不代表在当前设备重新执行。历史运行产物未随源码发布。

## 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 讯飞智聘项目综合测试报告 |
| 适用项目 | 讯飞智聘多源异构数据驱动岗位和能力图谱构建与动态演化分析系统 |
| 报告类型 | 软件工程综合测试报告 |
| 报告版本 | v1.0 |
| 报告日期 | 2026-08-30 |
| 测试工作区 | <project-root> |
| 编写/整理 | Codex |
| 评测状态 | completed |

> 本报告使用项目级评测产物 `summary.json` 与 `methodology.json` 的原始结果；银标和合成 gold 的结论不会被表述为独立真实人工金标结论。

## 结论摘要

项目级评测状态为 `completed`。控制合成 JD 的 Macro-F1 为 `0.9951`；100 份高拟真合成简历 PDF 的处理成功率为 `1.0`、Macro-F1 为 `0.6324`；真实 DB 岗位银标重复一致性为 `1.0`；500 组规则银标人岗匹配的 Top-1、Top-3 和 MRR 分别为 `0.3`、`0.93` 和 `0.5542`。这些数字对应不同数据层，不能合并成一个“真实准确率”。

完整 pytest 回归结果：命令 `python -m pytest -q`，`167 passed`，`1` 条 Starlette deprecation warning，总覆盖率 `74%`，耗时 `305.46s`。该结果支持工程回归套件通过，但不等同于算法金标验收通过。

## 一、测试目标与范围

### 1.1 测试目标

1. 验证岗位采集、清洗、去重、版本识别、图谱构建、演化分析和新岗位发现等核心流程是否可执行。
2. 验证简历结构化解析、字段抽取、证据关联和人岗匹配的可复现评测流程。
3. 验证服务层、数据存储层、API 契约和前端构建相关工程回归质量。
4. 以冻结输入、稳定 JSON、文件哈希和运行方法记录支撑结果复核。
5. 区分控制合成 gold、真实数据库 silver、一致性 silver 和规则型 match silver，避免混淆证据强度。

### 1.2 测试范围

| 测试域 | 覆盖内容 | 证据类型 |
|---|---|---|
| 工程回归 | 单元、接口、集成及已有自动化测试 | pytest 输出与覆盖率 |
| 数据治理/JD | 控制样本字段解析和质量结果 | controlled synthetic gold |
| 简历解析 | 100 份 PDF 的结构化字段抽取 | high-fidelity synthetic resume gold |
| 真实岗位一致性 | DB 样本两次重跑、字段一致性和稳定哈希 | real-DB silver consistency |
| 人岗匹配 | 100 profiles x 5 enterprise jobs 的排序 | rule-based match silver |
| 图谱/演化 | 岗位、技能、版本、证据和时间变化 | evidence-backed graph case |
| 新岗位/岗位族观察 | AI Agent 岗位目录持久值与重算值 | DB catalog fact |

### 1.3 不在本轮范围

真实生产环境高并发、SLA、灾备、长周期稳定性、生产数据库迁移、未经授权的平台绕过验证，以及由独立双人工专家完成的真实简历/人岗匹配金标验收均不在本轮已完成范围内。

## 二、冻结环境与来源溯源

### 2.1 环境快照

| 项目 | 冻结值 | 来源/备注 |
|---|---|---|
| 工作区 | <project-root> | 本次执行上下文 |
| Git HEAD | 4623e424e5141fe544254b8ec4260192e9dd8efe | methodology manifest |
| Git 分支 | 历史测试分支（未随发布副本提供） | methodology manifest |
| Git 脏状态 | true | tracked_status_entry_count=27；未展开未跟踪文件 |
| 操作系统 | Windows 11 | platform metadata |
| 机器架构 | AMD64 | platform metadata |
| Python | CPython 3.13.11 | platform metadata |
| 数据库 | <project-root>/data/talentgraph.db | read_only=true, bytes=430952448 |
| 数据库 SHA-256 | 104d2e14d5a2735a221c451ec0f747341e645d1d3c85363955a7e821b1c3985f | 冻结输入快照 |
| 评测 runner | <project-root>/scripts/evaluate_project_suite.py | SHA-256 674a02476ad9ba9efd7b7a484015abba084b44dd21fca31f5c5bf1f8aafbc317 |

### 2.2 数据库表计数

| 表 | 计数 |
|---|---|
| job_assets | 9826 |
| job_versions | 13800 |
| job_profiles | 13 |
| enterprise_jobs | 5 |

### 2.3 评测产物与方法学

| 产物 | 路径 | 记录 |
|---|---|---|
| 项目级汇总 | <project-root>/data/evaluation/project_suite/summary.json | schema=project-suite-v1；suite=talentgraph_project_suite；status=completed |
| 方法学 | <project-root>/data/evaluation/project_suite/methodology.json | schema=project-suite-v1；label_source=This file documents the executable local evidence suite. |
| 简历 manifest | <project-root>/data/evaluation/resume_gold_100/manifest.json | dataset=resume_gold_100；record_count=100；SHA-256=6eb01ec8c0fe6d5628125287b2a97a2be2caa4caf14ea2f04751c5ae27650acd |

方法学文件列明的可执行分段如下：

- `controlled_generated_jd`：generate_demo_jds(100) -> DataAgent.run; compare controlled fields.
- `resume_gold_pdf`：Parse all 100 existing manifest PDFs with extract_resume_text and ResumeParsingAgent.parse; score against gold JSON using the existing evaluator scorer.
- `db_jd_silver`：Select sorted non-synthetic persisted DB JDs, run DataAgent twice, report DB field agreement and repeat consistency.
- `match_benchmark`：Build enterprise JobGraph objects, call MatchAgent for 100 gold profiles x 5 jobs, rank by report score; compare against deterministic required/preferred skill plus domain rule-silver labels using top1/top3/MRR.
- `actual_graph_case`：Run JobGraphAgent on the accepted DB sample and preserve the produced graph payload.
- `ai_agent_engineer_db_case`：Read persisted job_profiles row ai-agent and compare with load_job_profiles recomputation when available.

## 三、数据来源与标注层级

| 数据层 | 定义 | 本次用途 | 可支持结论 |
|---|---|---|---|
| 控制合成 gold | `generate_demo_jds(100)` 产生、真值由控制字段给出 | DataAgent 字段解析和质量回归 | 冻结合成分布上的可复现性能 |
| 真实 DB silver consistency | 从只读 SQLite 取样并由 DataAgent 两次重跑 | 字段一致性、重复一致性和稳定哈希 | 当前快照内的一致性；不是现实市场真值准确率 |
| 高拟真 synthetic resume gold | `resume_gold_100` 的虚构匿名简历与 gold JSON | 100 份 PDF 的生产解析与字段评分 | 合成分布和 PDF 格式条件下的抽取性能 |
| 规则型 match silver | gold profile 与 5 个持久化 enterprise jobs 的规则相关集合 | MatchAgent 排序的 Top-k/MRR | 相对于规则参照的一致性；不是专家判断或录用结果 |

### 3.1 各评测段的原始来源

- `controlled_generated_jd`：label_type=`controlled`；label_source=core.sample_data.generate_demo_jds controlled fields + production DataAgent.run
  - 限制：Generated fixtures are controlled synthetic records, not market-distributed human labels.
  - 限制：The generator timestamps are excluded from determinism hashes.
- `resume_gold_pdf`：label_type=`synthetic_gold`；label_source=resume_gold_100 manifest/gold JSON + production extract_resume_text and ResumeParsingAgent.parse on 100 PDFs
  - 限制：Gold profiles are fictional generated resumes and do not represent a human-annotated population.
  - 限制：This run intentionally uses local deterministic parser mode; it does not measure remote LLM or vision quality.
  - 限制：Matching is evaluated separately with gold profile fields, so this section does not measure parser-to-match error propagation.
- `db_jd_silver`：label_type=`silver`；label_source=read-only production DB sample (job_assets/job_versions) re-run through DataAgent; no human gold labels
  - 限制：Silver agreement is a deterministic re-normalization check, not an accuracy score against ground truth.
  - 限制：The sample is sorted by persisted source_id and excludes synthetic DB rows when enough real rows exist.
  - 限制：DB contents can change outside this process; the recorded DB SHA256 identifies this run's input snapshot.
- `match_benchmark`：label_type=`rule_silver`；label_source=100 resume_gold_100 gold profile JSON x 5 persisted enterprise_jobs; relevance is deterministic rule-silver skill/domain overlap
  - 限制：Rule-silver relevance is a reproducible proxy, not human recruiter judgment or hiring outcome.
  - 限制：Gold profile fields bypass resume parsing in this section; parser quality is reported separately.
  - 限制：Five enterprise jobs are a small snapshot and ties are retained as a relevant set.
- `actual_graph_case`：label_type=`evidence_backed`；label_source=production DB JD sample -> DataAgent -> JobGraphAgent
  - 限制：This is one graph case from a bounded DB sample, not a graph-wide quality evaluation.
  - 限制：Graph semantics are evidence-backed by persisted JDs but are not human adjudicated here.
- `ai_agent_engineer_db_case`：label_type=`db_fact`；label_source=persisted production DB job_profiles row for job_key=ai-agent
  - 限制：This section reports a DB catalog fact and does not claim the catalog is a human gold label.
  - 限制：Persisted and recomputed catalog values can differ when the DB has been refreshed; both are shown when available.

高拟真简历数据为虚构匿名角色，不含电话、邮箱、身份证号或真实联系地址。它不是独立双人工真实简历金标。

## 四、抽样、可复现性与泄漏控制

| 项目 | 冻结记录 |
|---|---|
| 控制 JD | sample_count=100；accepted=100；rejected=0 |
| 简历 PDF | requested_count=100；pdf_count=100；gold_count=100；split={'calibration': 20, 'regression': 30, 'blind': 50} |
| DB silver | source_table=job_assets；candidate_count=9826；technical_candidate_count=9726；sample_count=100 |
| 匹配 | gold_profile_count=100；enterprise_job_count=5；pair_count=500；同分相关集合保留 |
| 简历格式/领域 | format={'可复制中文PDF': 100}；domain={'人工智能': 25, '大数据': 25, '智能系统': 25, '物联网': 25}；difficulty={'中': 40, '易': 20, '难': 40} |
| 简历处理模式 | provider_mode={'production_parser_deterministic_local': 100}；processing_success={'True': 100}；usable_parse={'True': 100} |

### 4.1 稳定性哈希与随机性

| 要素 | 记录值 |
|---|---|
| 随机种子 | 评测 runner 未调用 `random.seed`，`methodology.json` 也未记录 seed；不能声称存在一个已冻结的数值 seed |
| 稳定化规则 | runner 的 stable JSON 去除 VOLATILE_KEYS 中的时间戳、运行 ID 等易变字段后排序序列化 |
| 控制 JD 输入稳定 SHA-256 | e3e74956196428a1f7a23c00eb310153f17319a7fdf57291459cb74e5620a269 |
| 控制 JD 规范化稳定 SHA-256 | 9db0ff2f955e6a84ba2c953ad299a041839c7389ed9cebe0810d9a65400532bf |
| DB 首次规范化稳定 SHA-256 | 970daf0b194f4cd18e9b4271af490464cb296eb684805d76778762fa916fb86e |
| DB 重跑规范化稳定 SHA-256 | 970daf0b194f4cd18e9b4271af490464cb296eb684805d76778762fa916fb86e |
| 简历 manifest SHA-256 | 6eb01ec8c0fe6d5628125287b2a97a2be2caa4caf14ea2f04751c5ae27650acd |
| 简历 artifact hashes 聚合 SHA-256 | 85050f956902a09c65a2eab1e4e0742e7c6dd1c4aa62c1e95ed1ee9a3231c632 |
| 评测 runner SHA-256 | 674a02476ad9ba9efd7b7a484015abba084b44dd21fca31f5c5bf1f8aafbc317 |
| 数据库快照 SHA-256 | 104d2e14d5a2735a221c451ec0f747341e645d1d3c85363955a7e821b1c3985f |
| Git tracked status SHA-256 | d4531668f3a89a76325adc0cebd565177ce96afa60bbe9484bd1a64ef2887fdb |

因此本次可声称的是“在相同输入、稳定化规则和禁用远程 LLM 条件下可复核”；不能把未设置/未记录 seed 改写成数值种子保证。

### 4.2 泄漏预防

控制 JD、简历 gold 和规则 match silver 的输入均由评测 runner 直接读取或生成；匹配段直接使用 gold profile 字段，不经过简历解析，因此不把解析误差隐藏在匹配结果中。简历 manifest 保留 `calibration`/`regression`/`blind` 切分（20/30/50），本次 runner 读取全 100 份 PDF 并按分组记录。当前产物没有证明“所有调参过程绝无泄漏”，因此结论只写为冻结运行结果。

## 五、指标定义与统计口径

对一个字段或标签集合，TP 为正确预测项，FP 为多预测项，FN 为漏预测项：

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * Precision * Recall / (Precision + Recall)
Macro-F1  = (1 / m) * sum(F1_j), j = 1...m
Top-k hit rate = 命中相关项的样本数 / 排序样本总数
RR_i = 1 / rank_i（未命中时为 0）
MRR = (1 / n) * sum(RR_i)
rank correlation (Spearman) = corr(rank(predicted), rank(reference))
```

runner 对列表字段使用集合重叠计算 F1，对标量字段使用规范化后的完全相等；字段 Macro-F1 是字段 F1 的算术平均。匹配 MRR 使用每个候选人的最小相关岗位 rank；Top-1/Top-3 使用规则 silver 相关集合。

本次 `summary.json` 没有记录 rank correlation 数值，因此该指标只给出定义，结果记为“未报告”，不自行补算或替换为 Top-k/MRR。

## 六、执行命令与验证入口

### 6.1 工程回归

```bash
python -m pytest -q
```
既有结果：`167 passed`；`1` 条 Starlette deprecation warning；覆盖率 `74%`；耗时 `305.46s`。本报告记录该既有结果，不以本次文档生成过程替代该测试。

### 6.2 项目级评测 runner

```bash
python scripts/evaluate_project_suite.py
python scripts/evaluate_project_suite.py --db data/talentgraph.db --resume-data data/evaluation/resume_gold_100 --output-dir data/evaluation/project_suite --resume-workers 4
```
第一条是 runner 的默认入口；第二条将源代码中的默认参数显式展开，作为复现入口。产物文件中没有保存并行任务实际输入的完整 shell 历史，因此不把第二条虚构为已执行命令。runner 在 `local_only()` 下设置 `TALENTGRAPH_LLM_DISABLED=1`，并写入 `summary.json`、`methodology.json` 与 `metrics.csv`。

## 七、完整评测结果

### 7.1 顶层汇总原值

| summary key | 原始值 |
|---|---|
| status | completed |
| label_type | summary |
| label_source | aggregated from the six executable project-suite sections |
| limitations | Summary metrics inherit each section's labels and limitations; see section details. |
| controlled_jd_macro_f1 | 0.9951 |
| resume_pdf_count | 100 |
| resume_processing_success_rate | 1.0 |
| resume_macro_f1 | 0.6324 |
| db_jd_sample_count | 100 |
| db_jd_silver_consistency | 1.0 |
| match_pair_count | 500 |
| match_top1 | 0.3 |
| match_top3 | 0.93 |
| match_mrr | 0.5542 |
| graph_node_count | 59 |
| graph_edge_count | 73 |
| ai_agent_db_status | completed |

### 7.2 各评测域结果

| 评测域 | 数据层 | 样本/对数 | 成功/接受 | 主要指标 |
|---|---|---|---|---|
| controlled_generated_jd | controlled synthetic gold | sample=100 | accepted=100；rejected=0 | Macro-F1=0.9951；failure_record_count=38 |
| resume_gold_pdf | high-fidelity synthetic resume gold | requested=100；pdf=100；gold=100 | processing_success_rate=1.0；usable_parse_rate=1.0 | Macro-F1=0.6324；timing_mean_ms=746.12；p50_ms=749.88；max_ms=945.62 |
| db_jd_silver | real-DB silver consistency | sample=100 | accepted=100；rejected=0；repeat_accepted=100 | db_field_macro_f1=1.0；deterministic_record_consistency=1.0 |
| match_benchmark | rule-based match silver | profiles=100；jobs=5；pairs=500 | 无处理失败字段；按每人排序结果计分 | Top-1=0.3；Top-3=0.93；MRR=0.5542；primary_rule_silver_top1=0.3 |
| actual_graph_case | evidence-backed case | source=16；skill=14 | status=completed | nodes=59；edges=73 |
| ai_agent_engineer_db_case | DB catalog fact | job_key=ai-agent | status=completed | persisted_job_count=369；recomputed_job_count=397 |

### 7.3 控制合成 JD 字段结果

| 字段 | F1 |
|---|---|
| title | 1.0 |
| domain | 1.0 |
| skill_tags | 0.9708 |
| responsibilities | 1.0 |
| city | 1.0 |
| education | 1.0 |

质量汇总原值：{"accepted": 100, "active_jobs": 94, "avg_quality": 89.0, "cities": 8, "companies": 12, "fetched": 100, "rejected": 0, "total": 100}；失败记录数为 `38`。控制样本 accepted=`100`、rejected=`0`；产物只提供字段 F1，不把其反推为独立 Precision/Recall。

### 7.4 高拟真简历 gold 字段结果

| 字段 | Precision | Recall | F1 | F1<1 样本数 | F1=0 样本数 |
|---|---|---|---|---|---|
| job_intent | 1.0 | 1.0 | 1.0 | 0 | 0 |
| skills | 0.3064 | 0.8358 | 0.4483 | 100 | 0 |
| projects | 0.0 | 0.0 | 0.0 | 100 | 100 |
| experience_years | 1.0 | 1.0 | 1.0 | 0 | 0 |
| education | 0.55 | 0.55 | 0.55 | 45 | 45 |
| certifications | 0.73 | 0.73 | 0.73 | 27 | 27 |
| preferred_locations | 0.945 | 1.0 | 0.9633 | 11 | 0 |
| expected_salary_k | 0.0 | 0.0 | 0.0 | 100 | 100 |
| work_history | 1.0 | 1.0 | 1.0 | 0 | 0 |

| 项目 | 原始值 |
|---|---|
| dataset | resume_gold_100 |
| requested_count/pdf_count/gold_count | 100 / 100 / 100 |
| processing_success_rate | 1.0 |
| usable_parse_rate | 1.0 |
| macro_f1 | 0.6324 |
| provider_stats | {"failures":0,"local_parser_rows":100,"remote_used":0} |
| timing_ms | {"max":945.62,"mean":746.12,"p50":749.88} |
| timing_p95 | 未在 summary.json 记录；不从既有单样本报告外推 |

简历按格式均为可复制中文 PDF 共 100 份；领域为人工智能/大数据/智能系统/物联网各 25 份；难度为易 20、中 40、难 40；切分为 calibration 20、regression 30、blind 50；provider_mode 全部为 `production_parser_deterministic_local`。上述分组由 `summary.json` rows 计数得到，原始分组如下：

| 维度 | 计数 |
|---|---|
| format | {"可复制中文PDF":100} |
| domain | {"人工智能":25,"大数据":25,"智能系统":25,"物联网":25} |
| difficulty | {"中":40,"易":20,"难":40} |
| split | {"blind":50,"calibration":20,"regression":30} |
| provider_mode | {"production_parser_deterministic_local":100} |

### 7.5 真实 DB silver 结果

| 字段 | F1 |
|---|---|
| title | 1.0 |
| domain | 1.0 |
| skill_tags | 1.0 |
| responsibilities | 1.0 |
| city | 1.0 |
| education | 1.0 |
| company | 1.0 |

`db_field_macro_f1=1.0`；`deterministic_record_consistency=1.0`；首次与重复规范化稳定哈希完全相同（分别为 `970daf0b194f4cd18e9b4271af490464cb296eb684805d76778762fa916fb86e` 与 `970daf0b194f4cd18e9b4271af490464cb296eb684805d76778762fa916fb86e`）。这是内部重规范化一致性，不是对真实岗位真值的准确率。

### 7.6 匹配排序结果

| 指标 | 原始值 |
|---|---|
| top1 | 0.3 |
| top3 | 0.93 |
| mrr | 0.5542 |
| primary_rule_silver_top1 | 0.3 |

| reciprocal_rank | 样本数 |
|---|---|
| 0.25 | 7 |
| 0.333333 | 47 |
| 0.5 | 16 |
| 1.0 | 30 |

5 个企业岗位快照：

| job_id | title | domain | required_skills | preferred_skills |
|---|---|---|---|---|
| enterprise_job_70c5b39b4d | 容器化系统实施工程师 | 智能系统 | Docker、Kubernetes、Linux、Python、Git | CI/CD、Nginx |
| enterprise_job_8f642c186a | 前端数据可视化开发助理 | 智能系统 | HTML、CSS、JavaScript、Node.js、Python | React、TypeScript、Git |
| enterprise_job_b9625f4e64 | 数字化运营与数据分析专员 | 大数据 | Python、JavaScript、Node.js、SQL | Docker、Kubernetes |
| enterprise_job_cb84197868 | AI应用实施与知识库工程师 | 人工智能 | Python、Docker、Kubernetes、JavaScript、Node.js | 无 |
| enterprise_job_f36a4a67e1 | 项目内容与数据运营助理 | 大数据 | C、Python | 无 |

本次 `summary.json` 未记录 rank correlation 数值，故结果为“未报告”。

## 八、字段与失败分析

### 8.1 控制 JD

100 条控制样本全部 accepted，rejected=`0`；字段中只有 `skill_tags` 的 F1 为 `0.9708`，其余字段 F1 为 1.0。由于 runner 将任一字段 F1<1 的记录计入 failure，failure_record_count 为 `38`；summary 不保存逐条根因，因此不能进一步断言是某一具体规则导致。

### 8.2 简历字段

100/100 条处理成功且可用。rows 级计数显示：`projects` 与 `expected_salary_k` 各有 100 条 F1=0；`skills` 的 Precision=`0.3064`、Recall=`0.8358`、F1=`0.4483`，表现为过抽与漏抽并存；`education` 有 45 条 F1=0；`certifications` 有 27 条 F1=0；`preferred_locations` 有 11 条 F1<1 但没有 F1=0。job_intent、experience_years 和 work_history 在本次 rows 中均为完美。共有 23 条样本的 macro_f1<0.5，低分样本 ID 首批为 `resume_019, resume_023, resume_025, resume_027, resume_031, resume_033, resume_035, resume_039, resume_041, resume_043, resume_047, resume_049, resume_051, resume_059, resume_063, resume_071, resume_077, resume_079, resume_083, resume_089, resume_091, resume_095, resume_097`。这些是合成 PDF 解析暴露的字段边界问题，不外推为真实简历表现。

### 8.3 DB silver

样本 100 条、重复 accepted 100 条，所有 DB 字段 F1 均为 1.0，稳定哈希相同，故本段没有字段不一致失败。该结果更像确定性重规范化的回归门禁，不是市场标签准确率。

### 8.4 匹配排序

匹配共有 `500` 个 profile-job 对；100 位候选人中 Top-1 命中 `30` 条，Top-3 命中 `93` 条。MRR 的 reciprocal rank 分布为 `{'0.25': 7, '0.333333': 47, '0.5': 16, '1.0': 30}`。

一个可复核的 Top-1 失配样本：

| 项目 | 值 |
|---|---|
| candidate_id | resume_001 |
| 规则相关岗位 | enterprise_job_70c5b39b4d（容器化系统实施工程师） |
| 系统 predicted_top1 | enterprise_job_b9625f4e64（数字化运营与数据分析专员） |
| 规则相关岗位 rank | 3 |
| top1_hit/top3_hit | false / true |
| reciprocal_rank | 0.333333 |

该失配样本说明当前 MatchAgent 分数排序与规则 silver 相关集合可能不同；由于规则 silver 不是人工判断，不能据此直接判定产品推荐错误。

## 九、既有图谱证据案例

本次产物保存的既有生产链案例为岗位 `算法工程师`（target_job_id=`算法工程师`），来源数 `16`，技能数 `14`，图节点 `59`，图边 `73`，领域 `人工智能`，版本 `2026Q3`。

| 项目 | 原始证据 |
|---|---|
| node_types | capability_domain、evidence、job、responsibility、scenario、skill、tool |
| edge_labels | applied_in、enables、implemented_with、owns、preferred、required、requires、supported_by、validated_by |
| 技能 | Python |
| 技能类别/级别/重要性 | language / intermediate / required |
| 技能 confidence | 0.97 |
| 证据 source_id | 51job:153342411 |
| 证据 snippet | 4)熟练掌握C/C++、Python、MATLAB |
| evidence_summary | {"average_confidence":0.76,"evidence_count":28,"provider_status":{"configured":false,"mode":"deterministic_fallback","model":"qwen3.7-plus","provider":"openai-compatible","retries":1,"timeout_seconds":180.0,"trust_env_proxy":false},"source_count":16} |

该案例由 `production DB JD sample -> DataAgent -> JobGraphAgent` 产生；它证明了一个 bounded graph payload 能保留岗位、技能、证据和关系类型，不证明全图准确率。图语义由持久化 JD 支撑，但本次未作人工仲裁。报告不嵌入未被产物指向的截图；已有 `.runlogs/graph-role-timeline-corrected.png` 与 `.runlogs/evolution-ai-agent-version-chain.png` 仅作为可追溯的 UI 运行记录候选，不混入上述数值。

## 十、新兴岗位/岗位族观察案例

产物中可用于案例说明的是 `job_key=ai-agent` 的 DB catalog fact：标题 `AI Agent工程师`，领域 `人工智能`，持久化 job_count=`369`，按当前 DB 重算 job_count=`397`，状态 `completed`。这是岗位族/新兴岗位观察的一个可追溯例子，不是独立人工确认的新职业标签。

| 技能 | 持久化 demand_count | 持久化 demand_rate | 重算 demand_count | 重算 demand_rate |
|---|---|---|---|---|
| Agent | 338 | 91.6 | 366 | 92.2 |
| Python | 278 | 75.3 | 300 | 75.6 |
| RAG | 241 | 65.3 | 264 | 66.5 |
| LangChain | 175 | 47.4 | 192 | 48.4 |
| 工具调用 | 171 | 46.3 | 183 | 46.1 |
| LLM | 139 | 37.7 | 147 | 37.0 |
| Java | 94 | 25.5 | 110 | 27.7 |
| LangGraph | 91 | 24.7 | 98 | 24.7 |
| Prompt Engineering | 86 | 23.3 | 91 | 22.9 |
| 向量数据库 | 86 | 23.3 | 89 | 22.4 |
| Docker | 63 | 17.1 | 65 | 16.4 |
| PyTorch | 60 | 16.3 | 61 | 15.4 |

持久化和重算目录值存在 job_count 与技能计数/排序差异；该差异与产物声明的“DB 可能在进程外刷新”一致，应作为目录新鲜度与复算一致性风险跟踪，不能被解释为新岗位需求增长率。此案例没有记录 EmergingJobCandidate 的 confidence、maturity 或多平台趋势，因此这些指标记为未报告。

## 十一、科学有效性

### 11.1 内部有效性

runner 使用只读数据库、固定输入路径、稳定化 JSON 和 SHA-256；同时把远程 LLM 禁用为 `TALENTGRAPH_LLM_DISABLED=1`，降低外部服务波动。当前 Git 工作树存在 tracked dirtiness（27 条状态条目），且 manifest 明确不展开未跟踪文件，因此结果绑定于本次工作树与哈希，不能假设仅凭 HEAD 可完全重建。

### 11.2 构念有效性

Precision/Recall/F1/Macro-F1 对应字段抽取或集合重叠；Top-k/MRR 对应排序位置；DB silver consistency 对应内部重规范化一致性；rule-based match silver 对应规则参照一致性；图谱案例对应证据结构是否被保存。它们构造不同，不能互相替代。

### 11.3 外部有效性

控制合成 JD 与高拟真简历是受模板、词表、格式和领域比例约束的合成数据；5 个 enterprise jobs 是小快照；DB 样本受当前平台、时间窗口和技术岗位筛选影响。因此真实市场分布、真实简历噪声、招聘方偏好和跨时间泛化均未被充分验证。

### 11.4 结论有效性

结论仅针对产物中的分母、评分器、规则 silver 和运行条件。未报告的 rank correlation 不补算；未设置的 seed 不虚构；remote_used=0 的简历结果不写成远程 LLM 质量；没有人工双标的银标结果不写成真实准确率。

## 十二、局限性与风险

1. 本轮没有独立双人工专家对真实简历和真实人岗匹配进行盲标与仲裁，因此真实场景准确率尚无独立人工 gold 支撑。
2. `resume_gold_100` 是高拟真虚构数据，不能代表真实招聘市场分布，也不能替代授权真实简历集。
3. DB silver 只验证当前数据库快照中的一致性，不提供外部世界真值。
4. rule-based match silver 只验证相对于规则参照的匹配排序，不等同于专家共识、面试结果或录用结果。
5. 本次方法学明确 remote LLM calls disabled；图谱 provider configured=`false`、mode=`deterministic_fallback`。summary/methodology 未记录 HTTP 403；因此本报告不把 403 写成已发生故障，但也不把本次结果解释为远程模型效果。
6. runner 未设置/记录数值随机 seed；哈希和确定性本地模式降低重复差异，但不替代完整环境封存。
7. 前端构建体积、真实高并发、长周期稳定性和生产迁移仍需独立验收。

## 十三、结论与后续验收计划

### 13.1 真实结论

当前工程回归证据为 `167 passed`、1 条 Starlette deprecation warning、覆盖率 `74%`、耗时 `305.46s`。项目级评测已完成，但结果显示不同证据层级：控制合成 JD Macro-F1=`0.9951`；简历 synthetic gold Macro-F1=`0.6324`；DB silver consistency=`1.0`；match rule silver Top-1/Top-3/MRR=`0.3`/`0.93`/`0.5542`。因此可以确认工程评测链可执行且部分合成/一致性门禁通过，但不能据此宣称真实简历、人岗匹配或市场新岗位识别达到 90% 的独立人工验收目标。

### 13.2 后续验收准入条件

| 验收项 | 准入证据 | 通过判定 |
|---|---|---|
| JD/岗位字段 | 冻结 gold、字段级指标、失败样本和哈希 | 按正式阈值逐项满足，并保留独立复跑记录 |
| 简历抽取 | 合成 gold 全量结果、格式分层、失败样本；补真实人工 gold | 合成结果与真实人工集分别达到各自阈值 |
| 人岗匹配 | 独立专家双标、仲裁记录、冻结配对集 | 等级/差距/排序指标达到正式阈值 |
| DB/图谱一致性 | 数据库快照、约束清单、稳定哈希 | 所有关键一致性约束通过 |
| 新岗位观察 | 多平台来源、时间窗口、证据片段和人工复核 | 形成候选信号，不直接视为市场确认 |
| 工程回归 | pytest、覆盖率、warning 和环境记录 | 无失败；处理已知 warning |

### 13.3 建议复测顺序

1. 在不改变冻结测试集的前提下修复简历 `projects`、`expected_salary_k`、`skills` 等低分字段并运行回归。
2. 对真实简历和人岗匹配引入两名以上独立标注者、盲标和仲裁，形成独立 gold。
3. 重新运行全量评测，比较版本差异、分层波动和失败样本迁移；如需 rank correlation，先在 methodology 中冻结 tie 处理和公式。
4. 对远程 LLM 成功、未配置、403、超时和回退分别做可控复测，单列供应商/网络因素。
5. 通过性能、前端构建、长周期和生产迁移验收后，再形成最终发布结论。

## 附录 A：证据清单

| 编号 | 文件/命令 | 用途 | 状态 |
|---|---|---|---|
| A-01 | <project-root>/data/evaluation/project_suite/summary.json | 项目级完整结果 | 已到齐并解析 |
| A-02 | <project-root>/data/evaluation/project_suite/methodology.json | 方法学、标签层级和限制 | 已到齐并解析 |
| A-03 | python -m pytest -q | 工程回归 | 既有结果已记录 |
| A-04 | <project-root>/docs/testing/RESUME_GOLD_100_REPORT.md | 简历 gold 背景和已有说明 | 已检查；未修改 |
| A-05 | <project-root>/文档/测试数据与测试报告.md | 原始范围与历史测试底稿 | 已检查；未修改 |
| A-06 | <project-root>/.runlogs/graph-role-timeline-corrected.png | 既有图谱 UI 运行记录候选 | 未嵌入；不作为数值证据 |
| A-07 | <project-root>/.runlogs/evolution-ai-agent-version-chain.png | 既有版本链 UI 运行记录候选 | 未嵌入；不作为数值证据 |

## 附录 B：定稿核对项

- [x] `summary.json` 和 `methodology.json` 均存在且可解析。
- [x] 项目级数字来自评测产物原值；从 rows 得到的失败计数明确标注为行级计数。
- [x] Markdown 与 DOCX 由同一份 JSON 读取生成，核心结果、分母、限制和结论一致。
- [x] Word 设置为 A4，含标题页、自动 TOC 字段、宋体/黑体样式、页码和浅灰/浅蓝表头。
- [x] 未嵌入未被产物指向的截图。
- [x] 未修改 `文档/测试数据与测试报告.md`。
