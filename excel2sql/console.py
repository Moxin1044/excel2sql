# -*- coding: utf-8 -*-
"""终端输出工具：行式、彩色、非 TTY 自动降级。"""

import os
import sys

_RESET = "\033[0m"
_CODES = {
    "dim": "\033[2m",
    "bold": "\033[1m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}


class Console:
    """行式输出的控制台封装（不做全屏 TUI）。"""

    def __init__(self, color=True, quiet=False, stream=None):
        self.stream = stream or sys.stdout
        self.quiet = quiet
        if not color or os.environ.get("NO_COLOR"):
            self.color = False
        else:
            self.color = hasattr(self.stream, "isatty") and self.stream.isatty()

    # ---------- 基础 ----------

    def _paint(self, text, style):
        if not self.color:
            return text
        return _CODES.get(style, "") + text + _RESET

    def write(self, text="", style=None, end="\n"):
        if self.quiet:
            return
        if style:
            text = self._paint(text, style)
        print(text, end=end, file=self.stream)

    # ---------- 语义化输出 ----------

    def step(self, text):
        self.write("› " + text, "cyan")

    def info(self, text):
        self.write("  " + text, "dim")

    def success(self, text):
        self.write("✓ " + text, "green")

    def warn(self, text):
        self.write("! " + text, "yellow")

    def error(self, text):
        self.write("✗ " + text, "red")

    def title(self, text):
        self.write(text, "bold")

    def summary(self, rows, headers):
        """打印一个简单的对齐表格（行式，不做边框特效）。"""
        if self.quiet or not rows:
            return
        widths = []
        for i, head in enumerate(headers):
            width = len(str(head))
            for row in rows:
                width = max(width, len(str(row[i])))
            widths.append(min(width, 40))
        line = "  ".join(
            str(head).ljust(widths[i]) for i, head in enumerate(headers)
        )
        self.write("  " + line, "bold")
        self.write("  " + "-" * min(len(line), 120), "dim")
        for row in rows:
            cells = []
            for i, cell in enumerate(row):
                text = str(cell)
                if len(text) > widths[i]:
                    text = text[: max(0, widths[i] - 1)] + "…"
                cells.append(text.ljust(widths[i]))
            self.write("  " + "  ".join(cells))
