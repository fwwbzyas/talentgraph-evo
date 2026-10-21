# 数据采集与清洗流水线 — 项目介绍与技术路线

> 揭榜挂帅 XH-202621: 多源异构数据驱动岗位和能力图谱构建与动态演化分析研究
> 发榜单位: 科大讯飞 | 负责: 路z（大三，数据 Lead）
> 版本 v1.1.0 | 2026-06-23

---

## 一、模块定位

本模块是多源异构数据驱动岗位能力图谱项目的**上游数据基础设施**，对应项目文档中的两层：

| 项目文档对应 | 模块职责 |
|-------------|---------|
| 功能技术说明 — 工程1（数据采集层） | 招聘网站爬虫 + 技术社区数据采集 |
| 功能技术说明 — 工程4（多源数据清洗流水线） | MinHash 去重 + 抄袭检测 + 新鲜度加权 + AI 检测 + 质量评分 |
| 项目计划 — 创新4 | **多源数据清洗流水线** |

下游对接：周jj 的 5 大 Agent（Discover/Define/Validate/Update/Reflect），通过 `contracts/data_schema.py` 的 Pydantic Schema 契约进行数据交换。

---

## 二、技术架构

### 2.1 分阶段流水线

```
┌─────────────────────────────────────────────────────────┐
│                  Stage 0 · Config                        │
│  config/sources.yaml  →  数据源定义  →  CrawlConfig     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                  Stage 1 · Collect                       │
│  ┌──────────────┐    ┌──────────────┐                    │
│  │ ZhaopinCrawler│    │ (未来扩展)    │                    │
│  │ Playwright    │    │ Liepin/Boss/ │                    │
│  │ BEM CSS 解析  │    │ GitHub/arXiv │                    │
│  └──────┬───────┘    └──────┬───────┘                    │
│         └───────────────────┘                            │
│                   │                                       │
│           list[RawJobDescription]                         │
└───────────────────┬─────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────┐
│                  Stage 2 · Clean                         │
│                                                          │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │ DedupAgent   │ → │ QualityScorer│ → │ AI Detector  │  │
│  │ MinHash LSH  │   │ 4维度加权评分 │   │ 统计特征检测  │  │
│  │ (datasketch) │   │ 完整度/原创度 │   │ 句长方差/    │  │
│  │              │   │ 新鲜度/信息量 │   │ 特征词密度   │  │
│  └─────────────┘   └──────────────┘   └──────────────┘  │
│                                                          │
│           list[CleanedJobDescription]                     │
└───────────────────┬─────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────┐
│               Stage P · Publish Gate                     │
│                                                          │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ Schema 校验     │  │ PostgreSQL   │  │ QualityReport│  │
│  │ (Pydantic v2)  │  │ / JSON 入库  │  │ 质量报告生成  │  │
│  └────────────────┘  └──────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 技术选型理由

| 组件 | 选型 | 为什么选它 |
|------|------|-----------|
| 浏览器自动化 | `Playwright` | 智联使用腾讯云 EdgeOne 反爬，纯 HTTP 请求会触发 CAPTCHA；Playwright 真实浏览器天然通过验证 |
| HTML 解析 | `parsel` (lxml) | Scrapy 同款解析引擎，CSS/XPath 选择器 |
| 去重 | `datasketch` | Spotify 等大厂验证的 MinHash LSH 库 |
| Schema | `pydantic v2` | FastAPI 同款，与周jj 后端一致 |
| 日志 | 自研 `JsonLogger` | 结构化 JSON 日志，每条带 trace_id/agent |

### 2.3 智联招聘页面解析策略

智联搜索页采用 BEM CSS 命名，但**不同岗位卡片的 DOM 结构不完全一致**（有的有技能标签行，有的没有）。因此解析策略是：

- **关键字段**（公司名、薪资）：使用固定 BEM CSS 选择器，可靠性最高
- **地点/经验/学历**：从 `div.jobinfo` 提取全部文本行，按正则模式分类匹配
- **技能/福利标签**：从 `div.jobinfo__tag` 和 `div.companyinfo__tag` 专用容器提取，使用 XPath `string(.)` 穿透嵌套 div

正则匹配优先级：经验 → 学历 → 地点。兜底方案：按中文地址特征词（路/街/市/县/区/镇）模糊匹配。

---

## 三、采集效果（已验证）

以"大数据运维"为关键词，单页采集 20 条数据：

| 字段 | 准确率 | 示例 |
|------|:------:|------|
| 职位名称 | 100% | 运维开发工程师助理(早九晚六，周末双休，13薪) |
| 公司名称 | 100% | 江西图登网络科技有限公司 |
| 薪资 | 100% | 7000-9000元·13薪 |
| 地点 | 100% | 重庆·两江新区 |
| 经验 | 95% | 1-3年 / 经验不限 / 1年以下 |
| 学历 | 100% | 本科 / 大专 / 学历不限 |
| 技能标签 | ~90% | Python, Shell, Prometheus, Grafana, Nginx |
| 公司标签 | 100% | 民营, 100-299人, 大数据 |

平均质量分 63.5/100（仅列表页，无完整 JD 正文）。

---

## 四、数据模型

### 4.1 原始数据 → 清洗数据的转换

```
RawJobDescription                  CleanedJobDescription
─────────────────                  ─────────────────────
source: "zhaopin"        ──→      source: "zhaopin"
title: "Python工程师"    ──→      title: "Python工程师"
description: "..."        ──→      description_clean: "..."
salary_range: "15K-25K"  ──→      quality_score: 63.5
location: "北京·海淀"     ──→      quality_level: "medium"
company: "XX科技"         ──→      is_duplicate: false
experience: "1-3年"       ──→      cleaning_trace: {...}
education: "本科"          ──→      skills: [SkillItem(...)]
```

### 4.2 质量评分维度

| 维度 | 权重 | 满分 | 评分标准 |
|------|:---:|:---:|---------|
| 完整度 | 30% | 30 | title(5) + company(4) + description长度(10) + salary(4) + location(3) + experience(2) + education(2) |
| 原创度 | 30% | 30 | 检测模板化短语密度，密度越高分越低 |
| 新鲜度 | 20% | 20 | 指数衰减: `20 × e^(-λ·days)` |
| 信息量 | 20% | 20 | 文本长度(8) + 技能关键词密度(6) + 结构化程度(6) |

质量等级: HIGH(≥80) / MEDIUM(50-79) / LOW(<50)

---

## 五、与下游 Agent 的对接方式

### 5.1 Schema 契约

所有数据交换通过 `contracts/data_schema.py` 的 Pydantic 模型进行：

```python
from contracts import RawJobDescription, CleanedJobDescription

# 读 JSON 文件
import json
with open("output/cleaned/cleaned_jds_20260623.json") as f:
    jds = [CleanedJobDescription(**item) for item in json.load(f)]

# 从数据库读取
import psycopg2
conn = psycopg2.connect("postgresql://app:dev_only_pwd@localhost:5432/job_kg")
```

### 5.2 数据格式约定

| 约定 | 说明 |
|------|------|
| `source_url` 作为唯一键 | 去重/更新均以此为准 |
| `quality_score` ∈ [0, 100] | 下游按需过滤阈值 |
| `cleaning_trace` 含完整记录 | 支持可追溯和证据链 |
| `crawl_timestamp` 每条带时间戳 | 支持增量更新和时序对比 |

---

## 六、可复现性设计

| 机制 | 实现 |
|------|------|
| **Cookie 持久化** | JSON 文件带时间戳，过期可更新 |
| **HTML 缓存** | 每次采集自动保存页面到 `output/debug_html/` |
| **确定性去重** | `datasketch.MinHashLSH` 固定 seed |
| **结构化日志** | JSON 行格式，每条带 trace_id |

---

## 七、开发路线图

### 第一周 (6/23-6/30): 原型验证 ✅ 已完成

- [x] Schema 设计 (contracts/data_schema.py)
- [x] 智联招聘爬虫 — Playwright + BEM CSS 解析
- [x] 模式化字段提取（正则 + 兜底策略）
- [x] 去重模块 (pipeline/dedup.py)
- [x] 质量评分 (pipeline/quality.py)
- [x] Docker 化部署
- [x] Mock 数据 (3 组)
- [x] 单元测试 (19 个，全部通过)
- [x] 结构化日志 (core/logger.py)
- [x] Cookie 持久化 + session 记录

### 第二周 (7/1-7/5): 招聘网站爬虫完善

- [ ] 详情页采集（获取完整 JD 正文，提升质量分）
- [ ] 猎聘网爬虫 (Playwright + Cookie)
- [ ] Boss直聘爬虫 (字体反爬攻克)
- [ ] 代理 IP 池集成

### 第三周 (7/6-7/10): 技术社区采集

- [ ] B站课程关键词搜索采集
- [ ] 知乎话题/回答采集
- [ ] GitHub Trending API
- [ ] arXiv API

### P3 阶段 (8/21-8/22): 清洗流水线优化

- [ ] 模板抄袭检测（结构相似度算法）
- [ ] AI 生成检测模型集成
- [ ] 数据质量量化报告
- [ ] 金标测试集准确率验证

---

## 八、关键技术决策记录

| 决策 | 选择 | 备选方案 | 理由 |
|------|------|---------|------|
| 爬虫方案 | Playwright 浏览器 | httpx + requests | 智联 EdgeOne CAPTCHA 封杀纯 HTTP 请求 |
| 页面解析 | BEM CSS + 正则兜底 | 固定 XPath | 不同岗位的 DOM 结构不一致 |
| 去重算法 | datasketch.MinHashLSH | 自研 MinHash | 工业验证库，避免边界 bug |
| 数据存储 | JSON + PostgreSQL 双模 | 仅 PostgreSQL | 不装数据库也能用 |
| 登录方式 | Cookie 持久化 + 注入 | 自动化登录 | 避免验证码，Cookie 可复用数天 |
| AI 检测 | 统计特征 | GPTZero API | 不依赖外部 API，原型阶段足够 |
