#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兼容旧版入口：python excel2sql.py 输入.xlsx

v2 起推荐使用安装后的命令 `excel2sql`，此脚本仅为向后兼容保留。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from excel2sql.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
