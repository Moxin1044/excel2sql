# -*- coding: utf-8 -*-
"""excel2sql —— 将 Excel / CSV 转换为 SQL 文件（MySQL / PostgreSQL / SQLite）

v2 特性：
- 流式读取与写出（大文件不吃内存）
- 采样推断字段类型（不再全表扫描），Decimal 精确计算精度，避免浮点丢精度
- 多方言：mysql / postgres / sqlite
- 支持 CSV 输入、多文件、表名前缀后缀、自动自增主键、行数限制
- 行式彩色 CLI 输出（非 TTY 自动降级）
"""

__version__ = "2.0.0"

__all__ = ["__version__"]
