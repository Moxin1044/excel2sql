# -*- coding: utf-8 -*-
"""SQL 写出：流式、分批、低内存。"""


class SqlWriter:
    """把 sheet 数据流式写成 SQL 语句。"""

    def __init__(self, handle, dialect, batch_size=500, drop=False,
                 add_id=False, limit=0, create=True, insert=True):
        self.handle = handle
        self.dialect = dialect
        self.batch_size = max(1, int(batch_size))
        self.drop = drop
        self.add_id = add_id
        self.limit = int(limit or 0)
        self.create = create
        self.insert = insert

    # ---------- 基础写出 ----------

    def _line(self, text=""):
        self.handle.write(text + "\n")

    def preamble(self):
        for line in self.dialect.preamble():
            self._line(line)

    def epilogue(self):
        for line in self.dialect.epilogue():
            self._line(line)

    # ---------- 单表 ----------

    def write_table(self, table_name, header, types, rows, comment=None):
        """写出一张表的 DDL + DML，返回实际写入的行数。"""
        if comment:
            self._line("-- %s" % comment)

        columns = list(zip(header, types))
        written = 0

        if self.create:
            if self.drop:
                self._line(self.dialect.drop_table(table_name))
            if self.add_id:
                id_name, id_definition = self.dialect.primary_key_clause()
                definitions = ["  %s %s" % (self.dialect.quote_ident(id_name), id_definition)]
                definitions += [
                    "  %s %s" % (self.dialect.quote_ident(name), self.dialect.type_name(ctype))
                    for name, ctype in columns
                ]
                self._line("CREATE TABLE IF NOT EXISTS %s (" % self.dialect.quote_ident(table_name))
                self._line(",\n".join(definitions))
                suffix = ""
                if self.dialect.supports_engine:
                    suffix = " ENGINE=%s DEFAULT CHARSET=%s" % (self.dialect.engine, self.dialect.charset)
                self._line(")%s;" % suffix)
            else:
                self._line(self.dialect.create_table(table_name, columns))
            self._line()

        if self.insert and header:
            column_names = [name for name, _ in columns]
            if self.add_id:
                column_names = [self.dialect.primary_key_clause()[0]] + column_names
            written = self._write_rows(table_name, column_names, columns, rows)
            self._line()

        return written

    def _write_rows(self, table_name, column_names, columns, rows):
        head = self.dialect.insert_head(table_name, column_names)
        id_name = self.dialect.primary_key_clause()[0] if self.add_id else None
        id_value = 1

        batch = []
        written = 0
        for row in rows:
            if self.limit and written + len(batch) >= self.limit:
                break
            if id_name is not None:
                values = [str(id_value)]
                id_value += 1
            else:
                values = []
            for index, (_, ctype) in enumerate(columns):
                value = row[index] if index < len(row) else None
                values.append(self.dialect.literal(value, ctype))
            batch.append("(%s)" % ", ".join(values))

            if len(batch) >= self.batch_size:
                self._flush(head, batch)
                written += len(batch)
                batch = []

        if batch:
            self._flush(head, batch)
            written += len(batch)
        return written

    def _flush(self, head, batch):
        self._line(head)
        self._line(",\n".join(batch) + ";")
        self.handle.flush()
