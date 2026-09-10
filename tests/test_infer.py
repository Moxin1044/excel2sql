# -*- coding: utf-8 -*-
"""类型推断测试。"""

from datetime import date, datetime, time

from excel2sql.infer import apply_smart_text, infer_types


def infer_one(values):
    return infer_types([(value,) for value in values], 1)[0]


def test_integer_column_is_int():
    assert infer_one([1, 2, 3]).kind == "int"


def test_large_integer_is_bigint():
    assert infer_one([2 ** 40]).kind == "bigint"


def test_leading_zero_becomes_text():
    # 007 这类编号必须保留前导零，不能被当成数值
    assert infer_one(["007", "012"]).kind == "varchar"


def test_too_many_digits_becomes_text():
    assert infer_one(["123456789012345678"]).kind == "varchar"


def test_decimal_precision_is_exact():
    column = infer_one(["123.45", "0.10"])
    assert column.kind == "decimal"
    assert column.precision == 5
    assert column.scale == 2


def test_float_values_use_decimal():
    column = infer_one([1.5, 2.25])
    assert column.kind == "decimal"
    assert column.scale == 2


def test_bool_from_native_and_text():
    assert infer_one([True, False]).kind == "bool"
    assert infer_one(["true", "false"]).kind == "bool"
    assert infer_one(["是", "否"]).kind == "bool"


def test_date_and_datetime_detection():
    assert infer_one([date(2023, 1, 5), date(2023, 2, 6)]).kind == "date"
    assert infer_one(["2023-01-05", "2023/02/06"]).kind == "date"
    assert infer_one(["2023-01-05 10:00:00"]).kind == "datetime"
    assert infer_one([datetime(2023, 1, 5, 0, 0, 0)]).kind == "date"  # 全为零点 → DATE
    assert infer_one([time(10, 30)]).kind == "time"


def test_mixed_types_fall_back_to_text():
    assert infer_one([1, "abc"]).kind == "varchar"
    assert infer_one([1, "2023-01-05"]).kind == "varchar"


def test_empty_column_defaults_to_varchar_255():
    column = infer_one([None, None])
    assert column.kind == "varchar"
    assert column.length == 255


def test_text_size_buckets():
    assert infer_one(["x" * 300]).kind == "text"
    assert infer_one(["x" * 70000]).kind == "longtext"


def test_smart_text_for_phone_like_headers():
    types = infer_types([(1234567890, 12.5)], 2)
    assert types[0].kind == "int"
    adjusted = apply_smart_text(["手机号", "余额"], types)
    assert adjusted[0].kind == "text"
    assert adjusted[1].kind == "decimal"


def test_smart_text_keeps_normal_columns():
    types = infer_types([(1,)], 1)
    assert apply_smart_text(["数量"], types)[0].kind == "int"


def test_quoted_and_escaped_text_survives_inference():
    column = infer_one(["it's a \\ test", "中文内容"])
    assert column.kind == "varchar"
