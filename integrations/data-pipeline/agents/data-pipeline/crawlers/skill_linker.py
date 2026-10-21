"""
职位关键词 → GitHub 搜索词映射

把中文岗位名称映射成适合 GitHub 搜索的英文技术关键词组合，
让求职者搜完 JD 后能自动找到相关的开源项目来学习技能。

这是一个静态映射表 + 简单查找函数，后续可扩展成调用 LLM 动态生成搜索词。
B站、知乎、arXiv 等模块也在后续用类似思路接入。
"""

# ── 岗位关键词 → GitHub 搜索查询映射 ──
# 每个岗位对应多个技术方向的搜索词，选 star 最高的仓库推荐给用户

JOB_TO_GITHUB_QUERIES: dict[str, list[str]] = {
    # ── 大数据方向 ──
    "大数据开发工程师": [
        "big-data+spark+hadoop",
        "flink+stream-processing",
        "data-engineering+etl",
        "hive+data-warehouse",
    ],
    "大数据工程师": [
        "big-data+spark+hadoop",
        "flink+stream-processing",
    ],
    "数据仓库工程师": [
        "data-warehouse+hive",
        "etl+pipeline",
    ],
    "Flink开发": ["flink+stream-processing"],
    "Spark开发": ["apache-spark+big-data"],

    # ── AI/机器学习方向 ──
    "算法工程师": [
        "machine-learning+deep-learning",
        "recommendation-system",
        "nlp+natural-language-processing",
        "computer-vision+deep-learning",
    ],
    "大模型工程师": [
        "large-language-model+llm",
        "langchain+rag",
        "llm fine-tuning+lora",
    ],
    "NLP工程师": ["nlp+transformers", "natural-language-processing"],
    "CV工程师": ["computer-vision+deep-learning", "object-detection+yolo"],
    "AI工程师": [
        "machine-learning+tutorial",
        "deep-learning+pytorch",
        "large-language-model",
    ],
    "机器学习工程师": ["machine-learning+mlops", "pytorch+deep-learning"],

    # ── 后端方向 ──
    "Java工程师": [
        "spring-boot+microservices",
        "java+backend+framework",
    ],
    "Java开发工程师": [
        "spring-boot+microservices",
        "java+backend+framework",
    ],
    "Python工程师": [
        "fastapi+web-framework",
        "django+python",
    ],
    "Go工程师": [
        "golang+microservices",
        "go+web-framework",
    ],
    "后端开发工程师": [
        "backend+microservices",
        "rest-api+graphql",
    ],

    # ── 前端方向 ──
    "前端开发工程师": [
        "react+typescript",
        "vue+frontend",
        "nextjs+fullstack",
    ],
    "Web前端": ["react+frontend", "vue+javascript"],

    # ── DevOps/云原生 ──
    "运维工程师": [
        "devops+docker+kubernetes",
        "infrastructure-as-code+terraform",
    ],
    "DevOps工程师": [
        "devops+ci-cd",
        "kubernetes+helm",
    ],
    "云原生工程师": [
        "cloud-native+kubernetes",
        "service-mesh+istio",
    ],

    # ── 数据方向 ──
    "数据分析师": [
        "data-analysis+pandas",
        "data-visualization",
    ],
    "数据分析工程师": [
        "data-analysis+python",
        "business-intelligence",
    ],

    # ── 通用 ──
    "软件工程师": ["awesome+list", "system-design"],
    "全栈工程师": ["fullstack+web+app", "nextjs+prisma"],
}


def get_queries(keyword: str) -> list[str]:
    """根据岗位关键词查找对应的 GitHub 搜索查询列表。

    支持精确和模糊匹配：
    - 精确命中映射表直接返回
    - 部分命中则返回匹配度最高的
    - 都没命中则把原始关键词当作搜索词返回
    """
    # 精确匹配
    if keyword in JOB_TO_GITHUB_QUERIES:
        return JOB_TO_GITHUB_QUERIES[keyword]

    # 模糊匹配 — 看关键词是否包含映射表中的岗位名
    best_match = None
    best_len = 0
    for job_key in JOB_TO_GITHUB_QUERIES:
        # 双向包含检查
        if job_key in keyword or keyword in job_key:
            if len(job_key) > best_len:
                best_match = job_key
                best_len = len(job_key)

    if best_match:
        return JOB_TO_GITHUB_QUERIES[best_match]

    # 兜底：用原始中文关键词去搜（GitHub 也支持中文搜索，但效果不如英文）
    return [keyword.replace(" ", "+")]


def format_repo_summary(repos: list) -> str:
    """把 GitHub 仓库列表格式化为可读的推荐摘要文本"""
    if not repos:
        return "未找到相关仓库"

    lines = []
    for i, repo in enumerate(repos, 1):
        stars = repo.stargazers_count
        lang = repo.language or "未知"
        desc = repo.description or "(暂无简介)"
        # 截断过长描述
        if len(desc) > 80:
            desc = desc[:77] + "..."

        lines.append(
            f"  [{i}] {repo.full_name}  ⭐{stars}  [{lang}]\n"
            f"      {desc}\n"
            f"      {repo.html_url}"
        )

    return "\n".join(lines)
