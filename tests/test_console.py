from unittest.mock import patch

import pytest

from anvil import console as ui
from anvil.console import ConsoleManager


@pytest.fixture()
def manager():
    return ConsoleManager(force_color=False, force_unicode=False, force_live=False)


class TestConsoleManager:
    def test_info(self, manager, capsys):
        manager.info("hello")
        out = capsys.readouterr().out
        assert "hello" in out

    def test_success(self, manager, capsys):
        manager.success("done")
        out = capsys.readouterr().out
        assert "done" in out

    def test_warning(self, manager, capsys):
        manager.warning("old")
        out = capsys.readouterr().out
        assert "old" in out

    def test_error(self, manager, capsys):
        manager.error("failed")
        out = capsys.readouterr().out
        assert "failed" in out

    def test_step(self, manager, capsys):
        manager.step("step text")
        out = capsys.readouterr().out
        assert "step text" in out

    def test_debug_disabled_by_default(self, manager, capsys):
        manager.debug("secret")
        out = capsys.readouterr().out
        assert out == ""

    def test_debug_enabled(self, capsys):
        manager = ConsoleManager(force_color=False, force_unicode=False, force_live=False, verbose=True)
        manager.debug("secret")
        out = capsys.readouterr().out
        assert "secret" in out

    def test_title(self, manager, capsys):
        manager.title("Setup")
        out = capsys.readouterr().out
        assert "Setup" in out

    def test_section_indentation(self, manager, capsys):
        with manager.section("Section"):
            manager.info("inside")
        out = capsys.readouterr().out
        assert "Section" in out
        assert "inside" in out

    def test_info_block(self, manager, capsys):
        manager.info_block("pkg", {"mp3": 12, "txt": 3}, footer="total 15")
        out = capsys.readouterr().out
        assert "pkg" in out
        assert "mp3" in out
        assert "12" in out
        assert "total 15" in out

    def test_table(self, manager, capsys):
        manager.table(["File", "Size"], [["a.mp3", "3.2 MB"], ["b.txt", "1 KB"]])
        out = capsys.readouterr().out
        assert "File" in out
        assert "Size" in out
        assert "a.mp3" in out
        assert "b.txt" in out

    def test_box(self, manager, capsys):
        manager.box("Warning!", style="warn")
        out = capsys.readouterr().out
        assert "Warning!" in out

    def test_timer(self, manager, capsys):
        with manager.timer("fast"):
            pass
        out = capsys.readouterr().out
        assert "fast" in out
        assert "s" in out

    def test_ask(self, manager):
        with patch("builtins.input", return_value="answer"):
            assert manager.ask("Name") == "answer"

    def test_ask_default(self, manager):
        with patch("builtins.input", return_value=""):
            assert manager.ask("Name", default="guest") == "guest"

    def test_confirm_true(self, manager):
        with patch("builtins.input", return_value="y"):
            assert manager.confirm("Continue?") is True

    def test_confirm_false(self, manager):
        with patch("builtins.input", return_value="n"):
            assert manager.confirm("Continue?") is False

    def test_confirm_default_on_empty(self, manager):
        with patch("builtins.input", return_value=""):
            assert manager.confirm("Continue?", default=False) is False

    def test_select(self, manager):
        with patch("builtins.input", return_value="2"):
            assert manager.select("Env", ["dev", "prod"]) == "prod"

    def test_select_default(self, manager):
        with patch("builtins.input", return_value=""):
            assert manager.select("Env", ["dev", "prod"], default=0) == "dev"

    def test_password(self, manager):
        with patch("getpass.getpass", return_value="secret"):
            assert manager.password("Token") == "secret"

    def test_spinner(self, manager, capsys):
        with manager.spinner("loading") as sp:
            sp.set_final("loaded")
        out = capsys.readouterr().out
        assert "loading" in out or "loaded" in out

    def test_progress(self, capsys):
        manager = ConsoleManager(force_color=False, force_unicode=False, force_live=True)
        with manager.progress("copy", total=2) as bar:
            bar.update(1)
            bar.update(2)
        out = capsys.readouterr().out
        assert "copy" in out

    def test_task_success(self, manager, capsys):
        with manager.task("Task"):
            pass
        out = capsys.readouterr().out
        assert "Task" in out

    def test_task_failure(self, manager, capsys):
        with pytest.raises(RuntimeError):
            with manager.task("Task"):
                raise RuntimeError("boom")
        out = capsys.readouterr().out
        assert "Task" in out
        assert "boom" in out

    def test_numbered_step(self, manager, capsys):
        with manager.numbered_step(1, 2, "First"):
            pass
        out = capsys.readouterr().out
        assert "[1/2]" in out
        assert "First" in out

    def test_run_wrapper(self, manager):
        def main():
            return "ok"

        assert manager.run(main, exit_on_error=False) == "ok"

    def test_run_keyboard_interrupt(self, manager):
        def main():
            raise KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc:
            manager.run(main, exit_on_error=True)
        assert exc.value.code == 130

    def test_run_exception(self, manager):
        def main():
            raise RuntimeError("boom")

        with pytest.raises(SystemExit) as exc:
            manager.run(main, exit_on_error=True)
        assert exc.value.code == 1

    def test_singleton_exports(self):
        from anvil import console, get_manager
        from anvil.console import ConsoleManager, Progress, Spinner

        assert isinstance(console, ConsoleManager)
        assert get_manager() is console
        assert issubclass(Spinner, object)
        assert issubclass(Progress, object)
