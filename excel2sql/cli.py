# -*- coding: utf-8 -*-
"""excel2sql 命令行入口。"""

import argparse
import io
import os
import re
import sys
import time

from . import __version__
from .columntype import ColumnType
from .console import Console
from .dialects import get_dialect
from .infer import apply_smart_text, infer_types
from .reader import iter_sheets
from .writer import SqlWriter

GENERIC_SHEET_NAME = re.compile(r"^(sheet|工作表|csv)\s*\d*$", re.IGNORECASE)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="excel2sql",
        description="将 Excel / CSV 转换为 SQL 文件（MySQL / PostgreSQL / SQLite）",
    )
    parser.add_argument("inputs", nargs="+", help="输入文件（.xlsx / .xls / .csv，可多个）")
    parser.add_argument("-o", "--output", help="输出 SQL 文件路径（默认：输入文件名 + .sql）")
    parser.add_argument("--dialect", default="mysql", help="SQL 方言：mysql / postgres / sqlite（默认 mysql）")
    parser.add_argument("--sheet", help="仅转换指定 sheet（多个用逗号分隔，默认全部）")
    parser.add_argument("--charset", default="utf8mb4", help="表字符集（仅 mysql 生效，默认 utf8mb4）")
    parser.add_argument("--engine", default="InnoDB", help="存储引擎（仅 mysql 生效，默认 InnoDB）")
    parser.add_argument("--batch-size", type=int, default=500, help="每条 INSERT 包含的行数（默认 500）")
    parser.add_argument("--limit", type=int, default=0, help="每张表最多写入的行数（0 表示不限制）")
    parser.add_argument("--sample-size", type=int, default=1000, help="类型推断采样行数（默认 1000）")
    parser.add_argument("--sheet-table-names", help="指定 sheet 与表名的映射，如 用户表:users,订单:orders")
    parser.add_argument("--table-name", help="仅当只有一个 sheet 时，强制指定表名")
    parser.add_argument("--prefix", default="", help="表名前缀")
    parser.add_argument("--suffix", default="", help="表名后缀")
    parser.add_argument("--add-id", action="store_true", help="自动追加自增主键 id 列")
    parser.add_argument("--all-text", action="store_true", help="所有字段统一使用文本类型")
    parser.add_argument("--no-smart-text", action="store_true",
                        help="关闭智能文本识别（默认把手机号/编号/卡号类列名按文本处理）")
    parser.add_argument("--drop", action="store_true", help="生成 DROP TABLE IF EXISTS 语句")
    parser.add_argument("--no-create", action="store_true", help="不生成 CREATE TABLE 语句")
    parser.add_argument("--no-insert", action="store_true", help="不生成 INSERT 语句（只要建表结构）")
    parser.add_argument("--dry-run", action="store_true", help="只做解析与类型推断，不写出文件")
    parser.add_argument("-v", "--verbose", action="store_true", help="打印每张表的字段类型明细")
    parser.add_argument("-q", "--quiet", action="store_true", help="静默模式，只输出错误")
    parser.add_argument("--no-color", action="store_true", help="禁用彩色输出")
    parser.add_argument("--version", action="version", version="excel2sql %s" % __version__)
    return parser


def default_output(inputs, dialect):
    stem = os.path.splitext(os.path.basename(inputs[0]))[0]
    return "%s.sql" % stem


def parse_sheet_table_names(text):
    mapping = {}
    if not text:
        return mapping
    for pair in text.split(","):
        if not pair.strip():
            continue
        if ":" not in pair:
            raise ValueError("--sheet-table-names 格式应为 sheet:表名，例如 用户表:users")
        sheet, table = pair.split(":", 1)
        mapping[sheet.strip()] = table.strip()
    return mapping


def sanitize_table_name(sheet_name, source_path, mapping, table_name=None, prefix="", suffix=""):
    """sheet 名 → 合法表名（通用 sheet 名回退为文件名）。"""
    if table_name:
        base = table_name
    elif sheet_name in mapping:
        base = mapping[sheet_name]
    else:
        base = str(sheet_name).strip()
        if not base or GENERIC_SHEET_NAME.match(base):
            base = os.path.splitext(os.path.basename(source_path))[0]
    base = base.strip()
    if prefix:
        base = prefix + base
    if suffix:
        base = base + suffix
    return base or "table_1"


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    console = Console(color=not args.no_color, quiet=args.quiet)

    if args.sample_size < 1:
        console.error("--sample-size 必须大于 0")
        return 2
    if len(args.inputs) > 1 and not args.output:
        console.error("转换多个输入文件时必须用 -o 指定输出文件")
        return 2
    if args.table_name and len(args.inputs) > 1:
        console.error("--table-name 仅适用于单个输入文件")
        return 2

    try:
        sheet_table_names = parse_sheet_table_names(args.sheet_table_names)
    except ValueError as exc:
        console.error(str(exc))
        return 2

    try:
        dialect = get_dialect(args.dialect, engine=args.engine, charset=args.charset)
    except ValueError as exc:
        console.error(str(exc))
        return 2
    if dialect.name != "mysql" and (args.charset != "utf8mb4" or args.engine != "InnoDB"):
        console.warn("--charset / --engine 仅对 mysql 方言生效，已忽略")

    sheet_filter = None
    if args.sheet:
        sheet_filter = {name.strip() for name in args.sheet.split(",") if name.strip()}

    output_path = args.output or default_output(args.inputs, dialect.name)
    started = time.time()

    console.title("excel2sql %s" % __version__)
    console.step("方言 %s ｜ 输入 %d 个文件 ｜ 采样 %d 行" % (
        dialect.name, len(args.inputs), args.sample_size))

    table_rows = []
    total_rows = 0

    try:
        if args.dry_run:
            handle = io.StringIO()
        else:
            handle = open(output_path, "w", encoding="utf-8")

        try:
            writer = SqlWriter(
                handle, dialect,
                batch_size=args.batch_size,
                drop=args.drop,
                add_id=args.add_id,
                limit=args.limit,
                create=not args.no_create,
                insert=not args.no_insert,
            )
            if not args.dry_run:
                writer.preamble()

            used_names = set()
            for sheet in iter_sheets(args.inputs, sample_size=args.sample_size, sheet_filter=sheet_filter):
                table_name = sanitize_table_name(
                    sheet.sheet_name, sheet.source, sheet_table_names,
                    table_name=args.table_name, prefix=args.prefix, suffix=args.suffix,
                )
                if table_name in used_names:
                    index = 2
                    while "%s_%d" % (table_name, index) in used_names:
                        index += 1
                    table_name = "%s_%d" % (table_name, index)
                used_names.add(table_name)

                types = infer_types(sheet.sample, sheet.column_count)
                if not args.no_smart_text:
                    types = apply_smart_text(sheet.header, types)
                if args.all_text:
                    types = [ColumnType("text") for _ in types]

                if not sheet.sample and args.limit == 0:
                    console.warn("跳过空表 %s（sheet: %s）" % (table_name, sheet.sheet_name))
                    continue

                table_started = time.time()
                comment = "%s → %s" % (os.path.basename(sheet.source), sheet.sheet_name)
                rows_written = writer.write_table(
                    table_name, sheet.header, types, sheet.rows, comment=comment)
                elapsed = (time.time() - table_started) * 1000
                total_rows += rows_written
                table_rows.append([sheet.sheet_name, table_name, rows_written,
                                   len(sheet.header), "%.0f ms" % elapsed])
                console.success("%s ← %s（%d 行 / %d 列）" % (
                    table_name, sheet.sheet_name, rows_written, len(sheet.header)))
                if args.verbose:
                    for name, ctype in zip(sheet.header, types):
                        console.info("    %-24s %s" % (name, ctype))

            if not args.dry_run:
                writer.epilogue()
        finally:
            handle.close()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        console.error(str(exc))
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        console.error("已中断")
        return 130

    elapsed = time.time() - started
    if not table_rows:
        console.warn("没有可转换的数据（检查 --sheet 过滤条件或输入文件内容）")

    console.write()
    console.title("汇总")
    console.summary(table_rows, ["Sheet", "表名", "行数", "列数", "耗时"])
    console.write("  共 %d 张表 / %d 行，用时 %.2f 秒" % (len(table_rows), total_rows, elapsed))

    if args.dry_run:
        console.warn("dry-run：未写出文件")
    else:
        console.success("已生成 %s" % os.path.abspath(output_path))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
