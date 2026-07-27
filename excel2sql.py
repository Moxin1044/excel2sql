#!/usr/bin/env python3
"""Excel -> MySQL SQL 转换工具

将 .xlsx/.xls 文件转换为 CREATE TABLE + INSERT INTO 语句。
第一行默认作为表头（列名）。多个 sheet 会分别生成多张表。
"""

import argparse
import re
import sys
import warnings
from datetime import date, datetime, time as dtime

import pandas as pd


def quote_ident(name: str) -> str:
    """用反引号包裹标识符，转义内部反引号。中文/空格/特殊字符原样保留。"""
    name = str(name).strip()
    return "`" + name.replace("`", "``") + "`"


def sanitize_table_name(sheet_name: str, source_stem: str) -> str:
    name = str(sheet_name).strip()
    if not name or name.lower().startswith("sheet") is False and name == "":
        name = source_stem
    return name


def escape_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def infer_decimal_scale(series: pd.Series) -> int:
    """根据浮点值的小数位数估算 DECIMAL 的 scale，最小 2，最大 6。"""
    max_scale = 0
    for v in series.dropna():
        s = f"{v:.10f}".rstrip("0")
        if "." in s:
            scale = len(s.split(".")[1])
            max_scale = max(max_scale, scale)
        if max_scale >= 6:
            break
    return min(max(max_scale, 2), 6)


def infer_column_type(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "VARCHAR(255)"

    if pd.api.types.is_bool_dtype(series):
        return "TINYINT(1)"

    if pd.api.types.is_integer_dtype(series):
        max_abs = int(non_null.abs().max())
        if max_abs > 2147483647:
            return "BIGINT"
        return "INT"

    if pd.api.types.is_float_dtype(series):
        # 整数值也可能被 pandas 读成 float（因为有 NaN），先检查是否全是整数
        if (non_null % 1 == 0).all():
            max_abs = int(non_null.abs().max())
            return "BIGINT" if max_abs > 2147483647 else "INT"
        scale = infer_decimal_scale(non_null)
        int_digits = len(str(int(non_null.abs().max())))
        precision = min(int_digits + scale, 65)
        return f"DECIMAL({precision},{scale})"

    if pd.api.types.is_datetime64_any_dtype(series):
        times = non_null.dt.time
        if all(t == dtime(0, 0, 0) for t in times):
            return "DATE"
        return "DATETIME"

    # object 列：尝试数值 / 日期 / 布尔 推断
    as_numeric = pd.to_numeric(non_null, errors="coerce")
    if as_numeric.notna().all():
        if (as_numeric % 1 == 0).all():
            max_abs = int(as_numeric.abs().max())
            return "BIGINT" if max_abs > 2147483647 else "INT"
        scale = infer_decimal_scale(as_numeric)
        int_digits = len(str(int(as_numeric.abs().max())))
        precision = min(int_digits + scale, 65)
        return f"DECIMAL({precision},{scale})"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        as_datetime = pd.to_datetime(non_null, errors="coerce")
    if as_datetime.notna().all():
        times = as_datetime.dt.time
        if all(t == dtime(0, 0, 0) for t in times):
            return "DATE"
        return "DATETIME"

    max_len = non_null.astype(str).map(len).max()
    if max_len <= 255:
        # 预留一些余量，按常见档位取整
        for cap in (32, 64, 128, 255):
            if max_len <= cap:
                return f"VARCHAR({cap})"
    if max_len <= 65535:
        return "TEXT"
    return "LONGTEXT"


def format_value(value, col_type: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return "NULL"

    if col_type.startswith(("INT", "BIGINT", "TINYINT")):
        return str(int(value))

    if col_type.startswith("DECIMAL"):
        return f"{float(value):.10f}".rstrip("0").rstrip(".") or "0"

    if col_type == "DATE":
        if isinstance(value, (pd.Timestamp, datetime, date)):
            return f"'{value.strftime('%Y-%m-%d')}'"
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return "NULL"
        return f"'{parsed.strftime('%Y-%m-%d')}'"

    if col_type == "DATETIME":
        if isinstance(value, (pd.Timestamp, datetime)):
            return f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'"
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return "NULL"
        return f"'{parsed.strftime('%Y-%m-%d %H:%M:%S')}'"

    # VARCHAR / TEXT / LONGTEXT 及兜底情况
    return f"'{escape_string(str(value))}'"


def build_column_names(columns) -> list:
    names = []
    seen = {}
    for i, col in enumerate(columns):
        name = str(col).strip()
        if not name or name.lower().startswith("unnamed"):
            name = f"col_{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        names.append(name)
    return names


def generate_sql_for_sheet(
    df: pd.DataFrame,
    table_name: str,
    charset: str,
    engine: str,
    batch_size: int,
    drop_if_exists: bool,
) -> str:
    lines = []
    col_names = build_column_names(df.columns)
    col_types = [infer_column_type(df[col]) for col in df.columns]

    if drop_if_exists:
        lines.append(f"DROP TABLE IF EXISTS {quote_ident(table_name)};")

    lines.append(f"CREATE TABLE IF NOT EXISTS {quote_ident(table_name)} (")
    col_defs = [
        f"  {quote_ident(name)} {ctype}" for name, ctype in zip(col_names, col_types)
    ]
    lines.append(",\n".join(col_defs))
    lines.append(f") ENGINE={engine} DEFAULT CHARSET={charset};")
    lines.append("")

    if len(df) > 0:
        quoted_cols = ", ".join(quote_ident(name) for name in col_names)
        rows = df.to_records(index=False).tolist()
        raw_columns = list(df.columns)

        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            value_tuples = []
            for row in batch:
                values = [
                    format_value(row[i], col_types[i]) for i in range(len(raw_columns))
                ]
                value_tuples.append(f"({', '.join(values)})")
            lines.append(
                f"INSERT INTO {quote_ident(table_name)} ({quoted_cols}) VALUES"
            )
            lines.append(",\n".join(value_tuples) + ";")
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Excel 转 MySQL SQL 文件工具")
    parser.add_argument("input", help="输入 Excel 文件路径 (.xlsx/.xls)")
    parser.add_argument("-o", "--output", help="输出 SQL 文件路径（默认与输入同名，后缀改为 .sql）")
    parser.add_argument("--sheet", help="仅转换指定 sheet（默认转换全部 sheet）")
    parser.add_argument("--charset", default="utf8mb4", help="表字符集，默认 utf8mb4")
    parser.add_argument("--engine", default="InnoDB", help="存储引擎，默认 InnoDB")
    parser.add_argument("--batch-size", type=int, default=500, help="每条 INSERT 语句包含的行数，默认 500")
    parser.add_argument("--drop", action="store_true", help="生成 DROP TABLE IF EXISTS 语句")
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or re.sub(r"\.(xlsx|xls)$", ".sql", input_path, flags=re.IGNORECASE)
    if output_path == input_path:
        output_path = input_path + ".sql"

    try:
        sheets = pd.read_excel(input_path, sheet_name=args.sheet if args.sheet else None)
    except Exception as e:
        print(f"读取 Excel 失败: {e}", file=sys.stderr)
        sys.exit(1)

    if isinstance(sheets, pd.DataFrame):
        sheets = {args.sheet: sheets}

    source_stem = re.sub(r"\.(xlsx|xls)$", "", input_path.split("/")[-1], flags=re.IGNORECASE)

    all_sql = []
    all_sql.append("SET NAMES utf8mb4;")
    all_sql.append("SET FOREIGN_KEY_CHECKS = 0;")
    all_sql.append("")

    for sheet_name, df in sheets.items():
        df = df.dropna(how="all")
        if df.empty:
            continue
        table_name = sanitize_table_name(sheet_name, source_stem)
        sql = generate_sql_for_sheet(
            df,
            table_name,
            charset=args.charset,
            engine=args.engine,
            batch_size=args.batch_size,
            drop_if_exists=args.drop,
        )
        all_sql.append(f"-- Sheet: {sheet_name} -> Table: {table_name} ({len(df)} 行)")
        all_sql.append(sql)
        all_sql.append("")

    all_sql.append("SET FOREIGN_KEY_CHECKS = 1;")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_sql))

    print(f"已生成: {output_path}")


if __name__ == "__main__":
    main()
