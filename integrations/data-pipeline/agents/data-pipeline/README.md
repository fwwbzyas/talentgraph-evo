# Data Pipeline Agent

## 职责
多源异构数据采集 → 清洗流水线 → 质量评分 → 入库，为下游 5 大 Agent 提供高质量结构化数据。

## Owner
路z（大三，数据 Lead）

## 输入
- 用户在终端交互式输入岗位关键词列表
- 手动设置的 Cookie 文件 (`cookies/zhaopin.json`)

## 输出
- `list[RawJobDescription]` — 原始 JD 数据
- `list[CleanedJobDescription]` — 清洗后结构化 JD
- `QualityReport` — 质量报告（去重率、质量分分布）

## 架构（参考 atlens-pipeline 分阶段设计）

```
Stage 0 · Config
  sources.yaml → 数据源配置

Stage 1 · Collect
  Crawler → 搜索列表页 → 解析 JD 摘要 → 存储原始数据

Stage 2 · Clean
  DedupAgent → QualityScorer → 去重 + 质量评分 + AI检测

Stage P · Publish Gate
  Pydantic Schema 校验 → 入库(PostgreSQL/JSON) → 质量报告
```

## 依赖
- 上游 Agent: 无（数据采集是最上游）
- 下游 Agent: Discover Agent、Define Agent、Validate Agent（通过 KG 消费清洗后数据）
- 外部服务: PostgreSQL（可选，有 JSON fallback）

## 本地运行

```bash
cd agents/data-pipeline

# 安装依赖
pip install -r requirements.txt

# 设置 Cookie（首次使用）
python main.py --setup-cookies

# 交互式运行
python main.py

# 查看帮助
python main.py --help
```

## Docker 运行

```bash
# 在 data-pipeline/ 根目录
docker compose up -d postgres   # 启动数据库（可选）
docker compose build pipeline   # 构建镜像
docker compose run pipeline     # 运行采集
```

## 测试

```bash
pytest tests/ -v --cov
```
