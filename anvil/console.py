#!/usr/bin/env python3

from __future__ import annotations

import getpass
import math
import os
import shutil
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Optional, Sequence, Tuple

RGB = Tuple[int, int, int]

DEFAULT_PALETTE = {
    "accent_start": (56, 189, 248),
    "accent_end":   (16, 185, 129),
    "err":          (248, 113, 113),
    "warn":         (250, 204, 21),
    "dim":          (113, 113, 122),
    "fg":           (244, 244, 245),
}

_PARTIALS = " ▏▎▍▌▋▊▉█"


def _lerp(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _supports_truecolor() -> bool:
    ct = os.environ.get("COLORTERM", "")
    if ct in ("truecolor", "24bit"):
        return True
    term = os.environ.get("TERM", "")
    return "256color" in term or "kitty" in term or "wezterm" in term or "iterm" in term.lower()


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}с"
    m, s = divmod(int(round(seconds)), 60)
    if m < 60:
        return f"{m}хв {s}с"
    h, m = divmod(m, 60)
    return f"{h}год {m}хв"


class ConsoleManager:
    def __init__(
        self,
        palette: Optional[dict] = None,
        force_color: Optional[bool] = None,
        force_unicode: Optional[bool] = None,
        force_live: Optional[bool] = None,
        verbose: bool = False,
    ):
        p = {**DEFAULT_PALETTE, **(palette or {})}
        self._accent_start = p["accent_start"]
        self._accent_end = p["accent_end"]
        self._err_c = p["err"]
        self._warn_c = p["warn"]
        self._dim_c = p["dim"]
        self._fg_c = p["fg"]

        self.color = force_color if force_color is not None else self._can_color()
        self.truecolor = self.color and _supports_truecolor()
        self.unicode = force_unicode if force_unicode is not None else self._can_unicode()
        self.live = (
            force_live
            if force_live is not None
            else (bool(sys.stdout.isatty()) and not os.environ.get("NO_MOTION"))
        )
        self.width = shutil.get_terminal_size(fallback=(80, 24)).columns
        self.verbose = verbose

        self._lock = threading.RLock()
        self._indent = 0

    @staticmethod
    def _can_color() -> bool:
        if os.environ.get("NO_COLOR"):
            return False
        if not sys.stdout.isatty():
            return False
        term = os.environ.get("TERM", "dumb")
        return term != "dumb"

    @staticmethod
    def _can_unicode() -> bool:
        enc = sys.stdout.encoding or ""
        return enc.lower().startswith("utf")

    def fg(self, rgb: RGB, text: str) -> str:
        if not self.color:
            return text
        if self.truecolor:
            return f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{text}\x1b[0m"
        code = self._nearest_ansi16(rgb)
        return f"\x1b[{code}m{text}\x1b[0m"

    @staticmethod
    def _nearest_ansi16(rgb: RGB) -> int:
        table = {
            30: (0, 0, 0), 31: (205, 49, 49), 32: (13, 188, 121),
            33: (229, 229, 16), 34: (36, 114, 200), 35: (188, 63, 188),
            36: (17, 168, 205), 37: (229, 229, 229),
        }
        best = min(table.items(), key=lambda kv: sum((c1 - c2) ** 2 for c1, c2 in zip(kv[1], rgb)))
        return best[0]

    def ok(self, t: str) -> str:   return self.fg(self._accent_end, t)
    def work(self, t: str) -> str: return self.fg(self._accent_start, t)
    def err(self, t: str) -> str:  return self.fg(self._err_c, t)
    def warn(self, t: str) -> str: return self.fg(self._warn_c, t)
    def dim(self, t: str) -> str:  return self.fg(self._dim_c, t)
    def bold(self, t: str) -> str: return f"\x1b[1m{t}\x1b[0m" if self.color else t

    def rule(self, width: Optional[int] = None) -> str:
        w = width or min(self.width, 60)
        ch = "─" if self.unicode else "-"
        return self.dim(ch * w)

    def check(self) -> str:  return self.ok("✓") if self.unicode else self.ok("[ok]")
    def cross(self) -> str:  return self.err("✗") if self.unicode else self.err("[x]")
    def bullet(self) -> str: return "•" if self.unicode else "*"

    def _write(self, text: str = "") -> None:
        with self._lock:
            prefix = "  " * self._indent
            if prefix and text:
                text = "\n".join(prefix + line if line else line for line in text.split("\n"))
            print(text)

    def info(self, text: str) -> None:
        self._write(self.work(self.bullet()) + " " + text)

    def success(self, text: str) -> None:
        self._write(self.check() + " " + text)

    def error(self, text: str) -> None:
        self._write(self.cross() + " " + self.err(text))

    def warning(self, text: str) -> None:
        self._write(self.warn("!") + " " + text)

    def debug(self, text: str) -> None:
        if self.verbose:
            self._write(self.dim("· " + text))

    def step(self, text: str) -> None:
        self._write(self.dim(self.bullet()) + " " + text)

    def title(self, text: str) -> None:
        self._write("")
        self._write(self.rule())
        self._write(self.bold(self.fg(self._fg_c, text)))
        self._write(self.rule())

    @contextmanager
    def section(self, title: str):
        self._write(self.bold(self.fg(self._fg_c, title)))
        self._indent += 1
        try:
            yield self
        finally:
            self._indent -= 1

    def info_block(self, name: str, fields: dict[str, Any], footer: Optional[str] = None) -> None:
        self._write("")
        self._write(self.rule())
        self._write(self.bold(self.fg(self._fg_c, name)))
        dot = " · " if self.unicode else " . "
        line = dot.join(f"{self.dim(str(k))} {self.bold(str(v))}" for k, v in fields.items())
        if line:
            self._write(line)
        if footer:
            self._write(self.dim(footer))
        self._write(self.rule())
        self._write("")

    def table(self, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        cols = len(headers)
        str_rows = [[str(c) for c in row] for row in rows]
        widths = [len(h) for h in headers]
        for row in str_rows:
            for i in range(cols):
                widths[i] = max(widths[i], len(row[i]) if i < len(row) else 0)

        sep = "  "
        header_line = sep.join(self.bold(h.ljust(widths[i])) for i, h in enumerate(headers))
        self._write(header_line)
        self._write(self.rule(width=min(self.width, sum(widths) + sep.count(" ") * (cols - 1) + 2)))
        for row in str_rows:
            line = sep.join((row[i] if i < len(row) else "").ljust(widths[i]) for i in range(cols))
            self._write(line)

    def box(self, text: str, style: str = "info") -> None:
        color_fn = {
            "info": self.work, "warn": self.warn, "error": self.err, "ok": self.ok,
        }.get(style, self.work)
        lines = text.split("\n")
        w = max(len(l) for l in lines) + 2
        if self.unicode:
            top, bot, side = "┌" + "─" * w + "┐", "└" + "─" * w + "┘", "│"
        else:
            top, bot, side = "+" + "-" * w + "+", "+" + "-" * w + "+", "|"
        self._write(color_fn(top))
        for l in lines:
            self._write(color_fn(side) + " " + l.ljust(w - 1) + color_fn(side))
        self._write(color_fn(bot))

    def ask(self, prompt: str, default: Optional[str] = None) -> str:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(self.work(f"{prompt}{suffix}: ")).strip()
        return raw if raw else (default or "")

    def confirm(self, prompt: str, default: bool = True) -> bool:
        hint = "Y/n" if default else "y/N"
        resp = input(self.work(f"{prompt} [{hint}]: ")).strip().lower()
        if not resp:
            return default
        return resp in ("y", "yes", "т", "так")

    def select(self, prompt: str, options: Sequence[str], default: int = 0) -> str:
        self._write(prompt)
        for i, opt in enumerate(options, 1):
            marker = self.work(str(i)) if i - 1 != default else self.bold(self.work(str(i)))
            self._write(f"  {marker}) {opt}")
        while True:
            raw = input(self.work(f"Ваш вибір [1-{len(options)}, за замовчуванням {default + 1}]: ")).strip()
            if not raw:
                return options[default]
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            self.warning("Некоректний вибір, спробуйте ще раз.")

    def password(self, prompt: str) -> str:
        return getpass.getpass(self.work(f"{prompt}: "))

    def spinner(self, text: str) -> "Spinner":
        return Spinner(self, text)

    def progress(self, text: str, total: int) -> "Progress":
        return Progress(self, text, total)

    @contextmanager
    def task(self, text: str, swallow: bool = False):
        t0 = time.time()
        sp = self.spinner(text)
        sp.start()
        try:
            yield sp
        except Exception as e:
            elapsed = time.time() - t0
            sp.stop(final=f"{text}", failed=True)
            self.error(f"{e}")
            if not swallow:
                raise
        else:
            elapsed = time.time() - t0
            final = getattr(sp, "_final_text", "") or text
            sp.stop(final=f"{final} ({_format_duration(elapsed)})")

    @contextmanager
    def numbered_step(self, current: int, total: int, text: str, swallow: bool = False):
        label = f"{self.dim(f'[{current}/{total}]')} {text}"
        with self.task(label, swallow=swallow) as sp:
            yield sp

    @contextmanager
    def timer(self, label: str):
        t0 = time.time()
        try:
            yield
        finally:
            self.step(f"{label}: {self.dim(_format_duration(time.time() - t0))}")

    def run(self, main: Callable[[], Any], exit_on_error: bool = True) -> Any:
        try:
            return main()
        except KeyboardInterrupt:
            self._write("")
            self.warning("Перервано користувачем.")
            if exit_on_error:
                sys.exit(130)
        except SystemExit:
            raise
        except Exception as e:
            self.error(f"Неопрацьована помилка: {e}")
            if self.verbose:
                self._write(self.dim(traceback.format_exc()))
            if exit_on_error:
                sys.exit(1)


class Spinner:
    def __init__(self, manager: ConsoleManager, text: str):
        self.manager = manager
        self.text = text
        self.frames = (
            ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            if manager.unicode else ["|", "/", "-", "\\"]
        )
        self._stop = False
        self._thread: Optional[threading.Thread] = None
        self._failed = False
        self._final_text = ""

    def _color_at(self, t: float) -> RGB:
        pulse = 0.5 + 0.5 * math.sin(t * 2.2)
        return _lerp(self.manager._accent_start, self.manager._fg_c, pulse * 0.35)

    def _run(self):
        i = 0
        t0 = time.time()
        while not self._stop:
            f = self.frames[i % len(self.frames)]
            c = self._color_at(time.time() - t0)
            with self.manager._lock:
                sys.stdout.write("\r\x1b[K" + self.manager.fg(c, f) + " " + self.manager.dim(self.text))
                sys.stdout.flush()
            time.sleep(0.06)
            i += 1

    def start(self) -> "Spinner":
        if not self.manager.live:
            self.manager._write(self.text + "...")
            return self
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def set_final(self, text: str) -> None:
        self._final_text = text

    def fail(self) -> None:
        self._failed = True

    def stop(self, final: str = "", failed: bool = False) -> None:
        self._stop = True
        if self._thread:
            self._thread.join()
        msg = final or self._final_text or self.text
        mark = self.manager.cross() if failed else self.manager.check()
        with self.manager._lock:
            if self.manager.live:
                sys.stdout.write("\r\x1b[K" + mark + " " + msg + "\n")
            else:
                sys.stdout.write(mark + " " + msg + "\n")
            sys.stdout.flush()

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop(final=self._final_text, failed=self._failed or exc_type is not None)
        return False


class Progress:
    def __init__(self, manager: ConsoleManager, text: str, total: int):
        self.manager = manager
        self.text = text
        self.total = max(total, 1)
        self.width = 28
        self._current = 0

    def _bar(self, frac: float) -> str:
        exact = frac * self.width
        full = int(exact)
        rem = exact - full
        edge_idx = int(round(rem * (len(_PARTIALS) - 1))) if full < self.width else 0
        parts = []
        for i in range(self.width):
            pos_frac = (i + 0.5) / self.width
            color = _lerp(self.manager._accent_start, self.manager._accent_end, pos_frac)
            if i < full:
                ch = "█" if self.manager.unicode else "#"
                parts.append(self.manager.fg(color, ch))
            elif i == full and self.manager.unicode:
                parts.append(self.manager.fg(color, _PARTIALS[edge_idx]))
            else:
                ch = "░" if self.manager.unicode else "-"
                parts.append(self.manager.dim(ch))
        return "".join(parts)

    def _render(self, current: int) -> None:
        if not self.manager.live:
            return
        frac = min(current / self.total, 1.0)
        pct = int(frac * 100)
        bar = self._bar(frac)
        line = (
            f"{self.manager.dim(self.text)}  {bar}  "
            f"{self.manager.bold(f'{pct:3d}%')} {self.manager.dim(f'({current}/{self.total})')}"
        )
        with self.manager._lock:
            sys.stdout.write("\r\x1b[K" + line)
            sys.stdout.flush()

    def update(self, current: int) -> None:
        self._current = current
        self._render(current)

    def tick(self, step: int = 1) -> None:
        self.update(self._current + step)

    def finish(self) -> None:
        if self.manager.live:
            self._render(self.total)
            with self.manager._lock:
                sys.stdout.write("\n")
                sys.stdout.flush()

    def __enter__(self) -> "Progress":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.finish()
        return False


console = ConsoleManager()


def get_manager() -> ConsoleManager:
    return console
