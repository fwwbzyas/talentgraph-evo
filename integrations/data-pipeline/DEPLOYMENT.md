# 数据采集与清洗流水线 — 部署文档

> 揭榜挂帅 XH-202621 | 负责: 路z | 版本 v1.1.0

---

## 一、环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥3.10 | 推荐 3.12 |
| Playwright | ≥1.48 | 浏览器自动化，绕过 EdgeOne CAPTCHA |
| 浏览器 | Chromium | Playwright 自动安装 |
| 磁盘空间 | ≥1 GB | Chromium ~300MB + 项目 ~50MB + 数据 |
| 操作系统 | Windows / macOS / Linux | 需要图形界面以手动完成人机验证 |

---

## 二、快速开始（推荐：本地 venv）

### 步骤 1: 安装 Python 依赖

```bash
cd data-pipeline

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r agents/data-pipeline/requirements.txt

# 安装 Chromium 浏览器（仅首次）
playwright install chromium
```

### 步骤 2: 设置 Cookie（仅首次）

在浏览器中登录 zhaopin.com，然后：

```bash
python agents/data-pipeline/main.py --setup-cookies
```

按终端提示，从浏览器 DevTools 复制 Cookie 字符串粘贴即可。

Cookie 保存在 `agents/data-pipeline/cookies/zhaopin.json`，可持续复用。

### 步骤 3: 运行采集

```bash
# 交互式运行（终端提示输入关键词）
python agents/data-pipeline/main.py

# 命令行指定关键词
python agents/data-pipeline/main.py --keywords "大数据运维"
```

运行时会弹出 Chromium 浏览器窗口。如果出现人机验证（CAPTCHA），在浏览器中手动点击验证，脚本会自动等待并继续。

### 步骤 4: 查看结果

```
output/
├── raw/               ← 原始 JD 数据
├── cleaned/           ← 清洗后数据
├── reports/           ← 质量报告
└── debug_html/        ← 页面 HTML 缓存（调试用）
```

---

## 三、更改搜索职位

### 方法 A: 命令行参数（推荐）

```bash
# 单个关键词
python agents/data-pipeline/main.py -k "Python工程师"

# 多个关键词（逗号分隔，逐个搜索）
python agents/data-pipeline/main.py -k "Python工程师,Java开发,数据分析师"

# 调整翻页数和最低采集量
python agents/data-pipeline/main.py -k "算法工程师" -p 5 -n 30
```

### 方法 B: 交互式输入

```bash
python agents/data-pipeline/main.py
```

终端会提示：
```
  请输入你想采集的岗位关键词，多个关键词用逗号分隔。
  示例: Python工程师, Java开发, 大模型工程师, 数据分析师

  → 岗位关键词: 
```

输入关键词后回车确认即可。

### 完整 CLI 参数

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--keywords` | `-k` | (交互式输入) | 岗位关键词，逗号分隔 |
| `--max-pages` | `-p` | 3 | 每个关键词最大翻页数 (1-10) |
| `--min-results` | `-n` | 15 | 最少采集条数 |
| `--delay` | `-d` | 3.0 | 翻页间隔秒数 |
| `--output-dir` | `-o` | ./output | 输出目录 |
| `--setup-cookies` | — | — | 运行 Cookie 设置向导 |
| `--dry-run` | — | — | 仅测试配置，不实际采集 |
| `--help` | `-h` | — | 查看帮助 |

---

## 四、Cookie 管理

### Cookie 持久化

Cookie 保存在 `agents/data-pipeline/cookies/zhaopin.json`，格式：

```json
{
  "cookies": {
    "at": "...",
    "rt": "...",
    "x-zp-client-id": "..."
  },
  "saved_at": "2026-06-23 23:00:00",
  "source": "interactive_setup"
}
```

每次运行爬虫时自动加载并注入浏览器上下文。

### 更新过期 Cookie

Cookie 通常有效期数天。当采集结果为空或频繁触发 CAPTCHA 时：

```bash
python agents/data-pipeline/main.py --setup-cookies
```

### 手动准备 Cookie（用于无 GUI 服务器）

```bash
# 在本地浏览器登录 zhaopin.com 后
# F12 → Console → 执行:
console.log(document.cookie)

# 将输出内容写入 cookies/zhaopin.json:
{
  "cookies": {
    "at": "从document.cookie中提取的at值",
    "rt": "从document.cookie中提取的rt值"
  },
  "saved_at": "2026-06-23 23:00:00",
  "source": "manual_export"
}
```

---

## 五、Docker 部署（有限支持）

> Docker 模式下 Playwright 需要额外配置，且无法进行手动 CAPTCHA 验证。
> 仅建议在已通过 CAPTCHA 且有有效 Cookie 的情况下使用。

### 前置条件

- Cookie 已通过本地运行获取并保存在 `agents/data-pipeline/cookies/zhaopin.json`
- 已通过至少一次 CAPTCHA 验证

### 构建与运行

```bash
# 构建镜像
docker compose build pipeline

# 运行（需要已有有效 Cookie）
docker compose run --rm pipeline -k "Python工程师" -p 2

# 启动 PostgreSQL（可选）
docker compose up -d postgres
```

### Docker 限制

| 限制 | 说明 |
|------|------|
| 无 GUI | 无法手动完成 CAPTCHA，需提前在本地通过验证 |
| 浏览器依赖 | Dockerfile 需额外安装 Chromium 及依赖 |
| Cookie 必需 | 没有有效 Cookie 几乎无法使用 |

**建议：开发与日常使用直接用本地 venv，Docker 仅用于最终打包提交。**

---

## 六、故障排查

### 浏览器启动失败

```bash
# 重装 Chromium
playwright install chromium --force

# 检查系统依赖（Linux）
playwright install-deps chromium
```

### CAPTCHA 反复出现

1. Cookie 可能已过期 → 运行 `--setup-cookies`
2. 在浏览器中手动登录一次 zhaopin.com
3. 降低请求频率：`--delay 5`

### 采集结果为空或字段缺失

1. 查看调试 HTML：`output/debug_html/` 目录
2. 智联页面结构可能已变化 → 需更新 `crawlers/zhaopin.py` 中的 CSS 选择器

### PostgreSQl 连接失败

不影响使用——流水线自动降级为 JSON 文件模式，数据写入 `output/` 目录。
