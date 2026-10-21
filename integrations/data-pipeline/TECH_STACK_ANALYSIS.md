# 数据采集与清洗流水线 — 技术栈分析

> 揭榜挂帅 XH-202621 | 负责: 路z | 日期: 2026-07-16
> 对照需求: 数据实时获取 / 重复数据清洗 / 爬取 / 描述规范性清洗

---

## 一、总览

```
                       ┌──────────────────────────┐
                       │   contracts/data_schema  │
                       │   Pydantic v2 (不变)      │
                       └────────────┬─────────────┘
                                    │
       ┌────────────┬───────────────┼───────────────┬────────────┬──────────┐
       ▼            ▼               ▼               ▼            ▼          ▼
  ┌─────────┐ ┌──────────┐  ┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐
  │ 爬取层  │ │ 规范化层 │  │   去重层     │ │ 入库层   │ │ 调度层   │ │测试层│
  │         │ │          │  │              │ │          │ │          │ │      │
  │Playwright│ │ftfy      │  │datasketch    │ │PostgreSQL│ │APScheduler│ │pytest│
  │stealth   │ │jieba     │  │sklearn(TF-IDF)│ │JSON fallbk│ │sqlite3   │ │cov  │
  │fake-ua   │ │cpca      │  │shelve        │ │pydantic  │ │hashlib   │ │     │
  │fontTools │ │dateparser│  │rapidfuzz     │ │          │ │          │ │     │
  │httpx     │ │html      │  │              │ │          │ │          │ │     │
  │arxiv     │ │re        │  │              │ │          │ │          │ │     │
  │requests  │ │          │  │              │ │          │ │          │ │     │
  └─────────┘ └──────────┘  └──────────────┘ └──────────┘ └──────────┘ └──────┘
       │            │               │               │            │
       └────────────┴───────────────┴───────────────┴────────────┘
                                    │
                                    ▼
                       ┌───────────────────────┐
                       │ 下游 5 Agent (周jj)    │
                       │ 通过 contracts 对接    │
                       └───────────────────────┘
```

### 核心依赖 (已有，不变)

| 组件 | 用途 |
|------|------|
| `pydantic>=2.0` | Schema 校验，Schema-First 铁律的基石 |
| `playwright>=1.48` | 浏览器自动化，绕过 EdgeOne CAPTCHA |
| `datasketch>=1.6` | MinHash LSH 工业级去重 |
| `parsel>=1.9` | BEM CSS/XPath HTML 解析 |
| `httpx>=0.27` | 轻量 HTTP 请求 (猎聘/拉勾) |
| `pytest>=8.0` + `pytest-cov>=5.0` | 测试框架，目标覆盖率 ≥60% |
| `black>=24.0` + `ruff>=0.5` | 代码格式 + lint |

### 新增依赖清单

```txt
# ── 爬取增强 ──────────────────────────
playwright-stealth>=1.0       # 隐藏 navigator.webdriver 等自动化指纹
fake-useragent>=1.5           # 随机 User-Agent 轮转
fontTools>=4.50               # Boss直聘自定义字体解析 (glyph→unicode 映射)
arxiv>=2.1                    # arXiv 官方 Python 包，一行查询

# ── 描述规范化 ──────────────────────
ftfy>=6.2                     # Unicode 乱码修复 (\xa0→空格, 全角→半角)
jieba>=0.42                   # 中文分词，配合技能词典提取结构化技能
cpca>=0.8                     # 中国行政区划解析 (北京→province/city/district)
dateparser>=1.2               # 日期统一解析 ("3天前"/"6月20日"/ISO格式)
rapidfuzz>=3.8                # 模糊字符串匹配 (C扩展, 比 difflib 快 10-100x)

# ── 去重增强 ──────────────────────────
scikit-learn>=1.5             # TfidfVectorizer (模板抄袭结构相似度检测)

# ── 调度与增量 ─────────────────────
APScheduler>=3.10             # 轻量定时任务 (cron 表达式, 单文件 300KB)
```

---

## 二、爬取层

### 2.1 当前状态

| 已实现 | 缺口 |
|--------|------|
| 智联招聘列表页采集 (Playwright + Cookie 注入) | 详情页 `get_detail()` 存在但未接入 `search()` 主流程 |
| GitHub REST API + 限速指数退避 | Boss直聘 (字体反爬) |
| 三种运行模式 (zhaopin/github/linked) | 猎聘、拉勾 |
| CAPTCHA 检测 + 120s 人工验证等待 | B站/知乎/arXiv |
| Cookie 持久化 (`cookies/zhaopin.json`) | 代理 IP 池 |
| HTML 调试保存 (`output/debug_html/`) | 无请求限速自适应 (固定 3s delay) |

### 2.2 各数据源技术方案

| 数据源 | 方案 | 关键依赖 | 反爬难度 |
|--------|------|---------|:------:|
| **智联招聘** | Playwright 真实浏览器 + Cookie + BEM CSS 解析 | playwright, parsel | 高 (EdgeOne CAPTCHA) |
| **Boss直聘** | Playwright + fontTools 解析自定义字体映射 | playwright, fontTools | 极高 (字体混淆) |
| **猎聘** | httpx + Cookie 注入 + HTML 解析 | httpx, parsel | 中 |
| **拉勾** | httpx + Cookie 注入 | httpx, parsel | 低~中 |
| **GitHub** | REST API /search/repositories | requests ✅ 已有 | 低 (60次/h 未认证, 5000次/h 已认证) |
| **B站** | requests 公开搜索 API (无认证墙) | requests | 低 |
| **知乎** | Playwright + 持久化登录态 | playwright | 中 |
| **arXiv** | 官方 Python 包 `arxiv.Search()` | arxiv | 无 |

### 2.3 反爬对抗策略

```
                           ┌─────────────┐
                           │  请求入口    │
                           └──────┬──────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │       ProxyRotator        │
                    │   轮转代理 IP (付费API)     │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │     UA 轮转               │
                    │   fake-useragent          │
                    └─────────────┬─────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
        ┌──────────┐       ┌──────────┐        ┌──────────┐
        │ httpx    │       │Playwright│        │ requests │
        │ (猎聘/拉勾)│       │(智联/Boss)│        │ (GitHub/ │
        │          │       │          │        │  B站/arXiv)│
        └──────────┘       └────┬─────┘        └──────────┘
                                │
                    ┌───────────┴───────────┐
                    │  playwright-stealth   │
                    │  隐藏自动化特征        │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │   Cookie 持久化注入     │
                    │  cookies/*.json       │
                    └───────────────────────┘
```

### 2.4 Boss直聘字体反爬技术路线

```
Boss 详情页 HTML               字体文件 (woff2)
       │                            │
       ▼                            ▼
  parsel 提取文本            fontTools 解析
       │                     glyph → unicode 映射表
       ▼                            │
  乱码字符 (如 )  ──────────────→ 真实字符 (如 "年")
```

流程: Playwright 打开详情页 → 截图 + 获取 HTML → 检测页面中 `@font-face` 的自定义字体 URL → 下载 woff2 文件 → `fontTools.TTFont` 解析 cmap 表 → 建立 glyph name → unicode 映射 → 将 HTML 中被混淆的字符替换为真实字符。

### 2.5 各爬虫统一接口

所有爬虫实现 `BaseCrawler` 抽象基类 (已有)，接口不变:

```python
class BaseCrawler(ABC):
    source_name: str                    # Source 枚举值
    def search(keyword) -> list[RawJobDescription]
    def get_detail(url) -> RawJobDescription
    def collect() -> list[RawJobDescription]   # 公共编排逻辑
```

新增爬虫只需实现 `search()` 和 `get_detail()`，编排/去重逻辑由基类 `collect()` 统一处理。

---

## 三、描述规范化层

### 3.1 当前状态

| 已实现 | 缺口 |
|--------|------|
| 四维质量评分 (完整度/原创度/新鲜度/信息量) | 无文本规范化预处理 |
| AI 生成检测 (特征词密度 + 句长方差) | 技能标签 `list[SkillItem]` 始终为空 |
| 清洗追溯 `CleaningTrace` | 薪资/地点/经验格式未统一 |
| | 公司名/职位名未归一化 |

### 3.2 规范化流水线

```
list[RawJobDescription]
        │
        ▼
┌─────────────────────┐
│  Stage 2.0: Normalize│  ← 新增
│                     │
│  ftfy.fix_text()    │  Unicode 乱码修复
│  html.unescape()    │  HTML 实体解码 (&amp; → &)
│  re 空白符合并       │  \r\n\t → 空格, 多空行合并
│  控制字符过滤        │  去除 \x00-\x08 等不可见字符
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Stage 2.1: Extract │  ← 新增
│                     │
│  jieba + 技能词典    │  从正文提取结构化技能
│  cpca               │  地点归一化 (省/市/区)
│  dateparser         │  日期归一化 → datetime
│  re 薪资格式         │  "15K-25K·13薪" → {min, max, months}
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Stage 2.2: Dedup   │  已有 + 增强
│  Stage 2.3: Score   │  已有
└─────────────────────┘
```

### 3.3 各组件详解

#### ftfy — Unicode 修复

```python
import ftfy

# 原始数据中常见的脏文本
text = "Pythonå¼€å\x8f\x91å·¥ç¨å¸"   # 编码乱码
text = "Python工程师\xa0\xa0"                      # 非断行空格
text = "５年经验"                                   # 全角数字
text = "薪资：15000-25000元/月"                     # 全角冒号

# 一行修复
clean = ftfy.fix_text(text)
# → "Python工程师  " + NFKC 标准化处理
```

为什么选 ftfy: 手写正则永远覆盖不全 Unicode 边界情况 (Latin-1 双编码、CP1252 混合 UTF-8)，ftfy 是专门解决这个问题的库，Mozilla/Sphinx 等项目在用。

#### jieba — 中文技能提取

```python
import jieba

# 加载技能自定义词典
jieba.load_userdict("data/skill_dict.txt")
# 词典内容示例:
#   Spring Boot 5
#   Kubernetes 5
#   分布式系统 5
#   高并发 3

text = "负责后端开发，使用Python Django REST框架，熟悉MySQL和Redis"
words = jieba.cut(text)
# → ["Python", "Django", "REST", "框架", "MySQL", "Redis"]

# 对照已有 skill_linker.py 映射表 + quality.py tech_keywords
# 输出 list[SkillItem]
```

词典构建来源: 项目计划的 100 条金标 JD + `skill_linker.py:JOB_TO_GITHUB_QUERIES` 中的技术词 + `quality.py` 的 `tech_keywords`。

#### cpca — 行政区划解析

```python
import cpca

cpca.transform(["北京市海淀区中关村"], cut=False)
# → [{"省": "北京市", "市": "北京市", "区": "海淀区"}]

cpca.transform(["上海徐汇"], cut=False)
# → [{"省": "上海市", "市": "上海市", "区": "徐汇区"}]
```

#### dateparser — 日期归一化

```python
import dateparser

dateparser.parse("3天前")       # → datetime(2026, 7, 13)
dateparser.parse("6月20日")     # → datetime(2026, 6, 20)
dateparser.parse("2026-06-20")  # → datetime(2026, 6, 20)
dateparser.parse("昨天")        # → datetime(2026, 7, 15)
```

替代自写的 `_parse_days_ago()`，覆盖更多中文日期格式。

#### rapidfuzz — 公司名/职位名模糊匹配

```python
from rapidfuzz import fuzz, process

# 公司名归一化
names = ["北京字节跳动科技有限公司", "字节跳动", "ByteDance"]
fuzz.partial_ratio("字节跳动", "北京字节跳动科技有限公司")  # → 100

# 职位名归一化
fuzz.partial_ratio("Python后端开发工程师", "Python工程师")  # → 85
```

---

## 四、去重增强层

### 4.1 当前状态

| 已实现 | 缺口 |
|--------|------|
| MinHash LSH 文本去重 (datasketch, threshold=0.85) | 跨次运行去重 (LSH 索引未持久化) |
| 爬虫内部 source_url 去重 | 模板抄袭检测仅靠固定短语密度，无结构相似度 |
| | 公司名/职位名模糊匹配 (归一化后去重) |

### 4.2 增强方案

#### 跨次运行去重 — shelve 持久化 LSH 索引

```python
import shelve
from datasketch import MinHashLSH

class PersistentDedupAgent(DedupAgent):
    """带 LSH 索引持久化的去重器"""

    INDEX_FILE = "output/dedup_index.shelve"

    def __init__(self, threshold=0.85):
        super().__init__(threshold)
        # 从磁盘恢复索引
        self._load_index()

    def _load_index(self):
        with shelve.open(self.INDEX_FILE) as db:
            for key, sig in db.items():
                self._lsh.insert(key, sig)

    def _save_index(self, key, sig):
        with shelve.open(self.INDEX_FILE) as db:
            db[key] = sig
```

`shelve` 是 Python 标准库，提供 `dict` 风格的磁盘持久化。MinHash 签名每个 128 维 × 4 字节 = 512 字节，1 万条 JD 的索引约 5MB。

#### 模板抄袭检测 — TfidfVectorizer

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class TemplateDetector:
    """基于 TF-IDF 的结构相似度模板抄袭检测"""

    def __init__(self, threshold=0.80):
        self.vectorizer = TfidfVectorizer(
            analyzer="char",        # 字符级 n-gram，对中文更准确
            ngram_range=(3, 5),
            max_features=5000,
        )
        self.threshold = threshold

    def fit(self, jd_texts: list[str]):
        """用已有数据集建立 TF-IDF 矩阵"""
        self._matrix = self.vectorizer.fit_transform(jd_texts)

    def is_template(self, new_text: str) -> tuple[bool, float]:
        """判断新 JD 是否与已有库中的模板高度相似"""
        vec = self.vectorizer.transform([new_text])
        scores = cosine_similarity(vec, self._matrix)[0]
        max_score = scores.max()
        return max_score >= self.threshold, max_score
```

与 MinHash 的区别: MinHash 检测**完全相同或高度相似**的文本；TF-IDF 检测**结构相似但措辞不同**的模板（如同一模板被不同公司填充后发布）。

### 4.3 去重三道防线

```
原始数据
    │
    ▼
┌─────────────────────┐
│ 第一道: URL 去重     │  基于 source_url + 增量状态 sqlite
│ (跨次运行)           │  已采集过的 URL 直接跳过
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 第二道: 内容去重     │  MinHash LSH (datasketch)
│ (近似重复文本)       │  threshold=0.85
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 第三道: 模板抄袭检测 │  TF-IDF + cosine_similarity (sklearn)
│ (结构相似但措辞不同) │  threshold=0.80
└─────────┬───────────┘
          │
          ▼
       干净数据
```

---

## 五、调度与增量更新层

### 5.1 当前状态

完全手动 CLI 触发，无定时采集、无增量检测。

### 5.2 增量采集机制

```python
import sqlite3
import hashlib

class IncrementalTracker:
    """基于 SQLite 的增量采集状态管理"""

    def __init__(self, db_path="output/crawl_state.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS crawl_state (
                source_url TEXT PRIMARY KEY,
                crawl_timestamp TEXT,
                content_hash TEXT
            )
        """)

    def is_new(self, source_url: str) -> bool:
        """URL 是否从未采集过"""
        cur = self.conn.execute(
            "SELECT 1 FROM crawl_state WHERE source_url = ?", (source_url,)
        )
        return cur.fetchone() is None

    def has_changed(self, source_url: str, description: str) -> bool:
        """已采集过的 URL，描述内容是否变化"""
        cur = self.conn.execute(
            "SELECT content_hash FROM crawl_state WHERE source_url = ?",
            (source_url,)
        )
        row = cur.fetchone()
        if not row:
            return True
        new_hash = hashlib.md5(description.encode()).hexdigest()
        return new_hash != row[0]

    def mark_collected(self, source_url: str, description: str):
        """记录采集状态"""
        content_hash = hashlib.md5(description.encode()).hexdigest()
        self.conn.execute(
            "INSERT OR REPLACE INTO crawl_state VALUES (?, datetime('now'), ?)",
            (source_url, content_hash)
        )
        self.conn.commit()
```

流程: 采集前遍历历史 URL → 跳过未变化的 → 只抓新增和变更 → 更新增量状态表。

### 5.3 定时调度

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# 每天凌晨 2 点全量采集
scheduler.add_job(run_pipeline, "cron", hour=2, args=[keywords])

# 每 6 小时增量采集
scheduler.add_job(run_incremental, "interval", hours=6)

scheduler.start()
```

选 APScheduler 的理由: 单文件 300KB，无外部依赖，支持 cron/interval/date 三种触发器。比系统 crontab 跨平台，比 Celery 简单两个数量级。

---

## 六、关键不引入的技术

| 技术 | 理由 |
|------|------|
| **Scrapy** | 已有 `BaseCrawler` + Playwright 架构，引入 Scrapy 会与现有设计冲突 |
| **spaCy / Transformers** | 太重 (模型 500MB+)，jieba + 自定义词典在 JD 场景覆盖 90% 技能提取 |
| **Celery + Redis + RabbitMQ** | 单机部署无分布式需求，APScheduler 已满足 |
| **Elasticsearch** | shelve + MinHash LSH + TF-IDF 已覆盖去重和模板检测需求 |
| **GPTZero / LLM 调用** | 项目计划明确 AI 检测用统计特征，不走外部 API |
| **MySQL / MongoDB** | 已有 PostgreSQL + JSON 双模方案，不需要多数据库 |

---

## 七、与项目阶段的对应

| 项目阶段 | 时间 | 对应技术组件 |
|----------|------|-------------|
| **P0 已完成** | 6/19-6/30 | pydantic, playwright, datasketch, parsel, pytest, Docker |
| **P1 第二周** (招聘爬虫完善) | 7/1-7/5 | 详情页接入, fontTools(Boss), httpx(猎聘), fake-ua, playwright-stealth, 代理IP轮转 |
| **P1 第三周** (技术社区) | 7/6-7/10 | arxiv, requests(B站), Playwright(知乎) |
| **P1 第四周** (清洗基础) | 7/13-7/17 | ftfy, jieba+技能词典, cpca, dateparser |
| **P3 清洗优化** | 8/21-8/22 | sklearn TfidfVectorizer, shelve LSH 持久化, rapidfuzz |
| **P4 部署** | 8/26-9/2 | APScheduler, sqlite3 增量状态 |

---

## 八、风险与对策

| 风险 | 技术对策 |
|------|---------|
| Boss直聘字体反爬更新 | fontTools 解析 woff2 的 cmap 表是通用方法，不依赖特定字体文件格式 |
| 智联 EdgeOne CAPTCHA 升级 | 已选 Playwright 真实浏览器 + 人工验证等待，不是协议层绕过，升级影响有限 |
| GitHub API 限速 (60次/h) | 三档应对: 设置 Token (5000次/h) → 指数退避 → 降级到静态技能映射表 |
| jieba 技能分词不准确 | 构建项目专用技能词典 (来源: 100条金标 JD + 已有映射表)，非通用词典 |
| 代理 IP 成本 | 优先用免费池 + 长延迟采集；付费代理作为 P3 优化项 |
