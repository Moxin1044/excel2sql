# excel2sql

将 Excel 文件（`.xlsx` / `.xls`）转换为 MySQL 的 SQL 文件，自动生成 `CREATE TABLE` 和 `INSERT INTO` 语句。

## 特性

- 自动类型推断：根据列数据推断 `INT` / `BIGINT` / `DECIMAL` / `DATE` / `DATETIME` / `TINYINT(1)` / `VARCHAR(n)` / `TEXT`
- 多 Sheet 支持：每个 sheet 生成一张表，默认转换全部 sheet
- 字段名/表名清洗：中文、空格、特殊字符统一用反引号包裹，重复列名自动去重
- 转义安全：字符串中的单引号、反斜杠自动转义，空值转为 `NULL`
- 批量 INSERT：可配置每条 INSERT 语句包含的行数，避免超大 SQL 文件卡顿
- 可配置字符集（默认 `utf8mb4`）和存储引擎（默认 `InnoDB`）

## 安装

```bash
git clone https://github.com/Moxin1044/excel2sql.git
cd excel2sql
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## 使用

```bash
./venv/bin/python excel2sql.py 输入文件.xlsx
```

默认输出到与输入文件同名的 `.sql` 文件（例如 `输入文件.sql`）。

### 参数说明

| 参数 | 说明 | 默认值 |
|---|---|---|
| `-o, --output` | 指定输出 SQL 文件路径 | 输入文件名 + `.sql` |
| `--sheet` | 只转换指定的 sheet，不填则转换全部 | 全部 sheet |
| `--charset` | 表字符集 | `utf8mb4` |
| `--engine` | 存储引擎 | `InnoDB` |
| `--batch-size` | 每条 `INSERT` 语句包含的行数 | `500` |
| `--drop` | 生成 `DROP TABLE IF EXISTS` 语句 | 不生成 |

### 示例

```bash
# 转换全部 sheet，生成 test.sql
./venv/bin/python excel2sql.py test.xlsx

# 只转换名为"员工表"的 sheet，并加上 DROP TABLE
./venv/bin/python excel2sql.py test.xlsx --sheet 员工表 --drop -o employees.sql

# 每 200 行一条 INSERT，适合大表
./venv/bin/python excel2sql.py big_data.xlsx --batch-size 200
```

## 类型推断规则

- 整数列 → `INT`（超过 `2147483647` 则用 `BIGINT`）
- 布尔列 → `TINYINT(1)`
- 浮点列 → `DECIMAL(precision, scale)`，scale 根据实际小数位数推断
- 日期列（无时间部分）→ `DATE`；含时间部分 → `DATETIME`
- 文本列 → 按最大长度落在 32/64/128/255 档位使用 `VARCHAR(n)`；超过 255 用 `TEXT`/`LONGTEXT`

推断基于对整列非空值的扫描，遇到无法判定的情况会退化为更宽松的类型（如 `VARCHAR(255)`），保证生成的 SQL 至少能正确导入。

## 依赖

- Python 3.9+
- pandas
- openpyxl

## License

MIT
