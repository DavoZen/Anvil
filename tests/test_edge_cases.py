from unittest.mock import patch

import pytest

from anvil.console import ConsoleManager


@pytest.fixture()
def manager():
    return ConsoleManager(force_color=False, force_unicode=False, force_live=False)


class TestColorModes:
    def test_color_disabled(self, manager, capsys):
        manager.color = False
        out = manager.fg((255, 0, 0), "text")
        assert out == "text"

    def test_truecolor_enabled(self, capsys):
        m = ConsoleManager(force_color=True, force_unicode=False, force_live=False)
        out = m.fg((255, 0, 0), "text")
        assert "text" in out
        assert "\x1b[0m" in out
        if m.truecolor:
            assert "\x1b[38;2;255;0;0m" in out
        else:
            assert "\x1b[31m" in out

    def test_ansi16_fallback(self, capsys):
        m = ConsoleManager(force_color=True, force_unicode=False, force_live=False)
        m.truecolor = False
        out = m.fg((205, 49, 49), "text")
        assert "\x1b[31m" in out
        assert "text" in out

    def test_no_color_env(self, capsys):
        import os
        old = os.environ.get("NO_COLOR")
        os.environ["NO_COLOR"] = "1"
        try:
            m = ConsoleManager(force_unicode=False, force_live=False)
            assert m.color is False
        finally:
            if old is None:
                os.environ.pop("NO_COLOR", None)
            else:
                os.environ["NO_COLOR"] = old

    def test_nearest_ansi16(self, manager, capsys):
        assert manager._nearest_ansi16((0, 0, 0)) == 30
        assert manager._nearest_ansi16((205, 49, 49)) == 31


class TestUnicodeModes:
    def test_unicode_enabled(self, capsys):
        m = ConsoleManager(force_color=False, force_unicode=True, force_live=False)
        assert m.bullet() == "\u2022"
        assert m.check() == m.ok("\u2713")
        assert m.cross() == m.err("\u2717")

    def test_unicode_disabled(self, manager, capsys):
        assert manager.bullet() == "*"
        assert "[ok]" in manager.check()
        assert "[x]" in manager.cross()

    def test_rule_ascii(self, manager, capsys):
        r = manager.rule(width=4)
        assert r.count("-") == 4

    def test_rule_unicode_chars(self, capsys):
        m = ConsoleManager(force_color=False, force_unicode=True, force_live=False)
        r = m.rule(width=4)
        assert r.count("\u2500") == 4


class TestPalette:
    def test_custom_palette(self, capsys):
        custom = {
            "accent_start": (10, 20, 30),
            "accent_end": (40, 50, 60),
            "err": (70, 80, 90),
            "warn": (100, 110, 120),
            "dim": (130, 140, 150),
            "fg": (160, 170, 180),
        }
        m = ConsoleManager(palette=custom, force_color=True, force_unicode=False, force_live=False)
        assert m._accent_start == (10, 20, 30)
        assert m._accent_end == (40, 50, 60)
        assert m._err_c == (70, 80, 90)

    def test_default_palette(self, manager, capsys):
        assert manager._accent_start == (56, 189, 248)
        assert manager._accent_end == (16, 185, 129)


class TestEdgeCases:
    def test_empty_info(self, manager, capsys):
        manager.info("")
        out = capsys.readouterr().out
        assert out.strip() != ""

    def test_long_text(self, manager, capsys):
        long = "x" * 200
        manager.info(long)
        out = capsys.readouterr().out
        assert long in out

    def test_special_characters(self, manager, capsys):
        manager.info("special: \u00e9\u20ac")
        out = capsys.readouterr().out
        assert "special:" in out

    def test_indent_reset_after_section(self, manager, capsys):
        with manager.section("A"):
            manager.info("inner")
        manager.info("outer")
        out = capsys.readouterr().out
        assert "inner" in out
        assert "outer" in out

    def test_title_empty(self, manager, capsys):
        manager.title("")
        out = capsys.readouterr().out
        assert out != ""

    def test_box_multiline(self, manager, capsys):
        manager.box("line1\nline2", style="info")
        out = capsys.readouterr().out
        assert "line1" in out
        assert "line2" in out

    def test_info_block_no_fields(self, manager, capsys):
        manager.info_block("empty", {}, footer="no data")
        out = capsys.readouterr().out
        assert "empty" in out
        assert "no data" in out

    def test_table_empty_rows(self, manager, capsys):
        manager.table(["A", "B"], [])
        out = capsys.readouterr().out
        assert "A" in out
        assert "B" in out


class TestSpinner:
    def test_spinner_non_live(self, manager, capsys):
        with manager.spinner("working") as sp:
            sp.set_final("done")
        out = capsys.readouterr().out
        assert "working" in out or "done" in out

    def test_spinner_fail(self, manager, capsys):
        with manager.spinner("task") as sp:
            sp.fail()
        out = capsys.readouterr().out
        assert "[x]" in out or "\u2717" in out
        assert "task" in out

    def test_spinner_final_text(self, manager, capsys):
        with manager.spinner("loading") as sp:
            sp.set_final("loaded")
        out = capsys.readouterr().out
        assert "loaded" in out

    def test_spinner_with_exception(self, manager, capsys):
        with pytest.raises(RuntimeError):
            with manager.spinner("task"):
                raise RuntimeError("fail")
        out = capsys.readouterr().out
        assert "task" in out
        assert "[x]" in out or "\u2717" in out


class TestProgress:
    def test_progress_non_live(self, capsys):
        m = ConsoleManager(force_color=False, force_unicode=False, force_live=False)
        with m.progress("work", total=2) as bar:
            bar.update(1)
            bar.update(2)
        out = capsys.readouterr().out
        assert out == ""

    def test_progress_live(self, capsys):
        m = ConsoleManager(force_color=False, force_unicode=False, force_live=True)
        with m.progress("work", total=2) as bar:
            bar.update(1)
            bar.update(2)
        out = capsys.readouterr().out
        assert "work" in out

    def test_progress_tick(self, capsys):
        m = ConsoleManager(force_color=False, force_unicode=False, force_live=True)
        with m.progress("work", total=5) as bar:
            for _ in range(5):
                bar.tick()
        out = capsys.readouterr().out
        assert "work" in out

    def test_progress_finish_100_percent(self, capsys):
        m = ConsoleManager(force_color=False, force_unicode=False, force_live=True)
        with m.progress("work", total=1) as bar:
            bar.update(1)
        out = capsys.readouterr().out
        assert "100%" in out


class TestTask:
    def test_task_success_with_final(self, manager, capsys):
        with manager.task("Task") as sp:
            sp.set_final("Task done")
        out = capsys.readouterr().out
        assert "Task done" in out
        assert "Task" in out

    def test_task_swallow_exception(self, manager, capsys):
        with manager.task("Task", swallow=True):
            raise RuntimeError("ignored")
        out = capsys.readouterr().out
        assert "Task" in out
        assert "ignored" in out

    def test_task_reraises_by_default(self, manager, capsys):
        with pytest.raises(RuntimeError):
            with manager.task("Task"):
                raise RuntimeError("boom")

    def test_numbered_step_text(self, manager, capsys):
        with manager.numbered_step(2, 3, "Middle"):
            pass
        out = capsys.readouterr().out
        assert "[2/3]" in out
        assert "Middle" in out


class TestInput:
    def test_ask_empty_returns_default(self, manager):
        with patch("builtins.input", return_value=""):
            assert manager.ask("Name", default="guest") == "guest"

    def test_confirm_y_variants(self, manager):
        for val in ("y", "yes", "Y", "Yes"):
            with patch("builtins.input", return_value=val):
                assert manager.confirm("?") is True

    def test_confirm_n_variants(self, manager):
        for val in ("n", "no", "N", "No"):
            with patch("builtins.input", return_value=val):
                assert manager.confirm("?") is False

    def test_password(self, manager):
        with patch("getpass.getpass", return_value="secret"):
            assert manager.password("Token") == "secret"

    def test_select_returns_option(self, manager):
        with patch("builtins.input", return_value="2"):
            assert manager.select("Env", ["dev", "staging", "prod"]) == "staging"

    def test_select_default_on_empty(self, manager):
        with patch("builtins.input", return_value=""):
            assert manager.select("Env", ["a", "b", "c"], default=1) == "b"


class TestRunWrapper:
    def test_run_returns_value(self, manager):
        def main():
            return 42

        assert manager.run(main, exit_on_error=False) == 42

    def test_run_keyboard_interrupt_code(self, manager):
        def main():
            raise KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc:
            manager.run(main, exit_on_error=True)
        assert exc.value.code == 130

    def test_run_generic_exception_code(self, manager):
        def main():
            raise ValueError("x")

        with pytest.raises(SystemExit) as exc:
            manager.run(main, exit_on_error=True)
        assert exc.value.code == 1

    def test_run_system_exit_not_swallowed(self, manager):
        def main():
            raise SystemExit(7)

        with pytest.raises(SystemExit) as exc:
            manager.run(main, exit_on_error=True)
        assert exc.value.code == 7

    def test_run_verbose_traceback(self, manager, capsys):
        manager.verbose = True
        with pytest.raises(SystemExit):
            manager.run(lambda: (_ for _ in ()).throw(ValueError("x")), exit_on_error=True)
        out = capsys.readouterr().out
        assert "Traceback" in out


class TestModuleExports:
    def test_console_is_instance(self):
        from anvil import console
        from anvil.console import ConsoleManager

        assert isinstance(console, ConsoleManager)

    def test_get_manager_returns_same_instance(self):
        from anvil import get_manager

        a = get_manager()
        b = get_manager()
        assert a is b

    def test_all_exports(self):
        import anvil

        for name in ["ConsoleManager", "Progress", "Spinner", "console", "get_manager"]:
            assert name in anvil.__all__
            assert hasattr(anvil, name)
