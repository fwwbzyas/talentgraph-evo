# jd-crawler

研究用途的**公开职位 JD** 批量采集原型,目标站点:前程无忧 51job、猎聘。v0.2 起默认使用 **Playwright headed 浏览器**采集,httpx 为可选轻量模式。

> ⚠️ **合规使用声明(请先阅读)**
> - 本项目**仅供学术研究/学习**,不得用于任何商业用途。
> - 只采集**公开、免登录**可见的职位 JD 字段;**严禁**采集简历、求职者信息、HR 个人联系方式等任何个人信息;JD 正文中偶然出现的手机号/邮箱/微信号/QQ 会在入库前自动脱敏为 `[PHONE]`/`[EMAIL]`/`[WECHAT]`/`[QQ]`。
> - 请遵守目标站点的 robots.txt 与平台服务条款。实测:猎聘 robots `Disallow: /*?*`(搜索 URL 被禁,CLI 默认拦截,需 `--i-understand-robots` 显式确认);51job 未提供有效 robots.txt,仍须遵守其平台条款。
> - 默认限速 2 秒/请求 + 0.5~1.5 秒随机抖动,指数退避重试(≤3 次);矩阵模式组合间另有基准 6 秒的暂停(0.5~1.5 倍抖动);请保持低频,勿高并发。
> - **遇到验证码/滑块/WAF 风控时程序会立即停止该站点并记录,绝不打码、绝不绕过、不使用代理池对抗封禁、不伪造登录态。**
> - 浏览器模式合规形态:**强制非 headless**(窗口可见、人工可监督)、持久化用户目录(默认 `<output>/browser_profile`)仅用于复用本人已通过的验证状态;人机验证**只等待人工完成**(默认 180 秒,超时按风控停站);**不打码、不伪装浏览器指纹、不使用代理**。
> - 采集数据**不要公开传播**;如平台方提出异议,请立即停止并删除数据。
> - 使用者须自行承担使用本工具的一切法律责任。

## 安装

```bash
cd jd-crawler
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 浏览器模式(v0.2 主模式)依赖,requirements.txt 未包含,需手动安装:
pip install playwright && playwright install chromium
```

要求 Python ≥ 3.11。

## 用法

### 单次抓取(默认浏览器模式)

```bash
# 猎聘:搜索 Python 职位 1 页(搜索 URL 受其 robots 限制,需显式确认)
python -m jd_crawler.cli --site liepin --keyword Python --pages 1 \
    --contact you@example.com --i-understand-robots

# 51job:搜索北京 Python 职位 2 页
python -m jd_crawler.cli --site 51job --keyword Python --city 北京 --pages 2 \
    --contact you@example.com

# 退回轻量 httpx 模式(无浏览器;被风控站点会立即停站)
python -m jd_crawler.cli --site 51job --keyword Python --httpx

# httpx 模式被风控后自动切换浏览器模式
python -m jd_crawler.cli --site all --keyword 数据分析 --httpx --browser-fallback
```

### 矩阵批量

```bash
# 默认矩阵:2 站点 × 12 城市 × 24 关键词 = 每平台 288 组,每组默认 2 页
python -m jd_crawler.cli --matrix --site all --contact you@example.com

# JSON 覆盖矩阵(cities/keyword_groups/keywords/sites/pages)
python -m jd_crawler.cli --matrix --config my_matrix.json
```

默认 12 城市:北京、上海、广州、深圳、杭州、南京、苏州、成都、武汉、西安、合肥、长沙。24 关键词按 4 大类分组(完整清单见 `jd_crawler/config.py` 的 `KEYWORD_GROUPS`,亦可用交互菜单第 6 项查看):人工智能 8 个 / 大数据 7 个 / 智能系统 4 个 / 物联网 5 个。

矩阵模式特性:组合级容错(单组合失败仅记录并继续;`RiskControlError` 按合规停整个站点,另一站点不受影响;猎聘未确认 robots 则整站跳过);每轮清空页级进度(`done_pages`)但保留职位级去重集(`done_jobs`),定时轮跑可发现新职位且不重复入库;每轮结束写 `run_summary_{ts}.json` 摘要。

### 定时循环

```bash
# 每 24 小时自动跑一轮全矩阵(隐含 --matrix),Ctrl+C 优雅退出
python -m jd_crawler.cli --matrix --loop 24 --max-runs 30
```

轮次历史写入 `<output>/scheduler_state.json`。更稳妥的做法是用系统级调度(Windows 任务计划 / cron)定时直接调用上面的 CLI 命令。

### 交互式控制台

```bash
python -m jd_crawler.cli                # 无参数启动
python -m jd_crawler.cli --interactive  # 显式进入
```

菜单:1 单次抓取 / 2 矩阵批量 / 3 定时循环 / 4 数据清洗 / 5 数据库统计 / 6 查看矩阵配置 / 7 浏览器预热 / 0 退出。

### 其他命令

```bash
python -m jd_crawler.cli --preflight                 # 不登录预热(过站点验证)
python -m jd_crawler.cli --preflight --login          # 登录预热(自动弹扫码登录页)            # 浏览器预热:人工过验证固化 profile,供定时轮跑免干预
python -m jd_crawler.cli --stats                # SQLite 入库统计(按站点/检索城市/关键词聚合)
python -m jd_crawler.cli --clean                # 手动清洗:output/raw/*.jsonl → output/cleaned/
```

## 参数一览

| 参数 | 说明 |
| --- | --- |
| `--site {51job,liepin,all}` | 目标站点(默认 all) |
| `--keyword` | 搜索关键词(单次模式必填) |
| `--city` | 城市名(内置码表,如 北京/上海/深圳/杭州),缺省全国 |
| `--pages` | 列表页数(单次默认 1,矩阵默认 2;51job 从第 1 页起,猎聘 `curPage` 从 0 起) |
| `--output` | 输出目录(默认 `jd-crawler/output/raw`,cleaned 与其同级) |
| `--delay` | 请求间隔秒数(默认 2,另加 0.5~1.5s 抖动;**下限 1.0s**,设置更低会被自动提升为 1.0 并打印警告) |
| `--combo-pause` | (矩阵)组合间暂停基准秒数,实际 0.5~1.5 倍抖动(默认 6) |
| `--contact` | UA 中携带的联系邮箱(请替换为真实联系方式) |
| `--no-resume` | 忽略 checkpoint 重新爬 |
| `--details` / `--no-details` | (猎聘/httpx 模式)是否抓详情页(单次默认开,矩阵默认关) |
| `--matrix` | 矩阵批量:站点 × 12 城市 × 24 关键词 |
| `--config` | 矩阵配置 JSON(cities/keyword_groups/keywords/sites/pages) |
| `--loop HOURS` | 定时循环:每隔 HOURS 小时跑一轮(隐含 --matrix) |
| `--max-runs` | (--loop)最多轮数,缺省不限 |
| `--browser` | 显式使用浏览器模式(v0.2 起即默认,此 flag 仅为可读性保留) |
| `--httpx` | 退回轻量 httpx 模式(无浏览器;被风控站点会立即停站) |
| `--browser-fallback` | (--httpx 模式)httpx 被风控停站后自动切换浏览器模式 |
| `--preflight` | 浏览器预热:打开各站点搜索页,人工完成验证后固化 profile |
| `--login` | 登录模式:使用登录态 profile(`browser_profile_login`);首次需 `--preflight --login` 完成扫码登录(自动弹登录页,登录成功自动继续) |
| `--user-data-dir` | (浏览器模式)用户数据目录,默认 `<output>/browser_profile` |
| `--stats` | 打印 SQLite 入库统计后退出 |
| `--clean` | 对输出目录的 *.jsonl 执行数据清洗,写入配套 cleaned 目录 |
| `--interactive` | 进入交互式控制台(无参数启动时自动进入) |
| `--i-understand-robots` | 确认知悉 robots 限制后继续(仅限个人低频研究) |

## 输出文件

`<output>`(默认 `jd-crawler/output/raw/`):

- `{site}_{keyword}_{ts}.jsonl` — 单次模式输出,一行一条职位 JSON;
- `{site}_matrix_{tag}_{ts}.jsonl` + `.json` — 矩阵模式双格式输出(`tag` 为 `browser`/`httpx`;JSONL 断点友好,`.json` 为缩进格式化数组便于人工审阅);
- `jd_crawler.sqlite3` — SQLite 表 `jobs`(按 `source:job_id` 去重;含 `keyword`/`search_city` 检索上下文列,老库自动 `ALTER TABLE` 补列);
- `checkpoint.json` — 断点续爬状态(已完成页 + 已采职位 ID);
- `run_summary_{ts}.json` — 矩阵每轮摘要(每组合状态与新增条数);
- `scheduler_state.json` — 定时轮次历史;
- `crawl.log` — 运行日志(含风控停止记录);
- `browser_profile/` — 浏览器持久化用户目录(验证状态固化于此)。

清洗输出(同级 `output/cleaned/`):

- `*.cleaned.json` — 清洗后的缩进格式化 JSON(与 raw 的 JSONL 一一对应);
- `clean_report.json` — 每文件读入/写出条数汇总。

退出码:`0` 正常完成;`2` 有站点被风控/robots 拦截、组合失败或异常中断。

## 字段说明

| 字段 | 说明 |
| --- | --- |
| `source` / `job_id` | 来源站点 / 站点内职位 ID(联合去重键) |
| `title` | 岗位名 |
| `salary` | 薪资原文(如 `1.5-2.5万/月`、`25-35k·19薪`) |
| `city` | 工作城市/地区 |
| `company_name` | 公司名 |
| `experience` / `education` | 经验 / 学历要求 |
| `publish_date` | 发布/刷新时间(51job 列表有;猎聘列表无,为 null) |
| `description` | JD 正文(已脱敏)。浏览器模式下 51job 由真实 API 的 `jobDescribe` 填充;httpx 路径 51job 恒为空串;猎聘详情主体为 CSR,SSR 正文存在时才填充 |
| `job_url` | 职位链接(已剥离跟踪参数) |
| `company_tags` | 公司标签(行业/规模等) |
| `keyword` / `search_city` | 检索上下文(本次采集所用关键词/城市,spider 产出时标注,便于矩阵入库后统计追溯) |
| `crawled_at` | 采集时间(UTC) |

## 实测结论(2026-08-13,本机非沙箱)

| 站点 | httpx 路径 | 浏览器模式(v0.2 主模式) |
| --- | --- | --- |
| 51job | 触发阿里云 WAF(punish-loc 风控跳转),按合规要求仅检测并停站,未绕过 | ✅ 实测成功:通过捕获浏览器自身发出的 `search-pc` API 响应拿到数据;真实 API 结构为 `resultbody.job.items` + `resultbody.job.totalCount`(驼峰字段 `jobId/jobName/provideSalaryString/jobAreaString/workYearString/degreeString/issueDateString/jobHref/jobDescribe`),`parse_search` 同时兼容旧公开结构 `resultbody.joblist` |
| 猎聘 | 游客搜索列表为 CSR,拿不到职位卡片(数据 API 需风控 token,不请求) | ✅ 实测成功:北京 / 算法工程师 1 页 40 条;渲染完成后复用 SSR 卡片解析器解析 DOM |

> 浏览器模式如遇人机验证,请在弹出的浏览器窗口中**手动完成**(默认等待 180 秒,超时按风控停站);可先跑 `--preflight` 预热固化 profile。一旦在 `crawl.log` 看到 "风控停止" 记录,请不要再继续请求该站点。

## 数据清洗

`--clean`(或交互菜单第 4 项)对 `output/raw/*.jsonl` 执行清洗链,结果写入 `output/cleaned/`。清洗算法接入点是 `jd_crawler/cleaning.py` 的 `Cleaner` 协议:任何实现 `clean(record: dict) -> dict | None` 的对象都可挂入清洗链(返回 `None` 表示丢弃该记录),传给 `CleaningPipeline(cleaners=[...])` 或 `run_cleaning(..., cleaners=[...])` 即可。内置清洗器均为非破坏性的:

| 清洗器 | 作用 |
| --- | --- |
| `WhitespaceCleaner` | 压缩各文本字段多余空白 |
| `SalaryNormCleaner` | 派生 `salary_norm` 字段(统一估算为 "X-Yk/月",原 `salary` 不动) |
| `CrossSourceDedupCleaner` | 跨站点按 (标题, 公司, 城市) 软去重,后到记录打 `dup_of` 标而不删除 |

## 项目结构

```
jd-crawler/
├── SPEC.md                  # 设计规格(架构/契约/schema/实测结论)
├── README.md
├── requirements.txt
├── pytest.ini
├── jd_crawler/
│   ├── cli.py               # 命令行入口(单次/矩阵/定时/清洗/统计/预热)
│   ├── interactive.py       # 交互式控制台(无参数启动进入)
│   ├── config.py            # 矩阵配置(12 城市 × 24 关键词,JSON 可覆盖)
│   ├── batch.py             # BatchRunner 矩阵批量执行器(组合级容错/双格式输出)
│   ├── scheduler.py         # 定时循环调度(--loop)
│   ├── cleaning.py          # 数据清洗层(Cleaner 协议 + 内置清洗器)
│   ├── models.py            # 统一 JD schema(pydantic,含 keyword/search_city)
│   ├── sanitize.py          # 联系方式脱敏
│   ├── ratelimit.py         # 限速 + 指数退避
│   ├── http.py              # httpx 客户端 + 风控检测
│   ├── robots.py            # robots 快照与警示
│   ├── pipeline.py          # JSONL/SQLite 双写 + 去重 + checkpoint + stats
│   └── spiders/
│       ├── base.py
│       ├── job51.py         # 51job(httpx):sign + search-pc API
│       ├── liepin.py        # 猎聘(httpx):搜索卡片 + 详情 TDK 解析
│       └── browser.py       # 浏览器模式(v0.2 主模式):BrowserSession/BrowserSpider/preflight
└── tests/
    ├── fixtures/            # 猎聘卡片/详情页、51job WAF 页为真实抓取;
    │                        # 51job API JSON 含按公开结构重建样例(已标注)
    └── test_*.py            # pytest,56 个用例
```

## 测试

```bash
python -m pytest --basetemp=.pytest_tmp   # 56 个用例,全部 mock/fixture,不触网
```

`--basetemp=.pytest_tmp` 是为规避沙箱对系统临时目录的权限限制;非沙箱环境可直接 `python -m pytest`。
