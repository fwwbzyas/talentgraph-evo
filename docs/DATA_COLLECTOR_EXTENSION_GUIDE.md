# 讯飞智聘数据采集器扩展指南

## 1. 代码位置

原有智联采集器位于：

```text
agents/data/zhaopin_browser.py
```

本次新增采集器与智联放在同一目录：

```text
agents/data/job51_browser.py             # 前程无忧（51job）解析与浏览器采集
agents/data/liepin_browser.py             # 猎聘卡片、详情解析与浏览器采集
agents/data/supplemental_recruitment.py  # 两个新增源共享的调度、游标、脱敏、限速和风控停止
agents/data/source_policy.py             # 正式招聘源白名单、名称、状态文件和低量默认值
```

组员原始实现仍保留在 `integrations/jd-crawler/`，作为设计、fixture 和来源实现参考；应用运行时不依赖该目录，避免 Docker 构建、部署路径和二次开发发生隐式耦合。原有 `agents/data/boss_browser.py` 与 `agents/data/zhaopin_browser.py` 未被改动。

## 2. 接入链路

```text
51job / 猎聘公开岗位页面
  -> 同目录 Source Adapter
  -> agents/data/sources.py 注册
  -> agents/data/collection.py 并发编排
  -> normalize_recruitment_item
  -> DataGovernanceAgent
  -> job_assets / job_versions / data_audits
  -> JobGraph / KnowledgeGraph / Evolution / EmergingJob / Match
  -> FastAPI 与前端岗位数据、二维图谱、三维图谱、城市图谱
```

新增来源的 `source_category` 都是 `recruitment`。只有通过统一质量与治理门禁的记录才能成为正式图谱证据；解析失败、正文缺失或范围外岗位进入拒绝/审计记录，不会绕过门禁直接写图。

## 3. 搜索范围

四个招聘源共享智联现有范围：

- 城市：北京、上海、广州、深圳、杭州、南京、苏州、成都、武汉、西安、合肥、长沙；
- 岗位词：24 个，覆盖人工智能 8 个、大数据 7 个、智能系统 4 个、物联网 5 个；
- 标题准入：工程师、开发、研发、算法、架构、测试、数据、嵌入式、智能体/Agent；
- 排除：销售、客服、课程/招生、运营、市场、兼职等非目标岗位。

`DataCollectionAgent.apply_strategy()` 在新增来源没有独立配置时继承智联的城市和岗位词，避免配置漂移。

## 4. 原始输出契约

采集器返回 `list[dict]`，字段与原有招聘源一致：

| 字段 | 说明 |
| --- | --- |
| `source_id` | 平台原生岗位 ID；标准化后自动成为 `51job:<id>` 或 `liepin:<id>` |
| `source_platform` | `51job` 或 `liepin` |
| `source_url` | 去除跟踪查询参数的 HTTPS 原始岗位链接 |
| `title` / `company` / `content` | 岗位名、公司名、公开 JD 正文 |
| `city` / `district` | 城市与区县 |
| `salary_min_k` / `salary_max_k` / `salary_months` | 月薪千元口径及薪数；原文保留在 `metadata.salary_raw` |
| `experience_min_years` / `experience_max_years` / `education` | 经验和学历 |
| `tags` | 平台公开标签；后续仍由项目技能词典统一抽取 |
| `published_at` | 平台提供时使用，缺失则保留为空 |
| `collection_mode` | 固定为 `live` |
| `metadata` | 查询词、检索城市、页码、采集器和研究采集标记 |

手机号、邮箱、微信号和 QQ 会在适配器进入主清洗链前被占位脱敏。

## 5. 低量与合规策略

- BOSS/智联保持原策略；
- 51job/猎聘默认每源每次 36 条、每 1440 分钟（24 小时）一轮；
- 服务启动时，如果补充源超过 6 小时未完成采集，会在 20–60 秒随机延迟后补采一次；6 小时内重复重启不会重复抓取，随后恢复 24 小时间隔；
- 每次最多访问 4 个城市—岗位词页，使用持久化游标轮换 12×24 组合；
- 请求默认间隔 2.5–4.5 秒；
- 页面导航与关键选择器分别采用 20 秒和 5 秒的有界超时；连接关闭、重置、DNS 或导航超时按“来源暂不可用”静默结束，不阻塞采集编排线程；
- 检测到 WAF、验证码或安全验证时立即停止，不自动重试、打码或绕过；该来源本轮在前端静默结束，仅保留后端日志；
- 本地默认使用可见浏览器；Docker 使用 headless Chromium，但遇验证同样直接停止；
- 猎聘搜索 URL 受 robots 规则限制，必须在人工复核当前规则和平台条款后设置 `TALENTGRAPH_LIEPIN_ROBOTS_ACKNOWLEDGED=1`。

主要环境变量见 `.env.example`。状态文件分别为 `data/51job_collection_state.json` 和 `data/liepin_collection_state.json`。

## 6. API 与前端

以下接口自动包含新来源：

```text
GET  /api/data/sources
GET  /api/data/strategy
POST /api/data/collect
GET  /api/data/collection-runs
GET  /api/collection/coverage
GET  /api/jobs/facets
GET  /api/knowledge-graph
GET  /api/knowledge-graph/career-galaxy
GET  /api/knowledge-graph/relations
GET  /api/knowledge-graph/city-map
GET  /api/graph/overview
GET  /api/graph/temporal
GET  /api/graph/wormhole
GET  /api/evolution/market
```

图谱和演化接口的 `source_platform` 可选值为 `boss`、`zhaopin`、`51job`、`liepin`。前端数据源健康面板、岗位筛选、审计来源、二维/三维图谱和城市图谱使用相同来源名称映射，保持原有组件与样式。

## 7. 测试与扩展约束

离线测试入口：

```bash
pytest -q tests/test_supplemental_recruitment_sources.py
```

该测试不访问真实站点，覆盖：

- 组员 51job fixture 与签名算法兼容；
- 51job/猎聘解析和统一原始字段；
- 12 城、24 词和低量调度；
- 标准化、治理、审计和持久化；
- JobGraph、KnowledgeGraph、Evolution、EmergingJob、Match；
- 新来源进入图谱证据白名单。

新增第五个招聘源时，应新增独立适配器并更新 `source_policy.py`，不要修改已有采集器实现；必须提供离线 fixture，先通过统一治理和下游 Agent 兼容测试，再更新 API/前端来源映射。
