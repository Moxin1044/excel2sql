# -*- coding: utf-8 -*-
"""SQL 方言适配：标识符引用、字面量转义、类型映射、事务包装。"""

from datetime import date, datetime, time as dtime
from decimal import Decimal

from .columntype import ColumnType

# 数值型整数上限（超过即用 BIGINT）
INT32_MAX = 2147483647
INT64_DIGITS = 19  # 超过这个位数的"数字字符串"按文本处理，避免精度丢失


class Dialect:
    """方言基类，子类实现具体细节。"""

    name = "base"
    supports_engine = False
    supports_charset = False
    string_escapes_backslash = False

    # ---------- 标识符 ----------

    def quote_ident(self, name):
        raise NotImplementedError

    # ---------- 类型映射 ----------

    def type_name(self, column_type):
        kind = column_type.kind
        if kind == "bigint":
            return "BIGINT"
        if kind == "decimal":
            return "DECIMAL(%d,%d)" % (column_type.precision, column_type.scale)
        if kind == "float":
            return "DOUBLE"
        if kind == "varchar":
            return "VARCHAR(%d)" % column_type.length
        if kind == "longtext":
            return "LONGTEXT"
        return {
            "int": "INT",
            "bool": "TINYINT(1)",
            "date": "DATE",
            "datetime": "DATETIME",
            "time": "TIME",
            "text": "TEXT",
        }[kind]

    # ---------- 字面量 ----------

    def escape_string(self, value):
        text = value.replace("\x00", "")
        if self.string_escapes_backslash:
            text = (
                text.replace("\\", "\\\\")
                .replace("\x1a", "\\Z")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
            )
        text = text.replace("'", "''" if not self.string_escapes_backslash else "\\'")
        return text

    def literal(self, value, column_type):
        if value is None:
            return "NULL"
        kind = column_type.kind
        if kind in ("int", "bigint"):
            return str(int(value))
        if kind == "decimal":
            return format(Decimal(str(value)), "f")
        if kind == "float":
            return repr(float(value))
        if kind == "bool":
            return "1" if value in (True, 1, "1", "true", "TRUE") else "0"
        if kind in ("date", "datetime", "time"):
            text = value.isoformat(sep=" ") if isinstance(value, datetime) else str(value)
            return "'" + self.escape_string(text) + "'"
        return "'" + self.escape_string(str(value)) + "'"

    # ---------- 语句 ----------

    def create_table(self, table, columns, if_not_exists=True):
        """columns: [(name, ColumnType), ...]"""
        if_exists = "IF NOT EXISTS " if if_not_exists else ""
        definitions = [
            "  %s %s" % (self.quote_ident(name), self.type_name(ctype))
            for name, ctype in columns
        ]
        return "CREATE TABLE %s%s (\n%s\n)" % (
            if_exists,
            self.quote_ident(table),
            ",\n".join(definitions),
        )

    def drop_table(self, table):
        return "DROP TABLE IF EXISTS %s;" % self.quote_ident(table)

    def insert_head(self, table, column_names):
        cols = ", ".join(self.quote_ident(name) for name in column_names)
        return "INSERT INTO %s (%s) VALUES" % (self.quote_ident(table), cols)

    def primary_key_clause(self):
        """自动追加自增主键列时的 (列名, 定义) """
        return "id", "INT NOT NULL AUTO_INCREMENT PRIMARY KEY"

    # ---------- 文件包装 ----------

    def preamble(self):
        return []

    def epilogue(self):
        return []


class MySQLDialect(Dialect):
    name = "mysql"
    supports_engine = True
    supports_charset = True
    string_escapes_backslash = True

    def __init__(self, engine="InnoDB", charset="utf8mb4"):
        self.engine = engine
        self.charset = charset

    def quote_ident(self, name):
        return "`" + str(name).replace("`", "``") + "`"

    def create_table(self, table, columns, if_not_exists=True):
        sql = super().create_table(table, columns, if_not_exists=if_not_exists)
        return "%s ENGINE=%s DEFAULT CHARSET=%s;" % (sql, self.engine, self.charset)

    def preamble(self):
        return [
            "SET NAMES %s;" % self.charset,
            "SET FOREIGN_KEY_CHECKS = 0;",
            "",
        ]

    def epilogue(self):
        return ["SET FOREIGN_KEY_CHECKS = 1;"]


class PostgresDialect(Dialect):
    name = "postgres"

    def quote_ident(self, name):
        return '"' + str(name).replace('"', '""') + '"'

    def type_name(self, column_type):
        kind = column_type.kind
        return {
            "int": "INTEGER",
            "bigint": "BIGINT",
            "float": "DOUBLE PRECISION",
            "bool": "BOOLEAN",
            "datetime": "TIMESTAMP",
            "time": "TIME",
            "text": "TEXT",
            "longtext": "TEXT",
        }.get(kind, super().type_name(column_type))

    def literal(self, value, column_type):
        if column_type.kind == "bool" and value is not None:
            return "TRUE" if value in (True, 1, "1", "true", "TRUE") else "FALSE"
        return super().literal(value, column_type)

    def primary_key_clause(self):
        return "id", "BIGSERIAL PRIMARY KEY"

    def create_table(self, table, columns, if_not_exists=True):
        return super().create_table(table, columns, if_not_exists=if_not_exists) + ";"

    def preamble(self):
        return ["BEGIN;", ""]

    def epilogue(self):
        return ["COMMIT;"]


class SQLiteDialect(Dialect):
    name = "sqlite"

    def quote_ident(self, name):
        return '"' + str(name).replace('"', '""') + '"'

    def type_name(self, column_type):
        kind = column_type.kind
        if kind == "bigint":
            return "INTEGER"
        if kind == "decimal":
            return "NUMERIC"
        if kind == "float":
            return "REAL"
        if kind == "bool":
            return "INTEGER"
        if kind == "varchar":
            return "TEXT"
        if kind in ("date", "datetime", "time", "longtext"):
            return "TEXT"
        return {"int": "INTEGER", "text": "TEXT"}[kind]

    def primary_key_clause(self):
        return "id", "INTEGER PRIMARY KEY AUTOINCREMENT"

    def create_table(self, table, columns, if_not_exists=True):
        return super().create_table(table, columns, if_not_exists=if_not_exists) + ";"

    def preamble(self):
        return ["PRAGMA foreign_keys=OFF;", "BEGIN TRANSACTION;", ""]

    def epilogue(self):
        return ["COMMIT;"]


DIALECTS = {
    "mysql": MySQLDialect,
    "postgres": PostgresDialect,
    "postgresql": PostgresDialect,
    "pg": PostgresDialect,
    "sqlite": SQLiteDialect,
    "sqlite3": SQLiteDialect,
}


def get_dialect(name, **kwargs):
    """按名称构造方言实例；未知方言抛 ValueError。"""
    key = str(name or "mysql").strip().lower()
    if key not in DIALECTS:
        raise ValueError(
            "不支持的方言：%s（可选：mysql / postgres / sqlite）" % name
        )
    dialect_class = DIALECTS[key]
    if dialect_class is MySQLDialect:
        return dialect_class(**kwargs)
    return dialect_class()
