# jd-crawler 设计规格(SPEC)

> 版本: v0.2.0 · 2026-08-13
> 用途:**仅限学术研究**的公开职位 JD 批量采集原型。目标站点:前程无忧 51job、猎聘。
> v0.2 变更:Playwright headed 浏览器升为主模式(httpx 为可选轻量模式);新增矩阵批量(config/batch)、定时调度(scheduler)、数据清洗(cleaning)、交互式控制台(interactive);`JobPosting` 新增 `keyword`/`search_city` 检索上下文字段。

---

## 1. 现场侦察结论

### 1.0 浏览器模式实测(2026-08-13,本机非沙箱,v0.2 主模式)

| 站点 | httpx 路径 | 浏览器模式(Playwright headed) |
| --- | --- | --- |
| 51job | 搜索 API 触发阿里云 WAF(punish-loc 风控跳转)⇒ 按合规护栏停站,未绕过 | ✅ 成功:捕获浏览器自身发出的 `search-pc` API JSON 响应;**真实 API 结构为 `resultbody.job.items` + `resultbody.job.totalCount`**,字段为驼峰(`jobId/jobName/provideSalaryString/jobAreaString/workYearString/degreeString/issueDateString/jobHref/jobDescribe`);`description` 由 `jobDescribe` 填充(httpx 路径恒为空串) |
| 猎聘 | 游客搜索列表为 CSR,SSR 拿不到职位卡片(数据 API 需风控 token,实测 `{"flag":0}`,不请求) | ✅ 成功:北京 / 算法工程师 1 页 40 条;渲染完成后对 DOM 复用 `parse_search_cards` 解析 |

- `parse_search` 已同时兼容两种结构:现行真实 API(`resultbody.job.items`,驼峰字段)与旧公开结构(`resultbody.joblist`,小写字段,fixture 覆盖)。
- 浏览器模式合规形态见 §4.17 与 §5:强制 headed、持久化 profile、人机验证仅等待人工完成(180s 超时按风控停站)、不打码不伪装指纹不用代理。

### 1.1 51job(we.51job.com)— 早期沙箱侦察(2026-08-13,沙箱出口 IP 112.126.72.180)

| 项 | 实测结果 |
| --- | --- |
| 搜索 SSR 页 `GET /pc/search?keyword=...` | 200,但仅为 Vue SPA 空壳(`<div id="app">`),**无职位数据**,纯 CSR |
| 搜索 API `GET /api/job/search-pc` | 200,但返回**阿里云 WAF JS 挑战页**(`<textarea id="renderData">`、`aliyun_waf_*` meta、`acw_tc` Cookie),需浏览器执行混淆 JS 生成 `acw_sc__v2` Cookie;本机非沙箱实测进一步触发 punish-loc 风控跳转(见 §1.0) |
| sign 算法(从前端 JS 解出,gzip 传输的 chunk `app-06837ae4-*.js`) | `sign = HmacSHA256_hex(relative_url_with_query, cupid_sign_key)`;`relative_url_with_query` 形如 `/api/job/search-pc?api_key=51job&timestamp=<unix秒>&<querystring>`(POST 时再拼接 body) |
| `cupid_sign_key`(硬编码于前端 commonStore) | `abfc8f9dcf8c3f3d8aa294ac5f2cf2cc7767e5592590f39c3f503271dd68562b` |
| 其他必需请求头 | `uuid`、`From-Domain`(如 `51job_web`)、`account-id`(空)、`user-token`(空)、`partner`(空)、`property`(空 JSON) |
| 实测带正确 sign 请求 | 仍被 WAF 挑战页拦截 ⇒ **httpx 路径无法取得真实 JSON**;按合规护栏**不执行 WAF JS、不绕过**,爬虫检测到挑战页即停止;浏览器模式改走 §4.17 的响应捕获 |
| API 返回结构 | 现行真实结构(浏览器实测):`resultbody.job.items[]` + `resultbody.job.totalCount`(驼峰字段);旧公开结构:`resultbody.joblist[]`(jobid/jobname/providesalarytext/...,小写)。`parse_search` 两者兼容 |
| robots.txt | `we.51job.com/robots.txt` 与 `www.51job.com/robots.txt` 均未提供有效规则(返回 SPA 壳/跳转) |

### 1.2 猎聘(www.liepin.com)— 早期沙箱侦察

| 项 | 实测结果 |
| --- | --- |
| 游客搜索页 `GET /zhaopin/?key=Python&curPage=0` | 200,SSR 仅渲染页头/页脚 SEO 框架,**职位列表为 CSR**;首请求曾 302 至风控页 |
| 搜索数据 API `POST https://api-c.liepin.com/api/com.liepin.searchfront4c.pc-search-job` | 200 但 body 为 `{"flag":0}`(缺少 `security.min.js` 计算的 `x-fscp-*` 风控 token ⇒ 拒绝) |
| 详情页 `GET /job/<id>.shtml` | 200,**SSR 可用**:TDK(`<title>`、`meta description`,含岗位名/公司/城市/薪资/学历/经验)+ SSR 推荐职位卡片(`div.job-card-pc-container`,与搜索页卡片同构);**主体 JD 正文为 CSR** |
| 风控 | 同 IP 连续数请求后 302 → `https://safe.liepin.com/intercept/ip/captcha/dispatch?...`(滑块/验证码)。检测到即停止 |
| robots.txt | `Disallow: /*?*`(带查询串的 URL 全部被禁,含 `/zhaopin/?key=...`);`/job/*.shtml` 详情页未被禁止;`/hunter/*`、`/user/` 禁止 |

### 1.3 侦察对设计的影响

1. 两站均有**主动风控**,爬虫必须把"风控/验证码检测 + 立即停止"作为一等公民。
2. v0.2 起主通道为 **Playwright headed 浏览器**(§4.17):51job 捕获页面自身 `search-pc` 响应,猎聘渲染后解析 DOM;httpx 路径保留为可选轻量模式(`--httpx`),51job 走 API + sign,猎聘走 SSR HTML。
3. httpx 路径在沙箱/本机均无法稳定取得真实数据 ⇒ **解析逻辑以 fixture 单测验证**;fixture 优先使用真实抓取的页面片段(猎聘卡片/详情页为真实 HTML;51job API JSON 含按公开结构重建样例并在 fixture 头部注释标注);浏览器模式经本机人工监督实测(§1.0)。
4. 猎聘搜索 URL 带查询串,被其 robots 禁止 ⇒ 默认只做 robots 警示并需显式确认(见 §6)。

---

## 2. 总体架构

```
┌────────┐   args    ┌──────────────┐  JobPosting 流  ┌────────────────────┐
│ cli.py │ ────────▶ │ Spider(站点) │ ─────────────▶ │ DedupPipeline      │
└───┬────┘           │  browser.py  │                 │  ├─ JsonlWriter    │
    │                │  job51.py    │                 │  ├─ JsonArrayWriter│
    │                │  liepin.py   │                 │  └─ SQLiteWriter   │
    │                └──────┬───────┘                 └─────────┬──────────┘
    │ 编排                   │ 复用                             │ checkpoint.json
    ▼                       ▼             ▼              ▼      (断点续爬状态)
 interactive.py      http.py(httpx   ratelimit.py   sanitize.py
 config.py           会话/风控检测)   (限速+退避)    (联系方式脱敏)
 batch.py            spiders/browser.py(Playwright headed 会话,
 scheduler.py        人机验证等待,复用同一 RateLimiter 与解析器)
 cleaning.py(raw → cleaned)
```

- 每个站点一个 Spider,产出统一的 `JobPosting` 模型(§3);浏览器版 `BrowserSpider` 与 httpx 版同一接口,`BatchRunner`/CLI 可无感切换。
- HTTP 层统一处理:UA(带联系信息占位)、Cookie 会话、限速、指数退避重试、**风控检测**;浏览器路径沿用同一 `RateLimiter` 与 robots 护栏。
- Pipeline 双写 JSONL + SQLite(矩阵模式另写缩进格式化 JSON 数组),按 `source + job_id`(退化用 URL)去重,checkpoint 记录已完成页与已采职位 ID,支持断点续爬;`BatchRunner` 的 fresh_pages 语义支撑定时轮跑(§4.13)。

## 3. 数据 Schema(`jd_crawler/models.py`)

`JobPosting`(pydantic v2):

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source` | Literal["51job","liepin"] | 来源站点 |
| `job_id` | str | 站点内职位 ID(51job=`jobId`;猎聘=URL 中数字) |
| `title` | str | 岗位名 |
| `salary` | str \| None | 薪资原文(如 `1.5-2.5万/月`、`25-35k·19薪`) |
| `city` | str \| None | 工作城市/地区原文 |
| `company_name` | str \| None | 公司名 |
| `experience` | str \| None | 经验要求原文 |
| `education` | str \| None | 学历要求原文 |
| `publish_date` | str \| None | 发布/刷新时间原文 |
| `description` | str | 职位描述正文(**入库前经 sanitize 脱敏**;列表页拿不到时为空串;浏览器模式 51job 由 `jobDescribe` 填充) |
| `job_url` | str | 职位链接(已剥离跟踪参数;去重键之一) |
| `company_tags` | list[str] | 公司标签(行业/规模/融资阶段,可空) |
| `keyword` | str \| None | 检索关键词(v0.2 新增,spider 产出时标注,便于矩阵入库后统计追溯) |
| `search_city` | str \| None | 检索城市(v0.2 新增,同上) |
| `crawled_at` | datetime | 采集时间(UTC) |

**严禁采集**(模型层面就不存在这些字段):简历、求职者信息、HR 姓名/头像/IM、手机号、邮箱。
JD 正文中出现的手机号/邮箱在入库前由 `sanitize.py` 正则替换为 `[PHONE]`/`[EMAIL]`。

## 4. 模块契约

### 4.1 `jd_crawler/models.py`
- `class JobPosting(BaseModel)`:字段如上(含 v0.2 新增的 `keyword`/`search_city`);`model_post_init` 中对所有文本字段强制脱敏。
- `@property dedup_key -> str`:`f"{source}:{job_id}"`。

### 4.2 `jd_crawler/sanitize.py`
- `def mask_contacts(text: str) -> str`:手机号(`1[3-9]\d{9}` 及带分隔符变体)、邮箱、常见微信号(`微信/WeChat[:：]?\s*\w+`)替换为占位符。对 None/空串安全。

### 4.3 `jd_crawler/ratelimit.py`
- `class RateLimiter(interval=2.0, jitter=(0.5, 1.5))`
  - `wait()`:保证相邻请求间隔 ≥ interval,并额外 sleep `uniform(*jitter)`;`sleep` 可注入(测试用)。
- `def with_retry(func, max_retries=3, base_delay=2.0, retryable=(...), sleep=time.sleep)`:指数退避 `base_delay * 2**n`;`RiskControlError` **不重试,直接抛出**。

### 4.4 `jd_crawler/exceptions.py`
- `RiskControlError(site, url, evidence)`:检测到验证码/滑块/WAF/风控跳转。Spider 捕获后**停止该站点全部抓取**并记录。
- `FetchError`:网络/HTTP 错误(可重试)。

### 4.5 `jd_crawler/http.py`
- `class HttpClient(site_name, rate_limiter, contact="YOUR-EMAIL-PLACEHOLDER")`
  - UA:`jd-crawler/0.1 (+research; contact: {contact})` 叠加常见浏览器 UA 前缀,**不伪装搜索引擎爬虫**。
  - `get(url, **kw) -> httpx.Response` / `post(...)`:先 `RateLimiter.wait()`,再 `with_retry` 包装;每次响应后调用站点注入的 `risk_checker(response)`,命中即抛 `RiskControlError`。
  - `risk_checker` 判定(通用):① 响应 HTML 含 `aliyun_waf`/`id="renderData"`(51job WAF);② 30x 跳转目标含 `safe.liepin.com`/`captcha`;③ 最终 URL 或 body 含滑块/验证码特征(`safe.liepin.com`、`验证中心`、`captcha`、`punish`)。

### 4.6 `jd_crawler/spiders/base.py`
- `class BaseSpider(ABC)`
  - `site: str`
  - `iter_jobs(keyword: str, city: str|None, max_pages: int, checkpoint: Checkpoint) -> Iterator[JobPosting]`
  - 对已完成的页码/职位 ID 跳过;遇到 `RiskControlError` 向上抛,由 CLI/BatchRunner 记录并终止该站点。

### 4.7 `jd_crawler/spiders/job51.py`
- `Job51Spider(http: HttpClient, sign_key: str = CUPID_SIGN_KEY)`
- 请求构造(与前端实测一致):
  - 路径 `/api/job/search-pc`,固定参数 `api_key=51job`、`timestamp=<unix秒>`;
  - 业务参数:`keyword, searchType=2, function, industry, jobArea(城市码,默认 000000), jobArea2, landmark, metro, salary, workYear, degree, companyType, companySize, jobType, issueDate, sortType=0, pageNum, requestId, pageSize(≤50), source=1, accountId, pageCode=sou|sou|soulb`;
  - `sign = HmacSHA256_hex(urlencode排序前的原始 querystring 全串, sign_key)`(与前端 `url+(data||"")` 一致)。
- 解析:`parse_search(json_obj) -> tuple[list[JobPosting], total:int]`,**双结构兼容**:
  - 现行真实 API(v0.2 浏览器实测):`resultbody.job.items` / `resultbody.job.totalCount`,驼峰字段 `jobId/jobName/provideSalaryString/jobAreaString/workYearString/degreeString/issueDateString/jobHref/jobDescribe`;`description` 由 `jobDescribe` 填充(仅浏览器模式能拿到);
  - 旧公开结构(httpx 路径 fixture):`resultbody.joblist` + 小写字段。
- 详情正文(httpx 路径):`jobhref` 指向的详情页同样受 WAF 保护 ⇒ **只采列表字段**,`description` 恒为空串并在 README 说明;不实现详情抓取。
- 城市码表:内置常用城市码(`000000`全国、`010000`北京、`020000`上海、`030200`深圳、`030100`广州、`080200`杭州等),未知城市名报错提示。

### 4.8 `jd_crawler/spiders/liepin.py`
- `LiepinSpider(http: HttpClient, fetch_details: bool = True)`
- 搜索:`GET https://www.liepin.com/zhaopin/?key={kw}&curPage={n}`(可加 `city`/`dq`)。
  - 解析 `parse_search_cards(html) -> list[JobPosting]`:CSS `div.job-card-pc-container`;卡片内:`a[data-nick="job-detail-job-info"]`(href+`data-jobid`)、`.job-title-box div`、`.job-dq-box`、`.job-salary`、`.job-labels-box span`(经验/学历)、`.company-name`、`.company-tags-box span`。
  - **注意**:实测游客搜索页为 CSR,卡片可能为空 ⇒ 返回空列表并 log 提示"未获得 SSR 卡片";绝不转而请求带风控 token 的 API。
- 详情:`GET https://www.liepin.com/job/{id}.shtml`
  - `parse_detail(html, job) -> JobPosting`:优先解析 SSR 正文块(`.job-intro` / `.content-word` / `dd` 等历史结构,存在则用);缺失时回退解析 TDK:`<title>`(城市/岗位/公司)+ `meta[name=description]`(正则提取薪资/学历/经验)。
  - 详情页请求受同样限速与风控检测约束。
- 风控:任何 302 到 `safe.liepin.com` 或含验证码特征的响应 ⇒ `RiskControlError`。

### 4.9 `jd_crawler/pipeline.py`
- `class JsonlWriter(path)`:`write(job: JobPosting)`(一行一个 JSON,UTF-8,`ensure_ascii=False`)。
- `class SQLiteWriter(path)`:表 `jobs(dedup_key TEXT PRIMARY KEY, source, job_id, title, salary, city, company_name, experience, education, publish_date, description, job_url, keyword, search_city, crawled_at, raw_json)`;`INSERT OR IGNORE`。
  - **轻量迁移**:老库缺 `keyword`/`search_city` 列时自动 `ALTER TABLE ... ADD COLUMN`,历史库可直接复用。
  - `stats() -> dict`:返回 `total/first_crawled/last_crawled/by_source/by_search_city/by_keyword`(按检索城市与关键词聚合,供 CLI `--stats`)。
- `class DedupPipeline(jsonl, sqlite)`:`process(job) -> bool`(是否为新记录);内部维护 `seen: set[str]`。
- `class Checkpoint(path)`:`done_pages: dict[site|keyword|city, list[int]]`、`done_jobs: set[str]`;`is_page_done`、`mark_page`、`is_job_done`、`mark_job`、`save()`(原子写 JSON)。

### 4.10 `jd_crawler/robots.py`
- 内置两站 robots 规则快照(实测值,见 §1),`check(url) -> RobotsVerdict(allowed, rule, note)`。
- CLI/BatchRunner 启动时对目标 URL 模式做**警示**;猎聘搜索 URL(`/*?*`)默认警告并需 `--i-understand-robots` 显式确认才继续(矩阵模式未确认则整站跳过,组合标记 `skipped_robots`);详情页直接允许。

### 4.11 `jd_crawler/cli.py`
```
python -m jd_crawler.cli [--site {51job,liepin,all}] [--keyword KW] [--city 北京] \
    [--pages N] [--output DIR] [--delay 2.0] [--combo-pause 6.0] [--contact EMAIL] \
    [--resume/--no-resume] [--details/--no-details] \
    [--matrix [--config matrix.json]] [--loop HOURS [--max-runs N]] \
    [--httpx [--browser-fallback]] [--browser] [--user-data-dir DIR] \
    [--preflight] [--stats] [--clean] [--interactive] [--i-understand-robots]
```
- 模式分派:无参数/`--interactive` → 交互式控制台(§4.16);`--stats`/`--clean`/`--preflight` → 对应工具命令;`--matrix` 或 `--loop` → 矩阵批量(§4.13/§4.15);否则单次抓取(需 `--keyword`)。
- v0.2 起**浏览器为主模式**(`use_browser = not args.httpx`);`--httpx` 退回轻量模式,`--browser-fallback` 表示 httpx 被风控停站后自动切浏览器。
- 输出:默认 `jd-crawler/output/raw/` 下的 JSONL/JSON、SQLite、checkpoint、crawl.log、run_summary、browser_profile(详见 README"输出文件")。
- 任一站点抛 `RiskControlError` ⇒ 记录到 log + checkpoint,**停止该站点**,其余站点继续;退出码:0 全部完成,2 有站点被风控/robots 拦截、组合失败或异常中断。
- `--delay < 1.0` 自动 clamp 为 1.0 并告警(合规限速下限)。

### 4.12 `jd_crawler/config.py`(v0.2 新增)
- 默认矩阵常量:
  - `CITIES`(12):北京、上海、广州、深圳、杭州、南京、苏州、成都、武汉、西安、合肥、长沙;
  - `KEYWORD_GROUPS`(24 个,4 大类):
    - 人工智能(8):AI Agent 工程师、大模型应用工程师、RAG 工程师、机器学习工程师、算法工程师、多模态工程师、模型评测工程师、AI 平台工程师;
    - 大数据(7):大数据开发工程师、实时计算工程师、Flink 工程师、数据平台工程师、数据治理工程师、数据仓库工程师、湖仓架构师;
    - 智能系统(4):智能系统工程师、机器人软件工程师、边缘智能工程师、自动驾驶系统工程师;
    - 物联网(5):物联网平台工程师、物联网嵌入式工程师、IoT 工程师、边缘网关工程师、固件工程师;
  - `SITES`: `["51job", "liepin"]`。默认每平台 12 × 24 = **288 组**。
- `flatten_keywords(groups=None)`:按组顺序展开、去重保序;`keyword_category(kw, groups=None)`:反查所属大类。
- `@dataclass MatrixConfig(cities, keywords, sites, pages=2)`:`combos()` 产出 `(site, city, keyword)` 流;`combo_count()`。
- `load_matrix_config(path=None)`:JSON 覆盖,支持键 `cities` / `keyword_groups`(整组替换关键词表)/ `keywords`(追加)/ `sites`(校验合法站点)/ `pages`;`path=None` 返回默认全矩阵。

### 4.13 `jd_crawler/batch.py`(v0.2 新增)
- `class BatchRunner(config, out_dir, *, delay=2.0, combo_pause=6.0, contact=..., fetch_details=False, robots_ack=False, fresh_pages=True, use_browser=False, browser_fallback=False, user_data_dir=None, http_factory=..., sleep=...)`
  - **组合级容错隔离**:单组合 `FetchError`/解析异常只记 `failed` 并继续下一组合;`RiskControlError` 按合规护栏**停止整个站点**(剩余组合标记 `risk_stopped`),另一站点不受影响;猎聘未确认 robots ⇒ 整站组合标记 `skipped_robots`。
  - **组合间额外暂停**:`combo_pause × uniform(0.5, 1.5)` 秒,叠加在请求级限速之上。
  - **fresh_pages 语义**(默认开):每轮开始清空 `checkpoint.done_pages`、保留 `done_jobs` ⇒ 定时轮跑时页面会被重新抓取以发现新职位,同时不产生重复入库。
  - **browser_fallback**:httpx 通道站点被风控停站后,撤掉该站 httpx 组合记录,自动以浏览器通道重跑本站。
  - `delay` 下限 1.0s(与 CLI 一致的合规保护)。
- 输出文件命名(均在 `out_dir`):
  - `{site}_matrix_{tag}_{ts}.jsonl`(流式,断点友好)+ `{site}_matrix_{tag}_{ts}.json`(`JsonArrayWriter`,缩进格式化数组,便于人工审阅/下游清洗),`tag` 为 `browser`/`httpx`;
  - `run_summary_{ts}.json`:本轮摘要。
- `@dataclass ComboResult(site, city, keyword, status, new_jobs, error)`,`status ∈ {ok, empty, failed, risk_stopped, skipped_robots}`。
- `@dataclass RunSummary(run_id, started_at, finished_at, combos)`:聚合属性 `new_jobs` / `failed` / `risk_stopped_sites`;`to_dict()` 落盘。

### 4.14 `jd_crawler/cleaning.py`(v0.2 新增)
- **清洗算法接入点 —— `Cleaner` 协议**:任何实现 `name: str` 与 `clean(record: dict) -> dict | None` 的对象都可挂入清洗链;返回 `None` 表示丢弃该记录。挂接方式:`CleaningPipeline(cleaners=[...])` 或 `run_cleaning(raw_dir, cleaned_dir, cleaners=[...])`。
- `class CleaningPipeline(cleaners=None)`:按序执行清洗器;`clean_file(src, dst)` 读 JSONL、写**缩进格式化 JSON**,返回 `(读入条数, 写出条数)`。
- `run_cleaning(raw_dir, cleaned_dir, cleaners=None)`:清洗 `raw_dir` 下全部 `*.jsonl` → `cleaned_dir/{stem}.cleaned.json`,另写 `clean_report.json`(每文件 in/out 汇总);**全部文件共享同一条清洗链**(跨站点软去重才能生效)。
- 内置清洗器(均为**非破坏性**:规范化/派生/打标,不改写语义):
  - `WhitespaceCleaner`:压缩各文本字段(含 `keyword`/`search_city`)多余空白;
  - `SalaryNormCleaner`:派生 `salary_norm`(统一估算为 "X-Yk/月";万→×10k,/年→÷12;无法解析为空串),原 `salary` 不动;
  - `CrossSourceDedupCleaner`:跨站点按 (标准化标题, 标准化公司[去公司后缀], 城市[优先 search_city]) 软去重,后到记录打 `dup_of` 标(值为先见记录的 `dedup_key`),**不删除**。
- 预留扩展方向:薪资区间解析、公司名归一化、职位类别分类器、JD 分词/技能词抽取、embedding 去重等。
- CLI:`--clean`;交互菜单第 4 项。

### 4.15 `jd_crawler/scheduler.py`(v0.2 新增)
- `class Scheduler(run_once, *, interval_hours=24.0, max_runs=None, state_path=None, sleep=time.sleep)`
  - 进程内定时循环:每 `interval_hours` 执行一轮 `run_once()`(通常为 `BatchRunner.run`);间隔下限 0.05 小时(约 3 分钟,防误配)。
  - 轮次历史持久化到 `state_path`(CLI 传 `<output>/scheduler_state.json`):每轮记录 `run_id/new_jobs/failed_combos/risk_stopped_sites/status`,原子写。
  - **Ctrl+C 优雅退出**:分片 sleep(每片 ≤30s)保证长等待中也能较快响应中断;退出前状态已落盘,返回已完成轮数。
  - 风控停站的站点下一轮仍会重试(间隔通常足够长,且每轮 fresh_pages);若平台持续风控,请直接停止使用该站点。
  - 需要系统级调度时,建议改用 Windows 任务计划 / cron 直接调用 CLI(见 README)。

### 4.16 `jd_crawler/interactive.py` + CLI 扩展(v0.2 新增)
- 无参数启动 CLI(或显式 `--interactive`)进入交互式控制台 `run_interactive(default_output)`。
- 菜单:**1** 单次抓取(自定义站点/关键词/城市/页数)/ **2** 全矩阵批量抓取 / **3** 定时循环抓取 / **4** 数据清洗 / **5** 数据库统计 / **6** 查看当前矩阵配置(城市/关键词分组清单)/ **7** 浏览器预热 / **0** 退出。
- 各菜单项收集输入后拼装 argv 调 `cli.main(...)`;模式选择默认浏览器主模式,可选退回 `--httpx`(再可选 `--browser-fallback`);涉及猎聘时先询问 robots 确认。
- `KeyboardInterrupt` 只中断当前操作、返回主菜单;任何操作异常不退出菜单循环。

### 4.17 `jd_crawler/spiders/browser.py`(v0.2 新增,主模式)
- **定位**:httpx 路径被风控拦截时的人工兜底通道,自 v0.2 起为默认主模式。合规形态:
  - **强制 headed**(`headless=False`,窗口可见、人工可监督),`launch_persistent_context` 持久化用户目录(默认 `<output>/browser_profile`),仅用于复用本人已通过的站点验证状态;
  - 人机验证**由人完成**:检测到验证特征(标题/URL 含 `safe.liepin.com`/`验证`/`captcha`/`Security`/`Verification`)时仅轮询等待其消失(默认最多 180s),超时抛 `RiskControlError` 按风控停站;**绝不自动打码、绝不注入指纹伪装、不使用代理**;
  - 请求节奏沿用同一 `RateLimiter`(限速/抖动一致),robots 护栏在 CLI/BatchRunner 层与 httpx 路径完全一致。
- `class BrowserSession(user_data_dir, *, rate_limiter=None, verify_timeout=180, sleep=...)`:上下文管理器;`page()` 页级上下文;`goto(page, url)` = 限速等待 → 导航(`domcontentloaded`,60s 超时)→ `_wait_verification`。
- **解析复用 httpx 路径的成熟解析器,不维护第二套解析逻辑**:
  - `fetch_51job_search(session, keyword, city, page_num)`:打开 `we.51job.com/pc/search?...`,`page.on("response")` 收集页面自身发出的 `/api/job/search-pc` 响应(回调里只存对象,页面就绪后统一 `.json()`),取 joblist 最大的一份交给 `parse_search`;全部载荷为空且页面含 `id="renderData"` ⇒ WAF 挑战未通过,抛 `RiskControlError`。
  - `fetch_liepin_search(session, keyword, city, cur_page)`:打开搜索页,等 `div.job-card-pc-container` 出现(10s 超时,容忍缺页),取渲染后 DOM 交给 `parse_search_cards`。
- `preflight(user_data_dir, sites=("51job","liepin"), ...) -> dict[site, "ok" | "blocked: ..."]`:浏览器预热,打开各站点搜索页等待人工完成验证,把验证状态固化到用户目录,供定时轮跑免干预复用;CLI `--preflight`/交互菜单第 7 项。
- `class BrowserSpider(session, site)`:与 httpx 版同一 `iter_jobs` 接口(51job 页码从 1 起,猎聘从 0 起;空页即停);产出时为每条记录标注 `keyword`/`search_city`;checkpoint 语义一致。

## 5. 合规护栏(硬约束实现清单)

| 约束 | 实现位置 |
| --- | --- |
| 只采公开免登录字段 | schema §3;不带任何登录态 Cookie/token 头 |
| 手机号/邮箱/微信号脱敏 | `sanitize.mask_contacts`,pipeline 写入前强制执行 |
| 限速 2s + 抖动 0.5–1.5s,可调(下限 1.0s) | `RateLimiter` 默认参数,`--delay` 可调;CLI 与 `BatchRunner` 均对 `<1.0` 自动 clamp 并告警 |
| 矩阵组合间额外暂停(基准 6s,0.5~1.5 倍抖动) | `BatchRunner(combo_pause)`,`--combo-pause` |
| 指数退避重试 ≤3 次 | `with_retry` |
| 遇验证码/滑块/WAF 立即停站并记录 | `risk_checker` + `RiskControlError`,CLI/BatchRunner 停站逻辑 |
| 不打码、不绕过风控、不用代理池、不伪造登录态 | 代码中无相关路径;WAF 仅检测不执行其 JS |
| **浏览器模式强制 headed(禁 headless),人机验证仅等待人工完成(默认 180s,超时按风控停站),不伪装指纹** | `BrowserSession`(§4.17):`headless=False` 硬编码、`_wait_verification` 只轮询不干预 |
| 浏览器持久化 profile 仅复用本人验证状态 | `launch_persistent_context(<output>/browser_profile)`,`--preflight` 预热固化 |
| 正常 UA(带联系信息占位) | `HttpClient(contact=...)`,CLI `--contact` |
| 去重 + 断点续爬;定时轮跑发现新职位且不重复入库 | `DedupPipeline` + `Checkpoint`;`BatchRunner(fresh_pages=True)` 清 `done_pages` 保留 `done_jobs` |
| robots 警示 | `robots.py` + CLI 确认开关;矩阵模式未确认则猎聘整站跳过(`skipped_robots`) |

## 6. 测试策略

- `tests/fixtures/`:
  - `job51_search_response.json` — 按 §1.1 旧公开结构重建的样例(文件内 `_fixture_note` 字段标注非实测);v0.2 新增按浏览器实测的现行结构(`resultbody.job.items`,驼峰字段)样例。
  - `job51_waf_challenge.html` — **真实**抓取的阿里云 WAF 挑战页。
  - `liepin_search_cards.html` — 从**真实**详情页截取的 2 张职位卡片(与搜索页卡片同构)。
  - `liepin_job_detail.html` — **真实**详情页精简版(保留 TDK 与卡片)。
- 单测:解析正确性(含 51job 双结构兼容)、脱敏、限速器(注入假 sleep)、重试、风控检测(WAF 页 / safe.liepin 302)、sign 算法(已知答案测试)、去重与 checkpoint、SQLite 列迁移与 `stats()`、矩阵配置加载、`BatchRunner` 组合容错/fresh_pages/摘要落盘、`Scheduler` 轮次记录与中断、清洗链与内置清洗器、浏览器会话验证等待与预热(Playwright 全部 mock)、交互式控制台菜单、CLI robots 拦截与风控停站端到端。
- 共 **56 个用例**;网络层测试全部基于 `httpx.MockTransport` 与 fixture,Playwright 全部 mock,**不触网**;真实网络验证通过人工监督下小页数试跑完成(§1.0)。
- 运行:`python -m pytest --basetemp=.pytest_tmp`(规避沙箱对系统 tmp 目录的权限限制;非沙箱环境可省略)。

## 7. 依赖

Python ≥3.11;`httpx`、`parsel`、`pydantic`(requirements.txt 锁定最低版本);测试用 `pytest`。
浏览器模式(v0.2 主模式)另需 `playwright`(**未写入 requirements.txt,属手动安装的可选依赖**):`pip install playwright && playwright install chromium`。
