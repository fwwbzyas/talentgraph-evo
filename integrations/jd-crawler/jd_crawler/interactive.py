"""交互式控制台(SPEC §4.16):无参数启动 CLI 时进入。

菜单:
    1) 单次抓取(自定义 站点/关键词/城市/页数)
    2) 全矩阵批量抓取(12 城市 × 24 关键词)
    3) 定时循环抓取(每 N 小时自动一轮全矩阵)
    4) 数据清洗(raw/*.jsonl → cleaned/*.json)
    5) 数据库统计
    6) 查看当前矩阵配置
    0) 退出
"""

from __future__ import annotations

from pathlib import Path

from . import cli
from .config import CITIES, KEYWORD_GROUPS, MatrixConfig, flatten_keywords

_MENU = """
================ jd-crawler 交互式控制台 ================
 目标站点: 51job(前程无忧) / liepin(猎聘)
 主模式: Playwright headed 浏览器(人工验证一次,profile 复用)
---------------------------------------------------------
 1) 单次抓取(自定义 站点/关键词/城市/页数)
 2) 全矩阵批量抓取(12 城市 × 24 关键词 = 288 组/平台)
 3) 定时循环抓取(每 N 小时自动跑一轮全矩阵)
 4) 数据清洗(output/raw → output/cleaned)
 5) 数据库统计(output/raw/jd_crawler.sqlite3)
 6) 查看当前矩阵配置(城市/关键词)
 7) 浏览器预热(不登录:过站点验证 / 登录:自动弹扫码登录页,成功后自动继续)
 0) 退出
========================================================="""


def _ask(prompt: str, default: str = "") -> str:
    v = input(f"{prompt}" + (f" [默认 {default}]" if default else "") + ": ").strip()
    return v or default


def _ask_int(prompt: str, default: int) -> int:
    try:
        return int(_ask(prompt, str(default)))
    except ValueError:
        print("输入无效,使用默认值。")
        return default


def _ask_yes(prompt: str, default: bool = False) -> bool:
    v = _ask(prompt + "(y/n)", "y" if default else "n").lower()
    return v in ("y", "yes", "是")


def _ask_sites() -> str:
    print("站点选择: 1=51job  2=liepin  3=全部")
    return {"1": "51job", "2": "liepin", "3": "all"}.get(
        _ask("请选择", "3"), "all"
    )


def _robots_ack_for(site_arg: str) -> bool:
    if site_arg in ("liepin", "all"):
        return _ask_yes(
            "猎聘搜索 URL 受其 robots.txt 禁止(Disallow: /*?*)。"
            "确认仅个人低频研究使用并继续?"
        )
    return False


def _ask_mode() -> list[str]:
    """抓取模式:默认 headed 浏览器主模式;可选退回 httpx(+浏览器兜底);
    浏览器模式下再问登录/不登录(登录态 profile 需先用菜单 7 预热)。"""
    argv: list[str] = []
    if _ask_yes("退回轻量 httpx 模式(无浏览器,被风控即停站)?"):
        argv.append("--httpx")
        if _ask_yes("httpx 被风控后自动切换浏览器模式?"):
            argv.append("--browser-fallback")
    else:
        if _ask_yes("使用登录模式(已登录 profile;首次需先在菜单 7 完成登录)?"):
            argv.append("--login")
    return argv


def _do_single(out_dir: str) -> None:
    site = _ask_sites()
    keyword = _ask("关键词", "算法工程师")
    city = _ask("城市(留空=全国)")
    pages = _ask_int("列表页数", 1)
    delay = float(_ask("请求间隔秒数(下限 1.0)", "2.0"))
    details = _ask_yes("(猎聘/httpx 模式)抓取详情页?", default=False)
    mode = _ask_mode()
    ack = _robots_ack_for(site)
    argv = ["--site", site, "--keyword", keyword, "--pages", str(pages),
            "--output", out_dir, "--delay", str(delay)] + mode
    if city:
        argv += ["--city", city]
    if not details:
        argv += ["--no-details"]
    if ack:
        argv += ["--i-understand-robots"]
    rc = cli.main(argv)
    print("退出码:", rc, "(0=正常, 2=有站点被拦截/异常)")


def _matrix_config_from_input() -> tuple[MatrixConfig, bool]:
    site = _ask_sites()
    cfg = MatrixConfig()
    if site != "all":
        cfg.sites = [site]
    cfg.pages = _ask_int("每组合列表页数", cfg.pages)
    ack = _robots_ack_for(site)
    return cfg, ack


def _do_matrix(out_dir: str) -> None:
    cfg, ack = _matrix_config_from_input()
    delay = float(_ask("请求间隔秒数(下限 1.0)", "2.5"))
    pause = float(_ask("组合间暂停秒数", "6.0"))
    mode = _ask_mode()
    print(f"本轮共 {cfg.combo_count()} 组组合,预计耗时较长,可随时 Ctrl+C 中断,"
          f"checkpoint 已保存可续跑。")
    argv = ["--matrix", "--site", "all" if len(cfg.sites) > 1 else cfg.sites[0],
            "--pages", str(cfg.pages), "--output", out_dir,
            "--delay", str(delay), "--combo-pause", str(pause)] + mode
    if ack:
        argv += ["--i-understand-robots"]
    rc = cli.main(argv)
    print("退出码:", rc)


def _do_schedule(out_dir: str) -> None:
    cfg, ack = _matrix_config_from_input()
    hours = float(_ask("间隔小时数", "24"))
    max_runs = _ask_int("最大轮数(0=不限)", 0)
    mode = _ask_mode()
    argv = ["--matrix", "--loop", str(hours),
            "--site", "all" if len(cfg.sites) > 1 else cfg.sites[0],
            "--pages", str(cfg.pages), "--output", out_dir] + mode
    if max_runs > 0:
        argv += ["--max-runs", str(max_runs)]
    if ack:
        argv += ["--i-understand-robots"]
    rc = cli.main(argv)
    print("调度结束,退出码:", rc)


def _show_matrix() -> None:
    print(f"城市({len(CITIES)}): {'、'.join(CITIES)}")
    total = 0
    for cat, kws in KEYWORD_GROUPS.items():
        print(f"{cat}({len(kws)}): {'、'.join(kws)}")
        total += len(kws)
    print(f"关键词合计 {total} 个;每平台组合数 = {len(CITIES)} × {total} = "
          f"{len(CITIES) * total}")


def run_interactive(default_output: str) -> None:
    out_dir = _ask("输出目录", default_output)
    while True:
        print(_MENU)
        choice = input("请选择操作: ").strip()
        try:
            if choice == "1":
                _do_single(out_dir)
            elif choice == "2":
                _do_matrix(out_dir)
            elif choice == "3":
                _do_schedule(out_dir)
            elif choice == "4":
                cli.do_clean(out_dir)
            elif choice == "5":
                cli.do_stats(out_dir)
            elif choice == "6":
                _show_matrix()
            elif choice == "7":
                site = _ask_sites()
                argv = ["--preflight", "--site", site, "--output", out_dir]
                if _ask_yes("登录预热(自动弹出扫码登录页,登录成功自动继续)?"):
                    argv.append("--login")
                rc = cli.main(argv)
                print("退出码:", rc)
            elif choice == "0":
                print("再见。")
                return
            else:
                print("无效选择。")
        except KeyboardInterrupt:
            print("\n已中断当前操作,返回主菜单。")
        except Exception as e:  # 交互层兜底:任何操作失败不回掉菜单循环
            print(f"操作失败: {e}")
