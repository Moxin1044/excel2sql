# -*- coding: utf-8 -*-
"""字段类型推断：基于采样（默认 1000 行），精确处理精度与精度丢失风险。"""

import re
from datetime import date, datetime, time as dtime
from decimal import Decimal, InvalidOperation

from .columntype import ColumnType

INT32_MAX = 2147483647
MAX_SAFE_DIGITS = 15      # 超过 15 位数字（近似 IEEE754 安全整数）按文本处理
MAX_SCALE = 6
MAX_PRECISION = 65
VARCHAR_BUCKETS = (16, 32, 64, 128, 255)

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y年%m月%d日",
    "%d/%m/%Y",
    "%m/%d/%Y",
)
_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
)
_TIME_FORMATS = ("%H:%M:%S", "%H:%M")

_BOOL_TRUE = {"true", "yes", "y", "是"}
_BOOL_FALSE = {"false", "no", "n", "否"}


def parse_temporal(text):
    """尝试把字符串解析为 date / datetime / time，失败返回 None。"""
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def parse_decimal(text):
    """数字字符串 → Decimal；非数字返回 None。"""
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError, ArithmeticError):
        return None
    if not value.is_finite():
        return None
    return value


class ColumnProfiler:
    """单列采样画像。"""

    def __init__(self):
        self.empty = True
        self.flags = set()
        self.max_len = 0
        self.int_digits = 0
        self.decimal_scale = 0
        self.max_abs = Decimal(0)
        self.leading_zero = False
        self.all_times_midnight = True

    def feed(self, value):
        if value is None:
            return
        self.empty = False

        if isinstance(value, bool):
            self.flags.add("bool")
            return
        if isinstance(value, datetime):
            self.flags.add("datetime")
            if value.time() != dtime(0, 0, 0):
                self.all_times_midnight = False
            return
        if isinstance(value, date):
            self.flags.add("date")
            return
        if isinstance(value, dtime):
            self.flags.add("time")
            return
        if isinstance(value, int):
            self.flags.add("number")
            self._track_number(Decimal(value))
            return
        if isinstance(value, float):
            self.flags.add("number")
            self._track_number(Decimal(repr(value)))
            return

        text = str(value).strip()
        if not text:
            return

        lowered = text.lower()
        if lowered in _BOOL_TRUE or lowered in _BOOL_FALSE:
            self.flags.add("bool")
            return

        numeric = parse_decimal(text)
        if numeric is not None:
            self.flags.add("number")
            if text[0] == "0" and not text.startswith(("0.", "0。")) and len(text.lstrip("+-")) > 1:
                self.leading_zero = True
            self._track_number(numeric)
            return

        temporal = parse_temporal(text)
        if temporal is not None:
            if isinstance(temporal, datetime):
                self.flags.add("datetime")
                if temporal.time() != dtime(0, 0, 0):
                    self.all_times_midnight = False
            elif isinstance(temporal, date):
                self.flags.add("date")
            else:
                self.flags.add("time")
            return

        self.flags.add("text")
        self.max_len = max(self.max_len, len(text))

    def _track_number(self, value):
        value = value.copy_abs()
        if value > self.max_abs:
            self.max_abs = value
        digits = len(str(int(value)))
        self.int_digits = max(self.int_digits, digits)
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < 0:
            self.decimal_scale = max(self.decimal_scale, -exponent)

    # ---------- 结论 ----------

    def resolve(self):
        if self.empty:
            return ColumnType("varchar", length=255)

        flags = self.flags
        if flags == {"bool"}:
            return ColumnType("bool")
        if flags <= {"number"}:
            if self.leading_zero or self.int_digits > MAX_SAFE_DIGITS:
                return self._text_type()
            if self.decimal_scale == 0:
                if self.max_abs > INT32_MAX:
                    return ColumnType("bigint")
                return ColumnType("int")
            scale = min(self.decimal_scale, MAX_SCALE)
            precision = min(self.int_digits + scale, MAX_PRECISION)
            return ColumnType("decimal", precision=precision, scale=scale)
        if flags <= {"date"}:
            return ColumnType("date")
        if flags <= {"datetime"}:
            if self.all_times_midnight:
                return ColumnType("date")
            return ColumnType("datetime")
        if flags <= {"time"}:
            return ColumnType("time")
        return self._text_type()

    def _text_type(self):
        if self.max_len <= 255:
            for cap in VARCHAR_BUCKETS:
                if self.max_len <= cap:
                    return ColumnType("varchar", length=cap)
        if self.max_len <= 65535:
            return ColumnType("text")
        return ColumnType("longtext")


def infer_types(sample_rows, column_count):
    """对采样行做逐列推断，返回 ColumnType 列表。"""
    profilers = [ColumnProfiler() for _ in range(column_count)]
    for row in sample_rows:
        for index in range(column_count):
            profilers[index].feed(row[index] if index < len(row) else None)
    return [profiler.resolve() for profiler in profilers]


# 列名看起来是编号/号码/账号一类的字段，强制按文本处理：
# 避免手机号、卡号、编号被当成数值而丢失前导零或语义。
SMART_TEXT_PATTERN = re.compile(
    r"(手机|电话|座机|身份证|证件|卡号|账号|帐号|编号|学号|工号|邮编|编码|代码|"
    r"phone|mobile|telephone|idcard|id_card|card_no|account|zipcode|serial|code)",
    re.IGNORECASE,
)


def apply_smart_text(header, types):
    """按列名把编号/号码类字段改为文本类型。"""
    result = list(types)
    for index, name in enumerate(header):
        if SMART_TEXT_PATTERN.search(str(name)):
            result[index] = ColumnType("text")
    return result
