# -*- coding: utf-8 -*-
"""文本列长度策略测试：默认 TEXT 不截断；--varchar 全文件扫描精确取档。"""

import sqlite3

from openpyxl import Workbook

from excel2sql.cli import main


def make_workbook_with_hidden_long_value(path):
    """采样（前 100 行）只能看到短值，第 1101 行藏了一个 200 字符的长值。"""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "备注表"
    sheet.append(["编号", "备注"])
    for index in range(1200):
        sheet.append(["N%04d" % index, "长" * 200 if index == 1100 else "短"])
    workbook.save(str(path))


def read_sql(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def test_default_mode_uses_text_and_never_truncates(tmp_path):
    source = tmp_path / "long.xlsx"
    make_workbook_with_hidden_long_value(source)
    output = tmp_path / "safe.sql"

    assert main([str(source), "-o", str(output), "--dialect", "sqlite",
                 "--sample-size", "100", "-q"]) == 0
    sql = read_sql(output)
    assert '"备注" TEXT' in sql      # 默认不限长
    assert "VARCHAR" not in sql

    connection = sqlite3.connect(":memory:")
    connection.executescript(sql)
    longest = connection.execute('SELECT MAX(LENGTH("备注")) FROM "备注表"').fetchone()[0]
    assert longest == 200
    connection.close()


def test_varchar_mode_scans_whole_file_for_exact_length(tmp_path):
    source = tmp_path / "long.xlsx"
    make_workbook_with_hidden_long_value(source)
    output = tmp_path / "varchar.sql"

    # 用 mysql 方言才能看到 VARCHAR(n)（sqlite 方言下 VARCHAR 会映射为 TEXT）
    assert main([str(source), "-o", str(output), "--sample-size", "100",
                 "--varchar", "-q"]) == 0
    sql = read_sql(output)
    # 只看采样会错判成 VARCHAR(16)，全文件扫描后应得到 VARCHAR(255)
    assert "`备注` VARCHAR(255)" in sql
    assert "`编号` VARCHAR(16)" in sql
