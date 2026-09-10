# -*- coding: utf-8 -*-
"""方言：标识符引用、转义、类型映射。"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from excel2sql.columntype import ColumnType
from excel2sql.dialects import get_dialect


def test_mysql_identifier_and_escaping():
    dialect = get_dialect("mysql")
    assert dialect.quote_ident("用户表") == "`用户表`"
    assert dialect.quote_ident("a`b") == "`a``b`"
    # 反斜杠与单引号都要转义
    assert dialect.escape_string("it's a\\b") == "it\\'s a\\\\b"
    assert dialect.escape_string("换行\n结束") == "换行\\n结束"


def test_mysql_literals():
    dialect = get_dialect("mysql")
    assert dialect.literal(None, ColumnType("int")) == "NULL"
    assert dialect.literal(3, ColumnType("int")) == "3"
    assert dialect.literal(Decimal("1.50"), ColumnType("decimal")) == "1.50"
    assert dialect.literal(True, ColumnType("bool")) == "1"
    assert dialect.literal(date(2023, 1, 5), ColumnType("date")) == "'2023-01-05'"
    assert dialect.literal(datetime(2023, 1, 5, 10, 30),
                           ColumnType("datetime")) == "'2023-01-05 10:30:00'"


def test_mysql_decimal_literal_has_no_scientific_notation():
    dialect = get_dialect("mysql")
    value = Decimal("12345678901234567890.12")
    assert dialect.literal(value, ColumnType("decimal")) == "12345678901234567890.12"


def test_mysql_create_table_uses_engine_and_charset():
    dialect = get_dialect("mysql", engine="InnoDB", charset="utf8mb4")
    sql = dialect.create_table("t", [("id", ColumnType("int")),
                                     ("名字", ColumnType("varchar", 64))])
    assert "`id` INT" in sql
    assert "`名字` VARCHAR(64)" in sql
    assert "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;" in sql


def test_postgres_quoting_escaping_and_types():
    dialect = get_dialect("postgres")
    assert dialect.quote_ident('a"b') == '"a""b"'
    assert dialect.escape_string("it's") == "it''s"
    assert dialect.literal(True, ColumnType("bool")) == "TRUE"
    assert dialect.literal(False, ColumnType("bool")) == "FALSE"
    assert dialect.type_name(ColumnType("bool")) == "BOOLEAN"
    assert dialect.type_name(ColumnType("datetime")) == "TIMESTAMP"
    assert dialect.type_name(ColumnType("float")) == "DOUBLE PRECISION"
    assert dialect.type_name(ColumnType("int")) == "INTEGER"


def test_postgres_strips_nul_bytes():
    dialect = get_dialect("postgres")
    assert dialect.escape_string("a\x00b") == "ab"


def test_sqlite_types_and_wrapping():
    dialect = get_dialect("sqlite")
    assert dialect.type_name(ColumnType("bigint")) == "INTEGER"
    assert dialect.type_name(ColumnType("decimal", precision=6, scale=2)) == "NUMERIC"
    assert dialect.type_name(ColumnType("varchar", 64)) == "TEXT"
    assert dialect.type_name(ColumnType("date")) == "TEXT"
    assert "PRAGMA foreign_keys=OFF;" in dialect.preamble()[0]
    assert dialect.primary_key_clause() == ("id", "INTEGER PRIMARY KEY AUTOINCREMENT")


def test_unknown_dialect_raises_value_error():
    with pytest.raises(ValueError):
        get_dialect("oracle")


def test_dialect_aliases():
    assert get_dialect("pg").name == "postgres"
    assert get_dialect("postgresql").name == "postgres"
    assert get_dialect("sqlite3").name == "sqlite"
