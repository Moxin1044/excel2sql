# -*- coding: utf-8 -*-
"""列类型模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnType:
    """推断出的列类型（与具体方言解耦）。"""

    kind: str          # int | bigint | decimal | float | bool | date | datetime | time | varchar | text | longtext
    length: int = 0    # varchar 长度
    precision: int = 0  # decimal 总位数
    scale: int = 0      # decimal 小数位

    def __str__(self):
        if self.kind == "varchar":
            return "VARCHAR(%d)" % self.length
        if self.kind == "decimal":
            return "DECIMAL(%d,%d)" % (self.precision, self.scale)
        return self.kind.upper()

    @property
    def is_numeric(self):
        return self.kind in ("int", "bigint", "decimal", "float")
