"""
智联招聘爬虫 (Playwright 方案)

智联招聘使用腾讯云 EdgeOne 反爬，纯 httpx 请求会触发 CAPTCHA。
因此改用 Playwright 真实浏览器 + 持久化用户数据目录，
复用浏览器已登录状态，天然通过人机验证。

使用前:
  1. 在 Chrome/Edge 浏览器中登录 zhaopin.com
  2. 关闭浏览器
  3. 运行脚本时指定 Chrome 用户数据目录路径
  4. Playwright 会复用该目录中的登录态和已通过的 CAPTCHA
"""

import time
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from .base import BaseCrawler
from contracts.data_schema import RawJobDescription, CrawlConfig, Source


class ZhaopinCrawler(BaseCrawler):
    """
    基于 Playwright 的智联招聘采集器。

    使用持久化浏览器上下文 (persistent context)，
    复用用户已有的 Chrome 登录态和 EdgeOne CAPTCHA 通行证。

    输入: CrawlConfig
    输出: list[RawJobDescription]
    """

    source_name = Source.ZHAOPIN.value
    SEARCH_URL = "https://sou.zhaopin.com/jobs/searchresult.ashx"

    def __init__(self, config: CrawlConfig):
        super().__init__(config)
        self._browser = None
        self._context = None
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ═══════════════════════════════════════
    # Playwright 浏览器管理
    # ═══════════════════════════════════════

    def _launch_browser(self):
        """启动 Playwright 浏览器并注入 Cookie。"""
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        # 从持久化文件加载 Cookie 并注入浏览器上下文
        self._inject_cookies()

    def _inject_cookies(self):
        """从 cookies/zhaopin.json 加载 Cookie 并注入浏览器上下文。"""
        cookie_file = Path(__file__).resolve().parent.parent / "cookies" / "zhaopin.json"
        if not cookie_file.exists():
            print("[Cookie] 未找到 cookies/zhaopin.json，将不使用 Cookie")
            return
        with open(cookie_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        cookies = data.get("cookies", {})
        if not cookies:
            return
        # 转换为 Playwright cookie 格式
        pw_cookies = []
        for name, value in cookies.items():
            pw_cookies.append({
                "name": name,
                "value": value,
                "domain": ".zhaopin.com",
                "path": "/",
            })
        self._context.add_cookies(pw_cookies)
        print(f"[Cookie] 已注入 {len(pw_cookies)} 个 Cookie 到浏览器上下文")

    def _close_browser(self):
        """清理浏览器资源。"""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if hasattr(self, "_pw") and self._pw:
            self._pw.stop()

    # ═══════════════════════════════════════
    # 核心采集
    # ═══════════════════════════════════════

    def search(self, keyword: str) -> list[RawJobDescription]:
        """
        用 Playwright 浏览器搜索智联招聘岗位。

        每个关键词打开搜索结果页，滚动加载，解析职位卡片。
        """
        results: list[RawJobDescription] = []
        seen_urls: set[str] = set()

        try:
            self._launch_browser()
        except Exception as e:
            print(f"  [错误] 浏览器启动失败: {e}")
            print("  [提示] 安装 Playwright: pip install playwright && playwright install chromium")
            return results

        page = self._context.new_page()

        try:
            for page_num in range(1, self.config.max_pages + 1):
                if len(results) >= self.config.min_results:
                    break

                url = f"{self.SEARCH_URL}?kw={keyword}&p={page_num}"
                print(f"  请求: {url}")

                try:
                    page.goto(url, wait_until="networkidle", timeout=self.config.timeout * 1000)
                except Exception as e:
                    print(f"  [错误] 页面加载失败: {e}")
                    break

                # 检测 CAPTCHA — 自动轮询等待人工验证
                if self._detect_captcha(page):
                    print("  [!] 检测到人机验证! 请在弹出的浏览器窗口中点击验证。")
                    print("  [!] 等待验证完成（最多 120 秒）...")
                    if not self._wait_for_captcha(page, timeout=120):
                        print("  [错误] 验证超时，跳过此页")
                        break
                    print("  [OK] 验证通过，继续采集")

                # 滚动加载（部分页面懒加载）
                self._scroll_page(page, times=2)

                # 获取页面 HTML
                html = page.content()

                # 保存 HTML（用于调试）
                self._save_debug_html(keyword, page_num, html)

                # 解析
                from parsel import Selector
                sel = Selector(text=html)
                cards = self._find_job_cards(sel)

                page_count = 0
                for card in cards:
                    jd = self._parse_card(card)
                    if jd and jd.source_url not in seen_urls:
                        seen_urls.add(jd.source_url)
                        results.append(jd)
                        page_count += 1

                print(f"  第 {page_num} 页: {page_count} 条 (累计 {len(results)})")

                if page_count == 0:
                    print("  -> 无结果，停止翻页")
                    break

                if page_num < self.config.max_pages:
                    time.sleep(self.config.request_delay)

        finally:
            page.close()
            self._close_browser()

        return results

    def _detect_captcha(self, page) -> bool:
        """检测页面是否为人机验证页。"""
        try:
            title = page.title()
            if "Security" in title or "Verification" in title or "验证" in title:
                return True
            html = page.content()
            return "captcha" in html.lower() or "EO-Bot-Captcha-Token" in html
        except Exception:
            return False

    def _wait_for_captcha(self, page, timeout: int = 120) -> bool:
        """轮询等待用户手动完成 CAPTCHA 验证。"""
        for _ in range(timeout):
            time.sleep(2)
            try:
                title = page.title()
                html = page.content()[:500]
                # CAPTCHA 页面消失 = 验证通过
                if "Security" not in title and "Verification" not in title:
                    if "captcha" not in html.lower():
                        return True
            except Exception:
                pass
            print(".", end="", flush=True)
        print()
        return False

    def _scroll_page(self, page, times: int = 2):
        """模拟滚动以触发懒加载。"""
        for _ in range(times):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

    def _save_debug_html(self, keyword: str, page_num: int, html: str):
        """保存页面 HTML 用于调试。"""
        output_dir = Path(self.config.output_dir) / "debug_html"
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_kw = keyword.replace("/", "_").replace(" ", "_")
        path = output_dir / f"{safe_kw}_p{page_num}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    # ═══════════════════════════════════════
    # HTML 解析 — 基于智联当前 BEM 命名结构
    #
    # 智联 2026 年搜索页 DOM 结构（BEM 命名）:
    #   div.joblist-box__item                   卡片容器
    #     div.jobinfo__top                      标题+薪资区
    #       div.jobinfo__name-row               标题行
    #         a.jobinfo__name                  职位名+链接 (href=jobdetail/...)
    #       p.jobinfo__salary                   薪资
    #     div.jobinfo__other-info              地点/经验/学历容器
    #       div.jobinfo__other-info-item        单个字段
    #     div.companyinfo                       公司信息区
    #       a.companyinfo__name                公司名+链接
    #       div.companyinfo__tag               公司标签(规模/行业)
    # ═══════════════════════════════════════════

    def _find_job_cards(self, sel):
        """定位职位卡片: joblist-box__item。"""
        return sel.css('div.joblist-box__item')

    def _parse_card(self, card) -> Optional[RawJobDescription]:
        """基于 BEM 命名精确解析职位卡片。"""
        # ── 职位名 + 链接 ──
        name_sel = card.css('a.jobinfo__name')
        if not name_sel:
            return None
        url = name_sel[0].xpath('@href').get(default='').strip()
        title = name_sel[0].xpath('string(.)').get(default='').strip()
        if not url or not title:
            return None
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = 'https://www.zhaopin.com' + url

        # ── 薪资 ──
        salary = card.css('p.jobinfo__salary::text').get()
        salary = salary.strip() if salary else None

        # ── 公司名 ──
        company = card.css('a.companyinfo__name::text').get()
        company = company.strip() if company else None

        # ── 地点 / 经验 / 学历 ──
        # 从 div.jobinfo 全文按正则模式分类，不依赖特定 CSS class 位置。
        # （Zhaopin 不同岗位卡片 DOM 结构不一致，有的有技能标签行有的没有）
        jobinfo = card.css('div.jobinfo')
        all_lines: list[str] = []
        if jobinfo:
            all_lines = [
                l.strip() for l in jobinfo[0].xpath('string(.)').get().split('\n')
                if l.strip()
            ]

        location, experience, education = None, None, None

        import re
        for line in all_lines:
            if line == title or line == salary:
                continue
            # 经验: "X-X年" / "X年以下" / "X年以上" / "经验不限" / "应届"
            if re.search(r'\d+[-~]\d+年|\d+年以[上下]|经验不限|应届|在校', line):
                experience = line
            # 学历
            elif re.search(r'本科|硕士|博士|大专|中专|高中|学历不限|学历', line):
                education = line
            # 地点: · 分隔的城市格式 "上海·徐汇·虹梅路"
            elif re.search(r'[·•．]', line) and len(line) < 50:
                location = line

        # 兜底: 未识别到地点时按中文地址特征模糊匹配
        if not location:
            for line in all_lines:
                if re.search(r'[路街市县区镇园厦楼]', line) and len(line) < 50:
                    location = line
                    break

        # ── 福利/技能标签（div.jobinfo__tag）──
        wt_sel = card.css('div.jobinfo__tag')
        welfare_tags: list[str] = []
        if wt_sel:
            welfare_tags = [
                t.strip() for t in wt_sel[0].xpath('string(.)').get().split('\n')
                if t.strip()
            ]

        # ── 公司标签（规模/行业/融资阶段）──
        ct_sel = card.css('div.companyinfo__tag')
        company_tags: list[str] = []
        if ct_sel:
            company_tags = [
                t.strip() for t in ct_sel[0].xpath('string(.)').get().split('\n')
                if t.strip()
            ]

        # 合成描述：福利标签 + 公司标签
        all_tags = welfare_tags + company_tags
        extra_text = '。'.join(all_tags)
        description = f'{title}。{extra_text}' if extra_text else title

        return RawJobDescription(
            source=Source.ZHAOPIN,
            source_url=url,
            title=title,
            company=company,
            description=description,
            salary_range=salary,
            location=location,
            experience=experience,
            education=education,
            publish_date=None,
            crawl_timestamp=datetime.now(),
        )

    def get_detail(self, url: str) -> Optional[RawJobDescription]:
        """详情页采集（Playwright 版本）。"""
        try:
            if not hasattr(self, "_pw") or not self._pw:
                self._launch_browser()
        except Exception:
            return None

        page = self._context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=self.config.timeout * 1000)
            html = page.content()
            from parsel import Selector
            sel = Selector(text=html)

            title = sel.xpath("//h1/text() | //title/text()").get("").strip()
            desc_parts = sel.xpath(
                '//div[contains(@class,"des")]//text()'
                '| //div[contains(@class,"job")]//text()'
                '| //article//text()'
            ).getall()
            description = " ".join(p.strip() for p in desc_parts if p.strip()) or title

            return RawJobDescription(
                source=Source.ZHAOPIN,
                source_url=url,
                title=title,
                description=description,
                crawl_timestamp=datetime.now(),
            )
        finally:
            page.close()
