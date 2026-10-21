"""批量矩阵抓取执行器(SPEC §4.13)。

遍历 站点 × 城市 × 关键词 组合(默认 2 × 12 × 24 = 576 组合/轮),
具备:

- **组合级容错隔离**:单组合 FetchError/解析异常只记失败并继续;
  RiskControlError 按合规护栏**停止整个站点**,另一站点不受影响。
- **组合间额外暂停**(带抖动),叠加在请求级限速之上,进一步压低频率。
- **fresh_pages 语义**:每轮开始清空 done_pages(保留 done_jobs 去重集),
  保证定时轮跑时页面会被重新抓取以发现新职位,同时不产生重复入库。
- **运行摘要**:run_summary_{ts}.json 记录每组合状态与新增条数。
- **双格式输出**:流式 JSONL(断点友好) + 缩进格式化的 JSON 数组(便于人工审阅)。
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from . import robots
from .config import MatrixConfig
from .exceptions import FetchError, RiskControlError
from .http import HttpClient
from .models import JobPosting
from .pipeline import Checkpoint, DedupPipeline, JsonlWriter, SQLiteWriter
from .ratelimit import RateLimiter
from .spiders import Job51Spider, LiepinSpider

logger = logging.getLogger("jd_crawler.batch")


@dataclass
class ComboResult:
    site: str
    city: str
    keyword: str
    status: str = "ok"  # ok | empty | failed | risk_stopped | skipped_robots
    new_jobs: int = 0
    error: str = ""


@dataclass
class RunSummary:
    run_id: str
    started_at: str
    finished_at: str = ""
    combos: list[ComboResult] = field(default_factory=list)

    @property
    def new_jobs(self) -> int:
        return sum(c.new_jobs for c in self.combos)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.combos if c.status == "failed")

    @property
    def risk_stopped_sites(self) -> list[str]:
        return sorted({c.site for c in self.combos if c.status == "risk_stopped"})

    def to_dict(self) -> dict:
        d = asdict(self)
        d["new_jobs"] = self.new_jobs
        d["failed_combos"] = self.failed
        d["risk_stopped_sites"] = self.risk_stopped_sites
        return d


class JsonArrayWriter:
    """缩进格式化 JSON 数组输出(每轮一个文件,便于人工审阅/下游清洗)。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[dict] = []

    def write(self, job: JobPosting) -> None:
        self._items.append(job.model_dump(mode="json"))

    def close(self) -> None:
        self.path.write_text(
            json.dumps(self._items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _default_http_factory(site: str, rl: RateLimiter, contact: str) -> HttpClient:
    return HttpClient(site, rl, contact=contact)


class BatchRunner:
    """矩阵批量抓取。输出与 checkpoint 均落在 out_dir(默认 output/raw/)。"""

    def __init__(
        self,
        config: MatrixConfig,
        out_dir: str | Path,
        *,
        delay: float = 2.0,
        combo_pause: float = 6.0,
        contact: str = "YOUR-EMAIL-PLACEHOLDER",
        fetch_details: bool = False,
        robots_ack: bool = False,
        fresh_pages: bool = True,
        use_browser: bool = False,
        browser_fallback: bool = False,
        user_data_dir: str | Path | None = None,
        http_factory: Callable[[str, RateLimiter, str], HttpClient] = _default_http_factory,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.config = config
        self.out_dir = Path(out_dir)
        self.delay = max(delay, 1.0)
        self.combo_pause = combo_pause
        self.contact = contact
        self.fetch_details = fetch_details
        self.robots_ack = robots_ack
        self.fresh_pages = fresh_pages
        self.use_browser = use_browser
        self.browser_fallback = browser_fallback
        self.user_data_dir = Path(
            user_data_dir or self.out_dir / "browser_profile"
        )
        self.http_factory = http_factory
        self.sleep = sleep

    def _make_spider(self, site: str, http: HttpClient):
        if site == "51job":
            return Job51Spider(http)
        return LiepinSpider(http, fetch_details=self.fetch_details)

    def _robots_allows(self, site: str) -> bool:
        sample = {
            "51job": "https://we.51job.com/api/job/search-pc?api_key=51job",
            "liepin": "https://www.liepin.com/zhaopin/?key=x&curPage=0",
        }[site]
        v = robots.check(sample)
        if not v.allowed:
            logger.warning("robots 警示[%s]: %s (%s)", site, v.note, v.rule)
            if not self.robots_ack:
                logger.error(
                    "站点 %s 目标 URL 被 robots.txt 禁止,且未确认(--i-understand-robots);"
                    "本轮跳过该站点。", site,
                )
                return False
        elif v.note:
            logger.info("robots 提示[%s]: %s", site, v.note)
        return True

    def run(self) -> RunSummary:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary = RunSummary(
            run_id=ts,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        checkpoint = Checkpoint(self.out_dir / "checkpoint.json")
        if self.fresh_pages:
            # 轮跑可持续性的关键:页级进度每轮重来(发现新职位),
            # 职位级去重集保留(不重复入库)。
            checkpoint.done_pages.clear()

        sqlite = SQLiteWriter(self.out_dir / "jd_crawler.sqlite3")
        try:
            for site in self.config.sites:
                if not self._robots_allows(site):
                    for city in self.config.cities:
                        for kw in self.config.keywords:
                            summary.combos.append(
                                ComboResult(site, city, kw, status="skipped_robots")
                            )
                    continue
                site_stopped = self._run_site(site, ts, checkpoint, sqlite, summary,
                                              browser=self.use_browser)
                if site_stopped and self.browser_fallback and not self.use_browser:
                    logger.warning(
                        "站点 %s httpx 路径被风控,按 --browser-fallback 切换 "
                        "Playwright 备用模式重试本站(headed 浏览器,如遇验证请人工完成)。",
                        site,
                    )
                    # 撤掉 httpx 通道的组合记录,浏览器通道重新记录
                    summary.combos = [c for c in summary.combos if c.site != site]
                    site_stopped = self._run_site(site, ts, checkpoint, sqlite,
                                                  summary, browser=True)
                if site_stopped:
                    # 该站点剩余组合标记为风控停止,不再发起请求
                    done = {(c.site, c.city, c.keyword) for c in summary.combos}
                    for city in self.config.cities:
                        for kw in self.config.keywords:
                            if (site, city, kw) not in done:
                                summary.combos.append(
                                    ComboResult(site, city, kw, status="risk_stopped")
                                )
        finally:
            checkpoint.save()
            sqlite.close()

        summary.finished_at = datetime.now(timezone.utc).isoformat()
        sp = self.out_dir / f"run_summary_{ts}.json"
        sp.write_text(
            json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "本轮结束:新增 %d 条,失败组合 %d,风控停站 %s;摘要 %s",
            summary.new_jobs, summary.failed, summary.risk_stopped_sites or "无", sp,
        )
        return summary

    def _run_site(
        self,
        site: str,
        ts: str,
        checkpoint: Checkpoint,
        sqlite: SQLiteWriter,
        summary: RunSummary,
        *,
        browser: bool = False,
    ) -> bool:
        """抓取一个站点的全部组合;返回 True 表示因风控停站。"""
        tag = "browser" if browser else "httpx"
        jsonl = JsonlWriter(self.out_dir / f"{site}_matrix_{tag}_{ts}.jsonl")
        jarr = JsonArrayWriter(self.out_dir / f"{site}_matrix_{tag}_{ts}.json")
        pipeline = DedupPipeline(jsonl, sqlite)
        rl = RateLimiter(interval=self.delay)
        session = None
        http = None
        if browser:
            from .spiders.browser import BrowserSession, BrowserSpider
            session = BrowserSession(str(self.user_data_dir), rate_limiter=rl)
            session.__enter__()
            spider = BrowserSpider(session, site)
        else:
            http = self.http_factory(site, rl, self.contact)
            spider = self._make_spider(site, http)
        total = len(self.config.cities) * len(self.config.keywords)
        idx = 0
        try:
            for city in self.config.cities:
                for kw in self.config.keywords:
                    idx += 1
                    result = ComboResult(site, city, kw)
                    summary.combos.append(result)
                    logger.info(
                        "[%s] 组合 %d/%d: %s / %s", site, idx, total, city, kw,
                    )
                    try:
                        for job in spider.iter_jobs(kw, city, self.config.pages, checkpoint):
                            if pipeline.process(job):
                                jarr.write(job)
                                checkpoint.mark_job(job)
                                result.new_jobs += 1
                        if result.new_jobs == 0:
                            result.status = "empty"
                    except RiskControlError as e:
                        result.status = "risk_stopped"
                        result.error = str(e)
                        logger.error("风控停止: %s", e)
                        logger.error(
                            "已按合规要求停止站点 %s;checkpoint 已保存,稍后可续跑。",
                            site,
                        )
                        return True
                    except (FetchError, ValueError) as e:
                        result.status = "failed"
                        result.error = str(e)
                        logger.warning("组合失败(继续下一组合): %s", e)
                    except Exception:
                        result.status = "failed"
                        logger.exception("组合异常(继续下一组合)")
                    finally:
                        checkpoint.save()
                    # 组合间额外暂停(0.5x~1.5x 抖动),进一步压低整体频率
                    self.sleep(self.combo_pause * random.uniform(0.5, 1.5))
            return False
        finally:
            jarr.close()
            pipeline.close()
            if http is not None:
                http.close()
            if session is not None:
                session.__exit__(None, None, None)
