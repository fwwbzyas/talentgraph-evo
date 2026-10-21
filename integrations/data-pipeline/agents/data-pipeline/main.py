#!/usr/bin/env python3
"""
数据采集与清洗流水线 — CLI 入口

架构参考 atlens-pipeline 分阶段设计:
  Stage 0: 加载 sources.yaml 配置
  Stage 1: 爬虫采集（ZhaopinCrawler）
  Stage 2: 数据清洗（DedupAgent + QualityScorer）
  Stage P: Schema 校验 + 入库 + 质量报告

用法:
  python main.py                     # 交互式：在终端输入岗位关键词
  python main.py --keywords "Python工程师,Java工程师,大模型工程师"
  python main.py --setup-cookies     # 设置智联招聘 Cookie
  python main.py --output-dir ./output

工作流程:
  1. 用户在终端输入感兴趣的岗位关键词
  2. 爬虫采集智联招聘搜索结果（列表页摘要）
  3. 去重（MinHash LSH）
  4. 质量评分（完整度 + 原创度 + 新鲜度 + 信息量）
  5. AI 生成检测（统计特征）
  6. 输出原始数据 JSON + 清洗数据 JSON + 质量报告 JSON
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# 将项目根目录加入 sys.path，方便直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contracts.data_schema import CrawlConfig, QualityReport, QualityLevel
from crawlers import ZhaopinCrawler, GitHubCrawler, get_queries, format_repo_summary
from pipeline import DedupAgent, QualityScorer
from loader import DataLoader


# ═══════════════════════════════════════════════
# 职位关联技能推荐 — GitHub 仓库搜索
# ═══════════════════════════════════════════════

def run_github_search(
    keywords: list[str],
    per_page: int = 10,
    max_results: int = 20,
    github_token: str = "",
):
    """独立的 GitHub 仓库搜索：直接用关键词搜索开源项目。"""
    print("\n" + "=" * 64)
    print("  GitHub 仓库搜索 — 职位关联技能推荐")
    print("=" * 64)
    print(f"  搜索关键词: {', '.join(keywords)}")

    crawler = GitHubCrawler(token=github_token or None)

    all_repos: list = []
    for kw in keywords:
        print(f"\n  [搜索] {kw}")
        repos = crawler.search(kw, per_page=per_page, max_results=max_results)
        print(f"  -> 找到 {len(repos)} 个仓库")
        all_repos.extend(repos)

    if not all_repos:
        print("\n  未找到匹配的仓库。")
        return

    # 去重（按 repo_id）
    seen_ids = set()
    unique_repos = []
    for r in all_repos:
        if r.repo_id not in seen_ids:
            seen_ids.add(r.repo_id)
            unique_repos.append(r)

    # 按 star 数排序
    unique_repos.sort(key=lambda r: r.stargazers_count, reverse=True)

    print(f"\n{'=' * 64}")
    print(f"  共找到 {len(unique_repos)} 个不重复仓库")
    print(f"{'=' * 64}\n")
    print(format_repo_summary(unique_repos[:max_results]))
    print()

    # 保存结果到 JSON
    output_dir = Path("./output/github")
    output_dir.mkdir(parents=True, exist_ok=True)
    import json as _json
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"github_repos_{timestamp}.json"
    data = [r.model_dump(mode="json") for r in unique_repos]
    with open(filepath, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  结果已保存: {filepath}\n")


def run_linked_search(
    job_keywords: list[str],
    per_page: int = 5,
    max_results: int = 15,
    github_token: str = "",
):
    """联动模式：先搜智联招聘 JD，再自动关联 GitHub 仓库推荐。

    流程:
      1. 按岗位关键词采集智联招聘 JD
      2. 每个岗位关键词通过 SkillLinker 映射到 GitHub 搜索查询
      3. 搜索 GitHub 仓库并展示推荐结果
    """
    print("\n" + "=" * 64)
    print("  联动搜索 — 招聘JD + GitHub技能推荐")
    print("  揭榜挂帅 XH-202621 — 职位关联技能推荐模块（原型）")
    print("=" * 64)

    # ── 阶段 1: 采集 JD ──
    print(f"\n{'─' * 40}")
    print(f"  [阶段 1/2] 智联招聘 JD 采集")
    print(f"{'─' * 40}")

    config = CrawlConfig(
        keywords=job_keywords,
        max_pages=1,
        min_results=5,
        request_delay=3.0,
        timeout=30,
        output_dir="./output",
    )

    try:
        crawler = ZhaopinCrawler(config)
        raw_jds = crawler.collect()
    except Exception as e:
        print(f"  [警告] JD 采集失败: {e}")
        print("  -> 将跳过 JD 采集，直接用关键词搜索 GitHub...")
        raw_jds = []

    if raw_jds:
        print(f"  采集到 {len(raw_jds)} 条 JD")
        # 简单去重
        dedup = DedupAgent(threshold=0.85)
        raw_jds = dedup.deduplicate(raw_jds)
        print(f"  去重后: {len(raw_jds)} 条")

    # ── 阶段 2: GitHub 技能推荐 ──
    print(f"\n{'─' * 40}")
    print(f"  [阶段 2/2] GitHub 关联项目推荐")
    print(f"{'─' * 40}")

    github = GitHubCrawler(token=github_token or None)
    all_repos: list = []

    for kw in job_keywords:
        # 用 SkillLinker 把岗位名转成 GitHub 搜索词
        queries = get_queries(kw)
        print(f"\n  [{kw}] 映射到 {len(queries)} 组搜索词:")

        for q in queries[:3]:  # 最多取前 3 组搜索词，避免请求过多
            print(f"    -> 搜索: {q}")
            repos = github.search(q, per_page=per_page, max_results=max_results // len(queries))
            all_repos.extend(repos)
            print(f"       找到 {len(repos)} 个仓库")

    # 去重 + 排序
    seen_ids = set()
    unique_repos = []
    for r in all_repos:
        if r.repo_id not in seen_ids:
            seen_ids.add(r.repo_id)
            unique_repos.append(r)
    unique_repos.sort(key=lambda r: r.stargazers_count, reverse=True)

    # ── 汇总输出 ──
    print(f"\n{'=' * 64}")
    print(f"  联动搜索完成!")
    print(f"  JD 采集: {len(raw_jds)} 条")
    print(f"  GitHub 推荐: {len(unique_repos)} 个仓库")
    print(f"{'=' * 64}\n")
    print(format_repo_summary(unique_repos[:max_results]))
    print()

    # 保存
    output_dir = Path("./output/linked")
    output_dir.mkdir(parents=True, exist_ok=True)
    import json as _json
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 保存 JD
    if raw_jds:
        jd_path = output_dir / f"jobs_{timestamp}.json"
        jd_data = [jd.model_dump(mode="json") for jd in raw_jds]
        with open(jd_path, "w", encoding="utf-8") as f:
            _json.dump(jd_data, f, ensure_ascii=False, indent=2, default=str)
        print(f"  JD数据已保存: {jd_path}")

    # 保存 GitHub 推荐
    gh_path = output_dir / f"github_recommendations_{timestamp}.json"
    gh_data = [r.model_dump(mode="json") for r in unique_repos]
    with open(gh_path, "w", encoding="utf-8") as f:
        _json.dump(gh_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  GitHub推荐已保存: {gh_path}")
    print()


# ═══════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════

def run_pipeline(
    keywords: list[str],
    output_dir: str = "./output",
    max_pages: int = 3,
    min_results: int = 15,
    request_delay: float = 3.0,
):
    """
    执行完整的数据采集 → 清洗 → 入库流水线。

    对应项目计划 P1 阶段（数据采集与解析 MVP）的端到端验证目标。
    """
    print("\n" + "=" * 64)
    print("  数据采集与清洗流水线 v1.1")
    print("  揭榜挂帅 XH-202621 — 多源异构数据驱动岗位能力图谱")
    print("  负责: 路z")
    print("=" * 64)

    # ── Stage 0: 加载配置 ─────────────────
    config = CrawlConfig(
        keywords=keywords,
        max_pages=max_pages,
        min_results=min_results,
        request_delay=request_delay,
        timeout=30,
        output_dir=output_dir,
    )
    print(f"\n[Stage 0] 配置已加载")
    print(f"  关键词: {', '.join(config.keywords)}")
    print(f"  目标: 至少 {config.min_results} 条")
    print(f"  请求间隔: {config.request_delay}s")

    # ── Stage 1: 数据采集 ─────────────────
    print(f"\n[Stage 1] 开始采集 — 数据源: 智联招聘")

    crawler = ZhaopinCrawler(config)
    raw_jds = crawler.collect()

    if not raw_jds:
        print("\n[错误] 未采集到任何数据!")
        print("  可能原因:")
        print("  1. Cookie 未设置或已过期 → 运行 python main.py --setup-cookies")
        print("  2. 关键词无搜索结果")
        print("  3. 智联招聘页面结构变化（需要更新 XPath）")
        sys.exit(1)

    print(f"\n[Stage 1] 采集完成: 共 {len(raw_jds)} 条原始 JD")

    # ── Stage 2: 数据清洗 ─────────────────
    print(f"\n[Stage 2] 开始清洗...")

    # 2a: 去重
    dedup = DedupAgent(threshold=0.85)
    unique_jds = dedup.deduplicate(raw_jds)
    dedup_removed = len(raw_jds) - len(unique_jds)
    print(f"  去重: {len(raw_jds)} → {len(unique_jds)} (移除 {dedup_removed} 条)")

    # 2b: 质量评分
    scorer = QualityScorer()
    cleaned_jds = scorer.score_batch(unique_jds)

    # 质量分布统计
    distribution: dict[QualityLevel, int] = {}
    for jd in cleaned_jds:
        distribution[jd.quality_level] = distribution.get(jd.quality_level, 0) + 1

    avg_score = sum(jd.quality_score for jd in cleaned_jds) / len(cleaned_jds)

    print(f"  平均质量分: {avg_score:.1f}/100")
    print(f"  质量分布: HIGH={distribution.get(QualityLevel.HIGH, 0)} "
          f"MEDIUM={distribution.get(QualityLevel.MEDIUM, 0)} "
          f"LOW={distribution.get(QualityLevel.LOW, 0)}")

    # ── Stage P: 入库 + 报告 ─────────────────
    print(f"\n[Stage P] 入库 + 质量报告")

    loader = DataLoader(output_dir=output_dir)

    # 保存原始数据
    loader.save_raw(raw_jds)

    # 保存清洗数据
    loader.save_cleaned(cleaned_jds)

    # 生成质量报告
    report = QualityReport(
        total_raw=len(raw_jds),
        total_cleaned=len(cleaned_jds),
        dedup_removed=dedup_removed,
        dedup_rate=round(dedup_removed / max(len(raw_jds), 1), 3),
        noise_removed=0,
        avg_quality_score=round(avg_score, 1),
        quality_distribution=distribution,
    )
    loader.save_report(report)

    # ── 摘要输出 ─────────────────────────
    print(f"\n{'=' * 64}")
    print(f"  流水线完成!")
    print(f"  原始数据: {report.total_raw} 条")
    print(f"  去重移除: {report.dedup_removed} 条 ({report.dedup_rate:.1%})")
    print(f"  清洗后:   {report.total_cleaned} 条")
    print(f"  平均质量: {report.avg_quality_score}/100")
    print(f"  输出目录: {Path(output_dir).resolve()}")
    print(f"{'=' * 64}\n")

    # 打印前 3 条预览
    print("─" * 60)
    print("  数据预览 (前 3 条)")
    print("─" * 60)
    for i, jd in enumerate(cleaned_jds[:3], 1):
        print(f"\n  [{i}] {jd.title}")
        print(f"      公司: {jd.company or '未知'}")
        print(f"      质量分: {jd.quality_score}/100 ({jd.quality_level.value})")
        print(f"      AI生成概率: {jd.cleaning_trace.ai_generated_score:.2f}")
        if jd.description_clean:
            preview = jd.description_clean[:120].replace('\n', ' ')
            print(f"      描述: {preview}...")
    print()


# ═══════════════════════════════════════════════
# 交互式输入
# ═══════════════════════════════════════════════

def interactive_keywords() -> list[str]:
    """交互式获取用户输入的岗位关键词"""
    print("\n" + "=" * 60)
    print("  智联招聘岗位数据采集")
    print("=" * 60)
    print()
    print("  请输入你想采集的岗位关键词，多个关键词用逗号分隔。")
    print("  示例: Python工程师, Java开发, 大模型工程师, 数据分析师")
    print()

    while True:
        raw = input("  → 岗位关键词: ").strip()
        if not raw:
            print("  请输入至少一个关键词!")
            continue

        keywords = [kw.strip() for kw in raw.split(",") if kw.strip()]
        if not keywords:
            print("  输入无效，请重试!")
            continue

        # 确认
        print()
        print(f"  将采集以下 {len(keywords)} 个关键词的数据:")
        for i, kw in enumerate(keywords, 1):
            print(f"    {i}. {kw}")
        print()
        confirm = input("  确认开始? [Y/n]: ").strip().lower()
        if confirm in ("", "y", "yes"):
            return keywords
        print("  已取消，请重新输入。\n")


# ═══════════════════════════════════════════════
# Cookie 设置向导
# ═══════════════════════════════════════════════

def setup_cookies():
    """
    引导用户设置智联招聘 Cookie。

    步骤:
      1. 打开浏览器访问 zhaopin.com
      2. 登录（扫码或手机验证码）
      3. 打开 DevTools (F12) → Application → Cookies → www.zhaopin.com
      4. 复制所有 Cookie 字符串
      5. 粘贴到终端
    """
    print("\n" + "=" * 60)
    print("  智联招聘 Cookie 设置向导")
    print("=" * 60)
    print()
    print("  请按以下步骤操作:")
    print()
    print("  1. 打开浏览器，访问 https://www.zhaopin.com")
    print("  2. 登录你的智联招聘账号（手机扫码或验证码）")
    print("  3. 登录后按 F12 打开开发者工具")
    print("  4. 进入 Application → Cookies → www.zhaopin.com")
    print("  5. 复制所有 Cookie（选中全部 → 右键 Copy）")
    print("  6. 或者: 在 Console 中执行 document.cookie 并复制结果")
    print()
    print("  Cookie 示例格式:")
    print('  "at=xxx; rt=yyy; acw_tc=zzz; ..."')
    print()

    cookie_string = input("  请粘贴 Cookie 字符串: ").strip()

    if not cookie_string:
        print("  [取消] 未输入任何内容。")
        return

    from crawlers.zhaopin import ZhaopinCrawler

    ZhaopinCrawler.save_cookies_from_browser(cookie_string)
    print()
    print("  Cookie 设置完成! 现在可以运行 python main.py 开始采集。")
    print()


# ═══════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="数据采集与清洗流水线 ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                                                   # 交互式运行（智联招聘）
  python main.py --keywords "Python,Java,AI工程师"                 # 命令行指定关键词
  python main.py --mode github --keywords "machine-learning"       # GitHub 仓库搜索
  python main.py --mode linked --keywords "大数据开发工程师"        # 联动: JD采集 + GitHub推荐
  python main.py --setup-cookies                                   # 设置 Cookie
  python main.py --output-dir ./my_results                         # 自定义输出目录
        """,
    )

    parser.add_argument(
        "--mode", "-m",
        type=str,
        default="zhaopin",
        choices=["zhaopin", "github", "linked"],
        help="运行模式: zhaopin(招聘采集) github(仓库搜索) linked(联动搜索) (默认: zhaopin)",
    )
    parser.add_argument(
        "--keywords", "-k",
        type=str,
        help="关键词，多个用逗号分隔。不指定则交互式输入",
    )
    parser.add_argument(
        "--max-pages", "-p",
        type=int,
        default=3,
        help="每个关键词的最大翻页数 (默认: 3, zhaopin/linked 模式)",
    )
    parser.add_argument(
        "--min-results", "-n",
        type=int,
        default=15,
        help="最少采集条数 (默认: 15, zhaopin 模式)",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=3.0,
        help="请求间隔/秒 (默认: 3.0, zhaopin 模式)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="./output",
        help="输出目录 (默认: ./output)",
    )
    parser.add_argument(
        "--setup-cookies",
        action="store_true",
        help="运行 Cookie 设置向导",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅测试配置，不实际采集",
    )
    parser.add_argument(
        "--github-token",
        type=str,
        default="",
        help="GitHub Personal Access Token (提升API限速至5000次/小时)",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=10,
        help="GitHub 搜索每页数量 (默认: 10, github/linked 模式)",
    )

    args = parser.parse_args()

    # Cookie 设置模式
    if args.setup_cookies:
        setup_cookies()
        return

    # 获取关键词
    if args.keywords:
        keywords = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
        if not keywords:
            print("错误: --keywords 参数格式不正确")
            sys.exit(1)
    else:
        # GitHub/linked 模式也可以交互式输入
        keywords = interactive_keywords()

    if not keywords:
        print("未指定关键词，退出。")
        sys.exit(0)

    if args.dry_run:
        print(f"\n[Dry Run] mode={args.mode} keywords={', '.join(keywords)}")
        return

    # ── 按模式分发 ──
    if args.mode == "github":
        run_github_search(
            keywords=keywords,
            per_page=args.per_page,
            max_results=args.min_results,
            github_token=args.github_token,
        )
    elif args.mode == "linked":
        run_linked_search(
            job_keywords=keywords,
            per_page=args.per_page,
            max_results=args.min_results,
            github_token=args.github_token,
        )
    else:
        # zhaopin 模式 — 原有流程
        run_pipeline(
            keywords=keywords,
            output_dir=args.output_dir,
            max_pages=args.max_pages,
            min_results=args.min_results,
            request_delay=args.delay,
        )


if __name__ == "__main__":
    main()
