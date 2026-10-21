"""命令行入口(SPEC §4.11/§4.16)。

单次抓取(兼容旧用法):
    python -m jd_crawler.cli --site liepin --keyword Python --pages 2 \
        --output output/raw --contact you@example.com

矩阵批量(12 城市 × 24 关键词 × 站点):
    python -m jd_crawler.cli --matrix --site all --pages 2

定时循环(每 24 小时一轮全矩阵):
    python -m jd_crawler.cli --matrix --loop 24

其他:
    python -m jd_crawler.cli              # 无参数 → 交互式控制台
    python -m jd_crawler.cli --stats      # 数据库统计
    python -m jd_crawler.cli --clean      # raw → cleaned 数据清洗
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from . import __version__, robots
from .batch import BatchRunner
from .cleaning import run_cleaning
from .config import MatrixConfig, load_matrix_config
from .exceptions import RiskControlError
from .http import HttpClient
from .pipeline import Checkpoint, DedupPipeline, JsonlWriter, SQLiteWriter
from .ratelimit import RateLimiter
from .scheduler import Scheduler
from .spiders import Job51Spider, LiepinSpider


def default_output_dir() -> Path:
    """默认输出目录:jd-crawler/output/raw(与 jd-crawler/output/cleaned 配套)。"""
    pkg_root = Path(__file__).resolve().parents[1]  # jd-crawler/
    return pkg_root / "output" / "raw"


def default_cleaned_dir(raw_dir: str | Path) -> Path:
    """raw 目录配套的 cleaned 目录(output/raw → output/cleaned)。"""
    raw = Path(raw_dir)
    if raw.name == "raw":
        return raw.parent / "cleaned"
    return raw / "cleaned"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jd-crawler",
        description="研究用途的公开职位 JD 采集(51job/猎聘)。"
                    "仅限研究,遵守 robots 与平台条款,控制频率。"
                    "无参数启动进入交互式控制台。",
    )
    p.add_argument("--site", choices=["51job", "liepin", "all"], default="all")
    p.add_argument("--keyword", default=None, help="搜索关键词(单次模式必填),如 算法工程师")
    p.add_argument("--city", default=None, help="城市名(内置码表),缺省全国")
    p.add_argument("--pages", type=int, default=None,
                   help="列表页数(单次默认 1,矩阵默认 2;51job 从 1 起,猎聘 curPage 从 0 起)")
    p.add_argument("--output", default=None,
                   help="输出目录(默认 <项目根>/output/raw,cleaned 与其同级)")
    p.add_argument("--delay", type=float, default=2.0,
                   help="请求间隔秒数(默认 2,另有 0.5~1.5s 抖动;下限 1.0,低于下限自动提升并告警)")
    p.add_argument("--combo-pause", type=float, default=6.0,
                   help="(矩阵)组合间额外暂停基准秒数,实际 0.5~1.5 倍抖动(默认 6)")
    p.add_argument("--contact", default="YOUR-EMAIL-PLACEHOLDER",
                   help="UA 中携带的联系信息(请替换为真实邮箱)")
    p.add_argument("--resume", dest="resume", action="store_true", default=True)
    p.add_argument("--no-resume", dest="resume", action="store_false")
    p.add_argument("--details", dest="details", action="store_true", default=None,
                   help="(猎聘)抓详情页(单次模式默认开,矩阵模式默认关)")
    p.add_argument("--no-details", dest="details", action="store_false",
                   help="(猎聘)不抓详情页,只保留列表卡片字段")
    p.add_argument("--matrix", action="store_true",
                   help="按矩阵批量抓取:站点 × 12 城市 × 24 关键词(可用 --config 覆盖)")
    p.add_argument("--config", default=None,
                   help="矩阵配置 JSON(cities/keyword_groups/keywords/sites/pages)")
    p.add_argument("--loop", type=float, default=None, metavar="HOURS",
                   help="定时循环:每隔 HOURS 小时自动跑一轮(隐含 --matrix)")
    p.add_argument("--max-runs", type=int, default=None,
                   help="(--loop)最多轮数,缺省不限")
    p.add_argument("--stats", action="store_true", help="打印 SQLite 入库统计后退出")
    p.add_argument("--clean", action="store_true",
                   help="对输出目录的 *.jsonl 执行数据清洗,写入配套 cleaned 目录")
    p.add_argument("--browser", action="store_true",
                   help="显式使用浏览器模式(自 v0.2 起即默认,此 flag 仅为可读性保留)")
    p.add_argument("--httpx", action="store_true",
                   help="退回轻量 httpx 模式(无浏览器;被风控站点会立即停站)")
    p.add_argument("--browser-fallback", action="store_true",
                   help="(--httpx 模式)httpx 被风控停站后自动切换浏览器模式")
    p.add_argument("--preflight", action="store_true",
                   help="浏览器预热:打开各站点搜索页,人工完成验证后固化 profile,供定时轮跑复用")
    p.add_argument("--login", action="store_true",
                   help="登录模式:使用登录态 profile(browser_profile_login);"
                        "首次需先 --preflight --login 完成扫码/登录")
    p.add_argument("--user-data-dir", default=None,
                   help="(浏览器模式)浏览器用户数据目录,默认 <output>/browser_profile(_login)")
    p.add_argument("--interactive", action="store_true", help="进入交互式控制台")
    p.add_argument("--i-understand-robots", action="store_true",
                   help="确认已知悉目标 URL 的 robots 限制并仅为个人研究低频使用")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def setup_logging(out_dir: Path) -> logging.Logger:
    log = logging.getLogger("jd_crawler")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        log.addHandler(sh)
    fh = logging.FileHandler(out_dir / "crawl.log", encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    return log


def _robots_guard(site: str, keyword: str, understood: bool, log: logging.Logger) -> bool:
    """对站点典型目标 URL 做 robots 警示;返回是否继续。"""
    sample = {
        "51job": "https://we.51job.com/api/job/search-pc?api_key=51job",
        "liepin": f"https://www.liepin.com/zhaopin/?key={keyword}&curPage=0",
    }[site]
    v = robots.check(sample)
    if not v.allowed:
        log.warning("robots 警示[%s]: %s (%s)", site, v.note, v.rule)
        if not understood:
            log.error(
                "目标 URL 被 %s robots.txt 禁止。如确为个人研究且低频,请加 "
                "--i-understand-robots 后重试;否则已停止。", site,
            )
            return False
    elif v.note:
        log.info("robots 提示[%s]: %s", site, v.note)
    return True


def run_single(args, out_dir: Path, log: logging.Logger) -> int:
    """单次抓取(旧行为):站点 × 单关键词 × 单城市。"""
    sites = ["51job", "liepin"] if args.site == "all" else [args.site]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    checkpoint = Checkpoint(out_dir / "checkpoint.json")
    if not args.resume:
        checkpoint.done_pages.clear()
        checkpoint.done_jobs.clear()

    fetch_details = True if args.details is None else args.details
    use_browser = not args.httpx  # v0.2 起浏览器为主模式
    rc_interrupted = False
    for site in sites:
        if not _robots_guard(site, args.keyword, args.i_understand_robots, log):
            rc_interrupted = True
            continue
        jsonl = JsonlWriter(out_dir / f"{site}_{args.keyword}_{ts}.jsonl")
        sqlite = SQLiteWriter(out_dir / "jd_crawler.sqlite3")
        pipeline = DedupPipeline(jsonl, sqlite)
        rl = RateLimiter(interval=args.delay)
        session = None
        http = None
        if use_browser:
            from .spiders.browser import BrowserSession, BrowserSpider, profile_dir
            session = BrowserSession(
                args.user_data_dir or profile_dir(out_dir, login=args.login),
                rate_limiter=rl,
            )
            session.__enter__()
            spider = BrowserSpider(session, site)
        else:
            http = HttpClient(site, rl, contact=args.contact)
            spider = (Job51Spider(http) if site == "51job"
                      else LiepinSpider(http, fetch_details=fetch_details))
        count = 0
        try:
            for job in spider.iter_jobs(args.keyword, args.city, args.pages, checkpoint):
                if pipeline.process(job):
                    checkpoint.mark_job(job)
                    count += 1
                    log.info("[%s] 入库 %s | %s | %s | %s",
                             site, job.job_id, job.title, job.salary, job.city)
            log.info("[%s] 完成,新增 %d 条", site, count)
        except RiskControlError as e:
            rc_interrupted = True
            log.error("风控停止: %s", e)
            log.error("已按合规要求停止站点 %s;checkpoint 已保存,可稍后 --resume 续爬。", site)
        except Exception:
            log.exception("[%s] 抓取异常终止", site)
            rc_interrupted = True
        finally:
            checkpoint.save()
            pipeline.close()
            if http is not None:
                http.close()
            if session is not None:
                session.__exit__(None, None, None)

    return 2 if rc_interrupted else 0


def run_matrix(args, out_dir: Path, log: logging.Logger) -> int:
    cfg = load_matrix_config(args.config)
    if args.site != "all":
        cfg.sites = [args.site]
    if args.pages is not None:
        cfg.pages = args.pages
    fetch_details = bool(args.details)  # 矩阵默认不抓详情
    from .spiders.browser import profile_dir
    runner = BatchRunner(
        cfg, out_dir,
        delay=args.delay,
        combo_pause=args.combo_pause,
        contact=args.contact,
        fetch_details=fetch_details,
        robots_ack=args.i_understand_robots,
        use_browser=not args.httpx,  # v0.2 起浏览器为主模式
        browser_fallback=args.browser_fallback,
        user_data_dir=args.user_data_dir or profile_dir(out_dir, login=args.login),
    )
    if args.loop is None:
        summary = runner.run()
    else:
        log.info("定时循环模式:每 %.1f 小时一轮全矩阵(%d 组合/轮)。",
                 args.loop, cfg.combo_count())
        sched = Scheduler(
            runner.run,
            interval_hours=args.loop,
            max_runs=args.max_runs,
            state_path=out_dir / "scheduler_state.json",
        )
        sched.run()
        summary = None
    # 风控停站或组合失败 → 退出码 2
    if summary is not None and not summary.risk_stopped_sites and summary.failed == 0:
        return 0
    if summary is None:
        return 0
    return 2


def do_stats(out_dir: str | Path) -> None:
    db = Path(out_dir) / "jd_crawler.sqlite3"
    if not db.exists():
        print(f"未找到数据库: {db}")
        return
    w = SQLiteWriter(db)
    try:
        s = w.stats()
    finally:
        w.close()
    print(f"总条数: {s['total']}")
    print(f"首条采集: {s['first_crawled']}  最近采集: {s['last_crawled']}")
    print("按站点:", {k: v for k, v in s["by_source"].items()})
    if s["by_search_city"]:
        print("按检索城市 TOP:", s["by_search_city"][:12])
    if s["by_keyword"]:
        print("按关键词 TOP:", s["by_keyword"][:24])


def do_clean(out_dir: str | Path) -> None:
    cleaned = default_cleaned_dir(out_dir)
    report = run_cleaning(out_dir, cleaned)
    if not report:
        print(f"没有可清洗的文件({out_dir}/*.jsonl)")
        return
    for name, r in report.items():
        print(f"{name}: {r['in']} -> {r['out']}  →  {r['path']}")
    print(f"清洗报告: {cleaned / 'clean_report.json'}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # 无参数(或显式 --interactive)→ 交互式控制台
    if args.interactive or (argv is not None and not argv) or (
        argv is None and len(sys.argv) == 1
    ):
        from .interactive import run_interactive
        run_interactive(str(default_output_dir()))
        return 0

    out_dir = Path(args.output) if args.output else default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    log = setup_logging(out_dir)

    if args.stats:
        do_stats(out_dir)
        return 0
    if args.clean:
        do_clean(out_dir)
        return 0
    if args.preflight:
        from .spiders.browser import login_warmup, preflight, profile_dir
        sites = ("51job", "liepin") if args.site == "all" else (args.site,)
        udd = args.user_data_dir or profile_dir(out_dir, login=args.login)
        if args.login:
            results = login_warmup(udd, sites)
        else:
            results = preflight(udd, sites)
        for site, status in results.items():
            print(f"{site}: {status}")
        return 0 if all(v == "ok" for v in results.values()) else 2

    # 限速下限保护:防止误设过低频率对目标站造成压力
    if args.delay < 1.0:
        log.warning("--delay=%.2f 低于下限 1.0s,已自动提升为 1.0s(合规限速保护)。", args.delay)
        args.delay = 1.0

    if args.matrix or args.loop is not None:
        if args.login and args.httpx:
            log.warning("--login 仅对浏览器模式有效;httpx 模式不携带登录态,已忽略。")
        return run_matrix(args, out_dir, log)

    if not args.keyword:
        log.error("单次模式必须提供 --keyword;或使用 --matrix / 无参数进入交互式控制台。")
        return 2
    if args.login and args.httpx:
        log.warning("--login 仅对浏览器模式有效;httpx 模式不携带登录态,已忽略。")
    if args.pages is None:
        args.pages = 1
    return run_single(args, out_dir, log)


if __name__ == "__main__":
    raise SystemExit(main())
