# -*- coding: utf-8 -*-
"""输入读取：Excel(.xlsx/.xls) / CSV，流式产出，采样用于类型推断。"""

import csv
import itertools
import os

from .infer import parse_temporal  # noqa: F401  (对外复用)


def normalize_cell(value):
    """把原始单元格值规范化为：None / str / int / float / bool / date / datetime / time"""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return value


def clean_header(raw_header):
    """生成列名：空列名补 col_N，重名加后缀。"""
    names = []
    seen = {}
    for index, cell in enumerate(raw_header):
        name = "" if cell is None else str(cell).strip()
        if not name:
            name = "col_%d" % (index + 1)
        if name in seen:
            seen[name] += 1
            name = "%s_%d" % (name, seen[name])
        else:
            seen[name] = 0
        names.append(name)
    return names


def trim_trailing_empty(values):
    """去掉行尾的空单元格（保持列宽不变）"""
    end = len(values)
    while end > 0 and values[end - 1] is None:
        end -= 1
    return list(values[:end])


class SheetData:
    """一个待转换的 sheet（表头 + 采样 + 完整行迭代器）"""

    def __init__(self, source, sheet_name, header, sample, rows):
        self.source = source
        self.sheet_name = sheet_name
        self.header = header
        self.sample = sample
        self.rows = rows

    @property
    def column_count(self):
        return len(self.header)


def _open_xlsx(path):
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "读取 .xlsx 需要 openpyxl：pip install openpyxl"
        ) from exc
    return openpyxl.load_workbook(path, read_only=True, data_only=True)


def _xlsx_sheets(path, sample_size, sheet_filter):
    workbook = _open_xlsx(path)
    try:
        for worksheet in workbook.worksheets:
            if sheet_filter and worksheet.title not in sheet_filter:
                continue
            yield from _sheets_from_row_iterator(
                path, worksheet.title, worksheet.iter_rows(values_only=True), sample_size
            )
    finally:
        workbook.close()


def _sheets_from_row_iterator(source, sheet_name, row_iterator, sample_size):
    """从原始行迭代器构建 SheetData（先读表头与采样，再流式续读）"""
    iterator = iter(row_iterator)
    header = None
    for raw_row in iterator:
        values = trim_trailing_empty([normalize_cell(cell) for cell in raw_row])
        if not values:
            continue
        header = clean_header(values)
        break
    if header is None:
        return

    column_count = len(header)

    def _normalize(raw_row):
        values = trim_trailing_empty([normalize_cell(cell) for cell in raw_row])
        values = values + [None] * (column_count - len(values))
        return values[:column_count]

    sample = []
    for raw_row in iterator:
        values = _normalize(raw_row)
        if all(value is None for value in values):
            continue
        sample.append(values)
        if len(sample) >= sample_size:
            break

    def _all_rows():
        for row in sample:
            yield row
        for raw_row in iterator:
            values = _normalize(raw_row)
            if all(value is None for value in values):
                continue
            yield values

    yield SheetData(source, sheet_name, header, sample, _all_rows())


def _csv_sheets(path, sample_size, sheet_filter):
    if sheet_filter and "csv" not in sheet_filter:
        return
    encoding = None
    for candidate in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=candidate, newline="") as handle:
                handle.read(4096)
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue
    if encoding is None:
        raise RuntimeError("无法识别 CSV 文件编码（尝试过 utf-8 / gbk）：%s" % path)

    with open(path, "r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle)
        yield from _sheets_from_row_iterator(path, "csv", (tuple(row) for row in reader), sample_size)


def _xls_sheets(path, sample_size, sheet_filter):
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError(
            "读取 .xls 需要 xlrd：pip install xlrd（或另存为 .xlsx）"
        ) from exc
    workbook = xlrd.open_workbook(path)
    for sheet in workbook.sheets():
        if sheet_filter and sheet.name not in sheet_filter:
            continue
        rows = (
            tuple(sheet.row_values(index)) for index in range(sheet.nrows)
        )
        yield from _sheets_from_row_iterator(path, sheet.name, rows, sample_size)


def iter_sheets(paths, sample_size=1000, sheet_filter=None):
    """遍历多个输入文件的所有 sheet，产出 SheetData。"""
    for path in paths:
        if not os.path.exists(path):
            raise FileNotFoundError("输入文件不存在：%s" % path)
        extension = os.path.splitext(path)[1].lower()
        if extension == ".xlsx":
            yield from _xlsx_sheets(path, sample_size, sheet_filter)
        elif extension == ".xls":
            yield from _xls_sheets(path, sample_size, sheet_filter)
        elif extension == ".csv":
            yield from _csv_sheets(path, sample_size, sheet_filter)
        else:
            raise ValueError("不支持的输入格式：%s（支持 .xlsx / .xls / .csv）" % extension)
