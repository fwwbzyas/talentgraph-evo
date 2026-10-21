# GitHub 仓库采集 & 技能关联推荐模块

## 职责

从 GitHub 获取指定领域的开源仓库信息，作为"职位关联技能推荐"的数据源。
搜完招聘 JD 后自动推荐相关的 GitHub 项目，帮助求职者找到可学习的实际代码。

## Owner

路z（数据 Lead）

## 模块文件

| 文件 | 职责 |
|------|------|
| `crawlers/github.py` | 调用 GitHub REST API 搜索仓库 |
| `crawlers/skill_linker.py` | 中文岗位名 → GitHub 搜索词映射 |
| `tests/test_github_and_linker.py` | 单元测试 |
| `tests/mocks/github_mock.py` | API mock 数据 |

## 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| keyword | str | 搜索关键词，如 "big-data+spark" |
| per_page | int | 每页数量，默认 10，最大 100 |
| max_results | int | 总共最多返回条数，默认 20 |
| token | str(可选) | GitHub Personal Access Token，未认证限速 60次/小时 |

## 输出

`list[GitHubRepo]`，每条包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| full_name | str | 完整仓库名 (owner/repo) |
| name | str | 仓库名 |
| owner | str | 所有者 |
| description | str | 项目简介 |
| language | str | 主要编程语言 |
| topics | list[str] | 仓库主题标签（领域分类） |
| stargazers_count | int | Star 数 |
| forks_count | int | Fork 数 |
| html_url | str | 仓库页面 URL |
| matched_keyword | str | 匹配的搜索关键词 |

## 依赖

- 上游: 无（独立模块）
- 下游: 前端技能推荐面板（后续开发）
- 外部: GitHub REST API (`https://api.github.com/search/repositories`)
- 关联: `crawlers/skill_linker.py`（岗位关键词映射）

## 本地运行

```bash
cd agents/data-pipeline

# 安装依赖
pip install requests

# 模式1: 独立 GitHub 搜索
python main.py --mode github --keywords "machine-learning"

# 模式2: 联动搜索（JD采集 + GitHub推荐）
python main.py --mode linked --keywords "大数据开发工程师"

# 使用 Token 提升限速
set GITHUB_TOKEN=ghp_xxxxxxxxxxxx
python main.py --mode github --keywords "big-data" --per-page 20
```

## 测试

```bash
pytest tests/test_github_and_linker.py -v
```

## 技能关键词映射（skill_linker.py 当前覆盖）

大数据方向: 大数据开发、数据仓库、Spark、Flink
AI方向: 算法工程师、大模型工程师、NLP、CV、机器学习
后端方向: Java、Python、Go、后端开发
前端方向: React、Vue、Web前端
DevOps: 运维、K8s、云原生
数据方向: 数据分析

新增映射直接编辑 `JOB_TO_GITHUB_QUERIES` 字典。

## 后续扩展

- B站: 搜相关技术教程视频
- 知乎: 搜相关技术问答/文章
- arXiv: 搜相关前沿论文

每个新数据源按同样模式接入: 新增爬虫文件 + 在 skill_linker 添加映射。
