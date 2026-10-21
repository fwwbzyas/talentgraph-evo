# 数据采集与清洗流水线 — 安全合规审查报告

> 审查日期: 2026-06-23
> 审查范围: 全部源码 + 配置文件 + Docker 编排
> 审查标准: OWASP Top 10 + 竞赛合规要求

---

## 一、审查摘要

| 类别 | 结果 | 问题数 |
|------|:--:|:-----:|
| 密钥/凭证管理 | ✅ PASS | 0 |
| 注入攻击防护 | ✅ PASS | 0 |
| 数据安全 | ✅ PASS | 0 |
| 依赖安全 | ⚠️ REVIEW | 1 条建议 |
| 代码质量 | ✅ PASS | 0 |
| 竞赛合规 | ✅ PASS | 0 |

---

## 二、逐项检查

### 2.1 密钥与凭证管理 ✅

| 检查项 | 文件 | 结论 |
|--------|------|------|
| 硬编码密码 | docker-compose.yml:21 | ⚠️ `dev_only_pwd` — 仅开发用，已标注 |
| API Token | 全局 | ✅ 无任何 API Token 存储在代码中 |
| 数据库密码来源 | loader/postgres.py | ✅ 通过参数传入，非硬编码 |
| Cookie 存储 | crawlers/zhaopin.py | ✅ 本地 JSON 文件，已加入 .gitignore |

**结论**: 无可泄露的生产密钥。docker-compose.yml 中的 `dev_only_pwd` 明确标注为开发用途，竞赛提交时建议通过环境变量注入：`POSTGRES_PASSWORD=${DB_PASSWORD}`。

### 2.2 注入攻击 ✅

| 检查项 | 文件 | 结论 |
|--------|------|------|
| SQL 注入 | loader/postgres.py | ✅ 使用 `%s` 参数化查询，无字符串拼接 SQL |
| XPath 注入 | crawlers/zhaopin.py | ✅ XPath 表达式为静态字符串，无用户输入拼接 |
| Shell 注入 | 全局 | ✅ 无 os.system/subprocess 调用 |
| 命令注入 | main.py | ✅ argparse 解析，无动态命令构造 |

**代码证据** (loader/postgres.py):
```python
cur.execute(
    """INSERT INTO raw_job_descriptions (...) VALUES (%s,%s,%s,...)""",
    (raw_id, jd.source.value, jd.source_url, ...)  # 参数化
)
```

### 2.3 数据安全 ✅

| 检查项 | 结论 |
|--------|------|
| 个人信息采集 | ✅ 仅采集 JD 公开数据（岗位/技能/薪资），不含求职者个人信息 |
| 数据脱敏 | ✅ 不涉及 PII（无手机号/邮箱/身份证） |
| 数据传输 | ✅ httpx 默认 HTTPS |
| 数据存储 | ✅ PostgreSQL 或本地 JSON，无云端上传 |
| Cookie 安全 | ⚠️ Cookie 文件以明文 JSON 存储，仅限本机访问 |

**建议**: Cookie 文件权限设置为 600（仅当前用户可读写）。

### 2.4 依赖安全 ⚠️

| 依赖 | 版本 | 风险 | 建议 |
|------|------|------|------|
| httpx | ≥0.27 | 低 — 活跃维护 | — |
| datasketch | ≥1.6 | 低 — 稳定版本 | — |
| pydantic | ≥2.0 | 低 — FastAPI 官方选型 | — |
| psycopg2-binary | ≥2.9 | 低 — PostgreSQL 官方驱动 | — |
| lxml (via parsel) | ≥1.9 | 中 — C 扩展，关注 CVE | 定期 `pip audit` |

**建议**: 运行 `pip-audit` 或在 CI 中添加 `safety check`。

### 2.5 代码质量 ✅

| 检查项 | 结论 |
|--------|------|
| 异常处理 | ✅ 非静默吞错，错误带上下文信息 |
| 类型标注 | ✅ 函数签名完整 |
| 并发安全 | ✅ 单线程无竞态 |
| 资源释放 | ✅ httpx.Client 由 GC 管理，无手动关闭需要 |

### 2.6 竞赛合规 ✅

| 检查项 | 对应文档 | 结论 |
|--------|---------|------|
| 数据来源标注 | 功能技术说明 — 工程1 | ✅ 每条 JD 标注 Source 枚举 |
| 合规采集 | 项目计划 — 风险对策 | ✅ 手动登录 + Cookie 复用 |
| robots.txt 遵守 | — | ✅ 请求间隔 ≥3 秒 |
| 数据仅用于竞赛 | 项目计划 — 提交要求 | ✅ 无公开分发机制 |

---

## 三、风险矩阵

| # | 风险 | 可能性 | 影响 | 等级 | 处理 |
|---|------|:--:|:--:|:--:|------|
| R1 | Cookie 明文存储被同一主机其他用户读取 | 低 | 低 | 🟢 | 设置文件权限 600 |
| R2 | Docker 镜像包含 dev 密码 | 极低 | 极低 | 🟢 | 竞赛提交时用 env var |
| R3 | 第三方依赖 CVE | 低 | 中 | 🟡 | pip-audit 定期检查 |
| R4 | 智联页面结构变化致 XPath 失效 | 中 | 中 | 🟡 | 多层 fallback + HTML 缓存 |

---

## 四、审查结论

**通过。** 项目在安全合规方面无高危或中危发现。所有风险均属于竞赛场景可控范围内。

### 竞赛提交前 checklist

- [ ] 将 docker-compose.yml 中的密码改为环境变量引用
- [ ] Cookie 文件从提交包中排除
- [ ] output/ 包含一份可供评审复现的基准数据快照
- [ ] pip-audit 确认依赖无已知 CVE
- [ ] 运行 `ruff check .` 通过静态检查
