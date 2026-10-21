"""交互式控制台:菜单流转(monkeypatch input/cli.main)。"""

from jd_crawler import interactive


def test_interactive_exit_immediately(monkeypatch, capsys):
    inputs = iter(["data", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    interactive.run_interactive("data")
    assert "再见" in capsys.readouterr().out


def test_interactive_show_matrix(monkeypatch, capsys):
    inputs = iter(["data", "6", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    interactive.run_interactive("data")
    out = capsys.readouterr().out
    assert "288" in out  # 12 × 24
    assert "人工智能" in out and "物联网" in out


def test_interactive_single_run_invokes_cli(monkeypatch):
    captured = {}

    def fake_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(interactive.cli, "main", fake_main)
    # data → 1(单次) → 站点3=all → 关键词默认 → 城市默认 → 页数默认 →
    # delay 默认 → details 默认 → httpx? 否 → 登录? 否 → robots 确认 y → 0 退出
    inputs = iter(["data", "1", "3", "", "", "", "", "", "", "", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    interactive.run_interactive("data")
    argv = captured["argv"]
    assert "--site" in argv and "all" in argv
    assert "--keyword" in argv and "算法工程师" in argv
    assert "--no-details" in argv
    assert "--i-understand-robots" in argv
    assert "--httpx" not in argv  # 默认浏览器主模式


def test_interactive_matrix_invokes_cli(monkeypatch):
    captured = {}

    def fake_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(interactive.cli, "main", fake_main)
    # data → 2(矩阵) → 站点3 → 页数默认 → robots y → delay 默认 →
    # pause 默认 → httpx? 否 → 登录? 是 → 0
    inputs = iter(["data", "2", "3", "", "y", "", "", "", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    interactive.run_interactive("data")
    argv = captured["argv"]
    assert "--matrix" in argv
    assert "--httpx" not in argv  # 默认浏览器主模式
    assert "--login" in argv  # 登录模式选择生效
    assert "--i-understand-robots" in argv
